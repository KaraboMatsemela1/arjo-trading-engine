#!/usr/bin/env python3
"""Select the next dependency-safe READY execution issue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    args = parser.parse_args()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))

    candidates = []
    for item in state.get("issues", []):
        meta = item.get("meta") or {}
        if meta.get("TYPE") == "MASTER":
            continue
        if meta.get("STATE") != "READY":
            continue
        if not item.get("mechanically_ready", False):
            continue
        candidates.append(item)

    if not candidates:
        print(json.dumps({"next_issue": None, "reason": "NO_DEPENDENCY_SAFE_READY_ISSUE"}))
        return 3

    candidates.sort(key=lambda item: int(item["number"]))
    chosen = candidates[0]
    print(
        json.dumps(
            {
                "next_issue": chosen["number"],
                "title": chosen["title"],
                "issue_id": (chosen.get("meta") or {}).get("ISSUE_ID"),
                "type": (chosen.get("meta") or {}).get("TYPE"),
                "entry_gate": (chosen.get("meta") or {}).get("ENTRY_GATE"),
                "output_gate": (chosen.get("meta") or {}).get("OUTPUT_GATE"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
