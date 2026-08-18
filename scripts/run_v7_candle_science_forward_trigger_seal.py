#!/usr/bin/env python3
from __future__ import annotations
import json,os
from pathlib import Path
from v7_candle_science_forward_structure import acquire_forward_structure
from v7_candle_science_primitives import canon
from v7_candle_science_reconstruct import compare_reconstructions
AUTH=Path('research/profitability/V7_CANDLE_SCIENCE_FORWARD_STRUCTURE_AUTHORIZE.json');PROTOCOL='98ed03185f93643e1c1b326835bee169e1f72a84d00c5a6aa4e56453a2a57134';TRANSPORT='83bdd46c80acec241499d5d99e76df22b8c11cdf4edd5983b4f4937582fdbc8e'
def authorization()->dict:
    x=json.loads(AUTH.read_text());expected={'authorization':'AUTHORIZE_V7_FORWARD_H4_H1_TRIGGER_SEAL_AFTER_HISTORICAL_PASS','protocol_sha256':PROTOCOL,'forward_transport_sha256':TRANSPORT,'m1_authorized':False,'bid_ask_authorized':False,'economic_outcomes_authorized':False,'broker_mutation_authorized':False}
    if x!=expected:raise RuntimeError('V7 forward structure authorization boundary changed')
    return x
def write(path:Path,value:object):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def main()->int:
    auth=authorization();structure=acquire_forward_structure();triggers,comparison=compare_reconstructions(structure['h4'],structure['h1']);distinct=len({row['knowledge_time_utc'] for row in triggers});ready=len(triggers)>=60 and distinct>=60 and comparison['exact_match'] is True
    result={'schema_version':1,'candidate_id':'ARJO_V7_NQ_CANDLE_SCIENCE_H1_FVG_REJECTION_TO_OPPOSING_FVG_SYMMETRIC','protocol_sha256':PROTOCOL,'forward_transport_sha256':TRANSPORT,'authorization_sha256':canon(auth),'structure_manifest_sha256':structure['manifest']['manifest_sha256'],'h4_structure_sha256':structure['manifest']['h4_sha256'],'h1_structure_sha256':structure['manifest']['h1_sha256'],'trigger_set_sha256':canon(triggers),'trigger_count':len(triggers),'distinct_knowledge_timestamps':distinct,'minimum_necessary_for_forward_m1':60,'independent_reconstruction_exact':comparison['exact_match'],'primary_trigger_sha256':comparison['primary_sha256'],'reference_trigger_sha256':comparison['reference_sha256'],'primary_stats':comparison['primary_stats'],'reference_stats':comparison['reference_stats'],'classification':'FORWARD_TRIGGER_SAMPLE_NECESSARY_CONDITION_MET' if ready else 'FORWARD_TRIGGER_SAMPLE_NECESSARY_CONDITION_FAILED','market_data':{'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'MID','granularities':['H4','H1'],'start_inclusive':'2024-01-01T00:00:00Z','end_exclusive':'2026-08-01T00:00:00Z','m1_requested':False,'bid_ask_requested':False},'economic_outcomes_accessed':False,'fills_evaluated':False,'pnl_evaluated':False,'paper_execution':False,'live_execution':False,'broker_mutation':False};result['readiness_sha256']=canon(result)
    out=Path(os.getenv('V7_FORWARD_OUTPUT_DIR','artifacts/v7_candle_science_forward_trigger'));out.mkdir(parents=True,exist_ok=True);write(out/'v7_forward_h4_mid.json',structure['h4']);write(out/'v7_forward_h1_mid.json',structure['h1']);write(out/'v7_forward_structure_manifest.json',structure['manifest']);write(out/'v7_forward_triggers.json',triggers);write(out/'v7_forward_trigger_readiness.json',result);print(json.dumps(result,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
