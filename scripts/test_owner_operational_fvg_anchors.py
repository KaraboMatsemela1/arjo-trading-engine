#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_owner_operational_fvg_anchors import (  # noqa: E402
    EXPECTED_CLASSIFICATION,
    EXPECTED_CONVENTION_ID,
    FvgError,
    canonical_sha256,
    detect_formations,
    load_convention,
    selection_time,
    stream_select,
)


def bar(ts: str, *, low: str, high: str, minutes: int = 240, open_: str | None = None, close: str | None = None) -> dict:
    mid = str((float(low) + float(high)) / 2)
    return {
        "ts_start_utc": ts,
        "minutes": minutes,
        "open": open_ or mid,
        "high": high,
        "low": low,
        "close": close or mid,
    }


def manual_gap(*, direction: str, formation_end: datetime, low: str = "100", high: str = "110", suffix: str = "A") -> dict:
    return {
        "gap_id": f"OWNER-FVG-{suffix}",
        "direction": direction,
        "zone_low": low,
        "zone_high": high,
        "c1_ts_start_utc": (formation_end - timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
        "c2_ts_start_utc": (formation_end - timedelta(hours=8)).isoformat().replace("+00:00", "Z"),
        "c3_ts_start_utc": (formation_end - timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
        "formation_end_utc": formation_end.isoformat().replace("+00:00", "Z"),
        "classification": EXPECTED_CLASSIFICATION,
        "convention_id": EXPECTED_CONVENTION_ID,
    }


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except FvgError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected FvgError containing {needle!r}")


def main() -> int:
    convention_path = ROOT / "research" / "calibration" / "owner_operational_fvg_v1.json"
    convention, convention_sha = load_convention(convention_path)
    assert convention_sha == "cf12a1ce30d35dced52ef4f3c9bbb3ed11ab6509d6ada33e2f04089c68fafe7e"
    assert convention["classification"] == EXPECTED_CLASSIFICATION

    # Bullish standard wick-gap geometry: c3.low > c1.high.
    bullish = detect_formations([
        bar("2024-06-03T00:00:00Z", low="90", high="100"),
        bar("2024-06-03T04:00:00Z", low="99", high="112"),
        bar("2024-06-03T08:00:00Z", low="105", high="120"),
    ])
    assert len(bullish) == 1
    assert bullish[0]["direction"] == "BULLISH"
    assert bullish[0]["zone_low"] == "100"
    assert bullish[0]["zone_high"] == "105"
    assert bullish[0]["formation_end_utc"] == "2024-06-03T12:00:00Z"

    # Bearish standard wick-gap geometry: c3.high < c1.low.
    bearish = detect_formations([
        bar("2024-06-04T00:00:00Z", low="110", high="120"),
        bar("2024-06-04T04:00:00Z", low="98", high="112"),
        bar("2024-06-04T08:00:00Z", low="90", high="105"),
    ])
    assert len(bearish) == 1
    assert bearish[0]["direction"] == "BEARISH"
    assert bearish[0]["zone_low"] == "105"
    assert bearish[0]["zone_high"] == "110"

    # Missing 4h bucket means the three-candle construction fails closed.
    assert detect_formations([
        bar("2024-06-05T00:00:00Z", low="90", high="100"),
        bar("2024-06-05T08:00:00Z", low="101", high="110"),
        bar("2024-06-05T12:00:00Z", low="111", high="120"),
    ]) == []

    session = date(2024, 6, 3)
    session_ts = selection_time(session)
    gap = manual_gap(direction="BULLISH", formation_end=session_ts - timedelta(hours=1), low="100", high="110")

    # A completed 15m bar that fully traverses before 09:30 invalidates the gap.
    before_fill = bar(
        (session_ts - timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        low="99", high="111", minutes=15,
    )
    result = stream_select([before_fill], [gap], [session], convention_sha)
    assert result["selected_session_count"] == 0
    assert result["sessions"][0]["selected_fvg"] is None

    # A fill that completes after 09:30 cannot retroactively affect the decision.
    after_fill = bar(
        session_ts.isoformat().replace("+00:00", "Z"),
        low="99", high="111", minutes=15,
    )
    result = stream_select([after_fill], [gap], [session], convention_sha)
    assert result["selected_session_count"] == 1
    assert result["sessions"][0]["selected_fvg"]["gap_id"] == gap["gap_id"]
    assert result["sessions"][0]["future_session_bars_used"] is False

    # Same timestamp: fills are processed before a newly formed FVG, so c3 cannot fill itself.
    same_time_gap = manual_gap(direction="BULLISH", formation_end=session_ts, low="100", high="110", suffix="SAME")
    fill_ending_at_session = bar(
        (session_ts - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
        low="95", high="115", minutes=15,
    )
    result = stream_select([fill_ending_at_session], [same_time_gap], [session], convention_sha)
    assert result["sessions"][0]["selected_fvg"]["gap_id"] == "OWNER-FVG-SAME"

    # Most recently formed active FVG wins; input order cannot change the outcome.
    old_gap = manual_gap(direction="BULLISH", formation_end=session_ts - timedelta(hours=5), suffix="OLD")
    new_gap = manual_gap(direction="BEARISH", formation_end=session_ts - timedelta(hours=2), low="120", high="130", suffix="NEW")
    left = stream_select([], [old_gap, new_gap], [session], convention_sha)
    right = stream_select([], [new_gap, old_gap], [session], convention_sha)
    assert left["sessions"][0]["selected_fvg"]["gap_id"] == "OWNER-FVG-NEW"
    assert left["session_anchors_sha256"] == right["session_anchors_sha256"]

    # Convention tampering must be detected before any market-data selection.
    with tempfile.TemporaryDirectory() as tmp:
        tampered = copy.deepcopy(convention)
        tampered["geometry"]["bullish_predicate"] = "c3.low >= c1.high"
        path = Path(tmp) / "tampered.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        expect_error(lambda: load_convention(path), "convention SHA mismatch")

    # Canonicalization remains stable under insertion-order differences.
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})

    print("Owner operational FVG anchor tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
