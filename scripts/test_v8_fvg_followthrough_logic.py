#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import v8_fvg_followthrough_reconstruct as r
from v7_candle_science_primitives import canon
UTC=timezone.utc

def stamp(d):return d.isoformat().replace('+00:00','Z')
def row(start,o,h,l,c):return {'time':stamp(start),'open':str(o),'high':str(h),'low':str(l),'close':str(c),'complete':True,'volume':1}
def h4(i,o,h,l,c):return row(datetime(2020,1,1,tzinfo=UTC)+timedelta(hours=4*i),o,h,l,c)
def h1(i,o,h,l,c):return row(datetime(2020,1,1,16,tzinfo=UTC)+timedelta(hours=i),o,h,l,c)

def base_h4():
    return [h4(0,95,100,90,95),h4(1,100,110,92,100),h4(2,101,105,91,104),h4(3,104,112,96,111),h4(4,111,115,105,113),h4(5,113,116,106,114)]

def followthrough_h1():
    return [
        h1(0,100,105,95,100),
        h1(1,110,130,100,110),
        h1(2,105,110,100,105),
        h1(3,109,112,105,110),
        h1(4,116,119,115,118),
        h1(5,114,118,110,116),
        h1(6,116,119,113,117),
        h1(7,121,124,120,122),
        h1(8,122,125,119,123),
    ]

def run():
    h4_rows=base_h4();h1_rows=followthrough_h1()
    setups,_,stats=r.followthrough_candidates(h4_rows,h1_rows)
    assert stats['same_direction_B']>=1 and stats['opposite_direction_B']==0
    triggers,comparison=r.compare_reconstructions(h4_rows,h1_rows)
    assert comparison['exact_match'] is True and len(triggers)>=1
    first=triggers[0]
    assert first['direction']=='LONG'
    assert Decimal(first['stop_anchor'])==Decimal('118')
    assert Decimal(first['target_price'])==Decimal('130')
    assert first['B_known_at_utc']=='2020-01-02T00:00:00Z'

    targets=r.h1_swing_targets(h1_rows);setup=setups[0]
    assert r.TargetIndex(targets).find(setup)==r.target_reference(targets,setup)

    opposite=followthrough_h1()
    opposite[7]=h1(7,106,108,104,106)
    setups2,_,stats2=r.followthrough_candidates(h4_rows,opposite)
    assert stats2['opposite_direction_B']>=1
    assert all(item['B']['direction']==item['A']['direction'] for item in setups2)

    assert canon(triggers)==comparison['primary_sha256']==comparison['reference_sha256']
    print('v8_fvg_followthrough_offline_tests=PASS')
if __name__=='__main__':run()
