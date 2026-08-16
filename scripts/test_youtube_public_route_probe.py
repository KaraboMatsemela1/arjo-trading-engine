#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_youtube_public_routes import choose_track, extract_caption_tracks, public_route_state


def result(status: int | None, body: str = "", challenge: str | None = None) -> dict:
    return {
        "http_status": status,
        "bytes": len(body.encode()),
        "challenge_marker": challenge,
    }


def main() -> int:
    assert public_route_state(result(200, "ok")) == "PUBLIC_PAYLOAD_CAPTURED"
    assert public_route_state(result(403, "blocked")) == "ENVIRONMENT_ACCESS_FAILURE"
    assert public_route_state(result(200, "challenge", "captcha")) == "ENVIRONMENT_ACCESS_FAILURE"
    assert public_route_state(result(404, "missing")) == "SOURCE_UNAVAILABLE_AFTER_CONTACT"
    assert public_route_state(result(None)) == "ENVIRONMENT_ACCESS_FAILURE"

    tracks = [
        {
            "baseUrl": "https://www.youtube.com/api/timedtext?v=abc&lang=en",
            "languageCode": "en",
            "kind": "asr",
        },
        {
            "baseUrl": "https://www.youtube.com/api/timedtext?v=abc&lang=en-GB",
            "languageCode": "en-GB",
        },
        {
            "baseUrl": "https://third-party.example/transcript/abc",
            "languageCode": "en",
        },
    ]
    page = "prefix" + '"captionTracks":' + json.dumps(tracks, separators=(",", ":")) + "suffix"
    extracted = extract_caption_tracks(page)
    assert len(extracted) == 2, extracted
    assert all("youtube.com" in item["base_url"] for item in extracted)
    selected = choose_track(extracted)
    assert selected is not None
    assert selected["language_code"] == "en-GB", selected

    print("YouTube public route probe regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
