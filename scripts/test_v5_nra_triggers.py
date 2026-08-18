#!/usr/bin/env python3
"""Offline regressions for V5 H4/H1 structural trigger reconstruction."""
from __future__ import annotations

from v5_nra_triggers import compare_reconstructions, reconstruct


def candle(time: str, high: str, low: str, close: str, open_: str | None = None) -> dict:
    return {
        "time": time,
        "open": open_ or close,
        "high": high,
        "low": low,
        "close": close,
        "complete": True,
        "volume": 1,
    }


def fixture() -> tuple[list[dict], list[dict]]:
    h4 = [
        candle("2019-12-30T00:00:00Z", "100", "90", "95"),
        candle("2019-12-30T04:00:00Z", "110", "94", "105"),
        candle("2019-12-30T08:00:00Z", "105", "92", "100"),
        candle("2019-12-30T12:00:00Z", "108", "96", "104"),
    ]
    h1 = [
        candle("2020-01-02T00:00:00Z", "104", "100", "102"),
        candle("2020-01-02T01:00:00Z", "101", "96", "98"),
        candle("2020-01-02T02:00:00Z", "95", "90", "92"),
        candle("2020-01-02T03:00:00Z", "98", "94", "94"),
        candle("2020-01-02T04:00:00Z", "97", "93", "96"),
        candle("2020-01-02T05:00:00Z", "101", "96", "99"),
        candle("2020-01-02T06:00:00Z", "103", "98", "101"),
    ]
    return h4, h1


def main() -> None:
    h4, h1 = fixture()
    triggers, comparison = compare_reconstructions(h4, h1)
    assert comparison["exact_match"] is True
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger["knowledge_time_utc"] == "2020-01-02T06:00:00Z"
    assert trigger["trigger_close"] == "99"
    assert trigger["rejection_high"] == "98"
    assert trigger["stop_anchor"] == "93"
    assert trigger["target_price"] == "110"
    assert trigger["other_active_overhead_resistance_count"] == 0

    broken_h4 = [dict(row) for row in h4]
    broken_h4[1]["high"] = "98"
    no_target, _ = reconstruct(broken_h4, h1)
    assert no_target == []
    print("v5_nra_trigger_offline_regressions=PASS")


if __name__ == "__main__":
    main()
