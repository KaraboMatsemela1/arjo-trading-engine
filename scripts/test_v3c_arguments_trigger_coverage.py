#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "research/profitability/v3c_arguments_trigger_candidate.json"
SCANNER = ROOT / "scripts/scan_v3c_arguments_trigger_coverage.py"


def main() -> None:
    c = json.loads(CANDIDATE.read_text())
    assert c["candidate_sha256"] == "de51f2c721aaedd0f6587755ebcab31ac2b264188d3de1f5531ec7057fb53b7b"
    assert c["direct_first_party_sources"] == ["WEB_MMT_ARGUMENTS_20260817", "WEB_MMT_2CR_EXACT_20260817"]
    assert c["owner_operational_trigger"]["h4_swing_high"]["construction"] == "radius-1 three-bar pivot high"
    assert c["owner_operational_trigger"]["activation"]["predicate"] == "first later complete 1h close strictly above rejection_high"
    assert c["owner_operational_trigger"]["session_restriction"].startswith("NONE")
    assert c["owner_operational_trigger"]["expiry"].startswith("NONE")
    assert c["owner_operational_trigger"]["entry_fill"].startswith("UNRESOLVED")
    assert c["owner_operational_trigger"]["stop"].startswith("UNRESOLVED")
    assert c["owner_operational_trigger"]["target"].startswith("UNRESOLVED")
    assert c["development_coverage"]["coverage_floor"] == 30
    assert c["development_coverage"]["post_trigger_price_traversal_allowed"] is False
    assert c["development_coverage"]["performance_metrics_allowed"] is False
    assert c["backward_oos_boundary"]["2010_2023_v2_post_entry_outcomes_remain_unread"] is True

    text = SCANNER.read_text().lower()
    forbidden = [
        "measure_occurrence", "v2_m1_execution_measurement", "execution_outcomes",
        "net_expectancy", "profit_factor", "win_rate", "max_drawdown", "slippage",
        "target_first", "stop_first", "read_m1", "nas100_usd.1m"
    ]
    for token in forbidden:
        assert token not in text, token
    assert "entry_stop_target_defined\": false" in text
    assert "post_trigger_price_traversal_accessed\": false" in text
    assert "primary_swings" in text and "independent_swings" in text
    assert "primary_triggers" in text and "independent_triggers" in text
    print("V3-C Arguments trigger anti-outcome tests passed")


if __name__ == "__main__":
    main()
