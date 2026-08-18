#!/usr/bin/env python3
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import v6_momentum_primitives as p
import v6_momentum_reconstruct as r
UTC=timezone.utc

def candle(i:int,o:float,h:float,l:float,c:float,minutes:int=60):
    t=datetime(2020,1,1,tzinfo=UTC)+timedelta(minutes=i*minutes)
    return {'time':p.stamp(t),'open':str(o),'high':str(h),'low':str(l),'close':str(c),'complete':True,'volume':1}

def pivot(kind,price,n):
    return {'pivot_id':f'p{n}','kind':kind,'price':str(price),'source_time_utc':f'2020-01-01T{n:02d}:00:00Z','knowledge_time_utc':f'2020-01-01T{n:02d}:15:00Z','source_index':n}

def run():
    highs=[100,101,105,101,102,110,102,101,107,101,100];lows=[90,91,92,91,90,93,91,90,92,91,90]
    rows=[candle(i,95,highs[i],lows[i],95) for i in range(len(highs))]
    hs=[x for x in p.pivots(rows,60,'H1') if x['kind']=='H'];assert [Decimal(x['price']) for x in hs][:3]==[Decimal('105'),Decimal('110'),Decimal('107')]
    ith=[x for x in p.intermediate_targets(rows) if x['kind']=='ITH'];assert ith and Decimal(ith[0]['price'])==Decimal('110')
    bull=[candle(0,100,101,99,100),candle(1,100,102,99,101),candle(2,104,106,103,105)];assert p.h1_fvgs(bull)[0]['direction']=='BULL'
    bear=[candle(0,105,106,104,105),candle(1,104,105,102,103),candle(2,100,101,99,100)];assert p.h1_fvgs(bear)[0]['direction']=='BEAR'
    long=[pivot('H',106,1),pivot('L',100,2),pivot('H',107,3),pivot('L',102,4),pivot('H',108,5),pivot('L',104,6)];assert r.qualifies(long,'LONG')
    bad=list(long);bad[-1]=pivot('L',101,6);assert not r.qualifies(bad,'LONG')
    short=[pivot('L',94,1),pivot('H',100,2),pivot('L',93,3),pivot('H',98,4),pivot('L',92,5),pivot('H',96,6)];assert r.qualifies(short,'SHORT')
    flat=[candle(i,100,101,99,100) for i in range(140)];m15=[candle(i,100,101,99,100,15) for i in range(600)];triggers,cmp=r.compare_reconstructions(flat,m15);assert triggers==[] and cmp['exact_match'] is True
    print('v6_momentum_offline_tests=PASS')

if __name__=='__main__':run()
