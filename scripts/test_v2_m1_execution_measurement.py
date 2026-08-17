#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from v2_m1_execution_measurement import measure_occurrence

START = datetime(2026, 10, 5, 14, 30, tzinfo=UTC)
END = datetime(2027, 3, 1, tzinfo=UTC)
OCC = {
    "occurrence_id": "TEST",
    "second_sting_ts_utc": "2026-10-05T14:30:00Z",
    "touch_price": "100",
    "order_flow_leg_low": "90",
    "target_price": "120",
}


def interval_rows(*, touch_minute: int | None = 2, touch_low: str = "99", touch_high: str = "101") -> list[dict]:
    rows = []
    for i in range(15):
        low, high = "101", "110"
        if i == touch_minute:
            low, high = touch_low, touch_high
        rows.append({"ts_start_utc": (START + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"), "low": low, "high": high})
    return rows


class MeasurementTests(unittest.TestCase):
    def test_no_executable_entry_gets_no_measurement(self) -> None:
        result = measure_occurrence(occurrence=OCC, observability_status="NO_EXECUTABLE_ENTRY", m1_rows=[], end_exclusive=END)
        self.assertIsNone(result["execution_outcome"])

    def test_missing_minute_fails_integrity(self) -> None:
        rows = interval_rows(); rows.pop(4)
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=rows, end_exclusive=END)
        self.assertEqual(result["integrity_failure"], "M1_ENTRY_INTERVAL_INCOMPLETE")

    def test_15m_observable_but_no_m1_touch_fails_integrity(self) -> None:
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=interval_rows(touch_minute=None), end_exclusive=END)
        self.assertEqual(result["integrity_failure"], "M1_TOUCH_NOT_OBSERVED")

    def test_entry_minute_stop_is_ambiguous(self) -> None:
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=interval_rows(touch_low="89"), end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "AMBIGUOUS_INTRABAR_ORDER")

    def test_entry_minute_target_is_ambiguous(self) -> None:
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=interval_rows(touch_high="121"), end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "AMBIGUOUS_INTRABAR_ORDER")

    def test_later_stop_is_stop_first(self) -> None:
        rows = interval_rows()
        rows.append({"ts_start_utc": "2026-10-05T14:50:00Z", "low": "89", "high": "105"})
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=rows, end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "STOP_FIRST")
        self.assertEqual(result["event_ts"], "2026-10-05T14:50:00Z")

    def test_later_target_is_target_first(self) -> None:
        rows = interval_rows()
        rows.append({"ts_start_utc": "2026-10-05T14:50:00Z", "low": "95", "high": "121"})
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=rows, end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "TARGET_FIRST")

    def test_later_both_is_ambiguous(self) -> None:
        rows = interval_rows()
        rows.append({"ts_start_utc": "2026-10-05T14:50:00Z", "low": "89", "high": "121"})
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=rows, end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "AMBIGUOUS_INTRABAR_ORDER")

    def test_no_event_is_unresolved(self) -> None:
        result = measure_occurrence(occurrence=OCC, observability_status="EXECUTABLE_ENTRY", m1_rows=interval_rows(), end_exclusive=END)
        self.assertEqual(result["execution_outcome"], "UNRESOLVED_WINDOW_END")


if __name__ == "__main__":
    unittest.main()
