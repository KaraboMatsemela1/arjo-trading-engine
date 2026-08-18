#!/usr/bin/env python3
from __future__ import annotations
from bisect import bisect_left,bisect_right
from datetime import timedelta
from typing import Any
from v7_candle_science_primitives import BiasIndex,FirstTouchIndex,canon,dec,h1_fvgs,h4_break_events,ident,parse_time,price,stamp


def h1_swing_targets(h1:list[dict[str,Any]])->list[dict[str,Any]]:
    touch=FirstTouchIndex(h1);out=[]
    for i in range(1,len(h1)-1):
        left,middle,right=h1[i-1:i+2];known=parse_time(right['time'])+timedelta(hours=1)
        high=price(middle,'high');low=price(middle,'low')
        if high>price(left,'high') and high>price(right,'high'):
            out.append({'target_id':ident('V8H1SH',middle['time'],str(high),stamp(known)),'kind':'H','price':str(high),'source_index':i,'knowledge_h1_index':i+1,'knowledge_time_utc':stamp(known),'first_retouch_h1_index':touch.first_intersection(i+2,high,high)})
        if low<price(left,'low') and low<price(right,'low'):
            out.append({'target_id':ident('V8H1SL',middle['time'],str(low),stamp(known)),'kind':'L','price':str(low),'source_index':i,'knowledge_h1_index':i+1,'knowledge_time_utc':stamp(known),'first_retouch_h1_index':touch.first_intersection(i+2,low,low)})
    return sorted(out,key=lambda row:(row['knowledge_time_utc'],row['kind'],dec(row['price']),row['target_id']))


def followthrough_candidates(h4:list[dict[str,Any]],h1:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]],dict[str,int]]:
    bias=BiasIndex(h4_break_events(h4));fvgs=h1_fvgs(h1);out=[];stats={'h1_fvgs':len(fvgs),'aligned_A':0,'same_direction_B':0,'opposite_direction_B':0,'no_B_within_12':0,'bias_changed_before_B':0}
    for i,a in enumerate(fvgs):
        a_known=parse_time(a['knowledge_time_utc']);event=bias.at(a_known)
        if event is None or event['direction']!=a['direction']:continue
        stats['aligned_A']+=1;deadline=int(a['c3_index'])+12;b=None
        for candidate in fvgs[i+1:]:
            if int(candidate['c3_index'])<=int(a['c3_index']):continue
            if int(candidate['c3_index'])>deadline:break
            b=candidate;break
        if b is None:stats['no_B_within_12']+=1;continue
        b_known=parse_time(b['knowledge_time_utc'])
        if not bias.preserved(a_known,b_known,a['direction']):stats['bias_changed_before_B']+=1;continue
        if b['direction']!=a['direction']:stats['opposite_direction_B']+=1;continue
        stats['same_direction_B']+=1;trigger_close=str(price(h1[int(b['c3_index'])],'close'))
        out.append({'A':a,'B':b,'direction':'LONG' if a['direction']=='BULL' else 'SHORT','knowledge_time_utc':b['knowledge_time_utc'],'trigger_close':trigger_close,'bias_event_id':event['event_id'],'B_h1_index':int(b['c3_index'])})
    return out,fvgs,stats


def eligible_target(target:dict[str,Any],setup:dict[str,Any])->bool:
    trigger_time=parse_time(setup['knowledge_time_utc'])
    if parse_time(target['knowledge_time_utc'])>=trigger_time:return False
    touch=target.get('first_retouch_h1_index')
    if touch is not None and int(touch)<=int(setup['B_h1_index']):return False
    trigger_close=dec(setup['trigger_close']);target_price=dec(target['price'])
    return (setup['direction']=='LONG' and target['kind']=='H' and target_price>trigger_close) or (setup['direction']=='SHORT' and target['kind']=='L' and target_price<trigger_close)


def target_reference(targets:list[dict[str,Any]],setup:dict[str,Any])->dict[str,Any]|None:
    eligible=[target for target in targets if eligible_target(target,setup)]
    if not eligible:return None
    if setup['direction']=='LONG':
        best_price=min(dec(target['price']) for target in eligible)
    else:
        best_price=max(dec(target['price']) for target in eligible)
    same=[target for target in eligible if dec(target['price'])==best_price]
    return min(same,key=lambda row:(parse_time(row['knowledge_time_utc']),row['target_id']))


class TargetIndex:
    def __init__(self,targets:list[dict[str,Any]]):
        self.highs=sorted([row for row in targets if row['kind']=='H'],key=lambda row:(dec(row['price']),parse_time(row['knowledge_time_utc']),row['target_id']));self.high_prices=[dec(row['price']) for row in self.highs]
        self.lows=sorted([row for row in targets if row['kind']=='L'],key=lambda row:(dec(row['price']),parse_time(row['knowledge_time_utc']),row['target_id']));self.low_prices=[dec(row['price']) for row in self.lows]
    def find(self,setup:dict[str,Any])->dict[str,Any]|None:
        close=dec(setup['trigger_close'])
        if setup['direction']=='LONG':
            i=bisect_right(self.high_prices,close)
            while i<len(self.highs):
                level=self.high_prices[i];same=[]
                while i<len(self.highs) and self.high_prices[i]==level:same.append(self.highs[i]);i+=1
                eligible=[row for row in same if eligible_target(row,setup)]
                if eligible:return min(eligible,key=lambda row:(parse_time(row['knowledge_time_utc']),row['target_id']))
            return None
        i=bisect_left(self.low_prices,close)-1
        while i>=0:
            level=self.low_prices[i];same=[]
            while i>=0 and self.low_prices[i]==level:same.append(self.lows[i]);i-=1
            eligible=[row for row in same if eligible_target(row,setup)]
            if eligible:return min(eligible,key=lambda row:(parse_time(row['knowledge_time_utc']),row['target_id']))
        return None


def record(setup:dict[str,Any],target:dict[str,Any])->dict[str,Any]:
    a,b=setup['A'],setup['B'];direction=setup['direction'];stop=dec(b['lower'] if direction=='LONG' else b['upper']);target_price=dec(target['price'])
    return {'trigger_id':ident('V8TRG',direction,a['fvg_id'],b['fvg_id'],setup['knowledge_time_utc'],target['target_id'],str(stop),str(target_price)),'direction':direction,'knowledge_time_utc':setup['knowledge_time_utc'],'trigger_close':setup['trigger_close'],'stop_anchor':str(stop),'target_price':str(target_price),'target_id':target['target_id'],'target_kind':target['kind'],'target_known_at_utc':target['knowledge_time_utc'],'A_fvg_id':a['fvg_id'],'A_fvg_direction':a['direction'],'A_known_at_utc':a['knowledge_time_utc'],'B_fvg_id':b['fvg_id'],'B_fvg_direction':b['direction'],'B_lower':b['lower'],'B_upper':b['upper'],'B_known_at_utc':b['knowledge_time_utc'],'bias_event_id':setup['bias_event_id']}


def reconstruct_primary(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    setups,_,stats=followthrough_candidates(h4,h1);targets=h1_swing_targets(h1);index=TargetIndex(targets);out=[];stats=dict(stats);stats['without_target']=0
    for setup in setups:
        target=index.find(setup)
        if target is None:stats['without_target']+=1;continue
        out.append(record(setup,target))
    out.sort(key=lambda row:(row['knowledge_time_utc'],row['trigger_id']));stats['signals']=len(out);return out,stats


def reconstruct_reference(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    setups,_,stats=followthrough_candidates(h4,h1);targets=h1_swing_targets(h1);out=[];stats=dict(stats);stats['without_target']=0
    for setup in setups:
        target=target_reference(targets,setup)
        if target is None:stats['without_target']+=1;continue
        out.append(record(setup,target))
    out.sort(key=lambda row:(row['knowledge_time_utc'],row['trigger_id']));stats['signals']=len(out);return out,stats


def compare_reconstructions(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    primary,ps=reconstruct_primary(h4,h1);reference,rs=reconstruct_reference(h4,h1);ph,rh=canon(primary),canon(reference)
    if primary!=reference:raise RuntimeError(f'V8 independent reconstruction mismatch primary={ph} reference={rh}')
    return primary,{'exact_match':True,'primary_sha256':ph,'reference_sha256':rh,'primary_stats':ps,'reference_stats':rs}
