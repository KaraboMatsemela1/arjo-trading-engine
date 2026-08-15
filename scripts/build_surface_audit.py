#!/usr/bin/env python3
"""Build a machine-readable audit of first-party discovery surface coverage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DISCOVERY_DIR = Path("research/discovery")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def report_surface(name: str, root: str, report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {
            "platform": name,
            "root": root,
            "status": "NOT_RUN",
            "item_level_enumeration": False,
            "discovered_count": 0,
            "failures": ["DISCOVERY_REPORT_MISSING"],
        }
    failures = report.get("failures") or []
    discovered = int(report.get("discovered_count", 0))
    return {
        "platform": name,
        "root": root,
        "status": "ENUMERATED_CLEAN" if discovered > 0 and not failures else "ENUMERATED_WITH_GAPS",
        "item_level_enumeration": discovered > 0,
        "discovered_count": discovered,
        "failures": failures,
        "snapshot_sha256": report.get("normalized_snapshot_sha256", ""),
    }


def main() -> int:
    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    youtube = load_json(DISCOVERY_DIR / "new_sources.json")
    telegram = load_json(DISCOVERY_DIR / "telegram_discovery_report.json")
    website = load_json(DISCOVERY_DIR / "website_discovery_report.json")

    surfaces = [
        report_surface("youtube", "https://www.youtube.com/@Arjoio", youtube),
        report_surface("telegram", "https://t.me/ArjoioTrading", telegram),
        report_surface("website", "https://tradingmmt.com/", website),
        {
            "platform": "x",
            "root": "https://x.com/arjoio",
            "status": "ROOT_CONFIRMED_ITEM_ENUMERATION_ACCESS_LIMITED",
            "item_level_enumeration": False,
            "discovered_count": 0,
            "failures": ["UNAUTHENTICATED_ITEM_ENUMERATION_NOT_REPLAYABLY_AVAILABLE"],
            "closure_credit": "ZERO_UNTIL_ITEM_EVIDENCE_ACQUIRED",
        },
        {
            "platform": "instagram",
            "root": "https://www.instagram.com/arjoio/",
            "status": "ROOT_CONFIRMED_ITEM_ENUMERATION_ACCESS_LIMITED",
            "item_level_enumeration": False,
            "discovered_count": 0,
            "failures": ["UNAUTHENTICATED_ITEM_ENUMERATION_NOT_REPLAYABLY_AVAILABLE"],
            "closure_credit": "ZERO_UNTIL_ITEM_EVIDENCE_ACQUIRED",
        },
        {
            "platform": "discord",
            "root": "https://discord.gg/tradingmmt",
            "status": "FIRST_PARTY_LINKED_JOIN_REQUIRED",
            "item_level_enumeration": False,
            "discovered_count": 0,
            "failures": ["PLATFORM_JOIN_OR_AUTH_REQUIRED"],
            "closure_credit": "ZERO_UNTIL_ITEM_EVIDENCE_ACQUIRED",
        },
        {
            "platform": "link_hub",
            "root": "https://zaap.bio/arjo",
            "status": "FIRST_PARTY_LINKED_LOCATOR_ONLY",
            "item_level_enumeration": False,
            "discovered_count": 0,
            "failures": [],
            "closure_credit": "ZERO_LOCATOR_ONLY",
        },
    ]

    audit = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "semantic_closure_performed": False,
        "principle": "Transport/access limitations are not evidence absence.",
        "surfaces": surfaces,
        "source_universe_discovery_complete": all(
            surface["status"] not in {"NOT_RUN"} for surface in surfaces
        ),
        "unresolved_access_limited_surfaces": [
            surface["platform"]
            for surface in surfaces
            if "ACCESS_LIMITED" in surface["status"] or "JOIN_REQUIRED" in surface["status"]
        ],
    }
    output = DISCOVERY_DIR / "platform_surface_audit.json"
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"complete": audit["source_universe_discovery_complete"], "surfaces": len(surfaces)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
