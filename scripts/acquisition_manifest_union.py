"""Deterministically load the canonical union of acquisition manifest shards."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_ACQUISITION_GLOB = "research/acquisition_manifest*.jsonl"


def matching_paths(pattern: str) -> list[Path]:
    if any(char in pattern for char in "*?["):
        paths = sorted(Path().glob(pattern))
    else:
        path = Path(pattern)
        paths = [path] if path.exists() else []
    if not paths:
        raise ValueError(f"no acquisition manifest files match {pattern}")
    return paths


def load_acquisition_union(pattern: str = DEFAULT_ACQUISITION_GLOB) -> list[dict]:
    records: list[dict] = []
    seen: dict[str, Path] = {}
    for path in matching_paths(pattern):
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            source_id = str(row.get("source_id", ""))
            if not source_id:
                raise ValueError(f"{path}:{line_no}: acquisition record missing source_id")
            if source_id in seen:
                raise ValueError(
                    f"duplicate acquisition source_id {source_id} in {seen[source_id]} and {path}"
                )
            seen[source_id] = path
            records.append(row)
    return records
