#!/usr/bin/env python3
from __future__ import annotations
import json,os
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
import v6_momentum_structure as provider
from v7_candle_science_primitives import canon,dtext,parse_time,stamp
UTC=timezone.utc;START=datetime(2024,1,1,tzinfo=UTC);END=datetime(2026,8,1,tzinfo=UTC);HISTORICAL=Path('research/profitability/v7_candle_science_historical_result_v1.json');PROTOCOL='98ed03185f93643e1c1b326835bee169e1f72a84d00c5a6aa4e56453a2a57134';TRANSPORT='83bdd46c80acec241499d5d99e76df22b8c11cdf4edd5983b4f4937582fdbc8e'
def require_historical_gate()->dict[str,Any]:
    if not HISTORICAL.exists():raise RuntimeError('V7 forward structure access blocked: historical result not sealed')
    result=json.loads(HISTORICAL.read_text())
    if result.get('classification')!='V7_CANDLE_SCIENCE_HISTORICAL_EDGE_ESTABLISHED' or result.get('historical_edge_established') is not True or result.get('forward_confirmation_authorized') is not True:raise RuntimeError('V7 forward structure access blocked: historical gate did not pass')
    if result.get('validated_profitable_edge') is not False:raise RuntimeError('V7 historical result illegally claimed validation')
    if result.get('protocol_sha256')!=PROTOCOL or result.get('forward_confirmation_transport_sha256')!=TRANSPORT:raise RuntimeError('V7 forward structure immutable binding mismatch')
    return result
def chunks(days:int):
    cur=START;step=timedelta(days=days)
    while cur<END:nxt=min(cur+step,END);yield cur,nxt;cur=nxt
def acquire_component(token:str,granularity:str,minutes:int,chunk_days:int):
    duration=timedelta(minutes=minutes);by={};provenance=[]
    for a,b in chunks(chunk_days):
        raw,record=provider.request(token,granularity,a,b);record['admitted_candle_count']=0
        for item in raw:
            if item.get('complete') is not True:continue
            mid=item.get('mid')
            if not isinstance(mid,dict):raise RuntimeError('forward MID component missing')
            t=parse_time(str(item['time']));ended=t+duration
            if t<START or ended>END:continue
            row={'time':stamp(t),'open':dtext(Decimal(str(mid['o']))),'high':dtext(Decimal(str(mid['h']))),'low':dtext(Decimal(str(mid['l']))),'close':dtext(Decimal(str(mid['c']))),'complete':True,'volume':int(item.get('volume',0))};old=by.get(row['time'])
            if old is not None and old!=row:raise RuntimeError(f'conflicting forward {granularity} duplicate {row["time"]}')
            if old is None:by[row['time']]=row;record['admitted_candle_count']+=1
        provenance.append(record)
    rows=[by[key] for key in sorted(by)]
    if not rows:raise RuntimeError(f'no forward {granularity} rows')
    return rows,provenance
def acquire_forward_structure()->dict[str,Any]:
    historical=require_historical_gate();token=os.getenv('OANDA_TOKEN','').strip()
    if not token:raise RuntimeError('OANDA_TOKEN required for authorized V7 forward structure access')
    h4,h4p=acquire_component(token,'H4',240,120);h1,h1p=acquire_component(token,'H1',60,60)
    manifest={'schema_version':1,'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'M','granularities':['H4','H1'],'start_inclusive':stamp(START),'end_exclusive':stamp(END),'daily_alignment':17,'alignment_timezone':'America/New_York','weekly_alignment':'Friday','protocol_sha256':PROTOCOL,'forward_transport_sha256':TRANSPORT,'historical_result_sha256':historical['result_sha256'],'h4_rows':len(h4),'h1_rows':len(h1),'h4_sha256':canon(h4),'h1_sha256':canon(h1),'h4_provenance_sha256':canon(h4p),'h1_provenance_sha256':canon(h1p),'m1_requested':False,'bid_ask_requested':False,'economic_outcomes_accessed':False,'paper_execution':False,'live_execution':False,'broker_mutation':False};manifest['manifest_sha256']=canon(manifest);return {'h4':h4,'h1':h1,'h4_provenance':h4p,'h1_provenance':h1p,'manifest':manifest}
