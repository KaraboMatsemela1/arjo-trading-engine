#!/usr/bin/env python3
"""Canonical project-state entrypoint for the completed V1/V2 lifecycle.

The original ``project_state.py`` parser/renderer is retained as the stable
implementation. This entrypoint extends only the objective critical-path gate
sequence so generated state cannot regress to treating ``SPEC_READY`` as the
current gate after protected validation and the V2 lifecycle have completed.
"""
from __future__ import annotations

import project_state

V2_CRITICAL_GATES = [
    "PROTECTED_VALIDATION_PROTOCOL_FROZEN",
    "PROTECTED_VALIDATION_COMPLETE",
    "V2_REMEDIATION_DESIGN_READY",
    "V2_SPEC_FROZEN",
    "V2_FUTURE_VALIDATION_PROTOCOL_READY",
    "V2_CAUSAL_VALIDATION_PROTOCOL_READY",
    "V2_EXECUTION_MEASUREMENT_READY",
    "V2_FUTURE_VALIDATION_HARNESS_READY",
    "V2_FUTURE_VALIDATION_COMPLETE",
]


def install_final_critical_path() -> list[str]:
    """Append the post-SPEC lifecycle exactly once and return the path."""
    existing = list(project_state.CRITICAL_GATES)
    if existing[-len(V2_CRITICAL_GATES) :] == V2_CRITICAL_GATES:
        return existing
    overlap = set(existing) & set(V2_CRITICAL_GATES)
    if overlap:
        raise RuntimeError(
            "base project_state critical path partially overlaps final V2 gates: "
            + ", ".join(sorted(overlap))
        )
    project_state.CRITICAL_GATES = existing + V2_CRITICAL_GATES
    return list(project_state.CRITICAL_GATES)


install_final_critical_path()


if __name__ == "__main__":
    raise SystemExit(project_state.main())
