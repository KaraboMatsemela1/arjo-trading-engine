#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/profitability/v4_sharp_turn_execution_protocol_v1.json"
BOUNDARY = ROOT / "research/profitability/v4_sharp_turn_execution_evidence_boundary.json"
SOURCE_RECOVERY = ROOT / "research/v4_sharp_turn_candidate.json"
EXPECTED_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def validate_protocol(p: dict) -> None:
    recorded = p.get("protocol_sha256", "")
    material = dict(p)
    material.pop("protocol_sha256", None)
    assert recorded == EXPECTED_SHA, "unexpected recorded protocol SHA"
    assert canon(material) == EXPECTED_SHA, "protocol SHA drift"
    assert p["protocol_id"] == "ARJO_V4_SHARP_TURN_D1_H1_EXECUTION_V1"
    assert p["status"] == "FROZEN_BEFORE_V4_MARKET_OUTCOME_ACCESS"
    assert p["family"]["independent_of_failed_family"] == "V3_C_ARGUMENTS_2CR"
    assert p["family"]["v3c_outcomes_used_for_rule_selection"] is False
    assert p["semantic_boundary"]["engine_conventions_are_not_arjo_semantic_claims"] is True

    md = p["market_data"]
    assert md["provider"] == "OANDA_V20"
    assert md["instrument"] == "NAS100_USD"
    assert md["structure_granularities"] == ["M", "W", "D", "H1"]
    assert md["execution_price"] == "M1 BID/ASK"
    assert md["daily_alignment_hour"] == 17
    assert md["alignment_timezone"] == "America/New_York"
    assert md["weekly_alignment"] == "Friday"
    assert md["historical_window_classification"] == "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT"
    assert md["request_m1_only_after_v4_trigger_set_is_sealed"] is True
    assert md["no_market_request_authorized_by_protocol_freeze_issue"] is True

    assert p["fvg"]["first_intersection_consumes_context"] is True
    assert p["direction"]["required_timeframes"] == ["M", "W", "D"]
    assert p["sharp_turn"]["entry_timeframe"] == "H1"
    assert p["entry"]["pending_retracement"] is False
    assert p["risk"]["invalid_if_risk_nonpositive"] is True
    assert p["target"]["multiple_r"] == 2.0
    assert p["intrabar_order"]["same_m1_stop_and_target"] == "STOP_FIRST_CONSERVATIVE"
    assert p["holding"]["fixed_expiry"] is None
    assert p["holding"]["right_censored_trade_excluded_from_resolved_metrics"] is True
    assert p["portfolio_policy"]["concurrent_positions"] == "ONE_OPEN_POSITION_MAXIMUM"

    econ = p["economics"]
    assert econ["base_slippage_points_per_side"] == 0.5
    assert econ["stress_slippage_points_per_side"] == 1.0
    assert econ["financing_base_r_per_1440_complete_m1_bars"] == 0.005
    assert econ["financing_stress_r_per_1440_complete_m1_bars"] == 0.01

    assert p["metrics"]["minimum_resolved_executed_trades"] == 100
    prelim = p["classification_rules"]["PRELIMINARY_HISTORICAL_EDGE"]
    assert prelim["base_profit_factor_gt"] == 1.2
    assert prelim["bootstrap_95pct_ci_lower_net_expectancy_r_gt"] == 0.0
    assert prelim["stress_net_expectancy_r_gt"] == 0.0
    assert prelim["stress_profit_factor_gt"] == 1.0

    assert p["staged_access"]["no_economic_outcomes_during_protocol_freeze"] is True
    assert p["authorization"] == {
        "market_data_execution_for_issue_242": False,
        "backtest_execution": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }


def validate_boundary(b: dict) -> None:
    assert b["protocol_sha256"] == EXPECTED_SHA
    assert b["status"] == "FROZEN_BEFORE_V4_MARKET_OUTCOME_ACCESS"
    assert b["v4_market_data_requested"] is False
    assert b["v4_triggers_enumerated"] is False
    assert b["v4_economic_outcomes_accessed"] is False
    assert b["v4_performance_metrics_accessed"] is False
    assert b["v3c_outcomes_used_for_v4_rule_selection"] is False
    assert b["historical_window_is_untouched_family_holdout"] is False
    assert b["source_rules_vs_engine_conventions_separated"] is True
    assert b["provider_contract"]["no_request_in_issue_242"] is True
    assert b["authorization"] == {
        "market_data_execution": False,
        "backtest_execution": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }


def main() -> None:
    p = json.loads(PROTOCOL.read_text())
    b = json.loads(BOUNDARY.read_text())
    s = json.loads(SOURCE_RECOVERY.read_text())
    validate_protocol(p)
    validate_boundary(b)
    assert s["candidate_id"] == "V4_SHARP_TURN_FVG"
    assert s["family_independence"]["v3c_outcomes_consulted_for_selection"] is False
    print(json.dumps({
        "status": "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN",
        "protocol_sha256": EXPECTED_SHA,
        "v4_market_data_requested": False,
        "v4_economic_outcomes_accessed": False,
        "backtest_authorized": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
