#!/usr/bin/env python3
"""Lexically challenge the canonical concept union against captured Telegram text.

Only already-acquired direct first-party Telegram sources are eligible. Textless
captured posts are observed but do not provide lexical evidence. This audit never
defines strategy semantics automatically.
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

from discover_telegram_sources import ARCHIVE_URL, MESSAGE_RE, TIME_RE, fetch, next_before

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
    position = text.lower().find(needle.lower())
    if position < 0:
        return text[:limit]
    start = max(0, position - limit // 3)
    end = min(len(text), start + limit)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def load_term_catalogs(pattern: str) -> tuple[list[dict], list[str]]:
    paths = sorted(Path().glob(pattern))
    if not paths:
        raise ValueError(f"no term catalogs match {pattern}")
    by_id: dict[str, dict] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("semantic_synthesis_performed") is not False:
            raise ValueError(f"{path}: semantic_synthesis_performed must be false")
        for term in data.get("terms", []):
            concept_id = str(term["concept_id"])
            if concept_id in by_id:
                raise ValueError(f"duplicate term catalog concept_id: {concept_id}")
            normalized = dict(term)
            normalized["lexical_hit_required"] = bool(term.get("lexical_hit_required", True))
            by_id[concept_id] = normalized
    return [by_id[key] for key in sorted(by_id)], [path.as_posix() for path in paths]


def load_acquired_telegram_sources(path: Path) -> set[str]:
    source_ids: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        if (
            record.get("source_type") == "TELEGRAM_POST"
            and record.get("status") == "PAYLOAD_CAPTURED"
            and record.get("first_party_contacted") is True
            and record.get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"
            and record.get("sha256")
        ):
            source_ids.add(str(record["source_id"]))
    return source_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms-glob", default="research/concept_terms*.json")
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--output", default="research/review/concept_term_review.json")
    parser.add_argument("--candidates-output", default="research/review/lexical_candidates.json")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--max-source-ids", type=int, default=25)
    args = parser.parse_args()

    try:
        terms, term_files = load_term_catalogs(args.terms_glob)
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc))
        return 1

    eligible = load_acquired_telegram_sources(Path(args.acquisition))
    occurrences: dict[str, list[dict]] = defaultdict(list)
    lexical_counts: Counter[str] = Counter()
    lexical_sources: dict[str, list[str]] = defaultdict(list)
    lexical_examples: dict[str, str] = {}
    live_message_ids: set[int] = set()
    observed: set[str] = set()
    text_reviewed: set[str] = set()
    textless: set[str] = set()
    unregistered: set[str] = set()
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
            if message_id in live_message_ids:
                continue
            live_message_ids.add(message_id)
            page_ids.append(message_id)
            source_id = f"TG_ARJOIOTRADING_{message_id}"
            if source_id not in eligible:
                unregistered.add(source_id)
                continue
            observed.add(source_id)
            body = match.group("body")
            text = message_text(body)
            if not text:
                textless.add(source_id)
                continue
            text_reviewed.add(source_id)
            date = published_date(body)

            for term in terms:
                aliases = [str(alias) for alias in term.get("aliases", [])]
                matched = next(
                    (
                        alias for alias in aliases
                        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.IGNORECASE)
                    ),
                    None,
                )
                if matched:
                    occurrences[str(term["concept_id"])].append(
                        {"source_id": source_id, "date": date, "matched_alias": matched, "excerpt": excerpt(text, matched)}
                    )

            candidates = set(ACRONYM_RE.findall(text))
            candidates.update(value.strip() for value in QUOTED_RE.findall(text) if value.strip())
            for candidate in candidates:
                value = candidate.strip()
                if not value or value in NOISE:
                    continue
                lexical_counts[value] += 1
                if len(lexical_sources[value]) < args.max_source_ids:
                    lexical_sources[value].append(source_id)
                lexical_examples.setdefault(value, excerpt(text, value))

        candidate_before = next_before(page, current_before, page_ids)
        if candidate_before is None:
            break
        current_before = candidate_before
        time.sleep(max(args.sleep_seconds, 0.0))

    term_review = []
    for term in terms:
        concept_id = str(term["concept_id"])
        hits = occurrences.get(concept_id, [])
        term_review.append(
            {
                "concept_id": concept_id,
                "aliases": term.get("aliases", []),
                "discovery_source_ids": term.get("discovery_source_ids", []),
                "lexical_hit_required": term.get("lexical_hit_required", True),
                "message_count": len({hit["source_id"] for hit in hits}),
                "source_ids": list(dict.fromkeys(hit["source_id"] for hit in hits))[: args.max_source_ids],
                "examples": hits[:3],
                "semantic_definition_performed": False,
            }
        )

    missing = sorted(eligible - observed)
    review = {
        "schema_version": 2,
        "channel": "ArjoioTrading",
        "term_catalog_files": term_files,
        "pages_fetched": pages_fetched,
        "live_messages_seen": len(live_message_ids),
        "eligible_captured_messages": len(eligible),
        "messages_reviewed": len(observed),
        "text_messages_reviewed": len(text_reviewed),
        "textless_eligible_count": len(textless),
        "textless_eligible_source_ids": sorted(textless)[:100],
        "missing_eligible_count": len(missing),
        "missing_eligible_source_ids": missing[:100],
        "unregistered_live_count": len(unregistered),
        "unregistered_live_source_ids": sorted(unregistered)[:100],
        "failures": failures,
        "catalog_concept_count": len(terms),
        "terms": term_review,
        "semantic_synthesis_performed": False,
    }
    lexical = [
        {
            "candidate": candidate,
            "message_count": count,
            "source_ids": lexical_sources[candidate],
            "example": lexical_examples[candidate],
            "semantic_definition_performed": False,
        }
        for candidate, count in sorted(lexical_counts.items(), key=lambda item: (-item[1], item[0].lower()))
    ]
    candidate_report = {
        "schema_version": 2,
        "messages_observed": len(observed),
        "text_messages_reviewed": len(text_reviewed),
        "candidates": lexical,
        "semantic_synthesis_performed": False,
    }

    output = Path(args.output)
    candidates_output = Path(args.candidates_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(review, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    candidates_output.write_text(json.dumps(candidate_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "eligible": len(eligible), "observed": len(observed), "text_reviewed": len(text_reviewed),
        "textless": len(textless), "missing": len(missing), "unregistered": len(unregistered),
        "concepts": len(terms), "lexical_candidates": len(lexical), "failures": len(failures)
    }, sort_keys=True))
    if not observed:
        return 2
    return 4 if failures or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
