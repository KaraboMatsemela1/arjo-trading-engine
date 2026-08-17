#!/usr/bin/env python3
"""Evaluate preregistered V3-A coverage on 2024-2025 development data only.

V3-A differs from OWNER_OPERATIONAL_CONTEXT_V1 in exactly one place: an active
4h FVG and a confirmed 1h FVA must both exist at 09:30 NY, but their zones need
not geometrically overlap. Post-entry outcome bars are never read.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import build_owner_operational_context_occurrences as v2
from build_owner_operational_fvg_anchors import FvgError, build as build_fvg_anchors, canonical_sha256, decimal, parse_utc

NY = ZoneInfo("America/New_York")
CANDIDATE_ID = "ARJO_DERIVED_OWNER_OPERATIONAL_V3_COVERAGE_A"
CANDIDATE_SHA = "21907522648f957ad620a0d0d9e3f1c3f9de4f222e92866b1db37bb91271c305"
PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"


class V3CoverageError(RuntimeError):
    pass


def load_candidate(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = data.pop("candidate_sha256", "")
    if recorded != CANDIDATE_SHA or canonical_sha256(data) != CANDIDATE_SHA:
        raise V3CoverageError("V3 candidate SHA drift")
    if data.get("candidate_id") != CANDIDATE_ID:
        raise V3CoverageError("unexpected V3 candidate")
    if data.get("parent_profile_sha256") != PROFILE_SHA:
        raise V3CoverageError("parent V2 profile changed")
    change = data.get("change_set", {})
    if change.get("changed_field") != "fva.required_relationship_to_4h_fvg":
        raise V3CoverageError("V3 changed more than preregistered field")
    if change.get("all_other_owner_operational_predicates") != "UNCHANGED":
        raise V3CoverageError("V3 predicate boundary changed")
    if data.get("development_only_evaluation", {}).get("post_entry_outcomes_allowed") is not False:
        raise V3CoverageError("development outcome boundary changed")
    return data


def session_times(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC),
        datetime.combine(day, time(11, 0), tzinfo=NY).astimezone(UTC),
    )


def build(candidate_path: Path, artifact_dirs: list[Path]) -> dict:
    candidate = load_candidate(candidate_path)
    _, context_sha = v2.load_context_convention(Path("research/calibration/owner_operational_context_v1.json"))
    rows15, rows60, rows240, refs = v2.load_annual_bars(artifact_dirs)
    try:
        fvg_state = build_fvg_anchors(Path("research/calibration/owner_operational_fvg_v1.json"), artifact_dirs)
    except FvgError as exc:
        raise V3CoverageError(f"FVG dependency failed: {exc}") from exc
    if fvg_state.get("session_count") != 515:
        raise V3CoverageError("development session universe changed")

    highs, lows = v2.confirmed_pivots(rows60)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows15:
        by_day[parse_utc(row["ts_start_utc"]).astimezone(NY).date().isoformat()].append(row)

    ledger: list[dict] = []
    semantic_occurrences: list[dict] = []
    observability: list[dict] = []

    for fvg_row in fvg_state["sessions"]:
        day_str = str(fvg_row["session_date_ny"])
        day = date.fromisoformat(day_str)
        woo_start, woo_end = session_times(day)
        selected_fvg = fvg_row.get("selected_fvg")
        entry = {"session_date_ny": day_str, "status": None, "selected_fvg_gap_id": selected_fvg.get("gap_id") if selected_fvg else None}
        if selected_fvg is None:
            entry["status"] = "NO_FVG"; ledger.append(entry); continue

        eh = [x for x in highs if parse_utc(x["confirmed_at_utc"]) <= woo_start]
        el = [x for x in lows if parse_utc(x["confirmed_at_utc"]) <= woo_start]
        if not eh or not el:
            entry["status"] = "NO_FVA_PIVOT"; ledger.append(entry); continue
        ph = max(eh, key=lambda x: (x["confirmed_at_utc"], x["pivot_ts_utc"]))
        pl = max(el, key=lambda x: (x["confirmed_at_utc"], x["pivot_ts_utc"]))
        fva_low = min(decimal(ph["price"], "fva.high"), decimal(pl["price"], "fva.low"))
        fva_high = max(decimal(ph["price"], "fva.high"), decimal(pl["price"], "fva.low"))
        entry["fva_zone_low"], entry["fva_zone_high"] = str(fva_low), str(fva_high)
        entry["fvg_fva_overlap_required"] = False

        bars = sorted([r for r in by_day[day_str] if woo_start <= parse_utc(r["ts_start_utc"]) < woo_end], key=lambda r:r["ts_start_utc"])
        if len(bars) != 6:
            raise V3CoverageError(f"{day_str} lost six-bar WoO")

        rejection = None
        for idx in range(len(bars)-1):
            a,b=bars[idx:idx+2]
            if parse_utc(b["ts_start_utc"])-parse_utc(a["ts_start_utc"]) != timedelta(minutes=15): continue
            ar = decimal(a["high"],"2cr.high") >= fva_high and decimal(a["close"],"2cr.close") < fva_high
            br = decimal(b["high"],"2cr.high") >= fva_high and decimal(b["close"],"2cr.close") < fva_high
            if ar or br: rejection = a if ar else b; break
        if rejection is None:
            entry["status"]="NO_2CR_REJECTION"; ledger.append(entry); continue
        rejection_high=decimal(rejection["high"],"rejection.high"); rejection_ts=parse_utc(rejection["ts_start_utc"])
        entry["rejection_high"]=str(rejection_high); entry["rejection_ts_utc"]=rejection["ts_start_utc"]

        activation=None; activation_idx=None
        for idx,row in enumerate(bars):
            if parse_utc(row["ts_start_utc"]) <= rejection_ts: continue
            if decimal(row["close"],"activation.close") > rejection_high:
                activation=row; activation_idx=idx; break
        if activation is None or activation_idx is None:
            entry["status"]="NO_RUN"; ledger.append(entry); continue
        entry["activation_ts_utc"]=activation["ts_start_utc"]

        stings=[]
        for idx,row in enumerate(bars):
            if idx <= activation_idx: continue
            if decimal(row["low"],"sting.low") <= fva_high and decimal(row["high"],"sting.high") >= fva_low and decimal(row["close"],"sting.close") > fva_low:
                stings.append((idx,row))
            if len(stings)==2: break
        if len(stings)!=2:
            entry["status"]="NO_2_STING"; ledger.append(entry); continue
        _, first=stings[0]; second_idx, second=stings[1]
        touch=fva_high; close=decimal(second["close"],"second.close")
        leg_low=min(decimal(r["low"],"leg.low") for r in bars[activation_idx:second_idx+1])

        prior4=[r for r in rows240 if parse_utc(r["ts_start_utc"]) + timedelta(hours=4) <= woo_start]
        if not prior4:
            entry["status"]="NO_TARGET_ABOVE_ENTRY"; ledger.append(entry); continue
        target=max(decimal(r["high"],"target.high") for r in prior4)
        if target <= touch or target <= close:
            entry["status"]="NO_TARGET_ABOVE_ENTRY"; ledger.append(entry); continue
        if leg_low >= touch or leg_low >= close:
            entry["status"]="INVALID_STOP_ORDERING"; ledger.append(entry); continue

        oid=f"V3-CAL-{day_str}"
        semantic_occurrences.append({
            "occurrence_id":oid,"session_date_ny":day_str,"selected_fvg_gap_id":selected_fvg["gap_id"],
            "fva_zone_low":str(fva_low),"fva_zone_high":str(fva_high),"rejection_high":str(rejection_high),
            "activation_ts_utc":activation["ts_start_utc"],"first_sting_ts_utc":first["ts_start_utc"],
            "second_sting_ts_utc":second["ts_start_utc"],"touch_price":str(touch),"second_sting_low":second["low"],
            "second_sting_high":second["high"],"order_flow_leg_low":str(leg_low),"target_price":str(target)
        })
        obs = "EXECUTABLE_ENTRY" if decimal(second["low"],"second.low") <= touch <= decimal(second["high"],"second.high") else "NO_EXECUTABLE_ENTRY"
        observability.append({"occurrence_id":oid,"session_date_ny":day_str,"status":obs})
        entry["status"]="QUALIFIED"; entry["occurrence_id"]=oid; ledger.append(entry)

    ledger.sort(key=lambda x:x["session_date_ny"]); semantic_occurrences.sort(key=lambda x:x["session_date_ny"]); observability.sort(key=lambda x:x["session_date_ny"])
    executable=[x for x in observability if x["status"]=="EXECUTABLE_ENTRY"]
    floor=int(candidate["development_only_evaluation"]["coverage_feasibility_floor_per_2y"])
    result={
        "schema_version":1,"status":"V3_DEVELOPMENT_COVERAGE_DIAGNOSTIC_COMPLETE","candidate_id":CANDIDATE_ID,
        "candidate_sha256":CANDIDATE_SHA,"parent_profile_sha256":PROFILE_SHA,"context_v2_sha256":context_sha,
        "development_window":["2024-01-01T00:00:00Z","2026-01-01T00:00:00Z"],"session_count":len(ledger),
        "v2_baseline_qualified_occurrences":1,"v2_baseline_no_fva_overlap":413,
        "status_counts":dict(sorted(Counter(x["status"] for x in ledger).items())),
        "qualified_occurrence_count":len(semantic_occurrences),"executable_occurrence_count":len(executable),
        "coverage_feasibility_floor":floor,"coverage_feasible":len(executable)>=floor,
        "qualification_rows_sha256":canonical_sha256(ledger),"semantic_occurrences_sha256":canonical_sha256(semantic_occurrences),
        "observability_rows_sha256":canonical_sha256(observability),"semantic_occurrences":semantic_occurrences,
        "post_entry_outcomes_accessed":False,"performance_metrics_accessed":False,"backward_oos_outcomes_accessed":False,
        "candidate_selection_uses_performance":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False,
        "calibration_data_refs":refs,
    }
    result["report_sha256"]=canonical_sha256(result)
    return result


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--candidate",required=True); p.add_argument("--artifact-dir",action="append",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    try:
        r=build(Path(a.candidate),[Path(x) for x in a.artifact_dir]); Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    except Exception as exc:
        print(f"V3 coverage diagnostic failed: {exc}",file=sys.stderr); return 1
    print(json.dumps({"status":r["status"],"qualified":r["qualified_occurrence_count"],"executable":r["executable_occurrence_count"],"coverage_feasible":r["coverage_feasible"],"status_counts":r["status_counts"],"outcomes_accessed":False,"report_sha256":r["report_sha256"]},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
