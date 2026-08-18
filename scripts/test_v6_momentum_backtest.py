#!/usr/bin/env python3
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import v6_momentum_backtest_mechanics as m
UTC=timezone.utc

def stamp(i):return (datetime(2020,1,1,tzinfo=UTC)+timedelta(minutes=i)).isoformat().replace('+00:00','Z')
def bar(i,bido,bidh,bidl,bidc,asko,askh,askl,askc):return {'ts_start_utc':stamp(i),'bid':{'o':str(bido),'h':str(bidh),'l':str(bidl),'c':str(bidc)},'ask':{'o':str(asko),'h':str(askh),'l':str(askl),'c':str(askc)}}
def trigger(trigger_id,direction,stop,target):return {'trigger_id':trigger_id,'direction':direction,'knowledge_time_utc':stamp(0),'stop_anchor':str(stop),'target_price':str(target)}

def run():
    longbars=[bar(0,100,101,99,100,101,102,100,101),bar(1,102,106,102,105,103,107,103,106)]
    result=m.measure_trade(trigger('L','LONG',95,105),longbars,slip_points=Decimal('0'),financing_r_per_1440=Decimal('0'));assert result['status']=='TARGET' and result['net_r']>0
    shortbars=[bar(0,99,100,98,99,100,101,99,100),bar(1,94,95,93,94,95,96,92,94)]
    result=m.measure_trade(trigger('S','SHORT',105,95),shortbars,slip_points=Decimal('0'),financing_r_per_1440=Decimal('0'));assert result['status']=='TARGET' and result['net_r']>0
    both=[bar(0,100,110,90,100,101,111,91,101)]
    result=m.measure_trade(trigger('B','LONG',95,105),both,slip_points=Decimal('0'),financing_r_per_1440=Decimal('0'));assert result['status']=='STOP' and result['same_m1_stop_and_target'] is True
    kept,skipped=m.deduplicate([trigger('b','LONG',95,105),trigger('a','LONG',95,105)]);assert kept[0]['trigger_id']=='a' and skipped[0]['trigger_id']=='b'
    invalid=m.measure_trade(trigger('I','SHORT',95,105),shortbars,slip_points=Decimal('0'),financing_r_per_1440=Decimal('0'));assert invalid['status']=='INVALID_RISK_OR_TARGET_ORDERING'
    print('v6_momentum_backtest_offline_tests=PASS')
if __name__=='__main__':run()
