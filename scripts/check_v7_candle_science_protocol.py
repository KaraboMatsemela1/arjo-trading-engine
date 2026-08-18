#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
PROTOCOL=Path('research/profitability/v7_candle_science_protocol_v1.json');BOUNDARY=Path('research/profitability/v7_candle_science_preoutcome_boundary_v1.json');SOURCE=Path('research/profitability/v7_candle_science_source_recovery.md');EXPECTED='98ed03185f93643e1c1b326835bee169e1f72a84d00c5a6aa4e56453a2a57134'
def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def verify()->None:
    p=json.loads(PROTOCOL.read_text());recorded=p.pop('protocol_sha256');assert recorded==EXPECTED and canon(p)==EXPECTED
    assert p['status']=='FROZEN_BEFORE_ANY_V7_MARKET_DATA_ACCESS';assert p['multiple_testing']['v6_result_consulted_before_protocol_freeze'] is False;assert p['multiple_testing']['family_index_after_v3_v4_v5_v6']==5;assert p['trigger_gate']['minimum_sealed_triggers_before_m1']==300;assert p['historical_edge_gate']['minimum_resolved_executed_trades']==300;assert p['historical_edge_gate']['base_profit_factor_gt']==1.35;assert p['forward_confirmation_policy']['historical_pass_alone_is_validated_profitable_edge'] is False;assert p['safety']=={'broker_mutation_authorized':False,'live_execution_authorized':False,'paper_execution_authorized':False}
    b=json.loads(BOUNDARY.read_text());assert b['protocol_sha256']==EXPECTED and b['protocol_commit_sha']=='f0f4ede709c59dedeb4f629b48f6383d08a5bd36';assert b['v6_result_consulted_before_protocol_freeze'] is False;assert b['v6_ledger_consulted_for_v7_parameters'] is False
    for key in ['v7_h4_accessed','v7_h1_accessed','v7_m1_accessed','v7_mid_accessed','v7_bid_ask_accessed','v7_triggers_constructed','v7_fills_evaluated','v7_pnl_accessed','v7_expectancy_accessed','v7_profit_factor_accessed','v7_bootstrap_outcomes_accessed','v7_forward_outcomes_accessed','paper_execution','live_execution','broker_mutation']:
        assert b[key] is False,key
    source=SOURCE.read_text()
    for marker in ['candle-science/','increase-your-accuracy-by-doing-less/','this-is-exactly-where-to-place-your-stop-loss/','market-structure-order-flow-candle-science/']:assert marker in source
if __name__=='__main__':verify();print('v7_candle_science_protocol='+EXPECTED);print('v7_pre_market_data_boundary=PASS')
