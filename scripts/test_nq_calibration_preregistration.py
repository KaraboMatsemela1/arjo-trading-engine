#!/usr/bin/env python3
"""Regression tests for the frozen NQ calibration WoO contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_nq_calibration_preregistration import EXPECTED_WOO, validate  # noqa: E402


def base_packet() -> dict:
    return {
        "stage": "PREREGISTERED",
        "outcome_access_authorized": True,
        "dataset": {"calibration_data_accessed": False, "holdout_accessed": False},
        "seed_plan": {"evidence_ids": list(EXPECTED_WOO["basis_evidence_ids"])},
        "operational_configuration": {"window_of_opportunity": copy.deepcopy(EXPECTED_WOO)},
    }


def base_spec() -> dict:
    return {"operational_configuration": {"window_of_opportunity": copy.deepcopy(EXPECTED_WOO)}}


def main() -> int:
    packet = base_packet()
    spec = base_spec()
    assert validate(packet, spec) == []

    shifted = copy.deepcopy(packet)
    shifted["operational_configuration"]["window_of_opportunity"]["start_inclusive"] = "10:00:00"
    assert any("frozen 09:30-11:00" in error for error in validate(shifted, spec))

    holdout_leak = copy.deepcopy(packet)
    holdout_leak["dataset"]["holdout_accessed"] = True
    assert any("holdout_accessed" in error for error in validate(holdout_leak, spec))

    accessed = copy.deepcopy(packet)
    accessed["dataset"]["calibration_data_accessed"] = True
    assert any("calibration_data_accessed" in error for error in validate(accessed, spec))

    spec_mismatch = base_spec()
    spec_mismatch["operational_configuration"]["window_of_opportunity"]["end_exclusive"] = "11:30:00"
    errors = validate(packet, spec_mismatch)
    assert any("replay-spec WoO" in error for error in errors)
    assert any("configurations differ" in error for error in errors)

    print("NQ calibration preregistration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
