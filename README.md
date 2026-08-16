# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-executable specifications and evaluating them scientifically.

> **Current research state:** `FIRST_PARTY_PREDICATE_RECOVERY`
>
> **SPEC_READY:** `false`
>
> **Strategy implementation:** **PROHIBITED** until at least one predicate passes the independent `SPEC_READY` audit.

## Core rule

**Evidence before code.**

No detector, backtester, strategy candidate, trade counter, optimizer, performance evaluator, or broker execution logic may be implemented before at least one predicate passes the independent `SPEC_READY` audit.

## Project Progress

> Bars are qualitative stage indicators, not percentage estimates. Completed objective gates are full; blocked or unauthorized stages are empty.

```text
ENGINEERING FOUNDATION / GOVERNANCE
████████████████████   COMPLETE

FIRST-PARTY SOURCE UNIVERSE
████████████████████   COMPLETE

ACQUISITION TOOLING
████████████████████   COMPLETE

PUBLIC CORPUS ACQUISITION
████████████████████   COMPLETE — 1,175 / 1,175 sources terminally dispositioned

CONCEPT INVENTORY
████████████████████   COMPLETE — 36 source-bound concepts

ATOMIC EVIDENCE REGISTRY
████████████████████   COMPLETE — provenance-bound first-party evidence

PREDICATE SYNTHESIS / MATRIX
████████████████████   COMPLETE — 6 bounded candidates; required fields still incomplete

INDEPENDENT SPEC AUDIT
████████████████████   COMPLETE — BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE

FIRST-PARTY PREDICATE RECOVERY
████████████░░░░░░░░   ACTIVE — bounded recovery lanes; no candidate closed yet

SPEC FREEZE / v0.1
░░░░░░░░░░░░░░░░░░░░   BLOCKED — SPEC_READY = false

NEXT DETERMINISTIC CANDIDATE
░░░░░░░░░░░░░░░░░░░░   BLOCKED — no evidence-complete predicate

DETERMINISTIC DETECTOR
░░░░░░░░░░░░░░░░░░░░   NOT AUTHORIZED — requires SPEC_READY

BACKTESTER / ACTIVITY VALIDATION
░░░░░░░░░░░░░░░░░░░░   NOT AUTHORIZED — requires frozen deterministic spec

PERFORMANCE VALIDATION
░░░░░░░░░░░░░░░░░░░░   NOT AUTHORIZED — no pre-SPEC outcome optimization

OOS
░░░░░░░░░░░░░░░░░░░░   UNOPENED

CONFIRM
░░░░░░░░░░░░░░░░░░░░   UNOPENED

PAPER EXECUTION INFRASTRUCTURE
░░░░░░░░░░░░░░░░░░░░   NOT STARTED — downstream of deterministic validation

PAPER TRADING
░░░░░░░░░░░░░░░░░░░░   BLOCKED — requires qualification + explicit owner authorization

LEARNING ENGINE
░░░░░░░░░░░░░░░░░░░░   NOT STARTED — requires sufficient deterministic/paper labels

SHADOW TRADING
░░░░░░░░░░░░░░░░░░░░   NOT STARTED — requires paper readiness

CONTROLLED LIVE
░░░░░░░░░░░░░░░░░░░░   NOT AUTHORIZED — explicit future canary/risk approval required
```

### Current research position

- Governance, source discovery, acquisition tooling, corpus acquisition, concept inventory, evidence registry, and predicate-matrix gates are complete.
- The independent evidence-only audit process completed with `SPEC_READY = false` and outcome `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE`.
- Current work is bounded first-party predicate recovery. Missing semantics remain missing; inaccessible first-party sources receive zero semantic credit.
- No detector, backtester, trade-count analysis, optimizer, performance evaluation, paper execution, live execution, or broker logic is authorized yet.

## Canonical state

- GitHub Issues are the execution queue.
- Repository files are durable state.
- `project_state.json` is machine-generated state.
- `STATUS.md` is the human-readable gate summary.
- `PROJECT_BIBLE.md` defines immutable safeguards and lifecycle rules.
- No agent may maintain a hidden competing roadmap.

## Critical path

`GOVERNANCE_BOOTSTRAP_COMPLETE` → `SOURCE_UNIVERSE_DISCOVERED` → `ACQUISITION_TOOLING_READY` → `CORPUS_ACQUIRED` → `CONCEPT_INVENTORY_READY` → `EVIDENCE_REGISTRY_READY` → `PREDICATE_MATRIX_READY` → `INDEPENDENT_SPEC_AUDIT` → **first-party predicate recovery** → `SPEC_READY`

Engineering infrastructure that cannot influence strategy semantics may proceed independently.

## Safety boundaries

The autonomous system may research public evidence, build acquisition/provenance tooling, maintain project state, run CI, repair CI, open PRs, and merge dependency-safe green changes.

It may **not** invent strategy semantics, optimize interpretations toward profitability, inspect protected datasets early, lower preregistered thresholds, authorize paper execution, authorize live trading, or access live brokerage endpoints.

## Project status

See [`STATUS.md`](STATUS.md). Progress is reported by objective gates and explicit readiness states, not arbitrary completion percentages.
