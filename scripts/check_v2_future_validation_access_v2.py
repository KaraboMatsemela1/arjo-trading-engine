#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PROTOCOL_SHA = "193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38"
POLICY_SHA = "6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6"
READINESS_SHA = "1b55843921ceb090c85c6bee2571a38de2a6486e37d62782322cbaccea0984b0"
CONTRACT_SHA = "edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca"
FINAL_NOT_BEFORE = datetime(2027, 3, 1, tzinfo=UTC)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise RuntimeError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def _verified_embedded(path: Path, field: str, expected: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(data); recorded = str(unsigned.pop(field, ""))
    if recorded != expected or canonical_sha256(unsigned) != expected:
        raise RuntimeError(f"{path} SHA mismatch")
    return data


def verify_frozen_inputs(protocol_path: Path, policy_path: Path, readiness_path: Path, contract_path: Path) -> tuple[dict, dict]:
    protocol = _verified_embedded(protocol_path, "protocol_sha256", PROTOCOL_SHA)
    policy = _verified_embedded(policy_path, "policy_sha256", POLICY_SHA)
    readiness = _verified_embedded(readiness_path, "readiness_sha256", READINESS_SHA)
    contract = _verified_embedded(contract_path, "contract_sha256", CONTRACT_SHA)
    if protocol.get("protocol_id") != "ARJO_V2_FUTURE_VALIDATION_PROTOCOL_V2":
        raise RuntimeError("unexpected causal protocol")
    if policy.get("policy_id") != "V2_M1_TOUCH_SEQUENCING_V1":
        raise RuntimeError("unexpected M1 measurement policy")
    if readiness.get("status") != "V2_EXECUTION_MEASUREMENT_READY":
        raise RuntimeError("M1 measurement gate not ready")
    if contract.get("validation_protocol_sha256") != PROTOCOL_SHA or contract.get("measurement_policy_sha256") != POLICY_SHA:
        raise RuntimeError("request contract lineage mismatch")
    if contract.get("full_window_single_shot") is not True or parse_utc(contract["harness_acquisition_not_before"]) != FINAL_NOT_BEFORE:
        raise RuntimeError("single-shot final acquisition policy changed")
    return protocol, contract


def authorize(*, gate: str, now: datetime, authorization_path: Path | None, protocol_path: Path, policy_path: Path, readiness_path: Path, contract_path: Path) -> dict:
    protocol, contract = verify_frozen_inputs(protocol_path, policy_path, readiness_path, contract_path)
    now = now.astimezone(UTC)
    if gate not in {"acquisition", "evaluation"}:
        raise RuntimeError("unsupported final validation gate")
    if now < FINAL_NOT_BEFORE:
        raise RuntimeError(f"{gate} denied before 2027-03-01T00:00:00Z")
    if authorization_path is None or not authorization_path.exists():
        raise RuntimeError(f"{gate} denied: explicit authorization artifact missing")
    auth = json.loads(authorization_path.read_text(encoding="utf-8"))
    expected_id = contract["acquisition_authorization_id"] if gate == "acquisition" else contract["evaluation_authorization_id"]
    if auth.get("authorization_id") != expected_id or auth.get("gate") != gate or auth.get("authorized") is not True:
        raise RuntimeError("authorization identity/gate mismatch")
    required_bindings = {
        "protocol_sha256": PROTOCOL_SHA,
        "measurement_policy_sha256": POLICY_SHA,
        "request_contract_sha256": CONTRACT_SHA,
    }
    for key, value in required_bindings.items():
        if auth.get(key) != value:
            raise RuntimeError(f"authorization binding mismatch: {key}")
    if any(auth.get(key) is not False for key in ("paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized")):
        raise RuntimeError("validation authorization attempts to enable execution")
    return {"gate": gate, "status": "AUTHORIZED", "protocol_sha256": PROTOCOL_SHA, "request_contract_sha256": CONTRACT_SHA}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate", choices=["acquisition", "evaluation"], required=True)
    p.add_argument("--authorization")
    p.add_argument("--now")
    p.add_argument("--protocol", default="research/v2/future_validation_protocol_v2.json")
    p.add_argument("--policy", default="research/v2/v2_m1_touch_sequencing_v1.json")
    p.add_argument("--readiness", default="research/v2/v2_m1_measurement_readiness.json")
    p.add_argument("--contract", default="research/v2/nas100_oanda_future_validation_request_contract.json")
    args = p.parse_args()
    result = authorize(
        gate=args.gate,
        now=parse_utc(args.now) if args.now else datetime.now(UTC),
        authorization_path=Path(args.authorization) if args.authorization else None,
        protocol_path=Path(args.protocol), policy_path=Path(args.policy), readiness_path=Path(args.readiness), contract_path=Path(args.contract),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
