#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

LOCK = Path("research/profitability/v8_fvg_followthrough_historical_execution_lock_v1.json")
FORWARD = Path("research/profitability/v8_fvg_followthrough_forward_confirmation_transport_v1.json")
EXPECTED = "ccf0dcbe4ef084c7fc9251423513f107fa8ada14d9a9303b0353ca91f99cdf4e"
PROTOCOL = "79c0289293996f02faa6de1ecb5dcc6d6201a7b98bff1be842bab6cc707b547d"
TRIGGER_SHA = "bb42a146ed756f8a675a4d861c8c211951de29ccaddd3d642ff72cbf62d74747"
READINESS_SHA = "a13a33c588349c7ec11e33324956dbaf9810ba5fa8f88294f43194d33850b3ed"
STRUCTURE_SHA = "a61ef4aa9deb1ed3de36611a12c9afd83ca25aeb8e55cd63004fd2328a39b414"
FORWARD_SHA = "b72b6f8aaaf6c53c6f957917105feba4078cfd6e37c059c49b912cc4203503e8"


def canon(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def verify() -> dict:
    lock = json.loads(LOCK.read_text())
    recorded = lock.pop("execution_lock_sha256")
    assert recorded == EXPECTED
    assert canon(lock) == EXPECTED
    assert lock["status"] == "FROZEN_BEFORE_FIRST_V8_M1_RESPONSE"
    assert lock["protocol_sha256"] == PROTOCOL
    assert lock["trigger_set_sha256"] == TRIGGER_SHA
    assert lock["trigger_count"] == 5482
    assert lock["distinct_knowledge_timestamps"] == 5482
    assert lock["trigger_readiness_sha256"] == READINESS_SHA
    assert lock["structure_manifest_sha256"] == STRUCTURE_SHA
    assert lock["forward_confirmation_transport_sha256"] == FORWARD_SHA
    assert lock["historical_window"] == {
        "start_inclusive": "2010-01-01T00:00:00Z",
        "end_exclusive": "2024-01-01T00:00:00Z",
    }
    provider = lock["m1_provider_contract"]
    assert provider["provider"] == "OANDA_V20"
    assert provider["environment"] == "practice"
    assert provider["instrument"] == "NAS100_USD"
    assert provider["granularity"] == "M1"
    assert provider["price"] == "BA"
    assert provider["synthetic_candles"] is False
    assert provider["synthetic_fills"] is False
    gate = lock["historical_gate"]
    assert gate["minimum_resolved_executed_trades"] == 350
    assert gate["base_profit_factor_gt"] == 1.4
    assert gate["stress_profit_factor_gt"] == 1.15
    assert gate["positive_calendar_year_fraction_gte"] == 0.8
    for key in [
        "parameter_changes_after_first_m1_response",
        "cost_changes_after_first_m1_response",
        "threshold_changes_after_first_m1_response",
        "target_stop_rule_changes_after_first_m1_response",
        "forward_confirmation_access_authorized",
        "paper_execution_authorized",
        "live_execution_authorized",
        "broker_mutation_authorized",
    ]:
        assert lock[key] is False, key

    forward = json.loads(FORWARD.read_text())
    forward_recorded = forward.pop("transport_sha256")
    assert forward_recorded == FORWARD_SHA
    assert canon(forward) == FORWARD_SHA
    assert forward["protocol_sha256"] == PROTOCOL
    assert forward["status"] == "FROZEN_BEFORE_V8_HISTORICAL_M1_RESULT"
    access = forward["access_gate"]
    assert access["historical_gate_must_pass_before_forward_structure_access"] is True
    assert access["forward_m1_access_before_sealed_forward_triggers"] is False
    assert access["post_historical_parameter_changes_allowed"] is False
    assert access["post_historical_cost_changes_allowed"] is False
    assert access["post_historical_threshold_changes_allowed"] is False
    assert forward["safety"] == {
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    return lock


if __name__ == "__main__":
    verify()
    print(f"v8_historical_execution_lock={EXPECTED}")
    print("v8_m1_preoutcome_boundary=PASS")
