#!/usr/bin/env python3
"""Reconcile two isolated outcome-blind semantic annotation passes.

The two passes may be produced by the same model in separate non-cross-referencing
runs. This script therefore treats agreement as a reproducibility check, not as
independent-human consensus. It never discovers or repairs semantic anchors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DECISIONS = {"QUALIFIED", "NO_QUALIFIED_OCCURRENCE", "UNRESOLVED"}
FORBIDDEN_KEYS = {
    "pnl", "profit", "loss", "win", "return", "performance", "target_hit",
    "stop_hit", "rr", "expectancy", "score", "rank", "future_bars",
    "post_woo", "outcome",
}
EXPECTED_ISOLATION = "SAME_MODEL_SEPARATE_PASS_NO_CROSS_REFERENCE"
EXPECTED_CLASS = "GPT_5_6_SOL"


class ReconcileError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def assert_no_outcomes(value: object, path: str = "row") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in FORBIDDEN_KEYS:
                raise ReconcileError(f"forbidden outcome/performance key at {path}.{key}")
            assert_no_outcomes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            assert_no_outcomes(child, f"{path}[{idx}]")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReconcileError(f"{path}:{line_no} invalid JSON") from exc
            if not isinstance(row, dict):
                raise ReconcileError(f"{path}:{line_no} row must be object")
            rows.append(row)
    return rows


def read_pack_universe(paths: list[Path]) -> dict[str, str]:
    universe: dict[str, str] = {}
    for path in paths:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("status") != "OUTCOME_BLIND_ANNOTATION_PACKS_READY":
            raise ReconcileError(f"{path} is not a verified pack manifest")
        if manifest.get("post_woo_bars_included") is not False:
            raise ReconcileError(f"{path} indicates post-WoO bars")
        if manifest.get("holdout_accessed") is not False:
            raise ReconcileError(f"{path} indicates holdout access")
        if manifest.get("performance_fields_included") is not False:
            raise ReconcileError(f"{path} indicates performance fields")
        packs = manifest.get("packs")
        if not isinstance(packs, list) or len(packs) != int(manifest.get("pack_count", -1)):
            raise ReconcileError(f"{path} pack list/count mismatch")
        if canonical_sha256(packs) != manifest.get("packs_sha256"):
            raise ReconcileError(f"{path} pack list SHA mismatch")
        for item in packs:
            day = str(item.get("session_date_ny", ""))
            sha = str(item.get("pack_sha256", ""))
            if not day or len(sha) != 64:
                raise ReconcileError(f"{path} malformed pack identity")
            if day in universe and universe[day] != sha:
                raise ReconcileError(f"duplicate session has conflicting pack SHA: {day}")
            universe[day] = sha
    if not universe:
        raise ReconcileError("empty pack universe")
    return universe


def validate_pass(rows: list[dict], *, pass_id: str, universe: dict[str, str]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        assert_no_outcomes(row)
        if row.get("schema_version") != 1:
            raise ReconcileError(f"{pass_id}: unsupported row schema")
        if row.get("pass_id") != pass_id:
            raise ReconcileError(f"{pass_id}: row pass_id mismatch")
        if row.get("annotator_class") != EXPECTED_CLASS:
            raise ReconcileError(f"{pass_id}: annotator_class mismatch")
        if row.get("independent_human_annotator_claimed") is not False:
            raise ReconcileError(f"{pass_id}: independent-human claim is prohibited")
        if row.get("isolation_mode") != EXPECTED_ISOLATION:
            raise ReconcileError(f"{pass_id}: isolation_mode mismatch")
        if row.get("outcome_blind") is not True:
            raise ReconcileError(f"{pass_id}: outcome_blind must be true")
        day = str(row.get("session_date_ny", ""))
        pack_sha = str(row.get("pack_sha256", ""))
        if day not in universe or universe[day] != pack_sha:
            raise ReconcileError(f"{pass_id}: unknown/tampered pack identity {day}")
        if day in indexed:
            raise ReconcileError(f"{pass_id}: duplicate session {day}")
        decision = row.get("decision")
        if decision not in DECISIONS:
            raise ReconcileError(f"{pass_id}: invalid decision for {day}")
        anchors = row.get("anchors")
        anchor_sha = row.get("anchors_sha256")
        if decision == "QUALIFIED":
            if not isinstance(anchors, dict) or not anchors:
                raise ReconcileError(f"{pass_id}: qualified row missing anchors {day}")
            if anchor_sha != canonical_sha256(anchors):
                raise ReconcileError(f"{pass_id}: qualified anchor SHA mismatch {day}")
        else:
            if anchors is not None or anchor_sha is not None:
                raise ReconcileError(f"{pass_id}: non-qualified row may not carry anchors {day}")
        indexed[day] = row
    missing = sorted(set(universe) - set(indexed))
    extra = sorted(set(indexed) - set(universe))
    if missing or extra:
        raise ReconcileError(f"{pass_id}: pack universe mismatch missing={len(missing)} extra={len(extra)}")
    return indexed


def reconcile(universe: dict[str, str], a: dict[str, dict], b: dict[str, dict]) -> tuple[list[dict], dict]:
    consensus: list[dict] = []
    counts = {"QUALIFIED": 0, "NO_QUALIFIED_OCCURRENCE": 0, "UNRESOLVED": 0}
    for day in sorted(universe):
        ra, rb = a[day], b[day]
        da, db = ra["decision"], rb["decision"]
        result = {
            "schema_version": 1,
            "session_date_ny": day,
            "pack_sha256": universe[day],
            "decision": "UNRESOLVED",
            "anchors": None,
            "anchors_sha256": None,
            "pass_a_decision": da,
            "pass_b_decision": db,
            "same_model_reproducibility_only": True,
        }
        if da == db == "NO_QUALIFIED_OCCURRENCE":
            result["decision"] = "NO_QUALIFIED_OCCURRENCE"
        elif da == db == "QUALIFIED":
            if ra["anchors_sha256"] == rb["anchors_sha256"] and ra["anchors"] == rb["anchors"]:
                result["decision"] = "QUALIFIED"
                result["anchors"] = ra["anchors"]
                result["anchors_sha256"] = ra["anchors_sha256"]
        # Any disagreement or any UNRESOLVED remains UNRESOLVED by construction.
        counts[result["decision"]] += 1
        consensus.append(result)
    manifest = {
        "schema_version": 1,
        "status": "OCCURRENCE_ANNOTATION_CONSENSUS_RECONCILED",
        "session_count": len(consensus),
        "decision_counts": counts,
        "same_model_reproducibility_only": True,
        "independent_human_consensus_claimed": False,
        "post_woo_outcome_accessed": False,
        "holdout_accessed": False,
        "performance_fields_used": False,
        "consensus_sha256": canonical_sha256(consensus),
    }
    return consensus, manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pack-manifest", action="append", required=True)
    p.add_argument("--pass-a", required=True)
    p.add_argument("--pass-b", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--manifest-output", required=True)
    args = p.parse_args()
    try:
        universe = read_pack_universe([Path(x) for x in args.pack_manifest])
        a = validate_pass(read_jsonl(Path(args.pass_a)), pass_id="PASS_A", universe=universe)
        b = validate_pass(read_jsonl(Path(args.pass_b)), pass_id="PASS_B", universe=universe)
        consensus, manifest = reconcile(universe, a, b)
    except (OSError, ValueError, json.JSONDecodeError, ReconcileError) as exc:
        print(f"annotation reconciliation failed: {exc}", file=sys.stderr)
        return 1
    Path(args.output).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in consensus), encoding="utf-8")
    Path(args.manifest_output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
