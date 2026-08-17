#!/usr/bin/env python3
"""Minute-level measurement for the frozen V2 SECOND_STING_TOUCH rule.

This module does not qualify strategy occurrences or alter the frozen 15m
observability rule. It only measures the actual touch minute and subsequent
stop/target order from complete M1 source bars.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED_POLICY_SHA = "6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6"


class MeasurementError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"invalid timestamp: {value!r}") from exc
    if dt.utcoffset() is None:
        raise MeasurementError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MeasurementError(f"invalid decimal: {label}") from exc
    if not result.is_finite():
        raise MeasurementError(f"non-finite decimal: {label}")
    return result


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(policy.get("policy_sha256", ""))
    unsigned = dict(policy)
    unsigned.pop("policy_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != EXPECTED_POLICY_SHA or actual != EXPECTED_POLICY_SHA:
        raise MeasurementError("M1 measurement policy SHA mismatch")
    if policy.get("policy_id") != "V2_M1_TOUCH_SEQUENCING_V1":
        raise MeasurementError("unexpected M1 measurement policy")
    if policy.get("status") != "FROZEN_BEFORE_FUTURE_VALIDATION_ACCESS":
        raise MeasurementError("M1 measurement policy is not frozen")
    return policy


def _normalized_rows(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    seen: set[datetime] = set()
    for row in rows:
        ts = parse_utc(str(row["ts_start_utc"]))
        if ts in seen:
            raise MeasurementError("duplicate M1 timestamp")
        seen.add(ts)
        low = dec(row["low"], "low")
        high = dec(row["high"], "high")
        if high < low:
            raise MeasurementError("invalid M1 OHLC envelope")
        output.append({"ts": ts, "low": low, "high": high})
    output.sort(key=lambda item: item["ts"])
    return output


def measure_occurrence(*, occurrence: dict, observability_status: str, m1_rows: list[dict], end_exclusive: datetime) -> dict:
    oid = str(occurrence["occurrence_id"])
    if observability_status == "NO_EXECUTABLE_ENTRY":
        return {
            "occurrence_id": oid,
            "observability_status": observability_status,
            "measurement_status": "NO_M1_MEASUREMENT_NO_EXECUTABLE_ENTRY",
            "execution_outcome": None,
        }
    if observability_status != "EXECUTABLE_ENTRY":
        raise MeasurementError("unexpected 15m observability status")

    second_start = parse_utc(str(occurrence["second_sting_ts_utc"]))
    interval_end = second_start + timedelta(minutes=15)
    end_exclusive = end_exclusive.astimezone(UTC)
    if interval_end > end_exclusive:
        raise MeasurementError("entry interval crosses evaluation boundary")

    touch = dec(occurrence["touch_price"], "touch_price")
    stop = dec(occurrence["order_flow_leg_low"], "order_flow_leg_low")
    target = dec(occurrence["target_price"], "target_price")
    if not stop < touch < target:
        raise MeasurementError("invalid long entry/stop/target ordering")

    rows = _normalized_rows(m1_rows)
    entry_interval = [row for row in rows if second_start <= row["ts"] < interval_end]
    expected_times = {second_start + timedelta(minutes=i) for i in range(15)}
    if len(entry_interval) != 15 or {row["ts"] for row in entry_interval} != expected_times:
        return {
            "occurrence_id": oid,
            "observability_status": observability_status,
            "measurement_status": "VALIDATION_INTEGRITY_FAILURE",
            "integrity_failure": "M1_ENTRY_INTERVAL_INCOMPLETE",
            "execution_outcome": None,
        }

    entry_row = next((row for row in entry_interval if row["low"] <= touch <= row["high"]), None)
    if entry_row is None:
        return {
            "occurrence_id": oid,
            "observability_status": observability_status,
            "measurement_status": "VALIDATION_INTEGRITY_FAILURE",
            "integrity_failure": "M1_TOUCH_NOT_OBSERVED",
            "execution_outcome": None,
        }

    entry_ts = entry_row["ts"]
    base = {
        "occurrence_id": oid,
        "observability_status": observability_status,
        "measurement_status": "M1_ENTRY_OBSERVED",
        "entry_ts": entry_ts.isoformat().replace("+00:00", "Z"),
        "entry_price": str(touch),
        "stop_price": str(stop),
        "target_price": str(target),
    }

    entry_hit_stop = entry_row["low"] <= stop
    entry_hit_target = entry_row["high"] >= target
    if entry_hit_stop or entry_hit_target:
        return {
            **base,
            "execution_outcome": "AMBIGUOUS_INTRABAR_ORDER",
            "event_ts": entry_ts.isoformat().replace("+00:00", "Z"),
            "ambiguity": "ENTRY_MINUTE_CONTAINS_STOP_OR_TARGET",
        }

    for row in rows:
        if not entry_ts < row["ts"] < end_exclusive:
            continue
        hit_stop = row["low"] <= stop
        hit_target = row["high"] >= target
        if not hit_stop and not hit_target:
            continue
        if hit_stop and hit_target:
            status = "AMBIGUOUS_INTRABAR_ORDER"
        elif hit_stop:
            status = "STOP_FIRST"
        else:
            status = "TARGET_FIRST"
        return {
            **base,
            "execution_outcome": status,
            "event_ts": row["ts"].isoformat().replace("+00:00", "Z"),
        }

    return {**base, "execution_outcome": "UNRESOLVED_WINDOW_END"}
