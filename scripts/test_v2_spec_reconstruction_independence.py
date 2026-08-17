#!/usr/bin/env python3
from pathlib import Path

FORBIDDEN = [
    "build_owner_operational_fvg_anchors",
    "build_owner_operational_context_occurrences",
    "nq_calibration_replay",
    "run_owner_operational_calibration",
    "check_v2_execution_observability",
    "reconstruct_v2_spec_primary",
]


def main() -> int:
    source = Path(__file__).with_name("reconstruct_v2_spec_independent.py").read_text(encoding="utf-8")
    for name in FORBIDDEN:
        assert f"import {name}" not in source and f"from {name}" not in source, name
    assert "reconstruct_owner_operational_spec_independent" in source
    print("V2 Path B independence test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
