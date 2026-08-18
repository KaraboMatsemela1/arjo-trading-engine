#!/usr/bin/env python3
"""Strict-end V4 Sharp Turn structure transport.

Supersedes the noncanonical first structure run that bounded requests by candle
start only. This wrapper keeps the frozen V4 provider semantics but ensures raw
requests stop before any aligned candle whose price coverage crosses 2024-01-01.
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
    unsafe_start_boundary,
    zulu,
)

BOUNDARY_REVISION = "V4_STRICT_CANDLE_COVERAGE_END_V2"
NONCANONICAL_SUPERSEDED_RUN_ID = 32139161882
_ORIGINAL_PARSE_PAGE = v1.parse_page


def windows(granularity: str) -> list[tuple[datetime, datetime]]:
    if granularity not in GRANULARITIES:
        raise v1.V4StructureError("unapproved granularity")
    limit = safe_request_end(granularity)
    if limit <= v1.START:
        raise v1.V4StructureError("invalid strict request end")
    step = timedelta(days=v1.WINDOW_DAYS[granularity])
    result: list[tuple[datetime, datetime]] = []
    cursor = v1.START
    while cursor < limit:
        nxt = min(cursor + step, limit)
        result.append((cursor, nxt))
        cursor = nxt
    return result


def parse_page(payload: bytes, granularity: str) -> list[dict]:
    rows = _ORIGINAL_PARSE_PAGE(payload, granularity)
    unsafe = unsafe_start_boundary(granularity)
    for row in rows:
        start = v1.parse_utc(row["ts_start_utc"])
        if start >= unsafe:
            raise v1.V4StructureError(
                f"provider returned unsafe {granularity} candle start {row['ts_start_utc']}"
            )
        if not candle_is_fully_in_window(start, granularity):
            raise v1.V4StructureError(
                f"provider returned candle crossing frozen end: {granularity} {row['ts_start_utc']}"
            )
    return rows


def acquire(protocol_path: Path, output_dir: Path, delay: float = 0.02) -> dict:
    # Patch only the transport window/parser used by the already-reviewed V1
    # MID-only client. Strategy semantics and protocol parameters are unchanged.
    v1.windows = windows
    v1.parse_page = parse_page
    manifest = v1.acquire(protocol_path, output_dir, delay)

    for tf in GRANULARITIES:
        item = manifest["timeframes"][tf]
        last_start = v1.parse_utc(item["last_complete_bar"])
        last_end = candle_end(last_start, tf)
        if last_end > END:
            raise v1.V4StructureError(f"canonical {tf} structure crosses frozen end")
        item["last_complete_bar_end"] = zulu(last_end)
        item["unsafe_start_boundary"] = zulu(unsafe_start_boundary(tf))
        item["safe_request_end"] = zulu(safe_request_end(tf))
        for chunk in item["chunks"]:
            if v1.parse_utc(chunk["end"]) > safe_request_end(tf):
                raise v1.V4StructureError(f"{tf} request exceeded strict safe end")

    manifest["boundary_revision"] = BOUNDARY_REVISION
    manifest["all_admitted_candles_close_lte_frozen_end"] = True
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
        print(f"V4 strict-end structure acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "boundary_revision": manifest["boundary_revision"],
                "rows": {k: v["rows"] for k, v in manifest["timeframes"].items()},
                "retrieval_sha256": manifest["retrieval_sha256"],
                "all_admitted_candles_close_lte_frozen_end": True,
                "m1_data_requested": False,
                "economic_outcomes_evaluated": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
