#!/usr/bin/env python3
"""Primary production-path V2 backward-OOS occurrence scan. Never evaluates post-entry outcomes."""
from __future__ import annotations
import argparse, hashlib, json, sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import run_protected_validation_primary as base
from build_owner_operational_fvg_anchors import canonical_sha256, detect_formations

PROFILE_SHA="87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
PROTOCOL_SHA="3bbed5663762a5d484935de8383d02b4aa3d320e0d4ef02af9cf5469e3eddefe"
END=datetime(2024,1,1,tzinfo=UTC)

class ScanError(RuntimeError): pass

def fsha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(data:Path)->dict:
    m=json.loads((data/"NAS100_USD.manifest.json").read_text())
    u=dict(m); recorded=u.pop("manifest_sha256","")
    if not recorded or canonical_sha256(u)!=recorded: raise ScanError("manifest SHA mismatch")
    expected={"status":"PROFITABILITY_BACKWARD_OOS_STRUCTURE_READY","provider":"OANDA_V20","instrument":"NAS100_USD","semantic_price_component":"MID","source_granularity":"M15","protocol_sha256":PROTOCOL_SHA,"profile_sha256":PROFILE_SHA,"requested_end_exclusive":"2024-01-01T00:00:00Z","post_entry_outcomes_evaluated":False,"m1_outcome_data_requested":False,"mutation_endpoints_used":False}
    for k,v in expected.items():
        if m.get(k)!=v: raise ScanError(f"manifest boundary changed: {k}")
    if m["m15_sha256"]!=fsha(data/"NAS100_USD.15m.jsonl"): raise ScanError("M15 SHA mismatch")
    for mins in (60,240):
        if m["derived"][str(mins)]["sha256"]!=fsha(data/f"NAS100_USD.{mins}m.jsonl"): raise ScanError(f"{mins}m SHA mismatch")
    return m

def build(data:Path)->dict:
    m=verify(data); rows15=base.load_jsonl(data/"NAS100_USD.15m.jsonl",15); rows60=base.load_jsonl(data/"NAS100_USD.60m.jsonl",60); rows240=base.load_jsonl(data/"NAS100_USD.240m.jsonl",240)
    start=base.parse_utc(m["provider_first_complete_bar"]); base.HSTART=start; base.HEND=END
    sessions=base.complete_holdout_sessions(rows15); formations=detect_formations(rows240); fvg=base.select_fvgs(rows15,formations,sessions); ledger,occurrences,counts=base.qualify(rows15,rows60,rows240,fvg)
    obs=[]; executable=[]
    for occ in occurrences:
        touch=float(occ["touch_price"]); low=float(occ["second_sting_bar_low"]); high=float(occ["second_sting_bar_high"]); status="EXECUTABLE_ENTRY" if low<=touch<=high else "NO_EXECUTABLE_ENTRY"
        row={"occurrence_id":occ["occurrence_id"],"session_date_ny":occ["session_date_ny"],"status":status,"second_sting_ts_utc":occ["second_sting_ts_utc"],"touch_price":occ["touch_price"],"bar_low":occ["second_sting_bar_low"],"bar_high":occ["second_sting_bar_high"]}; obs.append(row)
        if status=="EXECUTABLE_ENTRY": executable.append(occ["occurrence_id"])
    obs.sort(key=lambda r:r["occurrence_id"]); executable.sort(); years=dict(sorted(Counter(r["session_date_ny"][:4] for r in obs if r["status"]=="EXECUTABLE_ENTRY").items()))
    result={"schema_version":1,"path_id":"PRIMARY_V2_PRODUCTION_PATH","status":"BACKWARD_OOS_OCCURRENCE_SCAN_COMPLETE","profile_sha256":PROFILE_SHA,"protocol_sha256":PROTOCOL_SHA,"data_manifest_sha256":m["manifest_sha256"],"scan_start":start.isoformat().replace("+00:00","Z"),"scan_end_exclusive":"2024-01-01T00:00:00Z","complete_session_count":len(sessions),"detected_fvg_formation_count":len(formations),"selected_fvg_session_count":int(fvg["selected_count"]),"qualification_status_counts":counts,"qualification_rows_sha256":canonical_sha256(ledger),"qualified_occurrence_ids":[o["occurrence_id"] for o in occurrences],"semantic_occurrence_set_sha256":canonical_sha256(occurrences),"observability_rows":obs,"observability_rows_sha256":canonical_sha256(obs),"observability_status_counts":dict(sorted(Counter(r["status"] for r in obs).items())),"executable_occurrence_ids":executable,"executable_occurrence_count":len(executable),"executable_occurrences_by_year":years,"post_entry_outcomes_accessed":False,"m1_outcome_data_accessed":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
    result["report_sha256"]=canonical_sha256(result); return result

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--data-dir",required=True); p.add_argument("--output",required=True); a=p.parse_args()
    try: r=build(Path(a.data_dir)); Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    except Exception as exc: print(f"primary backward OOS scan failed: {exc}",file=sys.stderr); return 1
    print(json.dumps({"path":r["path_id"],"sessions":r["complete_session_count"],"qualified":len(r["qualified_occurrence_ids"]),"executable":r["executable_occurrence_count"],"outcomes_accessed":False,"report_sha256":r["report_sha256"]},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
