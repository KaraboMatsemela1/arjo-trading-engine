#!/usr/bin/env python3
from __future__ import annotations
import json,os
from pathlib import Path
import check_v8_fvg_followthrough_protocol as protocol_check
from v7_candle_science_primitives import canon
from v8_fvg_followthrough_reconstruct import compare_reconstructions
from v8_fvg_followthrough_structure import acquire_structure
AUTH=Path('research/profitability/v8_fvg_followthrough_trigger_authorization_v1.json');PROTOCOL='79c0289293996f02faa6de1ecb5dcc6d6201a7b98bff1be842bab6cc707b547d'
def authorization()->dict:
    x=json.loads(AUTH.read_text());expected={'authorization':'AUTHORIZE_V8_H4_H1_TRIGGER_SEAL','issue':286,'protocol_sha256':PROTOCOL,'m1_authorized':False,'bid_ask_authorized':False,'economic_outcomes_authorized':False,'broker_mutation_authorized':False}
    if x!=expected:raise RuntimeError('V8 structure-only authorization boundary changed')
    return x
def write(path:Path,value:object):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def main()->int:
    protocol_check.verify();auth=authorization();structure=acquire_structure();triggers,comparison=compare_reconstructions(structure['h4'],structure['h1']);distinct=len({row['knowledge_time_utc'] for row in triggers});ready=len(triggers)>=350 and distinct>=350 and comparison['exact_match'] is True
    result={'schema_version':1,'candidate_id':'ARJO_V8_NQ_FVG_FOLLOWTHROUGH_H4_H1_SYMMETRIC','issue':286,'protocol_sha256':PROTOCOL,'authorization_sha256':canon(auth),'structure_manifest_sha256':structure['manifest']['manifest_sha256'],'h4_structure_sha256':structure['manifest']['h4_sha256'],'h1_structure_sha256':structure['manifest']['h1_sha256'],'trigger_set_sha256':canon(triggers),'trigger_count':len(triggers),'distinct_knowledge_timestamps':distinct,'minimum_required':350,'independent_reconstruction_exact':comparison['exact_match'],'primary_trigger_sha256':comparison['primary_sha256'],'reference_trigger_sha256':comparison['reference_sha256'],'primary_stats':comparison['primary_stats'],'reference_stats':comparison['reference_stats'],'classification':'TRIGGER_SAMPLE_NECESSARY_CONDITION_MET' if ready else 'TRIGGER_SAMPLE_NECESSARY_CONDITION_FAILED','market_data':{'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'MID','granularities':['H4','H1'],'strict_end_exclusive':'2024-01-01T00:00:00Z','m1_requested':False,'bid_ask_requested':False},'economic_outcomes_accessed':False,'fills_evaluated':False,'pnl_evaluated':False,'paper_execution':False,'live_execution':False,'broker_mutation':False};result['readiness_sha256']=canon(result)
    out=Path(os.getenv('V8_OUTPUT_DIR','artifacts/v8_fvg_followthrough_trigger_seal'));out.mkdir(parents=True,exist_ok=True);write(out/'v8_h4_mid.json',structure['h4']);write(out/'v8_h1_mid.json',structure['h1']);write(out/'v8_structure_manifest.json',structure['manifest']);write(out/'v8_fvg_followthrough_triggers.json',triggers);write(out/'v8_trigger_readiness.json',result);print(json.dumps(result,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
