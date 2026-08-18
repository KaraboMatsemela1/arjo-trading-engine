#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
from v7_candle_science_structure import acquire_structure as _acquire

def acquire_structure()->dict[str,Any]:
    structure=_acquire()
    manifest=structure['manifest']
    assert manifest['price']=='M'
    assert manifest['granularities']==['H4','H1']
    assert manifest['strict_end_exclusive']=='2024-01-01T00:00:00Z'
    assert manifest['m1_requested'] is False
    assert manifest['bid_ask_requested'] is False
    assert manifest['economic_outcomes_accessed'] is False
    assert manifest['broker_mutation'] is False
    return structure
