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


def canon(value:object)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def verified(path:Path,field:str)->dict:
    data=json.loads(path.read_text(encoding="utf-8")); recorded=str(data.get(field,"")); unsigned=dict(data); unsigned.pop(field,None)
    if not recorded or canon(unsigned)!=recorded: raise RuntimeError(f"{path} SHA mismatch")
    return data


def seal(primary:dict,independent:dict,comparison:dict)->dict:
    if comparison.get("primary_report_sha256")!=primary.get("report_sha256") or comparison.get("independent_report_sha256")!=independent.get("report_sha256"): raise RuntimeError("comparison/report binding mismatch")
    for doc in (primary,independent,comparison):
        if doc.get("profile_sha256")!=PROFILE_SHA or doc.get("protocol_sha256")!=PROTOCOL_SHA or doc.get("measurement_policy_sha256")!=POLICY_SHA: raise RuntimeError("frozen result binding changed")
    source=primary if comparison.get("implementation_agreement") is True else None
    result={
        "schema_version":1,"status":"V2_FUTURE_VALIDATION_COMPLETE","profile_id":"ARJO_DERIVED_OWNER_OPERATIONAL_V2","profile_sha256":PROFILE_SHA,
        "validation_protocol_id":"ARJO_V2_FUTURE_VALIDATION_PROTOCOL_V2","validation_protocol_sha256":PROTOCOL_SHA,
        "measurement_policy_id":"V2_M1_TOUCH_SEQUENCING_V1","measurement_policy_sha256":POLICY_SHA,
        "data_manifest_sha256":comparison.get("data_manifest_sha256"),"primary_report_sha256":primary["report_sha256"],"independent_report_sha256":independent["report_sha256"],"comparison_sha256":comparison["comparison_sha256"],
        "implementation_agreement":comparison["implementation_agreement"],"validation_classification":comparison["validation_classification"],
        "complete_session_count":source.get("complete_session_count") if source else None,"qualification_status_counts":source.get("qualification_status_counts") if source else None,
        "qualified_occurrence_ids":source.get("qualified_occurrence_ids") if source else None,"semantic_occurrence_set_sha256":source.get("semantic_occurrence_set_sha256") if source else None,
        "observability_status_counts":source.get("observability_status_counts") if source else None,"observability_rows_sha256":source.get("observability_rows_sha256") if source else None,
        "executable_occurrence_ids":source.get("executable_occurrence_ids") if source else None,"execution_outcomes":source.get("execution_outcomes") if source else None,"execution_outcomes_sha256":source.get("execution_outcomes_sha256") if source else None,
        "integrity_failures":source.get("integrity_failures") if source else None,"metrics":source.get("metrics") if source else None,
        "no_refit_performed":True,"bootstrap_performance_inspected":False,"holdout_2026h1_reused":False,"pre_start_market_data_accessed":False,
        "paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False,
    }
    result["validation_result_sha256"]=canon(result); return result


def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--primary",required=True); p.add_argument("--independent",required=True); p.add_argument("--comparison",required=True); p.add_argument("--output",required=True); args=p.parse_args()
    try:
        primary=verified(Path(args.primary),"report_sha256"); independent=verified(Path(args.independent),"report_sha256"); comparison=verified(Path(args.comparison),"comparison_sha256"); result=seal(primary,independent,comparison); out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except Exception as exc: print(f"V2 validation result sealing failed: {exc}",file=sys.stderr); return 1
    print(json.dumps({"status":result["status"],"classification":result["validation_classification"],"validation_result_sha256":result["validation_result_sha256"]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
