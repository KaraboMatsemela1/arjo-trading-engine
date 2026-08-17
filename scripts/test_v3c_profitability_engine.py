#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import v3c_profitability_engine as e

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "research/profitability/v3c_profitability_execution_lock_v1.json"
PROTOCOL = ROOT / "research/profitability/v3c_arguments_execution_protocol_v1.json"


def z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def bar(dt: datetime, *, bo="100", bh="101", bl="100", bc="100.5", ao="100", ah="101", al="100", ac="100.5") -> dict:
    return {"ts_start_utc": z(dt), "bid": {"o": bo, "h": bh, "l": bl, "c": bc}, "ask": {"o": ao, "h": ah, "l": al, "c": ac}}


def trigger(name: str, dt: datetime, *, stop="99.5", confirmed: datetime | None = None) -> dict:
    return {"trigger_id": name, "activation_known_at_utc": z(dt), "rejection_low": stop, "rejection_high": "101", "swing_confirmed_at_utc": z(confirmed or (dt - timedelta(hours=4)))}


def metric_from(values: list[float], scenario: str) -> dict:
    ledger = []
    base = datetime(2020, 1, 1, tzinfo=UTC)
    for idx, value in enumerate(values):
        ledger.append({"trigger_id": f"T{idx}", "knowledge_time_utc": z(base + timedelta(days=idx)), "entry_ts_utc": z(base + timedelta(days=idx)), "exit_ts_utc": z(base + timedelta(days=idx, minutes=1)), "status": "TARGET" if value > 0 else "STOP", "net_r": value})
    p = {"scenario": scenario, "ledger": ledger, "ledger_sha256": e.canon(ledger)}
    return e.metrics(p)


def main() -> None:
    lock = json.loads(LOCK.read_text())
    recorded = lock.pop("spec_sha256")
    assert recorded == "ba37fb3fe144bffa7481279b53af764f1614a42fdd63b4a2a493737f1867abd5"
    assert e.canon(lock) == recorded
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["protocol_sha256"] == "0b3a6a5e217e7e4c279f7384c14579e97bf6821bc59deefac3086e7b4ce4ba7a"
    assert protocol["authorization"] == {"paper_execution": False, "live_execution": False, "broker_mutation": False}

    t0 = datetime(2020, 1, 2, 10, 0, tzinfo=UTC)
    a = trigger("A", t0, confirmed=t0 - timedelta(hours=8))
    b = trigger("B", t0, confirmed=t0 - timedelta(hours=4))
    kept, skipped = e.deduplicate([a, b])
    assert [x["trigger_id"] for x in kept] == ["B"]
    assert skipped[0]["status"] == "SKIPPED_DUPLICATE_KNOWLEDGE_TIME"

    target_bars = [bar(t0, bo="100", bh="103", bl="100", bc="102", ao="100", ah="103.5", al="100.2", ac="102.5")]
    r = e.measure_trade(trigger("TGT", t0), target_bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    assert r["status"] == "TARGET" and r["exit_price"] == "102.0"

    both = [bar(t0, bo="100", bh="103", bl="99", bc="101", ao="100", ah="103.5", al="99.5", ac="101.5")]
    r = e.measure_trade(trigger("BOTH", t0), both, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    assert r["status"] == "STOP" and r["same_m1_stop_and_target"] is True
    assert r["exit_price"] == "99.0"

    invalid = e.measure_trade(trigger("BAD", t0, stop="101"), [bar(t0)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    assert invalid["status"] == "INVALID_RISK_ORDERING"

    censored = e.measure_trade(trigger("C", t0), [bar(t0 + timedelta(minutes=i)) for i in range(20)], slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    assert censored["status"] == "RIGHT_CENSORED_OOS_END"

    expiry_bars = [bar(t0 + timedelta(minutes=i), bo="100", bh="101", bl="100", bc="100.5", ao="100", ah="101.1", al="100", ac="100.6") for i in range(1440)]
    expiry = e.measure_trade(trigger("E", t0), expiry_bars, slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    assert expiry["status"] == "EXPIRY" and expiry["complete_m1_bars_held"] == 1440

    bars = [bar(t0 + timedelta(minutes=i), bo="100", bh="101", bl="100", bc="100.5", ao="100", ah="101.1", al="100", ac="100.6") for i in range(1440)]
    bars[2] = bar(t0 + timedelta(minutes=2), bo="100", bh="103", bl="100", bc="102", ao="100", ah="103.2", al="100", ac="102.2")
    def provider(_: datetime, __: int) -> list[dict]: return bars
    portfolio = e.evaluate_portfolio([trigger("P1", t0), trigger("P2", t0 + timedelta(minutes=1))], provider, scenario="BASE", slip_points=Decimal("0.5"), financing_r_per_1440=Decimal("0.005"))
    statuses = [x["status"] for x in portfolio["ledger"]]
    assert "TARGET" in statuses and "SKIPPED_CONCURRENT_POSITION" in statuses

    prelim_base = metric_from([1.0] * 90 + [-0.5] * 30, "BASE")
    prelim_stress = metric_from([0.7] * 90 + [-0.6] * 30, "STRESS")
    assert e.classify(prelim_base, prelim_stress) == "PRELIMINARY_PROFITABLE_EDGE"
    bad_stress = metric_from([0.1] * 30 + [-1.0] * 90, "STRESS")
    assert e.classify(prelim_base, bad_stress) == "EDGE_NOT_ESTABLISHED"
    insufficient = metric_from([1.0] * 99, "BASE")
    assert e.classify(insufficient, prelim_stress) == "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"

    strong_base = metric_from([1.0] * 220 + [-0.5] * 40, "BASE")
    strong_stress = metric_from([0.7] * 220 + [-0.6] * 40, "STRESS")
    assert e.classify(strong_base, strong_stress) == "STRONG_HISTORICAL_EDGE"

    print("V3-C profitability engine sabotage tests passed")


if __name__ == "__main__":
    main()
