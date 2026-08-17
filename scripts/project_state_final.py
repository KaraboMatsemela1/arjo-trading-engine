#!/usr/bin/env python3
"""Canonical project-state entrypoint for the closed Arjo research lifecycle.

The stable ``project_state.py`` parser/renderer is retained. This wrapper
extends the objective critical path through the completed V1/V2 engineering
work and terminates the current project at an explicit existing-evidence
closure gate. Untouched future V2 validation is preserved as optional future
research infrastructure, not as a blocker for this project's completion.
"""
from __future__ import annotations

import project_state

POST_SPEC_CRITICAL_GATES = [
    "PROTECTED_VALIDATION_PROTOCOL_FROZEN",
    "PROTECTED_VALIDATION_COMPLETE",
    "V2_REMEDIATION_DESIGN_READY",
    "V2_SPEC_FROZEN",
    "V2_FUTURE_VALIDATION_PROTOCOL_READY",
    "V2_CAUSAL_VALIDATION_PROTOCOL_READY",
    "V2_EXECUTION_MEASUREMENT_READY",
    "V2_FUTURE_VALIDATION_HARNESS_READY",
    "PROJECT_CLOSED_EXISTING_EVIDENCE",
]

TERMINAL_GATE = "PROJECT_CLOSED_EXISTING_EVIDENCE"
OPTIONAL_FUTURE_EXTENSION = "V2_FUTURE_VALIDATION_COMPLETE"
_BASE_DERIVE_STATE = project_state.derive_state


def install_final_critical_path() -> list[str]:
    """Append the post-SPEC lifecycle exactly once and return the path."""
    existing = list(project_state.CRITICAL_GATES)
    if existing[-len(POST_SPEC_CRITICAL_GATES) :] == POST_SPEC_CRITICAL_GATES:
        return existing
    overlap = set(existing) & set(POST_SPEC_CRITICAL_GATES)
    if overlap:
        raise RuntimeError(
            "base project_state critical path partially overlaps final gates: "
            + ", ".join(sorted(overlap))
        )
    project_state.CRITICAL_GATES = existing + POST_SPEC_CRITICAL_GATES
    return list(project_state.CRITICAL_GATES)


def derive_closed_state(issues: list[dict]) -> dict:
    """Derive state and preserve an explicit terminal gate after closure."""
    state = _BASE_DERIVE_STATE(issues)
    closed = TERMINAL_GATE in state["satisfied_gates"]
    state["project_complete"] = closed
    state["completion_basis"] = "EXISTING_EVIDENCE" if closed else None
    state["optional_future_validation_gate"] = OPTIONAL_FUTURE_EXTENSION
    if closed:
        # Base project_state historically falls back to SPEC_READY when every
        # critical gate is satisfied. A closed project must remain visibly
        # closed rather than appearing to regress to an earlier lifecycle gate.
        state["current_gate"] = TERMINAL_GATE
    return state


install_final_critical_path()
project_state.derive_state = derive_closed_state


if __name__ == "__main__":
    raise SystemExit(project_state.main())
