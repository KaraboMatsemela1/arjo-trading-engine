#!/usr/bin/env python3
"""Enumerate the official Arjo YouTube surfaces without interpreting semantics.

Requires the `yt-dlp` executable unless --fixture-dir is supplied. The script
normalizes discovery output, merges newly discovered first-party URLs into the
canonical source registry, and writes a machine-readable new-source report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SURFACES = {
    "videos": "https://www.youtube.com/@Arjoio/videos",
    "shorts": "https://www.youtube.com/@Arjoio/shorts",
    "streams": "https://www.youtube.com/@Arjoio/streams",
    "playlists": "https://www.youtube.com/@Arjoio/playlists",
}
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


def run_ytdlp(url: str) -> dict[str, Any]:
    executable = shutil.which("yt-dlp")
    if not executable:
        raise RuntimeError("yt-dlp executable not found")
    command = [
        executable,
        "--flat-playlist",
        "--dump-single-json",
        "--quiet",
        "--no-warnings",
        url,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=300)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"yt-dlp failed for {url}")
    return json.loads(completed.stdout)


def load_surface(surface: str, fixture_dir: Path | None) -> dict[str, Any]:
    if fixture_dir is None:
        return run_ytdlp(SURFACES[surface])
    fixture = fixture_dir / f"{surface}.json"
    if not fixture.exists():
        raise RuntimeError(f"Missing fixture: {fixture}")
    return json.loads(fixture.read_text(encoding="utf-8"))


def canonical_url(entry: dict[str, Any], surface: str) -> str:
    webpage = entry.get("webpage_url") or entry.get("url")
    entry_id = entry.get("id")
    if isinstance(webpage, str) and webpage.startswith("http"):
        return webpage
    if surface == "playlists" and entry_id:
        return f"https://www.youtube.com/playlist?list={entry_id}"
    if entry_id:
        return f"https://www.youtube.com/watch?v={entry_id}"
    return str(webpage or "")


def source_type(surface: str) -> str:
    return {
        "videos": "YOUTUBE_VIDEO",
        "shorts": "YOUTUBE_SHORT",
        "streams": "YOUTUBE_STREAM",
        "playlists": "YOUTUBE_PLAYLIST",
    }[surface]


def source_id(entry: dict[str, Any], surface: str, url: str) -> str:
    entry_id = str(entry.get("id") or "").strip()
    if not entry_id:
        entry_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    prefix = {
        "videos": "YT_VIDEO",
        "shorts": "YT_SHORT",
        "streams": "YT_STREAM",
        "playlists": "YT_PLAYLIST",
    }[surface]
    return f"{prefix}_{entry_id}"


def publication_date(entry: dict[str, Any]) -> str:
    raw = str(entry.get("upload_date") or "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
    if timestamp:
        try:
            return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            pass
    return ""


def normalize(payloads: dict[str, dict[str, Any]], retrieval_date: str) -> list[dict[str, str]]:
    by_url: dict[str, dict[str, str]] = {}
    for surface, payload in payloads.items():
        parent_channel_id = str(payload.get("channel_id") or payload.get("uploader_id") or "")
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            url = canonical_url(entry, surface)
            if not url:
                continue
            row = {
                "SOURCE_ID": source_id(entry, surface, url),
                "SOURCE_TYPE": source_type(surface),
                "TITLE": str(entry.get("title") or ""),
                "URL": url,
                "PUBLICATION_DATE": publication_date(entry),
                "AUTHOR": str(entry.get("channel") or entry.get("uploader") or "Arjo"),
                "CHANNEL_ID": str(entry.get("channel_id") or parent_channel_id),
                "FIRST_PARTY_STATUS": "CONFIRMED_FIRST_PARTY",
                "RETRIEVAL_DATE": retrieval_date,
                "RAW_ARTIFACT_SHA256": "",
                "TRANSCRIPT_AVAILABLE": "UNKNOWN",
                "FRAME_EXTRACTION_AVAILABLE": "UNKNOWN",
                "NOTES": f"Discovered deterministically from official YouTube {surface} surface; relevance unassessed; no semantic closure performed",
            }
            existing = by_url.get(url)
            if existing is None or row["SOURCE_TYPE"] == "YOUTUBE_VIDEO":
                by_url[url] = row
    return sorted(by_url.values(), key=lambda row: (row["SOURCE_TYPE"], row["URL"]))


def read_registry(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_registry(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--discovery-dir", default="research/discovery")
    parser.add_argument("--fixture-dir")
    args = parser.parse_args()

    retrieval_date = datetime.now(timezone.utc).date().isoformat()
    fixture_dir = Path(args.fixture_dir) if args.fixture_dir else None
    discovery_dir = Path(args.discovery_dir)
    discovery_dir.mkdir(parents=True, exist_ok=True)

    payloads: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for surface in SURFACES:
        try:
            payloads[surface] = load_surface(surface, fixture_dir)
        except Exception as exc:  # bounded discovery should record, not hide, access failures
            failures.append({"surface": surface, "url": SURFACES[surface], "error": str(exc)})

    if not payloads:
        (discovery_dir / "youtube_discovery_failures.json").write_text(
            json.dumps(failures, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("All YouTube discovery surfaces failed", file=sys.stderr)
        return 2

    discovered = normalize(payloads, retrieval_date)
    normalized_path = discovery_dir / "youtube_sources.jsonl"
    normalized_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in discovered)
    normalized_path.write_text(normalized_text, encoding="utf-8")
    normalized_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    registry_path = Path(args.registry)
    existing = read_registry(registry_path)
    existing_by_url = {row.get("URL", ""): row for row in existing if row.get("URL")}
    new_rows = [row for row in discovered if row["URL"] not in existing_by_url]
    merged_by_url = dict(existing_by_url)
    for row in discovered:
        merged_by_url.setdefault(row["URL"], row)
    merged = sorted(merged_by_url.values(), key=lambda row: (row.get("SOURCE_TYPE", ""), row.get("URL", "")))
    write_registry(registry_path, merged)

    report = {
        "schema_version": 1,
        "retrieval_date": retrieval_date,
        "surfaces_attempted": list(SURFACES),
        "surfaces_succeeded": sorted(payloads),
        "failures": failures,
        "discovered_count": len(discovered),
        "new_source_count": len(new_rows),
        "normalized_snapshot_sha256": normalized_sha256,
        "new_sources": new_rows,
    }
    (discovery_dir / "new_sources.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"discovered": len(discovered), "new": len(new_rows), "failures": len(failures)}))
    return 0 if not failures else 4


if __name__ == "__main__":
    raise SystemExit(main())
