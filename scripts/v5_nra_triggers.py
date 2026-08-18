#!/usr/bin/env python3
"""Pure structural reconstruction for the frozen V5 No-Resistance AoO family.

This module never reads M1 data and never evaluates post-trigger outcomes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

UTC = timezone.utc


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def stamp(value: datetime) -> str:
    value = value.astimezone(UTC).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def dec(value: str | int | float | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def dec_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def digest(prefix: str, *parts: object) -> str:
    payload = "|".join([prefix, *(str(part) for part in parts)])
    return f"{prefix}-{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def candle_decimal(candle: dict[str, Any], field: str) -> Decimal:
    return dec(candle[field])


@dataclass(frozen=True)
class Swing:
    swing_id: str
    price: Decimal
    source_time: datetime
    confirmed_at: datetime


@dataclass(frozen=True)
class Fvg:
    fvg_id: str
    index: int
    lower: Decimal
    upper: Decimal
    knowledge_time: datetime
    c1_time: datetime
    c3_time: datetime


@dataclass(frozen=True)
class ResistanceState:
    fvg: Fvg
    pair_a_index: int | None
    pair_b_index: int | None
    selected_index: int | None
    rejection_high: Decimal | None
    stop_anchor: Decimal | None
    disrespect_index: int | None
    disrespect_time: datetime | None


def h4_swings(candles: list[dict[str, Any]]) -> list[Swing]:
    result: list[Swing] = []
    for index in range(1, len(candles) - 1):
        previous = candles[index - 1]
        middle = candles[index]
        following = candles[index + 1]
        middle_high = candle_decimal(middle, "high")
        if not (
            middle_high > candle_decimal(previous, "high")
            and middle_high > candle_decimal(following, "high")
        ):
            continue
        source_time = parse_time(middle["time"])
        confirmed_at = parse_time(following["time"]) + timedelta(hours=4)
        result.append(
            Swing(
                swing_id=digest(
                    "H4SH",
                    stamp(source_time),
                    dec_text(middle_high),
                    stamp(confirmed_at),
                ),
                price=middle_high,
                source_time=source_time,
                confirmed_at=confirmed_at,
            )
        )
    return result


def bearish_h1_fvgs(candles: list[dict[str, Any]]) -> list[Fvg]:
    result: list[Fvg] = []
    for index in range(2, len(candles)):
        c1 = candles[index - 2]
        c3 = candles[index]
        c1_low = candle_decimal(c1, "low")
        c3_high = candle_decimal(c3, "high")
        if c3_high >= c1_low:
            continue
        c1_time = parse_time(c1["time"])
        c3_time = parse_time(c3["time"])
        result.append(
            Fvg(
                fvg_id=digest(
                    "H1BFVG",
                    stamp(c1_time),
                    stamp(c3_time),
                    dec_text(c3_high),
                    dec_text(c1_low),
                ),
                index=index,
                lower=c3_high,
                upper=c1_low,
                knowledge_time=c3_time + timedelta(hours=1),
                c1_time=c1_time,
                c3_time=c3_time,
            )
        )
    return result


def pair_values(candles: list[dict[str, Any]]) -> tuple[list[Decimal], list[Decimal], list[Decimal]]:
    min_high: list[Decimal] = []
    max_low: list[Decimal] = []
    min_close: list[Decimal] = []
    for index in range(len(candles) - 1):
        a = candles[index]
        b = candles[index + 1]
        min_high.append(min(candle_decimal(a, "high"), candle_decimal(b, "high")))
        max_low.append(max(candle_decimal(a, "low"), candle_decimal(b, "low")))
        min_close.append(min(candle_decimal(a, "close"), candle_decimal(b, "close")))
    return min_high, max_low, min_close


class PairSearchTree:
    """Find the first pair satisfying the frozen FVG/2CR inequalities."""

    def __init__(self, candles: list[dict[str, Any]]) -> None:
        self.candles = candles
        values = pair_values(candles)
        self.length = len(values[0])
        size = 1
        while size < max(1, self.length):
            size *= 2
        self.size = size
        negative = Decimal("-Infinity")
        positive = Decimal("Infinity")
        self.max_min_high = [negative] * (2 * size)
        self.min_max_low = [positive] * (2 * size)
        self.min_min_close = [positive] * (2 * size)
        for index in range(self.length):
            leaf = size + index
            self.max_min_high[leaf] = values[0][index]
            self.min_max_low[leaf] = values[1][index]
            self.min_min_close[leaf] = values[2][index]
        for node in range(size - 1, 0, -1):
            left = node * 2
            right = left + 1
            self.max_min_high[node] = max(
                self.max_min_high[left], self.max_min_high[right]
            )
            self.min_max_low[node] = min(
                self.min_max_low[left], self.min_max_low[right]
            )
            self.min_min_close[node] = min(
                self.min_min_close[left], self.min_min_close[right]
            )

    def first(self, start: int, lower: Decimal, upper: Decimal) -> int | None:
        return self._first(1, 0, self.size, start, lower, upper)

    def _first(
        self,
        node: int,
        left: int,
        right: int,
        start: int,
        lower: Decimal,
        upper: Decimal,
    ) -> int | None:
        if right <= start or left >= self.length:
            return None
        if self.max_min_high[node] < lower:
            return None
        if self.min_max_low[node] > upper:
            return None
        if self.min_min_close[node] >= lower:
            return None
        if right - left == 1:
            return left if self._pair_qualifies(left, lower, upper) else None
        middle = (left + right) // 2
        found = self._first(node * 2, left, middle, start, lower, upper)
        if found is not None:
            return found
        return self._first(node * 2 + 1, middle, right, start, lower, upper)

    def _pair_qualifies(self, index: int, lower: Decimal, upper: Decimal) -> bool:
        a = self.candles[index]
        b = self.candles[index + 1]
        a_interacts = (
            candle_decimal(a, "high") >= lower
            and candle_decimal(a, "low") <= upper
        )
        b_interacts = (
            candle_decimal(b, "high") >= lower
            and candle_decimal(b, "low") <= upper
        )
        if not (a_interacts and b_interacts):
            return False
        return (
            candle_decimal(a, "close") < lower
            or candle_decimal(b, "close") < lower
        )


class MaxCloseTree:
    def __init__(self, candles: list[dict[str, Any]]) -> None:
        self.candles = candles
        self.length = len(candles)
        size = 1
        while size < max(1, self.length):
            size *= 2
        self.size = size
        negative = Decimal("-Infinity")
        self.maximum = [negative] * (2 * size)
        for index, candle in enumerate(candles):
            self.maximum[size + index] = candle_decimal(candle, "close")
        for node in range(size - 1, 0, -1):
            self.maximum[node] = max(
                self.maximum[node * 2], self.maximum[node * 2 + 1]
            )

    def first_above(self, start: int, threshold: Decimal) -> int | None:
        return self._first(1, 0, self.size, start, threshold)

    def _first(
        self,
        node: int,
        left: int,
        right: int,
        start: int,
        threshold: Decimal,
    ) -> int | None:
        if right <= start or left >= self.length or self.maximum[node] <= threshold:
            return None
        if right - left == 1:
            return left
        middle = (left + right) // 2
        found = self._first(node * 2, left, middle, start, threshold)
        if found is not None:
            return found
        return self._first(node * 2 + 1, middle, right, start, threshold)


def state_from_pair(
    fvg: Fvg,
    pair_index: int | None,
    candles: list[dict[str, Any]],
    close_tree: MaxCloseTree | None,
) -> ResistanceState:
    if pair_index is None:
        return ResistanceState(fvg, None, None, None, None, None, None, None)
    a_index = pair_index
    b_index = pair_index + 1
    a = candles[a_index]
    b = candles[b_index]
    a_rejects = (
        candle_decimal(a, "high") >= fvg.lower
        and candle_decimal(a, "low") <= fvg.upper
        and candle_decimal(a, "close") < fvg.lower
    )
    b_rejects = (
        candle_decimal(b, "high") >= fvg.lower
        and candle_decimal(b, "low") <= fvg.upper
        and candle_decimal(b, "close") < fvg.lower
    )
    selected_index = b_index if b_rejects else a_index
    if not (a_rejects or b_rejects):
        raise AssertionError("pair selected without a frozen rejection")
    rejection_high = candle_decimal(candles[selected_index], "high")
    stop_anchor = min(candle_decimal(a, "low"), candle_decimal(b, "low"))
    if close_tree is None:
        disrespect_index = None
        for index in range(selected_index + 1, len(candles)):
            if candle_decimal(candles[index], "close") > rejection_high:
                disrespect_index = index
                break
    else:
        disrespect_index = close_tree.first_above(selected_index + 1, rejection_high)
    disrespect_time = None
    if disrespect_index is not None:
        disrespect_time = parse_time(candles[disrespect_index]["time"]) + timedelta(hours=1)
    return ResistanceState(
        fvg=fvg,
        pair_a_index=a_index,
        pair_b_index=b_index,
        selected_index=selected_index,
        rejection_high=rejection_high,
        stop_anchor=stop_anchor,
        disrespect_index=disrespect_index,
        disrespect_time=disrespect_time,
    )


def primary_states(candles: list[dict[str, Any]], fvgs: list[Fvg]) -> list[ResistanceState]:
    pair_tree = PairSearchTree(candles)
    close_tree = MaxCloseTree(candles)
    result: list[ResistanceState] = []
    for fvg in fvgs:
        pair_index = pair_tree.first(fvg.index + 1, fvg.lower, fvg.upper)
        result.append(state_from_pair(fvg, pair_index, candles, close_tree))
    return result


def independent_states(
    candles: list[dict[str, Any]], fvgs: list[Fvg]
) -> list[ResistanceState]:
    result: list[ResistanceState] = []
    for fvg in fvgs:
        pair_index = None
        for index in range(fvg.index + 1, len(candles) - 1):
            a = candles[index]
            b = candles[index + 1]
            a_interacts = (
                candle_decimal(a, "high") >= fvg.lower
                and candle_decimal(a, "low") <= fvg.upper
            )
            b_interacts = (
                candle_decimal(b, "high") >= fvg.lower
                and candle_decimal(b, "low") <= fvg.upper
            )
            if not (a_interacts and b_interacts):
                continue
            if not (
                candle_decimal(a, "close") < fvg.lower
                or candle_decimal(b, "close") < fvg.lower
            ):
                continue
            pair_index = index
            break
        result.append(state_from_pair(fvg, pair_index, candles, None))
    return result


def select_target(
    swings: list[Swing], trigger_close: Decimal, knowledge_time: datetime
) -> Swing | None:
    eligible = [
        swing
        for swing in swings
        if swing.confirmed_at <= knowledge_time and swing.price > trigger_close
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda swing: (
            swing.price,
            swing.confirmed_at,
            swing.source_time,
            swing.swing_id,
        ),
    )


def zone_blocks(fvg: Fvg, trigger_close: Decimal, target: Decimal) -> bool:
    return fvg.upper > trigger_close and fvg.lower < target


def trigger_records(
    states: list[ResistanceState],
    swings: list[Swing],
    h1: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    stats = {
        "resistance_fvgs": len(states),
        "with_2cr_pair": 0,
        "with_disrespect": 0,
        "without_causal_target": 0,
        "blocked_by_other_resistance": 0,
        "signals": 0,
    }
    for state in states:
        if state.pair_a_index is not None:
            stats["with_2cr_pair"] += 1
        if state.disrespect_index is None or state.disrespect_time is None:
            continue
        stats["with_disrespect"] += 1
        trigger_candle = h1[state.disrespect_index]
        trigger_close = candle_decimal(trigger_candle, "close")
        target = select_target(swings, trigger_close, state.disrespect_time)
        if target is None:
            stats["without_causal_target"] += 1
            continue
        blockers = []
        for other in states:
            if other.fvg.fvg_id == state.fvg.fvg_id:
                continue
            if other.fvg.knowledge_time > state.disrespect_time:
                continue
            if (
                other.disrespect_time is not None
                and other.disrespect_time <= state.disrespect_time
            ):
                continue
            if zone_blocks(other.fvg, trigger_close, target.price):
                blockers.append(other.fvg.fvg_id)
        if blockers:
            stats["blocked_by_other_resistance"] += 1
            continue
        if state.stop_anchor is None or state.rejection_high is None:
            raise AssertionError("disrespect event missing frozen pair state")
        pair_a = h1[state.pair_a_index]
        pair_b = h1[state.pair_b_index]
        selected = h1[state.selected_index]
        trigger_time = state.disrespect_time
        trigger_id = digest(
            "V5NRA",
            state.fvg.fvg_id,
            stamp(trigger_time),
            target.swing_id,
            dec_text(state.stop_anchor),
        )
        records.append(
            {
                "trigger_id": trigger_id,
                "knowledge_time_utc": stamp(trigger_time),
                "direction": "LONG",
                "trigger_h1_start_utc": stamp(parse_time(trigger_candle["time"])),
                "trigger_close": dec_text(trigger_close),
                "selected_resistance_fvg_id": state.fvg.fvg_id,
                "resistance_lower": dec_text(state.fvg.lower),
                "resistance_upper": dec_text(state.fvg.upper),
                "resistance_knowledge_time_utc": stamp(state.fvg.knowledge_time),
                "pair_a_h1_start_utc": stamp(parse_time(pair_a["time"])),
                "pair_b_h1_start_utc": stamp(parse_time(pair_b["time"])),
                "selected_rejection_h1_start_utc": stamp(parse_time(selected["time"])),
                "rejection_high": dec_text(state.rejection_high),
                "stop_anchor": dec_text(state.stop_anchor),
                "target_h4_swing_id": target.swing_id,
                "target_price": dec_text(target.price),
                "target_source_h4_start_utc": stamp(target.source_time),
                "target_confirmed_at_utc": stamp(target.confirmed_at),
                "other_active_overhead_resistance_count": 0,
            }
        )
    records.sort(key=lambda row: (row["knowledge_time_utc"], row["trigger_id"]))
    stats["signals"] = len(records)
    return records, stats


def reconstruct(
    h4: list[dict[str, Any]], h1: list[dict[str, Any]], independent: bool = False
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    swings = h4_swings(h4)
    fvgs = bearish_h1_fvgs(h1)
    states = independent_states(h1, fvgs) if independent else primary_states(h1, fvgs)
    records, stats = trigger_records(states, swings, h1)
    stats = {"h4_swing_highs": len(swings), **stats}
    return records, stats


def compare_reconstructions(
    h4: list[dict[str, Any]], h1: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    primary, primary_stats = reconstruct(h4, h1, independent=False)
    reference, reference_stats = reconstruct(h4, h1, independent=True)
    primary_sha = canonical_sha(primary)
    reference_sha = canonical_sha(reference)
    if primary != reference or primary_sha != reference_sha:
        raise AssertionError(
            "V5 primary/reference trigger reconstruction mismatch: "
            f"{primary_sha} != {reference_sha}"
        )
    return primary, {
        "primary_stats": primary_stats,
        "reference_stats": reference_stats,
        "primary_trigger_sha256": primary_sha,
        "reference_trigger_sha256": reference_sha,
        "exact_match": True,
    }
