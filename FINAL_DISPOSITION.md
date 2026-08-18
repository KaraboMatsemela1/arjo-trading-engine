# Final Project Disposition

## Terminal status

`POST_V4_CURRENT_EVIDENCE_RESEARCH_BOUNDARY_READY`

Completion basis:

`POST_V4_CURRENT_EVIDENCE_NO_VALIDATED_PROFITABLE_EDGE`

The Arjo Trading Engine current research and engineering lifecycle is complete. The repository now records the full governed path from first-party source discovery and evidence extraction through deterministic specification, protected validation, V2 remediation, backward historical profitability research, V3 strategy-family testing, V4 Sharp Turn testing, and the final post-V4 evidence boundary.

There is no remaining dependency-satisfied engineering or research backlog in the current lifecycle.

This is a successful project-completion state, but it is **not** a successful profitability result. Using the currently admitted evidence and preregistered execution rules, a validated profitable trading edge has not been established.

## Scientific disposition

### V1 — protected validation exposed an integrity defect

V1 reached `SPEC_READY` and was evaluated once on the protected 2026H1 holdout. The result was `VALIDATION_INTEGRITY_FAILURE` because the frozen `SECOND_STING_TOUCH` event could be semantically qualified while the required touch price was outside the designated second-sting 15-minute bar.

V1 was not refit after observing the protected result and is not execution eligible. The consumed 2026H1 interval remains one-way evidence and must not be reused for tuning or replacement-profile validation.

### V2 — execution observability remediated and frozen

V2 preserved the research semantics while adding fail-closed execution observability:

```text
second_sting_bar.low <= touch_price <= second_sting_bar.high
```

- true: `EXECUTABLE_ENTRY`
- false: `NO_EXECUTABLE_ENTRY`
- no synthetic or fallback fill when the touch is not observable

Frozen V2 profile:

```text
ARJO_DERIVED_OWNER_OPERATIONAL_V2
87a20345a10efacac287ff0becf0f618b721af745715cbd77c51ca7308aa67d6
```

Supporting bindings remain preserved:

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

V2 backward historical occurrence scanning found only 10 executable occurrences from 2010-2023 against a preregistered minimum of 30. The V2 economic-outcome stage therefore remained closed and the result was classified `INSUFFICIENT_SAMPLE_EDGE_NOT_ESTABLISHED`.

### V3 — broader coverage did not establish an edge

V3-A relaxed only the project-invented geometric overlap condition while preserving the remaining frozen predicates. It produced four execution-observable development occurrences against a minimum of 30 and was rejected outcome-blind.

V3-B transferred the unchanged V2 strategy across the fixed NAS100/SPX500/US30 set. It produced one executable portfolio occurrence and was also rejected outcome-blind.

V3-C tested the independently frozen 4h Swing High -> 1h 2CR-failure family with adequate historical sample size. The sealed 2010-2023 M1 BID/ASK result was `EDGE_NOT_ESTABLISHED`:

```text
Base resolved trades: 1304
Base expectancy:      +0.0013801963R/trade
Base profit factor:   1.0025647240
Base 95% CI:          [-0.0642641976R, +0.0645586741R]

Stress expectancy:    -0.0446837654R/trade
Stress profit factor: 0.9198829599
```

The result was not tuned after observation.

### V4 — Sharp Turn / FVG family also failed the frozen economic gate

Materially new public first-party evidence allowed a separate V4 Sharp Turn / FVG family to be recovered and independently preregistered without consulting V3-C outcomes for parameter selection.

The frozen V4 historical measurement used the sealed 2010-2023 trigger set and M1 BID/ASK economics. It also returned `EDGE_NOT_ESTABLISHED`:

```text
Base resolved trades: 127
Base expectancy:      +0.0014091678R/trade
Base profit factor:   1.0020664
Base win rate:        35.4331%
Base 95% CI:          [-0.2424640R, +0.2545526R]
Base max drawdown:    18.1676R

Stress expectancy:    -0.1063928393R/trade
Stress profit factor: 0.8554421
Stress win rate:      33.8583%
Stress 95% CI:        [-0.3458839R, +0.1483883R]
Stress max drawdown:  23.0660R
```

The V4 result SHA is:

```text
611cc822dcc5103ed700d245e3ffb95404ca9c41459a43f9b5183aa84aedf6b5
```

No V4 parameter tuning, consumed-ledger mining, predicate weakening, or generic ICT/SMC semantic backfill is permitted from this result.

## Post-V4 evidence boundary

The final outcome-blind candidate re-audit reviewed 36 admitted concepts. The remaining Phase-5 candidates are still semantically incomplete and no unused deterministic executable first-party family is available in the current evidence set.

New strategy research may begin only when at least one of the following is true:

1. genuinely new attributable Arjo first-party semantic evidence closes an incomplete strategy family;
2. another genuinely independent family is fully preregistered before outcome access;
3. the preserved untouched V2 future-validation lifecycle is intentionally reopened under its original no-refit and single-shot rules.

Post-result tuning of V3-C or V4, mining their consumed ledgers to create replacement predicates, silently relabelling owner conventions as source semantics, or filling gaps with generic ICT/SMC knowledge are prohibited.

## Optional future V2 validation

The sealed workflow remains preserved at:

```text
.github/workflows/v2-future-validation-execution.yml
```

Its frozen untouched design is not part of the current project critical path:

```text
Acquisition:        [2026-09-01, 2027-03-01)
Bootstrap:          [2026-09-01, 2026-10-01) — unscored
Scored validation:  [2026-10-01, 2027-03-01)
Earliest full read: 2027-03-01T00:00:00Z
```

Closing the current lifecycle does not assert `V2_FUTURE_VALIDATION_COMPLETE`.

## Execution permissions at closure

```text
SPEC_READY              = true
PAPER_EXECUTION_ENABLED = false
LIVE_TRADING_AUTHORIZED = false
BROKER_MUTATION          = false
```

`SPEC_READY=true` means deterministic and independently reconstructable research specification. It does not mean profitable, robust, production-ready, or execution-qualified.

## What the repository is now

The repository is a completed, auditable research system containing:

- provenance-bound first-party evidence and semantic boundaries;
- deterministic strategy specifications and independent reconstruction paths;
- protected-validation and backward historical research machinery;
- realistic BID/ASK execution measurement and cost stress;
- immutable failed-result records that prevent post-hoc rewriting;
- an optional untouched future-validation harness;
- explicit fail-closed paper/live/broker authorization gates.

The current Arjo research lifecycle is therefore formally closed at the post-V4 evidence boundary.