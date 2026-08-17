#!/usr/bin/env python3
"""Read-only OANDA calibration acquisition with SHA-bound provenance.

This module deliberately preserves the provider identity of NAS100_USD as an
OANDA Nasdaq-100 CFD price series. It does not claim CME NQ equivalence and it
never calls trading/mutation endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
MAX_OANDA_CANDLES_PER_RESPONSE = 5000


class CalibrationDataError(RuntimeError):
    pass


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalibrationDataError(f"invalid timestamp: {value}") from exc
    if parsed.utcoffset() is None:
        raise CalibrationDataError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(path: str | Path) -> dict:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "provider": "OANDA_V20",
        "venue": "OANDA_FXTRADE",
        "environment": "practice",
        "base_url": "https://api-fxpractice.oanda.com",
        "instrument": "NAS100_USD",
        "price_component": "M",
        "source_granularity": "M1",
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise CalibrationDataError(f"unexpected contract {key}")
    start = parse_utc(contract["start"])
    end = parse_utc(contract["end_exclusive"])
    holdout = parse_utc(contract["protected_holdout_start"])
    if start >= end:
        raise CalibrationDataError("contract start must precede end")
    if holdout != HOLDOUT_START or end > holdout:
        raise CalibrationDataError("contract crosses protected holdout boundary")
    page_minutes = contract.get("page_minutes")
    if not isinstance(page_minutes, int) or not 1 <= page_minutes <= MAX_OANDA_CANDLES_PER_RESPONSE:
        raise CalibrationDataError("page_minutes must be in 1..5000")
    if contract.get("mutation_endpoints_authorized") is not False:
        raise CalibrationDataError("mutation endpoints must remain unauthorized")
    return contract


def bounded_interval(contract: dict, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    contract_start = parse_utc(contract["start"])
    contract_end = parse_utc(contract["end_exclusive"])
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    if start < contract_start or end > contract_end or end <= start:
        raise CalibrationDataError("requested interval is outside frozen calibration contract")
    if end > HOLDOUT_START or start >= HOLDOUT_START:
        raise CalibrationDataError("protected holdout request prohibited")
    return start, end


def request_windows(start: datetime, end: datetime, page_minutes: int) -> list[tuple[datetime, datetime]]:
    if not 1 <= page_minutes <= MAX_OANDA_CANDLES_PER_RESPONSE:
        raise CalibrationDataError("invalid page size")
    windows: list[tuple[datetime, datetime]] = []
    cursor = start.astimezone(UTC)
    end = end.astimezone(UTC)
    step = timedelta(minutes=page_minutes)
    while cursor < end:
        nxt = min(cursor + step, end)
        windows.append((cursor, nxt))
        cursor = nxt
    return windows


def _decimal(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CalibrationDataError(f"invalid decimal {label}") from exc
    if not parsed.is_finite():
        raise CalibrationDataError(f"non-finite decimal {label}")
    return parsed


@dataclass(frozen=True)
class OandaMinuteBar:
    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    price_count: int
    source_sha256: str

    def __post_init__(self) -> None:
        if self.ts_open.utcoffset() != timedelta(0):
            raise CalibrationDataError("OANDA timestamps must be UTC")
        if self.ts_open >= HOLDOUT_START:
            raise CalibrationDataError("protected holdout bar encountered")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise CalibrationDataError("invalid OHLC envelope")
        if self.high < self.low or self.price_count < 0:
            raise CalibrationDataError("invalid candle values")
        if len(self.source_sha256) != 64:
            raise CalibrationDataError("source hash must be SHA-256")


def parse_candle_payload(payload: bytes, instrument: str, price_component: str = "M") -> list[OandaMinuteBar]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CalibrationDataError("invalid OANDA JSON") from exc
    if document.get("instrument") != instrument or document.get("granularity") != "M1":
        raise CalibrationDataError("provider response identity mismatch")
    raw_candles = document.get("candles")
    if not isinstance(raw_candles, list):
        raise CalibrationDataError("provider candles array missing")
    component_key = {"M": "mid", "B": "bid", "A": "ask"}.get(price_component)
    if component_key is None:
        raise CalibrationDataError("unsupported price component")
    source_hash = sha256_bytes(payload)
    bars: list[OandaMinuteBar] = []
    prior: datetime | None = None
    for raw in raw_candles:
        if not isinstance(raw, dict):
            raise CalibrationDataError("invalid candle record")
        if raw.get("complete") is not True:
            continue
        price = raw.get(component_key)
        if not isinstance(price, dict):
            raise CalibrationDataError("requested price component missing")
        ts = parse_utc(str(raw.get("time")))
        if prior is not None and ts <= prior:
            raise CalibrationDataError("duplicate or out-of-order candle inside provider page")
        prior = ts
        bars.append(
            OandaMinuteBar(
                ts_open=ts,
                open=_decimal(price.get("o"), "open"),
                high=_decimal(price.get("h"), "high"),
                low=_decimal(price.get("l"), "low"),
                close=_decimal(price.get("c"), "close"),
                price_count=int(raw.get("volume", 0)),
                source_sha256=source_hash,
            )
        )
    return bars


def _request_payload(
    *,
    base_url: str,
    account_id: str,
    token: str,
    instrument: str,
    start: datetime,
    end: datetime,
    price_component: str,
    timeout: float,
) -> tuple[bytes, str]:
    if not account_id or not token:
        raise CalibrationDataError("OANDA credentials missing")
    params = {
        "price": price_component,
        "granularity": "M1",
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": end.isoformat().replace("+00:00", "Z"),
        "smooth": "false",
        "includeFirst": "true",
    }
    real_path = f"/v3/accounts/{account_id}/instruments/{instrument}/candles"
    redacted_path = f"/v3/accounts/{{ACCOUNT}}/instruments/{instrument}/candles"
    url = f"{base_url.rstrip('/')}{real_path}?{urlencode(params)}"
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept-Datetime-Format": "RFC3339"},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
    canonical = urlencode(sorted((k, str(v)) for k, v in params.items()))
    request_sha = sha256_bytes(f"{redacted_path}?{canonical}".encode())
    return payload, request_sha


def merge_pages(pages: list[list[OandaMinuteBar]], start: datetime, end: datetime) -> list[OandaMinuteBar]:
    by_time: dict[datetime, OandaMinuteBar] = {}
    for page in pages:
        for bar in page:
            if bar.ts_open < start or bar.ts_open >= end:
                continue
            previous = by_time.get(bar.ts_open)
            if previous is not None:
                if (
                    previous.open,
                    previous.high,
                    previous.low,
                    previous.close,
                    previous.price_count,
                ) != (bar.open, bar.high, bar.low, bar.close, bar.price_count):
                    raise CalibrationDataError(f"conflicting duplicate at {bar.ts_open.isoformat()}")
                continue
            by_time[bar.ts_open] = bar
    output = [by_time[key] for key in sorted(by_time)]
    if not output:
        raise CalibrationDataError("retrieval returned no calibration candles")
    return output


def _bucket_start(ts: datetime, minutes: int) -> datetime:
    epoch_minute = int(ts.timestamp() // 60)
    floor = epoch_minute - (epoch_minute % minutes)
    return datetime.fromtimestamp(floor * 60, tz=UTC)


def aggregate_complete_buckets(bars: list[OandaMinuteBar], minutes: int) -> tuple[list[dict], int]:
    if minutes not in {15, 60, 240}:
        raise CalibrationDataError("unsupported derived interval")
    groups: dict[datetime, list[OandaMinuteBar]] = {}
    for bar in bars:
        groups.setdefault(_bucket_start(bar.ts_open, minutes), []).append(bar)
    output: list[dict] = []
    omitted = 0
    for start in sorted(groups):
        bucket = groups[start]
        expected = [start + timedelta(minutes=i) for i in range(minutes)]
        actual = [bar.ts_open for bar in bucket]
        if len(bucket) != minutes or actual != expected:
            omitted += 1
            continue
        output.append(
            {
                "ts_start_utc": start.isoformat().replace("+00:00", "Z"),
                "session_start_local": start.astimezone(NY).isoformat(),
                "open": str(bucket[0].open),
                "high": str(max(bar.high for bar in bucket)),
                "low": str(min(bar.low for bar in bucket)),
                "close": str(bucket[-1].close),
                "price_count": sum(bar.price_count for bar in bucket),
                "minutes": minutes,
            }
        )
    return output, omitted


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def acquire(contract_path: Path, output_dir: Path, start: datetime, end: datetime, *, delay: float = 0.05) -> dict:
    contract = load_contract(contract_path)
    start, end = bounded_interval(contract, start, end)
    account_id = os.getenv(contract["account_id_env"], "")
    token = os.getenv(contract["api_token_env"], "")
    if not account_id or not token:
        raise CalibrationDataError("required OANDA repository secrets are missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw-pages"
    raw_dir.mkdir(parents=True, exist_ok=True)

    page_meta: list[dict] = []
    parsed_pages: list[list[OandaMinuteBar]] = []
    windows = request_windows(start, end, contract["page_minutes"])
    for index, (page_start, page_end) in enumerate(windows):
        payload, request_sha = _request_payload(
            base_url=contract["base_url"],
            account_id=account_id,
            token=token,
            instrument=contract["instrument"],
            start=page_start,
            end=page_end,
            price_component=contract["price_component"],
            timeout=45.0,
        )
        raw_sha = sha256_bytes(payload)
        raw_path = raw_dir / f"page-{index:04d}.json"
        raw_path.write_bytes(payload)
        page_bars = parse_candle_payload(payload, contract["instrument"], contract["price_component"])
        parsed_pages.append(page_bars)
        page_meta.append(
            {
                "index": index,
                "start": page_start.isoformat().replace("+00:00", "Z"),
                "end": page_end.isoformat().replace("+00:00", "Z"),
                "request_sha256": request_sha,
                "raw_response_sha256": raw_sha,
                "raw_bytes": len(payload),
                "complete_m1_rows": len(page_bars),
            }
        )
        if delay and index < len(windows) - 1:
            time.sleep(delay)

    bars = merge_pages(parsed_pages, start, end)
    m1_records = [
        {
            "ts_start_utc": bar.ts_open.isoformat().replace("+00:00", "Z"),
            "session_start_local": bar.ts_open.astimezone(NY).isoformat(),
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "price_count": bar.price_count,
            "source_sha256": bar.source_sha256,
        }
        for bar in bars
    ]
    write_jsonl(output_dir / "NAS100_USD.M1.jsonl", m1_records)

    derived: dict[str, dict] = {}
    for minutes in contract["derived_granularities_minutes"]:
        records, omitted = aggregate_complete_buckets(bars, int(minutes))
        path = output_dir / f"NAS100_USD.{minutes}m.jsonl"
        write_jsonl(path, records)
        derived[str(minutes)] = {
            "rows": len(records),
            "omitted_incomplete_buckets": omitted,
            "sha256": sha256_file(path),
        }

    price_quantum = Decimal(1).scaleb(-1)  # Verified provider displayPrecision=1 in preflight.
    retrieval_digest = hashlib.sha256()
    for page in page_meta:
        retrieval_digest.update(page["request_sha256"].encode())
        retrieval_digest.update(page["raw_response_sha256"].encode())

    manifest = {
        "schema_version": 1,
        "provider": contract["provider"],
        "venue": contract["venue"],
        "environment": contract["environment"],
        "instrument": contract["instrument"],
        "instrument_identity": contract["instrument_identity"],
        "provider_instrument_type": "CFD",
        "price_component": contract["price_component_name"],
        "source_granularity": contract["source_granularity"],
        "provider_display_precision": 1,
        "provider_price_quantum": str(price_quantum),
        "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
        "request_contract_sha256": sha256_file(contract_path),
        "requested_start": start.isoformat().replace("+00:00", "Z"),
        "requested_end_exclusive": end.isoformat().replace("+00:00", "Z"),
        "protected_holdout_start": contract["protected_holdout_start"],
        "holdout_requested": False,
        "holdout_accessed": False,
        "mutation_endpoints_used": False,
        "raw_page_count": len(page_meta),
        "raw_pages": page_meta,
        "retrieval_sha256": retrieval_digest.hexdigest(),
        "m1_rows": len(m1_records),
        "m1_first": m1_records[0]["ts_start_utc"],
        "m1_last": m1_records[-1]["ts_start_utc"],
        "m1_sha256": sha256_file(output_dir / "NAS100_USD.M1.jsonl"),
        "derived": derived,
        "raw_payload_location": "WORKFLOW_ARTIFACT_ONLY_NOT_GIT",
        "paper_trading_authorized": False,
        "live_trading_authorized": False,
    }
    manifest_path = output_dir / "NAS100_USD.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="research/calibration/nas100_oanda_request_contract.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()
    try:
        manifest = acquire(
            Path(args.contract),
            Path(args.output_dir),
            parse_utc(args.start),
            parse_utc(args.end),
            delay=args.delay,
        )
    except CalibrationDataError as exc:
        print(f"calibration acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: manifest[k] for k in ("provider", "instrument", "requested_start", "requested_end_exclusive", "m1_rows", "retrieval_sha256", "holdout_accessed")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
