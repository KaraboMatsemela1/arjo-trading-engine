#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,os,sys,time
from datetime import UTC,datetime,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import oanda_backward_oos_structure as structure
import scan_v3c_backward_oos_triggers as trigger_scan
import v3c_profitability_engine as engine
BASE_URL="https://api-fxpractice.oanda.com";INSTRUMENT="NAS100_USD";ORIGIN=datetime(2010,1,1,tzinfo=UTC);OOS_END=datetime(2024,1,1,tzinfo=UTC);CHUNK=timedelta(days=3)
TRIGGER_SHA="e633ef474c35946ca40e3314cfd5511b2193b4fae387da2e2d75131c5ed7020b";PROTOCOL_SHA="0b3a6a5e217e7e4c279f7384c14579e97bf6821bc59deefac3086e7b4ce4ba7a";LOCK_SHA="cc1b6aa88a318c26fbc653751ab34c7c399241770a0db954fc3809c1fa0d17c7";STRUCTURE_CONTRACT_SHA="e7169fa7b3d76ac6856bc64f78debf52af5330642403bd0a6adb6999ebb4de7f"
class ProfitabilityError(RuntimeError):pass
def z(d:datetime)->str:return d.astimezone(UTC).isoformat().replace("+00:00","Z")
def parse(v:str)->datetime:
 d=datetime.fromisoformat(v.replace("Z","+00:00"));
 if d.utcoffset() is None:raise ProfitabilityError("naive timestamp")
 return d.astimezone(UTC)
def dec(v:object,label:str)->Decimal:
 try:x=Decimal(str(v))
 except (InvalidOperation,ValueError) as exc:raise ProfitabilityError(f"invalid decimal {label}") from exc
 if not x.is_finite():raise ProfitabilityError(f"nonfinite decimal {label}")
 return x
def fsha(p:Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
 return h.hexdigest()
def verify_lock(path:Path)->dict:
 x=json.loads(path.read_text());rec=x.pop("spec_sha256","")
 if rec!=LOCK_SHA or engine.canon(x)!=LOCK_SHA:raise ProfitabilityError("execution lock SHA drift")
 if x["status"]!="FROZEN_BEFORE_FIRST_M1_RESPONSE" or x["canonical_trigger_set_sha256"]!=TRIGGER_SHA:raise ProfitabilityError("execution lock boundary changed")
 if x["parameter_changes_after_first_m1_response"] is not False:raise ProfitabilityError("post-M1 parameter rule changed")
 return x
def verify_marker(path:Path)->dict:
 if not path.exists():raise ProfitabilityError("research M1 execution marker missing")
 x=json.loads(path.read_text());expected={"status":"AUTHORIZED_RESEARCH_M1_READ_AFTER_PREFLIGHT","trigger_set_sha256":TRIGGER_SHA,"execution_protocol_sha256":PROTOCOL_SHA,"profitability_lock_sha256":LOCK_SHA,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
 for k,v in expected.items():
  if x.get(k)!=v:raise ProfitabilityError(f"execution marker boundary changed: {k}")
 return x
class M1Cache:
 def __init__(self,root:Path,account:str,token:str):
  if not account or not token:raise ProfitabilityError("OANDA credentials missing")
  self.root=root;root.mkdir(parents=True,exist_ok=True);self.account=account;self.token=token;self.meta={};self.first_response_accessed=False
 def idx(self,d:datetime)->int:return max(0,int((d-ORIGIN).total_seconds()//CHUNK.total_seconds()))
 def bounds(self,i:int)->tuple[datetime,datetime]:
  a=ORIGIN+i*CHUNK;return a,min(a+CHUNK,OOS_END)
 def path(self,i:int)->Path:return self.root/f"m1-{i:05d}.jsonl"
 def _request(self,a:datetime,b:datetime)->tuple[bytes,str]:
  params={"price":"BA","granularity":"M1","from":z(a),"to":z(b),"smooth":"false","includeFirst":"true"};q=urlencode(params);real=f"/v3/accounts/{self.account}/instruments/{INSTRUMENT}/candles";red=f"/v3/accounts/{{ACCOUNT}}/instruments/{INSTRUMENT}/candles";reqsha=hashlib.sha256(f"{red}?{urlencode(sorted(params.items()))}".encode()).hexdigest();url=f"{BASE_URL}{real}?{q}"
  for attempt in range(5):
   req=Request(url,headers={"Authorization":f"Bearer {self.token}","Accept-Datetime-Format":"RFC3339"},method="GET")
   try:
    with urlopen(req,timeout=60) as r:return r.read(),reqsha
   except HTTPError as exc:
    if exc.code not in {429,500,502,503,504} or attempt==4:raise ProfitabilityError(f"OANDA M1 HTTP {exc.code}") from exc
   except URLError as exc:
    if attempt==4:raise ProfitabilityError("OANDA M1 request failed") from exc
   time.sleep(2**attempt)
  raise AssertionError("unreachable")
 def _parse(self,payload:bytes)->list[dict]:
  doc=json.loads(payload)
  if doc.get("instrument")!=INSTRUMENT or doc.get("granularity")!="M1":raise ProfitabilityError("M1 provider identity mismatch")
  rows=[];prior=None
  for raw in doc.get("candles",[]):
   if raw.get("complete") is not True:continue
   t=parse(str(raw.get("time")))
   if not ORIGIN<=t<OOS_END:raise ProfitabilityError("M1 row outside frozen OOS")
   if prior is not None and t<=prior:raise ProfitabilityError("M1 provider order violation")
   prior=t;row={"ts_start_utc":z(t)}
   for comp in ("bid","ask"):
    p=raw.get(comp)
    if not isinstance(p,dict):raise ProfitabilityError(f"missing {comp} component")
    o,h,l,c=(dec(p.get(k),f"{comp}.{k}") for k in ("o","h","l","c"))
    if h<max(o,c) or l>min(o,c) or h<l:raise ProfitabilityError(f"invalid {comp} envelope")
    row[comp]={"o":str(o),"h":str(h),"l":str(l),"c":str(c)}
   rows.append(row)
  return rows
 def chunk(self,i:int)->list[dict]:
  a,b=self.bounds(i)
  if a>=OOS_END:return []
  p=self.path(i)
  if not p.exists():
   payload,reqsha=self._request(a,b);self.first_response_accessed=True;rawsha=hashlib.sha256(payload).hexdigest();rows=self._parse(payload)
   with p.open("w") as f:
    for r in rows:f.write(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
   self.meta[i]={"chunk_index":i,"from":z(a),"to_exclusive":z(b),"request_sha256":reqsha,"raw_response_sha256":rawsha,"raw_bytes":len(payload),"complete_m1_rows":len(rows),"parsed_sha256":fsha(p)}
  else:
   rows=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
  return rows
 def get_bars(self,start:datetime,count:int)->list[dict]:
  if start>=OOS_END:return []
  i=self.idx(start);by={}
  while len(by)<count:
   a,_=self.bounds(i)
   if a>=OOS_END:break
   for r in self.chunk(i):
    t=parse(r["ts_start_utc"])
    if t<start:continue
    old=by.get(r["ts_start_utc"])
    if old is not None and old!=r:raise ProfitabilityError(f"conflicting duplicate M1 {r['ts_start_utc']}")
    by[r["ts_start_utc"]]=r
   i+=1
  return [by[k] for k in sorted(by)][:count]
 def provenance(self)->dict:
  rows=[self.meta[k] for k in sorted(self.meta)];out={"schema_version":1,"provider":"OANDA_V20","environment":"practice","instrument":INSTRUMENT,"granularity":"M1","price_components":"BA","chunk_calendar_days":3,"origin":z(ORIGIN),"end_exclusive":z(OOS_END),"chunks_requested":len(rows),"chunks":rows,"first_m1_response_accessed":self.first_response_accessed,"credentials_exposed":False,"mutation_endpoints_used":False};out["provenance_sha256"]=engine.canon(out);return out
def write_jsonl(path:Path,rows:list[dict])->None:
 with path.open("w") as f:
  for r in rows:f.write(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--output-dir",required=True);ap.add_argument("--marker",default="research/profitability/V3C_PROFITABILITY_EXECUTE_LOCK.json");args=ap.parse_args();out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
 try:
  verify_lock(Path("research/profitability/v3c_profitability_execution_lock_v1.json"));marker=verify_marker(Path(args.marker));protocol=json.loads(Path("research/profitability/v3c_arguments_execution_protocol_v1.json").read_text());
  if protocol.get("protocol_sha256")!=PROTOCOL_SHA:raise ProfitabilityError("protocol SHA drift")
  structure_dir=out/"structure";manifest=structure.acquire(Path("research/profitability/nas100_oanda_backward_oos_request_contract.json"),structure_dir,delay=0.01)
  if manifest["request_contract_sha256"]!=STRUCTURE_CONTRACT_SHA:raise ProfitabilityError("structure contract drift")
  trigger_report=trigger_scan.build(structure_dir,Path("research/profitability/v3c_arguments_trigger_candidate.json"),Path("research/profitability/v3c_arguments_execution_protocol_v1.json"))
  if trigger_report["trigger_set_sha256"]!=TRIGGER_SHA or trigger_report["dual_path_exact_match"] is not True:raise ProfitabilityError("canonical trigger set did not reconstruct exactly")
  triggers=trigger_report["sealed_triggers"];kept,dup=engine.deduplicate(triggers)
  if len(triggers)!=2327 or len(kept)!=1888 or len(dup)!=439:raise ProfitabilityError("canonical trigger cardinality changed")
  cache=M1Cache(out/"m1-cache",os.getenv("OANDA_ACCOUNT_ID",""),os.getenv("OANDA_API_TOKEN",""))
  base=engine.evaluate_portfolio(triggers,cache.get_bars,scenario="BASE",slip_points=Decimal("0.5"),financing_r_per_1440=Decimal("0.005"));stress=engine.evaluate_portfolio(triggers,cache.get_bars,scenario="STRESS",slip_points=Decimal("1.0"),financing_r_per_1440=Decimal("0.01"));bm=engine.metrics(base);sm=engine.metrics(stress);classification=engine.classify(bm,sm);prov=cache.provenance()
  write_jsonl(out/"base-trade-ledger.jsonl",base["ledger"]);write_jsonl(out/"stress-trade-ledger.jsonl",stress["ledger"]);(out/"provider-provenance.json").write_text(json.dumps(prov,indent=2,sort_keys=True)+"\n")
  result={"schema_version":1,"status":"V3_ARGUMENTS_PROFITABILITY_RESULT_READY","classification":classification,"validated_profitable_edge":classification in {"PRELIMINARY_PROFITABLE_EDGE","STRONG_HISTORICAL_EDGE"},"strong_historical_edge":classification=="STRONG_HISTORICAL_EDGE","trigger_set_sha256":TRIGGER_SHA,"trigger_count":len(triggers),"deduplicated_signal_count":len(kept),"duplicate_knowledge_time_skips":len(dup),"execution_protocol_sha256":PROTOCOL_SHA,"profitability_execution_lock_sha256":LOCK_SHA,"execution_marker":marker,"structure_manifest_sha256":manifest["manifest_sha256"],"structure_retrieval_sha256":manifest["retrieval_sha256"],"provider_provenance_sha256":prov["provenance_sha256"],"base_metrics":bm,"stress_metrics":sm,"base_ledger_sha256":base["ledger_sha256"],"stress_ledger_sha256":stress["ledger_sha256"],"first_m1_response_accessed":cache.first_response_accessed,"parameter_changes_after_first_m1_response":False,"development_2024_2025_outcomes_accessed":False,"v2_2010_2023_trade_outcomes_accessed":False,"no_refit_performed":True,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};result["result_sha256"]=engine.canon(result);(out/"profitability-result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
  # Raw/parsed cache is intentionally not part of canonical output; request+response hashes bind every provider chunk.
  import shutil;shutil.rmtree(out/"m1-cache",ignore_errors=True);shutil.rmtree(structure_dir,ignore_errors=True)
 except Exception as exc:print(f"V3-C profitability execution failed: {exc}",file=sys.stderr);return 1
 print(json.dumps({"status":result["status"],"classification":classification,"validated_profitable_edge":result["validated_profitable_edge"],"base_resolved":bm["resolved_executed_trades"],"base_expectancy_r":bm["net_expectancy_r"],"base_profit_factor":bm["profit_factor"],"base_bootstrap_ci":bm["bootstrap_95pct_ci_net_expectancy_r"],"stress_resolved":sm["resolved_executed_trades"],"stress_expectancy_r":sm["net_expectancy_r"],"stress_profit_factor":sm["profit_factor"],"result_sha256":result["result_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
