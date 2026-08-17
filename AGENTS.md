# Agent Operating Contract

## Purpose

This repository is designed for approximately 99% autonomous operation. Agents execute repository state; they do not redefine it.

## Canonical authority order

1. `PROJECT_BIBLE.md`
2. frozen/versioned specifications and calibration preregistrations
3. machine-readable gate state and issue metadata
4. GitHub master lifecycle issue
5. bounded task issue
6. supporting documentation

If instructions conflict, stop and surface the conflict. Never silently override a higher-authority rule.

## Claim protocol

Before starting an issue:

1. Confirm all declared dependencies are `COMPLETE`.
2. Confirm the entry gate is satisfied.
3. Confirm the issue is not actively claimed.
4. Claim exactly the bounded issue being executed.
5. Record owner/agent and state transition.
6. Work only within issue scope.
7. Run required deterministic checks.
8. Open a PR with issue linkage and gate impact.
9. When CI is green and required review is complete, merge safe work.
10. Mark issue `COMPLETE`, regenerate project state, then claim the next dependency-safe issue.

## Work-in-flight

Prefer one active implementation claim. A second claim is allowed only when the first lane is externally waiting (`CI_PENDING` or `REVIEW_PENDING`) and the second task is independent and dependency-safe.

Never treat `CI_PENDING` or `REVIEW_PENDING` as a global project blocker.

## Issue metadata contract

Every execution issue must declare:

- `ISSUE_ID`
- `TYPE`
- `DEPENDENCIES`
- `ENTRY_GATE`
- `OUTPUT_GATE`
- `OWNER`
- `STATE`

Allowed states:

- `BLOCKED`
- `READY`
- `CLAIMED`
- `IMPLEMENTING`
- `CI_PENDING`
- `REVIEW_PENDING`
- `COMPLETE`

## Research conduct

- First-party evidence determines semantics.
- Secondary sources receive zero closure credit.
- Missing means missing.
- Contradictory means contradictory until explicitly resolved.
- Do not infer generic ICT semantics into Arjo terminology.
- Do not upgrade `STRONG_PARTIAL` evidence to `DIRECT` through interpretation.
- Research recovery work must target a specific predicate field and stop condition.
- Calibration cannot manufacture semantic evidence. It may refine only an explicitly preregistered convention inside a locked first-party-supported semantic seed.

## Pre-SPEC_READY prohibition

While `SPEC_READY = false`, agents must not create or expose general strategy-performance analysis, including:

- unrestricted strategy trade counts;
- win-rate leaderboards;
- P&L;
- expectancy;
- Sharpe;
- profit factor;
- semantic-candidate optimization;
- market optimization;
- time optimization;
- instrument optimization.

The sole narrow exception is a valid `FIRST_PARTY_PRESCRIBED_CALIBRATION_V1` lifecycle after `CALIBRATION_AUTHORIZED`. In that state an agent may:

- acquire only the frozen calibration window, never the protected holdout;
- build the minimum deterministic data/replay infrastructure required for the locked seed;
- replay only preregistered parameter candidates or bounds;
- compute only the preregistered calibration observations/measures required by the frozen acceptance rule;
- freeze the calibration result without adding concepts, candidates, variants, windows, measures, or thresholds after outcome access begins.

Calibration completion never directly authorizes general implementation or sets `SPEC_READY`.

## Protected execution boundaries

- Calibration holdout, OOS, and CONFIRM require their explicit one-time access gates.
- Paper execution requires explicit owner authorization.
- Live execution may never be autonomously enabled.
- Live brokerage endpoints must remain technically blocked.

## Stop behavior

When semantics cannot be closed from first-party evidence, emit `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE` and create a bounded recovery issue if appropriate.

When an authorized calibration cannot select a convention under its frozen acceptance rule, emit a fail-closed calibration state rather than changing the preregistration after outcomes are visible.

Escalate only for the reasons enumerated in `PROJECT_BIBLE.md`.
