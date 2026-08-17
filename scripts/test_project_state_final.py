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


def issue(number: int, gate: str, state: str = "COMPLETE") -> dict:
    return {
        "number": number,
        "title": gate,
        "html_url": f"https://example.invalid/issues/{number}",
        "state": "closed" if state == "COMPLETE" else "open",
        "body": body(f"TEST-{number}", gate, state),
    }


def main() -> int:
    final_path = project_state.CRITICAL_GATES
    assert final_path[-9:] == project_state_final.V2_CRITICAL_GATES
    assert final_path[-1] == "V2_FUTURE_VALIDATION_COMPLETE"
    assert len(final_path) == len(set(final_path)), "critical path contains duplicate gates"
    assert "BLOCKED" in project_state.ALLOWED_STATES
    assert "EXTERNAL_WAIT" in project_state.ALLOWED_STATES

    fixtures = [issue(index + 1, gate) for index, gate in enumerate(final_path[:-1])]
    fixtures.extend(
        [
            {
                "number": 998,
                "title": "MASTER umbrella",
                "html_url": "https://example.invalid/issues/998",
                "state": "open",
                "body": body("MASTER", "NONE", "BLOCKED"),
            },
            {
                "number": 999,
                "title": "Final future validation",
                "html_url": "https://example.invalid/issues/999",
                "state": "open",
                "body": body("FINAL", "V2_FUTURE_VALIDATION_COMPLETE", "EXTERNAL_WAIT", "KaraboMatsemela1"),
            },
        ]
    )
    state = project_state.derive_state(fixtures)
    assert state["current_gate"] == "V2_FUTURE_VALIDATION_COMPLETE", state["current_gate"]
    assert state["spec_ready"] is True
    assert state["paper_execution_enabled"] is False
    assert state["live_execution_enabled"] is False
    assert "V2_FUTURE_VALIDATION_HARNESS_READY" in state["satisfied_gates"]
    assert "V2_FUTURE_VALIDATION_COMPLETE" not in state["satisfied_gates"]
    print("final_project_state_critical_path=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
