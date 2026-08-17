#!/usr/bin/env python3
"""Validate outcome-blind semantic-anchor occurrence packets.

The validator does not discover FVGs, FVAs, 2CRs, Order Flow legs, targets, or
2-Sting events. Those fields remain semantic annotations until direct
first-party rules make their selection machine-deterministic. This module only
checks two isolated annotation-pass agreement plus data-verifiable invariants.

The current protocol uses two non-cross-referencing passes from the same model.
Agreement is therefore a reproducibility check and MUST NOT be represented as
independent-human consensus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CAL_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
EXPECTED_PROVIDER = {
    "provider": "OANDA_V20",
    "venue": "OANDA_FXTRADE",
    "environment": "practice",
    "instrument": "NAS100_USD",
    "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
}
EXPECTED_CONTRACT_SHA = "8923d63d27df107fd422b9bab97490c8403d656ffb9c3577cc3e4f67474c4a51"
EXPECTED_ANNOTATOR_CLASS = "GPT_5_6_SOL"
EXPECTED_ISOLATION_MODE = "SAME_MODEL_SEPARATE_PASS_NO_CROSS_REFERENCE"
EXPECTED_PASS_IDS = {"PASS_A", "PASS_B"}
REQUIRED_EVIDENCE = {
    "four_h_fvg": {"EV_427DA06DF5EBFA7F4CFB170A"},
    "one_h_fva": {"EV_88AB61A79C3864A7767B6A11"},
    "rejection_high": {"EV_E2CA3E5215E4B2C2044D7BC9", "EV_7F8AE2B63C992516199935EE"},
    "order_flow_leg_low": {"EV_58E144AEBF95808F39138E22"},
    "target": {"EV_53110264054D0997F8C055BD"},
    "second_sting": {
        "EV_AED1F1512355C2B3B6DEAB4D",
        "EV_0FDC8E9BEC515E440157F18B",
        "EV_75D4CB1715AC2752B8F4AD1B",
    },
}
FORBIDDEN_OUTCOME_KEYS = {
    "pnl", "profit", "loss", "win", "return", "performance", "target_hit",
    "stop_hit", "rr", "expectancy", "score", "rank",
}


class OccurrenceValidationError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise OccurrenceValidationError(f"invalid timestamp: {value!r}") from exc
    if dt.utcoffset() is None:
        raise OccurrenceValidationError("timestamp must be timezone-aware")
    dt = dt.astimezone(UTC)
    if not CAL_START <= dt < HOLDOUT_START:
        raise OccurrenceValidationError("timestamp outside frozen calibration window")
    return dt


def decimal(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OccurrenceValidationError(f"invalid decimal for {label}") from exc
    if not parsed.is_finite():
        raise OccurrenceValidationError(f"non-finite decimal for {label}")
    return parsed


def assert_no_outcomes(value: object, path: str = "packet") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                raise OccurrenceValidationError(f"outcome/performance field prohibited at {path}.{key}")
            assert_no_outcomes(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_outcomes(item, f"{path}[{index}]")


def validate_provider(packet: dict) -> None:
    provider = packet.get("provider_identity")
    if not isinstance(provider, dict):
        raise OccurrenceValidationError("provider_identity missing")
    for key, expected in EXPECTED_PROVIDER.items():
        if provider.get(key) != expected:
            raise OccurrenceValidationError(f"provider identity mismatch: {key}")
    if packet.get("request_contract_sha256") != EXPECTED_CONTRACT_SHA:
        raise OccurrenceValidationError("request contract SHA mismatch")
    refs = packet.get("calibration_data_refs")
    if not isinstance(refs, list) or not refs:
        raise OccurrenceValidationError("calibration_data_refs missing")
    allowed = {9282976276, 9283007527}
    artifact_ids = {int(ref.get("artifact_id", -1)) for ref in refs if isinstance(ref, dict)}
    if not artifact_ids or not artifact_ids.issubset(allowed):
        raise OccurrenceValidationError("unrecognized calibration artifact reference")


def validate_annotations(packet: dict) -> dict:
    annotations = packet.get("annotations")
    if not isinstance(annotations, list) or len(annotations) != 2:
        raise OccurrenceValidationError("exactly two isolated annotation passes are required")
    ids = [str(item.get("annotator_id", "")) for item in annotations if isinstance(item, dict)]
    if len(ids) != 2 or not all(ids) or len(set(ids)) != 2:
        raise OccurrenceValidationError("two distinct pass-scoped annotator_id values are required")
    pass_ids = {str(item.get("pass_id", "")) for item in annotations if isinstance(item, dict)}
    if pass_ids != EXPECTED_PASS_IDS:
        raise OccurrenceValidationError("annotations must contain exactly PASS_A and PASS_B")

    canonical_anchors: list[dict] = []
    for annotation in annotations:
        if annotation.get("annotator_class") != EXPECTED_ANNOTATOR_CLASS:
            raise OccurrenceValidationError("unexpected annotator_class")
        if annotation.get("independent_human_annotator_claimed") is not False:
            raise OccurrenceValidationError("independent-human consensus claim is prohibited")
        if annotation.get("isolation_mode") != EXPECTED_ISOLATION_MODE:
            raise OccurrenceValidationError("unexpected annotation isolation_mode")
        if annotation.get("outcome_blind") is not True:
            raise OccurrenceValidationError("each annotation must be outcome_blind=true")
        if annotation.get("method") != "EVIDENCE_CONSTRAINED_SEMANTIC_ANNOTATION":
            raise OccurrenceValidationError("unexpected annotation method")
        anchors = annotation.get("anchors")
        if not isinstance(anchors, dict):
            raise OccurrenceValidationError("annotation anchors missing")
        if annotation.get("anchors_sha256") != canonical_sha256(anchors):
            raise OccurrenceValidationError("annotation anchor SHA mismatch")
        canonical_anchors.append(anchors)

    if canonical_sha256(canonical_anchors[0]) != canonical_sha256(canonical_anchors[1]):
        raise OccurrenceValidationError("isolated annotation passes do not agree on semantic anchors")
    anchors = canonical_anchors[0]
    if packet.get("consensus_anchors_sha256") != canonical_sha256(anchors):
        raise OccurrenceValidationError("consensus anchor SHA mismatch")
    if packet.get("independent_human_consensus_claimed") is not False:
        raise OccurrenceValidationError("packet must explicitly deny independent-human consensus")
    if packet.get("same_model_reproducibility_only") is not True:
        raise OccurrenceValidationError("packet must mark same-model reproducibility boundary")
    return anchors


def evidence_set(anchor: dict, label: str) -> set[str]:
    values = anchor.get("evidence_ids")
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise OccurrenceValidationError(f"{label} evidence_ids missing")
    return set(values)


def validate_anchor_provenance(anchors: dict) -> None:
    for name, expected in REQUIRED_EVIDENCE.items():
        anchor = anchors.get(name)
        if not isinstance(anchor, dict):
            raise OccurrenceValidationError(f"missing semantic anchor: {name}")
        if not expected.issubset(evidence_set(anchor, name)):
            raise OccurrenceValidationError(f"required first-party evidence missing for {name}")
        if anchor.get("selection_classification") != "SEMANTIC_ANNOTATION_NOT_MACHINE_DISCOVERY":
            raise OccurrenceValidationError(f"{name} must retain semantic-annotation classification")


def validate_zone(anchor: dict, label: str) -> None:
    low = decimal(anchor.get("zone_low"), f"{label}.zone_low")
    high = decimal(anchor.get("zone_high"), f"{label}.zone_high")
    if low >= high:
        raise OccurrenceValidationError(f"{label} zone_low must be below zone_high")
    parse_utc(str(anchor.get("anchor_ts_utc")))


def validate_woo(ts: datetime, label: str) -> None:
    local = ts.astimezone(NY)
    local_clock = local.timetz().replace(tzinfo=None)
    if not (time(9, 30) <= local_clock < time(11, 0)):
        raise OccurrenceValidationError(f"{label} outside frozen 09:30-11:00 America/New_York WoO")


def validate_data_observations(packet: dict, anchors: dict) -> None:
    observations = packet.get("observations")
    if not isinstance(observations, dict):
        raise OccurrenceValidationError("observations missing")

    activation = observations.get("activation_confirmation")
    if not isinstance(activation, dict):
        raise OccurrenceValidationError("activation_confirmation missing")
    if activation.get("route") != "CLOSE_ABOVE_REJECTION_HIGH":
        raise OccurrenceValidationError("only evidence-backed close-above run route is authorized")
    activation_ts = parse_utc(str(activation.get("ts_start_utc")))
    rejection = decimal(anchors["rejection_high"].get("price"), "rejection_high.price")
    activation_close = decimal(activation.get("close"), "activation_confirmation.close")
    if activation_close <= rejection:
        raise OccurrenceValidationError("activation close did not run supplied rejection high")

    first = observations.get("first_sting")
    second = observations.get("second_sting")
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise OccurrenceValidationError("first/second sting observations missing")
    first_ts = parse_utc(str(first.get("ts_start_utc")))
    second_ts = parse_utc(str(second.get("ts_start_utc")))
    if first_ts >= second_ts:
        raise OccurrenceValidationError("second sting must occur after first sting")
    validate_woo(first_ts, "first sting")
    validate_woo(second_ts, "second sting")
    if second_ts < activation_ts:
        raise OccurrenceValidationError("second sting cannot precede activation confirmation")

    touch_entry = decimal(second.get("touch_price"), "second_sting.touch_price")
    close_entry = decimal(second.get("close"), "second_sting.close")
    low = decimal(second.get("low"), "second_sting.low")
    high = decimal(second.get("high"), "second_sting.high")
    if not low <= touch_entry <= high or not low <= close_entry <= high:
        raise OccurrenceValidationError("second-sting observed prices outside supplied bar range")

    stop_anchor = decimal(anchors["order_flow_leg_low"].get("price"), "order_flow_leg_low.price")
    target = decimal(anchors["target"].get("price"), "target.price")
    for entry, label in ((touch_entry, "touch"), (close_entry, "15m close")):
        if stop_anchor >= entry:
            raise OccurrenceValidationError(f"long stop anchor must be below {label} entry")
        if target <= entry:
            raise OccurrenceValidationError(f"long target must be above {label} entry")

    if anchors["second_sting"].get("first_ts_utc") != first.get("ts_start_utc"):
        raise OccurrenceValidationError("first-sting anchor/observation timestamp mismatch")
    if anchors["second_sting"].get("second_ts_utc") != second.get("ts_start_utc"):
        raise OccurrenceValidationError("second-sting anchor/observation timestamp mismatch")


def validate_packet(packet: dict) -> dict:
    if packet.get("schema_version") != 1:
        raise OccurrenceValidationError("unsupported occurrence schema")
    if packet.get("direction") != "LONG":
        raise OccurrenceValidationError("locked occurrence direction must be LONG")
    assert_no_outcomes(packet)
    validate_provider(packet)
    anchors = validate_annotations(packet)
    validate_anchor_provenance(anchors)
    validate_zone(anchors["four_h_fvg"], "four_h_fvg")
    validate_zone(anchors["one_h_fva"], "one_h_fva")
    parse_utc(str(anchors["rejection_high"].get("anchor_ts_utc")))
    parse_utc(str(anchors["order_flow_leg_low"].get("anchor_ts_utc")))
    parse_utc(str(anchors["target"].get("anchor_ts_utc")))
    parse_utc(str(anchors["second_sting"].get("first_ts_utc")))
    parse_utc(str(anchors["second_sting"].get("second_ts_utc")))
    validate_data_observations(packet, anchors)

    return {
        "occurrence_id": packet.get("occurrence_id"),
        "status": "QUALIFIED_ANCHOR_REPRODUCIBILITY_CONSENSUS",
        "consensus_anchors_sha256": packet["consensus_anchors_sha256"],
        "provider": EXPECTED_PROVIDER["provider"],
        "instrument": EXPECTED_PROVIDER["instrument"],
        "outcome_fields_present": False,
        "holdout_accessed": False,
        "same_model_reproducibility_only": True,
        "independent_human_consensus_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        result = validate_packet(packet)
    except (OSError, json.JSONDecodeError, OccurrenceValidationError) as exc:
        print(f"occurrence validation failed: {exc}", file=sys.stderr)
        return 1
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
