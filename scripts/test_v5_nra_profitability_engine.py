#!/usr/bin/env python3
"""Offline sabotage/regression tests for frozen V5 economic mechanics."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import v5_nra_profitability_engine as engine


def z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def bar(dt: datetime, *, ask_open: str, bid_open: str, bid_high: str, bid_low: str, bid_close: str) -> dict:
    return {
        "ts_start_utc": z(dt),
        "ask": {"o": ask_open, "h": ask_open, "l": ask_open, "c": ask_open},
        "bid": {"o": bid_open, "h": bid_high, "l": bid_low, "c": bid_close},
    }


def trigger(trigger_id: str = "A", knowledge: str = "2020-01-02T10:00:00Z") -> dict:
    return {
        "trigger_id": trigger_id,
        "knowledge_time_utc": knowledge,
        "stop_anchor": "95",
        "target_price": "110",
    }


def main() -> None:
    start = datetime(2020, 1, 2, 10, tzinfo=UTC)

    # Target: entry 100.5, risk 5.5, target fill 109.5 => +1.636...R before financing.
    bars = [bar(start, ask_open="100", bid_open="99.8", bid_high="111", bid_low="99", bid_close="110")]
    result = engine.measure_trade(
        trigger(), bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005")
    )
    assert result["status"] == "TARGET"
    assert result["exit_price"] == "109.5"
    assert result["same_m1_stop_and_target"] is False

    # Same M1 target + stop is conservative STOP_FIRST.
    both = [bar(start, ask_open="100", bid_open="99", bid_high="111", bid_low="94", bid_close="105")]
    result = engine.measure_trade(
        trigger(), both, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005")
    )
    assert result["status"] == "STOP"
    assert result["same_m1_stop_and_target"] is True

    # Adverse gap stop uses bid open below stop, then exit slippage.
    gap = [bar(start, ask_open="100", bid_open="93", bid_high="99", bid_low="92", bid_close="94")]
    result = engine.measure_trade(
        trigger(), gap, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005")
    )
    assert result["status"] == "STOP"
    assert result["exit_price"] == "92.5"

    # Invalid structural ordering is rejected before P&L traversal.
    invalid = trigger(); invalid["target_price"] = "99"
    result = engine.measure_trade(
        invalid, bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005")
    )
    assert result["status"] == "INVALID_TARGET_ORDERING"

    # Same-knowledge dedup is explicitly ascending lexicographic trigger id.
    kept, skipped = engine.deduplicate([trigger("B"), trigger("A")])
    assert [row["trigger_id"] for row in kept] == ["A"]
    assert skipped[0]["kept_trigger_id"] == "A"

    # Frozen classifier: 100 profitable trades pass only with stress and positive CI.
    portfolio = {
        "scenario": "BASE",
        "ledger": [
            {
                "trigger_id": f"T{i:03d}",
                "knowledge_time_utc": z(start + timedelta(days=i)),
                "entry_ts_utc": z(start + timedelta(days=i)),
                "exit_ts_utc": z(start + timedelta(days=i, minutes=1)),
                "status": "TARGET",
                "net_r": 1.0,
            }
            for i in range(100)
        ],
    }
    portfolio["ledger_sha256"] = engine.canon(portfolio["ledger"])
    base_metrics = engine.metrics(portfolio)
    stress_portfolio = {**portfolio, "scenario": "STRESS"}
    stress_metrics = engine.metrics(stress_portfolio)
    assert engine.classify(base_metrics, stress_metrics, True) == "V5_HISTORICAL_EDGE_ESTABLISHED"
    assert engine.classify(base_metrics, stress_metrics, False) == "EDGE_NOT_ESTABLISHED"

    print("v5_nra_profitability_engine_regressions=PASS")


if __name__ == "__main__":
    main()
