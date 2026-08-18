#!/usr/bin/env python3
"""Reconstruct and seal V4 Sharp Turn triggers from structure-only candles.

No M1 reader, fill evaluator, target/stop traversal evaluator, P&L calculator, or
broker mutation path exists in this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from bisect import bisect_left
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
START = datetime(2010, 1, 1, tzinfo=UTC)
END = datetime(2024, 1, 1, tzinfo=UTC)
NY = ZoneInfo("America/New_York")
GRANULARITIES = ("M", "W", "D", "H1")
MIN_DISTINCT_KNOWLEDGE_TIMES = 100


class V4TriggerSealError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise V4TriggerSealError("naive timestamp")
    return dt.astimezone(UTC)


def zulu(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def candle_close_time(start: datetime, granularity: str) -> datetime:
    if granularity == "H1":
        return start + timedelta(hours=1)
    local = start.astimezone(NY)
    if granularity == "D":
        return (local + timedelta(days=1)).astimezone(UTC)
    if granularity == "W":
        return (local + timedelta(days=7)).astimezone(UTC)
    if granularity == "M":
        year = local.year + (1 if local.month == 12 else 0)
        month = 1 if local.month == 12 else local.month + 1
        next_local = datetime(
            year,
            month,
            1,
            local.hour,
            local.minute,
            local.second,
            local.microsecond,
            tzinfo=NY,
        )
        return next_local.astimezone(UTC)
    raise V4TriggerSealError(f"unsupported granularity {granularity}")


def read_jsonl(path: Path, granularity: str) -> list[dict]:
    rows = []
    prior = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("granularity") != granularity:
                raise V4TriggerSealError(f"granularity mismatch in {path}")
            start = parse_utc(raw["ts_start_utc"])
            if not START <= start < END:
                raise V4TriggerSealError("structure row outside frozen interval")
            if prior is not None and start <= prior:
                raise V4TriggerSealError("structure rows not strictly increasing")
            prior = start
            o, h, l, c = map(dec, (raw["open"], raw["high"], raw["low"], raw["close"]))
            if h < max(o, c) or l > min(o, c) or h < l:
                raise V4TriggerSealError("invalid OHLC envelope")
            rows.append(
                {
                    "start": start,
                    "close_time": candle_close_time(start, granularity),
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "granularity": granularity,
                    "source": raw,
                }
            )
    if not rows:
        raise V4TriggerSealError(f"empty {granularity} structure")
    return rows


def verify_protocol(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(protocol)
    recorded = unsigned.pop("protocol_sha256", "")
    if recorded != PROTOCOL_SHA or canon(unsigned) != PROTOCOL_SHA:
        raise V4TriggerSealError("protocol SHA drift")
    if protocol["status"] != "FROZEN_BEFORE_V4_MARKET_OUTCOME_ACCESS":
        raise V4TriggerSealError("protocol status drift")
    market = protocol["market_data"]
    if market["structure_granularities"] != list(GRANULARITIES):
        raise V4TriggerSealError("structure granularity drift")
    if market["structure_price"] != "MID" or market["execution_price"] != "M1 BID/ASK":
        raise V4TriggerSealError("price component boundary drift")
    if market["request_m1_only_after_v4_trigger_set_is_sealed"] is not True:
        raise V4TriggerSealError("M1 stage boundary drift")
    if market["historical_window_classification"] != "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT":
        raise V4TriggerSealError("historical classification drift")
    if protocol["metrics"]["minimum_resolved_executed_trades"] != MIN_DISTINCT_KNOWLEDGE_TIMES:
        raise V4TriggerSealError("minimum sample drift")
    if protocol["authorization"]["paper_execution"] or protocol["authorization"]["live_execution"] or protocol["authorization"]["broker_mutation"]:
        raise V4TriggerSealError("execution authorization drift")
    return protocol


def find_one(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise V4TriggerSealError(f"expected exactly one {name}, found {len(matches)}")
    return matches[0]


def verify_manifest(root: Path) -> dict:
    manifest = json.loads(find_one(root, "NAS100_USD.v4-structure-manifest.json").read_text())
    unsigned = dict(manifest)
    recorded = unsigned.pop("manifest_sha256", "")
    if not recorded or canon(unsigned) != recorded:
        raise V4TriggerSealError("structure manifest integrity failure")
    expected = {
        "status": "V4_SHARP_TURN_STRUCTURE_READY",
        "protocol_sha256": PROTOCOL_SHA,
        "provider": "OANDA_V20",
        "environment": "practice",
        "instrument": "NAS100_USD",
        "price_component_requested": "M",
        "semantic_price_component": "MID",
        "granularities_requested": list(GRANULARITIES),
        "requested_start": "2010-01-01T00:00:00Z",
        "requested_end_exclusive": "2024-01-01T00:00:00Z",
        "historical_window_classification": "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT",
        "m1_data_requested": False,
        "bid_ask_data_requested": False,
        "fills_evaluated": False,
        "economic_outcomes_evaluated": False,
        "performance_metrics_accessed": False,
        "mutation_endpoints_used": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise V4TriggerSealError(f"structure boundary drift: {key}")
    for granularity in GRANULARITIES:
        if granularity not in manifest["timeframes"]:
            raise V4TriggerSealError(f"missing {granularity} manifest")
    return manifest


def intersects(low1: Decimal, high1: Decimal, low2: Decimal, high2: Decimal) -> bool:
    return max(low1, low2) <= min(high1, high2)


def fvg_id(granularity: str, direction: str, c1: dict, c3: dict, lower: Decimal, upper: Decimal) -> str:
    payload = {
        "tf": granularity,
        "direction": direction,
        "c1": zulu(c1["start"]),
        "c3": zulu(c3["start"]),
        "lower": str(lower),
        "upper": str(upper),
    }
    return f"FVG-{granularity}-{canon(payload)[:24]}"


def attach_mitigation(fvgs: list[dict], rows: list[dict]) -> list[dict]:
    result = []
    for fvg in fvgs:
        item = dict(fvg)
        item["mitigation_known_at"] = None
        item["mitigation_bar_start"] = None
        for row in rows[fvg["c3_index"] + 1 :]:
            if intersects(row["low"], row["high"], fvg["lower"], fvg["upper"]):
                item["mitigation_known_at"] = row["close_time"]
                item["mitigation_bar_start"] = row["start"]
                break
        result.append(item)
    return result


def primary_fvgs(rows: list[dict], granularity: str, with_mitigation: bool = False) -> list[dict]:
    result = []
    for i in range(2, len(rows)):
        c1, c3 = rows[i - 2], rows[i]
        direction = None
        lower = upper = None
        if c3["low"] > c1["high"]:
            direction, lower, upper = "LONG", c1["high"], c3["low"]
        elif c3["high"] < c1["low"]:
            direction, lower, upper = "SHORT", c3["high"], c1["low"]
        if direction is None:
            continue
        result.append(
            {
                "id": fvg_id(granularity, direction, c1, c3, lower, upper),
                "granularity": granularity,
                "direction": direction,
                "c1_index": i - 2,
                "c3_index": i,
                "c1_start": c1["start"],
                "c3_start": c3["start"],
                "knowledge_time": c3["close_time"],
                "lower": lower,
                "upper": upper,
                "c3_close": c3["close"],
            }
        )
    return attach_mitigation(result, rows) if with_mitigation else result


def independent_fvgs(rows: list[dict], granularity: str, with_mitigation: bool = False) -> list[dict]:
    result = []
    for offset, (c1, _c2, c3) in enumerate(zip(rows, rows[1:], rows[2:])):
        candidates = []
        if c1["high"] < c3["low"]:
            candidates.append(("LONG", c1["high"], c3["low"]))
        if c1["low"] > c3["high"]:
            candidates.append(("SHORT", c3["high"], c1["low"]))
        for direction, lower, upper in candidates:
            result.append(
                {
                    "id": fvg_id(granularity, direction, c1, c3, lower, upper),
                    "granularity": granularity,
                    "direction": direction,
                    "c1_index": offset,
                    "c3_index": offset + 2,
                    "c1_start": c1["start"],
                    "c3_start": c3["start"],
                    "knowledge_time": c3["close_time"],
                    "lower": lower,
                    "upper": upper,
                    "c3_close": c3["close"],
                }
            )
    if not with_mitigation:
        return result
    enriched = []
    for fvg in result:
        later_hits = [
            row
            for row in rows[fvg["c3_index"] + 1 :]
            if intersects(row["low"], row["high"], fvg["lower"], fvg["upper"])
        ]
        item = dict(fvg)
        if later_hits:
            item["mitigation_known_at"] = later_hits[0]["close_time"]
            item["mitigation_bar_start"] = later_hits[0]["start"]
        else:
            item["mitigation_known_at"] = None
            item["mitigation_bar_start"] = None
        enriched.append(item)
    return enriched


def active_latest(fvgs: list[dict], reference: datetime) -> dict | None:
    candidates = [
        fvg
        for fvg in fvgs
        if fvg["knowledge_time"] <= reference
        and (fvg["mitigation_known_at"] is None or fvg["mitigation_known_at"] > reference)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda f: (f["knowledge_time"], f["id"]))[-1]


def first_h1_encounter(daily_fvg: dict, h1_rows: list[dict], starts: list[datetime]) -> dict | None:
    index = bisect_left(starts, daily_fvg["knowledge_time"])
    for row in h1_rows[index:]:
        if intersects(row["low"], row["high"], daily_fvg["lower"], daily_fvg["upper"]):
            return row
    return None


def context_record(daily: dict, encounter: dict, monthly: dict, weekly: dict, active_daily: dict) -> dict:
    payload = {
        "daily_fvg_id": daily["id"],
        "encounter_bar_start": zulu(encounter["start"]),
        "direction": active_daily["direction"],
        "monthly": monthly["id"],
        "weekly": weekly["id"],
        "daily_active": active_daily["id"],
    }
    return {
        "context_id": f"V4CTX-{canon(payload)[:24]}",
        "daily_fvg_id": daily["id"],
        "daily_fvg_direction": daily["direction"],
        "direction": active_daily["direction"],
        "daily_lower": daily["lower"],
        "daily_upper": daily["upper"],
        "daily_created_known_at": daily["knowledge_time"],
        "encounter_bar_start": encounter["start"],
        "encounter_known_at": encounter["close_time"],
        "monthly_fvg_id": monthly["id"],
        "weekly_fvg_id": weekly["id"],
        "daily_active_fvg_id": active_daily["id"],
    }


def primary_contexts(m_fvgs: list[dict], w_fvgs: list[dict], d_fvgs: list[dict], h1_rows: list[dict]) -> tuple[list[dict], dict]:
    starts = [r["start"] for r in h1_rows]
    stats = Counter()
    contexts = []
    for daily in d_fvgs:
        stats["daily_fvgs"] += 1
        encounter = first_h1_encounter(daily, h1_rows, starts)
        if encounter is None:
            stats["no_h1_encounter"] += 1
            continue
        reference = encounter["start"]
        m = active_latest(m_fvgs, reference)
        w = active_latest(w_fvgs, reference)
        d = active_latest(d_fvgs, reference)
        if m is None or w is None or d is None:
            stats["missing_direction_context"] += 1
            continue
        if d["id"] != daily["id"]:
            stats["daily_not_latest_active"] += 1
            continue
        directions = {m["direction"], w["direction"], d["direction"]}
        if len(directions) != 1:
            stats["direction_conflict"] += 1
            continue
        contexts.append(context_record(daily, encounter, m, w, d))
        stats["selected_contexts"] += 1
    contexts.sort(key=lambda c: (c["encounter_known_at"], c["context_id"]))
    return contexts, dict(sorted(stats.items()))


def independent_contexts(m_fvgs: list[dict], w_fvgs: list[dict], d_fvgs: list[dict], h1_rows: list[dict]) -> tuple[list[dict], dict]:
    stats = Counter()
    contexts = []
    eligible_h1 = [(r["start"], r) for r in h1_rows]
    for daily in d_fvgs:
        stats["daily_fvgs"] += 1
        encounter_candidates = [
            r
            for start, r in eligible_h1
            if start >= daily["knowledge_time"]
            and intersects(r["low"], r["high"], daily["lower"], daily["upper"])
        ]
        if not encounter_candidates:
            stats["no_h1_encounter"] += 1
            continue
        encounter = encounter_candidates[0]
        reference = encounter["start"]
        selected = []
        for pool in (m_fvgs, w_fvgs, d_fvgs):
            active = [
                f
                for f in pool
                if f["knowledge_time"] <= reference
                and (f["mitigation_known_at"] is None or reference < f["mitigation_known_at"])
            ]
            selected.append(max(active, key=lambda f: (f["knowledge_time"], f["id"])) if active else None)
        m, w, d = selected
        if any(x is None for x in selected):
            stats["missing_direction_context"] += 1
            continue
        if d["id"] != daily["id"]:
            stats["daily_not_latest_active"] += 1
            continue
        if not (m["direction"] == w["direction"] == d["direction"]):
            stats["direction_conflict"] += 1
            continue
        contexts.append(context_record(daily, encounter, m, w, d))
        stats["selected_contexts"] += 1
    contexts.sort(key=lambda c: (c["encounter_known_at"], c["context_id"]))
    return contexts, dict(sorted(stats.items()))


def make_trigger(context: dict, inbound: dict, outbound: dict, h1_rows: list[dict]) -> dict:
    interval = h1_rows[inbound["c1_index"] : outbound["c3_index"] + 1]
    if not interval:
        raise V4TriggerSealError("empty stop interval")
    direction = context["direction"]
    if direction == "LONG":
        stop = min(r["low"] for r in interval)
        extreme_row = next(r for r in interval if r["low"] == stop)
    else:
        stop = max(r["high"] for r in interval)
        extreme_row = next(r for r in interval if r["high"] == stop)
    payload = {
        "context_id": context["context_id"],
        "inbound": inbound["id"],
        "outbound": outbound["id"],
        "direction": direction,
        "knowledge": zulu(outbound["knowledge_time"]),
        "stop": str(stop),
    }
    return {
        "trigger_id": f"V4ST-{canon(payload)[:28]}",
        "context_id": context["context_id"],
        "daily_fvg_id": context["daily_fvg_id"],
        "direction": direction,
        "monthly_fvg_id": context["monthly_fvg_id"],
        "weekly_fvg_id": context["weekly_fvg_id"],
        "daily_active_fvg_id": context["daily_active_fvg_id"],
        "daily_fvg_lower": str(context["daily_lower"]),
        "daily_fvg_upper": str(context["daily_upper"]),
        "daily_context_created_known_at_utc": zulu(context["daily_created_known_at"]),
        "daily_encounter_bar_start_utc": zulu(context["encounter_bar_start"]),
        "daily_encounter_known_at_utc": zulu(context["encounter_known_at"]),
        "inbound_h1_fvg_id": inbound["id"],
        "inbound_h1_fvg_c1_start_utc": zulu(inbound["c1_start"]),
        "inbound_h1_fvg_known_at_utc": zulu(inbound["knowledge_time"]),
        "outbound_h1_fvg_id": outbound["id"],
        "outbound_h1_fvg_c3_start_utc": zulu(outbound["c3_start"]),
        "trigger_knowledge_time_utc": zulu(outbound["knowledge_time"]),
        "stop_anchor": str(stop),
        "stop_extreme_bar_start_utc": zulu(extreme_row["start"]),
    }


def primary_triggers(contexts: list[dict], h1_fvgs: list[dict], h1_rows: list[dict]) -> tuple[list[dict], dict]:
    stats = Counter()
    result = []
    for index, context in enumerate(contexts):
        cutoff = contexts[index + 1]["encounter_known_at"] if index + 1 < len(contexts) else END
        start = context["encounter_known_at"]
        direction = context["direction"]
        inbound_direction = "SHORT" if direction == "LONG" else "LONG"
        inbound = None
        for fvg in h1_fvgs:
            if fvg["knowledge_time"] < start:
                continue
            if fvg["knowledge_time"] >= cutoff:
                break
            if fvg["direction"] == inbound_direction and intersects(
                fvg["lower"], fvg["upper"], context["daily_lower"], context["daily_upper"]
            ):
                inbound = fvg
                break
        if inbound is None:
            stats["no_inbound_fvg"] += 1
            continue
        outbound = None
        for fvg in h1_fvgs:
            if fvg["knowledge_time"] <= inbound["knowledge_time"]:
                continue
            if fvg["knowledge_time"] >= cutoff:
                break
            qualifies = (
                direction == "LONG"
                and fvg["direction"] == "LONG"
                and fvg["c3_close"] > context["daily_upper"]
            ) or (
                direction == "SHORT"
                and fvg["direction"] == "SHORT"
                and fvg["c3_close"] < context["daily_lower"]
            )
            if qualifies:
                outbound = fvg
                break
        if outbound is None:
            stats["no_outbound_before_next_context"] += 1
            continue
        result.append(make_trigger(context, inbound, outbound, h1_rows))
        stats["triggers"] += 1
    result.sort(key=lambda t: (t["trigger_knowledge_time_utc"], t["trigger_id"]))
    return result, dict(sorted(stats.items()))


def independent_triggers(contexts: list[dict], h1_fvgs: list[dict], h1_rows: list[dict]) -> tuple[list[dict], dict]:
    stats = Counter()
    result = []
    for index, context in enumerate(contexts):
        start = context["encounter_known_at"]
        cutoff = contexts[index + 1]["encounter_known_at"] if index + 1 < len(contexts) else END
        wanted_inbound = "SHORT" if context["direction"] == "LONG" else "LONG"
        inbound_candidates = [
            f
            for f in h1_fvgs
            if start <= f["knowledge_time"] < cutoff
            and f["direction"] == wanted_inbound
            and intersects(f["lower"], f["upper"], context["daily_lower"], context["daily_upper"])
        ]
        if not inbound_candidates:
            stats["no_inbound_fvg"] += 1
            continue
        inbound = min(inbound_candidates, key=lambda f: (f["knowledge_time"], f["id"]))
        outbound_candidates = []
        for f in h1_fvgs:
            if not inbound["knowledge_time"] < f["knowledge_time"] < cutoff:
                continue
            if context["direction"] == "LONG":
                ok = f["direction"] == "LONG" and f["c3_close"] > context["daily_upper"]
            else:
                ok = f["direction"] == "SHORT" and f["c3_close"] < context["daily_lower"]
            if ok:
                outbound_candidates.append(f)
        if not outbound_candidates:
            stats["no_outbound_before_next_context"] += 1
            continue
        outbound = min(outbound_candidates, key=lambda f: (f["knowledge_time"], f["id"]))
        result.append(make_trigger(context, inbound, outbound, h1_rows))
        stats["triggers"] += 1
    result.sort(key=lambda t: (t["trigger_knowledge_time_utc"], t["trigger_id"]))
    return result, dict(sorted(stats.items()))


def serial_fvg(fvg: dict) -> dict:
    return {
        "id": fvg["id"],
        "granularity": fvg["granularity"],
        "direction": fvg["direction"],
        "c1_index": fvg["c1_index"],
        "c3_index": fvg["c3_index"],
        "c1_start": zulu(fvg["c1_start"]),
        "c3_start": zulu(fvg["c3_start"]),
        "knowledge_time": zulu(fvg["knowledge_time"]),
        "lower": str(fvg["lower"]),
        "upper": str(fvg["upper"]),
        "c3_close": str(fvg["c3_close"]),
        "mitigation_known_at": zulu(fvg["mitigation_known_at"]) if fvg.get("mitigation_known_at") else None,
        "mitigation_bar_start": zulu(fvg["mitigation_bar_start"]) if fvg.get("mitigation_bar_start") else None,
    }


def compare_fvgs(a: list[dict], b: list[dict]) -> bool:
    return [serial_fvg(x) for x in a] == [serial_fvg(x) for x in b]


def build(artifact_dir: Path, protocol_path: Path) -> dict:
    protocol = verify_protocol(protocol_path)
    manifest = verify_manifest(artifact_dir)
    rows = {
        granularity: read_jsonl(find_one(artifact_dir, f"NAS100_USD.{granularity}.jsonl"), granularity)
        for granularity in GRANULARITIES
    }

    primary = {
        tf: primary_fvgs(rows[tf], tf, with_mitigation=tf in {"M", "W", "D"})
        for tf in GRANULARITIES
    }
    independent = {
        tf: independent_fvgs(rows[tf], tf, with_mitigation=tf in {"M", "W", "D"})
        for tf in GRANULARITIES
    }
    for tf in GRANULARITIES:
        if not compare_fvgs(primary[tf], independent[tf]):
            raise V4TriggerSealError(f"independent FVG mismatch: {tf}")

    contexts_a, context_stats_a = primary_contexts(primary["M"], primary["W"], primary["D"], rows["H1"])
    contexts_b, context_stats_b = independent_contexts(independent["M"], independent["W"], independent["D"], rows["H1"])
    if contexts_a != contexts_b or context_stats_a != context_stats_b:
        raise V4TriggerSealError("independent Daily-context mismatch")

    triggers_a, trigger_stats_a = primary_triggers(contexts_a, primary["H1"], rows["H1"])
    triggers_b, trigger_stats_b = independent_triggers(contexts_b, independent["H1"], rows["H1"])
    if triggers_a != triggers_b or trigger_stats_a != trigger_stats_b:
        raise V4TriggerSealError("independent Sharp Turn trigger mismatch")

    knowledge_times = sorted({t["trigger_knowledge_time_utc"] for t in triggers_a})
    years = Counter(parse_utc(t["trigger_knowledge_time_utc"]).year for t in triggers_a)
    directions = Counter(t["direction"] for t in triggers_a)
    necessary = len(knowledge_times) >= MIN_DISTINCT_KNOWLEDGE_TIMES
    classification = (
        "TRIGGER_SAMPLE_NECESSARY_CONDITION_MET"
        if necessary
        else "INSUFFICIENT_TRIGGER_SAMPLE_EDGE_NOT_ESTABLISHED"
    )
    report = {
        "schema_version": 1,
        "status": "V4_SHARP_TURN_TRIGGERS_READY",
        "classification": classification,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": PROTOCOL_SHA,
        "structure_manifest_sha256": manifest["manifest_sha256"],
        "structure_retrieval_sha256": manifest["retrieval_sha256"],
        "provider": "OANDA_V20",
        "environment": "practice",
        "instrument": "NAS100_USD",
        "structure_price": "MID",
        "structure_granularities": list(GRANULARITIES),
        "historical_start": "2010-01-01T00:00:00Z",
        "historical_end_exclusive": "2024-01-01T00:00:00Z",
        "historical_window_classification": "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT",
        "structure_rows": {tf: len(rows[tf]) for tf in GRANULARITIES},
        "fvg_counts": {tf: len(primary[tf]) for tf in GRANULARITIES},
        "context_status_counts": context_stats_a,
        "trigger_status_counts": trigger_stats_a,
        "selected_daily_contexts": len(contexts_a),
        "trigger_count": len(triggers_a),
        "long_triggers": directions.get("LONG", 0),
        "short_triggers": directions.get("SHORT", 0),
        "distinct_trigger_knowledge_times": len(knowledge_times),
        "minimum_distinct_knowledge_times_required": MIN_DISTINCT_KNOWLEDGE_TIMES,
        "sample_necessary_condition_met": necessary,
        "triggers_by_year": {str(year): years[year] for year in sorted(years)},
        "trigger_set_sha256": canon(triggers_a),
        "sealed_triggers": triggers_a,
        "primary_independent_fvg_exact_match": True,
        "primary_independent_context_exact_match": True,
        "primary_independent_trigger_exact_match": True,
        "m1_data_requested": False,
        "bid_ask_data_requested": False,
        "fill_prices_accessed": False,
        "stop_target_traversal_accessed": False,
        "pnl_accessed": False,
        "expectancy_accessed": False,
        "profit_factor_accessed": False,
        "win_rate_accessed": False,
        "bootstrap_metrics_accessed": False,
        "economic_outcomes_accessed": False,
        "v3c_trade_ledger_accessed_for_v4_selection": False,
        "parameter_refit_performed": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    report["report_sha256"] = canon(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument(
        "--protocol",
        default="research/profitability/v4_sharp_turn_execution_protocol_v1.json",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = build(Path(args.artifact_dir), Path(args.protocol))
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"V4 Sharp Turn trigger seal failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "classification": report["classification"],
                "triggers": report["trigger_count"],
                "long": report["long_triggers"],
                "short": report["short_triggers"],
                "distinct_knowledge_times": report["distinct_trigger_knowledge_times"],
                "sample_necessary_condition_met": report["sample_necessary_condition_met"],
                "trigger_set_sha256": report["trigger_set_sha256"],
                "economic_outcomes_accessed": False,
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
