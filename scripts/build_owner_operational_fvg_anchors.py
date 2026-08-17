#!/usr/bin/env python3
"""Build deterministic pre-WoO 4h FVG anchors under OWNER_OPERATIONAL_FVG_V1.

This is not Arjo semantic discovery. The exact geometry, fill rule, and chronological
selector are an owner-authorized project convention frozen before occurrence replay
outcome inspection. The builder is streaming/time-causal: future session bars,
performance fields, and protected holdout data are never used for selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CAL_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
EXPECTED_ARTIFACTS = {2024: 9282976276, 2025: 9283007527}
EXPECTED_PROVIDER = {
    "provider": "OANDA_V20",
    "venue": "OANDA_FXTRADE",
    "environment": "practice",
    "instrument": "NAS100_USD",
    "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
    "price_component": "MID",
}
EXPECTED_CONVENTION_ID = "OWNER_OPERATIONAL_FVG_V1"
EXPECTED_CLASSIFICATION = "OWNER_OPERATIONAL_CONVENTION_NOT_ARJO_SEMANTIC_CLOSURE"


class FvgError(RuntimeError):
    pass


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FvgError(f"invalid timestamp: {value!r}") from exc
    if dt.utcoffset() is None:
        raise FvgError(f"naive timestamp: {value!r}")
    return dt.astimezone(UTC)


def decimal(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FvgError(f"invalid decimal {label}") from exc
    if not parsed.is_finite():
        raise FvgError(f"non-finite decimal {label}")
    return parsed


def load_convention(path: Path) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = data.get("convention_sha256")
    unsigned = dict(data)
    unsigned.pop("convention_sha256", None)
    actual = canonical_sha256(unsigned)
    if recorded != actual:
        raise FvgError("owner FVG convention SHA mismatch")
    if data.get("convention_id") != EXPECTED_CONVENTION_ID:
        raise FvgError("unexpected owner FVG convention id")
    if data.get("classification") != EXPECTED_CLASSIFICATION:
        raise FvgError("unexpected owner FVG classification")
    if data.get("authority") != "OWNER_DIRECTED_OPERATIONAL_CONVENTION":
        raise FvgError("unexpected owner FVG authority")
    if data.get("anti_bias", {}).get("performance_based_selection_allowed") is not False:
        raise FvgError("performance-based selection must remain prohibited")
    if data.get("calibration_boundary", {}).get("holdout_access_allowed") is not False:
        raise FvgError("holdout must remain prohibited")
    return data, actual


def validate_manifest(path: Path, year: int) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for key, expected in EXPECTED_PROVIDER.items():
        if manifest.get(key) != expected:
            raise FvgError(f"{year} manifest mismatch: {key}")
    if manifest.get("holdout_requested") is not False or manifest.get("holdout_accessed") is not False:
        raise FvgError(f"{year} manifest indicates holdout request/access")
    if manifest.get("mutation_endpoints_used") is not False:
        raise FvgError(f"{year} manifest indicates mutation endpoint use")
    first = parse_utc(str(manifest["m1_first"]))
    last = parse_utc(str(manifest["m1_last"]))
    if first.year != year or last.year != year:
        raise FvgError(f"{year} manifest year mismatch")
    return manifest


def load_jsonl(path: Path, expected_minutes: int) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("minutes", -1)) != expected_minutes:
                raise FvgError(f"{path}:{line_no} unexpected minutes")
            ts = parse_utc(str(row["ts_start_utc"]))
            end = ts + timedelta(minutes=expected_minutes)
            if ts < CAL_START or end > HOLDOUT_START:
                raise FvgError(f"{path}:{line_no} outside calibration boundary")
            for field in ("open", "high", "low", "close"):
                decimal(row.get(field), f"{path}:{line_no}.{field}")
            rows.append(row)
    rows.sort(key=lambda row: row["ts_start_utc"])
    return rows


def gap_id(anchor: dict) -> str:
    return "OWNER-FVG-" + canonical_sha256(anchor)[:20].upper()


def detect_formations(rows240: list[dict]) -> list[dict]:
    rows = sorted(rows240, key=lambda row: row["ts_start_utc"])
    formations: list[dict] = []
    for index in range(len(rows) - 2):
        c1, c2, c3 = rows[index : index + 3]
        t1 = parse_utc(c1["ts_start_utc"])
        t2 = parse_utc(c2["ts_start_utc"])
        t3 = parse_utc(c3["ts_start_utc"])
        if t2 - t1 != timedelta(hours=4) or t3 - t2 != timedelta(hours=4):
            continue
        high1, low1 = decimal(c1["high"], "c1.high"), decimal(c1["low"], "c1.low")
        high3, low3 = decimal(c3["high"], "c3.high"), decimal(c3["low"], "c3.low")
        direction = None
        zone_low = zone_high = None
        if low3 > high1:
            direction = "BULLISH"
            zone_low, zone_high = high1, low3
        elif high3 < low1:
            direction = "BEARISH"
            zone_low, zone_high = high3, low1
        if direction is None:
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
        anchor["classification"] = EXPECTED_CLASSIFICATION
        anchor["convention_id"] = EXPECTED_CONVENTION_ID
        formations.append(anchor)
    formations.sort(key=lambda item: (item["formation_end_utc"], item["gap_id"]))
    return formations


def complete_woo_days(rows15: list[dict]) -> list[date]:
    required = {time(9, 30), time(9, 45), time(10, 0), time(10, 15), time(10, 30), time(10, 45)}
    by_day: dict[date, set[time]] = defaultdict(set)
    for row in rows15:
        local = parse_utc(row["ts_start_utc"]).astimezone(NY)
        clock = local.time().replace(tzinfo=None)
        if clock in required:
            by_day[local.date()].add(clock)
    return sorted(
        day for day, clocks in by_day.items()
        if clocks == required and day.year in EXPECTED_ARTIFACTS
    )


def selection_time(day: date) -> datetime:
    return datetime.combine(day, time(9, 30), tzinfo=NY).astimezone(UTC)


def stream_select(rows15: list[dict], formations: list[dict], sessions: list[date], convention_sha: str) -> dict:
    fill_events: dict[datetime, list[dict]] = defaultdict(list)
    for row in rows15:
        fill_events[parse_utc(row["ts_start_utc"]) + timedelta(minutes=15)].append(row)
    formation_events: dict[datetime, list[dict]] = defaultdict(list)
    for gap in formations:
        formation_events[parse_utc(gap["formation_end_utc"])].append(gap)
    session_events: dict[datetime, list[date]] = defaultdict(list)
    for day in sessions:
        session_events[selection_time(day)].append(day)

    event_times = sorted(set(fill_events) | set(formation_events) | set(session_events))
    active: dict[str, dict] = {}
    output_rows: list[dict] = []
    deactivated = 0

    for event_time in event_times:
        if event_time >= HOLDOUT_START:
            raise FvgError("event stream reached holdout")

        # Frozen same-timestamp order: a completed 15m bar confirms fills first;
        # then a 4h gap becomes known; then the 09:30 session selection occurs.
        # This prevents the c3 candle from retroactively filling its own new gap.
        for bar in fill_events.get(event_time, []):
            low = decimal(bar["low"], "15m.low")
            high = decimal(bar["high"], "15m.high")
            remove: list[str] = []
            for gid, gap in active.items():
                if gap["direction"] == "BULLISH" and low <= decimal(gap["zone_low"], "gap.zone_low"):
                    remove.append(gid)
                elif gap["direction"] == "BEARISH" and high >= decimal(gap["zone_high"], "gap.zone_high"):
                    remove.append(gid)
            for gid in remove:
                active.pop(gid, None)
                deactivated += 1

        for gap in formation_events.get(event_time, []):
            active[gap["gap_id"]] = gap

        for day in session_events.get(event_time, []):
            chosen = max(active.values(), key=lambda gap: (gap["formation_end_utc"], gap["gap_id"])) if active else None
            row = {
                "session_date_ny": day.isoformat(),
                "selection_time_utc": event_time.isoformat().replace("+00:00", "Z"),
                "classification": EXPECTED_CLASSIFICATION,
                "convention_id": EXPECTED_CONVENTION_ID,
                "convention_sha256": convention_sha,
                "future_session_bars_used": False,
                "holdout_accessed": False,
                "performance_fields_used": False,
                "active_gap_count_at_selection": len(active),
                "status": "OWNER_FVG_SELECTED" if chosen else "NO_ACTIVE_OWNER_FVG",
                "selected_fvg": chosen,
            }
            output_rows.append(row)

    output_rows.sort(key=lambda row: row["session_date_ny"])
    return {
        "schema_version": 1,
        "status": "OWNER_OPERATIONAL_FVG_SESSION_ANCHORS_READY",
        "classification": EXPECTED_CLASSIFICATION,
        "convention_id": EXPECTED_CONVENTION_ID,
        "convention_sha256": convention_sha,
        "session_count": len(output_rows),
        "selected_session_count": sum(row["selected_fvg"] is not None for row in output_rows),
        "no_active_fvg_session_count": sum(row["selected_fvg"] is None for row in output_rows),
        "detected_formation_count": len(formations),
        "deactivated_formation_count_during_stream": deactivated,
        "future_session_bars_used": False,
        "holdout_accessed": False,
        "performance_fields_used": False,
        "session_anchors_sha256": canonical_sha256(output_rows),
        "sessions": output_rows,
    }


def build(convention_path: Path, artifact_dirs: list[Path]) -> dict:
    _, convention_sha = load_convention(convention_path)
    if len(artifact_dirs) != 2:
        raise FvgError("exactly two frozen annual artifact directories are required")

    all15: list[dict] = []
    all240: list[dict] = []
    source_manifests: list[dict] = []
    seen_years: set[int] = set()

    for directory in artifact_dirs:
        manifest_path = directory / "NAS100_USD.manifest.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        year = parse_utc(str(raw["m1_first"])).year
        if year not in EXPECTED_ARTIFACTS or year in seen_years:
            raise FvgError("unexpected or duplicate artifact year")
        seen_years.add(year)
        manifest = validate_manifest(manifest_path, year)
        all15.extend(load_jsonl(directory / "NAS100_USD.15m.jsonl", 15))
        all240.extend(load_jsonl(directory / "NAS100_USD.240m.jsonl", 240))
        source_manifests.append({
            "year": year,
            "artifact_id": EXPECTED_ARTIFACTS[year],
            "manifest_sha256": file_sha256(manifest_path),
            "retrieval_sha256": manifest["retrieval_sha256"],
        })

    if seen_years != set(EXPECTED_ARTIFACTS):
        raise FvgError("frozen annual artifact set incomplete")

    all15.sort(key=lambda row: row["ts_start_utc"])
    all240.sort(key=lambda row: row["ts_start_utc"])
    sessions = complete_woo_days(all15)
    if len(sessions) != 515:
        raise FvgError(f"expected 515 complete sessions, found {len(sessions)}")

    formations = detect_formations(all240)
    result = stream_select(all15, formations, sessions, convention_sha)
    result["source_manifests"] = sorted(source_manifests, key=lambda item: item["year"])
    result["source_artifact_ids"] = [EXPECTED_ARTIFACTS[2024], EXPECTED_ARTIFACTS[2025]]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--convention", required=True)
    parser.add_argument("--artifact-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(Path(args.convention), [Path(value) for value in args.artifact_dir])
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError, FvgError) as exc:
        print(f"owner FVG build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": result["status"],
        "session_count": result["session_count"],
        "selected_session_count": result["selected_session_count"],
        "no_active_fvg_session_count": result["no_active_fvg_session_count"],
        "detected_formation_count": result["detected_formation_count"],
        "session_anchors_sha256": result["session_anchors_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
