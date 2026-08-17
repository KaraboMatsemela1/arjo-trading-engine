#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEPENDENT = ROOT / "scripts/reconstruct_owner_operational_spec_independent.py"
PROFILE = ROOT / "docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V1.json"
FORBIDDEN = {
    "build_owner_operational_fvg_anchors",
    "build_owner_operational_context_occurrences",
    "nq_calibration_replay",
    "run_owner_operational_calibration",
    "reconstruct_owner_operational_spec_primary",
}


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> int:
    source = INDEPENDENT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    overlap = sorted(imported & FORBIDDEN)
    assert not overlap, f"independent path imports primary modules: {overlap}"

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    recorded = profile.pop("profile_sha256")
    assert recorded == "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"
    assert canonical_sha256(profile) == recorded
    assert profile["reconstruction_acceptance"]["path_b_may_import_primary_strategy_builders"] is False
    assert set(profile["reconstruction_acceptance"]["path_b_forbidden_imports"]).issubset(FORBIDDEN)
    assert profile["claim_profile"]["semantic_closure_claimed"] is False
    assert profile["claim_profile"]["fully_first_party_reconstructed"] is False
    assert profile["data_boundary"]["holdout_accessed"] is False

    print("Independent owner-operational SPEC reconstruction boundary tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
