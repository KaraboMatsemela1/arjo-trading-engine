#!/usr/bin/env python3
"""Generate machine-readable project state from canonical GitHub Issues.

This script is intentionally strategy-agnostic. It only interprets governance
metadata embedded in issue bodies and derives readiness/gate state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

META_RE = re.compile(r"<!--\s*project-meta\s*(.*?)\s*-->", re.DOTALL | re.IGNORECASE)
ALLOWED_STATES = {
    "BLOCKED",
    "READY",
    "CLAIMED",
    "IMPLEMENTING",
    "CI_PENDING",
    "REVIEW_PENDING",
    "COMPLETE",
}
CRITICAL_GATES = [
    "GOVERNANCE_BOOTSTRAP_COMPLETE",
    "SOURCE_UNIVERSE_DISCOVERED",
    "CORPUS_ACQUIRED",
    "CONCEPT_INVENTORY_READY",
    "EVIDENCE_REGISTRY_READY",
    "PREDICATE_MATRIX_READY",
    "SPEC_READY",
]


def parse_meta(body: str | None) -> dict[str, Any] | None:
    """Parse the repository's small line-oriented metadata contract."""
    match = META_RE.search(body or "")
    if not match:
        return None
    result: dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "DEPENDENCIES":
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid DEPENDENCIES JSON: {value}") from exc
            if not isinstance(parsed, list) or not all(isinstance(v, int) for v in parsed):
                raise ValueError("DEPENDENCIES must be a JSON array of issue numbers")
            result[key] = parsed
        else:
            result[key] = value
    return result


def fetch_issues(repo: str, token: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "arjo-trading-engine-project-state",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub issue fetch failed ({exc.code}): {detail}") from exc
        page_items = [item for item in payload if "pull_request" not in item]
        issues.extend(page_items)
        if len(payload) < 100:
            break
        page += 1
    return issues


def normalized_issue(issue: dict[str, Any]) -> dict[str, Any]:
    meta = parse_meta(issue.get("body"))
    return {
        "number": int(issue["number"]),
        "title": issue.get("title", ""),
        "url": issue.get("html_url", ""),
        "github_state": str(issue.get("state", "")).upper(),
        "meta": meta,
    }


def derive_state(issues: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [normalized_issue(issue) for issue in issues]
    indexed = {item["number"]: item for item in normalized}

    completed = {
        number
        for number, item in indexed.items()
        if item["meta"] and item["meta"].get("STATE") == "COMPLETE"
    }
    satisfied_gates = {"REPO_CREATED"}
    for item in normalized:
        meta = item["meta"]
        if not meta or meta.get("STATE") != "COMPLETE":
            continue
        output_gate = meta.get("OUTPUT_GATE")
        if output_gate and output_gate != "NONE":
            satisfied_gates.add(output_gate)

    issue_state: list[dict[str, Any]] = []
    for item in sorted(normalized, key=lambda value: value["number"]):
        meta = item["meta"]
        if not meta:
            issue_state.append({**item, "metadata_valid": False})
            continue
        dependencies = list(meta.get("DEPENDENCIES", []))
        dependencies_satisfied = all(dep in completed for dep in dependencies)
        entry_gate = meta.get("ENTRY_GATE", "")
        entry_gate_satisfied = entry_gate in satisfied_gates or entry_gate in {"", "NONE"}
        mechanically_ready = dependencies_satisfied and entry_gate_satisfied
        issue_state.append(
            {
                **item,
                "metadata_valid": meta.get("STATE") in ALLOWED_STATES,
                "dependencies_satisfied": dependencies_satisfied,
                "entry_gate_satisfied": entry_gate_satisfied,
                "mechanically_ready": mechanically_ready,
            }
        )

    first_unsatisfied = next((gate for gate in CRITICAL_GATES if gate not in satisfied_gates), None)
    current_gate = first_unsatisfied or "SPEC_READY"
    blockers = []
    for item in issue_state:
        meta = item.get("meta")
        if not meta:
            blockers.append(f"Issue #{item['number']} missing project metadata")
            continue
        if meta.get("STATE") == "BLOCKED":
            blockers.append(f"Issue #{item['number']} blocked: {item['title']}")

    return {
        "schema_version": 1,
        "project": os.environ.get("GITHUB_REPOSITORY", "arjo-trading-engine"),
        "current_gate": current_gate,
        "satisfied_gates": sorted(satisfied_gates),
        "spec_ready": "SPEC_READY" in satisfied_gates,
        "paper_execution_enabled": "PAPER_EXECUTION_ENABLED" in satisfied_gates,
        "live_execution_enabled": "LIVE_TRADING_AUTHORIZED" in satisfied_gates,
        "critical_path": CRITICAL_GATES,
        "issues": issue_state,
        "blocked_reasons": blockers,
        "owner_input_required": False,
    }


def render_status(state: dict[str, Any]) -> str:
    lines = [
        "# Project Status",
        "",
        "_Generated mechanically by `scripts/project_state.py`._",
        "",
        "## Current objective gate",
        "",
        f"`{state['current_gate']}`",
        "",
        "## Safety state",
        "",
        f"- `SPEC_READY`: `{str(state['spec_ready']).lower()}`",
        f"- `PAPER_EXECUTION_ENABLED`: `{str(state['paper_execution_enabled']).lower()}`",
        f"- `LIVE_EXECUTION_ENABLED`: `{str(state['live_execution_enabled']).lower()}`",
        "",
        "## Satisfied gates",
        "",
    ]
    lines.extend(f"- `{gate}`" for gate in state["satisfied_gates"])
    lines.extend(["", "## Issue queue", "", "| Issue | Type | State | Dependencies ready | Entry gate ready |", "|---|---|---|---|---|"])
    for item in state["issues"]:
        meta = item.get("meta") or {}
        lines.append(
            f"| #{item['number']} | {meta.get('TYPE', 'UNMANAGED')} | {meta.get('STATE', 'UNMANAGED')} | "
            f"{item.get('dependencies_satisfied', False)} | {item.get('entry_gate_satisfied', False)} |"
        )
    lines.extend(
        [
            "",
            "## Strategy implementation status",
            "",
            "**ALLOWED only when `SPEC_READY = true`.**" if state["spec_ready"] else "**PROHIBITED while `SPEC_READY = false`.**",
            "",
            "Progress is represented by objective gates only; arbitrary percentages are prohibited.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="project_state.json")
    parser.add_argument("--status-output", default="STATUS.md")
    parser.add_argument("--issues-json", help="Optional fixture file instead of GitHub API")
    args = parser.parse_args()

    if args.issues_json:
        with open(args.issues_json, "r", encoding="utf-8") as handle:
            issues = json.load(handle)
    else:
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GITHUB_TOKEN")
        if not repo or not token:
            print("GITHUB_REPOSITORY and GITHUB_TOKEN are required unless --issues-json is used", file=sys.stderr)
            return 2
        issues = fetch_issues(repo, token)

    try:
        state = derive_state(issues)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status_output = Path(args.status_output)
    status_output.parent.mkdir(parents=True, exist_ok=True)
    status_output.write_text(render_status(state), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
