#!/usr/bin/env python3
"""Build a bounded source delta between canonical and freshly scanned registries."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def read_registry(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def source_platform(row: dict[str, str]) -> str:
    source_type = row.get("SOURCE_TYPE", "")
    if source_type.startswith("YOUTUBE_"):
        return "YOUTUBE"
    if source_type == "TELEGRAM_POST":
        return "TELEGRAM"
    if source_type.startswith("WEBSITE_") or source_type == "FIRST_PARTY_LINKED_RESOURCE":
        return "WEBSITE"
    return "OTHER"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--scanned", required=True)
    parser.add_argument("--discovery-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--youtube-rc", type=int, required=True)
    parser.add_argument("--telegram-rc", type=int, required=True)
    parser.add_argument("--website-rc", type=int, required=True)
    args = parser.parse_args()

    baseline = read_registry(Path(args.baseline))
    scanned = read_registry(Path(args.scanned))
    baseline_urls = {row.get("URL", "") for row in baseline if row.get("URL")}
    new_rows = [row for row in scanned if row.get("URL") and row["URL"] not in baseline_urls]
    new_rows.sort(key=lambda row: (source_platform(row), row.get("SOURCE_TYPE", ""), row.get("URL", "")))

    discovery = Path(args.discovery_dir)
    platform_reports = {
        "youtube": read_json(discovery / "new_sources.json"),
        "telegram": read_json(discovery / "telegram_discovery_report.json"),
        "website": read_json(discovery / "website_discovery_report.json"),
    }
    exit_codes = {
        "youtube": args.youtube_rc,
        "telegram": args.telegram_rc,
        "website": args.website_rc,
    }
    platform_new_counts = {platform: 0 for platform in ("YOUTUBE", "TELEGRAM", "WEBSITE", "OTHER")}
    for row in new_rows:
        platform_new_counts[source_platform(row)] += 1

    report = {
        "schema_version": 1,
        "issue": 101,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_registry_rows": len(baseline),
        "scanned_registry_rows": len(scanned),
        "new_source_count": len(new_rows),
        "new_source_counts_by_platform": platform_new_counts,
        "new_sources": new_rows,
        "surface_exit_codes": exit_codes,
        "surface_reports": platform_reports,
        "semantic_closure_performed": False,
        "search_or_metadata_semantic_credit": "ZERO",
        "requires_bounded_acquisition": bool(new_rows),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "baseline": len(baseline),
        "scanned": len(scanned),
        "new": len(new_rows),
        "by_platform": platform_new_counts,
        "exit_codes": exit_codes,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
