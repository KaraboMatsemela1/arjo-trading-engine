#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from typing import Any
UTC=timezone.utc

def parse_time(v:str)->datetime:
    text=v[:-1]+'+00:00' if v.endswith('Z') else v;d=datetime.fromisoformat(text)
    if d.tzinfo is None:raise ValueError('naive timestamp')
    return d.astimezone(UTC)
def stamp(d:datetime)->str:return d.astimezone(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def dec(v:object)->Decimal:return Decimal(str(v))
def dtext(v:Decimal)->str:
    s=format(v,'f')
    if '.' in s:s=s.rstrip('0').rstrip('.')
    return s or '0'
def canon(v:object)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def ident(prefix:str,*parts:object)->str:return prefix+'-'+hashlib.sha256('|'.join([prefix,*map(str,parts)]).encode()).hexdigest()[:24]
def price(c:dict[str,Any],k:str)->Decimal:return dec(c[k])

class ExtremaSearch:
    def __init__(self,candles:list[dict[str,Any]]):
        self.n=len(candles);size=1
        while size<max(1,self.n):size*=2
        self.size=size;neg=Decimal('-Infinity');pos=Decimal('Infinity');self.max_high=[neg]*(2*size);self.min_low=[pos]*(2*size)
        for i,c in enumerate(candles):self.max_high[size+i]=price(c,'high');self.min_low[size+i]=price(c,'low')
        for node in range(size-1,0,-1):self.max_high[node]=max(self.max_high[node*2],self.max_high[node*2+1]);self.min_low[node]=min(self.min_low[node*2],self.min_low[node*2+1])
    def first_high_ge(self,start:int,threshold:Decimal)->int|None:return self._high(1,0,self.size,start,threshold)
    def _high(self,node:int,left:int,right:int,start:int,threshold:Decimal)->int|None:
        if right<=start or left>=self.n or self.max_high[node]<threshold:return None
        if right-left==1:return left
        mid=(left+right)//2;found=self._high(node*2,left,mid,start,threshold)
        return found if found is not None else self._high(node*2+1,mid,right,start,threshold)
    def first_low_le(self,start:int,threshold:Decimal)->int|None:return self._low(1,0,self.size,start,threshold)
    def _low(self,node:int,left:int,right:int,start:int,threshold:Decimal)->int|None:
        if right<=start or left>=self.n or self.min_low[node]>threshold:return None
        if right-left==1:return left
        mid=(left+right)//2;found=self._low(node*2,left,mid,start,threshold)
        return found if found is not None else self._low(node*2+1,mid,right,start,threshold)

def pivots(candles:list[dict[str,Any]],minutes:int,label:str)->list[dict[str,Any]]:
    out=[];dur=timedelta(minutes=minutes)
    for i in range(1,len(candles)-1):
        a,b,c=candles[i-1:i+2];known=parse_time(c['time'])+dur;bt=parse_time(b['time']);bh=price(b,'high');bl=price(b,'low')
        if bh>price(a,'high') and bh>price(c,'high'):out.append({'pivot_id':ident(label+'SH',stamp(bt),dtext(bh),stamp(known)),'kind':'H','price':dtext(bh),'source_time_utc':stamp(bt),'knowledge_time_utc':stamp(known),'source_index':i})
        if bl<price(a,'low') and bl<price(c,'low'):out.append({'pivot_id':ident(label+'SL',stamp(bt),dtext(bl),stamp(known)),'kind':'L','price':dtext(bl),'source_time_utc':stamp(bt),'knowledge_time_utc':stamp(known),'source_index':i})
    out.sort(key=lambda r:(r['source_time_utc'],r['kind'],r['pivot_id']));return out

def intermediate_targets(h1:list[dict[str,Any]])->list[dict[str,Any]]:
    ps=pivots(h1,60,'H1');out=[]
    for kind,name in [('H','ITH'),('L','ITL')]:
        seq=[p for p in ps if p['kind']==kind]
        for i in range(1,len(seq)-1):
            a,b,c=seq[i-1:i+2];ap,bp,cp=dec(a['price']),dec(b['price']),dec(c['price']);ok=(bp>ap and bp>cp) if kind=='H' else (bp<ap and bp<cp)
            if not ok:continue
            known=parse_time(c['knowledge_time_utc']);out.append({'target_id':ident(name,b['pivot_id'],c['pivot_id'],stamp(known)),'kind':name,'price':b['price'],'source_time_utc':b['source_time_utc'],'knowledge_time_utc':stamp(known),'knowledge_h1_index':c['source_index']+1})
    out.sort(key=lambda r:(r['knowledge_time_utc'],r['kind'],dec(r['price']),r['target_id']));return out

def attach_first_retouch(targets:list[dict[str,Any]],h1:list[dict[str,Any]])->list[dict[str,Any]]:
    tree=ExtremaSearch(h1);out=[]
    for target in targets:
        row=dict(target);start=int(row['knowledge_h1_index'])+1;threshold=dec(row['price']);row['first_retouch_h1_index']=tree.first_high_ge(start,threshold) if row['kind']=='ITH' else tree.first_low_le(start,threshold);out.append(row)
    return out

def h1_fvgs(h1:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for i in range(2,len(h1)):
        c1,c3=h1[i-2],h1[i];known=parse_time(c3['time'])+timedelta(hours=1)
        if price(c1,'high')<price(c3,'low'):lo,hi,direction=price(c1,'high'),price(c3,'low'),'BULL'
        elif price(c1,'low')>price(c3,'high'):lo,hi,direction=price(c3,'high'),price(c1,'low'),'BEAR'
        else:continue
        out.append({'fvg_id':ident('H1FVG',direction,c1['time'],c3['time'],dtext(lo),dtext(hi)),'direction':direction,'lower':dtext(lo),'upper':dtext(hi),'c3_index':i,'knowledge_time_utc':stamp(known),'c3_close':dtext(price(c3,'close'))})
    return out

def select_target(targets:list[dict[str,Any]],direction:str,at:datetime,context_i:int,px:Decimal)->dict[str,Any]|None:
    kind='ITH' if direction=='LONG' else 'ITL';eligible=[]
    for target in targets:
        if target['kind']!=kind or parse_time(target['knowledge_time_utc'])>at:continue
        tp=dec(target['price']);directional=(direction=='LONG' and tp>px) or (direction=='SHORT' and tp<px);retouch=target['first_retouch_h1_index']
        if directional and (retouch is None or int(retouch)>context_i):eligible.append(target)
    if not eligible:return None
    return min(eligible,key=lambda x:(dec(x['price']),x['knowledge_time_utc'],x['target_id'])) if direction=='LONG' else max(eligible,key=lambda x:(dec(x['price']),x['knowledge_time_utc'],x['target_id']))

def cycles(h1:list[dict[str,Any]])->list[dict[str,Any]]:
    fvgs=h1_fvgs(h1);targets=attach_first_retouch(intermediate_targets(h1),h1);out=[]
    for j in range(1,len(fvgs)):
        prev,opp=fvgs[j-1],fvgs[j]
        if prev['direction']==opp['direction']:continue
        direction='LONG' if prev['direction']=='BULL' else 'SHORT';target=select_target(targets,direction,parse_time(prev['knowledge_time_utc']),prev['c3_index'],dec(prev['c3_close']))
        if target is None:continue
        retouch=target['first_retouch_h1_index']
        if retouch is not None and int(retouch)<=opp['c3_index']:continue
        deadline_i=opp['c3_index']+120
        if deadline_i>=len(h1):continue
        deadline=parse_time(h1[deadline_i]['time'])+timedelta(hours=1)
        clean_target={k:v for k,v in target.items() if k!='first_retouch_h1_index'}
        out.append({'cycle_id':ident('V6CYCLE',direction,prev['fvg_id'],opp['fvg_id'],target['target_id']),'direction':direction,'context_fvg_id':prev['fvg_id'],'context_known_at_utc':prev['knowledge_time_utc'],'disturbance_fvg_id':opp['fvg_id'],'disturbance_known_at_utc':opp['knowledge_time_utc'],'deadline_utc':stamp(deadline),'target':clean_target})
    return out
