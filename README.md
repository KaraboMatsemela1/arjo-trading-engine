# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-replayable specifications and evaluating them scientifically.

> **Current lifecycle state:** `DEVELOPMENT_COMPLETE_VALIDATION_DEFERRED`
>
> **SPEC_READY:** `true` for the frozen owner-operational V2 research profile
>
> **Project engineering:** complete
>
> **Untouched V2 future validation:** deferred / optional follow-up
>
> **Paper execution:** `false` · **Live execution:** `false` · **Broker mutation:** `false`

## Final project state

The repository is wrapped on the best current frozen V2 research state. Evidence acquisition, concept inventory, atomic evidence, predicate synthesis, governed calibration, independent reconstruction, V1 protected validation, V2 remediation, causal protocol design, M1 execution measurement, and the optional future-validation harness are implemented.

The project is no longer considered incomplete merely because a future untouched market-data window has not yet closed.

The final disposition is recorded in `FINAL_DISPOSITION.md`.

## What happened to V1

The calibrated profile `ARJO_DERIVED_OWNER_OPERATIONAL_V1` reached independent `SPEC_READY` reconstruction and was evaluated once on the protected 2026H1 interval.

That untouched validation exposed an execution-integrity defect: the only qualified occurrence required `SECOND_STING_TOUCH`, but its frozen touch price lay outside the designated second-sting 15-minute bar. The result was sealed as `VALIDATION_INTEGRITY_FAILURE`.

V1 was **not refit**, is not execution eligible, and the consumed 2026H1 data/state may not be reused for V2 tuning or future validation.

## Frozen V2 research profile

V2 preserves the disclosed owner-operational semantic boundaries and adds fail-closed execution integrity.

The frozen 15-minute observability rule is:

```text
second_sting_bar.low <= touch_price <= second_sting_bar.high
```

- true → `EXECUTABLE_ENTRY`
- false → `NO_EXECUTABLE_ENTRY`
- no fallback fill, interpolation, synthetic fill, or target/stop outcome when no executable entry exists.

Minute-level event sequencing is separately frozen as an **execution measurement policy**, not an Arjo semantic claim:

- exactly 15 complete OANDA M1 candles must cover the second-sting interval;
- earliest M1 candle containing the touch is the observed entry minute;
- missing M1 touch after 15m observability → validation integrity failure;
- stop or target in the entry minute → `AMBIGUOUS_INTRABAR_ORDER`;
- later M1 stop+target in the same minute → ambiguous;
- later stop only → `STOP_FIRST`;
- later target only → `TARGET_FIRST`;
- no later event by validation end → `UNRESOLVED_WINDOW_END`.

## Frozen V2 bindings

```text
Profile
ARJO_DERIVED_OWNER_OPERATIONAL_V2
87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6

Causal future-validation protocol
ARJO_V2_FUTURE_VALIDATION_PROTOCOL_V2
193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38

M1 execution-measurement policy
V2_M1_TOUCH_SEQUENCING_V1
6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6

Future OANDA request contract
edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca

Future-validation harness readiness
8b4640018db1226dae10bd440e5abb20f60958b47882cb7f2cddb69c7f7add79
```

## Market-data identity

The owner-directed development/calibration data source is OANDA V20 practice `NAS100_USD`, MID prices.

`NAS100_USD` is explicitly treated as an **OANDA Nasdaq-100 CFD proxy/source for the locked NQ research seed**. The repository does not claim that this OANDA series is literal CME NQ futures or venue-equivalent to CME data.

## What the current project can be used for

The frozen V2 repository is now the retained research baseline. It may be used for deterministic code review, reproducible research/replay on permitted datasets, comparison against future revisions, and later scientific validation.

`SPEC_READY=true` means the research specification is deterministic and independently reconstructable under the project's governed evidence/configuration boundaries. It does **not** mean the strategy is proven profitable, robust, or production-ready.

## Optional future untouched validation

The sealed workflow remains implemented at:

```text
.github/workflows/v2-future-validation-execution.yml
```

The original frozen untouched protocol remains preserved for a possible future revisit:

```text
Acquisition interval:  [2026-09-01, 2027-03-01)
Causal bootstrap:      [2026-09-01, 2026-10-01)  unscored
Scored validation:     [2026-10-01, 2027-03-01)
Earliest full read:     2027-03-01T00:00:00Z
```

The current project wrap does **not** execute that workflow and does **not** assert `V2_FUTURE_VALIDATION_COMPLETE`.

If the validation is revisited later, the frozen chronology, single-shot access rule, SHA bindings, no-refit policy, and explicit owner authorization remain binding.

The inferential threshold remains frozen at **30 resolved executable occurrences**. A smaller future sample would be reported as `INSUFFICIENT_SAMPLE`; rules or windows are not widened afterward.

## Objective lifecycle at wrap

```text
V1 evidence / calibration / reconstruction                  COMPLETE
SPEC_READY                                                  COMPLETE
V1 PROTECTED_VALIDATION_PROTOCOL_FROZEN                    COMPLETE
V1 PROTECTED_VALIDATION_COMPLETE                           COMPLETE — integrity failure, no refit
V2_REMEDIATION_DESIGN_READY                                COMPLETE
V2_SPEC_FROZEN                                             COMPLETE
V2_FUTURE_VALIDATION_PROTOCOL_READY                        COMPLETE
V2_CAUSAL_VALIDATION_PROTOCOL_READY                        COMPLETE
V2_EXECUTION_MEASUREMENT_READY                             COMPLETE
V2_FUTURE_VALIDATION_HARNESS_READY                         COMPLETE
PROJECT_ENGINEERING                                        COMPLETE
V2_FUTURE_VALIDATION_COMPLETE                              DEFERRED / NOT ASSERTED
PAPER_EXECUTION_ENABLED                                    false
LIVE_TRADING_AUTHORIZED                                    false
BROKER_MUTATION                                            false
```

## Canonical control

- `PROJECT_BIBLE.md` remains the highest repository governance authority.
- `FINAL_DISPOSITION.md` records the current project wrap and re-entry boundaries.
- GitHub Issues remain the execution queue if the project is reopened later.
- Frozen specs/protocols/policies and their SHA bindings remain immutable historical research artifacts.
- No paper/live execution permission is created by project completion.

## Core safety rule

Evidence before code. Missing semantics are not filled by generic ICT/SMC assumptions, consumed protected data is not reused to refit the profile, and research completion does not authorize paper/live execution.
