#!/usr/bin/env python3
"""Recover bounded Issue #48 concept/field cue windows from the public Telegram archive.

Only Telegram sources already recorded as direct PAYLOAD_CAPTURED first-party
material in the canonical acquisition manifest are eligible. The script performs
lexical routing only: it does not assign predicate states or synthesize strategy
semantics. Excerpts are short and pre-SPEC performance/outcome terms are filtered.
Every archive page used for routing is optionally persisted and SHA-256 bound so
archive-derived locators are replayable inside the workflow artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import time
import urllib.error
from datetime import datetime
from pathlib import Path

from discover_telegram_sources import ARCHIVE_URL, MESSAGE_RE, TIME_RE, fetch, next_before
from evidence_antibias import contains_pre_spec_outcome

TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")

CONCEPT_ALIASES = {
    "AREA_OF_OPPORTUNITY": ["Area of Opportunity", "AoO"],
    "FAIR_VALUE_AREA": ["Fair Value Area", "FVA"],
    "FAIR_VALUE_GAP": ["Fair Value Gap", "FVG", "FVGs"],
    "TWO_CANDLE_REJECTION": ["2 Candle Rejection", "2CR"],
}

FIELD_CUES = {
    "INSTRUMENTS": re.compile(
        r"\b(?:gold|xau(?:usd)?|eurusd|gbpusd|usdjpy|usdchf|audusd|usdcad|nzdusd|gbpcad|eurcad|nq|es|dxy|btc|eth)\b",
        re.IGNORECASE,
    ),
    "TIMEFRAME": re.compile(
        r"\b(?:monthly|weekly|daily|day|4h|1h|2h|3h|15m|30m|5m|1m|htf|ltf|higher timeframe|lower timeframe)\b",
        re.IGNORECASE,
    ),
    "HIGHER_TIMEFRAME_CONTEXT": re.compile(
        r"\b(?:htf|higher timeframe|daily|weekly|monthly|4h|1h)\b",
        re.IGNORECASE,
    ),
    "DIRECTION": re.compile(
        r"\b(?:buy|buys|buying|sell|sells|selling|long|longs|short|shorts|bullish|bearish|higher|lower)\b",
        re.IGNORECASE,
    ),
    "PRECONDITIONS_SETUP": re.compile(
        r"\b(?:respect|respects|respected|disrespect|disrespects|disrespected|liquidity|rejection|run|runs|sweep|sweeps|swing high|swing low|pd array|breakaway gap|bag|resistance|equilibrium)\b",
        re.IGNORECASE,
    ),
    "TRIGGER_ENTRY": re.compile(
        r"\b(?:trigger|entry|entries|enter|involved|involvement|2cr|2 candle rejection|rejection)\b",
        re.IGNORECASE,
    ),
    "STOP": re.compile(r"\b(?:stop loss|stop-loss|stops?|sl)\b", re.IGNORECASE),
    "TARGET": re.compile(r"\b(?:target|targets|draw on liquidity|dol|take highs|take lows|highs|lows)\b", re.IGNORECASE),
    "INVALIDATION_EXPIRY": re.compile(
        r"\b(?:invalid|invalidate|invalidation|fail|fails|failed|failure|expire|expires|expiry|until)\b",
        re.IGNORECASE,
    ),
    "SESSION_TIME_RULE": re.compile(
        r"\b(?:new york|ny|london|asia|session|am|pm|midnight|open|opening|killzone|kill zone)\b",
        re.IGNORECASE,
    ),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def eligible_sources(path: Path) -> set[str]:
    result: set[str] = set()
    for record in read_jsonl(path):
        if (
            record.get("source_type") == "TELEGRAM_POST"
            and record.get("status") == "PAYLOAD_CAPTURED"
            and record.get("first_party_contacted") is True
            and record.get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"
            and record.get("sha256")
        ):
            result.add(str(record["source_id"]))
    return result


def clean_text(body: str) -> str:
    match = TEXT_RE.search(body)
    if not match:
        return ""
    value = BR_RE.sub(" ", match.group(1))
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


def bounded_excerpt(text: str, match: re.Match[str], max_words: int) -> str:
    before = text[: match.start()].split()
    hit = text[match.start() : match.end()].split()
    after = text[match.end() :].split()
    left = before[-6:]
    right = after[: max(0, max_words - len(left) - len(hit))]
    return " ".join([*left, *hit, *right]).strip()


def concept_hits(text: str) -> dict[str, list[tuple[str, re.Match[str]]]]:
    hits: dict[str, list[tuple[str, re.Match[str]]]] = {}
    for concept_id, aliases in CONCEPT_ALIASES.items():
        rows: list[tuple[str, re.Match[str]]] = []
        for alias in aliases:
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", re.IGNORECASE)
            rows.extend((alias, match) for match in pattern.finditer(text))
        if rows:
            hits[concept_id] = sorted(rows, key=lambda row: row[1].start())
    return hits


def persist_archive_page(
    cache_root: Path | None,
    page: str,
    page_index: int,
    current_before: int | None,
    url: str,
) -> dict[str, str]:
    payload = page.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    file_name = ""
    if cache_root is not None:
        cache_root.mkdir(parents=True, exist_ok=True)
        before_label = "root" if current_before is None else str(current_before)
        file_name = f"page_{page_index:03d}_before_{before_label}_{digest[:16]}.html"
        (cache_root / file_name).write_bytes(payload)
    return {
        "url": url,
        "sha256": digest,
        "cache_file": file_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive-cache-root")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--max-words", type=int, default=20)
    parser.add_argument("--max-excerpts-per-message", type=int, default=12)
    args = parser.parse_args()

    eligible = eligible_sources(Path(args.acquisition))
    cache_root = Path(args.archive_cache_root) if args.archive_cache_root else None
    visited_before: set[int | None] = set()
    current_before: int | None = None
    seen_ids: set[int] = set()
    pages_fetched = 0
    failures: list[dict[str, str]] = []
    rows: list[dict] = []
    archive_pages: list[dict[str, str]] = []

    for page_index in range(args.max_pages):
        if current_before in visited_before:
            break
        visited_before.add(current_before)
        url = ARCHIVE_URL if current_before is None else f"{ARCHIVE_URL}?before={current_before}"
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"url": url, "error": str(exc)})
            break
        page_meta = persist_archive_page(cache_root, page, page_index, current_before, url)
        archive_pages.append(page_meta)
        pages_fetched += 1
        page_ids: list[int] = []

        for match in MESSAGE_RE.finditer(page):
            message_id = int(match.group(1))
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            page_ids.append(message_id)
            source_id = f"TG_ARJOIOTRADING_{message_id}"
            if source_id not in eligible:
                continue
            body = match.group("body")
            text = clean_text(body)
            if not text:
                continue
            concepts = concept_hits(text)
            if not concepts:
                continue

            cue_hits: dict[str, list[re.Match[str]]] = {
                field: list(pattern.finditer(text)) for field, pattern in FIELD_CUES.items()
            }
            cue_hits = {field: values for field, values in cue_hits.items() if values}
            excerpts: list[dict[str, str]] = []
            seen_excerpt: set[str] = set()

            for concept_id, matches in concepts.items():
                for alias, concept_match in matches[:3]:
                    excerpt = bounded_excerpt(text, concept_match, args.max_words)
                    if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.lower() not in seen_excerpt:
                        seen_excerpt.add(excerpt.lower())
                        excerpts.append({"kind": "CONCEPT", "label": concept_id, "matched": alias, "excerpt": excerpt})
            for field, matches in cue_hits.items():
                for cue_match in matches[:2]:
                    excerpt = bounded_excerpt(text, cue_match, args.max_words)
                    if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.lower() not in seen_excerpt:
                        seen_excerpt.add(excerpt.lower())
                        excerpts.append({"kind": "FIELD_CUE", "label": field, "matched": cue_match.group(0), "excerpt": excerpt})
                    if len(excerpts) >= args.max_excerpts_per_message:
                        break
                if len(excerpts) >= args.max_excerpts_per_message:
                    break

            rows.append(
                {
                    "source_id": source_id,
                    "date": published_date(body),
                    "concepts": sorted(concepts),
                    "field_cues": sorted(cue_hits),
                    "archive_page_url": page_meta["url"],
                    "archive_page_sha256": page_meta["sha256"],
                    "archive_page_cache_file": page_meta["cache_file"],
                    "excerpts": excerpts[: args.max_excerpts_per_message],
                    "semantic_synthesis_performed": False,
                }
            )

        candidate = next_before(page, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(args.sleep_seconds, 0.0))

    report = {
        "schema_version": 2,
        "issue": 48,
        "archive_url": ARCHIVE_URL,
        "eligible_captured_telegram_sources": len(eligible),
        "pages_fetched": pages_fetched,
        "messages_seen": len(seen_ids),
        "recovery_message_count": len(rows),
        "failures": failures,
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
        "shared_antibias_guard": True,
        "archive_pages_sha256_bound": True,
        "archive_pages": archive_pages,
        "messages": sorted(rows, key=lambda row: int(str(row["source_id"]).rsplit("_", 1)[-1])),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"eligible": len(eligible), "pages": pages_fetched, "messages": len(rows), "failures": len(failures)}, sort_keys=True))
    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
