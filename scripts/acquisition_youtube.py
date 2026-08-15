#!/usr/bin/env python3
"""YouTube acquisition adapter using replayable yt-dlp calls."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from acquisition_manifest import add_artifacts, base_record, store_artifact


def _status_from_error(stderr: str) -> str:
    text = stderr.lower()
    if any(token in text for token in ("private video", "video unavailable", "removed by", "has been removed")):
        return "SOURCE_REMOVED"
    if any(token in text for token in ("sign in", "http error 403", "http error 429", "captcha")):
        return "ENVIRONMENT_ACCESS_FAILURE"
    return "SOURCE_UNAVAILABLE_AFTER_CONTACT"


def _capture_files(workdir: Path, cache_root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(workdir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            kind, content_type = "YOUTUBE_METADATA", "application/json"
        elif suffix == ".description":
            kind, content_type = "YOUTUBE_DESCRIPTION", "text/plain"
        elif suffix in {".vtt", ".srt", ".ttml"}:
            kind, content_type = "YOUTUBE_CAPTION", "text/vtt"
        else:
            continue
        artifacts.append(store_artifact(cache_root, path.read_bytes(), kind, content_type, suffix))
    return artifacts


def acquire_youtube(source: dict[str, str], cache_root: Path, timeout: int, fixture_dir: Path | None = None) -> dict[str, Any]:
    record = base_record(source, "yt-dlp")
    if fixture_dir is not None:
        fixture = fixture_dir / f"{source['SOURCE_ID']}.json"
        record.update(first_party_contacted=False, closure_credit="ZERO_FIXTURE_ONLY", transport="fixture")
        if not fixture.exists():
            record["notes"] = "Fixture absent; no network contact performed"
            return record
        payload = json.dumps(json.loads(fixture.read_text(encoding="utf-8")), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        artifact = store_artifact(cache_root, payload, "YOUTUBE_METADATA", "application/json", ".json")
        return add_artifacts(record, [artifact])

    executable = shutil.which("yt-dlp")
    if not executable:
        record.update(status="ENVIRONMENT_ACCESS_FAILURE", error_class="FileNotFoundError", error_detail="yt-dlp executable not found")
        return record

    with tempfile.TemporaryDirectory(prefix="arjo-acq-") as temp:
        workdir = Path(temp)
        output = str(workdir / "%(id)s.%(ext)s")
        command = [
            executable,
            "--skip-download",
            "--write-info-json",
            "--write-description",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "all,-live_chat",
            "--sub-format",
            "vtt",
            "--output",
            output,
            "--no-warnings",
            source["URL"],
        ]
        try:
            completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            record.update(status="ENVIRONMENT_ACCESS_FAILURE", error_class="TimeoutExpired", error_detail="yt-dlp timed out")
            return record
        except OSError as exc:
            record.update(status="ENVIRONMENT_ACCESS_FAILURE", error_class=type(exc).__name__, error_detail=str(exc))
            return record

        if completed.returncode != 0:
            record.update(status=_status_from_error(completed.stderr), error_class="YTDLP_ERROR", error_detail=completed.stderr.strip()[-2000:])
            return record

        artifacts = _capture_files(workdir, cache_root)
        if not artifacts:
            return record
        record["notes"] = "Public metadata/description/caption artifacts captured when exposed by the source"
        return add_artifacts(record, artifacts)
