#!/usr/bin/env python3
"""Canonical project-state entrypoint for the completed Arjo research lifecycle.

The stable ``project_state.py`` parser/renderer is retained. This wrapper
extends the objective critical path through V1/V2 engineering, backward-OOS
profitability research, V3 outcome-blind coverage work, the sealed V3-C
economic result, and the final current-evidence research boundary.

The earlier ``PROJECT_CLOSED_EXISTING_EVIDENCE`` gate is retained as a
historical lifecycle milestone. It is no longer terminal because subsequent
profitability research was explicitly opened and completed. Untouched future
V2 validation remains optional future research infrastructure, not a blocker
for completion of the current-evidence project.
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
    "PROFITABILITY_VALIDATION_PROTOCOL_FROZEN",
    "PROFITABILITY_BACKWARD_OOS_OCCURRENCES_READY",
    "V3_COVERAGE_DIAGNOSIS_COMPLETE",
    "V3_MULTI_INDEX_COVERAGE_DIAGNOSIS_COMPLETE",
    "V3_ARGUMENTS_TRIGGER_COVERAGE_READY",
    "V3_ARGUMENTS_EXECUTION_PROTOCOL_FROZEN",
    "V3_ARGUMENTS_BACKWARD_OOS_TRIGGERS_READY",
    "V3_ARGUMENTS_PROFITABILITY_RESULT_READY",
    "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
]

HISTORICAL_CLOSURE_GATE = "PROJECT_CLOSED_EXISTING_EVIDENCE"
TERMINAL_GATE = "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
COMPLETION_BASIS = "CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE"
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
    """Derive state while preserving the explicit current-evidence terminal state."""
    state = _BASE_DERIVE_STATE(issues)
    complete = TERMINAL_GATE in state["satisfied_gates"]
    state["project_complete"] = complete
    state["completion_basis"] = COMPLETION_BASIS if complete else None
    state["historical_existing_evidence_closure"] = HISTORICAL_CLOSURE_GATE in state["satisfied_gates"]
    state["optional_future_validation_gate"] = OPTIONAL_FUTURE_EXTENSION
    if complete:
        # Base state historically falls back to SPEC_READY when every critical
        # gate is satisfied. A completed research lifecycle must remain visibly
        # at its actual terminal evidence boundary instead of regressing.
        state["current_gate"] = TERMINAL_GATE
    return state


install_final_critical_path()
project_state.derive_state = derive_closed_state


if __name__ == "__main__":
    raise SystemExit(project_state.main())
