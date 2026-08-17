#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile
from pathlib import Path
import seal_backward_oos_occurrences as seal

ROOT=Path(__file__).resolve().parents[1]

def static_boundaries()->None:
 primary=(ROOT/"scripts/scan_backward_oos_occurrences_primary.py").read_text()
 independent=(ROOT/"scripts/scan_backward_oos_occurrences_independent.py").read_text()
 acquisition=(ROOT/"scripts/oanda_backward_oos_structure.py").read_text()
 for text in (primary,independent,acquisition):
  assert "measure_occurrence" not in text
  assert "v2_m1_execution_measurement" not in text
  assert "execution_outcomes" not in text
 assert "run_protected_validation_primary" not in independent
 assert "build_owner_operational_fvg_anchors" not in independent
 assert "run_v2_future_validation" not in independent
 assert '"post_entry_outcomes_evaluated": False' in acquisition

def report(path:str)->dict:
 return {"path_id":path,"profile_sha256":"p","protocol_sha256":"q","data_manifest_sha256":"m","scan_start":"2010-01-01T00:00:00Z","scan_end_exclusive":"2024-01-01T00:00:00Z","complete_session_count":100,"detected_fvg_formation_count":2,"selected_fvg_session_count":50,"qualification_status_counts":{"QUALIFIED":1},"qualification_rows_sha256":"l","qualified_occurrence_ids":["x"],"semantic_occurrence_set_sha256":"o","observability_rows_sha256":"z","observability_status_counts":{"EXECUTABLE_ENTRY":1},"executable_occurrence_ids":["x"],"executable_occurrence_count":1,"executable_occurrences_by_year":{"2012":1},"post_entry_outcomes_accessed":False,"m1_outcome_data_accessed":False,"report_sha256":path}

def main()->None:
 static_boundaries()
 with tempfile.TemporaryDirectory() as d:
  d=Path(d);p=d/"p.json";i=d/"i.json";o=d/"o.json";p.write_text(json.dumps(report("P")));i.write_text(json.dumps(report("I")))
  import sys
  old=sys.argv;sys.argv=["seal", "--primary",str(p),"--independent",str(i),"--output",str(o)]
  try: assert seal.main()==0
  finally: sys.argv=old
  out=json.loads(o.read_text());assert out["classification"]=="INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED";assert out["post_entry_outcomes_accessed"] is False
 print("backward OOS occurrence sabotage tests passed")
if __name__=="__main__":main()
