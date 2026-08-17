#!/usr/bin/env python3
"""Regression guard for the post-V3 current-evidence research disposition."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = ROOT / "research" / "disposition" / "current_evidence_research_boundary_v1.json"


def main() -> None:
    data = json.loads(DISPOSITION.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["disposition_id"] == "ARJO_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_V1"
    assert data["status"] == "NO_VALIDATED_PROFITABLE_EDGE_CURRENT_EVIDENCE"
    assert data["entry_gate"] == "V3_ARGUMENTS_PROFITABILITY_RESULT_READY"
    assert data["output_gate"] == "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"

    # A research boundary must never silently authorize execution.
    assert data["validated_profitable_edge"] is False
    assert data["paper_execution_enabled"] is False
    assert data["live_execution_enabled"] is False
    assert data["broker_mutation_enabled"] is False
    assert data["post_result_refit_permitted"] is False

    families = {item["family"]: item for item in data["tested_families"]}
    assert set(families) == {
        "V2_AOO_FVA_FVG_2CR",
        "V3A_AOO_WITHOUT_GEOMETRIC_ZONE_OVERLAP",
        "V3B_FIXED_MULTI_INDEX_V2_SEMANTICS",
        "V3C_ARGUMENTS_2CR",
    }

    v2 = families["V2_AOO_FVA_FVG_2CR"]
    assert v2["result"] == "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    assert v2["resolved_or_executable_count"] == 10
    assert v2["resolved_or_executable_count"] < v2["frozen_minimum_count"]

    v3a = families["V3A_AOO_WITHOUT_GEOMETRIC_ZONE_OVERLAP"]
    assert v3a["result"] == "COVERAGE_INFEASIBLE_REJECTED"
    assert v3a["development_execution_observable"] == 4
    assert v3a["development_execution_observable"] < v3a["frozen_minimum_count"]
    assert v3a["post_entry_outcomes_accessed"] is False

    v3b = families["V3B_FIXED_MULTI_INDEX_V2_SEMANTICS"]
    assert v3b["result"] == "COVERAGE_INFEASIBLE_REJECTED"
    assert v3b["portfolio_executable_occurrences"] == 1
    assert v3b["portfolio_executable_occurrences"] < v3b["frozen_minimum_count"]
    assert v3b["post_entry_outcomes_accessed"] is False

    v3c = families["V3C_ARGUMENTS_2CR"]
    assert v3c["result"] == "EDGE_NOT_ESTABLISHED"
    assert v3c["workflow_run"] == 32056095283
    assert v3c["result_sha256"] == "e2af05e4fad93def189bedd22cc865ea78be4ac43a1a2e9d5e5822c8b84ff78b"
    assert v3c["base"]["resolved_executed_trades"] == 1304
    assert v3c["base"]["profit_factor"] < 1.20
    assert v3c["base"]["bootstrap_95_low_r"] < 0
    assert v3c["stress"]["net_expectancy_r"] < 0
    assert v3c["stress"]["profit_factor"] < 1.0
    assert v3c["base"]["data_integrity_failures"] == 0
    assert v3c["stress"]["data_integrity_failures"] == 0
    assert v3c["post_result_refit_performed"] is False

    unused = data["unused_first_party_family_disposition"]
    assert unused["executable_unused_family_available"] is False
    assert unused["reviewed_concept_count"] == 36
    assert unused["candidate_count"] == 6
    assert unused["generic_ict_smc_semantic_backfill_permitted"] is False
    assert set(unused["rejected_unrepresented_operational_cues"]) == {
        "RESISTANCE_LIQUIDITY_RUNS",
        "TAPE_READING",
    }

    access = data["first_party_access_debt"]
    assert access["youtube_public_semantic_payload_available"] is False
    assert access["classification"] == "PUBLIC_PAGE_METADATA_AVAILABLE_BUT_SEMANTIC_PAYLOAD_UNAVAILABLE"
    assert access["secondary_transcript_semantic_substitution_permitted"] is False
    assert access["captcha_or_auth_bypass_permitted"] is False

    assert len(data["reentry_conditions"]) >= 3
    assert len(data["forbidden_reentry_paths"]) >= 5
    assert any("V3-C" in item for item in data["forbidden_reentry_paths"])

    print("current-evidence research boundary regression: PASS")


if __name__ == "__main__":
    main()
