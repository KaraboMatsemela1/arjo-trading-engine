#!/usr/bin/env python3
"""Independent standard-library protected-holdout evaluator.

No production FVG/context/replay builder is imported. Frozen conventions are
reimplemented directly to cross-check the primary validation path.
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


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"invalid timestamp {value!r}") from exc
    if dt.utcoffset() is None:
        raise ValidationError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def num(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"invalid decimal {label}") from exc
    if not result.is_finite():
        raise ValidationError(f"non-finite decimal {label}")
    return result


def verify_embedded(path: Path, field: str, expected: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = str(data.get(field, ""))
    unsigned = dict(data); unsigned.pop(field, None)
    if recorded != expected or canon(unsigned) != expected:
        raise ValidationError(f"{path} frozen SHA mismatch")
    return data


def verify_inputs(protocol_path: Path, profile_path: Path, readiness_path: Path, cal_dirs: list[Path], holdout_dir: Path) -> None:
    protocol = verify_embedded(protocol_path, "protocol_sha256", PROTOCOL_SHA)
    profile = verify_embedded(profile_path, "profile_sha256", PROFILE_SHA)
    if protocol.get("status") != "FROZEN_BEFORE_HOLDOUT_ACCESS":
        raise ValidationError("protocol is not frozen")
    if profile.get("claim_profile", {}).get("semantic_closure_claimed") is not False:
        raise ValidationError("profile claim boundary changed")
    fvg = profile.get("owner_conventions", {}).get("fvg", {})
    context = profile.get("owner_conventions", {}).get("context", {})
    if fvg.get("canonical_sha256") != FVG_SHA or context.get("canonical_sha256") != CONTEXT_SHA:
        raise ValidationError("owner convention profile binding changed")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if readiness.get("status") != "PROTECTED_HOLDOUT_DATA_READY" or readiness.get("manifest_byte_sha256") != HOLDOUT_MANIFEST_SHA:
        raise ValidationError("holdout readiness changed")
    if readiness.get("holdout_accessed") is not True or readiness.get("calibration_window_accessed_by_holdout_job") is not False:
        raise ValidationError("holdout readiness boundary changed")
    if len(cal_dirs) != 2:
        raise ValidationError("exactly two calibration context directories required")
    years: set[int] = set()
    for directory in cal_dirs:
        path = directory / "NAS100_USD.manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        year = parse(manifest["m1_first"]).year
        if year not in CAL_MANIFEST_SHA or year in years or file_sha(path) != CAL_MANIFEST_SHA.get(year):
            raise ValidationError("calibration context artifact changed")
        if manifest.get("holdout_accessed") is not False:
            raise ValidationError("calibration artifact indicates holdout access")
        years.add(year)
    if years != {2024, 2025}:
        raise ValidationError("calibration context incomplete")
    hp = holdout_dir / "NAS100_USD.manifest.json"
    hm = json.loads(hp.read_text(encoding="utf-8"))
    if file_sha(hp) != HOLDOUT_MANIFEST_SHA:
        raise ValidationError("holdout manifest SHA mismatch")
    if hm.get("requested_start") != "2026-01-01T00:00:00Z" or hm.get("requested_end_exclusive") != "2026-07-01T00:00:00Z":
        raise ValidationError("holdout interval changed")
    if hm.get("holdout_accessed") is not True or hm.get("calibration_window_accessed") is not False or hm.get("mutation_endpoints_used") is not False:
        raise ValidationError("holdout access/mutation boundary changed")


def read_rows(path: Path, minutes: int) -> list[dict]:
    output: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("minutes", -1)) != minutes:
                raise ValidationError(f"{path}:{line_no} wrong granularity")
            parse(row["ts_start_utc"])
            for field in ("open", "high", "low", "close"):
                num(row[field], field)
            output.append(row)
    output.sort(key=lambda row: row["ts_start_utc"])
    return output


def combined(cal_dirs: list[Path], holdout_dir: Path, minutes: int) -> list[dict]:
    rows: list[dict] = []
    for directory in [*cal_dirs, holdout_dir]:
        rows.extend(read_rows(directory / f"NAS100_USD.{minutes}m.jsonl", minutes))
    rows.sort(key=lambda row: row["ts_start_utc"])
    return rows


def gap_id(anchor: dict) -> str:
    return "OWNER-FVG-" + canon(anchor)[:20].upper()


def detect_fvgs(rows240: list[dict]) -> list[dict]:
    output: list[dict] = []
    for i in range(len(rows240) - 2):
        c1, c2, c3 = rows240[i:i+3]
        t1, t2, t3 = parse(c1["ts_start_utc"]), parse(c2["ts_start_utc"]), parse(c3["ts_start_utc"])
        if t2 - t1 != timedelta(hours=4) or t3 - t2 != timedelta(hours=4):
            continue
        h1, l1, h3, l3 = num(c1["high"], "c1.high"), num(c1["low"], "c1.low"), num(c3["high"], "c3.high"), num(c3["low"], "c3.low")
        if l3 > h1:
            direction, zone_low, zone_high = "BULLISH", h1, l3
        elif h3 < l1:
            direction, zone_low, zone_high = "BEARISH", h3, l1
        else:
            continue
        anchor = {
            "direction": direction,
            "zone_low": str(zone_low), "zone_high": str(zone_high),
            "c1_ts_start_utc": t1.isoformat().replace("+00:00", "Z"),
            "c2_ts_start_utc": t2.isoformat().replace("+00:00", "Z"),
            "c3_ts_start_utc": t3.isoformat().replace("+00:00", "Z"),
            "formation_end_utc": (t3 + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
        }
        anchor["gap_id"] = gap_id(anchor); anchor["classification"] = CLASSIFICATION; anchor["convention_id"] = "OWNER_OPERATIONAL_FVG_V1"
        output.append(anchor)
    output.sort(key=lambda row: (row["formation_end_utc"], row["gap_id"]))
    return output


def holdout_sessions(rows15: list[dict]) -> list[date]:
    required = {time(9,30), time(9,45), time(10), time(10,15), time(10,30), time(10,45)}
    seen: dict[date, set[time]] = defaultdict(set)
    for row in rows15:
        dt = parse(row["ts_start_utc"])
        if not HSTART <= dt < HEND:
            continue
        local = dt.astimezone(NY); clock = local.time().replace(tzinfo=None)
        if clock in required:
            seen[local.date()].add(clock)
    return sorted(day for day, clocks in seen.items() if clocks == required)


def select_time(day: date) -> datetime:
    return datetime.combine(day, time(9,30), tzinfo=NY).astimezone(UTC)


def fvg_sessions(rows15: list[dict], formations: list[dict], sessions: list[date]) -> list[dict]:
    fills: dict[datetime, list[dict]] = defaultdict(list)
    for bar in rows15:
        end = parse(bar["ts_start_utc"]) + timedelta(minutes=15)
        if end <= HEND:
            fills[end].append(bar)
    forms: dict[datetime, list[dict]] = defaultdict(list)
    for gap in formations:
        forms[parse(gap["formation_end_utc"])].append(gap)
    sess: dict[datetime, list[date]] = defaultdict(list)
    for day in sessions:
        sess[select_time(day)].append(day)
    active: dict[str, dict] = {}; output: list[dict] = []
    for event in sorted(set(fills) | set(forms) | set(sess)):
        if event > HEND:
            continue
        for bar in fills.get(event, []):
            low, high = num(bar["low"], "fill.low"), num(bar["high"], "fill.high")
            remove = [gid for gid, gap in active.items() if (gap["direction"] == "BULLISH" and low <= num(gap["zone_low"], "gap.low")) or (gap["direction"] == "BEARISH" and high >= num(gap["zone_high"], "gap.high"))]
            for gid in remove:
                active.pop(gid, None)
        for gap in forms.get(event, []):
            active[gap["gap_id"]] = gap
        for day in sess.get(event, []):
            chosen = max(active.values(), key=lambda gap: (gap["formation_end_utc"], gap["gap_id"])) if active else None
            output.append({"session_date_ny": day.isoformat(), "selected_fvg": chosen})
    output.sort(key=lambda row: row["session_date_ny"])
    return output


def pivots(rows60: list[dict]) -> tuple[list[dict], list[dict]]:
    highs: list[dict] = []; lows: list[dict] = []
    for i in range(1, len(rows60)-1):
        left, center, right = rows60[i-1:i+2]
        tl, tc, tr = parse(left["ts_start_utc"]), parse(center["ts_start_utc"]), parse(right["ts_start_utc"])
        if tc-tl != timedelta(hours=1) or tr-tc != timedelta(hours=1):
            continue
        ch, cl = num(center["high"], "pivot.high"), num(center["low"], "pivot.low")
        is_high = ch > num(left["high"], "left.high") and ch > num(right["high"], "right.high")
        is_low = cl < num(left["low"], "left.low") and cl < num(right["low"], "right.low")
        if is_high and is_low:
            continue
        confirmed = tr + timedelta(hours=1)
        if is_high:
            highs.append({"price": str(ch), "pivot_ts_utc": center["ts_start_utc"], "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z")})
        if is_low:
            lows.append({"price": str(cl), "pivot_ts_utc": center["ts_start_utc"], "confirmed_at_utc": confirmed.isoformat().replace("+00:00", "Z")})
    return highs, lows


def qualify(rows15: list[dict], rows60: list[dict], rows240: list[dict], sessions: list[dict]) -> tuple[list[dict], list[dict], dict]:
    phs, pls = pivots(rows60); by_day: dict[str, list[dict]] = defaultdict(list)
    for bar in rows15:
        by_day[parse(bar["ts_start_utc"]).astimezone(NY).date().isoformat()].append(bar)
    ledger: list[dict] = []; occurrences: list[dict] = []
    for item in sessions:
        day_str = item["session_date_ny"]; day = date.fromisoformat(day_str); start = select_time(day); end = datetime.combine(day, time(11), tzinfo=NY).astimezone(UTC); gap = item["selected_fvg"]
        lr: dict = {"session_date_ny": day_str, "status": None, "selected_fvg_gap_id": gap.get("gap_id") if gap else None}
        if gap is None:
            lr["status"] = "NO_FVG"; ledger.append(lr); continue
        eh = [p for p in phs if parse(p["confirmed_at_utc"]) <= start]; el = [p for p in pls if parse(p["confirmed_at_utc"]) <= start]
        if not eh or not el:
            lr["status"] = "NO_FVA_PIVOT"; ledger.append(lr); continue
        ph = max(eh, key=lambda p: (p["confirmed_at_utc"], p["pivot_ts_utc"])); pl = max(el, key=lambda p: (p["confirmed_at_utc"], p["pivot_ts_utc"]))
        fvl = min(num(ph["price"], "ph"), num(pl["price"], "pl")); fvh = max(num(ph["price"], "ph"), num(pl["price"], "pl")); lr["fva_zone_low"], lr["fva_zone_high"] = str(fvl), str(fvh)
        if fvh < num(gap["zone_low"], "gap.low") or fvl > num(gap["zone_high"], "gap.high"):
            lr["status"] = "NO_FVA_OVERLAP"; ledger.append(lr); continue
        woo = sorted([bar for bar in by_day[day_str] if start <= parse(bar["ts_start_utc"]) < end], key=lambda bar: bar["ts_start_utc"])
        if len(woo) != 6:
            raise ValidationError(f"{day_str} WoO completeness changed")
        rejection = None
        for i in range(len(woo)-1):
            a,b = woo[i:i+2]
            if parse(b["ts_start_utc"]) - parse(a["ts_start_utc"]) != timedelta(minutes=15):
                continue
            ar = num(a["high"], "reject.high") >= fvh and num(a["close"], "reject.close") < fvh
            br = num(b["high"], "reject.high") >= fvh and num(b["close"], "reject.close") < fvh
            if ar or br:
                rejection = a if ar else b; break
        if rejection is None:
            lr["status"] = "NO_2CR_REJECTION"; ledger.append(lr); continue
        rh = num(rejection["high"], "rejection.high"); rt = parse(rejection["ts_start_utc"]); lr["rejection_ts_utc"], lr["rejection_high"] = rejection["ts_start_utc"], str(rh)
        activation = None; ai = None
        for i, bar in enumerate(woo):
            if parse(bar["ts_start_utc"]) <= rt:
                continue
            if num(bar["close"], "activation.close") > rh:
                activation, ai = bar, i; break
        if activation is None or ai is None:
            lr["status"] = "NO_RUN"; ledger.append(lr); continue
        lr["activation_ts_utc"] = activation["ts_start_utc"]
        stings: list[tuple[int,dict]] = []
        for i, bar in enumerate(woo):
            if i <= ai:
                continue
            if num(bar["low"], "sting.low") <= fvh and num(bar["high"], "sting.high") >= fvl and num(bar["close"], "sting.close") > fvl:
                stings.append((i,bar))
            if len(stings) == 2:
                break
        if len(stings) != 2:
            lr["status"] = "NO_2_STING"; ledger.append(lr); continue
        _, s1 = stings[0]; si, s2 = stings[1]; touch = fvh; close_price = num(s2["close"], "second.close"); leg = min(num(bar["low"], "leg.low") for bar in woo[ai:si+1])
        prior = [bar for bar in rows240 if parse(bar["ts_start_utc"]) + timedelta(hours=4) <= start]
        target = max(num(bar["high"], "target.high") for bar in prior); source = max((bar for bar in prior if num(bar["high"], "target.high") == target), key=lambda bar: bar["ts_start_utc"])
        if target <= touch or target <= close_price:
            lr["status"] = "NO_TARGET_ABOVE_ENTRY"; ledger.append(lr); continue
        if leg >= touch or leg >= close_price:
            lr["status"] = "INVALID_STOP_ORDERING"; ledger.append(lr); continue
        oid = f"OWNER-VAL-{day_str}"
        occurrence = {
            "occurrence_id": oid, "session_date_ny": day_str, "fvg_gap_id": gap["gap_id"],
            "fvg_zone_low": gap["zone_low"], "fvg_zone_high": gap["zone_high"], "fva_zone_low": str(fvl), "fva_zone_high": str(fvh),
            "rejection_ts_utc": rejection["ts_start_utc"], "rejection_high": str(rh), "activation_ts_utc": activation["ts_start_utc"],
            "first_sting_ts_utc": s1["ts_start_utc"], "second_sting_ts_utc": s2["ts_start_utc"],
            "second_sting_bar_low": s2["low"], "second_sting_bar_high": s2["high"], "touch_price": str(touch), "close_price": str(close_price),
            "order_flow_leg_low": str(leg), "target_price": str(target), "target_source_ts_utc": source["ts_start_utc"],
        }
        occurrences.append(occurrence); lr["status"] = "QUALIFIED"; lr["occurrence_id"] = oid; ledger.append(lr)
    ledger.sort(key=lambda row: row["session_date_ny"]); occurrences.sort(key=lambda row: row["session_date_ny"])
    return ledger, occurrences, dict(sorted(Counter(row["status"] for row in ledger).items()))


def execute(rows15: list[dict], occurrences: list[dict]) -> tuple[list[dict], list[dict]]:
    outcomes: list[dict] = []; failures: list[dict] = []
    for occ in occurrences:
        touch = num(occ["touch_price"], "touch"); low = num(occ["second_sting_bar_low"], "second.low"); high = num(occ["second_sting_bar_high"], "second.high")
        if not low <= touch <= high:
            failures.append({"occurrence_id": occ["occurrence_id"], "kind": "UNOBSERVABLE_SECOND_STING_TOUCH", "second_sting_ts_utc": occ["second_sting_ts_utc"], "touch_price": occ["touch_price"], "bar_low": occ["second_sting_bar_low"], "bar_high": occ["second_sting_bar_high"]})
            continue
        entry_ts = parse(occ["second_sting_ts_utc"]); entry, stop, target = float(touch), float(occ["order_flow_leg_low"]), float(occ["target_price"]); emitted = None
        for bar in rows15:
            bt = parse(bar["ts_start_utc"])
            if not HSTART <= bt < HEND or bt < entry_ts:
                continue
            hs, ht = float(bar["low"]) <= stop, float(bar["high"]) >= target
            if not hs and not ht:
                continue
            if bt == entry_ts or (hs and ht): status = "AMBIGUOUS_INTRABAR_ORDER"
            elif hs: status = "STOP_FIRST"
            else: status = "TARGET_FIRST"
            emitted = {"occurrence_id": occ["occurrence_id"], "status": status, "entry_ts": entry_ts.isoformat(), "entry_price": entry, "stop_price": stop, "target_price": target, "event_ts": bt.isoformat()}; break
        if emitted is None:
            emitted = {"occurrence_id": occ["occurrence_id"], "status": "UNRESOLVED_WINDOW_END", "entry_ts": entry_ts.isoformat(), "entry_price": entry, "stop_price": stop, "target_price": target}
        outcomes.append(emitted)
    outcomes.sort(key=lambda row: row["occurrence_id"]); failures.sort(key=lambda row: (row["occurrence_id"], row["kind"]))
    return outcomes, failures


def build(protocol_path: Path, profile_path: Path, readiness_path: Path, cal_dirs: list[Path], holdout_dir: Path) -> dict:
    verify_inputs(protocol_path, profile_path, readiness_path, cal_dirs, holdout_dir)
    rows15 = combined(cal_dirs, holdout_dir, 15); rows60 = combined(cal_dirs, holdout_dir, 60); rows240 = combined(cal_dirs, holdout_dir, 240)
    formations = detect_fvgs(rows240); sessions = holdout_sessions(rows15); selected = fvg_sessions(rows15, formations, sessions)
    ledger, occurrences, counts = qualify(rows15, rows60, rows240, selected); outcomes, failures = execute(rows15, occurrences)
    report = {
        "schema_version": 1, "path_id": "INDEPENDENT_STANDARD_LIBRARY_PATH", "protocol_sha256": PROTOCOL_SHA, "profile_sha256": PROFILE_SHA,
        "holdout_boundary_ok": True, "holdout_accessed": True, "no_refit_performed": True,
        "complete_session_count": len(sessions), "detected_fvg_formation_count": len(formations),
        "holdout_formed_fvg_count": sum(HSTART <= parse(g["formation_end_utc"]) < HEND for g in formations),
        "selected_fvg_session_count": sum(row["selected_fvg"] is not None for row in selected),
        "qualification_status_counts": counts, "qualification_rows_sha256": canon(ledger),
        "qualified_occurrence_ids": [row["occurrence_id"] for row in occurrences], "occurrence_set_sha256": canon(occurrences),
        "execution_outcomes": outcomes, "execution_outcomes_sha256": canon(outcomes),
        "integrity_failures": failures, "integrity_failures_sha256": canon(failures),
        "frozen_execution": {"second_sting_fill_event": "SECOND_STING_TOUCH", "stop_buffer_ticks": 0},
    }
    unsigned = dict(report); report["report_sha256"] = canon(unsigned); return report


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--protocol",required=True);p.add_argument("--profile",required=True);p.add_argument("--readiness",required=True);p.add_argument("--calibration-dir",action="append",required=True);p.add_argument("--holdout-dir",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    try:
        result=build(Path(a.protocol),Path(a.profile),Path(a.readiness),[Path(x) for x in a.calibration_dir],Path(a.holdout_dir));Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    except Exception as exc:
        print(f"independent protected validation failed: {exc}",file=sys.stderr);return 1
    print(json.dumps({"path_id":result["path_id"],"sessions":result["complete_session_count"],"qualified":len(result["qualified_occurrence_ids"]),"integrity_failures":len(result["integrity_failures"]),"report_sha256":result["report_sha256"]},sort_keys=True));return 0


if __name__ == "__main__": raise SystemExit(main())
