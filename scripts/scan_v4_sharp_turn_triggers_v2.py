#!/usr/bin/env python3
"""Canonical V4 Sharp Turn trigger seal with strict candle-end chronology.

Uses the frozen V4 strategy semantics unchanged. The V2 revision corrects only
provider-aligned candle knowledge times / historical coverage boundaries.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import scan_v4_sharp_turn_triggers as v1
from v4_sharp_turn_candle_boundaries import END, GRANULARITIES, candle_end, zulu

BOUNDARY_REVISION = "V4_STRICT_CANDLE_COVERAGE_END_V2"
NONCANONICAL_SUPERSEDED_RUN_ID = 32139161882


def verify_v2_manifest(root: Path) -> dict:
    manifest = json.loads(
        v1.find_one(root, "NAS100_USD.v4-structure-manifest.json").read_text()
    )
    if manifest.get("boundary_revision") != BOUNDARY_REVISION:
        raise v1.V4TriggerSealError("strict candle-end boundary revision missing")
    if manifest.get("all_admitted_candles_close_lte_frozen_end") is not True:
        raise v1.V4TriggerSealError("candle-end boundary not proven")
    if manifest.get("raw_request_windows_exclude_first_cross_end_candle_start") is not True:
        raise v1.V4TriggerSealError("raw request boundary not proven")
    if manifest.get("supersedes_noncanonical_workflow_run_id") != NONCANONICAL_SUPERSEDED_RUN_ID:
        raise v1.V4TriggerSealError("noncanonical run disposition drift")
    if manifest.get("noncanonical_run_excluded_from_research_inference") is not True:
        raise v1.V4TriggerSealError("noncanonical run not excluded")
    for tf in GRANULARITIES:
        item = manifest["timeframes"][tf]
        if v1.parse_utc(item["last_complete_bar_end"]) > END:
            raise v1.V4TriggerSealError(f"{tf} structure crosses frozen end")
    return manifest


def build(artifact_dir: Path, protocol_path: Path) -> dict:
    # Correct the higher-timeframe knowledge clock used by V1's deterministic
    # scanner. In particular an OANDA M timestamp is an aligned monthly start;
    # its causal close is the next month-end 17:00 New York boundary, not the
    # first calendar day of the following month.
    v1.candle_close_time = candle_end
    manifest = verify_v2_manifest(artifact_dir)
    report = v1.build(artifact_dir, protocol_path)
    report["boundary_revision"] = BOUNDARY_REVISION
    report["all_structure_candles_close_lte_frozen_end"] = True
    report["supersedes_noncanonical_workflow_run_id"] = NONCANONICAL_SUPERSEDED_RUN_ID
    report["noncanonical_run_excluded_from_research_inference"] = True
    report["structure_manifest_sha256"] = manifest["manifest_sha256"]
    report["structure_retrieval_sha256"] = manifest["retrieval_sha256"]
    for trigger in report["sealed_triggers"]:
        known = v1.parse_utc(trigger["trigger_knowledge_time_utc"])
        if known > END:
            raise v1.V4TriggerSealError("trigger knowledge crosses frozen end")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    report["report_sha256"] = v1.canon(unsigned)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument(
        "--protocol",
        default="research/profitability/v4_sharp_turn_execution_protocol_v1.json",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = build(Path(args.artifact_dir), Path(args.protocol))
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"V4 strict-end trigger seal failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "classification": report["classification"],
                "boundary_revision": report["boundary_revision"],
                "triggers": report["trigger_count"],
                "long": report["long_triggers"],
                "short": report["short_triggers"],
                "distinct_knowledge_times": report["distinct_trigger_knowledge_times"],
                "sample_necessary_condition_met": report["sample_necessary_condition_met"],
                "trigger_set_sha256": report["trigger_set_sha256"],
                "economic_outcomes_accessed": False,
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
