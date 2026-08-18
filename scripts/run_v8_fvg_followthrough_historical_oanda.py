#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import check_v8_fvg_followthrough_historical_lock as lock_check
import check_v8_fvg_followthrough_protocol as protocol_check
from v6_momentum_backtest_mechanics import evaluate
from v6_momentum_m1_oanda import M1Cache
from v7_candle_science_primitives import canon
from v8_fvg_followthrough_backtest_metrics import classify, metrics
from v8_fvg_followthrough_reconstruct import compare_reconstructions
from v8_fvg_followthrough_structure import acquire_structure

PROTOCOL = "79c0289293996f02faa6de1ecb5dcc6d6201a7b98bff1be842bab6cc707b547d"
TRIGGER = "bb42a146ed756f8a675a4d861c8c211951de29ccaddd3d642ff72cbf62d74747"
READINESS = "a13a33c588349c7ec11e33324956dbaf9810ba5fa8f88294f43194d33850b3ed"
STRUCTURE = "a61ef4aa9deb1ed3de36611a12c9afd83ca25aeb8e55cd63004fd2328a39b414"
LOCK = "ccf0dcbe4ef084c7fc9251423513f107fa8ada14d9a9303b0353ca91f99cdf4e"
FORWARD = "b72b6f8aaaf6c53c6f957917105feba4078cfd6e37c059c49b912cc4203503e8"
AUTH = Path("research/profitability/V8_FVG_FOLLOWTHROUGH_M1_EXECUTE_LOCK.json")


def require_authorization() -> dict:
    if not AUTH.exists():
        raise RuntimeError("V8 historical M1 authorization marker missing")
    marker = json.loads(AUTH.read_text())
    expected = {
        "status": "AUTHORIZED_RESEARCH_M1_READ_AFTER_PREFLIGHT",
        "issue": 290,
        "protocol_sha256": PROTOCOL,
        "trigger_set_sha256": TRIGGER,
        "trigger_count": 5482,
        "distinct_knowledge_timestamps": 5482,
        "trigger_readiness_sha256": READINESS,
        "structure_manifest_sha256": STRUCTURE,
        "historical_execution_lock_sha256": LOCK,
        "forward_confirmation_transport_sha256": FORWARD,
        "forward_confirmation_access_authorized": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    if marker != expected:
        raise RuntimeError("V8 historical M1 authorization boundary changed")
    return marker


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    output = Path(
        os.getenv(
            "V8_HIST_OUTPUT_DIR",
            "artifacts/v8_fvg_followthrough_historical",
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    cache_dir = output / "m1-cache"
    try:
        protocol_check.verify()
        lock_check.verify()
        authorization = require_authorization()
        structure = acquire_structure()
        triggers, comparison = compare_reconstructions(
            structure["h4"],
            structure["h1"],
        )
        trigger_sha = canon(triggers)
        distinct = len({row["knowledge_time_utc"] for row in triggers})
        if comparison["exact_match"] is not True:
            raise RuntimeError("V8 independent trigger reconstruction mismatch")
        if trigger_sha != TRIGGER or len(triggers) != 5482 or distinct != 5482:
            raise RuntimeError(
                "V8 sealed trigger set did not reproduce exactly "
                f"sha={trigger_sha} count={len(triggers)} distinct={distinct}"
            )
        if structure["manifest"]["manifest_sha256"] != STRUCTURE:
            raise RuntimeError("V8 historical structure manifest did not reproduce exactly")

        token = os.getenv("OANDA_API_TOKEN", "").strip()
        if not token:
            raise RuntimeError("OANDA_API_TOKEN missing")
        cache = M1Cache(cache_dir, token)
        base = evaluate(
            triggers,
            cache.get_bars,
            scenario="BASE",
            slip_points=Decimal("0.5"),
            financing_r_per_1440=Decimal("0.005"),
        )
        stress = evaluate(
            triggers,
            cache.get_bars,
            scenario="STRESS",
            slip_points=Decimal("1.0"),
            financing_r_per_1440=Decimal("0.01"),
        )
        base_metrics = metrics(base)
        stress_metrics = metrics(stress)
        classification = classify(base_metrics, stress_metrics)
        historical_pass = (
            classification == "V8_FVG_FOLLOWTHROUGH_HISTORICAL_EDGE_ESTABLISHED"
        )
        provenance = cache.provenance()
        if cache.first_response_accessed is not True:
            raise RuntimeError("V8 historical execution completed without first M1 response")

        write_jsonl(output / "base-trade-ledger.jsonl", base["ledger"])
        write_jsonl(output / "stress-trade-ledger.jsonl", stress["ledger"])
        write_json(output / "provider-provenance.json", provenance)
        result = {
            "schema_version": 1,
            "status": "V8_FVG_FOLLOWTHROUGH_HISTORICAL_PROFITABILITY_RESULT_READY",
            "candidate_id": "ARJO_V8_NQ_FVG_FOLLOWTHROUGH_H4_H1_SYMMETRIC",
            "issue": 290,
            "classification": classification,
            "historical_edge_established": historical_pass,
            "validated_profitable_edge": False,
            "forward_confirmation_authorized": historical_pass,
            "protocol_sha256": PROTOCOL,
            "trigger_set_sha256": TRIGGER,
            "trigger_count": len(triggers),
            "distinct_knowledge_timestamps": distinct,
            "trigger_readiness_sha256": READINESS,
            "structure_manifest_sha256": STRUCTURE,
            "historical_execution_lock_sha256": LOCK,
            "forward_confirmation_transport_sha256": FORWARD,
            "execution_authorization": authorization,
            "provider_provenance_sha256": provenance["provenance_sha256"],
            "base_metrics": base_metrics,
            "stress_metrics": stress_metrics,
            "base_ledger_sha256": base["ledger_sha256"],
            "stress_ledger_sha256": stress["ledger_sha256"],
            "first_m1_response_accessed": True,
            "parameter_changes_after_first_m1_response": False,
            "cost_changes_after_first_m1_response": False,
            "threshold_changes_after_first_m1_response": False,
            "target_stop_rule_changes_after_first_m1_response": False,
            "no_refit_performed": True,
            "forward_confirmation_outcomes_accessed": False,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        result["result_sha256"] = canon(result)
        write_json(output / "historical-result.json", result)
        print(
            json.dumps(
                {
                    "classification": classification,
                    "historical_edge_established": historical_pass,
                    "validated_profitable_edge": False,
                    "forward_confirmation_authorized": historical_pass,
                    "base_resolved": base_metrics["resolved_executed_trades"],
                    "base_expectancy_r": base_metrics["net_expectancy_r"],
                    "base_profit_factor": base_metrics["profit_factor"],
                    "base_bootstrap_ci": base_metrics[
                        "bootstrap_95pct_ci_net_expectancy_r"
                    ],
                    "positive_calendar_year_fraction": base_metrics[
                        "positive_calendar_year_fraction"
                    ],
                    "stress_expectancy_r": stress_metrics["net_expectancy_r"],
                    "stress_profit_factor": stress_metrics["profit_factor"],
                    "result_sha256": result["result_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(f"V8 historical profitability execution failed: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
