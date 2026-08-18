#!/usr/bin/env python3
"""Frozen time-boundary helpers for V4 Sharp Turn structure.

OANDA aligned higher-timeframe candles may have timestamps inside a requested
window while their OHLC coverage crosses the frozen start or end. Canonical V4
structure admits only candles whose entire interval is contained in
[2010-01-01T00:00:00Z, 2024-01-01T00:00:00Z).
"""
from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
START = datetime(2010, 1, 1, tzinfo=UTC)
END = datetime(2024, 1, 1, tzinfo=UTC)
GRANULARITIES = ("M", "W", "D", "H1")


class V4BoundaryError(RuntimeError):
    pass


def zulu(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def candle_end(start: datetime, granularity: str) -> datetime:
    if start.utcoffset() is None:
        raise V4BoundaryError("candle start must be timezone aware")
    start = start.astimezone(UTC)
    if granularity == "H1":
        return start + timedelta(hours=1)
    local = start.astimezone(NY)
    if granularity == "D":
        target = local.date() + timedelta(days=1)
        return datetime(target.year, target.month, target.day, 17, tzinfo=NY).astimezone(UTC)
    if granularity == "W":
        target = local.date() + timedelta(days=7)
        return datetime(target.year, target.month, target.day, 17, tzinfo=NY).astimezone(UTC)
    if granularity == "M":
        year = local.year + (1 if local.month == 12 else 0)
        month = 1 if local.month == 12 else local.month + 1
        day = calendar.monthrange(year, month)[1]
        return datetime(year, month, day, 17, tzinfo=NY).astimezone(UTC)
    raise V4BoundaryError(f"unsupported granularity: {granularity}")


def safe_request_start(granularity: str) -> datetime:
    """First aligned start whose whole candle is on/after frozen START."""
    if granularity == "H1":
        return START
    if granularity in {"D", "W"}:
        # First 17:00 New York aligned boundary after UTC START. W is Friday.
        return datetime(2010, 1, 1, 17, tzinfo=NY).astimezone(UTC)
    if granularity == "M":
        # First complete aligned monthly candle fully inside the window begins
        # at the Jan-31 17:00 New York boundary and covers February 2010.
        return datetime(2010, 1, 31, 17, tzinfo=NY).astimezone(UTC)
    raise V4BoundaryError(f"unsupported granularity: {granularity}")


def unsafe_end_start_boundary(granularity: str) -> datetime:
    """First aligned start before END whose candle coverage crosses END."""
    if granularity == "H1":
        return END
    if granularity in {"D", "M"}:
        return datetime(2023, 12, 31, 17, tzinfo=NY).astimezone(UTC)
    if granularity == "W":
        return datetime(2023, 12, 29, 17, tzinfo=NY).astimezone(UTC)
    raise V4BoundaryError(f"unsupported granularity: {granularity}")


def safe_request_end(granularity: str) -> datetime:
    # Keep `to` strictly before the first cross-END start in case the provider
    # treats exact time endpoints inclusively.
    return unsafe_end_start_boundary(granularity) - timedelta(microseconds=1)


def candle_is_fully_in_window(start: datetime, granularity: str) -> bool:
    start = start.astimezone(UTC)
    end = candle_end(start, granularity)
    return START <= start < END and end <= END


def assert_frozen_boundaries() -> None:
    expected_start = {
        "H1": "2010-01-01T00:00:00Z",
        "D": "2010-01-01T22:00:00Z",
        "W": "2010-01-01T22:00:00Z",
        "M": "2010-01-31T22:00:00Z",
    }
    expected_unsafe_end = {
        "H1": "2024-01-01T00:00:00Z",
        "D": "2023-12-31T22:00:00Z",
        "W": "2023-12-29T22:00:00Z",
        "M": "2023-12-31T22:00:00Z",
    }
    for tf in GRANULARITIES:
        assert zulu(safe_request_start(tf)) == expected_start[tf]
        assert zulu(unsafe_end_start_boundary(tf)) == expected_unsafe_end[tf]
        assert safe_request_start(tf) < safe_request_end(tf)
        assert safe_request_end(tf) < unsafe_end_start_boundary(tf)


if __name__ == "__main__":
    assert_frozen_boundaries()
    print("V4 fully-contained candle boundaries verified")
