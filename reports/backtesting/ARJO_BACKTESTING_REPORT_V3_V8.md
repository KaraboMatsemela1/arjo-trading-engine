# Arjo Trading Engine — Consolidated Backtesting Report (V3-C through V8)

**Report basis:** canonical GitHub Actions artifacts and their base/stress trade ledgers. Historical test window is 2010–2023 for the economic runs summarized here. This report does not reinterpret failed results or tune any consumed strategy family.

## Executive conclusion

The backtesting machinery is producing reproducible, cost-aware results, but **none of V3-C through V8 establishes a profitable edge**. V3-C and V4 are effectively break-even before stress; every family is negative under stress. V5 demonstrates why win rate is not sufficient: it wins more than half its trades but loses money because winners are too small relative to losses.

The correct next step is a separately governed **profitability research reset**, not a reactive V9 tweak. The objective is to discover a candidate with positive out-of-sample expectancy, PF above the frozen threshold, a positive bootstrap lower bound, positive stressed economics, and acceptable drawdown. If no candidate passes those gates, the correct result remains `NO_EDGE` rather than manufacturing a profitable backtest.

## Canonical summary

| Strategy | Resolved | Base Exp. | Base PF | Win rate | Base max DD | 95% CI | Positive years | Stress Exp. | Stress PF | Stress max DD | Integrity failures |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| V3-C Arguments/2CR | 1,304 | +0.0014R | 1.003 | 42.5% | 48.8R | [-0.0643, +0.0646] | 57.1% | -0.0447R | 0.920 | 95.1R | 0 |
| V4 Sharp Turn | 127 | +0.0014R | 1.002 | 35.4% | 18.2R | [-0.2425, +0.2546] | 57.1% | -0.1064R | 0.855 | 23.1R | 0 |
| V5 No-Resistance AoO | 2,881 | -0.1033R | 0.433 | 55.3% | 301.8R | [-0.1205, -0.0865] | 0.0% | -0.1544R | 0.271 | 448.7R | 3 |
| V6 Momentum | 435 | -0.0815R | 0.897 | 24.6% | 77.9R | [-0.3035, +0.1636] | 28.6% | -0.1681R | 0.798 | 93.4R | 0 |
| V7 Candle Science | 3,637 | -0.2757R | 0.675 | 21.9% | 1033.4R | [-0.3444, -0.2050] | 7.1% | -0.3788R | 0.578 | 1374.5R | 3 |
| V8 FVG Follow-Through | 3,669 | -0.2344R | 0.638 | 39.4% | 876.2R | [-0.2769, -0.1909] | 0.0% | -0.3105R | 0.545 | 1140.6R | 2 |

## Equity curves

![Base cumulative R](assets/base_equity_curves.svg)

![Stress cumulative R](assets/stress_equity_curves.svg)

The raw cumulative-R curves make the scale of failure visible: V3-C and V4 finish approximately flat in base, while V5–V8 compound persistent negative expectancy over much larger trade counts. Under stress, even V3-C and V4 become negative.

### Closest candidates zoom

![Closest candidates](assets/closest_candidates_equity.svg)

## Drawdown

![Base drawdown curves](assets/base_drawdown_curves.svg)

The largest base drawdowns are V7 (~1,033R) and V8 (~876R). These are not deployable risk profiles. V3-C has a much smaller ~48.8R maximum drawdown, but its economics remain statistically indistinguishable from zero and fail under stress.

## Expectancy and profit factor

![Expectancy comparison](assets/expectancy_comparison.svg)

![Profit factor comparison](assets/profit_factor_comparison.svg)

Only V3-C and V4 have slightly positive base expectancy, and both have PF ≈ 1.00 — effectively break-even. Neither has a positive lower bootstrap confidence bound. Every stress PF is below 1.0.

## Win/loss distribution

![Trade R distribution](assets/trade_r_distribution.svg)

| Strategy | Wins | Losses | Win rate | Mean winner | Mean loser | Median trade |
|---|---:|---:|---:|---:|---:|---:|
| V3-C Arguments/2CR | 554 | 750 | 42.5% | +1.270R | -0.936R | -0.735R |
| V4 Sharp Turn | 45 | 82 | 35.4% | +1.929R | -1.056R | -1.013R |
| V5 No-Resistance AoO | 1,592 | 1,289 | 55.3% | +0.143R | -0.407R | +0.008R |
| V6 Momentum | 107 | 328 | 24.6% | +2.899R | -1.054R | -1.028R |
| V7 Candle Science | 795 | 2,842 | 21.9% | +2.617R | -1.085R | -1.036R |
| V8 FVG Follow-Through | 1,446 | 2,223 | 39.4% | +1.048R | -1.068R | -1.014R |

V5 is the clearest payoff-ratio warning: **55.3% wins**, but an average winner of only **+0.143R** against an average loser of **−0.407R**. V6 and V7 have low win rates but much larger winners; they still fail because the frequency and cost-adjusted payoff do not overcome losses.

## Calendar-year consistency

![Annual expectancy](assets/annual_expectancy.svg)

V3-C and V4 each have positive base expectancy in 8 of 14 calendar years (57.1%), but neither survives the full statistical and stress gates. V5 and V8 have zero positive calendar years; V7 has one; V6 has four.

## Evidence ranking — closest to an edge, not 'best backtest'

1. **V3-C Arguments/2CR** — Best evidence of near break-even economics: +0.0014R base expectancy over 1,304 trades and PF 1.003, but the CI crosses zero and stress falls to -0.0447R / PF 0.920.
2. **V4 Sharp Turn** — Also near break-even in base (+0.0014R, PF 1.002), but only 127 resolved trades and much wider uncertainty; stress is clearly negative.
3. **V6 Momentum** — PF 0.897 is the strongest sub-break-even PF among failed negative-base families; however expectancy is -0.0815R and only 4/14 years are positive.
4. **V5 No-Resistance AoO** — Large sample and 55.3% win rate, but poor payoff asymmetry produces -0.103R expectancy, PF 0.433 and zero positive years.
5. **V8 FVG Follow-Through** — Large sample but -0.234R expectancy, PF 0.638, zero positive years and two integrity failures.
6. **V7 Candle Science** — Worst cumulative loss and drawdown of the six; -0.276R expectancy, PF 0.675, only one positive year and three integrity failures.

This ranking is descriptive only. It must **not** be used to mine or retune consumed V3–V8 ledgers. That would create selection bias and violate the post-V8 governance boundary.

## Canonical provenance

| Strategy | Issue | Workflow run | Artifact | Artifact SHA-256 | Result SHA-256 |
|---|---:|---:|---:|---|---|
| V3-C Arguments/2CR | #232 | `32056095283` | `9296780777` | `354695de39745b789284e7ee0e18e031576fb48538ad8250877b3e2e78d03880` | `e2af05e4fad93def189bedd22cc865ea78be4ac43a1a2e9d5e5822c8b84ff78b` |
| V4 Sharp Turn | #247 | `32142106100` | `9326688249` | `d9b0423bec7a0f1e483a969b5dc52445814775397a2d44891af52b2a233683c5` | `611cc822dcc5103ed700d245e3ffb95404ca9c41459a43f9b5183aa84aedf6b5` |
| V5 No-Resistance AoO | #255 | `32154798217` | `9331836239` | `de5a23a252db3cf6e3b4de6a8f77fbd80c0a2f0aae33c44a93b92b80202e1ff0` | `4474926ae20e67d5e23010a62654d41d2a3f6cefbff835f7c122e011c64d7345` |
| V6 Momentum | #270 | `32168638822` | `9336642236` | `b3fab38ade6aa6f7c030a1d6bc8e57708ba44228a9e77276076872758e8e6897` | `4fcf249633f165250a99b602dd1cdd7bd20b07f6fbd27d09d1c8ee632a989fec` |
| V7 Candle Science | #280 | `32171459041` | `9337992406` | `79613fa5dad131722d3fe4ad0605f76ea12a61c09160733e5a819463ab15368b` | `9856cb07a6afe9c3d9bf1e611b1f614352c3f95e06b54be6841c5a614a93deaa` |
| V8 FVG Follow-Through | #290 | `32180745000` | `9341353565` | `8315a61860dc4fe68fdfef6792cf9cca7361bd8409bf5499c61f7c27018585f3` | `0bba2f2feb2f51cad8c89b31ff9102ffe107caafba1159d77151b9043e153f80` |

The downloaded ZIP SHA-256 values were recomputed locally and match the GitHub Actions artifact digests listed above.

## Path to genuine profitability

The next lifecycle should change the **research method**, not force the old strategies to pass. The recommended reset is:

1. Pre-register a finite, independent strategy universe before reading associated outcomes.
2. Separate discovery, model-selection, and sealed confirmation windows; use walk-forward evaluation inside discovery/selection.
3. Apply realistic BID/ASK, slippage, financing and conservative intrabar ordering from the current engine.
4. Control multiple testing (candidate budget + false-discovery / deflated-Sharpe-style correction) so a lucky backtest is not promoted.
5. Require minimum sample size and stability across years/regimes/instruments, not just aggregate P&L.
6. Promote only candidates with positive base and stress expectancy, PF comfortably above 1, positive bootstrap lower bound, and tolerable drawdown.
7. Keep a final confirmation slice sealed until the candidate and all thresholds are frozen.
8. If the confirmation fails, reject the candidate; do not tune against the holdout.

### Proposed promotion gate

- resolved trades: **>= 500** historical / **>= 100** sealed confirmation
- base expectancy: **> +0.10R/trade**
- base profit factor: **> 1.25**
- bootstrap 95% lower bound: **> 0**
- stress expectancy: **> 0**
- stress profit factor: **> 1.10**
- positive calendar years: **>= 70%**
- integrity failures / synthetic fills: **0**
- drawdown: must remain within the preregistered risk envelope
- final label `VALIDATED_PROFITABLE_EDGE` only after the sealed confirmation passes

## Bottom line

The engine can produce trustworthy backtests. What it has not yet produced is a trustworthy profitable strategy. The new research lifecycle should be judged by whether it can find an edge **without weakening these controls**. Profitable historical numbers are a milestone; profitable, statistically defensible out-of-sample numbers are the actual target.
