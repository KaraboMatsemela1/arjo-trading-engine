# V8 FVG Follow-Through source recovery

Captured for Issue #284 before the V7 historical profitability result was inspected.

## First-party Arjo / The MMT sources

1. **Remember: Where Most Traders Lose** — https://tradingmmt.com/remember-where-most-traders-lose/
   - Arjo frames FVG follow-through as a directional trust test: a same-direction FVG after the initial FVG supports continuation, while an opposing FVG signals failed follow-through / consolidation.
   - The V8 hypothesis uses only that directional follow-through distinction as source-backed semantics.

2. **The Simple Secret I Used to Create This Trading Plan** — https://tradingmmt.com/the-simple-secret-i-used-to-create-this-trading-plan/
   - Arjo uses FVGs to build bias, narrative and context, and discusses opposing PD Array context as a potential swing/resistance area.

## Source / engine boundary

The sources do **not** specify a complete machine implementation for H4 BOS bias, pivot radius, exact H1 FVG inequalities, a 12-H1 search window, causal H1 swing targets, stop placement at the follow-through FVG boundary, OANDA proxy selection, M1 execution, slippage, financing, concurrency, bootstrap, or statistical thresholds. Those are explicitly engine conventions in `v8_fvg_followthrough_protocol_v1.json`.

No V7 historical result, V7 trade ledger, V8 market data, V8 trigger set, V8 M1 data, V8 P&L or V8 economic metric was consulted while freezing this family.