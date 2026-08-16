#!/usr/bin/env python3
"""Probe legitimate unauthenticated public YouTube routes for bounded canaries.

This is transport recovery only. It never treats titles, descriptions, oEmbed
metadata, or search snippets as semantic evidence. Caption payload is considered
eligible for a later bounded semantic pass only when its URL is exposed directly
inside a successful public YouTube page response and the caption host is official.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CHALLENGE_MARKERS = (
    "sign in to confirm you're not a bot",
    "sign in to confirm you’re not a bot",
    "unusual traffic",
    "captcha",
    "our systems have detected unusual traffic",
)
OFFICIAL_CAPTION_HOSTS = {"www.youtube.com", "youtube.com"}


def read_targets(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"SOURCE_ID", "VIDEO_ID", "URL"}
    for row in rows:
        if not required.issubset(row) or not all(row.get(key) for key in required):
            raise ValueError("invalid canary row")
    return rows


def request(url: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ArjoTradingEngineResearch/1.0 (+public-first-party-access-probe)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            text = body.decode("utf-8", errors="replace")
            challenge = next((marker for marker in CHALLENGE_MARKERS if marker in text.casefold()), None)
            return {
                "url": url,
                "final_url": response.geturl(),
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "challenge_marker": challenge,
                "body_text": text,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read()
        text = body.decode("utf-8", errors="replace")
        challenge = next((marker for marker in CHALLENGE_MARKERS if marker in text.casefold()), None)
        return {
            "url": url,
            "final_url": exc.geturl(),
            "http_status": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "challenge_marker": challenge,
            "body_text": text,
            "error": f"HTTPError:{exc.code}",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "final_url": url,
            "http_status": None,
            "content_type": "",
            "bytes": 0,
            "sha256": None,
            "challenge_marker": None,
            "body_text": "",
            "error": f"{type(exc).__name__}:{exc}",
        }


def public_route_state(result: dict[str, Any]) -> str:
    if result["challenge_marker"]:
        return "ENVIRONMENT_ACCESS_FAILURE"
    status = result["http_status"]
    if status is None:
        return "ENVIRONMENT_ACCESS_FAILURE"
    if status in {401, 403, 429}:
        return "ENVIRONMENT_ACCESS_FAILURE"
    if 200 <= status < 300 and result["bytes"] > 0:
        return "PUBLIC_PAYLOAD_CAPTURED"
    if status in {404, 410}:
        return "SOURCE_UNAVAILABLE_AFTER_CONTACT"
    return "SOURCE_CONTACTED_NO_PAYLOAD"


def extract_caption_tracks(page_text: str) -> list[dict[str, Any]]:
    marker = '"captionTracks":'
    tracks: list[dict[str, Any]] = []
    start = 0
    decoder = json.JSONDecoder()
    while True:
        index = page_text.find(marker, start)
        if index < 0:
            break
        payload_start = index + len(marker)
        try:
            value, consumed = decoder.raw_decode(page_text[payload_start:])
        except json.JSONDecodeError:
            start = payload_start
            continue
        if isinstance(value, list):
            for track in value:
                if not isinstance(track, dict):
                    continue
                base_url = track.get("baseUrl")
                if not isinstance(base_url, str):
                    continue
                host = urllib.parse.urlparse(base_url).hostname or ""
                if host in OFFICIAL_CAPTION_HOSTS:
                    tracks.append(
                        {
                            "base_url": base_url,
                            "language_code": str(track.get("languageCode", "")),
                            "kind": str(track.get("kind", "")),
                        }
                    )
        start = payload_start + consumed
    unique: dict[str, dict[str, Any]] = {}
    for track in tracks:
        unique.setdefault(track["base_url"], track)
    return list(unique.values())


def choose_track(tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for track in tracks:
        if track["language_code"].lower().startswith("en") and track["kind"] != "asr":
            return track
    for track in tracks:
        if track["language_code"].lower().startswith("en"):
            return track
    return tracks[0] if tracks else None


def redacted_route(result: dict[str, Any], route: str) -> dict[str, Any]:
    return {
        "route": route,
        "state": public_route_state(result),
        "url": result["url"],
        "final_url": result["final_url"],
        "http_status": result["http_status"],
        "content_type": result["content_type"],
        "bytes": result["bytes"],
        "sha256": result["sha256"],
        "challenge_marker": result["challenge_marker"],
        "error": result["error"],
        "semantic_credit": "ZERO_TRANSPORT_PROBE",
    }


def probe_target(target: dict[str, str], timeout: int, caption_dir: Path) -> dict[str, Any]:
    video_id = target["VIDEO_ID"]
    watch_url = f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"
    embed_url = f"https://www.youtube.com/embed/{urllib.parse.quote(video_id)}"
    oembed_url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": watch_url, "format": "json"}
    )

    watch = request(watch_url, timeout)
    embed = request(embed_url, timeout)
    oembed = request(oembed_url, timeout)

    tracks: list[dict[str, Any]] = []
    for page in (watch, embed):
        if public_route_state(page) == "PUBLIC_PAYLOAD_CAPTURED":
            tracks.extend(extract_caption_tracks(page["body_text"]))
    tracks = list({track["base_url"]: track for track in tracks}.values())
    selected = choose_track(tracks)

    caption_summary: dict[str, Any] | None = None
    if selected is not None:
        caption = request(selected["base_url"], timeout)
        state = public_route_state(caption)
        caption_summary = redacted_route(caption, "caption_from_public_page")
        caption_summary.update(
            {
                "language_code": selected["language_code"],
                "kind": selected["kind"],
                "discovered_from_public_page": True,
                "official_host": True,
                "semantic_credit": "ELIGIBLE_DIRECT_FIRST_PARTY_PAYLOAD" if state == "PUBLIC_PAYLOAD_CAPTURED" else "ZERO_TRANSPORT_FAILURE",
            }
        )
        if state == "PUBLIC_PAYLOAD_CAPTURED":
            caption_dir.mkdir(parents=True, exist_ok=True)
            suffix = ".xml" if "xml" in caption["content_type"].lower() else ".txt"
            path = caption_dir / f"{target['SOURCE_ID']}{suffix}"
            path.write_text(caption["body_text"], encoding="utf-8")
            caption_summary["artifact_file"] = path.name

    semantic_payload_captured = bool(
        caption_summary and caption_summary["state"] == "PUBLIC_PAYLOAD_CAPTURED"
    )
    return {
        "source_id": target["SOURCE_ID"],
        "video_id": video_id,
        "predicate_context": target.get("PREDICATE_CONTEXT", ""),
        "routes": [
            redacted_route(watch, "watch"),
            redacted_route(embed, "embed"),
            redacted_route(oembed, "oembed_metadata"),
        ],
        "caption_tracks_exposed": len(tracks),
        "caption": caption_summary,
        "direct_semantic_payload_captured": semantic_payload_captured,
        "titles_descriptions_metadata_semantic_credit": "ZERO",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default="research/recovery/issue_87_youtube_canaries.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--caption-dir", required=True)
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()

    targets = read_targets(Path(args.targets))
    results = [probe_target(target, args.timeout, Path(args.caption_dir)) for target in targets]
    report = {
        "schema_version": 1,
        "issue": 87,
        "probe_policy": "PUBLIC_UNAUTHENTICATED_OFFICIAL_ROUTES_ONLY",
        "target_count": len(results),
        "semantic_payloads_captured": sum(1 for result in results if result["direct_semantic_payload_captured"]),
        "results": results,
        "cookies_used": False,
        "authentication_used": False,
        "captcha_bypass_used": False,
        "stealth_or_proxy_rotation_used": False,
        "private_api_used": False,
        "third_party_transcript_used": False,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "targets": len(results),
                "semantic_payloads_captured": report["semantic_payloads_captured"],
                "route_states": {
                    state: sum(
                        1
                        for result in results
                        for route in result["routes"]
                        if (state := route["state"])
                    )
                    for state in sorted(
                        {route["state"] for result in results for route in result["routes"]}
                    )
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
