#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import v7_candle_science_forward_structure as structure
from v7_candle_science_forward_metrics import classify_forward

def metric(resolved=60,expectancy=.10,pf=1.25,lower=.02):return {'resolved_executed_trades':resolved,'net_expectancy_r':expectancy,'profit_factor':pf,'no_negative_trades':False,'positive_r_sum':10.0,'bootstrap_95pct_ci_net_expectancy_r':[lower,.2],'data_integrity_failures':0,'synthetic_fills':0}
def run():
    assert not Path('research/profitability/v7_candle_science_historical_result_v1.json').exists()
    try:structure.require_historical_gate()
    except RuntimeError as exc:assert 'historical result not sealed' in str(exc)
    else:raise AssertionError('V7 forward provider gate opened before historical result')
    base=metric();stress=metric(expectancy=.05,pf=1.10);assert classify_forward(base,stress)=='VALIDATED_PROFITABLE_EDGE_V7_CANDLE_SCIENCE_FORWARD_OOS'
    assert classify_forward(metric(resolved=59),stress)=='FORWARD_INSUFFICIENT_SAMPLE_EDGE_NOT_VALIDATED'
    assert classify_forward(metric(pf=1.15),stress)=='FORWARD_EDGE_NOT_VALIDATED'
    assert classify_forward(base,metric(expectancy=.05,pf=1.05))=='FORWARD_EDGE_NOT_VALIDATED'
    print('v7_forward_preflight=PASS_BLOCKED_BEFORE_HISTORICAL_GATE')
if __name__=='__main__':run()
