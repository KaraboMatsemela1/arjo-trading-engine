# Predicate Synthesis 001

## Purpose

Phase 5 asks whether the first-party evidence registry is sufficient to reconstruct deterministic predicates. It does not assume that any candidate is executable or profitable.

## Candidate admission

A named concept is not automatically a predicate candidate. A candidate requires direct first-party evidence of an operational relationship such as:

- direction;
- involvement or entry;
- target selection;
- hold/fail behavior;
- a setup transition.

The initial seed contains six bounded operational relationships. `scripts/build_candidate_selection_audit.py` independently surfaces direct evidence with operational lexical cues that is not represented in those candidates. Such cues require review; the audit never creates a predicate automatically.

## Canonical field matrix

Every candidate receives exactly these 16 fields:

`INPUTS`, `INSTRUMENTS`, `TIMEFRAME`, `HIGHER_TIMEFRAME_CONTEXT`, `DIRECTION`, `PRECONDITIONS`, `SETUP`, `TRIGGER`, `ENTRY`, `STOP`, `TARGET`, `INVALIDATION`, `EXPIRY`, `SESSION/TIME_RULE`, `OPTIONAL_CONDITIONS`, `REQUIRED_CONDITIONS`.

Allowed states are:

- `SATISFIED`
- `PARTIAL`
- `MISSING`
- `CONTRADICTORY`
- `NOT_APPLICABLE`

Unsupported fields default to `MISSING`. A `PARTIAL` field must cite evidence and state an explicit limitation. A `SATISFIED` field requires direct evidence. The current seed deliberately makes conservative partial claims and no executable-completion claim.

## Closure ranking

Closure ranking is performance-blind. Candidates are ordered lexicographically by:

1. number of `MISSING` fields;
2. number of `CONTRADICTORY` fields;
3. number of `PARTIAL` fields;
4. total unresolved fields;
5. predicate ID for deterministic tie-breaking.

No trade count, return, win rate, expectancy, or other market outcome may influence candidate selection or closure ranking.

## Minimal recovery set

Each candidate defines bounded recovery bundles tied to unresolved field groups. `scripts/build_predicate_matrix.py` computes an exact minimum-cardinality set cover over those bundles for the candidate's unresolved fields. `scripts/build_recovery_tasks.py` emits one bounded recovery task per candidate and marks only the two closest candidates as the active recovery set; the rest remain backlog.

Recovery targets remain first-party-only. Secondary/search-index material retains zero semantic closure credit.

## Two-engineer preflight

`scripts/two_engineer_preflight.py` reconstructs the candidate field packet using two independent serialization/code paths:

- candidate-registry expansion;
- generated matrix reconstruction.

Hashes and normalized rows must match. This is a deterministic reproducibility preflight only. It explicitly does **not** claim two independent humans/models and does not satisfy the later independent `SPEC_READY` audit in Issue #9.

## Candidate omission audit

The candidate-selection omission audit scans only direct first-party evidence for bounded operational lexical cues. Unrepresented cue-bearing concepts are surfaced as `REVIEW_REQUIRED`. They must be either admitted as candidates or explicitly dispositioned before `PREDICATE_MATRIX_READY` can be granted.

## Phase boundary

Phase 5 may produce matrices, closure rankings, contradiction records, reconstruction packets, and targeted recovery tasks. It may not implement detectors, inspect trade counts, backtest, optimize, evaluate performance, place paper trades, place live trades, or add broker execution logic.
