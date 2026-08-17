#!/usr/bin/env python3
"""Fail-closed verification of the sealed protected validation result."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from compare_protected_validation_paths import compare

EXPECTED_PROTOCOL_SHA = "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"
EXPECTED_PROFILE_SHA = "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"
EXPECTED_PRIMARY_SHA = "40911d352e79ac1a512bef58354414047ad3c440536a4361a5db06f9c3ea7597"
EXPECTED_INDEPENDENT_SHA = "db8b285791f6bc51b5d420e4f092ef780208f64a75d16de6980edc141562f8e8"
EXPECTED_RESULT_SHA = "a3f1afbaf1a9206fef4b6e11b3f0b42d6eba022f67b94e0a756708cc3323e474"
EXPECTED_OCCURRENCE_SHA = "be83b83b4bc4ca4807e43397d0bb977f2779281db685b0c1a04e71641a027cd8"
EXPECTED_QUALIFICATION_SHA = "0707ea9fcca783a33102804e3b76a8d388b415662f3b7e831dc43f237442bfd6"
EXPECTED_INTEGRITY_SHA = "d68b2ecd93f19db09af4a32a5d6aa66090052309aa0e261a6bdb46610a2ede82"
EXPECTED_OUTCOME_SHA = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e7b1a24e0b313b6a27e136"
EXPECTED_HOLDOUT_ARTIFACT_ID = 9287054804
EXPECTED_VALIDATION_ARTIFACT_ID = 9287604531


class ResultError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def verified_embedded(path: Path, field: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(data.get(field, ""))
    unsigned = dict(data)
    unsigned.pop(field, None)
    if recorded != canonical_sha256(unsigned):
        raise ResultError(f"{path} embedded {field} mismatch")
    return data


def validate(
    *,
    protocol_path: Path,
    readiness_path: Path,
    primary_path: Path,
    independent_path: Path,
    result_path: Path,
) -> dict:
    protocol = verified_embedded(protocol_path, "protocol_sha256")
    if protocol.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA:
        raise ResultError("protected protocol SHA changed")
    if protocol.get("profile", {}).get("profile_sha256") != EXPECTED_PROFILE_SHA:
        raise ResultError("protected profile binding changed")

    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if readiness.get("status") != "PROTECTED_HOLDOUT_DATA_READY":
        raise ResultError("protected holdout readiness missing")
    if readiness.get("artifact_id") != EXPECTED_HOLDOUT_ARTIFACT_ID:
        raise ResultError("unexpected holdout artifact id")
    if readiness.get("holdout_accessed") is not True:
        raise ResultError("holdout readiness must record accessed=true")
    if readiness.get("calibration_window_accessed_by_holdout_job") is not False:
        raise ResultError("holdout acquisition improperly accessed calibration window")
    authorization = readiness.get("authorization", {})
    for key in ("profile_refit_authorized", "alternate_variant_selection_authorized", "paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized"):
        if authorization.get(key) is not False:
            raise ResultError(f"holdout readiness authorization changed: {key}")

    primary = verified_embedded(primary_path, "report_sha256")
    independent = verified_embedded(independent_path, "report_sha256")
    if primary.get("report_sha256") != EXPECTED_PRIMARY_SHA:
        raise ResultError("primary protected report SHA changed")
    if independent.get("report_sha256") != EXPECTED_INDEPENDENT_SHA:
        raise ResultError("independent protected report SHA changed")

    result = verified_embedded(result_path, "validation_result_sha256")
    if result.get("validation_result_sha256") != EXPECTED_RESULT_SHA:
        raise ResultError("protected validation result SHA changed")

    regenerated = compare(protocol_path, primary_path, independent_path)
    invariant_fields = (
        "status",
        "validation_protocol_id",
        "validation_protocol_sha256",
        "profile_id",
        "profile_sha256",
        "validation_classification",
        "implementation_agreement",
        "primary_report_sha256",
        "independent_report_sha256",
        "complete_session_count",
        "detected_fvg_formation_count",
        "holdout_formed_fvg_count",
        "selected_fvg_session_count",
        "qualification_status_counts",
        "qualified_occurrence_ids",
        "qualification_rows_sha256",
        "occurrence_set_sha256",
        "execution_outcomes",
        "execution_outcomes_sha256",
        "integrity_failures",
        "integrity_failures_sha256",
        "metrics",
        "holdout_accessed",
        "no_refit_performed",
        "paper_execution_authorized",
        "live_execution_authorized",
        "broker_mutation_authorized",
        "validation_result_sha256",
    )
    for field in invariant_fields:
        if result.get(field) != regenerated.get(field):
            raise ResultError(f"committed result differs from regenerated comparison: {field}")

    if result.get("status") != "PROTECTED_VALIDATION_COMPLETE":
        raise ResultError("protected validation is not complete")
    if result.get("validation_classification") != "VALIDATION_INTEGRITY_FAILURE":
        raise ResultError("unexpected protected validation classification")
    if result.get("implementation_agreement") is not True:
        raise ResultError("protected validation paths do not agree")
    critical = result.get("critical_agreement", {})
    if not isinstance(critical, dict) or len(critical) != 14 or any(v.get("status") != "PASS" for v in critical.values() if isinstance(v, dict)):
        raise ResultError("all 14 protected agreement fields must PASS")

    expected_funnel = {
        "NO_2CR_REJECTION": 16,
        "NO_FVA_OVERLAP": 101,
        "NO_RUN": 8,
        "QUALIFIED": 1,
    }
    if result.get("complete_session_count") != 126:
        raise ResultError("unexpected protected complete-session count")
    if result.get("detected_fvg_formation_count") != 443 or result.get("holdout_formed_fvg_count") != 96:
        raise ResultError("unexpected protected FVG counts")
    if result.get("selected_fvg_session_count") != 126:
        raise ResultError("unexpected selected-FVG session count")
    if result.get("qualification_status_counts") != expected_funnel:
        raise ResultError("unexpected protected qualification funnel")
    if result.get("qualified_occurrence_ids") != ["OWNER-VAL-2026-06-23"]:
        raise ResultError("unexpected protected qualified occurrence")
    if result.get("qualification_rows_sha256") != EXPECTED_QUALIFICATION_SHA:
        raise ResultError("protected qualification ledger SHA changed")
    if result.get("occurrence_set_sha256") != EXPECTED_OCCURRENCE_SHA:
        raise ResultError("protected occurrence set SHA changed")
    if result.get("execution_outcomes") != [] or result.get("execution_outcomes_sha256") != EXPECTED_OUTCOME_SHA:
        raise ResultError("execution outcomes must remain empty after unobservable fill")

    failures = result.get("integrity_failures")
    if not isinstance(failures, list) or len(failures) != 1:
        raise ResultError("expected exactly one protected integrity failure")
    failure = failures[0]
    expected_failure = {
        "bar_high": "29693.4",
        "bar_low": "29578.0",
        "kind": "UNOBSERVABLE_SECOND_STING_TOUCH",
        "occurrence_id": "OWNER-VAL-2026-06-23",
        "second_sting_ts_utc": "2026-06-23T14:45:00Z",
        "touch_price": "29698.1",
    }
    if failure != expected_failure or result.get("integrity_failures_sha256") != EXPECTED_INTEGRITY_SHA:
        raise ResultError("protected execution-observability failure changed")

    metrics = result.get("metrics", {})
    if metrics.get("qualified_occurrence_count") != 1 or metrics.get("resolved_occurrence_count") != 0:
        raise ResultError("unexpected protected sample counts")
    if metrics.get("outcome_counts") != {
        "AMBIGUOUS_INTRABAR_ORDER": 0,
        "STOP_FIRST": 0,
        "TARGET_FIRST": 0,
        "UNRESOLVED_WINDOW_END": 0,
    }:
        raise ResultError("unexpected protected outcome counts")
    if metrics.get("mean_realized_r_when_resolved") is not None or metrics.get("cumulative_realized_r_when_resolved") is not None:
        raise ResultError("R metrics must remain undefined with zero resolved occurrences")
    if metrics.get("inferential_resolved_occurrence_threshold") != 30:
        raise ResultError("protected sample threshold changed")

    for key in ("paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized"):
        if result.get(key) is not False:
            raise ResultError(f"protected result must not authorize {key}")
    if result.get("holdout_accessed") is not True or result.get("no_refit_performed") is not True:
        raise ResultError("holdout/no-refit result boundary changed")

    return {
        "status": "PROTECTED_VALIDATION_COMPLETE",
        "validation_classification": result["validation_classification"],
        "validation_result_sha256": result["validation_result_sha256"],
        "primary_report_sha256": primary["report_sha256"],
        "independent_report_sha256": independent["report_sha256"],
        "qualified_occurrence_id": result["qualified_occurrence_ids"][0],
        "integrity_failure": failure["kind"],
        "holdout_accessed": True,
        "no_refit_performed": True,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "validation_artifact_id": EXPECTED_VALIDATION_ARTIFACT_ID,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="research/validation/protected_validation_protocol_v1.json")
    parser.add_argument("--readiness", default="research/validation/protected_holdout_data_readiness.json")
    parser.add_argument("--primary", default="research/validation/reconstruction/PRIMARY_PROTECTED_VALIDATION_PATH.json")
    parser.add_argument("--independent", default="research/validation/reconstruction/INDEPENDENT_PROTECTED_VALIDATION_PATH.json")
    parser.add_argument("--result", default="research/validation/PROTECTED_VALIDATION.json")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        summary = validate(
            protocol_path=Path(args.protocol),
            readiness_path=Path(args.readiness),
            primary_path=Path(args.primary),
            independent_path=Path(args.independent),
            result_path=Path(args.result),
        )
    except (OSError, json.JSONDecodeError, ResultError) as exc:
        print(f"protected validation result check failed: {exc}", file=sys.stderr)
        return 1
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
