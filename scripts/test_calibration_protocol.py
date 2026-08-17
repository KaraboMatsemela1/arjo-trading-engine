#!/usr/bin/env python3
"""Regression tests for FIRST_PARTY_PRESCRIBED_CALIBRATION_V1."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_calibration_protocol import validate_packet  # noqa: E402
def evidence(): return {"EV_DIRECT":{"EVIDENCE_ID":"EV_DIRECT","CONFIDENCE":"DIRECT"},"EV_PARTIAL":{"EVIDENCE_ID":"EV_PARTIAL","CONFIDENCE":"STRONG_PARTIAL"}}
def base_packet():
    return {"schema_version":1,"protocol":"FIRST_PARTY_PRESCRIBED_CALIBRATION_V1","packet_id":"TEST-CAL-001","predicate_id":"TEST_PREDICATE","stage":"PREREGISTERED","semantic_candidate_locked":True,"seed_plan":{"replayability_status":"REPLAYABLE","instrument":"NQ","timeframes":["4h","15m"],"rule_summary":"Frozen semantic seed","evidence_ids":["EV_DIRECT"]},"calibratable_parameters":[{"name":"entry_variant","semantic_role":"Refine a first-party-declared entry family only.","basis_evidence_ids":["EV_DIRECT","EV_PARTIAL"],"predeclared_candidates":["A","B"]}],"dataset":{"windows_declared":True,"calibration_start":"2024-01-01","calibration_end":"2024-12-31","holdout_start":"2025-01-01","holdout_end":"2025-06-30","calibration_data_accessed":False,"holdout_accessed":False},"objective":{"kind":"FIRST_PARTY_PARAMETER_REFINEMENT","predeclared_measure":"Choose only among preregistered parameter variants.","acceptance_rule":"Apply the frozen rule without adding concepts after outcome access."},"anti_bias":{"candidate_discovery_allowed":False,"new_concepts_after_outcome_access_allowed":False,"semantic_candidate_selection_by_performance_allowed":False,"holdout_use_during_calibration_allowed":False,"performance_leaderboard_allowed":False},"outcome_access_authorized":False}
def main():
    ev=evidence(); packet=base_packet(); assert validate_packet(packet,ev)==[]
    authorized=copy.deepcopy(packet); authorized["outcome_access_authorized"]=True; authorized["preregistration_ref"]="scripts/fixtures/calibration_preregistration.txt"; authorized["preregistration_sha256"]="bd4177e792e5f57f389f44a4ef63d3a5ade62aaa88aaa7810b3a9bea37d3fd6f"; assert validate_packet(authorized,ev)==[]
    bad_hash=copy.deepcopy(authorized); bad_hash["preregistration_sha256"]="a"*64; assert any("does not match" in e for e in validate_packet(bad_hash,ev))
    blocked=copy.deepcopy(authorized); blocked["seed_plan"]["replayability_status"]="BLOCKED_UNRESOLVED_EXECUTION_PARAMETERS"; assert any("REPLAYABLE seed plan" in e for e in validate_packet(blocked,ev))
    leaked=copy.deepcopy(authorized); leaked["dataset"]["holdout_accessed"]=True; assert any("holdout_accessed" in e for e in validate_packet(leaked,ev))
    late=copy.deepcopy(authorized); late["anti_bias"]["candidate_discovery_allowed"]=True; assert any("candidate_discovery_allowed" in e for e in validate_packet(late,ev))
    no_windows=copy.deepcopy(authorized); no_windows["dataset"]={"windows_declared":False,"calibration_data_accessed":False,"holdout_accessed":False}; assert any("frozen calibration and holdout windows" in e for e in validate_packet(no_windows,ev))
    premature=copy.deepcopy(authorized); premature["dataset"]["calibration_data_accessed"]=True; assert any("frozen before calibration data is accessed" in e for e in validate_packet(premature,ev))
    complete=copy.deepcopy(authorized); complete["stage"]="CALIBRATION_COMPLETE"; complete["dataset"]["calibration_data_accessed"]=True; complete["calibration_result_ref"]="research/calibration/result.json"; complete["calibration_result_sha256"]="b"*64; assert validate_packet(complete,ev)==[]
    print("Calibration protocol contract tests passed"); return 0
if __name__=="__main__": raise SystemExit(main())
