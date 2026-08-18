#!/usr/bin/env python3
from __future__ import annotations
import os
from typing import Any
from v6_momentum_structure import acquire
from v7_candle_science_primitives import canon

def acquire_structure()->dict[str,Any]:
    token=os.getenv('OANDA_TOKEN','').strip()
    if not token:raise RuntimeError('OANDA_TOKEN required for read-only V7 structure acquisition')
    h4,h4_provenance=acquire(token,'H4',240,240)
    h1,h1_provenance=acquire(token,'H1',60,120)
    manifest={'schema_version':1,'provider':'OANDA_V20_PRACTICE_READ_ONLY','instrument':'NAS100_USD','price':'M','granularities':['H4','H1'],'strict_start':'2010-01-01T00:00:00Z','strict_end_exclusive':'2024-01-01T00:00:00Z','daily_alignment':17,'alignment_timezone':'America/New_York','weekly_alignment':'Friday','h4_rows':len(h4),'h1_rows':len(h1),'h4_sha256':canon(h4),'h1_sha256':canon(h1),'h4_provenance_sha256':canon(h4_provenance),'h1_provenance_sha256':canon(h1_provenance),'m1_requested':False,'bid_ask_requested':False,'economic_outcomes_accessed':False,'paper_execution':False,'live_execution':False,'broker_mutation':False};manifest['manifest_sha256']=canon(manifest)
    return {'h4':h4,'h1':h1,'h4_provenance':h4_provenance,'h1_provenance':h1_provenance,'manifest':manifest}
