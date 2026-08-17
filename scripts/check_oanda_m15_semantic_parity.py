#!/usr/bin/env python3
"""Verify OANDA direct M15 MID equals existing M1->M15 UTC aggregation on permitted 2024 development data."""
from __future__ import annotations

import json, os, sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE="https://api-fxpractice.oanda.com"; INSTRUMENT="NAS100_USD"
START=datetime(2024,3,11,tzinfo=UTC); END=datetime(2024,3,12,tzinfo=UTC)


def get(granularity:str)->list[dict]:
    account=os.getenv("OANDA_ACCOUNT_ID",""); token=os.getenv("OANDA_API_TOKEN","")
    if not account or not token: raise RuntimeError("OANDA credentials missing")
    q=urlencode({"price":"M","granularity":granularity,"from":START.isoformat().replace("+00:00","Z"),"to":END.isoformat().replace("+00:00","Z"),"smooth":"false","includeFirst":"true"})
    req=Request(f"{BASE}/v3/accounts/{account}/instruments/{INSTRUMENT}/candles?{q}",headers={"Authorization":f"Bearer {token}","Accept-Datetime-Format":"RFC3339"})
    with urlopen(req,timeout=45) as r: doc=json.loads(r.read())
    if doc.get("instrument")!=INSTRUMENT or doc.get("granularity")!=granularity: raise RuntimeError("provider identity mismatch")
    return [x for x in doc["candles"] if x.get("complete") is True]


def ts(raw:dict)->datetime: return datetime.fromisoformat(raw["time"].replace("Z","+00:00")).astimezone(UTC)
def d(x:object)->Decimal: return Decimal(str(x))


def aggregate(m1:list[dict])->dict[str,tuple[Decimal,Decimal,Decimal,Decimal]]:
    groups={}
    for raw in m1:
        t=ts(raw); minute=(t.minute//15)*15; start=t.replace(minute=minute,second=0,microsecond=0)
        groups.setdefault(start,[]).append(raw)
    out={}
    for start,bars in groups.items():
        bars=sorted(bars,key=ts); expected=[start+timedelta(minutes=i) for i in range(15)]
        if [ts(b) for b in bars]!=expected: continue
        p=[b["mid"] for b in bars]
        out[start.isoformat().replace("+00:00","Z")]=(d(p[0]["o"]),max(d(x["h"]) for x in p),min(d(x["l"]) for x in p),d(p[-1]["c"]))
    return out


def main()->int:
    try:
        m1=get("M1"); direct=get("M15"); derived=aggregate(m1); compared=0
        for raw in direct:
            key=ts(raw).isoformat().replace("+00:00","Z")
            if key not in derived: continue
            p=raw["mid"]; actual=(d(p["o"]),d(p["h"]),d(p["l"]),d(p["c"]))
            if actual!=derived[key]: raise RuntimeError(f"M15 parity mismatch at {key}")
            compared+=1
        if compared < 80: raise RuntimeError(f"insufficient parity sample: {compared}")
        print(json.dumps({"status":"DIRECT_M15_SEMANTIC_PARITY_VERIFIED","date":"2024-03-11","compared_complete_m15_bars":compared,"outcomes_evaluated":False},sort_keys=True)); return 0
    except Exception as exc:
        print(f"M15 parity failed: {exc}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
