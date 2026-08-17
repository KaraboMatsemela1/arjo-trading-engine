#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"scripts/run_v2_future_validation_independent.py"
FORBIDDEN={
    "run_v2_future_validation_primary",
    "run_protected_validation_primary",
    "build_owner_operational_fvg_anchors",
    "build_owner_operational_context_occurrences",
    "v2_m1_execution_measurement",
    "nq_calibration_replay",
}


def main()->int:
    tree=ast.parse(TARGET.read_text(encoding="utf-8"),filename=str(TARGET)); imported=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module: imported.add(node.module.split(".")[0])
    bad=sorted(imported & FORBIDDEN)
    if bad: raise SystemExit(f"independent V2 future path imports forbidden modules: {bad}")
    source=TARGET.read_text(encoding="utf-8")
    if "INDEPENDENT_V2_STANDARD_LIBRARY_PATH" not in source: raise SystemExit("independent path id missing")
    print("v2_future_path_b_independence=PASS"); return 0


if __name__=="__main__": raise SystemExit(main())
