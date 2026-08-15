# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-executable specifications and evaluating them scientifically.

> **Current gate:** `GOVERNANCE_BOOTSTRAP`
>
> **Strategy implementation:** **PROHIBITED** until `SPEC_READY = true`.

## Core rule

**Evidence before code.**

No detector, backtester, strategy candidate, trade counter, optimizer, performance evaluator, or broker execution logic may be implemented before at least one predicate passes the independent `SPEC_READY` audit.

## Canonical state

- GitHub Issues are the execution queue.
- Repository files are durable state.
- `project_state.json` is machine-generated state.
- `STATUS.md` is the human-readable gate summary.
- `PROJECT_BIBLE.md` defines immutable safeguards and lifecycle rules.
- No agent may maintain a hidden competing roadmap.

## Initial critical path

`GOVERNANCE_BOOTSTRAP` → `SOURCE_UNIVERSE_DISCOVERED` → `CORPUS_ACQUIRED` → `CONCEPT_INVENTORY_READY` → `EVIDENCE_REGISTRY_READY` → `PREDICATE_MATRIX_READY` → `SPEC_AUDIT` → `SPEC_READY`

Engineering infrastructure that cannot influence strategy semantics may proceed independently.

## Safety boundaries

The autonomous system may research public evidence, build acquisition/provenance tooling, maintain project state, run CI, repair CI, open PRs, and merge dependency-safe green changes.

It may **not** invent strategy semantics, optimize interpretations toward profitability, inspect protected datasets early, lower preregistered thresholds, authorize paper execution, authorize live trading, or access live brokerage endpoints.

## Project status

See [`STATUS.md`](STATUS.md). Progress is reported by objective gates, not arbitrary percentages.
