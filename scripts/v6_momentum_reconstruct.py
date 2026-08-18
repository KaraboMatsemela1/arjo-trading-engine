#!/usr/bin/env python3
from __future__ import annotations
from bisect import bisect_left
from datetime import timedelta
from typing import Any
from v6_momentum_primitives import canon,cycles,dec,dtext,ident,parse_time,pivots,price,stamp

def qualifies(win:list[dict[str,Any]],direction:str)->bool:
    expected='HLHLHL' if direction=='LONG' else 'LHLHLH'
    if ''.join(p['kind'] for p in win)!=expected:return False
    v=[dec(p['price']) for p in win]
    if direction=='LONG':
        h1,l1,h2,l2,h3,l3=v
        return h2>h1 and h3>h2 and l2>l1 and l3>l2 and (h3-l3)<(h2-l2)<(h1-l1) and h1>l1 and h2>l2 and h3>l3
    l1,h1,l2,h2,l3,h3=v
    return l2<l1 and l3<l2 and h2<h1 and h3<h2 and (h3-l3)<(h2-l2)<(h1-l1) and h1>l1 and h2>l2 and h3>l3

def target_touch(bar:dict[str,Any],target,direction:str)->bool:return price(bar,'high')>=target if direction=='LONG' else price(bar,'low')<=target

def record(cyc:dict[str,Any],win:list[dict[str,Any]],bar:dict[str,Any],known)->dict[str,Any]:
    direction=cyc['direction'];target=cyc['target'];tp=dec(target['price']);stop=dec(win[-1]['price'])
    return {'trigger_id':ident('V6TRG',direction,cyc['cycle_id'],*(p['pivot_id'] for p in win),stamp(known),dtext(stop),dtext(tp)),'direction':direction,'knowledge_time_utc':stamp(known),'trigger_m15_start_utc':bar['time'],'trigger_close':dtext(price(bar,'close')),'stop_anchor':dtext(stop),'target_price':dtext(tp),'target_id':target['target_id'],'target_known_at_utc':target['knowledge_time_utc'],'cycle_id':cyc['cycle_id'],'context_fvg_id':cyc['context_fvg_id'],'context_known_at_utc':cyc['context_known_at_utc'],'disturbance_fvg_id':cyc['disturbance_fvg_id'],'disturbance_known_at_utc':cyc['disturbance_known_at_utc'],'deadline_utc':cyc['deadline_utc'],'pattern_pivot_ids':[p['pivot_id'] for p in win],'pattern_prices':[p['price'] for p in win]}

def _reconstruct(h1:list[dict[str,Any]],m15:list[dict[str,Any]],reference:bool)->tuple[list[dict[str,Any]],dict[str,int]]:
    cs=cycles(h1);ps=pivots(m15,15,'M15');pk=[parse_time(p['knowledge_time_utc']) for p in ps];bk=[parse_time(b['time']) for b in m15];out=[];stats={'cycles':len(cs),'patterns':0,'target_touched_before_trigger':0,'signals':0}
    for cyc in cs:
        start=parse_time(cyc['disturbance_known_at_utc']);deadline=parse_time(cyc['deadline_utc']);direction=cyc['direction'];target=dec(cyc['target']['price'])
        left=bisect_left(pk,start)
        while left<len(pk) and pk[left]<=start:left+=1
        right=bisect_left(pk,deadline+timedelta(microseconds=1));rel=ps[left:right];win=None
        for i in range(5,len(rel)):
            candidate=rel[i-5:i+1]
            if qualifies(candidate,direction):win=candidate;break
        if win is None:continue
        stats['patterns']+=1;known_after=parse_time(win[-1]['knowledge_time_utc']);bi=bisect_left(bk,known_after)
        if reference:
            bar_iter=m15[bi:]
        else:
            bar_iter=(m15[i] for i in range(bi,len(m15)))
        for bar in bar_iter:
            bt=parse_time(bar['time']);known=bt+timedelta(minutes=15)
            if known>deadline:break
            if target_touch(bar,target,direction):stats['target_touched_before_trigger']+=1;break
            close=price(bar,'close');break_level=dec(win[-2]['price']);fires=close>break_level if direction=='LONG' else close<break_level;before_target=close<target if direction=='LONG' else close>target
            if fires and before_target:out.append(record(cyc,win,bar,known));break
    out.sort(key=lambda r:(r['knowledge_time_utc'],r['trigger_id']));stats['signals']=len(out);return out,stats

def reconstruct_primary(h1:list[dict[str,Any]],m15:list[dict[str,Any]]):return _reconstruct(h1,m15,False)
def reconstruct_reference(h1:list[dict[str,Any]],m15:list[dict[str,Any]]):return _reconstruct(h1,m15,True)
def compare_reconstructions(h1:list[dict[str,Any]],m15:list[dict[str,Any]]):
    primary,ps=reconstruct_primary(h1,m15);reference,rs=reconstruct_reference(h1,m15);ph,rh=canon(primary),canon(reference)
    if primary!=reference:raise RuntimeError(f'independent V6 reconstruction mismatch primary={ph} reference={rh}')
    return primary,{'exact_match':True,'primary_sha256':ph,'reference_sha256':rh,'primary_stats':ps,'reference_stats':rs}
