#!/usr/bin/env python3
"""Content-addressed artifact and acquisition-manifest utilities."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def base_record(source: dict[str, str], transport: str) -> dict[str, Any]:
    seed = f"{source['SOURCE_ID']}|{source['URL']}|{transport}".encode()
    return {
        "schema_version": SCHEMA_VERSION,
        "acquisition_id": "ACQ_" + hashlib.sha256(seed).hexdigest()[:24].upper(),
        "source_id": source["SOURCE_ID"],
        "source_type": source.get("SOURCE_TYPE", ""),
        "source_url": source["URL"],
        "attempted_at": utc_now(),
        "status": "SOURCE_CONTACTED_NO_PAYLOAD",
        "transport": transport,
        "first_party_contacted": True,
        "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD_ONLY",
        "semantic_extraction_performed": False,
        "artifacts": [],
        "sha256": "",
        "error_class": "",
        "error_detail": "",
        "http_status": None,
        "notes": "",
    }


def _suffix(content_type: str, fallback: str) -> str:
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) if content_type else None
    return ".html" if guessed == ".htm" else (guessed or fallback)


def store_artifact(cache_root: Path, payload: bytes, kind: str, content_type: str, suffix: str = ".bin") -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    target = cache_root / digest[:2] / f"{digest}{_suffix(content_type, suffix)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(payload)
    return {
        "kind": kind,
        "sha256": digest,
        "bytes": len(payload),
        "content_type": content_type,
        "cache_path": target.as_posix(),
    }


def add_artifacts(record: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    if not artifacts:
        return record
    record["artifacts"] = artifacts
    record["sha256"] = artifacts[0]["sha256"]
    record["status"] = "PAYLOAD_CAPTURED"
    return record


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            value = json.loads(raw)
            records[str(value["source_id"])] = value
    return records


def write_manifest(path: Path, records: Iterable[dict[str, Any]], merge: bool = True) -> None:
    by_source = load_manifest(path) if merge else {}
    for record in records:
        by_source[str(record["source_id"])] = record
    lines = [json.dumps(by_source[key], ensure_ascii=False, sort_keys=True, separators=(",", ":")) for key in sorted(by_source)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
