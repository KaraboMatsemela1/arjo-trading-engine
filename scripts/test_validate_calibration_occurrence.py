#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
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
            "zone_low": "20000.0", "zone_high": "20100.0", "anchor_ts_utc": "2025-06-02T12:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_427DA06DF5EBFA7F4CFB170A"],
        },
        "one_h_fva": {
            "zone_low": "20020.0", "zone_high": "20080.0", "anchor_ts_utc": "2025-06-02T13:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_88AB61A79C3864A7767B6A11"],
        },
        "rejection_high": {
            "price": "20090.0", "anchor_ts_utc": "2025-06-02T13:15:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_E2CA3E5215E4B2C2044D7BC9", "EV_7F8AE2B63C992516199935EE"],
        },
        "order_flow_leg_low": {
            "price": "20040.0", "anchor_ts_utc": "2025-06-02T13:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_58E144AEBF95808F39138E22"],
        },
        "target": {
            "price": "20250.0", "anchor_ts_utc": "2025-06-02T12:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": ["EV_53110264054D0997F8C055BD"],
        },
        "second_sting": {
            "first_ts_utc": "2025-06-02T13:45:00Z", "second_ts_utc": "2025-06-02T14:00:00Z",
            "selection_classification": "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY",
            "evidence_ids": [
                "EV_AED1F1512355C2B3B6DEAB4D", "EV_0FDC8E9BEC515E440157F18B", "EV_75D4CB1715AC2752B8F4AD1B"
            ],
        },
    }


def annotation(pass_id: str, a: dict) -> dict:
    return {
        "pass_id": pass_id,
        "annotator_id": f"GPT_5_6_SOL_{pass_id}",
        "annotator_class": "GPT_5_6_SOL",
        "independent_human_annotator_claimed": False,
        "isolation_mode": "SAME_MODEL_SEPARATE_PASS_NO_CROSS_REFERENCE",
        "outcome_blind": True,
        "method": "EVIDENCE_CONSTRAINED_SEMANTIC_ANNOTATION",
        "anchors": copy.deepcopy(a),
        "anchors_sha256": canonical_sha256(a),
    }


def packet() -> dict:
    a = anchors()
    anchor_sha = canonical_sha256(a)
    return {
        "schema_version": 1,
        "occurrence_id": "SYN-CAL-001",
        "direction": "LONG",
        "same_model_reproducibility_only": True,
        "independent_human_consensus_claimed": False,
        "provider_identity": {
            "provider": "OANDA_V20", "venue": "OANDA_FXTRADE", "environment": "practice",
            "instrument": "NAS100_USD", "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
        },
        "request_contract_sha256": "8923d63d27df107fd422b9bab97490c8403d656ffb9c3577cc3e4f67474c4a51",
        "calibration_data_refs": [
            {"year": 2025, "artifact_id": 9283007527, "retrieval_sha256": "4a53100460c78af9bc216c96ccf853df4b43f0a5b9cd7a9098c55b4191faeb0f"}
        ],
        "annotations": [annotation("PASS_A", a), annotation("PASS_B", a)],
        "consensus_anchors_sha256": anchor_sha,
        "observations": {
            "activation_confirmation": {
                "route": "CLOSE_ABOVE_REJECTION_HIGH", "ts_start_utc": "2025-06-02T13:30:00Z", "close": "20110.0"
            },
            "first_sting": {
                "ts_start_utc": "2025-06-02T13:45:00Z", "low": "20060.0", "high": "20130.0", "close": "20110.0"
            },
            "second_sting": {
                "ts_start_utc": "2025-06-02T14:00:00Z", "low": "20070.0", "high": "20140.0",
                "touch_price": "20100.0", "close": "20120.0"
            },
        },
    }


def refresh_annotation_shas(p: dict) -> None:
    for item in p["annotations"]:
        item["anchors_sha256"] = canonical_sha256(item["anchors"])
    p["consensus_anchors_sha256"] = canonical_sha256(p["annotations"][0]["anchors"])


def expect_error(mutator, needle: str) -> None:
    p = packet(); mutator(p)
    try:
        validate_packet(p)
    except OccurrenceValidationError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected error containing {needle!r}")


def main() -> int:
    result = validate_packet(packet())
    assert result["status"] == "QUALIFIED_ANCHOR_REPRODUCIBILITY_CONSENSUS"
    assert result["same_model_reproducibility_only"] is True
    assert result["independent_human_consensus_claimed"] is False

    expect_error(lambda p: p["annotations"][1].__setitem__("annotator_id", "GPT_5_6_SOL_PASS_A"), "distinct pass-scoped")
    expect_error(lambda p: p["annotations"][1].__setitem__("pass_id", "PASS_A"), "PASS_A and PASS_B")
    expect_error(lambda p: p["annotations"][0].__setitem__("independent_human_annotator_claimed", True), "independent-human")
    expect_error(lambda p: p.__setitem__("same_model_reproducibility_only", False), "same-model reproducibility")

    def disagree(p: dict) -> None:
        p["annotations"][1]["anchors"]["target"]["price"] = "20300.0"
        p["annotations"][1]["anchors_sha256"] = canonical_sha256(p["annotations"][1]["anchors"])
    expect_error(disagree, "do not agree")

    expect_error(lambda p: p["observations"].__setitem__("pnl", 100), "outcome/performance field prohibited")
    expect_error(lambda p: p["observations"]["second_sting"].__setitem__("ts_start_utc", "2026-01-02T14:00:00Z"), "outside frozen calibration window")
    expect_error(lambda p: p.__setitem__("request_contract_sha256", "0" * 64), "request contract SHA mismatch")
    expect_error(lambda p: p["calibration_data_refs"][0].__setitem__("artifact_id", 123), "unrecognized calibration artifact")

    def missing_evidence(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["rejection_high"]["evidence_ids"] = ["EV_E2CA3E5215E4B2C2044D7BC9"]
        refresh_annotation_shas(p)
    expect_error(missing_evidence, "required first-party evidence missing for rejection_high")

    def classification(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["target"]["selection_classification"] = "AUTO_DISCOVERED"
        refresh_annotation_shas(p)
    expect_error(classification, "target must retain semantic-annotation classification")

    def outside_woo(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["second_sting"]["second_ts_utc"] = "2025-06-02T15:15:00Z"
        refresh_annotation_shas(p); p["observations"]["second_sting"]["ts_start_utc"] = "2025-06-02T15:15:00Z"
    expect_error(outside_woo, "outside frozen 09:30-11:00")

    expect_error(lambda p: p["observations"]["activation_confirmation"].__setitem__("close", "20090.0"), "did not run supplied rejection high")

    def bad_stop(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["order_flow_leg_low"]["price"] = "20120.0"
        refresh_annotation_shas(p)
    expect_error(bad_stop, "long stop anchor must be below")

    def bad_target(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["target"]["price"] = "20100.0"
        refresh_annotation_shas(p)
    expect_error(bad_target, "long target must be above")

    def mismatch_sting(p: dict) -> None:
        for item in p["annotations"]: item["anchors"]["second_sting"]["second_ts_utc"] = "2025-06-02T14:15:00Z"
        refresh_annotation_shas(p)
    expect_error(mismatch_sting, "second-sting anchor/observation timestamp mismatch")

    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    assert len(hashlib.sha256(b"x").hexdigest()) == 64
    print("Calibration occurrence validator tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
