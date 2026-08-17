#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_OCCURRENCE_SET_SHA = "af363ac2bc08aaa3605a99b6fef688d284fc9df576d371a83e948271df5ba331"


class ObservabilityError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def dec(value: object, label: str) -> Decimal:
    try:
        out = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ObservabilityError(f"invalid decimal: {label}") from exc
    if not out.is_finite():
        raise ObservabilityError(f"non-finite decimal: {label}")
    return out


def build(source: dict) -> dict:
    if source.get("occurrence_set_sha256") != EXPECTED_OCCURRENCE_SET_SHA:
        raise ObservabilityError("source occurrence-set SHA mismatch")
    if source.get("holdout_accessed") is not False:
        raise ObservabilityError("development source must not access holdout")
    if source.get("outcome_fields_present") is not False:
        raise ObservabilityError("development source contains outcome fields")
    if source.get("performance_comparison_performed") is not False:
        raise ObservabilityError("performance comparison is prohibited")
    occurrences = source.get("occurrences")
    if not isinstance(occurrences, list) or not occurrences:
        raise ObservabilityError("non-empty occurrence set required")

    rows = []
    for occurrence in occurrences:
        oid = str(occurrence.get("occurrence_id", ""))
        sting = occurrence.get("second_sting", {})
        bar = sting.get("bar", {})
        touch = dec(sting.get("touch_price"), f"{oid}.touch_price")
        low = dec(bar.get("low"), f"{oid}.low")
        high = dec(bar.get("high"), f"{oid}.high")
        if low > high:
            raise ObservabilityError(f"{oid}: invalid second-sting range")
        observed = low <= touch <= high
        rows.append(
            {
                "occurrence_id": oid,
                "second_sting_ts_utc": bar.get("ts_start_utc"),
                "touch_price": str(touch),
                "bar_low": str(low),
                "bar_high": str(high),
                "status": "EXECUTABLE_ENTRY" if observed else "NO_EXECUTABLE_ENTRY",
                "target_stop_evaluation_authorized": observed,
                "fallback_fill_used": False,
            }
        )
    rows.sort(key=lambda row: row["occurrence_id"])
    counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    report = {
        "schema_version": 1,
        "status": "V2_DEVELOPMENTAL_OBSERVABILITY_COMPLETE",
        "invariant_id": "V2_SECOND_STING_TOUCH_OBSERVABILITY_V1",
        "source_occurrence_set_sha256": EXPECTED_OCCURRENCE_SET_SHA,
        "occurrence_count": len(rows),
        "status_counts": counts,
        "executable_occurrence_ids": [row["occurrence_id"] for row in rows if row["status"] == "EXECUTABLE_ENTRY"],
        "observability_rows": rows,
        "observability_rows_sha256": canonical_sha256(rows),
        "performance_comparison_performed": False,
        "holdout_accessed": False,
        "semantic_rules_changed": False,
        "execution_fill_rule_changed": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        source = json.loads(Path(args.source).read_text(encoding="utf-8"))
        report = build(source)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ObservabilityError) as exc:
        print(f"V2 observability check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "status_counts": report["status_counts"], "sha256": report["report_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
