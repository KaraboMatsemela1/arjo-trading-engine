#!/usr/bin/env python3
"""Outcome-blind V3-C 4h Swing High -> 1h 2CR failure trigger coverage.

This file intentionally stops at the bullish activation close. It has no entry,
stop, target, post-trigger traversal, or P&L implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

CANDIDATE_SHA = "de51f2c721aaedd0f6587755ebcab31ac2b264188d3de1f5531ec7057fb53b7b"
START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)


class V3CError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise V3CError("naive timestamp")
    return dt.astimezone(UTC)


def num(value: object) -> Decimal:
    return Decimal(str(value))


def load_candidate(path: Path) -> dict:
    x = json.loads(path.read_text(encoding="utf-8"))
    recorded = x.pop("candidate_sha256", "")
    if recorded != CANDIDATE_SHA or canon(x) != CANDIDATE_SHA:
        raise V3CError("candidate SHA drift")
    if x.get("candidate_id") != "ARJO_ARGUMENTS_4H_SWING_1H_2CR_V3C":
        raise V3CError("unexpected candidate")
    if x["development_coverage"]["post_trigger_price_traversal_allowed"] is not False:
        raise V3CError("post-trigger boundary changed")
    if x["development_coverage"]["performance_metrics_allowed"] is not False:
        raise V3CError("performance boundary changed")
    if x["owner_operational_trigger"]["entry_fill"] != "UNRESOLVED_NOT_DEFINED_IN_THIS_CANDIDATE":
        raise V3CError("entry was added before trigger coverage")
    return x


def find_one(root: Path, name: str) -> Path:
    hits = list(root.rglob(name))
    if len(hits) != 1:
        raise V3CError(f"expected exactly one {name} under {root}, found {len(hits)}")
    return hits[0]


def load_rows(artifact_dirs: list[Path], minutes: int) -> list[dict]:
    rows: list[dict] = []
    for root in artifact_dirs:
        path = find_one(root, f"NAS100_USD.{minutes}m.jsonl")
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if int(row.get("minutes", 0)) != minutes:
                        raise V3CError(f"unexpected minutes in {path}")
                    ts = parse(row["ts_start_utc"])
                    if START <= ts < END:
                        rows.append(row)
    rows.sort(key=lambda r: r["ts_start_utc"])
    if not rows:
        raise V3CError(f"no {minutes}m rows")
    seen = set()
    for row in rows:
        ts = row["ts_start_utc"]
        if ts in seen:
            raise V3CError(f"duplicate {minutes}m timestamp {ts}")
        seen.add(ts)
    return rows


def primary_swings(rows4: list[dict]) -> list[dict]:
    out = []
    for i in range(1, len(rows4) - 1):
        left, middle, right = rows4[i - 1], rows4[i], rows4[i + 1]
        lt, mt, rt = parse(left["ts_start_utc"]), parse(middle["ts_start_utc"]), parse(right["ts_start_utc"])
        if mt - lt != timedelta(hours=4) or rt - mt != timedelta(hours=4):
            continue
        mh = num(middle["high"])
        if mh > num(left["high"]) and mh > num(right["high"]):
            out.append({
                "swing_id": f"H4-SH-{middle['ts_start_utc']}",
                "swing_ts_utc": middle["ts_start_utc"],
                "swing_high": str(mh),
                "confirmed_at_utc": (rt + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
            })
    return out


def primary_triggers(rows1: list[dict], swings: list[dict]) -> tuple[list[dict], dict]:
    triggers = []
    statuses = Counter()
    for swing in swings:
        confirmed = parse(swing["confirmed_at_utc"])
        level = num(swing["swing_high"])
        pair = None
        for i in range(len(rows1) - 1):
            a, b = rows1[i], rows1[i + 1]
            at, bt = parse(a["ts_start_utc"]), parse(b["ts_start_utc"])
            if at < confirmed or bt - at != timedelta(hours=1):
                continue
            ar = num(a["high"]) >= level and num(a["close"]) < level
            br = num(b["high"]) >= level and num(b["close"]) < level
            if ar or br:
                rejection = b if br else a
                pair = (i, a, b, rejection)
                break
        if pair is None:
            statuses["NO_2CR_REJECTION_PAIR"] += 1
            continue
        idx, a, b, rejection = pair
        rejection_high = num(rejection["high"])
        activation = None
        for row in rows1[idx + 2 :]:
            if num(row["close"]) > rejection_high:
                activation = row
                break
        if activation is None:
            statuses["NO_REJECTION_HIGH_RUN"] += 1
            continue
        statuses["TRIGGERED"] += 1
        triggers.append({
            "trigger_id": f"V3C-{swing['swing_id']}",
            "swing_id": swing["swing_id"],
            "swing_ts_utc": swing["swing_ts_utc"],
            "swing_high": swing["swing_high"],
            "swing_confirmed_at_utc": swing["confirmed_at_utc"],
            "pair_first_ts_utc": a["ts_start_utc"],
            "pair_second_ts_utc": b["ts_start_utc"],
            "rejection_candle_ts_utc": rejection["ts_start_utc"],
            "rejection_high": str(rejection_high),
            "activation_bar_ts_utc": activation["ts_start_utc"],
            "activation_close": activation["close"],
        })
    triggers.sort(key=lambda x: (x["activation_bar_ts_utc"], x["swing_id"]))
    return triggers, dict(sorted(statuses.items()))


def independent_swings(rows4: list[dict]) -> list[dict]:
    indexed = {parse(r["ts_start_utc"]): r for r in rows4}
    out = []
    for ts in sorted(indexed):
        left_ts, right_ts = ts - timedelta(hours=4), ts + timedelta(hours=4)
        if left_ts not in indexed or right_ts not in indexed:
            continue
        middle, left, right = indexed[ts], indexed[left_ts], indexed[right_ts]
        mh = num(middle["high"])
        if mh <= num(left["high"]) or mh <= num(right["high"]):
            continue
        out.append({
            "swing_id": f"H4-SH-{middle['ts_start_utc']}",
            "swing_ts_utc": middle["ts_start_utc"],
            "swing_high": str(mh),
            "confirmed_at_utc": (right_ts + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
        })
    return out


def independent_triggers(rows1: list[dict], swings: list[dict]) -> tuple[list[dict], dict]:
    # Precompute every contiguous pair; then select the first qualifying pair per swing.
    pairs = []
    for a, b in zip(rows1, rows1[1:]):
        at, bt = parse(a["ts_start_utc"]), parse(b["ts_start_utc"])
        if bt - at == timedelta(hours=1):
            pairs.append((at, a, b))
    triggers = []
    statuses = Counter()
    for swing in swings:
        confirmed = parse(swing["confirmed_at_utc"])
        level = num(swing["swing_high"])
        chosen = None
        for at, a, b in pairs:
            if at < confirmed:
                continue
            reject_a = num(a["high"]) >= level and num(a["close"]) < level
            reject_b = num(b["high"]) >= level and num(b["close"]) < level
            if not (reject_a or reject_b):
                continue
            chosen = (a, b, b if reject_b else a)
            break
        if chosen is None:
            statuses["NO_2CR_REJECTION_PAIR"] += 1
            continue
        a, b, rejection = chosen
        pair_end = parse(b["ts_start_utc"]) + timedelta(hours=1)
        rejection_high = num(rejection["high"])
        activation = next((r for r in rows1 if parse(r["ts_start_utc"]) >= pair_end and num(r["close"]) > rejection_high), None)
        if activation is None:
            statuses["NO_REJECTION_HIGH_RUN"] += 1
            continue
        statuses["TRIGGERED"] += 1
        triggers.append({
            "trigger_id": f"V3C-{swing['swing_id']}",
            "swing_id": swing["swing_id"],
            "swing_ts_utc": swing["swing_ts_utc"],
            "swing_high": swing["swing_high"],
            "swing_confirmed_at_utc": swing["confirmed_at_utc"],
            "pair_first_ts_utc": a["ts_start_utc"],
            "pair_second_ts_utc": b["ts_start_utc"],
            "rejection_candle_ts_utc": rejection["ts_start_utc"],
            "rejection_high": str(rejection_high),
            "activation_bar_ts_utc": activation["ts_start_utc"],
            "activation_close": activation["close"],
        })
    triggers.sort(key=lambda x: (x["activation_bar_ts_utc"], x["swing_id"]))
    return triggers, dict(sorted(statuses.items()))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--artifact-dir", action="append", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    try:
        candidate = load_candidate(Path(args.candidate))
        roots = [Path(x) for x in args.artifact_dir]
        rows1 = load_rows(roots, 60)
        rows4 = load_rows(roots, 240)
        sw_a, sw_b = primary_swings(rows4), independent_swings(rows4)
        if sw_a != sw_b:
            raise V3CError("primary/independent swing reconstruction mismatch")
        tr_a, st_a = primary_triggers(rows1, sw_a)
        tr_b, st_b = independent_triggers(rows1, sw_b)
        if tr_a != tr_b or st_a != st_b:
            raise V3CError("primary/independent trigger reconstruction mismatch")
        dates = defaultdict(int)
        for t in tr_a:
            dates[parse(t["activation_bar_ts_utc"]).date().isoformat()] += 1
        floor = int(candidate["development_coverage"]["coverage_floor"])
        result = {
            "schema_version": 1,
            "status": "V3_ARGUMENTS_TRIGGER_COVERAGE_READY",
            "candidate_sha256": CANDIDATE_SHA,
            "development_window": ["2024-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
            "h4_swing_high_count": len(sw_a),
            "trigger_status_counts": st_a,
            "trigger_count": len(tr_a),
            "unique_activation_dates": len(dates),
            "max_triggers_same_date": max(dates.values(), default=0),
            "coverage_floor": floor,
            "coverage_feasible": len(tr_a) >= floor,
            "trigger_set_sha256": canon(tr_a),
            "triggers": tr_a,
            "dual_path_exact_match": True,
            "post_trigger_price_traversal_accessed": False,
            "entry_stop_target_defined": False,
            "performance_metrics_accessed": False,
            "backward_oos_outcomes_accessed": False,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        result["report_sha256"] = canon(result)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"V3-C trigger scan failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": result["status"],
        "swings": result["h4_swing_high_count"],
        "triggers": result["trigger_count"],
        "unique_dates": result["unique_activation_dates"],
        "coverage_feasible": result["coverage_feasible"],
        "outcomes_accessed": False,
        "report_sha256": result["report_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
