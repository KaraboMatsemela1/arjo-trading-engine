#!/usr/bin/env python3
"""Independent block-index reference path for the frozen V5 trigger seal.

The primary path uses segment trees. This reference uses fixed-size blocks plus
exact within-block scans, preserving the same frozen inequalities while avoiding
an O(FVG * H1) brute-force runtime on 14 years of data.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import v5_nra_triggers as core


class BlockPairSearch:
    def __init__(self, candles: list[dict[str, Any]], block_size: int = 256) -> None:
        self.candles = candles
        self.block_size = block_size
        self.min_high, self.max_low, self.min_close = core.pair_values(candles)
        self.length = len(self.min_high)
        self.blocks: list[tuple[Decimal, Decimal, Decimal]] = []
        neg = Decimal("-Infinity")
        pos = Decimal("Infinity")
        for start in range(0, self.length, block_size):
            end = min(start + block_size, self.length)
            self.blocks.append(
                (
                    max(self.min_high[start:end], default=neg),
                    min(self.max_low[start:end], default=pos),
                    min(self.min_close[start:end], default=pos),
                )
            )

    def qualifies(self, index: int, lower: Decimal, upper: Decimal) -> bool:
        return (
            self.min_high[index] >= lower
            and self.max_low[index] <= upper
            and self.min_close[index] < lower
        )

    def first(self, start: int, lower: Decimal, upper: Decimal) -> int | None:
        if start >= self.length:
            return None
        block_size = self.block_size
        first_block = start // block_size
        first_end = min((first_block + 1) * block_size, self.length)
        for index in range(start, first_end):
            if self.qualifies(index, lower, upper):
                return index
        for block in range(first_block + 1, len(self.blocks)):
            max_min_high, min_max_low, min_min_close = self.blocks[block]
            if max_min_high < lower or min_max_low > upper or min_min_close >= lower:
                continue
            begin = block * block_size
            end = min(begin + block_size, self.length)
            for index in range(begin, end):
                if self.qualifies(index, lower, upper):
                    return index
        return None


class BlockCloseSearch:
    def __init__(self, candles: list[dict[str, Any]], block_size: int = 256) -> None:
        self.candles = candles
        self.block_size = block_size
        self.closes = [core.candle_decimal(candle, "close") for candle in candles]
        neg = Decimal("-Infinity")
        self.block_max: list[Decimal] = []
        for start in range(0, len(self.closes), block_size):
            self.block_max.append(max(self.closes[start : start + block_size], default=neg))

    def first_above(self, start: int, threshold: Decimal) -> int | None:
        length = len(self.closes)
        if start >= length:
            return None
        block_size = self.block_size
        first_block = start // block_size
        first_end = min((first_block + 1) * block_size, length)
        for index in range(start, first_end):
            if self.closes[index] > threshold:
                return index
        for block in range(first_block + 1, len(self.block_max)):
            if self.block_max[block] <= threshold:
                continue
            begin = block * block_size
            end = min(begin + block_size, length)
            for index in range(begin, end):
                if self.closes[index] > threshold:
                    return index
        return None


def reference_states_fast(
    candles: list[dict[str, Any]], fvgs: list[core.Fvg]
) -> list[core.ResistanceState]:
    pair_search = BlockPairSearch(candles)
    close_search = BlockCloseSearch(candles)
    states: list[core.ResistanceState] = []
    for fvg in fvgs:
        pair_index = pair_search.first(fvg.index + 1, fvg.lower, fvg.upper)
        states.append(core.state_from_pair(fvg, pair_index, candles, close_search))
    return states


def compare_reconstructions_fast(
    h4: list[dict[str, Any]], h1: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    swings = core.h4_swings(h4)
    fvgs = core.bearish_h1_fvgs(h1)
    primary_states = core.primary_states(h1, fvgs)
    reference_states = reference_states_fast(h1, fvgs)
    primary, primary_stats = core.trigger_records(primary_states, swings, h1)
    reference, reference_stats = core.trigger_records(reference_states, swings, h1)
    primary_sha = core.canonical_sha(primary)
    reference_sha = core.canonical_sha(reference)
    if primary != reference or primary_sha != reference_sha:
        raise AssertionError(
            "V5 segment-tree/block-index trigger mismatch: "
            f"{primary_sha} != {reference_sha}"
        )
    return primary, {
        "primary_stats": {"h4_swing_highs": len(swings), **primary_stats},
        "reference_stats": {"h4_swing_highs": len(swings), **reference_stats},
        "primary_trigger_sha256": primary_sha,
        "reference_trigger_sha256": reference_sha,
        "exact_match": True,
        "reference_algorithm": "FIXED_BLOCK_INDEX_PLUS_EXACT_SCAN",
    }
