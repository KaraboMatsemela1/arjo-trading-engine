#!/usr/bin/env python3
"""Regression tests for the frozen NQ calibration WoO contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_nq_calibration_preregistration import EXPECTED_WOO, validate  # noqa: E402

FROZEN_SHA = "a" * 64


def base_packet() -> dict:
    return {
        "stage": "PREREGISTERED",
        "outcome_access_authorized": True,
        "preregistration_sha256": FROZEN_SHA,
        "dataset": {"calibration_data_accessed": False, "holdout_accessed": False},
        "seed_plan": {"evidence_ids": list(EXPECTED_WOO["basis_evidence_ids"])},
        "operational_configuration": {"window_of_opportunity": copy.deepcopy(EXPECTED_WOO)},
    }


def completed_packet() -> dict:
    packet = base_packet()
    packet["stage"] = "CALIBRATION_COMPLETE"
    packet["dataset"]["calibration_data_accessed"] = True
    packet["calibration_result_ref"] = "research/calibration/result.json"
    packet["calibration_result_sha256"] = "b" * 64
    return packet


def base_spec() -> dict:
    return {"operational_configuration": {"window_of_opportunity": copy.deepcopy(EXPECTED_WOO)}}


def main() -> int:
    packet = base_packet()
    spec = base_spec()
    assert validate(packet, spec, replay_spec_sha256=FROZEN_SHA) == []

    # Lifecycle advancement may change data-access state, but not the frozen WoO/prereg SHA.
    completed = completed_packet()
    assert validate(completed, spec, replay_spec_sha256=FROZEN_SHA) == []

    shifted = copy.deepcopy(packet)
    shifted["operational_configuration"]["window_of_opportunity"]["start_inclusive"] = "10:00:00"
    assert any("frozen 09:30-11:00" in error for error in validate(shifted, spec, replay_spec_sha256=FROZEN_SHA))

    completed_shifted = completed_packet()
    completed_shifted["operational_configuration"]["window_of_opportunity"]["end_exclusive"] = "10:45:00"
    assert any("frozen 09:30-11:00" in error for error in validate(completed_shifted, spec, replay_spec_sha256=FROZEN_SHA))

    holdout_leak = copy.deepcopy(completed)
    holdout_leak["dataset"]["holdout_accessed"] = True
    assert any("holdout_accessed" in error for error in validate(holdout_leak, spec, replay_spec_sha256=FROZEN_SHA))

    prereg_accessed = copy.deepcopy(packet)
    prereg_accessed["dataset"]["calibration_data_accessed"] = True
    assert any("calibration_data_accessed" in error for error in validate(prereg_accessed, spec, replay_spec_sha256=FROZEN_SHA))

    completed_unaccessed = completed_packet()
    completed_unaccessed["dataset"]["calibration_data_accessed"] = False
    assert any("CALIBRATION_COMPLETE requires calibration_data_accessed=true" in error for error in validate(completed_unaccessed, spec, replay_spec_sha256=FROZEN_SHA))

    spec_mismatch = base_spec()
    spec_mismatch["operational_configuration"]["window_of_opportunity"]["end_exclusive"] = "11:30:00"
    errors = validate(packet, spec_mismatch, replay_spec_sha256=FROZEN_SHA)
    assert any("replay-spec WoO" in error for error in errors)
    assert any("configurations differ" in error for error in errors)

    sha_mismatch = validate(packet, spec, replay_spec_sha256="c" * 64)
    assert any("does not match the frozen replay specification" in error for error in sha_mismatch)

    invalid_stage = copy.deepcopy(packet)
    invalid_stage["stage"] = "SEED_ASSESSMENT"
    assert any("stage must be one of" in error for error in validate(invalid_stage, spec, replay_spec_sha256=FROZEN_SHA))

    missing_result = completed_packet()
    del missing_result["calibration_result_ref"]
    assert any("calibration_result_ref" in error for error in validate(missing_result, spec, replay_spec_sha256=FROZEN_SHA))

    print("NQ calibration preregistration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
