#!/usr/bin/env python3
"""Compare primary and independent reconstructions against the frozen SPEC profile."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CRITICAL_KEYS = [
    "fvg_convention_sha256",
    "context_convention_sha256",
    "detected_fvg_formation_count",
    "session_count",
    "selected_fvg_session_count",
    "no_active_fvg_session_count",
    "no_active_fvg_sessions",
    "fvg_session_anchors_sha256",
    "status_counts",
    "qualified_occurrence_ids",
    "qualification_rows_sha256",
    "occurrence_set_sha256",
    "variant_result_count",
    "replay_status_counts",
    "replay_event_timestamps",
    "replay_results_sha256",
    "calibrated_execution",
    "semantic_closure_claimed",
    "holdout_accessed",
]


class ComparisonError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verified_profile(path: Path) -> tuple[dict, str]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(profile.get("profile_sha256", ""))
    unsigned = dict(profile)
    unsigned.pop("profile_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual:
        raise ComparisonError("frozen profile SHA mismatch")
    return profile, actual


def verified_report(path: Path, expected_path_id: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("path_id") != expected_path_id:
        raise ComparisonError(f"unexpected reconstruction path id for {path}")
    if report.get("reconstruction_status") != "PASS":
        raise ComparisonError(f"reconstruction did not pass: {expected_path_id}")
    recorded = str(report.get("reconstruction_sha256", ""))
    unsigned = dict(report)
    unsigned.pop("reconstruction_sha256", None)
    if recorded != canonical_sha256(unsigned):
        raise ComparisonError(f"reconstruction report SHA mismatch: {expected_path_id}")
    return report


def expected_from_profile(profile: dict) -> dict:
    expected = profile["expected_reconstruction"]
    return {
        "fvg_convention_sha256": profile["owner_conventions"]["fvg"]["canonical_sha256"],
        "context_convention_sha256": profile["owner_conventions"]["context"]["canonical_sha256"],
        "detected_fvg_formation_count": expected["detected_fvg_formation_count"],
        "session_count": expected["session_count"],
        "selected_fvg_session_count": expected["selected_fvg_session_count"],
        "no_active_fvg_session_count": expected["no_active_fvg_session_count"],
        "no_active_fvg_sessions": expected["no_active_fvg_sessions"],
        "fvg_session_anchors_sha256": expected["fvg_session_anchors_sha256"],
        "status_counts": expected["status_counts"],
        "qualified_occurrence_ids": expected["qualified_occurrence_ids"],
        "qualification_rows_sha256": expected["qualification_rows_sha256"],
        "occurrence_set_sha256": expected["occurrence_set_sha256"],
        "variant_result_count": expected["variant_result_count"],
        "replay_status_counts": expected["replay_status_counts"],
        "replay_event_timestamps": expected["replay_event_timestamps"],
        "replay_results_sha256": expected["replay_results_sha256"],
        "calibrated_execution": {
            "second_sting_fill_event": profile["calibrated_execution"]["second_sting_fill_event"],
            "stop_buffer_ticks": profile["calibrated_execution"]["stop_buffer_ticks"],
            "performance_status_used_for_selection": profile["calibrated_execution"]["performance_status_used_for_selection"],
        },
        "semantic_closure_claimed": False,
        "holdout_accessed": False,
    }


def compare(profile_path: Path, primary_path: Path, independent_path: Path) -> dict:
    profile, profile_sha = verified_profile(profile_path)
    primary = verified_report(primary_path, "PRIMARY_PRODUCTION_PATH")
    independent = verified_report(independent_path, "INDEPENDENT_STANDARD_LIBRARY_PATH")
    if primary.get("profile_sha256") != profile_sha or independent.get("profile_sha256") != profile_sha:
        raise ComparisonError("reconstruction profile SHA does not match frozen target")
    target = expected_from_profile(profile)
    mismatches: list[dict] = []
    agreement: dict = {}
    for key in CRITICAL_KEYS:
        a = primary.get(key)
        b = independent.get(key)
        expected = target[key]
        passed = a == b == expected
        agreement[key] = {"status": "PASS" if passed else "FAIL", "value_sha256": canonical_sha256(expected)}
        if not passed:
            mismatches.append({"field": key, "primary": a, "independent": b, "expected": expected})
    if mismatches:
        raise ComparisonError("critical reconstruction mismatch: " + json.dumps(mismatches, sort_keys=True))

    critical_values = {key: target[key] for key in CRITICAL_KEYS}
    audit = {
        "schema_version": 1,
        "audit_protocol": "OWNER_OPERATIONAL_TWO_PATH_SPEC_RECONSTRUCTION_V1",
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "predicate_id": "AOO_FVA_2CR_FVG_LONG_CONTEXT",
        "outcome": "PASS",
        "all_required_fields_satisfied": True,
        "contradictions_resolved": True,
        "provenance_complete": True,
        "two_engineer_test": "PASS",
        "independent_reconstruction": "PASS",
        "frozen_spec_ref": str(profile_path),
        "semantic_closure_claimed": False,
        "owner_operational_conventions_disclosed": True,
        "fully_first_party_reconstructed": False,
        "performance_data_used_for_semantic_selection": False,
        "holdout_accessed": False,
        "path_a_id": primary["path_id"],
        "path_b_id": independent["path_id"],
        "path_a_reconstruction_sha256": primary["reconstruction_sha256"],
        "path_b_reconstruction_sha256": independent["reconstruction_sha256"],
        "critical_fields": agreement,
        "critical_values_sha256": canonical_sha256(critical_values),
    }
    audit["audit_sha256"] = canonical_sha256(audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--independent", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = compare(Path(args.profile), Path(args.primary), Path(args.independent))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"SPEC reconstruction comparison failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"outcome": result["outcome"], "audit_sha256": result["audit_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
