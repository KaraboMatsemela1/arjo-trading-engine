"""Deterministically load the canonical union of source registry shards."""

from __future__ import annotations

import csv
from pathlib import Path

DEFAULT_SOURCE_GLOB = "research/source_registry*.csv"


def matching_paths(pattern: str) -> list[Path]:
    if any(char in pattern for char in "*?["):
        paths = sorted(Path().glob(pattern))
    else:
        path = Path(pattern)
        paths = [path] if path.exists() else []
    if not paths:
        raise ValueError(f"no source registry files match {pattern}")
    return paths


def load_source_union(pattern: str = DEFAULT_SOURCE_GLOB) -> list[dict]:
    records: list[dict] = []
    seen: dict[str, Path] = {}
    expected_fields: list[str] | None = None
    for path in matching_paths(pattern):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            if expected_fields is None:
                expected_fields = fields
            elif fields != expected_fields:
                raise ValueError(f"{path}: source registry header differs from canonical header")
            for row in reader:
                source_id = str(row.get("SOURCE_ID", ""))
                if not source_id:
                    raise ValueError(f"{path}: source row missing SOURCE_ID")
                if source_id in seen:
                    raise ValueError(
                        f"duplicate SOURCE_ID {source_id} in {seen[source_id]} and {path}"
                    )
                seen[source_id] = path
                records.append(row)
    return records
