#!/usr/bin/env python3
"""Acquire V4 Sharp Turn structure-only OANDA candles.

This module is deliberately incapable of requesting M1, BID, ASK, orders, trades,
or any mutation endpoint. It acquires only MID candles at the protocol-frozen
M/W/D/H1 granularities for the backward historical development interval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
START = datetime(2010, 1, 1, tzinfo=UTC)
END = datetime(2024, 1, 1, tzinfo=UTC)
BASE_URL = "https://api-fxpractice.oanda.com"
INSTRUMENT = "NAS100_USD"
GRANULARITIES = ("M", "W", "D", "H1")
WINDOW_DAYS = {"M": 30000, "W": 30000, "D": 3000, "H1": 180}
MAX_CANDLES = 5000


class V4StructureError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise V4StructureError("naive timestamp")
    return dt.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V4StructureError(f"invalid decimal {label}") from exc
    if not result.is_finite():
        raise V4StructureError(f"non-finite decimal {label}")
    return result


def verify_protocol(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(protocol)
    recorded = unsigned.pop("protocol_sha256", "")
    if recorded != PROTOCOL_SHA or canon(unsigned) != PROTOCOL_SHA:
        raise V4StructureError("V4 protocol SHA drift")
    market = protocol["market_data"]
    expected = {
        "provider": "OANDA_V20",
        "environment": "practice",
        "instrument": INSTRUMENT,
        "structure_price": "MID",
        "structure_granularities": list(GRANULARITIES),
        "smooth": False,
        "include_first": True,
        "daily_alignment_hour": 17,
        "alignment_timezone": "America/New_York",
        "weekly_alignment": "Friday",
        "historical_structure_start": "2010-01-01T00:00:00Z",
        "historical_structure_end_exclusive": "2024-01-01T00:00:00Z",
        "historical_window_classification": "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT",
        "request_m1_only_after_v4_trigger_set_is_sealed": True,
        "no_market_request_authorized_by_protocol_freeze_issue": True,
    }
    for key, value in expected.items():
        if market.get(key) != value:
            raise V4StructureError(f"V4 protocol market-data drift: {key}")
    if protocol["authorization"] != {
        "market_data_execution_for_issue_242": False,
        "backtest_execution": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }:
        raise V4StructureError("V4 execution authorization boundary drift")
    return protocol


def windows(granularity: str) -> list[tuple[datetime, datetime]]:
    if granularity not in GRANULARITIES:
        raise V4StructureError("unapproved granularity")
    step = timedelta(days=WINDOW_DAYS[granularity])
    result = []
    cursor = START
    while cursor < END:
        nxt = min(cursor + step, END)
        result.append((cursor, nxt))
        cursor = nxt
    return result


def request_params(granularity: str, start: datetime, end: datetime) -> dict[str, str]:
    if granularity not in GRANULARITIES or granularity == "M1":
        raise V4StructureError("unapproved granularity request")
    if not START <= start < end <= END:
        raise V4StructureError("request outside frozen V4 history")
    return {
        "price": "M",
        "granularity": granularity,
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": end.isoformat().replace("+00:00", "Z"),
        "smooth": "false",
        "includeFirst": "true",
        "dailyAlignment": "17",
        "alignmentTimezone": "America/New_York",
        "weeklyAlignment": "Friday",
    }


def request_payload(
    *, account: str, token: str, granularity: str, start: datetime, end: datetime, retries: int = 4
) -> tuple[bytes, str]:
    params = request_params(granularity, start, end)
    real_path = f"/v3/accounts/{account}/instruments/{INSTRUMENT}/candles"
    redacted_path = f"/v3/accounts/{{ACCOUNT}}/instruments/{INSTRUMENT}/candles"
    query = urlencode(params)
    url = f"{BASE_URL}{real_path}?{query}"
    request_sha = hashlib.sha256(
        f"{redacted_path}?{urlencode(sorted(params.items()))}".encode()
    ).hexdigest()
    for attempt in range(retries):
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Datetime-Format": "RFC3339",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=60) as response:
                return response.read(), request_sha
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise V4StructureError(f"OANDA HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt == retries - 1:
                raise V4StructureError("OANDA request failed") from exc
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def parse_page(payload: bytes, granularity: str) -> list[dict]:
    try:
        doc = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise V4StructureError("invalid OANDA JSON") from exc
    if doc.get("instrument") != INSTRUMENT or doc.get("granularity") != granularity:
        raise V4StructureError("provider identity mismatch")
    candles = doc.get("candles")
    if not isinstance(candles, list) or len(candles) > MAX_CANDLES:
        raise V4StructureError("invalid candle payload")
    rows = []
    prior: datetime | None = None
    for raw in candles:
        if raw.get("complete") is not True:
            continue
        if "bid" in raw or "ask" in raw:
            raise V4StructureError("BID/ASK leaked into structure-only response")
        mid = raw.get("mid")
        if not isinstance(mid, dict):
            raise V4StructureError("MID component missing")
        ts = parse_utc(str(raw.get("time")))
        if prior is not None and ts <= prior:
            raise V4StructureError("provider page order violation")
        prior = ts
        o, h, l, c = (dec(mid.get(k), f"mid.{k}") for k in ("o", "h", "l", "c"))
        if h < max(o, c) or l > min(o, c) or h < l:
            raise V4StructureError("invalid MID OHLC envelope")
        rows.append(
            {
                "ts_start_utc": ts.isoformat().replace("+00:00", "Z"),
                "open": str(o),
                "high": str(h),
                "low": str(l),
                "close": str(c),
                "price_count": int(raw.get("volume", 0)),
                "granularity": granularity,
            }
        )
    return rows


def merge_pages(pages: list[list[dict]]) -> list[dict]:
    by_time: dict[str, dict] = {}
    for page in pages:
        for row in page:
            ts = parse_utc(row["ts_start_utc"])
            if not START <= ts < END:
                continue
            previous = by_time.get(row["ts_start_utc"])
            if previous is not None and previous != row:
                raise V4StructureError(f"conflicting duplicate {row['ts_start_utc']}")
            by_time[row["ts_start_utc"]] = row
    rows = [by_time[key] for key in sorted(by_time)]
    if not rows:
        raise V4StructureError("provider returned no structure rows")
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def acquire(protocol_path: Path, output_dir: Path, delay: float = 0.02) -> dict:
    verify_protocol(protocol_path)
    account = os.getenv("OANDA_ACCOUNT_ID", "")
    token = os.getenv("OANDA_API_TOKEN", "")
    if not account or not token:
        raise V4StructureError("required OANDA repository secrets missing")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_root = output_dir / "raw-pages"
    raw_root.mkdir(exist_ok=True)
    timeframe_manifest: dict[str, dict] = {}
    retrieval_digest = hashlib.sha256()

    for granularity in GRANULARITIES:
        pages = []
        chunk_meta = []
        gran_raw = raw_root / granularity
        gran_raw.mkdir(exist_ok=True)
        chunks = windows(granularity)
        for index, (start, end) in enumerate(chunks):
            payload, request_sha = request_payload(
                account=account,
                token=token,
                granularity=granularity,
                start=start,
                end=end,
            )
            raw_sha = hashlib.sha256(payload).hexdigest()
            (gran_raw / f"page-{index:04d}.json").write_bytes(payload)
            parsed = parse_page(payload, granularity)
            pages.append(parsed)
            item = {
                "index": index,
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
                "request_sha256": request_sha,
                "raw_response_sha256": raw_sha,
                "raw_bytes": len(payload),
                "complete_rows": len(parsed),
            }
            chunk_meta.append(item)
            retrieval_digest.update(granularity.encode())
            retrieval_digest.update(request_sha.encode())
            retrieval_digest.update(raw_sha.encode())
            if delay and index + 1 < len(chunks):
                time.sleep(delay)

        rows = merge_pages(pages)
        path = output_dir / f"NAS100_USD.{granularity}.jsonl"
        write_jsonl(path, rows)
        timeframe_manifest[granularity] = {
            "rows": len(rows),
            "first_complete_bar": rows[0]["ts_start_utc"],
            "last_complete_bar": rows[-1]["ts_start_utc"],
            "sha256": file_sha(path),
            "chunks": chunk_meta,
        }

    manifest = {
        "schema_version": 1,
        "status": "V4_SHARP_TURN_STRUCTURE_READY",
        "protocol_sha256": PROTOCOL_SHA,
        "provider": "OANDA_V20",
        "environment": "practice",
        "instrument": INSTRUMENT,
        "price_component_requested": "M",
        "semantic_price_component": "MID",
        "granularities_requested": list(GRANULARITIES),
        "smooth": False,
        "include_first": True,
        "daily_alignment_hour": 17,
        "alignment_timezone": "America/New_York",
        "weekly_alignment": "Friday",
        "requested_start": "2010-01-01T00:00:00Z",
        "requested_end_exclusive": "2024-01-01T00:00:00Z",
        "historical_window_classification": "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT",
        "timeframes": timeframe_manifest,
        "retrieval_sha256": retrieval_digest.hexdigest(),
        "m1_data_requested": False,
        "bid_ask_data_requested": False,
        "fills_evaluated": False,
        "economic_outcomes_evaluated": False,
        "performance_metrics_accessed": False,
        "mutation_endpoints_used": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    manifest["manifest_sha256"] = canon(manifest)
    (output_dir / "NAS100_USD.v4-structure-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        default="research/profitability/v4_sharp_turn_execution_protocol_v1.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--delay", type=float, default=0.02)
    args = parser.parse_args()
    try:
        manifest = acquire(Path(args.protocol), Path(args.output_dir), args.delay)
    except Exception as exc:
        print(f"V4 structure acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "protocol_sha256": manifest["protocol_sha256"],
                "granularities": manifest["granularities_requested"],
                "rows": {k: v["rows"] for k, v in manifest["timeframes"].items()},
                "retrieval_sha256": manifest["retrieval_sha256"],
                "m1_data_requested": False,
                "economic_outcomes_evaluated": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
