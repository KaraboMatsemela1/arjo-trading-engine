#!/usr/bin/env python3
"""Execute only the preregistered calibration dimensions on frozen occurrences."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

from build_owner_operational_context_occurrences import build as build_occurrences
from build_owner_operational_fvg_anchors import canonical_sha256, load_jsonl, parse_utc
from nq_calibration_replay import ReplayBar, SeedOccurrence, evaluate_occurrence, load_replay_spec

EXPECTED_OCCURRENCE_SET_SHA = "af363ac2bc08aaa3605a99b6fef688d284fc9df576d371a83e948271df5ba331"
EXPECTED_PREREG_SHA = "dbd2b9e943d5e60d35a4de5e9e697ec5eacdf118f285659a1414eb557e8bf557"
SELECTED_FILL = "SECOND_STING_TOUCH"
SELECTED_BUFFER = 0


class CalibrationExecutionError(RuntimeError):
    pass


def build(*, replay_spec_path: Path, context_convention_path: Path, fvg_convention_path: Path, artifact_dirs: list[Path]) -> dict:
    load_replay_spec(replay_spec_path)
    if hashlib.sha256(replay_spec_path.read_bytes()).hexdigest() != EXPECTED_PREREG_SHA:
        raise CalibrationExecutionError("replay spec preregistration SHA changed")

    occurrence_state = build_occurrences(
        context_convention_path=context_convention_path,
        fvg_convention_path=fvg_convention_path,
        artifact_dirs=artifact_dirs,
    )
    if occurrence_state.get("occurrence_set_sha256") != EXPECTED_OCCURRENCE_SET_SHA:
        raise CalibrationExecutionError("frozen occurrence set SHA changed")
    if occurrence_state.get("qualified_occurrence_count") != 1:
        raise CalibrationExecutionError("expected exactly one frozen occurrence")

    bars: list[dict] = []
    for directory in artifact_dirs:
        bars.extend(load_jsonl(directory / "NAS100_USD.15m.jsonl", 15))
    bars.sort(key=lambda row: row["ts_start_utc"])

    all_results: list[dict] = []
    for row in occurrence_state["occurrences"]:
        second_start = parse_utc(row["second_sting"]["bar"]["ts_start_utc"])
        touch_ts = second_start
        close_ts = second_start + timedelta(minutes=15)
        replay_bars = tuple(
            ReplayBar(parse_utc(bar["ts_start_utc"]), float(bar["high"]), float(bar["low"]))
            for bar in bars
            if parse_utc(bar["ts_start_utc"]) >= touch_ts
        )
        seed = SeedOccurrence(
            occurrence_id=row["occurrence_id"],
            tick_size=float(row["provider_identity"]["provider_price_quantum"]),
            second_sting_touch_ts=touch_ts,
            second_sting_touch_price=float(row["second_sting"]["touch_price"]),
            second_sting_close_ts=close_ts,
            second_sting_close_price=float(row["second_sting"]["close_price"]),
            order_flow_leg_low=float(row["order_flow_leg_low"]),
            target_price=float(row["target"]["price"]),
            bars_after_activation=replay_bars,
        )
        results = evaluate_occurrence(seed)
        if len(results) != 6:
            raise CalibrationExecutionError("expected six preregistered variant results")
        all_results.extend(results)

    all_results.sort(key=lambda result: (result["occurrence_id"], result["fill_event"], result["stop_buffer_ticks"]))
    status_counts = dict(sorted(Counter(result["status"] for result in all_results).items()))
    selected = [
        result for result in all_results
        if result["fill_event"] == SELECTED_FILL and result["stop_buffer_ticks"] == SELECTED_BUFFER
    ]
    if len(selected) != 1:
        raise CalibrationExecutionError("selected structural convention missing")

    result = {
        "schema_version": 1,
        "status": "CALIBRATION_COMPLETE",
        "protocol": "FIRST_PARTY_PRESCRIBED_CALIBRATION_V1",
        "predicate_id": "AOO_FVA_2CR_FVG_LONG_CONTEXT",
        "occurrence_set_sha256": EXPECTED_OCCURRENCE_SET_SHA,
        "preregistration_sha256": EXPECTED_PREREG_SHA,
        "calibration_data_accessed": True,
        "holdout_accessed": False,
        "semantic_candidate_comparison_performed": False,
        "performance_leaderboard_performed": False,
        "owner_operational_conventions_disclosed": True,
        "variant_result_count": len(all_results),
        "status_counts": status_counts,
        "replay_results_sha256": canonical_sha256(all_results),
        "replay_results": all_results,
        "selection": {
            "second_sting_fill_event": SELECTED_FILL,
            "stop_buffer_ticks": SELECTED_BUFFER,
            "selected_variant_status": selected[0]["status"],
            "performance_status_used_for_selection": False,
            "basis": {
                "second_sting_fill_event": "NARROWEST_SEMANTIC_EXTENSION: touch is the already-required second-sting interaction and adds no 15m close-confirmation condition.",
                "stop_buffer_ticks": "NARROWEST_SEMANTIC_EXTENSION: zero buffer preserves the exact operational Order Flow leg-low anchor and adds no provider-price quantum offset."
            },
            "tie_handling": "Replay outcome status does not rank candidates. Structural narrowness applies the preregistered acceptance rule; contradictory observability would fail closed."
        },
        "outcome_window": "Frozen calibration 15m bars from each entry event forward through the calibration dataset only; evaluator stops at first stop/target event and never reads protected holdout."
    }
    unsigned = dict(result)
    result["calibration_result_sha256"] = canonical_sha256(unsigned)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-spec", required=True)
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            replay_spec_path=Path(args.replay_spec),
            context_convention_path=Path(args.context_convention),
            fvg_convention_path=Path(args.fvg_convention),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"calibration execution failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": result["status"],
        "status_counts": result["status_counts"],
        "replay_results_sha256": result["replay_results_sha256"],
        "calibration_result_sha256": result["calibration_result_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
