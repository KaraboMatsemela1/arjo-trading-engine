#!/usr/bin/env python3
"""Validate research registry schemas and evidence-to-predicate provenance."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from evidence_registry_union import DEFAULT_EVIDENCE_GLOB, load_evidence_union

SOURCE_FIELDS = {
    "SOURCE_ID",
    "SOURCE_TYPE",
    "TITLE",
    "URL",
    "PUBLICATION_DATE",
    "AUTHOR",
    "CHANNEL_ID",
    "FIRST_PARTY_STATUS",
    "RETRIEVAL_DATE",
    "RAW_ARTIFACT_SHA256",
    "TRANSCRIPT_AVAILABLE",
    "FRAME_EXTRACTION_AVAILABLE",
    "NOTES",
}
EVIDENCE_FIELDS = {
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
CONFIDENCE = {"DIRECT", "STRONG_PARTIAL", "CONTEXTUAL", "INSUFFICIENT"}
PREDICATE_STATES = {"SATISFIED", "PARTIAL", "MISSING", "CONTRADICTORY", "NOT_APPLICABLE"}
ACQUISITION_STATES = {
    "ENVIRONMENT_ACCESS_FAILURE",
    "SOURCE_CONTACTED_NO_PAYLOAD",
    "PAYLOAD_CAPTURED",
    "SOURCE_REMOVED",
    "SOURCE_UNAVAILABLE_AFTER_CONTACT",
}


def read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"Missing required registry: {path}"]
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}:{line_number}: record must be a JSON object")
            continue
        records.append(value)
    return records, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_GLOB)
    args = parser.parse_args()
    root = Path(args.repo_root)
    errors: list[str] = []

    source_path = root / "research/source_registry.csv"
    if not source_path.exists():
        errors.append(f"Missing required registry: {source_path}")
        source_rows = []
    else:
        with source_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            missing = SOURCE_FIELDS - fields
            if missing:
                errors.append(f"source_registry.csv missing fields: {sorted(missing)}")
            source_rows = list(reader)
    source_ids = {row.get("SOURCE_ID", "") for row in source_rows if row.get("SOURCE_ID")}
    if len(source_ids) != len([row for row in source_rows if row.get("SOURCE_ID")]):
        errors.append("source_registry.csv contains duplicate SOURCE_ID values")

    try:
        pattern = args.evidence
        if not Path(args.repo_root).resolve() == Path(".").resolve():
            # Repository-root override is used only by local/offline validation. Resolve
            # the default shard glob relative to that root without changing CLI behavior.
            pattern = str(root / pattern) if any(char in pattern for char in "*?[") else str(root / pattern)
        evidence_records = load_evidence_union(pattern)
    except (ValueError, json.JSONDecodeError) as exc:
        evidence_records = []
        errors.append(f"Evidence registry union invalid: {exc}")

    evidence_ids: set[str] = set()
    for record in evidence_records:
        missing = EVIDENCE_FIELDS - set(record)
        if missing:
            errors.append(f"Evidence record missing fields: {sorted(missing)}")
            continue
        evidence_id = str(record["EVIDENCE_ID"])
        if evidence_id in evidence_ids:
            errors.append(f"Duplicate EVIDENCE_ID: {evidence_id}")
        evidence_ids.add(evidence_id)
        if record["CONFIDENCE"] not in CONFIDENCE:
            errors.append(f"Invalid evidence confidence for {evidence_id}: {record['CONFIDENCE']}")
        if record["SOURCE_ID"] not in source_ids:
            errors.append(f"Evidence {evidence_id} references unknown SOURCE_ID {record['SOURCE_ID']}")

    predicate_path = root / "research/predicate_matrix.csv"
    if not predicate_path.exists():
        errors.append(f"Missing required registry: {predicate_path}")
    else:
        with predicate_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"PREDICATE_ID", "FIELD", "STATE", "EVIDENCE_IDS", "NOTES"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                errors.append(f"predicate_matrix.csv missing fields: {sorted(missing)}")
            for row_number, row in enumerate(reader, start=2):
                state = row.get("STATE", "")
                if state not in PREDICATE_STATES:
                    errors.append(f"predicate_matrix.csv:{row_number}: invalid STATE {state}")
                refs = [value.strip() for value in row.get("EVIDENCE_IDS", "").split(";") if value.strip()]
                if state == "SATISFIED" and not refs:
                    errors.append(f"predicate_matrix.csv:{row_number}: SATISFIED field has no evidence")
                for evidence_id in refs:
                    if evidence_id not in evidence_ids:
                        errors.append(
                            f"predicate_matrix.csv:{row_number}: references unknown evidence {evidence_id}"
                        )

    acquisition_records, json_errors = read_jsonl(root / "research/acquisition_manifest.jsonl")
    errors.extend(json_errors)
    for index, record in enumerate(acquisition_records, start=1):
        status = record.get("status")
        if status not in ACQUISITION_STATES:
            errors.append(f"acquisition_manifest.jsonl record {index}: invalid status {status}")
        if status == "PAYLOAD_CAPTURED" and not record.get("sha256"):
            errors.append(f"acquisition_manifest.jsonl record {index}: captured payload lacks sha256")

    if errors:
        print("Provenance validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Provenance validation passed: {len(source_ids)} sources, "
        f"{len(evidence_ids)} evidence records, {len(acquisition_records)} acquisition records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
