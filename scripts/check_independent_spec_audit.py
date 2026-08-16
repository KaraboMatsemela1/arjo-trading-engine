#!/usr/bin/env python3
"""Validate independent SPEC readiness audit invariants and fail closed."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

REQUIRED_FIELDS = [
    "INPUTS", "INSTRUMENTS", "TIMEFRAME", "HIGHER_TIMEFRAME_CONTEXT", "DIRECTION",
    "PRECONDITIONS", "SETUP", "TRIGGER", "ENTRY", "STOP", "TARGET", "INVALIDATION",
    "EXPIRY", "SESSION/TIME_RULE", "OPTIONAL_CONDITIONS", "REQUIRED_CONDITIONS",
]
INCOMPLETE = {"MISSING", "PARTIAL", "CONTRADICTORY"}


def load_matrix(path: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(str(row["PREDICATE_ID"]), []).append(row)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    parser.add_argument("--recovery", default="research/predicate_recovery_tasks.json")
    args = parser.parse_args()

    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    matrix = load_matrix(Path(args.matrix))
    recovery = json.loads(Path(args.recovery).read_text(encoding="utf-8"))
    recovery_ids = {str(row["task_id"]) for row in recovery.get("tasks", [])}
    errors: list[str] = []

    if audit.get("schema_version") != 2:
        errors.append("audit schema_version must be 2")
    if audit.get("audit_protocol") != "INDEPENDENT_EVIDENCE_ONLY_SPEC_READINESS_V2":
        errors.append("unexpected audit protocol")
    for flag in (
        "phase5_builder_imported", "phase5_preflight_is_independent_two_engineer_test",
        "community_interpretations_used", "generic_ict_smc_knowledge_used",
        "performance_data_consulted", "trade_counts_consulted",
    ):
        if audit.get(flag) is not False:
            errors.append(f"audit must state {flag}=false")
    if audit.get("required_field_count") != len(REQUIRED_FIELDS):
        errors.append("audit required_field_count mismatch")
    if audit.get("implementation_authorized") is not audit.get("spec_ready"):
        errors.append("implementation_authorized must exactly equal spec_ready")
    if audit.get("spec_ready") is False and audit.get("frozen_spec_ref") is not None:
        errors.append("failed audit must not freeze a spec")

    candidates = audit.get("candidates", [])
    audit_rows = {str(row.get("predicate_id", "")): row for row in candidates}
    if len(audit_rows) != len(candidates):
        errors.append("audit contains duplicate candidate IDs")
    if set(audit_rows) != set(matrix):
        errors.append("audit candidate IDs do not exactly match predicate matrix")

    any_pass = False
    candidate_outcomes: list[str] = []
    for predicate_id, rows in matrix.items():
        row = audit_rows.get(predicate_id, {})
        fields = [str(item.get("FIELD", "")) for item in rows]
        counts = Counter(fields)
        duplicate_fields = sorted(field for field, count in counts.items() if count != 1)
        missing_fields = sorted(set(REQUIRED_FIELDS) - set(fields))
        unexpected_fields = sorted(set(fields) - set(REQUIRED_FIELDS))
        row_by_field = {
            str(item["FIELD"]): str(item["STATE"])
            for item in rows
            if str(item.get("FIELD", "")) in REQUIRED_FIELDS
        }
        actual_unresolved = [field for field in REQUIRED_FIELDS if row_by_field.get(field, "MISSING") in INCOMPLETE]
        all_satisfied = (
            len(rows) == len(REQUIRED_FIELDS)
            and not duplicate_fields
            and not missing_fields
            and not unexpected_fields
            and all(row_by_field.get(field) == "SATISFIED" for field in REQUIRED_FIELDS)
        )
        contradictions_resolved = not any(row_by_field.get(field) == "CONTRADICTORY" for field in REQUIRED_FIELDS)

        if row.get("matrix_row_count") != len(rows):
            errors.append(f"{predicate_id}: matrix_row_count mismatch")
        if row.get("matrix_duplicate_fields") != duplicate_fields:
            errors.append(f"{predicate_id}: matrix_duplicate_fields mismatch")
        if row.get("matrix_missing_fields") != missing_fields:
            errors.append(f"{predicate_id}: matrix_missing_fields mismatch")
        if row.get("matrix_unexpected_fields") != unexpected_fields:
            errors.append(f"{predicate_id}: matrix_unexpected_fields mismatch")
        if row.get("unresolved_fields") != actual_unresolved:
            errors.append(f"{predicate_id}: unresolved_fields mismatch")
        if row.get("all_required_fields_satisfied") is not all_satisfied:
            errors.append(f"{predicate_id}: all_required_fields_satisfied mismatch")
        if row.get("contradictions_resolved") is not contradictions_resolved:
            errors.append(f"{predicate_id}: contradictions_resolved mismatch")
        if row.get("provenance_complete") is not True:
            errors.append(f"{predicate_id}: evidence provenance audit is incomplete")
        if row.get("phase5_reconstruction_preflight") != "PASS":
            errors.append(f"{predicate_id}: Phase 5 reconstruction preflight did not pass")
        if "two_engineer_test" in row:
            errors.append(f"{predicate_id}: legacy two_engineer_test field conflates Phase 5 and independent audit")
        if row.get("executable_semantics_reconstructed") is not False:
            errors.append(f"{predicate_id}: executable semantics must remain false in V2 audit")

        recovery_task_id = row.get("recovery_task_id")
        if actual_unresolved and recovery_task_id not in recovery_ids:
            errors.append(f"{predicate_id}: unresolved candidate has no bounded recovery task")

        outcome = str(row.get("outcome", ""))
        candidate_outcomes.append(outcome)
        passed = outcome == "PASS"
        any_pass = any_pass or passed
        if passed:
            if not all_satisfied:
                errors.append(f"{predicate_id}: PASS with incomplete matrix")
            if row.get("independent_two_engineer_test") != "PASS":
                errors.append(f"{predicate_id}: PASS without independent two-engineer PASS")
            if row.get("independent_reconstruction") != "PASS":
                errors.append(f"{predicate_id}: PASS without independent reconstruction PASS")
        elif actual_unresolved:
            if outcome != "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE":
                errors.append(f"{predicate_id}: unresolved candidate must need first-party evidence")
            expected = "NOT_ATTEMPTED_INCOMPLETE_REQUIRED_FIELDS"
            if row.get("independent_two_engineer_test") != expected:
                errors.append(f"{predicate_id}: independent two-engineer test must not run on incomplete fields")
            if row.get("independent_reconstruction") != expected:
                errors.append(f"{predicate_id}: independent reconstruction must not run on incomplete fields")
        elif all_satisfied:
            expected = "REQUIRES_INDEPENDENT_RECONSTRUCTION_PACKET"
            if outcome != "BLOCKED_NEEDS_INDEPENDENT_RECONSTRUCTION_PACKET":
                errors.append(f"{predicate_id}: structurally complete candidate must await independent packet")
            if row.get("independent_two_engineer_test") != expected:
                errors.append(f"{predicate_id}: independent two-engineer state must await packet")
            if row.get("independent_reconstruction") != expected:
                errors.append(f"{predicate_id}: reconstruction state must await packet")

    if audit.get("spec_ready") is not any_pass:
        errors.append("overall spec_ready must equal whether any candidate passed")
    if any_pass:
        expected_outcome = "PASS"
    elif "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE" in candidate_outcomes:
        expected_outcome = "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"
    elif "BLOCKED_NEEDS_INDEPENDENT_RECONSTRUCTION_PACKET" in candidate_outcomes:
        expected_outcome = "BLOCKED_NEEDS_INDEPENDENT_RECONSTRUCTION_PACKET"
    else:
        expected_outcome = "INSUFFICIENT_EVIDENCE"
    if audit.get("overall_outcome") != expected_outcome:
        errors.append(f"overall_outcome mismatch: expected {expected_outcome}")

    if errors:
        print("Independent SPEC audit validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({"candidates": len(matrix), "spec_ready": audit["spec_ready"], "outcome": audit["overall_outcome"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
