#!/usr/bin/env python3
from pathlib import Path
import v6_momentum_forward_structure as structure
from v6_momentum_forward_metrics import classify_forward

def run():
    assert not Path('research/profitability/v6_momentum_historical_result_v1.json').exists()
    try:structure.require_historical_gate()
    except RuntimeError as exc:assert 'historical result not sealed' in str(exc)
    else:raise AssertionError('forward structure gate opened without historical result')
    empty={'resolved_executed_trades':0,'net_expectancy_r':None,'profit_factor':None,'no_negative_trades':False,'positive_r_sum':0.0,'bootstrap_95pct_ci_net_expectancy_r':[None,None],'data_integrity_failures':0,'synthetic_fills':0}
    assert classify_forward(empty,empty)=='FORWARD_INSUFFICIENT_SAMPLE_EDGE_NOT_VALIDATED'
    print('v6_forward_preflight=PASS_BLOCKED_BEFORE_HISTORICAL_GATE')
if __name__=='__main__':run()
