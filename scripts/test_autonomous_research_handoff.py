#!/usr/bin/env python3
"""Regression checks for bounded autonomous research and governance handoffs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PR_TOKEN_CONTRACT = "secrets.ARJO_AUTOMATION_PR_TOKEN || secrets.GITHUB_TOKEN"
DISPATCH_HELPER = "scripts/dispatch_autonomous_validation.sh"


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
        "actions: write",
        "pull-requests: write",
        "gh pr create",
        "gh issue create",
        "Merge only after normal",
        PR_TOKEN_CONTRACT,
        DISPATCH_HELPER,
    )
    forbid(text, "gh pr merge", "gh merge", "enable-auto-merge", "--auto")


def check_project_state_publication() -> None:
    text = read("project-state.yml")
    require(
        text,
        "actions: write",
        "pull-requests: write",
        "group: project-state-publication",
        "cancel-in-progress: false",
        'branch="automation/project-state-current"',
        "git push --force-with-lease",
        "gh pr list",
        "gh pr create",
        "reviewed PR is open or refreshed",
        PR_TOKEN_CONTRACT,
        DISPATCH_HELPER,
    )
    forbid(
        text,
        "gh issue create",
        "gh pr merge",
        "gh merge",
        "enable-auto-merge",
        "--auto",
        "project-state-${GITHUB_RUN_ID}",
    )


def check_dispatch_helper() -> None:
    helper = (ROOT / DISPATCH_HELPER).read_text(encoding="utf-8")
    require(
        helper,
        "gh workflow run",
        "ci.yml",
        "dependency-validation.yml",
        "gate-integrity.yml",
        '--ref "$ref"',
    )
    ci = read("ci.yml")
    require(ci, "workflow_dispatch:")


def main() -> int:
    source_watch = read("new-source-detection.yml")
    require(
        source_watch,
        "research/source_registry.csv",
        "actions: write",
        "pull-requests: write",
        "gh pr create",
        PR_TOKEN_CONTRACT,
        DISPATCH_HELPER,
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

    check_project_state_publication()
    check_dispatch_helper()

    print(
        "autonomous handoff contracts valid: source watch -> corpus -> "
        "concept/evidence -> predicate, coalesced Project State PRs, "
        "dedicated PR credential fallback, and exact dispatched validation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
