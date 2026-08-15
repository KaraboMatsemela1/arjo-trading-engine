#!/usr/bin/env python3
"""Offline deterministic smoke test for corpus acquisition tooling."""

from __future__ import annotations

import csv
import hashlib
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


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        registry = base / "source_registry.csv"
        manifest = base / "manifest.jsonl"
        cache = base / "cache"
        fixtures = base / "fixtures"
        fixtures.mkdir()

        with registry.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow({field: {"SOURCE_ID":"YT_VIDEO_demo","SOURCE_TYPE":"YOUTUBE_VIDEO","TITLE":"Demo","URL":"https://www.youtube.com/watch?v=demo","FIRST_PARTY_STATUS":"CONFIRMED_FIRST_PARTY"}.get(field, "") for field in FIELDS})
            writer.writerow({field: {"SOURCE_ID":"ROOT_demo","SOURCE_TYPE":"PLATFORM_ROOT","TITLE":"Root","URL":"https://example.invalid/root","FIRST_PARTY_STATUS":"CONFIRMED_FIRST_PARTY"}.get(field, "") for field in FIELDS})

        payload = {"id": "demo", "title": "Fixture metadata", "description": "fixture only"}
        (fixtures / "YT_VIDEO_demo.json").write_text(json.dumps(payload), encoding="utf-8")
        acquired = run(
            str(ROOT / "scripts/acquire_corpus.py"), "--registry", str(registry),
            "--manifest", str(manifest), "--cache-root", str(cache),
            "--fixture-dir", str(fixtures), "--source-id", "YT_VIDEO_demo",
        )
        if acquired.returncode:
            print(acquired.stdout, acquired.stderr, file=sys.stderr)
            return 1

        record = json.loads(manifest.read_text(encoding="utf-8").strip())
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        assert record["status"] == "PAYLOAD_CAPTURED"
        assert record["sha256"] == hashlib.sha256(normalized).hexdigest()
        assert record["semantic_extraction_performed"] is False
        assert record["first_party_contacted"] is False
        assert record["closure_credit"] == "ZERO_FIXTURE_ONLY"

        validated = run(
            str(ROOT / "scripts/check_acquisition_manifest.py"),
            "--registry", str(registry), "--manifest", str(manifest),
        )
        if validated.returncode:
            print(validated.stdout, validated.stderr, file=sys.stderr)
            return 1

        planned = run(str(ROOT / "scripts/acquire_corpus.py"), "--registry", str(registry), "--plan")
        assert planned.returncode == 0
        assert json.loads(planned.stdout)["selected"] == 1

    print("Acquisition tooling smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
