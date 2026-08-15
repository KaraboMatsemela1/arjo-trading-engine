#!/usr/bin/env python3
"""Validate concept inventory shape, dependencies and direct first-party provenance."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ALLOWED_STATES = {
    "DIRECT",
    "DIRECT_CONCEPT_PARTIAL_EXECUTION",
    "DIRECT_EXAMPLE_PARTIAL",
    "DIRECT_ALIAS_PARTIAL",
    "STRONG_PARTIAL",
    "CONTEXTUAL",
    "NAMED_CONTEXTUAL",
    "NAMED_UNRESOLVED",
}
REQUIRED = {
    "CONCEPT_ID", "FIRST_PARTY_DEFINITION", "SOURCE_IDS", "TIMESTAMPS",
    "DEPENDENCIES", "AMBIGUITIES", "CONTRADICTIONS", "DEFINITION_STATE",
    "EXECUTABLE_RULE_CLAIMED",
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default="research/concept_inventory.jsonl")
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        concepts = load_jsonl(Path(args.inventory))
        acquisitions = load_jsonl(Path(args.acquisition))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        sources = {row["SOURCE_ID"]: row for row in csv.DictReader(handle) if row.get("SOURCE_ID")}
    acquisition_by_source = {str(row.get("source_id", "")): row for row in acquisitions}
    concept_ids = [str(row.get("CONCEPT_ID", "")) for row in concepts]
    concept_set = set(concept_ids)

    if not concepts:
        errors.append("concept inventory is empty")
    if len(concept_ids) != len(concept_set):
        errors.append("duplicate CONCEPT_ID detected")

    for index, row in enumerate(concepts, start=1):
        concept_id = str(row.get("CONCEPT_ID", f"row-{index}"))
        missing = REQUIRED - set(row)
        extra = set(row) - REQUIRED
        if missing:
            errors.append(f"{concept_id}: missing fields {sorted(missing)}")
        if extra:
            errors.append(f"{concept_id}: unexpected fields {sorted(extra)}")
        if not row.get("FIRST_PARTY_DEFINITION"):
            errors.append(f"{concept_id}: empty FIRST_PARTY_DEFINITION")
        if row.get("DEFINITION_STATE") not in ALLOWED_STATES:
            errors.append(f"{concept_id}: invalid DEFINITION_STATE {row.get('DEFINITION_STATE')}")
        if row.get("EXECUTABLE_RULE_CLAIMED") is not False:
            errors.append(f"{concept_id}: executable rule claim is forbidden in Phase 3")

        source_ids = row.get("SOURCE_IDS")
        timestamps = row.get("TIMESTAMPS")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"{concept_id}: SOURCE_IDS must be a non-empty list")
            continue
        if not isinstance(timestamps, list) or len(timestamps) != len(source_ids):
            errors.append(f"{concept_id}: TIMESTAMPS must align one-to-one with SOURCE_IDS")

        for position, source_id in enumerate(source_ids):
            source = sources.get(str(source_id))
            if source is None:
                errors.append(f"{concept_id}: unknown source {source_id}")
                continue
            if source.get("FIRST_PARTY_STATUS") != "CONFIRMED_FIRST_PARTY":
                errors.append(f"{concept_id}: source {source_id} is not confirmed direct first-party")
            acquisition = acquisition_by_source.get(str(source_id))
            if acquisition is None:
                errors.append(f"{concept_id}: source {source_id} has no acquisition record")
                continue
            if acquisition.get("status") != "PAYLOAD_CAPTURED":
                errors.append(f"{concept_id}: source {source_id} has no captured payload ({acquisition.get('status')})")
            if acquisition.get("first_party_contacted") is not True:
                errors.append(f"{concept_id}: source {source_id} was not directly contacted")
            if acquisition.get("closure_credit") != "DIRECT_FIRST_PARTY_PAYLOAD":
                errors.append(f"{concept_id}: source {source_id} lacks direct payload closure credit")
            if not acquisition.get("sha256"):
                errors.append(f"{concept_id}: source {source_id} lacks SHA-256 payload provenance")
            if isinstance(timestamps, list) and position < len(timestamps):
                expected = source.get("PUBLICATION_DATE", "")
                if expected and str(timestamps[position]) != expected:
                    errors.append(
                        f"{concept_id}: timestamp/date mismatch for {source_id}: "
                        f"inventory={timestamps[position]} registry={expected}"
                    )

        dependencies = row.get("DEPENDENCIES")
        if not isinstance(dependencies, list):
            errors.append(f"{concept_id}: DEPENDENCIES must be a list")
        else:
            for dependency in dependencies:
                if dependency not in concept_set:
                    errors.append(f"{concept_id}: unknown dependency {dependency}")
                if dependency == concept_id:
                    errors.append(f"{concept_id}: self-dependency")
        for field in ("AMBIGUITIES", "CONTRADICTIONS"):
            if not isinstance(row.get(field), list):
                errors.append(f"{concept_id}: {field} must be a list")

    # Cycle check keeps hierarchy deterministic without claiming causality.
    graph = {str(row["CONCEPT_ID"]): list(row.get("DEPENDENCIES", [])) for row in concepts if row.get("CONCEPT_ID")}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            errors.append(f"dependency cycle detected at {node}")
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for concept_id in graph:
        visit(concept_id)

    if errors:
        print("Concept inventory validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    states: dict[str, int] = {}
    for row in concepts:
        state = str(row["DEFINITION_STATE"])
        states[state] = states.get(state, 0) + 1
    print(json.dumps({"concepts": len(concepts), "definition_states": dict(sorted(states.items()))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
