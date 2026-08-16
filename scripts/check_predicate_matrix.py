#!/usr/bin/env python3
"""Validate Phase 5 matrix completeness, evidence use, closure ranking and anti-bias boundaries."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

FIELDS = [
    "INPUTS", "INSTRUMENTS", "TIMEFRAME", "HIGHER_TIMEFRAME_CONTEXT", "DIRECTION",
    "PRECONDITIONS", "SETUP", "TRIGGER", "ENTRY", "STOP", "TARGET", "INVALIDATION",
    "EXPIRY", "SESSION/TIME_RULE", "OPTIONAL_CONDITIONS", "REQUIRED_CONDITIONS",
]
STATES = {"SATISFIED", "PARTIAL", "MISSING", "CONTRADICTORY", "NOT_APPLICABLE"}
UNRESOLVED = {"PARTIAL", "MISSING", "CONTRADICTORY"}
FORBIDDEN = re.compile(
    r"(?:\bwin\s*rate\b|\bprofit\s*factor\b|\bsharpe\b|\bexpectancy\b|\bp\s*&\s*l\b|\bpnl\b|\btrade\s*count\b|\d+(?:\.\d+)?%)",
    re.IGNORECASE,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    parser.add_argument("--evidence", default="research/evidence_registry.jsonl")
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    parser.add_argument("--closure", default="research/predicate_closure.json")
    args = parser.parse_args()

    errors: list[str] = []
    candidate_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    candidates = {str(row["predicate_id"]): row for row in candidate_data.get("candidates", [])}
    evidence = {str(row["EVIDENCE_ID"]): row for row in read_jsonl(Path(args.evidence))}
    with Path(args.matrix).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    closure = json.loads(Path(args.closure).read_text(encoding="utf-8"))

    if candidate_data.get("selection_policy", {}).get("performance_data_consulted") is not False:
        errors.append("candidate selection must be performance-blind")
    if closure.get("performance_data_consulted") is not False:
        errors.append("closure ranking must be performance-blind")
    if set(candidates) != {str(row["PREDICATE_ID"]) for row in rows}:
        errors.append("matrix predicate IDs do not exactly match candidate registry")

    grouped: dict[str, list[dict]] = {predicate_id: [] for predicate_id in candidates}
    seen_pairs: set[tuple[str, str]] = set()
    for row in rows:
        predicate_id = str(row.get("PREDICATE_ID", ""))
        field = str(row.get("FIELD", ""))
        state = str(row.get("STATE", ""))
        pair = (predicate_id, field)
        if pair in seen_pairs:
            errors.append(f"duplicate matrix row {predicate_id}/{field}")
        seen_pairs.add(pair)
        if predicate_id not in candidates:
            errors.append(f"unknown predicate {predicate_id}")
            continue
        grouped[predicate_id].append(row)
        if field not in FIELDS:
            errors.append(f"{predicate_id}: unknown field {field}")
        if state not in STATES:
            errors.append(f"{predicate_id}/{field}: invalid state {state}")

        refs = [value.strip() for value in str(row.get("EVIDENCE_IDS", "")).split(";") if value.strip()]
        unknown_refs = sorted(set(refs) - set(evidence))
        if unknown_refs:
            errors.append(f"{predicate_id}/{field}: unknown evidence {unknown_refs}")
        notes = str(row.get("NOTES", ""))
        if FORBIDDEN.search(notes):
            errors.append(f"{predicate_id}/{field}: performance/outcome metric leaked into synthesis notes")

        if state == "MISSING" and refs:
            errors.append(f"{predicate_id}/{field}: MISSING field must not cite evidence as if it supported the field")
        if state == "PARTIAL":
            if not refs:
                errors.append(f"{predicate_id}/{field}: PARTIAL field requires evidence")
            if "limitation:" not in notes.lower():
                errors.append(f"{predicate_id}/{field}: PARTIAL notes must state an explicit limitation")
            if refs and not any(evidence.get(ref, {}).get("CONFIDENCE") != "INSUFFICIENT" for ref in refs):
                errors.append(f"{predicate_id}/{field}: PARTIAL field has only INSUFFICIENT evidence")
        if state == "SATISFIED":
            if not refs:
                errors.append(f"{predicate_id}/{field}: SATISFIED field requires evidence")
            if refs and not any(evidence.get(ref, {}).get("CONFIDENCE") == "DIRECT" for ref in refs):
                errors.append(f"{predicate_id}/{field}: SATISFIED field requires at least one DIRECT record")
        if state == "CONTRADICTORY":
            if len(refs) < 2:
                errors.append(f"{predicate_id}/{field}: CONTRADICTORY field requires at least two evidence records")
            if "contradict" not in notes.lower():
                errors.append(f"{predicate_id}/{field}: contradiction handling must be explicit in notes")
        if state == "NOT_APPLICABLE" and not notes.strip():
            errors.append(f"{predicate_id}/{field}: NOT_APPLICABLE requires rationale")

        candidate_concepts = set(candidates[predicate_id].get("concepts", []))
        for ref in refs:
            record = evidence.get(ref)
            if record and record.get("SUPPORTED_CONCEPT") not in candidate_concepts:
                errors.append(
                    f"{predicate_id}/{field}: evidence {ref} supports concept {record.get('SUPPORTED_CONCEPT')} outside candidate concept set"
                )

    for predicate_id, candidate_rows in grouped.items():
        fields = [str(row["FIELD"]) for row in candidate_rows]
        if len(candidate_rows) != len(FIELDS) or set(fields) != set(FIELDS):
            errors.append(f"{predicate_id}: matrix must contain exactly the canonical 16 fields")
        rationale = str(candidates[predicate_id].get("rationale", ""))
        if FORBIDDEN.search(rationale):
            errors.append(f"{predicate_id}: performance/outcome metric leaked into candidate rationale")
        evidence_source_ids = {str(record["SOURCE_ID"]) for record in evidence.values()}
        unknown_sources = sorted(set(candidates[predicate_id].get("source_ids", [])) - evidence_source_ids)
        if unknown_sources:
            errors.append(f"{predicate_id}: candidate cites sources absent from evidence registry {unknown_sources}")

    closure_by_id = {str(row["predicate_id"]): row for row in closure.get("candidates", [])}
    if set(closure_by_id) != set(candidates):
        errors.append("closure report candidate IDs do not exactly match candidate registry")
    expected_order: list[tuple[tuple[int, int, int], int, str]] = []
    for predicate_id, candidate_rows in grouped.items():
        state_counts = {state: 0 for state in STATES}
        for row in candidate_rows:
            state_counts[str(row["STATE"])] += 1
        unresolved = [str(row["FIELD"]) for row in candidate_rows if row["STATE"] in UNRESOLVED]
        expected_tuple = [state_counts["MISSING"], state_counts["CONTRADICTORY"], state_counts["PARTIAL"]]
        report = closure_by_id.get(predicate_id, {})
        if report.get("closure_tuple_missing_contradictory_partial") != expected_tuple:
            errors.append(f"{predicate_id}: closure tuple does not match matrix")
        if report.get("closure_distance") != len(unresolved):
            errors.append(f"{predicate_id}: closure distance does not match unresolved field count")
        if report.get("unresolved_fields") != unresolved:
            errors.append(f"{predicate_id}: unresolved field ordering does not match matrix")
        if report.get("performance_data_consulted") is not False:
            errors.append(f"{predicate_id}: closure entry must be performance-blind")
        if report.get("executable_rule_complete") is not False:
            errors.append(f"{predicate_id}: Phase 5 must not claim executable-rule completion")
        expected_order.append((tuple(expected_tuple), len(unresolved), predicate_id))

    expected_order.sort()
    ranked_ids = [row[2] for row in expected_order]
    actual_ranked = [row["predicate_id"] for row in sorted(closure.get("candidates", []), key=lambda row: int(row["closure_rank"]))]
    if actual_ranked != ranked_ids:
        errors.append(f"closure ranking mismatch: expected {ranked_ids}, got {actual_ranked}")

    if errors:
        print("Predicate matrix validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({"candidates": len(candidates), "matrix_rows": len(rows), "ranked_ids": actual_ranked}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
