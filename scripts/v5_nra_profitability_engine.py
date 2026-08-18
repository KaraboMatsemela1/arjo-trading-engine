#!/usr/bin/env python3
"""Frozen V5 No-Resistance AoO M1 economic measurement primitives.

Pure logic only: this module performs no network I/O.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable

RESOLVED = {"STOP", "TARGET", "EXPIRY"}
BOOTSTRAP_SEED = 20260818
BOOTSTRAP_REPLICATES = 10000


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("naive timestamp")
    return parsed.astimezone(UTC)


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def deduplicate(triggers: list[dict]) -> tuple[list[dict], list[dict]]:
    """Freeze same-knowledge handling to lexicographically smallest trigger id."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in triggers:
        groups[row["knowledge_time_utc"]].append(row)
    kept: list[dict] = []
    skipped: list[dict] = []
    for knowledge in sorted(groups):
        candidates = sorted(groups[knowledge], key=lambda row: row["trigger_id"])
        winner = candidates[0]
        kept.append(winner)
        for row in candidates[1:]:
            skipped.append(
                {
                    "trigger_id": row["trigger_id"],
                    "knowledge_time_utc": knowledge,
                    "status": "SKIPPED_DUPLICATE_KNOWLEDGE_TIME",
                    "kept_trigger_id": winner["trigger_id"],
                }
            )
    kept.sort(key=lambda row: (row["knowledge_time_utc"], row["trigger_id"]))
    return kept, skipped


def measure_trade(
    trigger: dict,
    bars: list[dict],
    *,
    slip_points: Decimal,
    financing_r_per_1440: Decimal,
) -> dict:
    knowledge = ts(trigger["knowledge_time_utc"])
    eligible = [bar for bar in bars if ts(bar["ts_start_utc"]) >= knowledge]
    if not eligible or (
        ts(eligible[0]["ts_start_utc"]) - knowledge
    ).total_seconds() > 72 * 3600:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["knowledge_time_utc"],
            "status": "DATA_INTEGRITY_FAILURE",
            "reason": "NO_ELIGIBLE_M1_WITHIN_72H",
        }

    first = eligible[0]
    raw_entry = dec(first["ask"]["o"])
    stop = dec(trigger["stop_anchor"])
    target = dec(trigger["target_price"])
    if stop >= raw_entry:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["knowledge_time_utc"],
            "entry_ts_utc": first["ts_start_utc"],
            "raw_entry_price": str(raw_entry),
            "stop_price": str(stop),
            "target_price": str(target),
            "status": "INVALID_RISK_ORDERING",
            "reason": "STOP_NOT_STRICTLY_BELOW_RAW_ENTRY",
        }
    if target <= raw_entry:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["knowledge_time_utc"],
            "entry_ts_utc": first["ts_start_utc"],
            "raw_entry_price": str(raw_entry),
            "stop_price": str(stop),
            "target_price": str(target),
            "status": "INVALID_TARGET_ORDERING",
            "reason": "TARGET_NOT_STRICTLY_ABOVE_RAW_ENTRY",
        }

    entry = raw_entry + slip_points
    risk = entry - stop
    if risk <= 0:
        raise AssertionError("positive frozen risk violated after adverse entry slippage")
    usable = eligible[:1440]
    for index, bar in enumerate(usable):
        bid_open = dec(bar["bid"]["o"])
        bid_high = dec(bar["bid"]["h"])
        bid_low = dec(bar["bid"]["l"])
        stop_hit = bid_low <= stop
        target_hit = bid_high >= target
        if stop_hit:
            raw_exit = bid_open if bid_open < stop else stop
            exit_price = raw_exit - slip_points
            status = "STOP"
        elif target_hit:
            exit_price = target - slip_points
            status = "TARGET"
        else:
            continue
        held = index + 1
        gross = (exit_price - entry) / risk
        financing = financing_r_per_1440 * Decimal(held) / Decimal(1440)
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["knowledge_time_utc"],
            "entry_ts_utc": first["ts_start_utc"],
            "exit_ts_utc": bar["ts_start_utc"],
            "status": status,
            "raw_entry_price": str(raw_entry),
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

    if len(usable) < 1440:
        return {
            "trigger_id": trigger["trigger_id"],
            "knowledge_time_utc": trigger["knowledge_time_utc"],
            "entry_ts_utc": first["ts_start_utc"],
            "raw_entry_price": str(raw_entry),
            "entry_price": str(entry),
            "stop_price": str(stop),
            "target_price": str(target),
            "risk_points": str(risk),
            "complete_m1_bars_observed": len(usable),
            "status": "RIGHT_CENSORED_OOS_END",
        }

    final = usable[-1]
    exit_price = dec(final["bid"]["c"]) - slip_points
    gross = (exit_price - entry) / risk
    return {
        "trigger_id": trigger["trigger_id"],
        "knowledge_time_utc": trigger["knowledge_time_utc"],
        "entry_ts_utc": first["ts_start_utc"],
        "exit_ts_utc": final["ts_start_utc"],
        "status": "EXPIRY",
        "raw_entry_price": str(raw_entry),
        "entry_price": str(entry),
        "stop_price": str(stop),
        "target_price": str(target),
        "exit_price": str(exit_price),
        "risk_points": str(risk),
        "complete_m1_bars_held": 1440,
        "gross_r": float(gross),
        "financing_r": float(financing_r_per_1440),
        "net_r": float(gross - financing_r_per_1440),
        "same_m1_stop_and_target": False,
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
    ledger = list(duplicate_skips)
    open_until: datetime | None = None
    for trigger in kept:
        knowledge = ts(trigger["knowledge_time_utc"])
        if open_until is not None and knowledge <= open_until:
            ledger.append(
                {
                    "trigger_id": trigger["trigger_id"],
                    "knowledge_time_utc": trigger["knowledge_time_utc"],
                    "status": "SKIPPED_CONCURRENT_POSITION",
                    "prior_position_exit_m1_start_utc": open_until.isoformat().replace(
                        "+00:00", "Z"
                    ),
                }
            )
            continue
        result = measure_trade(
            trigger,
            get_bars(knowledge, 1440),
            slip_points=slip_points,
            financing_r_per_1440=financing_r_per_1440,
        )
        ledger.append(result)
        if result["status"] in RESOLVED:
            open_until = ts(result["exit_ts_utc"])
    ledger.sort(
        key=lambda row: (
            row.get("knowledge_time_utc", ""),
            row["trigger_id"],
            row["status"],
        )
    )
    return {"scenario": scenario, "ledger": ledger, "ledger_sha256": canon(ledger)}


def _profit_factor(values: list[float]) -> tuple[float, bool, float, float]:
    positive = sum(value for value in values if value > 0)
    negative = sum(value for value in values if value < 0)
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


def _bootstrap(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(BOOTSTRAP_SEED)
    size = len(values)
    means = [
        sum(values[rng.randrange(size)] for _ in range(size)) / size
        for _ in range(BOOTSTRAP_REPLICATES)
    ]
    means.sort()
    return means[int(0.025 * (BOOTSTRAP_REPLICATES - 1))], means[
        int(0.975 * (BOOTSTRAP_REPLICATES - 1))
    ]


def metrics(portfolio: dict) -> dict:
    ledger = portfolio["ledger"]
    resolved = [row for row in ledger if row["status"] in RESOLVED]
    values = [float(row["net_r"]) for row in resolved]
    pf, no_losses, positive, negative = _profit_factor(values)
    years: dict[str, list[float]] = defaultdict(list)
    for row in resolved:
        years[str(ts(row["entry_ts_utc"]).year)].append(float(row["net_r"]))
    year_expectancy = {
        year: sum(year_values) / len(year_values)
        for year, year_values in sorted(years.items())
    }
    lower, upper = _bootstrap(values)
    statuses = dict(sorted(Counter(row["status"] for row in ledger).items()))
    output = {
        "scenario": portfolio["scenario"],
        "ledger_sha256": portfolio["ledger_sha256"],
        "resolved_executed_trades": len(resolved),
        "total_ledger_rows": len(ledger),
        "status_counts": statuses,
        "data_integrity_failures": statuses.get("DATA_INTEGRITY_FAILURE", 0),
        "synthetic_fills": 0,
        "skipped_duplicate_signals": statuses.get(
            "SKIPPED_DUPLICATE_KNOWLEDGE_TIME", 0
        ),
        "skipped_concurrent_signals": statuses.get("SKIPPED_CONCURRENT_POSITION", 0),
        "invalid_risk_signals": statuses.get("INVALID_RISK_ORDERING", 0),
        "invalid_target_signals": statuses.get("INVALID_TARGET_ORDERING", 0),
        "right_censored_signals": statuses.get("RIGHT_CENSORED_OOS_END", 0),
        "net_expectancy_r": sum(values) / len(values) if values else None,
        "median_net_r": statistics.median(values) if values else None,
        "profit_factor": None if math.isinf(pf) else pf,
        "no_negative_trades": no_losses,
        "positive_r_sum": positive,
        "negative_r_sum": negative,
        "win_rate": sum(1 for value in values if value > 0) / len(values)
        if values
        else None,
        "max_drawdown_r": _max_drawdown(values),
        "bootstrap_95pct_ci_net_expectancy_r": [lower, upper],
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "calendar_year_net_expectancy_r": year_expectancy,
        "positive_calendar_year_fraction": sum(
            1 for value in year_expectancy.values() if value > 0
        )
        / len(year_expectancy)
        if year_expectancy
        else None,
        "unique_entry_dates": len({row["entry_ts_utc"][:10] for row in resolved}),
    }
    output["metrics_sha256"] = canon(output)
    return output


def pf_threshold_value(metrics_: dict) -> float:
    if metrics_["no_negative_trades"] and metrics_["positive_r_sum"] > 0:
        return math.inf
    return float(metrics_["profit_factor"] or 0.0)


def classify(base: dict, stress: dict, independent_trigger_exact: bool = True) -> str:
    if base["resolved_executed_trades"] < 100:
        return "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
    base_pf = pf_threshold_value(base)
    stress_pf = pf_threshold_value(stress)
    lower = base["bootstrap_95pct_ci_net_expectancy_r"][0]
    passed = (
        independent_trigger_exact
        and base["net_expectancy_r"] is not None
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
    return "V5_HISTORICAL_EDGE_ESTABLISHED" if passed else "EDGE_NOT_ESTABLISHED"
