#!/usr/bin/env python3
"""Recover bounded Issue #94 cue windows from canonical Telegram post 88."""

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

TARGET_SOURCE_ID = "TG_ARJOIOTRADING_88"
TARGET_SHA256 = "5a130afb13fa6533504a79821f00aadfbc25ce09f0188f93174546cf53d55eae"
TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")

CUES = {
    "MMBM": re.compile(r"\bMMBM\b|\bmarket maker (?:buy|buying) model\b", re.IGNORECASE),
    "LRLR": re.compile(r"\bLRLR\b|\blow resistance liquidity run\b", re.IGNORECASE),
    "INSTRUMENTS": re.compile(r"\b(?:ES|NQ|gold|xau(?:usd)?|eurusd|gbpusd|dxy|btc|eth)\b", re.IGNORECASE),
    "TIMEFRAME": re.compile(r"\b(?:monthly|weekly|daily|4h|1h|30m|15m|5m|htf|mtf|ltf|higher timeframe|lower timeframe)\b", re.IGNORECASE),
    "DIRECTION": re.compile(r"\b(?:bullish|bearish|buy|buyers?|sell|sellers?|long|short|shorts|higher|lower|highs?|lows?)\b", re.IGNORECASE),
    "MODEL_STATE": re.compile(r"\b(?:finished|completed?|consolidat(?:e|ing|ion)|took|take|pair(?:ed|ing)?)\b", re.IGNORECASE),
    "TRIGGER": re.compile(r"\b(?:trigger|confirmation|confirm|break|sweep|run|take|took|raid)\b", re.IGNORECASE),
    "ENTRY": re.compile(r"\b(?:entry|enter|involv(?:e|ed|ement))\b", re.IGNORECASE),
    "STOP_CONTEXT": re.compile(r"\b(?:stop loss|stop losses|buy stops?|sell stops?)\b", re.IGNORECASE),
    "TARGET": re.compile(r"\b(?:target|draw on liquidity|liquidity|EQHs?)\b", re.IGNORECASE),
    "SESSION/TIME_RULE": re.compile(r"\b(?:session|killzone|london|new york|asia|am|pm)\b", re.IGNORECASE),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def target_is_eligible(path: Path) -> bool:
    for record in read_jsonl(path):
        if record.get("source_id") != TARGET_SOURCE_ID:
            continue
        return bool(
            record.get("source_type") == "TELEGRAM_POST"
            and record.get("status") == "PAYLOAD_CAPTURED"
            and record.get("first_party_contacted") is True
            and record.get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"
            and record.get("sha256") == TARGET_SHA256
        )
    return False


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
    left_budget = min(10, max(0, max_words - len(hit)))
    left = before[-left_budget:]
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


def recover_message(body: str, page_meta: dict[str, str], max_words: int, max_excerpts: int) -> dict:
    text = clean_text(body)
    excerpts: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    matched_cues: set[str] = set()
    for label, pattern in CUES.items():
        for hit in list(pattern.finditer(text))[:4]:
            matched_cues.add(label)
            excerpt = bounded_excerpt(text, hit, max_words)
            key = excerpt.casefold()
            if not excerpt or key in seen:
                continue
            seen.add(key)
            if contains_pre_spec_outcome(excerpt):
                excluded.append({"label": label, "matched": hit.group(0), "reason": "PRE_SPEC_OUTCOME_GUARD"})
                continue
            excerpts.append({"label": label, "matched": hit.group(0), "excerpt": excerpt})
            if len(excerpts) >= max_excerpts:
                break
    return {
        "source_id": TARGET_SOURCE_ID,
        "date": published_date(body),
        "message_word_count": len(text.split()),
        "matched_cues": sorted(matched_cues),
        "archive_page_url": page_meta["url"],
        "archive_page_sha256": page_meta["sha256"],
        "archive_page_cache_file": page_meta["cache_file"],
        "excerpts": excerpts[:max_excerpts],
        "excluded_excerpt_count": len(excluded),
        "excluded_excerpt_labels": sorted({item["label"] for item in excluded}),
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive-cache-root")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.12)
    parser.add_argument("--max-words", type=int, default=20)
    parser.add_argument("--max-excerpts", type=int, default=24)
    args = parser.parse_args()
    if not target_is_eligible(Path(args.acquisition)):
        raise SystemExit("Issue 94 Telegram target is not the canonical captured first-party payload")
    cache_root = Path(args.archive_cache_root) if args.archive_cache_root else None
    current_before: int | None = None
    visited: set[int | None] = set()
    seen_ids: set[int] = set()
    pages: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    recovered: dict | None = None
    for page_index in range(args.max_pages):
        if current_before in visited or recovered is not None:
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
            if message_id == 88:
                recovered = recover_message(match.group("body"), page_meta, args.max_words, args.max_excerpts)
                break
        if recovered is not None:
            break
        candidate = next_before(page, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(args.sleep_seconds, 0.0))
    report = {
        "schema_version": 1,
        "issue": 94,
        "predicate_id": "MMBM_LRLR_SHORT_CONTEXT",
        "bounded_source_ids": [TARGET_SOURCE_ID],
        "recovered_source_ids": [TARGET_SOURCE_ID] if recovered else [],
        "missing_source_ids": [] if recovered else [TARGET_SOURCE_ID],
        "pages_fetched": len(pages),
        "messages_seen": len(seen_ids),
        "failures": failures,
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
        "shared_antibias_guard": True,
        "archive_pages_sha256_bound": True,
        "archive_pages": pages,
        "messages": [recovered] if recovered else [],
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(pages), "recovered": 1 if recovered else 0, "missing": 0 if recovered else 1, "failures": len(failures), "matched_cues": recovered["matched_cues"] if recovered else [], "excerpts": recovered["excerpts"] if recovered else [], "excluded_excerpt_count": recovered["excluded_excerpt_count"] if recovered else 0}, ensure_ascii=False, sort_keys=True))
    return 4 if failures or recovered is None else 0


if __name__ == "__main__":
    raise SystemExit(main())
