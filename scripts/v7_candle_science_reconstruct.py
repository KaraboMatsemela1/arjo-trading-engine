#!/usr/bin/env python3
from __future__ import annotations
from bisect import bisect_left,bisect_right
from datetime import timedelta
from typing import Any
from v7_candle_science_primitives import BiasIndex,attach_first_retouch,canon,dec,h1_fvgs,h4_break_events,ident,intersects,parse_time,price,stamp

def _rejections(h4:list[dict[str,Any]],h1:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]],BiasIndex,dict[str,int]]:
    bias=BiasIndex(h4_break_events(h4));fvgs=attach_first_retouch(h1_fvgs(h1),h1);out=[];stats={'h1_fvgs':len(fvgs),'aligned_fvgs':0,'qualifying_rejections':0,'bias_changed_before_rejection':0}
    for fvg in fvgs:
        fvg_known=parse_time(fvg['knowledge_time_utc']);event=bias.at(fvg_known)
        if event is None or event['direction']!=fvg['direction']:continue
        stats['aligned_fvgs']+=1;direction=fvg['direction'];end=min(len(h1)-1,int(fvg['c3_index'])+12)
        for index in range(int(fvg['c3_index'])+1,end+1):
            candle=h1[index];known=parse_time(candle['time'])+timedelta(hours=1)
            if not bias.preserved(fvg_known,known,direction):stats['bias_changed_before_rejection']+=1;break
            if not intersects(candle,fvg):continue
            close=price(candle,'close');qualifies=close>dec(fvg['upper']) if direction=='BULL' else close<dec(fvg['lower'])
            if not qualifies:continue
            rejection_bias=bias.at(known)
            if rejection_bias is None or rejection_bias['direction']!=direction:raise AssertionError('preserved bias missing at rejection')
            out.append({'setup_fvg':fvg,'direction':'LONG' if direction=='BULL' else 'SHORT','rejection_h1_index':index,'rejection_time_utc':candle['time'],'knowledge_time_utc':stamp(known),'rejection_close':str(close),'rejection_low':str(price(candle,'low')),'rejection_high':str(price(candle,'high')),'bias_event_id':event['event_id'],'rejection_bias_event_id':rejection_bias['event_id']});stats['qualifying_rejections']+=1;break
    return out,fvgs,bias,stats

def _eligible_target(fvg:dict[str,Any],rejection:dict[str,Any])->bool:
    if parse_time(fvg['knowledge_time_utc'])>=parse_time(rejection['knowledge_time_utc']):return False
    touch=fvg.get('first_retouch_h1_index')
    if touch is not None and int(touch)<=int(rejection['rejection_h1_index']):return False
    close=dec(rejection['rejection_close'])
    if rejection['direction']=='LONG':return fvg['direction']=='BEAR' and dec(fvg['lower'])>close
    return fvg['direction']=='BULL' and dec(fvg['upper'])<close

def _target_bruteforce(fvgs:list[dict[str,Any]],rejection:dict[str,Any])->dict[str,Any]|None:
    candidates=[fvg for fvg in fvgs if _eligible_target(fvg,rejection)]
    if not candidates:return None
    if rejection['direction']=='LONG':
        boundary=min(dec(x['lower']) for x in candidates);same=[x for x in candidates if dec(x['lower'])==boundary]
    else:
        boundary=max(dec(x['upper']) for x in candidates);same=[x for x in candidates if dec(x['upper'])==boundary]
    return min(same,key=lambda x:(parse_time(x['knowledge_time_utc']),x['fvg_id']))

class TargetIndex:
    def __init__(self,fvgs:list[dict[str,Any]]):
        self.bear=sorted([x for x in fvgs if x['direction']=='BEAR'],key=lambda x:(dec(x['lower']),parse_time(x['knowledge_time_utc']),x['fvg_id']));self.bear_keys=[dec(x['lower']) for x in self.bear]
        self.bull=sorted([x for x in fvgs if x['direction']=='BULL'],key=lambda x:(dec(x['upper']),parse_time(x['knowledge_time_utc']),x['fvg_id']));self.bull_keys=[dec(x['upper']) for x in self.bull]
    def find(self,rejection:dict[str,Any])->dict[str,Any]|None:
        close=dec(rejection['rejection_close'])
        if rejection['direction']=='LONG':
            i=bisect_right(self.bear_keys,close)
            while i<len(self.bear):
                boundary=self.bear_keys[i];same=[]
                while i<len(self.bear) and self.bear_keys[i]==boundary:same.append(self.bear[i]);i+=1
                eligible=[x for x in same if _eligible_target(x,rejection)]
                if eligible:return min(eligible,key=lambda x:(parse_time(x['knowledge_time_utc']),x['fvg_id']))
            return None
        i=bisect_left(self.bull_keys,close)-1
        while i>=0:
            boundary=self.bull_keys[i];same=[]
            while i>=0 and self.bull_keys[i]==boundary:same.append(self.bull[i]);i-=1
            eligible=[x for x in same if _eligible_target(x,rejection)]
            if eligible:return min(eligible,key=lambda x:(parse_time(x['knowledge_time_utc']),x['fvg_id']))
        return None

def _record(rejection:dict[str,Any],target:dict[str,Any])->dict[str,Any]:
    setup=rejection['setup_fvg'];direction=rejection['direction'];stop=dec(rejection['rejection_low'] if direction=='LONG' else rejection['rejection_high']);target_price=dec(target['lower'] if direction=='LONG' else target['upper'])
    return {'trigger_id':ident('V7TRG',direction,setup['fvg_id'],rejection['knowledge_time_utc'],target['fvg_id'],str(stop),str(target_price)),'direction':direction,'knowledge_time_utc':rejection['knowledge_time_utc'],'rejection_h1_start_utc':rejection['rejection_time_utc'],'rejection_close':rejection['rejection_close'],'stop_anchor':str(stop),'target_price':str(target_price),'setup_fvg_id':setup['fvg_id'],'setup_fvg_direction':setup['direction'],'setup_fvg_lower':setup['lower'],'setup_fvg_upper':setup['upper'],'setup_fvg_known_at_utc':setup['knowledge_time_utc'],'target_fvg_id':target['fvg_id'],'target_fvg_direction':target['direction'],'target_fvg_lower':target['lower'],'target_fvg_upper':target['upper'],'target_fvg_known_at_utc':target['knowledge_time_utc'],'bias_event_id':rejection['bias_event_id'],'rejection_bias_event_id':rejection['rejection_bias_event_id']}

def reconstruct_primary(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    rejections,fvgs,_,stats=_rejections(h4,h1);index=TargetIndex(fvgs);out=[];stats=dict(stats);stats['without_target']=0
    for rejection in rejections:
        target=index.find(rejection)
        if target is None:stats['without_target']+=1;continue
        out.append(_record(rejection,target))
    out.sort(key=lambda x:(x['knowledge_time_utc'],x['trigger_id']));stats['signals']=len(out);return out,stats

def reconstruct_reference(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    rejections,fvgs,_,stats=_rejections(h4,h1);out=[];stats=dict(stats);stats['without_target']=0
    for rejection in rejections:
        target=_target_bruteforce(fvgs,rejection)
        if target is None:stats['without_target']+=1;continue
        out.append(_record(rejection,target))
    out.sort(key=lambda x:(x['knowledge_time_utc'],x['trigger_id']));stats['signals']=len(out);return out,stats

def compare_reconstructions(h4:list[dict[str,Any]],h1:list[dict[str,Any]]):
    primary,ps=reconstruct_primary(h4,h1);reference,rs=reconstruct_reference(h4,h1);ph,rh=canon(primary),canon(reference)
    if primary!=reference:raise RuntimeError(f'V7 independent reconstruction mismatch primary={ph} reference={rh}')
    return primary,{'exact_match':True,'primary_sha256':ph,'reference_sha256':rh,'primary_stats':ps,'reference_stats':rs}
