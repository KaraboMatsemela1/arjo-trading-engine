#!/usr/bin/env python3
"""Offline regression checks for bounded Issue #85 recovery tooling."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from build_issue85_recovery_windows import bounded_window
from build_issue85_telegram_recovery import TARGET_SOURCE_IDS, persist_page, targets_are_eligible
from evidence_antibias import contains_pre_spec_outcome


def record(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "source_type": "TELEGRAM_POST",
        "status": "PAYLOAD_CAPTURED",
        "first_party_contacted": True,
        "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD",
        "sha256": "a" * 64,
    }


def main() -> int:
    contaminated = "Order Flow produced an 82% win rate before this Target example."
    match = re.search(r"Order Flow", contaminated)
    assert match is not None
    assert contains_pre_spec_outcome(bounded_window(contaminated, match, 20))

    safe = "Episode 1, we're diving into Order Flow and how that tells us the Target."
    match = re.search(r"Order Flow", safe)
    assert match is not None
    excerpt = bounded_window(safe, match, 20)
    assert "Order Flow" in excerpt and "Target" in excerpt
    assert not contains_pre_spec_outcome(excerpt)

    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.jsonl"
        manifest.write_text(
            "".join(json.dumps(record(source_id)) + "\n" for source_id in sorted(TARGET_SOURCE_IDS)),
            encoding="utf-8",
        )
        assert targets_are_eligible(manifest)

        incomplete = Path(tmp) / "incomplete.jsonl"
        incomplete.write_text(
            "".join(json.dumps(record(source_id)) + "\n" for source_id in sorted(TARGET_SOURCE_IDS)[:-1]),
            encoding="utf-8",
        )
        assert not targets_are_eligible(incomplete)

        page = '<html><body><div>first-party archive fixture</div></body></html>'
        expected_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
        meta = persist_page(Path(tmp), page, 1, 790, "https://t.me/s/ArjoioTrading?before=790")
        assert meta["sha256"] == expected_sha
        assert (Path(tmp) / meta["cache_file"]).read_bytes() == page.encode("utf-8")

    print("Issue 85 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
