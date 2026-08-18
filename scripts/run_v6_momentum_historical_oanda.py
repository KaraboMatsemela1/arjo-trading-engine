#!/usr/bin/env python3
from __future__ import annotations
import json,os,shutil
from decimal import Decimal
from pathlib import Path
import check_v6_momentum_historical_lock as lock_check
import check_v6_momentum_protocol as protocol_check
from v6_momentum_backtest_mechanics import evaluate
from v6_momentum_backtest_metrics import classify,metrics
from v6_momentum_m1_oanda import M1Cache
from v6_momentum_primitives import canon
from v6_momentum_reconstruct import compare_reconstructions
from v6_momentum_structure import acquire_structure

PROTOCOL_SHA='8a4839f9c9c07bec97aa78fe57ea246e8c256ad88c458ce9bf37b9f5b1b892ab'
TRIGGER_SHA='644edb8b1fe008a053f4fbdc368f6117d1c20ba478b9277bb1fb1f8f5cf9a150'
READINESS_SHA='f214b9154b3c40fb6cc472fd8858bc4781aedb3c28e7d4f252d0832dbf3b9cad'
STRUCTURE_SHA='4cb58637b433b544865a6a94cdc2b48b344d47824e8ba0f76b9be5f67496dd2c'
LOCK_SHA='1d883fe81a274aa81437da2ca732d09f887529cea3d07a8d58f0a85ed2c2f779'
FORWARD_SHA='24bbcc1c31f1469c45ca70cffdf1fafb4821cada857c9ab04233d90bca601ce6'
AUTH=Path('research/profitability/V6_MOMENTUM_M1_EXECUTE_LOCK.json')

def require_authorization()->dict:
    if not AUTH.exists():raise RuntimeError('V6 historical M1 authorization marker missing')
    x=json.loads(AUTH.read_text());expected={'status':'AUTHORIZED_RESEARCH_M1_READ_AFTER_PREFLIGHT','issue':270,'protocol_sha256':PROTOCOL_SHA,'trigger_set_sha256':TRIGGER_SHA,'trigger_count':1331,'distinct_knowledge_timestamps':441,'historical_execution_lock_sha256':LOCK_SHA,'forward_confirmation_transport_sha256':FORWARD_SHA,'forward_confirmation_access_authorized':False,'paper_execution_authorized':False,'live_execution_authorized':False,'broker_mutation_authorized':False}
    if x!=expected:raise RuntimeError('V6 historical M1 authorization boundary changed')
    return x

def write_json(path:Path,value:object)->None:path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def write_jsonl(path:Path,rows:list[dict])->None:
    with path.open('w') as f:
        for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')

def main()->int:
    output=Path(os.environ.get('V6_HIST_OUTPUT_DIR','artifacts/v6_momentum_historical'));output.mkdir(parents=True,exist_ok=True);cache_dir=output/'m1-cache';result=None
    try:
        protocol_check.verify();lock_check.verify();authorization=require_authorization()
        structure=acquire_structure();triggers,comparison=compare_reconstructions(structure['h1'],structure['m15']);trigger_sha=canon(triggers);distinct=len({row['knowledge_time_utc'] for row in triggers})
        if comparison['exact_match'] is not True:raise RuntimeError('V6 independent trigger reconstruction mismatch')
        if trigger_sha!=TRIGGER_SHA or len(triggers)!=1331 or distinct!=441:raise RuntimeError(f'V6 sealed trigger set did not reproduce exactly sha={trigger_sha} count={len(triggers)} distinct={distinct}')
        if structure['manifest']['manifest_sha256']!=STRUCTURE_SHA:raise RuntimeError('V6 historical structure manifest did not reproduce exactly')
        token=os.getenv('OANDA_API_TOKEN','').strip()
        if not token:raise RuntimeError('OANDA_API_TOKEN missing')
        cache=M1Cache(cache_dir,token)
        base=evaluate(triggers,cache.get_bars,scenario='BASE',slip_points=Decimal('0.5'),financing_r_per_1440=Decimal('0.005'))
        stress=evaluate(triggers,cache.get_bars,scenario='STRESS',slip_points=Decimal('1.0'),financing_r_per_1440=Decimal('0.01'))
        base_metrics=metrics(base);stress_metrics=metrics(stress);classification=classify(base_metrics,stress_metrics);historical_pass=classification=='V6_MOMENTUM_HISTORICAL_EDGE_ESTABLISHED';provenance=cache.provenance()
        if cache.first_response_accessed is not True:raise RuntimeError('historical execution completed without a first M1 response')
        write_jsonl(output/'base-trade-ledger.jsonl',base['ledger']);write_jsonl(output/'stress-trade-ledger.jsonl',stress['ledger']);write_json(output/'provider-provenance.json',provenance)
        result={'schema_version':1,'status':'V6_MOMENTUM_HISTORICAL_PROFITABILITY_RESULT_READY','candidate_id':'ARJO_V6_NQ_MOMENTUM_CYCLE_CONTINUATION_H1_M15_SYMMETRIC','issue':270,'classification':classification,'historical_edge_established':historical_pass,'validated_profitable_edge':False,'forward_confirmation_authorized':historical_pass,'protocol_sha256':PROTOCOL_SHA,'trigger_set_sha256':TRIGGER_SHA,'trigger_count':len(triggers),'distinct_knowledge_timestamps':distinct,'trigger_readiness_sha256':READINESS_SHA,'structure_manifest_sha256':STRUCTURE_SHA,'historical_execution_lock_sha256':LOCK_SHA,'forward_confirmation_transport_sha256':FORWARD_SHA,'execution_authorization':authorization,'provider_provenance_sha256':provenance['provenance_sha256'],'base_metrics':base_metrics,'stress_metrics':stress_metrics,'base_ledger_sha256':base['ledger_sha256'],'stress_ledger_sha256':stress['ledger_sha256'],'first_m1_response_accessed':True,'parameter_changes_after_first_m1_response':False,'cost_changes_after_first_m1_response':False,'threshold_changes_after_first_m1_response':False,'target_stop_rule_changes_after_first_m1_response':False,'no_refit_performed':True,'forward_confirmation_outcomes_accessed':False,'paper_execution_authorized':False,'live_execution_authorized':False,'broker_mutation_authorized':False};result['result_sha256']=canon(result);write_json(output/'historical-result.json',result)
        print(json.dumps({'classification':classification,'historical_edge_established':historical_pass,'validated_profitable_edge':False,'forward_confirmation_authorized':historical_pass,'base_resolved':base_metrics['resolved_executed_trades'],'base_expectancy_r':base_metrics['net_expectancy_r'],'base_profit_factor':base_metrics['profit_factor'],'base_bootstrap_ci':base_metrics['bootstrap_95pct_ci_net_expectancy_r'],'positive_calendar_year_fraction':base_metrics['positive_calendar_year_fraction'],'stress_expectancy_r':stress_metrics['net_expectancy_r'],'stress_profit_factor':stress_metrics['profit_factor'],'result_sha256':result['result_sha256']},sort_keys=True))
    except Exception as exc:
        print(f'V6 historical profitability execution failed: {exc}',file=__import__('sys').stderr);return 1
    finally:
        shutil.rmtree(cache_dir,ignore_errors=True)
        # H1/M15 normalized rows are not persisted by this runner; the pre-M1 sealed hashes bind them.
    return 0

if __name__=='__main__':raise SystemExit(main())
