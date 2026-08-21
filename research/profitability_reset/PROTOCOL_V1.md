# Profitability Research Reset Protocol V1

Status: **FROZEN BEFORE R1 ECONOMIC OUTCOMES**

Issue: #298

## Purpose

Re-enter research after the V3-C–V8 no-edge boundary with a methodology designed to find a **genuine cost-adjusted out-of-sample edge**, not to force positive historical results.

A positive backtest is not the objective by itself. Promotion requires profitability that survives chronological separation, realistic execution costs, stress, statistical uncertainty, multiple-testing correction, calendar/regime stability, and a sealed confirmation interval.

If no candidate satisfies the frozen gates, the correct project result is `NO_EDGE_FOUND_RESET_V1`.

## Independence boundary

Consumed V3-C–V8 economic outcomes are quarantined.

They may be used only for:
- the consolidated historical report;
- benchmarking the research process and backtester integrity.

They may **not** select or modify:
- candidate strategy family;
- entry/exit predicates;
- session window;
- target or stop;
- cost assumptions;
- filters;
- parameter grid;
- sample/promotion thresholds.

No reactive V9 derived from the best or least-bad failed ledger is permitted.

## Preregistered R1 family universe

The initial reset is limited to **12 configurations total** across the following independently motivated families.

### Family A — Timely Opening Range Breakout / opening momentum

Source anchor: Tsai et al. (2019), *Assessing the Profitability of Timely Opening Range Breakout on Index Futures Markets*, IEEE Access 7, DOI `10.1109/ACCESS.2019.2899177`.

The source uses one-minute index-futures data, defines resistance/support from an observed opening period, enters on the subsequent break and exits at the active-session end. It reports early probing windows as strongest in the US index markets. The reset will replicate the family causally on provider BID/ASK data rather than copy source returns.

R1 allocation: **3 configurations maximum**.

### Family B — Intraday time-series momentum

Independent hypothesis: early-session directional return contains information about later-session directional return. All clock windows and execution rules must be frozen before associated outcomes are opened.

R1 allocation: **3 configurations maximum**.

### Family C — Medium-horizon time-series momentum

Source anchor: Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, Journal of Financial Economics 104(2), DOI `10.1016/j.jfineco.2011.11.003`.

The source documents own-past-return continuation across equity-index, currency, commodity and bond futures over intermediate horizons. Any Arjo implementation must use a finite preregistered horizon set and provider-correct economics.

R1 allocation: **4 configurations maximum**.

### Family D — Volatility-managed exposure overlay

Source anchor: Moreira & Muir (2017), *Volatility-Managed Portfolios*, Journal of Finance, DOI `10.1111/jofi.12513`.

This is a risk overlay only. It may scale a candidate whose unscaled signal already passes its selection gate; it may not rescue a negative-alpha signal or become a hidden parameter-search surface.

R1 allocation: **2 overlay configurations maximum**.

Total maximum configurations: **12**. The count includes every configuration whose economic outcome is examined. Failed or aborted outcome-bearing trials still consume budget.

## Multiple-testing control

For every run, persist:
- family ID;
- configuration ID;
- exact parameter payload hash;
- date/time of freeze;
- trial ordinal;
- data interval accessed;
- metrics opened.

No unconstrained optimizer, Bayesian optimizer, genetic search or broad grid search is permitted in R1.

Candidate significance must be adjusted for the number of attempted configurations. Where a Sharpe-like statistic is applicable, compute a Deflated-Sharpe-style adjustment informed by Bailey & López de Prado (2014), DOI `10.3905/jpm.2014.40.5.094`. Bootstrap confidence intervals remain mandatory and do not substitute for multiple-testing correction.

## Chronological design

Default R1 chronology:

- discovery / engineering: `[2010-01-01, 2019-01-01)`;
- walk-forward selection: `[2019-01-01, 2022-01-01)`;
- sealed family-level confirmation: `[2022-01-01, 2026-01-01)`.

The 2022–2025 interval is family-level sealed confirmation for this reset, **not a pristine project-wide holdout**, because this repository has previously consumed market data covering overlapping years for other families. Any successful label must disclose that limitation.

A genuinely fresh chronological confirmation after the research date remains mandatory before paper/live authorization.

## Data and execution requirements

- Provider identity must be explicit; proxy instruments may not be relabeled as literal exchange futures.
- MID may be used for causal signal formation only when frozen by the family protocol.
- Economic fills must use real BID/ASK where the provider exposes it.
- No synthetic bars, forward fills or favorable gap assumptions.
- Same-bar or sequencing ambiguity must resolve conservatively or fail closed according to the family protocol.
- Base and stress transaction-cost scenarios are mandatory.
- Credential values are never persisted.
- Paper/live/broker mutation remains disabled.

## Selection-stage minimum gate

Before a candidate can spend its family confirmation interval it must satisfy its family-specific sample gate plus all of:

- positive base expectancy in discovery;
- positive base expectancy in walk-forward;
- PF > 1.10 in both partitions;
- positive stressed expectancy in walk-forward;
- majority positive calendar years where meaningful;
- zero synthetic fills;
- zero unresolved data-integrity failures.

Family protocols may be stricter but not weaker after outcomes are opened.

## Historical-confirmation promotion gate

A candidate may receive `HISTORICALLY_PROFITABLE_EDGE_RESET_V1` only if its sealed 2022–2025 confirmation meets the family-specific gate and at minimum:

- adequate preregistered resolved sample;
- base expectancy > `+0.05R/trade` for trade-based families;
- base PF > `1.20`;
- bootstrap 95% expectancy lower bound > `0`;
- stress expectancy > `0`;
- stress PF > `1.10`;
- >=70% positive calendar years when there are enough years for the statistic to be meaningful;
- multiple-testing-adjusted evidence passes;
- zero integrity failures;
- zero synthetic fills;
- max drawdown within the family preregistered envelope.

The stronger label `VALIDATED_PROFITABLE_EDGE` is **not available** from R1 historical confirmation. It requires a separate genuinely fresh chronological confirmation.

## No-refit rule

Once a family/configuration first opens economic outcomes:
- its parameters cannot be changed and retested under the same configuration ID;
- a materially changed rule is a new configuration and consumes trial budget;
- once the sealed family confirmation is opened, no further parameter modification is permitted for that family result;
- a failed confirmation is a rejection, not a tuning dataset.

## R1 order of work

1. Freeze TORB causal replication.
2. Implement deterministic offline/synthetic tests and sabotage tests.
3. Acquire only discovery/walk-forward TORB data under the frozen provider contract.
4. Apply the preregistered TORB selection rule.
5. Open TORB sealed confirmation only if selection gate passes.
6. Continue to the next independent family if TORB fails, while preserving the finite 12-trial budget.

## Execution permissions

- `PAPER_EXECUTION_ENABLED=false`
- `LIVE_TRADING_AUTHORIZED=false`
- `BROKER_MUTATION=false`

A profitable historical result does not change these permissions.
