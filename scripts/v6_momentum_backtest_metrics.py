#!/usr/bin/env python3
from __future__ import annotations
import math,random,statistics
from collections import Counter,defaultdict
from v6_momentum_backtest_mechanics import RESOLVED,canon,ts

def _profit_factor(values:list[float]):
    positive=sum(x for x in values if x>0);negative=sum(x for x in values if x<0)
    if negative==0:return (math.inf if positive>0 else 0.0),True,positive,negative
    return positive/abs(negative),False,positive,negative

def _max_drawdown(values:list[float])->float:
    equity=peak=worst=0.0
    for value in values:
        equity+=value;peak=max(peak,equity);worst=max(worst,peak-equity)
    return worst

def _bootstrap(values:list[float],replicates:int=10000,seed:int=20260818):
    if not values:return None,None
    rng=random.Random(seed);n=len(values);means=[sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(replicates)];means.sort();return means[int(.025*(replicates-1))],means[int(.975*(replicates-1))]

def metrics(portfolio:dict)->dict:
    ledger=portfolio['ledger'];resolved=[row for row in ledger if row['status'] in RESOLVED];values=[float(row['net_r']) for row in resolved];pf,no_losses,positive,negative=_profit_factor(values);years=defaultdict(list);directions=defaultdict(list)
    for row in resolved:
        years[str(ts(row['entry_ts_utc']).year)].append(float(row['net_r']));directions[row['direction']].append(float(row['net_r']))
    year_exp={year:sum(vals)/len(vals) for year,vals in sorted(years.items())};lo,hi=_bootstrap(values);statuses=dict(sorted(Counter(row['status'] for row in ledger).items()))
    out={'scenario':portfolio['scenario'],'ledger_sha256':portfolio['ledger_sha256'],'resolved_executed_trades':len(resolved),'total_ledger_rows':len(ledger),'status_counts':statuses,'data_integrity_failures':statuses.get('DATA_INTEGRITY_FAILURE',0),'synthetic_fills':0,'skipped_duplicate_signals':statuses.get('SKIPPED_DUPLICATE_KNOWLEDGE_TIME',0),'skipped_concurrent_signals':statuses.get('SKIPPED_CONCURRENT_POSITION',0),'invalid_risk_signals':statuses.get('INVALID_RISK_OR_TARGET_ORDERING',0),'right_censored_signals':statuses.get('RIGHT_CENSORED_HISTORICAL_END',0),'net_expectancy_r':sum(values)/len(values) if values else None,'median_net_r':statistics.median(values) if values else None,'profit_factor':None if math.isinf(pf) else pf,'no_negative_trades':no_losses,'positive_r_sum':positive,'negative_r_sum':negative,'win_rate':sum(1 for x in values if x>0)/len(values) if values else None,'max_drawdown_r':_max_drawdown(values),'bootstrap_95pct_ci_net_expectancy_r':[lo,hi],'calendar_year_net_expectancy_r':year_exp,'positive_calendar_year_fraction':sum(1 for x in year_exp.values() if x>0)/len(year_exp) if year_exp else None,'direction_net_expectancy_r':{direction:sum(vals)/len(vals) for direction,vals in sorted(directions.items())},'unique_entry_dates':len({row['entry_ts_utc'][:10] for row in resolved})};out['metrics_sha256']=canon(out);return out

def pf_value(m:dict)->float:return math.inf if m['no_negative_trades'] and m['positive_r_sum']>0 else float(m['profit_factor'] or 0.0)
def classify(base:dict,stress:dict)->str:
    if base['resolved_executed_trades']<250:return 'INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED'
    lower=base['bootstrap_95pct_ci_net_expectancy_r'][0]
    passed=(base['net_expectancy_r'] is not None and base['net_expectancy_r']>0 and pf_value(base)>1.30 and lower is not None and lower>0 and stress['net_expectancy_r'] is not None and stress['net_expectancy_r']>0 and pf_value(stress)>1.05 and (base['positive_calendar_year_fraction'] or 0)>=.70 and base['data_integrity_failures']==0 and stress['data_integrity_failures']==0 and base['synthetic_fills']==0 and stress['synthetic_fills']==0)
    return 'V6_MOMENTUM_HISTORICAL_EDGE_ESTABLISHED' if passed else 'EDGE_NOT_ESTABLISHED'
