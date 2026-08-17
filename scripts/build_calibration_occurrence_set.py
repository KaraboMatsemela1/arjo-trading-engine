#!/usr/bin/env python3
"""Build a deterministic qualified occurrence set from outcome-blind packets.

No occurrence discovery occurs here. Every input packet must already contain two
independent, agreeing semantic-anchor annotations and must pass the fail-closed
validator in validate_calibration_occurrence.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_calibration_occurrence import OccurrenceValidationError, canonical_sha256, validate_packet


class OccurrenceSetError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(packet_paths: list[Path]) -> dict:
    if not packet_paths:
        raise OccurrenceSetError("at least one qualified occurrence packet is required")

    rows: list[dict] = []
    seen_ids: set[str] = set()
    seen_consensus: set[str] = set()
    for path in sorted(packet_paths, key=lambda p: p.name):
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
            result = validate_packet(packet)
        except (OSError, json.JSONDecodeError, OccurrenceValidationError) as exc:
            raise OccurrenceSetError(f"invalid occurrence packet {path}: {exc}") from exc

        occurrence_id = result.get("occurrence_id")
        if not isinstance(occurrence_id, str) or not occurrence_id:
            raise OccurrenceSetError(f"packet {path} has no occurrence_id")
        if occurrence_id in seen_ids:
            raise OccurrenceSetError(f"duplicate occurrence_id: {occurrence_id}")
        seen_ids.add(occurrence_id)

        consensus = str(result["consensus_anchors_sha256"])
        if consensus in seen_consensus:
            raise OccurrenceSetError(f"duplicate consensus anchor set: {consensus}")
        seen_consensus.add(consensus)

        observations = packet["observations"]
        activation_ts = observations["activation_confirmation"]["ts_start_utc"]
        second_ts = observations["second_sting"]["ts_start_utc"]
        rows.append(
            {
                "occurrence_id": occurrence_id,
                "packet_path": str(path),
                "packet_sha256": file_sha256(path),
                "consensus_anchors_sha256": consensus,
                "activation_ts_utc": activation_ts,
                "second_sting_ts_utc": second_ts,
                "provider": result["provider"],
                "instrument": result["instrument"],
                "outcome_fields_present": False,
                "holdout_accessed": False,
            }
        )

    rows.sort(key=lambda row: (row["activation_ts_utc"], row["occurrence_id"]))
    set_sha = canonical_sha256(rows)
    return {
        "schema_version": 1,
        "status": "CALIBRATION_OCCURRENCES_READY",
        "source": "INDEPENDENT_OUTCOME_BLIND_SEMANTIC_ANCHOR_CONSENSUS",
        "provider": "OANDA_V20",
        "instrument": "NAS100_USD",
        "occurrence_count": len(rows),
        "occurrence_set_sha256": set_sha,
        "outcome_fields_present": False,
        "holdout_accessed": False,
        "performance_comparison_performed": False,
        "occurrences": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packets", nargs="*")
    parser.add_argument("--packet-dir")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = [Path(value) for value in args.packets]
    if args.packet_dir:
        paths.extend(sorted(Path(args.packet_dir).glob("*.json")))
    # Preserve deterministic unique paths without silently ignoring duplicate packets.
    if len({str(path) for path in paths}) != len(paths):
        print("occurrence set build failed: duplicate input path", file=sys.stderr)
        return 1
    try:
        manifest = build(paths)
    except OccurrenceSetError as exc:
        print(f"occurrence set build failed: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "occurrence_count": manifest["occurrence_count"], "occurrence_set_sha256": manifest["occurrence_set_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
