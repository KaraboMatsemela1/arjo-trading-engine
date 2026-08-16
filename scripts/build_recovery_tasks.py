#!/usr/bin/env python3
"""Build bounded first-party-only recovery tasks from predicate closure results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    parser.add_argument("--closure", default="research/predicate_closure.json")
    parser.add_argument("--output", default="research/predicate_recovery_tasks.json")
    parser.add_argument("--active-limit", type=int, default=2)
    args = parser.parse_args()

    candidates_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    closure = json.loads(Path(args.closure).read_text(encoding="utf-8"))
    candidates = {str(row["predicate_id"]): row for row in candidates_data.get("candidates", [])}
    errors: list[str] = []
    tasks: list[dict] = []

    ranked = sorted(closure.get("candidates", []), key=lambda row: int(row["closure_rank"]))
    for row in ranked:
        predicate_id = str(row["predicate_id"])
        candidate = candidates.get(predicate_id)
        if candidate is None:
            errors.append(f"closure references unknown candidate {predicate_id}")
            continue
        bundle_map = {str(bundle["bundle_id"]): bundle for bundle in candidate.get("recovery_bundles", [])}
        selected_ids = [str(value) for value in row.get("minimal_recovery_bundle_ids", [])]
        unknown = sorted(set(selected_ids) - set(bundle_map))
        if unknown:
            errors.append(f"{predicate_id}: closure selected unknown bundles {unknown}")
            continue

        selected = [bundle_map[bundle_id] for bundle_id in selected_ids]
        covered_fields = sorted({str(field) for bundle in selected for field in bundle.get("fields", [])})
        unresolved = [str(value) for value in row.get("unresolved_fields", [])]
        missing_coverage = sorted(set(unresolved) - set(covered_fields))
        if missing_coverage:
            errors.append(f"{predicate_id}: minimal recovery bundles miss fields {missing_coverage}")

        task = {
            "task_id": f"RECOVER_{predicate_id}",
            "predicate_id": predicate_id,
            "closure_rank": int(row["closure_rank"]),
            "closure_tuple_missing_contradictory_partial": row["closure_tuple_missing_contradictory_partial"],
            "unresolved_fields": unresolved,
            "minimal_recovery_bundle_ids": selected_ids,
            "recovery_targets": [
                {
                    "bundle_id": str(bundle["bundle_id"]),
                    "fields": [str(value) for value in bundle.get("fields", [])],
                    "target": str(bundle["target"]),
                }
                for bundle in selected
            ],
            "source_ids_already_supporting_candidate": candidate.get("source_ids", []),
            "concepts": candidate.get("concepts", []),
            "constraints": {
                "first_party_only": True,
                "locator_only_secondary_credit": False,
                "performance_data_prohibited": True,
                "invented_semantics_prohibited": True,
            },
            "issue_title": f"Recovery: close first-party predicate gaps for {predicate_id}",
            "issue_creation_requested": False,
        }
        tasks.append(task)

    active_limit = max(0, min(args.active_limit, len(tasks)))
    report = {
        "schema_version": 1,
        "generation_basis": "MINIMUM_CARDINALITY_RECOVERY_BUNDLE_COVER_OF_UNRESOLVED_FIELDS",
        "performance_data_consulted": False,
        "active_recovery_limit": active_limit,
        "active_recovery_task_ids": [task["task_id"] for task in tasks[:active_limit]],
        "backlog_recovery_task_ids": [task["task_id"] for task in tasks[active_limit:]],
        "tasks": tasks,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if errors:
        print("Recovery task generation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "tasks": len(tasks),
                "active": active_limit,
                "active_task_ids": report["active_recovery_task_ids"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
