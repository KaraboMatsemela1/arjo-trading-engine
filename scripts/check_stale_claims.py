#!/usr/bin/env python3
"""Fail when an active project claim has not been updated within its lease."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from project_state import fetch_issues, parse_meta

ACTIVE = {"CLAIMED", "IMPLEMENTING", "CI_PENDING", "REVIEW_PENDING"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=float(os.environ.get("STALE_CLAIM_HOURS", "24")))
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    stale: list[str] = []
    active_count = 0
    for issue in fetch_issues(repo, token):
        meta = parse_meta(issue.get("body")) or {}
        issue_state = meta.get("STATE")
        if issue_state not in ACTIVE:
            continue
        active_count += 1
        updated_raw = issue.get("updated_at")
        if not updated_raw:
            stale.append(f"#{issue['number']} has no updated_at timestamp")
            continue
        updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
        age_hours = (now - updated).total_seconds() / 3600
        if age_hours > args.hours:
            stale.append(
                f"#{issue['number']} {issue_state} owned by {meta.get('OWNER')} is stale "
                f"({age_hours:.1f}h > {args.hours:.1f}h lease)"
            )

    if stale:
        print("Stale claim validation failed:", file=sys.stderr)
        for item in stale:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(f"Stale claim validation passed; {active_count} active claim(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
