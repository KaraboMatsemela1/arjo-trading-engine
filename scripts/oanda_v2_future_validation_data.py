#!/usr/bin/env python3
"""Single-shot read-only OANDA acquisition for the frozen V2 future validation."""
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

from check_v2_future_validation_access_v2 import authorize, canonical_sha256, parse_utc
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

START = datetime(2026, 9, 1, tzinfo=UTC)
BOOTSTRAP_END = datetime(2026, 10, 1, tzinfo=UTC)
SCORED_START = BOOTSTRAP_END
END = datetime(2027, 3, 1, tzinfo=UTC)
CONTRACT_SHA = "edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca"


class FutureDataError(RuntimeError):
    pass


def load_contract(path: Path) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(contract); recorded = str(unsigned.pop("contract_sha256", ""))
    if recorded != CONTRACT_SHA or canonical_sha256(unsigned) != CONTRACT_SHA:
        raise FutureDataError("future validation request contract SHA mismatch")
    expected = {
        "contract_id": "ARJO-V2-VAL-OANDA-NAS100-001",
        "provider": "OANDA_V20",
        "venue": "OANDA_FXTRADE",
        "environment": "practice",
        "base_url": "https://api-fxpractice.oanda.com",
        "instrument": "NAS100_USD",
        "price_component": "M",
        "source_granularity": "M1",
        "start": "2026-09-01T00:00:00Z",
        "bootstrap_end_exclusive": "2026-10-01T00:00:00Z",
        "scored_start": "2026-10-01T00:00:00Z",
        "end_exclusive": "2027-03-01T00:00:00Z",
        "full_window_single_shot": True,
        "harness_acquisition_not_before": "2027-03-01T00:00:00Z",
        "pre_start_market_data_authorized": False,
        "v1_holdout_reuse_authorized": False,
        "mutation_endpoints_authorized": False,
        "paper_trading_authorized": False,
        "live_trading_authorized": False,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise FutureDataError(f"unexpected future contract field: {key}")
    if contract.get("derived_granularities_minutes") != [15, 60, 240]:
        raise FutureDataError("derived granularity policy changed")
    if not isinstance(contract.get("page_minutes"), int) or not 1 <= contract["page_minutes"] <= MAX_OANDA_CANDLES_PER_RESPONSE:
        raise FutureDataError("invalid OANDA page size")
    return contract


@dataclass(frozen=True)
class FutureMinuteBar:
    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    price_count: int
    source_sha256: str

    def __post_init__(self) -> None:
        if self.ts_open.utcoffset() != timedelta(0) or not START <= self.ts_open < END:
            raise FutureDataError("M1 timestamp outside frozen future window")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.high < self.low:
            raise FutureDataError("invalid M1 OHLC envelope")
        if self.price_count < 0 or len(self.source_sha256) != 64:
            raise FutureDataError("invalid provider candle metadata")


def parse_candle_payload(payload: bytes, instrument: str, price_component: str = "M") -> list[FutureMinuteBar]:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FutureDataError("invalid OANDA JSON") from exc
    if document.get("instrument") != instrument or document.get("granularity") != "M1":
        raise FutureDataError("provider response identity mismatch")
    candles = document.get("candles")
    if not isinstance(candles, list):
        raise FutureDataError("provider candles array missing")
    component_key = {"M": "mid", "B": "bid", "A": "ask"}.get(price_component)
    if component_key is None:
        raise FutureDataError("unsupported price component")
    source_hash = sha256_bytes(payload)
    output: list[FutureMinuteBar] = []
    prior: datetime | None = None
    for raw in candles:
        if not isinstance(raw, dict) or raw.get("complete") is not True:
            continue
        price = raw.get(component_key)
        if not isinstance(price, dict):
            raise FutureDataError("requested price component missing")
        ts = parse_utc(str(raw.get("time")))
        if prior is not None and ts <= prior:
            raise FutureDataError("duplicate/out-of-order provider candle")
        prior = ts
        output.append(FutureMinuteBar(
            ts_open=ts,
            open=_decimal(price.get("o"), "open"),
            high=_decimal(price.get("h"), "high"),
            low=_decimal(price.get("l"), "low"),
            close=_decimal(price.get("c"), "close"),
            price_count=int(raw.get("volume", 0)),
            source_sha256=source_hash,
        ))
    return output


def merge_pages(pages: list[list[FutureMinuteBar]]) -> list[FutureMinuteBar]:
    by_time: dict[datetime, FutureMinuteBar] = {}
    for page in pages:
        for bar in page:
            previous = by_time.get(bar.ts_open)
            if previous is not None:
                if (previous.open, previous.high, previous.low, previous.close, previous.price_count) != (bar.open, bar.high, bar.low, bar.close, bar.price_count):
                    raise FutureDataError(f"conflicting duplicate at {bar.ts_open.isoformat()}")
                continue
            by_time[bar.ts_open] = bar
    output = [by_time[key] for key in sorted(by_time)]
    if not output:
        raise FutureDataError("retrieval returned no future validation candles")
    return output


def acquire(*, contract_path: Path, authorization_path: Path, output_dir: Path, delay: float = 0.05) -> dict:
    authorize(
        gate="acquisition", now=datetime.now(UTC), authorization_path=authorization_path,
        protocol_path=Path("research/v2/future_validation_protocol_v2.json"),
        policy_path=Path("research/v2/v2_m1_touch_sequencing_v1.json"),
        readiness_path=Path("research/v2/v2_m1_measurement_readiness.json"),
        contract_path=contract_path,
    )
    contract = load_contract(contract_path)
    account_id = os.getenv(contract["account_id_env"], "")
    token = os.getenv(contract["api_token_env"], "")
    if not account_id or not token:
        raise FutureDataError("required OANDA repository secrets are missing")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw-pages"; raw_dir.mkdir(parents=True, exist_ok=True)
    page_meta: list[dict] = []
    parsed_pages: list[list[FutureMinuteBar]] = []
    windows = request_windows(START, END, contract["page_minutes"])
    for index, (page_start, page_end) in enumerate(windows):
        if page_start < START or page_end > END:
            raise FutureDataError("generated request page crosses frozen window")
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

    bars = merge_pages(parsed_pages)
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
        retrieval_digest.update(page["request_sha256"].encode()); retrieval_digest.update(page["raw_response_sha256"].encode())
    manifest = {
        "schema_version": 1,
        "status": "V2_FUTURE_VALIDATION_DATA_READY",
        "validation_protocol_sha256": contract["validation_protocol_sha256"],
        "measurement_policy_sha256": contract["measurement_policy_sha256"],
        "request_contract_sha256": CONTRACT_SHA,
        "provider": contract["provider"], "venue": contract["venue"], "environment": contract["environment"],
        "instrument": contract["instrument"], "instrument_identity": contract["instrument_identity"],
        "price_component": contract["price_component_name"], "source_granularity": "M1",
        "provider_price_quantum": "0.1", "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
        "requested_start": "2026-09-01T00:00:00Z", "bootstrap_end_exclusive": "2026-10-01T00:00:00Z",
        "scored_start": "2026-10-01T00:00:00Z", "requested_end_exclusive": "2027-03-01T00:00:00Z",
        "full_window_single_shot": True, "state_at_start": "EMPTY",
        "pre_start_market_data_accessed": False, "v1_holdout_reused": False,
        "future_validation_data_accessed": True, "mutation_endpoints_used": False,
        "raw_page_count": len(page_meta), "raw_pages": page_meta,
        "retrieval_sha256": retrieval_digest.hexdigest(),
        "m1_rows": len(m1_records), "m1_first": m1_records[0]["ts_start_utc"], "m1_last": m1_records[-1]["ts_start_utc"],
        "m1_sha256": sha256_file(output_dir / "NAS100_USD.M1.jsonl"), "derived": derived,
        "raw_payload_location": "WORKFLOW_ARTIFACT_ONLY_NOT_GIT",
        "paper_execution_authorized": False, "live_execution_authorized": False, "broker_mutation_authorized": False,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    (output_dir / "NAS100_USD.manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--authorization", required=True)
    p.add_argument("--contract", default="research/v2/nas100_oanda_future_validation_request_contract.json")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--delay", type=float, default=0.05)
    args = p.parse_args()
    try:
        manifest = acquire(contract_path=Path(args.contract), authorization_path=Path(args.authorization), output_dir=Path(args.output_dir), delay=args.delay)
    except Exception as exc:
        print(f"V2 future validation acquisition failed: {exc}", file=sys.stderr); return 1
    print(json.dumps({"status": manifest["status"], "m1_rows": manifest["m1_rows"], "retrieval_sha256": manifest["retrieval_sha256"], "mutation_endpoints_used": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
