#!/usr/bin/env python3
"""Deterministic evaluator for preregistered NQ calibration execution variants.

This module does not detect Arjo setups. It consumes pre-qualified occurrences
produced under the frozen semantic seed and evaluates only the preregistered
execution conventions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

ALLOWED_FILL_EVENTS = {"SECOND_STING_TOUCH", "SECOND_STING_15M_CLOSE"}
ALLOWED_STOP_BUFFERS = {0, 1, 2}


class ReplayError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayBar:
    ts: datetime
    high: float
    low: float


@dataclass(frozen=True)
class SeedOccurrence:
    occurrence_id: str
    tick_size: float
    second_sting_touch_ts: datetime | None
    second_sting_touch_price: float | None
    second_sting_close_ts: datetime | None
    second_sting_close_price: float | None
    order_flow_leg_low: float
    target_price: float
    bars_after_activation: tuple[ReplayBar, ...]


def load_replay_spec(path: str | Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    conventions = spec.get("calibration_only_conventions", {})
    if set(conventions.get("second_sting_fill_event", [])) != ALLOWED_FILL_EVENTS:
        raise ReplayError("replay spec fill variants differ from preregistration")
    if set(conventions.get("stop_buffer_ticks", [])) != ALLOWED_STOP_BUFFERS:
        raise ReplayError("replay spec stop variants differ from preregistration")
    if spec.get("fixed_semantics", {}).get("direction") != "long":
        raise ReplayError("only the locked long seed is supported")
    return spec


def _entry(occurrence: SeedOccurrence, fill_event: str) -> tuple[datetime, float] | None:
    if fill_event == "SECOND_STING_TOUCH":
        if occurrence.second_sting_touch_ts is None or occurrence.second_sting_touch_price is None:
            return None
        return occurrence.second_sting_touch_ts, occurrence.second_sting_touch_price
    if fill_event == "SECOND_STING_15M_CLOSE":
        if occurrence.second_sting_close_ts is None or occurrence.second_sting_close_price is None:
            return None
        return occurrence.second_sting_close_ts, occurrence.second_sting_close_price
    raise ReplayError(f"unsupported fill event {fill_event}")


def evaluate_variant(occurrence: SeedOccurrence, *, fill_event: str, stop_buffer_ticks: int) -> dict:
    if fill_event not in ALLOWED_FILL_EVENTS:
        raise ReplayError("fill event was not preregistered")
    if stop_buffer_ticks not in ALLOWED_STOP_BUFFERS:
        raise ReplayError("stop buffer was not preregistered")
    if occurrence.tick_size <= 0:
        raise ReplayError("tick_size must be positive provider/instrument metadata")
    if occurrence.target_price <= occurrence.order_flow_leg_low:
        raise ReplayError("target must be above the bullish Order Flow stop anchor")

    entry = _entry(occurrence, fill_event)
    if entry is None:
        return {
            "occurrence_id": occurrence.occurrence_id,
            "fill_event": fill_event,
            "stop_buffer_ticks": stop_buffer_ticks,
            "status": "NO_TRADE_PARAMETER_NOT_MET",
        }

    entry_ts, entry_price = entry
    stop_price = occurrence.order_flow_leg_low - stop_buffer_ticks * occurrence.tick_size
    if entry_price <= stop_price:
        raise ReplayError("entry price must be above stop price for locked long seed")

    eligible = sorted((bar for bar in occurrence.bars_after_activation if bar.ts >= entry_ts), key=lambda b: b.ts)
    for bar in eligible:
        hit_stop = bar.low <= stop_price
        hit_target = bar.high >= occurrence.target_price
        if hit_stop and hit_target:
            return {
                "occurrence_id": occurrence.occurrence_id,
                "fill_event": fill_event,
                "stop_buffer_ticks": stop_buffer_ticks,
                "status": "AMBIGUOUS_INTRABAR_ORDER",
                "entry_ts": entry_ts.isoformat(),
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target_price": occurrence.target_price,
                "event_ts": bar.ts.isoformat(),
            }
        if hit_stop:
            status = "STOP_FIRST"
        elif hit_target:
            status = "TARGET_FIRST"
        else:
            continue
        return {
            "occurrence_id": occurrence.occurrence_id,
            "fill_event": fill_event,
            "stop_buffer_ticks": stop_buffer_ticks,
            "status": status,
            "entry_ts": entry_ts.isoformat(),
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": occurrence.target_price,
            "event_ts": bar.ts.isoformat(),
        }

    return {
        "occurrence_id": occurrence.occurrence_id,
        "fill_event": fill_event,
        "stop_buffer_ticks": stop_buffer_ticks,
        "status": "UNRESOLVED_WINDOW_END",
        "entry_ts": entry_ts.isoformat(),
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": occurrence.target_price,
    }


def evaluate_occurrence(occurrence: SeedOccurrence) -> list[dict]:
    results: list[dict] = []
    for fill_event in sorted(ALLOWED_FILL_EVENTS):
        for buffer_ticks in sorted(ALLOWED_STOP_BUFFERS):
            results.append(evaluate_variant(occurrence, fill_event=fill_event, stop_buffer_ticks=buffer_ticks))
    return results


def summarize(results: Iterable[dict]) -> dict:
    counts: dict[str, int] = {}
    total = 0
    for result in results:
        total += 1
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    return {"total_variant_results": total, "status_counts": dict(sorted(counts.items()))}
