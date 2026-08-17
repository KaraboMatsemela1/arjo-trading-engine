#!/usr/bin/env python3
"""Validate the protected holdout protocol before any 2026 market-data access."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_PROTOCOL_SHA = "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"
EXPECTED_PROFILE_SHA = "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"
EXPECTED_SPEC_AUDIT_SHA = "d022853a24dd0c46293adec61942ced2c5d811d9e63dbc75414aab34c5f25930"
EXPECTED_FVG_SHA = "cf12a1ce30d35dced52ef4f3c9bbb3ed11ab6509d6ada33e2f04089c68fafe7e"
EXPECTED_CONTEXT_SHA = "dba7892337e391ba6673de5b9df932a271c3af28103e10cecaa0163a9995bc5e"
EXPECTED_CALIBRATION_FILE_SHA = "e7ee6ed79290bd9396fc931f11b7cb11bf14e0e5e78a8ea3d34a2dd3e1bcc039"
EXPECTED_WINDOW = {
    "start_inclusive": "2026-01-01T00:00:00Z",
    "end_exclusive": "2026-07-01T00:00:00Z",
    "request_must_not_cross_end": True,
}
EXPECTED_PROVIDER = {
    "provider": "OANDA_V20",
    "venue": "OANDA_FXTRADE",
    "environment": "practice",
    "instrument": "NAS100_USD",
    "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
    "price_component": "MID",
    "source_granularity": "M1",
    "derived_granularities_minutes": [15, 60, 240],
    "complete_bucket_only": True,
    "fabricate_missing_minutes": False,
    "provider_price_quantum": "0.1",
    "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
    "read_only": True,
}
NO_REFIT_FALSE_KEYS = {
    "execution_changes_allowed",
    "fva_rule_changes_allowed",
    "fvg_rule_changes_allowed",
    "holdout_reuse_for_new_profile_tuning_allowed",
    "metric_changes_allowed",
    "normalization_changes_allowed",
    "provider_identity_changes_allowed",
    "sample_threshold_changes_allowed",
    "stop_rule_changes_allowed",
    "target_rule_changes_allowed",
    "two_cr_rule_changes_allowed",
    "two_sting_rule_changes_allowed",
    "validation_window_changes_allowed",
    "woo_changes_allowed",
}
EXPECTED_OUTCOME_CLASSES = [
    "TARGET_FIRST",
    "STOP_FIRST",
    "AMBIGUOUS_INTRABAR_ORDER",
    "UNRESOLVED_WINDOW_END",
]
EXPECTED_DECISION_CLASSES = {
    "NO_QUALIFYING_OCCURRENCES",
    "INSUFFICIENT_SAMPLE",
    "SUFFICIENT_SAMPLE_POSITIVE",
    "SUFFICIENT_SAMPLE_NONPOSITIVE",
    "IMPLEMENTATION_DIVERGENCE",
    "VALIDATION_INTEGRITY_FAILURE",
}


class ProtocolError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def canonical_embedded_sha(path: Path, field: str) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(data.get(field, ""))
    unsigned = dict(data)
    unsigned.pop(field, None)
    actual = canonical_sha256(unsigned)
    if recorded != actual:
        raise ProtocolError(f"{path} embedded {field} mismatch")
    return data, actual


def validate(
    *,
    protocol_path: Path,
    profile_path: Path,
    spec_audit_path: Path,
    fvg_path: Path,
    context_path: Path,
    calibration_result_path: Path,
    seed_path: Path,
) -> dict:
    protocol, protocol_sha = canonical_embedded_sha(protocol_path, "protocol_sha256")
    if protocol_sha != EXPECTED_PROTOCOL_SHA:
        raise ProtocolError("protected validation protocol SHA changed")
    if protocol.get("protocol_id") != "ARJO_PROTECTED_VALIDATION_V1":
        raise ProtocolError("unexpected validation protocol id")
    if protocol.get("status") != "FROZEN_BEFORE_HOLDOUT_ACCESS":
        raise ProtocolError("protocol must be frozen before holdout access")

    profile, profile_sha = canonical_embedded_sha(profile_path, "profile_sha256")
    if profile_sha != EXPECTED_PROFILE_SHA:
        raise ProtocolError("frozen SPEC profile SHA changed")
    if protocol.get("profile", {}).get("profile_sha256") != profile_sha:
        raise ProtocolError("protocol does not bind frozen profile SHA")
    if profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise ProtocolError("profile semantic closure claim changed")
    if profile.get("claim_profile", {}).get("fully_first_party_reconstructed") is not False:
        raise ProtocolError("profile first-party reconstruction claim changed")

    audit, audit_sha = canonical_embedded_sha(spec_audit_path, "audit_sha256")
    if audit_sha != EXPECTED_SPEC_AUDIT_SHA:
        raise ProtocolError("SPEC_READY audit SHA changed")
    if protocol.get("profile", {}).get("spec_ready_audit_sha256") != audit_sha:
        raise ProtocolError("protocol does not bind SPEC_READY audit")
    if audit.get("outcome") != "PASS" or audit.get("holdout_accessed") is not False:
        raise ProtocolError("SPEC_READY audit is not a clean pre-holdout PASS")

    _, fvg_sha = canonical_embedded_sha(fvg_path, "convention_sha256")
    _, context_sha = canonical_embedded_sha(context_path, "convention_sha256")
    if fvg_sha != EXPECTED_FVG_SHA or context_sha != EXPECTED_CONTEXT_SHA:
        raise ProtocolError("owner convention SHA changed")
    if protocol.get("owner_conventions") != {"fvg_sha256": fvg_sha, "context_sha256": context_sha}:
        raise ProtocolError("protocol owner-convention binding changed")

    if file_sha256(calibration_result_path) != EXPECTED_CALIBRATION_FILE_SHA:
        raise ProtocolError("calibration result file SHA changed")
    calibration = json.loads(calibration_result_path.read_text(encoding="utf-8"))
    selection = calibration.get("selection", {})
    frozen_execution = protocol.get("frozen_execution", {})
    if selection.get("second_sting_fill_event") != "SECOND_STING_TOUCH" or selection.get("stop_buffer_ticks") != 0:
        raise ProtocolError("calibrated execution selection changed")
    if frozen_execution.get("second_sting_fill_event") != selection.get("second_sting_fill_event"):
        raise ProtocolError("protocol fill event differs from calibration")
    if frozen_execution.get("stop_buffer_ticks") != selection.get("stop_buffer_ticks"):
        raise ProtocolError("protocol stop buffer differs from calibration")
    if frozen_execution.get("alternate_variants_allowed") is not False:
        raise ProtocolError("holdout may not evaluate alternate variants for selection")
    if frozen_execution.get("performance_status_used_for_selection") is not False:
        raise ProtocolError("calibrated selection must remain non-performance-based")
    if calibration.get("holdout_accessed") is not False:
        raise ProtocolError("calibration result indicates holdout access")

    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    if seed.get("stage") != "CALIBRATION_COMPLETE":
        raise ProtocolError("seed must remain CALIBRATION_COMPLETE")
    if seed.get("dataset", {}).get("holdout_accessed") is not False:
        raise ProtocolError("seed indicates holdout access before protocol freeze")

    if protocol.get("window") != EXPECTED_WINDOW:
        raise ProtocolError("protected validation window changed")
    if protocol.get("provider_identity") != EXPECTED_PROVIDER:
        raise ProtocolError("protected provider/normalization identity changed")

    no_refit = protocol.get("no_refit")
    if not isinstance(no_refit, dict) or set(no_refit) != NO_REFIT_FALSE_KEYS:
        raise ProtocolError("no-refit key set changed")
    if any(no_refit.get(key) is not False for key in NO_REFIT_FALSE_KEYS):
        raise ProtocolError("all no-refit mutations must remain false")

    if protocol.get("outcome_classes") != EXPECTED_OUTCOME_CLASSES:
        raise ProtocolError("protected outcome classes changed")
    sample = protocol.get("sample_policy", {})
    if sample.get("inferential_resolved_occurrence_threshold") != 30:
        raise ProtocolError("sample sufficiency threshold changed")
    if set(sample.get("classifications", {})) != EXPECTED_DECISION_CLASSES:
        raise ProtocolError("validation decision class set changed")

    metrics = protocol.get("metrics", {})
    if metrics.get("resolved_occurrence_count") != "TARGET_FIRST + STOP_FIRST":
        raise ProtocolError("resolved occurrence definition changed")
    wilson = metrics.get("wilson_interval", {})
    if wilson.get("confidence") != 0.95 or wilson.get("z") != 1.959963984540054:
        raise ProtocolError("Wilson interval policy changed")

    dual = protocol.get("dual_path_validation", {})
    if dual.get("required") is not True:
        raise ProtocolError("dual-path holdout validation must remain required")
    if dual.get("primary_path") != "PRIMARY_PRODUCTION_PATH" or dual.get("independent_path") != "INDEPENDENT_STANDARD_LIBRARY_PATH":
        raise ProtocolError("validation reconstruction path identity changed")

    access = protocol.get("holdout_access", {})
    if access.get("accessed_before_protocol_freeze") is not False:
        raise ProtocolError("protocol records pre-freeze holdout access")
    if access.get("authorized_after_gate") != "PROTECTED_VALIDATION_PROTOCOL_FROZEN":
        raise ProtocolError("holdout authorization gate changed")

    authorization = protocol.get("authorization", {})
    for key in ("paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized"):
        if authorization.get(key) is not False:
            raise ProtocolError(f"{key} must remain false")

    return {
        "status": "PROTECTED_VALIDATION_PROTOCOL_FROZEN",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha,
        "profile_sha256": profile_sha,
        "spec_ready_audit_sha256": audit_sha,
        "holdout_accessed": False,
        "holdout_start": EXPECTED_WINDOW["start_inclusive"],
        "holdout_end_exclusive": EXPECTED_WINDOW["end_exclusive"],
        "inferential_resolved_occurrence_threshold": 30,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="research/validation/protected_validation_protocol_v1.json")
    parser.add_argument("--profile", default="docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V1.json")
    parser.add_argument("--spec-audit", default="docs/spec/SPEC_READY.json")
    parser.add_argument("--fvg", default="research/calibration/owner_operational_fvg_v1.json")
    parser.add_argument("--context", default="research/calibration/owner_operational_context_v1.json")
    parser.add_argument("--calibration-result", default="research/calibration/owner_operational_calibration_result.json")
    parser.add_argument("--seed", default="research/calibration/aoo_nq_seed_assessment.json")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = validate(
            protocol_path=Path(args.protocol),
            profile_path=Path(args.profile),
            spec_audit_path=Path(args.spec_audit),
            fvg_path=Path(args.fvg),
            context_path=Path(args.context),
            calibration_result_path=Path(args.calibration_result),
            seed_path=Path(args.seed),
        )
    except (OSError, json.JSONDecodeError, ProtocolError) as exc:
        print(f"protected validation protocol failed: {exc}", file=sys.stderr)
        return 1
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
