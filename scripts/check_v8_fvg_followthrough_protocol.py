#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
PROTOCOL=Path('research/profitability/v8_fvg_followthrough_protocol_v1.json');BOUNDARY=Path('research/profitability/v8_fvg_followthrough_preoutcome_boundary_v1.json');SOURCE=Path('research/profitability/v8_fvg_followthrough_source_recovery.md');EXPECTED='79c0289293996f02faa6de1ecb5dcc6d6201a7b98bff1be842bab6cc707b547d'
def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def verify()->None:
    p=json.loads(PROTOCOL.read_text());recorded=p.pop('protocol_sha256');assert recorded==EXPECTED and canon(p)==EXPECTED
    assert p['status']=='FROZEN_BEFORE_ANY_V8_MARKET_DATA_ACCESS';assert p['multiple_testing']['v7_result_consulted_before_protocol_freeze'] is False;assert p['multiple_testing']['family_index_after_v3_v4_v5_v6_v7']==6;assert p['trigger_gate']['minimum_sealed_triggers_before_m1']==350;assert p['historical_edge_gate']['minimum_resolved_executed_trades']==350;assert p['historical_edge_gate']['base_profit_factor_gt']==1.4;assert p['historical_edge_gate']['stress_profit_factor_gt']==1.15;assert p['historical_edge_gate']['positive_calendar_year_fraction_gte']==0.8;assert p['forward_confirmation_policy']['historical_pass_alone_is_validated_profitable_edge'] is False;assert p['safety']=={'broker_mutation_authorized':False,'live_execution_authorized':False,'paper_execution_authorized':False}
    b=json.loads(BOUNDARY.read_text());assert b['protocol_sha256']==EXPECTED and b['protocol_commit_sha']=='5c03237b05d2accf97f3f363949056e714388ec9';assert b['v7_result_consulted_before_protocol_freeze'] is False and b['v7_ledger_consulted_for_v8_parameters'] is False
    for key in ['v8_h4_accessed','v8_h1_accessed','v8_m1_accessed','v8_mid_accessed','v8_bid_ask_accessed','v8_triggers_constructed','v8_fills_evaluated','v8_pnl_accessed','v8_expectancy_accessed','v8_profit_factor_accessed','v8_bootstrap_outcomes_accessed','v8_forward_outcomes_accessed','paper_execution','live_execution','broker_mutation']:assert b[key] is False,key
    source=SOURCE.read_text();assert 'remember-where-most-traders-lose/' in source;assert 'the-simple-secret-i-used-to-create-this-trading-plan/' in source
if __name__=='__main__':verify();print('v8_fvg_followthrough_protocol='+EXPECTED);print('v8_pre_market_data_boundary=PASS')
