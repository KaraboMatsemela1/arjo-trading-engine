"""Validation primitives for the independent SPEC reconstruction packet."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_matrix_sha256(rows: list[dict]) -> str:
    normalized = [
        {
            "FIELD": str(row.get("FIELD", "")),
            "STATE": str(row.get("STATE", "")),
            "EVIDENCE_IDS": str(row.get("EVIDENCE_IDS", "")),
            "NOTES": str(row.get("NOTES", "")),
        }
        for row in rows
    ]
    normalized.sort(key=lambda row: row["FIELD"])
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def load_packet(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "candidate_packets": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("independent reconstruction packet must be a JSON object")
    return value


def validate_candidate_packet(bundle: dict, predicate_id: str, rows: list[dict], repo_root: Path) -> dict:
    errors: list[str] = []
    if bundle.get("schema_version") != 1:
        errors.append("packet schema_version must be 1")
    packets = [
        row for row in bundle.get("candidate_packets", [])
        if isinstance(row, dict) and str(row.get("predicate_id", "")) == predicate_id
    ]
    if len(packets) != 1:
        errors.append(f"expected exactly one packet for {predicate_id}, found {len(packets)}")
        return {"status": "FAIL", "errors": errors, "frozen_spec_ref": None}

    packet = packets[0]
    expected_matrix_sha = candidate_matrix_sha256(rows)
    if packet.get("predicate_matrix_sha256") != expected_matrix_sha:
        errors.append("packet predicate_matrix_sha256 does not match audited candidate matrix")

    frozen_spec_ref = str(packet.get("frozen_spec_ref", ""))
    frozen_spec_sha = str(packet.get("frozen_spec_sha256", ""))
    if not frozen_spec_ref:
        errors.append("packet frozen_spec_ref is required")
    if not HEX64.match(frozen_spec_sha):
        errors.append("packet frozen_spec_sha256 must be a lowercase SHA-256 digest")
    if frozen_spec_ref:
        spec_path = repo_root / frozen_spec_ref
        if not spec_path.is_file():
            errors.append(f"frozen spec does not exist: {frozen_spec_ref}")
        elif HEX64.match(frozen_spec_sha):
            actual_spec_sha = sha256_bytes(spec_path.read_bytes())
            if actual_spec_sha != frozen_spec_sha:
                errors.append("frozen spec content does not match frozen_spec_sha256")

    engineers = packet.get("engineers")
    if not isinstance(engineers, list) or len(engineers) != 2:
        errors.append("packet must contain exactly two independent engineer reconstructions")
        engineers = []
    ids = [str(row.get("id", "")) for row in engineers if isinstance(row, dict)]
    if len(ids) == 2 and (not all(ids) or len(set(ids)) != 2):
        errors.append("engineer reconstruction IDs must be non-empty and distinct")

    for index, engineer in enumerate(engineers, start=1):
        label = f"engineer {index}"
        if not isinstance(engineer, dict):
            errors.append(f"{label} must be an object")
            continue
        if engineer.get("independent") is not True:
            errors.append(f"{label} must state independent=true")
        if engineer.get("evidence_only") is not True:
            errors.append(f"{label} must state evidence_only=true")
        for flag in (
            "community_interpretations_used",
            "generic_ict_smc_knowledge_used",
            "performance_data_consulted",
            "trade_counts_consulted",
        ):
            if engineer.get(flag) is not False:
                errors.append(f"{label} must state {flag}=false")
        if engineer.get("reconstruction_sha256") != frozen_spec_sha:
            errors.append(f"{label} reconstruction_sha256 must equal frozen_spec_sha256")
        if engineer.get("predicate_matrix_sha256") != expected_matrix_sha:
            errors.append(f"{label} predicate_matrix_sha256 does not match audited matrix")

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "frozen_spec_ref": frozen_spec_ref or None,
        "predicate_matrix_sha256": expected_matrix_sha,
    }
