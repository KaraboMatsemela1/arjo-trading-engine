# Decision Log

## ADR-0001 — Evidence before code

**Status:** ACCEPTED

Strategy implementation is prohibited until at least one predicate passes the independent `SPEC_READY` gate.

## ADR-0002 — First-party semantic authority

**Status:** ACCEPTED

Only Arjo first-party public educational material may close strategy semantics. Secondary sources may locate first-party material but receive zero closure credit.

## ADR-0003 — Repository-native project management

**Status:** ACCEPTED

GitHub Issues are the execution queue, repository files are durable state, and deterministic scripts generate current project state. No hidden competing roadmap is allowed.

## ADR-0004 — Objective gate reporting

**Status:** ACCEPTED

Project progress is reported through explicit gate states, never arbitrary percentages.

## ADR-0005 — No performance-guided semantic resolution

**Status:** ACCEPTED

Ambiguities and contradictions may not be resolved by selecting the interpretation with superior backtest outcomes.

## ADR-0006 — Human authorization boundaries

**Status:** ACCEPTED

Paper execution and every live-trading boundary require explicit owner authorization. Live trading can never be autonomously authorized.
