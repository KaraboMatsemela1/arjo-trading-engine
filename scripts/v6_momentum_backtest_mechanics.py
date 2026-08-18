#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal
from typing import Callable
UTC=timezone.utc;RESOLVED={'STOP','TARGET','EXPIRY'}

def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def ts(v:str)->datetime:
    x=datetime.fromisoformat(v.replace('Z','+00:00'))
    if x.tzinfo is None:raise ValueError('naive timestamp')
    return x.astimezone(UTC)
def dec(v:object)->Decimal:return Decimal(str(v))

def deduplicate(triggers:list[dict])->tuple[list[dict],list[dict]]:
    groups=defaultdict(list)
    for row in triggers:groups[row['knowledge_time_utc']].append(row)
    kept=[];skipped=[]
    for knowledge in sorted(groups):
        rows=sorted(groups[knowledge],key=lambda x:x['trigger_id']);winner=rows[0];kept.append(winner)
        for row in rows[1:]:skipped.append({'trigger_id':row['trigger_id'],'direction':row['direction'],'knowledge_time_utc':knowledge,'status':'SKIPPED_DUPLICATE_KNOWLEDGE_TIME','kept_trigger_id':winner['trigger_id']})
    return kept,skipped

def measure_trade(trigger:dict,bars:list[dict],*,slip_points:Decimal,financing_r_per_1440:Decimal)->dict:
    knowledge=ts(trigger['knowledge_time_utc']);eligible=[bar for bar in bars if ts(bar['ts_start_utc'])>=knowledge];base={'trigger_id':trigger['trigger_id'],'direction':trigger['direction'],'knowledge_time_utc':trigger['knowledge_time_utc']}
    if not eligible or (ts(eligible[0]['ts_start_utc'])-knowledge).total_seconds()>72*3600:return {**base,'status':'DATA_INTEGRITY_FAILURE','reason':'NO_ELIGIBLE_M1_WITHIN_72H'}
    first=eligible[0];direction=trigger['direction'];stop=dec(trigger['stop_anchor']);target=dec(trigger['target_price'])
    if direction=='LONG':raw_entry=dec(first['ask']['o']);entry=raw_entry+slip_points;risk=entry-stop;valid=stop<entry<target
    elif direction=='SHORT':raw_entry=dec(first['bid']['o']);entry=raw_entry-slip_points;risk=stop-entry;valid=target<entry<stop
    else:return {**base,'status':'DATA_INTEGRITY_FAILURE','reason':'UNKNOWN_DIRECTION'}
    common={**base,'entry_ts_utc':first['ts_start_utc'],'entry_price':str(entry),'raw_entry_price':str(raw_entry),'stop_price':str(stop),'target_price':str(target)}
    if not valid or risk<=0:return {**common,'status':'INVALID_RISK_OR_TARGET_ORDERING'}
    usable=eligible[:1440]
    for idx,bar in enumerate(usable):
        if direction=='LONG':
            opened,high,low=dec(bar['bid']['o']),dec(bar['bid']['h']),dec(bar['bid']['l']);stop_hit=low<=stop;target_hit=high>=target
            if stop_hit:raw_exit=opened if opened<stop else stop;exit_price=raw_exit-slip_points;status='STOP'
            elif target_hit:exit_price=target-slip_points;status='TARGET'
            else:continue
            gross=(exit_price-entry)/risk
        else:
            opened,high,low=dec(bar['ask']['o']),dec(bar['ask']['h']),dec(bar['ask']['l']);stop_hit=high>=stop;target_hit=low<=target
            if stop_hit:raw_exit=opened if opened>stop else stop;exit_price=raw_exit+slip_points;status='STOP'
            elif target_hit:exit_price=target+slip_points;status='TARGET'
            else:continue
            gross=(entry-exit_price)/risk
        held=idx+1;financing=financing_r_per_1440*Decimal(held)/Decimal(1440)
        return {**common,'exit_ts_utc':bar['ts_start_utc'],'exit_price':str(exit_price),'risk_points':str(risk),'complete_m1_bars_held':held,'status':status,'gross_r':float(gross),'financing_r':float(financing),'net_r':float(gross-financing),'same_m1_stop_and_target':bool(stop_hit and target_hit)}
    if len(usable)<1440:return {**common,'risk_points':str(risk),'complete_m1_bars_observed':len(usable),'status':'RIGHT_CENSORED_HISTORICAL_END'}
    final=usable[-1]
    if direction=='LONG':exit_price=dec(final['bid']['c'])-slip_points;gross=(exit_price-entry)/risk
    else:exit_price=dec(final['ask']['c'])+slip_points;gross=(entry-exit_price)/risk
    return {**common,'exit_ts_utc':final['ts_start_utc'],'exit_price':str(exit_price),'risk_points':str(risk),'complete_m1_bars_held':1440,'status':'EXPIRY','gross_r':float(gross),'financing_r':float(financing_r_per_1440),'net_r':float(gross-financing_r_per_1440),'same_m1_stop_and_target':False}

def evaluate(triggers:list[dict],get_bars:Callable[[datetime,int],list[dict]],*,scenario:str,slip_points:Decimal,financing_r_per_1440:Decimal)->dict:
    kept,duplicates=deduplicate(triggers);ledger=list(duplicates);open_until=None
    for trigger in kept:
        knowledge=ts(trigger['knowledge_time_utc'])
        if open_until is not None and knowledge<=open_until:
            ledger.append({'trigger_id':trigger['trigger_id'],'direction':trigger['direction'],'knowledge_time_utc':trigger['knowledge_time_utc'],'status':'SKIPPED_CONCURRENT_POSITION','prior_position_exit_m1_start_utc':open_until.isoformat().replace('+00:00','Z')});continue
        result=measure_trade(trigger,get_bars(knowledge,1440),slip_points=slip_points,financing_r_per_1440=financing_r_per_1440);ledger.append(result)
        if result['status'] in RESOLVED:open_until=ts(result['exit_ts_utc'])
    ledger.sort(key=lambda x:(x.get('knowledge_time_utc',''),x['trigger_id'],x['status']));return {'scenario':scenario,'ledger':ledger,'ledger_sha256':canon(ledger)}
