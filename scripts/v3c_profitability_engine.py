#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math,random,statistics
from collections import Counter,defaultdict
from datetime import UTC,datetime
from decimal import Decimal
from typing import Callable
RESOLVED={"STOP","TARGET","EXPIRY"}
def canon(x:object)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def ts(v:str)->datetime:
 d=datetime.fromisoformat(v.replace("Z","+00:00"))
 if d.utcoffset() is None:raise ValueError("naive timestamp")
 return d.astimezone(UTC)
def dec(x:object)->Decimal:return Decimal(str(x))
def deduplicate(triggers:list[dict])->tuple[list[dict],list[dict]]:
 groups=defaultdict(list)
 for r in triggers:groups[r["activation_known_at_utc"]].append(r)
 kept=[];skipped=[]
 for knowledge in sorted(groups):
  candidates=sorted(groups[knowledge],key=lambda x:(x["swing_confirmed_at_utc"],x["trigger_id"]));winner=candidates[-1];kept.append(winner)
  for r in candidates[:-1]:skipped.append({"trigger_id":r["trigger_id"],"knowledge_time_utc":knowledge,"status":"SKIPPED_DUPLICATE_KNOWLEDGE_TIME","kept_trigger_id":winner["trigger_id"]})
 return kept,skipped
def measure_trade(trigger:dict,bars:list[dict],*,slip_points:Decimal,financing_r_per_1440:Decimal)->dict:
 knowledge=ts(trigger["activation_known_at_utc"]);eligible=[b for b in bars if ts(b["ts_start_utc"])>=knowledge]
 if not eligible or (ts(eligible[0]["ts_start_utc"])-knowledge).total_seconds()>72*3600:return {"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"status":"DATA_INTEGRITY_FAILURE","reason":"NO_ELIGIBLE_M1_WITHIN_72H"}
 first=eligible[0];entry=dec(first["ask"]["o"])+slip_points;stop=dec(trigger["rejection_low"]);risk=entry-stop
 if risk<=0:return {"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"entry_ts_utc":first["ts_start_utc"],"entry_price":str(entry),"stop_price":str(stop),"status":"INVALID_RISK_ORDERING"}
 target=entry+Decimal("2")*risk;usable=eligible[:1440]
 for idx,bar in enumerate(usable):
  bo,bh,bl=dec(bar["bid"]["o"]),dec(bar["bid"]["h"]),dec(bar["bid"]["l"]);stop_hit,target_hit=bl<=stop,bh>=target
  if stop_hit:raw=bo if bo<=stop else stop;exit_price=raw-slip_points;status="STOP"
  elif target_hit:exit_price=target-slip_points;status="TARGET"
  else:continue
  held=idx+1;gross=(exit_price-entry)/risk;fin=financing_r_per_1440*Decimal(held)/Decimal(1440)
  return {"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"entry_ts_utc":first["ts_start_utc"],"exit_ts_utc":bar["ts_start_utc"],"status":status,"entry_price":str(entry),"stop_price":str(stop),"target_price":str(target),"exit_price":str(exit_price),"risk_points":str(risk),"complete_m1_bars_held":held,"gross_r":float(gross),"financing_r":float(fin),"net_r":float(gross-fin),"same_m1_stop_and_target":bool(stop_hit and target_hit)}
 if len(usable)<1440:return {"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"entry_ts_utc":first["ts_start_utc"],"entry_price":str(entry),"stop_price":str(stop),"target_price":str(target),"risk_points":str(risk),"complete_m1_bars_observed":len(usable),"status":"RIGHT_CENSORED_OOS_END"}
 final=usable[-1];exit_price=dec(final["bid"]["c"])-slip_points;gross=(exit_price-entry)/risk
 return {"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"entry_ts_utc":first["ts_start_utc"],"exit_ts_utc":final["ts_start_utc"],"status":"EXPIRY","entry_price":str(entry),"stop_price":str(stop),"target_price":str(target),"exit_price":str(exit_price),"risk_points":str(risk),"complete_m1_bars_held":1440,"gross_r":float(gross),"financing_r":float(financing_r_per_1440),"net_r":float(gross-financing_r_per_1440),"same_m1_stop_and_target":False}
def evaluate_portfolio(triggers:list[dict],get_bars:Callable[[datetime,int],list[dict]],*,scenario:str,slip_points:Decimal,financing_r_per_1440:Decimal)->dict:
 kept,duplicate_skips=deduplicate(triggers);ledger=list(duplicate_skips);open_until=None
 for trigger in kept:
  knowledge=ts(trigger["activation_known_at_utc"])
  if open_until is not None and knowledge<=open_until:ledger.append({"trigger_id":trigger["trigger_id"],"knowledge_time_utc":trigger["activation_known_at_utc"],"status":"SKIPPED_CONCURRENT_POSITION","prior_position_exit_m1_start_utc":open_until.isoformat().replace("+00:00","Z")});continue
  r=measure_trade(trigger,get_bars(knowledge,1440),slip_points=slip_points,financing_r_per_1440=financing_r_per_1440);ledger.append(r)
  if r["status"] in RESOLVED:open_until=ts(r["exit_ts_utc"])
 ledger.sort(key=lambda x:(x.get("knowledge_time_utc",""),x["trigger_id"],x["status"]));return {"scenario":scenario,"ledger":ledger,"ledger_sha256":canon(ledger)}
def _pf(v:list[float])->tuple[float,bool,float,float]:
 pos=sum(x for x in v if x>0);neg=sum(x for x in v if x<0)
 return ((math.inf if pos>0 else 0.0),True,pos,neg) if neg==0 else (pos/abs(neg),False,pos,neg)
def _max_dd(v:list[float])->float:
 eq=peak=worst=0.0
 for x in v:eq+=x;peak=max(peak,eq);worst=max(worst,peak-eq)
 return worst
def _bootstrap(v:list[float],n:int=10000,seed:int=20260817)->tuple[float|None,float|None]:
 if not v:return None,None
 rng=random.Random(seed);size=len(v);means=[sum(v[rng.randrange(size)] for _ in range(size))/size for _ in range(n)];means.sort();return means[int(.025*(n-1))],means[int(.975*(n-1))]
def metrics(portfolio:dict)->dict:
 ledger=portfolio["ledger"];resolved=[x for x in ledger if x["status"] in RESOLVED];values=[float(x["net_r"]) for x in resolved];pf,no_losses,pos,neg=_pf(values);years=defaultdict(list)
 for r in resolved:years[str(ts(r["entry_ts_utc"]).year)].append(float(r["net_r"]))
 year_exp={y:sum(v)/len(v) for y,v in sorted(years.items())};lo,hi=_bootstrap(values);st=dict(sorted(Counter(x["status"] for x in ledger).items()))
 out={"scenario":portfolio["scenario"],"ledger_sha256":portfolio["ledger_sha256"],"resolved_executed_trades":len(resolved),"total_ledger_rows":len(ledger),"status_counts":st,"data_integrity_failures":st.get("DATA_INTEGRITY_FAILURE",0),"synthetic_fills":0,"skipped_duplicate_signals":st.get("SKIPPED_DUPLICATE_KNOWLEDGE_TIME",0),"skipped_concurrent_signals":st.get("SKIPPED_CONCURRENT_POSITION",0),"invalid_risk_signals":st.get("INVALID_RISK_ORDERING",0),"right_censored_signals":st.get("RIGHT_CENSORED_OOS_END",0),"net_expectancy_r":sum(values)/len(values) if values else None,"median_net_r":statistics.median(values) if values else None,"profit_factor":None if math.isinf(pf) else pf,"no_negative_trades":no_losses,"positive_r_sum":pos,"negative_r_sum":neg,"win_rate":sum(1 for x in values if x>0)/len(values) if values else None,"max_drawdown_r":_max_dd(values),"bootstrap_95pct_ci_net_expectancy_r":[lo,hi],"calendar_year_net_expectancy_r":year_exp,"positive_calendar_year_fraction":sum(1 for x in year_exp.values() if x>0)/len(year_exp) if year_exp else None,"unique_entry_dates":len({x["entry_ts_utc"][:10] for x in resolved})};out["metrics_sha256"]=canon(out);return out
def pf_threshold_value(m:dict)->float:return math.inf if m["no_negative_trades"] and m["positive_r_sum"]>0 else float(m["profit_factor"] or 0.0)
def classify(base:dict,stress:dict)->str:
 if base["resolved_executed_trades"]<100:return "INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED"
 bpf,spf=pf_threshold_value(base),pf_threshold_value(stress);lo=base["bootstrap_95pct_ci_net_expectancy_r"][0]
 prelim=base["net_expectancy_r"] is not None and base["net_expectancy_r"]>0 and bpf>1.2 and lo is not None and lo>0 and stress["net_expectancy_r"] is not None and stress["net_expectancy_r"]>0 and spf>1.0 and base["data_integrity_failures"]==0 and stress["data_integrity_failures"]==0 and base["synthetic_fills"]==0 and stress["synthetic_fills"]==0
 if not prelim:return "EDGE_NOT_ESTABLISHED"
 strong=base["resolved_executed_trades"]>=250 and bpf>1.3 and lo is not None and lo>0 and stress["net_expectancy_r"] is not None and stress["net_expectancy_r"]>0 and (base["positive_calendar_year_fraction"] or 0)>=.7 and base["data_integrity_failures"]==0
 return "STRONG_HISTORICAL_EDGE" if strong else "PRELIMINARY_PROFITABLE_EDGE"
