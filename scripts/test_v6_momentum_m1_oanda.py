#!/usr/bin/env python3
import json,tempfile
from datetime import datetime,timezone
from pathlib import Path
from v6_momentum_m1_oanda import M1Cache
UTC=timezone.utc

def run():
    with tempfile.TemporaryDirectory() as tmp:
        cache=M1Cache(Path(tmp),'dummy-not-used')
        payload=json.dumps({'instrument':'NAS100_USD','granularity':'M1','candles':[{'complete':True,'time':'2020-01-02T10:00:00Z','bid':{'o':'100','h':'102','l':'99','c':'101'},'ask':{'o':'101','h':'103','l':'100','c':'102'}},{'complete':False,'time':'2020-01-02T10:01:00Z','bid':{'o':'101','h':'102','l':'100','c':'101'},'ask':{'o':'102','h':'103','l':'101','c':'102'}}]}).encode()
        a=datetime(2020,1,2,10,0,tzinfo=UTC);b=datetime(2020,1,2,10,2,tzinfo=UTC);rows=cache._parse(payload,a,b)
        assert len(rows)==1 and rows[0]['bid']['o']=='100' and rows[0]['ask']['o']=='101'
        bad=json.dumps({'instrument':'NAS100_USD','granularity':'M1','candles':[{'complete':True,'time':'2020-01-02T10:00:00Z','bid':{'o':'100','h':'99','l':'98','c':'100'},'ask':{'o':'101','h':'103','l':'100','c':'102'}}]}).encode()
        try:cache._parse(bad,a,b)
        except RuntimeError as exc:assert 'invalid bid envelope' in str(exc)
        else:raise AssertionError('invalid bid envelope accepted')
        outside=json.dumps({'instrument':'NAS100_USD','granularity':'M1','candles':[{'complete':True,'time':'2024-01-01T00:00:00Z','bid':{'o':'100','h':'101','l':'99','c':'100'},'ask':{'o':'101','h':'102','l':'100','c':'101'}}]}).encode()
        assert cache._parse(outside,a,b)==[]
    print('v6_momentum_m1_oanda_offline_tests=PASS')

if __name__=='__main__':run()
