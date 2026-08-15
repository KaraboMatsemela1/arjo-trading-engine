#!/usr/bin/env python3
"""Enumerate the public Arjoio Trading Telegram archive without semantic analysis.

The script discovers public message locators only. It does not treat message text
as evidence and does not perform strategy interpretation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHANNEL = "ArjoioTrading"
ARCHIVE_URL = f"https://t.me/s/{CHANNEL}"
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
MESSAGE_RE = re.compile(
    rf'data-post="{re.escape(CHANNEL)}/(\d+)"(?P<body>.*?)(?=data-post="{re.escape(CHANNEL)}/|$)',
    re.IGNORECASE | re.DOTALL,
)
TIME_RE = re.compile(r'<time[^>]+datetime="([^"]+)"', re.IGNORECASE)
BEFORE_RE = re.compile(r'href="[^"]*\?before=(\d+)"', re.IGNORECASE)


def fetch(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "arjo-trading-engine-source-discovery/1.0 (+research; public metadata only)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def iso_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def parse_messages(html: str, retrieval_date: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[int] = set()
    for match in MESSAGE_RE.finditer(html):
        message_id = int(match.group(1))
        if message_id in seen:
            continue
        seen.add(message_id)
        body = match.group("body")
        time_match = TIME_RE.search(body)
        published = iso_date(time_match.group(1) if time_match else None)
        rows.append(
            {
                "SOURCE_ID": f"TG_{CHANNEL.upper()}_{message_id}",
                "SOURCE_TYPE": "TELEGRAM_POST",
                "TITLE": f"Arjoio Trading Telegram post {message_id}",
                "URL": f"https://t.me/{CHANNEL}/{message_id}",
                "PUBLICATION_DATE": published,
                "AUTHOR": "Arjoio Trading",
                "CHANNEL_ID": CHANNEL,
                "FIRST_PARTY_STATUS": "CONFIRMED_FIRST_PARTY",
                "RETRIEVAL_DATE": retrieval_date,
                "RAW_ARTIFACT_SHA256": "",
                "TRANSCRIPT_AVAILABLE": "NOT_APPLICABLE",
                "FRAME_EXTRACTION_AVAILABLE": "UNKNOWN",
                "NOTES": "Discovered from the public first-party Telegram archive; relevance unassessed; message content not used for semantic closure during discovery",
            }
        )
    return rows


def next_before(html: str, current_before: int | None, message_ids: list[int]) -> int | None:
    candidates = {int(value) for value in BEFORE_RE.findall(html)}
    if message_ids:
        floor = min(message_ids)
        candidates = {value for value in candidates if value <= floor}
    if current_before is not None:
        candidates = {value for value in candidates if value < current_before}
    return max(candidates) if candidates else None


def read_registry(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_registry(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_registry(path: Path, discovered: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = read_registry(path)
    by_url = {row.get("URL", ""): row for row in existing if row.get("URL")}
    new_rows = [row for row in discovered if row["URL"] not in by_url]
    for row in discovered:
        by_url.setdefault(row["URL"], row)
    merged = sorted(by_url.values(), key=lambda row: (row.get("SOURCE_TYPE", ""), row.get("URL", "")))
    write_registry(path, merged)
    return new_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--discovery-dir", default="research/discovery")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    args = parser.parse_args()

    retrieval_date = datetime.now(timezone.utc).date().isoformat()
    discovery_dir = Path(args.discovery_dir)
    discovery_dir.mkdir(parents=True, exist_ok=True)

    all_rows: dict[int, dict[str, str]] = {}
    failures: list[dict[str, Any]] = []
    visited_before: set[int | None] = set()
    current_before: int | None = None
    pages_fetched = 0

    for _ in range(args.max_pages):
        if current_before in visited_before:
            break
        visited_before.add(current_before)
        url = ARCHIVE_URL if current_before is None else f"{ARCHIVE_URL}?before={current_before}"
        try:
            html = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"url": url, "error": str(exc)})
            break

        pages_fetched += 1
        page_rows = parse_messages(html, retrieval_date)
        page_ids: list[int] = []
        for row in page_rows:
            message_id = int(row["SOURCE_ID"].rsplit("_", 1)[-1])
            page_ids.append(message_id)
            all_rows[message_id] = row

        candidate = next_before(html, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(args.sleep_seconds, 0.0))

    discovered = [all_rows[key] for key in sorted(all_rows)]
    normalized_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in discovered)
    snapshot_path = discovery_dir / "telegram_sources.jsonl"
    snapshot_path.write_text(normalized_text, encoding="utf-8")
    snapshot_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    new_rows = merge_registry(Path(args.registry), discovered) if discovered else []
    report = {
        "schema_version": 1,
        "channel": CHANNEL,
        "archive_url": ARCHIVE_URL,
        "retrieval_date": retrieval_date,
        "pages_fetched": pages_fetched,
        "discovered_count": len(discovered),
        "new_source_count": len(new_rows),
        "failures": failures,
        "normalized_snapshot_sha256": snapshot_sha256,
        "semantic_closure_performed": False,
    }
    (discovery_dir / "telegram_discovery_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({"discovered": len(discovered), "new": len(new_rows), "failures": len(failures)}))
    if not discovered:
        return 2
    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
