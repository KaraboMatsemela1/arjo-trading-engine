# Atomic Evidence Extraction 001

## Purpose

Phase 4 converts concept citations into atomic evidence records without creating executable strategy rules.

## Atomicity

Each record answers one narrow question:

- does this direct first-party source explicitly mention/use the concept in context; or
- does the cited material establish a complete deterministic construction?

Concept mention/context and deterministic construction are deliberately separate. A direct mention never upgrades a missing construction into a rule.

## Proof boundary

Every record contains both:

- `WHAT_IT_PROVES`
- `WHAT_IT_DOES_NOT_PROVE`

This prevents later synthesis from treating partial evidence as complete semantics.

## Minimal excerpts

Text evidence is extracted only from already acquired, direct first-party Telegram sources. Quotes are bounded to at most 25 words by validation and the builder targets an 18-word maximum. Raw posts are not copied into the repository.

## Explicit insufficiency

Every concept with unresolved inventory ambiguity receives a `DETERMINISTIC_CONSTRUCTION` record with `CONFIDENCE=INSUFFICIENT`. The record identifies the missing construction without claiming that the rule is absent from all possible first-party material.

Textless/link-preview concept citations also remain explicit `INSUFFICIENT` evidence unless direct textual support is recovered.

## Anti-bias guard

Before `SPEC_READY`, evidence validation rejects leaked outcome/performance metrics such as percentages, win rate, profit factor, Sharpe, expectancy, P&L, or trade-count claims. Concept/context language such as qualitative probability remains allowed when it is part of Arjo's source terminology, but it cannot be used for outcome selection.

## Provenance

Every evidence source must:

- exist in `research/source_registry.csv`;
- be `CONFIRMED_FIRST_PARTY`;
- have `PAYLOAD_CAPTURED` in the acquisition manifest;
- show direct first-party contact;
- carry `DIRECT_FIRST_PARTY_PAYLOAD` closure credit;
- have a SHA-256 acquisition hash;
- match the source publication date.

## Phase boundary

`EVIDENCE_REGISTRY_READY` means evidence is atomized and its gaps are explicit. It does not mean any candidate predicate is complete. Phase 5 must map evidence independently to required predicate fields and leave unsupported fields `MISSING`, `PARTIAL`, or `CONTRADICTORY`.
