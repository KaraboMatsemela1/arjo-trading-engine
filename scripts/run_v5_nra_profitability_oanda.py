#!/usr/bin/env python3
"""Execute the frozen V5 No-Resistance AoO historical BID/ASK measurement.

The runner reacquires H4/H1 structure and proves the exact sealed V5 trigger
set before the first M1 provider response. After that boundary, no V5 rule or
economic parameter is mutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import check_v5_nra_profitability_lock as lock_check
import check_v5_no_resistance_aoo_protocol as protocol_check
import v5_nra_profitability_engine as engine
import v5_nra_structure as structure
from v5_nra_reference_fast import compare_reconstructions_fast
from v5_nra_triggers import canonical_sha

BASE_URL = "https://api-fxpractice.oanda.com"
INSTRUMENT = "NAS100_USD"
ORIGIN = datetime(2010, 1, 1, tzinfo=UTC)
OOS_END = datetime(2024, 1, 1, tzinfo=UTC)
CHUNK = timedelta(days=3)
EXPECTED_PROTOCOL_SHA = protocol_check.EXPECTED_PROTOCOL_SHA
EXPECTED_TRANSPORT_SHA = protocol_check.EXPECTED_TRANSPORT_SHA
EXPECTED_LOCK_SHA = lock_check.EXPECTED_LOCK_SHA
EXPECTED_TRIGGER_SHA = lock_check.EXPECTED_TRIGGER_SHA
EXPECTED_READINESS_SHA = lock_check.EXPECTED_READINESS_SHA
EXPECTED_TRIGGER_COUNT = 4737
MARKER = Path("research/profitability/V5_NRA_PROFITABILITY_EXECUTE_LOCK.json")


class V5ProfitabilityError(RuntimeError):
    pass


def z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise V5ProfitabilityError("naive timestamp")
    return parsed.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V5ProfitabilityError(f"invalid decimal {label}") from exc
    if not number.is_finite():
        raise V5ProfitabilityError(f"nonfinite decimal {label}")
    return number


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_marker(path: Path = MARKER) -> dict:
    if not path.exists():
        raise V5ProfitabilityError("V5 research M1 execution marker missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "AUTHORIZED_V5_RESEARCH_M1_READ_AFTER_TRIGGER_SEAL",
        "issue": 255,
        "protocol_sha256": EXPECTED_PROTOCOL_SHA,
        "structure_transport_sha256": EXPECTED_TRANSPORT_SHA,
        "profitability_lock_sha256": EXPECTED_LOCK_SHA,
        "trigger_set_sha256": EXPECTED_TRIGGER_SHA,
        "trigger_readiness_sha256": EXPECTED_READINESS_SHA,
        "trigger_count": EXPECTED_TRIGGER_COUNT,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    if payload != expected:
        raise V5ProfitabilityError("V5 execution marker boundary changed")
    return payload


class M1Cache:
    def __init__(self, root: Path, account: str, token: str) -> None:
        if not account or not token:
            raise V5ProfitabilityError("OANDA credentials missing")
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.account = account
        self.token = token
        self.meta: dict[int, dict] = {}
        self.first_response_accessed = False

    def index(self, value: datetime) -> int:
        return max(0, int((value - ORIGIN).total_seconds() // CHUNK.total_seconds()))

    def bounds(self, index: int) -> tuple[datetime, datetime]:
        start = ORIGIN + index * CHUNK
        return start, min(start + CHUNK, OOS_END)

    def path(self, index: int) -> Path:
        return self.root / f"m1-{index:05d}.jsonl"

    def request(self, start: datetime, end: datetime) -> tuple[bytes, str]:
        params = {
            "price": "BA",
            "granularity": "M1",
            "from": z(start),
            "to": z(end),
            "smooth": "false",
            "includeFirst": "true",
        }
        query = urlencode(params)
        real_path = f"/v3/accounts/{self.account}/instruments/{INSTRUMENT}/candles"
        redacted_path = f"/v3/accounts/{{ACCOUNT}}/instruments/{INSTRUMENT}/candles"
        request_sha = hashlib.sha256(
            f"{redacted_path}?{urlencode(sorted(params.items()))}".encode()
        ).hexdigest()
        url = f"{BASE_URL}{real_path}?{query}"
        for attempt in range(5):
            request = Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept-Datetime-Format": "RFC3339",
                    "User-Agent": "arjo-v5-nra-profitability",
                },
                method="GET",
            )
            try:
                with urlopen(request, timeout=60) as response:
                    return response.read(), request_sha
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    raise V5ProfitabilityError(
                        f"OANDA M1 HTTP {exc.code}: {detail}"
                    ) from exc
            except URLError as exc:
                if attempt == 4:
                    raise V5ProfitabilityError("OANDA M1 request failed") from exc
            time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def parse_payload(self, payload: bytes) -> list[dict]:
        document = json.loads(payload)
        if document.get("instrument") != INSTRUMENT:
            raise V5ProfitabilityError("M1 provider instrument mismatch")
        if document.get("granularity") != "M1":
            raise V5ProfitabilityError("M1 provider granularity mismatch")
        rows: list[dict] = []
        prior: datetime | None = None
        for raw in document.get("candles", []):
            if raw.get("complete") is not True:
                continue
            timestamp = parse(str(raw.get("time")))
            if not ORIGIN <= timestamp < OOS_END:
                raise V5ProfitabilityError("M1 row outside frozen history")
            if prior is not None and timestamp <= prior:
                raise V5ProfitabilityError("M1 provider order violation")
            prior = timestamp
            row: dict = {"ts_start_utc": z(timestamp)}
            for component in ("bid", "ask"):
                price = raw.get(component)
                if not isinstance(price, dict):
                    raise V5ProfitabilityError(f"missing {component} component")
                open_, high, low, close = (
                    dec(price.get(field), f"{component}.{field}")
                    for field in ("o", "h", "l", "c")
                )
                if high < max(open_, close) or low > min(open_, close) or high < low:
                    raise V5ProfitabilityError(f"invalid {component} envelope")
                row[component] = {
                    "o": str(open_),
                    "h": str(high),
                    "l": str(low),
                    "c": str(close),
                }
            rows.append(row)
        return rows

    def chunk(self, index: int) -> list[dict]:
        start, end = self.bounds(index)
        if start >= OOS_END:
            return []
        path = self.path(index)
        if not path.exists():
            payload, request_sha = self.request(start, end)
            self.first_response_accessed = True
            raw_sha = hashlib.sha256(payload).hexdigest()
            rows = self.parse_payload(payload)
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(
                        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    )
            self.meta[index] = {
                "chunk_index": index,
                "from": z(start),
                "to_exclusive": z(end),
                "request_sha256": request_sha,
                "raw_response_sha256": raw_sha,
                "raw_bytes": len(payload),
                "complete_m1_rows": len(rows),
                "parsed_sha256": file_sha(path),
            }
        else:
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return rows

    def get_bars(self, start: datetime, count: int) -> list[dict]:
        if start >= OOS_END:
            return []
        index = self.index(start)
        by_time: dict[str, dict] = {}
        while len(by_time) < count:
            chunk_start, _ = self.bounds(index)
            if chunk_start >= OOS_END:
                break
            for row in self.chunk(index):
                timestamp = parse(row["ts_start_utc"])
                if timestamp < start:
                    continue
                existing = by_time.get(row["ts_start_utc"])
                if existing is not None and existing != row:
                    raise V5ProfitabilityError(
                        f"conflicting duplicate M1 {row['ts_start_utc']}"
                    )
                by_time[row["ts_start_utc"]] = row
            index += 1
        return [by_time[key] for key in sorted(by_time)][:count]

    def provenance(self) -> dict:
        chunks = [self.meta[key] for key in sorted(self.meta)]
        output = {
            "schema_version": 1,
            "provider": "OANDA_V20",
            "environment": "practice",
            "instrument": INSTRUMENT,
            "granularity": "M1",
            "price_components": "BA",
            "chunk_calendar_days": 3,
            "origin": z(ORIGIN),
            "end_exclusive": z(OOS_END),
            "chunks_requested": len(chunks),
            "chunks": chunks,
            "first_m1_response_accessed": self.first_response_accessed,
            "credentials_exposed": False,
            "mutation_endpoints_used": False,
        }
        output["provenance_sha256"] = engine.canon(output)
        return output


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def reconstruct_before_m1() -> tuple[list[dict], dict, dict]:
    protocol_check.verify()
    lock_check.verify()
    acquired = structure.acquire_structure()
    triggers, comparison = compare_reconstructions_fast(acquired["h4"], acquired["h1"])
    trigger_sha = canonical_sha(triggers)
    if comparison["exact_match"] is not True:
        raise V5ProfitabilityError("pre-M1 independent trigger reconstruction failed")
    if trigger_sha != EXPECTED_TRIGGER_SHA:
        raise V5ProfitabilityError(
            f"pre-M1 trigger SHA mismatch {trigger_sha} != {EXPECTED_TRIGGER_SHA}"
        )
    if len(triggers) != EXPECTED_TRIGGER_COUNT:
        raise V5ProfitabilityError("pre-M1 trigger cardinality changed")
    manifest = acquired["manifest"]
    return triggers, comparison, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        marker = verify_marker()
        triggers, comparison, structure_manifest = reconstruct_before_m1()
        # The M1 cache is intentionally instantiated only after exact trigger reconstruction.
        cache = M1Cache(
            output_dir / "m1-cache",
            os.getenv("OANDA_ACCOUNT_ID", "").strip(),
            os.getenv("OANDA_API_TOKEN", "").strip(),
        )
        base = engine.evaluate_portfolio(
            triggers,
            cache.get_bars,
            scenario="BASE",
            slip_points=Decimal("0.5"),
            financing_r_per_1440=Decimal("0.005"),
        )
        stress = engine.evaluate_portfolio(
            triggers,
            cache.get_bars,
            scenario="STRESS",
            slip_points=Decimal("1.0"),
            financing_r_per_1440=Decimal("0.01"),
        )
        base_metrics = engine.metrics(base)
        stress_metrics = engine.metrics(stress)
        classification = engine.classify(
            base_metrics,
            stress_metrics,
            independent_trigger_exact=comparison["exact_match"],
        )
        provenance = cache.provenance()
        write_jsonl(output_dir / "base-trade-ledger.jsonl", base["ledger"])
        write_jsonl(output_dir / "stress-trade-ledger.jsonl", stress["ledger"])
        (output_dir / "provider-provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = {
            "schema_version": 1,
            "status": "V5_NO_RESISTANCE_AOO_PROFITABILITY_RESULT_READY",
            "classification": classification,
            "historical_edge_established": classification
            == "V5_HISTORICAL_EDGE_ESTABLISHED",
            "validated_profitable_edge": False,
            "validated_profitable_edge_reason": "BACKWARD_HISTORY_REQUIRES_SEPARATE_PROTECTED_CONFIRMATION",
            "candidate_id": "ARJO_V5_NQ_NO_RESISTANCE_AOO_H4_SWING_HIGH_LONG",
            "protocol_sha256": EXPECTED_PROTOCOL_SHA,
            "structure_transport_sha256": EXPECTED_TRANSPORT_SHA,
            "profitability_execution_lock_sha256": EXPECTED_LOCK_SHA,
            "trigger_set_sha256": EXPECTED_TRIGGER_SHA,
            "trigger_readiness_sha256": EXPECTED_READINESS_SHA,
            "trigger_count": len(triggers),
            "distinct_knowledge_timestamps": len(
                {row["knowledge_time_utc"] for row in triggers}
            ),
            "pre_m1_independent_reconstruction_exact": comparison["exact_match"],
            "pre_m1_primary_trigger_sha256": comparison["primary_trigger_sha256"],
            "pre_m1_reference_trigger_sha256": comparison["reference_trigger_sha256"],
            "pre_m1_structure_manifest_sha256": structure_manifest["manifest_sha256"],
            "execution_marker": marker,
            "provider_provenance_sha256": provenance["provenance_sha256"],
            "base_metrics": base_metrics,
            "stress_metrics": stress_metrics,
            "base_ledger_sha256": base["ledger_sha256"],
            "stress_ledger_sha256": stress["ledger_sha256"],
            "first_m1_response_accessed": cache.first_response_accessed,
            "parameter_changes_after_first_m1_response": False,
            "post_result_tuning_performed": False,
            "historical_window_pristine_project_holdout": False,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        result["result_sha256"] = engine.canon(result)
        (output_dir / "profitability-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(output_dir / "m1-cache", ignore_errors=True)
    except Exception as exc:
        print(f"V5 profitability execution failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "classification": classification,
                "historical_edge_established": result["historical_edge_established"],
                "validated_profitable_edge": False,
                "base_resolved": base_metrics["resolved_executed_trades"],
                "base_expectancy_r": base_metrics["net_expectancy_r"],
                "base_profit_factor": base_metrics["profit_factor"],
                "base_bootstrap_ci": base_metrics[
                    "bootstrap_95pct_ci_net_expectancy_r"
                ],
                "stress_resolved": stress_metrics["resolved_executed_trades"],
                "stress_expectancy_r": stress_metrics["net_expectancy_r"],
                "stress_profit_factor": stress_metrics["profit_factor"],
                "result_sha256": result["result_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
