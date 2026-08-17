#!/usr/bin/env python3
"""Pure deterministic V3-C profitability measurement engine.

No provider I/O lives here. All trading/economic mechanics are frozen in
v3c_arguments_execution_protocol_v1.json and v3c_profitability_execution_lock_v1.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable, Iterable

RESOLVED = {"STOP", "TARGET", "EXPIRY"}


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def ts(value: str) -> datetime:
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("naive timestamp")
    return d.astimezone(UTC)


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def deduplicate(triggers: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in triggers:
        groups[row["activation_known_at_utc"]].append(row)
    kept, skipped = [], []
    for knowledge in sorted(groups):
        candidates = sorted(groups[knowledge], key=lambda x: (x["swing_confirmed_at_utc"], x["trigger_id"]))
        winner = candidates[-1]
        kept.append(winner)
        for row in candidates[:-1]:
            skipped.append({
                "trigger_id": row["trigger_id"],
                "knowledge_time_utc": knowledge,
                "status": "SKIPPED_DUPLICATE_KNOWLEDGE_TIME",
                "kept_trigger_id": winner["trigger_id"],
            })
    return kept, skipped


def measure_trade(trigger: dict, bars: list[dict], *, slip_points: Decimal, financing_r_per_1440: Decimal) -> dict:
    knowledge = ts(trigger["activation_known_at_utc"])
    eligible = [b for b in bars if ts(b["ts_start_utc"]) >= knowledge]
    if not eligible or (ts(eligible[0]["ts_start_utc"]) - knowledge).total_seconds() > 72 * 3600:
        return {"trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"], "status": "DATA_INTEGRITY_FAILURE", "reason": "NO_ELIGIBLE_M1_WITHIN_72H"}

    first = eligible[0]
    entry = dec(first["ask"]["o"]) + slip_points
    stop = dec(trigger["rejection_low"])
    risk = entry - stop
    if risk <= 0:
        return {
            "trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"],
            "entry_ts_utc": first["ts_start_utc"], "entry_price": str(entry), "stop_price": str(stop),
            "status": "INVALID_RISK_ORDERING",
        }
    target = entry + Decimal("2") * risk
    usable = eligible[:1440]
    for idx, bar in enumerate(usable):
        bo, bh, bl = dec(bar["bid"]["o"]), dec(bar["bid"]["h"]), dec(bar["bid"]["l"])
        stop_hit, target_hit = bl <= stop, bh >= target
        if stop_hit:
            raw_exit = bo if bo <= stop else stop
            exit_price = raw_exit - slip_points
            status = "STOP"
        elif target_hit:
            exit_price = target - slip_points
            status = "TARGET"
        else:
            continue
        held = idx + 1
        gross_r = (exit_price - entry) / risk
        financing = financing_r_per_1440 * Decimal(held) / Decimal(1440)
        net_r = gross_r - financing
        return {
            "trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"],
            "entry_ts_utc": first["ts_start_utc"], "exit_ts_utc": bar["ts_start_utc"], "status": status,
            "entry_price": str(entry), "stop_price": str(stop), "target_price": str(target), "exit_price": str(exit_price),
            "risk_points": str(risk), "complete_m1_bars_held": held, "gross_r": float(gross_r),
            "financing_r": float(financing), "net_r": float(net_r), "same_m1_stop_and_target": bool(stop_hit and target_hit),
        }

    if len(usable) < 1440:
        return {
            "trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"],
            "entry_ts_utc": first["ts_start_utc"], "entry_price": str(entry), "stop_price": str(stop),
            "target_price": str(target), "risk_points": str(risk), "complete_m1_bars_observed": len(usable),
            "status": "RIGHT_CENSORED_OOS_END",
        }

    final = usable[-1]
    exit_price = dec(final["bid"]["c"]) - slip_points
    gross_r = (exit_price - entry) / risk
    financing = financing_r_per_1440
    net_r = gross_r - financing
    return {
        "trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"],
        "entry_ts_utc": first["ts_start_utc"], "exit_ts_utc": final["ts_start_utc"], "status": "EXPIRY",
        "entry_price": str(entry), "stop_price": str(stop), "target_price": str(target), "exit_price": str(exit_price),
        "risk_points": str(risk), "complete_m1_bars_held": 1440, "gross_r": float(gross_r),
        "financing_r": float(financing), "net_r": float(net_r), "same_m1_stop_and_target": False,
    }


def evaluate_portfolio(
    triggers: list[dict],
    get_bars: Callable[[datetime, int], list[dict]],
    *,
    scenario: str,
    slip_points: Decimal,
    financing_r_per_1440: Decimal,
) -> dict:
    kept, duplicate_skips = deduplicate(triggers)
    ledger: list[dict] = list(duplicate_skips)
    open_until: datetime | None = None
    for trigger in kept:
        knowledge = ts(trigger["activation_known_at_utc"])
        if open_until is not None and knowledge <= open_until:
            ledger.append({
                "trigger_id": trigger["trigger_id"], "knowledge_time_utc": trigger["activation_known_at_utc"],
                "status": "SKIPPED_CONCURRENT_POSITION", "prior_position_exit_m1_start_utc": open_until.isoformat().replace("+00:00", "Z"),
            })
            continue
        bars = get_bars(knowledge, 1440)
        result = measure_trade(trigger, bars, slip_points=slip_points, financing_r_per_1440=financing_r_per_1440)
        ledger.append(result)
        if result["status"] in RESOLVED:
            open_until = ts(result["exit_ts_utc"])
    ledger.sort(key=lambda x: (x.get("knowledge_time_utc", ""), x["trigger_id"], x["status"]))
    return {"scenario": scenario, "ledger": ledger, "ledger_sha256": canon(ledger)}


def _pf(values: list[float]) -> tuple[float, bool, float, float]:
    positive = sum(v for v in values if v > 0)
    negative = sum(v for v in values if v < 0)
    if negative == 0:
        return math.inf if positive > 0 else 0.0, True, positive, negative
    return positive / abs(negative), False, positive, negative


def _max_dd(values: list[float]) -> float:
    equity = peak = 0.0
    worst = 0.0
    for v in values:
        equity += v
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _bootstrap(values: list[float], *, n: int = 10000, seed: int = 20260817) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(seed)
    size = len(values)
    means = [sum(values[rng.randrange(size)] for _ in range(size)) / size for _ in range(n)]
    means.sort()
    lo = means[int(0.025 * (n - 1))]
    hi = means[int(0.975 * (n - 1))]
    return lo, hi


def metrics(portfolio: dict) -> dict:
    ledger = portfolio["ledger"]
    resolved = [x for x in ledger if x["status"] in RESOLVED]
    values = [float(x["net_r"]) for x in resolved]
    pf, no_losses, pos, neg = _pf(values)
    years: dict[str, list[float]] = defaultdict(list)
    for x in resolved:
        years[str(ts(x["entry_ts_utc"]).year)].append(float(x["net_r"]))
    year_expectancy = {y: sum(v) / len(v) for y, v in sorted(years.items())}
    lo, hi = _bootstrap(values)
    statuses = dict(sorted(Counter(x["status"] for x in ledger).items()))
    result = {
        "scenario": portfolio["scenario"],
        "ledger_sha256": portfolio["ledger_sha256"],
        "resolved_executed_trades": len(resolved),
        "total_ledger_rows": len(ledger),
        "status_counts": statuses,
        "data_integrity_failures": statuses.get("DATA_INTEGRITY_FAILURE", 0),
        "synthetic_fills": 0,
        "skipped_duplicate_signals": statuses.get("SKIPPED_DUPLICATE_KNOWLEDGE_TIME", 0),
        "skipped_concurrent_signals": statuses.get("SKIPPED_CONCURRENT_POSITION", 0),
        "invalid_risk_signals": statuses.get("INVALID_RISK_ORDERING", 0),
        "right_censored_signals": statuses.get("RIGHT_CENSORED_OOS_END", 0),
        "net_expectancy_r": sum(values) / len(values) if values else None,
        "median_net_r": sorted(values)[len(values) // 2] if values else None,
        "profit_factor": None if math.isinf(pf) else pf,
        "profit_factor_threshold_value": pf,
        "no_negative_trades": no_losses,
        "positive_r_sum": pos,
        "negative_r_sum": neg,
        "win_rate": sum(1 for v in values if v > 0) / len(values) if values else None,
        "max_drawdown_r": _max_dd(values),
        "bootstrap_95pct_ci_net_expectancy_r": [lo, hi],
        "calendar_year_net_expectancy_r": year_expectancy,
        "positive_calendar_year_fraction": (sum(1 for v in year_expectancy.values() if v > 0) / len(year_expectancy)) if year_expectancy else None,
        "unique_entry_dates": len({x["entry_ts_utc"][:10] for x in resolved}),
    }
    result["metrics_sha256"] = canon({k: v for k, v in result.items() if k != "profit_factor_threshold_value"})
    return result


def classify(base: dict, stress: dict) -> str:
    if base["resolved_executed_trades"] < 100:
        return "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    base_pf = float(base["profit_factor_threshold_value"])
    stress_pf = float(stress["profit_factor_threshold_value"])
    lo = base["bootstrap_95pct_ci_net_expectancy_r"][0]
    preliminary = (
        base["net_expectancy_r"] is not None and base["net_expectancy_r"] > 0
        and base_pf > 1.2
        and lo is not None and lo > 0
        and stress["net_expectancy_r"] is not None and stress["net_expectancy_r"] > 0
        and stress_pf > 1.0
        and base["data_integrity_failures"] == 0
        and stress["data_integrity_failures"] == 0
        and base["synthetic_fills"] == 0 and stress["synthetic_fills"] == 0
    )
    if not preliminary:
        return "EDGE_NOT_ESTABLISHED"
    strong = (
        base["resolved_executed_trades"] >= 250
        and base_pf > 1.3
        and lo is not None and lo > 0
        and stress["net_expectancy_r"] is not None and stress["net_expectancy_r"] > 0
        and (base["positive_calendar_year_fraction"] or 0) >= 0.7
        and base["data_integrity_failures"] == 0
    )
    return "STRONG_HISTORICAL_EDGE" if strong else "PRELIMINARY_PROFITABLE_EDGE"
