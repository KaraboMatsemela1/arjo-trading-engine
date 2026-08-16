#!/usr/bin/env python3
"""Classify first-party discovery watch deltas without semantic interpretation.

The durable watch state intentionally contains only transport/discovery status.
Titles, snippets, metadata, access status, and search results receive zero semantic
closure credit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SURFACES = ("youtube", "telegram", "website")


def classify_exit_code(code: int) -> str:
    return {
        0: "CLEAN_DISCOVERY",
        2: "NO_DISCOVERY_PAYLOAD",
        4: "PARTIAL_DISCOVERY_DEGRADATION",
    }.get(code, "UNEXPECTED_EXIT_CODE")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def normalized_exit_codes(report: dict[str, Any]) -> dict[str, int]:
    raw = report.get("surface_exit_codes")
    if not isinstance(raw, dict):
        raise ValueError("incremental report missing surface_exit_codes object")
    missing = [surface for surface in SURFACES if surface not in raw]
    if missing:
        raise ValueError(f"incremental report missing exit codes: {missing}")
    return {surface: int(raw[surface]) for surface in SURFACES}


def build_watch_state(report: dict[str, Any]) -> dict[str, Any]:
    exit_codes = normalized_exit_codes(report)
    return {
        "schema_version": 1,
        "surface_exit_codes": exit_codes,
        "surface_states": {
            surface: classify_exit_code(exit_codes[surface]) for surface in SURFACES
        },
        "semantic_closure_performed": False,
        "search_or_metadata_semantic_credit": "ZERO",
    }


def build_decision(
    report: dict[str, Any],
    baseline_state: dict[str, Any],
    current_state: dict[str, Any],
) -> dict[str, Any]:
    new_source_count = int(report.get("new_source_count", 0))
    if new_source_count < 0:
        raise ValueError("new_source_count cannot be negative")

    baseline_codes = baseline_state.get("surface_exit_codes")
    baseline_missing = not isinstance(baseline_codes, dict)
    previous_codes = None
    if not baseline_missing:
        previous_codes = {surface: int(baseline_codes.get(surface, -1)) for surface in SURFACES}

    current_codes = current_state["surface_exit_codes"]
    access_state_changed = baseline_missing or previous_codes != current_codes

    reasons: list[str] = []
    if new_source_count:
        reasons.append("NEW_FIRST_PARTY_SOURCE_URLS")
    if baseline_missing:
        reasons.append("ACCESS_BASELINE_MISSING")
    elif access_state_changed:
        reasons.append("ACCESS_STATE_CHANGED")

    return {
        "schema_version": 1,
        "new_source_count": new_source_count,
        "access_state_changed": access_state_changed,
        "baseline_missing": baseline_missing,
        "previous_surface_exit_codes": previous_codes,
        "current_surface_exit_codes": current_codes,
        "should_publish": bool(reasons),
        "publication_reasons": reasons,
        "semantic_closure_performed": False,
        "search_or_metadata_semantic_credit": "ZERO",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incremental-report", required=True)
    parser.add_argument("--baseline-state", required=True)
    parser.add_argument("--state-output", required=True)
    parser.add_argument("--decision-output", required=True)
    args = parser.parse_args()

    report = load_json(Path(args.incremental_report))
    baseline = load_json(Path(args.baseline_state))
    current_state = build_watch_state(report)
    decision = build_decision(report, baseline, current_state)

    Path(args.state_output).write_text(
        json.dumps(current_state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.decision_output).write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
