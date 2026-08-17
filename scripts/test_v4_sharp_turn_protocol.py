#!/usr/bin/env python3
from __future__ import annotations

import copy
import json

import check_v4_sharp_turn_execution_protocol as checker


def expect_failure(fn, value: dict) -> None:
    try:
        fn(value)
    except AssertionError:
        return
    raise AssertionError("sabotaged V4 protocol/boundary unexpectedly passed")


def main() -> None:
    protocol = json.loads(checker.PROTOCOL.read_text())
    boundary = json.loads(checker.BOUNDARY.read_text())

    checker.validate_protocol(protocol)
    checker.validate_boundary(boundary)

    cases: list[tuple[str, dict]] = []

    x = copy.deepcopy(protocol)
    x["protocol_sha256"] = "0" * 64
    cases.append(("sha", x))

    x = copy.deepcopy(protocol)
    x["market_data"]["no_market_request_authorized_by_protocol_freeze_issue"] = False
    cases.append(("market_access", x))

    x = copy.deepcopy(protocol)
    x["family"]["v3c_outcomes_used_for_rule_selection"] = True
    cases.append(("v3c_leakage", x))

    x = copy.deepcopy(protocol)
    x["market_data"]["historical_window_classification"] = "UNTOUCHED_OOS"
    cases.append(("false_holdout_claim", x))

    x = copy.deepcopy(protocol)
    x["target"]["multiple_r"] = 3.0
    cases.append(("target_refit", x))

    x = copy.deepcopy(protocol)
    x["economics"]["stress_slippage_points_per_side"] = 0.0
    cases.append(("stress_weakening", x))

    x = copy.deepcopy(protocol)
    x["authorization"]["paper_execution"] = True
    cases.append(("paper_enable", x))

    for name, sabotaged in cases:
        expect_failure(checker.validate_protocol, sabotaged)
        print(f"sabotage_{name}=PASS")

    b = copy.deepcopy(boundary)
    b["v4_economic_outcomes_accessed"] = True
    expect_failure(checker.validate_boundary, b)
    print("sabotage_outcome_access=PASS")

    b = copy.deepcopy(boundary)
    b["authorization"]["broker_mutation"] = True
    expect_failure(checker.validate_boundary, b)
    print("sabotage_broker_mutation=PASS")

    print("v4_sharp_turn_protocol_sabotage_suite=PASS")


if __name__ == "__main__":
    main()
