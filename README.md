# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-executable specifications and evaluating them scientifically.

> **Current research state:** `NEW_FIRST_PARTY_EVIDENCE_REQUIRED`
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
████████████████████   COMPLETE — 88 records across 4 evidence shards

PREDICATE SYNTHESIS / MATRIX
████████████████████   COMPLETE — 6 bounded candidates; required fields still incomplete

INDEPENDENT SPEC AUDIT
████████████████████   COMPLETE — BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE

FIRST-PARTY PREDICATE RECOVERY
████████████████████   COMPLETE — bounded pass exhausted across all 6 candidates

PUBLIC YOUTUBE ACCESS RECOVERY
████████████████████   COMPLETE — semantic payload unavailable on allowed public routes

NEW FIRST-PARTY EVIDENCE DISCOVERY
░░░░░░░░░░░░░░░░░░░░   REQUIRED — current evidence ceiling blocks further semantic closure

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

### Current predicate closure

| Candidate | Current state | Readiness |
|---|---:|---|
| `AOO_FVA_2CR_FVG_LONG_CONTEXT` | 7 MISSING / 9 PARTIAL | incomplete |
| `PD_ARRAY_2CR_FAILURE_INVOLVEMENT` | 9 MISSING / 7 PARTIAL | incomplete |
| `MMBM_LRLR_SHORT_CONTEXT` | 10 MISSING / 6 PARTIAL | incomplete |
| `ORDER_BLOCK_MT_HOLD_CONTEXT` | 10 MISSING / 6 PARTIAL | incomplete |
| `ORDER_FLOW_TARGET_BIAS` | 12 MISSING / 4 PARTIAL | incomplete |
| `EQUILIBRIUM_STOP_RUN_CONTEXT` | 13 MISSING / 3 PARTIAL | incomplete |

No candidate has a `SATISFIED` deterministic field set or an executable rule. Closure ranking is evidence-completeness only and never uses performance.

### Current research position

- Governance, source discovery, acquisition tooling, corpus acquisition, concept inventory, evidence registry, predicate synthesis, bounded predicate recovery, and independent audit processes are complete.
- All six current candidates have received bounded first-party recovery passes. None is evidence-complete.
- The refreshed independent evidence-only audit remains `SPEC_READY = false` with outcome `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE`.
- The allowed unauthenticated public YouTube routes were separately tested. Watch pages are bot-challenged in the runner; public embed/oEmbed responses expose availability/metadata but no semantic caption payload. Those surfaces receive zero semantic closure credit.
- The next research lane is **genuinely new direct first-party evidence discovery/acquisition**. Existing exhausted source sets should not be recycled unless the public payload/access conditions materially change.
- No detector, backtester, trade-count analysis, optimizer, performance evaluation, paper execution, live execution, or broker logic is authorized yet.

## Canonical state

- GitHub Issues are the execution queue.
- Repository files are durable state.
- `project_state.json` is machine-generated state.
- `STATUS.md` is the human-readable gate summary.
- `PROJECT_BIBLE.md` defines immutable safeguards and lifecycle rules.
- No agent may maintain a hidden competing roadmap.

## Critical path

`GOVERNANCE_BOOTSTRAP_COMPLETE` → `SOURCE_UNIVERSE_DISCOVERED` → `ACQUISITION_TOOLING_READY` → `CORPUS_ACQUIRED` → `CONCEPT_INVENTORY_READY` → `EVIDENCE_REGISTRY_READY` → `PREDICATE_MATRIX_READY` → `INDEPENDENT_SPEC_AUDIT` → `BOUNDED_PREDICATE_RECOVERY_COMPLETE` → **new direct first-party evidence required** → `SPEC_READY`

Engineering infrastructure that cannot influence strategy semantics may proceed independently.

## Safety boundaries

The autonomous system may research public evidence, build acquisition/provenance tooling, maintain project state, run CI, repair CI, open PRs, and merge dependency-safe green changes.

It may **not** invent strategy semantics, optimize interpretations toward profitability, inspect protected datasets early, lower preregistered thresholds, authorize paper execution, authorize live trading, or access live brokerage endpoints.

## Project status

See [`STATUS.md`](STATUS.md). Progress is reported by objective gates and explicit readiness states, not arbitrary completion percentages.
