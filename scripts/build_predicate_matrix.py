#!/usr/bin/env python3
"""Build a complete predicate-field matrix and deterministic closure ranking.

This phase is evidence synthesis only. Unsupported fields become MISSING and no
performance information is consulted. Closure ranking is lexicographic on
(missing, contradictory, partial), never on market outcomes. Post-Phase-4
recovery evidence is additive: the immutable base registry is read together with
validated evidence shards, and bounded field overrides are applied explicitly.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path

from evidence_registry_union import DEFAULT_EVIDENCE_GLOB, load_evidence_union

FIELDS = [
    "INPUTS",
    "INSTRUMENTS",
    "TIMEFRAME",
    "HIGHER_TIMEFRAME_CONTEXT",
    "DIRECTION",
    "PRECONDITIONS",
    "SETUP",
    "TRIGGER",
    "ENTRY",
    "STOP",
    "TARGET",
    "INVALIDATION",
    "EXPIRY",
    "SESSION/TIME_RULE",
    "OPTIONAL_CONDITIONS",
    "REQUIRED_CONDITIONS",
]
ALLOWED_STATES = {"SATISFIED", "PARTIAL", "MISSING", "CONTRADICTORY", "NOT_APPLICABLE"}
UNRESOLVED_STATES = {"PARTIAL", "MISSING", "CONTRADICTORY"}


def load_candidates(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("selection_policy", {}).get("performance_data_consulted") is not False:
        raise ValueError("candidate selection must state performance_data_consulted=false")
    if data.get("selection_policy", {}).get("executable_rule_claimed") is not False:
        raise ValueError("candidate selection must not claim an executable rule")
    if data.get("required_fields") != FIELDS:
        raise ValueError("candidate required_fields must exactly match the canonical 16-field order")
    return data


def load_overrides(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("performance_data_consulted") is not False:
        raise ValueError("predicate field overrides must state performance_data_consulted=false")
    result: dict[tuple[str, str], dict] = {}
    for row in data.get("overrides", []):
        predicate_id = str(row.get("predicate_id", ""))
        field = str(row.get("field", ""))
        key = (predicate_id, field)
        if not predicate_id or field not in FIELDS:
            raise ValueError(f"invalid predicate field override {predicate_id}/{field}")
        if key in result:
            raise ValueError(f"duplicate predicate field override {predicate_id}/{field}")
        result[key] = row
    return result


def expand_candidate(
    candidate: dict,
    evidence_ids: set[str],
    overrides: dict[tuple[str, str], dict],
) -> list[dict]:
    predicate_id = str(candidate["predicate_id"])
    hypotheses = dict(candidate.get("field_hypotheses", {}))
    for field in FIELDS:
        override = overrides.get((predicate_id, field))
        if override is not None:
            hypotheses[field] = {
                "state": override.get("state"),
                "evidence_ids": override.get("evidence_ids", []),
                "notes": override.get("notes", ""),
            }
    unknown_fields = sorted(set(hypotheses) - set(FIELDS))
    if unknown_fields:
        raise ValueError(f"{predicate_id}: unknown field hypotheses {unknown_fields}")

    rows: list[dict] = []
    for field in FIELDS:
        hypothesis = hypotheses.get(field)
        if hypothesis is None:
            rows.append(
                {
                    "PREDICATE_ID": predicate_id,
                    "FIELD": field,
                    "STATE": "MISSING",
                    "EVIDENCE_IDS": "",
                    "NOTES": f"No direct first-party evidence in the current registry establishes {field} for this candidate.",
                }
            )
            continue

        state = str(hypothesis.get("state", ""))
        if state not in ALLOWED_STATES:
            raise ValueError(f"{predicate_id}/{field}: invalid state {state}")
        refs = [str(value) for value in hypothesis.get("evidence_ids", [])]
        missing_refs = sorted(set(refs) - evidence_ids)
        if missing_refs:
            raise ValueError(f"{predicate_id}/{field}: unknown evidence IDs {missing_refs}")
        rows.append(
            {
                "PREDICATE_ID": predicate_id,
                "FIELD": field,
                "STATE": state,
                "EVIDENCE_IDS": ";".join(refs),
                "NOTES": str(hypothesis.get("notes", "")).strip(),
            }
        )
    return rows


def minimal_bundle_cover(candidate: dict, unresolved_fields: set[str]) -> list[str]:
    if not unresolved_fields:
        return []
    bundles = list(candidate.get("recovery_bundles", []))
    normalized: list[tuple[str, set[str]]] = []
    for bundle in bundles:
        bundle_id = str(bundle["bundle_id"])
        fields = {str(value) for value in bundle.get("fields", [])} & unresolved_fields
        if fields:
            normalized.append((bundle_id, fields))

    covered = set().union(*(fields for _, fields in normalized)) if normalized else set()
    missing_coverage = sorted(unresolved_fields - covered)
    if missing_coverage:
        raise ValueError(
            f"{candidate['predicate_id']}: recovery bundles do not cover unresolved fields {missing_coverage}"
        )

    normalized.sort(key=lambda item: item[0])
    for size in range(1, len(normalized) + 1):
        valid: list[tuple[str, ...]] = []
        for combo in itertools.combinations(normalized, size):
            union = set().union(*(fields for _, fields in combo))
            if unresolved_fields <= union:
                valid.append(tuple(bundle_id for bundle_id, _ in combo))
        if valid:
            return list(sorted(valid)[0])
    raise ValueError(f"{candidate['predicate_id']}: no recovery bundle cover found")


def build(
    candidate_data: dict,
    evidence_records: list[dict],
    overrides: dict[tuple[str, str], dict] | None = None,
) -> tuple[list[dict], dict]:
    overrides = overrides or {}
    evidence_ids = {str(row["EVIDENCE_ID"]) for row in evidence_records}
    candidates = list(candidate_data.get("candidates", []))
    predicate_ids = [str(row["predicate_id"]) for row in candidates]
    if len(predicate_ids) != len(set(predicate_ids)):
        raise ValueError("duplicate predicate_id in candidate registry")
    if not candidates:
        raise ValueError("candidate registry is empty")
    unknown_override_predicates = sorted({predicate_id for predicate_id, _ in overrides} - set(predicate_ids))
    if unknown_override_predicates:
        raise ValueError(f"predicate field overrides reference unknown candidates {unknown_override_predicates}")

    matrix_rows: list[dict] = []
    closures: list[dict] = []
    for candidate in candidates:
        rows = expand_candidate(candidate, evidence_ids, overrides)
        matrix_rows.extend(rows)
        state_counts = {state: 0 for state in sorted(ALLOWED_STATES)}
        for row in rows:
            state_counts[row["STATE"]] += 1
        unresolved = [row["FIELD"] for row in rows if row["STATE"] in UNRESOLVED_STATES]
        unresolved_set = set(unresolved)
        minimal_bundles = minimal_bundle_cover(candidate, unresolved_set)
        closure_tuple = [
            state_counts["MISSING"],
            state_counts["CONTRADICTORY"],
            state_counts["PARTIAL"],
        ]
        closures.append(
            {
                "predicate_id": candidate["predicate_id"],
                "candidate_type": candidate["candidate_type"],
                "source_ids": candidate.get("source_ids", []),
                "concepts": candidate.get("concepts", []),
                "field_state_counts": state_counts,
                "unresolved_fields": unresolved,
                "closure_distance": len(unresolved),
                "closure_tuple_missing_contradictory_partial": closure_tuple,
                "minimal_recovery_bundle_ids": minimal_bundles,
                "performance_data_consulted": False,
                "executable_rule_complete": False,
            }
        )

    closures.sort(
        key=lambda row: (
            tuple(row["closure_tuple_missing_contradictory_partial"]),
            row["closure_distance"],
            row["predicate_id"],
        )
    )
    for rank, row in enumerate(closures, start=1):
        row["closure_rank"] = rank

    closure_report = {
        "schema_version": 1,
        "ranking_basis": "LEXICOGRAPHIC_MISSING_CONTRADICTORY_PARTIAL_THEN_TOTAL_UNRESOLVED",
        "performance_data_consulted": False,
        "candidate_count": len(candidates),
        "required_field_count": len(FIELDS),
        "candidates": closures,
    }
    return matrix_rows, closure_report


def write_matrix(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["PREDICATE_ID", "FIELD", "STATE", "EVIDENCE_IDS", "NOTES"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_GLOB)
    parser.add_argument("--overrides", default="research/predicate_field_overrides.json")
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    parser.add_argument("--closure", default="research/predicate_closure.json")
    args = parser.parse_args()

    candidate_data = load_candidates(Path(args.candidates))
    evidence = load_evidence_union(args.evidence)
    overrides = load_overrides(Path(args.overrides))
    rows, closure = build(candidate_data, evidence, overrides)
    write_matrix(rows, Path(args.matrix))
    Path(args.closure).write_text(json.dumps(closure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidates": closure["candidate_count"],
                "matrix_rows": len(rows),
                "evidence_records": len(evidence),
                "override_count": len(overrides),
                "closest_candidate": closure["candidates"][0]["predicate_id"],
                "closest_closure_tuple": closure["candidates"][0]["closure_tuple_missing_contradictory_partial"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
