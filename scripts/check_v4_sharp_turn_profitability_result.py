#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("research/profitability/v4_sharp_turn_result")
RESULT = ROOT / "result.json"
MANIFEST = ROOT / "manifest.json"
PROVENANCE = ROOT / "provider_provenance.json"
BASE_LEDGER = ROOT / "base_trade_ledger.jsonl"
STRESS_LEDGER = ROOT / "stress_trade_ledger.jsonl"
TRIGGERS = ROOT / "pre_m1_trigger_reconstruction.json"
INDEX = ROOT / "sealed_result_index_v1.json"

EXPECTED_RESULT_SHA = "611cc822dcc5103ed700d245e3ffb95404ca9c41459a43f9b5183aa84aedf6b5"
EXPECTED_INDEX_SHA = "378914c83709e38457a1e2ff6638f4bfc03940900359722039c6f3a0b846f502"
EXPECTED_TRIGGER_SHA = "1df6eabb176ef85ce203f3eeb7b76007d0114dfb98d1b1ad0f76f703d779847a"
EXPECTED_READINESS_SHA = "6fb99be106ffa98857693211c5e4814f90a1e874b3255168874a0e1a47a6dba3"
EXPECTED_PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
EXPECTED_LOCK_SHA = "846e3c106f9f478fe3ef74ad8152431f42bc2d0cac0d314d9a71d6aef8f0ec30"
EXPECTED_ARTIFACT_ZIP_SHA = "d9b0423bec7a0f1e483a969b5dc52445814775397a2d44891af52b2a233683c5"
EXPECTED_MANIFEST_SHA = "d331ac40cad6a6a8d9f22dde0d266bb08267ff3b7e5d5e9b2a185599fe75a405"
EXPECTED_PROVIDER_SHA = "49613226a15a5837f8bad201b64027a5135cfcd293ad1bf1774d0180343b03eb"
END = datetime(2024, 1, 1, tzinfo=UTC)


def canon(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def verify_result() -> dict:
    r = json.loads(RESULT.read_text())
    unsigned = dict(r)
    recorded = unsigned.pop("result_sha256")
    assert recorded == EXPECTED_RESULT_SHA
    assert canon(unsigned) == EXPECTED_RESULT_SHA, "result SHA drift"
    assert r["status"] == "V4_SHARP_TURN_PROFITABILITY_RESULT_READY"
    assert r["classification"] == "EDGE_NOT_ESTABLISHED"
    assert r["validated_historical_edge"] is False
    assert r["strong_historical_edge"] is False
    assert r["historical_window_classification"] == "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT"
    assert r["trigger_set_sha256"] == EXPECTED_TRIGGER_SHA
    assert r["trigger_readiness_sha256"] == EXPECTED_READINESS_SHA
    assert r["execution_protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    assert r["profitability_execution_lock_sha256"] == EXPECTED_LOCK_SHA
    assert r["trigger_count"] == 213
    assert r["long_trigger_count"] == 192
    assert r["short_trigger_count"] == 21
    assert r["exact_trigger_reconstruction_before_first_m1_response"] is True
    assert r["first_m1_response_accessed"] is True
    assert r["parameter_changes_after_first_m1_response"] is False
    assert r["no_refit_performed"] is True
    assert r["v3c_outcomes_used_for_v4_execution_selection"] is False
    assert r["post_2023_m1_requested_or_admitted"] is False
    assert r["synthetic_fills"] == 0
    assert r["provider_chunks_requested"] == 780
    assert r["provider_provenance_sha256"] == EXPECTED_PROVIDER_SHA
    assert r["paper_execution_authorized"] is False
    assert r["live_execution_authorized"] is False
    assert r["broker_mutation_authorized"] is False

    b, s = r["base_metrics"], r["stress_metrics"]
    assert b["resolved_executed_trades"] == 127
    assert b["long_trades"] == 115 and b["short_trades"] == 12
    assert b["status_counts"] == {"RIGHT_CENSORED_DATASET_END": 1, "SKIPPED_CONCURRENT_POSITION": 85, "STOP": 82, "TARGET": 45}
    assert b["data_integrity_failures"] == 0 and b["synthetic_fills"] == 0
    assert b["net_expectancy_r"] == 0.0014091677822265101
    assert b["profit_factor"] == 1.0020664176151879
    assert b["bootstrap_95pct_ci_net_expectancy_r"] == [-0.24246404376698275, 0.25455263594850913]
    assert b["win_rate"] == 0.3543307086614173
    assert b["max_drawdown_r"] == 18.16758391184618
    assert b["ledger_sha256"] == "2acf31b9f33617a6a3f11456008e3311a47cd0de57bae4f64e7e22cda65176d0"
    assert s["resolved_executed_trades"] == 127
    assert s["long_trades"] == 115 and s["short_trades"] == 12
    assert s["status_counts"] == {"RIGHT_CENSORED_DATASET_END": 1, "SKIPPED_CONCURRENT_POSITION": 85, "STOP": 84, "TARGET": 43}
    assert s["data_integrity_failures"] == 0 and s["synthetic_fills"] == 0
    assert s["net_expectancy_r"] == -0.10639283934312664
    assert s["profit_factor"] == 0.8554420945575948
    assert s["bootstrap_95pct_ci_net_expectancy_r"] == [-0.3458839445238532, 0.14838828933321035]
    assert s["ledger_sha256"] == "5f52e57e955ff9ef692111ac904e994e92516c5f0e35efa1ded3aa3f9a9b3ff4"
    return r


def verify_manifest(r: dict) -> dict:
    m = json.loads(MANIFEST.read_text())
    unsigned = dict(m)
    recorded = unsigned.pop("manifest_sha256")
    assert recorded == EXPECTED_MANIFEST_SHA
    assert canon(unsigned) == EXPECTED_MANIFEST_SHA, "evidence manifest SHA drift"
    assert m["status"] == "V4_SHARP_TURN_PROFITABILITY_EVIDENCE_PERSISTED"
    assert m["source_workflow_run_id"] == 32142106100
    assert m["source_head_sha"] == "424bd5683d8dd4a536fe60dc6a606fa59bfd931a"
    assert m["classification"] == "EDGE_NOT_ESTABLISHED"
    assert m["result_sha256"] == r["result_sha256"]
    assert m["paper_execution_authorized"] is False
    assert m["live_execution_authorized"] is False
    assert m["broker_mutation_authorized"] is False
    for name, path in {
        "result.json": RESULT,
        "provider_provenance.json": PROVENANCE,
        "base_trade_ledger.jsonl": BASE_LEDGER,
        "stress_trade_ledger.jsonl": STRESS_LEDGER,
        "pre_m1_trigger_reconstruction.json": TRIGGERS,
    }.items():
        assert path.is_file() and path.stat().st_size == m["files"][name]["bytes"]
        assert file_sha(path) == m["files"][name]["sha256"], name
    return m


def verify_provider(r: dict) -> None:
    p = json.loads(PROVENANCE.read_text())
    unsigned = dict(p)
    recorded = unsigned.pop("provenance_sha256")
    assert recorded == EXPECTED_PROVIDER_SHA
    assert canon(unsigned) == EXPECTED_PROVIDER_SHA, "provider provenance SHA drift"
    assert p["provider"] == "OANDA_V20"
    assert p["environment"] == "practice"
    assert p["instrument"] == "NAS100_USD"
    assert p["granularity"] == "M1"
    assert p["price_components"] == "BA"
    assert p["chunk_calendar_days"] == 3
    assert p["strict_end_exclusive"] == "2024-01-01T00:00:00Z"
    assert p["last_request_to_lt_strict_end"] is True
    assert p["chunks_requested"] == r["provider_chunks_requested"] == 780
    assert p["first_m1_response_accessed"] is True
    assert p["credentials_exposed"] is False
    assert p["mutation_endpoints_used"] is False
    for chunk in p["chunks"]:
        assert parse(chunk["to"]) < END
        assert len(chunk["request_sha256"]) == 64
        assert len(chunk["raw_response_sha256"]) == 64
        assert len(chunk["parsed_sha256"]) == 64


def verify_ledgers(r: dict) -> None:
    base = read_jsonl(BASE_LEDGER)
    stress = read_jsonl(STRESS_LEDGER)
    assert canon(base) == r["base_ledger_sha256"]
    assert canon(stress) == r["stress_ledger_sha256"]
    assert len(base) == len(stress) == 213
    allowed = {"STOP", "TARGET", "RIGHT_CENSORED_DATASET_END", "SKIPPED_CONCURRENT_POSITION", "SKIPPED_DUPLICATE_TRIGGER_TIME", "DATA_INTEGRITY_FAILURE", "INVALID_RISK_ORDERING"}
    assert all(row["status"] in allowed for row in base + stress)


def verify_trigger_binding(r: dict) -> None:
    t = json.loads(TRIGGERS.read_text())
    assert t["status"] == "V4_SHARP_TURN_TRIGGERS_READY"
    assert t["trigger_set_sha256"] == EXPECTED_TRIGGER_SHA == r["trigger_set_sha256"]
    assert t["trigger_count"] == 213
    assert t["distinct_trigger_knowledge_times"] == 213
    assert t["economic_outcomes_accessed"] is False
    assert t["m1_data_requested"] is False


def verify_index(r: dict) -> None:
    x = json.loads(INDEX.read_text())
    unsigned = dict(x)
    recorded = unsigned.pop("evidence_index_sha256")
    assert recorded == EXPECTED_INDEX_SHA
    assert canon(unsigned) == EXPECTED_INDEX_SHA, "sealed result index SHA drift"
    assert x["status"] == "V4_SHARP_TURN_PROFITABILITY_RESULT_SEALED"
    assert x["source_workflow_run_id"] == 32142106100
    assert x["source_head_sha"] == "424bd5683d8dd4a536fe60dc6a606fa59bfd931a"
    assert x["artifact_id"] == 9326688249
    assert x["artifact_zip_sha256"] == EXPECTED_ARTIFACT_ZIP_SHA
    assert x["result_sha256"] == r["result_sha256"]
    assert x["classification"] == r["classification"] == "EDGE_NOT_ESTABLISHED"
    assert x["data_integrity_failures"] == 0 and x["synthetic_fills"] == 0
    assert x["no_refit_performed"] is True
    assert x["paper_execution_authorized"] is False
    assert x["live_execution_authorized"] is False
    assert x["broker_mutation_authorized"] is False


def main() -> None:
    r = verify_result()
    verify_manifest(r)
    verify_provider(r)
    verify_ledgers(r)
    verify_trigger_binding(r)
    verify_index(r)
    print(json.dumps({
        "status": "V4_SHARP_TURN_PROFITABILITY_RESULT_VERIFIED",
        "classification": r["classification"],
        "result_sha256": r["result_sha256"],
        "resolved_trades": r["base_metrics"]["resolved_executed_trades"],
        "base_expectancy_r": r["base_metrics"]["net_expectancy_r"],
        "base_profit_factor": r["base_metrics"]["profit_factor"],
        "stress_expectancy_r": r["stress_metrics"]["net_expectancy_r"],
        "stress_profit_factor": r["stress_metrics"]["profit_factor"],
        "data_integrity_failures": 0,
        "synthetic_fills": 0,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
