#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_PROTOCOL_SHA = "193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38"
EXPECTED_PARENT_SHA = "8231a335a6b5beb1784fa308a0e8b4f80c516ef7bff9d696217d123f3bd378dd"
EXPECTED_PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(protocol)
    recorded = str(unsigned.pop("protocol_sha256", ""))
    if recorded != EXPECTED_PROTOCOL_SHA or canonical_sha256(unsigned) != EXPECTED_PROTOCOL_SHA:
        raise RuntimeError("causal future-validation protocol SHA mismatch")
    if protocol.get("protocol_id") != "ARJO_V2_FUTURE_VALIDATION_PROTOCOL_V2" or protocol.get("status") != "FROZEN_BEFORE_FUTURE_VALIDATION_ACCESS":
        raise RuntimeError("unexpected protocol identity/status")
    if protocol.get("supersedes", {}).get("protocol_sha256") != EXPECTED_PARENT_SHA:
        raise RuntimeError("superseded V1 protocol binding changed")
    if protocol.get("profile", {}).get("profile_sha256") != EXPECTED_PROFILE_SHA:
        raise RuntimeError("V2 profile binding changed")

    expected_window = {
        "acquisition_start_inclusive": "2026-09-01T00:00:00Z",
        "bootstrap_end_exclusive": "2026-10-01T00:00:00Z",
        "consumed_v1_2026h1_reuse_prohibited": True,
        "end_exclusive": "2027-03-01T00:00:00Z",
        "request_must_not_cross_end": True,
        "request_must_not_precede_acquisition_start": True,
        "scored_start_inclusive": "2026-10-01T00:00:00Z",
    }
    if protocol.get("window") != expected_window:
        raise RuntimeError("causal validation windows changed")

    init = protocol.get("initialization_policy", {})
    required = {
        "policy_id": "V2_COLD_START_BOOTSTRAP_V1",
        "classification": "OPERATIONAL_DEPLOYMENT_INITIALIZATION_POLICY_NOT_ARJO_SEMANTIC_CLAIM",
        "state_at_acquisition_start": "EMPTY",
        "pre_start_market_data_allowed": False,
        "pre_start_state_snapshot_allowed": False,
        "v1_holdout_state_or_data_allowed": False,
        "bootstrap_start_inclusive": "2026-09-01T00:00:00Z",
        "bootstrap_end_exclusive": "2026-10-01T00:00:00Z",
        "bootstrap_sessions_scored": False,
        "bootstrap_outcomes_evaluated": False,
        "bootstrap_performance_inspected": False,
        "scored_start_inclusive": "2026-10-01T00:00:00Z",
        "state_transition": "BOOTSTRAP_STATE_CONTINUES_CAUSALLY_INTO_SCORED_WINDOW",
    }
    for key, value in required.items():
        if init.get(key) != value:
            raise RuntimeError(f"initialization policy changed: {key}")
    if any(value is not False for value in protocol.get("no_refit", {}).values()):
        raise RuntimeError("no-refit policy weakened")
    if protocol.get("sample_policy", {}).get("inferential_resolved_executable_occurrence_threshold") != 30:
        raise RuntimeError("sample threshold changed")
    if any(protocol.get("authorization", {}).get(key) is not False for key in (
        "future_validation_data_access_authorized", "future_validation_evaluation_authorized",
        "paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized"
    )):
        raise RuntimeError("authorization boundary changed")
    return protocol


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    result = validate(Path(args.protocol))
    print(json.dumps({"status": "V2_CAUSAL_VALIDATION_PROTOCOL_READY", "protocol_sha256": result["protocol_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
