#!/usr/bin/env python3
"""Require one evidence-bound disposition for every candidate-selection omission cue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED_DECISIONS = {"NOT_CANDIDATE", "ADMIT_CANDIDATE"}
ALLOWED_RETAINED_ROLES = {"RECOVERY_CONTEXT_ONLY", "OBSERVATIONAL_METHOD", "CANDIDATE"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="research/candidate_selection_audit.json")
    parser.add_argument("--dispositions", default="research/candidate_selection_dispositions.json")
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    args = parser.parse_args()

    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    dispositions_doc = json.loads(Path(args.dispositions).read_text(encoding="utf-8"))
    candidates_doc = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    errors: list[str] = []

    if audit.get("performance_data_consulted") is not False:
        errors.append("candidate omission audit must be performance-blind")
    if dispositions_doc.get("performance_data_consulted") is not False:
        errors.append("candidate dispositions must be performance-blind")
    if dispositions_doc.get("invented_semantics_used") is not False:
        errors.append("candidate dispositions must state invented_semantics_used=false")

    review_required = {
        str(row["concept_id"]): {str(value) for value in row.get("operational_cue_evidence_ids", [])}
        for row in audit.get("unrepresented_operational_cues", [])
        if row.get("review_state") == "REVIEW_REQUIRED"
    }
    dispositions = dispositions_doc.get("dispositions", [])
    by_concept: dict[str, dict] = {}
    for row in dispositions:
        concept_id = str(row.get("concept_id", ""))
        if not concept_id:
            errors.append("disposition has empty concept_id")
            continue
        if concept_id in by_concept:
            errors.append(f"duplicate disposition for {concept_id}")
        by_concept[concept_id] = row
        decision = row.get("decision")
        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{concept_id}: invalid decision {decision}")
        if row.get("retained_role") not in ALLOWED_RETAINED_ROLES:
            errors.append(f"{concept_id}: invalid retained_role {row.get('retained_role')}")
        if not str(row.get("reason", "")).strip():
            errors.append(f"{concept_id}: reason is required")
        if not str(row.get("future_admission_condition", "")).strip():
            errors.append(f"{concept_id}: future_admission_condition is required")
        actual_ids = {str(value) for value in row.get("audit_evidence_ids", [])}
        expected_ids = review_required.get(concept_id)
        if expected_ids is not None and actual_ids != expected_ids:
            errors.append(
                f"{concept_id}: disposition evidence IDs {sorted(actual_ids)} != audit evidence IDs {sorted(expected_ids)}"
            )

    missing = sorted(set(review_required) - set(by_concept))
    extra = sorted(set(by_concept) - set(review_required))
    if missing:
        errors.append(f"undispositioned review-required concepts: {missing}")
    if extra:
        errors.append(f"dispositions exist for concepts not review-required: {extra}")

    candidate_concepts = {
        str(concept)
        for candidate in candidates_doc.get("candidates", [])
        for concept in candidate.get("concepts", [])
    }
    for concept_id, row in by_concept.items():
        if row.get("decision") == "NOT_CANDIDATE" and concept_id in candidate_concepts:
            errors.append(f"{concept_id}: marked NOT_CANDIDATE but already represented in candidate registry")
        if row.get("decision") == "ADMIT_CANDIDATE" and concept_id not in candidate_concepts:
            errors.append(f"{concept_id}: ADMIT_CANDIDATE requires representation in candidate registry")

    if errors:
        print("Candidate disposition validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "review_required": len(review_required),
                "dispositions": len(by_concept),
                "not_candidate": sum(1 for row in by_concept.values() if row.get("decision") == "NOT_CANDIDATE"),
                "admit_candidate": sum(1 for row in by_concept.values() if row.get("decision") == "ADMIT_CANDIDATE"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
