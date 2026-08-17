# First-Party-Prescribed Calibration Protocol

## Purpose

The evidence-first boundary remains intact, but `SPEC_READY` must not create a circular requirement that contradicts the documented first-party strategy-development process.

Direct Trading MMT material describes narrow seed plans first and then plan-specific study/calibration. Examples include a `4h AoO -> 15m, 2 Sting Entry` seed followed by review of wins, losses and missed moves, and separate stop guidance that says the best stop is the one backed by data for the specific trading plan.

This protocol therefore distinguishes **semantic discovery** from **parameter calibration**.

## Lifecycle

`PREDICATE_MATRIX_READY -> SEMANTIC_SEED_READY -> CALIBRATION_AUTHORIZED -> CALIBRATED_SPEC_FROZEN -> independent reconstruction -> SPEC_READY`

`CALIBRATION_AUTHORIZED` is not `SPEC_READY`. It does not authorize paper trading, live trading, broker logic, or performance-driven candidate discovery.

## Semantic seed

Before any calibration outcomes are inspected, a seed must be frozen from direct first-party evidence. The seed must identify:

- the semantic candidate;
- instrument and timeframe stack;
- the directly supported rule skeleton;
- every parameter that remains calibratable;
- the direct evidence supporting each parameter family;
- whether the seed is replayable without hidden human judgment.

If the seed is not replayable, outcome access remains forbidden.

## Preregistration

Before calibration data is read, freeze:

- the calibration parameter names;
- candidate parameter variants or numerical bounds;
- calibration window;
- untouched holdout/OOS window;
- the single predeclared refinement measure;
- the acceptance rule;
- the semantic candidate identity.

The preregistration must be content-addressed before outcome access is authorized.

## Allowed use of outcomes

Calibration may only refine a parameter family that first-party evidence already says is plan-specific, relative, data-backed, or selected through study. Outcome data may not invent a new semantic concept or select among unrelated strategy candidates.

Examples of potentially calibratable implementation questions include a first-party-declared entry variant or a relative stop boundary. The exact admissible parameter set must be preregistered for the concrete seed plan; this document does not authorize a parameter merely by naming it.

## Forbidden uses

Even after calibration is authorized:

- no new candidate discovery from backtest results;
- no semantic candidate ranking by Sharpe, profit factor, win rate, return, or trade count;
- no adding concepts after seeing outcomes;
- no peeking at the holdout during calibration;
- no unconstrained grid search;
- no promotion to `SPEC_READY` from calibration results alone.

## Completion

A calibration result must be SHA-bound and produce a frozen calibrated spec. That spec still has to pass provenance, deterministic replay, the independent two-reconstruction packet, and the independent SPEC audit.

The holdout remains untouched until the post-calibration validation stage explicitly authorizes its use.
