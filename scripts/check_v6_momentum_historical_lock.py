#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path

LOCK=Path('research/profitability/v6_momentum_historical_execution_lock_v1.json')
TRIGGER_RESULT=Path('research/profitability/v6_momentum_trigger_result_v1.json')
FORWARD=Path('research/profitability/v6_momentum_forward_confirmation_transport_v1.json')
EXPECTED_LOCK_SHA='1d883fe81a274aa81437da2ca732d09f887529cea3d07a8d58f0a85ed2c2f779'
PROTOCOL_SHA='8a4839f9c9c07bec97aa78fe57ea246e8c256ad88c458ce9bf37b9f5b1b892ab'
TRIGGER_SHA='644edb8b1fe008a053f4fbdc368f6117d1c20ba478b9277bb1fb1f8f5cf9a150'
FORWARD_SHA='24bbcc1c31f1469c45ca70cffdf1fafb4821cada857c9ab04233d90bca601ce6'

def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def verify()->dict:
    lock=json.loads(LOCK.read_text());recorded=lock.pop('execution_lock_sha256')
    assert recorded==EXPECTED_LOCK_SHA and canon(lock)==EXPECTED_LOCK_SHA
    assert lock['status']=='FROZEN_BEFORE_FIRST_V6_M1_RESPONSE'
    assert lock['protocol_sha256']==PROTOCOL_SHA
    assert lock['trigger_set_sha256']==TRIGGER_SHA and lock['trigger_count']==1331 and lock['distinct_knowledge_timestamps']==441
    assert lock['trigger_readiness_sha256']=='f214b9154b3c40fb6cc472fd8858bc4781aedb3c28e7d4f252d0832dbf3b9cad'
    assert lock['structure_manifest_sha256']=='4cb58637b433b544865a6a94cdc2b48b344d47824e8ba0f76b9be5f67496dd2c'
    assert lock['forward_confirmation_transport_sha256']==FORWARD_SHA
    assert lock['historical_window']=={'start_inclusive':'2010-01-01T00:00:00Z','end_exclusive':'2024-01-01T00:00:00Z'}
    assert lock['m1_provider_contract']['price']=='BA' and lock['m1_provider_contract']['granularity']=='M1'
    assert lock['parameter_changes_after_first_m1_response'] is False
    assert lock['cost_changes_after_first_m1_response'] is False
    assert lock['threshold_changes_after_first_m1_response'] is False
    assert lock['target_stop_rule_changes_after_first_m1_response'] is False
    assert lock['forward_confirmation_access_authorized'] is False
    assert lock['paper_execution_authorized'] is False and lock['live_execution_authorized'] is False and lock['broker_mutation_authorized'] is False
    trig=json.loads(TRIGGER_RESULT.read_text());assert trig['trigger_set_sha256']==TRIGGER_SHA and trig['trigger_count']==1331 and trig['distinct_knowledge_timestamps']==441 and trig['economic_outcomes_accessed'] is False
    f=json.loads(FORWARD.read_text());fr=f.pop('transport_sha256');assert fr==FORWARD_SHA and canon(f)==FORWARD_SHA and f['status']=='FROZEN_BEFORE_V6_HISTORICAL_M1_RESULT'
    return lock

if __name__=='__main__':
    verify();print('v6_historical_execution_lock='+EXPECTED_LOCK_SHA);print('v6_m1_preoutcome_boundary=PASS')
