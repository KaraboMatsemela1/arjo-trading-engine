#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_occurrence_annotation_passes import (  # noqa: E402
    ReconcileError, canonical_sha256, read_pack_universe, reconcile, validate_pass,
)


def pack_manifest(items: list[dict]) -> dict:
    return {
        "status": "OUTCOME_BLIND_ANNOTATION_PACKS_READY",
        "pack_count": len(items),
        "post_woo_bars_included": False,
        "holdout_accessed": False,
        "performance_fields_included": False,
        "packs_sha256": canonical_sha256(items),
        "packs": items,
    }


def row(day: str, sha: str, pass_id: str, decision: str, anchors=None) -> dict:
    return {
        "schema_version": 1,
        "session_date_ny": day,
        "pack_sha256": sha,
        "pass_id": pass_id,
        "annotator_id": f"GPT_5_6_SOL_{pass_id}",
        "annotator_class": "GPT_5_6_SOL",
        "independent_human_annotator_claimed": False,
        "isolation_mode": "SAME_MODEL_SEPARATE_PASS_NO_CROSS_REFERENCE",
        "outcome_blind": True,
        "decision": decision,
        "anchors": copy.deepcopy(anchors),
        "anchors_sha256": canonical_sha256(anchors) if anchors is not None else None,
    }


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except ReconcileError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected {needle!r}")


def main() -> int:
    items = [
        {"session_date_ny": "2025-01-02", "pack_sha256": "1" * 64},
        {"session_date_ny": "2025-01-03", "pack_sha256": "2" * 64},
        {"session_date_ny": "2025-01-06", "pack_sha256": "3" * 64},
    ]
    anchors = {"semantic": {"price": "100.0"}}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "packs.json"
        p.write_text(json.dumps(pack_manifest(items)))
        universe = read_pack_universe([p])

    a_rows = [
        row(items[0]["session_date_ny"], items[0]["pack_sha256"], "PASS_A", "QUALIFIED", anchors),
        row(items[1]["session_date_ny"], items[1]["pack_sha256"], "PASS_A", "NO_QUALIFIED_OCCURRENCE"),
        row(items[2]["session_date_ny"], items[2]["pack_sha256"], "PASS_A", "QUALIFIED", anchors),
    ]
    b_rows = [
        row(items[0]["session_date_ny"], items[0]["pack_sha256"], "PASS_B", "QUALIFIED", anchors),
        row(items[1]["session_date_ny"], items[1]["pack_sha256"], "PASS_B", "NO_QUALIFIED_OCCURRENCE"),
        row(items[2]["session_date_ny"], items[2]["pack_sha256"], "PASS_B", "UNRESOLVED"),
    ]
    a = validate_pass(a_rows, pass_id="PASS_A", universe=universe)
    b = validate_pass(b_rows, pass_id="PASS_B", universe=universe)
    consensus, manifest = reconcile(universe, a, b)
    assert [x["decision"] for x in consensus] == ["QUALIFIED", "NO_QUALIFIED_OCCURRENCE", "UNRESOLVED"]
    assert manifest["decision_counts"] == {"QUALIFIED": 1, "NO_QUALIFIED_OCCURRENCE": 1, "UNRESOLVED": 1}
    assert manifest["independent_human_consensus_claimed"] is False

    disagreement = copy.deepcopy(b_rows)
    disagreement[0]["anchors"] = {"semantic": {"price": "101.0"}}
    disagreement[0]["anchors_sha256"] = canonical_sha256(disagreement[0]["anchors"])
    b2 = validate_pass(disagreement, pass_id="PASS_B", universe=universe)
    consensus2, _ = reconcile(universe, a, b2)
    assert consensus2[0]["decision"] == "UNRESOLVED"
    assert consensus2[0]["anchors"] is None

    missing = a_rows[:-1]
    expect_error(lambda: validate_pass(missing, pass_id="PASS_A", universe=universe), "pack universe mismatch")

    false_independence = copy.deepcopy(a_rows)
    false_independence[0]["independent_human_annotator_claimed"] = True
    expect_error(lambda: validate_pass(false_independence, pass_id="PASS_A", universe=universe), "independent-human claim")

    leaked = copy.deepcopy(a_rows)
    leaked[0]["pnl"] = 100
    expect_error(lambda: validate_pass(leaked, pass_id="PASS_A", universe=universe), "forbidden outcome/performance")

    bad_pack = copy.deepcopy(a_rows)
    bad_pack[0]["pack_sha256"] = "f" * 64
    expect_error(lambda: validate_pass(bad_pack, pass_id="PASS_A", universe=universe), "unknown/tampered pack identity")

    bad_nonqualified = copy.deepcopy(a_rows)
    bad_nonqualified[1]["anchors"] = anchors
    bad_nonqualified[1]["anchors_sha256"] = canonical_sha256(anchors)
    expect_error(lambda: validate_pass(bad_nonqualified, pass_id="PASS_A", universe=universe), "may not carry anchors")

    print("Occurrence annotation reconciliation tests passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
