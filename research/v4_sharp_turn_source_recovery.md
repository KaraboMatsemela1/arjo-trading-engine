# V4 Sharp Turn / FVG source recovery

Issue: #239  
Recovery date: 2026-08-17  
Outcome access: **none**  
V3-C result/parameter reuse: **prohibited**  
Paper/live/broker mutation: **false**

## Why this lane is allowed

The post-V3 boundary prohibited tuning the failed `Arguments/2CR` family against consumed OOS outcomes. This V4 lane is reopened only because newly reachable public source material describes a different setup family: **Sharp Turn entry from Fair Value Gaps**. The candidate is defined from source semantics before any V4 market-result access.

## Source grades

### Grade A — Arjo-authored text, mirror transport

These pages are Thread Reader mirrors of posts authored by `@arjoio`. The transport is third-party, but the text is attributed to the first-party author and links back to the corresponding X thread.

| ID | Canonical URL | Operational content recovered |
|---|---|---|
| `ARJO_X_ST_1779604305923748190` | https://threadreaderapp.com/thread/1779604305923748190.html | Sharp Turn chain: Bias/DOL -> directional FVG -> timeframe alignment -> FVG into HTF FVG -> FVG out -> enter second FVG -> stop at swing high / swing-high bodies. |
| `ARJO_X_TF_1794840255331512683` | https://threadreaderapp.com/thread/1794840255331512683.html | Five foundational levels; higher-timeframe Bias; Narrative PD Array; Context Area; lower-timeframe entry; Sharp Turn vs higher-confirmation entry; risk-management timeframe concept. |
| `ARJO_X_PD_HOLD_1797370754142441864` | https://threadreaderapp.com/thread/1797370754142441864.html | FVA/FVG/Swing-Point hold/fail context; FVG third candle; lower-timeframe FVG confirmation. |
| `ARJO_X_MMXM_1799902120310669427` | https://threadreaderapp.com/thread/1799902120310669427.html | Market Structure -> Offering Fair Value / Seeking Liquidity -> MMBM/MMSM; MMBM via bullish FVA respect or bearish FVA failure, inverse for MMSM. |
| `ARJO_X_CONTEXT_1753202981493723369` | https://threadreaderapp.com/thread/1753202981493723369.html | Context Boundary, first opposing PD Array as Context Target, and explicit 1:2 rejection target guidance. |
| `ARJO_X_FVG_1821247796512542926` | https://threadreaderapp.com/thread/1821247796512542926.html | FVG is a 3-candle pattern; third candle classifies RFVG/PFVG/BAG; beginners advised to focus on PFVGs. |

### Grade B — transcript witness of Arjo's public YouTube lesson

Canonical video: https://www.youtube.com/watch?v=hqvMBGpslH4  
Title: `Arjo's World of Fair Value Gaps`

Independent transcript witnesses located:

- https://pickscribe.com/v/hqvMBGpslH4/
- https://lilys.ai/en/notes/414684
- https://glasp.co/youtube/hqvMBGpslH4

Recovered details include:

- exact 3-candle bullish/bearish FVG geometry;
- 3-candle swing-high/swing-low construction and confirmation time;
- recent order-flow-leg emphasis;
- higher-timeframe hierarchy and alignment requirement;
- one-use / unmitigated-FVG treatment;
- Sharp Turn baseline mappings;
- FVG-in then FVG-out construction;
- order-flow-leg extreme as stop-cover reference;
- 2R beginner target;
- break-even after new directional FVGs beyond entry.

The transcript witnesses are **not silently promoted to Grade A**. They are retained as derived first-party-content witnesses. A recurring transcription error renders `15 minute` as `50 minute`; the intended value is corroborated by other mirrors/slides but this recovery record does not pretend the transcript itself is error-free.

## Recovered deterministic semantics

### Directly supported by Grade A authored text

1. A Sharp Turn is downstream of Bias/DOL and a directional higher-timeframe FVG.
2. Narrative and entry timeframes must be aligned.
3. The core Sharp Turn pattern is an entry-timeframe FVG **into** the higher-timeframe FVG followed by an FVG **out of** it.
4. Entry participation is on the second/outbound FVG.
5. Beginner stop placement is at the relevant swing extreme or the swing bodies.
6. Context Boundary is the HTF/MTF PD Array being traded from; Context Target is the first opposing PD Array.
7. A 1:2 rejection target is explicitly recommended in Context.
8. FVGs use a 3-candle pattern and the third candle is behaviorally important.

### Supported only after Grade B transcript recovery

1. Exact FVG price geometry.
2. Exact 3-candle swing geometry.
3. Concrete Sharp Turn timeframe baseline: Monthly->Daily, Weekly->4H, Daily->1H, 4H->15m, 1H->5m, 15m->1m.
4. The recent order-flow leg as the direction-bearing leg.
5. Unmitigated FVG selection.
6. Order-flow-leg high/low as the stop-cover reference in the worked entry.
7. Break-even logic after new FVGs form beyond entry.

## Anti-bias boundary

No V3-C trade ledger, V3-C per-period result, V3-C instrument winner/loser split, or 2024-2025 protected outcome was consulted to select these semantics. The candidate was chosen because the newly accessible authored sources explicitly define a complete-looking entry family, not because a price-history scan suggested it.

## Recovery verdict

`V4_SHARP_TURN_STILL_INCOMPLETE`

The family is **substantially more recoverable** than it was at the previous boundary, but a sealed economic protocol would still require semantic invention in at least these places:

- exact executable entry price on the second/outbound FVG (creation close, gap edge, midpoint, retracement, or another rule is not uniquely specified by Grade A text);
- deterministic treatment when multiple qualifying outbound FVGs occur;
- deterministic FVG subtype threshold for `PFVG` / consolidation versus rejection/breakaway when numeric candle-size boundaries are required;
- signal expiry / maximum wait if the selected entry mechanic requires a retracement fill;
- universal long/short stop-body rule and tie handling at equal swing extrema;
- whether session/killzone filtering is required or merely optional for this specific modern Sharp Turn family.

These fields must be recovered from Arjo material or explicitly frozen as implementation conventions **before** any market outcomes are exposed. No backtest is authorized by this record.