#!/usr/bin/env python3
"""Regression checks for the independent SPEC audit contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from independent_reconstruction_packet import candidate_matrix_sha256, validate_candidate_packet  # noqa: E402
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
        assert isinstance(candidate["independent_packet_validation"], dict)
        if candidate["unresolved_fields"]:
            expected = "NOT_ATTEMPTED_INCOMPLETE_REQUIRED_FIELDS"
            assert candidate["independent_two_engineer_test"] == expected
            assert candidate["independent_reconstruction"] == expected
            assert candidate["independent_packet_validation"]["status"] == "NOT_EVALUATED"
            assert candidate["outcome"] == "BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec_ref = "docs/spec/FROZEN_SPEC.json"
        spec_path = root / spec_ref
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text('{"rule":"evidence-only"}\n', encoding="utf-8")
        spec_sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        rows = [
            {"FIELD": field, "STATE": "SATISFIED", "EVIDENCE_IDS": f"EV_{index:024X}", "NOTES": "direct"}
            for index, field in enumerate(REQUIRED_FIELDS, start=1)
        ]
        matrix_sha = candidate_matrix_sha256(rows)
        bundle = {
            "schema_version": 1,
            "candidate_packets": [
                {
                    "predicate_id": "SYNTHETIC",
                    "predicate_matrix_sha256": matrix_sha,
                    "frozen_spec_ref": spec_ref,
                    "frozen_spec_sha256": spec_sha,
                    "engineers": [
                        {
                            "id": "independent-a",
                            "independent": True,
                            "evidence_only": True,
                            "community_interpretations_used": False,
                            "generic_ict_smc_knowledge_used": False,
                            "performance_data_consulted": False,
                            "trade_counts_consulted": False,
                            "reconstruction_sha256": spec_sha,
                            "predicate_matrix_sha256": matrix_sha,
                        },
                        {
                            "id": "independent-b",
                            "independent": True,
                            "evidence_only": True,
                            "community_interpretations_used": False,
                            "generic_ict_smc_knowledge_used": False,
                            "performance_data_consulted": False,
                            "trade_counts_consulted": False,
                            "reconstruction_sha256": spec_sha,
                            "predicate_matrix_sha256": matrix_sha,
                        },
                    ],
                }
            ],
        }
        result = validate_candidate_packet(bundle, "SYNTHETIC", rows, root)
        assert result["status"] == "PASS", result
        tampered = json.loads(json.dumps(bundle))
        tampered["candidate_packets"][0]["engineers"][1]["reconstruction_sha256"] = "0" * 64
        result = validate_candidate_packet(tampered, "SYNTHETIC", rows, root)
        assert result["status"] == "FAIL"

    print("Independent SPEC audit contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
