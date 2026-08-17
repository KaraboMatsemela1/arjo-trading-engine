#!/usr/bin/env python3
"""Fail-closed validation for the frozen NQ calibration WoO configuration."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EXPECTED_WOO = {
    "mode": "PRESET_SESSION",
    "start_inclusive": "09:30:00",
    "end_exclusive": "11:00:00",
    "timezone": "America/New_York",
    "classification": "CONFIGURED_POLICY_FROM_FIRST_PARTY_EXAMPLE",
    "basis_evidence_ids": [
        "EV_6065BAEFC53803A9239A6CF6",
        "EV_DE2F50C2FB863386182ACEE1",
    ],
}


def validate(packet: dict, replay_spec: dict) -> list[str]:
    errors: list[str] = []
    if packet.get("stage") != "PREREGISTERED":
        errors.append("NQ calibration packet must remain PREREGISTERED before calibration completes")
    if packet.get("outcome_access_authorized") is not True:
        errors.append("NQ calibration packet must explicitly authorize the preregistered calibration")

    dataset = packet.get("dataset", {})
    if dataset.get("calibration_data_accessed") is not False:
        errors.append("calibration_data_accessed must remain false at preregistration freeze")
    if dataset.get("holdout_accessed") is not False:
        errors.append("holdout_accessed must remain false")

    packet_woo = packet.get("operational_configuration", {}).get("window_of_opportunity")
    spec_woo = replay_spec.get("operational_configuration", {}).get("window_of_opportunity")
    if packet_woo != EXPECTED_WOO:
        errors.append("packet WoO does not exactly match the frozen 09:30-11:00 New York policy")
    if spec_woo != EXPECTED_WOO:
        errors.append("replay-spec WoO does not exactly match the frozen 09:30-11:00 New York policy")
    if packet_woo != spec_woo:
        errors.append("packet and replay-spec WoO configurations differ")

    try:
        ZoneInfo(EXPECTED_WOO["timezone"])
    except ZoneInfoNotFoundError:
        errors.append("configured WoO timezone is not a valid IANA zone")

    try:
        start = time.fromisoformat(EXPECTED_WOO["start_inclusive"])
        end = time.fromisoformat(EXPECTED_WOO["end_exclusive"])
        if start >= end:
            errors.append("WoO start must be earlier than WoO end")
    except ValueError:
        errors.append("WoO clock values must be valid ISO local times")

    required_evidence = set(EXPECTED_WOO["basis_evidence_ids"])
    seed_evidence = set(packet.get("seed_plan", {}).get("evidence_ids", []))
    if not required_evidence.issubset(seed_evidence):
        errors.append("seed plan must include the WoO basis evidence IDs")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", default="research/calibration/aoo_nq_seed_assessment.json")
    args = parser.parse_args()

    packet_path = Path(args.packet)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    replay_ref = packet.get("preregistration_ref")
    if not isinstance(replay_ref, str) or not replay_ref:
        print("NQ calibration preregistration validation failed:\n- preregistration_ref is required", file=sys.stderr)
        return 1
    replay_path = Path(replay_ref)
    replay_spec = json.loads(replay_path.read_text(encoding="utf-8"))

    errors = validate(packet, replay_spec)
    if errors:
        print("NQ calibration preregistration validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(json.dumps({"packet_id": packet["packet_id"], "woo": EXPECTED_WOO}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
