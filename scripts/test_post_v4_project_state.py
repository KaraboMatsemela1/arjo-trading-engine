#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import project_state_final as final

EXPECTED_SUFFIX = [
    "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
    "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN",
    "V4_SHARP_TURN_TRIGGERS_READY",
    "V4_SHARP_TURN_PROFITABILITY_RESULT_READY",
    "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
]


def fake_base_state(satisfied: list[str]) -> dict:
    return {
        "satisfied_gates": list(satisfied),
        "project_complete": False,
        "completion_basis": None,
        "current_gate": "SPEC_READY",
    }


def derive_with(satisfied: list[str]) -> dict:
    original = final._BASE_DERIVE_STATE
    try:
        final._BASE_DERIVE_STATE = lambda issues: fake_base_state(satisfied)
        return final.derive_closed_state([])
    finally:
        final._BASE_DERIVE_STATE = original


def main() -> None:
    assert final.POST_SPEC_CRITICAL_GATES[-len(EXPECTED_SUFFIX):] == EXPECTED_SUFFIX
    assert final.TERMINAL_GATE == "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert final.COMPLETION_BASIS == "POST_V4_CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE"
    assert final.HISTORICAL_CURRENT_EVIDENCE_GATE == "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert final.HISTORICAL_CLOSURE_GATE == "PROJECT_CLOSED_EXISTING_EVIDENCE"

    old_terminal = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
    ])
    assert old_terminal["project_complete"] is False
    assert old_terminal["completion_basis"] is None
    assert old_terminal["historical_existing_evidence_closure"] is True
    assert old_terminal["historical_current_evidence_boundary"] is True

    v4_result_only = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
        "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN",
        "V4_SHARP_TURN_TRIGGERS_READY",
        "V4_SHARP_TURN_PROFITABILITY_RESULT_READY",
    ])
    assert v4_result_only["project_complete"] is False
    assert v4_result_only["completion_basis"] is None

    complete = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
        "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN",
        "V4_SHARP_TURN_TRIGGERS_READY",
        "V4_SHARP_TURN_PROFITABILITY_RESULT_READY",
        final.TERMINAL_GATE,
    ])
    assert complete["project_complete"] is True
    assert complete["completion_basis"] == final.COMPLETION_BASIS
    assert complete["current_gate"] == final.TERMINAL_GATE
    assert complete["historical_existing_evidence_closure"] is True
    assert complete["historical_current_evidence_boundary"] is True
    assert complete["optional_future_validation_gate"] == "V2_FUTURE_VALIDATION_COMPLETE"

    print("POST_V4_PROJECT_STATE_TERMINAL_REGRESSION_READY")


if __name__ == "__main__":
    main()
