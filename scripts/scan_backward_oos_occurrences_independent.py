#!/usr/bin/env python3
"""Independent standard-library V2 backward-OOS occurrence scan. No production strategy builders or outcome evaluator."""
from __future__ import annotations
import argparse, hashlib, json, sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import run_protected_validation_independent as base

PROFILE_SHA="87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
PROTOCOL_SHA="3bbed5663762a5d484935de8383d02b4aa3d320e0d4ef02af9cf5469e3eddefe"
END=datetime(2024,1,1,tzinfo=UTC)
class ScanError(RuntimeError): pass

def fsha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(data:Path)->dict:
 m=json.loads((data/"NAS100_USD.manifest.json").read_text());u=dict(m);rec=u.pop("manifest_sha256","")
 if not rec or base.canon(u)!=rec:raise ScanError("manifest SHA mismatch")
 for k,v in {"status":"PROFITABILITY_BACKWARD_OOS_STRUCTURE_READY","provider":"OANDA_V20","instrument":"NAS100_USD","semantic_price_component":"MID","source_granularity":"M15","protocol_sha256":PROTOCOL_SHA,"profile_sha256":PROFILE_SHA,"requested_end_exclusive":"2024-01-01T00:00:00Z","post_entry_outcomes_evaluated":False,"m1_outcome_data_requested":False,"mutation_endpoints_used":False}.items():
  if m.get(k)!=v:raise ScanError(f"manifest boundary changed: {k}")
 if m["m15_sha256"]!=fsha(data/"NAS100_USD.15m.jsonl"):raise ScanError("M15 SHA mismatch")
 for x in (60,240):
  if m["derived"][str(x)]["sha256"]!=fsha(data/f"NAS100_USD.{x}m.jsonl"):raise ScanError(f"{x}m SHA mismatch")
 return m

def build(data:Path)->dict:
 m=verify(data);r15=base.read_rows(data/"NAS100_USD.15m.jsonl",15);r60=base.read_rows(data/"NAS100_USD.60m.jsonl",60);r240=base.read_rows(data/"NAS100_USD.240m.jsonl",240);start=base.parse(m["provider_first_complete_bar"]);base.HSTART=start;base.HEND=END
 sessions=base.holdout_sessions(r15);forms=base.detect_fvgs(r240);selected=base.fvg_sessions(r15,forms,sessions);ledger,occ,counts=base.qualify(r15,r60,r240,selected);obs=[];exe=[]
 for o in occ:
  touch=base.num(o["touch_price"],"touch");low=base.num(o["second_sting_bar_low"],"low");high=base.num(o["second_sting_bar_high"],"high");status="EXECUTABLE_ENTRY" if low<=touch<=high else "NO_EXECUTABLE_ENTRY";obs.append({"occurrence_id":o["occurrence_id"],"session_date_ny":o["session_date_ny"],"status":status,"second_sting_ts_utc":o["second_sting_ts_utc"],"touch_price":o["touch_price"],"bar_low":o["second_sting_bar_low"],"bar_high":o["second_sting_bar_high"]});exe.extend([o["occurrence_id"]] if status=="EXECUTABLE_ENTRY" else [])
 obs.sort(key=lambda x:x["occurrence_id"]);exe.sort();years=dict(sorted(Counter(x["session_date_ny"][:4] for x in obs if x["status"]=="EXECUTABLE_ENTRY").items()));out={"schema_version":1,"path_id":"INDEPENDENT_V2_STANDARD_LIBRARY_PATH","status":"BACKWARD_OOS_OCCURRENCE_SCAN_COMPLETE","profile_sha256":PROFILE_SHA,"protocol_sha256":PROTOCOL_SHA,"data_manifest_sha256":m["manifest_sha256"],"scan_start":start.isoformat().replace("+00:00","Z"),"scan_end_exclusive":"2024-01-01T00:00:00Z","complete_session_count":len(sessions),"detected_fvg_formation_count":len(forms),"selected_fvg_session_count":sum(x["selected_fvg"] is not None for x in selected),"qualification_status_counts":counts,"qualification_rows_sha256":base.canon(ledger),"qualified_occurrence_ids":[o["occurrence_id"] for o in occ],"semantic_occurrence_set_sha256":base.canon(occ),"observability_rows":obs,"observability_rows_sha256":base.canon(obs),"observability_status_counts":dict(sorted(Counter(x["status"] for x in obs).items())),"executable_occurrence_ids":exe,"executable_occurrence_count":len(exe),"executable_occurrences_by_year":years,"post_entry_outcomes_accessed":False,"m1_outcome_data_accessed":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};out["report_sha256"]=base.canon(out);return out

def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--data-dir",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 try:r=build(Path(a.data_dir));Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
 except Exception as exc:print(f"independent backward OOS scan failed: {exc}",file=sys.stderr);return 1
 print(json.dumps({"path":r["path_id"],"sessions":r["complete_session_count"],"qualified":len(r["qualified_occurrence_ids"]),"executable":r["executable_occurrence_count"],"outcomes_accessed":False,"report_sha256":r["report_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
