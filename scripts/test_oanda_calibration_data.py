#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from oanda_calibration_data import (  # noqa: E402
    CalibrationDataError,
    OandaMinuteBar,
    aggregate_complete_buckets,
    bounded_interval,
    load_contract,
    merge_pages,
    parse_candle_payload,
    request_windows,
)

CONTRACT = ROOT / "research/calibration/nas100_oanda_request_contract.json"


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except CalibrationDataError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected CalibrationDataError containing {needle!r}")


def payload(times: list[datetime], *, close_shift: Decimal = Decimal("0")) -> bytes:
    candles = []
    for i, ts in enumerate(times):
        base = Decimal("20000") + i
        candles.append(
            {
                "complete": True,
                "volume": 10 + i,
                "time": ts.isoformat().replace("+00:00", "Z"),
                "mid": {
                    "o": str(base),
                    "h": str(base + Decimal("2")),
                    "l": str(base - Decimal("2")),
                    "c": str(base + close_shift),
                },
            }
        )
    return json.dumps({"instrument": "NAS100_USD", "granularity": "M1", "candles": candles}).encode()


def main() -> int:
    contract = load_contract(CONTRACT)
    assert contract["provider"] == "OANDA_V20"
    assert contract["end_exclusive"] == "2026-01-01T00:00:00Z"
    assert contract["mutation_endpoints_authorized"] is False

    start = datetime(2024, 3, 11, 13, 30, tzinfo=UTC)
    end = start + timedelta(minutes=9001)
    windows = request_windows(start, end, 4500)
    assert len(windows) == 3
    assert all((b - a) <= timedelta(minutes=5000) for a, b in windows)

    bounded_interval(contract, datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
    expect_error(
        lambda: bounded_interval(contract, datetime(2025, 12, 31, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)),
        "outside frozen calibration contract",
    )

    times = [start + timedelta(minutes=i) for i in range(15)]
    bars = parse_candle_payload(payload(times), "NAS100_USD")
    assert len(bars) == 15
    assert isinstance(bars[0].open, Decimal)
    assert bars[0].ts_open == start

    derived, omitted = aggregate_complete_buckets(bars, 15)
    assert len(derived) == 1 and omitted == 0
    assert derived[0]["session_start_local"].startswith("2024-03-11T09:30:00-04:00")

    gapped = bars[:7] + bars[8:]
    derived, omitted = aggregate_complete_buckets(gapped, 15)
    assert derived == [] and omitted == 1

    first = parse_candle_payload(payload(times[:10]), "NAS100_USD")
    second = parse_candle_payload(payload(times[9:]), "NAS100_USD")
    merged = merge_pages([first, second], start, start + timedelta(minutes=15))
    assert len(merged) == 15

    conflicting_payload = payload(times[9:], close_shift=Decimal("1"))
    conflicting = parse_candle_payload(conflicting_payload, "NAS100_USD")
    expect_error(
        lambda: merge_pages([first, conflicting], start, start + timedelta(minutes=15)),
        "conflicting duplicate",
    )

    duplicate_times = [start, start]
    expect_error(lambda: parse_candle_payload(payload(duplicate_times), "NAS100_USD"), "duplicate or out-of-order")

    holdout = [datetime(2026, 1, 1, tzinfo=UTC)]
    expect_error(lambda: parse_candle_payload(payload(holdout), "NAS100_USD"), "protected holdout bar")

    with tempfile.TemporaryDirectory() as td:
        bad_path = Path(td) / "bad.json"
        bad = dict(contract)
        bad["end_exclusive"] = "2026-01-02T00:00:00Z"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        expect_error(lambda: load_contract(bad_path), "crosses protected holdout boundary")

    bar = OandaMinuteBar(
        ts_open=start,
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0"),
        close=Decimal("1.5"),
        price_count=1,
        source_sha256="a" * 64,
    )
    assert bar.ts_open == start

    print("OANDA calibration data offline tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
