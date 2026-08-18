#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "research/disposition/post_v4_current_evidence_research_boundary_v1.json"
V1 = ROOT / "research/disposition/current_evidence_research_boundary_v1.json"
REAUDIT = ROOT / "research/disposition/post_v4_candidate_reaudit_v1.json"
V4_RESULT = ROOT / "research/profitability/v4_sharp_turn_result/result.json"

EXPECTED_BOUNDARY_SHA = "28b8be6ed43a41147736262ae57fd35c89aa51d550dd3d5437e9b3667f992be2"
EXPECTED_V1_BLOB_CONTENT_SHA1 = "1927b17edca70a0970b02759e930c6ccf35b5a64"
EXPECTED_REAUDIT_SHA = "05ed66db6c433bb3b25f14a7abebf2be9e0bb12f538599fcecdb7932061a30d4"
EXPECTED_V4_RESULT_SHA = "611cc822dcc5103ed700d245e3ffb95404ca9c41459a43f9b5183aa84aedf6b5"


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def main() -> None:
    boundary = json.loads(BOUNDARY.read_text())
    recorded = boundary.pop("boundary_sha256")
    assert recorded == EXPECTED_BOUNDARY_SHA
    assert canon(boundary) == EXPECTED_BOUNDARY_SHA
    assert boundary["output_gate"] == "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert boundary["status"] == "NO_VALIDATED_PROFITABLE_EDGE_CURRENT_EVIDENCE_POST_V4"
    assert boundary["validated_profitable_edge"] is False
    assert boundary["post_result_refit_permitted"] is False
    assert boundary["paper_execution_enabled"] is False
    assert boundary["live_execution_enabled"] is False
    assert boundary["broker_mutation_enabled"] is False

    assert git_blob_sha1(V1) == EXPECTED_V1_BLOB_CONTENT_SHA1
    v1 = json.loads(V1.read_text())
    assert v1["disposition_id"] == "ARJO_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_V1"
    assert v1["output_gate"] == "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"

    reaudit = json.loads(REAUDIT.read_text())
    unsigned_reaudit = dict(reaudit)
    assert unsigned_reaudit.pop("audit_sha256") == EXPECTED_REAUDIT_SHA
    assert canon(unsigned_reaudit) == EXPECTED_REAUDIT_SHA
    assert reaudit["status"] == "NO_UNUSED_EXECUTABLE_FIRST_PARTY_FAMILY"
    assert reaudit["reviewed_concept_count"] == 36
    assert reaudit["phase5_candidate_count"] == 6
    assert all(x["disposition"] == "INCOMPLETE_SEMANTICS_NO_EXECUTION" for x in reaudit["phase5_candidates"])
    assert all(x["outcome_access_authorized"] is False for x in reaudit["phase5_candidates"])
    assert reaudit["semantic_policy"]["post_result_family_tuning_permitted"] is False
    assert reaudit["semantic_policy"]["generic_ict_smc_backfill_permitted"] is False

    v4 = json.loads(V4_RESULT.read_text())
    assert v4["status"] == "V4_SHARP_TURN_PROFITABILITY_RESULT_READY"
    assert v4["classification"] == "EDGE_NOT_ESTABLISHED"
    assert v4["result_sha256"] == EXPECTED_V4_RESULT_SHA
    assert v4["validated_historical_edge"] is False
    assert v4["strong_historical_edge"] is False
    assert v4["no_refit_performed"] is True
    assert v4["parameter_changes_after_first_m1_response"] is False
    assert v4["post_2023_m1_requested_or_admitted"] is False
    assert v4["synthetic_fills"] == 0
    assert v4["paper_execution_authorized"] is False
    assert v4["live_execution_authorized"] is False
    assert v4["broker_mutation_authorized"] is False
    assert v4["base_metrics"]["resolved_executed_trades"] == 127
    assert v4["base_metrics"]["profit_factor"] == 1.0020664176151879
    assert v4["base_metrics"]["bootstrap_95pct_ci_net_expectancy_r"][0] < 0
    assert v4["stress_metrics"]["net_expectancy_r"] < 0
    assert v4["stress_metrics"]["profit_factor"] == 0.8554420945575948
    assert v4["base_metrics"]["data_integrity_failures"] == 0
    assert v4["stress_metrics"]["data_integrity_failures"] == 0

    v3c = boundary["sealed_failed_families"]["v3c"]
    assert v3c["classification"] == "EDGE_NOT_ESTABLISHED"
    assert v3c["result_sha256"] == "e2af05e4fad93def189bedd22cc865ea78be4ac43a1a2e9d5e5822c8b84ff78b"
    assert v3c["post_result_refit_permitted"] is False

    print(json.dumps({
        "status": "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
        "boundary_sha256": EXPECTED_BOUNDARY_SHA,
        "v4_result_sha256": EXPECTED_V4_RESULT_SHA,
        "validated_profitable_edge": False,
        "unused_executable_first_party_family": False,
        "paper_execution_enabled": False,
        "live_execution_enabled": False,
        "broker_mutation_enabled": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
