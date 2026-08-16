#!/usr/bin/env python3
"""Require every Phase 5 omission-audit review item to have one bounded disposition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED_DECISIONS = {
    "ADMIT_CANDIDATE",
    "NOT_ADMITTED_INSUFFICIENT_OPERATIONAL_RELATIONSHIP",
    "NOT_ADMITTED_NON_PREDICATE_PRACTICE",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="research/candidate_selection_audit.json")
    parser.add_argument("--dispositions", default="research/candidate_selection_dispositions.json")
    args = parser.parse_args()

    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    dispositions = json.loads(Path(args.dispositions).read_text(encoding="utf-8"))
    errors: list[str] = []

    if audit.get("performance_data_consulted") is not False:
        errors.append("candidate audit must remain performance-blind")
    if dispositions.get("performance_data_consulted") is not False:
        errors.append("candidate dispositions must remain performance-blind")
    if dispositions.get("predicate_candidate_created") is not False:
        errors.append("this disposition packet must not silently create predicate candidates")

    review_items = {
        str(row["concept_id"]): row
        for row in audit.get("unrepresented_operational_cues", [])
        if row.get("review_state") == "REVIEW_REQUIRED"
    }

    disposition_rows = dispositions.get("dispositions", [])
    disposition_map: dict[str, dict] = {}
    for row in disposition_rows:
        concept_id = str(row.get("concept_id", ""))
        if not concept_id:
            errors.append("disposition missing concept_id")
            continue
        if concept_id in disposition_map:
            errors.append(f"duplicate disposition for {concept_id}")
        disposition_map[concept_id] = row
        decision = row.get("decision")
        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{concept_id}: invalid decision {decision}")
        if not str(row.get("reason", "")).strip():
            errors.append(f"{concept_id}: disposition reason must be non-empty")
        evidence_ids = row.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"{concept_id}: evidence_ids must be a non-empty list")

    missing = sorted(set(review_items) - set(disposition_map))
    stale = sorted(set(disposition_map) - set(review_items))
    if missing:
        errors.append(f"undispositioned REVIEW_REQUIRED concepts: {missing}")
    if stale:
        errors.append(f"dispositions exist for concepts not currently REVIEW_REQUIRED: {stale}")

    for concept_id, audit_row in review_items.items():
        disposition = disposition_map.get(concept_id)
        if disposition is None:
            continue
        allowed_evidence = set(str(value) for value in audit_row.get("operational_cue_evidence_ids", []))
        supplied_evidence = set(str(value) for value in disposition.get("evidence_ids", []))
        if not supplied_evidence.issubset(allowed_evidence):
            errors.append(
                f"{concept_id}: disposition references evidence outside the omission audit: "
                f"{sorted(supplied_evidence - allowed_evidence)}"
            )
        if disposition.get("decision") == "ADMIT_CANDIDATE":
            errors.append(
                f"{concept_id}: ADMIT_CANDIDATE requires a separate candidate-registry change; "
                "this disposition-only packet cannot silently admit it"
            )

    if errors:
        print("Candidate disposition validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "review_required": len(review_items),
                "dispositioned": len(disposition_map),
                "remaining_unresolved": len(set(review_items) - set(disposition_map)),
                "performance_data_consulted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
