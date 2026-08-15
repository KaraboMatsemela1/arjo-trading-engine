#!/usr/bin/env python3
"""Offline tests for deterministic sharding, manifest merge and corpus coverage."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "SOURCE_ID", "SOURCE_TYPE", "TITLE", "URL", "PUBLICATION_DATE", "AUTHOR",
    "CHANNEL_ID", "FIRST_PARTY_STATUS", "RETRIEVAL_DATE", "RAW_ARTIFACT_SHA256",
    "TRANSCRIPT_AVAILABLE", "FRAME_EXTRACTION_AVAILABLE", "NOTES",
]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], text=True, capture_output=True, check=False)


def source_row(source_id: str, source_type: str) -> dict[str, str]:
    return {
        field: {
            "SOURCE_ID": source_id,
            "SOURCE_TYPE": source_type,
            "TITLE": source_id,
            "URL": f"https://example.invalid/{source_id}",
            "FIRST_PARTY_STATUS": "CONFIRMED_FIRST_PARTY",
        }.get(field, "")
        for field in FIELDS
    }


def terminal(source_id: str, source_type: str, status: str) -> dict:
    captured = status == "PAYLOAD_CAPTURED"
    digest = "a" * 64 if captured else ""
    return {
        "schema_version": 1,
        "acquisition_id": f"ACQ_{source_id}",
        "source_id": source_id,
        "source_type": source_type,
        "source_url": f"https://example.invalid/{source_id}",
        "attempted_at": "2026-08-15T00:00:00Z",
        "status": status,
        "transport": "fixture",
        "first_party_contacted": True,
        "closure_credit": "DIRECT_FIRST_PARTY_PAYLOAD" if captured else "ZERO_NO_PAYLOAD",
        "semantic_extraction_performed": False,
        "artifacts": ([{"kind": "TEST", "sha256": digest, "bytes": 1, "content_type": "text/plain", "content_address": f"aa/{digest}.txt"}] if captured else []),
        "sha256": digest,
        "error_class": "",
        "error_detail": "",
        "http_status": None,
        "notes": "",
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        registry = base / "source_registry.csv"
        shards = base / "shards"
        shards.mkdir()
        merged = base / "merged.jsonl"
        coverage = base / "coverage.json"

        rows = [
            source_row("A", "TELEGRAM_POST"),
            source_row("B", "YOUTUBE_VIDEO"),
            source_row("C", "TELEGRAM_POST"),
            source_row("ROOT", "PLATFORM_ROOT"),
        ]
        with registry.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        plan0 = run(str(ROOT / "scripts/acquire_corpus.py"), "--registry", str(registry), "--shard-count", "2", "--shard-index", "0", "--plan")
        plan1 = run(str(ROOT / "scripts/acquire_corpus.py"), "--registry", str(registry), "--shard-count", "2", "--shard-index", "1", "--plan")
        assert plan0.returncode == 0 and plan1.returncode == 0
        assert json.loads(plan0.stdout)["selected"] + json.loads(plan1.stdout)["selected"] == 3

        (shards / "shard-0.jsonl").write_text(json.dumps(terminal("A", "TELEGRAM_POST", "PAYLOAD_CAPTURED")) + "\n" + json.dumps(terminal("C", "TELEGRAM_POST", "PAYLOAD_CAPTURED")) + "\n", encoding="utf-8")
        (shards / "shard-1.jsonl").write_text(json.dumps(terminal("B", "YOUTUBE_VIDEO", "ENVIRONMENT_ACCESS_FAILURE")) + "\n", encoding="utf-8")

        merge = run(str(ROOT / "scripts/merge_acquisition_manifests.py"), "--input-dir", str(shards), "--output", str(merged))
        if merge.returncode:
            print(merge.stdout, merge.stderr, file=sys.stderr)
            return 1

        validate = run(str(ROOT / "scripts/check_acquisition_manifest.py"), "--registry", str(registry), "--manifest", str(merged))
        if validate.returncode:
            print(validate.stdout, validate.stderr, file=sys.stderr)
            return 1

        audit = run(str(ROOT / "scripts/check_corpus_coverage.py"), "--registry", str(registry), "--manifest", str(merged), "--report", str(coverage))
        if audit.returncode:
            print(audit.stdout, audit.stderr, file=sys.stderr)
            return 1
        report = json.loads(coverage.read_text(encoding="utf-8"))
        assert report["complete"] is True
        assert report["relevant_source_count"] == 3
        assert report["terminal_record_count"] == 3
        assert report["by_status"]["PAYLOAD_CAPTURED"] == 2
        assert report["by_status"]["ENVIRONMENT_ACCESS_FAILURE"] == 1

    print("Corpus acquisition orchestration tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
