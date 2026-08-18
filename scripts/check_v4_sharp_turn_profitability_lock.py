#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

LOCK = Path("research/profitability/v4_sharp_turn_profitability_execution_lock_v1.json")
PROTOCOL = Path("research/profitability/v4_sharp_turn_execution_protocol_v1.json")
READINESS = Path("research/profitability/v4_sharp_turn_trigger_readiness_v1.json")
LOCK_SHA = "846e3c106f9f478fe3ef74ad8152431f42bc2d0cac0d314d9a71d6aef8f0ec30"
PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
READINESS_SHA = "6fb99be106ffa98857693211c5e4814f90a1e874b3255168874a0e1a47a6dba3"
TRIGGER_SHA = "1df6eabb176ef85ce203f3eeb7b76007d0114dfb98d1b1ad0f76f703d779847a"


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    lock = json.loads(LOCK.read_text())
    unsigned = dict(lock)
    recorded = unsigned.pop("spec_sha256")
    assert recorded == LOCK_SHA
    assert canon(unsigned) == LOCK_SHA, "V4 execution lock SHA drift"
    assert lock["status"] == "FROZEN_BEFORE_FIRST_V4_M1_RESPONSE"
    assert lock["parent_protocol_sha256"] == PROTOCOL_SHA
    assert lock["trigger_readiness_sha256"] == READINESS_SHA
    assert lock["canonical_trigger_set_sha256"] == TRIGGER_SHA
    assert lock["canonical_trigger_count"] == 213
    assert lock["canonical_long_triggers"] == 192
    assert lock["canonical_short_triggers"] == 21
    assert lock["boundary_revision"] == "V4_STRICT_CANDLE_COVERAGE_END_V2"
    assert lock["provider_mechanics"]["price"] == "BA"
    assert lock["provider_mechanics"]["granularity"] == "M1"
    assert lock["provider_mechanics"]["last_request_to_must_be_lt_strict_end"] is True
    assert lock["execution"]["fixed_expiry"] is None
    assert lock["execution"]["exit_conditions"] == ["STOP", "TARGET", "RIGHT_CENSORED_DATASET_END"]
    assert lock["execution"]["same_m1_stop_and_target"] == "STOP_FIRST_CONSERVATIVE"
    assert lock["economics"]["target_multiple_r"] == 2.0
    assert lock["economics"]["base_slippage_points_per_side"] == 0.5
    assert lock["economics"]["stress_slippage_points_per_side"] == 1.0
    assert lock["metrics"]["minimum_resolved_executed_trades"] == 100
    assert lock["parameter_changes_after_first_m1_response"] is False
    assert lock["canonical_structure_must_reproduce_before_first_m1_response"] is True
    assert lock["v3c_outcomes_used_for_v4_execution_selection"] is False
    assert lock["paper_execution_authorized"] is False
    assert lock["live_execution_authorized"] is False
    assert lock["broker_mutation_authorized"] is False

    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["protocol_sha256"] == PROTOCOL_SHA
    assert protocol["holding"]["fixed_expiry"] is None
    assert protocol["holding"]["exit_conditions"] == ["STOP", "TARGET", "RIGHT_CENSORED_DATASET_END"]
    assert protocol["entry"]["max_wait_for_first_m1_elapsed_hours"] == 72
    assert protocol["portfolio_policy"]["concurrent_positions"] == "ONE_OPEN_POSITION_MAXIMUM"
    assert protocol["target"]["multiple_r"] == 2.0
    assert protocol["metrics"]["minimum_resolved_executed_trades"] == 100
    assert protocol["metrics"]["bootstrap"] == {"method": "IID executed-trade bootstrap", "replicates": 10000, "seed": 20260817}

    readiness = json.loads(READINESS.read_text())
    assert readiness["readiness_sha256"] == READINESS_SHA
    assert readiness["canonical_full_trigger_set_sha256"] == TRIGGER_SHA
    assert readiness["trigger_count"] == 213
    assert readiness["distinct_trigger_knowledge_times"] == 213
    assert readiness["sample_necessary_condition_met"] is True
    assert readiness["economic_outcomes_accessed"] is False

    print(json.dumps({
        "status": "V4_SHARP_TURN_PROFITABILITY_LOCK_VERIFIED",
        "lock_sha256": LOCK_SHA,
        "protocol_sha256": PROTOCOL_SHA,
        "readiness_sha256": READINESS_SHA,
        "trigger_set_sha256": TRIGGER_SHA,
        "first_m1_response_authorized": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
