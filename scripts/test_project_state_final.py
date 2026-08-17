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
    assert final_path.index(project_state_final.HISTORICAL_CLOSURE_GATE) < final_path.index(
        project_state_final.TERMINAL_GATE
    )
    assert project_state_final.OPTIONAL_FUTURE_EXTENSION not in final_path
    assert len(final_path) == len(set(final_path)), "critical path contains duplicate gates"

    # The previous closure is now only a historical milestone. Once it is
    # satisfied, the next objective must be profitability preregistration.
    historical = completed_through(final_path, project_state_final.HISTORICAL_CLOSURE_GATE)
    historical_state = project_state.derive_state(historical)
    assert historical_state["historical_existing_evidence_closure"] is True
    assert historical_state["project_complete"] is False
    assert historical_state["completion_basis"] is None
    assert historical_state["current_gate"] == "PROFITABILITY_VALIDATION_PROTOCOL_FROZEN"

    # After the sealed V3-C economic result, the research boundary itself is
    # still required before the lifecycle may be called complete.
    profitability = completed_through(final_path, "V3_ARGUMENTS_PROFITABILITY_RESULT_READY")
    profitability_state = project_state.derive_state(profitability)
    assert profitability_state["current_gate"] == project_state_final.TERMINAL_GATE
    assert profitability_state["project_complete"] is False
    assert profitability_state["completion_basis"] is None

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
    assert complete_state["completion_basis"] == "CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE"
    assert complete_state["historical_existing_evidence_closure"] is True
    assert complete_state["optional_future_validation_gate"] == "V2_FUTURE_VALIDATION_COMPLETE"
    assert complete_state["spec_ready"] is True
    assert complete_state["paper_execution_enabled"] is False
    assert complete_state["live_execution_enabled"] is False
    print("project_current_evidence_terminal_boundary=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
