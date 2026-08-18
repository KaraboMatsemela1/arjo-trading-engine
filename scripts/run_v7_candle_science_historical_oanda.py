#!/usr/bin/env python3
from __future__ import annotations
import json,os,shutil,sys
from decimal import Decimal
from pathlib import Path
import check_v7_candle_science_historical_lock as lock_check
import check_v7_candle_science_protocol as protocol_check
from v6_momentum_backtest_mechanics import evaluate
from v6_momentum_m1_oanda import M1Cache
from v7_candle_science_backtest_metrics import classify,metrics
from v7_candle_science_primitives import canon
from v7_candle_science_reconstruct import compare_reconstructions
from v7_candle_science_structure import acquire_structure
PROTOCOL='98ed03185f93643e1c1b326835bee169e1f72a84d00c5a6aa4e56453a2a57134';TRIGGER='0286fc800d0b20399848945b2ae6b7520a6d314767a4ef8bb043b476bb3d2c98';READINESS='5d929529a3c386081cb45042e1fff1041eb795d1cc2ef92a30ad4bc2d8f8dd3b';STRUCTURE='a61ef4aa9deb1ed3de36611a12c9afd83ca25aeb8e55cd63004fd2328a39b414';LOCK='56a00ad6a45d926221330acf2c2160ce862752dc93f712c3b35b68cf35194049';FORWARD='83bdd46c80acec241499d5d99e76df22b8c11cdf4edd5983b4f4937582fdbc8e';AUTH=Path('research/profitability/V7_CANDLE_SCIENCE_M1_EXECUTE_LOCK.json')
def require_authorization()->dict:
    if not AUTH.exists():raise RuntimeError('V7 historical M1 authorization marker missing')
    x=json.loads(AUTH.read_text());expected={'status':'AUTHORIZED_RESEARCH_M1_READ_AFTER_PREFLIGHT','issue':280,'protocol_sha256':PROTOCOL,'trigger_set_sha256':TRIGGER,'trigger_count':5212,'distinct_knowledge_timestamps':4972,'historical_execution_lock_sha256':LOCK,'forward_confirmation_transport_sha256':FORWARD,'forward_confirmation_access_authorized':False,'paper_execution_authorized':False,'live_execution_authorized':False,'broker_mutation_authorized':False}
    if x!=expected:raise RuntimeError('V7 historical M1 authorization boundary changed')
    return x
def write_json(path:Path,value:object)->None:path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def write_jsonl(path:Path,rows:list[dict])->None:
    with path.open('w') as handle:
        for row in rows:handle.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
def main()->int:
    output=Path(os.getenv('V7_HIST_OUTPUT_DIR','artifacts/v7_candle_science_historical'));output.mkdir(parents=True,exist_ok=True);cache_dir=output/'m1-cache'
    try:
        protocol_check.verify();lock_check.verify();authorization=require_authorization();structure=acquire_structure();triggers,comparison=compare_reconstructions(structure['h4'],structure['h1']);trigger_sha=canon(triggers);distinct=len({row['knowledge_time_utc'] for row in triggers})
        if comparison['exact_match'] is not True:raise RuntimeError('V7 independent trigger reconstruction mismatch')
        if trigger_sha!=TRIGGER or len(triggers)!=5212 or distinct!=4972:raise RuntimeError(f'V7 sealed trigger set did not reproduce exactly sha={trigger_sha} count={len(triggers)} distinct={distinct}')
        if structure['manifest']['manifest_sha256']!=STRUCTURE:raise RuntimeError('V7 historical structure manifest did not reproduce exactly')
        token=os.getenv('OANDA_API_TOKEN','').strip()
        if not token:raise RuntimeError('OANDA_API_TOKEN missing')
        cache=M1Cache(cache_dir,token);base=evaluate(triggers,cache.get_bars,scenario='BASE',slip_points=Decimal('0.5'),financing_r_per_1440=Decimal('0.005'));stress=evaluate(triggers,cache.get_bars,scenario='STRESS',slip_points=Decimal('1.0'),financing_r_per_1440=Decimal('0.01'));bm=metrics(base);sm=metrics(stress);classification=classify(bm,sm);historical_pass=classification=='V7_CANDLE_SCIENCE_HISTORICAL_EDGE_ESTABLISHED';provenance=cache.provenance()
        if cache.first_response_accessed is not True:raise RuntimeError('V7 historical execution completed without first M1 response')
        write_jsonl(output/'base-trade-ledger.jsonl',base['ledger']);write_jsonl(output/'stress-trade-ledger.jsonl',stress['ledger']);write_json(output/'provider-provenance.json',provenance)
        result={'schema_version':1,'status':'V7_CANDLE_SCIENCE_HISTORICAL_PROFITABILITY_RESULT_READY','candidate_id':'ARJO_V7_NQ_CANDLE_SCIENCE_H1_FVG_REJECTION_TO_OPPOSING_FVG_SYMMETRIC','issue':280,'classification':classification,'historical_edge_established':historical_pass,'validated_profitable_edge':False,'forward_confirmation_authorized':historical_pass,'protocol_sha256':PROTOCOL,'trigger_set_sha256':TRIGGER,'trigger_count':len(triggers),'distinct_knowledge_timestamps':distinct,'trigger_readiness_sha256':READINESS,'structure_manifest_sha256':STRUCTURE,'historical_execution_lock_sha256':LOCK,'forward_confirmation_transport_sha256':FORWARD,'execution_authorization':authorization,'provider_provenance_sha256':provenance['provenance_sha256'],'base_metrics':bm,'stress_metrics':sm,'base_ledger_sha256':base['ledger_sha256'],'stress_ledger_sha256':stress['ledger_sha256'],'first_m1_response_accessed':True,'parameter_changes_after_first_m1_response':False,'cost_changes_after_first_m1_response':False,'threshold_changes_after_first_m1_response':False,'target_stop_rule_changes_after_first_m1_response':False,'no_refit_performed':True,'forward_confirmation_outcomes_accessed':False,'paper_execution_authorized':False,'live_execution_authorized':False,'broker_mutation_authorized':False};result['result_sha256']=canon(result);write_json(output/'historical-result.json',result)
        print(json.dumps({'classification':classification,'historical_edge_established':historical_pass,'validated_profitable_edge':False,'forward_confirmation_authorized':historical_pass,'base_resolved':bm['resolved_executed_trades'],'base_expectancy_r':bm['net_expectancy_r'],'base_profit_factor':bm['profit_factor'],'base_bootstrap_ci':bm['bootstrap_95pct_ci_net_expectancy_r'],'positive_calendar_year_fraction':bm['positive_calendar_year_fraction'],'stress_expectancy_r':sm['net_expectancy_r'],'stress_profit_factor':sm['profit_factor'],'result_sha256':result['result_sha256']},sort_keys=True));return 0
    except Exception as exc:print(f'V7 historical profitability execution failed: {exc}',file=sys.stderr);return 1
    finally:shutil.rmtree(cache_dir,ignore_errors=True)
if __name__=='__main__':raise SystemExit(main())
