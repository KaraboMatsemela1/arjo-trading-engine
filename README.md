# Arjo Trading Engine

Research-grade, evidence-first project for translating Arjo's public first-party trading education into deterministic, machine-replayable research specifications.

> **Project status:** `PROJECT_CLOSED_EXISTING_EVIDENCE`
>
> **Research / engineering scope:** complete
>
> **SPEC_READY:** `true` for the frozen deterministic V2 research profile
>
> **Validated profitable edge:** **not established**
>
> **Paper execution:** `false` · **Live execution:** `false` · **Broker mutation:** `false`

## Final disposition

The project was closed on **2026-08-17** using the evidence already acquired and sealed. The owner explicitly chose not to keep project completion blocked on a future validation window.

The complete closure record is in [`FINAL_DISPOSITION.md`](FINAL_DISPOSITION.md).

### V1 result

`ARJO_DERIVED_OWNER_OPERATIONAL_V1` completed calibration, independent reconstruction and one-time protected 2026H1 validation.

That protected test produced `VALIDATION_INTEGRITY_FAILURE`: a `SECOND_STING_TOUCH` could be semantically qualified while the frozen touch price was outside the designated second-sting 15-minute bar.

V1 was not refit and is not execution eligible.

### V2 result

`ARJO_DERIVED_OWNER_OPERATIONAL_V2` remediates the V1 execution-integrity defect by requiring observable 15-minute touch containment and a separate deterministic M1 sequencing policy.

V2's specification, independent reconstruction, causal initialization design, execution-measurement policy and guarded future-validation harness are complete and frozen.

V2 was **not** evaluated on the previously reserved future window before project closure. Therefore this repository does not claim V2 is externally validated, profitable, paper-qualified or live-ready.

## Final scientific conclusion

The project successfully converted the available evidence into deterministic research artifacts and used protected validation to expose a genuine execution-integrity defect. The defect was mechanically remediated in V2.

Using the evidence currently available, however, a **validated trading edge has not been established**.

That is the final conclusion of the current project version.

## Frozen V2 execution integrity

The 15-minute observability rule is:

```text
second_sting_bar.low <= touch_price <= second_sting_bar.high
```

- true → `EXECUTABLE_ENTRY`
- false → `NO_EXECUTABLE_ENTRY`
- no fallback fill, interpolation or synthetic fill is allowed.

Minute-level event sequencing is separately frozen as an execution-measurement policy, not an Arjo semantic claim.

## Data-source boundary

The owner-directed provider is OANDA V20 practice `NAS100_USD`, MID prices.

`NAS100_USD` is explicitly treated as an **OANDA Nasdaq-100 CFD proxy/source for the locked NQ research seed**. The repository does not claim it is literal CME NQ futures or venue-equivalent to CME data.

## Optional future extension

The previously built future-validation workflow remains in the repository as optional later research infrastructure:

```text
.github/workflows/v2-future-validation-execution.yml
```

Issue #201 was closed as `not planned` for the current lifecycle. Running that workflow later would be a new/reopened validation extension; it is no longer a prerequisite for declaring this project complete.

## Objective lifecycle

```text
Evidence / calibration / reconstruction                    COMPLETE
SPEC_READY                                                  COMPLETE
V1 PROTECTED_VALIDATION_COMPLETE                           COMPLETE — integrity failure, no refit
V2_REMEDIATION_DESIGN_READY                                COMPLETE
V2_SPEC_FROZEN                                             COMPLETE
V2_CAUSAL_VALIDATION_PROTOCOL_READY                        COMPLETE
V2_EXECUTION_MEASUREMENT_READY                             COMPLETE
V2_FUTURE_VALIDATION_HARNESS_READY                         COMPLETE
PROJECT_CLOSED_EXISTING_EVIDENCE                           COMPLETE
OPTIONAL V2 FUTURE VALIDATION                              NOT PERFORMED / NOT REQUIRED
PAPER_EXECUTION_ENABLED                                    false
LIVE_TRADING_AUTHORIZED                                    false
```

## Canonical control

- GitHub Issues are the historical execution queue.
- Issue #1 is the canonical lifecycle tracker.
- `PROJECT_BIBLE.md` remains the highest repository governance authority.
- `FINAL_DISPOSITION.md` records the closure conclusion.
- `project_state.json` and `STATUS.md` are mechanically generated lifecycle state.

## Core safety rule

Project closure is not trading authorization. No missing semantics are filled by generic ICT/SMC assumptions, no validation result is retroactively refit, and no paper/live execution is enabled by this closure.
