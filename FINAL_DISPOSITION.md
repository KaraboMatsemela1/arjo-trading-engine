# Arjo Trading Engine — Final Disposition

**Closure basis:** existing acquired and sealed evidence as of 2026-08-17.

## Final status

The current Arjo Trading Engine research and engineering project is **complete and closed**.

Terminal gate: `PROJECT_CLOSED_EXISTING_EVIDENCE`.

This is a project-completion statement, **not** a claim that the strategy has a validated profitable edge.

## What the evidence establishes

### V1

The V1 owner-operational profile completed calibration, independent reconstruction and a one-time protected 2026H1 validation.

The protected validation result was `VALIDATION_INTEGRITY_FAILURE`: the frozen `SECOND_STING_TOUCH` could qualify while the touch price was outside the designated second-sting 15-minute bar. V1 was not refit and is not execution eligible.

### V2

V2 fixed that execution-integrity defect by separating semantic qualification from observable execution and by adding deterministic minute-level sequencing. Its profile, independent reconstruction, causal bootstrap design, M1 measurement policy and guarded validation harness are complete and frozen.

V2 has **not** been evaluated on the previously reserved future validation window. Therefore the project does not claim that V2 is externally validated, profitable, paper-qualified or live-ready.

## Final scientific conclusion

The project successfully translated the available first-party/owner-governed material into deterministic research artifacts and exposed a real execution-integrity defect through protected validation. The remediation is mechanically complete.

However, using the evidence currently available, a **validated trading edge has not been established**.

That is the final research conclusion for this project version.

## Optional future extension

The frozen future-validation workflow and protocol remain in the repository for optional later research. Issue #201 was retired from the current critical path by owner decision on 2026-08-17.

If the project is revisited later, that work must be treated as a new/reopened validation extension and must not retroactively change this closure record.

## Safety / execution state

- `SPEC_READY`: true for deterministic research implementation.
- `PAPER_EXECUTION_ENABLED`: false.
- `LIVE_TRADING_AUTHORIZED`: false.
- Broker mutation: false.
- No profitability or production-readiness claim is implied by project closure.

## Frozen V2 identifiers retained for reproducibility

- profile: `ARJO_DERIVED_OWNER_OPERATIONAL_V2`
- profile SHA: `87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6`
- causal protocol SHA: `193beab06f415d1117e79ce6142ef13f5ce67f3448b4be44c025ffdd00142d38`
- M1 sequencing policy SHA: `6de757b7957a48c85b72e215c986defee5aebca4e317f3f839b04b47cdf064d6`
- future OANDA request contract SHA: `edf42c53bbfd0bf222ff7eb43b85aa8a4b8d2dfd38a443732d1aa1cbecc17eca`
- future-validation harness readiness SHA: `8b4640018db1226dae10bd440e5abb20f60958b47882cb7f2cddb69c7f7add79`

## Data-source boundary

OANDA V20 practice `NAS100_USD` MID data is treated as an OANDA Nasdaq-100 CFD proxy/source for the locked NQ research seed. The repository does not claim venue or price-series equivalence with CME NQ futures.
