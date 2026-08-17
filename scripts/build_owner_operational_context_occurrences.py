#!/usr/bin/env python3
"""Materialize calibration occurrences under frozen owner operational conventions.

No replay outcome bars are read beyond the frozen 11:00 America/New_York WoO.
Exact FVA/2CR/2-Sting/Order-Flow/target predicates are owner operational
conventions, not claimed as recovered Arjo-exact semantics.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from build_owner_operational_fvg_anchors import (
    EXPECTED_CLASSIFICATION,
    FvgError,
    build as build_fvg_anchors,
    canonical_sha256,
    decimal,
    file_sha256,
    load_jsonl,
    parse_utc,
)

NY = ZoneInfo("America/New_York")
CAL_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
EXPECTED_CONTEXT_ID = "OWNER_OPERATIONAL_CONTEXT_V1"
EXPECTED_CONTEXT_SHA = "dba7892337e391ba6673de5b9df932a271c3af28103e10cecaa0163a9995bc5e"
EXPECTED_FVG_SHA = "cf12a1ce30d35dced52ef4f3c9bbb3ed11ab6509d6ada33e2f04089c68fafe7e"
EXPECTED_FVG_ANCHOR_SHA = "5277a36e777cdac36aa4f27b42435257c6ecd46a1a7c8bf852f1bc9e4f908166"
EXPECTED_ARTIFACTS = {2024: 9282976276, 2025: 9283007527}
EXPECTED_PRICE_QUANTUM = Decimal("0.1")


class ContextError(RuntimeError):
    pass


def load_context_convention(path: Path) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(data.get("convention_sha256", ""))
    unsigned = dict(data)
    unsigned.pop("convention_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual or actual != EXPECTED_CONTEXT_SHA:
        raise ContextError("owner context convention SHA mismatch")
    if data.get("convention_id") != EXPECTED_CONTEXT_ID:
        raise ContextError("unexpected owner context convention id")
    if data.get("classification") != EXPECTED_CLASSIFICATION:
        raise ContextError("unexpected owner context classification")
    if data.get("authority") != "OWNER_DIRECTED_OPERATIONAL_CONVENTION":
        raise ContextError("unexpected owner context authority")
    depends = data.get("depends_on", {})
    if depends.get("fvg_convention_sha256") != EXPECTED_FVG_SHA:
        raise ContextError("owner context convention references unexpected FVG SHA")
    anti = data.get("anti_bias", {})
    required_false = {
        "future_session_bars_allowed",
        "holdout_allowed",
        "performance_based_selection_allowed",
        "post_woo_outcomes_allowed",
        "rule_adjustment_after_diagnostic_counts_allowed",
        "semantic_candidate_ranking_allowed",
    }
    if any(anti.get(key) is not False for key in required_false):
        raise ContextError("owner context anti-bias boundary changed")
    return data, actual


def load_annual_bars(artifact_dirs: list[Path]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    if len(artifact_dirs) != 2:
        raise ContextError("exactly two frozen annual artifact directories are required")
    rows15: list[dict] = []
    rows60: list[dict] = []
    rows240: list[dict] = []
    refs: list[dict] = []
    seen_years: set[int] = set()
    for directory in artifact_dirs:
        manifest_path = directory / "NAS100_USD.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        year = parse_utc(str(manifest["m1_first"])).year
        if year not in EXPECTED_ARTIFACTS or year in seen_years:
            raise ContextError("unexpected or duplicate annual artifact")
        seen_years.add(year)
        if manifest.get("holdout_accessed") is not False or manifest.get("holdout_requested") is not False:
            raise ContextError("annual manifest indicates holdout access/request")
        if manifest.get("mutation_endpoints_used") is not False:
            raise ContextError("annual manifest indicates mutation endpoint use")
        if decimal(manifest.get("provider_price_quantum"), "provider_price_quantum") != EXPECTED_PRICE_QUANTUM:
            raise ContextError("provider price quantum changed")
        if manifest.get("provider_price_quantum_classification") != "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK":
            raise ContextError("provider price quantum classification changed")
        rows15.extend(load_jsonl(directory / "NAS100_USD.15m.jsonl", 15))
        rows60.extend(load_jsonl(directory / "NAS100_USD.60m.jsonl", 60))
        rows240.extend(load_jsonl(directory / "NAS100_USD.240m.jsonl", 240))
        refs.append({
            "year": year,
            "artifact_id": EXPECTED_ARTIFACTS[year],
            "manifest_sha256": file_sha256(manifest_path),
            "retrieval_sha256": manifest["retrieval_sha256"],
        })
    if seen_years != set(EXPECTED_ARTIFACTS):
        raise ContextError("frozen annual artifact set incomplete")
    rows15.sort(key=lambda row: row["ts_start_utc"])
    rows60.sort(key=lambda row: row["ts_start_utc"])
    rows240.sort(key=lambda row: row["ts_start_utc"])
    return rows15, rows60, rows240, sorted(refs, key=lambda item: item["year"])


def confirmed_pivots(rows60: list[dict]) -> tuple[list[dict], list[dict]]:
    highs: list[dict] = []
    lows: list[dict] = []
    for index in range(1, len(rows60) - 1):
        left, center, right = rows60[index - 1 : index + 2]
        tl = parse_utc(left["ts_start_utc"])
        tc = parse_utc(center["ts_start_utc"])
        tr = parse_utc(right["ts_start_utc"])
        if tc - tl != timedelta(hours=1) or tr - tc != timedelta(hours=1):
            continue
        center_high = decimal(center["high"], "pivot.high")
        center_low = decimal(center["low"], "pivot.low")
        is_high = center_high > decimal(left["high"], "left.high") and center_high > decimal(right["high"], "right.high")
        is_low = center_low < decimal(left["low"], "left.low") and center_low < decimal(right["low"], "right.low")
        if is_high and is_low:
            continue
        confirmed = tr + timedelta(hours=1)
        if is_high:
            highs.append({
                "kind": "HIGH",
                "price": str(center_high),
                "pivot_ts_utc": center["ts_start_utc"],
                "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z"),
            })
        if is_low:
            lows.append({
                "kind": "LOW",
                "price": str(center_low),
                "pivot_ts_utc": center["ts_start_utc"],
                "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z"),
            })
    return highs, lows


def session_times(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC)
    end = datetime.combine(day, time(11, 0), tzinfo=NY).astimezone(UTC)
    return start, end


def bar_snapshot(row: dict) -> dict:
    return {field: row[field] for field in ("ts_start_utc", "open", "high", "low", "close")}


def build(*, context_convention_path: Path, fvg_convention_path: Path, artifact_dirs: list[Path]) -> dict:
    _, context_sha = load_context_convention(context_convention_path)
    rows15, rows60, rows240, data_refs = load_annual_bars(artifact_dirs)
    try:
        fvg_state = build_fvg_anchors(fvg_convention_path, artifact_dirs)
    except FvgError as exc:
        raise ContextError(f"owner FVG dependency failed: {exc}") from exc
    if fvg_state.get("convention_sha256") != EXPECTED_FVG_SHA:
        raise ContextError("owner FVG convention SHA changed")
    if fvg_state.get("session_anchors_sha256") != EXPECTED_FVG_ANCHOR_SHA:
        raise ContextError("owner FVG anchor universe changed")
    if int(fvg_state.get("session_count", -1)) != 515:
        raise ContextError("owner FVG session universe changed")

    pivot_highs, pivot_lows = confirmed_pivots(rows60)
    rows15_by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows15:
        day = parse_utc(row["ts_start_utc"]).astimezone(NY).date().isoformat()
        rows15_by_day[day].append(row)

    qualification_rows: list[dict] = []
    occurrences: list[dict] = []

    for fvg_row in fvg_state["sessions"]:
        day_str = str(fvg_row["session_date_ny"])
        day = date.fromisoformat(day_str)
        woo_start, woo_end = session_times(day)
        if not CAL_START <= woo_start < HOLDOUT_START or woo_end > HOLDOUT_START:
            raise ContextError("session outside calibration boundary")
        selected_fvg = fvg_row.get("selected_fvg")
        ledger: dict = {
            "session_date_ny": day_str,
            "status": None,
            "selected_fvg_gap_id": selected_fvg.get("gap_id") if selected_fvg else None,
        }
        if selected_fvg is None:
            ledger["status"] = "NO_FVG"
            qualification_rows.append(ledger)
            continue

        eligible_highs = [item for item in pivot_highs if parse_utc(item["confirmed_at_utc"]) <= woo_start]
        eligible_lows = [item for item in pivot_lows if parse_utc(item["confirmed_at_utc"]) <= woo_start]
        if not eligible_highs or not eligible_lows:
            ledger["status"] = "NO_FVA_PIVOT"
            qualification_rows.append(ledger)
            continue
        pivot_high = max(eligible_highs, key=lambda item: (item["confirmed_at_utc"], item["pivot_ts_utc"]))
        pivot_low = max(eligible_lows, key=lambda item: (item["confirmed_at_utc"], item["pivot_ts_utc"]))
        fva_low = min(decimal(pivot_high["price"], "fva.pivot_high"), decimal(pivot_low["price"], "fva.pivot_low"))
        fva_high = max(decimal(pivot_high["price"], "fva.pivot_high"), decimal(pivot_low["price"], "fva.pivot_low"))
        fva = {
            "zone_low": str(fva_low),
            "zone_high": str(fva_high),
            "pivot_high": pivot_high,
            "pivot_low": pivot_low,
            "classification": EXPECTED_CLASSIFICATION,
            "convention_id": EXPECTED_CONTEXT_ID,
        }
        ledger["fva_zone_low"] = str(fva_low)
        ledger["fva_zone_high"] = str(fva_high)
        fvg_low = decimal(selected_fvg["zone_low"], "fvg.zone_low")
        fvg_high = decimal(selected_fvg["zone_high"], "fvg.zone_high")
        if fva_high < fvg_low or fva_low > fvg_high:
            ledger["status"] = "NO_FVA_OVERLAP"
            qualification_rows.append(ledger)
            continue

        woo_rows = sorted(
            [row for row in rows15_by_day[day_str] if woo_start <= parse_utc(row["ts_start_utc"]) < woo_end],
            key=lambda row: row["ts_start_utc"],
        )
        if len(woo_rows) != 6:
            raise ContextError(f"{day_str} lost frozen six-bar WoO completeness")

        rejection: dict | None = None
        for index in range(len(woo_rows) - 1):
            first, second = woo_rows[index : index + 2]
            if parse_utc(second["ts_start_utc"]) - parse_utc(first["ts_start_utc"]) != timedelta(minutes=15):
                continue
            first_rejects = decimal(first["high"], "2cr.first.high") >= fva_high and decimal(first["close"], "2cr.first.close") < fva_high
            second_rejects = decimal(second["high"], "2cr.second.high") >= fva_high and decimal(second["close"], "2cr.second.close") < fva_high
            if first_rejects or second_rejects:
                rejection = first if first_rejects else second
                break
        if rejection is None:
            ledger["status"] = "NO_2CR_REJECTION"
            qualification_rows.append(ledger)
            continue
        rejection_high = decimal(rejection["high"], "rejection.high")
        rejection_ts = parse_utc(rejection["ts_start_utc"])
        ledger["rejection_ts_utc"] = rejection["ts_start_utc"]
        ledger["rejection_high"] = str(rejection_high)

        activation: dict | None = None
        activation_index: int | None = None
        for index, row in enumerate(woo_rows):
            if parse_utc(row["ts_start_utc"]) <= rejection_ts:
                continue
            if decimal(row["close"], "activation.close") > rejection_high:
                activation = row
                activation_index = index
                break
        if activation is None or activation_index is None:
            ledger["status"] = "NO_RUN"
            qualification_rows.append(ledger)
            continue
        ledger["activation_ts_utc"] = activation["ts_start_utc"]

        stings: list[tuple[int, dict]] = []
        for index, row in enumerate(woo_rows):
            if index <= activation_index:
                continue
            if decimal(row["low"], "sting.low") <= fva_high and decimal(row["high"], "sting.high") >= fva_low and decimal(row["close"], "sting.close") > fva_low:
                stings.append((index, row))
            if len(stings) == 2:
                break
        if len(stings) != 2:
            ledger["status"] = "NO_2_STING"
            qualification_rows.append(ledger)
            continue
        _, first_sting = stings[0]
        second_sting_index, second_sting = stings[1]
        touch_price = fva_high
        close_price = decimal(second_sting["close"], "second_sting.close")
        leg_rows = woo_rows[activation_index : second_sting_index + 1]
        order_flow_leg_low = min(decimal(row["low"], "order_flow_leg.low") for row in leg_rows)

        prior_4h = [row for row in rows240 if parse_utc(row["ts_start_utc"]) + timedelta(hours=4) <= woo_start]
        if not prior_4h:
            ledger["status"] = "NO_TARGET_ABOVE_ENTRY"
            qualification_rows.append(ledger)
            continue
        target_price = max(decimal(row["high"], "target.high") for row in prior_4h)
        target_source = max(
            (row for row in prior_4h if decimal(row["high"], "target.high") == target_price),
            key=lambda row: row["ts_start_utc"],
        )
        if target_price <= touch_price or target_price <= close_price:
            ledger["status"] = "NO_TARGET_ABOVE_ENTRY"
            qualification_rows.append(ledger)
            continue
        if order_flow_leg_low >= touch_price or order_flow_leg_low >= close_price:
            ledger["status"] = "INVALID_STOP_ORDERING"
            qualification_rows.append(ledger)
            continue

        occurrence_id = f"OWNER-CAL-{day_str}"
        occurrence = {
            "schema_version": 1,
            "occurrence_id": occurrence_id,
            "session_date_ny": day_str,
            "direction": "LONG",
            "classification": EXPECTED_CLASSIFICATION,
            "semantic_closure_claimed": False,
            "provider_identity": {
                "provider": "OANDA_V20",
                "instrument": "NAS100_USD",
                "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
                "price_component": "MID",
                "provider_price_quantum": str(EXPECTED_PRICE_QUANTUM),
                "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
            },
            "calibration_data_refs": data_refs,
            "owner_fvg_convention_sha256": EXPECTED_FVG_SHA,
            "owner_context_convention_sha256": context_sha,
            "owner_fvg_session_anchors_sha256": EXPECTED_FVG_ANCHOR_SHA,
            "four_h_fvg": selected_fvg,
            "one_h_fva": fva,
            "rejection": {"bar": bar_snapshot(rejection), "rejection_high": str(rejection_high)},
            "activation": {"route": "CLOSE_ABOVE_REJECTION_HIGH", "bar": bar_snapshot(activation)},
            "first_sting": {"bar": bar_snapshot(first_sting)},
            "second_sting": {
                "bar": bar_snapshot(second_sting),
                "touch_price": str(touch_price),
                "close_price": str(close_price),
            },
            "order_flow_leg_low": str(order_flow_leg_low),
            "target": {"price": str(target_price), "source_4h_bar": bar_snapshot(target_source)},
            "outcome_fields_present": False,
            "post_woo_bars_used": False,
            "holdout_accessed": False,
            "performance_comparison_performed": False,
        }
        occurrence["occurrence_sha256"] = canonical_sha256(occurrence)
        occurrences.append(occurrence)
        ledger["status"] = "QUALIFIED"
        ledger["occurrence_id"] = occurrence_id
        qualification_rows.append(ledger)

    qualification_rows.sort(key=lambda row: row["session_date_ny"])
    occurrences.sort(key=lambda row: row["session_date_ny"])
    status_counts = Counter(row["status"] for row in qualification_rows)
    result = {
        "schema_version": 1,
        "status": "CALIBRATION_OCCURRENCES_READY",
        "source": "OWNER_OPERATIONAL_CONVENTIONS_FROZEN_PRE_OUTCOME",
        "classification": EXPECTED_CLASSIFICATION,
        "semantic_closure_claimed": False,
        "context_convention_sha256": context_sha,
        "fvg_convention_sha256": EXPECTED_FVG_SHA,
        "fvg_session_anchors_sha256": EXPECTED_FVG_ANCHOR_SHA,
        "session_count": len(qualification_rows),
        "qualified_occurrence_count": len(occurrences),
        "status_counts": dict(sorted(status_counts.items())),
        "qualification_rows_sha256": canonical_sha256(qualification_rows),
        "occurrence_set_sha256": canonical_sha256(occurrences),
        "outcome_fields_present": False,
        "post_woo_bars_used": False,
        "holdout_accessed": False,
        "performance_comparison_performed": False,
        "calibration_data_refs": data_refs,
        "qualification_rows": qualification_rows,
        "occurrences": occurrences,
    }
    if result["session_count"] != 515:
        raise ContextError("frozen 515-session universe changed")
    if result["qualified_occurrence_count"] < 1:
        raise ContextError("owner operational convention produced no calibration occurrence")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            context_convention_path=Path(args.context_convention),
            fvg_convention_path=Path(args.fvg_convention),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError, ContextError, FvgError) as exc:
        print(f"owner operational context build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": result["status"],
        "session_count": result["session_count"],
        "qualified_occurrence_count": result["qualified_occurrence_count"],
        "status_counts": result["status_counts"],
        "qualification_rows_sha256": result["qualification_rows_sha256"],
        "occurrence_set_sha256": result["occurrence_set_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
