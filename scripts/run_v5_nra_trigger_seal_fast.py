#!/usr/bin/env python3
"""Run the V5 trigger seal with the independent block-index reference path."""
from __future__ import annotations

import run_v5_nra_trigger_seal as base
from v5_nra_reference_fast import compare_reconstructions_fast

base.compare_reconstructions = compare_reconstructions_fast

if __name__ == "__main__":
    raise SystemExit(base.main())
