#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nq_calibration_replay import (  # noqa: E402
    ReplayBar,
    ReplayError,
    SeedOccurrence,
    evaluate_occurrence,
    evaluate_variant,
    load_replay_spec,
    summarize,
)

UTC = timezone.utc
SPEC = ROOT / "research/calibration/aoo_nq_replay_spec.json"


def dt(hour: int, minute: int) -> datetime:
    return datetime(2025, 6, 2, hour, minute, tzinfo=UTC)


def main() -> int:
    spec = load_replay_spec(SPEC)
    assert spec["instrument"] == "NQ"

    occurrence = SeedOccurrence(
        occurrence_id="SYN-001",
        tick_size=0.25,
        second_sting_touch_ts=dt(14, 0),
        second_sting_touch_price=100.0,
        second_sting_close_ts=dt(14, 15),
        second_sting_close_price=100.5,
        order_flow_leg_low=99.0,
        target_price=103.0,
        bars_after_activation=(
            ReplayBar(dt(14, 0), high=101.0, low=99.5),
            ReplayBar(dt(14, 15), high=103.25, low=99.75),
        ),
    )
    results = evaluate_occurrence(occurrence)
    assert len(results) == 6
    assert summarize(results)["total_variant_results"] == 6
    assert any(row["status"] == "TARGET_FIRST" for row in results)

    # Missing second-sting close produces no trade for that preregistered fill convention only.
    no_close = SeedOccurrence(
        occurrence_id="SYN-002",
        tick_size=0.25,
        second_sting_touch_ts=dt(14, 0),
        second_sting_touch_price=100.0,
        second_sting_close_ts=None,
        second_sting_close_price=None,
        order_flow_leg_low=99.0,
        target_price=103.0,
        bars_after_activation=(ReplayBar(dt(14, 0), high=101.0, low=99.5),),
    )
    close_result = evaluate_variant(no_close, fill_event="SECOND_STING_15M_CLOSE", stop_buffer_ticks=0)
    assert close_result["status"] == "NO_TRADE_PARAMETER_NOT_MET"

    # Same-bar stop and target is deliberately unresolved rather than inventing intrabar ordering.
    ambiguous = SeedOccurrence(
        occurrence_id="SYN-003",
        tick_size=0.25,
        second_sting_touch_ts=dt(14, 0),
        second_sting_touch_price=100.0,
        second_sting_close_ts=dt(14, 0),
        second_sting_close_price=100.0,
        order_flow_leg_low=99.0,
        target_price=102.0,
        bars_after_activation=(ReplayBar(dt(14, 0), high=102.5, low=98.5),),
    )
    row = evaluate_variant(ambiguous, fill_event="SECOND_STING_TOUCH", stop_buffer_ticks=0)
    assert row["status"] == "AMBIGUOUS_INTRABAR_ORDER"

    # Tick size is supplied by provider/instrument metadata and can differ in fixtures.
    buffered = SeedOccurrence(
        occurrence_id="SYN-004",
        tick_size=0.5,
        second_sting_touch_ts=dt(14, 0),
        second_sting_touch_price=100.0,
        second_sting_close_ts=dt(14, 0),
        second_sting_close_price=100.0,
        order_flow_leg_low=99.0,
        target_price=105.0,
        bars_after_activation=(ReplayBar(dt(14, 0), high=101.0, low=98.25),),
    )
    row = evaluate_variant(buffered, fill_event="SECOND_STING_TOUCH", stop_buffer_ticks=2)
    assert row["stop_price"] == 98.0
    assert row["status"] == "UNRESOLVED_WINDOW_END"

    try:
        evaluate_variant(occurrence, fill_event="UNREGISTERED", stop_buffer_ticks=0)
    except ReplayError as exc:
        assert "not preregistered" in str(exc)
    else:
        raise AssertionError("unregistered fill convention must fail closed")

    try:
        evaluate_variant(occurrence, fill_event="SECOND_STING_TOUCH", stop_buffer_ticks=3)
    except ReplayError as exc:
        assert "not preregistered" in str(exc)
    else:
        raise AssertionError("unregistered stop buffer must fail closed")

    print("NQ calibration replay synthetic tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
