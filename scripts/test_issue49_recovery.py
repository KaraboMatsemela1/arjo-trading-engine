#!/usr/bin/env python3
"""Offline regression checks for bounded Issue #49 recovery tooling."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from build_issue49_recovery_windows import bounded_window
from build_issue49_telegram_recovery import TARGET_SOURCE_IDS, eligible_targets, persist_archive_page
from evidence_antibias import contains_pre_spec_outcome


def main() -> int:
    contaminated = "PD Arrays and 2CR produced 72% outcomes before this example."
    match = re.search(r"PD Arrays", contaminated)
    assert match is not None
    assert contains_pre_spec_outcome(bounded_window(contaminated, match, 20))
    assert not contains_pre_spec_outcome("Opposing PD Arrays are resistance and 2CR tells when they fail.")

    fixture = [
        {
            "source_id": source_id,
            "source_type": "TELEGRAM_POST",
            "status": "PAYLOAD_CAPTURED",
            "first_party_contacted": True,
            "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD",
            "sha256": "a" * 64,
        }
        for source_id in sorted(TARGET_SOURCE_IDS)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.jsonl"
        manifest.write_text("".join(json.dumps(row) + "\n" for row in fixture), encoding="utf-8")
        assert eligible_targets(manifest) == TARGET_SOURCE_IDS

        page = '<html><body><div>first-party archive fixture</div></body></html>'
        expected_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
        meta = persist_archive_page(Path(tmp), page, 2, 791, "https://t.me/s/ArjoioTrading?before=791")
        assert meta["sha256"] == expected_sha
        assert (Path(tmp) / meta["cache_file"]).read_bytes() == page.encode("utf-8")

    print("Issue 49 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
