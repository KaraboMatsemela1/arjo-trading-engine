#!/usr/bin/env python3
"""Build atomic first-party evidence records from concept-cited Telegram sources.

Evidence extraction is deliberately narrower than predicate synthesis. An exact
term mention proves only that the first-party source uses that concept/context; it
does not create an executable rule. Every concept ambiguity is separately emitted
as an INSUFFICIENT deterministic-construction record.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import re
import time
import urllib.error
from collections import defaultdict
from pathlib import Path

from discover_telegram_sources import ARCHIVE_URL, MESSAGE_RE, fetch, next_before
from evidence_antibias import contains_pre_spec_outcome

TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^\"]*"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def load_inventory(pattern: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(Path().glob(pattern)):
        rows.extend(read_jsonl(path))
    if not rows:
        raise ValueError(f"no inventory records match {pattern}")
    return rows


def load_terms(pattern: str) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for path in sorted(Path().glob(pattern)):
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("terms", []):
            concept_id = str(row["concept_id"])
            if concept_id in by_id:
                raise ValueError(f"duplicate term catalog concept_id {concept_id}")
            by_id[concept_id] = row
    return by_id


def clean_text(body: str) -> str:
    match = TEXT_RE.search(body)
    if not match:
        return ""
    value = BR_RE.sub(" ", match.group(1))
    value = TAG_RE.sub(" ", value)
    value = html_lib.unescape(value)
    value = URL_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_telegram_messages(
    eligible: set[str], max_pages: int, sleep_seconds: float
) -> tuple[dict[str, str], list[dict[str, str]]]:
    messages: dict[str, str] = {}
    failures: list[dict[str, str]] = []
    current_before: int | None = None
    visited: set[int | None] = set()
    seen_ids: set[int] = set()

    for _ in range(max_pages):
        if current_before in visited:
            break
        visited.add(current_before)
        url = ARCHIVE_URL if current_before is None else f"{ARCHIVE_URL}?before={current_before}"
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"url": url, "error": str(exc)})
            break
        page_ids: list[int] = []
        for match in MESSAGE_RE.finditer(page):
            message_id = int(match.group(1))
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            page_ids.append(message_id)
            source_id = f"TG_ARJOIOTRADING_{message_id}"
            if source_id in eligible:
                messages[source_id] = clean_text(match.group("body"))
        candidate = next_before(page, current_before, page_ids)
        if candidate is None:
            break
        current_before = candidate
        time.sleep(max(sleep_seconds, 0.0))
    return messages, failures


def minimal_quote(text: str, aliases: list[str], max_words: int = 18) -> tuple[str, str]:
    """Return the first alias-centered quote window with no pre-SPEC outcome data."""

    aliases = sorted({alias.strip() for alias in aliases if alias.strip()}, key=len, reverse=True)
    for alias in aliases:
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", re.IGNORECASE)
        for match in pattern.finditer(text):
            prefix = text[: match.start()].split()
            hit = text[match.start() : match.end()].split()
            suffix = text[match.end() :].split()
            left = prefix[-5:]
            right_budget = max(0, max_words - len(left) - len(hit))
            right = suffix[:right_budget]
            quote = " ".join([*left, *hit, *right]).strip()[:180]
            if contains_pre_spec_outcome(quote):
                continue
            return quote, alias
    return "", ""


def evidence_id(source_id: str, concept_id: str, field: str, ordinal: int = 0) -> str:
    seed = f"{source_id}|{concept_id}|{field}|{ordinal}".encode()
    return "EV_" + hashlib.sha256(seed).hexdigest()[:24].upper()


def build_records(
    inventory: list[dict],
    terms: dict[str, dict],
    source_dates: dict[str, str],
    messages: dict[str, str],
) -> list[dict]:
    records: list[dict] = []
    for concept in sorted(inventory, key=lambda row: str(row["CONCEPT_ID"])):
        concept_id = str(concept["CONCEPT_ID"])
        term = terms.get(concept_id, {})
        aliases = [str(value) for value in term.get("aliases", [])]
        source_ids = list(dict.fromkeys(str(value) for value in concept.get("SOURCE_IDS", [])))

        for ordinal, source_id in enumerate(source_ids):
            text = messages.get(source_id, "")
            quote, matched_alias = minimal_quote(text, aliases)
            confidence = "DIRECT" if quote else "INSUFFICIENT"
            records.append(
                {
                    "EVIDENCE_ID": evidence_id(source_id, concept_id, "CONCEPT_MENTION_OR_CONTEXT", ordinal),
                    "SOURCE_ID": source_id,
                    "TIMESTAMP": source_dates.get(source_id, ""),
                    "MINIMAL_QUOTE": quote,
                    "FRAME_LOCATOR": (
                        f"TELEGRAM_MESSAGE:{source_id.removeprefix('TG_ARJOIOTRADING_')}:TEXT"
                        if quote
                        else f"TELEGRAM_MESSAGE:{source_id.removeprefix('TG_ARJOIOTRADING_')}:NO_SAFE_TEXT_MATCH"
                    ),
                    "SUPPORTED_CONCEPT": concept_id,
                    "SUPPORTED_FIELD": "CONCEPT_MENTION_OR_CONTEXT",
                    "WHAT_IT_PROVES": (
                        f"Direct first-party source explicitly uses '{matched_alias}' in context for {concept_id}."
                        if quote
                        else f"The provenance-bound source is cited for {concept_id}, but this extractor cannot recover a pre-SPEC-safe matching text window."
                    ),
                    "WHAT_IT_DOES_NOT_PROVE": "It does not by itself establish a complete deterministic trading predicate, parameter set, invalidation, expiry, or performance claim.",
                    "CONFIDENCE": confidence,
                }
            )

        ambiguities = [str(value) for value in concept.get("AMBIGUITIES", []) if str(value).strip()]
        if ambiguities and source_ids:
            source_id = source_ids[0]
            text = messages.get(source_id, "")
            quote, _ = minimal_quote(text, aliases)
            records.append(
                {
                    "EVIDENCE_ID": evidence_id(source_id, concept_id, "DETERMINISTIC_CONSTRUCTION", 0),
                    "SOURCE_ID": source_id,
                    "TIMESTAMP": source_dates.get(source_id, ""),
                    "MINIMAL_QUOTE": quote,
                    "FRAME_LOCATOR": (
                        f"TELEGRAM_MESSAGE:{source_id.removeprefix('TG_ARJOIOTRADING_')}:TEXT"
                        if quote
                        else f"TELEGRAM_MESSAGE:{source_id.removeprefix('TG_ARJOIOTRADING_')}:NO_SAFE_TEXT_MATCH"
                    ),
                    "SUPPORTED_CONCEPT": concept_id,
                    "SUPPORTED_FIELD": "DETERMINISTIC_CONSTRUCTION",
                    "WHAT_IT_PROVES": "The cited first-party material establishes concept existence/context only to the stated inventory level.",
                    "WHAT_IT_DOES_NOT_PROVE": "It does not establish: " + ambiguities[0],
                    "CONFIDENCE": "INSUFFICIENT",
                }
            )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-glob", default="research/concept_inventory*.jsonl")
    parser.add_argument("--terms-glob", default="research/concept_terms*.json")
    parser.add_argument("--registry", default="research/source_registry.csv")
    parser.add_argument("--acquisition", default="research/acquisition_manifest.jsonl")
    parser.add_argument("--messages-json")
    parser.add_argument("--output", default="research/evidence_registry.jsonl")
    parser.add_argument("--coverage", default="research/evidence_coverage.json")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    args = parser.parse_args()

    inventory = load_inventory(args.inventory_glob)
    terms = load_terms(args.terms_glob)
    with Path(args.registry).open(newline="", encoding="utf-8") as handle:
        source_rows = {row["SOURCE_ID"]: row for row in csv.DictReader(handle) if row.get("SOURCE_ID")}
    source_dates = {source_id: row.get("PUBLICATION_DATE", "") for source_id, row in source_rows.items()}
    acquisition = {str(row.get("source_id", "")): row for row in read_jsonl(Path(args.acquisition))}

    cited_sources = {str(source_id) for concept in inventory for source_id in concept.get("SOURCE_IDS", [])}
    eligible = {
        source_id
        for source_id in cited_sources
        if source_id.startswith("TG_ARJOIOTRADING_")
        and acquisition.get(source_id, {}).get("status") == "PAYLOAD_CAPTURED"
        and acquisition.get(source_id, {}).get("first_party_contacted") is True
        and acquisition.get(source_id, {}).get("closure_credit") == "DIRECT_FIRST_PARTY_PAYLOAD"
        and acquisition.get(source_id, {}).get("sha256")
    }

    if args.messages_json:
        messages = json.loads(Path(args.messages_json).read_text(encoding="utf-8"))
        failures: list[dict[str, str]] = []
    else:
        messages, failures = fetch_telegram_messages(eligible, args.max_pages, args.sleep_seconds)

    records = build_records(inventory, terms, source_dates, messages)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records
        )
        + "\n",
        encoding="utf-8",
    )

    concept_ids = {str(row["CONCEPT_ID"]) for row in inventory}
    covered = {str(row["SUPPORTED_CONCEPT"]) for row in records}
    direct_mentions = defaultdict(int)
    insufficient_construction = set()
    for row in records:
        if (
            row["SUPPORTED_FIELD"] == "CONCEPT_MENTION_OR_CONTEXT"
            and row["CONFIDENCE"] != "INSUFFICIENT"
        ):
            direct_mentions[row["SUPPORTED_CONCEPT"]] += 1
        if (
            row["SUPPORTED_FIELD"] == "DETERMINISTIC_CONSTRUCTION"
            and row["CONFIDENCE"] == "INSUFFICIENT"
        ):
            insufficient_construction.add(row["SUPPORTED_CONCEPT"])

    coverage = {
        "schema_version": 1,
        "concept_count": len(concept_ids),
        "evidence_record_count": len(records),
        "covered_concept_count": len(covered),
        "concepts_with_direct_text_evidence": len(direct_mentions),
        "concepts_with_explicit_construction_gap": len(insufficient_construction),
        "cited_source_count": len(cited_sources),
        "eligible_direct_cited_source_count": len(eligible),
        "messages_recovered": len(messages),
        "retrieval_failures": failures,
        "missing_concepts": sorted(concept_ids - covered),
        "semantic_synthesis_performed": False,
    }
    Path(args.coverage).write_text(
        json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(coverage, sort_keys=True))
    return 4 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
