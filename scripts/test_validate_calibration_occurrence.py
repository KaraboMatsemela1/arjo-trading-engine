#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_calibration_occurrence import (  # noqa: E402
    OccurrenceValidationError,
    canonical_sha256,
    validate_packet,
)


def anchors() -> dict:
    return {
        "four_h_fvg": {
            "zone_low": "20000.0",
            "zone_high": "20100.0",
            "anchor_ts_utc": "2025-06-02T12:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_427DA06DF5EBFA7F4CFB170A"],
        },
        "one_h_fva": {
            "zone_low": "20020.0",
            "zone_high": "20080.0",
            "anchor_ts_utc": "2025-06-02T13:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_88AB61A79C3864A7767B6A11"],
        },
        "rejection_high": {
            "price": "20090.0",
            "anchor_ts_utc": "2025-06-02T13:15:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_E2CA3E5215E4B2C2044D7BC9"],
        },
        "order_flow_leg_low": {
            "price": "20040.0",
            "anchor_ts_utc": "2025-06-02T13:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_58E144AEBF95808F39138E22"],
        },
        "target": {
            "price": "20250.0",
            "anchor_ts_utc": "2025-06-02T12:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_53110264054D0997F8C055BD"],
        },
        "second_sting": {
            "first_ts_utc": "2025-06-02T13:45:00Z",
            "second_ts_utc": "2025-06-02T14:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_AED1F1512355C2B3B6DEAB4D"],
        },
    }


def packet() -> dict:
    a = anchors()
    anchor_sha = canonical_sha256(a)
    annotations = [
        {
            "annotator_id": "RECONSTRUCTOR_A",
            "outcome_blind": True,
            "method": "EVIDENCE_CONSTRAINED_SEMANTIC_ANNOTATION",
            "anchors": copy.deepcopy(a),
            "anchors_sha256": anchor_sha,
        },
        {
            "annotator_id": "RECONSTRUCTOR_B",
            "outcome_blind": True,
            "method": "EVIDENCE_CONSTRAINED_SEMANTIC_ANNOTATION",
            "anchors": copy.deepcopy(a),
            "anchors_sha256": anchor_sha,
        },
    ]
    return {
        "schema_version": 1,
        "occurrence_id": "SYN-CAL-001",
        "direction": "LONG",
        "provider_identity": {
            "provider": "OANDA_V20",
            "venue": "OANDA_FXTRADE",
            "environment": "practice",
            "instrument": "NAS100_USD",
            "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
        },
        "request_contract_sha256": "8923d63d27df107fd422b9bab97490c8403d656ffb9c3577cc3e4f67474c4a51",
        "calibration_data_refs": [
            {"year": 2025, "artifact_id": 9283007527, "retrieval_sha256": "4a53100460c78af9bc216c96ccf853df4b43f0a5b9cd7a9098c55b4191faeb0f"}
        ],
        "annotations": annotations,
        "consensus_anchors_sha256": anchor_sha,
        "observations": {
            "activation_confirmation": {
                "route": "CLOSE_ABOVE_REJECTION_HIGH",
                "ts_start_utc": "2025-06-02T13:30:00Z",
                "close": "20110.0",
            },
            "first_sting": {
                "ts_start_utc": "2025-06-02T13:45:00Z",
                "low": "20060.0",
                "high": "20130.0",
                "close": "20110.0",
            },
            "second_sting": {
                "ts_start_utc": "2025-06-02T14:00:00Z",
                "low": "20070.0",
                "high": "20140.0",
                "touch_price": "20100.0",
                "close": "20120.0",
            },
        },
    }


def refresh_annotation_shas(p: dict) -> None:
    for annotation in p["annotations"]:
        annotation["anchors_sha256"] = canonical_sha256(annotation["anchors"])
    p["consensus_anchors_sha256"] = canonical_sha256(p["annotations"][0]["anchors"])


def expect_error(mutator, needle: str) -> None:
    p = packet()
    mutator(p)
    try:
        validate_packet(p)
    except OccurrenceValidationError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected error containing {needle!r}")


def main() -> int:
    result = validate_packet(packet())
    assert result["status"] == "QUALIFIED_ANCHOR_CONSENSUS"
    assert result["outcome_fields_present"] is False
    assert result["holdout_accessed"] is False

    expect_error(
        lambda p: p["annotations"][1].__setitem__("annotator_id", "RECONSTRUCTOR_A"),
        "distinct annotator_id",
    )

    def disagree(p: dict) -> None:
        p["annotations"][1]["anchors"]["target"]["price"] = "20300.0"
        p["annotations"][1]["anchors_sha256"] = canonical_sha256(p["annotations"][1]["anchors"])
    expect_error(disagree, "do not agree")

    def outcome(p: dict) -> None:
        p["observations"]["pnl"] = 100
    expect_error(outcome, "outcome/performance field prohibited")

    def holdout(p: dict) -> None:
        p["observations"]["second_sting"]["ts_start_utc"] = "2026-01-02T14:00:00Z"
    expect_error(holdout, "outside frozen calibration window")

    expect_error(
        lambda p: p.__setitem__("request_contract_sha256", "0" * 64),
        "request contract SHA mismatch",
    )

    def artifact(p: dict) -> None:
        p["calibration_data_refs"][0]["artifact_id"] = 123
    expect_error(artifact, "unrecognized calibration artifact")

    def missing_evidence(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["one_h_fva"]["evidence_ids"] = []
        refresh_annotation_shas(p)
    expect_error(missing_evidence, "required first-party evidence missing for one_h_fva")

    def classification(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["target"]["selection_classification"] = "AUTO_DISCOVERED"
        refresh_annotation_shas(p)
    expect_error(classification, "target must retain semantic-annotation classification")

    def outside_woo(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["second_sting"]["second_ts_utc"] = "2025-06-02T15:15:00Z"
        refresh_annotation_shas(p)
        p["observations"]["second_sting"]["ts_start_utc"] = "2025-06-02T15:15:00Z"
    expect_error(outside_woo, "outside frozen 09:30-11:00")

    def no_run(p: dict) -> None:
        p["observations"]["activation_confirmation"]["close"] = "20090.0"
    expect_error(no_run, "did not run supplied rejection high")

    def bad_stop(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["order_flow_leg_low"]["price"] = "20120.0"
        refresh_annotation_shas(p)
    expect_error(bad_stop, "long stop anchor must be below")

    def bad_target(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["target"]["price"] = "20100.0"
        refresh_annotation_shas(p)
    expect_error(bad_target, "long target must be above")

    def mismatch_sting(p: dict) -> None:
        for annotation in p["annotations"]:
            annotation["anchors"]["second_sting"]["second_ts_utc"] = "2025-06-02T14:15:00Z"
        refresh_annotation_shas(p)
    expect_error(mismatch_sting, "second-sting anchor/observation timestamp mismatch")

    # Canonicalization is deterministic and not sensitive to dict insertion order.
    left = {"a": 1, "b": 2}
    right = {"b": 2, "a": 1}
    assert canonical_sha256(left) == canonical_sha256(right)
    assert len(hashlib.sha256(b"x").hexdigest()) == 64

    print("Calibration occurrence validator tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
