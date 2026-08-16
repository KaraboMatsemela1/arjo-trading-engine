#!/usr/bin/env python3
"""Recover bounded Issue #85 cue windows from three canonical Telegram posts.

The public first-party archive is scanned only for posts 785, 786 and 790.
Archive pages are SHA-bound and all excerpts pass the shared pre-SPEC anti-bias guard.
No predicate assignment or semantic synthesis is performed here.
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

TARGET_SOURCE_IDS = {
    "TG_ARJOIOTRADING_785",
    "TG_ARJOIOTRADING_786",
    "TG_ARJOIOTRADING_790",
}
TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")
CONCEPT_ALIASES = {
    "ORDER_FLOW": ["Order Flow", "Order Flow Leg", "Order Flow Legs"],
    "TARGET_BIAS": ["Target", "Bias"],
}
FIELD_CUES = {
    "INSTRUMENTS": re.compile(r"\b(?:gold|xau(?:usd)?|eurusd|gbpusd|nq|es|dxy|btc|eth)\b", re.IGNORECASE),
    "TIMEFRAME": re.compile(r"\b(?:monthly|weekly|daily|4h|1h|15m|5m|htf|ltf|higher timeframe|lower timeframe)\b", re.IGNORECASE),
    "DIRECTION": re.compile(r"\b(?:bullish|bearish|buy|sell|long|short|higher|lower)\b", re.IGNORECASE),
    "TRIGGER": re.compile(r"\b(?:trigger|confirmation|confirm|shift|transition|break|disrespect|respect)\b", re.IGNORECASE),
    "ENTRY": re.compile(r"\b(?:entry|enter|involv(?:e|ed|ement))\b", re.IGNORECASE),
    "SESSION/TIME_RULE": re.compile(r"\b(?:session|killzone|london|new york|asia|am|pm)\b", re.IGNORECASE),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def targets_are_eligible(path: Path) -> bool:
    eligible: set[str] = set()
    for record in read_jsonl(path):
        source_id = str(record.get("source_id", ""))
        if source_id not in TARGET_SOURCE_IDS:
            continue
        if (
            record.get("source_type") == "TELEGRAM_POST"
            and record.get("status") == "PAYLOAD_CAPTURED"
            and record.get("first_party_contacted") is True
            and record.get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"
            and record.get("sha256")
        ):
            eligible.add(source_id)
    return eligible == TARGET_SOURCE_IDS


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
    return " ".join([*left, *hit, *after[: max(0, max_words - len(left) - len(hit))]]).strip()


def persist_page(cache_root: Path | None, page: str, index: int, before: int | None, url: str) -> dict[str, str]:
    payload = page.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    file_name = ""
    if cache_root is not None:
        cache_root.mkdir(parents=True, exist_ok=True)
        label = "root" if before is None else str(before)
        file_name = f"page_{index:03d}_before_{label}_{digest[:16]}.html"
        (cache_root / file_name).write_bytes(payload)
    return {"url": url, "sha256": digest, "cache_file": file_name}


def recover_message(body: str, source_id: str, page_meta: dict[str, str], max_words: int, max_excerpts: int) -> dict:
    text = clean_text(body)
    excerpts: list[dict[str, str]] = []
    seen_excerpt: set[str] = set()
    concepts: set[str] = set()

    for concept, aliases in CONCEPT_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", re.IGNORECASE)
            for hit in list(pattern.finditer(text))[:3]:
                concepts.add(concept)
                excerpt = bounded_excerpt(text, hit, max_words)
                if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.casefold() not in seen_excerpt:
                    seen_excerpt.add(excerpt.casefold())
                    excerpts.append({"kind": "CONCEPT", "label": concept, "matched": alias, "excerpt": excerpt})

    field_cues: set[str] = set()
    for field, pattern in FIELD_CUES.items():
        hits = list(pattern.finditer(text))
        if hits:
            field_cues.add(field)
        for hit in hits[:2]:
            excerpt = bounded_excerpt(text, hit, max_words)
            if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.casefold() not in seen_excerpt:
                seen_excerpt.add(excerpt.casefold())
                excerpts.append({"kind": "FIELD_CUE", "label": field, "matched": hit.group(0), "excerpt": excerpt})
            if len(excerpts) >= max_excerpts:
                break

    return {
        "source_id": source_id,
        "date": published_date(body),
        "concepts": sorted(concepts),
        "field_cues": sorted(field_cues),
        "archive_page_url": page_meta["url"],
        "archive_page_sha256": page_meta["sha256"],
        "archive_page_cache_file": page_meta["cache_file"],
        "excerpts": excerpts[:max_excerpts],
        "semantic_synthesis_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive-cache-root")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--max-words", type=int, default=20)
    parser.add_argument("--max-excerpts", type=int, default=18)
    args = parser.parse_args()

    if not targets_are_eligible(Path(args.acquisition)):
        raise SystemExit("Issue 85 Telegram targets are not canonical captured first-party payloads")

    cache_root = Path(args.archive_cache_root) if args.archive_cache_root else None
    current_before: int | None = None
    visited: set[int | None] = set()
    seen_ids: set[int] = set()
    pages: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    recovered: dict[str, dict] = {}

    for page_index in range(args.max_pages):
        if current_before in visited or set(recovered) == TARGET_SOURCE_IDS:
            break
        visited.add(current_before)
        url = ARCHIVE_URL if current_before is None else f"{ARCHIVE_URL}?before={current_before}"
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"url": url, "error": str(exc)})
            break

        page_meta = persist_page(cache_root, page, page_index, current_before, url)
        pages.append(page_meta)
        page_ids: list[int] = []

        for match in MESSAGE_RE.finditer(page):
            message_id = int(match.group(1))
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            page_ids.append(message_id)
            source_id = f"TG_ARJOIOTRADING_{message_id}"
            if source_id not in TARGET_SOURCE_IDS or source_id in recovered:
                continue
            recovered[source_id] = recover_message(
                match.group("body"), source_id, page_meta, args.max_words, args.max_excerpts
            )

        candidate = next_before(page, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(args.sleep_seconds, 0.0))

    missing = sorted(TARGET_SOURCE_IDS - set(recovered))
    report = {
        "schema_version": 1,
        "issue": 85,
        "predicate_id": "ORDER_FLOW_TARGET_BIAS",
        "bounded_source_ids": sorted(TARGET_SOURCE_IDS),
        "recovered_source_ids": sorted(recovered),
        "missing_source_ids": missing,
        "pages_fetched": len(pages),
        "messages_seen": len(seen_ids),
        "failures": failures,
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
        "shared_antibias_guard": True,
        "archive_pages_sha256_bound": True,
        "archive_pages": pages,
        "messages": [recovered[source_id] for source_id in sorted(recovered)],
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"pages": len(pages), "recovered": len(recovered), "missing": len(missing), "failures": len(failures)},
            sort_keys=True,
        )
    )
    return 4 if failures or missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
