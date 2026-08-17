#!/usr/bin/env python3
"""Primary reconstruction path for the frozen owner-operational SPEC profile.

This path intentionally exercises the merged production builders/replay code. It
is compared against a separately implemented standard-library reconstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from build_owner_operational_context_occurrences import build as build_occurrences
from build_owner_operational_fvg_anchors import build as build_fvg, canonical_sha256
from run_owner_operational_calibration import build as run_calibration


class PrimaryReconstructionError(RuntimeError):
    pass


def load_profile(path: Path) -> tuple[dict, str]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(profile.get("profile_sha256", ""))
    unsigned = dict(profile)
    unsigned.pop("profile_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual:
        raise PrimaryReconstructionError("frozen profile SHA mismatch")
    if profile.get("profile_id") != "ARJO_DERIVED_OWNER_OPERATIONAL_V1":
        raise PrimaryReconstructionError("unexpected frozen profile id")
    if profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise PrimaryReconstructionError("owner operational profile must not claim semantic closure")
    return profile, actual


def build(
    *,
    profile_path: Path,
    fvg_convention_path: Path,
    context_convention_path: Path,
    replay_spec_path: Path,
    artifact_dirs: list[Path],
) -> dict:
    profile, profile_sha = load_profile(profile_path)
    fvg = build_fvg(fvg_convention_path, artifact_dirs)
    occurrences = build_occurrences(
        context_convention_path=context_convention_path,
        fvg_convention_path=fvg_convention_path,
        artifact_dirs=artifact_dirs,
    )
    calibration = run_calibration(
        replay_spec_path=replay_spec_path,
        context_convention_path=context_convention_path,
        fvg_convention_path=fvg_convention_path,
        artifact_dirs=artifact_dirs,
    )

    no_active = [
        row["session_date_ny"]
        for row in fvg["sessions"]
        if row.get("selected_fvg") is None
    ]
    occurrence_ids = [row["occurrence_id"] for row in occurrences["occurrences"]]
    replay_events = sorted({str(row["event_ts"]) for row in calibration["replay_results"]})

    report = {
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "path_id": "PRIMARY_PRODUCTION_PATH",
        "reconstruction_status": "PASS",
        "semantic_closure_claimed": False,
        "owner_operational_conventions_present": True,
        "fvg_convention_sha256": fvg["convention_sha256"],
        "context_convention_sha256": occurrences["context_convention_sha256"],
        "detected_fvg_formation_count": fvg["detected_formation_count"],
        "session_count": fvg["session_count"],
        "selected_fvg_session_count": fvg["selected_session_count"],
        "no_active_fvg_session_count": fvg["no_active_fvg_session_count"],
        "no_active_fvg_sessions": no_active,
        "fvg_session_anchors_sha256": fvg["session_anchors_sha256"],
        "status_counts": occurrences["status_counts"],
        "qualified_occurrence_ids": occurrence_ids,
        "qualification_rows_sha256": occurrences["qualification_rows_sha256"],
        "occurrence_set_sha256": occurrences["occurrence_set_sha256"],
        "variant_result_count": calibration["variant_result_count"],
        "replay_status_counts": calibration["status_counts"],
        "replay_event_timestamps": replay_events,
        "replay_results_sha256": calibration["replay_results_sha256"],
        "calibrated_execution": {
            "second_sting_fill_event": calibration["selection"]["second_sting_fill_event"],
            "stop_buffer_ticks": calibration["selection"]["stop_buffer_ticks"],
            "performance_status_used_for_selection": calibration["selection"]["performance_status_used_for_selection"],
        },
        "holdout_accessed": False,
    }
    report["reconstruction_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--replay-spec", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            profile_path=Path(args.profile),
            fvg_convention_path=Path(args.fvg_convention),
            context_convention_path=Path(args.context_convention),
            replay_spec_path=Path(args.replay_spec),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"primary SPEC reconstruction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"path_id": result["path_id"], "status": result["reconstruction_status"], "sha256": result["reconstruction_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
