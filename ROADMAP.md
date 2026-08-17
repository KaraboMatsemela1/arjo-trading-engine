# Roadmap

## Phase 0 — Governance

**Exit gate:** `GOVERNANCE_BOOTSTRAP_COMPLETE`

Deliver canonical governance documents, repository structure, issue metadata contract, machine-readable project state, deterministic dependency/gate checks, and baseline GitHub Actions.

## Phase 1 — Source discovery

**Exit gate:** `SOURCE_UNIVERSE_DISCOVERED`

Discover the complete relevant public first-party Arjo source universe. Secondary sources may help locate first-party sources but receive zero closure credit.

## Phase 2 — Corpus acquisition

**Exit gate:** `CORPUS_ACQUIRED`

Acquire metadata, descriptions, chapters, captions/transcripts where publicly retrievable, timestamp the corpus, create frame locators where chart meaning is required, and hash/provenance-bind captured artifacts.

## Phase 3 — Concept inventory

**Exit gate:** `CONCEPT_INVENTORY_READY`

Derive Arjo's actual concept taxonomy from the acquired first-party corpus without importing external ICT assumptions.

## Phase 4 — Field-level evidence

**Exit gate:** `EVIDENCE_REGISTRY_READY`

Extract atomic evidence records with explicit proof scope and confidence.

## Phase 5 — Predicate synthesis

**Exit gate:** `PREDICATE_MATRIX_READY`

Map every executable field to first-party evidence, track `SATISFIED`, `PARTIAL`, `MISSING`, `CONTRADICTORY`, and `NOT_APPLICABLE`, calculate minimal closure sets, and generate bounded recovery issues.

## Phase 5A — Calibration protocol and semantic seed closure

**Exit gates:** `CALIBRATION_PROTOCOL_READY` → `SEMANTIC_SEED_READY` → `CALIBRATION_AUTHORIZED`

When direct first-party material prescribes plan-specific study/calibration for otherwise ambiguous execution conventions, lock one narrow semantic seed before outcomes are read. Freeze the calibratable parameters/variants or bounds, calibration and protected holdout windows, measures, acceptance rule, and immutable content hash. This stage may not discover or select semantic candidates from outcomes.

If no deterministic replayable seed can be formed without inventing semantics, remain blocked on first-party evidence.

## Phase 5B — Governed calibration

**Exit gate:** `CALIBRATED_SPEC_FROZEN`

Acquire only the frozen calibration window, build only the minimum provenance-bound data/replay infrastructure needed by the locked seed, replay only preregistered conventions, and freeze the result under the preregistered acceptance rule. The protected holdout remains unread.

Calibration is not a general backtest or optimizer. It cannot add concepts, candidates, variants, windows, measures, or thresholds after outcome access begins, and it cannot convert genuinely missing first-party semantics into a rule because of better performance.

## SPEC_READY audit

**Exit gate:** `SPEC_READY`

After any required governed calibration, require complete provenance, deterministic required fields/configuration boundaries, contradiction handling, two-engineer reconstruction, and an independent audit. A completed calibration packet does not automatically imply `SPEC_READY`.

Only a passing independent audit authorizes the frozen general strategy specification.

## Phase 6 — Post-SPEC scientific-validation preregistration

**Exit gate:** `CANDIDATE_PREREGISTERED`

Commit the immutable post-SPEC candidate configuration and DEV/OOS/CONFIRM boundaries before performance outcomes are observed. This is separate from the earlier calibration preregistration.

## Phase 7 — General implementation

**Entry gate:** `SPEC_READY`

Implement normalization, detector, signal ledger, backtester, risk model, and execution simulator with provenance references to the frozen specification. Calibration-only replay code may be promoted/reused only after it conforms to the frozen `SPEC_READY` specification.

## Phases 8–11 — Scientific validation

DEV activity → DEV performance → one-time OOS → one-time CONFIRM. No post-outcome threshold changes or protected-data tuning.

## Phases 12–14 — Paper infrastructure and qualification

Practice-only broker boundary, risk controls, kill switch, reconciliation, idempotency, persistent state, observability, audit logs, alerts, and runbooks. Paper execution remains disabled until explicit owner authorization.

## Phase 15+ — Future controlled progression

Learning readiness, shadow trading, and controlled live canary each require new preregistered gates. Live trading is never autonomously authorized.
