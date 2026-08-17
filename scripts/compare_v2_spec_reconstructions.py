#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CRITICAL_FIELDS = [
    "profile_sha256",
    "semantic_occurrence_set_sha256",
    "qualification_rows_sha256",
    "qualification_status_counts",
    "qualified_occurrence_ids",
    "observability_rows_sha256",
    "observability_status_counts",
    "executable_occurrence_ids",
    "holdout_2026h1_accessed",
    "future_validation_data_accessed",
    "performance_comparison_performed",
    "paper_execution_authorized",
    "live_execution_authorized",
    "broker_mutation_authorized",
]


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--independent", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        primary = json.loads(Path(args.primary).read_text(encoding="utf-8"))
        independent = json.loads(Path(args.independent).read_text(encoding="utf-8"))
        expected = profile["expected_reconstruction"]
        mismatches = [field for field in CRITICAL_FIELDS if primary.get(field) != independent.get(field)]
        expected_fields = {
            "semantic_occurrence_set_sha256": expected["semantic_occurrence_set_sha256"],
            "qualification_rows_sha256": expected["qualification_rows_sha256"],
            "qualification_status_counts": expected["qualification_status_counts"],
            "qualified_occurrence_ids": expected["qualified_occurrence_ids"],
            "observability_rows_sha256": expected["observability_rows_sha256"],
            "observability_status_counts": expected["observability_status_counts"],
            "executable_occurrence_ids": expected["executable_occurrence_ids"],
        }
        for field, value in expected_fields.items():
            if primary.get(field) != value or independent.get(field) != value:
                mismatches.append("expected:" + field)
        if mismatches:
            raise RuntimeError("V2 reconstruction mismatch: " + ",".join(mismatches))
        result = {
            "schema_version": 1,
            "status": "V2_SPEC_FROZEN",
            "profile_id": profile["profile_id"],
            "profile_sha256": profile["profile_sha256"],
            "implementation_agreement": True,
            "critical_fields": CRITICAL_FIELDS,
            "primary_reconstruction_sha256": primary["reconstruction_sha256"],
            "independent_reconstruction_sha256": independent["reconstruction_sha256"],
            "semantic_occurrence_set_sha256": primary["semantic_occurrence_set_sha256"],
            "qualification_rows_sha256": primary["qualification_rows_sha256"],
            "observability_rows_sha256": primary["observability_rows_sha256"],
            "observability_status_counts": primary["observability_status_counts"],
            "executable_occurrence_ids": primary["executable_occurrence_ids"],
            "holdout_2026h1_accessed": False,
            "future_validation_data_accessed": False,
            "semantic_closure_claimed": False,
            "fully_first_party_reconstructed": False,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        result["audit_sha256"] = canonical_sha256(result)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"V2 reconstruction comparison failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "sha256": result["audit_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
