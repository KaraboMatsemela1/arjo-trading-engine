#!/usr/bin/env python3
"""Verify the pre-result V5 forward family-specific OOS confirmation freeze."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROTOCOL = Path("research/profitability/v5_nra_forward_confirmation_protocol_v1.json")
EXPECTED_SHA = "d86258ba66ba9eba20ed72e57af0368b90512ec24bc8e8a42f82be5cce1910b4"


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def verify(path: Path = PROTOCOL) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload.pop("protocol_sha256", "")
    assert recorded == EXPECTED_SHA and canon(payload) == EXPECTED_SHA, "V5 confirmation protocol SHA drift"
    assert payload["status"] == "FROZEN_BEFORE_V5_HISTORICAL_RESULT_VISIBILITY"
    window = payload["confirmation_window"]
    assert window["score_start"] == "2024-01-01T00:00:00Z"
    assert window["score_end_exclusive"] == "2026-08-01T00:00:00Z"
    assert window["v5_m1_outcomes_accessed_before_freeze"] is False
    assert payload["conditional_access"]["confirmation_m1_authorized_before_historical_pass"] is False
    assert payload["conditional_access"]["confirmation_m1_requires_historical_classification"] == "V5_HISTORICAL_EDGE_ESTABLISHED"
    assert payload["mechanics"]["identical_to_historical_v5"] is True
    assert payload["mechanics"]["post_historical_tuning_allowed"] is False
    gate = payload["validation_gate"]
    assert gate["minimum_confirmation_resolved_executed_trades"] == 100
    assert gate["base_profit_factor_gt"] == 1.2
    assert gate["bootstrap_95pct_lower_expectancy_r_gt"] == 0.0
    assert gate["stress_profit_factor_gt"] == 1.0
    assert gate["pass_classification"] == "VALIDATED_PROFITABLE_EDGE_V5_FAMILY_SPECIFIC_FORWARD_OOS"
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
        print(f"V5 forward confirmation protocol verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"v5_forward_confirmation_protocol={EXPECTED_SHA}")
    print("v5_confirmation_pre_result_freeze=PASS")
