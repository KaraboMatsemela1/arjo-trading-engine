#!/usr/bin/env python3
"""Validate atomic evidence shape, direct provenance, coverage and anti-bias rules."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from evidence_antibias import contains_pre_spec_outcome
from evidence_registry_union import DEFAULT_EVIDENCE_GLOB, load_evidence_union

CONFIDENCE = {"DIRECT", "STRONG_PARTIAL", "CONTEXTUAL", "INSUFFICIENT"}
FIELDS = {
    "EVIDENCE_ID",
    "SOURCE_ID",
    "TIMESTAMP",
    "MINIMAL_QUOTE",
    "FRAME_LOCATOR",
    "SUPPORTED_CONCEPT",
    "SUPPORTED_FIELD",
    "WHAT_IT_PROVES",
    "WHAT_IT_DOES_NOT_PROVE",
    "CONFIDENCE",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def load_inventory(pattern: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(Path().glob(pattern)):
        rows.extend(read_jsonl(path))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_GLOB)
    parser.add_argument("--coverage", default="research/evidence_coverage.json")
    parser.add_argument("--inventory-glob", default="research/concept_inventory*.jsonl")
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    args = parser.parse_args()

    errors: list[str] = []
    inventory = load_inventory(args.inventory_glob)
    concepts = {str(row["CONCEPT_ID"]): row for row in inventory}
    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        sources = {row["SOURCE_ID"]: row for row in csv.DictReader(handle) if row.get("SOURCE_ID")}
    acquisitions = {
        str(row.get("source_id", "")): row for row in read_jsonl(Path(args.acquisition))
    }
    try:
        evidence = load_evidence_union(args.evidence)
    except ValueError as exc:
        print(f"Evidence registry validation failed:\n- {exc}", file=sys.stderr)
        return 1

    seen_ids: set[str] = set()
    concept_evidence: dict[str, list[dict]] = {concept_id: [] for concept_id in concepts}
    cited_pairs = {
        (str(concept["CONCEPT_ID"]), str(source_id))
        for concept in inventory
        for source_id in concept.get("SOURCE_IDS", [])
    }
    evidence_pairs: set[tuple[str, str]] = set()

    for index, record in enumerate(evidence, start=1):
        label = str(record.get("EVIDENCE_ID", f"row-{index}"))
        missing = FIELDS - set(record)
        extra = set(record) - FIELDS
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")
        if extra:
            errors.append(f"{label}: unexpected fields {sorted(extra)}")
        if label in seen_ids:
            errors.append(f"duplicate EVIDENCE_ID: {label}")
        seen_ids.add(label)
        if record.get("CONFIDENCE") not in CONFIDENCE:
            errors.append(f"{label}: invalid confidence {record.get('CONFIDENCE')}")
        concept_id = str(record.get("SUPPORTED_CONCEPT", ""))
        source_id = str(record.get("SOURCE_ID", ""))
        if concept_id not in concepts:
            errors.append(f"{label}: unknown concept {concept_id}")
        else:
            concept_evidence[concept_id].append(record)
        evidence_pairs.add((concept_id, source_id))

        source = sources.get(source_id)
        if source is None:
            errors.append(f"{label}: unknown source {source_id}")
        else:
            if source.get("FIRST_PARTY_STATUS") != "CONFIRMED_FIRST_PARTY":
                errors.append(f"{label}: source {source_id} is not confirmed first-party")
            expected_date = source.get("PUBLICATION_DATE", "")
            if expected_date and record.get("TIMESTAMP") != expected_date:
                errors.append(
                    f"{label}: timestamp mismatch {record.get('TIMESTAMP')} != {expected_date}"
                )

        acquisition = acquisitions.get(source_id)
        if acquisition is None:
            errors.append(f"{label}: no acquisition record for {source_id}")
        else:
            if acquisition.get("status") != "PAYLOAD_CAPTURED":
                errors.append(f"{label}: source {source_id} has no captured payload")
            if acquisition.get("first_party_contacted") is not True:
                errors.append(f"{label}: source {source_id} was not directly contacted")
            if acquisition.get("closure_credit") != "DIRECT_FIRST_PARTY_PAYLOAD":
                errors.append(f"{label}: source {source_id} lacks direct closure credit")
            if not acquisition.get("sha256"):
                errors.append(f"{label}: source {source_id} lacks SHA-256 provenance")

        quote = str(record.get("MINIMAL_QUOTE", ""))
        if len(quote.split()) > 25:
            errors.append(f"{label}: quote exceeds 25-word bound")
        if record.get("CONFIDENCE") != "INSUFFICIENT" and not quote:
            errors.append(f"{label}: non-insufficient evidence requires a quote")
        combined = " ".join(
            str(record.get(field, ""))
            for field in ("MINIMAL_QUOTE", "WHAT_IT_PROVES", "WHAT_IT_DOES_NOT_PROVE")
        )
        if contains_pre_spec_outcome(combined):
            errors.append(f"{label}: pre-SPEC performance/outcome metric leaked into evidence")
        if not str(record.get("WHAT_IT_PROVES", "")).strip() or not str(
            record.get("WHAT_IT_DOES_NOT_PROVE", "")
        ).strip():
            errors.append(f"{label}: proof boundaries must be non-empty")

    missing_pairs = sorted(cited_pairs - evidence_pairs)
    if missing_pairs:
        errors.append(
            f"concept-cited source relationships missing evidence: {missing_pairs[:25]}"
        )

    for concept_id, concept in concepts.items():
        rows = concept_evidence.get(concept_id, [])
        if not rows:
            errors.append(f"{concept_id}: no evidence records")
            continue
        ambiguities = [value for value in concept.get("AMBIGUITIES", []) if str(value).strip()]
        if ambiguities and not any(
            row.get("SUPPORTED_FIELD") == "DETERMINISTIC_CONSTRUCTION"
            and row.get("CONFIDENCE") == "INSUFFICIENT"
            for row in rows
        ):
            errors.append(
                f"{concept_id}: ambiguity exists but no explicit insufficient construction evidence"
            )

    coverage = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    if coverage.get("semantic_synthesis_performed") is not False:
        errors.append("coverage report must state semantic_synthesis_performed=false")
    if coverage.get("concept_count") != len(concepts):
        errors.append(f"coverage concept count {coverage.get('concept_count')} != {len(concepts)}")
    if coverage.get("covered_concept_count") != len(concepts):
        errors.append(
            f"coverage does not cover all concepts: {coverage.get('covered_concept_count')} / {len(concepts)}"
        )
    if coverage.get("retrieval_failures"):
        errors.append(f"evidence extraction retrieval failures: {coverage.get('retrieval_failures')}")

    if errors:
        print("Evidence registry validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "concepts": len(concepts),
                "evidence_records": len(evidence),
                "evidence_shards": len(list(Path().glob("research/evidence_registry*.jsonl"))),
                "cited_relationships": len(cited_pairs),
                "concepts_with_direct_or_partial_text": sum(
                    1
                    for rows in concept_evidence.values()
                    if any(row.get("CONFIDENCE") != "INSUFFICIENT" for row in rows)
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
