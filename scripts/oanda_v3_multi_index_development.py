#!/usr/bin/env python3
"""Acquire V3-B 2024-2025 U.S. index structure from OANDA without outcomes."""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import oanda_backward_oos_structure as common

CANDIDATE_SHA="c40cf7223bcb956d0e668e48dfeb29fbb7aa529fe45350710bbe5aaf2c2160b9"
PROFILE_SHA="87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
START=datetime(2024,1,1,tzinfo=UTC); END=datetime(2026,1,1,tzinfo=UTC)
INSTRUMENTS=["NAS100_USD","SPX500_USD","US30_USD"]
BASE="https://api-fxpractice.oanda.com"

class V3DataError(RuntimeError): pass

def load_candidate(path:Path)->dict:
    x=json.loads(path.read_text()); rec=x.pop("candidate_sha256","")
    if rec!=CANDIDATE_SHA or common.canon(x)!=CANDIDATE_SHA: raise V3DataError("candidate SHA drift")
    if x["change_set"]["fixed_candidate_instruments"]!=INSTRUMENTS: raise V3DataError("instrument set drift")
    if x["change_set"]["all_v2_strategy_predicates"]!="UNCHANGED" or x["change_set"]["v3_a_overlap_removal"]!="NOT_INCLUDED": raise V3DataError("V2 rule boundary changed")
    if x["development_coverage"]["post_entry_outcomes_allowed"] is not False or x["development_coverage"]["performance_metrics_allowed"] is not False: raise V3DataError("outcome boundary changed")
    return x

def account_instruments(account:str,token:str)->dict[str,dict]:
    req=Request(f"{BASE}/v3/accounts/{account}/instruments",headers={"Authorization":f"Bearer {token}","Accept-Datetime-Format":"RFC3339"})
    try:
        with urlopen(req,timeout=45) as r: doc=json.loads(r.read())
    except HTTPError as exc: raise V3DataError(f"instrument metadata HTTP {exc.code}") from exc
    except URLError as exc: raise V3DataError("instrument metadata request failed") from exc
    rows=doc.get("instruments")
    if not isinstance(rows,list): raise V3DataError("instrument metadata missing")
    return {str(r.get("name")):r for r in rows if isinstance(r,dict) and r.get("name")}

def safe_metadata(raw:dict)->dict:
    keys=("name","displayName","type","pipLocation","displayPrecision","tradeUnitsPrecision","minimumTradeSize","maximumOrderUnits")
    return {k:raw.get(k) for k in keys if k in raw}

def acquire_one(instrument:str, account:str, token:str, out:Path)->dict:
    c={"base_url":BASE,"instrument":instrument,"page_candles":4500}
    rawdir=out/"raw-pages";rawdir.mkdir(parents=True,exist_ok=True); parsed=[]; pages=[]
    wins=common.windows(START,END,4500)
    for idx,(a,b) in enumerate(wins):
        payload,reqsha=common.request_payload(c=c,account=account,token=token,start=a,end=b)
        rawsha=hashlib.sha256(payload).hexdigest(); (rawdir/f"page-{idx:04d}.json").write_bytes(payload)
        rows=common.parse_page(payload,instrument); parsed.append(rows); pages.append({"index":idx,"start":a.isoformat().replace("+00:00","Z"),"end":b.isoformat().replace("+00:00","Z"),"request_sha256":reqsha,"raw_response_sha256":rawsha,"complete_m15_rows":len(rows)})
        if idx+1<len(wins): time.sleep(0.02)
    r15=common.merge_pages(parsed,START,END); common.write_jsonl(out/f"{instrument}.15m.jsonl",r15); derived={}
    for mins in (60,240):
        rows,omitted=common.aggregate(r15,mins); p=out/f"{instrument}.{mins}m.jsonl";common.write_jsonl(p,rows);derived[str(mins)]={"rows":len(rows),"omitted_incomplete_buckets":omitted,"sha256":common.file_sha(p)}
    digest=hashlib.sha256()
    for p in pages:digest.update(p["request_sha256"].encode());digest.update(p["raw_response_sha256"].encode())
    m={"schema_version":1,"status":"V3_MULTI_INDEX_DEVELOPMENT_STRUCTURE_READY","instrument":instrument,"provider":"OANDA_V20","venue":"OANDA_FXTRADE","environment":"practice","requested_start":"2024-01-01T00:00:00Z","requested_end_exclusive":"2026-01-01T00:00:00Z","requested_price_components":"MBA","semantic_price_component":"MID","source_granularity":"M15","candidate_sha256":CANDIDATE_SHA,"parent_profile_sha256":PROFILE_SHA,"first_complete_bar":r15[0]["ts_start_utc"],"last_complete_bar":r15[-1]["ts_start_utc"],"m15_rows":len(r15),"m15_sha256":common.file_sha(out/f"{instrument}.15m.jsonl"),"derived":derived,"raw_page_count":len(pages),"raw_pages":pages,"retrieval_sha256":digest.hexdigest(),"post_entry_outcomes_evaluated":False,"m1_outcome_data_requested":False,"mutation_endpoints_used":False}
    m["manifest_sha256"]=common.canon(m);(out/f"{instrument}.manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n");return m

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--candidate",required=True);p.add_argument("--output-dir",required=True);a=p.parse_args()
    try:
        load_candidate(Path(a.candidate));account=os.getenv("OANDA_ACCOUNT_ID","");token=os.getenv("OANDA_API_TOKEN","")
        if not account or not token:raise V3DataError("OANDA credentials missing")
        available=account_instruments(account,token);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);availability=[];manifests=[]
        for name in INSTRUMENTS:
            ok=name in available;availability.append({"instrument":name,"available":ok,"metadata":safe_metadata(available[name]) if ok else None})
            if ok:manifests.append(acquire_one(name,account,token,out/name))
        if not manifests:raise V3DataError("none of the preregistered instruments are available")
        summary={"schema_version":1,"status":"V3_MULTI_INDEX_DEVELOPMENT_DATA_READY","candidate_sha256":CANDIDATE_SHA,"fixed_candidate_instruments":INSTRUMENTS,"availability":availability,"available_instruments":[x["instrument"] for x in availability if x["available"]],"unavailable_instruments":[x["instrument"] for x in availability if not x["available"]],"replacement_instruments_used":False,"manifests":[{"instrument":m["instrument"],"manifest_sha256":m["manifest_sha256"],"m15_rows":m["m15_rows"],"retrieval_sha256":m["retrieval_sha256"]} for m in manifests],"post_entry_outcomes_evaluated":False,"performance_metrics_accessed":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};summary["summary_sha256"]=common.canon(summary);(out/"multi-index-summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    except Exception as exc:print(f"V3 multi-index acquisition failed: {exc}",file=sys.stderr);return 1
    print(json.dumps({"status":summary["status"],"available":summary["available_instruments"],"unavailable":summary["unavailable_instruments"],"outcomes_accessed":False,"summary_sha256":summary["summary_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
