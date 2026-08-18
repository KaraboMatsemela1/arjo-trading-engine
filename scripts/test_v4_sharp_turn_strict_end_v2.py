#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime

import oanda_v4_sharp_turn_structure_v2 as acq
import v4_sharp_turn_candle_boundaries as b


def main() -> None:
    b.assert_frozen_boundaries()

    jan = datetime(2010, 1, 31, 22, tzinfo=UTC)
    assert b.zulu(b.candle_end(jan, "M")) == "2010-02-28T22:00:00Z"
    feb = datetime(2010, 2, 28, 22, tzinfo=UTC)
    assert b.zulu(b.candle_end(feb, "M")) == "2010-03-31T21:00:00Z"

    # Partial aligned candles crossing either frozen boundary are noncanonical.
    assert not b.candle_is_fully_in_window(datetime(2009, 12, 31, 22, tzinfo=UTC), "M")
    assert b.candle_is_fully_in_window(datetime(2010, 1, 31, 22, tzinfo=UTC), "M")
    assert not b.candle_is_fully_in_window(datetime(2023, 12, 29, 22, tzinfo=UTC), "W")
    assert not b.candle_is_fully_in_window(datetime(2023, 12, 31, 22, tzinfo=UTC), "M")
    assert b.candle_is_fully_in_window(datetime(2023, 12, 22, 22, tzinfo=UTC), "W")
    assert b.candle_is_fully_in_window(datetime(2023, 11, 30, 22, tzinfo=UTC), "M")

    for tf in b.GRANULARITIES:
        chunks = acq.windows(tf)
        assert chunks
        assert chunks[0][0] == b.safe_request_start(tf)
        assert chunks[-1][1] == b.safe_request_end(tf)
        assert chunks[-1][1] < b.unsafe_end_start_boundary(tf)
        assert all(
            b.safe_request_start(tf) <= start < end <= b.safe_request_end(tf)
            for start, end in chunks
        )

    print("V4 fully-contained candle boundary V2 regressions passed")


if __name__ == "__main__":
    main()
