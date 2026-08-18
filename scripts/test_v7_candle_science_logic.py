#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import v7_candle_science_primitives as p
import v7_candle_science_reconstruct as r
UTC=timezone.utc

def row(start:datetime,o,h,l,c):return {'time':p.stamp(start),'open':str(o),'high':str(h),'low':str(l),'close':str(c),'complete':True,'volume':1}
def h4(i,o,h,l,c):return row(datetime(2020,1,1,tzinfo=UTC)+timedelta(hours=4*i),o,h,l,c)
def h1(i,o,h,l,c):return row(datetime(2020,1,1,16,tzinfo=UTC)+timedelta(hours=i),o,h,l,c)

def run():
    h4_rows=[h4(0,95,100,90,95),h4(1,100,110,92,100),h4(2,101,105,91,104),h4(3,104,112,96,111)]
    swings=p.h4_swings(h4_rows);assert any(x['kind']=='H' and Decimal(x['price'])==Decimal('110') for x in swings)
    events=p.h4_break_events(h4_rows);assert len(events)==1 and events[0]['direction']=='BULL' and Decimal(events[0]['broken_level'])==Decimal('110')
    bias=p.BiasIndex(events);assert bias.at(datetime(2020,1,1,22,tzinfo=UTC))['direction']=='BULL';assert bias.preserved(datetime(2020,1,1,22,tzinfo=UTC),datetime(2020,1,1,23,tzinfo=UTC),'BULL')

    h1_rows=[
        h1(0,122,125,120,122),h1(1,120,123,118,120),h1(2,112,115,110,112),
        h1(3,98,100,95,98),h1(4,101,103,99,101),h1(5,107,108,105,107),
        h1(6,104,107,101,106),h1(7,106,109,104,108),
    ]
    fvgs=p.attach_first_retouch(p.h1_fvgs(h1_rows),h1_rows);bear=[x for x in fvgs if x['direction']=='BEAR' and Decimal(x['lower'])==Decimal('115')];assert bear and bear[0]['first_retouch_h1_index'] is None
    triggers,comparison=r.compare_reconstructions(h4_rows,h1_rows);assert comparison['exact_match'] is True;assert len(triggers)==1
    trigger=triggers[0];assert trigger['direction']=='LONG';assert Decimal(trigger['stop_anchor'])==Decimal('101');assert Decimal(trigger['target_price'])==Decimal('115');assert trigger['knowledge_time_utc']=='2020-01-01T23:00:00Z'

    target_rows=[{'fvg_id':'a','direction':'BULL','lower':'80','upper':'90','c3_index':0,'knowledge_time_utc':'2020-01-01T18:00:00Z','first_retouch_h1_index':None},{'fvg_id':'b','direction':'BULL','lower':'82','upper':'92','c3_index':0,'knowledge_time_utc':'2020-01-01T19:00:00Z','first_retouch_h1_index':None}]
    rejection={'direction':'SHORT','knowledge_time_utc':'2020-01-01T23:00:00Z','rejection_h1_index':6,'rejection_close':'100'}
    assert r.TargetIndex(target_rows).find(rejection)['fvg_id']=='b';assert r._target_bruteforce(target_rows,rejection)['fvg_id']=='b'
    print('v7_candle_science_offline_tests=PASS')
if __name__=='__main__':run()
