#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from check_v2_future_validation_protocol import EXPECTED_PROTOCOL_SHA, canonical_sha256


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise RuntimeError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def check_access(protocol_path: Path, gate: str, now: datetime, authorization_path: Path | None) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    unsigned = dict(protocol)
    recorded = str(unsigned.pop("protocol_sha256", ""))
    if recorded != EXPECTED_PROTOCOL_SHA or canonical_sha256(unsigned) != EXPECTED_PROTOCOL_SHA:
        raise RuntimeError("protocol SHA mismatch")

    key = "market_data_acquisition" if gate == "acquisition" else "outcome_evaluation"
    config = protocol["access_gates"][key]
    not_before = parse_utc(config["not_before"])
    if now.astimezone(UTC) < not_before:
        raise RuntimeError(f"{gate} denied before {config['not_before']}")
    if authorization_path is None or not authorization_path.exists():
        raise RuntimeError(f"{gate} denied: explicit authorization missing")

    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    expected_id = config["authorization_id"]
    if authorization.get("authorization_id") != expected_id:
        raise RuntimeError("authorization id mismatch")
    if authorization.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA:
        raise RuntimeError("authorization protocol binding mismatch")
    if authorization.get("gate") != gate or authorization.get("authorized") is not True:
        raise RuntimeError("authorization does not enable requested gate")
    if authorization.get("paper_execution_authorized") is not False or authorization.get("live_execution_authorized") is not False or authorization.get("broker_mutation_authorized") is not False:
        raise RuntimeError("authorization attempts to enable execution")
    return {"gate": gate, "status": "AUTHORIZED", "protocol_sha256": EXPECTED_PROTOCOL_SHA}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", required=True)
    p.add_argument("--gate", choices=["acquisition", "evaluation"], required=True)
    p.add_argument("--now")
    p.add_argument("--authorization")
    args = p.parse_args()
    now = parse_utc(args.now) if args.now else datetime.now(UTC)
    result = check_access(Path(args.protocol), args.gate, now, Path(args.authorization) if args.authorization else None)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
