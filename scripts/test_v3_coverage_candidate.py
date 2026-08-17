#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT/'research/profitability/v3_coverage_candidate_a.json'
SCRIPT=ROOT/'scripts/diagnose_v3_coverage_candidate.py'


def main()->None:
    c=json.loads(CAND.read_text())
    assert c['candidate_id']=='ARJO_DERIVED_OWNER_OPERATIONAL_V3_COVERAGE_A'
    assert c['candidate_sha256']=='21907522648f957ad620a0d0d9e3f1c3f9de4f222e92866b1db37bb91271c305'
    assert c['change_set']['changed_field']=='fva.required_relationship_to_4h_fvg'
    assert c['change_set']['all_other_owner_operational_predicates']=='UNCHANGED'
    assert c['development_only_evaluation']['post_entry_outcomes_allowed'] is False
    assert c['development_only_evaluation']['coverage_feasibility_floor_per_2y']==30
    assert c['backward_oos_boundary']['2010_2023_post_entry_outcomes_accessed'] is False
    text=SCRIPT.read_text()
    forbidden=['measure_occurrence','v2_m1_execution_measurement','execution_outcomes','net_expectancy','profit_factor','win_rate']
    for token in forbidden:
        assert token not in text, token
    assert 'NO_FVA_OVERLAP' not in text
    assert 'fvg_fva_overlap_required' in text
    print('V3 coverage candidate anti-outcome tests passed')

if __name__=='__main__': main()
