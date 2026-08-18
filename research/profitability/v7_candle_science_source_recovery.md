# V7 Candle Science source recovery

Captured for Issue #274 before the V6 historical profitability result was available.

## First-party Arjo / The MMT sources

1. **Candle Science** — https://tradingmmt.com/candle-science/
   - Price is framed as consolidation → expansion → consolidation across three higher-timeframe candles.
   - The expansion phase forms the body of a potential FVG.
   - Arjo states that after the third candle closes, price can sting back into that FVG.

2. **Increase Your Accuracy by Doing Less** — https://tradingmmt.com/increase-your-accuracy-by-doing-less/
   - Determine bias, mark nearby PD Arrays, wait for price to reach them, and evaluate same-timeframe Candle Science rejection.
   - For a bullish aligned discount array, examples of rejection include a lower wick stinging the array or a strong up-candle.
   - If the aligned array rejects, Arjo describes looking to get involved until the next PD Array; arrays against the bias act as resistance/targets.

3. **This Is Exactly Where to Place Your Stop Loss** — https://tradingmmt.com/this-is-exactly-where-to-place-your-stop-loss/
   - Stop placement belongs where price changes from high-probability to low-probability / where price should not return.
   - FVG legs, swing extremes, 2CR and FVA context are discussed as stop-placement information.

4. **Market Structure -> Order Flow -> Candle Science** — https://tradingmmt.com/market-structure-order-flow-candle-science/
   - Market Structure supplies direction, Order Flow refines continuation location / where price should not retrace, and Candle Science supplies timing.

## Source / engine boundary

The sources do not provide a complete machine specification for H4 break-of-structure, pivot radius, exact FVG inequalities, rejection close threshold, search-window length, target tie-breaks, OANDA proxy, M1 fill model, slippage/financing, concurrency, expiry, bootstrap or statistical pass thresholds. Those are explicitly engine conventions in `v7_candle_science_protocol_v1.json`.

No V6 historical result, V6 ledger, V7 market data, V7 trigger set, V7 M1 data, V7 P&L or V7 economic metric was consulted while freezing this family.