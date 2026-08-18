#!/usr/bin/env python3
"""Verify the frozen V5 No-Resistance AoO protocol before any V5 outcomes."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

PROTOCOL = Path("research/profitability/v5_no_resistance_aoo_protocol_v1.json")
BOUNDARY = Path("research/profitability/v5_no_resistance_aoo_evidence_boundary_v1.json")
EXPECTED_PROTOCOL_SHA = "f01d01ffcb4711f53b86a71c14fec0b6a145fafc9edc140d41d602d29eadb5ff"
EXPECTED_BOUNDARY_SHA = "c0e07cad4987223d98141d72d2750375a1abd59a4ba31e456dfdcfc963724d7b"

def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def verify(protocol_path: Path = PROTOCOL, boundary_path: Path = BOUNDARY) -> None:
    p = json.loads(protocol_path.read_text(encoding="utf-8"))
    b = json.loads(boundary_path.read_text(encoding="utf-8"))
    recorded = p.pop("protocol_sha256", "")
    assert recorded == EXPECTED_PROTOCOL_SHA and canon(p) == EXPECTED_PROTOCOL_SHA, "V5 protocol SHA drift"
    assert p["status"] == "FROZEN_BEFORE_V5_MARKET_OUTCOME_ACCESS"
    assert p["family"]["failed_v3c_or_v4_parameters_modified"] is False
    assert p["family"]["v3c_outcomes_used_for_v5_rule_selection"] is False
    assert p["family"]["v4_outcomes_used_for_v5_rule_selection"] is False
    assert p["semantic_boundary"]["engine_conventions_are_not_arjo_semantic_claims"] is True
    assert p["h4_target"]["ath_proxy_forbidden"] is True
    assert p["market_data"]["structure_granularities"] == ["H4", "H1"]
    assert p["market_data"]["structure_price"] == "MID"
    assert p["market_data"]["execution_price"] == "M1 BID/ASK"
    assert p["market_data"]["request_m1_only_after_v5_trigger_set_is_sealed"] is True
    assert p["market_data"]["no_market_request_authorized_by_protocol_freeze_issue"] is True
    assert p["metrics"]["minimum_resolved_executed_trades"] == 100
    assert p["classification_rules"]["V5_HISTORICAL_EDGE_ESTABLISHED"]["base_profit_factor_gt"] == 1.2
    assert p["classification_rules"]["VALIDATED_PROFITABLE_EDGE"].startswith("PROHIBITED_FROM_BACKWARD_HISTORY_ALONE")
    assert p["authorization"] == {
        "market_data_execution_for_issue_252": False,
        "backtest_execution_for_issue_252": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }
    brecorded = b.pop("boundary_sha256", "")
    assert brecorded == EXPECTED_BOUNDARY_SHA and canon(b) == EXPECTED_BOUNDARY_SHA, "V5 boundary SHA drift"
    for key in (
        "v5_market_data_requested", "v5_structure_reconstructed", "v5_triggers_enumerated",
        "v5_m1_bid_ask_requested", "v5_economic_outcomes_accessed", "v5_performance_metrics_accessed",
        "v3c_outcomes_used_for_rule_selection", "v4_outcomes_used_for_rule_selection",
        "failed_family_post_result_tuning", "paper_execution_authorized",
        "live_execution_authorized", "broker_mutation_authorized",
    ):
        assert b[key] is False, f"pre-outcome boundary violated: {key}"
    assert b["protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    assert b["derived_profile_not_exact_arjo_strategy"] is True
    assert b["historical_window_is_pristine_market_holdout"] is False

if __name__ == "__main__":
    try:
        verify()
    except Exception as exc:
        print(f"V5 protocol verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"v5_no_resistance_aoo_protocol={EXPECTED_PROTOCOL_SHA}")
    print("v5_pre_outcome_boundary=PASS")
