#!/usr/bin/env python3
from __future__ import annotations
import json,os
from pathlib import Path
import check_v6_momentum_protocol as protocol_check
from v6_momentum_primitives import canon
from v6_momentum_reconstruct import compare_reconstructions
from v6_momentum_structure import acquire_structure

AUTH=Path('research/profitability/v6_momentum_trigger_authorization_v1.json')
EXPECTED='AUTHORIZE_V6_H1_M15_TRIGGER_SEAL'
PROTOCOL_SHA='8a4839f9c9c07bec97aa78fe57ea246e8c256ad88c458ce9bf37b9f5b1b892ab'

def authorization():
    x=json.loads(AUTH.read_text());assert x=={'authorization':EXPECTED,'issue':266,'protocol_sha256':PROTOCOL_SHA,'m1_authorized':False,'bid_ask_authorized':False,'economic_outcomes_authorized':False,'broker_mutation_authorized':False};return x

def write(path:Path,value:object):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def main()->int:
    protocol_check.verify();auth=authorization();structure=acquire_structure();triggers,cmp=compare_reconstructions(structure['h1'],structure['m15']);distinct=len({x['knowledge_time_utc'] for x in triggers});ready=len(triggers)>=250 and distinct>=250 and cmp['exact_match'] is True
    result={'schema_version':1,'issue':266,'candidate_id':'ARJO_V6_NQ_MOMENTUM_CYCLE_CONTINUATION_H1_M15_SYMMETRIC','protocol_sha256':PROTOCOL_SHA,'authorization_sha256':canon(auth),'structure_manifest_sha256':structure['manifest']['manifest_sha256'],'h1_structure_sha256':structure['manifest']['h1_sha256'],'m15_structure_sha256':structure['manifest']['m15_sha256'],'trigger_set_sha256':canon(triggers),'trigger_count':len(triggers),'distinct_knowledge_timestamps':distinct,'minimum_required':250,'independent_reconstruction_exact':cmp['exact_match'],'primary_trigger_sha256':cmp['primary_sha256'],'reference_trigger_sha256':cmp['reference_sha256'],'primary_stats':cmp['primary_stats'],'reference_stats':cmp['reference_stats'],'classification':'TRIGGER_SAMPLE_NECESSARY_CONDITION_MET' if ready else 'TRIGGER_SAMPLE_NECESSARY_CONDITION_FAILED','market_data':{'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'MID','granularities':['H1','M15'],'strict_end_exclusive':'2024-01-01T00:00:00Z','m1_requested':False,'bid_ask_requested':False},'economic_outcomes_accessed':False,'fills_evaluated':False,'pnl_evaluated':False,'paper_execution':False,'live_execution':False,'broker_mutation':False};result['readiness_sha256']=canon(result)
    out=Path(os.getenv('V6_OUTPUT_DIR','artifacts/v6_momentum_trigger_seal'));out.mkdir(parents=True,exist_ok=True);write(out/'v6_h1_mid.json',structure['h1']);write(out/'v6_m15_mid.json',structure['m15']);write(out/'v6_h1_provenance.json',structure['h1_provenance']);write(out/'v6_m15_provenance.json',structure['m15_provenance']);write(out/'v6_structure_manifest.json',structure['manifest']);write(out/'v6_momentum_triggers.json',triggers);write(out/'v6_trigger_readiness.json',result);print(json.dumps(result,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
