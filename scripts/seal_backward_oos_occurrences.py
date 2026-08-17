#!/usr/bin/env python3
"""Compare and seal outcome-blind backward-OOS occurrence scans."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path

def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--primary",required=True);p.add_argument("--independent",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 try:
  x=json.loads(Path(a.primary).read_text());y=json.loads(Path(a.independent).read_text())
  for r in (x,y):
   if r.get("post_entry_outcomes_accessed") is not False or r.get("m1_outcome_data_accessed") is not False:raise RuntimeError("outcome boundary violated")
  fields=["profile_sha256","protocol_sha256","data_manifest_sha256","scan_start","scan_end_exclusive","complete_session_count","detected_fvg_formation_count","selected_fvg_session_count","qualification_status_counts","qualification_rows_sha256","qualified_occurrence_ids","semantic_occurrence_set_sha256","observability_rows_sha256","observability_status_counts","executable_occurrence_ids","executable_occurrence_count","executable_occurrences_by_year"]
  mismatch=[f for f in fields if x.get(f)!=y.get(f)]
  if mismatch:raise RuntimeError("dual-path mismatch: "+",".join(mismatch))
  n=int(x["executable_occurrence_count"]);classification="SAMPLE_THRESHOLD_MET" if n>=30 else "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
  out={"schema_version":1,"status":"PROFITABILITY_BACKWARD_OOS_OCCURRENCES_READY","classification":classification,"minimum_executable_occurrences":30,"executable_occurrence_count":n,"qualified_occurrence_count":len(x["qualified_occurrence_ids"]),"complete_session_count":x["complete_session_count"],"executable_occurrence_ids":x["executable_occurrence_ids"],"executable_occurrences_by_year":x["executable_occurrences_by_year"],"semantic_occurrence_set_sha256":x["semantic_occurrence_set_sha256"],"observability_rows_sha256":x["observability_rows_sha256"],"qualification_rows_sha256":x["qualification_rows_sha256"],"data_manifest_sha256":x["data_manifest_sha256"],"primary_report_sha256":x["report_sha256"],"independent_report_sha256":y["report_sha256"],"dual_path_exact_match":True,"post_entry_outcomes_accessed":False,"m1_outcome_data_accessed":False,"no_refit_performed":True,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};out["readiness_sha256"]=canon(out);Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 except Exception as exc:print(f"backward OOS occurrence sealing failed: {exc}",file=sys.stderr);return 1
 print(json.dumps({"status":out["status"],"classification":out["classification"],"executable":n,"readiness_sha256":out["readiness_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
