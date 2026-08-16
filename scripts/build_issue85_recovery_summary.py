#!/usr/bin/env python3
"""Build a compact, anti-bias-safe summary of the bounded Issue #85 recovery run."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evidence_antibias import contains_pre_spec_outcome


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def checked_excerpt(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    if len(text.split()) > 20:
        raise ValueError("Issue 85 summary excerpt exceeds 20-word copyright bound")
    if contains_pre_spec_outcome(text):
        raise ValueError(f"Issue 85 summary rejected outcome-contaminated excerpt: {text!r}")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--windows", required=True)
    parser.add_argument("--telegram", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = read_jsonl(Path(args.manifest))
    windows = read_json(Path(args.windows))
    telegram = read_json(Path(args.telegram))

    statuses = Counter(str(row.get("status", "UNKNOWN")) for row in manifest)
    direct_sources: list[dict] = []
    for row in windows.get("sources", []):
        safe_windows = []
        for item in row.get("windows", []):
            excerpt = checked_excerpt(str(item.get("excerpt", "")))
            if excerpt:
                safe_windows.append({"matched_term": str(item.get("matched_term", "")), "excerpt": excerpt})
        direct_sources.append(
            {
                "source_id": str(row.get("source_id", "")),
                "status": str(row.get("status", "")),
                "closure_credit": str(row.get("closure_credit", "")),
                "sha256": str(row.get("sha256", "")),
                "windows": safe_windows,
            }
        )

    telegram_sources: list[dict] = []
    for row in telegram.get("messages", []):
        excerpts = []
        for item in row.get("excerpts", []):
            excerpt = checked_excerpt(str(item.get("excerpt", "")))
            if excerpt:
                excerpts.append(
                    {
                        "kind": str(item.get("kind", "")),
                        "label": str(item.get("label", "")),
                        "matched": str(item.get("matched", "")),
                        "excerpt": excerpt,
                    }
                )
        telegram_sources.append(
            {
                "source_id": str(row.get("source_id", "")),
                "date": str(row.get("date", "")),
                "concepts": list(row.get("concepts", [])),
                "field_cues": list(row.get("field_cues", [])),
                "archive_page_sha256": str(row.get("archive_page_sha256", "")),
                "excerpts": excerpts,
            }
        )

    summary = {
        "schema_version": 1,
        "issue": 85,
        "predicate_id": "ORDER_FLOW_TARGET_BIAS",
        "attempted_source_count": len(manifest),
        "status_counts": dict(sorted(statuses.items())),
        "direct_payload_window_count": sum(len(row["windows"]) for row in direct_sources),
        "telegram_recovered_source_count": len(telegram_sources),
        "telegram_missing_source_ids": list(telegram.get("missing_source_ids", [])),
        "telegram_archive_page_count": int(telegram.get("pages_fetched", 0)),
        "telegram_archive_failure_count": len(telegram.get("failures", [])),
        "archive_pages_sha256_bound": bool(telegram.get("archive_pages_sha256_bound", False)),
        "shared_antibias_guard": True,
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
        "direct_sources": direct_sources,
        "telegram_sources": telegram_sources,
    }
    Path(args.output).write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
