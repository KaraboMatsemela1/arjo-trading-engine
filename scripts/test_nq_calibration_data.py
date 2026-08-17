#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nq_calibration_data import (  # noqa: E402
    CalibrationDataError,
    MinuteBar,
    acquire_databento,
    aggregate_bars,
    build_raw_manifest,
    load_contract,
)

UTC = timezone.utc
CONTRACT = ROOT / "research/calibration/nq_databento_request_contract.json"


def bars(start: datetime, count: int, instrument_id: int = 100) -> list[MinuteBar]:
    return [
        MinuteBar(start + timedelta(minutes=i), instrument_id, 100 + i, 101 + i, 99 + i, 100.5 + i, 1)
        for i in range(count)
    ]


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except CalibrationDataError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected CalibrationDataError containing {needle!r}")


def main() -> int:
    contract = load_contract(CONTRACT)
    assert contract["end_exclusive"] == "2026-01-01T00:00:00Z"

    # Normal aggregation is deterministic and preserves instrument identity.
    start = datetime(2025, 3, 10, 13, 0, tzinfo=UTC)
    out = aggregate_bars(bars(start, 15), 15)
    assert len(out) == 1
    assert out[0]["instrument_id"] == 100
    assert out[0]["volume"] == 15
    # DST is represented explicitly: 13:00 UTC is 09:00 New York after spring DST change.
    assert out[0]["session_start_local"].startswith("2025-03-10T09:00:00-04:00")

    # Missing minute must fail closed.
    missing = bars(start, 15)
    del missing[7]
    expect_error(lambda: aggregate_bars(missing, 15), "incomplete 15m bucket")

    # Roll within an aggregation bucket must fail closed.
    rolled = bars(start, 15)
    rolled[8] = MinuteBar(rolled[8].ts_event, 200, rolled[8].open, rolled[8].high, rolled[8].low, rolled[8].close, rolled[8].volume)
    expect_error(lambda: aggregate_bars(rolled, 15), "roll inside 15m bucket")

    # Protected holdout bars must never be normalized.
    holdout = bars(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), 15)
    expect_error(lambda: aggregate_bars(holdout, 15), "protected holdout bar")

    # Contract tampering across holdout ceiling fails before provider access.
    with tempfile.TemporaryDirectory() as td:
        bad_contract = Path(td) / "bad.json"
        bad = dict(contract)
        bad["end_exclusive"] = "2026-01-02T00:00:00Z"
        bad_contract.write_text(json.dumps(bad), encoding="utf-8")
        expect_error(lambda: load_contract(bad_contract), "crosses protected holdout boundary")

        artifact = Path(td) / "sample.dbn.zst"
        artifact.write_bytes(b"licensed-test-placeholder")
        manifest = build_raw_manifest(CONTRACT, artifact, instrument_ids=[2, 1, 2], raw_symbols=["NQH5", "NQM5"])
        assert manifest["instrument_ids"] == [1, 2]
        assert len(manifest["artifact_sha256"]) == 64
        assert manifest["end_exclusive"] == "2026-01-01T00:00:00Z"

    # Live adapter is secret-only; no API key means no import/network attempt.
    previous = os.environ.pop("DATABENTO_API_KEY", None)
    try:
        expect_error(lambda: acquire_databento(CONTRACT, "/tmp/never.dbn.zst"), "missing required secret")
    finally:
        if previous is not None:
            os.environ["DATABENTO_API_KEY"] = previous

    print("NQ calibration data foundation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
