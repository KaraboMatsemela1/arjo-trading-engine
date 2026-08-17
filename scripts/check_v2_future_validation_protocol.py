#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_PROTOCOL_ID = "ARJO_V2_FUTURE_VALIDATION_PROTOCOL_V1"
EXPECTED_PROTOCOL_SHA = "8231a335a6b5beb1784fa308a0e8b4f80c516ef7bff9d696217d123f3bd378dd"
EXPECTED_PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
EXPECTED_RESERVATION_SHA = "77cb50d000e4eecfaff6890d60ae296e5a06381b220debcb868240711c525853"
EXPECTED_REMEDIATION_SHA = "ad74e7bf4dee89e6bbed4b8efbe07d87723c9e4dca529126c7d4e7917ad1c960"
EXPECTED_V1_DISPOSITION_SHA = "71f1c1b67399fb297d037d0b8cb9bb0699afb3b2c894c0659042486a55bfc949"
EXPECTED_INVARIANT_SHA = "1822f7aa9f43cdabfa4f50d10c932e7eb600e5ffd6821615f8fff440cbe9c2c5"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(protocol_path: Path, profile_path: Path, reservation_path: Path, remediation_path: Path, disposition_path: Path) -> dict:
    protocol = load(protocol_path)
    unsigned = dict(protocol)
    recorded = str(unsigned.pop("protocol_sha256", ""))
    actual = canonical_sha256(unsigned)
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID or recorded != EXPECTED_PROTOCOL_SHA or actual != EXPECTED_PROTOCOL_SHA:
        raise RuntimeError("future validation protocol identity/SHA mismatch")
    if protocol.get("status") != "FROZEN_BEFORE_FUTURE_VALIDATION_ACCESS":
        raise RuntimeError("protocol is not frozen before future access")

    profile = load(profile_path)
    if profile.get("profile_id") != "ARJO_DERIVED_OWNER_OPERATIONAL_V2" or profile.get("profile_sha256") != EXPECTED_PROFILE_SHA:
        raise RuntimeError("V2 profile mismatch")
    if profile.get("authorization", {}).get("paper_execution_authorized") is not False or profile.get("authorization", {}).get("live_execution_authorized") is not False or profile.get("authorization", {}).get("broker_mutation_authorized") is not False:
        raise RuntimeError("V2 execution authorization boundary changed")

    reservation = load(reservation_path)
    if reservation.get("reservation_sha256") != EXPECTED_RESERVATION_SHA or reservation.get("data_accessed") is not False or reservation.get("data_access_authorized") is not False:
        raise RuntimeError("future validation reservation changed or accessed")
    remediation = load(remediation_path)
    if remediation.get("readiness_sha256") != EXPECTED_REMEDIATION_SHA or remediation.get("execution_observability_invariant_sha256") != EXPECTED_INVARIANT_SHA:
        raise RuntimeError("V2 remediation lineage mismatch")
    disposition = load(disposition_path)
    if disposition.get("disposition_sha256") != EXPECTED_V1_DISPOSITION_SHA or disposition.get("consumed_holdout", {}).get("reuse_for_v2_tuning_or_validation_allowed") is not False:
        raise RuntimeError("V1 holdout disposition changed")

    window = protocol["window"]
    if window != {
        "consumed_v1_2026h1_reuse_prohibited": True,
        "end_exclusive": "2027-03-01T00:00:00Z",
        "request_must_not_cross_end": True,
        "request_must_not_precede_start": True,
        "start_inclusive": "2026-09-01T00:00:00Z",
    }:
        raise RuntimeError("future validation window changed")

    if any(value is not False for value in protocol["no_refit"].values()):
        raise RuntimeError("no-refit policy weakened")
    obs = protocol["observability"]
    required_false = ["unobservable_fill_allowed", "future_bar_fallback_allowed", "close_fallback_allowed", "alternate_fill_allowed", "target_stop_evaluation_when_unobservable_allowed"]
    if obs.get("predicate") != "second_sting_bar.low <= touch_price <= second_sting_bar.high" or any(obs.get(k) is not False for k in required_false):
        raise RuntimeError("observability policy changed")
    if protocol["sample_policy"].get("inferential_resolved_executable_occurrence_threshold") != 30:
        raise RuntimeError("sample threshold changed")
    if protocol["authorization"] != {
        "broker_mutation_authorized": False,
        "future_validation_data_access_authorized": False,
        "future_validation_evaluation_authorized": False,
        "live_execution_authorized": False,
        "paper_execution_authorized": False,
    }:
        raise RuntimeError("protocol authorization boundary changed")
    return protocol


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--reservation", required=True)
    p.add_argument("--remediation", required=True)
    p.add_argument("--v1-disposition", required=True)
    args = p.parse_args()
    protocol = validate(Path(args.protocol), Path(args.profile), Path(args.reservation), Path(args.remediation), Path(args.v1_disposition))
    print(json.dumps({"status": "V2_FUTURE_VALIDATION_PROTOCOL_READY", "protocol_sha256": protocol["protocol_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
