#!/usr/bin/env python3
"""Outcome-blind V3-B coverage scan across the preregistered U.S. index set."""
from __future__ import annotations

import argparse, json, sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import oanda_backward_oos_structure as common
import run_protected_validation_primary as primary
import run_protected_validation_independent as independent
from build_owner_operational_fvg_anchors import detect_formations

CANDIDATE_SHA="c40cf7223bcb956d0e668e48dfeb29fbb7aa529fe45350710bbe5aaf2c2160b9"
START=datetime(2024,1,1,tzinfo=UTC);END=datetime(2026,1,1,tzinfo=UTC)

class CoverageError(RuntimeError):pass

def load_manifest(root:Path,instrument:str)->dict:
    p=root/instrument/f"{instrument}.manifest.json";m=json.loads(p.read_text());u=dict(m);rec=u.pop("manifest_sha256","")
    if not rec or common.canon(u)!=rec:raise CoverageError(f"manifest SHA mismatch {instrument}")
    for k,v in {"instrument":instrument,"status":"V3_MULTI_INDEX_DEVELOPMENT_STRUCTURE_READY","candidate_sha256":CANDIDATE_SHA,"requested_start":"2024-01-01T00:00:00Z","requested_end_exclusive":"2026-01-01T00:00:00Z","semantic_price_component":"MID","source_granularity":"M15","post_entry_outcomes_evaluated":False,"m1_outcome_data_requested":False,"mutation_endpoints_used":False}.items():
        if m.get(k)!=v:raise CoverageError(f"manifest boundary changed {instrument}:{k}")
    return m

def normalize_occ(instrument:str,occ:list[dict])->list[dict]:
    out=[]
    for x in occ:
        y=dict(x); y["occurrence_id"]=f"{instrument}:{x['occurrence_id']}";y["instrument"]=instrument;out.append(y)
    return sorted(out,key=lambda z:(z["session_date_ny"],z["occurrence_id"]))

def primary_scan(root:Path,instrument:str,m:dict)->dict:
    r15=primary.load_jsonl(root/instrument/f"{instrument}.15m.jsonl",15);r60=primary.load_jsonl(root/instrument/f"{instrument}.60m.jsonl",60);r240=primary.load_jsonl(root/instrument/f"{instrument}.240m.jsonl",240)
    primary.HSTART=START;primary.HEND=END;sessions=primary.complete_holdout_sessions(r15);forms=detect_formations(r240);fvg=primary.select_fvgs(r15,forms,sessions);ledger,occ,counts=primary.qualify(r15,r60,r240,fvg);occ=normalize_occ(instrument,occ);obs=[]
    for o in occ:
        touch=float(o["touch_price"]);low=float(o["second_sting_bar_low"]);high=float(o["second_sting_bar_high"]);obs.append({"occurrence_id":o["occurrence_id"],"instrument":instrument,"session_date_ny":o["session_date_ny"],"status":"EXECUTABLE_ENTRY" if low<=touch<=high else "NO_EXECUTABLE_ENTRY"})
    return {"sessions":len(sessions),"forms":len(forms),"selected":int(fvg["selected_count"]),"counts":counts,"ledger_sha":common.canon(ledger),"occ":occ,"occ_sha":common.canon(occ),"obs":obs,"obs_sha":common.canon(obs)}

def independent_scan(root:Path,instrument:str,m:dict)->dict:
    r15=independent.read_rows(root/instrument/f"{instrument}.15m.jsonl",15);r60=independent.read_rows(root/instrument/f"{instrument}.60m.jsonl",60);r240=independent.read_rows(root/instrument/f"{instrument}.240m.jsonl",240)
    independent.HSTART=START;independent.HEND=END;sessions=independent.holdout_sessions(r15);forms=independent.detect_fvgs(r240);selected=independent.fvg_sessions(r15,forms,sessions);ledger,occ,counts=independent.qualify(r15,r60,r240,selected);occ=normalize_occ(instrument,occ);obs=[]
    for o in occ:
        touch=independent.num(o["touch_price"],"touch");low=independent.num(o["second_sting_bar_low"],"low");high=independent.num(o["second_sting_bar_high"],"high");obs.append({"occurrence_id":o["occurrence_id"],"instrument":instrument,"session_date_ny":o["session_date_ny"],"status":"EXECUTABLE_ENTRY" if low<=touch<=high else "NO_EXECUTABLE_ENTRY"})
    return {"sessions":len(sessions),"forms":len(forms),"selected":sum(x["selected_fvg"] is not None for x in selected),"counts":counts,"ledger_sha":common.canon(ledger),"occ":occ,"occ_sha":common.canon(occ),"obs":obs,"obs_sha":common.canon(obs)}

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--data-dir",required=True);p.add_argument("--candidate",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    try:
        cand=json.loads(Path(a.candidate).read_text());rec=cand.pop("candidate_sha256","")
        if rec!=CANDIDATE_SHA or common.canon(cand)!=CANDIDATE_SHA:raise CoverageError("candidate SHA drift")
        root=Path(a.data_dir);summary=json.loads((root/"multi-index-summary.json").read_text());available=summary["available_instruments"];fixed=cand["change_set"]["fixed_candidate_instruments"]
        if any(x not in fixed for x in available) or summary["replacement_instruments_used"] is not False:raise CoverageError("instrument-set boundary violated")
        per={};all_obs=[]
        for instrument in available:
            m=load_manifest(root,instrument);x=primary_scan(root,instrument,m);y=independent_scan(root,instrument,m)
            for key in ("sessions","forms","selected","counts","ledger_sha","occ_sha","obs_sha"):
                if x[key]!=y[key]:raise CoverageError(f"dual-path mismatch {instrument}:{key}")
            exe=[z for z in x["obs"] if z["status"]=="EXECUTABLE_ENTRY"];all_obs.extend(exe);per[instrument]={"complete_sessions":x["sessions"],"detected_fvgs":x["forms"],"selected_fvg_sessions":x["selected"],"qualification_status_counts":x["counts"],"qualified_occurrence_count":len(x["occ"]),"executable_occurrence_count":len(exe),"semantic_occurrences_sha256":x["occ_sha"],"observability_rows_sha256":x["obs_sha"],"dual_path_exact_match":True}
        all_obs.sort(key=lambda z:(z["session_date_ny"],z["instrument"],z["occurrence_id"]));clusters=defaultdict(list)
        for z in all_obs:clusters[z["session_date_ny"]].append(z["instrument"])
        unique_dates=len(clusters);raw=len(all_obs);floor=int(cand["development_coverage"]["portfolio_executable_occurrence_floor"]);feasible=raw>=floor and unique_dates>=floor
        out={"schema_version":1,"status":"V3_MULTI_INDEX_COVERAGE_DIAGNOSTIC_COMPLETE","candidate_sha256":CANDIDATE_SHA,"fixed_candidate_instruments":fixed,"available_instruments":available,"unavailable_instruments":summary["unavailable_instruments"],"per_instrument":per,"raw_executable_occurrence_count":raw,"unique_executable_signal_dates":unique_dates,"same_date_cluster_count":sum(1 for v in clusters.values() if len(v)>1),"max_same_date_cluster_size":max([len(v) for v in clusters.values()] or [0]),"coverage_feasibility_floor":floor,"coverage_feasible":feasible,"effective_independence_policy":"same-date cross-index signals count as one signal date for feasibility","executable_signal_dates":dict(sorted((k,sorted(v)) for k,v in clusters.items())),"post_entry_outcomes_accessed":False,"performance_metrics_accessed":False,"backward_oos_outcomes_accessed":False,"candidate_selection_uses_performance":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};out["report_sha256"]=common.canon(out);Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    except Exception as exc:print(f"V3 multi-index coverage failed: {exc}",file=sys.stderr);return 1
    print(json.dumps({"status":out["status"],"available":available,"raw_executable":raw,"unique_dates":unique_dates,"clusters":out["same_date_cluster_count"],"coverage_feasible":feasible,"outcomes_accessed":False,"report_sha256":out["report_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
