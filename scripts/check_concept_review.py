#!/usr/bin/env python3
"""Validate that the lexical review covered the full captured Telegram corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True)
    parser.add_argument("--inventory", default="research/concept_inventory.jsonl")
    args = parser.parse_args()

    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    inventory_ids = {
        json.loads(raw)["CONCEPT_ID"]
        for raw in Path(args.inventory).read_text(encoding="utf-8").splitlines()
        if raw.strip()
    }
    term_rows = {row["concept_id"]: row for row in review.get("terms", [])}
    errors: list[str] = []

    if review.get("semantic_synthesis_performed") is not False:
        errors.append("lexical review must not synthesize semantics")
    if review.get("failures"):
        errors.append(f"archive retrieval failures present: {review['failures']}")
    if review.get("missing_eligible_count") != 0:
        errors.append(f"captured Telegram sources missing from live review: {review.get('missing_eligible_count')}")
    if review.get("unregistered_live_count") != 0:
        errors.append(
            f"live first-party posts exist outside the acquired corpus: {review.get('unregistered_live_count')}"
        )
    if review.get("messages_reviewed") != review.get("eligible_captured_messages"):
        errors.append(
            "reviewed message count does not equal eligible captured message count: "
            f"{review.get('messages_reviewed')} != {review.get('eligible_captured_messages')}"
        )

    missing_inventory_terms = sorted(inventory_ids - set(term_rows))
    if missing_inventory_terms:
        errors.append(f"inventory concepts absent from term review: {missing_inventory_terms}")
    zero_hit = sorted(
        concept_id
        for concept_id in inventory_ids
        if concept_id in term_rows and int(term_rows[concept_id].get("message_count", 0)) == 0
    )
    if zero_hit:
        errors.append(f"catalogued concepts have zero lexical hits across captured corpus: {zero_hit}")

    if errors:
        print("Concept review completeness failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "messages_reviewed": review["messages_reviewed"],
                "catalog_concepts": len(term_rows),
                "inventory_concepts": len(inventory_ids),
                "unregistered_live": review["unregistered_live_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
