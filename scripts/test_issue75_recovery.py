#!/usr/bin/env python3
"""Offline regression checks for bounded Issue #75 recovery tooling."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from build_issue75_recovery_windows import bounded_window
from build_issue75_telegram_recovery import TARGET_SOURCE_ID, persist_page, target_is_eligible
from evidence_antibias import contains_pre_spec_outcome


def main() -> int:
    contaminated = "Order Blocks held with an 82% outcome before this MT example."
    match = re.search(r"Order Blocks", contaminated)
    assert match is not None
    assert contains_pre_spec_outcome(bounded_window(contaminated, match, 20))
    assert contains_pre_spec_outcome("29 Order Blocks failed after disrespecting MT.")
    assert contains_pre_spec_outcome("Out of 71 OBs, 42 held in this sample.")
    assert contains_pre_spec_outcome("Chance of holding when MT is respected is higher.")
    assert not contains_pre_spec_outcome("I gathered the data on ES for Daily Order Blocks")
    assert not contains_pre_spec_outcome("OBs that hold will respect MT, which is a useful indication.")

    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "manifest.jsonl"
        manifest.write_text(json.dumps({
            "source_id": TARGET_SOURCE_ID,
            "source_type": "TELEGRAM_POST",
            "status": "PAYLOAD_CAPTURED",
            "first_party_contacted": True,
            "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD",
            "sha256": "a" * 64,
        }) + "\n", encoding="utf-8")
        assert target_is_eligible(manifest)

        page = '<html><body><div>first-party archive fixture</div></body></html>'
        expected_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
        meta = persist_page(Path(tmp), page, 1, 80, "https://t.me/s/ArjoioTrading?before=80")
        assert meta["sha256"] == expected_sha
        assert (Path(tmp) / meta["cache_file"]).read_bytes() == page.encode("utf-8")

    print("Issue 75 recovery regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
