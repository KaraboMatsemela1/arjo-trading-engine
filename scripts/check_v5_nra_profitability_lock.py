#!/usr/bin/env python3
"""Verify the immutable V5 economic execution lock before first M1 access."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import v5_nra_profitability_engine as engine

LOCK = Path("research/profitability/v5_nra_profitability_execution_lock_v1.json")
EXPECTED_LOCK_SHA = "7c509c72e290a427d9a44e5ab133e624e766f73450e78ed68790d1b3d51f6b87"
EXPECTED_PROTOCOL_SHA = "f01d01ffcb4711f53b86a71c14fec0b6a145fafc9edc140d41d602d29eadb5ff"
EXPECTED_TRANSPORT_SHA = "8a31db889e5105a8a7a351d79ce247cfaf2bc68451e6565ef80aac17d72580f0"
EXPECTED_TRIGGER_SHA = "b65671c07e811924341a75c8e21434d275c4b6283febd2c45978b59ebfe4bb10"
EXPECTED_READINESS_SHA = "9fcdf27b9fbc2d14bd878d3ebfd73a19fe32282066502e6c3350ea9ca8bb2a28"


def verify(path: Path = LOCK) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload.pop("lock_sha256", "")
    assert recorded == EXPECTED_LOCK_SHA
    assert engine.canon(payload) == EXPECTED_LOCK_SHA, "V5 economic lock SHA drift"
    assert payload["status"] == "FROZEN_BEFORE_FIRST_V5_M1_RESPONSE"
    assert payload["protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    assert payload["structure_transport_sha256"] == EXPECTED_TRANSPORT_SHA
    assert payload["trigger_set_sha256"] == EXPECTED_TRIGGER_SHA
    assert payload["trigger_readiness_sha256"] == EXPECTED_READINESS_SHA
    assert payload["trigger_count"] == 4737
    assert payload["pre_m1_reconstruction"]["no_first_m1_response_before_all_checks_pass"] is True
    assert payload["m1_provider"]["price"] == "BA"
    assert payload["m1_provider"]["granularity"] == "M1"
    assert payload["m1_provider"]["strict_end_exclusive"] == "2024-01-01T00:00:00Z"
    assert payload["signal_ordering"]["same_knowledge_time_dedup"] == "LEXICOGRAPHIC_ASCENDING_TRIGGER_ID_FIRST"
    assert payload["risk_target"]["same_m1_stop_and_target"] == "STOP_FIRST_CONSERVATIVE"
    assert payload["historical_edge_gate"]["base_profit_factor_gt"] == 1.2
    assert payload["historical_edge_gate"]["minimum_resolved_executed_trades"] == 100
    assert payload["bootstrap"] == {
        "method": "IID_EXECUTED_TRADE_BOOTSTRAP",
        "replicates": 10000,
        "seed": 20260818,
    }
    assert payload["classification"]["validated_profitable_edge_from_backward_history_alone"] is False
    assert payload["post_first_m1"]["parameter_changes_allowed"] is False
    assert payload["post_first_m1"]["failed_family_tuning_allowed"] is False
    assert payload["safety"] == {
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    return payload


if __name__ == "__main__":
    try:
        verify()
    except Exception as exc:
        print(f"V5 profitability lock verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"v5_profitability_lock={EXPECTED_LOCK_SHA}")
    print("v5_first_m1_boundary=PASS")
