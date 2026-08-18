#!/usr/bin/env python3
"""Sabotage regressions for the frozen V5 protocol."""
from __future__ import annotations
import json, tempfile
from pathlib import Path
import check_v5_no_resistance_aoo_protocol as check

P = json.loads(check.PROTOCOL.read_text())
B = json.loads(check.BOUNDARY.read_text())

def must_fail(p: dict, b: dict) -> None:
    with tempfile.TemporaryDirectory() as td:
        pp, bp = Path(td)/"p.json", Path(td)/"b.json"
        pp.write_text(json.dumps(p), encoding="utf-8")
        bp.write_text(json.dumps(b), encoding="utf-8")
        try:
            check.verify(pp, bp)
        except (AssertionError, KeyError):
            return
        raise AssertionError("sabotage unexpectedly passed")

mutations = []
p = json.loads(json.dumps(P)); p["market_data"]["historical_structure_end_exclusive"]="2025-01-01T00:00:00Z"; mutations.append((p,B))
p = json.loads(json.dumps(P)); p["h4_target"]["ath_proxy_forbidden"]=False; mutations.append((p,B))
p = json.loads(json.dumps(P)); p["economics"]["base_slippage_points_per_side"]=0.0; mutations.append((p,B))
p = json.loads(json.dumps(P)); p["classification_rules"]["V5_HISTORICAL_EDGE_ESTABLISHED"]["base_profit_factor_gt"]=1.0; mutations.append((p,B))
p = json.loads(json.dumps(P)); p["authorization"]["paper_execution"]=True; mutations.append((p,B))
b = json.loads(json.dumps(B)); b["v5_economic_outcomes_accessed"]=True; mutations.append((P,b))
for p,b in mutations: must_fail(p,b)
check.verify()
print(f"v5_protocol_sabotage_cases={len(mutations)} PASS")
