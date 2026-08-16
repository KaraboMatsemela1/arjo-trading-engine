#!/usr/bin/env python3
"""Validate the independent evidence-only SPEC readiness audit artifact."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    "INPUTS", "INSTRUMENTS", "TIMEFRAME", "HIGHER_TIMEFRAME_CONTEXT", "DIRECTION",
    "PRECONDITIONS", "SETUP", "TRIGGER", "ENTRY", "STOP", "TARGET", "INVALIDATION",
    "EXPIRY", "SESSION/TIME_RULE", "OPTIONAL_CONDITIONS", "REQUIRED_CONDITIONS",
}
ALLOWED_OUTCOMES = {
    "PASS",
    "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "BLOCKED_NEEDS_VERSIONED_RECONSTRUCTION_PACKET",
}


def matrix_predicates(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {str(row["PREDICATE_ID"]) for row in csv.DictReader(handle)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="docs/spec/SPEC_AUDIT.json")
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    args = parser.parse_args()

    report = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    expected_predicates = matrix_predicates(Path(args.matrix))
    errors: list[str] = []

    if report.get("audit_protocol") != "INDEPENDENT_EVIDENCE_ONLY_SPEC_READINESS_V1":
        errors.append("unexpected independent audit protocol")
    if report.get("phase5_builder_imported") is not False:
        errors.append("independent auditor must not import the Phase 5 builder")
    for flag in (
        "community_interpretations_used",
        "generic_ict_smc_knowledge_used",
        "performance_data_consulted",
        "trade_counts_consulted",
    ):
        if report.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if report.get("required_field_count") != len(REQUIRED_FIELDS):
        errors.append(f"required_field_count must be {len(REQUIRED_FIELDS)}")

    candidates = report.get("candidates", [])
    by_predicate = {str(row.get("predicate_id", "")): row for row in candidates}
    if set(by_predicate) != expected_predicates:
        errors.append(
            f"audit candidate set does not match matrix: missing={sorted(expected_predicates - set(by_predicate))} "
            f"extra={sorted(set(by_predicate) - expected_predicates)}"
        )
    if report.get("candidate_count") != len(candidates):
        errors.append("candidate_count does not match candidates array")

    passed_candidates: list[str] = []
    for predicate_id, row in by_predicate.items():
        outcome = row.get("outcome")
        if outcome not in ALLOWED_OUTCOMES:
            errors.append(f"{predicate_id}: invalid outcome {outcome}")
        unresolved = set(str(value) for value in row.get("unresolved_fields", []))
        if not unresolved.issubset(REQUIRED_FIELDS):
            errors.append(f"{predicate_id}: unknown unresolved fields {sorted(unresolved - REQUIRED_FIELDS)}")
        state_counts = row.get("field_state_counts", {})
        if sum(int(value) for value in state_counts.values()) != len(REQUIRED_FIELDS):
            errors.append(f"{predicate_id}: field state counts do not total {len(REQUIRED_FIELDS)}")
        if row.get("provenance_complete") is not True:
            errors.append(f"{predicate_id}: evidence provenance is incomplete")
        for check in row.get("evidence_provenance_checks", []):
            if check.get("status") != "PASS":
                errors.append(f"{predicate_id}: evidence provenance failure for {check.get('evidence_id')}")
        if row.get("two_engineer_test") != "PASS":
            errors.append(f"{predicate_id}: Phase 5 reproducibility preflight is not PASS")
        if row.get("executable_semantics_reconstructed") is not False:
            errors.append(f"{predicate_id}: auditor must not claim reconstructed executable semantics without a pass packet")

        if outcome == "PASS":
            passed_candidates.append(predicate_id)
            if row.get("all_required_fields_satisfied") is not True:
                errors.append(f"{predicate_id}: PASS requires all required fields SATISFIED")
            if row.get("contradictions_resolved") is not True:
                errors.append(f"{predicate_id}: PASS requires zero unresolved contradictions")
            if unresolved:
                errors.append(f"{predicate_id}: PASS cannot contain unresolved fields")
        else:
            if row.get("all_required_fields_satisfied") is True and outcome == "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE":
                errors.append(f"{predicate_id}: evidence-blocked outcome inconsistent with all fields satisfied")

    expected_spec_ready = bool(passed_candidates)
    if report.get("spec_ready") is not expected_spec_ready:
        errors.append(f"spec_ready must equal whether any candidate passed ({expected_spec_ready})")
    if report.get("implementation_authorized") is not expected_spec_ready:
        errors.append("implementation_authorized must exactly track spec_ready")
    if expected_spec_ready and not report.get("frozen_spec_ref"):
        errors.append("a passing audit requires a frozen_spec_ref")
    if not expected_spec_ready and report.get("frozen_spec_ref") is not None:
        errors.append("blocked audit must not claim a frozen spec")
    expected_overall = "PASS" if expected_spec_ready else "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"
    if report.get("overall_outcome") != expected_overall:
        errors.append(f"overall_outcome must be {expected_overall}")

    if errors:
        print("Independent SPEC audit validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "candidate_count": len(candidates),
        "passed_candidates": passed_candidates,
        "spec_ready": report.get("spec_ready"),
        "overall_outcome": report.get("overall_outcome"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
