#!/usr/bin/env python3
"""Read-only OANDA protected-validation acquisition for the frozen 2026 holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from oanda_calibration_data import (
    MAX_OANDA_CANDLES_PER_RESPONSE,
    NY,
    _decimal,
    _request_payload,
    aggregate_complete_buckets,
    request_windows,
    sha256_bytes,
    sha256_file,
    write_jsonl,
)

VALIDATION_START = datetime(2026, 1, 1, tzinfo=UTC)
VALIDATION_END = datetime(2026, 7, 1, tzinfo=UTC)
EXPECTED_PROTOCOL_SHA = "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"


class ProtectedValidationDataError(RuntimeError):
    pass


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtectedValidationDataError(f"invalid timestamp: {value}") from exc
    if dt.utcoffset() is None:
        raise ProtectedValidationDataError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_protocol(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(protocol.get("protocol_sha256", ""))
    unsigned = dict(protocol)
    unsigned.pop("protocol_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual or actual != EXPECTED_PROTOCOL_SHA:
        raise ProtectedValidationDataError("protected validation protocol SHA mismatch")
    if protocol.get("status") != "FROZEN_BEFORE_HOLDOUT_ACCESS":
        raise ProtectedValidationDataError("validation protocol is not frozen")
    if protocol.get("window") != {
        "start_inclusive": "2026-01-01T00:00:00Z",
        "end_exclusive": "2026-07-01T00:00:00Z",
        "request_must_not_cross_end": True,
    }:
        raise ProtectedValidationDataError("protected window changed")
    return protocol


def load_contract(path: Path, protocol: dict) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "contract_id": "ARJO-VAL-OANDA-NAS100-001",
        "validation_protocol_id": "ARJO_PROTECTED_VALIDATION_V1",
        "validation_protocol_sha256": EXPECTED_PROTOCOL_SHA,
        "required_entry_gate": "PROTECTED_VALIDATION_PROTOCOL_FROZEN",
        "provider": "OANDA_V20",
        "venue": "OANDA_FXTRADE",
        "environment": "practice",
        "base_url": "https://api-fxpractice.oanda.com",
        "instrument": "NAS100_USD",
        "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
        "price_component": "M",
        "price_component_name": "MID",
        "source_granularity": "M1",
        "start": "2026-01-01T00:00:00Z",
        "end_exclusive": "2026-07-01T00:00:00Z",
        "protected_validation_only": True,
        "calibration_data_write_authorized": False,
        "mutation_endpoints_authorized": False,
        "paper_trading_authorized": False,
        "live_trading_authorized": False,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise ProtectedValidationDataError(f"unexpected holdout contract {key}")
    if protocol.get("protocol_sha256") != contract["validation_protocol_sha256"]:
        raise ProtectedValidationDataError("contract/protocol SHA mismatch")
    page_minutes = contract.get("page_minutes")
    if not isinstance(page_minutes, int) or not 1 <= page_minutes <= MAX_OANDA_CANDLES_PER_RESPONSE:
        raise ProtectedValidationDataError("page_minutes must be in 1..5000")
    if contract.get("derived_granularities_minutes") != [15, 60, 240]:
        raise ProtectedValidationDataError("derived granularity policy changed")
    return contract


def bounded_interval(contract: dict, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start = start.astimezone(UTC)
    end = end.astimezone(UTC)
    if parse_utc(contract["start"]) != VALIDATION_START or parse_utc(contract["end_exclusive"]) != VALIDATION_END:
        raise ProtectedValidationDataError("contract validation window mismatch")
    if start < VALIDATION_START or end > VALIDATION_END or end <= start:
        raise ProtectedValidationDataError("request outside protected validation interval")
    return start, end


@dataclass(frozen=True)
class HoldoutMinuteBar:
    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    price_count: int
    source_sha256: str

    def __post_init__(self) -> None:
        if self.ts_open.utcoffset() != timedelta(0):
            raise ProtectedValidationDataError("OANDA timestamp must be UTC")
        if not VALIDATION_START <= self.ts_open < VALIDATION_END:
            raise ProtectedValidationDataError("bar outside protected validation interval")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.high < self.low:
            raise ProtectedValidationDataError("invalid OHLC envelope")
        if self.price_count < 0 or len(self.source_sha256) != 64:
            raise ProtectedValidationDataError("invalid provider candle metadata")


def parse_candle_payload(payload: bytes, instrument: str, price_component: str = "M") -> list[HoldoutMinuteBar]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProtectedValidationDataError("invalid OANDA JSON") from exc
    if document.get("instrument") != instrument or document.get("granularity") != "M1":
        raise ProtectedValidationDataError("provider response identity mismatch")
    candles = document.get("candles")
    if not isinstance(candles, list):
        raise ProtectedValidationDataError("provider candles array missing")
    component_key = {"M": "mid", "B": "bid", "A": "ask"}.get(price_component)
    if component_key is None:
        raise ProtectedValidationDataError("unsupported price component")
    source_hash = sha256_bytes(payload)
    output: list[HoldoutMinuteBar] = []
    prior: datetime | None = None
    for raw in candles:
        if not isinstance(raw, dict) or raw.get("complete") is not True:
            continue
        price = raw.get(component_key)
        if not isinstance(price, dict):
            raise ProtectedValidationDataError("requested price component missing")
        ts = parse_utc(str(raw.get("time")))
        if prior is not None and ts <= prior:
            raise ProtectedValidationDataError("duplicate/out-of-order provider candle")
        prior = ts
        output.append(HoldoutMinuteBar(
            ts_open=ts,
            open=_decimal(price.get("o"), "open"),
            high=_decimal(price.get("h"), "high"),
            low=_decimal(price.get("l"), "low"),
            close=_decimal(price.get("c"), "close"),
            price_count=int(raw.get("volume", 0)),
            source_sha256=source_hash,
        ))
    return output


def merge_pages(pages: list[list[HoldoutMinuteBar]], start: datetime, end: datetime) -> list[HoldoutMinuteBar]:
    by_time: dict[datetime, HoldoutMinuteBar] = {}
    for page in pages:
        for bar in page:
            if not start <= bar.ts_open < end:
                continue
            prior = by_time.get(bar.ts_open)
            if prior is not None:
                if (prior.open, prior.high, prior.low, prior.close, prior.price_count) != (bar.open, bar.high, bar.low, bar.close, bar.price_count):
                    raise ProtectedValidationDataError(f"conflicting duplicate at {bar.ts_open.isoformat()}")
                continue
            by_time[bar.ts_open] = bar
    result = [by_time[key] for key in sorted(by_time)]
    if not result:
        raise ProtectedValidationDataError("retrieval returned no protected validation candles")
    return result


def acquire(*, contract_path: Path, protocol_path: Path, output_dir: Path, start: datetime, end: datetime, delay: float = 0.05) -> dict:
    protocol = load_protocol(protocol_path)
    contract = load_contract(contract_path, protocol)
    start, end = bounded_interval(contract, start, end)
    account_id = os.getenv(contract["account_id_env"], "")
    token = os.getenv(contract["api_token_env"], "")
    if not account_id or not token:
        raise ProtectedValidationDataError("required OANDA repository secrets are missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw-pages"
    raw_dir.mkdir(parents=True, exist_ok=True)

    page_meta: list[dict] = []
    parsed_pages: list[list[HoldoutMinuteBar]] = []
    windows = request_windows(start, end, contract["page_minutes"])
    for index, (page_start, page_end) in enumerate(windows):
        if page_start < VALIDATION_START or page_end > VALIDATION_END:
            raise ProtectedValidationDataError("generated request page crosses protected window")
        payload, request_sha = _request_payload(
            base_url=contract["base_url"], account_id=account_id, token=token,
            instrument=contract["instrument"], start=page_start, end=page_end,
            price_component=contract["price_component"], timeout=45.0,
        )
        raw_sha = sha256_bytes(payload)
        (raw_dir / f"page-{index:04d}.json").write_bytes(payload)
        page_bars = parse_candle_payload(payload, contract["instrument"], contract["price_component"])
        parsed_pages.append(page_bars)
        page_meta.append({
            "index": index,
            "start": page_start.isoformat().replace("+00:00", "Z"),
            "end": page_end.isoformat().replace("+00:00", "Z"),
            "request_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "raw_bytes": len(payload),
            "complete_m1_rows": len(page_bars),
        })
        if delay and index < len(windows) - 1:
            time.sleep(delay)

    bars = merge_pages(parsed_pages, start, end)
    m1_records = [{
        "ts_start_utc": bar.ts_open.isoformat().replace("+00:00", "Z"),
        "session_start_local": bar.ts_open.astimezone(NY).isoformat(),
        "open": str(bar.open), "high": str(bar.high), "low": str(bar.low), "close": str(bar.close),
        "price_count": bar.price_count, "source_sha256": bar.source_sha256,
    } for bar in bars]
    write_jsonl(output_dir / "NAS100_USD.M1.jsonl", m1_records)

    derived: dict[str, dict] = {}
    for minutes in contract["derived_granularities_minutes"]:
        records, omitted = aggregate_complete_buckets(bars, int(minutes))
        path = output_dir / f"NAS100_USD.{minutes}m.jsonl"
        write_jsonl(path, records)
        derived[str(minutes)] = {"rows": len(records), "omitted_incomplete_buckets": omitted, "sha256": sha256_file(path)}

    retrieval_digest = hashlib.sha256()
    for page in page_meta:
        retrieval_digest.update(page["request_sha256"].encode())
        retrieval_digest.update(page["raw_response_sha256"].encode())

    manifest = {
        "schema_version": 1,
        "validation_protocol_id": protocol["protocol_id"],
        "validation_protocol_sha256": protocol["protocol_sha256"],
        "provider": contract["provider"], "venue": contract["venue"], "environment": contract["environment"],
        "instrument": contract["instrument"], "instrument_identity": contract["instrument_identity"],
        "provider_instrument_type": "CFD", "price_component": contract["price_component_name"],
        "source_granularity": contract["source_granularity"], "provider_display_precision": 1,
        "provider_price_quantum": "0.1",
        "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
        "request_contract_sha256": sha256_file(contract_path),
        "requested_start": start.isoformat().replace("+00:00", "Z"),
        "requested_end_exclusive": end.isoformat().replace("+00:00", "Z"),
        "protected_validation_accessed": True,
        "holdout_accessed": True,
        "calibration_window_accessed": False,
        "request_inside_protected_window": True,
        "mutation_endpoints_used": False,
        "raw_page_count": len(page_meta), "raw_pages": page_meta,
        "retrieval_sha256": retrieval_digest.hexdigest(),
        "m1_rows": len(m1_records), "m1_first": m1_records[0]["ts_start_utc"], "m1_last": m1_records[-1]["ts_start_utc"],
        "m1_sha256": sha256_file(output_dir / "NAS100_USD.M1.jsonl"), "derived": derived,
        "raw_payload_location": "WORKFLOW_ARTIFACT_ONLY_NOT_GIT",
        "paper_trading_authorized": False, "live_trading_authorized": False,
    }
    manifest_path = output_dir / "NAS100_USD.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="research/validation/nas100_oanda_holdout_request_contract.json")
    parser.add_argument("--protocol", default="research/validation/protected_validation_protocol_v1.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()
    try:
        manifest = acquire(
            contract_path=Path(args.contract), protocol_path=Path(args.protocol), output_dir=Path(args.output_dir),
            start=parse_utc(args.start), end=parse_utc(args.end), delay=args.delay,
        )
    except Exception as exc:
        print(f"protected validation acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "provider": manifest["provider"], "instrument": manifest["instrument"],
        "requested_start": manifest["requested_start"], "requested_end_exclusive": manifest["requested_end_exclusive"],
        "m1_rows": manifest["m1_rows"], "retrieval_sha256": manifest["retrieval_sha256"],
        "holdout_accessed": manifest["holdout_accessed"], "mutation_endpoints_used": manifest["mutation_endpoints_used"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
