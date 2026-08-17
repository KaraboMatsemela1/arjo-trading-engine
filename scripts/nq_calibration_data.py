#!/usr/bin/env python3
"""Frozen NQ calibration data contract, acquisition adapter, and deterministic aggregation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
HOLDOUT_START = datetime(2026, 1, 1, tzinfo=UTC)


class CalibrationDataError(RuntimeError):
    pass


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise CalibrationDataError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def load_contract(path: str | Path) -> dict:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    end = parse_utc(contract["end_exclusive"])
    holdout = parse_utc(contract["protected_holdout_start"])
    if end > holdout or holdout != HOLDOUT_START:
        raise CalibrationDataError("request contract crosses protected holdout boundary")
    if contract["dataset"] != "GLBX.MDP3" or contract["schema"] != "ohlcv-1m":
        raise CalibrationDataError("unexpected provider dataset/schema")
    if contract["symbols"] != ["NQ.v.0"] or contract["stype_in"] != "continuous":
        raise CalibrationDataError("unexpected NQ continuous contract")
    return contract


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contract_sha256(path: str | Path) -> str:
    return file_sha256(path)


def acquire_databento(contract_path: str | Path, output_path: str | Path) -> Path:
    """Download only the frozen calibration range. Never used by CI."""
    contract = load_contract(contract_path)
    api_key = os.environ.get(contract["credential_env"])
    if not api_key:
        raise CalibrationDataError(f"missing required secret {contract['credential_env']}")
    try:
        import databento as db  # type: ignore
    except ImportError as exc:
        raise CalibrationDataError("databento package is required for live acquisition") from exc
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    client = db.Historical(api_key)
    client.timeseries.get_range(
        dataset=contract["dataset"],
        schema=contract["schema"],
        symbols=contract["symbols"],
        stype_in=contract["stype_in"],
        stype_out=contract["stype_out"],
        start=contract["start"],
        end=contract["end_exclusive"],
        path=output,
    )
    if not output.exists() or output.stat().st_size == 0:
        raise CalibrationDataError("provider returned no raw artifact")
    return output


@dataclass(frozen=True)
class MinuteBar:
    ts_event: datetime
    instrument_id: int
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def session_local(self) -> datetime:
        return self.ts_event.astimezone(NY)


def _bucket_start(ts: datetime, minutes: int) -> datetime:
    ts = ts.astimezone(UTC)
    epoch_minute = int(ts.timestamp() // 60)
    floored = epoch_minute - (epoch_minute % minutes)
    return datetime.fromtimestamp(floored * 60, tz=UTC)


def aggregate_bars(bars: Iterable[MinuteBar], minutes: int) -> list[dict]:
    if minutes not in {15, 60, 240}:
        raise CalibrationDataError("unsupported aggregation interval")
    ordered = sorted(bars, key=lambda b: b.ts_event)
    groups: dict[datetime, list[MinuteBar]] = {}
    for bar in ordered:
        if bar.ts_event.tzinfo is None:
            raise CalibrationDataError("bar timestamp must be timezone-aware")
        ts = bar.ts_event.astimezone(UTC)
        if ts >= HOLDOUT_START:
            raise CalibrationDataError("protected holdout bar encountered")
        groups.setdefault(_bucket_start(ts, minutes), []).append(bar)

    output: list[dict] = []
    for start in sorted(groups):
        bucket = groups[start]
        if len(bucket) != minutes:
            raise CalibrationDataError(f"incomplete {minutes}m bucket at {start.isoformat()}")
        expected = [start.timestamp() + 60 * i for i in range(minutes)]
        actual = [b.ts_event.astimezone(UTC).timestamp() for b in bucket]
        if actual != expected:
            raise CalibrationDataError(f"missing or duplicate minute in bucket {start.isoformat()}")
        ids = {b.instrument_id for b in bucket}
        if len(ids) != 1:
            raise CalibrationDataError(f"continuous-contract roll inside {minutes}m bucket")
        output.append(
            {
                "ts_start_utc": start.isoformat().replace("+00:00", "Z"),
                "session_start_local": start.astimezone(NY).isoformat(),
                "instrument_id": bucket[0].instrument_id,
                "open": bucket[0].open,
                "high": max(b.high for b in bucket),
                "low": min(b.low for b in bucket),
                "close": bucket[-1].close,
                "volume": sum(b.volume for b in bucket),
                "minutes": minutes,
            }
        )
    return output


def build_raw_manifest(contract_path: str | Path, artifact_path: str | Path, *, instrument_ids: Iterable[int], raw_symbols: Iterable[str], mapping_metadata_sha256: str | None = None) -> dict:
    contract = load_contract(contract_path)
    artifact = Path(artifact_path)
    if not artifact.exists() or artifact.stat().st_size <= 0:
        raise CalibrationDataError("raw artifact missing or empty")
    return {
        "schema_version": 1,
        "provider": "databento",
        "request_contract_sha256": contract_sha256(contract_path),
        "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "artifact_path": str(artifact),
        "artifact_sha256": file_sha256(artifact),
        "artifact_bytes": artifact.stat().st_size,
        "dataset": contract["dataset"],
        "schema": contract["schema"],
        "symbols": contract["symbols"],
        "stype_in": contract["stype_in"],
        "stype_out": contract["stype_out"],
        "start": contract["start"],
        "end_exclusive": contract["end_exclusive"],
        "protected_holdout_start": contract["protected_holdout_start"],
        "instrument_ids": sorted(set(instrument_ids)),
        "raw_symbols": sorted(set(raw_symbols)),
        "mapping_metadata_sha256": mapping_metadata_sha256,
    }
