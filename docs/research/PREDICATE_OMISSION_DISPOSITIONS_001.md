# Predicate Omission Dispositions 001

## Purpose

Phase 5's candidate-selection audit surfaced direct first-party operational language that was not represented by the six candidate relationships. The audit is intentionally lexical and cannot silently promote a concept into a predicate. Every `REVIEW_REQUIRED` item therefore needs an explicit evidence-bound disposition before `PREDICATE_MATRIX_READY` can be granted.

## RESISTANCE_LIQUIDITY_RUNS

Evidence: `EV_47407FF3FBAB9E586CA93D3B`.

The current direct text describes LRLR / Low Resistance Liquidity Run as indicating explosive moves. This establishes move-character context, but it does not currently define an operational relationship sufficient for candidate admission under the Phase 5 policy: no direction rule, involvement/entry action, target rule, hold/fail action, or setup transition is established.

Disposition: `NOT_ADMITTED_INSUFFICIENT_OPERATIONAL_RELATIONSHIP`.

This is not a claim that LRLR can never be part of a predicate. It means the currently admitted first-party evidence is insufficient to create one without invented semantics.

## TAPE_READING

Evidence: `EV_C2D2AD099F3842101F97C924`.

The current direct text defines Tape Reading as studying real-time price delivery for experience while holding no interest in pushing an entry. That evidence supports treatment as an observational/practice concept rather than an executable predicate relationship.

Disposition: `NOT_ADMITTED_NON_PREDICATE_PRACTICE`.

## Gate rule

`scripts/check_candidate_selection_dispositions.py` requires every regenerated `REVIEW_REQUIRED` omission-audit item to have exactly one current disposition tied only to the evidence IDs surfaced by that audit. Stale dispositions fail. Silent candidate admission fails. A future `ADMIT_CANDIDATE` decision requires a separate reviewed change to the candidate registry and matrix state.

No performance data, trade counts, backtest results, or market outcomes were consulted in either disposition.
