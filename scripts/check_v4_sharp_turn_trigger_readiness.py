#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

READINESS = Path("research/profitability/v4_sharp_turn_trigger_readiness_v1.json")
EXPECTED_READINESS_SHA = "6fb99be106ffa98857693211c5e4814f90a1e874b3255168874a0e1a47a6dba3"
EXPECTED_PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
EXPECTED_TRIGGER_SHA = "1df6eabb176ef85ce203f3eeb7b76007d0114dfb98d1b1ad0f76f703d779847a"
EXPECTED_REPORT_SHA = "66162d2073b7806481bc384ba9de47ba34d71229760b704b2f2c79568bf25d70"
EXPECTED_MANIFEST_SHA = "7e05d892234c93dc7e27d298bf8c7fba475596c65fa7637236e9b4340bfa7f66"
EXPECTED_RETRIEVAL_SHA = "af895aa753f1f505d73faeb7ce97768347f8a0937a4c6574da43becf1f304e70"
EXPECTED_ROWS = {"M": 167, "W": 730, "D": 3661, "H1": 83704}
EXPECTED_FILE_SHAS = {
    "M": "23bcb4d90dc1fab1a349d8763f9b677ba3e975cfa1cb2e5ddeebe92644fd9df6",
    "W": "da56401905ffe857eef3e8ba8404135e308d1560131109bb33aabb1b5e80d100",
    "D": "eb6ceabefc2c14d6f2f1a968ef11e4b2875121262586127bf157ae2bb4fd8a53",
    "H1": "ea9a7a9b4868e0863c786499a7ec9c7a4681774081b8109a3cae74a800f8f73f",
}


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def verify_readiness() -> dict:
    r = json.loads(READINESS.read_text())
    unsigned = dict(r)
    recorded = unsigned.pop("readiness_sha256", "")
    assert recorded == EXPECTED_READINESS_SHA
    assert canon(unsigned) == EXPECTED_READINESS_SHA, "readiness SHA drift"
    assert r["status"] == "V4_SHARP_TURN_TRIGGERS_READY"
    assert r["classification"] == "TRIGGER_SAMPLE_NECESSARY_CONDITION_MET"
    assert r["boundary_revision"] == "V4_STRICT_CANDLE_COVERAGE_END_V2"
    assert r["protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    assert r["historical_window_classification"] == "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT"
    assert r["canonical_full_trigger_set_sha256"] == EXPECTED_TRIGGER_SHA
    assert r["source_report_sha256"] == EXPECTED_REPORT_SHA
    assert r["structure_manifest_sha256"] == EXPECTED_MANIFEST_SHA
    assert r["structure_retrieval_sha256"] == EXPECTED_RETRIEVAL_SHA
    assert r["structure_rows"] == EXPECTED_ROWS
    assert r["selected_daily_contexts"] == 351
    assert r["trigger_count"] == 213
    assert r["long_triggers"] == 192
    assert r["short_triggers"] == 21
    assert r["distinct_trigger_knowledge_times"] == 213
    assert r["minimum_distinct_knowledge_times_required"] == 100
    assert r["sample_necessary_condition_met"] is True
    assert r["primary_independent_fvg_exact_match"] is True
    assert r["primary_independent_context_exact_match"] is True
    assert r["primary_independent_trigger_exact_match"] is True
    assert r["all_admitted_candles_fully_contained_in_frozen_window"] is True
    assert r["noncanonical_run_32139161882_excluded"] is True
    for tf, sha in EXPECTED_FILE_SHAS.items():
        assert r["structure_timeframes"][tf]["sha256"] == sha
        assert r["structure_timeframes"][tf]["rows"] == EXPECTED_ROWS[tf]
    false_fields = [
        "m1_data_requested",
        "bid_ask_data_requested",
        "fill_prices_accessed",
        "stop_target_traversal_accessed",
        "pnl_accessed",
        "expectancy_accessed",
        "profit_factor_accessed",
        "win_rate_accessed",
        "bootstrap_metrics_accessed",
        "economic_outcomes_accessed",
        "v3c_trade_ledger_accessed_for_v4_selection",
        "parameter_refit_performed",
        "paper_execution_authorized",
        "live_execution_authorized",
        "broker_mutation_authorized",
    ]
    for field in false_fields:
        assert r[field] is False, field
    return r


def verify_reproduction(r: dict, report_path: Path, manifest_path: Path) -> None:
    report = json.loads(report_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert report["protocol_sha256"] == r["protocol_sha256"]
    assert report["boundary_revision"] == r["boundary_revision"]
    assert report["trigger_set_sha256"] == r["canonical_full_trigger_set_sha256"]
    assert report["report_sha256"] == r["source_report_sha256"]
    assert report["trigger_count"] == r["trigger_count"]
    assert report["long_triggers"] == r["long_triggers"]
    assert report["short_triggers"] == r["short_triggers"]
    assert report["distinct_trigger_knowledge_times"] == r["distinct_trigger_knowledge_times"]
    assert report["selected_daily_contexts"] == r["selected_daily_contexts"]
    assert manifest["manifest_sha256"] == r["structure_manifest_sha256"]
    assert manifest["retrieval_sha256"] == r["structure_retrieval_sha256"]
    assert manifest["all_admitted_candles_fully_contained_in_frozen_window"] is True
    for tf in EXPECTED_ROWS:
        assert manifest["timeframes"][tf]["rows"] == r["structure_timeframes"][tf]["rows"]
        assert manifest["timeframes"][tf]["sha256"] == r["structure_timeframes"][tf]["sha256"]
    assert report["m1_data_requested"] is False
    assert report["economic_outcomes_accessed"] is False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--computed-report", type=Path)
    parser.add_argument("--computed-manifest", type=Path)
    args = parser.parse_args()
    r = verify_readiness()
    if bool(args.computed_report) != bool(args.computed_manifest):
        raise SystemExit("computed report and manifest must be supplied together")
    if args.computed_report:
        verify_reproduction(r, args.computed_report, args.computed_manifest)
    print(
        json.dumps(
            {
                "status": r["status"],
                "readiness_sha256": EXPECTED_READINESS_SHA,
                "trigger_set_sha256": EXPECTED_TRIGGER_SHA,
                "trigger_count": 213,
                "distinct_trigger_knowledge_times": 213,
                "sample_necessary_condition_met": True,
                "exact_reproduction_checked": bool(args.computed_report),
                "m1_data_requested": False,
                "economic_outcomes_accessed": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
