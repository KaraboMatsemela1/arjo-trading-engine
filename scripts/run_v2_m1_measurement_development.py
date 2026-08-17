#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from v2_m1_execution_measurement import canonical_sha256, measure_occurrence


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--occurrences", required=True)
    p.add_argument("--m1", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    source = json.loads(Path(args.occurrences).read_text(encoding="utf-8"))
    if source.get("holdout_accessed") is not False or source.get("performance_comparison_performed") is not False:
        raise RuntimeError("development occurrence source boundary changed")
    occurrences = [row for row in source.get("occurrences", []) if row.get("occurrence_id") == "OWNER-CAL-2024-04-26"]
    if len(occurrences) != 1:
        raise RuntimeError("expected frozen development occurrence not found exactly once")
    source_occ = occurrences[0]

    second = source_occ["second_sting"]
    occurrence = {
        "occurrence_id": source_occ["occurrence_id"],
        "second_sting_ts_utc": second["bar"]["ts_start_utc"],
        "touch_price": second["touch_price"],
        "order_flow_leg_low": source_occ["order_flow_leg_low"],
        "target_price": source_occ["target"]["price"],
    }
    touch = float(occurrence["touch_price"])
    low = float(second["bar"]["low"])
    high = float(second["bar"]["high"])
    observability = "EXECUTABLE_ENTRY" if low <= touch <= high else "NO_EXECUTABLE_ENTRY"

    rows: list[dict] = []
    with Path(args.m1).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append({"ts_start_utc": row["ts_start_utc"], "low": row["low"], "high": row["high"]})

    measurement = measure_occurrence(
        occurrence=occurrence,
        observability_status=observability,
        m1_rows=rows,
        end_exclusive=datetime(2025, 1, 1, tzinfo=UTC),
    )
    report = {
        "schema_version": 1,
        "status": "DEVELOPMENTAL_M1_MEASUREMENT_COMPLETE",
        "source_occurrence_set_sha256": source["occurrence_set_sha256"],
        "occurrence_id": occurrence["occurrence_id"],
        "measurement": measurement,
        "holdout_2026h1_accessed": False,
        "future_validation_data_accessed": False,
        "performance_comparison_performed": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report_sha256": report["report_sha256"], "measurement": measurement}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
