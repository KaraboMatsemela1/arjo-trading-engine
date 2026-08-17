#!/usr/bin/env python3
"""Build outcome-blind annotation packs from sealed OANDA calibration bars.

This module deliberately performs no Arjo semantic discovery. It only slices the
already-sealed derived bars into deterministic context packets that end at the
frozen 11:00 America/New_York opportunity-window boundary. Semantic anchors are
added later by isolated evidence-constrained annotation passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CAL_START = datetime(2024, 1, 1, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)
EXPECTED_PROVIDER = {
    "provider": "OANDA_V20",
    "environment": "practice",
    "instrument": "NAS100_USD",
    "instrument_identity": "OANDA_NASDAQ100_CFD_PROXY_FOR_LOCKED_NQ_SEED",
    "price_component": "MID",
}
ARTIFACT_BY_YEAR = {2024: 9282976276, 2025: 9283007527}
TF_MINUTES = {"15m": 15, "60m": 60, "240m": 240}
CONTEXT_LOOKBACK = {"15m": timedelta(days=1), "60m": timedelta(days=3), "240m": timedelta(days=7)}


class PackError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise PackError(f"naive timestamp: {value}")
    return dt.astimezone(UTC)


def load_jsonl(path: Path, minutes: int) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if int(row.get("minutes", -1)) != minutes:
                raise PackError(f"{path}:{line_no} unexpected minutes")
            ts = parse_utc(str(row["ts_start_utc"]))
            end = ts + timedelta(minutes=minutes)
            if not CAL_START <= ts < HOLDOUT_START or end > HOLDOUT_START:
                raise PackError(f"{path}:{line_no} outside calibration window")
            rows.append(row)
    rows.sort(key=lambda x: x["ts_start_utc"])
    return rows


def validate_manifest(manifest: dict, *, year: int, artifact_id: int) -> None:
    for key, expected in EXPECTED_PROVIDER.items():
        if manifest.get(key) != expected:
            raise PackError(f"manifest provider mismatch: {key}")
    if manifest.get("holdout_accessed") is not False or manifest.get("holdout_requested") is not False:
        raise PackError("manifest indicates holdout access/request")
    if manifest.get("mutation_endpoints_used") is not False:
        raise PackError("manifest indicates trading/mutation endpoint use")
    if artifact_id != ARTIFACT_BY_YEAR.get(year):
        raise PackError("artifact id does not match frozen annual artifact")
    first = parse_utc(str(manifest["m1_first"]))
    last = parse_utc(str(manifest["m1_last"]))
    if first.year != year or last.year != year:
        raise PackError("manifest year mismatch")


def session_cutoffs(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time(9, 30), tzinfo=NY)
    end_local = datetime.combine(day, time(11, 0), tzinfo=NY)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def complete_woo_days(rows15: list[dict]) -> list[date]:
    by_day: dict[date, set[time]] = {}
    required = {time(9, 30), time(9, 45), time(10, 0), time(10, 15), time(10, 30), time(10, 45)}
    for row in rows15:
        ts = parse_utc(row["ts_start_utc"])
        local = ts.astimezone(NY)
        if local.time().replace(tzinfo=None) in required:
            by_day.setdefault(local.date(), set()).add(local.time().replace(tzinfo=None))
    return sorted(day for day, clocks in by_day.items() if clocks == required)


def slice_rows(rows: list[dict], *, minutes: int, start: datetime, cutoff: datetime) -> list[dict]:
    result: list[dict] = []
    delta = timedelta(minutes=minutes)
    for row in rows:
        ts = parse_utc(row["ts_start_utc"])
        end = ts + delta
        # Critical anti-leak invariant: the entire bar must be known by cutoff.
        if start <= ts and end <= cutoff:
            result.append(row)
    return result


def build_pack(*, day: date, bars: dict[str, list[dict]], manifest: dict, manifest_path: Path, artifact_id: int) -> dict:
    woo_start, cutoff = session_cutoffs(day)
    if not CAL_START <= woo_start < HOLDOUT_START or cutoff > HOLDOUT_START:
        raise PackError("session cutoff outside calibration window")
    contexts: dict[str, list[dict]] = {}
    for tf, minutes in TF_MINUTES.items():
        contexts[tf] = slice_rows(
            bars[tf], minutes=minutes, start=cutoff - CONTEXT_LOOKBACK[tf], cutoff=cutoff
        )
    woo_rows = [
        row for row in contexts["15m"]
        if woo_start <= parse_utc(row["ts_start_utc"]) < cutoff
    ]
    if len(woo_rows) != 6:
        raise PackError(f"{day.isoformat()} does not have six complete 15m WoO bars")
    pack = {
        "schema_version": 1,
        "status": "OUTCOME_BLIND_ANNOTATION_PACK",
        "session_date_ny": day.isoformat(),
        "woo": {
            "timezone": "America/New_York",
            "start_inclusive": "09:30:00",
            "end_exclusive": "11:00:00",
            "start_utc": woo_start.isoformat().replace("+00:00", "Z"),
            "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
        },
        "provider_identity": {
            "provider": manifest["provider"],
            "environment": manifest["environment"],
            "instrument": manifest["instrument"],
            "instrument_identity": manifest["instrument_identity"],
            "price_component": manifest["price_component"],
        },
        "calibration_data_ref": {
            "artifact_id": artifact_id,
            "annual_manifest_sha256": file_sha256(manifest_path),
            "annual_m1_sha256": manifest["m1_sha256"],
        },
        "annotation_boundary": {
            "outcome_blind": True,
            "post_woo_bars_included": False,
            "holdout_accessed": False,
            "semantic_discovery_performed": False,
            "purpose": "EVIDENCE_CONSTRAINED_SEMANTIC_ANNOTATION_ONLY",
        },
        "context": contexts,
    }
    # Assert no represented bar reaches beyond the cutoff.
    for tf, rows in contexts.items():
        minutes = TF_MINUTES[tf]
        for row in rows:
            if parse_utc(row["ts_start_utc"]) + timedelta(minutes=minutes) > cutoff:
                raise PackError("post-WoO leakage detected")
    pack["pack_sha256"] = canonical_sha256(pack)
    return pack


def build_all(*, derived_dir: Path, manifest_path: Path, artifact_id: int, output_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    year = parse_utc(str(manifest["m1_first"])).year
    validate_manifest(manifest, year=year, artifact_id=artifact_id)
    bars = {
        "15m": load_jsonl(derived_dir / "NAS100_USD.15m.jsonl", 15),
        "60m": load_jsonl(derived_dir / "NAS100_USD.60m.jsonl", 60),
        "240m": load_jsonl(derived_dir / "NAS100_USD.240m.jsonl", 240),
    }
    days = [day for day in complete_woo_days(bars["15m"]) if day.year == year]
    if not days:
        raise PackError("no complete frozen WoO days found")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for day in days:
        pack = build_pack(day=day, bars=bars, manifest=manifest, manifest_path=manifest_path, artifact_id=artifact_id)
        path = output_dir / f"{day.isoformat()}.json"
        path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append({"session_date_ny": day.isoformat(), "pack_sha256": pack["pack_sha256"]})
    manifest_out = {
        "schema_version": 1,
        "status": "OUTCOME_BLIND_ANNOTATION_PACKS_READY",
        "year": year,
        "artifact_id": artifact_id,
        "pack_count": len(rows),
        "post_woo_bars_included": False,
        "holdout_accessed": False,
        "performance_fields_included": False,
        "packs_sha256": canonical_sha256(rows),
        "packs": rows,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest_out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--derived-dir", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--artifact-id", type=int, required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    try:
        result = build_all(
            derived_dir=Path(args.derived_dir), manifest_path=Path(args.manifest),
            artifact_id=args.artifact_id, output_dir=Path(args.output_dir)
        )
    except (OSError, json.JSONDecodeError, ValueError, PackError) as exc:
        print(f"annotation pack build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: result[k] for k in ("status", "year", "pack_count", "packs_sha256")}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
