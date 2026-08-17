#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_v2_execution_observability import (  # noqa: E402
    EXPECTED_OCCURRENCE_SET_SHA,
    ObservabilityError,
    build,
)


def source(touch: str = "100", low: str = "99", high: str = "101") -> dict:
    return {
        "occurrence_set_sha256": EXPECTED_OCCURRENCE_SET_SHA,
        "holdout_accessed": False,
        "outcome_fields_present": False,
        "performance_comparison_performed": False,
        "occurrences": [
            {
                "occurrence_id": "X",
                "second_sting": {
                    "touch_price": touch,
                    "bar": {
                        "ts_start_utc": "2025-01-02T14:30:00Z",
                        "low": low,
                        "high": high,
                    },
                },
            }
        ],
    }


def expect_error(mutator, text: str) -> None:
    value = source()
    mutator(value)
    try:
        build(value)
    except ObservabilityError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError("expected ObservabilityError")


def main() -> int:
    report = build(source())
    assert report["status_counts"] == {"EXECUTABLE_ENTRY": 1}
    assert report["observability_rows"][0]["target_stop_evaluation_authorized"] is True

    report = build(source("102", "99", "101"))
    assert report["status_counts"] == {"NO_EXECUTABLE_ENTRY": 1}
    row = report["observability_rows"][0]
    assert row["target_stop_evaluation_authorized"] is False
    assert row["fallback_fill_used"] is False

    expect_error(lambda value: value.__setitem__("occurrence_set_sha256", "0" * 64), "SHA mismatch")
    expect_error(lambda value: value.__setitem__("holdout_accessed", True), "must not access holdout")
    expect_error(lambda value: value.__setitem__("outcome_fields_present", True), "contains outcome fields")
    expect_error(lambda value: value.__setitem__("performance_comparison_performed", True), "performance comparison is prohibited")

    print("V2 observability tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
