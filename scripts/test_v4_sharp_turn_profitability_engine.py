#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import v4_sharp_turn_profitability_engine as e

END = datetime(2024, 1, 1, tzinfo=UTC)
T0 = datetime(2020, 1, 2, 10, tzinfo=UTC)


def z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def bar(minute: int, *, bid_o=100, bid_h=101, bid_l=99, bid_c=100, ask_o=101, ask_h=102, ask_l=100, ask_c=101) -> dict:
    return {
        "ts_start_utc": z(T0 + timedelta(minutes=minute)),
        "bid": {"o": str(bid_o), "h": str(bid_h), "l": str(bid_l), "c": str(bid_c)},
        "ask": {"o": str(ask_o), "h": str(ask_h), "l": str(ask_l), "c": str(ask_c)},
    }


def trigger(tid: str, direction: str, stop: str, minute: int = 0) -> dict:
    return {
        "trigger_id": tid,
        "direction": direction,
        "trigger_knowledge_time_utc": z(T0 + timedelta(minutes=minute)),
        "stop_anchor": stop,
    }


def test_long_target_and_cost() -> None:
    t = trigger("L", "LONG", "95")
    bars = [bar(0), bar(1, bid_o=102, bid_h=115, bid_l=101, bid_c=114, ask_o=103, ask_h=116, ask_l=102, ask_c=115)]
    r = e.measure_trade(t, bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"), dataset_end=END)
    assert r["status"] == "TARGET"
    assert r["entry_price"] == "101.5"
    assert r["risk_points"] == "6.5"
    assert r["target_price"] == "114.5"
    assert r["exit_price"] == "114.0"
    assert r["complete_m1_bars_held"] == 2
    assert r["net_r"] < 2.0


def test_short_target_and_cost() -> None:
    t = trigger("S", "SHORT", "106")
    bars = [bar(0), bar(1, bid_o=98, bid_h=99, bid_l=85, bid_c=86, ask_o=99, ask_h=100, ask_l=86, ask_c=87)]
    r = e.measure_trade(t, bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"), dataset_end=END)
    assert r["status"] == "TARGET"
    assert r["entry_price"] == "99.5"
    assert r["risk_points"] == "6.5"
    assert r["target_price"] == "86.5"
    assert r["exit_price"] == "87.0"
    assert r["net_r"] < 2.0


def test_same_bar_stop_first_long_and_short() -> None:
    long_r = e.measure_trade(
        trigger("L2", "LONG", "95"),
        [bar(0, bid_o=100, bid_h=120, bid_l=90, bid_c=100, ask_o=101, ask_h=121, ask_l=91, ask_c=101)],
        slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END,
    )
    assert long_r["status"] == "STOP" and long_r["same_m1_stop_and_target"] is True
    short_r = e.measure_trade(
        trigger("S2", "SHORT", "106"),
        [bar(0, bid_o=100, bid_h=110, bid_l=80, bid_c=100, ask_o=101, ask_h=120, ask_l=80, ask_c=101)],
        slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END,
    )
    assert short_r["status"] == "STOP" and short_r["same_m1_stop_and_target"] is True


def test_adverse_gap_stop_no_favorable_target_gap() -> None:
    long_stop = e.measure_trade(trigger("LG", "LONG", "95"), [bar(0, bid_o=90, bid_h=92, bid_l=89, bid_c=91, ask_o=101, ask_h=102, ask_l=100, ask_c=101)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END)
    assert long_stop["status"] == "STOP" and long_stop["exit_price"] == "89.5"
    short_stop = e.measure_trade(trigger("SG", "SHORT", "106"), [bar(0, bid_o=100, bid_h=101, bid_l=99, bid_c=100, ask_o=110, ask_h=111, ask_l=109, ask_c=110)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END)
    assert short_stop["status"] == "STOP" and short_stop["exit_price"] == "110.5"


def test_invalid_risk_and_wait_guard() -> None:
    invalid = e.measure_trade(trigger("BAD", "LONG", "102"), [bar(0)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END)
    assert invalid["status"] == "INVALID_RISK_ORDERING"
    late_bar = dict(bar(0)); late_bar["ts_start_utc"] = z(T0 + timedelta(hours=73))
    late = e.measure_trade(trigger("LATE", "LONG", "95"), [late_bar], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END)
    assert late["status"] == "DATA_INTEGRITY_FAILURE"


def test_right_censor_is_not_resolved() -> None:
    r = e.measure_trade(trigger("C", "LONG", "50"), [bar(0), bar(1)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"), dataset_end=T0 + timedelta(minutes=2))
    assert r["status"] == "RIGHT_CENSORED_DATASET_END"
    p = {"scenario": "BASE", "ledger": [r], "ledger_sha256": e.canon([r])}
    m = e.metrics(p)
    assert m["resolved_executed_trades"] == 0
    assert m["right_censored_signals"] == 1


def test_concurrency_and_dedup() -> None:
    triggers = [trigger("A", "LONG", "95", 0), trigger("B", "SHORT", "106", 0), trigger("C", "SHORT", "106", 1)]
    def provider(_):
        return [bar(0), bar(1, bid_o=102, bid_h=115, bid_l=101, bid_c=114, ask_o=103, ask_h=116, ask_l=102, ask_c=115)]
    p = e.evaluate_portfolio(triggers, provider, scenario="BASE", slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0"), dataset_end=END)
    statuses = [x["status"] for x in p["ledger"]]
    assert "SKIPPED_DUPLICATE_TRIGGER_TIME" in statuses
    assert "SKIPPED_CONCURRENT_POSITION" in statuses


def test_stress_is_never_better_on_same_long_target_path() -> None:
    t = trigger("STRESS", "LONG", "95")
    bars = [bar(0), bar(1, bid_o=102, bid_h=116, bid_l=101, bid_c=115, ask_o=103, ask_h=117, ask_l=102, ask_c=116)]
    base = e.measure_trade(t, bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"), dataset_end=END)
    stress = e.measure_trade(t, bars, slip_points=Decimal("1.0"), financing_r_per_1440=Decimal("0.01"), dataset_end=END)
    assert base["status"] == stress["status"] == "TARGET"
    assert stress["net_r"] < base["net_r"]


def test_classification_thresholds() -> None:
    def m(n, exp, pf, lo):
        return {
            "resolved_executed_trades": n,
            "net_expectancy_r": exp,
            "profit_factor": pf,
            "no_negative_trades": False,
            "positive_r_sum": 100.0,
            "bootstrap_95pct_ci_net_expectancy_r": [lo, 0.5],
            "data_integrity_failures": 0,
            "synthetic_fills": 0,
            "positive_calendar_year_fraction": 0.8,
        }
    assert e.classify(m(99, .2, 1.5, .1), m(99, .1, 1.2, .05)) == "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    assert e.classify(m(100, .2, 1.1, .1), m(100, .1, 1.2, .05)) == "EDGE_NOT_ESTABLISHED"
    assert e.classify(m(100, .2, 1.5, .1), m(100, .1, 1.2, .05)) == "PRELIMINARY_HISTORICAL_EDGE"
    assert e.classify(m(250, .2, 1.5, .1), m(250, .1, 1.2, .05)) == "STRONG_HISTORICAL_EDGE"


def main() -> None:
    test_long_target_and_cost()
    test_short_target_and_cost()
    test_same_bar_stop_first_long_and_short()
    test_adverse_gap_stop_no_favorable_target_gap()
    test_invalid_risk_and_wait_guard()
    test_right_censor_is_not_resolved()
    test_concurrency_and_dedup()
    test_stress_is_never_better_on_same_long_target_path()
    test_classification_thresholds()
    print("V4 Sharp Turn profitability engine pre-M1 sabotage tests passed")


if __name__ == "__main__":
    main()
