#!/usr/bin/env python3
"""Ensure SPEC_READY cannot be asserted without a profile-appropriate audit.

Legacy audits retain the original required checks. The owner-operational profile
adds a stronger two-path reconstruction boundary: frozen profile SHA, committed
Path A/Path B reports, explicit non-first-party-closure disclosure, unread
holdout, non-performance semantic selection, and no execution authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from compare_owner_operational_spec_reconstructions import compare as compare_owner_reports

REQUIRED_AUDIT_FIELDS = {
    "predicate_id",
    "outcome",
    "all_required_fields_satisfied",
    "contradictions_resolved",
    "provenance_complete",
    "two_engineer_test",
    "independent_reconstruction",
    "frozen_spec_ref",
}
OWNER_PROFILE_ID = "ARJO_DERIVED_OWNER_OPERATIONAL_V1"
OWNER_AUDIT_PROTOCOL = "OWNER_OPERATIONAL_TWO_PATH_SPEC_RECONSTRUCTION_V1"
OWNER_REQUIRED_FIELDS = {
    "audit_protocol",
    "audit_sha256",
    "profile_id",
    "profile_sha256",
    "semantic_closure_claimed",
    "fully_first_party_reconstructed",
    "owner_operational_conventions_disclosed",
    "performance_data_used_for_semantic_selection",
    "holdout_accessed",
    "path_a_id",
    "path_a_ref",
    "path_a_reconstruction_sha256",
    "path_b_id",
    "path_b_ref",
    "path_b_reconstruction_sha256",
    "critical_fields",
    "critical_values_sha256",
    "spec_ready_scope",
    "execution_authorization",
    "verification",
}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def common_errors(audit: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_AUDIT_FIELDS - set(audit)
    if missing:
        return [f"missing fields: {sorted(missing)}"]
    checks = {
        "outcome": audit["outcome"] == "PASS",
        "all_required_fields_satisfied": audit["all_required_fields_satisfied"] is True,
        "contradictions_resolved": audit["contradictions_resolved"] is True,
        "provenance_complete": audit["provenance_complete"] is True,
        "two_engineer_test": audit["two_engineer_test"] == "PASS",
        "independent_reconstruction": audit["independent_reconstruction"] == "PASS",
        "frozen_spec_ref": isinstance(audit["frozen_spec_ref"], str) and bool(audit["frozen_spec_ref"]),
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    return errors


def owner_operational_errors(audit: dict) -> list[str]:
    errors: list[str] = []
    missing = OWNER_REQUIRED_FIELDS - set(audit)
    if missing:
        return [f"owner-operational audit missing fields: {sorted(missing)}"]
    if audit.get("audit_protocol") != OWNER_AUDIT_PROTOCOL:
        errors.append("unexpected owner-operational audit protocol")
    if audit.get("profile_id") != OWNER_PROFILE_ID:
        errors.append("unexpected owner-operational profile id")
    if audit.get("semantic_closure_claimed") is not False:
        errors.append("owner-operational SPEC must preserve semantic_closure_claimed=false")
    if audit.get("fully_first_party_reconstructed") is not False:
        errors.append("owner-operational SPEC must not claim full first-party reconstruction")
    if audit.get("owner_operational_conventions_disclosed") is not True:
        errors.append("owner operational conventions must remain disclosed")
    if audit.get("performance_data_used_for_semantic_selection") is not False:
        errors.append("performance data must not be used for semantic selection")
    if audit.get("holdout_accessed") is not False:
        errors.append("protected holdout must remain unread at SPEC_READY")
    if audit.get("spec_ready_scope") != "CALIBRATED_OPERATIONAL_SPEC_READY_FOR_PROTECTED_VALIDATION":
        errors.append("unexpected SPEC_READY scope")

    execution = audit.get("execution_authorization")
    if not isinstance(execution, dict):
        errors.append("execution_authorization missing")
    else:
        for key in ("paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized"):
            if execution.get(key) is not False:
                errors.append(f"{key} must remain false at SPEC_READY")

    critical = audit.get("critical_fields")
    if not isinstance(critical, dict) or len(critical) != 19:
        errors.append("owner-operational audit must contain exactly 19 critical fields")
    elif any(not isinstance(value, dict) or value.get("status") != "PASS" for value in critical.values()):
        errors.append("all owner-operational critical fields must PASS")

    recorded_audit_sha = audit.get("audit_sha256")
    unsigned_audit = dict(audit)
    unsigned_audit.pop("audit_sha256", None)
    if recorded_audit_sha != canonical_sha256(unsigned_audit):
        errors.append("SPEC_READY audit SHA mismatch")

    profile_path = Path(str(audit.get("frozen_spec_ref", "")))
    path_a = Path(str(audit.get("path_a_ref", "")))
    path_b = Path(str(audit.get("path_b_ref", "")))
    for label, path in (("frozen profile", profile_path), ("Path A report", path_a), ("Path B report", path_b)):
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
    if errors:
        return errors

    try:
        regenerated = compare_owner_reports(profile_path, path_a, path_b)
    except Exception as exc:
        return [f"committed two-path reconstruction does not regenerate: {exc}"]

    invariant_fields = (
        "profile_id",
        "profile_sha256",
        "predicate_id",
        "outcome",
        "all_required_fields_satisfied",
        "contradictions_resolved",
        "provenance_complete",
        "two_engineer_test",
        "independent_reconstruction",
        "semantic_closure_claimed",
        "owner_operational_conventions_disclosed",
        "fully_first_party_reconstructed",
        "performance_data_used_for_semantic_selection",
        "holdout_accessed",
        "path_a_id",
        "path_b_id",
        "path_a_reconstruction_sha256",
        "path_b_reconstruction_sha256",
        "critical_values_sha256",
    )
    for field in invariant_fields:
        if audit.get(field) != regenerated.get(field):
            errors.append(f"committed SPEC_READY differs from regenerated two-path audit: {field}")

    if audit.get("profile_sha256") != "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585":
        errors.append("unexpected frozen owner-operational profile SHA")
    if audit.get("path_a_reconstruction_sha256") != "eeb9997e9f913cc79755c6f4fdf9760138326956c98ca565c02e306f1c949761":
        errors.append("unexpected Path A reconstruction SHA")
    if audit.get("path_b_reconstruction_sha256") != "102dac4b77a53ce1a12d2085fe04cd04d144d807b672f7b3a6da06f4791df138":
        errors.append("unexpected Path B reconstruction SHA")

    verification = audit.get("verification")
    if not isinstance(verification, dict):
        errors.append("reconstruction verification provenance missing")
    else:
        if verification.get("workflow_run_id") != 32023985087:
            errors.append("unexpected reconstruction workflow run id")
        if verification.get("artifact_id") != 9286388843:
            errors.append("unexpected reconstruction artifact id")
        digest = verification.get("artifact_digest")
        if digest != "sha256:2777bf35417506220a84afb570231ed2447217ac89674dc380882a9adebd1e18":
            errors.append("unexpected reconstruction artifact digest")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="project_state.json")
    parser.add_argument("--audit", default="docs/spec/SPEC_READY.json")
    args = parser.parse_args()

    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    if not state.get("spec_ready", False):
        print("SPEC_READY is false; audit artifact not yet required")
        return 0

    audit_path = Path(args.audit)
    if not audit_path.exists():
        print(f"SPEC_READY asserted without audit artifact: {audit_path}", file=sys.stderr)
        return 1
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"SPEC_READY audit artifact is invalid JSON: {exc}", file=sys.stderr)
        return 1

    errors = common_errors(audit)
    if audit.get("profile_id") == OWNER_PROFILE_ID:
        errors.extend(owner_operational_errors(audit))
    if errors:
        print("SPEC_READY audit failed required checks:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"SPEC_READY audit artifact valid for predicate {audit['predicate_id']} profile={audit.get('profile_id', 'LEGACY')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
