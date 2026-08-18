#!/usr/bin/env python3
from __future__ import annotations

import project_state
import project_state_final


def body(issue_id: str, output_gate: str, state: str = "COMPLETE", owner: str = "UNCLAIMED") -> str:
    return f"""<!-- project-meta
ISSUE_ID: {issue_id}
TYPE: TEST
DEPENDENCIES: []
ENTRY_GATE: NONE
OUTPUT_GATE: {output_gate}
OWNER: {owner}
STATE: {state}
-->"""


def issue(number: int, gate: str, state: str = "COMPLETE", owner: str = "UNCLAIMED") -> dict:
    return {
        "number": number,
        "title": gate,
        "html_url": f"https://example.invalid/issues/{number}",
        "state": "closed" if state == "COMPLETE" else "open",
        "body": body(f"TEST-{number}", gate, state, owner),
    }


def completed_through(final_path: list[str], gate: str) -> list[dict]:
    end = final_path.index(gate) + 1
    return [issue(index + 1, item) for index, item in enumerate(final_path[:end])]


def main() -> int:
    final_path = project_state.CRITICAL_GATES
    suffix = project_state_final.POST_SPEC_CRITICAL_GATES
    assert final_path[-len(suffix) :] == suffix
    assert final_path[-1] == project_state_final.TERMINAL_GATE
    assert project_state_final.HISTORICAL_CLOSURE_GATE in final_path
    assert project_state_final.HISTORICAL_CURRENT_EVIDENCE_GATE in final_path
    assert final_path.index(project_state_final.HISTORICAL_CLOSURE_GATE) < final_path.index(
        project_state_final.HISTORICAL_CURRENT_EVIDENCE_GATE
    ) < final_path.index(project_state_final.TERMINAL_GATE)
    assert project_state_final.OPTIONAL_FUTURE_EXTENSION not in final_path
    assert len(final_path) == len(set(final_path)), "critical path contains duplicate gates"

    # The original project closure is historical; profitability research follows it.
    historical = completed_through(final_path, project_state_final.HISTORICAL_CLOSURE_GATE)
    historical_state = project_state.derive_state(historical)
    assert historical_state["historical_existing_evidence_closure"] is True
    assert historical_state["project_complete"] is False
    assert historical_state["completion_basis"] is None
    assert historical_state["current_gate"] == "PROFITABILITY_VALIDATION_PROTOCOL_FROZEN"

    # V3-C's economic result still requires the original current-evidence boundary.
    v3_result = completed_through(final_path, "V3_ARGUMENTS_PROFITABILITY_RESULT_READY")
    v3_result_state = project_state.derive_state(v3_result)
    assert v3_result_state["current_gate"] == project_state_final.HISTORICAL_CURRENT_EVIDENCE_GATE
    assert v3_result_state["project_complete"] is False
    assert v3_result_state["completion_basis"] is None

    # The original current-evidence boundary became historical when V4 was opened.
    old_boundary = completed_through(final_path, project_state_final.HISTORICAL_CURRENT_EVIDENCE_GATE)
    old_boundary_state = project_state.derive_state(old_boundary)
    assert old_boundary_state["historical_current_evidence_boundary"] is True
    assert old_boundary_state["current_gate"] == "V4_SHARP_TURN_EXECUTION_PROTOCOL_FROZEN"
    assert old_boundary_state["project_complete"] is False
    assert old_boundary_state["completion_basis"] is None

    # A completed V4 economic result must still advance to the post-V4 boundary.
    v4_result = completed_through(final_path, "V4_SHARP_TURN_PROFITABILITY_RESULT_READY")
    v4_result_state = project_state.derive_state(v4_result)
    assert v4_result_state["current_gate"] == project_state_final.TERMINAL_GATE
    assert v4_result_state["project_complete"] is False
    assert v4_result_state["completion_basis"] is None

    # An implementing terminal issue must not be treated as a satisfied gate.
    pending = [issue(index + 1, gate) for index, gate in enumerate(final_path[:-1])]
    pending.append(issue(999, project_state_final.TERMINAL_GATE, "IMPLEMENTING", "CHATGPT"))
    pending_state = project_state.derive_state(pending)
    assert pending_state["current_gate"] == project_state_final.TERMINAL_GATE
    assert pending_state["project_complete"] is False
    assert pending_state["completion_basis"] is None

    complete = [issue(index + 1, gate) for index, gate in enumerate(final_path)]
    complete_state = project_state.derive_state(complete)
    assert complete_state["current_gate"] == project_state_final.TERMINAL_GATE
    assert complete_state["project_complete"] is True
    assert complete_state["completion_basis"] == project_state_final.COMPLETION_BASIS
    assert complete_state["completion_basis"] == "POST_V4_CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE"
    assert complete_state["historical_existing_evidence_closure"] is True
    assert complete_state["historical_current_evidence_boundary"] is True
    assert complete_state["optional_future_validation_gate"] == "V2_FUTURE_VALIDATION_COMPLETE"
    assert complete_state["spec_ready"] is True
    assert complete_state["paper_execution_enabled"] is False
    assert complete_state["live_execution_enabled"] is False
    print("project_post_v4_current_evidence_terminal_boundary=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
