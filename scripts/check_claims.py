#!/usr/bin/env python3
"""Enforce the repository's bounded work-in-flight claim invariant."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

IMPLEMENTATION = {"CLAIMED", "IMPLEMENTING"}
WAITING = {"CI_PENDING", "REVIEW_PENDING"}
ACTIVE = IMPLEMENTATION | WAITING


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    args = parser.parse_args()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))

    active = []
    errors: list[str] = []
    for item in state.get("issues", []):
        meta = item.get("meta") or {}
        issue_state = meta.get("STATE")
        if issue_state in ACTIVE:
            active.append(item)
            if meta.get("OWNER") in {None, "", "UNCLAIMED"}:
                errors.append(f"Issue #{item['number']} is {issue_state} without a claim owner")

    implementing = [item for item in active if (item.get("meta") or {}).get("STATE") in IMPLEMENTATION]
    waiting = [item for item in active if (item.get("meta") or {}).get("STATE") in WAITING]

    if len(active) > 2:
        errors.append(f"Too many active claims: {len(active)} (maximum 2)")
    if len(implementing) > 1:
        errors.append("More than one active implementation lane exists")
    if len(active) == 2 and not (len(implementing) == 1 and len(waiting) == 1):
        errors.append("Two active claims are permitted only as one implementation lane plus one external-wait lane")

    if errors:
        print("Claim validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    summary = ", ".join(
        f"#{item['number']}:{(item.get('meta') or {}).get('STATE')}" for item in active
    ) or "none"
    print(f"Claim validation passed; active claims: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
