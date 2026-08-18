#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable, Iterable

RESOLVED = {"STOP", "TARGET"}


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def ts(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("naive timestamp")
    return result.astimezone(UTC)


def zulu(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def deduplicate(triggers: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for trigger in triggers:
        groups[trigger["trigger_knowledge_time_utc"]].append(trigger)
    kept: list[dict] = []
    skipped: list[dict] = []
    for knowledge in sorted(groups):
        candidates = sorted(groups[knowledge], key=lambda x: x["trigger_id"])
        winner = candidates[0]
        kept.append(winner)
        for trigger in candidates[1:]:
            skipped.append(
                {
                    "trigger_id": trigger["trigger_id"],
                    "knowledge_time_utc": knowledge,
                    "direction": trigger["direction"],
                    "status": "SKIPPED_DUPLICATE_TRIGGER_TIME",
                    "kept_trigger_id": winner["trigger_id"],
                }
            )
    return kept, skipped


def _entry(trigger: dict, first: dict, slip: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    direction = trigger["direction"]
    stop = dec(trigger["stop_anchor"])
    if direction == "LONG":
        entry = dec(first["ask"]["o"]) + slip
        risk = entry - stop
        target = entry + Decimal("2") * risk
    elif direction == "SHORT":
        entry = dec(first["bid"]["o"]) - slip
        risk = stop - entry
        target = entry - Decimal("2") * risk
    else:
        raise ValueError(f"unsupported direction {direction}")
    return entry, stop, target


def measure_trade(
    trigger: dict,
    bars: Iterable[dict],
    *,
    slip_points: Decimal,
    financing_r_per_1440: Decimal,
    dataset_end: datetime,
    max_wait_hours: int = 72,
) -> dict:
    knowledge = ts(trigger["trigger_knowledge_time_utc"])
    iterator = iter(bars)
    first = None
    for bar in iterator:
        start = ts(bar["ts_start_utc"])
        if start < knowledge:
            continue
        first = bar
        break
    if first is None:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
            "direction": trigger["direction"],
            "status": "RIGHT_CENSORED_DATASET_END",
            "reason": "NO_M1_BEFORE_DATASET_END",
        }
    first_ts = ts(first["ts_start_utc"])
    if (first_ts - knowledge).total_seconds() > max_wait_hours * 3600:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
            "direction": trigger["direction"],
            "status": "DATA_INTEGRITY_FAILURE",
            "reason": "NO_ELIGIBLE_M1_WITHIN_72H",
            "first_observed_m1_start_utc": first["ts_start_utc"],
        }

    entry, stop, target = _entry(trigger, first, slip_points)
    direction = trigger["direction"]
    risk = entry - stop if direction == "LONG" else stop - entry
    if risk <= 0:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
            "direction": direction,
            "entry_ts_utc": first["ts_start_utc"],
            "entry_price": str(entry),
            "stop_price": str(stop),
            "status": "INVALID_RISK_ORDERING",
        }

    def evaluate_bar(bar: dict, held: int) -> dict | None:
        if direction == "LONG":
            component = bar["bid"]
            o, h, l = dec(component["o"]), dec(component["h"]), dec(component["l"])
            stop_hit, target_hit = l <= stop, h >= target
            if stop_hit:
                raw = o if o <= stop else stop
                exit_price = raw - slip_points
                status = "STOP"
            elif target_hit:
                exit_price = target - slip_points
                status = "TARGET"
            else:
                return None
            gross = (exit_price - entry) / risk
        else:
            component = bar["ask"]
            o, h, l = dec(component["o"]), dec(component["h"]), dec(component["l"])
            stop_hit, target_hit = h >= stop, l <= target
            if stop_hit:
                raw = o if o >= stop else stop
                exit_price = raw + slip_points
                status = "STOP"
            elif target_hit:
                exit_price = target + slip_points
                status = "TARGET"
            else:
                return None
            gross = (entry - exit_price) / risk
        financing = financing_r_per_1440 * Decimal(held) / Decimal(1440)
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
            "direction": direction,
            "entry_ts_utc": first["ts_start_utc"],
            "exit_ts_utc": bar["ts_start_utc"],
            "status": status,
            "entry_price": str(entry),
            "stop_price": str(stop),
            "target_price": str(target),
            "exit_price": str(exit_price),
            "risk_points": str(risk),
            "complete_m1_bars_held": held,
            "gross_r": float(gross),
            "financing_r": float(financing),
            "net_r": float(gross - financing),
            "same_m1_stop_and_target": bool(stop_hit and target_hit),
        }

    held = 1
    result = evaluate_bar(first, held)
    if result is not None:
        return result
    for bar in iterator:
        start = ts(bar["ts_start_utc"])
        if start >= dataset_end:
            break
        held += 1
        result = evaluate_bar(bar, held)
        if result is not None:
            return result
    return {
        "trigger_id": trigger["trigger_id"],
        "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
        "direction": direction,
        "entry_ts_utc": first["ts_start_utc"],
        "entry_price": str(entry),
        "stop_price": str(stop),
        "target_price": str(target),
        "risk_points": str(risk),
        "complete_m1_bars_observed": held,
        "status": "RIGHT_CENSORED_DATASET_END",
    }


def evaluate_portfolio(
    triggers: list[dict],
    iter_bars: Callable[[datetime], Iterable[dict]],
    *,
    scenario: str,
    slip_points: Decimal,
    financing_r_per_1440: Decimal,
    dataset_end: datetime,
) -> dict:
    kept, duplicate_skips = deduplicate(triggers)
    ledger = list(duplicate_skips)
    open_until: datetime | None = None
    censored_open = False
    for trigger in kept:
        knowledge = ts(trigger["trigger_knowledge_time_utc"])
        if censored_open or (open_until is not None and knowledge <= open_until):
            ledger.append(
                {
                    "trigger_id": trigger["trigger_id"],
                    "knowledge_time_utc": trigger["trigger_knowledge_time_utc"],
                    "direction": trigger["direction"],
                    "status": "SKIPPED_CONCURRENT_POSITION",
                    "prior_position_exit_m1_start_utc": zulu(open_until) if open_until else None,
                }
            )
            continue
        result = measure_trade(
            trigger,
            iter_bars(knowledge),
            slip_points=slip_points,
            financing_r_per_1440=financing_r_per_1440,
            dataset_end=dataset_end,
        )
        ledger.append(result)
        if result["status"] in RESOLVED:
            open_until = ts(result["exit_ts_utc"])
        elif result["status"] == "RIGHT_CENSORED_DATASET_END" and "entry_ts_utc" in result:
            open_until = dataset_end
            censored_open = True
    ledger.sort(key=lambda x: (x.get("knowledge_time_utc", ""), x["trigger_id"], x["status"]))
    return {"scenario": scenario, "ledger": ledger, "ledger_sha256": canon(ledger)}


def _profit_factor(values: list[float]) -> tuple[float, bool, float, float]:
    positive = sum(x for x in values if x > 0)
    negative = sum(x for x in values if x < 0)
    if negative == 0:
        return (math.inf if positive > 0 else 0.0), True, positive, negative
    return positive / abs(negative), False, positive, negative


def _max_drawdown(values: list[float]) -> float:
    equity = peak = worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def _bootstrap(values: list[float], n: int = 10000, seed: int = 20260817) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(seed)
    size = len(values)
    means = [sum(values[rng.randrange(size)] for _ in range(size)) / size for _ in range(n)]
    means.sort()
    return means[int(0.025 * (n - 1))], means[int(0.975 * (n - 1))]


def metrics(portfolio: dict) -> dict:
    ledger = portfolio["ledger"]
    resolved = [row for row in ledger if row["status"] in RESOLVED]
    values = [float(row["net_r"]) for row in resolved]
    pf, no_losses, positive, negative = _profit_factor(values)
    years: dict[str, list[float]] = defaultdict(list)
    for row in resolved:
        years[str(ts(row["entry_ts_utc"]).year)].append(float(row["net_r"]))
    year_expectancy = {year: sum(vals) / len(vals) for year, vals in sorted(years.items())}
    lo, hi = _bootstrap(values)
    status_counts = dict(sorted(Counter(row["status"] for row in ledger).items()))
    out = {
        "scenario": portfolio["scenario"],
        "ledger_sha256": portfolio["ledger_sha256"],
        "resolved_executed_trades": len(resolved),
        "long_trades": sum(1 for row in resolved if row["direction"] == "LONG"),
        "short_trades": sum(1 for row in resolved if row["direction"] == "SHORT"),
        "total_ledger_rows": len(ledger),
        "status_counts": status_counts,
        "data_integrity_failures": status_counts.get("DATA_INTEGRITY_FAILURE", 0),
        "synthetic_fills": 0,
        "skipped_duplicate_signals": status_counts.get("SKIPPED_DUPLICATE_TRIGGER_TIME", 0),
        "skipped_concurrent_signals": status_counts.get("SKIPPED_CONCURRENT_POSITION", 0),
        "invalid_risk_signals": status_counts.get("INVALID_RISK_ORDERING", 0),
        "right_censored_signals": status_counts.get("RIGHT_CENSORED_DATASET_END", 0),
        "net_expectancy_r": sum(values) / len(values) if values else None,
        "median_net_r": statistics.median(values) if values else None,
        "profit_factor": None if math.isinf(pf) else pf,
        "no_negative_trades": no_losses,
        "positive_r_sum": positive,
        "negative_r_sum": negative,
        "win_rate": sum(1 for value in values if value > 0) / len(values) if values else None,
        "max_drawdown_r": _max_drawdown(values),
        "bootstrap_95pct_ci_net_expectancy_r": [lo, hi],
        "calendar_year_net_expectancy_r": year_expectancy,
        "positive_calendar_year_fraction": (
            sum(1 for value in year_expectancy.values() if value > 0) / len(year_expectancy)
            if year_expectancy
            else None
        ),
        "unique_entry_dates": len({row["entry_ts_utc"][:10] for row in resolved}),
    }
    out["metrics_sha256"] = canon(out)
    return out


def _pf_threshold(metrics_: dict) -> float:
    if metrics_["no_negative_trades"] and metrics_["positive_r_sum"] > 0:
        return math.inf
    return float(metrics_["profit_factor"] or 0.0)


def classify(base: dict, stress: dict) -> str:
    if base["resolved_executed_trades"] < 100:
        return "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    base_pf = _pf_threshold(base)
    stress_pf = _pf_threshold(stress)
    lower = base["bootstrap_95pct_ci_net_expectancy_r"][0]
    preliminary = (
        base["net_expectancy_r"] is not None
        and base["net_expectancy_r"] > 0
        and base_pf > 1.2
        and lower is not None
        and lower > 0
        and stress["net_expectancy_r"] is not None
        and stress["net_expectancy_r"] > 0
        and stress_pf > 1.0
        and base["data_integrity_failures"] == 0
        and stress["data_integrity_failures"] == 0
        and base["synthetic_fills"] == 0
        and stress["synthetic_fills"] == 0
    )
    if not preliminary:
        return "EDGE_NOT_ESTABLISHED"
    strong = (
        base["resolved_executed_trades"] >= 250
        and base_pf > 1.3
        and lower is not None
        and lower > 0
        and stress["net_expectancy_r"] is not None
        and stress["net_expectancy_r"] > 0
        and (base["positive_calendar_year_fraction"] or 0) >= 0.7
        and base["data_integrity_failures"] == 0
    )
    return "STRONG_HISTORICAL_EDGE" if strong else "PRELIMINARY_HISTORICAL_EDGE"
