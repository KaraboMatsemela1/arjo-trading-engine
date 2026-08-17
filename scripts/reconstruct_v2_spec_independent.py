#!/usr/bin/env python3
"""V2 Path B: independent semantic reconstruction plus inline observability.

This path does not import production FVG/context/replay builders, the production
V2 observability checker, or V2 Path A.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import reconstruct_owner_operational_spec_independent as independent_v1

PROFILE_ID = "ARJO_DERIVED_OWNER_OPERATIONAL_V2"
V1_PROFILE_SHA = "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"


class V2IndependentError(RuntimeError):
    pass


def load_v2_profile(path: Path) -> tuple[dict, str]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = profile.get("profile_sha256")
    unsigned = dict(profile)
    unsigned.pop("profile_sha256", None)
    actual = independent_v1.canonical_sha256(unsigned)
    if recorded != actual or profile.get("profile_id") != PROFILE_ID:
        raise V2IndependentError("V2 profile integrity mismatch")
    if profile.get("inherits_v1", {}).get("profile_sha256") != V1_PROFILE_SHA:
        raise V2IndependentError("V1 binding changed")
    if profile.get("data_boundary", {}).get("consumed_v1_holdout_2026h1_access_allowed") is not False:
        raise V2IndependentError("2026H1 reuse allowed")
    return profile, actual


def observe(occurrences: list[dict]) -> dict:
    rows = []
    for occurrence in occurrences:
        sting = occurrence["second_sting"]
        bar = sting["bar"]
        touch = Decimal(str(sting["touch_price"]))
        low = Decimal(str(bar["low"]))
        high = Decimal(str(bar["high"]))
        observed = low <= touch <= high
        rows.append(
            {
                "occurrence_id": occurrence["occurrence_id"],
                "second_sting_ts_utc": bar["ts_start_utc"],
                "touch_price": str(touch),
                "bar_low": str(low),
                "bar_high": str(high),
                "status": "EXECUTABLE_ENTRY" if observed else "NO_EXECUTABLE_ENTRY",
                "target_stop_evaluation_authorized": observed,
                "fallback_fill_used": False,
            }
        )
    rows.sort(key=lambda row: row["occurrence_id"])
    return {
        "rows": rows,
        "rows_sha256": independent_v1.canonical_sha256(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "executable_ids": [row["occurrence_id"] for row in rows if row["status"] == "EXECUTABLE_ENTRY"],
    }


def build(
    *,
    v2_profile_path: Path,
    v1_profile_path: Path,
    fvg_path: Path,
    context_path: Path,
    artifact_dirs: list[Path],
) -> dict:
    profile, profile_sha = load_v2_profile(v2_profile_path)
    v1_profile, _ = independent_v1.verified_profile(v1_profile_path)
    fvg_sha = profile["inherited_owner_conventions"]["fvg"]["sha256"]
    context_sha = profile["inherited_owner_conventions"]["context"]["sha256"]
    independent_v1.verified_json_contract(fvg_path, expected_id=independent_v1.FVG_ID, expected_sha=fvg_sha)
    independent_v1.verified_json_contract(context_path, expected_id=independent_v1.CONTEXT_ID, expected_sha=context_sha)
    rows15, rows60, rows240, refs = independent_v1.load_artifacts(v1_profile, artifact_dirs)
    formations = independent_v1.detect_fvgs(rows240)
    sessions = independent_v1.complete_sessions(rows15)
    fvg_state = independent_v1.select_fvgs(rows15, formations, sessions, fvg_sha)
    qualified = independent_v1.qualify_occurrences(
        rows15=rows15,
        rows60=rows60,
        rows240=rows240,
        data_refs=refs,
        fvg_state=fvg_state,
        context_sha=context_sha,
        fvg_sha=fvg_sha,
    )
    observability = observe(qualified["occurrences"])
    report = {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "profile_sha256": profile_sha,
        "path_id": "INDEPENDENT_V2_STANDARD_LIBRARY_PATH",
        "reconstruction_status": "PASS",
        "semantic_closure_claimed": False,
        "fully_first_party_reconstructed": False,
        "semantic_occurrence_set_sha256": qualified["occurrence_set_sha256"],
        "qualification_rows_sha256": qualified["qualification_rows_sha256"],
        "qualification_status_counts": qualified["status_counts"],
        "qualified_occurrence_ids": [row["occurrence_id"] for row in qualified["occurrences"]],
        "observability_rows_sha256": observability["rows_sha256"],
        "observability_status_counts": observability["status_counts"],
        "executable_occurrence_ids": observability["executable_ids"],
        "holdout_2026h1_accessed": False,
        "future_validation_data_accessed": False,
        "performance_comparison_performed": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    report["reconstruction_sha256"] = independent_v1.canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-profile", required=True)
    parser.add_argument("--v1-profile", required=True)
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            v2_profile_path=Path(args.v2_profile),
            v1_profile_path=Path(args.v1_profile),
            context_path=Path(args.context_convention),
            fvg_path=Path(args.fvg_convention),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"V2 independent reconstruction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"path_id": result["path_id"], "sha256": result["reconstruction_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
