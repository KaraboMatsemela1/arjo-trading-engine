#!/usr/bin/env python3
from __future__ import annotations
import argparse,bisect,hashlib,json,sys
from collections import Counter
from datetime import UTC,datetime,timedelta
from pathlib import Path
import scan_v3c_arguments_trigger_coverage as v3c
CANDIDATE_SHA="de51f2c721aaedd0f6587755ebcab31ac2b264188d3de1f5531ec7057fb53b7b";PROTOCOL_SHA="0b3a6a5e217e7e4c279f7384c14579e97bf6821bc59deefac3086e7b4ce4ba7a";STRUCTURE_REQUEST_CONTRACT_SHA="e7169fa7b3d76ac6856bc64f78debf52af5330642403bd0a6adb6999ebb4de7f";END=datetime(2024,1,1,tzinfo=UTC);MIN_DISTINCT_KNOWLEDGE_TIMES=100
class TriggerSealError(RuntimeError):pass
def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def parse(v:str)->datetime:
 d=datetime.fromisoformat(v.replace("Z","+00:00"));
 if d.utcoffset() is None:raise TriggerSealError("naive timestamp")
 return d.astimezone(UTC)
def find_one(root:Path,name:str)->Path:
 h=list(root.rglob(name))
 if len(h)!=1:raise TriggerSealError(f"expected exactly one {name}, found {len(h)}")
 return h[0]
def verify_structure(root:Path)->dict:
 m=json.loads(find_one(root,"NAS100_USD.manifest.json").read_text());u=dict(m);rec=u.pop("manifest_sha256","")
 if not rec or canon(u)!=rec:raise TriggerSealError("structure manifest integrity failure")
 expected={"status":"PROFITABILITY_BACKWARD_OOS_STRUCTURE_READY","provider":"OANDA_V20","venue":"OANDA_FXTRADE","environment":"practice","instrument":"NAS100_USD","requested_price_components":"MBA","semantic_price_component":"MID","source_granularity":"M15","request_contract_sha256":STRUCTURE_REQUEST_CONTRACT_SHA,"requested_start":"2010-01-01T00:00:00Z","requested_end_exclusive":"2024-01-01T00:00:00Z","state_at_provider_first_bar":"EMPTY","post_entry_outcomes_evaluated":False,"m1_outcome_data_requested":False,"mutation_endpoints_used":False}
 for k,v in expected.items():
  if m.get(k)!=v:raise TriggerSealError(f"structure boundary changed: {k}")
 if parse(m["provider_first_complete_bar"])>=END or parse(m["provider_last_complete_bar"])>=END:raise TriggerSealError("structure chronology invalid")
 return m
def trigger_row(s:dict,a:dict,b:dict,rej:dict,act:dict)->dict:
 return {"trigger_id":f"V3C-{s['swing_id']}","swing_id":s["swing_id"],"swing_ts_utc":s["swing_ts_utc"],"swing_high":s["swing_high"],"swing_confirmed_at_utc":s["confirmed_at_utc"],"pair_first_ts_utc":a["ts_start_utc"],"pair_second_ts_utc":b["ts_start_utc"],"rejection_candle_ts_utc":rej["ts_start_utc"],"rejection_high":str(v3c.num(rej["high"],"rejection.high")),"activation_bar_ts_utc":act["ts_start_utc"],"activation_close":act["close"]}
def fast_primary(rows1:list[dict],swings:list[dict])->tuple[list[dict],dict]:
 times=[parse(r["ts_start_utc"]) for r in rows1];out=[];st=Counter()
 for s in swings:
  confirmed=parse(s["confirmed_at_utc"]);level=v3c.num(s["swing_high"],"swing.high");start=bisect.bisect_left(times,confirmed);chosen=None
  for i in range(start,len(rows1)-1):
   a,b=rows1[i],rows1[i+1]
   if times[i+1]-times[i]!=timedelta(hours=1):continue
   ar=v3c.num(a["high"],"a.high")>=level and v3c.num(a["close"],"a.close")<level;br=v3c.num(b["high"],"b.high")>=level and v3c.num(b["close"],"b.close")<level
   if ar or br:chosen=(i,a,b,b if br else a);break
  if chosen is None:st["NO_2CR_REJECTION_PAIR"]+=1;continue
  i,a,b,rej=chosen;rh=v3c.num(rej["high"],"rejection.high");act=None
  for row in rows1[i+2:]:
   if v3c.num(row["close"],"activation.close")>rh:act=row;break
  if act is None:st["NO_REJECTION_HIGH_RUN"]+=1;continue
  st["TRIGGERED"]+=1;out.append(trigger_row(s,a,b,rej,act))
 out.sort(key=lambda x:(x["activation_bar_ts_utc"],x["swing_id"]));return out,dict(sorted(st.items()))
def fast_independent(rows1:list[dict],swings:list[dict])->tuple[list[dict],dict]:
 times=[parse(r["ts_start_utc"]) for r in rows1];pairs=[];pair_times=[]
 for i in range(len(rows1)-1):
  if times[i+1]-times[i]==timedelta(hours=1):pairs.append((i,rows1[i],rows1[i+1]));pair_times.append(times[i])
 out=[];st=Counter()
 for s in swings:
  confirmed=parse(s["confirmed_at_utc"]);level=v3c.num(s["swing_high"],"swing.high");chosen=None
  for k in range(bisect.bisect_left(pair_times,confirmed),len(pairs)):
   i,a,b=pairs[k];ra=v3c.num(a["high"],"a.high")>=level and v3c.num(a["close"],"a.close")<level;rb=v3c.num(b["high"],"b.high")>=level and v3c.num(b["close"],"b.close")<level
   if ra or rb:chosen=(i,a,b,b if rb else a);break
  if chosen is None:st["NO_2CR_REJECTION_PAIR"]+=1;continue
  i,a,b,rej=chosen;rh=v3c.num(rej["high"],"rejection.high");next_time=parse(b["ts_start_utc"])+timedelta(hours=1);j=bisect.bisect_left(times,next_time);act=None
  for row in rows1[j:]:
   if v3c.num(row["close"],"activation.close")>rh:act=row;break
  if act is None:st["NO_REJECTION_HIGH_RUN"]+=1;continue
  st["TRIGGERED"]+=1;out.append(trigger_row(s,a,b,rej,act))
 out.sort(key=lambda x:(x["activation_bar_ts_utc"],x["swing_id"]));return out,dict(sorted(st.items()))
def parity_check(rows1:list[dict],rows4:list[dict])->None:
 p1=rows1[:min(3000,len(rows1))];cut=parse(p1[-1]["ts_start_utc"])+timedelta(hours=1);p4=[r for r in rows4 if parse(r["ts_start_utc"])<cut];sa=v3c.primary_swings(p4);sb=v3c.independent_swings(p4)
 if sa!=sb:raise TriggerSealError("bounded swing reference mismatch")
 refa,sta=v3c.primary_triggers(p1,sa);refb,stb=v3c.independent_triggers(p1,sb);fasta,fsta=fast_primary(p1,sa);fastb,fstb=fast_independent(p1,sb)
 if refa!=fasta or sta!=fsta or refb!=fastb or stb!=fstb or fasta!=fastb:raise TriggerSealError("optimized traversal failed bounded reference parity")
def enrich(triggers:list[dict],rows1:list[dict])->list[dict]:
 h1={r["ts_start_utc"]:r for r in rows1};out=[]
 for t in triggers:
  rej=h1.get(t["rejection_candle_ts_utc"]);act=h1.get(t["activation_bar_ts_utc"])
  if rej is None or act is None:raise TriggerSealError(f"trigger H1 row missing: {t['trigger_id']}")
  known=parse(t["activation_bar_ts_utc"])+timedelta(hours=1)
  if known>END:raise TriggerSealError("activation knowledge crosses OOS end")
  r=dict(t);r["rejection_low"]=str(rej["low"]);r["activation_known_at_utc"]=known.isoformat().replace("+00:00","Z");r["activation_h1_close"]=str(act["close"]);out.append(r)
 return sorted(out,key=lambda x:(x["activation_known_at_utc"],x["trigger_id"]))
def build(root:Path,candidate_path:Path,protocol_path:Path)->dict:
 m=verify_structure(root);c=json.loads(candidate_path.read_text());cr=c.pop("candidate_sha256","")
 if cr!=CANDIDATE_SHA or canon(c)!=CANDIDATE_SHA:raise TriggerSealError("candidate SHA drift")
 p=json.loads(protocol_path.read_text());pr=p.pop("protocol_sha256","")
 if pr!=PROTOCOL_SHA or canon(p)!=PROTOCOL_SHA:raise TriggerSealError("execution protocol SHA drift")
 if p["market_data"]["request_m1_only_after_backward_oos_trigger_set_is_sealed"] is not True or p["market_data"]["development_2024_2025_outcomes_must_remain_unread"] is not True:raise TriggerSealError("protocol outcome boundary changed")
 v3c.START=parse(m["provider_first_complete_bar"]);v3c.END=END;rows1=v3c.load_rows([root],60);rows4=v3c.load_rows([root],240);parity_check(rows1,rows4);sa=v3c.primary_swings(rows4);sb=v3c.independent_swings(rows4)
 if sa!=sb:raise TriggerSealError("swing mismatch")
 ta,sta=fast_primary(rows1,sa);tb,stb=fast_independent(rows1,sb)
 if ta!=tb or sta!=stb:raise TriggerSealError("trigger mismatch")
 sealed=enrich(ta,rows1);times=sorted({x["activation_known_at_utc"] for x in sealed});years=Counter(parse(x["activation_known_at_utc"]).year for x in sealed);ok=len(times)>=MIN_DISTINCT_KNOWLEDGE_TIMES
 r={"schema_version":1,"status":"V3_ARGUMENTS_BACKWARD_OOS_TRIGGERS_READY","classification":"TRIGGER_SAMPLE_NECESSARY_CONDITION_MET" if ok else "INSUFFICIENT_TRIGGER_SAMPLE_EDGE_NOT_ESTABLISHED","candidate_sha256":CANDIDATE_SHA,"execution_protocol_sha256":PROTOCOL_SHA,"structure_request_contract_sha256":STRUCTURE_REQUEST_CONTRACT_SHA,"structure_manifest_sha256":m["manifest_sha256"],"structure_retrieval_sha256":m["retrieval_sha256"],"structure_transport":"DETERMINISTIC_REACQUISITION_UNDER_FROZEN_M15_CONTRACT_AFTER_GITHUB_ARTIFACT_503","provider_first_complete_bar":m["provider_first_complete_bar"],"end_exclusive":"2024-01-01T00:00:00Z","h4_swing_high_count":len(sa),"trigger_status_counts":sta,"trigger_count":len(sealed),"distinct_activation_knowledge_times":len(times),"minimum_distinct_knowledge_times_required":MIN_DISTINCT_KNOWLEDGE_TIMES,"sample_necessary_condition_met":ok,"triggers_by_activation_year":{str(k):years[k] for k in sorted(years)},"trigger_set_sha256":canon(sealed),"sealed_triggers":sealed,"dual_path_exact_match":True,"optimized_traversal_reference_parity":True,"m1_data_requested":False,"post_trigger_price_traversal_accessed":False,"performance_metrics_accessed":False,"development_2024_2025_outcomes_accessed":False,"v2_2010_2023_trade_outcomes_accessed":False,"no_refit_performed":True,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False};r["report_sha256"]=canon(r);return r
def main()->int:
 a=argparse.ArgumentParser();a.add_argument("--artifact-dir",required=True);a.add_argument("--candidate",required=True);a.add_argument("--protocol",required=True);a.add_argument("--output",required=True);x=a.parse_args()
 try:r=build(Path(x.artifact_dir),Path(x.candidate),Path(x.protocol));Path(x.output).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
 except Exception as e:print(f"V3-C backward-OOS trigger seal failed: {e}",file=sys.stderr);return 1
 print(json.dumps({"status":r["status"],"classification":r["classification"],"swings":r["h4_swing_high_count"],"triggers":r["trigger_count"],"distinct_knowledge_times":r["distinct_activation_knowledge_times"],"sample_necessary_condition_met":r["sample_necessary_condition_met"],"trigger_set_sha256":r["trigger_set_sha256"],"outcomes_accessed":False,"report_sha256":r["report_sha256"]},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
