# Project Bible

## Mission

Build a research-grade, reproducible algorithmic trading repository that attempts to translate Arjo's public first-party educational material into deterministic rules, then evaluates those rules scientifically.

The project does **not** assume the methodology is profitable.

## Immutable principles

1. **Evidence before code.** General strategy implementation remains blocked until `SPEC_READY`. The only pre-`SPEC_READY` strategy-adjacent code permitted is the minimum data/replay infrastructure required to execute a valid `FIRST_PARTY_PRESCRIBED_CALIBRATION_V1` packet after `CALIBRATION_AUTHORIZED`.
2. **First-party closure only.** Secondary sources may locate first-party material but receive zero semantic closure credit.
3. **No invented semantics.** Missing fields remain missing. Calibration may operationalize only a first-party-supported semantic family through variants or bounds frozen before outcome access; it may not create a new semantic rule from results.
4. **No performance-guided semantic specification.** Before `CALIBRATION_AUTHORIZED`, outcome inspection is forbidden. During an authorized calibration, only the locked seed, frozen calibration window, preregistered parameters, and preregistered measures/acceptance rule may be used. Semantic candidate discovery or selection by performance remains forbidden. Before `SPEC_READY`, P&L, expectancy, Sharpe, profit factor, performance leaderboards, market/time/instrument optimization, and protected-data tuning remain forbidden.
5. **Two-engineer test.** A predicate is not ready unless two independent engineers could implement it and produce materially identical signals.
6. **Contradictions are explicit.** Conflicts are versioned, context-dependent, or unresolved; unresolved conflicts block readiness.
7. **Immutable preregistration.** Calibration choices are frozen before calibration outcomes are read. Later scientific-validation candidate parameters and DEV/OOS/CONFIRM boundaries are frozen before their protected outcomes are observed.
8. **Protected data is one-way.** Calibration holdout, OOS, and CONFIRM data remain unread until their explicit lifecycle gate permits one-time access.
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
- after `CALIBRATION_AUTHORIZED`, build only the minimum provenance-bound market-data and deterministic replay infrastructure needed by the frozen calibration packet;
- execute only the frozen calibration packet against its declared calibration window while keeping its holdout unread;
- implement the general frozen strategy after `SPEC_READY`;
- run and repair CI;
- update documentation;
- open PRs;
- merge safe green PRs;
- maintain project state.

## Forbidden autonomous work

The autonomous system may not:

- invent strategy semantics;
- choose semantic interpretations because they backtest better;
- add calibration variants, concepts, candidates, windows, measures, or acceptance rules after calibration outcome access begins;
- change frozen strategy rules based on results;
- lower preregistered validation thresholds;
- inspect calibration holdout, OOS, or CONFIRM data early;
- use pre-`SPEC_READY` calibration as a general optimizer or performance leaderboard;
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
7. `CALIBRATION_PROTOCOL_READY`
8. `SEMANTIC_SEED_READY`
9. `CALIBRATION_AUTHORIZED`
10. `CALIBRATED_SPEC_FROZEN`
11. independent reconstruction / `SPEC_AUDIT`
12. `SPEC_READY`
13. `CANDIDATE_PREREGISTERED` for post-SPEC scientific validation
14. `IMPLEMENTATION_READY`
15. `DEV_ACTIVITY_PASS`
16. `DEV_PERFORMANCE_PASS`
17. `OOS_PASS`
18. `CONFIRM_PASS`
19. `PROMOTE_TO_PAPER_CANDIDATE`
20. `PAPER_EXECUTION_ENABLED` — owner authorization required
21. `PAPER_QUALIFIED`
22. Future live gates — owner authorization required at every live boundary

## Governed calibration requirements

Calibration before `SPEC_READY` is valid only when all of the following hold:

- a first-party-supported semantic seed is locked;
- the seed is deterministically replayable apart from explicitly declared calibratable conventions;
- every calibratable convention and its candidate set or bounds is frozen before outcomes are read;
- calibration and holdout windows are frozen and non-overlapping;
- the calibration measure and acceptance rule are frozen before outcomes are read;
- the preregistration is content-hash bound;
- holdout remains unread during calibration;
- calibration cannot discover or select semantic candidates from outcomes;
- completion produces a frozen, provenance-bound calibrated spec; it does not directly imply `SPEC_READY`.

## SPEC_READY requirements

At least one predicate/specification must satisfy all of the following after any required governed calibration:

- every required semantic field is deterministic and supported or explicitly governed by a pre-outcome configuration boundary;
- contradictions are zero or explicitly resolved;
- provenance is complete;
- any calibration packet is complete, frozen, and audit-valid;
- two-engineer test passes;
- an independent auditor reconstructs the specification using only the admissible first-party evidence plus explicitly frozen pre-outcome configuration/calibration artifacts.

Calibration may not convert genuinely missing first-party semantics into `SATISFIED` merely because one variant performs better.

Only after the independent audit passes may the general strategy specification be frozen/versioned as `SPEC_READY` and normal implementation begin.

## Preferred failure modes

Prefer:

- `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE` over invented semantics;
- `INSUFFICIENT_EVIDENCE` over false-positive closure;
- `CALIBRATION_BLOCKED` over post-outcome rule invention;
- `REJECT` over manipulating validation rules.
