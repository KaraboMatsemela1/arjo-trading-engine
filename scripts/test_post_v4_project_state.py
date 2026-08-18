#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import project_state_final as final

EXPECTED_POST_V4_SEQUENCE = [
    "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
    "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN",
    "V4_SHARP_TURN_TRIGGERS_READY",
    "V4_SHARP_TURN_PROFITABILITY_RESULT_READY",
    "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY",
    "V5_NO_RESISTANCE_AOO_PROTOCOL_FROZEN",
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
    start = final.POST_SPEC_CRITICAL_GATES.index(EXPECTED_POST_V4_SEQUENCE[0])
    assert (
        final.POST_SPEC_CRITICAL_GATES[
            start : start + len(EXPECTED_POST_V4_SEQUENCE)
        ]
        == EXPECTED_POST_V4_SEQUENCE
    )
    assert final.HISTORICAL_POST_V4_GATE == "POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert final.HISTORICAL_V8_RESULT_GATE == "V8_FVG_FOLLOWTHROUGH_HISTORICAL_PROFITABILITY_RESULT_READY"
    assert final.TERMINAL_GATE == "POST_V8_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert final.COMPLETION_BASIS == "POST_V8_CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE"
    assert final.HISTORICAL_CURRENT_EVIDENCE_GATE == "CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY"
    assert final.HISTORICAL_CLOSURE_GATE == "PROJECT_CLOSED_EXISTING_EVIDENCE"

    old_terminal = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
        final.HISTORICAL_POST_V4_GATE,
    ])
    assert old_terminal["project_complete"] is False
    assert old_terminal["completion_basis"] is None
    assert old_terminal["historical_existing_evidence_closure"] is True
    assert old_terminal["historical_current_evidence_boundary"] is True
    assert old_terminal["historical_post_v4_boundary"] is True
    assert old_terminal["historical_v8_result_ready"] is False

    v8_result = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
        final.HISTORICAL_POST_V4_GATE,
        final.HISTORICAL_V8_RESULT_GATE,
    ])
    assert v8_result["project_complete"] is False
    assert v8_result["completion_basis"] is None
    assert v8_result["historical_v8_result_ready"] is True

    complete = derive_with([
        final.HISTORICAL_CLOSURE_GATE,
        final.HISTORICAL_CURRENT_EVIDENCE_GATE,
        final.HISTORICAL_POST_V4_GATE,
        final.HISTORICAL_V8_RESULT_GATE,
        final.TERMINAL_GATE,
    ])
    assert complete["project_complete"] is True
    assert complete["completion_basis"] == final.COMPLETION_BASIS
    assert complete["current_gate"] == final.TERMINAL_GATE
    assert complete["historical_existing_evidence_closure"] is True
    assert complete["historical_current_evidence_boundary"] is True
    assert complete["historical_post_v4_boundary"] is True
    assert complete["historical_v8_result_ready"] is True
    assert complete["optional_future_validation_gate"] == "V2_FUTURE_VALIDATION_COMPLETE"

    print("POST_V4_HISTORICAL_CHECKPOINT_AND_POST_V8_TERMINAL_READY")


if __name__ == "__main__":
    main()
