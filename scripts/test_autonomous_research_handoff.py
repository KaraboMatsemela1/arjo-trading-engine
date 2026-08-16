#!/usr/bin/env python3
"""Regression checks for the bounded autonomous research handoff chain."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def require(text: str, *needles: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"missing workflow contract entries: {missing}")


def forbid(text: str, *needles: str) -> None:
    present = [needle for needle in needles if needle in text]
    if present:
        raise AssertionError(f"forbidden autonomous behavior present: {present}")


def check_reviewed_publication(name: str) -> None:
    text = read(name)
    require(
        text,
        "pull-requests: write",
        "gh pr create",
        "gh issue create",
        "Merge only after normal",
    )
    forbid(text, "gh pr merge", "gh merge", "enable-auto-merge", "--auto")


def main() -> int:
    source_watch = read("new-source-detection.yml")
    require(
        source_watch,
        "research/source_registry.csv",
        "pull-requests: write",
        "gh pr create",
    )
    forbid(source_watch, "gh pr merge", "gh merge", "enable-auto-merge", "--auto")

    corpus = read("corpus-acquisition.yml")
    require(corpus, "research/source_registry.csv")
    check_reviewed_publication("corpus-acquisition.yml")

    concept_review = read("concept-inventory-review.yml")
    require(
        concept_review,
        "research/source_registry.csv",
        "research/acquisition_manifest.jsonl",
    )

    evidence = read("evidence-extraction.yml")
    require(
        evidence,
        "research/source_registry.csv",
        "research/acquisition_manifest.jsonl",
    )
    check_reviewed_publication("evidence-extraction.yml")

    predicate = read("predicate-synthesis.yml")
    check_reviewed_publication("predicate-synthesis.yml")

    print(
        "autonomous research handoff contract valid: "
        "source watch -> corpus -> concept/evidence -> predicate; reviewed PRs only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
