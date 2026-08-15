#!/usr/bin/env python3
"""Replayable, evidence-neutral corpus acquisition orchestrator."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from acquisition_http import acquire_http
from acquisition_manifest import base_record, write_manifest
from acquisition_youtube import acquire_youtube
from acquisition_states import ACQUISITION_STATES

YOUTUBE_TYPES = {"YOUTUBE_VIDEO", "YOUTUBE_SHORT", "YOUTUBE_STREAM", "YOUTUBE_PLAYLIST"}
HTTP_TYPES = {"TELEGRAM_POST", "WEBSITE_PAGE", "WEBSITE_EDUCATIONAL_HUB", "WEBSITE_NEWSLETTER_HUB"}
LOCATOR_TYPES = {"PLATFORM_ROOT", "LINK_HUB", "FIRST_PARTY_LINKED_RESOURCE"}


def read_sources(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row.get("SOURCE_ID") and row.get("URL")]


def select_sources(sources: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    selected = sources
    if args.source_id:
        wanted = set(args.source_id)
        selected = [row for row in selected if row["SOURCE_ID"] in wanted]
    if args.source_type:
        wanted = set(args.source_type)
        selected = [row for row in selected if row.get("SOURCE_TYPE") in wanted]
    if not args.include_roots:
        selected = [row for row in selected if row.get("SOURCE_TYPE") not in LOCATOR_TYPES]
    return selected[: args.limit] if args.limit is not None else selected


def locator_record(source: dict[str, str]) -> dict:
    record = base_record(source, "locator-only")
    record.update(
        status="SOURCE_CONTACTED_NO_PAYLOAD",
        first_party_contacted=False,
        closure_credit="ZERO_LOCATOR_ONLY",
        notes="Locator/root only; direct item-level acquisition required before semantic closure",
    )
    return record


def acquire(source: dict[str, str], cache_root: Path, timeout: int, fixture_dir: Path | None) -> dict:
    source_type = source.get("SOURCE_TYPE", "")
    if source_type in YOUTUBE_TYPES:
        return acquire_youtube(source, cache_root, timeout, fixture_dir)
    if source_type in HTTP_TYPES:
        return acquire_http(source, cache_root, timeout)
    return locator_record(source)


def print_plan(selected: list[dict[str, str]]) -> int:
    counts: dict[str, int] = {}
    for row in selected:
        source_type = row.get("SOURCE_TYPE", "")
        counts[source_type] = counts.get(source_type, 0) + 1
    print(json.dumps({"selected": len(selected), "by_type": counts}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--manifest", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--cache-root", default=".research-cache/artifacts")
    parser.add_argument("--source-id", action="append")
    parser.add_argument("--source-type", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--fixture-dir")
    parser.add_argument("--include-roots", action="store_true")
    parser.add_argument("--replace-manifest", action="store_true")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()

    selected = select_sources(read_sources(Path(args.registry)), args)
    if args.plan:
        return print_plan(selected)
    if not selected:
        print("No sources selected", file=sys.stderr)
        return 2

    cache_root = Path(args.cache_root)
    fixture_dir = Path(args.fixture_dir) if args.fixture_dir else None
    records = [acquire(row, cache_root, args.timeout, fixture_dir) for row in selected]
    write_manifest(Path(args.manifest), records, merge=not args.replace_manifest)

    statuses: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        statuses[status] = statuses.get(status, 0) + 1
    print(json.dumps({"attempted": len(records), "statuses": statuses}, sort_keys=True))
    return 0 if all(record["status"] in ACQUISITION_STATES for record in records) else 3


if __name__ == "__main__":
    raise SystemExit(main())
