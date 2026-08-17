#!/usr/bin/env python3
"""Secret-safe Databento availability/cost preflight for the frozen NQ calibration request."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nq_calibration_data import CalibrationDataError, load_contract  # noqa: E402

CONTRACT_PATH = ROOT / "research/calibration/nq_databento_request_contract.json"
OUTPUT_PATH = ROOT / ".calibration-data/nq_databento_preflight.json"


def main() -> int:
    contract = load_contract(CONTRACT_PATH)
    output = {
        "schema_version": 1,
        "provider": "databento",
        "dataset": contract["dataset"],
        "schema": contract["schema"],
        "symbols": contract["symbols"],
        "stype_in": contract["stype_in"],
        "start": contract["start"],
        "end_exclusive": contract["end_exclusive"],
        "protected_holdout_start": contract["protected_holdout_start"],
        "holdout_requested": False,
        "credential_value_exposed": False,
    }

    key = os.environ.get(contract["credential_env"], "")
    if not key:
        output.update({"status": "MISSING_CREDENTIAL", "estimated_cost_usd": None})
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output, sort_keys=True))
        return 0

    try:
        import databento as db  # type: ignore
    except ImportError as exc:
        raise CalibrationDataError("databento package is required for provider preflight") from exc

    client = db.Historical(key)
    cost = client.metadata.get_cost(
        dataset=contract["dataset"],
        symbols=contract["symbols"],
        schema=contract["schema"],
        stype_in=contract["stype_in"],
        start=contract["start"],
        end=contract["end_exclusive"],
    )
    output.update({"status": "COST_ESTIMATED", "estimated_cost_usd": float(cost)})
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
