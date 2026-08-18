#!/usr/bin/env python3
"""Offline boundary regressions for the V5 OANDA profitability runner."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import run_v5_nra_profitability_oanda as runner


def main() -> None:
    # A pre-M1 trigger reconstruction failure must abort before M1Cache construction.
    original_marker = runner.verify_marker
    original_reconstruct = runner.reconstruct_before_m1
    original_cache = runner.M1Cache
    cache_constructed = False

    def fake_marker() -> dict:
        return {
            "status": "AUTHORIZED_V5_RESEARCH_M1_READ_AFTER_TRIGGER_SEAL",
            "issue": 255,
        }

    def failed_reconstruction():
        raise runner.V5ProfitabilityError("synthetic trigger SHA mismatch")

    class ForbiddenCache:
        def __init__(self, *args, **kwargs) -> None:
            nonlocal cache_constructed
            cache_constructed = True
            raise AssertionError("M1 cache constructed before trigger reconstruction")

    runner.verify_marker = fake_marker
    runner.reconstruct_before_m1 = failed_reconstruction
    runner.M1Cache = ForbiddenCache
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_argv = sys.argv
            sys.argv = ["run_v5_nra_profitability_oanda.py", "--output-dir", temp_dir]
            try:
                code = runner.main()
            finally:
                sys.argv = old_argv
        assert code == 1
        assert cache_constructed is False
    finally:
        runner.verify_marker = original_marker
        runner.reconstruct_before_m1 = original_reconstruct
        runner.M1Cache = original_cache

    # Marker contract must fail closed when any safety permission is enabled.
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "marker.json"
        path.write_text(
            """{
  "status": "AUTHORIZED_V5_RESEARCH_M1_READ_AFTER_TRIGGER_SEAL",
  "issue": 255,
  "protocol_sha256": "f01d01ffcb4711f53b86a71c14fec0b6a145fafc9edc140d41d602d29eadb5ff",
  "structure_transport_sha256": "8a31db889e5105a8a7a351d79ce247cfaf2bc68451e6565ef80aac17d72580f0",
  "profitability_lock_sha256": "7c509c72e290a427d9a44e5ab133e624e766f73450e78ed68790d1b3d51f6b87",
  "trigger_set_sha256": "b65671c07e811924341a75c8e21434d275c4b6283febd2c45978b59ebfe4bb10",
  "trigger_readiness_sha256": "9fcdf27b9fbc2d14bd878d3ebfd73a19fe32282066502e6c3350ea9ca8bb2a28",
  "trigger_count": 4737,
  "paper_execution_authorized": true,
  "live_execution_authorized": false,
  "broker_mutation_authorized": false
}
""",
            encoding="utf-8",
        )
        try:
            runner.verify_marker(path)
        except runner.V5ProfitabilityError:
            pass
        else:
            raise AssertionError("unsafe V5 M1 marker unexpectedly accepted")

    print("v5_nra_profitability_runner_boundary_regressions=PASS")


if __name__ == "__main__":
    main()
