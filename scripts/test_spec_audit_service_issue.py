#!/usr/bin/env python3
"""Regression checks for shell-safe SPEC-audit service issue publication."""

from __future__ import annotations

from build_spec_audit_service_issue import build_body


def main() -> int:
    branch = "automation/spec-audit-12345"
    body = build_body(branch=branch, run_id="12345")

    assert f"Service generated branch: `{branch}`" in body
    assert "inspect `spec_ready` and `overall_outcome`" in body
    assert "ISSUE_ID: ARJO-AUTO-SPEC-AUDIT-12345" in body
    assert "OUTPUT_GATE: NONE" in body
    assert "STATE: READY" in body

    # Backticks are deliberately literal Markdown. The workflow must pass this
    # body via --body-file rather than evaluating it inside a shell string.
    assert body.count("`") >= 6

    for branch_value, run_id in (("", "123"), ("branch", "")):
        try:
            build_body(branch=branch_value, run_id=run_id)
        except ValueError:
            pass
        else:
            raise AssertionError("empty branch/run_id must fail closed")

    print("SPEC audit service issue publication tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
