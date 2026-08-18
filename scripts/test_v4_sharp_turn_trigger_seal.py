#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scan = load("v4scan", ROOT / "scan_v4_sharp_turn_triggers.py")
acq = load("v4acq", ROOT / "oanda_v4_sharp_turn_structure.py")


def row(hour: int, o: str, h: str, l: str, c: str) -> dict:
    start = datetime(2020, 1, 1, hour, tzinfo=UTC)
    return {
        "start": start,
        "close_time": start + timedelta(hours=1),
        "open": Decimal(o),
        "high": Decimal(h),
        "low": Decimal(l),
        "close": Decimal(c),
        "granularity": "H1",
        "source": {},
    }


def fvg(fid: str, direction: str, known_hour: int, lower: str, upper: str, c1: int, c3: int, close: str) -> dict:
    known = datetime(2020, 1, 1, known_hour, tzinfo=UTC)
    return {
        "id": fid,
        "granularity": "H1",
        "direction": direction,
        "c1_index": c1,
        "c3_index": c3,
        "c1_start": known - timedelta(hours=3),
        "c3_start": known - timedelta(hours=1),
        "knowledge_time": known,
        "lower": Decimal(lower),
        "upper": Decimal(upper),
        "c3_close": Decimal(close),
    }


def context(cid: str, direction: str, encounter_hour: int, lower: str, upper: str) -> dict:
    encounter = datetime(2020, 1, 1, encounter_hour, tzinfo=UTC)
    return {
        "context_id": cid,
        "daily_fvg_id": f"D-{cid}",
        "daily_fvg_direction": direction,
        "direction": direction,
        "daily_lower": Decimal(lower),
        "daily_upper": Decimal(upper),
        "daily_created_known_at": encounter - timedelta(days=1),
        "encounter_bar_start": encounter - timedelta(hours=1),
        "encounter_known_at": encounter,
        "monthly_fvg_id": f"M-{cid}",
        "weekly_fvg_id": f"W-{cid}",
        "daily_active_fvg_id": f"D-{cid}",
    }


def test_request_boundary() -> None:
    params = acq.request_params("H1", acq.START, acq.START + timedelta(days=1))
    assert params["price"] == "M"
    assert params["granularity"] == "H1"
    assert params["dailyAlignment"] == "17"
    assert params["alignmentTimezone"] == "America/New_York"
    assert params["weeklyAlignment"] == "Friday"
    try:
        acq.request_params("M1", acq.START, acq.START + timedelta(hours=1))
    except acq.V4StructureError:
        pass
    else:
        raise AssertionError("M1 request must be impossible")
    try:
        acq.request_params("H1", acq.START, acq.END + timedelta(hours=1))
    except acq.V4StructureError:
        pass
    else:
        raise AssertionError("post-2023 request must be impossible")


def test_mid_only_parse() -> None:
    payload = b'{"instrument":"NAS100_USD","granularity":"H1","candles":[{"complete":true,"time":"2020-01-01T00:00:00Z","mid":{"o":"1","h":"2","l":"0","c":"1.5"},"volume":1}]}'
    rows = acq.parse_page(payload, "H1")
    assert len(rows) == 1 and rows[0]["close"] == "1.5"
    leaked = b'{"instrument":"NAS100_USD","granularity":"H1","candles":[{"complete":true,"time":"2020-01-01T00:00:00Z","mid":{"o":"1","h":"2","l":"0","c":"1.5"},"bid":{"o":"1","h":"2","l":"0","c":"1.5"},"volume":1}]}'
    try:
        acq.parse_page(leaked, "H1")
    except acq.V4StructureError:
        pass
    else:
        raise AssertionError("BID/ASK leakage must fail")


def test_fvg_geometry_and_mitigation() -> None:
    rows = [
        row(0, "100", "101", "99", "100"),
        row(1, "100", "103", "100", "102"),
        row(2, "103", "104", "102", "103"),
        row(3, "103", "105", "101", "104"),
    ]
    a = scan.primary_fvgs(rows, "H1")
    b = scan.independent_fvgs(rows, "H1")
    assert scan.compare_fvgs(a, b)
    assert a[0]["direction"] == "LONG"
    assert a[0]["lower"] == Decimal("101") and a[0]["upper"] == Decimal("102")
    enriched = scan.attach_mitigation(a, rows)
    assert enriched[0]["mitigation_known_at"] == rows[3]["close_time"]


def test_active_context_causality() -> None:
    base = {
        "granularity": "D",
        "direction": "LONG",
        "c1_index": 0,
        "c3_index": 2,
        "c1_start": datetime(2019, 12, 1, tzinfo=UTC),
        "c3_start": datetime(2019, 12, 3, tzinfo=UTC),
        "lower": Decimal("100"),
        "upper": Decimal("101"),
        "c3_close": Decimal("102"),
        "mitigation_bar_start": None,
    }
    old = dict(base, id="old", knowledge_time=datetime(2019, 12, 4, tzinfo=UTC), mitigation_known_at=None)
    new = dict(base, id="new", knowledge_time=datetime(2019, 12, 5, tzinfo=UTC), mitigation_known_at=datetime(2020, 1, 1, 12, tzinfo=UTC))
    assert scan.active_latest([old, new], datetime(2020, 1, 1, 11, tzinfo=UTC))["id"] == "new"
    assert scan.active_latest([old, new], datetime(2020, 1, 1, 12, tzinfo=UTC))["id"] == "old"


def test_long_and_short_trigger_symmetry() -> None:
    rows = [row(i, "100", str(110 + i), str(90 - i), "100") for i in range(12)]
    long_ctx = context("LONGCTX", "LONG", 2, "100", "105")
    short_ctx = context("SHORTCTX", "SHORT", 8, "95", "100")
    h1_fvgs = [
        fvg("LIN", "SHORT", 3, "101", "104", 0, 2, "102"),
        fvg("LOUT", "LONG", 4, "104", "106", 1, 3, "106"),
        fvg("SIN", "LONG", 9, "96", "99", 6, 8, "98"),
        fvg("SOUT", "SHORT", 10, "94", "96", 7, 9, "94"),
    ]
    contexts = [long_ctx, short_ctx]
    a, sa = scan.primary_triggers(contexts, h1_fvgs, rows)
    b, sb = scan.independent_triggers(contexts, h1_fvgs, rows)
    assert a == b and sa == sb
    assert len(a) == 2
    assert a[0]["direction"] == "LONG" and a[1]["direction"] == "SHORT"
    assert a[0]["stop_anchor"] == "87"
    assert a[1]["stop_anchor"] == "119"
    assert a[0]["trigger_knowledge_time_utc"].endswith("04:00:00Z")
    assert a[1]["trigger_knowledge_time_utc"].endswith("10:00:00Z")


def test_next_context_cutoff() -> None:
    rows = [row(i, "100", "110", "90", "100") for i in range(8)]
    contexts = [context("A", "LONG", 2, "100", "105"), context("B", "LONG", 5, "100", "105")]
    fvgs = [
        fvg("AIN", "SHORT", 3, "101", "104", 0, 2, "102"),
        fvg("TOO-LATE", "LONG", 5, "104", "106", 2, 4, "106"),
    ]
    triggers, stats = scan.primary_triggers(contexts, fvgs, rows)
    assert not any(t["context_id"] == "A" for t in triggers)
    assert stats["no_outbound_before_next_context"] >= 1


def main() -> None:
    test_request_boundary()
    test_mid_only_parse()
    test_fvg_geometry_and_mitigation()
    test_active_context_causality()
    test_long_and_short_trigger_symmetry()
    test_next_context_cutoff()
    print("V4 Sharp Turn trigger-seal offline and sabotage tests passed")


if __name__ == "__main__":
    main()
