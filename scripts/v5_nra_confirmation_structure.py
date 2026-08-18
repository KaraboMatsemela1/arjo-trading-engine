#!/usr/bin/env python3
"""Read-only H4/H1 structure acquisition for V5 forward confirmation sealing."""
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
END = datetime(2026, 8, 1, tzinfo=timezone.utc)
ALIGNMENT_TIMEZONE = "America/New_York"
DAILY_ALIGNMENT = 17
WEEKLY_ALIGNMENT = "Friday"
CONFIRMATION_PROTOCOL_SHA = "d86258ba66ba9eba20ed72e57af0368b90512ec24bc8e8a42f82be5cce1910b4"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_price(value: str) -> str:
    return dec_text(Decimal(value))


def normalize_candle(raw: dict[str, Any], hours: int) -> dict[str, Any] | None:
    if raw.get("complete") is not True:
        return None
    mid = raw.get("mid")
    if not isinstance(mid, dict):
        raise RuntimeError("confirmation structure candle missing MID payload")
    started = parse_time(str(raw["time"]))
    ended = started + timedelta(hours=hours)
    # Admit only fully-contained causal structure; returned boundary candles may be dropped.
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


def chunks(start: datetime, end: datetime, days: int):
    cursor = start
    step = timedelta(days=days)
    while cursor < end:
        stop = min(cursor + step, end)
        yield cursor, stop
        cursor = stop


def request_chunk(token: str, granularity: str, start: datetime, end: datetime):
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
    request_sha = canonical_sha({"instrument": INSTRUMENT, "params": params})
    url = f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "arjo-v5-nra-forward-confirmation-structure",
        },
    )
    last: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                payload = json.loads(raw)
                candles_ = payload.get("candles")
                if not isinstance(candles_, list):
                    raise RuntimeError("OANDA confirmation structure response missing candles")
                return candles_, {
                    "granularity": granularity,
                    "from": params["from"],
                    "to": params["to"],
                    "request_sha256": request_sha,
                    "response_sha256": sha_bytes(raw),
                    "response_candle_count": len(candles_),
                }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last = RuntimeError(f"OANDA HTTP {exc.code}: {detail}")
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt < 4:
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"confirmation structure request failed: {last}")


def acquire(granularity: str):
    token = os.environ.get("OANDA_TOKEN", "").strip()
    if not token:
        raise RuntimeError("OANDA_TOKEN required")
    hours = 1 if granularity == "H1" else 4
    chunk_days = 120 if granularity == "H1" else 300
    by_time: dict[str, dict[str, Any]] = {}
    provenance: list[dict[str, Any]] = []
    for start, end in chunks(START, END, chunk_days):
        raw, record = request_chunk(token, granularity, start, end)
        record["admitted_candle_count"] = 0
        for item in raw:
            candle = normalize_candle(item, hours)
            if candle is None:
                continue
            existing = by_time.get(candle["time"])
            if existing is not None and existing != candle:
                raise RuntimeError(f"conflicting {granularity} duplicate at {candle['time']}")
            if existing is None:
                by_time[candle["time"]] = candle
                record["admitted_candle_count"] += 1
        provenance.append(record)
    candles_ = [by_time[key] for key in sorted(by_time)]
    if not candles_:
        raise RuntimeError(f"no {granularity} confirmation structure admitted")
    return candles_, provenance


def acquire_structure() -> dict[str, Any]:
    h4, h4_provenance = acquire("H4")
    h1, h1_provenance = acquire("H1")
    manifest = {
        "schema_version": 1,
        "confirmation_protocol_sha256": CONFIRMATION_PROTOCOL_SHA,
        "provider": "OANDA_V20_PRACTICE_READ_ONLY",
        "instrument": INSTRUMENT,
        "price": "M",
        "daily_alignment": DAILY_ALIGNMENT,
        "alignment_timezone": ALIGNMENT_TIMEZONE,
        "weekly_alignment": WEEKLY_ALIGNMENT,
        "structure_start": stamp(START),
        "structure_end_exclusive": stamp(END),
        "fully_contained_candles_only": True,
        "h4_rows": len(h4),
        "h1_rows": len(h1),
        "h4_sha256": canonical_sha(h4),
        "h1_sha256": canonical_sha(h1),
        "h4_request_provenance_sha256": canonical_sha(h4_provenance),
        "h1_request_provenance_sha256": canonical_sha(h1_provenance),
        "m1_requested": False,
        "bid_ask_requested": False,
        "credentials_exposed": False,
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
