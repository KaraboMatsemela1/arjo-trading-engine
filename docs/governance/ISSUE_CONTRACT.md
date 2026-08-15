# GitHub Issue Execution Contract

Every execution issue must contain exactly one machine-readable metadata block:

```text
<!-- project-meta
ISSUE_ID: ARJO-000
TYPE: GOVERNANCE
DEPENDENCIES: []
ENTRY_GATE: REPO_CREATED
OUTPUT_GATE: EXAMPLE_GATE
OWNER: UNCLAIMED
STATE: READY
-->
```

## Required fields

- `ISSUE_ID` — stable project identifier; never reuse.
- `TYPE` — bounded work category.
- `DEPENDENCIES` — JSON array of GitHub issue numbers.
- `ENTRY_GATE` — gate that must already be satisfied before execution.
- `OUTPUT_GATE` — gate produced when the issue completes, or `NONE`.
- `OWNER` — `UNCLAIMED` or the active agent/user identifier.
- `STATE` — one of the allowed states below.

## Allowed states

`BLOCKED`, `READY`, `CLAIMED`, `IMPLEMENTING`, `CI_PENDING`, `REVIEW_PENDING`, `COMPLETE`

## State transition rules

- `BLOCKED → READY` only when dependencies and entry gate are satisfied.
- `READY → CLAIMED` only after claim checks pass.
- `CLAIMED → IMPLEMENTING` when work begins.
- `IMPLEMENTING → CI_PENDING` when a PR is awaiting CI.
- `CI_PENDING → REVIEW_PENDING` when required CI passes and review remains.
- `CI_PENDING → IMPLEMENTING` when CI fails and repair begins.
- `REVIEW_PENDING → IMPLEMENTING` when review requests changes.
- `REVIEW_PENDING → COMPLETE` only after safe merge and output verification.
- Any state may transition to `BLOCKED` only with an explicit blocker reason.

## Dependency semantics

A dependency is satisfied only when the referenced issue metadata state is `COMPLETE` or the issue is closed with a project-complete disposition. Merely having an open PR or pending CI does not satisfy a dependency.

## Claim invariant

At most two active claims may exist: one externally waiting lane (`CI_PENDING` or `REVIEW_PENDING`) and one active implementation lane (`CLAIMED` or `IMPLEMENTING`). Two simultaneously implementing claims are invalid unless the governance contract is explicitly versioned by owner decision.

## Master issue

The canonical master lifecycle issue is a dashboard and index. Child issue metadata remains authoritative for task state; the master issue must not invent a competing state model.
