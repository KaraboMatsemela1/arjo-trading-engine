#!/usr/bin/env python3
"""Ensure SPEC_READY cannot be asserted without an explicit audit artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_AUDIT_FIELDS = {
    "predicate_id",
    "outcome",
    "all_required_fields_satisfied",
    "contradictions_resolved",
    "provenance_complete",
    "two_engineer_test",
    "independent_reconstruction",
    "frozen_spec_ref",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    parser.add_argument("--audit", default="docs/spec/SPEC_READY.json")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    if not state.get("spec_ready", False):
        print("SPEC_READY is false; audit artifact not yet required")
        return 0

    audit_path = Path(args.audit)
    if not audit_path.exists():
        print(f"SPEC_READY asserted without audit artifact: {audit_path}", file=sys.stderr)
        return 1

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    missing = REQUIRED_AUDIT_FIELDS - set(audit)
    if missing:
        print(f"SPEC_READY audit artifact missing fields: {sorted(missing)}", file=sys.stderr)
        return 1

    checks = {
        "outcome": audit["outcome"] == "PASS",
        "all_required_fields_satisfied": audit["all_required_fields_satisfied"] is True,
        "contradictions_resolved": audit["contradictions_resolved"] is True,
        "provenance_complete": audit["provenance_complete"] is True,
        "two_engineer_test": audit["two_engineer_test"] == "PASS",
        "independent_reconstruction": audit["independent_reconstruction"] == "PASS",
        "frozen_spec_ref": bool(audit["frozen_spec_ref"]),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print(f"SPEC_READY audit failed required checks: {failed}", file=sys.stderr)
        return 1

    print(f"SPEC_READY audit artifact valid for predicate {audit['predicate_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
