#!/usr/bin/env python3
"""Acquire outcome-blind backward-OOS M15 structure from OANDA.

Requests MBA candles for provenance/execution-price availability, but writes only
MID M15 semantic bars plus deterministic UTC H1/H4 aggregates. No strategy
outcome evaluator is imported or called here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
EXPECTED_CONTRACT_SHA = "e7169fa7b3d76ac6856bc64f78debf52af5330642403bd0a6adb6999ebb4de7f"
EXPECTED_PROTOCOL_SHA = "3bbed5663762a5d484935de8383d02b4aa3d320e0d4ef02af9cf5469e3eddefe"
EXPECTED_PROFILE_SHA = "87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6"
MAX_CANDLES = 5000


class BackwardOosDataError(RuntimeError):
    pass


def canon(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackwardOosDataError(f"invalid timestamp: {value}") from exc
    if dt.utcoffset() is None:
        raise BackwardOosDataError("timestamp must be timezone aware")
    return dt.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        x = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BackwardOosDataError(f"invalid decimal {label}") from exc
    if not x.is_finite():
        raise BackwardOosDataError(f"non-finite decimal {label}")
    return x


def load_contract(path: Path) -> dict:
    c = json.loads(path.read_text(encoding="utf-8"))
    if canon(c) != EXPECTED_CONTRACT_SHA:
        raise BackwardOosDataError("backward-OOS request contract SHA drift")
    expected = {
        "provider": "OANDA_V20", "venue": "OANDA_FXTRADE", "environment": "practice",
        "base_url": "https://api-fxpractice.oanda.com", "instrument": "NAS100_USD",
        "price_component": "MBA", "semantic_price_component": "M", "source_granularity": "M15",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA, "profile_sha256": EXPECTED_PROFILE_SHA,
        "mutation_endpoints_authorized": False, "post_entry_outcome_evaluation_authorized": False,
    }
    for key, value in expected.items():
        if c.get(key) != value:
            raise BackwardOosDataError(f"unexpected contract {key}")
    start, end = parse_utc(c["start"]), parse_utc(c["end_exclusive"])
    if start != datetime(2010, 1, 1, tzinfo=UTC) or end != datetime(2024, 1, 1, tzinfo=UTC) or start >= end:
        raise BackwardOosDataError("backward-OOS chronology changed")
    n = int(c.get("page_candles", 0))
    if not 1 <= n <= MAX_CANDLES:
        raise BackwardOosDataError("invalid page_candles")
    return c


def windows(start: datetime, end: datetime, page_candles: int) -> list[tuple[datetime, datetime]]:
    step = timedelta(minutes=15 * page_candles)
    out = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + step, end)
        out.append((cursor, nxt)); cursor = nxt
    return out


def request_payload(*, c: dict, account: str, token: str, start: datetime, end: datetime, retries: int = 4) -> tuple[bytes, str]:
    params = {
        "price": "MBA", "granularity": "M15",
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": end.isoformat().replace("+00:00", "Z"),
        "smooth": "false", "includeFirst": "true",
    }
    real_path = f"/v3/accounts/{account}/instruments/{c['instrument']}/candles"
    redacted = f"/v3/accounts/{{ACCOUNT}}/instruments/{c['instrument']}/candles"
    query = urlencode(params); url = f"{c['base_url']}{real_path}?{query}"
    req_sha = hashlib.sha256(f"{redacted}?{urlencode(sorted(params.items()))}".encode()).hexdigest()
    for attempt in range(retries):
        req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept-Datetime-Format": "RFC3339"}, method="GET")
        try:
            with urlopen(req, timeout=60) as response:
                return response.read(), req_sha
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise BackwardOosDataError(f"OANDA HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt == retries - 1:
                raise BackwardOosDataError("OANDA request failed") from exc
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def parse_page(payload: bytes, instrument: str) -> list[dict]:
    try:
        doc = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BackwardOosDataError("invalid OANDA JSON") from exc
    if doc.get("instrument") != instrument or doc.get("granularity") != "M15":
        raise BackwardOosDataError("provider identity mismatch")
    candles = doc.get("candles")
    if not isinstance(candles, list):
        raise BackwardOosDataError("candles missing")
    out = []
    prior = None
    for raw in candles:
        if raw.get("complete") is not True:
            continue
        ts = parse_utc(str(raw.get("time")))
        if prior is not None and ts <= prior:
            raise BackwardOosDataError("page order violation")
        prior = ts
        for component in ("mid", "bid", "ask"):
            p = raw.get(component)
            if not isinstance(p, dict):
                raise BackwardOosDataError(f"MBA component missing: {component}")
            o, h, l, cl = (dec(p.get(k), f"{component}.{k}") for k in ("o", "h", "l", "c"))
            if h < max(o, cl) or l > min(o, cl) or h < l:
                raise BackwardOosDataError(f"invalid {component} envelope")
        mid = raw["mid"]
        out.append({
            "ts_start_utc": ts.isoformat().replace("+00:00", "Z"),
            "session_start_local": ts.astimezone(NY).isoformat(),
            "open": str(dec(mid["o"], "mid.o")), "high": str(dec(mid["h"], "mid.h")),
            "low": str(dec(mid["l"], "mid.l")), "close": str(dec(mid["c"], "mid.c")),
            "price_count": int(raw.get("volume", 0)), "minutes": 15,
        })
    return out


def merge_pages(pages: list[list[dict]], start: datetime, end: datetime) -> list[dict]:
    by_ts: dict[str, dict] = {}
    for page in pages:
        for row in page:
            ts = parse_utc(row["ts_start_utc"])
            if not start <= ts < end:
                continue
            old = by_ts.get(row["ts_start_utc"])
            if old is not None and old != row:
                raise BackwardOosDataError(f"conflicting duplicate {row['ts_start_utc']}")
            by_ts[row["ts_start_utc"]] = row
    rows = [by_ts[k] for k in sorted(by_ts)]
    if not rows:
        raise BackwardOosDataError("provider returned no M15 data in candidate interval")
    return rows


def aggregate(rows15: list[dict], minutes: int) -> tuple[list[dict], int]:
    if minutes not in {60, 240}:
        raise BackwardOosDataError("unsupported aggregate interval")
    groups: dict[datetime, list[dict]] = {}
    for row in rows15:
        ts = parse_utc(row["ts_start_utc"])
        epoch_min = int(ts.timestamp() // 60); bucket_min = epoch_min - epoch_min % minutes
        start = datetime.fromtimestamp(bucket_min * 60, tz=UTC)
        groups.setdefault(start, []).append(row)
    expected_count = minutes // 15; out = []; omitted = 0
    for start in sorted(groups):
        bucket = sorted(groups[start], key=lambda r: r["ts_start_utc"])
        expected = [start + timedelta(minutes=15*i) for i in range(expected_count)]
        actual = [parse_utc(r["ts_start_utc"]) for r in bucket]
        if actual != expected:
            omitted += 1; continue
        out.append({
            "ts_start_utc": start.isoformat().replace("+00:00", "Z"),
            "session_start_local": start.astimezone(NY).isoformat(),
            "open": bucket[0]["open"], "high": str(max(dec(r["high"], "high") for r in bucket)),
            "low": str(min(dec(r["low"], "low") for r in bucket)), "close": bucket[-1]["close"],
            "price_count": sum(int(r["price_count"]) for r in bucket), "minutes": minutes,
        })
    return out, omitted


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def acquire(contract_path: Path, output_dir: Path, *, delay: float = 0.03) -> dict:
    c = load_contract(contract_path); start, end = parse_utc(c["start"]), parse_utc(c["end_exclusive"])
    account, token = os.getenv(c["account_id_env"], ""), os.getenv(c["api_token_env"], "")
    if not account or not token:
        raise BackwardOosDataError("required OANDA repository secrets missing")
    output_dir.mkdir(parents=True, exist_ok=True); raw_dir = output_dir / "raw-pages"; raw_dir.mkdir(exist_ok=True)
    parsed = []; meta = []
    for idx, (pstart, pend) in enumerate(windows(start, end, int(c["page_candles"]))):
        payload, req_sha = request_payload(c=c, account=account, token=token, start=pstart, end=pend)
        raw_sha = hashlib.sha256(payload).hexdigest(); (raw_dir / f"page-{idx:04d}.json").write_bytes(payload)
        page = parse_page(payload, c["instrument"]); parsed.append(page)
        meta.append({"index": idx, "start": pstart.isoformat().replace("+00:00", "Z"), "end": pend.isoformat().replace("+00:00", "Z"), "request_sha256": req_sha, "raw_response_sha256": raw_sha, "raw_bytes": len(payload), "complete_m15_rows": len(page)})
        if delay and idx + 1 < len(windows(start, end, int(c["page_candles"]))): time.sleep(delay)
    rows15 = merge_pages(parsed, start, end); write_jsonl(output_dir / "NAS100_USD.15m.jsonl", rows15)
    derived = {}
    for mins in (60, 240):
        rows, omitted = aggregate(rows15, mins); path = output_dir / f"NAS100_USD.{mins}m.jsonl"; write_jsonl(path, rows)
        derived[str(mins)] = {"rows": len(rows), "omitted_incomplete_buckets": omitted, "sha256": file_sha(path)}
    digest = hashlib.sha256()
    for p in meta:
        digest.update(p["request_sha256"].encode()); digest.update(p["raw_response_sha256"].encode())
    manifest = {
        "schema_version": 1, "status": "PROFITABILITY_BACKWARD_OOS_STRUCTURE_READY",
        "provider": c["provider"], "venue": c["venue"], "environment": c["environment"], "instrument": c["instrument"],
        "instrument_identity": c["instrument_identity"], "requested_price_components": "MBA", "semantic_price_component": "MID",
        "source_granularity": "M15", "request_contract_sha256": EXPECTED_CONTRACT_SHA, "protocol_sha256": EXPECTED_PROTOCOL_SHA,
        "profile_sha256": EXPECTED_PROFILE_SHA, "requested_start": c["start"], "requested_end_exclusive": c["end_exclusive"],
        "provider_first_complete_bar": rows15[0]["ts_start_utc"], "provider_last_complete_bar": rows15[-1]["ts_start_utc"],
        "state_at_provider_first_bar": "EMPTY", "m15_rows": len(rows15), "m15_sha256": file_sha(output_dir / "NAS100_USD.15m.jsonl"),
        "derived": derived, "raw_page_count": len(meta), "raw_pages": meta, "retrieval_sha256": digest.hexdigest(),
        "post_entry_outcomes_evaluated": False, "m1_outcome_data_requested": False, "mutation_endpoints_used": False,
        "paper_execution_authorized": False, "live_execution_authorized": False, "broker_mutation_authorized": False,
    }
    unsigned = dict(manifest); manifest["manifest_sha256"] = canon(unsigned)
    (output_dir / "NAS100_USD.manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--contract", default="research/profitability/nas100_oanda_backward_oos_request_contract.json"); p.add_argument("--output-dir", required=True); p.add_argument("--delay", type=float, default=0.03); a = p.parse_args()
    try:
        m = acquire(Path(a.contract), Path(a.output_dir), delay=a.delay)
    except Exception as exc:
        print(f"backward OOS structure acquisition failed: {exc}", file=sys.stderr); return 1
    print(json.dumps({k:m[k] for k in ("status","provider_first_complete_bar","provider_last_complete_bar","m15_rows","retrieval_sha256","post_entry_outcomes_evaluated")}, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
