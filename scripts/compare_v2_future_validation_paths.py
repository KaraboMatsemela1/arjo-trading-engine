#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROFILE_SHA="87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
PROTOCOL_SHA="193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38"
POLICY_SHA="6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6"
CRITICAL_FIELDS=[
    "complete_session_count","detected_fvg_formation_count","selected_fvg_session_count",
    "qualification_status_counts","qualified_occurrence_ids","qualification_rows_sha256","semantic_occurrence_set_sha256",
    "observability_rows_sha256","observability_status_counts","executable_occurrence_ids","execution_outcomes","execution_outcomes_sha256",
    "integrity_failures","metrics","validation_classification","future_validation_boundary_ok"
]


def canon(value:object)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def load_report(path:Path,expected_path:str)->dict:
    report=json.loads(path.read_text(encoding="utf-8")); recorded=str(report.get("report_sha256","")); unsigned=dict(report); unsigned.pop("report_sha256",None)
    if not recorded or canon(unsigned)!=recorded: raise RuntimeError(f"{path} report SHA mismatch")
    if report.get("path_id")!=expected_path: raise RuntimeError(f"{path} unexpected path id")
    if report.get("profile_sha256")!=PROFILE_SHA or report.get("protocol_sha256")!=PROTOCOL_SHA or report.get("measurement_policy_sha256")!=POLICY_SHA: raise RuntimeError(f"{path} frozen binding changed")
    if any(report.get(k) is not False for k in ("holdout_2026h1_accessed","pre_start_market_data_accessed","paper_execution_authorized","live_execution_authorized","broker_mutation_authorized")): raise RuntimeError(f"{path} boundary changed")
    return report


def compare(primary:dict,independent:dict)->dict:
    mismatches=[]; agreement={}
    if primary.get("data_manifest_sha256")!=independent.get("data_manifest_sha256"): mismatches.append("data_manifest_sha256")
    for field in CRITICAL_FIELDS:
        same=primary.get(field)==independent.get(field); agreement[field]={"status":"PASS" if same else "FAIL","value_sha256":canon(primary.get(field)) if same else None}
        if not same: mismatches.append(field)
    classification="IMPLEMENTATION_DIVERGENCE" if mismatches else primary["validation_classification"]
    result={"schema_version":1,"status":"V2_FUTURE_VALIDATION_COMPARISON_COMPLETE","implementation_agreement":not mismatches,"mismatches":mismatches,"critical_agreement":agreement,"profile_sha256":PROFILE_SHA,"protocol_sha256":PROTOCOL_SHA,"measurement_policy_sha256":POLICY_SHA,"data_manifest_sha256":primary.get("data_manifest_sha256"),"primary_report_sha256":primary["report_sha256"],"independent_report_sha256":independent["report_sha256"],"validation_classification":classification,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
    result["comparison_sha256"]=canon(result); return result


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--primary",required=True); p.add_argument("--independent",required=True); p.add_argument("--output",required=True); args=p.parse_args()
    try:
        result=compare(load_report(Path(args.primary),"PRIMARY_V2_PRODUCTION_PATH"),load_report(Path(args.independent),"INDEPENDENT_V2_STANDARD_LIBRARY_PATH")); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except Exception as exc: print(f"V2 future validation comparison failed: {exc}",file=sys.stderr); return 1
    print(json.dumps({"implementation_agreement":result["implementation_agreement"],"classification":result["validation_classification"],"comparison_sha256":result["comparison_sha256"]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
