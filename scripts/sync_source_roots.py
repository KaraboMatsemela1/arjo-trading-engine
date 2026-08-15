#!/usr/bin/env python3
"""Synchronize research/source_roots.json into the canonical source registry."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE_FIELDS = [
    "SOURCE_ID",
    "SOURCE_TYPE",
    "TITLE",
    "URL",
    "PUBLICATION_DATE",
    "AUTHOR",
    "CHANNEL_ID",
    "FIRST_PARTY_STATUS",
    "RETRIEVAL_DATE",
    "RAW_ARTIFACT_SHA256",
    "TRANSCRIPT_AVAILABLE",
    "FRAME_EXTRACTION_AVAILABLE",
    "NOTES",
]


def source_type(platform: str) -> str:
    if platform == "website":
        return "WEBSITE_ROOT"
    if platform == "link_hub":
        return "LINK_HUB"
    return "PLATFORM_ROOT"


def title_for(root: dict) -> str:
    platform = root["platform"].replace("_", " ").title()
    return f"Arjo {platform} discovery root"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", default="research/source_roots.json")
    parser.add_argument("--registry", default="research/source_registry.csv")
    args = parser.parse_args()

    roots = json.loads(Path(args.roots).read_text(encoding="utf-8"))["roots"]
    registry_path = Path(args.registry)
    rows: list[dict[str, str]] = []
    if registry_path.exists():
        with registry_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

    by_id = {row.get("SOURCE_ID", ""): row for row in rows if row.get("SOURCE_ID")}
    retrieval_date = datetime.now(timezone.utc).date().isoformat()

    for root in roots:
        source_id = root["source_id"]
        row = by_id.get(source_id, {})
        row.update(
            {
                "SOURCE_ID": source_id,
                "SOURCE_TYPE": source_type(root["platform"]),
                "TITLE": row.get("TITLE") or title_for(root),
                "URL": root["url"],
                "PUBLICATION_DATE": row.get("PUBLICATION_DATE", ""),
                "AUTHOR": row.get("AUTHOR") or "Arjo",
                "CHANNEL_ID": row.get("CHANNEL_ID") or root["platform"],
                "FIRST_PARTY_STATUS": root["status"],
                "RETRIEVAL_DATE": retrieval_date,
                "RAW_ARTIFACT_SHA256": row.get("RAW_ARTIFACT_SHA256", ""),
                "TRANSCRIPT_AVAILABLE": row.get("TRANSCRIPT_AVAILABLE") or "UNKNOWN",
                "FRAME_EXTRACTION_AVAILABLE": row.get("FRAME_EXTRACTION_AVAILABLE") or "UNKNOWN",
                "NOTES": f"DISCOVERY_ROOT_ONLY; {root['basis']}; zero semantic closure until item-level evidence is acquired",
            }
        )
        by_id[source_id] = row

    merged = sorted(by_id.values(), key=lambda row: (row.get("SOURCE_TYPE", ""), row.get("URL", "")))
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)

    print(json.dumps({"roots_synced": len(roots), "registry_rows": len(merged)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
