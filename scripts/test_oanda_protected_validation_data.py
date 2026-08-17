#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from oanda_protected_validation_data import (  # noqa: E402
    EXPECTED_PROTOCOL_SHA,
    VALIDATION_END,
    VALIDATION_START,
    ProtectedValidationDataError,
    acquire,
    bounded_interval,
    canonical_sha256,
    load_contract,
    load_protocol,
    merge_pages,
    parse_candle_payload,
    parse_utc,
)
from oanda_calibration_data import aggregate_complete_buckets, request_windows  # noqa: E402

PROTOCOL = ROOT / "research/validation/protected_validation_protocol_v1.json"
CONTRACT = ROOT / "research/validation/nas100_oanda_holdout_request_contract.json"


def candle(ts: datetime, price: float = 100.0) -> dict:
    return {
        "complete": True,
        "volume": 1,
        "time": ts.isoformat().replace("+00:00", "Z"),
        "mid": {
            "o": f"{price:.1f}",
            "h": f"{price + 1:.1f}",
            "l": f"{price - 1:.1f}",
            "c": f"{price + 0.2:.1f}",
        },
    }


def payload(start: datetime, count: int) -> bytes:
    doc = {
        "instrument": "NAS100_USD",
        "granularity": "M1",
        "candles": [candle(start + timedelta(minutes=i), 100 + i / 10) for i in range(count)],
    }
    return json.dumps(doc, separators=(",", ":")).encode()


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except ProtectedValidationDataError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected ProtectedValidationDataError containing {needle!r}")


def main() -> int:
    protocol = load_protocol(PROTOCOL)
    assert protocol["protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    contract = load_contract(CONTRACT, protocol)
    assert contract["start"] == "2026-01-01T00:00:00Z"
    assert contract["end_exclusive"] == "2026-07-01T00:00:00Z"
    assert contract["mutation_endpoints_authorized"] is False
    assert contract["paper_trading_authorized"] is False
    assert contract["live_trading_authorized"] is False
    assert contract["account_id_env"] == "OANDA_ACCOUNT_ID"
    assert contract["api_token_env"] == "OANDA_API_TOKEN"

    assert bounded_interval(contract, VALIDATION_START, VALIDATION_END) == (VALIDATION_START, VALIDATION_END)
    expect_error(lambda: bounded_interval(contract, VALIDATION_START - timedelta(minutes=1), VALIDATION_END), "outside protected validation interval")
    expect_error(lambda: bounded_interval(contract, VALIDATION_START, VALIDATION_END + timedelta(minutes=1)), "outside protected validation interval")
    expect_error(lambda: bounded_interval(contract, VALIDATION_END, VALIDATION_END), "outside protected validation interval")

    windows = request_windows(VALIDATION_START, VALIDATION_END, 4500)
    assert windows[0][0] == VALIDATION_START
    assert windows[-1][1] == VALIDATION_END
    assert all(0 < int((end - start).total_seconds() // 60) <= 4500 for start, end in windows)
    assert all(VALIDATION_START <= start < end <= VALIDATION_END for start, end in windows)

    sample = parse_candle_payload(payload(VALIDATION_START, 15), "NAS100_USD", "M")
    assert len(sample) == 15
    assert sample[0].ts_open == VALIDATION_START
    assert sample[-1].ts_open == VALIDATION_START + timedelta(minutes=14)
    agg15, omitted = aggregate_complete_buckets(sample, 15)
    assert len(agg15) == 1 and omitted == 0

    expect_error(lambda: parse_candle_payload(payload(VALIDATION_START - timedelta(minutes=1), 1), "NAS100_USD", "M"), "bar outside protected validation interval")
    expect_error(lambda: parse_candle_payload(payload(VALIDATION_END, 1), "NAS100_USD", "M"), "bar outside protected validation interval")

    # Duplicate merge conflicts fail closed while both duplicate bars remain valid OHLC candles.
    page_a = parse_candle_payload(payload(VALIDATION_START, 2), "NAS100_USD", "M")
    page_b_doc = json.loads(payload(VALIDATION_START + timedelta(minutes=1), 1))
    page_b_doc["candles"][0]["mid"]["c"] = "100.4"
    page_b = parse_candle_payload(json.dumps(page_b_doc).encode(), "NAS100_USD", "M")
    expect_error(lambda: merge_pages([page_a, page_b], VALIDATION_START, VALIDATION_START + timedelta(minutes=2)), "conflicting duplicate")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        start = VALIDATION_START
        end = VALIDATION_START + timedelta(minutes=15)
        fake_payload = payload(start, 15)
        fake_request_sha = "a" * 64
        env = {"OANDA_ACCOUNT_ID": "test-account", "OANDA_API_TOKEN": "test-token"}
        with patch.dict(os.environ, env, clear=False), patch("oanda_protected_validation_data._request_payload", return_value=(fake_payload, fake_request_sha)):
            manifest = acquire(contract_path=CONTRACT, protocol_path=PROTOCOL, output_dir=out, start=start, end=end, delay=0)
        assert manifest["holdout_accessed"] is True
        assert manifest["protected_validation_accessed"] is True
        assert manifest["calibration_window_accessed"] is False
        assert manifest["request_inside_protected_window"] is True
        assert manifest["mutation_endpoints_used"] is False
        assert manifest["paper_trading_authorized"] is False
        assert manifest["live_trading_authorized"] is False
        assert manifest["requested_start"] == "2026-01-01T00:00:00Z"
        assert manifest["requested_end_exclusive"] == "2026-01-01T00:15:00Z"
        assert manifest["m1_rows"] == 15
        assert manifest["derived"]["15"]["rows"] == 1
        text = (out / "NAS100_USD.manifest.json").read_text(encoding="utf-8")
        assert "test-token" not in text
        assert "test-account" not in text

    contract_text = CONTRACT.read_text(encoding="utf-8")
    assert "OANDA_ACCOUNT_ID" in contract_text
    assert "OANDA_API_TOKEN" in contract_text
    assert "Bearer " not in contract_text
    assert "test-token" not in contract_text
    assert "test-account" not in contract_text
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
    assert parse_utc("2026-01-01T00:00:00Z") == datetime(2026, 1, 1, tzinfo=UTC)

    print("Protected OANDA holdout acquisition tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
