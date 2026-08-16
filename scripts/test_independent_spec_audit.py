#!/usr/bin/env python3
"""Regression checks for the independent SPEC audit contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_independent_spec_audit import REQUIRED_FIELDS, matrix_shape  # noqa: E402


def main() -> int:
    valid_rows = [{"FIELD": field} for field in REQUIRED_FIELDS]
    assert matrix_shape(valid_rows)["valid"] is True

    duplicate_rows = valid_rows + [{"FIELD": REQUIRED_FIELDS[0]}]
    duplicate_shape = matrix_shape(duplicate_rows)
    assert duplicate_shape["valid"] is False
    assert REQUIRED_FIELDS[0] in duplicate_shape["duplicate_fields"]
    assert duplicate_shape["row_count"] == len(REQUIRED_FIELDS) + 1

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "SPEC_AUDIT.json"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_independent_spec_audit.py"), "--output", str(output)],
            cwd=ROOT,
            check=True,
        )
        audit = json.loads(output.read_text(encoding="utf-8"))

    assert audit["schema_version"] == 2
    assert audit["phase5_preflight_is_independent_two_engineer_test"] is False
    for candidate in audit["candidates"]:
        assert "two_engineer_test" not in candidate
        assert candidate["phase5_reconstruction_preflight"] in {"PASS", "FAIL"}
        if candidate["unresolved_fields"]:
            expected = "NOT_ATTEMPTED_INCOMPLETE_REQUIRED_FIELDS"
            assert candidate["independent_two_engineer_test"] == expected
            assert candidate["independent_reconstruction"] == expected
            assert candidate["outcome"] == "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"

    print("Independent SPEC audit contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
