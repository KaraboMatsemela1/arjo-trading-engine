#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from typing import Any
from v6_momentum_primitives import canon,dtext,parse_time,stamp
UTC=timezone.utc;BASE_URL='https://api-fxpractice.oanda.com';INSTRUMENT='NAS100_USD';START=datetime(2010,1,1,tzinfo=UTC);END=datetime(2024,1,1,tzinfo=UTC);DAILY_ALIGNMENT=17;ALIGNMENT_TIMEZONE='America/New_York';WEEKLY_ALIGNMENT='Friday'

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def norm(v:object)->str:return dtext(Decimal(str(v)))
def request_sha(params:dict[str,str])->str:return canon({'instrument':INSTRUMENT,'params':params})
def chunks(start:datetime,end:datetime,days:int):
    cur=start;step=timedelta(days=days)
    while cur<end:
        nxt=min(cur+step,end);yield cur,nxt;cur=nxt

def request(token:str,granularity:str,start:datetime,end:datetime)->tuple[list[dict[str,Any]],dict[str,Any]]:
    params={'from':stamp(start),'to':stamp(end),'granularity':granularity,'price':'M','smooth':'false','includeFirst':'true','dailyAlignment':str(DAILY_ALIGNMENT),'alignmentTimezone':ALIGNMENT_TIMEZONE,'weeklyAlignment':WEEKLY_ALIGNMENT};url=f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles?{urllib.parse.urlencode(params)}";last=None
    for attempt in range(5):
        req=urllib.request.Request(url,headers={'Authorization':f'Bearer {token}','Accept':'application/json','User-Agent':'arjo-v6-momentum-trigger-seal'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read();doc=json.loads(raw);rows=doc.get('candles')
                if not isinstance(rows,list):raise RuntimeError('OANDA response missing candles')
                return rows,{'granularity':granularity,'from':params['from'],'to':params['to'],'request_sha256':request_sha(params),'response_sha256':sha_bytes(raw),'response_candle_count':len(rows)}
        except urllib.error.HTTPError as e:
            detail=e.read().decode(errors='replace')[:300];last=RuntimeError(f'OANDA HTTP {e.code}: {detail}')
            if e.code not in {429,500,502,503,504}:raise last from e
        except (urllib.error.URLError,TimeoutError) as e:last=e
        if attempt<4:time.sleep(min(2**attempt,8))
    raise RuntimeError(f'OANDA request failed: {last}')

def acquire(token:str,granularity:str,minutes:int,chunk_days:int)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    dur=timedelta(minutes=minutes);by={};provenance=[]
    for a,b in chunks(START,END,chunk_days):
        raw,rec=request(token,granularity,a,b);rec['admitted_candle_count']=0
        for x in raw:
            if x.get('complete') is not True:continue
            mid=x.get('mid')
            if not isinstance(mid,dict):raise RuntimeError('MID payload missing')
            t=parse_time(str(x['time']));ended=t+dur
            if t<START or ended>END:continue
            row={'time':stamp(t),'open':norm(mid['o']),'high':norm(mid['h']),'low':norm(mid['l']),'close':norm(mid['c']),'complete':True,'volume':int(x.get('volume',0))};old=by.get(row['time'])
            if old is not None and old!=row:raise RuntimeError(f'conflicting duplicate {granularity} {row["time"]}')
            if old is None:by[row['time']]=row;rec['admitted_candle_count']+=1
        provenance.append(rec)
    rows=[by[k] for k in sorted(by)]
    if not rows:raise RuntimeError(f'no {granularity} rows')
    return rows,provenance

def acquire_structure()->dict[str,Any]:
    token=os.getenv('OANDA_TOKEN','').strip()
    if not token:raise RuntimeError('OANDA_TOKEN required')
    h1,h1p=acquire(token,'H1',60,120);m15,m15p=acquire(token,'M15',15,30)
    manifest={'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':INSTRUMENT,'price':'M','strict_start':stamp(START),'strict_end_exclusive':stamp(END),'daily_alignment':DAILY_ALIGNMENT,'alignment_timezone':ALIGNMENT_TIMEZONE,'weekly_alignment':WEEKLY_ALIGNMENT,'h1_rows':len(h1),'m15_rows':len(m15),'h1_sha256':canon(h1),'m15_sha256':canon(m15),'h1_provenance_sha256':canon(h1p),'m15_provenance_sha256':canon(m15p),'m1_requested':False,'bid_ask_requested':False,'broker_mutation':False};manifest['manifest_sha256']=canon(manifest)
    return {'h1':h1,'m15':m15,'h1_provenance':h1p,'m15_provenance':m15p,'manifest':manifest}
