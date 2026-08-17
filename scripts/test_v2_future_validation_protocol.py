#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from check_v2_future_validation_access import check_access
from check_v2_future_validation_protocol import EXPECTED_PROTOCOL_SHA, canonical_sha256, validate

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/v2/future_validation_protocol_v1.json"
PROFILE = ROOT / "docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V2.json"
RESERVATION = ROOT / "research/v2/future_validation_reservation_v1.json"
REMEDIATION = ROOT / "research/v2/v2_remediation_readiness.json"
DISPOSITION = ROOT / "research/v2/v1_post_validation_disposition.json"


class ProtocolTests(unittest.TestCase):
    def test_frozen_protocol_validates(self) -> None:
        result = validate(PROTOCOL, PROFILE, RESERVATION, REMEDIATION, DISPOSITION)
        self.assertEqual(result["protocol_sha256"], EXPECTED_PROTOCOL_SHA)

    def _tampered_protocol(self, mutate) -> Path:
        data = json.loads(PROTOCOL.read_text())
        mutate(data)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(data, handle)
            return Path(handle.name)

    def test_window_tamper_fails(self) -> None:
        path = self._tampered_protocol(lambda d: d["window"].__setitem__("start_inclusive", "2026-08-01T00:00:00Z"))
        with self.assertRaises(RuntimeError):
            validate(path, PROFILE, RESERVATION, REMEDIATION, DISPOSITION)

    def test_refit_enable_fails(self) -> None:
        path = self._tampered_protocol(lambda d: d["no_refit"].__setitem__("observability_rule_changes_allowed", True))
        with self.assertRaises(RuntimeError):
            validate(path, PROFILE, RESERVATION, REMEDIATION, DISPOSITION)

    def test_fallback_fill_enable_fails(self) -> None:
        path = self._tampered_protocol(lambda d: d["observability"].__setitem__("future_bar_fallback_allowed", True))
        with self.assertRaises(RuntimeError):
            validate(path, PROFILE, RESERVATION, REMEDIATION, DISPOSITION)

    def test_pre_window_acquisition_denied(self) -> None:
        with self.assertRaises(RuntimeError):
            check_access(PROTOCOL, "acquisition", datetime(2026, 8, 31, 23, 59, tzinfo=UTC), None)

    def test_post_start_acquisition_still_needs_authorization(self) -> None:
        with self.assertRaises(RuntimeError):
            check_access(PROTOCOL, "acquisition", datetime(2026, 9, 1, 0, 1, tzinfo=UTC), None)

    def test_pre_end_evaluation_denied_even_with_authorization(self) -> None:
        auth = {
            "authorization_id": "ARJO_V2_FUTURE_VALIDATION_EVALUATION_V1",
            "protocol_sha256": EXPECTED_PROTOCOL_SHA,
            "gate": "evaluation",
            "authorized": True,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(auth, handle)
            path = Path(handle.name)
        with self.assertRaises(RuntimeError):
            check_access(PROTOCOL, "evaluation", datetime(2027, 2, 28, 23, 59, tzinfo=UTC), path)

    def test_post_end_evaluation_can_open_only_with_exact_authorization(self) -> None:
        auth = {
            "authorization_id": "ARJO_V2_FUTURE_VALIDATION_EVALUATION_V1",
            "protocol_sha256": EXPECTED_PROTOCOL_SHA,
            "gate": "evaluation",
            "authorized": True,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(auth, handle)
            path = Path(handle.name)
        result = check_access(PROTOCOL, "evaluation", datetime(2027, 3, 1, 0, 0, tzinfo=UTC), path)
        self.assertEqual(result["status"], "AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
