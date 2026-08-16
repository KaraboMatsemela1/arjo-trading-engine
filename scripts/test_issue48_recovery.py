#!/usr/bin/env python3
"""Offline regression checks for bounded Issue #48 recovery tooling."""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

from build_issue48_recovery_windows import bounded_window
from build_issue48_telegram_archive_recovery import persist_archive_page
from evidence_antibias import contains_pre_spec_outcome


def main() -> int:
    contaminated = "AoO context produced 2 winners this week before the next example."
    match = re.search(r"AoO", contaminated)
    assert match is not None
    excerpt = bounded_window(contaminated, match, 20)
    assert contains_pre_spec_outcome(excerpt)

    assert contains_pre_spec_outcome("This setup had 72% historical outcomes.")
    assert not contains_pre_spec_outcome("The stop loss sits below the structural low.")

    page = '<html><body><div>first-party archive fixture</div></body></html>'
    expected_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        meta = persist_archive_page(
            Path(tmp),
            page,
            page_index=3,
            current_before=778,
            url="https://t.me/s/ArjoioTrading?before=778",
        )
        assert meta["sha256"] == expected_sha
        assert meta["cache_file"]
        cached = Path(tmp) / meta["cache_file"]
        assert cached.read_bytes() == page.encode("utf-8")

    print("Issue 48 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
