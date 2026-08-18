#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy

from v8_fvg_followthrough_backtest_metrics import classify


def metric(
    *,
    resolved: int = 350,
    expectancy: float = 0.20,
    pf: float = 1.50,
    lower: float = 0.05,
    positive_years: float = 0.85,
) -> dict:
    return {
        "resolved_executed_trades": resolved,
        "net_expectancy_r": expectancy,
        "profit_factor": pf,
        "no_negative_trades": False,
        "positive_r_sum": 100.0,
        "bootstrap_95pct_ci_net_expectancy_r": [lower, 0.30],
        "positive_calendar_year_fraction": positive_years,
        "data_integrity_failures": 0,
        "synthetic_fills": 0,
    }


def run() -> None:
    base = metric()
    stress = metric(expectancy=0.08, pf=1.20)
    assert classify(base, stress) == "V8_FVG_FOLLOWTHROUGH_HISTORICAL_EDGE_ESTABLISHED"

    x = deepcopy(base)
    x["profit_factor"] = 1.40
    assert classify(x, stress) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(base)
    x["bootstrap_95pct_ci_net_expectancy_r"] = [0.0, 0.20]
    assert classify(x, stress) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(base)
    x["positive_calendar_year_fraction"] = 0.799
    assert classify(x, stress) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(stress)
    x["profit_factor"] = 1.15
    assert classify(base, x) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(stress)
    x["net_expectancy_r"] = 0.0
    assert classify(base, x) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(base)
    x["data_integrity_failures"] = 1
    assert classify(x, stress) == "EDGE_NOT_ESTABLISHED"

    x = deepcopy(stress)
    x["synthetic_fills"] = 1
    assert classify(base, x) == "EDGE_NOT_ESTABLISHED"

    assert (
        classify(metric(resolved=349), stress)
        == "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    )
    print("v8_fvg_followthrough_backtest_gate_tests=PASS")


if __name__ == "__main__":
    run()
