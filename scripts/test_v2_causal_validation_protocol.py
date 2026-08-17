#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from check_v2_causal_validation_protocol import EXPECTED_PROTOCOL_SHA, validate

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/v2/future_validation_protocol_v2.json"


class CausalProtocolTests(unittest.TestCase):
    def test_protocol_validates(self) -> None:
        result = validate(PROTOCOL)
        self.assertEqual(result["protocol_sha256"], EXPECTED_PROTOCOL_SHA)

    def _tamper(self, mutate) -> Path:
        data = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        mutate(data)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(data, handle)
            return Path(handle.name)

    def test_prestart_carry_in_cannot_be_enabled(self) -> None:
        path = self._tamper(lambda d: d["initialization_policy"].__setitem__("pre_start_market_data_allowed", True))
        with self.assertRaises(RuntimeError):
            validate(path)

    def test_v1_holdout_state_cannot_seed_v2(self) -> None:
        path = self._tamper(lambda d: d["initialization_policy"].__setitem__("v1_holdout_state_or_data_allowed", True))
        with self.assertRaises(RuntimeError):
            validate(path)

    def test_bootstrap_cannot_be_scored(self) -> None:
        path = self._tamper(lambda d: d["initialization_policy"].__setitem__("bootstrap_sessions_scored", True))
        with self.assertRaises(RuntimeError):
            validate(path)

    def test_bootstrap_performance_cannot_be_inspected(self) -> None:
        path = self._tamper(lambda d: d["initialization_policy"].__setitem__("bootstrap_performance_inspected", True))
        with self.assertRaises(RuntimeError):
            validate(path)

    def test_scored_start_cannot_move(self) -> None:
        path = self._tamper(lambda d: d["window"].__setitem__("scored_start_inclusive", "2026-09-15T00:00:00Z"))
        with self.assertRaises(RuntimeError):
            validate(path)

    def test_initialization_rule_is_no_refit(self) -> None:
        path = self._tamper(lambda d: d["no_refit"].__setitem__("initialization_policy_changes_allowed", True))
        with self.assertRaises(RuntimeError):
            validate(path)


if __name__ == "__main__":
    unittest.main()
