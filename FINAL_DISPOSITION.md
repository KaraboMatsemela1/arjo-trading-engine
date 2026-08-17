# Final Project Disposition

## Status

`DEVELOPMENT_COMPLETE_VALIDATION_DEFERRED`

The Arjo Trading Engine is wrapped on the best currently available, frozen V2 research state. All engineering required to discover evidence, construct deterministic rules, calibrate the governed owner-operational profile, independently reconstruct it, expose the V1 execution-integrity defect, remediate that defect in V2, and build deterministic evaluation tooling is complete.

The project is **not waiting for a future date in order to be considered complete as an engineering/research build**.

Future untouched validation is preserved as an optional scientific follow-up. It is not part of the current completion definition.

## Current retained research artifact

Frozen profile:

```text
ARJO_DERIVED_OWNER_OPERATIONAL_V2
87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6
```

Supporting frozen bindings:

```text
Causal future-validation protocol
193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38

M1 execution-measurement policy
6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6

Future OANDA request contract
edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca

Future-validation harness readiness
8b4640018db1226dae10bd440e5abb20f60958b47882cb7f2cddb69c7f7add79
```

`SPEC_READY=true` means the frozen research specification is deterministic and independently reconstructable under the repository's governed evidence/configuration boundaries. It does **not** mean the strategy has been proven profitable or future-validated.

## V1 disposition

V1 reached protected validation and produced `VALIDATION_INTEGRITY_FAILURE`.

The defect was structural: `SECOND_STING_TOUCH` could be semantically qualified while the frozen touch price was outside the designated second-sting 15-minute bar. V1 was not refit and is not execution eligible.

The consumed 2026H1 protected interval remains one-way evidence. It must not be reused as V2 tuning or future-validation evidence.

## V2 remediation retained

V2 preserves the strategy/research specification while adding fail-closed execution observability:

```text
second_sting_bar.low <= touch_price <= second_sting_bar.high
```

- true: `EXECUTABLE_ENTRY`
- false: `NO_EXECUTABLE_ENTRY`
- no synthetic/fallback fill when the touch is not observable

The frozen M1 sequencing policy then determines observable event order without inventing intrabar OHLC ordering.

## What is usable now

The repository may be used now as:

- a reproducible research implementation of the frozen V2 profile;
- a deterministic replay/reference implementation on data that is legally permitted for development/reproduction;
- a code and research baseline for future revisions;
- a sealed starting point if a later untouched validation is desired.

The repository must **not** be represented as having passed untouched V2 future validation.

No claim of profitability, robustness, production readiness, or execution qualification is created by this wrap-up.

## Deferred optional future validation

The prebuilt workflow remains preserved at:

```text
.github/workflows/v2-future-validation-execution.yml
```

Its frozen untouched design is still available if the project is revisited later:

```text
Acquisition:        [2026-09-01, 2027-03-01)
Bootstrap:          [2026-09-01, 2026-10-01) — unscored
Scored validation:  [2026-10-01, 2027-03-01)
Earliest full read: 2027-03-01T00:00:00Z
```

The workflow is intentionally not executed as part of current project completion. If it is run in the future, the frozen chronology, SHA bindings, no-refit rule, single-shot data-access rule, and owner authorization remain binding.

Closing/defering the old future-validation issue does **not** assert `V2_FUTURE_VALIDATION_COMPLETE`.

## Execution permissions at wrap

```text
PAPER_EXECUTION_ENABLED = false
LIVE_TRADING_AUTHORIZED = false
BROKER_MUTATION          = false
```

Those permissions are outside this research wrap and require separate explicit owner authorization/lifecycle work if ever desired.

## Re-entry rule

The repository can be reopened later for one of three legitimate reasons:

1. run the preserved untouched future validation;
2. add genuinely new first-party evidence and intentionally version a new strategy profile;
3. start a separately authorized paper/execution qualification lifecycle.

Any such work must create a new bounded issue/lifecycle rather than silently rewriting this final V2 disposition.
