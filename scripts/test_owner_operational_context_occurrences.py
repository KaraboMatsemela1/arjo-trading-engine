#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_owner_operational_context_occurrences import (  # noqa: E402
    ContextError,
    EXPECTED_CLASSIFICATION,
    EXPECTED_CONTEXT_SHA,
    confirmed_pivots,
    load_context_convention,
)

CONVENTION = ROOT / "research/calibration/owner_operational_context_v1.json"


def bar(ts: str, high: str, low: str) -> dict:
    return {
        "ts_start_utc": ts,
        "minutes": 60,
        "open": low,
        "high": high,
        "low": low,
        "close": high,
    }


def main() -> int:
    convention, sha = load_context_convention(CONVENTION)
    assert sha == EXPECTED_CONTEXT_SHA
    assert convention["classification"] == EXPECTED_CLASSIFICATION
    assert convention["anti_bias"]["rule_adjustment_after_diagnostic_counts_allowed"] is False

    rows = [
        bar("2025-06-02T10:00:00Z", "100", "90"),
        bar("2025-06-02T11:00:00Z", "110", "95"),
        bar("2025-06-02T12:00:00Z", "105", "92"),
        bar("2025-06-02T13:00:00Z", "103", "80"),
        bar("2025-06-02T14:00:00Z", "108", "85"),
    ]
    highs, lows = confirmed_pivots(rows)
    assert len(highs) == 1
    assert highs[0]["price"] == "110"
    assert highs[0]["pivot_ts_utc"] == "2025-06-02T11:00:00Z"
    assert highs[0]["confirmed_at_utc"] == "2025-06-02T13:00:00Z"
    assert len(lows) == 1
    assert lows[0]["price"] == "80"
    assert lows[0]["pivot_ts_utc"] == "2025-06-02T13:00:00Z"
    assert lows[0]["confirmed_at_utc"] == "2025-06-02T15:00:00Z"

    # Missing a 1h bucket must not create a pivot across the gap.
    broken = [rows[0], rows[1], rows[3]]
    broken_highs, broken_lows = confirmed_pivots(broken)
    assert broken_highs == []
    assert broken_lows == []

    # Any convention edit without a new versioned SHA fails before data is processed.
    with tempfile.TemporaryDirectory() as tmp:
        payload = copy.deepcopy(convention)
        payload["two_sting"]["selection"] = "changed after freeze"
        path = Path(tmp) / "tampered.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            load_context_convention(path)
        except ContextError as exc:
            assert "convention SHA mismatch" in str(exc)
        else:
            raise AssertionError("tampered context convention must fail closed")

    print("Owner operational context tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
