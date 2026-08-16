#!/usr/bin/env python3
"""Build the bounded SPEC-audit service issue body without shell interpolation.

The workflow passes trusted scalar values as command-line arguments and writes the
Markdown body to a file consumed by ``gh issue create --body-file``. Markdown
content is never evaluated by the shell.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_body(*, branch: str, run_id: str) -> str:
    if not branch.strip():
        raise ValueError("branch is required")
    if not run_id.strip():
        raise ValueError("run_id is required")
    return f"""<!-- project-meta
ISSUE_ID: ARJO-AUTO-SPEC-AUDIT-{run_id}
TYPE: SPEC_AUDIT_SERVICE
DEPENDENCIES: [8]
ENTRY_GATE: PREDICATE_MATRIX_READY
OUTPUT_GATE: NONE
OWNER: UNCLAIMED
STATE: READY
-->

Independent evidence-only SPEC readiness audit completed and passed audit-invariant validation.

Service generated branch: `{branch}`

Open a PR to main and merge only if normal CI/provenance/SPEC guards remain green. A successful workflow does not imply SPEC_READY; inspect `spec_ready` and `overall_outcome` in the artifact.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_body(branch=args.branch, run_id=args.run_id), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
