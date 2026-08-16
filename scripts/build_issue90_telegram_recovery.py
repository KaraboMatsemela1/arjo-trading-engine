#!/usr/bin/env python3
"""Recover bounded Equilibrium/stop-run cues from canonical Arjo Telegram posts.

Selection is lexical only and limited to the exact Issue #90 terms. A message is
eligible only when its TG source is already a direct first-party PAYLOAD_CAPTURED
record in the canonical acquisition manifest. Archive pages are SHA-bound and all
emitted excerpts pass the shared pre-SPEC anti-bias guard. No predicate state is
assigned here.
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

TERM_PATTERNS = {
    "EQUILIBRIUM": re.compile(r"(?<![A-Za-z0-9])equilibrium(?![A-Za-z0-9])", re.IGNORECASE),
    "STOP_RUN": re.compile(r"(?<![A-Za-z0-9])(?:stop\s+run|stop-run|stoprun)(?![A-Za-z0-9])", re.IGNORECASE),
}

FIELD_CUES = {
    "INSTRUMENTS": re.compile(
        r"\b(?:gold|xau(?:usd)?|eurusd|gbpusd|usdjpy|usdchf|audusd|usdcad|nzdusd|nq|es|dxy|btc|eth)\b",
        re.IGNORECASE,
    ),
    "TIMEFRAME": re.compile(
        r"\b(?:monthly|weekly|daily|4h|1h|2h|3h|30m|15m|5m|1m|htf|ltf|higher timeframe|lower timeframe)\b",
        re.IGNORECASE,
    ),
    "HIGHER_TIMEFRAME_CONTEXT": re.compile(
        r"\b(?:htf|higher timeframe|monthly|weekly|daily|4h|1h)\b",
        re.IGNORECASE,
    ),
    "DIRECTION": re.compile(
        r"\b(?:buy|buys|buying|sell|sells|selling|long|longs|short|shorts|bullish|bearish|higher|lower)\b",
        re.IGNORECASE,
    ),
    "TRIGGER_ENTRY": re.compile(
        r"\b(?:trigger|confirmation|confirm|entry|entries|enter|involved|involvement|sweep|sweeps|reject|rejection)\b",
        re.IGNORECASE,
    ),
    "STOP": re.compile(r"\b(?:stop loss|stop-loss|sl)\b", re.IGNORECASE),
    "TARGET": re.compile(r"\b(?:target|targets|highs|lows|draw on liquidity|dol)\b", re.IGNORECASE),
    "INVALIDATION_EXPIRY": re.compile(
        r"\b(?:invalid|invalidate|invalidation|fail|fails|failed|failure|expire|expires|expiry|until)\b",
        re.IGNORECASE,
    ),
    "SESSION_TIME_RULE": re.compile(
        r"\b(?:new york|london|asia|session|killzone|kill zone|midnight|open|opening)\b",
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


def persist_page(cache_root: Path | None, page: str, page_index: int, current_before: int | None, url: str) -> dict[str, str]:
    payload = page.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    file_name = ""
    if cache_root is not None:
        cache_root.mkdir(parents=True, exist_ok=True)
        label = "root" if current_before is None else str(current_before)
        file_name = f"page_{page_index:03d}_before_{label}_{digest[:16]}.html"
        (cache_root / file_name).write_bytes(payload)
    return {"url": url, "sha256": digest, "cache_file": file_name}


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
    current_before: int | None = None
    visited: set[int | None] = set()
    seen_ids: set[int] = set()
    pages: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    rows: list[dict] = []

    for page_index in range(args.max_pages):
        if current_before in visited:
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
            if source_id not in eligible:
                continue
            body = match.group("body")
            text = clean_text(body)
            if not text:
                continue

            term_hits = {
                label: list(pattern.finditer(text))
                for label, pattern in TERM_PATTERNS.items()
                if pattern.search(text)
            }
            if not term_hits:
                continue

            cue_hits = {
                field: list(pattern.finditer(text))
                for field, pattern in FIELD_CUES.items()
                if pattern.search(text)
            }
            excerpts: list[dict[str, str]] = []
            seen_excerpt: set[str] = set()

            for label, hits in term_hits.items():
                for hit in hits[:3]:
                    excerpt = bounded_excerpt(text, hit, args.max_words)
                    if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.casefold() not in seen_excerpt:
                        seen_excerpt.add(excerpt.casefold())
                        excerpts.append({"kind": "TERM", "label": label, "matched": hit.group(0), "excerpt": excerpt})

            for field, hits in cue_hits.items():
                for hit in hits[:2]:
                    excerpt = bounded_excerpt(text, hit, args.max_words)
                    if excerpt and not contains_pre_spec_outcome(excerpt) and excerpt.casefold() not in seen_excerpt:
                        seen_excerpt.add(excerpt.casefold())
                        excerpts.append({"kind": "FIELD_CUE", "label": field, "matched": hit.group(0), "excerpt": excerpt})
                    if len(excerpts) >= args.max_excerpts_per_message:
                        break
                if len(excerpts) >= args.max_excerpts_per_message:
                    break

            rows.append(
                {
                    "source_id": source_id,
                    "date": published_date(body),
                    "term_labels": sorted(term_hits),
                    "contains_equilibrium": "EQUILIBRIUM" in term_hits,
                    "contains_stop_run": "STOP_RUN" in term_hits,
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
        "schema_version": 1,
        "issue": 90,
        "predicate_id": "EQUILIBRIUM_STOP_RUN_CONTEXT",
        "lexical_terms": ["equilibrium", "stop run", "stop-run", "stoprun"],
        "eligible_captured_telegram_sources": len(eligible),
        "pages_fetched": len(pages),
        "messages_seen": len(seen_ids),
        "recovery_message_count": len(rows),
        "equilibrium_message_count": sum(1 for row in rows if row["contains_equilibrium"]),
        "stop_run_message_count": sum(1 for row in rows if row["contains_stop_run"]),
        "joint_message_count": sum(1 for row in rows if row["contains_equilibrium"] and row["contains_stop_run"]),
        "failures": failures,
        "archive_pages_sha256_bound": True,
        "shared_antibias_guard": True,
        "performance_data_consulted": False,
        "semantic_synthesis_performed": False,
        "archive_pages": pages,
        "messages": sorted(rows, key=lambda row: int(str(row["source_id"]).rsplit("_", 1)[-1])),
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "eligible": len(eligible),
                "pages": len(pages),
                "messages": len(rows),
                "equilibrium": report["equilibrium_message_count"],
                "stop_run": report["stop_run_message_count"],
                "joint": report["joint_message_count"],
                "failures": len(failures),
            },
            sort_keys=True,
        )
    )
    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
