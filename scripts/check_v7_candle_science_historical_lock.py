#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
LOCK=Path('research/profitability/v7_candle_science_historical_execution_lock_v1.json');TRIGGER=Path('research/profitability/v7_candle_science_trigger_result_v1.json');FORWARD=Path('research/profitability/v7_candle_science_forward_confirmation_transport_v1.json')
EXPECTED='56a00ad6a45d926221330acf2c2160ce862752dc93f712c3b35b68cf35194049';PROTOCOL='98ed03185f93643e1c1b326835bee169e1f72a84d00c5a6aa4e56453a2a57134';TRIGGER_SHA='0286fc800d0b20399848945b2ae6b7520a6d314767a4ef8bb043b476bb3d2c98';FORWARD_SHA='83bdd46c80acec241499d5d99e76df22b8c11cdf4edd5983b4f4937582fdbc8e'
def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def verify()->dict:
    lock=json.loads(LOCK.read_text());recorded=lock.pop('execution_lock_sha256');assert recorded==EXPECTED and canon(lock)==EXPECTED
    assert lock['status']=='FROZEN_BEFORE_FIRST_V7_M1_RESPONSE';assert lock['protocol_sha256']==PROTOCOL;assert lock['trigger_set_sha256']==TRIGGER_SHA;assert lock['trigger_count']==5212 and lock['distinct_knowledge_timestamps']==4972;assert lock['trigger_readiness_sha256']=='5d929529a3c386081cb45042e1fff1041eb795d1cc2ef92a30ad4bc2d8f8dd3b';assert lock['structure_manifest_sha256']=='a61ef4aa9deb1ed3de36611a12c9afd83ca25aeb8e55cd63004fd2328a39b414';assert lock['forward_confirmation_transport_sha256']==FORWARD_SHA
    assert lock['historical_window']=={'start_inclusive':'2010-01-01T00:00:00Z','end_exclusive':'2024-01-01T00:00:00Z'};assert lock['m1_provider_contract']['price']=='BA' and lock['m1_provider_contract']['granularity']=='M1';assert lock['historical_gate']['minimum_resolved_executed_trades']==300 and lock['historical_gate']['base_profit_factor_gt']==1.35 and lock['historical_gate']['stress_profit_factor_gt']==1.1 and lock['historical_gate']['positive_calendar_year_fraction_gte']==0.75
    for key in ['parameter_changes_after_first_m1_response','cost_changes_after_first_m1_response','threshold_changes_after_first_m1_response','target_stop_rule_changes_after_first_m1_response','forward_confirmation_access_authorized','paper_execution_authorized','live_execution_authorized','broker_mutation_authorized']:assert lock[key] is False,key
    trigger=json.loads(TRIGGER.read_text());assert trigger['trigger_set_sha256']==TRIGGER_SHA and trigger['trigger_count']==5212 and trigger['distinct_knowledge_timestamps']==4972 and trigger['economic_outcomes_accessed'] is False
    forward=json.loads(FORWARD.read_text());fr=forward.pop('transport_sha256');assert fr==FORWARD_SHA and canon(forward)==FORWARD_SHA and forward['status']=='FROZEN_BEFORE_V7_HISTORICAL_M1_RESULT'
    return lock
if __name__=='__main__':verify();print('v7_historical_execution_lock='+EXPECTED);print('v7_m1_preoutcome_boundary=PASS')
