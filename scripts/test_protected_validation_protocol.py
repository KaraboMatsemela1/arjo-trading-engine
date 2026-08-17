#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_protected_validation_protocol import (  # noqa: E402
    ProtocolError,
    canonical_sha256,
    validate,
)

PROTOCOL = ROOT / "research/validation/protected_validation_protocol_v1.json"
PROFILE = ROOT / "docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V1.json"
AUDIT = ROOT / "docs/spec/SPEC_READY.json"
FVG = ROOT / "research/calibration/owner_operational_fvg_v1.json"
CONTEXT = ROOT / "research/calibration/owner_operational_context_v1.json"
CAL_RESULT = ROOT / "research/calibration/owner_operational_calibration_result.json"
SEED = ROOT / "research/calibration/aoo_nq_seed_assessment.json"


def run(protocol_path: Path) -> dict:
    return validate(
        protocol_path=protocol_path,
        profile_path=PROFILE,
        spec_audit_path=AUDIT,
        fvg_path=FVG,
        context_path=CONTEXT,
        calibration_result_path=CAL_RESULT,
        seed_path=SEED,
    )


def write_mutation(tmp: str, mutator) -> Path:
    payload = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    mutator(payload)
    unsigned = dict(payload)
    unsigned.pop("protocol_sha256", None)
    payload["protocol_sha256"] = canonical_sha256(unsigned)
    path = Path(tmp) / "protocol.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def expect_error(mutator, needle: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = write_mutation(tmp, mutator)
        try:
            run(path)
        except ProtocolError as exc:
            assert needle in str(exc), (needle, str(exc))
        else:
            raise AssertionError(f"expected ProtocolError containing {needle!r}")


def main() -> int:
    result = run(PROTOCOL)
    assert result["status"] == "PROTECTED_VALIDATION_PROTOCOL_FROZEN"
    assert result["protocol_sha256"] == "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"
    assert result["holdout_accessed"] is False
    assert result["inferential_resolved_occurrence_threshold"] == 30
    assert result["paper_execution_authorized"] is False
    assert result["live_execution_authorized"] is False

    # Even if an attacker re-hashes a changed protocol, the frozen expected SHA rejects it first.
    expect_error(
        lambda p: p["window"].__setitem__("end_exclusive", "2026-08-01T00:00:00Z"),
        "protocol SHA changed",
    )
    expect_error(
        lambda p: p["sample_policy"].__setitem__("inferential_resolved_occurrence_threshold", 5),
        "protocol SHA changed",
    )
    expect_error(
        lambda p: p["no_refit"].__setitem__("fvg_rule_changes_allowed", True),
        "protocol SHA changed",
    )
    expect_error(
        lambda p: p["frozen_execution"].__setitem__("alternate_variants_allowed", True),
        "protocol SHA changed",
    )
    expect_error(
        lambda p: p["holdout_access"].__setitem__("accessed_before_protocol_freeze", True),
        "protocol SHA changed",
    )
    expect_error(
        lambda p: p["authorization"].__setitem__("paper_execution_authorized", True),
        "protocol SHA changed",
    )

    # Raw byte/canonical tampering without updating the embedded SHA also fails.
    with tempfile.TemporaryDirectory() as tmp:
        payload = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        payload["provider_identity"]["instrument"] = "OTHER"
        path = Path(tmp) / "bad-sha.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            run(path)
        except ProtocolError as exc:
            assert "embedded protocol_sha256 mismatch" in str(exc)
        else:
            raise AssertionError("protocol with stale embedded SHA must fail")

    print("Protected validation protocol sabotage tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
