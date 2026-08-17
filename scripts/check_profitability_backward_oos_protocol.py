#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/profitability/backward_oos_protocol_v1.json"
AUDIT = ROOT / "research/profitability/backward_oos_untouched_audit_v1.json"
EXPECTED_SHA256 = "3bbed5663762a5d484935de8383d02b4aa3d320e0d4ef02af9cf5469e3eddefe"


def canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    audit = json.loads(AUDIT.read_text())

    assert canonical_sha(protocol) == EXPECTED_SHA256, "protocol SHA drift"
    assert protocol["status"] == "FROZEN_BEFORE_BACKWARD_OOS_ACCESS"
    assert protocol["strategy"]["profile_sha256"] == "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
    assert protocol["strategy"]["no_refit"] is True
    assert protocol["strategy"]["no_parameter_selection"] is True
    assert protocol["data"]["start_inclusive"] == "2010-01-01T00:00:00Z"
    assert protocol["data"]["end_exclusive"] == "2024-01-01T00:00:00Z"
    assert protocol["data"]["pricing"] == "MBA"
    assert protocol["stages"]["stage_1_occurrence_frequency"]["outcomes_allowed"] is False
    assert protocol["stages"]["stage_1_occurrence_frequency"]["minimum_executable_occurrences_for_profitability_inference"] == 30
    assert protocol["authorization"] == {"paper_execution": False, "live_execution": False, "broker_mutation": False}

    assert audit["candidate_window"] == [protocol["data"]["start_inclusive"], protocol["data"]["end_exclusive"]]
    assert audit["committed_pre_2024_oanda_market_data_contract_found"] is False
    assert audit["committed_pre_2024_oanda_market_data_artifact_found"] is False
    assert audit["result"] == "ELIGIBLE_BACKWARD_OOS_MARKET_DATA_WINDOW"

    # The candidate must end at or before every known governed market-data window.
    candidate_end = protocol["data"]["end_exclusive"]
    for start, _end in protocol["data"]["known_repo_market_data_windows_excluded"]:
        assert candidate_end <= start, f"candidate overlaps known governed window starting {start}"

    print(json.dumps({
        "status": "PROFITABILITY_VALIDATION_PROTOCOL_FROZEN",
        "protocol_sha256": EXPECTED_SHA256,
        "candidate_window": audit["candidate_window"],
        "outcomes_accessed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
