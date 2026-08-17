#!/usr/bin/env python3
"""Validate first-party-prescribed pre-SPEC calibration packets.

Calibration is deliberately narrower than performance analysis. A packet may
only authorize outcome access after a deterministic semantic seed is frozen and
all calibration choices and holdout boundaries were preregistered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from evidence_registry_union import DEFAULT_EVIDENCE_GLOB, load_evidence_union

PROTOCOL = "FIRST_PARTY_PRESCRIBED_CALIBRATION_V1"
STAGES = {"PREREGISTERED", "CALIBRATION_COMPLETE"}
REPLAYABILITY = {"REPLAYABLE", "BLOCKED_UNRESOLVED_EXECUTION_PARAMETERS"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def parse_date(value: object, label: str, errors: list[str]) -> date | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be an ISO date")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} must be an ISO date")
        return None


def validate_packet(packet: dict, evidence: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    packet_id = str(packet.get("packet_id", "<unknown>"))
    prefix = f"{packet_id}: "

    if packet.get("schema_version") != 1:
        errors.append(prefix + "schema_version must be 1")
    if packet.get("protocol") != PROTOCOL:
        errors.append(prefix + f"protocol must be {PROTOCOL}")
    if packet.get("stage") not in STAGES:
        errors.append(prefix + f"stage must be one of {sorted(STAGES)}")
    if not str(packet.get("predicate_id", "")):
        errors.append(prefix + "predicate_id is required")
    if packet.get("semantic_candidate_locked") is not True:
        errors.append(prefix + "semantic_candidate_locked must be true")

    seed = packet.get("seed_plan")
    if not isinstance(seed, dict):
        errors.append(prefix + "seed_plan must be an object")
        seed = {}
    replayability = seed.get("replayability_status")
    if replayability not in REPLAYABILITY:
        errors.append(prefix + f"seed_plan.replayability_status must be one of {sorted(REPLAYABILITY)}")
    if not str(seed.get("instrument", "")):
        errors.append(prefix + "seed_plan.instrument is required")
    timeframes = seed.get("timeframes")
    if not isinstance(timeframes, list) or not timeframes or not all(isinstance(value, str) and value for value in timeframes):
        errors.append(prefix + "seed_plan.timeframes must be a non-empty string list")
    if not str(seed.get("rule_summary", "")).strip():
        errors.append(prefix + "seed_plan.rule_summary is required")

    seed_refs = seed.get("evidence_ids")
    if not isinstance(seed_refs, list) or not seed_refs:
        errors.append(prefix + "seed_plan.evidence_ids must be non-empty")
        seed_refs = []
    for evidence_id in seed_refs:
        row = evidence.get(str(evidence_id))
        if row is None:
            errors.append(prefix + f"seed plan references unknown evidence {evidence_id}")
        elif row.get("CONFIDENCE") == "INSUFFICIENT":
            errors.append(prefix + f"seed plan evidence {evidence_id} is INSUFFICIENT")

    parameters = packet.get("calibratable_parameters")
    if not isinstance(parameters, list):
        errors.append(prefix + "calibratable_parameters must be a list")
        parameters = []
    names: set[str] = set()
    for index, parameter in enumerate(parameters, start=1):
        label = prefix + f"parameter {index}: "
        if not isinstance(parameter, dict):
            errors.append(label + "must be an object")
            continue
        name = str(parameter.get("name", ""))
        if not name:
            errors.append(label + "name is required")
        elif name in names:
            errors.append(label + f"duplicate parameter name {name}")
        names.add(name)
        if not str(parameter.get("semantic_role", "")).strip():
            errors.append(label + "semantic_role is required")
        refs = parameter.get("basis_evidence_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(label + "basis_evidence_ids must be non-empty")
            refs = []
        for evidence_id in refs:
            if str(evidence_id) not in evidence:
                errors.append(label + f"unknown evidence {evidence_id}")
        candidates = parameter.get("predeclared_candidates")
        bounds = parameter.get("predeclared_bounds")
        if not candidates and not bounds:
            errors.append(label + "requires predeclared_candidates or predeclared_bounds")
        if candidates is not None and (not isinstance(candidates, list) or not candidates):
            errors.append(label + "predeclared_candidates must be a non-empty list when supplied")
        if bounds is not None:
            if not isinstance(bounds, dict) or set(bounds) != {"min", "max"}:
                errors.append(label + "predeclared_bounds must contain exactly min and max")
            elif not all(isinstance(bounds[key], (int, float)) for key in ("min", "max")):
                errors.append(label + "predeclared_bounds min/max must be numeric")
            elif bounds["min"] >= bounds["max"]:
                errors.append(label + "predeclared_bounds min must be less than max")

    anti_bias = packet.get("anti_bias")
    if not isinstance(anti_bias, dict):
        errors.append(prefix + "anti_bias must be an object")
        anti_bias = {}
    for flag in (
        "candidate_discovery_allowed",
        "new_concepts_after_outcome_access_allowed",
        "semantic_candidate_selection_by_performance_allowed",
        "holdout_use_during_calibration_allowed",
        "performance_leaderboard_allowed",
    ):
        if anti_bias.get(flag) is not False:
            errors.append(prefix + f"anti_bias.{flag} must be false")

    objective = packet.get("objective")
    if not isinstance(objective, dict):
        errors.append(prefix + "objective must be an object")
        objective = {}
    if objective.get("kind") != "FIRST_PARTY_PARAMETER_REFINEMENT":
        errors.append(prefix + "objective.kind must be FIRST_PARTY_PARAMETER_REFINEMENT")
    if not str(objective.get("predeclared_measure", "")).strip():
        errors.append(prefix + "objective.predeclared_measure is required")
    if not str(objective.get("acceptance_rule", "")).strip():
        errors.append(prefix + "objective.acceptance_rule is required")

    dataset = packet.get("dataset")
    if not isinstance(dataset, dict):
        errors.append(prefix + "dataset must be an object")
        dataset = {}
    windows_declared = dataset.get("windows_declared") is True
    calibration_data_accessed = dataset.get("calibration_data_accessed")
    holdout_accessed = dataset.get("holdout_accessed")
    if calibration_data_accessed not in {True, False}:
        errors.append(prefix + "dataset.calibration_data_accessed must be boolean")
    if holdout_accessed is not False:
        errors.append(prefix + "dataset.holdout_accessed must remain false before SPEC_READY")

    if windows_declared:
        cal_start = parse_date(dataset.get("calibration_start"), prefix + "dataset.calibration_start", errors)
        cal_end = parse_date(dataset.get("calibration_end"), prefix + "dataset.calibration_end", errors)
        hold_start = parse_date(dataset.get("holdout_start"), prefix + "dataset.holdout_start", errors)
        hold_end = parse_date(dataset.get("holdout_end"), prefix + "dataset.holdout_end", errors)
        if cal_start and cal_end and cal_start > cal_end:
            errors.append(prefix + "calibration_start must not be after calibration_end")
        if hold_start and hold_end and hold_start > hold_end:
            errors.append(prefix + "holdout_start must not be after holdout_end")
        if cal_end and hold_start and cal_end >= hold_start:
            errors.append(prefix + "calibration and holdout windows must not overlap")
    elif packet.get("outcome_access_authorized") is True:
        errors.append(prefix + "outcome access requires frozen calibration and holdout windows")

    outcome_authorized = packet.get("outcome_access_authorized")
    if outcome_authorized not in {True, False}:
        errors.append(prefix + "outcome_access_authorized must be boolean")
    if outcome_authorized is True:
        if replayability != "REPLAYABLE":
            errors.append(prefix + "outcome access requires a REPLAYABLE seed plan")
        if not parameters:
            errors.append(prefix + "outcome access requires at least one preregistered calibration parameter")
        if calibration_data_accessed is not False:
            errors.append(prefix + "authorization packet must be frozen before calibration data is accessed")
        frozen_sha = str(packet.get("preregistration_sha256", ""))
        if not HEX64.match(frozen_sha):
            errors.append(prefix + "outcome access requires preregistration_sha256")

    if packet.get("stage") == "CALIBRATION_COMPLETE":
        if outcome_authorized is not True:
            errors.append(prefix + "CALIBRATION_COMPLETE requires prior outcome access authorization")
        if calibration_data_accessed is not True:
            errors.append(prefix + "CALIBRATION_COMPLETE requires calibration_data_accessed=true")
        result_ref = str(packet.get("calibration_result_ref", ""))
        result_sha = str(packet.get("calibration_result_sha256", ""))
        if not result_ref or not HEX64.match(result_sha):
            errors.append(prefix + "CALIBRATION_COMPLETE requires SHA-bound calibration result")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_GLOB)
    args = parser.parse_args()

    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    evidence = {str(row["EVIDENCE_ID"]): row for row in load_evidence_union(args.evidence)}
    errors = validate_packet(packet, evidence)
    if errors:
        print("Calibration protocol validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(json.dumps({"packet_id": packet["packet_id"], "stage": packet["stage"], "outcome_access_authorized": packet["outcome_access_authorized"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
