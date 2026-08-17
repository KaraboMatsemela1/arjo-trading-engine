#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts/scan_v3c_backward_oos_triggers.py"


def main() -> None:
    text = SCANNER.read_text(encoding="utf-8").lower()
    forbidden = [
        "oanda_api_token",
        "oanda_account_id",
        "urlopen",
        "request(",
        "nas100_usd.1m",
        "measure_occurrence",
        "v2_m1_execution_measurement",
        "execution_outcomes",
        "net_expectancy",
        "profit_factor",
        "win_rate",
        "max_drawdown",
        "slippage",
        "target_first",
        "stop_first",
    ]
    for token in forbidden:
        assert token not in text, token

    required = [
        "m1_data_requested\": false",
        "post_trigger_price_traversal_accessed\": false",
        "performance_metrics_accessed\": false",
        "development_2024_2025_outcomes_accessed\": false",
        "v2_2010_2023_trade_outcomes_accessed\": false",
        "minimum_distinct_knowledge_times_required",
        "dual_path_exact_match",
        "rejection_low",
        "activation_known_at_utc",
    ]
    for token in required:
        assert token in text, token

    print("V3-C backward-OOS trigger-seal anti-leak tests passed")


if __name__ == "__main__":
    main()
