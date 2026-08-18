#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from bisect import bisect_right
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from typing import Any
UTC=timezone.utc

def parse_time(value:str)->datetime:
    text=value[:-1]+'+00:00' if value.endswith('Z') else value;d=datetime.fromisoformat(text)
    if d.tzinfo is None:raise ValueError('naive timestamp')
    return d.astimezone(UTC)
def stamp(value:datetime)->str:return value.astimezone(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def dec(value:object)->Decimal:return Decimal(str(value))
def dtext(value:Decimal)->str:
    text=format(value,'f')
    if '.' in text:text=text.rstrip('0').rstrip('.')
    return text or '0'
def canon(value:object)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def ident(prefix:str,*parts:object)->str:return prefix+'-'+hashlib.sha256('|'.join([prefix,*map(str,parts)]).encode()).hexdigest()[:24]
def price(candle:dict[str,Any],field:str)->Decimal:return dec(candle[field])

def h4_swings(candles:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for i in range(1,len(candles)-1):
        left,middle,right=candles[i-1:i+2];known=parse_time(right['time'])+timedelta(hours=4);source=parse_time(middle['time']);high=price(middle,'high');low=price(middle,'low')
        if high>price(left,'high') and high>price(right,'high'):out.append({'swing_id':ident('V7H4SH',stamp(source),dtext(high),stamp(known)),'kind':'H','price':dtext(high),'source_time_utc':stamp(source),'knowledge_time_utc':stamp(known),'source_index':i})
        if low<price(left,'low') and low<price(right,'low'):out.append({'swing_id':ident('V7H4SL',stamp(source),dtext(low),stamp(known)),'kind':'L','price':dtext(low),'source_time_utc':stamp(source),'knowledge_time_utc':stamp(known),'source_index':i})
    return sorted(out,key=lambda r:(r['knowledge_time_utc'],r['kind'],r['swing_id']))

def h4_break_events(candles:list[dict[str,Any]])->list[dict[str,Any]]:
    swings=h4_swings(candles);by_kind={'H':[],'L':[]}
    for swing in swings:by_kind[swing['kind']].append(swing)
    pointers={'H':0,'L':0};latest={'H':None,'L':None};broken=set();events=[]
    for index,candle in enumerate(candles):
        known=parse_time(candle['time'])+timedelta(hours=4)
        for kind in ('H','L'):
            seq=by_kind[kind]
            while pointers[kind]<len(seq) and parse_time(seq[pointers[kind]]['knowledge_time_utc'])<=known:
                latest[kind]=seq[pointers[kind]];pointers[kind]+=1
        close=price(candle,'close');high=latest['H'];low=latest['L']
        if high is not None and high['swing_id'] not in broken and close>dec(high['price']):
            broken.add(high['swing_id']);events.append({'event_id':ident('V7BOS','BULL',high['swing_id'],stamp(known)),'direction':'BULL','knowledge_time_utc':stamp(known),'h4_index':index,'broken_swing_id':high['swing_id'],'broken_level':high['price'],'close':dtext(close)})
        if low is not None and low['swing_id'] not in broken and close<dec(low['price']):
            broken.add(low['swing_id']);events.append({'event_id':ident('V7BOS','BEAR',low['swing_id'],stamp(known)),'direction':'BEAR','knowledge_time_utc':stamp(known),'h4_index':index,'broken_swing_id':low['swing_id'],'broken_level':low['price'],'close':dtext(close)})
    return sorted(events,key=lambda r:(r['knowledge_time_utc'],r['event_id']))

class BiasIndex:
    def __init__(self,events:list[dict[str,Any]]):self.events=events;self.times=[parse_time(row['knowledge_time_utc']) for row in events]
    def at(self,knowledge:datetime)->dict[str,Any]|None:
        i=bisect_right(self.times,knowledge)-1;return None if i<0 else self.events[i]
    def preserved(self,start:datetime,end:datetime,direction:str)->bool:
        left=bisect_right(self.times,start);right=bisect_right(self.times,end)
        return all(self.events[i]['direction']==direction for i in range(left,right))

def h1_fvgs(candles:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for i in range(2,len(candles)):
        c1,c3=candles[i-2],candles[i];known=parse_time(c3['time'])+timedelta(hours=1)
        if price(c1,'high')<price(c3,'low'):lower,upper,direction=price(c1,'high'),price(c3,'low'),'BULL'
        elif price(c1,'low')>price(c3,'high'):lower,upper,direction=price(c3,'high'),price(c1,'low'),'BEAR'
        else:continue
        out.append({'fvg_id':ident('V7H1FVG',direction,c1['time'],c3['time'],dtext(lower),dtext(upper)),'direction':direction,'lower':dtext(lower),'upper':dtext(upper),'c3_index':i,'knowledge_time_utc':stamp(known)})
    return out

class FirstTouchIndex:
    def __init__(self,candles:list[dict[str,Any]]):
        self.candles=candles;self.n=len(candles);size=1
        while size<max(1,self.n):size*=2
        self.size=size;neg=Decimal('-Infinity');pos=Decimal('Infinity');self.max_high=[neg]*(2*size);self.min_low=[pos]*(2*size)
        for i,candle in enumerate(candles):self.max_high[size+i]=price(candle,'high');self.min_low[size+i]=price(candle,'low')
        for node in range(size-1,0,-1):self.max_high[node]=max(self.max_high[node*2],self.max_high[node*2+1]);self.min_low[node]=min(self.min_low[node*2],self.min_low[node*2+1])
    def first_intersection(self,start:int,lower:Decimal,upper:Decimal)->int|None:return self._first(1,0,self.size,start,lower,upper)
    def _first(self,node:int,left:int,right:int,start:int,lower:Decimal,upper:Decimal)->int|None:
        if right<=start or left>=self.n or self.max_high[node]<lower or self.min_low[node]>upper:return None
        if right-left==1:
            candle=self.candles[left]
            return left if price(candle,'high')>=lower and price(candle,'low')<=upper else None
        middle=(left+right)//2;found=self._first(node*2,left,middle,start,lower,upper)
        return found if found is not None else self._first(node*2+1,middle,right,start,lower,upper)

def attach_first_retouch(fvgs:list[dict[str,Any]],candles:list[dict[str,Any]])->list[dict[str,Any]]:
    tree=FirstTouchIndex(candles);out=[]
    for fvg in fvgs:
        row=dict(fvg);row['first_retouch_h1_index']=tree.first_intersection(int(row['c3_index'])+1,dec(row['lower']),dec(row['upper']));out.append(row)
    return out

def intersects(candle:dict[str,Any],fvg:dict[str,Any])->bool:return price(candle,'high')>=dec(fvg['lower']) and price(candle,'low')<=dec(fvg['upper'])
