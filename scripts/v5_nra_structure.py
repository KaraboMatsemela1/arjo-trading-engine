#!/usr/bin/env python3
"""Read-only OANDA H4/H1 structure acquisition for frozen V5 trigger sealing."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from v5_nra_triggers import canonical_sha, dec_text, parse_time, stamp

BASE_URL = "https://api-fxpractice.oanda.com"
INSTRUMENT = "NAS100_USD"
START = datetime(2010, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 1, 1, tzinfo=timezone.utc)
H4_REQUEST_END = datetime(2023, 12, 31, 22, tzinfo=timezone.utc)
ALIGNMENT_TIMEZONE = "America/New_York"
DAILY_ALIGNMENT = 17
WEEKLY_ALIGNMENT = "Friday"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_request_sha(params: dict[str, str]) -> str:
    return canonical_sha({"instrument": INSTRUMENT, "params": params})


def normalized_price(value: str) -> str:
    return dec_text(Decimal(value))


def normalize_candle(raw: dict[str, Any], hours: int) -> dict[str, Any] | None:
    if raw.get("complete") is not True:
        return None
    mid = raw.get("mid")
    if not isinstance(mid, dict):
        raise RuntimeError("OANDA structure candle missing MID payload")
    started = parse_time(str(raw["time"]))
    ended = started + timedelta(hours=hours)
    if started < START or ended > END:
        return None
    return {
        "time": stamp(started),
        "open": normalized_price(str(mid["o"])),
        "high": normalized_price(str(mid["h"])),
        "low": normalized_price(str(mid["l"])),
        "close": normalized_price(str(mid["c"])),
        "complete": True,
        "volume": int(raw.get("volume", 0)),
    }


def chunk_ranges(start: datetime, end: datetime, days: int) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = []
    cursor = start
    step = timedelta(days=days)
    while cursor < end:
        stop = min(cursor + step, end)
        result.append((cursor, stop))
        cursor = stop
    return result


def request_chunk(
    token: str,
    granularity: str,
    start: datetime,
    end: datetime,
    attempts: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "from": stamp(start),
        "to": stamp(end),
        "granularity": granularity,
        "price": "M",
        "smooth": "false",
        "includeFirst": "true",
        "dailyAlignment": str(DAILY_ALIGNMENT),
        "alignmentTimezone": ALIGNMENT_TIMEZONE,
        "weeklyAlignment": WEEKLY_ALIGNMENT,
    }
    encoded = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles?{encoded}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "arjo-v5-nra-structure-seal",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw_bytes = response.read()
                payload = json.loads(raw_bytes)
                candles = payload.get("candles")
                if not isinstance(candles, list):
                    raise RuntimeError("OANDA structure response missing candles list")
                return candles, {
                    "granularity": granularity,
                    "from": params["from"],
                    "to": params["to"],
                    "request_sha256": canonical_request_sha(params),
                    "response_sha256": sha_bytes(raw_bytes),
                    "response_candle_count": len(candles),
                }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = RuntimeError(f"OANDA HTTP {exc.code}: {detail}")
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last_error from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"OANDA structure request failed after retries: {last_error}")


def acquire_granularity(token: str, granularity: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if granularity == "H1":
        hours = 1
        request_end = END
        chunk_days = 120
    elif granularity == "H4":
        hours = 4
        request_end = H4_REQUEST_END
        chunk_days = 300
    else:
        raise ValueError(f"unsupported V5 structure granularity: {granularity}")
    by_time: dict[str, dict[str, Any]] = {}
    provenance: list[dict[str, Any]] = []
    for chunk_start, chunk_end in chunk_ranges(START, request_end, chunk_days):
        raw_candles, record = request_chunk(
            token,
            granularity,
            chunk_start,
            chunk_end,
        )
        record["admitted_candle_count"] = 0
        for raw in raw_candles:
            candle = normalize_candle(raw, hours)
            if candle is None:
                continue
            existing = by_time.get(candle["time"])
            if existing is not None and existing != candle:
                raise RuntimeError(
                    f"non-identical duplicate {granularity} candle at {candle['time']}"
                )
            if existing is None:
                by_time[candle["time"]] = candle
                record["admitted_candle_count"] += 1
        provenance.append(record)
    candles = [by_time[key] for key in sorted(by_time)]
    if not candles:
        raise RuntimeError(f"no complete {granularity} candles admitted")
    for candle in candles:
        started = parse_time(candle["time"])
        ended = started + timedelta(hours=hours)
        if not (START <= started < END and ended <= END):
            raise RuntimeError(f"{granularity} candle escaped frozen boundary")
    return candles, provenance


def acquire_structure() -> dict[str, Any]:
    token = os.environ.get("OANDA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("OANDA_TOKEN is required for read-only V5 structure acquisition")
    h4, h4_provenance = acquire_granularity(token, "H4")
    h1, h1_provenance = acquire_granularity(token, "H1")
    manifest = {
        "provider": "OANDA_V20_PRACTICE_READ_ONLY",
        "instrument": INSTRUMENT,
        "price": "M",
        "daily_alignment": DAILY_ALIGNMENT,
        "alignment_timezone": ALIGNMENT_TIMEZONE,
        "weekly_alignment": WEEKLY_ALIGNMENT,
        "strict_start": stamp(START),
        "strict_end_exclusive": stamp(END),
        "h4_request_end_exclusive": stamp(H4_REQUEST_END),
        "h4_rows": len(h4),
        "h1_rows": len(h1),
        "h4_sha256": canonical_sha(h4),
        "h1_sha256": canonical_sha(h1),
        "h4_request_provenance_sha256": canonical_sha(h4_provenance),
        "h1_request_provenance_sha256": canonical_sha(h1_provenance),
        "credential_exposed": False,
        "m1_requested": False,
        "bid_ask_requested": False,
        "broker_mutation": False,
    }
    manifest["manifest_sha256"] = canonical_sha(manifest)
    return {
        "h4": h4,
        "h1": h1,
        "h4_provenance": h4_provenance,
        "h1_provenance": h1_provenance,
        "manifest": manifest,
    }
