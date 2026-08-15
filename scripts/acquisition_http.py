#!/usr/bin/env python3
"""Public HTTP acquisition adapter."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from acquisition_manifest import add_artifacts, base_record, store_artifact

USER_AGENT = "arjo-trading-engine-acquisition/1.0 (+public research provenance)"


def _classify(exc: urllib.error.HTTPError) -> str:
    if exc.code in {404, 410}:
        return "SOURCE_REMOVED"
    if exc.code in {401, 403, 407, 429}:
        return "ENVIRONMENT_ACCESS_FAILURE"
    return "SOURCE_UNAVAILABLE_AFTER_CONTACT"


def acquire_http(source: dict[str, str], cache_root: Path, timeout: int) -> dict[str, Any]:
    record = base_record(source, "urllib")
    request = urllib.request.Request(
        source["URL"],
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,text/plain,*/*;q=0.5"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            record["http_status"] = getattr(response, "status", 200)
            payload = response.read()
            content_type = response.headers.get("Content-Type", "application/octet-stream")
    except urllib.error.HTTPError as exc:
        record.update(
            status=_classify(exc),
            http_status=exc.code,
            error_class=type(exc).__name__,
            error_detail=f"HTTP {exc.code}",
        )
        return record
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        record.update(
            status="ENVIRONMENT_ACCESS_FAILURE",
            error_class=type(exc).__name__,
            error_detail=str(exc),
        )
        return record

    if not payload:
        return record
    artifact = store_artifact(cache_root, payload, "PUBLIC_PAGE", content_type, ".html")
    return add_artifacts(record, [artifact])
