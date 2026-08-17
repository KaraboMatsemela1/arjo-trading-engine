#!/usr/bin/env python3
"""Strict schema and provenance validation for the acquisition manifest union."""

from __future__ import annotations

import argparse
import re
import sys

from acquisition_manifest_union import DEFAULT_ACQUISITION_GLOB, load_acquisition_union
from acquisition_states import ACQUISITION_STATES
from source_registry_union import DEFAULT_SOURCE_GLOB, load_source_union

REQUIRED = {
    "schema_version", "acquisition_id", "source_id", "source_type", "source_url",
    "attempted_at", "status", "transport", "first_party_contacted", "closure_credit",
    "semantic_extraction_performed", "artifacts", "sha256", "error_class",
    "error_detail", "http_status", "notes",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=DEFAULT_SOURCE_GLOB)
    parser.add_argument("--manifest", default=DEFAULT_ACQUISITION_GLOB)
    args = parser.parse_args()

    errors: list[str] = []
    try:
        source_ids = {str(row["SOURCE_ID"]) for row in load_source_union(args.registry)}
        records = load_acquisition_union(args.manifest)
    except ValueError as exc:
        print(f"Acquisition manifest validation failed:\n- {exc}", file=sys.stderr)
        return 1

    for index, record in enumerate(records, start=1):
        missing = REQUIRED - set(record)
        if missing:
            errors.append(f"record {index}: missing fields {sorted(missing)}")
            continue
        source_id = str(record["source_id"])
        if source_id not in source_ids:
            errors.append(f"record {index}: unknown source_id {source_id}")
        if record["status"] not in ACQUISITION_STATES:
            errors.append(f"record {index}: invalid status {record['status']}")
        if record["semantic_extraction_performed"] is not False:
            errors.append(f"record {index}: semantic extraction must remain false")
        artifacts = record["artifacts"]
        if not isinstance(artifacts, list):
            errors.append(f"record {index}: artifacts must be a list")
            continue
        if record["status"] == "PAYLOAD_CAPTURED":
            if not artifacts:
                errors.append(f"record {index}: captured payload has no artifacts")
            if not HEX64.match(str(record["sha256"])):
                errors.append(f"record {index}: captured payload lacks valid sha256")
            if record["first_party_contacted"] and record["closure_credit"] != "DIRECT_FIRST_PARTY_PAYLOAD":
                errors.append(f"record {index}: direct captured payload lacks direct closure credit")
        else:
            if record["sha256"]:
                errors.append(f"record {index}: non-captured status claims sha256")
            if record["closure_credit"] not in {"ZERO_NO_PAYLOAD", "ZERO_FIXTURE_ONLY", "ZERO_LOCATOR_ONLY"}:
                errors.append(f"record {index}: non-captured status claims semantic closure credit")
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not HEX64.match(str(artifact.get("sha256", ""))):
                errors.append(f"record {index}: invalid artifact sha256")
            if not isinstance(artifact, dict) or not isinstance(artifact.get("bytes"), int) or artifact.get("bytes", -1) < 0:
                errors.append(f"record {index}: invalid artifact byte length")
        if record["closure_credit"] in {"ZERO_FIXTURE_ONLY", "ZERO_LOCATOR_ONLY"} and record["first_party_contacted"]:
            errors.append(f"record {index}: zero-credit locator/fixture cannot claim first-party contact")

    if errors:
        print("Acquisition manifest validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Acquisition manifest validation passed: {len(records)} terminal records across shards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
