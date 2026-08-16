#!/usr/bin/env python3
"""Compare two independent serialization paths for the Phase 5 reconstruction packet.

This is the deterministic precursor to the later independent SPEC_READY audit. It
does not claim two independent humans or models; it proves that candidate packets,
explicit evidence-recovery field overrides, and the generated matrix reconstruct
the same normalized field assignments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def load_overrides(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("performance_data_consulted") is not False:
        raise ValueError("predicate field overrides must state performance_data_consulted=false")
    result: dict[tuple[str, str], dict] = {}
    for row in data.get("overrides", []):
        key = (str(row.get("predicate_id", "")), str(row.get("field", "")))
        if not all(key):
            raise ValueError("predicate field override requires predicate_id and field")
        if key in result:
            raise ValueError(f"duplicate predicate field override {key[0]}/{key[1]}")
        result[key] = row
    return result


def from_candidate_registry(
    data: dict,
    overrides: dict[tuple[str, str], dict],
) -> dict[str, list[dict]]:
    fields = list(data["required_fields"])
    result: dict[str, list[dict]] = {}
    for candidate in data.get("candidates", []):
        predicate_id = str(candidate["predicate_id"])
        hypotheses = dict(candidate.get("field_hypotheses", {}))
        rows: list[dict] = []
        for field in fields:
            override = overrides.get((predicate_id, field))
            if override is not None:
                hypothesis = {
                    "state": override.get("state"),
                    "evidence_ids": override.get("evidence_ids", []),
                    "notes": override.get("notes", ""),
                }
            else:
                hypothesis = hypotheses.get(field)
            if hypothesis is None:
                rows.append(
                    {
                        "field": field,
                        "state": "MISSING",
                        "evidence_ids": [],
                        "notes": f"No direct first-party evidence in the current registry establishes {field} for this candidate.",
                    }
                )
            else:
                rows.append(
                    {
                        "field": field,
                        "state": str(hypothesis["state"]),
                        "evidence_ids": [str(value) for value in hypothesis.get("evidence_ids", [])],
                        "notes": str(hypothesis.get("notes", "")).strip(),
                    }
                )
        result[predicate_id] = rows
    return result


def from_matrix(path: Path, canonical_fields: list[str]) -> dict[str, list[dict]]:
    grouped: dict[str, dict[str, dict]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            predicate_id = str(row["PREDICATE_ID"])
            grouped.setdefault(predicate_id, {})[str(row["FIELD"])] = {
                "field": str(row["FIELD"]),
                "state": str(row["STATE"]),
                "evidence_ids": [value for value in str(row["EVIDENCE_IDS"]).split(";") if value],
                "notes": str(row["NOTES"]),
            }
    return {
        predicate_id: [field_map[field] for field in canonical_fields if field in field_map]
        for predicate_id, field_map in grouped.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    parser.add_argument("--overrides", default="research/predicate_field_overrides.json")
    parser.add_argument("--matrix", default="research/predicate_matrix.csv")
    parser.add_argument("--output", default="research/two_engineer_preflight.json")
    args = parser.parse_args()

    candidate_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    fields = list(candidate_data["required_fields"])
    overrides = load_overrides(Path(args.overrides))
    engineer_a = from_candidate_registry(candidate_data, overrides)
    engineer_b = from_matrix(Path(args.matrix), fields)
    predicate_ids = sorted(set(engineer_a) | set(engineer_b))
    results: list[dict] = []
    mismatch = False
    for predicate_id in predicate_ids:
        a_value = engineer_a.get(predicate_id)
        b_value = engineer_b.get(predicate_id)
        a_hash = digest(a_value)
        b_hash = digest(b_value)
        agreement = a_value == b_value
        mismatch = mismatch or not agreement
        results.append(
            {
                "predicate_id": predicate_id,
                "candidate_registry_hash": a_hash,
                "matrix_reconstruction_hash": b_hash,
                "agreement": agreement,
            }
        )

    report = {
        "schema_version": 1,
        "protocol": "TWO_ENGINEER_DETERMINISTIC_RECONSTRUCTION_PREFLIGHT",
        "independence_scope": "TWO_INDEPENDENT_CODE_PATHS_OVER_THE_SAME_EVIDENCE_ONLY_PACKET",
        "field_overrides_included": bool(overrides),
        "field_override_count": len(overrides),
        "independent_humans_or_models": False,
        "satisfies_independent_spec_ready_audit": False,
        "performance_data_consulted": False,
        "status": "FAIL" if mismatch else "PASS",
        "candidate_count": len(predicate_ids),
        "candidates": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidate_count": len(predicate_ids),
                "field_override_count": len(overrides),
            },
            sort_keys=True,
        )
    )
    if mismatch:
        print("Two-path reconstruction mismatch detected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
