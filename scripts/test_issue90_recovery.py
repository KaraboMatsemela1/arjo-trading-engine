#!/usr/bin/env python3
"""Offline regression checks for Issue #90 Telegram recovery."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from build_issue90_telegram_recovery import FIELD_CUES, TERM_PATTERNS, bounded_excerpt, eligible_sources, persist_page
from evidence_antibias import contains_pre_spec_outcome


def main() -> int:
    text = "At equilibrium thats where you'll likely get a stop run as price reacts."
    eq = TERM_PATTERNS["EQUILIBRIUM"].search(text)
    sr = TERM_PATTERNS["STOP_RUN"].search(text)
    assert eq is not None and sr is not None
    assert not contains_pre_spec_outcome(bounded_excerpt(text, eq, 20))
    assert not contains_pre_spec_outcome(bounded_excerpt(text, sr, 20))

    # The selected phrase "stop run" must not be misclassified as a stop-loss or entry trigger.
    assert not FIELD_CUES["STOP"].search(text)
    assert not FIELD_CUES["TRIGGER_ENTRY"].search(text)
    assert FIELD_CUES["STOP"].search("Use a stop loss beyond the level")
    assert FIELD_CUES["TRIGGER_ENTRY"].search("Wait for confirmation before entry")

    contaminated = "At equilibrium this setup had a 72% win rate before the stop run."
    eq = TERM_PATTERNS["EQUILIBRIUM"].search(contaminated)
    assert eq is not None
    assert contains_pre_spec_outcome(bounded_excerpt(contaminated, eq, 20))

    assert TERM_PATTERNS["STOP_RUN"].search("stop-run")
    assert TERM_PATTERNS["STOP_RUN"].search("stoprun")
    assert TERM_PATTERNS["STOP_RUN"].search("stop run")
    assert not TERM_PATTERNS["EQUILIBRIUM"].search("premium discount midpoint")

    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.jsonl"
        good = {
            "source_id": "TG_ARJOIOTRADING_16",
            "source_type": "TELEGRAM_POST",
            "status": "PAYLOAD_CAPTURED",
            "first_party_contacted": True,
            "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD",
            "sha256": "a" * 64,
        }
        bad = dict(good)
        bad["source_id"] = "TG_ARJOIOTRADING_999"
        bad["closure_credit"] = "ZERO"
        manifest.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
        assert eligible_sources(manifest) == {"TG_ARJOIOTRADING_16"}

        page = '<html><body><div>equilibrium stop run fixture</div></body></html>'
        expected = hashlib.sha256(page.encode("utf-8")).hexdigest()
        meta = persist_page(Path(tmp), page, 2, 100, "https://t.me/s/ArjoioTrading?before=100")
        assert meta["sha256"] == expected
        assert (Path(tmp) / meta["cache_file"]).read_bytes() == page.encode("utf-8")

    print("Issue 90 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
