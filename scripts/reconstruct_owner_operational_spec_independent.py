#!/usr/bin/env python3
"""Independent standard-library reconstruction of ARJO_DERIVED_OWNER_OPERATIONAL_V1.

This file intentionally does not import any production FVG/context/replay builder.
It reconstructs the frozen owner conventions directly from their JSON contracts
and sealed OANDA OHLC artifacts, then independently evaluates the preregistered
execution variants. Its output is compared to the primary production path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CAL_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
CLASSIFICATION = "OWNER_OPERATIONAL_CONVENTION_NOT_ARJO_SEMANTIC_CLOSURE"
FVG_ID = "OWNER_OPERATIONAL_FVG_V1"
CONTEXT_ID = "OWNER_OPERATIONAL_CONTEXT_V1"
ALLOWED_FILL_EVENTS = {"SECOND_STING_TOUCH", "SECOND_STING_15M_CLOSE"}
ALLOWED_STOP_BUFFERS = {0, 1, 2}


class IndependentReconstructionError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise IndependentReconstructionError(f"invalid timestamp: {value!r}") from exc
    if dt.utcoffset() is None:
        raise IndependentReconstructionError(f"naive timestamp: {value!r}")
    return dt.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IndependentReconstructionError(f"invalid decimal {label}") from exc
    if not parsed.is_finite():
        raise IndependentReconstructionError(f"non-finite decimal {label}")
    return parsed


def verified_json_contract(path: Path, *, expected_id: str, expected_sha: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(data.get("convention_sha256", ""))
    unsigned = dict(data)
    unsigned.pop("convention_sha256", None)
    actual = canonical_sha256(unsigned)
    if data.get("convention_id") != expected_id or recorded != expected_sha or actual != expected_sha:
        raise IndependentReconstructionError(f"frozen convention mismatch: {expected_id}")
    if data.get("classification") != CLASSIFICATION:
        raise IndependentReconstructionError(f"classification mismatch: {expected_id}")
    return data


def verified_profile(path: Path) -> tuple[dict, str]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(profile.get("profile_sha256", ""))
    unsigned = dict(profile)
    unsigned.pop("profile_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual:
        raise IndependentReconstructionError("profile SHA mismatch")
    if profile.get("profile_id") != "ARJO_DERIVED_OWNER_OPERATIONAL_V1":
        raise IndependentReconstructionError("unexpected profile id")
    claim = profile.get("claim_profile", {})
    if claim.get("semantic_closure_claimed") is not False or claim.get("fully_first_party_reconstructed") is not False:
        raise IndependentReconstructionError("profile improperly claims first-party semantic closure")
    return profile, actual


def load_bars(path: Path, expected_minutes: int) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("minutes", -1)) != expected_minutes:
                raise IndependentReconstructionError(f"{path}:{line_no} granularity mismatch")
            ts = parse_utc(str(row["ts_start_utc"]))
            if ts < CAL_START or ts + timedelta(minutes=expected_minutes) > HOLDOUT_START:
                raise IndependentReconstructionError(f"{path}:{line_no} crosses calibration boundary")
            for key in ("open", "high", "low", "close"):
                dec(row[key], f"{path}:{line_no}.{key}")
            rows.append(row)
    rows.sort(key=lambda row: row["ts_start_utc"])
    return rows


def load_artifacts(profile: dict, artifact_dirs: list[Path]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    expected_ids = {2024: 9282976276, 2025: 9283007527}
    if sorted(profile["data_boundary"]["source_artifact_ids"]) != sorted(expected_ids.values()):
        raise IndependentReconstructionError("profile artifact IDs changed")
    if len(artifact_dirs) != 2:
        raise IndependentReconstructionError("exactly two annual artifact dirs required")
    rows15: list[dict] = []
    rows60: list[dict] = []
    rows240: list[dict] = []
    refs: list[dict] = []
    years: set[int] = set()
    provider = profile["provider_identity"]
    for directory in artifact_dirs:
        manifest_path = directory / "NAS100_USD.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        year = parse_utc(str(manifest["m1_first"])).year
        if year not in expected_ids or year in years:
            raise IndependentReconstructionError("unexpected or duplicate artifact year")
        years.add(year)
        for key in ("provider", "venue", "environment", "instrument", "instrument_identity", "price_component"):
            if manifest.get(key) != provider[key]:
                raise IndependentReconstructionError(f"provider mismatch: {key}")
        if str(manifest.get("provider_price_quantum")) != provider["provider_price_quantum"]:
            raise IndependentReconstructionError("provider price quantum mismatch")
        if manifest.get("provider_price_quantum_classification") != provider["provider_price_quantum_classification"]:
            raise IndependentReconstructionError("provider price quantum classification mismatch")
        if manifest.get("holdout_requested") is not False or manifest.get("holdout_accessed") is not False:
            raise IndependentReconstructionError("holdout touched in annual artifact")
        if manifest.get("mutation_endpoints_used") is not False:
            raise IndependentReconstructionError("mutation endpoint indicated in annual artifact")
        rows15.extend(load_bars(directory / "NAS100_USD.15m.jsonl", 15))
        rows60.extend(load_bars(directory / "NAS100_USD.60m.jsonl", 60))
        rows240.extend(load_bars(directory / "NAS100_USD.240m.jsonl", 240))
        refs.append({
            "year": year,
            "artifact_id": expected_ids[year],
            "manifest_sha256": file_sha256(manifest_path),
            "retrieval_sha256": manifest["retrieval_sha256"],
        })
    if years != {2024, 2025}:
        raise IndependentReconstructionError("annual artifact set incomplete")
    rows15.sort(key=lambda row: row["ts_start_utc"])
    rows60.sort(key=lambda row: row["ts_start_utc"])
    rows240.sort(key=lambda row: row["ts_start_utc"])
    return rows15, rows60, rows240, sorted(refs, key=lambda row: row["year"])


def gap_id(anchor: dict) -> str:
    return "OWNER-FVG-" + canonical_sha256(anchor)[:20].upper()


def detect_fvgs(rows240: list[dict]) -> list[dict]:
    formations: list[dict] = []
    for index in range(len(rows240) - 2):
        c1, c2, c3 = rows240[index : index + 3]
        t1, t2, t3 = (parse_utc(row["ts_start_utc"]) for row in (c1, c2, c3))
        if t2 - t1 != timedelta(hours=4) or t3 - t2 != timedelta(hours=4):
            continue
        h1, l1 = dec(c1["high"], "c1.high"), dec(c1["low"], "c1.low")
        h3, l3 = dec(c3["high"], "c3.high"), dec(c3["low"], "c3.low")
        direction: str | None = None
        zone_low: Decimal | None = None
        zone_high: Decimal | None = None
        if l3 > h1:
            direction, zone_low, zone_high = "BULLISH", h1, l3
        elif h3 < l1:
            direction, zone_low, zone_high = "BEARISH", h3, l1
        if direction is None or zone_low is None or zone_high is None:
            continue
        formation_end = t3 + timedelta(hours=4)
        anchor = {
            "direction": direction,
            "zone_low": str(zone_low),
            "zone_high": str(zone_high),
            "c1_ts_start_utc": t1.isoformat().replace("+00:00", "Z"),
            "c2_ts_start_utc": t2.isoformat().replace("+00:00", "Z"),
            "c3_ts_start_utc": t3.isoformat().replace("+00:00", "Z"),
            "formation_end_utc": formation_end.isoformat().replace("+00:00", "Z"),
        }
        anchor["gap_id"] = gap_id(anchor)
        anchor["classification"] = CLASSIFICATION
        anchor["convention_id"] = FVG_ID
        formations.append(anchor)
    formations.sort(key=lambda row: (row["formation_end_utc"], row["gap_id"]))
    return formations


def complete_sessions(rows15: list[dict]) -> list[date]:
    required = {time(9, 30), time(9, 45), time(10, 0), time(10, 15), time(10, 30), time(10, 45)}
    clocks: dict[date, set[time]] = defaultdict(set)
    for row in rows15:
        local = parse_utc(row["ts_start_utc"]).astimezone(NY)
        local_clock = local.time().replace(tzinfo=None)
        if local_clock in required:
            clocks[local.date()].add(local_clock)
    return sorted(day for day, seen in clocks.items() if seen == required and day.year in {2024, 2025})


def selection_time(day: date) -> datetime:
    return datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC)


def select_fvgs(rows15: list[dict], formations: list[dict], sessions: list[date], fvg_sha: str) -> dict:
    fill_events: dict[datetime, list[dict]] = defaultdict(list)
    for row in rows15:
        fill_events[parse_utc(row["ts_start_utc"]) + timedelta(minutes=15)].append(row)
    formation_events: dict[datetime, list[dict]] = defaultdict(list)
    for gap in formations:
        formation_events[parse_utc(gap["formation_end_utc"])].append(gap)
    session_events: dict[datetime, list[date]] = defaultdict(list)
    for day in sessions:
        session_events[selection_time(day)].append(day)
    active: dict[str, dict] = {}
    output: list[dict] = []
    for event_time in sorted(set(fill_events) | set(formation_events) | set(session_events)):
        if event_time >= HOLDOUT_START:
            raise IndependentReconstructionError("event stream reached holdout")
        for bar in fill_events.get(event_time, []):
            low, high = dec(bar["low"], "15m.low"), dec(bar["high"], "15m.high")
            remove: list[str] = []
            for gid, gap in active.items():
                if gap["direction"] == "BULLISH" and low <= dec(gap["zone_low"], "gap.zone_low"):
                    remove.append(gid)
                elif gap["direction"] == "BEARISH" and high >= dec(gap["zone_high"], "gap.zone_high"):
                    remove.append(gid)
            for gid in remove:
                active.pop(gid, None)
        for gap in formation_events.get(event_time, []):
            active[gap["gap_id"]] = gap
        for day in session_events.get(event_time, []):
            chosen = max(active.values(), key=lambda gap: (gap["formation_end_utc"], gap["gap_id"])) if active else None
            output.append({
                "session_date_ny": day.isoformat(),
                "selection_time_utc": event_time.isoformat().replace("+00:00", "Z"),
                "classification": CLASSIFICATION,
                "convention_id": FVG_ID,
                "convention_sha256": fvg_sha,
                "future_session_bars_used": False,
                "holdout_accessed": False,
                "performance_fields_used": False,
                "active_gap_count_at_selection": len(active),
                "status": "OWNER_FVG_SELECTED" if chosen else "NO_ACTIVE_OWNER_FVG",
                "selected_fvg": chosen,
            })
    output.sort(key=lambda row: row["session_date_ny"])
    return {
        "sessions": output,
        "session_anchors_sha256": canonical_sha256(output),
        "session_count": len(output),
        "selected_session_count": sum(row["selected_fvg"] is not None for row in output),
        "no_active_fvg_session_count": sum(row["selected_fvg"] is None for row in output),
    }


def confirmed_pivots(rows60: list[dict]) -> tuple[list[dict], list[dict]]:
    highs: list[dict] = []
    lows: list[dict] = []
    for index in range(1, len(rows60) - 1):
        left, center, right = rows60[index - 1 : index + 2]
        tl, tc, tr = (parse_utc(row["ts_start_utc"]) for row in (left, center, right))
        if tc - tl != timedelta(hours=1) or tr - tc != timedelta(hours=1):
            continue
        center_high, center_low = dec(center["high"], "pivot.high"), dec(center["low"], "pivot.low")
        is_high = center_high > dec(left["high"], "left.high") and center_high > dec(right["high"], "right.high")
        is_low = center_low < dec(left["low"], "left.low") and center_low < dec(right["low"], "right.low")
        if is_high and is_low:
            continue
        confirmed = tr + timedelta(hours=1)
        if is_high:
            highs.append({"kind": "HIGH", "price": str(center_high), "pivot_ts_utc": center["ts_start_utc"], "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z")})
        if is_low:
            lows.append({"kind": "LOW", "price": str(center_low), "pivot_ts_utc": center["ts_start_utc"], "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z")})
    return highs, lows


def session_window(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC)
    end = datetime.combine(day, time(11, 0), tzinfo=NY).astimezone(UTC)
    return start, end


def snapshot(row: dict) -> dict:
    return {field: row[field] for field in ("ts_start_utc", "open", "high", "low", "close")}


def qualify_occurrences(
    *, rows15: list[dict], rows60: list[dict], rows240: list[dict], data_refs: list[dict], fvg_state: dict, context_sha: str, fvg_sha: str
) -> dict:
    pivot_highs, pivot_lows = confirmed_pivots(rows60)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows15:
        by_day[parse_utc(row["ts_start_utc"]).astimezone(NY).date().isoformat()].append(row)
    ledger_rows: list[dict] = []
    occurrences: list[dict] = []
    for fvg_row in fvg_state["sessions"]:
        day_str = fvg_row["session_date_ny"]
        day = date.fromisoformat(day_str)
        woo_start, woo_end = session_window(day)
        selected_fvg = fvg_row.get("selected_fvg")
        ledger: dict = {
            "session_date_ny": day_str,
            "status": None,
            "selected_fvg_gap_id": selected_fvg.get("gap_id") if selected_fvg else None,
        }
        if selected_fvg is None:
            ledger["status"] = "NO_FVG"
            ledger_rows.append(ledger)
            continue
        eligible_highs = [item for item in pivot_highs if parse_utc(item["confirmed_at_utc"]) <= woo_start]
        eligible_lows = [item for item in pivot_lows if parse_utc(item["confirmed_at_utc"]) <= woo_start]
        if not eligible_highs or not eligible_lows:
            ledger["status"] = "NO_FVA_PIVOT"
            ledger_rows.append(ledger)
            continue
        pivot_high = max(eligible_highs, key=lambda item: (item["confirmed_at_utc"], item["pivot_ts_utc"]))
        pivot_low = max(eligible_lows, key=lambda item: (item["confirmed_at_utc"], item["pivot_ts_utc"]))
        fva_low = min(dec(pivot_high["price"], "fva.high"), dec(pivot_low["price"], "fva.low"))
        fva_high = max(dec(pivot_high["price"], "fva.high"), dec(pivot_low["price"], "fva.low"))
        fva = {
            "zone_low": str(fva_low),
            "zone_high": str(fva_high),
            "pivot_high": pivot_high,
            "pivot_low": pivot_low,
            "classification": CLASSIFICATION,
            "convention_id": CONTEXT_ID,
        }
        ledger["fva_zone_low"] = str(fva_low)
        ledger["fva_zone_high"] = str(fva_high)
        fvg_low, fvg_high = dec(selected_fvg["zone_low"], "fvg.low"), dec(selected_fvg["zone_high"], "fvg.high")
        if fva_high < fvg_low or fva_low > fvg_high:
            ledger["status"] = "NO_FVA_OVERLAP"
            ledger_rows.append(ledger)
            continue
        woo_rows = sorted([row for row in by_day[day_str] if woo_start <= parse_utc(row["ts_start_utc"]) < woo_end], key=lambda row: row["ts_start_utc"])
        if len(woo_rows) != 6:
            raise IndependentReconstructionError(f"{day_str} WoO completeness changed")
        rejection: dict | None = None
        for index in range(len(woo_rows) - 1):
            first, second = woo_rows[index : index + 2]
            if parse_utc(second["ts_start_utc"]) - parse_utc(first["ts_start_utc"]) != timedelta(minutes=15):
                continue
            first_rejects = dec(first["high"], "reject.high") >= fva_high and dec(first["close"], "reject.close") < fva_high
            second_rejects = dec(second["high"], "reject.high") >= fva_high and dec(second["close"], "reject.close") < fva_high
            if first_rejects or second_rejects:
                rejection = first if first_rejects else second
                break
        if rejection is None:
            ledger["status"] = "NO_2CR_REJECTION"
            ledger_rows.append(ledger)
            continue
        rejection_high = dec(rejection["high"], "rejection.high")
        rejection_ts = parse_utc(rejection["ts_start_utc"])
        ledger["rejection_ts_utc"] = rejection["ts_start_utc"]
        ledger["rejection_high"] = str(rejection_high)
        activation: dict | None = None
        activation_index: int | None = None
        for index, row in enumerate(woo_rows):
            if parse_utc(row["ts_start_utc"]) <= rejection_ts:
                continue
            if dec(row["close"], "activation.close") > rejection_high:
                activation, activation_index = row, index
                break
        if activation is None or activation_index is None:
            ledger["status"] = "NO_RUN"
            ledger_rows.append(ledger)
            continue
        ledger["activation_ts_utc"] = activation["ts_start_utc"]
        stings: list[tuple[int, dict]] = []
        for index, row in enumerate(woo_rows):
            if index <= activation_index:
                continue
            if dec(row["low"], "sting.low") <= fva_high and dec(row["high"], "sting.high") >= fva_low and dec(row["close"], "sting.close") > fva_low:
                stings.append((index, row))
            if len(stings) == 2:
                break
        if len(stings) != 2:
            ledger["status"] = "NO_2_STING"
            ledger_rows.append(ledger)
            continue
        _, first_sting = stings[0]
        second_index, second_sting = stings[1]
        touch_price, close_price = fva_high, dec(second_sting["close"], "second.close")
        leg_low = min(dec(row["low"], "leg.low") for row in woo_rows[activation_index : second_index + 1])
        prior_4h = [row for row in rows240 if parse_utc(row["ts_start_utc"]) + timedelta(hours=4) <= woo_start]
        if not prior_4h:
            ledger["status"] = "NO_TARGET_ABOVE_ENTRY"
            ledger_rows.append(ledger)
            continue
        target_price = max(dec(row["high"], "target.high") for row in prior_4h)
        target_source = max((row for row in prior_4h if dec(row["high"], "target.high") == target_price), key=lambda row: row["ts_start_utc"])
        if target_price <= touch_price or target_price <= close_price:
            ledger["status"] = "NO_TARGET_ABOVE_ENTRY"
            ledger_rows.append(ledger)
            continue
        if leg_low >= touch_price or leg_low >= close_price:
            ledger["status"] = "INVALID_STOP_ORDERING"
            ledger_rows.append(ledger)
            continue
        occurrence_id = f"OWNER-CAL-{day_str}"
        occurrence = {
            "schema_version": 1,
            "occurrence_id": occurrence_id,
            "session_date_ny": day_str,
            "direction": "LONG",
            "classification": CLASSIFICATION,
            "semantic_closure_claimed": False,
            "provider_identity": {
                "provider": "OANDA_V20",
                "instrument": "NAS100_USD",
                "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
                "price_component": "MID",
                "provider_price_quantum": "0.1",
                "provider_price_quantum_classification": "PROVIDER_PRICE_PRECISION_POLICY_NOT_EXCHANGE_TICK",
            },
            "calibration_data_refs": data_refs,
            "owner_fvg_convention_sha256": fvg_sha,
            "owner_context_convention_sha256": context_sha,
            "owner_fvg_session_anchors_sha256": fvg_state["session_anchors_sha256"],
            "four_h_fvg": selected_fvg,
            "one_h_fva": fva,
            "rejection": {"bar": snapshot(rejection), "rejection_high": str(rejection_high)},
            "activation": {"route": "CLOSE_ABOVE_REJECTION_HIGH", "bar": snapshot(activation)},
            "first_sting": {"bar": snapshot(first_sting)},
            "second_sting": {"bar": snapshot(second_sting), "touch_price": str(touch_price), "close_price": str(close_price)},
            "order_flow_leg_low": str(leg_low),
            "target": {"price": str(target_price), "source_4h_bar": snapshot(target_source)},
            "outcome_fields_present": False,
            "post_woo_bars_used": False,
            "holdout_accessed": False,
            "performance_comparison_performed": False,
        }
        occurrence["occurrence_sha256"] = canonical_sha256(occurrence)
        occurrences.append(occurrence)
        ledger["status"] = "QUALIFIED"
        ledger["occurrence_id"] = occurrence_id
        ledger_rows.append(ledger)
    ledger_rows.sort(key=lambda row: row["session_date_ny"])
    occurrences.sort(key=lambda row: row["session_date_ny"])
    return {
        "qualification_rows": ledger_rows,
        "occurrences": occurrences,
        "status_counts": dict(sorted(Counter(row["status"] for row in ledger_rows).items())),
        "qualification_rows_sha256": canonical_sha256(ledger_rows),
        "occurrence_set_sha256": canonical_sha256(occurrences),
    }


def replay(occurrences: list[dict], rows15: list[dict], replay_spec: dict) -> dict:
    conventions = replay_spec.get("calibration_only_conventions", {})
    if set(conventions.get("second_sting_fill_event", [])) != ALLOWED_FILL_EVENTS:
        raise IndependentReconstructionError("replay fill candidate set changed")
    if set(conventions.get("stop_buffer_ticks", [])) != ALLOWED_STOP_BUFFERS:
        raise IndependentReconstructionError("replay stop candidate set changed")
    if replay_spec.get("fixed_semantics", {}).get("direction") != "long":
        raise IndependentReconstructionError("replay direction changed")
    results: list[dict] = []
    for occurrence in occurrences:
        second_start = parse_utc(occurrence["second_sting"]["bar"]["ts_start_utc"])
        touch_ts = second_start
        close_ts = second_start + timedelta(minutes=15)
        bars_after = [row for row in rows15 if parse_utc(row["ts_start_utc"]) >= touch_ts]
        tick = float(occurrence["provider_identity"]["provider_price_quantum"])
        stop_anchor = float(occurrence["order_flow_leg_low"])
        target = float(occurrence["target"]["price"])
        for fill_event in sorted(ALLOWED_FILL_EVENTS):
            if fill_event == "SECOND_STING_TOUCH":
                entry_ts = touch_ts
                entry_price = float(occurrence["second_sting"]["touch_price"])
            else:
                entry_ts = close_ts
                entry_price = float(occurrence["second_sting"]["close_price"])
            for buffer_ticks in sorted(ALLOWED_STOP_BUFFERS):
                stop_price = stop_anchor - buffer_ticks * tick
                if entry_price <= stop_price:
                    raise IndependentReconstructionError("entry/stop ordering invalid")
                emitted: dict | None = None
                for bar in bars_after:
                    bar_ts = parse_utc(bar["ts_start_utc"])
                    if bar_ts < entry_ts:
                        continue
                    hit_stop = float(bar["low"]) <= stop_price
                    hit_target = float(bar["high"]) >= target
                    if hit_stop and hit_target:
                        status = "AMBIGUOUS_INTRABAR_ORDER"
                    elif hit_stop:
                        status = "STOP_FIRST"
                    elif hit_target:
                        status = "TARGET_FIRST"
                    else:
                        continue
                    emitted = {
                        "occurrence_id": occurrence["occurrence_id"],
                        "fill_event": fill_event,
                        "stop_buffer_ticks": buffer_ticks,
                        "status": status,
                        "entry_ts": entry_ts.isoformat(),
                        "entry_price": entry_price,
                        "stop_price": stop_price,
                        "target_price": target,
                        "event_ts": bar_ts.isoformat(),
                    }
                    break
                if emitted is None:
                    emitted = {
                        "occurrence_id": occurrence["occurrence_id"],
                        "fill_event": fill_event,
                        "stop_buffer_ticks": buffer_ticks,
                        "status": "UNRESOLVED_WINDOW_END",
                        "entry_ts": entry_ts.isoformat(),
                        "entry_price": entry_price,
                        "stop_price": stop_price,
                        "target_price": target,
                    }
                results.append(emitted)
    results.sort(key=lambda row: (row["occurrence_id"], row["fill_event"], row["stop_buffer_ticks"]))
    return {
        "results": results,
        "status_counts": dict(sorted(Counter(row["status"] for row in results).items())),
        "replay_results_sha256": canonical_sha256(results),
        "event_timestamps": sorted({row["event_ts"] for row in results if "event_ts" in row}),
    }


def build(
    *, profile_path: Path, fvg_convention_path: Path, context_convention_path: Path, replay_spec_path: Path, artifact_dirs: list[Path]
) -> dict:
    profile, profile_sha = verified_profile(profile_path)
    fvg_sha = profile["owner_conventions"]["fvg"]["canonical_sha256"]
    context_sha = profile["owner_conventions"]["context"]["canonical_sha256"]
    verified_json_contract(fvg_convention_path, expected_id=FVG_ID, expected_sha=fvg_sha)
    verified_json_contract(context_convention_path, expected_id=CONTEXT_ID, expected_sha=context_sha)
    rows15, rows60, rows240, data_refs = load_artifacts(profile, artifact_dirs)
    formations = detect_fvgs(rows240)
    sessions = complete_sessions(rows15)
    fvg_state = select_fvgs(rows15, formations, sessions, fvg_sha)
    qualified = qualify_occurrences(
        rows15=rows15,
        rows60=rows60,
        rows240=rows240,
        data_refs=data_refs,
        fvg_state=fvg_state,
        context_sha=context_sha,
        fvg_sha=fvg_sha,
    )
    replay_spec = json.loads(replay_spec_path.read_text(encoding="utf-8"))
    replay_state = replay(qualified["occurrences"], rows15, replay_spec)
    calibrated = profile["calibrated_execution"]
    report = {
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha,
        "path_id": "INDEPENDENT_STANDARD_LIBRARY_PATH",
        "reconstruction_status": "PASS",
        "semantic_closure_claimed": False,
        "owner_operational_conventions_present": True,
        "fvg_convention_sha256": fvg_sha,
        "context_convention_sha256": context_sha,
        "detected_fvg_formation_count": len(formations),
        "session_count": fvg_state["session_count"],
        "selected_fvg_session_count": fvg_state["selected_session_count"],
        "no_active_fvg_session_count": fvg_state["no_active_fvg_session_count"],
        "no_active_fvg_sessions": [row["session_date_ny"] for row in fvg_state["sessions"] if row["selected_fvg"] is None],
        "fvg_session_anchors_sha256": fvg_state["session_anchors_sha256"],
        "status_counts": qualified["status_counts"],
        "qualified_occurrence_ids": [row["occurrence_id"] for row in qualified["occurrences"]],
        "qualification_rows_sha256": qualified["qualification_rows_sha256"],
        "occurrence_set_sha256": qualified["occurrence_set_sha256"],
        "variant_result_count": len(replay_state["results"]),
        "replay_status_counts": replay_state["status_counts"],
        "replay_event_timestamps": replay_state["event_timestamps"],
        "replay_results_sha256": replay_state["replay_results_sha256"],
        "calibrated_execution": {
            "second_sting_fill_event": calibrated["second_sting_fill_event"],
            "stop_buffer_ticks": calibrated["stop_buffer_ticks"],
            "performance_status_used_for_selection": calibrated["performance_status_used_for_selection"],
        },
        "holdout_accessed": False,
    }
    report["reconstruction_sha256"] = canonical_sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--fvg-convention", required=True)
    parser.add_argument("--context-convention", required=True)
    parser.add_argument("--replay-spec", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(
            profile_path=Path(args.profile),
            fvg_convention_path=Path(args.fvg_convention),
            context_convention_path=Path(args.context_convention),
            replay_spec_path=Path(args.replay_spec),
            artifact_dirs=[Path(value) for value in args.artifact_dir],
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"independent SPEC reconstruction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"path_id": result["path_id"], "status": result["reconstruction_status"], "sha256": result["reconstruction_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
