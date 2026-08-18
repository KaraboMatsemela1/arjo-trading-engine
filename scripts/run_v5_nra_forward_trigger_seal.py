#!/usr/bin/env python3
"""Seal V5 forward-confirmation triggers without accessing confirmation economics."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from check_v5_nra_forward_confirmation_protocol import verify as verify_confirmation
from v5_nra_confirmation_structure import acquire_structure
from v5_nra_reference_fast import compare_reconstructions_fast
from v5_nra_triggers import canonical_sha

SCORE_START = datetime(2024, 1, 1, tzinfo=UTC)
SCORE_END = datetime(2026, 8, 1, tzinfo=UTC)
CONFIRMATION_PROTOCOL_SHA = "d86258ba66ba9eba20ed72e57af0368b90512ec24bc8e8a42f82be5cce1910b4"
AUTHORIZATION = Path("research/profitability/v5_nra_forward_trigger_seal_authorization_v1.json")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_authorization() -> dict:
    value = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    expected = {
        "authorization": "AUTHORIZE_V5_FORWARD_STRUCTURE_TRIGGER_SEAL",
        "issue": 262,
        "confirmation_protocol_sha256": CONFIRMATION_PROTOCOL_SHA,
        "confirmation_m1_authorized": False,
        "economic_outcomes_authorized": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    if value != expected:
        raise RuntimeError("V5 forward trigger-seal authorization changed")
    return value


def main() -> int:
    verify_confirmation()
    authorization = require_authorization()
    structure = acquire_structure()
    all_triggers, comparison = compare_reconstructions_fast(
        structure["h4"], structure["h1"]
    )
    scored = [
        row
        for row in all_triggers
        if SCORE_START <= parse(row["knowledge_time_utc"]) < SCORE_END
    ]
    scored.sort(key=lambda row: (row["knowledge_time_utc"], row["trigger_id"]))
    scored_sha = canonical_sha(scored)
    readiness = {
        "schema_version": 1,
        "issue": 262,
        "candidate_id": "ARJO_V5_NQ_NO_RESISTANCE_AOO_H4_SWING_HIGH_LONG",
        "confirmation_protocol_sha256": CONFIRMATION_PROTOCOL_SHA,
        "score_start": "2024-01-01T00:00:00Z",
        "score_end_exclusive": "2026-08-01T00:00:00Z",
        "structure_manifest_sha256": structure["manifest"]["manifest_sha256"],
        "h4_structure_sha256": structure["manifest"]["h4_sha256"],
        "h1_structure_sha256": structure["manifest"]["h1_sha256"],
        "all_causal_trigger_count_through_confirmation_end": len(all_triggers),
        "confirmation_trigger_count": len(scored),
        "confirmation_distinct_knowledge_timestamps": len(
            {row["knowledge_time_utc"] for row in scored}
        ),
        "confirmation_trigger_set_sha256": scored_sha,
        "independent_reconstruction_exact": comparison["exact_match"],
        "primary_full_trigger_sha256": comparison["primary_trigger_sha256"],
        "reference_full_trigger_sha256": comparison["reference_trigger_sha256"],
        "authorization_sha256": canonical_sha(authorization),
        "minimum_confirmation_resolved_trade_gate": 100,
        "confirmation_m1_requested": False,
        "economic_outcomes_accessed": False,
        "fills_evaluated": False,
        "pnl_evaluated": False,
        "paper_execution": False,
        "live_execution": False,
        "broker_mutation": False,
    }
    readiness["readiness_sha256"] = canonical_sha(readiness)
    output = Path(os.environ.get("V5_CONFIRM_OUTPUT_DIR", "artifacts/v5_nra_forward_trigger_seal"))
    output.mkdir(parents=True, exist_ok=True)
    write(output / "v5_forward_h4_mid.json", structure["h4"])
    write(output / "v5_forward_h1_mid.json", structure["h1"])
    write(output / "v5_forward_h4_request_provenance.json", structure["h4_provenance"])
    write(output / "v5_forward_h1_request_provenance.json", structure["h1_provenance"])
    write(output / "v5_forward_structure_manifest.json", structure["manifest"])
    write(output / "v5_forward_confirmation_triggers.json", scored)
    write(output / "v5_forward_trigger_readiness.json", readiness)
    print(json.dumps(readiness, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
