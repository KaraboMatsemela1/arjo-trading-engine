#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from check_v2_future_validation_access_v2 import CONTRACT_SHA, POLICY_SHA, PROTOCOL_SHA, authorize
from compare_v2_future_validation_paths import canon as compare_canon, compare
from run_v2_future_validation_independent import evaluate_core as independent_core
from run_v2_future_validation_primary import evaluate_core as primary_core
from seal_v2_future_validation_result import seal

ROOT=Path(__file__).resolve().parents[1]


def six_bar_session()->list[dict]:
    times=["2026-10-05T13:30:00Z","2026-10-05T13:45:00Z","2026-10-05T14:00:00Z","2026-10-05T14:15:00Z","2026-10-05T14:30:00Z","2026-10-05T14:45:00Z"]
    return [{"ts_start_utc":ts,"open":"100","high":"101","low":"99","close":"100","minutes":15} for ts in times]


def wrap(path_id:str,state:dict)->dict:
    report={"schema_version":1,"path_id":path_id,"status":"V2_FUTURE_VALIDATION_PATH_COMPLETE","profile_sha256":"87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6","protocol_sha256":PROTOCOL_SHA,"measurement_policy_sha256":POLICY_SHA,"data_manifest_sha256":"synthetic-manifest",**state,"holdout_2026h1_accessed":False,"pre_start_market_data_accessed":False,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
    report["report_sha256"]=compare_canon(report); return report


class HarnessTests(unittest.TestCase):
    def test_dual_paths_agree_on_synthetic_no_occurrence(self)->None:
        rows15=six_bar_session(); primary=primary_core(rows15=rows15,rows60=[],rows240=[],m1_rows=[]); independent=independent_core(rows15=rows15,rows60=[],rows240=[],m1_rows=[])
        self.assertEqual(primary,independent)
        self.assertEqual(primary["complete_session_count"],1)
        self.assertEqual(primary["qualification_status_counts"],{"NO_FVG":1})
        self.assertEqual(primary["validation_classification"],"NO_QUALIFYING_OCCURRENCES")
        p=wrap("PRIMARY_V2_PRODUCTION_PATH",primary); i=wrap("INDEPENDENT_V2_STANDARD_LIBRARY_PATH",independent); c=compare(p,i)
        self.assertTrue(c["implementation_agreement"])
        final=seal(p,i,c)
        self.assertEqual(final["validation_classification"],"NO_QUALIFYING_OCCURRENCES")
        self.assertFalse(final["paper_execution_authorized"])

    def test_final_gate_denies_before_march_even_with_perfect_authorization(self)->None:
        auth={"authorization_id":"ARJO_V2_FUTURE_VALIDATION_DATA_ACCESS_V1","gate":"acquisition","authorized":True,"protocol_sha256":PROTOCOL_SHA,"measurement_policy_sha256":POLICY_SHA,"request_contract_sha256":CONTRACT_SHA,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
        with tempfile.NamedTemporaryFile("w",suffix=".json",delete=False) as handle:
            json.dump(auth,handle); path=Path(handle.name)
        with self.assertRaises(RuntimeError):
            authorize(gate="acquisition",now=datetime(2027,2,28,23,59,tzinfo=UTC),authorization_path=path,protocol_path=ROOT/"research/v2/future_validation_protocol_v2.json",policy_path=ROOT/"research/v2/v2_m1_touch_sequencing_v1.json",readiness_path=ROOT/"research/v2/v2_m1_measurement_readiness.json",contract_path=ROOT/"research/v2/nas100_oanda_future_validation_request_contract.json")

    def test_exact_authorization_can_open_after_march_without_enabling_trading(self)->None:
        auth={"authorization_id":"ARJO_V2_FUTURE_VALIDATION_EVALUATION_V1","gate":"evaluation","authorized":True,"protocol_sha256":PROTOCOL_SHA,"measurement_policy_sha256":POLICY_SHA,"request_contract_sha256":CONTRACT_SHA,"paper_execution_authorized":False,"live_execution_authorized":False,"broker_mutation_authorized":False}
        with tempfile.NamedTemporaryFile("w",suffix=".json",delete=False) as handle:
            json.dump(auth,handle); path=Path(handle.name)
        result=authorize(gate="evaluation",now=datetime(2027,3,1,0,0,tzinfo=UTC),authorization_path=path,protocol_path=ROOT/"research/v2/future_validation_protocol_v2.json",policy_path=ROOT/"research/v2/v2_m1_touch_sequencing_v1.json",readiness_path=ROOT/"research/v2/v2_m1_measurement_readiness.json",contract_path=ROOT/"research/v2/nas100_oanda_future_validation_request_contract.json")
        self.assertEqual(result["status"],"AUTHORIZED")


if __name__=="__main__": unittest.main()
