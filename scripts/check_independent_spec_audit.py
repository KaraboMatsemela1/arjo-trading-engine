#!/usr/bin/env python3
"""Validate independent SPEC readiness audit invariants and fail closed."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = [
    "INPUTS", "INSTRUMENTS", "TIMEFRAME", "HIGHER_TIMEFRAME_CONTEXT", "DIRECTION",
    "PRECONDITIONS", "SETUP", "TRIGGER", "ENTRY", "STOP", "TARGET", "INVALIDATION",
    "EXPIRY", "SESSION/TIME_RULE", "OPTIONAL_CONDITIONS", "REQUIRED_CONDITIONS",
]


def load_matrix(path: Path) -> dict[str, dict[str, str]]:
    grouped: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped.setdefault(str(row["PREDICATE_ID"]), {})[str(row["FIELD"])] = str(row["STATE"])
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

    for flag in (
        "phase5_builder_imported", "community_interpretations_used", "generic_ict_smc_knowledge_used",
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

    audit_rows = {str(row["predicate_id"]): row for row in audit.get("candidates", [])}
    if set(audit_rows) != set(matrix):
        errors.append("audit candidate IDs do not exactly match predicate matrix")

    any_pass = False
    for predicate_id, fields in matrix.items():
        row = audit_rows.get(predicate_id, {})
        actual_unresolved = [field for field in REQUIRED_FIELDS if fields.get(field) in {"MISSING", "PARTIAL", "CONTRADICTORY"}]
        all_satisfied = all(fields.get(field) == "SATISFIED" for field in REQUIRED_FIELDS)
        contradictions_resolved = not any(fields.get(field) == "CONTRADICTORY" for field in REQUIRED_FIELDS)
        if row.get("unresolved_fields") != actual_unresolved:
            errors.append(f"{predicate_id}: unresolved_fields mismatch")
        if row.get("all_required_fields_satisfied") is not all_satisfied:
            errors.append(f"{predicate_id}: all_required_fields_satisfied mismatch")
        if row.get("contradictions_resolved") is not contradictions_resolved:
            errors.append(f"{predicate_id}: contradictions_resolved mismatch")
        if row.get("provenance_complete") is not True:
            errors.append(f"{predicate_id}: evidence provenance audit is incomplete")
        if row.get("two_engineer_test") != "PASS":
            errors.append(f"{predicate_id}: Phase 5 reconstruction preflight did not pass")
        if row.get("executable_semantics_reconstructed") is not False:
            errors.append(f"{predicate_id}: auditor must not claim executable semantics before independent reconstruction PASS")
        recovery_task_id = row.get("recovery_task_id")
        if actual_unresolved and recovery_task_id not in recovery_ids:
            errors.append(f"{predicate_id}: unresolved candidate has no bounded recovery task")

        passed = row.get("outcome") == "PASS"
        any_pass = any_pass or passed
        if passed:
            if not all_satisfied:
                errors.append(f"{predicate_id}: PASS with unresolved required fields")
            if row.get("independent_reconstruction") != "PASS":
                errors.append(f"{predicate_id}: PASS without independent reconstruction PASS")
        else:
            if actual_unresolved and row.get("outcome") != "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE":
                errors.append(f"{predicate_id}: unresolved candidate must be BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE")
            if actual_unresolved and row.get("independent_reconstruction") != "NOT_ATTEMPTED_INCOMPLETE_REQUIRED_FIELDS":
                errors.append(f"{predicate_id}: incomplete candidate must not attempt executable reconstruction")

    if audit.get("spec_ready") is not any_pass:
        errors.append("overall spec_ready must equal whether any candidate passed")
    expected_outcome = "PASS" if any_pass else "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"
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
