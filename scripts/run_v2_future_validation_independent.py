#!/usr/bin/env python3
"""Independent standard-library V2 future-validation evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import run_protected_validation_independent as base
from check_v2_future_validation_access_v2 import authorize

SCORED_START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2027, 3, 1, tzinfo=UTC)
PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
PROTOCOL_SHA = "193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38"
POLICY_SHA = "6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6"
CONTRACT_SHA = "edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca"


class IndependentFutureError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embedded(path: Path, field: str, expected: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")); unsigned = dict(data); recorded = str(unsigned.pop(field, ""))
    if recorded != expected or canon(unsigned) != expected:
        raise IndependentFutureError(f"{path} frozen SHA mismatch")
    return data


def verify_inputs(data_dir: Path, profile_path: Path) -> dict:
    profile = embedded(profile_path, "profile_sha256", PROFILE_SHA)
    if profile.get("profile_id") != "ARJO_DERIVED_OWNER_OPERATIONAL_V2" or profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise IndependentFutureError("V2 profile boundary changed")
    manifest_path = data_dir / "NAS100_USD.manifest.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    unsigned = dict(manifest); recorded = str(unsigned.pop("manifest_sha256", ""))
    if not recorded or canon(unsigned) != recorded:
        raise IndependentFutureError("future manifest SHA mismatch")
    expected = {
        "status":"V2_FUTURE_VALIDATION_DATA_READY", "validation_protocol_sha256":PROTOCOL_SHA, "measurement_policy_sha256":POLICY_SHA,
        "request_contract_sha256":CONTRACT_SHA, "provider":"OANDA_V20", "venue":"OANDA_FXTRADE", "environment":"practice",
        "instrument":"NAS100_USD", "instrument_identity":"OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED", "price_component":"MID", "source_granularity":"M1",
        "requested_start":"2026-09-01T00:00:00Z", "bootstrap_end_exclusive":"2026-10-01T00:00:00Z", "scored_start":"2026-10-01T00:00:00Z",
        "requested_end_exclusive":"2027-03-01T00:00:00Z", "full_window_single_shot":True, "state_at_start":"EMPTY",
        "pre_start_market_data_accessed":False, "v1_holdout_reused":False, "future_validation_data_accessed":True, "mutation_endpoints_used":False,
    }
    for key,value in expected.items():
        if manifest.get(key) != value: raise IndependentFutureError(f"future manifest boundary changed: {key}")
    if manifest.get("m1_sha256") != file_sha(data_dir / "NAS100_USD.M1.jsonl"): raise IndependentFutureError("M1 SHA mismatch")
    for minutes in (15,60,240):
        if manifest.get("derived",{}).get(str(minutes),{}).get("sha256") != file_sha(data_dir / f"NAS100_USD.{minutes}m.jsonl"):
            raise IndependentFutureError(f"derived {minutes}m SHA mismatch")
    return manifest


def load_m1(path: Path) -> list[dict]:
    rows=[]
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row=json.loads(line); rows.append({"ts":base.parse(row["ts_start_utc"]),"low":base.num(row["low"],"m1.low"),"high":base.num(row["high"],"m1.high")})
    rows.sort(key=lambda r:r["ts"]); return rows


def measure(occ: dict, status: str, rows: list[dict]) -> dict:
    oid=occ["occurrence_id"]
    if status == "NO_EXECUTABLE_ENTRY": return {"occurrence_id":oid,"observability_status":status,"measurement_status":"NO_M1_MEASUREMENT_NO_EXECUTABLE_ENTRY","execution_outcome":None}
    start=base.parse(occ["second_sting_ts_utc"]); interval_end=start+timedelta(minutes=15)
    touch=base.num(occ["touch_price"],"touch"); stop=base.num(occ["order_flow_leg_low"],"stop"); target=base.num(occ["target_price"],"target")
    interval=[r for r in rows if start <= r["ts"] < interval_end]
    expected={start+timedelta(minutes=i) for i in range(15)}
    if len(interval)!=15 or {r["ts"] for r in interval}!=expected:
        return {"occurrence_id":oid,"observability_status":status,"measurement_status":"VALIDATION_INTEGRITY_FAILURE","integrity_failure":"M1_ENTRY_INTERVAL_INCOMPLETE","execution_outcome":None}
    entry=next((r for r in interval if r["low"] <= touch <= r["high"]),None)
    if entry is None:
        return {"occurrence_id":oid,"observability_status":status,"measurement_status":"VALIDATION_INTEGRITY_FAILURE","integrity_failure":"M1_TOUCH_NOT_OBSERVED","execution_outcome":None}
    result={"occurrence_id":oid,"observability_status":status,"measurement_status":"M1_ENTRY_OBSERVED","entry_ts":entry["ts"].isoformat().replace("+00:00","Z"),"entry_price":str(touch),"stop_price":str(stop),"target_price":str(target)}
    if entry["low"] <= stop or entry["high"] >= target:
        return {**result,"execution_outcome":"AMBIGUOUS_INTRABAR_ORDER","event_ts":entry["ts"].isoformat().replace("+00:00","Z"),"ambiguity":"ENTRY_MINUTE_CONTAINS_STOP_OR_TARGET"}
    for row in rows:
        if not entry["ts"] < row["ts"] < END: continue
        hit_stop=row["low"] <= stop; hit_target=row["high"] >= target
        if not hit_stop and not hit_target: continue
        outcome="AMBIGUOUS_INTRABAR_ORDER" if hit_stop and hit_target else "STOP_FIRST" if hit_stop else "TARGET_FIRST"
        return {**result,"execution_outcome":outcome,"event_ts":row["ts"].isoformat().replace("+00:00","Z")}
    return {**result,"execution_outcome":"UNRESOLVED_WINDOW_END"}


def metrics(session_count:int, qualified_count:int, obs:list[dict], outcomes:list[dict])->dict:
    executable=sum(r["status"]=="EXECUTABLE_ENTRY" for r in obs); no_exec=sum(r["status"]=="NO_EXECUTABLE_ENTRY" for r in obs)
    counts=dict(sorted(Counter(r["execution_outcome"] for r in outcomes).items())); realized=[]
    for r in outcomes:
        if r["execution_outcome"]=="STOP_FIRST": realized.append(-1.0)
        elif r["execution_outcome"]=="TARGET_FIRST":
            entry,stop,target=float(r["entry_price"]),float(r["stop_price"]),float(r["target_price"]); realized.append((target-entry)/(entry-stop))
    n=len(realized); wins=counts.get("TARGET_FIRST",0); prop=wins/n if n else None; interval=None
    if n:
        z=1.959963984540054; denom=1+z*z/n; center=(prop+z*z/(2*n))/denom; half=z*math.sqrt((prop*(1-prop)+z*z/(4*n))/n)/denom; interval=[max(0.0,center-half),min(1.0,center+half)]
    return {"complete_session_count":session_count,"qualified_occurrence_count":qualified_count,"occurrence_rate_per_complete_session":qualified_count/session_count if session_count else 0.0,"executable_entry_count":executable,"no_executable_entry_count":no_exec,"executable_rate_per_qualified_occurrence":executable/qualified_count if qualified_count else None,"outcome_counts_for_executable_entries":counts,"resolved_executable_occurrence_count":n,"realized_r":realized,"mean_realized_r_when_resolved":sum(realized)/n if n else None,"cumulative_realized_r_when_resolved":sum(realized) if n else None,"target_first_proportion_among_resolved":prop,"target_first_wilson_interval_95":interval,"inferential_resolved_executable_occurrence_threshold":30}


def classify(q:int,m:dict,failures:list[dict])->str:
    if failures:return "VALIDATION_INTEGRITY_FAILURE"
    if q==0:return "NO_QUALIFYING_OCCURRENCES"
    if m["executable_entry_count"]==0:return "NO_EXECUTABLE_ENTRIES"
    if m["resolved_executable_occurrence_count"]<30:return "INSUFFICIENT_SAMPLE"
    return "SUFFICIENT_SAMPLE_POSITIVE" if float(m["mean_realized_r_when_resolved"])>0 else "SUFFICIENT_SAMPLE_NONPOSITIVE"


def evaluate_core(*,rows15:list[dict],rows60:list[dict],rows240:list[dict],m1_rows:list[dict])->dict:
    base.HSTART=SCORED_START; base.HEND=END
    sessions=base.holdout_sessions(rows15); formations=base.detect_fvgs(rows240); fvg_rows=base.fvg_sessions(rows15,formations,sessions)
    ledger,occurrences,status_counts=base.qualify(rows15,rows60,rows240,fvg_rows)
    obs=[]; outcomes=[]; failures=[]; executable_ids=[]
    for occ in occurrences:
        touch=base.num(occ["touch_price"],"touch"); low=base.num(occ["second_sting_bar_low"],"low"); high=base.num(occ["second_sting_bar_high"],"high")
        status="EXECUTABLE_ENTRY" if low <= touch <= high else "NO_EXECUTABLE_ENTRY"
        obs.append({"occurrence_id":occ["occurrence_id"],"status":status,"second_sting_ts_utc":occ["second_sting_ts_utc"],"touch_price":occ["touch_price"],"bar_low":occ["second_sting_bar_low"],"bar_high":occ["second_sting_bar_high"]})
        measured=measure(occ,status,m1_rows)
        if measured.get("measurement_status")=="VALIDATION_INTEGRITY_FAILURE": failures.append({"occurrence_id":occ["occurrence_id"],"kind":measured["integrity_failure"]})
        elif status=="EXECUTABLE_ENTRY":
            executable_ids.append(occ["occurrence_id"])
            if measured.get("execution_outcome") is not None: outcomes.append(measured)
    obs.sort(key=lambda r:r["occurrence_id"]); outcomes.sort(key=lambda r:r["occurrence_id"])
    m=metrics(len(sessions),len(occurrences),obs,outcomes)
    return {"complete_session_count":len(sessions),"detected_fvg_formation_count":len(formations),"selected_fvg_session_count":sum(r["selected_fvg"] is not None for r in fvg_rows),"qualification_status_counts":status_counts,"qualified_occurrence_ids":[r["occurrence_id"] for r in occurrences],"qualification_rows_sha256":canon(ledger),"semantic_occurrence_set_sha256":canon(occurrences),"observability_rows":obs,"observability_rows_sha256":canon(obs),"observability_status_counts":dict(sorted(Counter(r["status"] for r in obs).items())),"executable_occurrence_ids":sorted(executable_ids),"execution_outcomes":outcomes,"execution_outcomes_sha256":canon(outcomes),"integrity_failures":failures,"metrics":m,"validation_classification":classify(len(occurrences),m,failures),"future_validation_boundary_ok":True}


def build(data_dir:Path,profile_path:Path)->dict:
    manifest=verify_inputs(data_dir,profile_path); rows15=base.read_rows(data_dir/"NAS100_USD.15m.jsonl",15); rows60=base.read_rows(data_dir/"NAS100_USD.60m.jsonl",60); rows240=base.read_rows(data_dir/"NAS100_USD.240m.jsonl",240)
    result=evaluate_core(rows15=rows15,rows60=rows60,rows240=rows240,m1_rows=load_m1(data_dir/"NAS100_USD.M1.jsonl"))
    report={"schema_version":1,"path_id":"INDEPENDENT_V2_STANDARD_LIBRARY_PATH","status":"V2_FUTURE_VALIDATION_PATH_COMPLETE","profile_sha256":PROFILE_SHA,"protocol_sha256":PROTOCOL_SHA,"measurement_policy_sha256":POLICY_SHA,"data_manifest_sha256":manifest["manifest_sha256"],**result,"holdout_2026h1_accessed":False,"pre_start_market_data_accessed":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}; report["report_sha256"]=canon(report); return report


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--authorization",required=True); p.add_argument("--data-dir",required=True); p.add_argument("--output",required=True); p.add_argument("--profile",default="docs/spec/ARJO_DERIVED_OWNER_OPERATIONAL_V2.json"); args=p.parse_args()
    try:
        authorize(gate="evaluation",now=datetime.now(UTC),authorization_path=Path(args.authorization),protocol_path=Path("research/v2/future_validation_protocol_v2.json"),policy_path=Path("research/v2/v2_m1_touch_sequencing_v1.json"),readiness_path=Path("research/v2/v2_m1_measurement_readiness.json"),contract_path=Path("research/v2/nas100_oanda_future_validation_request_contract.json")); report=build(Path(args.data_dir),Path(args.profile)); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except Exception as exc: print(f"independent V2 future validation failed: {exc}",file=sys.stderr); return 1
    print(json.dumps({"path_id":report["path_id"],"classification":report["validation_classification"],"report_sha256":report["report_sha256"]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
