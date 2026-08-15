#!/usr/bin/env python3
"""Validate dependency graph and active issue readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ACTIVE_STATES = {"READY", "CLAIMED", "IMPLEMENTING", "CI_PENDING", "REVIEW_PENDING"}
REQUIRED_META = {"ISSUE_ID", "TYPE", "DEPENDENCIES", "ENTRY_GATE", "OUTPUT_GATE", "OWNER", "STATE"}


def load_state(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def detect_cycle(graph: dict[int, list[int]]) -> list[int] | None:
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(node: int, stack: list[int]) -> list[int] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for dep in graph.get(node, []):
            cycle = visit(dep, stack)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node, [])
        if cycle:
            return cycle
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    args = parser.parse_args()
    state = load_state(args.state)
    issues = state.get("issues", [])
    indexed = {int(item["number"]): item for item in issues}
    errors: list[str] = []
    graph: dict[int, list[int]] = {}

    for item in issues:
        number = int(item["number"])
        meta = item.get("meta")
        if not meta:
            errors.append(f"Issue #{number} is missing project-meta")
            continue
        missing = sorted(REQUIRED_META - set(meta))
        if missing:
            errors.append(f"Issue #{number} missing metadata fields: {', '.join(missing)}")
            continue
        deps = list(meta.get("DEPENDENCIES", []))
        graph[number] = deps
        if number in deps:
            errors.append(f"Issue #{number} depends on itself")
        for dep in deps:
            if dep not in indexed:
                errors.append(f"Issue #{number} references missing dependency #{dep}")

        current = meta.get("STATE")
        if current in ACTIVE_STATES and current != "READY":
            if not item.get("dependencies_satisfied", False):
                errors.append(f"Issue #{number} is {current} with incomplete dependencies")
            if not item.get("entry_gate_satisfied", False):
                errors.append(f"Issue #{number} is {current} with unsatisfied entry gate {meta.get('ENTRY_GATE')}")
        if current == "READY" and not item.get("mechanically_ready", False):
            errors.append(f"Issue #{number} is READY but dependencies or entry gate are not satisfied")

    cycle = detect_cycle(graph)
    if cycle:
        errors.append("Dependency cycle detected: " + " -> ".join(f"#{n}" for n in cycle))

    if errors:
        print("Dependency validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Dependency validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
