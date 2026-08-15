#!/usr/bin/env python3
"""Require exactly one terminal acquisition disposition for every item source."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from acquisition_states import ACQUISITION_STATES

LOCATOR_TYPES = {"PLATFORM_ROOT", "LINK_HUB", "FIRST_PARTY_LINKED_RESOURCE"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--manifest", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--report", default="research/corpus_coverage.json")
    args = parser.parse_args()

    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("SOURCE_ID") and row.get("URL")]
    relevant = {
        row["SOURCE_ID"]: row
        for row in rows
        if row.get("SOURCE_TYPE") not in LOCATOR_TYPES
    }

    records: dict[str, dict] = {}
    duplicates: list[str] = []
    for raw in Path(args.manifest).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        source_id = str(record.get("source_id", ""))
        if source_id in records:
            duplicates.append(source_id)
        records[source_id] = record

    missing = sorted(set(relevant) - set(records))
    unexpected = sorted(set(records) - set(relevant))
    invalid_states = sorted(
        source_id for source_id, record in records.items()
        if source_id in relevant and record.get("status") not in ACQUISITION_STATES
    )
    semantic_violations = sorted(
        source_id for source_id, record in records.items()
        if source_id in relevant and record.get("semantic_extraction_performed") is not False
    )

    by_status = Counter()
    by_type = Counter()
    captured_by_type = Counter()
    for source_id, row in relevant.items():
        record = records.get(source_id)
        if not record:
            continue
        source_type = row.get("SOURCE_TYPE", "")
        status = str(record.get("status", ""))
        by_type[source_type] += 1
        by_status[status] += 1
        if status == "PAYLOAD_CAPTURED":
            captured_by_type[source_type] += 1

    complete = not (missing or unexpected or duplicates or invalid_states or semantic_violations)
    report = {
        "schema_version": 1,
        "complete": complete,
        "relevant_source_count": len(relevant),
        "terminal_record_count": len(records),
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "duplicate_count": len(duplicates),
        "invalid_state_count": len(invalid_states),
        "semantic_violation_count": len(semantic_violations),
        "by_status": dict(sorted(by_status.items())),
        "by_source_type": dict(sorted(by_type.items())),
        "captured_by_source_type": dict(sorted(captured_by_type.items())),
        "missing_source_ids": missing[:100],
        "unexpected_source_ids": unexpected[:100],
        "duplicate_source_ids": sorted(set(duplicates))[:100],
        "invalid_state_source_ids": invalid_states[:100],
        "semantic_violation_source_ids": semantic_violations[:100],
        "semantic_synthesis_performed": False,
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("complete", "relevant_source_count", "terminal_record_count", "missing_count", "by_status")}, sort_keys=True))

    if not complete:
        print("Corpus coverage is incomplete", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
