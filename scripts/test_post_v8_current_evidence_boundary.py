#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "research/disposition/post_v8_current_evidence_research_boundary_v1.json"
EXPECTED_SHA = "70962787ae0c55ed83ec9f5f62ee1968a48563b42b7ee19dee7370b5cd9206cb"
EXPECTED_RESULTS = {
    "v3c": "e2af05e4fad93def189bedd22cc865ea78be4ac43a1a2e9d5e5822c8b84ff78b",
    "v4": "611cc822dcc5103ed700d245e3ffb95404ca9c41459a43f9b5183aa84aedf6b5",
    "v5": "4474926ae20e67d5e23010a62654d41d2a3f6cefbff835f7c122e011c64d7345",
    "v6": "4fcf249633f165250a99b602dd1cdd7bd20b07f6fbd27d09d1c8ee632a989fec",
    "v7": "9856cb07a6afe9c3d9bf1e611b1f614352c3f95e06b54be6841c5a614a93deaa",
    "v8": "0bba2f2feb2f51cad8c89b31ff9102ffe107caafba1159d77151b9043e153f80",
}


def canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    boundary = json.loads(BOUNDARY.read_text())
    recorded = boundary.pop("boundary_sha256")
    assert recorded == EXPECTED_SHA
    assert canonical_sha(boundary) == EXPECTED_SHA

    assert boundary["disposition_id"] == "ARJO_POST_V8_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_V1"
    assert boundary["dependency_issue"] == 290
    assert boundary["entry_gate"] == "V8_FVG_FOLLOWTHROUGH_HISTORICAL_PROFITABILITY_RESULT_READY"
    assert boundary["output_gate"] == "POST_V8_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert boundary["status"] == "NO_VALIDATED_PROFITABLE_EDGE_CURRENT_EVIDENCE_POST_V8"
    assert boundary["validated_profitable_edge"] is False
    assert boundary["economic_family_search_count"] == 6

    failed = boundary["sealed_failed_economic_families"]
    assert set(failed) == set(EXPECTED_RESULTS)
    for family, expected_sha in EXPECTED_RESULTS.items():
        assert failed[family]["classification"] == "EDGE_NOT_ESTABLISHED"
        assert failed[family]["result_sha256"] == expected_sha
        assert failed[family]["post_result_refit_permitted"] is False

    v8 = failed["v8"]
    assert v8["canonical_workflow_run_id"] == 32180745000
    assert v8["resolved_executed_trades_base"] == 3669
    assert v8["resolved_executed_trades_stress"] == 3629
    assert v8["base_net_expectancy_r"] == -0.23440107691220544
    assert v8["base_profit_factor"] == 0.637854890965066
    assert v8["base_bootstrap_95pct_ci_net_expectancy_r"] == [
        -0.27691947579039256,
        -0.1909480729998966,
    ]
    assert v8["positive_calendar_year_fraction"] == 0.0
    assert v8["base_data_integrity_failures"] == 2
    assert v8["stress_net_expectancy_r"] == -0.3104670341746885
    assert v8["stress_profit_factor"] == 0.5445883202178201
    assert v8["stress_bootstrap_95pct_ci_net_expectancy_r"] == [
        -0.34994952454132744,
        -0.26967025087678825,
    ]
    assert v8["stress_data_integrity_failures"] == 2
    assert v8["synthetic_fills"] == 0
    assert v8["forward_confirmation_authorized"] is False
    assert v8["forward_confirmation_outcomes_accessed"] is False

    excluded = boundary["outcome_blind_exclusions"]
    assert excluded["v2"]["executable_occurrences"] == 10
    assert excluded["v3a"]["execution_observable_occurrences"] == 4
    assert excluded["v3b"]["portfolio_executable_occurrences"] == 1
    assert all(item["frozen_minimum"] == 30 for item in excluded.values())
    assert all(
        item["status"] == "INSUFFICIENT_OCCURRENCES_NO_ECONOMIC_OUTCOME_ACCESS"
        for item in excluded.values()
    )

    search = boundary["family_search_boundary"]
    assert search["v9_frozen_before_v8_result"] is False
    assert search["reactive_v9_creation_permitted"] is False
    assert search["failed_family_ledger_mining_permitted"] is False
    assert search["generic_ict_smc_semantic_backfill_permitted"] is False

    assert len(boundary["reentry_conditions"]) == 3
    assert boundary["post_result_refit_permitted"] is False
    assert boundary["v8_forward_confirmation_authorized"] is False
    assert boundary["v8_forward_confirmation_outcomes_accessed"] is False
    assert boundary["paper_execution_enabled"] is False
    assert boundary["live_execution_enabled"] is False
    assert boundary["broker_mutation_enabled"] is False

    print("POST_V8_CURRENT_EVIDENCE_NO_EDGE_BOUNDARY_READY")


if __name__ == "__main__":
    main()
