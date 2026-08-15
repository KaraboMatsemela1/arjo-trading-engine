#!/usr/bin/env python3
"""Build a copyright-bounded lexical review of the public first-party Telegram corpus.

The output is a discovery/review aid only. It records term occurrences and small
context snippets; it does not define concepts or synthesize executable rules.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import time
import urllib.error
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from discover_telegram_sources import ARCHIVE_URL, BEFORE_RE, MESSAGE_RE, TIME_RE, fetch, next_before

TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")
ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z]{2,7}|[0-9][A-Z]{1,6})(?![A-Za-z0-9])")
QUOTED_RE = re.compile(r"[\"']([^\"'\n]{3,48})[\"']")
NOISE = {
    "EST", "NY", "YT", "USD", "EUR", "GBP", "AUD", "CAD", "CHF", "JPY",
    "ES", "NQ", "DXY", "BTC", "ETH", "PDF", "FAQ", "DM", "VIP", "MMT",
}


def message_text(body: str) -> str:
    match = TEXT_RE.search(body)
    if not match:
        return ""
    value = BR_RE.sub("\n", match.group(1))
    value = TAG_RE.sub(" ", value)
    value = html_lib.unescape(value)
    value = URL_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def published_date(body: str) -> str:
    match = TIME_RE.search(body)
    if not match:
        return ""
    try:
        return datetime.fromisoformat(match.group(1).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def excerpt(text: str, needle: str, limit: int = 180) -> str:
    lower = text.lower()
    pos = lower.find(needle.lower())
    if pos < 0:
        return text[:limit]
    start = max(0, pos - limit // 3)
    end = min(len(text), start + limit)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def load_term_catalog(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("terms", []))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", default="research/concept_terms.json")
    parser.add_argument("--output", default="research/review/concept_term_review.json")
    parser.add_argument("--candidates-output", default="research/review/lexical_candidates.json")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--max-source-ids", type=int, default=25)
    args = parser.parse_args()

    terms = load_term_catalog(Path(args.terms))
    occurrences: dict[str, list[dict]] = defaultdict(list)
    lexical_counts: Counter[str] = Counter()
    lexical_sources: dict[str, list[str]] = defaultdict(list)
    lexical_examples: dict[str, str] = {}
    seen_messages: set[int] = set()
    failures: list[dict[str, str]] = []
    current_before: int | None = None
    visited_before: set[int | None] = set()
    pages_fetched = 0

    for _ in range(args.max_pages):
        if current_before in visited_before:
            break
        visited_before.add(current_before)
        url = ARCHIVE_URL if current_before is None else f"{ARCHIVE_URL}?before={current_before}"
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"url": url, "error": str(exc)})
            break
        pages_fetched += 1
        page_ids: list[int] = []

        for match in MESSAGE_RE.finditer(page):
            message_id = int(match.group(1))
            if message_id in seen_messages:
                continue
            seen_messages.add(message_id)
            page_ids.append(message_id)
            body = match.group("body")
            text = message_text(body)
            if not text:
                continue
            source_id = f"TG_ARJOIOTRADING_{message_id}"
            date = published_date(body)

            for term in terms:
                aliases = [str(alias) for alias in term.get("aliases", [])]
                matched = next((alias for alias in aliases if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE)), None)
                if matched:
                    occurrences[str(term["concept_id"])].append(
                        {"source_id": source_id, "date": date, "matched_alias": matched, "excerpt": excerpt(text, matched)}
                    )

            candidates = set(ACRONYM_RE.findall(text))
            candidates.update(value.strip() for value in QUOTED_RE.findall(text) if value.strip())
            for candidate in candidates:
                normalized = candidate.strip()
                if not normalized or normalized in NOISE:
                    continue
                lexical_counts[normalized] += 1
                if len(lexical_sources[normalized]) < args.max_source_ids:
                    lexical_sources[normalized].append(source_id)
                lexical_examples.setdefault(normalized, excerpt(text, normalized))

        candidate = next_before(page, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(args.sleep_seconds, 0.0))

    review_terms: list[dict] = []
    catalog_ids = {str(term["concept_id"]) for term in terms}
    for term in terms:
        concept_id = str(term["concept_id"])
        hits = occurrences.get(concept_id, [])
        review_terms.append(
            {
                "concept_id": concept_id,
                "aliases": term.get("aliases", []),
                "discovery_source_ids": term.get("discovery_source_ids", []),
                "message_count": len({hit["source_id"] for hit in hits}),
                "source_ids": list(dict.fromkeys(hit["source_id"] for hit in hits))[: args.max_source_ids],
                "examples": hits[:3],
                "semantic_definition_performed": False,
            }
        )

    review = {
        "schema_version": 1,
        "channel": "ArjoioTrading",
        "pages_fetched": pages_fetched,
        "messages_reviewed": len(seen_messages),
        "failures": failures,
        "catalog_concept_count": len(catalog_ids),
        "terms": review_terms,
        "semantic_synthesis_performed": False,
    }

    lexical = []
    for candidate, count in sorted(lexical_counts.items(), key=lambda item: (-item[1], item[0].lower())):
        lexical.append(
            {
                "candidate": candidate,
                "message_count": count,
                "source_ids": lexical_sources[candidate],
                "example": lexical_examples[candidate],
                "semantic_definition_performed": False,
            }
        )
    candidate_report = {
        "schema_version": 1,
        "messages_reviewed": len(seen_messages),
        "minimum_frequency_not_applied": True,
        "candidates": lexical,
        "semantic_synthesis_performed": False,
    }

    output = Path(args.output)
    candidates_output = Path(args.candidates_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(review, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    candidates_output.write_text(json.dumps(candidate_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"messages_reviewed": len(seen_messages), "pages_fetched": pages_fetched, "known_terms": len(review_terms), "lexical_candidates": len(lexical), "failures": len(failures)}, sort_keys=True))
    if not seen_messages:
        return 2
    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
