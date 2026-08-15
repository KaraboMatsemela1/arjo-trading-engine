#!/usr/bin/env python3
"""Merge sharded acquisition manifests without silently resolving conflicts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VOLATILE_FIELDS = {"attempted_at"}


def semantic_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in VOLATILE_FIELDS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", default="research/acquisition_manifest.jsonl")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    files = sorted(input_dir.rglob("*.jsonl"))
    if not files:
        print("No shard manifests found", file=sys.stderr)
        return 2

    records: dict[str, dict[str, Any]] = {}
    origins: dict[str, str] = {}
    errors: list[str] = []
    input_records = 0

    for path in files:
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            input_records += 1
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_no}: invalid JSON: {exc}")
                continue
            source_id = str(record.get("source_id", ""))
            if not source_id:
                errors.append(f"{path}:{line_no}: missing source_id")
                continue
            if source_id in records:
                if semantic_record(records[source_id]) != semantic_record(record):
                    errors.append(
                        f"conflicting terminal records for {source_id}: {origins[source_id]} vs {path}:{line_no}"
                    )
                continue
            records[source_id] = record
            origins[source_id] = f"{path}:{line_no}"

    if errors:
        print("Acquisition manifest merge failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(records[key], ensure_ascii=False, sort_keys=True, separators=(",", ":")) for key in sorted(records)]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(json.dumps({"input_files": len(files), "input_records": input_records, "unique_sources": len(records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
