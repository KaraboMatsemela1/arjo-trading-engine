#!/usr/bin/env python3
"""Seal V3-C Arguments triggers on 2010-2023 MID H1/H4 structure only.

This stage is deliberately incapable of reading M1 execution data or traversing
post-trigger outcomes. It reuses the frozen dual-path trigger constructors and
enriches each agreed trigger only with information known by the activation H1
bar close: rejection-candle low/high and causal knowledge timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import scan_v3c_arguments_trigger_coverage as v3c

CANDIDATE_SHA = "de51f2c721aaedd0f6587755ebcab31ac2b264188d3de1f5531ec7057fb53b7b"
PROTOCOL_SHA = "0b3a6a5e217e7e4c279f7384c14579e97bf6821bc59deefac3086e7b4ce4ba7a"
EXPECTED_STRUCTURE_MANIFEST_SHA = "bacad0d2357655c2fe6faf8b3f3488df2baafa5172212a5b1d307bf3ae1075ed"
END = datetime(2024, 1, 1, tzinfo=UTC)
MIN_DISTINCT_KNOWLEDGE_TIMES = 100


class TriggerSealError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise TriggerSealError("naive timestamp")
    return dt.astimezone(UTC)


def find_one(root: Path, name: str) -> Path:
    hits = list(root.rglob(name))
    if len(hits) != 1:
        raise TriggerSealError(f"expected exactly one {name}, found {len(hits)}")
    return hits[0]


def verify_structure(root: Path) -> dict:
    path = find_one(root, "NAS100_USD.manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("manifest_sha256") != EXPECTED_STRUCTURE_MANIFEST_SHA:
        raise TriggerSealError("unexpected backward-OOS structure manifest SHA")
    unsigned = dict(manifest)
    recorded = unsigned.pop("manifest_sha256", "")
    if not recorded or canon(unsigned) != recorded:
        raise TriggerSealError("structure manifest integrity failure")
    expected = {
        "status": "PROFITABILITY_BACKWARD_OOS_STRUCTURE_READY",
        "provider": "OANDA_V20",
        "instrument": "NAS100_USD",
        "semantic_price_component": "MID",
        "source_granularity": "M15",
        "requested_end_exclusive": "2024-01-01T00:00:00Z",
        "post_entry_outcomes_evaluated": False,
        "m1_outcome_data_requested": False,
        "mutation_endpoints_used": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise TriggerSealError(f"structure boundary changed: {key}")
    return manifest


def enrich(triggers: list[dict], rows1: list[dict]) -> list[dict]:
    h1 = {row["ts_start_utc"]: row for row in rows1}
    out = []
    for trigger in triggers:
        rejection = h1.get(trigger["rejection_candle_ts_utc"])
        activation = h1.get(trigger["activation_bar_ts_utc"])
        if rejection is None or activation is None:
            raise TriggerSealError(f"trigger H1 row missing: {trigger['trigger_id']}")
        activation_start = parse(trigger["activation_bar_ts_utc"])
        knowledge = activation_start + timedelta(hours=1)
        if knowledge > END:
            raise TriggerSealError("activation knowledge crosses OOS end")
        row = dict(trigger)
        row["rejection_low"] = str(rejection["low"])
        row["rejection_high"] = str(trigger["rejection_high"])
        row["activation_known_at_utc"] = knowledge.isoformat().replace("+00:00", "Z")
        row["activation_h1_close"] = str(activation["close"])
        out.append(row)
    out.sort(key=lambda x: (x["activation_known_at_utc"], x["trigger_id"]))
    return out


def build(root: Path, candidate_path: Path, protocol_path: Path) -> dict:
    manifest = verify_structure(root)

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_recorded = candidate.pop("candidate_sha256", "")
    if candidate_recorded != CANDIDATE_SHA or canon(candidate) != CANDIDATE_SHA:
        raise TriggerSealError("candidate SHA drift")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_recorded = protocol.pop("protocol_sha256", "")
    if protocol_recorded != PROTOCOL_SHA or canon(protocol) != PROTOCOL_SHA:
        raise TriggerSealError("execution protocol SHA drift")
    if protocol["market_data"]["request_m1_only_after_backward_oos_trigger_set_is_sealed"] is not True:
        raise TriggerSealError("M1 stage boundary changed")
    if protocol["market_data"]["development_2024_2025_outcomes_must_remain_unread"] is not True:
        raise TriggerSealError("development outcome boundary changed")

    start = parse(manifest["provider_first_complete_bar"])
    v3c.START = start
    v3c.END = END
    rows1 = v3c.load_rows([root], 60)
    rows4 = v3c.load_rows([root], 240)

    swings_a = v3c.primary_swings(rows4)
    swings_b = v3c.independent_swings(rows4)
    if swings_a != swings_b:
        raise TriggerSealError("primary/independent swing mismatch")

    triggers_a, status_a = v3c.primary_triggers(rows1, swings_a)
    triggers_b, status_b = v3c.independent_triggers(rows1, swings_b)
    if triggers_a != triggers_b or status_a != status_b:
        raise TriggerSealError("primary/independent trigger mismatch")

    sealed = enrich(triggers_a, rows1)
    knowledge_times = sorted({x["activation_known_at_utc"] for x in sealed})
    by_year = dict(sorted(Counter(parse(x["activation_known_at_utc"]).year for x in sealed).items()))
    by_year = {str(k): v for k, v in by_year.items()}
    sufficient = len(knowledge_times) >= MIN_DISTINCT_KNOWLEDGE_TIMES

    result = {
        "schema_version": 1,
        "status": "V3_ARGUMENTS_BACKWARD_OOS_TRIGGERS_READY",
        "classification": "TRIGGER_SAMPLE_NECESSARY_CONDITION_MET" if sufficient else "INSUFFICIENT_TRIGGER_SAMPLE_EDGE_NOT_ESTABLISHED",
        "candidate_sha256": CANDIDATE_SHA,
        "execution_protocol_sha256": PROTOCOL_SHA,
        "structure_manifest_sha256": manifest["manifest_sha256"],
        "provider_first_complete_bar": manifest["provider_first_complete_bar"],
        "end_exclusive": "2024-01-01T00:00:00Z",
        "h4_swing_high_count": len(swings_a),
        "trigger_status_counts": status_a,
        "trigger_count": len(sealed),
        "distinct_activation_knowledge_times": len(knowledge_times),
        "minimum_distinct_knowledge_times_required": MIN_DISTINCT_KNOWLEDGE_TIMES,
        "sample_necessary_condition_met": sufficient,
        "triggers_by_activation_year": by_year,
        "trigger_set_sha256": canon(sealed),
        "sealed_triggers": sealed,
        "dual_path_exact_match": True,
        "m1_data_requested": False,
        "post_trigger_price_traversal_accessed": False,
        "performance_metrics_accessed": False,
        "development_2024_2025_outcomes_accessed": False,
        "v2_2010_2023_trade_outcomes_accessed": False,
        "no_refit_performed": True,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    result["report_sha256"] = canon(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(Path(args.artifact_dir), Path(args.candidate), Path(args.protocol))
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"V3-C backward-OOS trigger seal failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": result["status"],
        "classification": result["classification"],
        "swings": result["h4_swing_high_count"],
        "triggers": result["trigger_count"],
        "distinct_knowledge_times": result["distinct_activation_knowledge_times"],
        "sample_necessary_condition_met": result["sample_necessary_condition_met"],
        "trigger_set_sha256": result["trigger_set_sha256"],
        "outcomes_accessed": False,
        "report_sha256": result["report_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
