#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT/'research/profitability/v3_multi_index_candidate_b.json'
ACQ=ROOT/'scripts/oanda_v3_multi_index_development.py'
SCAN=ROOT/'scripts/scan_v3_multi_index_coverage.py'

def main()->None:
    c=json.loads(CAND.read_text())
    assert c['candidate_sha256']=='c40cf7223bcb956d0e668e48dfeb29fbb7aa529fe45350710bbe5aaf2c2160b9'
    assert c['change_set']['fixed_candidate_instruments']==['NAS100_USD','SPX500_USD','US30_USD']
    assert c['change_set']['changed_dimension']=='instrument_eligibility_only'
    assert c['change_set']['all_v2_strategy_predicates']=='UNCHANGED'
    assert c['change_set']['v3_a_overlap_removal']=='NOT_INCLUDED'
    assert c['development_coverage']['post_entry_outcomes_allowed'] is False
    assert c['development_coverage']['performance_metrics_allowed'] is False
    assert c['backward_oos_boundary']['2010_2023_v2_outcomes_remain_unread'] is True
    for path in (ACQ,SCAN):
        text=path.read_text()
        for forbidden in ('measure_occurrence','v2_m1_execution_measurement','execution_outcomes','net_expectancy','profit_factor','win_rate','target_first','stop_first'):
            assert forbidden not in text.lower(), (path.name,forbidden)
    scan=SCAN.read_text()
    assert 'run_protected_validation_primary' in scan
    assert 'run_protected_validation_independent' in scan
    assert 'same-date cross-index signals count as one signal date for feasibility' in scan
    print('V3 multi-index coverage anti-outcome tests passed')

if __name__=='__main__':main()
