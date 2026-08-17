# Roadmap — Closed

The current Arjo Trading Engine project lifecycle is complete.

Terminal gate: `PROJECT_CLOSED_EXISTING_EVIDENCE`.

The owner chose on **2026-08-17** to close the project using the evidence already acquired and sealed rather than keep completion blocked on a future untouched-validation window.

## Completed lifecycle

### Governance, source recovery and evidence synthesis

Complete:
- `GOVERNANCE_BOOTSTRAP_COMPLETE`
- `SOURCE_UNIVERSE_DISCOVERED`
- `ACQUISITION_TOOLING_READY`
- `CORPUS_ACQUIRED`
- `CONCEPT_INVENTORY_READY`
- `EVIDENCE_REGISTRY_READY`
- `PREDICATE_MATRIX_READY`

### V1 calibration and reconstruction

Complete:
- `CALIBRATION_PROTOCOL_READY`
- `SEMANTIC_SEED_READY`
- `CALIBRATION_AUTHORIZED`
- `CALIBRATION_PREREGISTRATION_COMPLETE`
- `CALIBRATION_DATA_PIPELINE_READY`
- `CALIBRATION_REPLAY_HARNESS_READY`
- `CALIBRATION_DATA_READY`
- `CALIBRATION_OCCURRENCES_READY`
- `CALIBRATED_SPEC_FROZEN`
- `SPEC_READY`

### V1 protected validation

Complete:
- `PROTECTED_VALIDATION_PROTOCOL_FROZEN`
- `PROTECTED_VALIDATION_COMPLETE`

Result: `VALIDATION_INTEGRITY_FAILURE`.

The protected 2026H1 test exposed that V1 could qualify `SECOND_STING_TOUCH` when the touch price was outside the designated second-sting 15-minute bar. V1 was not refit and is not execution eligible.

### V2 remediation and deterministic reconstruction

Complete:
- `V2_REMEDIATION_DESIGN_READY`
- `V2_SPEC_FROZEN`
- `V2_FUTURE_VALIDATION_PROTOCOL_READY`
- `V2_CAUSAL_VALIDATION_PROTOCOL_READY`
- `V2_EXECUTION_MEASUREMENT_READY`
- `V2_FUTURE_VALIDATION_HARNESS_READY`

V2 fixes the execution-observability defect and freezes deterministic M1 sequencing without converting that sequencing policy into an Arjo semantic claim.

## Project closure

Complete:
- `PROJECT_CLOSED_EXISTING_EVIDENCE`

Final scientific interpretation:

- deterministic research implementation: complete;
- V1 protected validation: failed on execution integrity;
- V2 mechanical remediation: complete;
- V2 untouched future validation: not performed;
- validated profitable edge: not established;
- paper/live/broker authorization: not granted.

See [`FINAL_DISPOSITION.md`](FINAL_DISPOSITION.md).

## Optional future work — not part of this roadmap

The frozen V2 future-validation workflow remains available as optional later research infrastructure. Issue #201 is closed as `not planned` for this project version.

If the project is revisited later, future validation must be treated as a new/reopened extension and must not retroactively change the existing-evidence closure record.

There is no remaining active implementation phase in the current roadmap.
