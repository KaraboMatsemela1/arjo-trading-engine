# Roadmap

The engineering roadmap is complete. The project is wrapped on the frozen V2 research baseline with status:

```text
DEVELOPMENT_COMPLETE_VALIDATION_DEFERRED
```

Untouched V2 future validation is preserved as an optional future scientific follow-up, not a blocking project deliverable.

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

The 2026H1 interval is consumed and may not be reused for V2 tuning, initialization or future-validation evidence.

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

Production and independent standard-library paths agree on the sealed developmental reconstruction.

### V2 future-validation protocol

**Gate:** `V2_FUTURE_VALIDATION_PROTOCOL_READY` — COMPLETE

Future-validation boundaries, result taxonomy, sample threshold, no-refit policy and authorization boundaries were frozen before future-window access.

### Causal cold-start correction

**Gate:** `V2_CAUSAL_VALIDATION_PROTOCOL_READY` — COMPLETE

The strategy carries FVG/pivot state, so any later untouched validation uses a frozen empty-state bootstrap design rather than forbidden historical carry-in.

Frozen protocol SHA:

```text
193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38
```

### M1 execution sequencing

**Gate:** `V2_EXECUTION_MEASUREMENT_READY` — COMPLETE

The M1 measurement policy establishes causal event timing without inferring unknown OHLC order:

```text
V2_M1_TOUCH_SEQUENCING_V1
6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6
```

### Future-validation harness

**Gate:** `V2_FUTURE_VALIDATION_HARNESS_READY` — COMPLETE

The sealed optional validation path is fully implemented and tested, including SHA/date/authorization guards, single-shot read-only OANDA acquisition, deterministic normalization, causal bootstrap, dual independent evaluation paths, observability/sequencing checks, preregistered classification, and SHA-bound result sealing.

Frozen request-contract SHA:

```text
edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca
```

Harness readiness SHA:

```text
8b4640018db1226dae10bd440e5abb20f60958b47882cb7f2cddb69c7f7add79
```

## Project completion boundary

The project is complete as an engineering/research build at the current V2 state.

The following is deliberately **not** claimed:

```text
V2_FUTURE_VALIDATION_COMPLETE = false / not asserted
```

This does not block current project completion. It only limits the claims that may be made about the frozen V2 profile.

The current V2 profile may be retained as a reproducible research implementation and baseline. It must not be described as future-validated, proven profitable, production-ready, or execution-qualified.

## Optional future re-entry

The workflow remains preserved at:

```text
.github/workflows/v2-future-validation-execution.yml
```

If the project is revisited after the original chronology boundary, the frozen optional protocol remains:

```text
Acquisition:        [2026-09-01, 2027-03-01)
Bootstrap:          [2026-09-01, 2026-10-01) — unscored
Scored validation:  [2026-10-01, 2027-03-01)
Earliest full read: 2027-03-01T00:00:00Z
```

That future work must be opened as a new bounded lifecycle. Closing the previous wait issue does not satisfy or assert `V2_FUTURE_VALIDATION_COMPLETE`.

## Execution boundaries at wrap

```text
PAPER_EXECUTION_ENABLED = false
LIVE_TRADING_AUTHORIZED = false
BROKER_MUTATION          = false
```

Paper or live work, if ever desired, requires a separate explicit authorization and qualification lifecycle.

No further work is required for the current project wrap.
