# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-replayable specifications and evaluating them scientifically.

> **Current lifecycle state:** governed calibration
>
> **CALIBRATION_AUTHORIZED:** `true` for the locked NQ AoO seed only
>
> **SPEC_READY:** `false`
>
> **General strategy implementation:** prohibited until the independent `SPEC_READY` audit passes.

## Core rule

**Evidence before code.**

First-party evidence remains the semantic authority. The repository now supports one narrow pre-`SPEC_READY` exception: after a locked seed reaches `CALIBRATION_AUTHORIZED`, the project may build only the minimum provenance-bound data/replay infrastructure needed to execute its SHA-bound `FIRST_PARTY_PRESCRIBED_CALIBRATION_V1` packet. That calibration cannot invent semantics, expand its candidate set after outcome access, inspect its protected holdout, or authorize paper/live trading.

## Objective project progress

```text
GOVERNANCE_BOOTSTRAP_COMPLETE       COMPLETE
SOURCE_UNIVERSE_DISCOVERED          COMPLETE
ACQUISITION_TOOLING_READY           COMPLETE
CORPUS_ACQUIRED                     COMPLETE
CONCEPT_INVENTORY_READY             COMPLETE
EVIDENCE_REGISTRY_READY             COMPLETE
PREDICATE_MATRIX_READY              COMPLETE
CALIBRATION_PROTOCOL_READY          COMPLETE
SEMANTIC_SEED_READY                 COMPLETE
CALIBRATION_AUTHORIZED              COMPLETE — locked NQ AoO seed only
CALIBRATION_PREREGISTRATION         ACTIVE — deterministic WoO freeze
CALIBRATION_DATA_READY              PENDING
CALIBRATED_SPEC_FROZEN              PENDING
SPEC_READY                          false
GENERAL IMPLEMENTATION              NOT AUTHORIZED
PROTECTED VALIDATION                UNOPENED
PAPER EXECUTION                     NOT AUTHORIZED
LIVE EXECUTION                      NOT AUTHORIZED
```

Progress is reported by objective gates and explicit readiness states rather than arbitrary percentages.

## Current locked calibration seed

The current bounded study is NQ long context only:

- 4h FVG + 1h FVA context;
- opposing resistance / 2CR rejection high must be run before seeking the long;
- 15m `2 Sting Entry` family;
- bullish Order Flow leg-low stop anchor;
- next HTF premium-array / ATH target context;
- no required parameter inside the frozen Window of Opportunity means no trade / move on.

Only these execution conventions are calibratable:

- `second_sting_fill_event`: `SECOND_STING_TOUCH` or `SECOND_STING_15M_CLOSE`;
- `stop_buffer_ticks`: `0`, `1`, or `2`.

Calibration dates are frozen to **2024-01-01 through 2025-12-31**. The protected calibration holdout is **2026-01-01 through 2026-06-30** and remains unread.

## Current critical path

`PREDICATE_MATRIX_READY`
→ `CALIBRATION_PROTOCOL_READY`
→ `SEMANTIC_SEED_READY`
→ `CALIBRATION_AUTHORIZED`
→ `CALIBRATION_PREREGISTRATION_COMPLETE`
→ `CALIBRATION_DATA_READY`
→ `CALIBRATED_SPEC_FROZEN`
→ independent reconstruction / `SPEC_AUDIT`
→ `SPEC_READY`
→ post-SPEC scientific-validation preregistration
→ general implementation
→ DEV / OOS / CONFIRM
→ controlled paper qualification.

## What calibration is allowed to do

A valid pre-SPEC calibration may:

- use only its frozen semantic seed;
- read only its frozen calibration window;
- replay only preregistered execution variants/bounds;
- compute only the preregistered calibration observations/measures;
- freeze one result under the preregistered acceptance rule;
- fail closed on ties, contradictions, missing data, or unreplayable semantics.

It may **not** use outcomes to create concepts, discover a different semantic candidate, move windows, add variants, lower acceptance rules, inspect the holdout, or treat better profitability as semantic proof.

## Canonical state

- GitHub Issues are the execution queue.
- `PROJECT_BIBLE.md` is the highest repository governance authority.
- Frozen specifications and calibration preregistrations bind executable work.
- `project_state.json` is machine-generated state.
- `STATUS.md` is the derived human-readable gate summary.
- Issue #1 is the canonical project tracker / lifecycle dashboard.
- No agent may maintain a hidden competing roadmap.

## Safety boundaries

The autonomous system may research lawful public first-party evidence, maintain provenance, build bounded calibration/research infrastructure, run/repair CI, open PRs, and merge dependency-safe green changes.

It may **not** invent strategy semantics, optimize semantic interpretations toward profitability, inspect protected datasets early, authorize paper execution, authorize live trading, or access live brokerage endpoints.

## Project status

See [`STATUS.md`](STATUS.md) and the master lifecycle issue for the mechanically current state.
