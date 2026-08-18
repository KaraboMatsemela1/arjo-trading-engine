#!/usr/bin/env python3
from __future__ import annotations
import math
from v6_momentum_backtest_metrics import metrics

def pf_value(m:dict)->float:
    return math.inf if m['no_negative_trades'] and m['positive_r_sum']>0 else float(m['profit_factor'] or 0.0)

def classify(base:dict,stress:dict)->str:
    if base['resolved_executed_trades']<300:return 'INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED'
    lower=base['bootstrap_95pct_ci_net_expectancy_r'][0]
    passed=(base['net_expectancy_r'] is not None and base['net_expectancy_r']>0 and pf_value(base)>1.35 and lower is not None and lower>0 and stress['net_expectancy_r'] is not None and stress['net_expectancy_r']>0 and pf_value(stress)>1.10 and (base['positive_calendar_year_fraction'] or 0)>=0.75 and base['data_integrity_failures']==0 and stress['data_integrity_failures']==0 and base['synthetic_fills']==0 and stress['synthetic_fills']==0)
    return 'V7_CANDLE_SCIENCE_HISTORICAL_EDGE_ESTABLISHED' if passed else 'EDGE_NOT_ESTABLISHED'

__all__=['metrics','classify']
