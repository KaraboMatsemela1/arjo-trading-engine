#!/usr/bin/env python3
"""Enforce non-negotiable lifecycle gates against repository contents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FORBIDDEN_PRE_SPEC_DIRS = {
    "strategy",
    "strategies",
    "detector",
    "detectors",
    "backtest",
    "backtests",
    "backtester",
    "optimizer",
    "optimizers",
    "candidates",
}
EXECUTABLE_SUFFIXES = {".py", ".rs", ".ts", ".tsx", ".js", ".cs", ".go", ".java", ".cpp", ".c"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    root = Path(args.repo_root).resolve()
    errors: list[str] = []

    if state.get("live_execution_enabled"):
        errors.append("LIVE execution may never be autonomously enabled")

    if not state.get("spec_ready", False):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXECUTABLE_SUFFIXES:
                continue
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if ".git" in relative.parts:
                continue
            lowered_parts = {part.lower() for part in relative.parts[:-1]}
            forbidden = lowered_parts & FORBIDDEN_PRE_SPEC_DIRS
            if forbidden:
                errors.append(
                    f"Pre-SPEC_READY executable strategy path forbidden: {relative} "
                    f"(matched {sorted(forbidden)})"
                )

    if state.get("paper_execution_enabled"):
        authorizations = [
            item
            for item in state.get("issues", [])
            if (item.get("meta") or {}).get("TYPE") == "OWNER_AUTHORIZATION"
            and (item.get("meta") or {}).get("OUTPUT_GATE") == "PAPER_EXECUTION_ENABLED"
            and (item.get("meta") or {}).get("STATE") == "COMPLETE"
        ]
        if not authorizations:
            errors.append("PAPER_EXECUTION_ENABLED lacks completed OWNER_AUTHORIZATION issue")

    if errors:
        print("Gate-integrity validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Gate-integrity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
