#!/usr/bin/env python3
"""Primary protected-holdout evaluator for the frozen owner-operational profile.

Uses production FVG/pivot primitives where they are boundary-neutral, while
orchestrating the frozen 2026-only session evaluation with 2024-2025 carry-in
context. It never evaluates alternate calibration variants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from build_owner_operational_fvg_anchors import canonical_sha256, detect_formations
from build_owner_operational_context_occurrences import confirmed_pivots

NY = ZoneInfo("America/New_York")
HSTART = datetime(2026, 1, 1, tzinfo=UTC)
HEND = datetime(2026, 7, 1, tzinfo=UTC)
PROTOCOL_SHA = "258f4f27736f66d2a83e020e7c04e89f0d78de0372c3320e95011b2617883347"
PROFILE_SHA = "7f768d392175275df9aceb854802234c0abc9918ac0d016853c691f6b45a9585"
FVG_SHA = "cf12a1ce30d35dced52ef4f3c9bbb3ed11ab6509d6ada33e2f04089c68fafe7e"
CONTEXT_SHA = "dba7892337e391ba6673de5b9df932a271c3af28103e10cecaa0163a9995bc5e"
HOLDOUT_MANIFEST_SHA = "0268ffde29b961b1f86cc43894c92c6097660ae3b39745740d3386de25b5149e"
CAL_MANIFEST_SHA = {2024: "6a4c8b41fae77a6bbd0bb1a809cabae63944a00339f30912ca57685aeff65dd7", 2025: "4f038884fe18f1cdaa9d05a4eabb1aa820491f118f0d34f94b32d77e35fc5f02"}
CLASSIFICATION = "OWNER_OPERATIONAL_CONVENTION_NOT_ARJO_SEMANTIC_CLOSURE"


class ValidationError(RuntimeError):
    pass


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid timestamp {value!r}") from exc
    if dt.utcoffset() is None:
        raise ValidationError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"invalid decimal {label}") from exc
    if not result.is_finite():
        raise ValidationError(f"non-finite decimal {label}")
    return result


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path, minutes: int) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("minutes", -1)) != minutes:
                raise ValidationError(f"{path}:{line_no} granularity mismatch")
            parse_utc(str(row["ts_start_utc"]))
            for key in ("open", "high", "low", "close"):
                dec(row[key], f"{path}:{line_no}.{key}")
            rows.append(row)
    rows.sort(key=lambda row: row["ts_start_utc"])
    return rows


def verify_inputs(protocol_path: Path, profile_path: Path, readiness_path: Path, cal_dirs: list[Path], holdout_dir: Path) -> None:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_sha256") != PROTOCOL_SHA or protocol.get("status") != "FROZEN_BEFORE_HOLDOUT_ACCESS":
        raise ValidationError("protected validation protocol changed")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("profile_sha256") != PROFILE_SHA or profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise ValidationError("frozen SPEC profile changed")
    if profile.get("owner_conventions", {}).get("fvg", {}).get("canonical_sha256") != FVG_SHA:
        raise ValidationError("frozen FVG convention changed")
    if profile.get("owner_conventions", {}).get("context", {}).get("canonical_sha256") != CONTEXT_SHA:
        raise ValidationError("frozen context convention changed")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if readiness.get("status") != "PROTECTED_HOLDOUT_DATA_READY" or readiness.get("validation_protocol_sha256") != PROTOCOL_SHA:
        raise ValidationError("holdout readiness binding changed")
    if readiness.get("holdout_accessed") is not True or readiness.get("calibration_window_accessed_by_holdout_job") is not False:
        raise ValidationError("holdout readiness access boundary changed")
    if readiness.get("manifest_byte_sha256") != HOLDOUT_MANIFEST_SHA:
        raise ValidationError("holdout readiness manifest SHA changed")
    if len(cal_dirs) != 2:
        raise ValidationError("exactly two calibration context directories required")
    seen: set[int] = set()
    for directory in cal_dirs:
        manifest = json.loads((directory / "NAS100_USD.manifest.json").read_text(encoding="utf-8"))
        year = parse_utc(manifest["m1_first"]).year
        if year not in CAL_MANIFEST_SHA or year in seen:
            raise ValidationError("unexpected calibration context artifact")
        seen.add(year)
        if file_sha256(directory / "NAS100_USD.manifest.json") != CAL_MANIFEST_SHA[year]:
            raise ValidationError(f"calibration manifest SHA changed for {year}")
        if manifest.get("holdout_accessed") is not False:
            raise ValidationError("calibration artifact indicates holdout access")
    if seen != {2024, 2025}:
        raise ValidationError("calibration context artifacts incomplete")
    hmanifest = json.loads((holdout_dir / "NAS100_USD.manifest.json").read_text(encoding="utf-8"))
    if file_sha256(holdout_dir / "NAS100_USD.manifest.json") != HOLDOUT_MANIFEST_SHA:
        raise ValidationError("holdout manifest byte SHA mismatch")
    if hmanifest.get("requested_start") != "2026-01-01T00:00:00Z" or hmanifest.get("requested_end_exclusive") != "2026-07-01T00:00:00Z":
        raise ValidationError("holdout interval changed")
    if hmanifest.get("holdout_accessed") is not True or hmanifest.get("calibration_window_accessed") is not False:
        raise ValidationError("holdout manifest access boundary changed")
    if hmanifest.get("mutation_endpoints_used") is not False:
        raise ValidationError("holdout manifest indicates mutation endpoint use")


def combined_rows(cal_dirs: list[Path], holdout_dir: Path, minutes: int) -> list[dict]:
    rows: list[dict] = []
    for directory in [*cal_dirs, holdout_dir]:
        rows.extend(load_jsonl(directory / f"NAS100_USD.{minutes}m.jsonl", minutes))
    rows.sort(key=lambda row: row["ts_start_utc"])
    return rows


def complete_holdout_sessions(rows15: list[dict]) -> list[date]:
    required = {time(9, 30), time(9, 45), time(10, 0), time(10, 15), time(10, 30), time(10, 45)}
    by_day: dict[date, set[time]] = defaultdict(set)
    for row in rows15:
        dt = parse_utc(row["ts_start_utc"])
        if not HSTART <= dt < HEND:
            continue
        local = dt.astimezone(NY)
        clock = local.time().replace(tzinfo=None)
        if clock in required:
            by_day[local.date()].add(clock)
    return sorted(day for day, clocks in by_day.items() if clocks == required)


def selection_time(day: date) -> datetime:
    return datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC)


def select_fvgs(rows15: list[dict], formations: list[dict], sessions: list[date]) -> dict:
    fill_events: dict[datetime, list[dict]] = defaultdict(list)
    for row in rows15:
        end = parse_utc(row["ts_start_utc"]) + timedelta(minutes=15)
        if end <= HEND:
            fill_events[end].append(row)
    formation_events: dict[datetime, list[dict]] = defaultdict(list)
    for gap in formations:
        formation_events[parse_utc(gap["formation_end_utc"])].append(gap)
    session_events: dict[datetime, list[date]] = defaultdict(list)
    for day in sessions:
        session_events[selection_time(day)].append(day)
    active: dict[str, dict] = {}
    output: list[dict] = []
    for event_time in sorted(set(fill_events) | set(formation_events) | set(session_events)):
        if event_time > HEND:
            continue
        for bar in fill_events.get(event_time, []):
            low, high = dec(bar["low"], "fill.low"), dec(bar["high"], "fill.high")
            remove: list[str] = []
            for gid, gap in active.items():
                if gap["direction"] == "BULLISH" and low <= dec(gap["zone_low"], "gap.low"):
                    remove.append(gid)
                elif gap["direction"] == "BEARISH" and high >= dec(gap["zone_high"], "gap.high"):
                    remove.append(gid)
            for gid in remove:
                active.pop(gid, None)
        for gap in formation_events.get(event_time, []):
            active[gap["gap_id"]] = gap
        for day in session_events.get(event_time, []):
            chosen = max(active.values(), key=lambda gap: (gap["formation_end_utc"], gap["gap_id"])) if active else None
            output.append({"session_date_ny": day.isoformat(), "selected_fvg": chosen})
    output.sort(key=lambda row: row["session_date_ny"])
    return {"sessions": output, "selected_count": sum(row["selected_fvg"] is not None for row in output)}


def qualify(rows15: list[dict], rows60: list[dict], rows240: list[dict], fvg_state: dict) -> tuple[list[dict], list[dict], dict]:
    pivot_highs, pivot_lows = confirmed_pivots(rows60)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows15:
        by_day[parse_utc(row["ts_start_utc"]).astimezone(NY).date().isoformat()].append(row)
    ledger: list[dict] = []
    occurrences: list[dict] = []
    for item in fvg_state["sessions"]:
        day_str = item["session_date_ny"]
        day = date.fromisoformat(day_str)
        woo_start = selection_time(day)
        woo_end = datetime.combine(day, time(11, 0), tzinfo=NY).astimezone(UTC)
        gap = item["selected_fvg"]
        row: dict = {"session_date_ny": day_str, "status": None, "selected_fvg_gap_id": gap.get("gap_id") if gap else None}
        if gap is None:
            row["status"] = "NO_FVG"; ledger.append(row); continue
        highs = [x for x in pivot_highs if parse_utc(x["confirmed_at_utc"]) <= woo_start]
        lows = [x for x in pivot_lows if parse_utc(x["confirmed_at_utc"]) <= woo_start]
        if not highs or not lows:
            row["status"] = "NO_FVA_PIVOT"; ledger.append(row); continue
        ph = max(highs, key=lambda x: (x["confirmed_at_utc"], x["pivot_ts_utc"]))
        pl = max(lows, key=lambda x: (x["confirmed_at_utc"], x["pivot_ts_utc"]))
        fva_low = min(dec(ph["price"], "fva.ph"), dec(pl["price"], "fva.pl"))
        fva_high = max(dec(ph["price"], "fva.ph"), dec(pl["price"], "fva.pl"))
        row["fva_zone_low"], row["fva_zone_high"] = str(fva_low), str(fva_high)
        if fva_high < dec(gap["zone_low"], "fvg.low") or fva_low > dec(gap["zone_high"], "fvg.high"):
            row["status"] = "NO_FVA_OVERLAP"; ledger.append(row); continue
        woo = sorted([x for x in by_day[day_str] if woo_start <= parse_utc(x["ts_start_utc"]) < woo_end], key=lambda x: x["ts_start_utc"])
        if len(woo) != 6:
            raise ValidationError(f"{day_str} no longer has six complete WoO bars")
        rejection = None
        for i in range(len(woo) - 1):
            first, second = woo[i:i+2]
            if parse_utc(second["ts_start_utc"]) - parse_utc(first["ts_start_utc"]) != timedelta(minutes=15):
                continue
            first_rejects = dec(first["high"], "2cr.high") >= fva_high and dec(first["close"], "2cr.close") < fva_high
            second_rejects = dec(second["high"], "2cr.high") >= fva_high and dec(second["close"], "2cr.close") < fva_high
            if first_rejects or second_rejects:
                rejection = first if first_rejects else second
                break
        if rejection is None:
            row["status"] = "NO_2CR_REJECTION"; ledger.append(row); continue
        rejection_high = dec(rejection["high"], "rejection.high")
        rejection_ts = parse_utc(rejection["ts_start_utc"])
        row["rejection_ts_utc"], row["rejection_high"] = rejection["ts_start_utc"], str(rejection_high)
        activation = None; activation_index = None
        for i, bar in enumerate(woo):
            if parse_utc(bar["ts_start_utc"]) <= rejection_ts:
                continue
            if dec(bar["close"], "activation.close") > rejection_high:
                activation, activation_index = bar, i
                break
        if activation is None or activation_index is None:
            row["status"] = "NO_RUN"; ledger.append(row); continue
        row["activation_ts_utc"] = activation["ts_start_utc"]
        stings: list[tuple[int, dict]] = []
        for i, bar in enumerate(woo):
            if i <= activation_index:
                continue
            if dec(bar["low"], "sting.low") <= fva_high and dec(bar["high"], "sting.high") >= fva_low and dec(bar["close"], "sting.close") > fva_low:
                stings.append((i, bar))
            if len(stings) == 2:
                break
        if len(stings) != 2:
            row["status"] = "NO_2_STING"; ledger.append(row); continue
        _, first_sting = stings[0]; second_index, second_sting = stings[1]
        touch = fva_high; close_price = dec(second_sting["close"], "second.close")
        leg_low = min(dec(bar["low"], "leg.low") for bar in woo[activation_index:second_index+1])
        prior = [bar for bar in rows240 if parse_utc(bar["ts_start_utc"]) + timedelta(hours=4) <= woo_start]
        target = max(dec(bar["high"], "target.high") for bar in prior)
        target_source = max((bar for bar in prior if dec(bar["high"], "target.high") == target), key=lambda bar: bar["ts_start_utc"])
        if target <= touch or target <= close_price:
            row["status"] = "NO_TARGET_ABOVE_ENTRY"; ledger.append(row); continue
        if leg_low >= touch or leg_low >= close_price:
            row["status"] = "INVALID_STOP_ORDERING"; ledger.append(row); continue
        oid = f"OWNER-VAL-{day_str}"
        occurrence = {
            "occurrence_id": oid,
            "session_date_ny": day_str,
            "fvg_gap_id": gap["gap_id"],
            "fvg_zone_low": gap["zone_low"], "fvg_zone_high": gap["zone_high"],
            "fva_zone_low": str(fva_low), "fva_zone_high": str(fva_high),
            "rejection_ts_utc": rejection["ts_start_utc"], "rejection_high": str(rejection_high),
            "activation_ts_utc": activation["ts_start_utc"],
            "first_sting_ts_utc": first_sting["ts_start_utc"],
            "second_sting_ts_utc": second_sting["ts_start_utc"],
            "second_sting_bar_low": second_sting["low"], "second_sting_bar_high": second_sting["high"],
            "touch_price": str(touch), "close_price": str(close_price),
            "order_flow_leg_low": str(leg_low), "target_price": str(target),
            "target_source_ts_utc": target_source["ts_start_utc"],
        }
        occurrences.append(occurrence)
        row["status"] = "QUALIFIED"; row["occurrence_id"] = oid; ledger.append(row)
    ledger.sort(key=lambda x: x["session_date_ny"]); occurrences.sort(key=lambda x: x["session_date_ny"])
    return ledger, occurrences, dict(sorted(Counter(x["status"] for x in ledger).items()))


def execute_frozen(rows15: list[dict], occurrences: list[dict]) -> tuple[list[dict], list[dict]]:
    outcomes: list[dict] = []
    failures: list[dict] = []
    for occ in occurrences:
        touch = dec(occ["touch_price"], "touch")
        second_low = dec(occ["second_sting_bar_low"], "second.low")
        second_high = dec(occ["second_sting_bar_high"], "second.high")
        if not second_low <= touch <= second_high:
            failures.append({
                "occurrence_id": occ["occurrence_id"],
                "kind": "UNOBSERVABLE_SECOND_STING_TOUCH",
                "second_sting_ts_utc": occ["second_sting_ts_utc"],
                "touch_price": occ["touch_price"],
                "bar_low": occ["second_sting_bar_low"],
                "bar_high": occ["second_sting_bar_high"],
            })
            continue
        entry_ts = parse_utc(occ["second_sting_ts_utc"])
        entry, stop, target = float(touch), float(occ["order_flow_leg_low"]), float(occ["target_price"])
        emitted = None
        for bar in rows15:
            bar_ts = parse_utc(bar["ts_start_utc"])
            if not HSTART <= bar_ts < HEND or bar_ts < entry_ts:
                continue
            hit_stop = float(bar["low"]) <= stop
            hit_target = float(bar["high"]) >= target
            if not hit_stop and not hit_target:
                continue
            if bar_ts == entry_ts:
                status = "AMBIGUOUS_INTRABAR_ORDER"
            elif hit_stop and hit_target:
                status = "AMBIGUOUS_INTRABAR_ORDER"
            elif hit_stop:
                status = "STOP_FIRST"
            else:
                status = "TARGET_FIRST"
            emitted = {"occurrence_id": occ["occurrence_id"], "status": status, "entry_ts": entry_ts.isoformat(), "entry_price": entry, "stop_price": stop, "target_price": target, "event_ts": bar_ts.isoformat()}
            break
        if emitted is None:
            emitted = {"occurrence_id": occ["occurrence_id"], "status": "UNRESOLVED_WINDOW_END", "entry_ts": entry_ts.isoformat(), "entry_price": entry, "stop_price": stop, "target_price": target}
        outcomes.append(emitted)
    outcomes.sort(key=lambda x: x["occurrence_id"]); failures.sort(key=lambda x: (x["occurrence_id"], x["kind"]))
    return outcomes, failures


def build(protocol_path: Path, profile_path: Path, readiness_path: Path, cal_dirs: list[Path], holdout_dir: Path) -> dict:
    verify_inputs(protocol_path, profile_path, readiness_path, cal_dirs, holdout_dir)
    rows15 = combined_rows(cal_dirs, holdout_dir, 15); rows60 = combined_rows(cal_dirs, holdout_dir, 60); rows240 = combined_rows(cal_dirs, holdout_dir, 240)
    formations = detect_formations(rows240)
    sessions = complete_holdout_sessions(rows15)
    fvg_state = select_fvgs(rows15, formations, sessions)
    ledger, occurrences, counts = qualify(rows15, rows60, rows240, fvg_state)
    outcomes, failures = execute_frozen(rows15, occurrences)
    report = {
        "schema_version": 1,
        "path_id": "PRIMARY_PRODUCTION_PATH",
        "protocol_sha256": PROTOCOL_SHA,
        "profile_sha256": PROFILE_SHA,
        "holdout_boundary_ok": True,
        "holdout_accessed": True,
        "no_refit_performed": True,
        "complete_session_count": len(sessions),
        "detected_fvg_formation_count": len(formations),
        "holdout_formed_fvg_count": sum(HSTART <= parse_utc(gap["formation_end_utc"]) < HEND for gap in formations),
        "selected_fvg_session_count": fvg_state["selected_count"],
        "qualification_status_counts": counts,
        "qualification_rows_sha256": canonical_sha256(ledger),
        "qualified_occurrence_ids": [x["occurrence_id"] for x in occurrences],
        "occurrence_set_sha256": canonical_sha256(occurrences),
        "execution_outcomes": outcomes,
        "execution_outcomes_sha256": canonical_sha256(outcomes),
        "integrity_failures": failures,
        "integrity_failures_sha256": canonical_sha256(failures),
        "frozen_execution": {"second_sting_fill_event": "SECOND_STING_TOUCH", "stop_buffer_ticks": 0},
    }
    unsigned = dict(report); report["report_sha256"] = canonical_sha256(unsigned)
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", required=True); p.add_argument("--profile", required=True); p.add_argument("--readiness", required=True)
    p.add_argument("--calibration-dir", action="append", required=True); p.add_argument("--holdout-dir", required=True); p.add_argument("--output", required=True)
    args = p.parse_args()
    try:
        result = build(Path(args.protocol), Path(args.profile), Path(args.readiness), [Path(x) for x in args.calibration_dir], Path(args.holdout_dir))
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"primary protected validation failed: {exc}", file=sys.stderr); return 1
    print(json.dumps({"path_id": result["path_id"], "sessions": result["complete_session_count"], "qualified": len(result["qualified_occurrence_ids"]), "integrity_failures": len(result["integrity_failures"]), "report_sha256": result["report_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
