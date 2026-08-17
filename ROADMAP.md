# Roadmap

The engineering roadmap is complete through the V2 future-validation harness. The only unfinished project gate is the untouched final V2 validation in Issue #201, which is intentionally blocked by chronology until **2027-03-01T00:00:00Z** and explicit owner dispatch.

## Completed foundation

### Phase 0 — Governance

**Gate:** `GOVERNANCE_BOOTSTRAP_COMPLETE` — COMPLETE

Canonical governance, issue metadata, dependency validation, project-state generation and CI controls.

### Phases 1–5 — Evidence and deterministic specification foundation

**Gates:**
- `SOURCE_UNIVERSE_DISCOVERED` — COMPLETE
- `ACQUISITION_TOOLING_READY` — COMPLETE
- `CORPUS_ACQUIRED` — COMPLETE
- `CONCEPT_INVENTORY_READY` — COMPLETE
- `EVIDENCE_REGISTRY_READY` — COMPLETE
- `PREDICATE_MATRIX_READY` — COMPLETE

First-party evidence remains the semantic authority. Owner-operational conventions are explicitly versioned where exact first-party machine semantics could not be recovered.

### Phase 6A — Governed V1 calibration

**Gates:**
- `CALIBRATION_PROTOCOL_READY` — COMPLETE
- `SEMANTIC_SEED_READY` — COMPLETE
- `CALIBRATION_AUTHORIZED` — COMPLETE
- `CALIBRATION_PREREGISTRATION_COMPLETE` — COMPLETE
- `CALIBRATION_DATA_PIPELINE_READY` — COMPLETE
- `CALIBRATION_REPLAY_HARNESS_READY` — COMPLETE
- `CALIBRATION_DATA_READY` — COMPLETE
- `CALIBRATION_OCCURRENCES_READY` — COMPLETE
- `CALIBRATED_SPEC_FROZEN` — COMPLETE

The owner-directed OANDA practice `NAS100_USD` source was used for 2024–2025 calibration. It is an OANDA Nasdaq-100 CFD proxy/source, not asserted to be literal CME NQ futures.

Frozen V1 execution selected `SECOND_STING_TOUCH` with stop buffer `0` structurally, not by performance ranking.

### V1 independent reconstruction

**Gate:** `SPEC_READY` — COMPLETE

The calibrated owner-operational V1 profile was independently reconstructed by production and isolated standard-library paths.

### V1 protected validation

**Gates:**
- `PROTECTED_VALIDATION_PROTOCOL_FROZEN` — COMPLETE
- `PROTECTED_VALIDATION_COMPLETE` — COMPLETE

The one-time protected 2026H1 read exposed `VALIDATION_INTEGRITY_FAILURE`: V1 could semantically qualify a second sting while the frozen touch price was not present in that bar. No target/stop outcome was assigned for the defective occurrence and V1 was not refit.

The 2026H1 interval is consumed and may not be reused for V2 tuning, initialization or validation.

## V2 remediation lifecycle — complete

### V2 execution-observability remediation

**Gate:** `V2_REMEDIATION_DESIGN_READY` — COMPLETE

V2 separates semantic qualification from executable fill observability:

```text
second_sting_bar.low <= touch_price <= second_sting_bar.high
```

False produces `NO_EXECUTABLE_ENTRY`, never a synthetic or fallback fill.

### V2 independent SPEC reconstruction

**Gate:** `V2_SPEC_FROZEN` — COMPLETE

Frozen profile:

```text
ARJO_DERIVED_OWNER_OPERATIONAL_V2
87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6
```

Production and independent standard-library paths agree on the sealed 2024–2025 developmental reconstruction.

### V2 future-validation protocol

**Gate:** `V2_FUTURE_VALIDATION_PROTOCOL_READY` — COMPLETE

Initial future-validation boundaries, result taxonomy, sample threshold, no-refit policy and explicit authorization gates were frozen before any future-window data access.

### Causal cold-start correction

**Gate:** `V2_CAUSAL_VALIDATION_PROTOCOL_READY` — COMPLETE

The strategy carries FVG/pivot state, so a scored September 1 start would require forbidden pre-window carry-in. The superseding causal protocol therefore freezes:

```text
Acquisition:       [2026-09-01, 2027-03-01)
State at Sep 1:    EMPTY
Bootstrap:         [2026-09-01, 2026-10-01) — unscored
Scored validation:[2026-10-01, 2027-03-01)
```

No pre-start market data, state snapshot or V1 2026H1 state/data may seed V2.

Frozen protocol SHA:

```text
193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38
```

### M1 execution sequencing

**Gate:** `V2_EXECUTION_MEASUREMENT_READY` — COMPLETE

The 15-minute V2 observability rule is unchanged. A separate M1 measurement policy establishes causal event timing without inferring unknown OHLC order:

```text
V2_M1_TOUCH_SEQUENCING_V1
6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6
```

Missing M1 touch after 15m observability fails integrity. Stop/target in the entry minute or both in a later minute is `AMBIGUOUS_INTRABAR_ORDER`.

### Complete future-validation harness

**Gate:** `V2_FUTURE_VALIDATION_HARNESS_READY` — COMPLETE

The entire final path is implemented and tested:
- SHA/date/authorization guards;
- single-shot, read-only OANDA full-window acquisition;
- deterministic M1 → 15m/60m/240m normalization;
- empty-state bootstrap;
- production semantic/evaluation path;
- isolated independent standard-library path;
- V2 observability and M1 sequencing;
- exact dual-path comparison;
- preregistered metric and classification computation;
- SHA-bound final result sealing.

Frozen request-contract SHA:

```text
edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca
```

Harness readiness SHA:

```text
8b4640018db1226dae10bd440e5abb20f60958b47882cb7f2cddb69c7f7add79
```

## Final remaining phase — untouched V2 validation

**Issue:** #201

**Gate:** `V2_FUTURE_VALIDATION_COMPLETE` — PENDING / `EXTERNAL_WAIT`

**Earliest legal execution:** `2027-03-01T00:00:00Z`

The final workflow is already implemented at:

```text
.github/workflows/v2-future-validation-execution.yml
```

It intentionally implements no rolling/partial acquisition. After the full window closes, repository owner `KaraboMatsemela1` must explicitly dispatch it with:

```text
AUTHORIZE_V2_FUTURE_VALIDATION
```

The workflow then acquires the exact full OANDA window once, runs both independent evaluation paths, compares them, computes the frozen result classification, and seals the final evidence.

The inferential threshold remains **30 resolved executable occurrences**. If the full untouched window produces fewer, the result is `INSUFFICIENT_SAMPLE`; the project does not widen the window or adjust rules afterward.

## Post-validation boundaries

`V2_FUTURE_VALIDATION_COMPLETE` is a research-validation result gate, not automatic trading permission.

Paper execution remains disabled unless the owner separately authorizes a new paper-qualification lifecycle. Live trading is never autonomously authorized. Broker mutation remains disabled.

No further strategy engineering, refit or validation-window modification is planned before #201 executes unless a genuine implementation-integrity defect is discovered.
