# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-replayable specifications and evaluating them scientifically.

> **Current lifecycle state:** development complete; untouched V2 future validation pending chronology
>
> **SPEC_READY:** `true` for the frozen owner-operational V2 research profile
>
> **V2_FUTURE_VALIDATION_HARNESS_READY:** `true`
>
> **Current objective gate:** `V2_FUTURE_VALIDATION_COMPLETE`
>
> **Paper execution:** `false` · **Live execution:** `false` · **Broker mutation:** `false`

## Current project state

All research engineering, calibration infrastructure, V1 protected-validation analysis, V2 remediation, independent reconstruction, causal initialization, execution measurement, and final validation tooling that can legally be completed before the untouched future window is complete.

The only substantive unfinished task is GitHub Issue **#201**: execute the sealed V2 future validation after **2027-03-01T00:00:00Z**. The remaining delay is an intentional protected-data chronology boundary, not an engineering backlog.

No reserved V2 validation market data from `2026-09-01` onward has been requested or read.

## What happened to V1

The calibrated profile `ARJO_DERIVED_OWNER_OPERATIONAL_V1` reached independent `SPEC_READY` reconstruction and was then evaluated once on the protected 2026H1 interval.

That untouched validation exposed an execution-integrity defect: the only qualified occurrence required `SECOND_STING_TOUCH`, but its frozen touch price lay outside the designated second-sting 15-minute bar. The result was sealed as `VALIDATION_INTEGRITY_FAILURE`.

V1 was **not refit**, is not execution eligible, and the consumed 2026H1 data/state may not be reused for V2 tuning or validation.

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

The owner-directed data source is OANDA V20 practice `NAS100_USD`, MID prices.

`NAS100_USD` is explicitly treated as an **OANDA Nasdaq-100 CFD proxy/source for the locked NQ research seed**. The repository does not claim that this OANDA series is literal CME NQ futures or venue-equivalent to CME data.

## Final untouched validation

The final workflow is already implemented:

```text
.github/workflows/v2-future-validation-execution.yml
```

The harness is deliberately stricter than a rolling validation process. It implements **one full-window acquisition only after the complete window has closed**.

### Frozen chronology

```text
Acquisition interval:  [2026-09-01, 2027-03-01)
Causal bootstrap:      [2026-09-01, 2026-10-01)  unscored
Scored validation:     [2026-10-01, 2027-03-01)
Earliest execution:     2027-03-01T00:00:00Z
```

State begins EMPTY on September 1. September is used only to build causal FVG/pivot/internal state. Bootstrap outcomes and performance are not scored or inspected. No pre-September state snapshot, no pre-start market data, and no V1 2026H1 carry-in may seed V2.

After March 1, the repository owner must explicitly dispatch the final workflow with the exact phrase:

```text
AUTHORIZE_V2_FUTURE_VALIDATION
```

That authorization is bounded to research data acquisition/evaluation. It does **not** authorize paper trading, live trading, or broker mutation.

## Final validation execution path

Once the chronology and owner-dispatch gates are both satisfied, the prebuilt workflow will:

1. validate every frozen SHA and authorization boundary;
2. acquire OANDA `NAS100_USD` MID M1 read-only for the exact full window;
3. normalize complete 15m / 60m / 240m buckets;
4. initialize empty state and process September bootstrap causally;
5. score October through February;
6. run the production semantic/evaluation path;
7. run the isolated independent standard-library path;
8. apply the frozen 15m observability and M1 sequencing policies;
9. compare all critical outputs exactly;
10. compute the preregistered metrics/classification;
11. SHA-seal the final validation result and evidence artifact.

The inferential threshold remains frozen at **30 resolved executable occurrences**. A smaller sample is reported as `INSUFFICIENT_SAMPLE`; the rules or window are not widened afterward.

## Objective lifecycle

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
V2_FUTURE_VALIDATION_COMPLETE                              PENDING — Issue #201 / March 2027
PAPER_EXECUTION_ENABLED                                    false
LIVE_TRADING_AUTHORIZED                                    false
```

Progress is represented by objective gates rather than arbitrary percentages.

## Canonical control

- GitHub Issues are the execution queue.
- Issue #1 is the canonical lifecycle tracker.
- `PROJECT_BIBLE.md` is the highest repository governance authority.
- Frozen specs/protocols/policies and their SHA bindings govern executable research work.
- `project_state.json` is mechanically generated state.
- `STATUS.md` is its human-readable summary.
- No agent may maintain a hidden competing roadmap.

## Core safety rule

Evidence before code. Missing semantics are not filled by generic ICT/SMC assumptions, validation data is not used to refit the profile, and no paper/live execution is enabled by research completion.
