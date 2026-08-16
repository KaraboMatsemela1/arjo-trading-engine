#!/usr/bin/env python3
"""Surface direct operational-looking evidence not represented by candidate predicates.

This is an omission detector, not a semantic classifier. Keyword cues only place a
concept into a review queue; they never create a predicate automatically.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

OPERATIONAL_CUE = re.compile(
    r"(?:\bentry\b|\btarget\b|\bdirection\b|\bhold\b|\bholds\b|\bfail\b|\bfailure\b|"
    r"\binvolved\b|\blook for\b|\bbuys?\b|\bsells?\b|\bshorts?\b|\blongs?\b|"
    r"\bstop run\b|\bresistance\b|\bgo lower\b|\bgo higher\b|\btrade\b)",
    re.IGNORECASE,
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="research/candidate_predicates.json")
    parser.add_argument("--evidence", default="research/evidence_registry.jsonl")
    parser.add_argument("--inventory-glob", default="research/concept_inventory*.jsonl")
    parser.add_argument("--output", default="research/candidate_selection_audit.json")
    args = parser.parse_args()

    candidate_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    represented = {
        str(concept)
        for candidate in candidate_data.get("candidates", [])
        for concept in candidate.get("concepts", [])
    }
    inventory_ids: set[str] = set()
    for path in sorted(Path().glob(args.inventory_glob)):
        inventory_ids.update(str(row["CONCEPT_ID"]) for row in read_jsonl(path))

    cue_ids: dict[str, list[str]] = defaultdict(list)
    cue_quotes: dict[str, list[str]] = defaultdict(list)
    for record in read_jsonl(Path(args.evidence)):
        if record.get("CONFIDENCE") != "DIRECT" or record.get("SUPPORTED_FIELD") != "CONCEPT_MENTION_OR_CONTEXT":
            continue
        quote = str(record.get("MINIMAL_QUOTE", ""))
        if not quote or not OPERATIONAL_CUE.search(quote):
            continue
        concept = str(record["SUPPORTED_CONCEPT"])
        cue_ids[concept].append(str(record["EVIDENCE_ID"]))
        if len(cue_quotes[concept]) < 3:
            cue_quotes[concept].append(quote)

    rows = []
    for concept in sorted(inventory_ids):
        rows.append(
            {
                "concept_id": concept,
                "represented_in_candidate": concept in represented,
                "operational_cue_evidence_ids": sorted(set(cue_ids.get(concept, []))),
                "bounded_examples": cue_quotes.get(concept, []),
                "review_state": (
                    "REPRESENTED"
                    if concept in represented
                    else "REVIEW_REQUIRED"
                    if cue_ids.get(concept)
                    else "NO_OPERATIONAL_CUE_IN_CURRENT_DIRECT_TEXT"
                ),
            }
        )

    unrepresented = [row for row in rows if row["review_state"] == "REVIEW_REQUIRED"]
    report = {
        "schema_version": 1,
        "method": "LEXICAL_OMISSION_AUDIT_ONLY",
        "semantic_classification_performed": False,
        "performance_data_consulted": False,
        "candidate_count": len(candidate_data.get("candidates", [])),
        "inventory_concept_count": len(inventory_ids),
        "represented_concept_count": len(represented),
        "unrepresented_operational_cue_count": len(unrepresented),
        "unrepresented_operational_cues": unrepresented,
        "concept_review": rows,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "inventory_concepts": len(inventory_ids),
                "represented_concepts": len(represented),
                "unrepresented_operational_cues": len(unrepresented),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
