#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_discovery_watch_state import build_decision, build_watch_state


def report(*, youtube: int = 0, telegram: int = 0, website: int = 2, new: int = 0) -> dict:
    return {
        "new_source_count": new,
        "surface_exit_codes": {
            "youtube": youtube,
            "telegram": telegram,
            "website": website,
        },
    }


def baseline(*, youtube: int = 0, telegram: int = 0, website: int = 2) -> dict:
    state = build_watch_state(report(youtube=youtube, telegram=telegram, website=website))
    return json.loads(json.dumps(state))


def assert_unchanged_access_and_zero_new_is_quiet() -> None:
    current_report = report()
    current_state = build_watch_state(current_report)
    decision = build_decision(current_report, baseline(), current_state)
    assert decision["should_publish"] is False
    assert decision["access_state_changed"] is False
    assert decision["publication_reasons"] == []


def assert_new_source_requires_publication() -> None:
    current_report = report(new=1)
    current_state = build_watch_state(current_report)
    decision = build_decision(current_report, baseline(), current_state)
    assert decision["should_publish"] is True
    assert decision["access_state_changed"] is False
    assert decision["publication_reasons"] == ["NEW_FIRST_PARTY_SOURCE_URLS"]


def assert_access_transition_requires_publication() -> None:
    current_report = report(website=0)
    current_state = build_watch_state(current_report)
    decision = build_decision(current_report, baseline(), current_state)
    assert decision["should_publish"] is True
    assert decision["access_state_changed"] is True
    assert decision["publication_reasons"] == ["ACCESS_STATE_CHANGED"]
    assert decision["previous_surface_exit_codes"]["website"] == 2
    assert decision["current_surface_exit_codes"]["website"] == 0


def assert_missing_baseline_fails_open_to_review() -> None:
    current_report = report()
    current_state = build_watch_state(current_report)
    decision = build_decision(current_report, {}, current_state)
    assert decision["should_publish"] is True
    assert decision["baseline_missing"] is True
    assert decision["publication_reasons"] == ["ACCESS_BASELINE_MISSING"]


def assert_state_is_deterministic_and_semantic_credit_is_zero() -> None:
    current = build_watch_state(report())
    assert current == build_watch_state(report())
    assert current["surface_states"] == {
        "youtube": "CLEAN_DISCOVERY",
        "telegram": "CLEAN_DISCOVERY",
        "website": "NO_DISCOVERY_PAYLOAD",
    }
    assert current["semantic_closure_performed"] is False
    assert current["search_or_metadata_semantic_credit"] == "ZERO"


def assert_serialized_state_has_no_clock_fields() -> None:
    current = build_watch_state(report())
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.json"
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        text = path.read_text(encoding="utf-8")
        assert "generated_at" not in text
        assert "retrieval_date" not in text


def main() -> None:
    assert_unchanged_access_and_zero_new_is_quiet()
    assert_new_source_requires_publication()
    assert_access_transition_requires_publication()
    assert_missing_baseline_fails_open_to_review()
    assert_state_is_deterministic_and_semantic_credit_is_zero()
    assert_serialized_state_has_no_clock_fields()
    print("discovery watch state tests passed")


if __name__ == "__main__":
    main()
