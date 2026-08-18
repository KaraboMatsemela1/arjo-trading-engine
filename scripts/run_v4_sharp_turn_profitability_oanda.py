#!/usr/bin/env python3
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

import oanda_v4_sharp_turn_structure_v2 as structure
import scan_v4_sharp_turn_triggers_v2 as trigger_scan
import v4_sharp_turn_profitability_engine as engine
from check_v4_sharp_turn_trigger_readiness import verify_readiness, verify_reproduction

BASE_URL = "https://api-fxpractice.oanda.com"
INSTRUMENT = "NAS100_USD"
ORIGIN = datetime(2010, 1, 1, tzinfo=UTC)
END = datetime(2024, 1, 1, tzinfo=UTC)
SAFE_REQUEST_END = END - timedelta(microseconds=1)
CHUNK = timedelta(days=3)
PROTOCOL_SHA = "a3cdb1fbe309ec3aab6bee05a80999d8012fabfee06cf2eedba2d28eb387accd"
READINESS_SHA = "6fb99be106ffa98857693211c5e4814f90a1e874b3255168874a0e1a47a6dba3"
TRIGGER_SHA = "1df6eabb176ef85ce203f3eeb7b76007d0114dfb98d1b1ad0f76f703d779847a"
LOCK_SHA = "846e3c106f9f478fe3ef74ad8152431f42bc2d0cac0d314d9a71d6aef8f0ec30"


class V4ProfitabilityError(RuntimeError):
    pass


def zulu(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise V4ProfitabilityError("naive timestamp")
    return result.astimezone(UTC)


def dec(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V4ProfitabilityError(f"invalid decimal {label}") from exc
    if not result.is_finite():
        raise V4ProfitabilityError(f"non-finite decimal {label}")
    return result


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_lock(path: Path) -> dict:
    lock = json.loads(path.read_text())
    unsigned = dict(lock)
    recorded = unsigned.pop("spec_sha256", "")
    if recorded != LOCK_SHA or engine.canon(unsigned) != LOCK_SHA:
        raise V4ProfitabilityError("V4 execution lock SHA drift")
    expected = {
        "status": "FROZEN_BEFORE_FIRST_V4_M1_RESPONSE",
        "parent_protocol_sha256": PROTOCOL_SHA,
        "trigger_readiness_sha256": READINESS_SHA,
        "canonical_trigger_set_sha256": TRIGGER_SHA,
        "canonical_trigger_count": 213,
        "boundary_revision": "V4_STRICT_CANDLE_COVERAGE_END_V2",
        "parameter_changes_after_first_m1_response": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    for key, value in expected.items():
        if lock.get(key) != value:
            raise V4ProfitabilityError(f"V4 execution lock boundary changed: {key}")
    return lock


def verify_marker(path: Path) -> dict:
    if not path.exists():
        raise V4ProfitabilityError("V4 research M1 execution marker missing")
    marker = json.loads(path.read_text())
    expected = {
        "status": "AUTHORIZED_SINGLE_V4_HISTORICAL_M1_READ_AFTER_PREFLIGHT",
        "issue": 247,
        "protocol_sha256": PROTOCOL_SHA,
        "trigger_readiness_sha256": READINESS_SHA,
        "trigger_set_sha256": TRIGGER_SHA,
        "profitability_lock_sha256": LOCK_SHA,
        "boundary_revision": "V4_STRICT_CANDLE_COVERAGE_END_V2",
        "parameter_changes_after_first_m1_response": False,
        "paper_execution_authorized": False,
        "live_execution_authorized": False,
        "broker_mutation_authorized": False,
    }
    for key, value in expected.items():
        if marker.get(key) != value:
            raise V4ProfitabilityError(f"V4 execution marker boundary changed: {key}")
    return marker


class M1Cache:
    def __init__(self, root: Path, account: str, token: str):
        if not account or not token:
            raise V4ProfitabilityError("OANDA repository secrets missing")
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.account = account
        self.token = token
        self.meta: dict[int, dict] = {}
        self.first_response_accessed = False
        self.request_count = 0

    def index(self, value: datetime) -> int:
        return max(0, int((value - ORIGIN).total_seconds() // CHUNK.total_seconds()))

    def bounds(self, index: int) -> tuple[datetime, datetime]:
        start = ORIGIN + index * CHUNK
        return start, min(start + CHUNK, SAFE_REQUEST_END)

    def path(self, index: int) -> Path:
        return self.root / f"m1-{index:05d}.jsonl"

    def _request(self, start: datetime, end: datetime) -> tuple[bytes, str]:
        if not ORIGIN <= start < end < END:
            raise V4ProfitabilityError("M1 request outside strict frozen history")
        params = {
            "price": "BA",
            "granularity": "M1",
            "from": zulu(start),
            "to": zulu(end),
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
                },
                method="GET",
            )
            try:
                with urlopen(request, timeout=60) as response:
                    payload = response.read()
                    self.first_response_accessed = True
                    self.request_count += 1
                    return payload, request_sha
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    raise V4ProfitabilityError(f"OANDA M1 HTTP {exc.code}") from exc
            except URLError as exc:
                if attempt == 4:
                    raise V4ProfitabilityError("OANDA M1 request failed") from exc
            time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def _parse(self, payload: bytes) -> list[dict]:
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise V4ProfitabilityError("invalid OANDA M1 JSON") from exc
        if document.get("instrument") != INSTRUMENT or document.get("granularity") != "M1":
            raise V4ProfitabilityError("M1 provider identity mismatch")
        rows = []
        prior = None
        for raw in document.get("candles", []):
            if raw.get("complete") is not True:
                continue
            timestamp = parse(str(raw.get("time")))
            if not ORIGIN <= timestamp < END:
                raise V4ProfitabilityError("M1 row outside strict frozen history")
            if prior is not None and timestamp <= prior:
                raise V4ProfitabilityError("M1 provider order violation")
            prior = timestamp
            row = {"ts_start_utc": zulu(timestamp)}
            for component in ("bid", "ask"):
                price = raw.get(component)
                if not isinstance(price, dict):
                    raise V4ProfitabilityError(f"missing {component} M1 component")
                o, h, l, c = (dec(price.get(key), f"{component}.{key}") for key in ("o", "h", "l", "c"))
                if h < max(o, c) or l > min(o, c) or h < l:
                    raise V4ProfitabilityError(f"invalid {component} M1 envelope")
                row[component] = {"o": str(o), "h": str(h), "l": str(l), "c": str(c)}
            if dec(row["ask"]["o"], "ask.o") < dec(row["bid"]["o"], "bid.o"):
                raise V4ProfitabilityError("negative opening spread")
            if dec(row["ask"]["c"], "ask.c") < dec(row["bid"]["c"], "bid.c"):
                raise V4ProfitabilityError("negative closing spread")
            rows.append(row)
        return rows

    def chunk(self, index: int) -> list[dict]:
        start, end = self.bounds(index)
        if start >= SAFE_REQUEST_END:
            return []
        path = self.path(index)
        if not path.exists():
            payload, request_sha = self._request(start, end)
            raw_sha = hashlib.sha256(payload).hexdigest()
            rows = self._parse(payload)
            with path.open("w") as handle:
                for row in rows:
                    handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            self.meta[index] = {
                "chunk_index": index,
                "from": zulu(start),
                "to": zulu(end),
                "request_sha256": request_sha,
                "raw_response_sha256": raw_sha,
                "raw_bytes": len(payload),
                "complete_m1_rows": len(rows),
                "parsed_sha256": file_sha(path),
            }
        else:
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        return rows

    def iter_from(self, start: datetime):
        index = self.index(start)
        seen: dict[str, dict] = {}
        while True:
            chunk_start, _ = self.bounds(index)
            if chunk_start >= SAFE_REQUEST_END:
                break
            for row in self.chunk(index):
                timestamp = parse(row["ts_start_utc"])
                if timestamp < start:
                    continue
                old = seen.get(row["ts_start_utc"])
                if old is not None:
                    if old != row:
                        raise V4ProfitabilityError(f"conflicting duplicate M1 {row['ts_start_utc']}")
                    continue
                seen[row["ts_start_utc"]] = row
                yield row
            index += 1

    def provenance(self) -> dict:
        chunks = [self.meta[key] for key in sorted(self.meta)]
        out = {
            "schema_version": 1,
            "provider": "OANDA_V20",
            "environment": "practice",
            "instrument": INSTRUMENT,
            "granularity": "M1",
            "price_components": "BA",
            "chunk_calendar_days": 3,
            "origin": zulu(ORIGIN),
            "strict_end_exclusive": zulu(END),
            "last_request_to_lt_strict_end": all(parse(x["to"]) < END for x in chunks),
            "chunks_requested": len(chunks),
            "chunks": chunks,
            "first_m1_response_accessed": self.first_response_accessed,
            "credentials_exposed": False,
            "mutation_endpoints_used": False,
        }
        out["provenance_sha256"] = engine.canon(out)
        return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--marker",
        default="research/profitability/V4_SHARP_TURN_PROFITABILITY_EXECUTE_LOCK.json",
    )
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    first_m1_access = False
    try:
        lock = verify_lock(Path("research/profitability/v4_sharp_turn_profitability_execution_lock_v1.json"))
        marker = verify_marker(Path(args.marker))
        readiness = verify_readiness()
        if readiness["readiness_sha256"] != READINESS_SHA:
            raise V4ProfitabilityError("readiness SHA drift")

        structure_dir = output / "structure"
        manifest = structure.acquire(
            Path("research/profitability/v4_sharp_turn_execution_protocol_v1.json"),
            structure_dir,
            delay=0.01,
        )
        trigger_report = trigger_scan.build(
            structure_dir,
            Path("research/profitability/v4_sharp_turn_execution_protocol_v1.json"),
        )
        report_path = output / "pre-m1-trigger-reconstruction.json"
        manifest_path = structure_dir / "NAS100_USD.v4-structure-manifest.json"
        report_path.write_text(json.dumps(trigger_report, indent=2, sort_keys=True) + "\n")
        verify_reproduction(readiness, report_path, manifest_path)
        if trigger_report["trigger_set_sha256"] != TRIGGER_SHA:
            raise V4ProfitabilityError("canonical V4 trigger set did not reconstruct exactly")
        triggers = trigger_report["sealed_triggers"]
        if len(triggers) != 213:
            raise V4ProfitabilityError("canonical V4 trigger cardinality changed")
        if len({x["trigger_knowledge_time_utc"] for x in triggers}) != 213:
            raise V4ProfitabilityError("canonical V4 trigger-time cardinality changed")

        # First network-capable M1 object is created only after exact canonical
        # structure/trigger reproduction has passed. Object construction itself
        # performs no request; first response occurs inside portfolio evaluation.
        cache = M1Cache(
            output / "m1-cache",
            os.getenv("OANDA_ACCOUNT_ID", ""),
            os.getenv("OANDA_API_TOKEN", ""),
        )
        base = engine.evaluate_portfolio(
            triggers,
            cache.iter_from,
            scenario="BASE",
            slip_points=Decimal("0.5"),
            financing_r_per_1440=Decimal("0.005"),
            dataset_end=END,
        )
        first_m1_access = cache.first_response_accessed
        if not first_m1_access:
            raise V4ProfitabilityError("economic run completed without first M1 response")
        stress = engine.evaluate_portfolio(
            triggers,
            cache.iter_from,
            scenario="STRESS",
            slip_points=Decimal("1.0"),
            financing_r_per_1440=Decimal("0.01"),
            dataset_end=END,
        )
        base_metrics = engine.metrics(base)
        stress_metrics = engine.metrics(stress)
        classification = engine.classify(base_metrics, stress_metrics)
        provenance = cache.provenance()

        write_jsonl(output / "base-trade-ledger.jsonl", base["ledger"])
        write_jsonl(output / "stress-trade-ledger.jsonl", stress["ledger"])
        (output / "provider-provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")

        result = {
            "schema_version": 1,
            "status": "V4_SHARP_TURN_PROFITABILITY_RESULT_READY",
            "classification": classification,
            "validated_historical_edge": classification in {"PRELIMINARY_HISTORICAL_EDGE", "STRONG_HISTORICAL_EDGE"},
            "strong_historical_edge": classification == "STRONG_HISTORICAL_EDGE",
            "historical_window_classification": "BACKWARD_HISTORICAL_DEVELOPMENT_NOT_UNTOUCHED_FAMILY_HOLDOUT",
            "trigger_set_sha256": TRIGGER_SHA,
            "trigger_readiness_sha256": READINESS_SHA,
            "trigger_count": len(triggers),
            "long_trigger_count": sum(1 for x in triggers if x["direction"] == "LONG"),
            "short_trigger_count": sum(1 for x in triggers if x["direction"] == "SHORT"),
            "execution_protocol_sha256": PROTOCOL_SHA,
            "profitability_execution_lock_sha256": LOCK_SHA,
            "execution_marker": marker,
            "structure_manifest_sha256": manifest["manifest_sha256"],
            "structure_retrieval_sha256": manifest["retrieval_sha256"],
            "provider_provenance_sha256": provenance["provenance_sha256"],
            "provider_chunks_requested": provenance["chunks_requested"],
            "base_metrics": base_metrics,
            "stress_metrics": stress_metrics,
            "base_ledger_sha256": base["ledger_sha256"],
            "stress_ledger_sha256": stress["ledger_sha256"],
            "first_m1_response_accessed": cache.first_response_accessed,
            "exact_trigger_reconstruction_before_first_m1_response": True,
            "parameter_changes_after_first_m1_response": False,
            "no_refit_performed": True,
            "v3c_outcomes_used_for_v4_execution_selection": False,
            "post_2023_m1_requested_or_admitted": False,
            "synthetic_fills": 0,
            "paper_execution_authorized": False,
            "live_execution_authorized": False,
            "broker_mutation_authorized": False,
        }
        result["result_sha256"] = engine.canon(result)
        (output / "profitability-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

        shutil.rmtree(output / "m1-cache", ignore_errors=True)
        shutil.rmtree(structure_dir, ignore_errors=True)
    except Exception as exc:
        print(f"V4 Sharp Turn profitability execution failed: {exc}", file=sys.stderr)
        print(f"first_v4_m1_response_accessed={first_m1_access}", file=sys.stderr)
        return 1

    print(json.dumps({
        "status": result["status"],
        "classification": classification,
        "validated_historical_edge": result["validated_historical_edge"],
        "base_resolved": base_metrics["resolved_executed_trades"],
        "base_long": base_metrics["long_trades"],
        "base_short": base_metrics["short_trades"],
        "base_expectancy_r": base_metrics["net_expectancy_r"],
        "base_profit_factor": base_metrics["profit_factor"],
        "base_bootstrap_ci": base_metrics["bootstrap_95pct_ci_net_expectancy_r"],
        "stress_resolved": stress_metrics["resolved_executed_trades"],
        "stress_expectancy_r": stress_metrics["net_expectancy_r"],
        "stress_profit_factor": stress_metrics["profit_factor"],
        "provider_chunks_requested": provenance["chunks_requested"],
        "result_sha256": result["result_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
