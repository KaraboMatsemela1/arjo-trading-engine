#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
from typing import Any
from v6_momentum_backtest_mechanics import canon,ts
UTC=timezone.utc;BASE_URL='https://api-fxpractice.oanda.com';INSTRUMENT='NAS100_USD';ORIGIN=datetime(2010,1,1,tzinfo=UTC);END=datetime(2024,1,1,tzinfo=UTC);CHUNK=timedelta(days=3)

def stamp(d:datetime)->str:return d.astimezone(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def dec(v:object,label:str)->Decimal:
    try:x=Decimal(str(v))
    except (InvalidOperation,ValueError) as exc:raise RuntimeError(f'invalid decimal {label}') from exc
    if not x.is_finite():raise RuntimeError(f'nonfinite decimal {label}')
    return x

def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

class M1Cache:
    def __init__(self,root:Path,token:str):
        if not token:raise RuntimeError('OANDA token missing')
        self.root=root;root.mkdir(parents=True,exist_ok=True);self.token=token;self.meta:dict[int,dict[str,Any]]={};self.first_response_accessed=False
    def index(self,d:datetime)->int:return max(0,int((d-ORIGIN).total_seconds()//CHUNK.total_seconds()))
    def bounds(self,i:int):
        a=ORIGIN+i*CHUNK;return a,min(a+CHUNK,END)
    def path(self,i:int)->Path:return self.root/f'm1-{i:05d}.jsonl'
    def _request(self,a:datetime,b:datetime)->tuple[bytes,str]:
        params={'from':stamp(a),'to':stamp(b),'granularity':'M1','price':'BA','smooth':'false','includeFirst':'true'};redacted={'instrument':INSTRUMENT,'params':params};request_sha=canon(redacted);url=f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles?{urllib.parse.urlencode(params)}";last=None
        for attempt in range(5):
            req=urllib.request.Request(url,headers={'Authorization':f'Bearer {self.token}','Accept':'application/json','Accept-Datetime-Format':'RFC3339','User-Agent':'arjo-v6-historical-economics'})
            try:
                with urllib.request.urlopen(req,timeout=60) as response:return response.read(),request_sha
            except urllib.error.HTTPError as exc:
                detail=exc.read().decode(errors='replace')[:300];last=RuntimeError(f'OANDA M1 HTTP {exc.code}: {detail}')
                if exc.code not in {429,500,502,503,504}:raise last from exc
            except (urllib.error.URLError,TimeoutError) as exc:last=exc
            if attempt<4:time.sleep(min(2**attempt,8))
        raise RuntimeError(f'OANDA M1 request failed: {last}')
    def _parse(self,payload:bytes,a:datetime,b:datetime)->list[dict[str,Any]]:
        doc=json.loads(payload);rows=[];prior=None
        if doc.get('instrument')!=INSTRUMENT or doc.get('granularity')!='M1':raise RuntimeError('M1 provider identity mismatch')
        for raw in doc.get('candles',[]):
            if raw.get('complete') is not True:continue
            t=ts(str(raw.get('time')))
            if not (a<=t<b):continue
            if not (ORIGIN<=t<END):raise RuntimeError('M1 row outside historical window')
            if prior is not None and t<=prior:raise RuntimeError('M1 provider order violation')
            prior=t;row={'ts_start_utc':stamp(t)}
            for component in ('bid','ask'):
                payload_component=raw.get(component)
                if not isinstance(payload_component,dict):raise RuntimeError(f'missing {component} component')
                o,h,l,c=(dec(payload_component.get(key),f'{component}.{key}') for key in ('o','h','l','c'))
                if h<max(o,c) or l>min(o,c) or h<l:raise RuntimeError(f'invalid {component} envelope')
                row[component]={'o':str(o),'h':str(h),'l':str(l),'c':str(c)}
            rows.append(row)
        return rows
    def chunk(self,i:int)->list[dict[str,Any]]:
        a,b=self.bounds(i)
        if a>=END:return []
        path=self.path(i)
        if not path.exists():
            payload,request_sha=self._request(a,b);self.first_response_accessed=True;rows=self._parse(payload,a,b)
            with path.open('w') as f:
                for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
            self.meta[i]={'chunk_index':i,'from':stamp(a),'to_exclusive':stamp(b),'request_sha256':request_sha,'raw_response_sha256':hashlib.sha256(payload).hexdigest(),'raw_bytes':len(payload),'complete_m1_rows':len(rows),'parsed_sha256':file_sha(path)}
        else:rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        return rows
    def get_bars(self,start:datetime,count:int)->list[dict[str,Any]]:
        if start>=END:return []
        i=self.index(start);by_time={};empty_run=0
        while len(by_time)<count:
            a,_=self.bounds(i)
            if a>=END:break
            rows=self.chunk(i);empty_run=empty_run+1 if not rows else 0
            for row in rows:
                t=ts(row['ts_start_utc'])
                if t<start:continue
                old=by_time.get(row['ts_start_utc'])
                if old is not None and old!=row:raise RuntimeError(f'conflicting duplicate M1 {row["ts_start_utc"]}')
                by_time[row['ts_start_utc']]=row
            i+=1
            if empty_run>10 and not by_time:break
        return [by_time[key] for key in sorted(by_time)][:count]
    def provenance(self)->dict[str,Any]:
        chunks=[self.meta[key] for key in sorted(self.meta)];out={'schema_version':1,'provider':'OANDA_V20','environment':'practice','instrument':INSTRUMENT,'granularity':'M1','price_components':'BA','chunk_calendar_days':3,'origin':stamp(ORIGIN),'end_exclusive':stamp(END),'chunks_requested':len(chunks),'chunks':chunks,'first_m1_response_accessed':self.first_response_accessed,'credentials_exposed':False,'mutation_endpoints_used':False,'synthetic_candles':False,'synthetic_fills':False};out['provenance_sha256']=canon(out);return out
