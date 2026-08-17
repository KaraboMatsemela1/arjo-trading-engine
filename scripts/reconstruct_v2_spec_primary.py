#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_owner_operational_context_occurrences import build as build_occurrences, canonical_sha256
from check_v2_execution_observability import build as apply_observability

PROFILE_ID = "ARJO_DERIVED_OWNER_OPERATIONAL_V2"


class V2PrimaryError(RuntimeError):
    pass


def load_profile(path: Path) -> tuple[dict, str]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = profile.get("profile_sha256")
    unsigned = dict(profile)
    unsigned.pop("profile_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual or profile.get("profile_id") != PROFILE_ID:
        raise V2PrimaryError("V2 profile integrity mismatch")
    if profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise V2PrimaryError("semantic closure claim changed")
    if any(
        profile.get("authorization", {}).get(key) is not False
        for key in ("paper_execution_authorized", "live_execution_authorized", "broker_mutation_authorized")
    ):
        raise V2PrimaryError("execution authorization changed")
    if profile.get("data_boundary", {}).get("consumed_v1_holdout_2026h1_access_allowed") is not False:
        raise V2PrimaryError("2026H1 reuse allowed")
    return profile, actual


def build(*, profile_path: Path, context_path: Path, fvg_path: Path, artifact_dirs: list[Path]) -> dict:
    _, profile_sha = load_profile(profile_path)
    semantic = build_occurrences(
        context_convention_path=context_path,
        fvg_convention_path=fvg_path,
        artifact_dirs=artifact_dirs,
    )
    observability = apply_observability(semantic)
    report = {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "profile_sha256": profile_sha,
        "path_id": "PRIMARY_V2_PRODUCTION_PATH",
        "reconstruction_status": "PASS",
        "semantic_closure_claimed": False,
        "fully_first_party_reconstructed": False,
        "semantic_occurrence_set_sha256": semantic["occurrence_set_sha256"],
        "qualification_rows_sha256": semantic["qualification_rows_sha256"],
        "qualification_status_counts": semantic["status_counts"],
        "qualified_occurrence_ids": [row["occurrence_id"] for row in semantic["occurrences"]],
        "observability_rows_sha256": observability["observability_rows_sha256"],
        "observability_status_counts": observability["status_counts"],
        "executable_occurrence_ids": observability["executable_occurrence_ids"],
        "holdout_2026h1_accessed": False,
        "future_validation_data_accessed": False,
        "performance_comparison_performed": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    report["reconstruction_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            profile_path=Path(args.profile),
            context_path=Path(args.context_convention),
            fvg_path=Path(args.fvg_convention),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"V2 primary reconstruction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"path_id": result["path_id"], "sha256": result["reconstruction_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
