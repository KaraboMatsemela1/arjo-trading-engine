"""Deterministically load the canonical union of evidence registry shards."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_EVIDENCE_GLOB = "research/evidence_registry*.jsonl"


def matching_paths(pattern: str) -> list[Path]:
    if any(char in pattern for char in "*?["):
        paths = sorted(Path().glob(pattern))
    else:
        path = Path(pattern)
        paths = [path] if path.exists() else []
    if not paths:
        raise ValueError(f"no evidence registry files match {pattern}")
    return paths


def load_evidence_union(pattern: str = DEFAULT_EVIDENCE_GLOB) -> list[dict]:
    records: list[dict] = []
    seen: dict[str, Path] = {}
    for path in matching_paths(pattern):
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            evidence_id = str(row.get("EVIDENCE_ID", ""))
            if not evidence_id:
                raise ValueError(f"{path}: evidence record missing EVIDENCE_ID")
            if evidence_id in seen:
                raise ValueError(
                    f"duplicate EVIDENCE_ID {evidence_id} in {seen[evidence_id]} and {path}"
                )
            seen[evidence_id] = path
            records.append(row)
    return records
