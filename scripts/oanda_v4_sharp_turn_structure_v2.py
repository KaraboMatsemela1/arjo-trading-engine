#!/usr/bin/env python3
"""Fully-contained V4 Sharp Turn structure transport V2.

Supersedes the noncanonical first run. Raw requests begin at the first aligned
candle fully inside the frozen historical window and stop before the first
aligned candle whose coverage would cross the frozen end.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import oanda_v4_sharp_turn_structure as v1
from v4_sharp_turn_candle_boundaries import (
    END,
    GRANULARITIES,
    candle_end,
    candle_is_fully_in_window,
    safe_request_end,
    safe_request_start,
    unsafe_end_start_boundary,
    zulu,
)

BOUNDARY_REVISION = "V4_STRICT_CANDLE_COVERAGE_END_V2"
NONCANONICAL_SUPERSEDED_RUN_ID = 32139161882
_ORIGINAL_PARSE_PAGE = v1.parse_page


def windows(granularity: str) -> list[tuple[datetime, datetime]]:
    if granularity not in GRANULARITIES:
        raise v1.V4StructureError("unapproved granularity")
    cursor = safe_request_start(granularity)
    limit = safe_request_end(granularity)
    if not v1.START <= cursor < limit <= v1.END:
        raise v1.V4StructureError("invalid fully-contained request window")
    step = timedelta(days=v1.WINDOW_DAYS[granularity])
    result: list[tuple[datetime, datetime]] = []
    while cursor < limit:
        nxt = min(cursor + step, limit)
        result.append((cursor, nxt))
        cursor = nxt
    return result


def parse_page(payload: bytes, granularity: str) -> list[dict]:
    rows = _ORIGINAL_PARSE_PAGE(payload, granularity)
    safe_start = safe_request_start(granularity)
    unsafe_end = unsafe_end_start_boundary(granularity)
    for row in rows:
        start = v1.parse_utc(row["ts_start_utc"])
        if start < safe_start:
            raise v1.V4StructureError(
                f"provider returned pre-window {granularity} candle start {row['ts_start_utc']}"
            )
        if start >= unsafe_end:
            raise v1.V4StructureError(
                f"provider returned cross-end {granularity} candle start {row['ts_start_utc']}"
            )
        if not candle_is_fully_in_window(start, granularity):
            raise v1.V4StructureError(
                f"provider returned non-contained candle: {granularity} {row['ts_start_utc']}"
            )
    return rows


def acquire(protocol_path: Path, output_dir: Path, delay: float = 0.02) -> dict:
    v1.windows = windows
    v1.parse_page = parse_page
    manifest = v1.acquire(protocol_path, output_dir, delay)

    for tf in GRANULARITIES:
        item = manifest["timeframes"][tf]
        first_start = v1.parse_utc(item["first_complete_bar"])
        last_start = v1.parse_utc(item["last_complete_bar"])
        last_end = candle_end(last_start, tf)
        if first_start < safe_request_start(tf):
            raise v1.V4StructureError(f"canonical {tf} structure crosses frozen start")
        if last_end > END:
            raise v1.V4StructureError(f"canonical {tf} structure crosses frozen end")
        item["first_safe_request_start"] = zulu(safe_request_start(tf))
        item["last_complete_bar_end"] = zulu(last_end)
        item["unsafe_end_start_boundary"] = zulu(unsafe_end_start_boundary(tf))
        item["safe_request_end"] = zulu(safe_request_end(tf))
        for chunk in item["chunks"]:
            if v1.parse_utc(chunk["start"]) < safe_request_start(tf):
                raise v1.V4StructureError(f"{tf} request preceded safe start")
            if v1.parse_utc(chunk["end"]) > safe_request_end(tf):
                raise v1.V4StructureError(f"{tf} request exceeded safe end")

    manifest["boundary_revision"] = BOUNDARY_REVISION
    manifest["all_admitted_candles_fully_contained_in_frozen_window"] = True
    manifest["all_admitted_candles_close_lte_frozen_end"] = True
    manifest["raw_request_windows_exclude_partial_start_and_end_candles"] = True
    manifest["raw_request_windows_exclude_first_cross_end_candle_start"] = True
    manifest["supersedes_noncanonical_workflow_run_id"] = NONCANONICAL_SUPERSEDED_RUN_ID
    manifest["noncanonical_run_excluded_from_research_inference"] = True
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = v1.canon(unsigned)
    (output_dir / "NAS100_USD.v4-structure-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        default="research/profitability/v4_sharp_turn_execution_protocol_v1.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--delay", type=float, default=0.02)
    args = parser.parse_args()
    try:
        manifest = acquire(Path(args.protocol), Path(args.output_dir), args.delay)
    except Exception as exc:
        print(f"V4 fully-contained structure acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "boundary_revision": manifest["boundary_revision"],
                "rows": {k: v["rows"] for k, v in manifest["timeframes"].items()},
                "retrieval_sha256": manifest["retrieval_sha256"],
                "all_admitted_candles_fully_contained_in_frozen_window": True,
                "m1_data_requested": False,
                "economic_outcomes_evaluated": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
