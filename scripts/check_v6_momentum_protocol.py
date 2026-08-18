#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PROTOCOL = Path('research/profitability/v6_momentum_protocol_v1.json')
BOUNDARY = Path('research/profitability/v6_momentum_pre_outcome_boundary_v1.json')
SOURCE = Path('research/profitability/v6_momentum_source_recovery.md')
V5_RESULT = Path('research/profitability/v5_nra_historical_result_v1.json')
EXPECTED_PROTOCOL_SHA = '8a4839f9c9c07bec97aa78fe57ea246e8c256ad88c458ce9bf37b9f5b1b892ab'
EXPECTED_V5_RESULT_SHA = '4474926ae20e67d5e23010a62654d41d2a3f6cefbff835f7c122e011c64d7345'


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def verify() -> None:
    p = json.loads(PROTOCOL.read_text())
    recorded = p.pop('protocol_sha256')
    assert recorded == EXPECTED_PROTOCOL_SHA
    assert canon(p) == EXPECTED_PROTOCOL_SHA
    assert p['status'] == 'FROZEN_BEFORE_ANY_V6_MARKET_DATA_ACCESS'
    assert p['candidate_id'] == 'ARJO_V6_NQ_MOMENTUM_CYCLE_CONTINUATION_H1_M15_SYMMETRIC'
    assert p['engine_conventions']['historical_window_end_exclusive'] == '2024-01-01T00:00:00Z'
    assert p['forward_confirmation_policy']['economics_access_only_after_historical_pass'] is True
    assert p['forward_confirmation_policy']['historical_pass_alone_is_validated_profitable_edge'] is False
    assert p['trigger_gate']['minimum_sealed_triggers_before_m1'] == 250
    assert p['historical_edge_gate']['minimum_resolved_executed_trades'] == 250
    assert p['historical_edge_gate']['base_profit_factor_gt'] == 1.3
    assert p['historical_edge_gate']['positive_calendar_year_fraction_gte'] == 0.7
    assert p['multiple_testing']['failed_family_post_result_tuning_permitted'] is False
    assert p['multiple_testing']['consumed_failed_ledger_mining_permitted'] is False
    assert p['safety'] == {
        'broker_mutation_authorized': False,
        'live_execution_authorized': False,
        'paper_execution_authorized': False,
    }

    b = json.loads(BOUNDARY.read_text())
    assert b['protocol_sha256'] == EXPECTED_PROTOCOL_SHA
    forbidden_true = [
        'v6_market_structure_accessed','v6_h1_accessed','v6_m15_accessed','v6_m1_accessed',
        'v6_bid_ask_accessed','v6_triggers_constructed','v6_pnl_accessed','v6_expectancy_accessed',
        'v6_profit_factor_accessed','v6_bootstrap_outcomes_accessed','v6_forward_confirmation_outcomes_accessed',
        'v5_post_result_tuning_used','v5_consumed_ledger_mining_used','paper_execution','live_execution','broker_mutation'
    ]
    for key in forbidden_true:
        assert b[key] is False, key

    assert SOURCE.exists()
    source = SOURCE.read_text()
    for required in [
        'market-structure-order-flow-candle-science', 'the-momentum-theory', 'the-3-cycles-of-momentum',
        'the-best-ltf-entries-happen-here', 'the-easiest-areas-to-trade', 'the-closer-the-dol-the-better-your-trade-is'
    ]:
        assert required in source

    v5 = json.loads(V5_RESULT.read_text())
    assert v5['result_sha256'] == EXPECTED_V5_RESULT_SHA
    assert v5['classification'] == 'EDGE_NOT_ESTABLISHED'
    assert v5['post_result_tuning_permitted'] is False
    assert v5['forward_confirmation_authorized'] is False


if __name__ == '__main__':
    verify()
    print('v6_momentum_protocol=' + EXPECTED_PROTOCOL_SHA)
    print('v6_pre_outcome_boundary=PASS')
