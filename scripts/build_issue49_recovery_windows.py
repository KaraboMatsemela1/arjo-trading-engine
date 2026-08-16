#!/usr/bin/env python3
"""Build copyright-bounded lexical windows from directly captured Issue #49 targets.

This is a locator/evidence-recovery aid only. It does not assign predicate field
states or synthesize semantics. Only PAYLOAD_CAPTURED first-party attempts are
read, and excerpts are capped at 20 whitespace-delimited words.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from evidence_antibias import contains_pre_spec_outcome

TERMS = [
    "PD Array", "PD Arrays", "Premium Array", "Discount Array", "No Resistance",
    "No Resistance Area", "resistance", "hold", "holds", "holding", "fail", "fails",
    "failed", "failure", "respect", "disrespect", "Candle Science", "2 Candle Rejection",
    "2CR", "rejection", "trigger", "entry", "enter", "involved", "involvement",
    "confirmation", "direction", "bullish", "bearish", "buy", "sell", "long", "short",
    "stop loss", "target", "invalid", "invalidation", "expiry", "session", "4h", "1h",
    "15m", "5m", "higher timeframe", "lower timeframe", "HTF", "LTF",
]
META_TEXT_KEYS = {"description", "og:description", "twitter:description", "og:title", "twitter:title"}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if lower_tag != "meta":
            return
        attr_map = {str(key).lower(): value for key, value in attrs if value is not None}
        key = str(attr_map.get("property") or attr_map.get("name") or "").lower()
        content = str(attr_map.get("content") or "").strip()
        if key in META_TEXT_KEYS and content:
            self.parts.append(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def to_text(payload: bytes, content_type: str) -> str:
    decoded = payload.decode("utf-8", errors="replace")
    if "html" not in content_type.lower() and "<html" not in decoded.lower():
        return re.sub(r"\s+", " ", decoded).strip()
    parser = TextExtractor()
    parser.feed(decoded)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def bounded_window(text: str, match: re.Match[str], max_words: int) -> str:
    before = text[: match.start()].split()
    hit = text[match.start() : match.end()].split()
    after = text[match.end() :].split()
    left_budget = min(7, max(0, max_words - len(hit)))
    right_budget = max(0, max_words - len(hit) - left_budget)
    return " ".join(before[-left_budget:] + hit + after[:right_budget]).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-words", type=int, default=20)
    parser.add_argument("--max-windows-per-source", type=int, default=16)
    args = parser.parse_args()

    records = read_jsonl(Path(args.manifest))
    cache_root = Path(args.cache_root)
    sources: list[dict] = []
    total_windows = 0

    for record in sorted(records, key=lambda row: str(row.get("source_id", ""))):
        row = {
            "source_id": record.get("source_id"),
            "source_type": record.get("source_type"),
            "source_url": record.get("source_url"),
            "status": record.get("status"),
            "closure_credit": record.get("closure_credit"),
            "sha256": record.get("sha256", ""),
            "windows": [],
            "semantic_synthesis_performed": False,
        }
        if record.get("status") != "PAYLOAD_CAPTURED" or record.get("closure_credit") != "DIRECT_FIRST_PARTY_PAYLOAD":
            sources.append(row)
            continue

        texts: list[str] = []
        for artifact in record.get("artifacts", []):
            rel = str(artifact.get("content_address", ""))
            path = cache_root / rel
            if rel and path.exists():
                texts.append(to_text(path.read_bytes(), str(artifact.get("content_type", ""))))
        text = re.sub(r"\s+", " ", " ".join(texts)).strip()
        seen: set[tuple[str, str]] = set()
        for term in TERMS:
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)
            for match in pattern.finditer(text):
                excerpt = bounded_window(text, match, args.max_words)
                if not excerpt or contains_pre_spec_outcome(excerpt):
                    continue
                key = (term.casefold(), excerpt.casefold())
                if key in seen:
                    continue
                seen.add(key)
                row["windows"].append({"matched_term": term, "excerpt": excerpt})
                if len(row["windows"]) >= args.max_windows_per_source:
                    break
            if len(row["windows"]) >= args.max_windows_per_source:
                break
        total_windows += len(row["windows"])
        sources.append(row)

    report = {
        "schema_version": 1,
        "issue": 49,
        "predicate_id": "PD_ARRAY_2CR_FAILURE_INVOLVEMENT",
        "semantic_synthesis_performed": False,
        "performance_data_consulted": False,
        "shared_antibias_guard": True,
        "max_excerpt_words": args.max_words,
        "source_count": len(sources),
        "captured_source_count": sum(1 for row in sources if row["status"] == "PAYLOAD_CAPTURED"),
        "window_count": total_windows,
        "sources": sources,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(sources), "captured": report["captured_source_count"], "windows": total_windows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
