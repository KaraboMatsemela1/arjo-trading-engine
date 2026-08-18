#!/usr/bin/env python3
from __future__ import annotations
import json,os
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
import v6_momentum_structure as historical
from v6_momentum_primitives import canon,dtext,parse_time,stamp
UTC=timezone.utc;START=datetime(2024,1,1,tzinfo=UTC);END=datetime(2026,8,1,tzinfo=UTC);HISTORICAL_RESULT=Path('research/profitability/v6_momentum_historical_result_v1.json');PROTOCOL_SHA='8a4839f9c9c07bec97aa78fe57ea246e8c256ad88c458ce9bf37b9f5b1b892ab';FORWARD_SHA='24bbcc1c31f1469c45ca70cffdf1fafb4821cada857c9ab04233d90bca601ce6'

def require_historical_gate()->dict[str,Any]:
    if not HISTORICAL_RESULT.exists():raise RuntimeError('V6 forward structure access blocked: historical result not sealed')
    r=json.loads(HISTORICAL_RESULT.read_text())
    if r.get('classification')!='V6_MOMENTUM_HISTORICAL_EDGE_ESTABLISHED' or r.get('historical_edge_established') is not True or r.get('forward_confirmation_authorized') is not True:raise RuntimeError('V6 forward structure access blocked: historical gate did not pass')
    if r.get('protocol_sha256')!=PROTOCOL_SHA or r.get('forward_confirmation_transport_sha256')!=FORWARD_SHA:raise RuntimeError('V6 forward structure access blocked: immutable binding mismatch')
    if r.get('validated_profitable_edge') is not False:raise RuntimeError('historical result illegally claimed validation')
    return r

def bounds(days:int):
    cur=START;step=timedelta(days=days)
    while cur<END:
        nxt=min(cur+step,END);yield cur,nxt;cur=nxt

def acquire_component(token:str,granularity:str,minutes:int,chunk_days:int):
    duration=timedelta(minutes=minutes);by={};provenance=[]
    for a,b in bounds(chunk_days):
        raw,record=historical.request(token,granularity,a,b);record['admitted_candle_count']=0
        for item in raw:
            if item.get('complete') is not True:continue
            mid=item.get('mid')
            if not isinstance(mid,dict):raise RuntimeError('forward MID payload missing')
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
    historical_result=require_historical_gate();token=os.getenv('OANDA_TOKEN','').strip()
    if not token:raise RuntimeError('OANDA_TOKEN required for authorized V6 forward structure read')
    h1,h1p=acquire_component(token,'H1',60,120);m15,m15p=acquire_component(token,'M15',15,30)
    manifest={'schema_version':1,'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'M','start_inclusive':stamp(START),'end_exclusive':stamp(END),'daily_alignment':17,'alignment_timezone':'America/New_York','weekly_alignment':'Friday','protocol_sha256':PROTOCOL_SHA,'forward_transport_sha256':FORWARD_SHA,'historical_result_sha256':historical_result['result_sha256'],'h1_rows':len(h1),'m15_rows':len(m15),'h1_sha256':canon(h1),'m15_sha256':canon(m15),'h1_provenance_sha256':canon(h1p),'m15_provenance_sha256':canon(m15p),'m1_requested':False,'bid_ask_requested':False,'economic_outcomes_accessed':False,'broker_mutation':False};manifest['manifest_sha256']=canon(manifest);return {'h1':h1,'m15':m15,'h1_provenance':h1p,'m15_provenance':m15p,'manifest':manifest}
