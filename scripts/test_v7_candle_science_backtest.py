#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
from v7_candle_science_backtest_metrics import classify

def metric(*,resolved=300,expectancy=.20,pf=1.5,lower=.05,positive_years=.80):
    return {'resolved_executed_trades':resolved,'net_expectancy_r':expectancy,'profit_factor':pf,'no_negative_trades':False,'positive_r_sum':100.0,'bootstrap_95pct_ci_net_expectancy_r':[lower,.30],'positive_calendar_year_fraction':positive_years,'data_integrity_failures':0,'synthetic_fills':0}

def run():
    base=metric();stress=metric(expectancy=.08,pf=1.2);assert classify(base,stress)=='V7_CANDLE_SCIENCE_HISTORICAL_EDGE_ESTABLISHED'
    x=deepcopy(base);x['profit_factor']=1.35;assert classify(x,stress)=='EDGE_NOT_ESTABLISHED'
    x=deepcopy(base);x['bootstrap_95pct_ci_net_expectancy_r']=[0.0,.2];assert classify(x,stress)=='EDGE_NOT_ESTABLISHED'
    x=deepcopy(base);x['positive_calendar_year_fraction']=.749;assert classify(x,stress)=='EDGE_NOT_ESTABLISHED'
    x=deepcopy(stress);x['profit_factor']=1.10;assert classify(base,x)=='EDGE_NOT_ESTABLISHED'
    assert classify(metric(resolved=299),stress)=='INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED'
    print('v7_candle_science_backtest_gate_tests=PASS')
if __name__=='__main__':run()
