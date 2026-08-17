#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH_B = ROOT / "scripts/run_protected_validation_independent.py"
FORBIDDEN = {
    "run_protected_validation_primary",
    "build_owner_operational_fvg_anchors",
    "build_owner_operational_context_occurrences",
    "nq_calibration_replay",
    "run_owner_operational_calibration",
    "reconstruct_owner_operational_spec_primary",
}


def main() -> int:
    tree = ast.parse(PATH_B.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    overlap = sorted(imported & FORBIDDEN)
    assert not overlap, f"protected independent path imports forbidden production modules: {overlap}"
    print("Protected validation Path B independence test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
