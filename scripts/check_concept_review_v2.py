#!/usr/bin/env python3
"""Validate full captured-corpus concept review and candidate dispositions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_inventory(pattern: str) -> set[str]:
    ids: set[str] = set()
    for path in sorted(Path().glob(pattern)):
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                concept_id = str(json.loads(raw)["CONCEPT_ID"])
                if concept_id in ids:
                    raise ValueError(f"duplicate inventory concept: {concept_id}")
                ids.add(concept_id)
    if not ids:
        raise ValueError(f"no inventory records match {pattern}")
    return ids


def load_dispositions(path: Path) -> tuple[set[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("semantic_synthesis_performed") is not False:
        errors.append("candidate disposition file must not synthesize semantics")
    all_candidates: set[str] = set()
    for state, values in data.get("dispositions", {}).items():
        if state not in {
            "ADDED_TO_INVENTORY", "EXISTING_ALIAS",
            "INSUFFICIENT_CONTEXT_NOT_INVENTORIED", "NON_STRATEGY_NOISE",
        }:
            errors.append(f"invalid disposition state {state}")
        for value in values:
            if value in all_candidates:
                errors.append(f"candidate appears in multiple dispositions: {value}")
            all_candidates.add(str(value))
    if data.get("source_audit_candidate_count") != len(all_candidates):
        errors.append(
            f"declared candidate count {data.get('source_audit_candidate_count')} != dispositioned {len(all_candidates)}"
        )
    return all_candidates, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--inventory-glob", default="research/concept_inventory*.jsonl")
    parser.add_argument("--dispositions", default="research/review/lexical_candidate_dispositions.json")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        inventory_ids = load_inventory(args.inventory_glob)
        dispositioned, disposition_errors = load_dispositions(Path(args.dispositions))
        errors.extend(disposition_errors)
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    candidate_report = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    term_rows = {str(row["concept_id"]): row for row in review.get("terms", [])}

    if review.get("semantic_synthesis_performed") is not False:
        errors.append("lexical review must not synthesize semantics")
    if candidate_report.get("semantic_synthesis_performed") is not False:
        errors.append("candidate report must not synthesize semantics")
    if review.get("failures"):
        errors.append(f"archive retrieval failures present: {review['failures']}")
    if review.get("missing_eligible_count") != 0:
        errors.append(f"captured Telegram sources missing from live review: {review.get('missing_eligible_count')}")
    if review.get("unregistered_live_count") != 0:
        errors.append(f"live first-party posts exist outside acquired corpus: {review.get('unregistered_live_count')}")
    if review.get("messages_reviewed") != review.get("eligible_captured_messages"):
        errors.append(
            "observed eligible count does not equal captured eligible count: "
            f"{review.get('messages_reviewed')} != {review.get('eligible_captured_messages')}"
        )
    if review.get("text_messages_reviewed", 0) + review.get("textless_eligible_count", 0) != review.get("messages_reviewed"):
        errors.append("text + textless accounting does not equal observed eligible corpus")

    missing_terms = sorted(inventory_ids - set(term_rows))
    extra_terms = sorted(set(term_rows) - inventory_ids)
    if missing_terms:
        errors.append(f"inventory concepts absent from term review: {missing_terms}")
    if extra_terms:
        errors.append(f"term catalog contains concepts absent from inventory: {extra_terms}")

    zero_required = sorted(
        concept_id for concept_id, row in term_rows.items()
        if row.get("lexical_hit_required", True) and int(row.get("message_count", 0)) == 0
    )
    if zero_required:
        errors.append(f"lexical-hit-required concepts have zero hits: {zero_required}")

    actual_candidates = {str(row["candidate"]) for row in candidate_report.get("candidates", [])}
    missing_dispositions = sorted(actual_candidates - dispositioned)
    stale_dispositions = sorted(dispositioned - actual_candidates)
    if missing_dispositions:
        errors.append(f"undispositioned lexical candidates: {missing_dispositions}")
    if stale_dispositions:
        errors.append(f"dispositions no longer present in regenerated audit: {stale_dispositions}")

    if errors:
        print("Concept review completeness failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "captured_messages": review["eligible_captured_messages"],
        "observed_messages": review["messages_reviewed"],
        "text_messages": review["text_messages_reviewed"],
        "textless_messages": review["textless_eligible_count"],
        "inventory_concepts": len(inventory_ids),
        "lexical_candidates": len(actual_candidates),
        "candidate_dispositions": len(dispositioned),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
