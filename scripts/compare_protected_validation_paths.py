#!/usr/bin/env python3
"""Compare protected validation paths and compute preregistered metrics/classification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

PROTOCOL_SHA = "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"
PROFILE_SHA = "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"
FROZEN_CRITICAL = [
    "complete_session_count",
    "detected_fvg_formation_count",
    "selected_fvg_session_count",
    "qualification_status_counts",
    "qualified_occurrence_ids",
    "occurrence_set_sha256",
    "execution_outcomes",
    "execution_outcomes_sha256",
    "holdout_boundary_ok",
]
EXTRA_AGREEMENT = [
    "holdout_formed_fvg_count",
    "qualification_rows_sha256",
    "integrity_failures",
    "integrity_failures_sha256",
    "frozen_execution",
]
OUTCOME_CLASSES = ["TARGET_FIRST", "STOP_FIRST", "AMBIGUOUS_INTRABAR_ORDER", "UNRESOLVED_WINDOW_END"]


class ComparisonError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verified_report(path: Path, path_id: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("path_id") != path_id:
        raise ComparisonError(f"unexpected path id: {path}")
    if report.get("protocol_sha256") != PROTOCOL_SHA or report.get("profile_sha256") != PROFILE_SHA:
        raise ComparisonError(f"frozen protocol/profile binding changed: {path_id}")
    if report.get("holdout_accessed") is not True or report.get("no_refit_performed") is not True:
        raise ComparisonError(f"holdout/no-refit boundary failed: {path_id}")
    recorded = str(report.get("report_sha256", "")); unsigned = dict(report); unsigned.pop("report_sha256", None)
    if recorded != canon(unsigned):
        raise ComparisonError(f"report SHA mismatch: {path_id}")
    return report


def wilson(successes: int, n: int, z: float) -> dict | None:
    if n <= 0:
        return None
    p = successes / n; denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return {"lower": center-half, "upper": center+half, "confidence": 0.95, "z": z}


def compare(protocol_path: Path, primary_path: Path, independent_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_sha256") != PROTOCOL_SHA:
        raise ComparisonError("protected validation protocol SHA changed")
    frozen_fields = protocol.get("dual_path_validation", {}).get("critical_agreement_fields")
    if frozen_fields != FROZEN_CRITICAL:
        raise ComparisonError("frozen critical agreement field list changed")
    primary = verified_report(primary_path, "PRIMARY_PRODUCTION_PATH")
    independent = verified_report(independent_path, "INDEPENDENT_STANDARD_LIBRARY_PATH")

    mismatches: list[dict] = []
    agreement: dict[str, dict] = {}
    for key in FROZEN_CRITICAL + EXTRA_AGREEMENT:
        a, b = primary.get(key), independent.get(key)
        passed = a == b
        agreement[key] = {"status": "PASS" if passed else "FAIL", "value_sha256": canon(a) if passed else None}
        if not passed:
            mismatches.append({"field": key, "primary": a, "independent": b})

    if mismatches:
        classification = "IMPLEMENTATION_DIVERGENCE"
        metrics = None
    else:
        outcomes = primary["execution_outcomes"]
        failures = primary["integrity_failures"]
        counts = Counter(row["status"] for row in outcomes)
        outcome_counts = {name: int(counts.get(name, 0)) for name in OUTCOME_CLASSES}
        qualified = len(primary["qualified_occurrence_ids"])
        complete_sessions = int(primary["complete_session_count"])
        resolved = outcome_counts["TARGET_FIRST"] + outcome_counts["STOP_FIRST"]
        realized_r: list[float] = []
        for row in outcomes:
            if row["status"] == "STOP_FIRST":
                realized_r.append(-1.0)
            elif row["status"] == "TARGET_FIRST":
                entry, stop, target = float(row["entry_price"]), float(row["stop_price"]), float(row["target_price"])
                realized_r.append((target-entry)/(entry-stop))
        mean_r = sum(realized_r)/len(realized_r) if realized_r else None
        cumulative_r = sum(realized_r) if realized_r else None
        target_prop = outcome_counts["TARGET_FIRST"]/resolved if resolved else None
        z = float(protocol["metrics"]["wilson_interval"]["z"])
        metrics = {
            "qualified_occurrence_count": qualified,
            "resolved_occurrence_count": resolved,
            "outcome_counts": outcome_counts,
            "occurrence_rate_per_complete_session": qualified/complete_sessions if complete_sessions else None,
            "realized_r": realized_r,
            "mean_realized_r_when_resolved": mean_r,
            "cumulative_realized_r_when_resolved": cumulative_r,
            "target_first_proportion_among_resolved": target_prop,
            "target_first_wilson_interval_95": wilson(outcome_counts["TARGET_FIRST"], resolved, z),
            "inferential_resolved_occurrence_threshold": int(protocol["sample_policy"]["inferential_resolved_occurrence_threshold"]),
        }
        if failures:
            classification = "VALIDATION_INTEGRITY_FAILURE"
        elif qualified == 0:
            classification = "NO_QUALIFYING_OCCURRENCES"
        elif resolved < metrics["inferential_resolved_occurrence_threshold"]:
            classification = "INSUFFICIENT_SAMPLE"
        elif mean_r is not None and mean_r > 0:
            classification = "SUFFICIENT_SAMPLE_POSITIVE"
        else:
            classification = "SUFFICIENT_SAMPLE_NONPOSITIVE"

    result = {
        "schema_version": 1,
        "status": "PROTECTED_VALIDATION_COMPLETE",
        "validation_protocol_id": protocol["protocol_id"],
        "validation_protocol_sha256": PROTOCOL_SHA,
        "profile_id": protocol["profile"]["profile_id"],
        "profile_sha256": PROFILE_SHA,
        "validation_classification": classification,
        "implementation_agreement": not mismatches,
        "critical_agreement": agreement,
        "mismatches": mismatches,
        "primary_report_sha256": primary["report_sha256"],
        "independent_report_sha256": independent["report_sha256"],
        "complete_session_count": primary["complete_session_count"] if not mismatches else None,
        "detected_fvg_formation_count": primary["detected_fvg_formation_count"] if not mismatches else None,
        "holdout_formed_fvg_count": primary["holdout_formed_fvg_count"] if not mismatches else None,
        "selected_fvg_session_count": primary["selected_fvg_session_count"] if not mismatches else None,
        "qualification_status_counts": primary["qualification_status_counts"] if not mismatches else None,
        "qualified_occurrence_ids": primary["qualified_occurrence_ids"] if not mismatches else None,
        "qualification_rows_sha256": primary["qualification_rows_sha256"] if not mismatches else None,
        "occurrence_set_sha256": primary["occurrence_set_sha256"] if not mismatches else None,
        "execution_outcomes": primary["execution_outcomes"] if not mismatches else None,
        "execution_outcomes_sha256": primary["execution_outcomes_sha256"] if not mismatches else None,
        "integrity_failures": primary["integrity_failures"] if not mismatches else None,
        "integrity_failures_sha256": primary["integrity_failures_sha256"] if not mismatches else None,
        "metrics": metrics,
        "holdout_accessed": True,
        "holdout_window": protocol["window"],
        "no_refit_performed": True,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    unsigned = dict(result); result["validation_result_sha256"] = canon(unsigned)
    return result


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("--protocol",required=True);p.add_argument("--primary",required=True);p.add_argument("--independent",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    try:
        result=compare(Path(a.protocol),Path(a.primary),Path(a.independent));Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except Exception as exc:
        print(f"protected validation comparison failed: {exc}",file=sys.stderr);return 1
    print(json.dumps({"status":result["status"],"classification":result["validation_classification"],"implementation_agreement":result["implementation_agreement"],"result_sha256":result["validation_result_sha256"]},sort_keys=True));return 0


if __name__ == "__main__": raise SystemExit(main())
