#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_calibration_occurrence_set import OccurrenceSetError, build  # noqa: E402
from test_validate_calibration_occurrence import packet, refresh_annotation_shas  # noqa: E402


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except OccurrenceSetError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected error containing {needle!r}")


def main() -> int:
    expect_error(lambda: build([]), "at least one qualified occurrence packet")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p1 = packet()
        p1["occurrence_id"] = "OCC-002"
        p1_path = root / "b.json"
        write(p1_path, p1)

        p2 = packet()
        p2["occurrence_id"] = "OCC-001"
        for annotation in p2["annotations"]:
            annotation["anchors"]["four_h_fvg"]["zone_low"] = "19900.0"
            annotation["anchors"]["four_h_fvg"]["zone_high"] = "20000.0"
            annotation["anchors"]["rejection_high"]["price"] = "20080.0"
            annotation["anchors"]["order_flow_leg_low"]["price"] = "20030.0"
            annotation["anchors"]["target"]["price"] = "20300.0"
            annotation["anchors"]["second_sting"]["first_ts_utc"] = "2025-06-03T13:45:00Z"
            annotation["anchors"]["second_sting"]["second_ts_utc"] = "2025-06-03T14:00:00Z"
        refresh_annotation_shas(p2)
        p2["observations"]["activation_confirmation"]["ts_start_utc"] = "2025-06-03T13:30:00Z"
        p2["observations"]["activation_confirmation"]["close"] = "20110.0"
        p2["observations"]["first_sting"]["ts_start_utc"] = "2025-06-03T13:45:00Z"
        p2["observations"]["second_sting"]["ts_start_utc"] = "2025-06-03T14:00:00Z"
        p2_path = root / "a.json"
        write(p2_path, p2)

        manifest = build([p1_path, p2_path])
        assert manifest["status"] == "CALIBRATION_OCCURRENCES_READY"
        assert manifest["occurrence_count"] == 2
        assert len(manifest["occurrence_set_sha256"]) == 64
        assert manifest["outcome_fields_present"] is False
        assert manifest["holdout_accessed"] is False
        assert manifest["performance_comparison_performed"] is False
        assert [row["occurrence_id"] for row in manifest["occurrences"]] == ["OCC-002", "OCC-001"]
        assert all(len(row["packet_sha256"]) == 64 for row in manifest["occurrences"])

        # Deterministic regardless of input path ordering.
        reversed_manifest = build([p2_path, p1_path])
        assert reversed_manifest["occurrence_set_sha256"] == manifest["occurrence_set_sha256"]

        duplicate_id = copy.deepcopy(p2)
        duplicate_id["occurrence_id"] = "OCC-002"
        dup_path = root / "c.json"
        write(dup_path, duplicate_id)
        expect_error(lambda: build([p1_path, dup_path]), "duplicate occurrence_id")

        duplicate_consensus = copy.deepcopy(p1)
        duplicate_consensus["occurrence_id"] = "OCC-003"
        consensus_path = root / "d.json"
        write(consensus_path, duplicate_consensus)
        expect_error(lambda: build([p1_path, consensus_path]), "duplicate consensus anchor set")

        outcome = copy.deepcopy(p2)
        outcome["observations"]["performance"] = "good"
        outcome_path = root / "e.json"
        write(outcome_path, outcome)
        expect_error(lambda: build([outcome_path]), "outcome/performance field prohibited")

        disagreement = copy.deepcopy(p2)
        disagreement["annotations"][1]["anchors"]["target"]["price"] = "20400.0"
        disagreement["annotations"][1]["anchors_sha256"] = __import__("validate_calibration_occurrence").canonical_sha256(disagreement["annotations"][1]["anchors"])
        disagreement_path = root / "f.json"
        write(disagreement_path, disagreement)
        expect_error(lambda: build([disagreement_path]), "do not agree")

    print("Calibration occurrence set builder tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
