"""Shared pre-SPEC evidence anti-bias checks.

This module deliberately targets outcome/performance language only. Strategy
semantics such as ``stop loss`` must remain available for later evidence work.
"""

from __future__ import annotations

import re

FORBIDDEN_PRE_SPEC = re.compile(
    r"(?:"
    r"\bwin\s*rate\b|"
    r"\bprofit\s*factor\b|"
    r"\bsharpe\b|"
    r"\bexpectancy\b|"
    r"\bp\s*&\s*l\b|"
    r"\bpnl\b|"
    r"\btrade\s*count\b|"
    r"\d+(?:\.\d+)?%|"
    r"\b(?:winner|winners|loser|losers)\b|"
    r"\b(?:won|lost)\s+(?:(?:a|an|the|\d+)\s+)?(?:trade|trades|position|positions)\b|"
    r"\b(?:winning|losing)\s+(?:trade|trades|day|week|month|streak)\b|"
    r"\b\d+\s+(?:order\s+blocks?|obs?|trades?|setups?|entries?|positions?)\s+(?:held|failed|won|lost|worked|profited)\b|"
    r"\bout\s+of\s+\d+\s+(?:order\s+blocks?|obs?|trades?|setups?|entries?|positions?)\b|"
    r"\bchance\s+of\s+(?:holding|failing|winning|losing|success|failure)\b"
    r")",
    re.IGNORECASE,
)


def contains_pre_spec_outcome(text: str) -> bool:
    """Return whether text exposes prohibited pre-SPEC outcome/performance language."""

    return FORBIDDEN_PRE_SPEC.search(text) is not None
