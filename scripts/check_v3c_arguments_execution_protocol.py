#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/profitability/v3c_arguments_execution_protocol_v1.json"
BOUNDARY = ROOT / "research/profitability/v3c_arguments_execution_evidence_boundary.json"
ARGUMENTS = ROOT / "research/recovery/issue_127_payloads/web_mmt_arguments_20260817.json"
TWO_CR = ROOT / "research/recovery/issue_167_payloads/web_mmt_2cr_exact_20260817.json"
EXPECTED_SHA = "0b3a6a5e217e7e4c279f7384c14579e97bf6821bc59deefac3086e7b4ce4ba7a"


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> None:
    p = json.loads(PROTOCOL.read_text())
    recorded = p.pop("protocol_sha256", "")
    assert recorded == EXPECTED_SHA
    assert canon(p) == EXPECTED_SHA, "protocol SHA drift"
    assert p["status"] == "FROZEN_BEFORE_V3C_POST_TRIGGER_OUTCOME_ACCESS"
    assert p["trigger"]["candidate_sha256"] == "de51f2c721aaedd0f6587755ebcab31ac2b264188d3de1f5531ec7057fb53b7b"
    assert p["market_data"]["backward_oos_start"] == "2010-01-01T00:00:00Z"
    assert p["market_data"]["backward_oos_end_exclusive"] == "2024-01-01T00:00:00Z"
    assert p["market_data"]["development_2024_2025_outcomes_must_remain_unread"] is True
    assert p["market_data"]["request_m1_only_after_backward_oos_trigger_set_is_sealed"] is True
    assert p["entry"]["direction"] == "LONG"
    assert p["target"]["multiple_r"] == 2.0
    assert p["expiry"]["max_complete_m1_bars_from_entry_inclusive"] == 1440
    assert p["signal_portfolio_policy"]["concurrent_positions"] == "ONE_OPEN_LONG_POSITION_MAXIMUM"
    assert p["metrics"]["minimum_resolved_executed_trades"] == 100
    assert p["authorization"] == {"paper_execution": False, "live_execution": False, "broker_mutation": False}
    assert p["semantic_boundary"] == {
        "direct_first_party_entry_fill": False,
        "direct_first_party_stop_selector_for_arguments_family": False,
        "direct_first_party_target_selector_for_arguments_family": False,
        "measurement_conventions_are_not_arjo_semantic_closure": True,
    }

    b = json.loads(BOUNDARY.read_text())
    assert b["status"] == "FROZEN_BEFORE_V3C_OUTCOME_ACCESS"
    assert b["post_trigger_outcomes_accessed"] is False
    assert b["performance_metrics_accessed"] is False
    assert b["backward_oos_outcomes_accessed"] is False
    assert len(b["owner_operational_measurement_conventions"]) == 8

    a = json.loads(ARGUMENTS.read_text())
    c = json.loads(TWO_CR.read_text())
    assert a["source_id"] == "WEB_MMT_ARGUMENTS_20260817"
    assert c["source_id"] == "WEB_MMT_2CR_EXACT_20260817"
    assert any("Swing High on the 4h" in x for x in a["excerpts"])
    assert any("rejection high gets run" in x for x in a["excerpts"])
    assert any("candle close above the high" in x for x in c["excerpts"])

    print(json.dumps({
        "status": "V3_ARGUMENTS_EXECUTION_PROTOCOL_FROZEN",
        "protocol_sha256": EXPECTED_SHA,
        "post_trigger_outcomes_accessed": False,
        "performance_metrics_accessed": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
