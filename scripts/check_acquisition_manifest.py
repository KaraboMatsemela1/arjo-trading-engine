#!/usr/bin/env python3
"""Strict schema and provenance validation for acquisition_manifest.jsonl."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from acquisition_states import ACQUISITION_STATES

REQUIRED = {
    "schema_version", "acquisition_id", "source_id", "source_type", "source_url",
    "attempted_at", "status", "transport", "first_party_contacted", "closure_credit",
    "semantic_extraction_performed", "artifacts", "sha256", "error_class",
    "error_detail", "http_status", "notes",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--manifest", default="research/acquisition_manifest.jsonl")
    args = parser.parse_args()

    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        source_ids = {row["SOURCE_ID"] for row in csv.DictReader(handle) if row.get("SOURCE_ID")}

    errors: list[str] = []
    seen: set[str] = set()
    count = 0
    path = Path(args.manifest)
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        count += 1
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc}")
            continue
        missing = REQUIRED - set(record)
        if missing:
            errors.append(f"line {line_no}: missing fields {sorted(missing)}")
            continue
        source_id = str(record["source_id"])
        if source_id not in source_ids:
            errors.append(f"line {line_no}: unknown source_id {source_id}")
        if source_id in seen:
            errors.append(f"line {line_no}: duplicate terminal record for {source_id}")
        seen.add(source_id)
        if record["status"] not in ACQUISITION_STATES:
            errors.append(f"line {line_no}: invalid status {record['status']}")
        if record["semantic_extraction_performed"] is not False:
            errors.append(f"line {line_no}: semantic extraction must remain false")
        artifacts = record["artifacts"]
        if not isinstance(artifacts, list):
            errors.append(f"line {line_no}: artifacts must be a list")
            continue
        if record["status"] == "PAYLOAD_CAPTURED":
            if not artifacts:
                errors.append(f"line {line_no}: captured payload has no artifacts")
            if not HEX64.match(str(record["sha256"])):
                errors.append(f"line {line_no}: captured payload lacks valid sha256")
            if record["first_party_contacted"] and record["closure_credit"] != "DIRECT_FIRST_PARTY_PAYLOAD":
                errors.append(f"line {line_no}: direct captured payload lacks direct closure credit")
        else:
            if record["sha256"]:
                errors.append(f"line {line_no}: non-captured status claims sha256")
            if record["closure_credit"] not in {"ZERO_NO_PAYLOAD", "ZERO_FIXTURE_ONLY", "ZERO_LOCATOR_ONLY"}:
                errors.append(f"line {line_no}: non-captured status claims semantic closure credit")
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not HEX64.match(str(artifact.get("sha256", ""))):
                errors.append(f"line {line_no}: invalid artifact sha256")
            if not isinstance(artifact, dict) or not isinstance(artifact.get("bytes"), int) or artifact.get("bytes", -1) < 0:
                errors.append(f"line {line_no}: invalid artifact byte length")
        if record["closure_credit"] in {"ZERO_FIXTURE_ONLY", "ZERO_LOCATOR_ONLY"} and record["first_party_contacted"]:
            errors.append(f"line {line_no}: zero-credit locator/fixture cannot claim first-party contact")

    if errors:
        print("Acquisition manifest validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Acquisition manifest validation passed: {count} terminal records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
