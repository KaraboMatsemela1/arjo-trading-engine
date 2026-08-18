#!/usr/bin/env python3
"""Frozen time-boundary helpers for V4 Sharp Turn structure.

OANDA aligned W/M candles may have timestamps before the historical end while
their price coverage extends beyond it. Canonical V4 structure therefore admits
a candle only when its entire interval closes on or before the frozen UTC end.
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
        # Preserve the 17:00 New York aligned wall-clock boundary across DST.
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


def unsafe_start_boundary(granularity: str) -> datetime:
    """Earliest aligned candle start before END whose coverage crosses END.

    Requests end immediately before this boundary, so the raw provider response
    cannot legitimately include a candle that contains any post-END prices.
    """
    if granularity == "H1":
        return END
    if granularity in {"D", "M"}:
        # 17:00 America/New_York on 2023-12-31 = 2023-12-31T22:00:00Z.
        return datetime(2023, 12, 31, 17, tzinfo=NY).astimezone(UTC)
    if granularity == "W":
        # Friday 17:00 New York weekly boundary; the 2023-12-29 candle crosses 2024-01-01.
        return datetime(2023, 12, 29, 17, tzinfo=NY).astimezone(UTC)
    raise V4BoundaryError(f"unsupported granularity: {granularity}")


def safe_request_end(granularity: str) -> datetime:
    # OANDA `to` is kept strictly before the first unsafe candle start even if a
    # server interprets the endpoint inclusively at exact candle boundaries.
    return unsafe_start_boundary(granularity) - timedelta(microseconds=1)


def candle_is_fully_in_window(start: datetime, granularity: str) -> bool:
    end = candle_end(start, granularity)
    return START <= start.astimezone(UTC) < END and end <= END


def assert_frozen_boundaries() -> None:
    expected_unsafe = {
        "H1": "2024-01-01T00:00:00Z",
        "D": "2023-12-31T22:00:00Z",
        "W": "2023-12-29T22:00:00Z",
        "M": "2023-12-31T22:00:00Z",
    }
    for tf, expected in expected_unsafe.items():
        assert zulu(unsafe_start_boundary(tf)) == expected
        assert safe_request_end(tf) < unsafe_start_boundary(tf)


if __name__ == "__main__":
    assert_frozen_boundaries()
    print("V4 strict candle-coverage boundaries verified")
