#!/usr/bin/env python3
"""Primary V2 future-validation evaluator using production semantic primitives."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import run_protected_validation_primary as base
from build_owner_operational_fvg_anchors import detect_formations
from check_v2_future_validation_access_v2 import authorize, canonical_sha256
from v2_m1_execution_measurement import measure_occurrence

START = datetime(2026, 9, 1, tzinfo=UTC)
SCORED_START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2027, 3, 1, tzinfo=UTC)
PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
PROTOCOL_SHA = "193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38"
POLICY_SHA = "6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6"
CONTRACT_SHA = "edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca"


class FutureValidationError(RuntimeError):
    pass


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _embedded(path: Path, field: str, expected: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    unsigned = dict(data); recorded = str(unsigned.pop(field, ""))
    if recorded != expected or canonical_sha256(unsigned) != expected:
        raise FutureValidationError(f"{path} frozen SHA mismatch")
    return data


def verify_inputs(data_dir: Path, profile_path: Path) -> dict:
    profile = _embedded(profile_path, "profile_sha256", PROFILE_SHA)
    if profile.get("profile_id") != "ARJO_DERIVED_OWNER_OPERATIONAL_V2" or profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise FutureValidationError("V2 profile boundary changed")
    manifest_path = data_dir / "NAS100_USD.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    unsigned = dict(manifest); recorded = str(unsigned.pop("manifest_sha256", ""))
    if not recorded or canonical_sha256(unsigned) != recorded:
        raise FutureValidationError("future data manifest SHA mismatch")
    expected = {
        "status": "V2_FUTURE_VALIDATION_DATA_READY",
        "validation_protocol_sha256": PROTOCOL_SHA,
        "measurement_policy_sha256": POLICY_SHA,
        "request_contract_sha256": CONTRACT_SHA,
        "provider": "OANDA_V20",
        "venue": "OANDA_FXTRADE",
        "environment": "practice",
        "instrument": "NAS100_USD",
        "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
        "price_component": "MID",
        "source_granularity": "M1",
        "requested_start": "2026-09-01T00:00:00Z",
        "bootstrap_end_exclusive": "2026-10-01T00:00:00Z",
        "scored_start": "2026-10-01T00:00:00Z",
        "requested_end_exclusive": "2027-03-01T00:00:00Z",
        "full_window_single_shot": True,
        "state_at_start": "EMPTY",
        "pre_start_market_data_accessed": False,
        "v1_holdout_reused": False,
        "future_validation_data_accessed": True,
        "mutation_endpoints_used": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise FutureValidationError(f"future manifest boundary changed: {key}")
    for minutes in (15, 60, 240):
        path = data_dir / f"NAS100_USD.{minutes}m.jsonl"
        if str(manifest.get("derived", {}).get(str(minutes), {}).get("sha256")) != _file_sha(path):
            raise FutureValidationError(f"derived {minutes}m SHA mismatch")
    if manifest.get("m1_sha256") != _file_sha(data_dir / "NAS100_USD.M1.jsonl"):
        raise FutureValidationError("M1 SHA mismatch")
    return manifest


def load_m1(path: Path) -> list[dict]:
    output: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line); output.append({"ts_start_utc": row["ts_start_utc"], "low": row["low"], "high": row["high"]})
    return output


def metrics(*, session_count: int, qualified_count: int, observability_rows: list[dict], outcomes: list[dict]) -> dict:
    executable = sum(row["status"] == "EXECUTABLE_ENTRY" for row in observability_rows)
    no_exec = sum(row["status"] == "NO_EXECUTABLE_ENTRY" for row in observability_rows)
    counts = dict(sorted(Counter(row["execution_outcome"] for row in outcomes).items()))
    resolved_rows = [row for row in outcomes if row["execution_outcome"] in {"TARGET_FIRST", "STOP_FIRST"}]
    realized: list[float] = []
    for row in resolved_rows:
        if row["execution_outcome"] == "STOP_FIRST":
            realized.append(-1.0)
        else:
            entry, stop, target = float(row["entry_price"]), float(row["stop_price"]), float(row["target_price"])
            realized.append((target - entry) / (entry - stop))
    resolved = len(realized)
    wins = counts.get("TARGET_FIRST", 0)
    proportion = wins / resolved if resolved else None
    interval = None
    if resolved:
        z = 1.959963984540054; n = resolved; p = proportion
        denom = 1 + z*z/n; center = (p + z*z/(2*n))/denom
        half = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/denom
        interval = [max(0.0, center-half), min(1.0, center+half)]
    return {
        "complete_session_count": session_count,
        "qualified_occurrence_count": qualified_count,
        "occurrence_rate_per_complete_session": qualified_count / session_count if session_count else 0.0,
        "executable_entry_count": executable,
        "no_executable_entry_count": no_exec,
        "executable_rate_per_qualified_occurrence": executable / qualified_count if qualified_count else None,
        "outcome_counts_for_executable_entries": counts,
        "resolved_executable_occurrence_count": resolved,
        "realized_r": realized,
        "mean_realized_r_when_resolved": sum(realized)/resolved if resolved else None,
        "cumulative_realized_r_when_resolved": sum(realized) if resolved else None,
        "target_first_proportion_among_resolved": proportion,
        "target_first_wilson_interval_95": interval,
        "inferential_resolved_executable_occurrence_threshold": 30,
    }


def classification(*, qualified_count: int, metrics_state: dict, integrity_failures: list[dict]) -> str:
    if integrity_failures:
        return "VALIDATION_INTEGRITY_FAILURE"
    if qualified_count == 0:
        return "NO_QUALIFYING_OCCURRENCES"
    if metrics_state["executable_entry_count"] == 0:
        return "NO_EXECUTABLE_ENTRIES"
    if metrics_state["resolved_executable_occurrence_count"] < 30:
        return "INSUFFICIENT_SAMPLE"
    return "SUFFICIENT_SAMPLE_POSITIVE" if float(metrics_state["mean_realized_r_when_resolved"]) > 0 else "SUFFICIENT_SAMPLE_NONPOSITIVE"


def evaluate_core(*, rows15: list[dict], rows60: list[dict], rows240: list[dict], m1_rows: list[dict]) -> dict:
    base.HSTART = SCORED_START; base.HEND = END
    sessions = base.complete_holdout_sessions(rows15)
    formations = detect_formations(rows240)
    fvg_state = base.select_fvgs(rows15, formations, sessions)
    ledger, occurrences, status_counts = base.qualify(rows15, rows60, rows240, fvg_state)
    observability_rows: list[dict] = []
    outcomes: list[dict] = []
    integrity_failures: list[dict] = []
    executable_ids: list[str] = []
    for occ in occurrences:
        touch = float(occ["touch_price"]); low = float(occ["second_sting_bar_low"]); high = float(occ["second_sting_bar_high"])
        status = "EXECUTABLE_ENTRY" if low <= touch <= high else "NO_EXECUTABLE_ENTRY"
        obs = {"occurrence_id": occ["occurrence_id"], "status": status, "second_sting_ts_utc": occ["second_sting_ts_utc"], "touch_price": occ["touch_price"], "bar_low": occ["second_sting_bar_low"], "bar_high": occ["second_sting_bar_high"]}
        observability_rows.append(obs)
        measurement = measure_occurrence(occurrence=occ, observability_status=status, m1_rows=m1_rows, end_exclusive=END)
        if measurement.get("measurement_status") == "VALIDATION_INTEGRITY_FAILURE":
            integrity_failures.append({"occurrence_id": occ["occurrence_id"], "kind": measurement["integrity_failure"]})
        elif status == "EXECUTABLE_ENTRY":
            executable_ids.append(occ["occurrence_id"])
            if measurement.get("execution_outcome") is not None:
                outcomes.append(measurement)
    observability_rows.sort(key=lambda row: row["occurrence_id"]); outcomes.sort(key=lambda row: row["occurrence_id"])
    metric_state = metrics(session_count=len(sessions), qualified_count=len(occurrences), observability_rows=observability_rows, outcomes=outcomes)
    return {
        "complete_session_count": len(sessions),
        "detected_fvg_formation_count": len(formations),
        "selected_fvg_session_count": int(fvg_state["selected_count"]),
        "qualification_status_counts": status_counts,
        "qualified_occurrence_ids": [row["occurrence_id"] for row in occurrences],
        "qualification_rows_sha256": canonical_sha256(ledger),
        "semantic_occurrence_set_sha256": canonical_sha256(occurrences),
        "observability_rows": observability_rows,
        "observability_rows_sha256": canonical_sha256(observability_rows),
        "observability_status_counts": dict(sorted(Counter(row["status"] for row in observability_rows).items())),
        "executable_occurrence_ids": sorted(executable_ids),
        "execution_outcomes": outcomes,
        "execution_outcomes_sha256": canonical_sha256(outcomes),
        "integrity_failures": integrity_failures,
        "metrics": metric_state,
        "validation_classification": classification(qualified_count=len(occurrences), metrics_state=metric_state, integrity_failures=integrity_failures),
        "future_validation_boundary_ok": True,
    }


def build(*, data_dir: Path, profile_path: Path) -> dict:
    manifest = verify_inputs(data_dir, profile_path)
    rows15 = base.load_jsonl(data_dir / "NAS100_USD.15m.jsonl", 15)
    rows60 = base.load_jsonl(data_dir / "NAS100_USD.60m.jsonl", 60)
    rows240 = base.load_jsonl(data_dir / "NAS100_USD.240m.jsonl", 240)
    result = evaluate_core(rows15=rows15, rows60=rows60, rows240=rows240, m1_rows=load_m1(data_dir / "NAS100_USD.M1.jsonl"))
    report = {
        "schema_version": 1, "path_id": "PRIMARY_V2_PRODUCTION_PATH", "status": "V2_FUTURE_VALIDATION_PATH_COMPLETE",
        "profile_sha256": PROFILE_SHA, "protocol_sha256": PROTOCOL_SHA, "measurement_policy_sha256": POLICY_SHA,
        "data_manifest_sha256": manifest["manifest_sha256"], **result,
        "holdout_2026h1_accessed": False, "pre_start_market_data_accessed": False,
        "paper_execution_authorized": False, "live_execution_authorized": False, "broker_mutation_authorized": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--authorization", required=True); p.add_argument("--data-dir", required=True); p.add_argument("--output", required=True); p.add_argument("--profile", default="docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V2.json")
    args = p.parse_args()
    try:
        authorize(gate="evaluation", now=datetime.now(UTC), authorization_path=Path(args.authorization), protocol_path=Path("research/v2/future_validation_protocol_v2.json"), policy_path=Path("research/v2/v2_m1_touch_sequencing_v1.json"), readiness_path=Path("research/v2/v2_m1_measurement_readiness.json"), contract_path=Path("research/v2/nas100_oanda_future_validation_request_contract.json"))
        report = build(data_dir=Path(args.data_dir), profile_path=Path(args.profile))
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    except Exception as exc:
        print(f"primary V2 future validation failed: {exc}", file=sys.stderr); return 1
    print(json.dumps({"path_id": report["path_id"], "classification": report["validation_classification"], "report_sha256": report["report_sha256"]}, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
