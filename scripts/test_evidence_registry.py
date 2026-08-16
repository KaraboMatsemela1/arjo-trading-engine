#!/usr/bin/env python3
"""Offline smoke test for evidence construction, quote bounds and anti-bias filtering."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_evidence_registry import build_records, minimal_quote  # noqa: E402
from evidence_antibias import contains_pre_spec_outcome  # noqa: E402


def main() -> int:
    inventory = [
        {
            "CONCEPT_ID": "TEST_CONCEPT",
            "SOURCE_IDS": ["TG_ARJOIOTRADING_1"],
            "AMBIGUITIES": ["Exact deterministic construction is unresolved."],
        }
    ]
    terms = {"TEST_CONCEPT": {"aliases": ["Test Concept"]}}
    dates = {"TG_ARJOIOTRADING_1": "2026-01-01"}
    messages = {
        "TG_ARJOIOTRADING_1": "Before context Test Concept appears here with additional words after it."
    }
    records = build_records(inventory, terms, dates, messages)
    if len(records) != 2:
        raise SystemExit(f"expected 2 records, got {len(records)}")
    mention = next(
        row for row in records if row["SUPPORTED_FIELD"] == "CONCEPT_MENTION_OR_CONTEXT"
    )
    gap = next(
        row for row in records if row["SUPPORTED_FIELD"] == "DETERMINISTIC_CONSTRUCTION"
    )
    assert mention["CONFIDENCE"] == "DIRECT"
    assert "Test Concept" in mention["MINIMAL_QUOTE"]
    assert len(mention["MINIMAL_QUOTE"].split()) <= 18
    assert gap["CONFIDENCE"] == "INSUFFICIENT"
    assert "unresolved" in gap["WHAT_IT_DOES_NOT_PROVE"]

    quote, alias = minimal_quote("alpha beta gamma Long Alias delta epsilon", ["Long Alias"])
    assert alias == "Long Alias"
    assert "Long Alias" in quote
    assert len(quote.split()) <= 18

    # A percentage-contaminated occurrence must be skipped for a later clean occurrence.
    quote, alias = minimal_quote(
        "Test Concept showed 72% in this old outcome note. Later clean context uses Test Concept for study only.",
        ["Test Concept"],
    )
    assert alias == "Test Concept"
    assert "72%" not in quote
    assert "Later clean context" in quote

    # Explicit winner/loser outcome language is also prohibited before SPEC_READY.
    quote, alias = minimal_quote(
        "Test Concept gave 2 winners this week. Later clean context uses Test Concept for study only.",
        ["Test Concept"],
    )
    assert alias == "Test Concept"
    assert "winners" not in quote.lower()
    assert "Later clean context" in quote

    # If every occurrence is contaminated, extraction must downgrade to no safe quote.
    quote, alias = minimal_quote("Test Concept had 72% outcomes.", ["Test Concept"])
    assert quote == ""
    assert alias == ""
    quote, alias = minimal_quote("Test Concept produced a winner.", ["Test Concept"])
    assert quote == ""
    assert alias == ""

    # Strategy-semantic stop-loss language must remain available to later evidence work.
    assert not contains_pre_spec_outcome("The stop loss sits below the structural low.")
    assert contains_pre_spec_outcome("I took 2 winners this week.")
    assert contains_pre_spec_outcome("We lost 3 trades yesterday.")

    print("Evidence registry smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
