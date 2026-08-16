#!/usr/bin/env python3
"""Reconcile durable evidence coverage with the canonical additive registry union."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_registry_union import DEFAULT_EVIDENCE_GLOB, load_evidence_union, matching_paths


def record_count(path: Path) -> int:
    return sum(1 for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", default="research/evidence_coverage.json")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_GLOB)
    parser.add_argument("--base", default="research/evidence_registry.jsonl")
    args = parser.parse_args()

    coverage_path = Path(args.coverage)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if coverage.get("semantic_synthesis_performed") is not False:
        raise ValueError("coverage reconciliation requires semantic_synthesis_performed=false")

    union = load_evidence_union(args.evidence)
    shard_paths = matching_paths(args.evidence)
    base_path = Path(args.base)
    base_count = record_count(base_path) if base_path.exists() else 0

    coverage["base_evidence_record_count"] = base_count
    coverage["evidence_record_count"] = len(union)
    coverage["evidence_shard_count"] = len(shard_paths)
    coverage["recovery_evidence_record_count"] = len(union) - base_count
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "base_evidence_records": base_count,
                "evidence_records": len(union),
                "evidence_shards": len(shard_paths),
                "recovery_evidence_records": len(union) - base_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
