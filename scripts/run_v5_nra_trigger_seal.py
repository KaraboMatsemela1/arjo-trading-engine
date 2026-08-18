#!/usr/bin/env python3
"""Execute the authorized V5 structure-only trigger seal.

No M1 data or economic outcome is requested by this program.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import check_v5_no_resistance_aoo_protocol as protocol_check
from v5_nra_structure import acquire_structure
from v5_nra_triggers import canonical_sha, compare_reconstructions

AUTHORIZATION = Path("research/profitability/v5_nra_trigger_seal_authorization_v1.json")
EXPECTED_PHRASE = "AUTHORIZE_V5_STRUCTURE_TRIGGER_SEAL"
EXPECTED_PROTOCOL_SHA = protocol_check.EXPECTED_PROTOCOL_SHA
EXPECTED_TRANSPORT_SHA = protocol_check.EXPECTED_TRANSPORT_SHA


def require_authorization() -> dict:
    payload = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    assert payload["authorization"] == EXPECTED_PHRASE
    assert payload["issue"] == 254
    assert payload["protocol_sha256"] == EXPECTED_PROTOCOL_SHA
    assert payload["structure_transport_sha256"] == EXPECTED_TRANSPORT_SHA
    assert payload["m1_authorized"] is False
    assert payload["economic_outcomes_authorized"] is False
    assert payload["broker_mutation_authorized"] is False
    return payload


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    protocol_check.verify()
    authorization = require_authorization()
    structure = acquire_structure()
    triggers, comparison = compare_reconstructions(structure["h4"], structure["h1"])
    distinct_knowledge = len({row["knowledge_time_utc"] for row in triggers})
    classification = (
        "TRIGGER_SAMPLE_NECESSARY_CONDITION_MET"
        if len(triggers) >= 100
        else "TRIGGER_SAMPLE_NECESSARY_CONDITION_FAILED"
    )
    trigger_sha = canonical_sha(triggers)
    readiness = {
        "schema_version": 1,
        "issue": 254,
        "candidate_id": "ARJO_V5_NQ_NO_RESISTANCE_AOO_H4_SWING_HIGH_LONG",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA,
        "structure_transport_sha256": EXPECTED_TRANSPORT_SHA,
        "authorization_sha256": canonical_sha(authorization),
        "structure_manifest_sha256": structure["manifest"]["manifest_sha256"],
        "h4_structure_sha256": structure["manifest"]["h4_sha256"],
        "h1_structure_sha256": structure["manifest"]["h1_sha256"],
        "trigger_set_sha256": trigger_sha,
        "trigger_count": len(triggers),
        "distinct_knowledge_timestamps": distinct_knowledge,
        "minimum_necessary_trigger_count": 100,
        "classification": classification,
        "independent_reconstruction_exact": comparison["exact_match"],
        "primary_trigger_sha256": comparison["primary_trigger_sha256"],
        "reference_trigger_sha256": comparison["reference_trigger_sha256"],
        "primary_stats": comparison["primary_stats"],
        "reference_stats": comparison["reference_stats"],
        "market_data": {
            "provider": "OANDA_V20_PRACTICE_READ_ONLY",
            "instrument": "NAS100_USD",
            "structure_price": "MID",
            "granularities": ["H4", "H1"],
            "strict_end_exclusive": "2024-01-01T00:00:00Z",
            "m1_requested": False,
            "bid_ask_requested": False,
        },
        "economic_outcomes_accessed": False,
        "fills_evaluated": False,
        "pnl_evaluated": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }
    readiness["readiness_sha256"] = canonical_sha(readiness)
    output_dir = Path(os.environ.get("V5_OUTPUT_DIR", "artifacts/v5_nra_trigger_seal"))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "v5_h4_mid.json", structure["h4"])
    write_json(output_dir / "v5_h1_mid.json", structure["h1"])
    write_json(output_dir / "v5_h4_request_provenance.json", structure["h4_provenance"])
    write_json(output_dir / "v5_h1_request_provenance.json", structure["h1_provenance"])
    write_json(output_dir / "v5_structure_manifest.json", structure["manifest"])
    write_json(output_dir / "v5_no_resistance_aoo_triggers.json", triggers)
    write_json(output_dir / "v5_trigger_readiness.json", readiness)
    print(json.dumps(readiness, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
