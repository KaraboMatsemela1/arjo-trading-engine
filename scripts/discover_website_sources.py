#!/usr/bin/env python3
"""Discover public first-party Trading MMT web pages and linked educational assets.

This is a URL/title discovery crawler, not a semantic extractor. It stays on the
first-party site and records external resources only when directly linked by the
first-party site. Strategy meaning is never inferred here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = "https://tradingmmt.com/"
HOST = "tradingmmt.com"
SEEDS = [ROOT, f"{ROOT}newsletter/", f"{ROOT}mmc/"]
EXTERNAL_RESOURCE_HOSTS = {"drive.google.com", "arjoo.notion.site", "www.notion.so", "notion.site"}
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".zip", ".mp4", ".mp3", ".webm",
}
SKIP_PATH_PREFIXES = (
    "/wp-admin/", "/wp-login", "/cart/", "/checkout/", "/my-account/",
)
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


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.published_time = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "a" and values.get("href"):
            self.links.append(values["href"])
        elif tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "meta":
            prop = (values.get("property") or values.get("name") or "").lower()
            if prop in {"article:published_time", "date", "datepublished"} and values.get("content"):
                self.published_time = values["content"]
        elif tag.lower() == "time" and not self.published_time and values.get("datetime"):
            self.published_time = values["datetime"]

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(part for part in self.title_parts if part).strip()


def fetch(url: str, timeout: int = 30) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "arjo-trading-engine-source-discovery/1.0 (+research; public metadata only)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"unsupported content type: {content_type}")
        return final_url, response.read().decode("utf-8", errors="replace")


def canonicalize(base: str, href: str) -> str | None:
    absolute = urllib.parse.urljoin(base, href)
    parsed = urllib.parse.urlsplit(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return None
    clean = urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))
    if clean.endswith("//"):
        clean = clean[:-1]
    if hostname == HOST and not clean.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        clean += "/"
    return clean


def publication_date(raw: str) -> str:
    if not raw:
        return ""
    value = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return ""


def make_id(prefix: str, url: str) -> str:
    return f"{prefix}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:20].upper()}"


def internal_row(url: str, title: str, published: str, retrieval_date: str) -> dict[str, str]:
    path = urllib.parse.urlsplit(url).path
    source_type = "WEBSITE_PAGE"
    if path == "/mmc/":
        source_type = "WEBSITE_EDUCATIONAL_HUB"
    elif path == "/newsletter/":
        source_type = "WEBSITE_NEWSLETTER_HUB"
    return {
        "SOURCE_ID": make_id("WEB", url),
        "SOURCE_TYPE": source_type,
        "TITLE": title or path or url,
        "URL": url,
        "PUBLICATION_DATE": published,
        "AUTHOR": "Arjoio's MMT",
        "CHANNEL_ID": HOST,
        "FIRST_PARTY_STATUS": "CONFIRMED_FIRST_PARTY",
        "RETRIEVAL_DATE": retrieval_date,
        "RAW_ARTIFACT_SHA256": "",
        "TRANSCRIPT_AVAILABLE": "NOT_APPLICABLE",
        "FRAME_EXTRACTION_AVAILABLE": "UNKNOWN",
        "NOTES": "Discovered by bounded crawl of the first-party Trading MMT public website; relevance unassessed; no semantic closure performed",
    }


def external_row(url: str, retrieval_date: str) -> dict[str, str]:
    host = urllib.parse.urlsplit(url).hostname or ""
    return {
        "SOURCE_ID": make_id("WEBLINK", url),
        "SOURCE_TYPE": "FIRST_PARTY_LINKED_RESOURCE",
        "TITLE": f"First-party linked resource on {host}",
        "URL": url,
        "PUBLICATION_DATE": "",
        "AUTHOR": "Arjoio's MMT",
        "CHANNEL_ID": HOST,
        "FIRST_PARTY_STATUS": "CONFIRMED_FIRST_PARTY_LINKED",
        "RETRIEVAL_DATE": retrieval_date,
        "RAW_ARTIFACT_SHA256": "",
        "TRANSCRIPT_AVAILABLE": "UNKNOWN",
        "FRAME_EXTRACTION_AVAILABLE": "UNKNOWN",
        "NOTES": "Directly linked from the official Trading MMT site; ownership/content must be provenance-bound during acquisition; no semantic closure performed",
    }


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
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--sleep-seconds", type=float, default=0.10)
    args = parser.parse_args()

    retrieval_date = datetime.now(timezone.utc).date().isoformat()
    discovery_dir = Path(args.discovery_dir)
    discovery_dir.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque(SEEDS)
    queued = set(SEEDS)
    visited: set[str] = set()
    internal_rows: dict[str, dict[str, str]] = {}
    external_rows: dict[str, dict[str, str]] = {}
    failures: list[dict[str, Any]] = []

    while queue and len(visited) < args.max_pages:
        requested_url = queue.popleft()
        if requested_url in visited:
            continue
        path = urllib.parse.urlsplit(requested_url).path
        if path.startswith(SKIP_PATH_PREFIXES):
            continue
        visited.add(requested_url)
        try:
            final_url, html = fetch(requested_url)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            failures.append({"url": requested_url, "error": str(exc)})
            continue

        parser_html = PageParser()
        parser_html.feed(html)
        canonical_final = canonicalize(final_url, final_url) or final_url
        internal_rows[canonical_final] = internal_row(
            canonical_final,
            parser_html.title,
            publication_date(parser_html.published_time),
            retrieval_date,
        )

        for href in parser_html.links:
            url = canonicalize(final_url, href)
            if not url:
                continue
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower()
            if host == HOST:
                if parsed.path.startswith(SKIP_PATH_PREFIXES):
                    continue
                if url not in visited and url not in queued and len(queued) + len(visited) < args.max_pages * 2:
                    queue.append(url)
                    queued.add(url)
            elif host in EXTERNAL_RESOURCE_HOSTS:
                external_rows.setdefault(url, external_row(url, retrieval_date))

        time.sleep(max(args.sleep_seconds, 0.0))

    discovered = sorted(
        [*internal_rows.values(), *external_rows.values()],
        key=lambda row: (row["SOURCE_TYPE"], row["URL"]),
    )
    normalized_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in discovered)
    (discovery_dir / "website_sources.jsonl").write_text(normalized_text, encoding="utf-8")
    snapshot_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    new_rows = merge_registry(Path(args.registry), discovered) if discovered else []
    report = {
        "schema_version": 1,
        "root": ROOT,
        "retrieval_date": retrieval_date,
        "pages_attempted": len(visited),
        "internal_pages_discovered": len(internal_rows),
        "first_party_linked_resources_discovered": len(external_rows),
        "discovered_count": len(discovered),
        "new_source_count": len(new_rows),
        "queue_truncated": bool(queue),
        "failures": failures,
        "normalized_snapshot_sha256": snapshot_sha256,
        "semantic_closure_performed": False,
    }
    (discovery_dir / "website_discovery_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "discovered": len(discovered),
                "new": len(new_rows),
                "failures": len(failures),
                "queue_truncated": bool(queue),
            }
        )
    )
    if not discovered:
        return 2
    return 4 if failures or queue else 0


if __name__ == "__main__":
    raise SystemExit(main())
