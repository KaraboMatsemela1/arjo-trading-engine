#!/usr/bin/env python3
"""Independently audit persisted predicate candidates for SPEC_READY.

This auditor does not import the Phase 5 builder. It treats the persisted matrix as
claims to verify against the evidence/acquisition registries. Executable
reconstruction is attempted only after all 16 required fields are SATISFIED.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REQUIRED_FIELDS = [
    "INPUTS", "INSTRUMENTS", "TIMEFRAME", "HIGHER_TIMEFRAME_CONTEXT", "DIRECTION",
    "PRECONDITIONS", "SETUP", "TRIGGER", "ENTRY", "STOP", "TARGET", "INVALIDATION",
    "EXPIRY", "SESSION/TIME_RULE", "OPTIONAL_CONDITIONS", "REQUIRED_CONDITIONS",
]
ALLOWED_STATES = {"SATISFIED", "PARTIAL", "MISSING", "CONTRADICTORY", "NOT_APPLICABLE"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def load_matrix(path: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(str(row["PREDICATE_ID"]), []).append(row)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    parser.add_argument("--evidence", default="research/evidence_registry.jsonl")
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--preflight", default="research/two_engineer_preflight.json")
    parser.add_argument("--recovery", default="research/predicate_recovery_tasks.json")
    parser.add_argument("--output", default="docs/spec/SPEC_AUDIT.json")
    args = parser.parse_args()

    matrix = load_matrix(Path(args.matrix))
    evidence = {str(row["EVIDENCE_ID"]): row for row in read_jsonl(Path(args.evidence))}
    acquisition = {str(row.get("source_id", "")): row for row in read_jsonl(Path(args.acquisition))}
    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        sources = {row["SOURCE_ID"]: row for row in csv.DictReader(handle) if row.get("SOURCE_ID")}
    preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
    recovery = json.loads(Path(args.recovery).read_text(encoding="utf-8"))
    recovery_by_predicate = {str(row["predicate_id"]): row for row in recovery.get("tasks", [])}
    preflight_by_predicate = {str(row["predicate_id"]): row for row in preflight.get("candidates", [])}

    candidate_audits: list[dict] = []
    any_pass = False
    for predicate_id in sorted(matrix):
        rows = matrix[predicate_id]
        row_by_field = {str(row["FIELD"]): row for row in rows}
        field_states = {field: str(row_by_field.get(field, {}).get("STATE", "MISSING")) for field in REQUIRED_FIELDS}
        invalid_states = sorted({state for state in field_states.values() if state not in ALLOWED_STATES})
        state_counts = {state: sum(1 for value in field_states.values() if value == state) for state in sorted(ALLOWED_STATES)}
        unresolved_fields = [field for field in REQUIRED_FIELDS if field_states[field] in {"MISSING", "PARTIAL", "CONTRADICTORY"}]
        evidence_ids = sorted({
            value.strip()
            for row in rows
            for value in str(row.get("EVIDENCE_IDS", "")).split(";")
            if value.strip()
        })

        evidence_checks: list[dict] = []
        provenance_complete = True
        for evidence_id in evidence_ids:
            record = evidence.get(evidence_id)
            if record is None:
                provenance_complete = False
                evidence_checks.append({"evidence_id": evidence_id, "status": "UNKNOWN_EVIDENCE"})
                continue
            source_id = str(record["SOURCE_ID"])
            source = sources.get(source_id)
            acquired = acquisition.get(source_id)
            checks = {
                "known_source": source is not None,
                "confirmed_first_party": bool(source and source.get("FIRST_PARTY_STATUS") == "CONFIRMED_FIRST_PARTY"),
                "payload_captured": bool(acquired and acquired.get("status") == "PAYLOAD_CAPTURED"),
                "first_party_contacted": bool(acquired and acquired.get("first_party_contacted") is True),
                "direct_closure_credit": bool(acquired and acquired.get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"),
                "sha256_bound": bool(acquired and acquired.get("sha256")),
            }
            status = "PASS" if all(checks.values()) else "FAIL"
            provenance_complete = provenance_complete and status == "PASS"
            evidence_checks.append({"evidence_id": evidence_id, "source_id": source_id, "status": status, "checks": checks})

        all_required_fields_satisfied = all(field_states[field] == "SATISFIED" for field in REQUIRED_FIELDS)
        contradictions_resolved = state_counts["CONTRADICTORY"] == 0
        preflight_row = preflight_by_predicate.get(predicate_id, {})
        two_engineer_test = (
            "PASS"
            if preflight.get("status") == "PASS" and preflight_row.get("agreement") is True
            else "FAIL"
        )

        structural_pass = (
            not invalid_states
            and len(row_by_field) == len(REQUIRED_FIELDS)
            and set(row_by_field) == set(REQUIRED_FIELDS)
            and all_required_fields_satisfied
            and contradictions_resolved
            and provenance_complete
            and two_engineer_test == "PASS"
        )
        if structural_pass:
            independent_reconstruction = "REQUIRES_VERSIONED_EXECUTABLE_PACKET"
            outcome = "BLOCKED_NEEDS_VERSIONED_RECONSTRUCTION_PACKET"
        else:
            independent_reconstruction = "NOT_ATTEMPTED_INCOMPLETE_REQUIRED_FIELDS"
            outcome = "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE" if unresolved_fields else "INSUFFICIENT_EVIDENCE"

        passed = structural_pass and independent_reconstruction == "PASS" and outcome == "PASS"
        any_pass = any_pass or passed
        recovery_task = recovery_by_predicate.get(predicate_id)
        candidate_audits.append(
            {
                "predicate_id": predicate_id,
                "outcome": "PASS" if passed else outcome,
                "all_required_fields_satisfied": all_required_fields_satisfied,
                "contradictions_resolved": contradictions_resolved,
                "provenance_complete": provenance_complete,
                "two_engineer_test": two_engineer_test,
                "independent_reconstruction": independent_reconstruction,
                "field_state_counts": state_counts,
                "unresolved_fields": unresolved_fields,
                "invalid_states": invalid_states,
                "evidence_ids": evidence_ids,
                "evidence_provenance_checks": evidence_checks,
                "recovery_task_id": recovery_task.get("task_id") if recovery_task else None,
                "recovery_bundle_ids": recovery_task.get("minimal_recovery_bundle_ids", []) if recovery_task else [],
                "executable_semantics_reconstructed": False,
            }
        )

    overall_outcome = "PASS" if any_pass else "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"
    report = {
        "schema_version": 1,
        "audit_protocol": "INDEPENDENT_EVIDENCE_ONLY_SPEC_READINESS_V1",
        "audit_code_path": "scripts/run_independent_spec_audit.py",
        "phase5_builder_imported": False,
        "community_interpretations_used": False,
        "generic_ict_smc_knowledge_used": False,
        "performance_data_consulted": False,
        "trade_counts_consulted": False,
        "spec_ready": any_pass,
        "overall_outcome": overall_outcome,
        "implementation_authorized": any_pass,
        "frozen_spec_ref": None,
        "required_field_count": len(REQUIRED_FIELDS),
        "candidate_count": len(candidate_audits),
        "candidates": candidate_audits,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"spec_ready": report["spec_ready"], "outcome": overall_outcome, "candidates": len(candidate_audits)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
