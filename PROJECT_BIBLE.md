# Project Bible

## Mission

Build a research-grade, reproducible algorithmic trading repository that attempts to translate Arjo's public first-party educational material into deterministic rules, then evaluates those rules scientifically.

The project does **not** assume the methodology is profitable.

## Immutable principles

1. **Evidence before code.** Strategy implementation is blocked until `SPEC_READY`.
2. **First-party closure only.** Secondary sources may locate first-party material but receive zero semantic closure credit.
3. **No invented semantics.** Missing fields remain missing.
4. **No performance-guided specification.** Before `SPEC_READY`, trade counts, win rate, P&L, expectancy, Sharpe, profit factor, and parameter/market/time/instrument optimization are forbidden.
5. **Two-engineer test.** A predicate is not ready unless two independent engineers could implement it and produce materially identical signals.
6. **Contradictions are explicit.** Conflicts are versioned, context-dependent, or unresolved; unresolved conflicts block readiness.
7. **Immutable preregistration.** Candidate parameters and DEV/OOS/CONFIRM boundaries are committed before outcomes are observed.
8. **Protected data is one-way.** OOS and CONFIRM may be opened once only through deterministic guards.
9. **Paper execution requires owner authorization.**
10. **Live trading is never autonomously authorized.** Live brokerage endpoints must remain technically blocked.

## Canonical project control

- GitHub Issues = execution queue.
- Repository files = durable project state.
- `project_state.json` = machine-generated current state.
- `STATUS.md` = derived human summary.
- Master lifecycle issue = dependency graph, gates, work queue, blockers, critical path.
- No agent may keep a hidden competing roadmap.

## Allowed autonomous work

The autonomous system may:

- discover public first-party sources;
- acquire lawful public evidence and metadata;
- hash and provenance-bind artifacts;
- extract timestamped evidence;
- create bounded recovery issues;
- build research and engineering infrastructure;
- write tests;
- implement frozen specifications after `SPEC_READY`;
- run and repair CI;
- update documentation;
- open PRs;
- merge safe green PRs;
- maintain project state.

## Forbidden autonomous work

The autonomous system may not:

- invent strategy semantics;
- choose interpretations because they backtest better;
- change frozen strategy rules based on results;
- lower preregistered validation thresholds;
- inspect protected datasets early;
- authorize paper execution;
- authorize live trading;
- access live brokerage endpoints.

## Escalation reasons

Only escalate routine execution when one of these machine states applies:

- `FIRST_PARTY_SEMANTIC_DECISION_REQUIRED`
- `SECURITY_SECRET_REQUIRED`
- `FINANCIAL_RISK_AUTHORIZATION_REQUIRED`
- `PAPER_EXECUTION_AUTHORIZATION_REQUIRED`
- `LIVE_TRADING_AUTHORIZATION_REQUIRED`
- `IRRECOVERABLE_EXTERNAL_ACCESS_FAILURE`

## Strategy research lifecycle gates

1. `GOVERNANCE_BOOTSTRAP`
2. `SOURCE_UNIVERSE_DISCOVERED`
3. `CORPUS_ACQUIRED`
4. `CONCEPT_INVENTORY_READY`
5. `EVIDENCE_REGISTRY_READY`
6. `PREDICATE_MATRIX_READY`
7. `SPEC_AUDIT`
8. `SPEC_READY`
9. `CANDIDATE_PREREGISTERED`
10. `IMPLEMENTATION_READY`
11. `DEV_ACTIVITY_PASS`
12. `DEV_PERFORMANCE_PASS`
13. `OOS_PASS`
14. `CONFIRM_PASS`
15. `PROMOTE_TO_PAPER_CANDIDATE`
16. `PAPER_EXECUTION_ENABLED` — owner authorization required
17. `PAPER_QUALIFIED`
18. Future live gates — owner authorization required at every live boundary

## SPEC_READY requirements

At least one predicate must satisfy all of the following:

- all required fields are `SATISFIED`;
- contradictions are zero or explicitly resolved;
- provenance is complete;
- two-engineer test passes;
- an independent auditor reconstructs the predicate using only cited first-party evidence.

Only then may the specification be frozen and versioned.

## Preferred failure modes

Prefer:

- `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE` over invented semantics;
- `INSUFFICIENT_EVIDENCE` over false-positive closure;
- `REJECT` over manipulating validation rules.
