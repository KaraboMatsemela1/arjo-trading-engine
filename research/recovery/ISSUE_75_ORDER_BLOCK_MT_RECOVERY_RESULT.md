# Issue 75 — Order Block / MT bounded first-party recovery

## Outcome

The bounded recovery pass produced a **narrow scope advancement only** for `ORDER_BLOCK_MT_HOLD_CONTEXT`.

Candidate state moves from:

- `12 MISSING / 4 PARTIAL / 0 SATISFIED / 0 CONTRADICTORY`

to:

- `10 MISSING / 6 PARTIAL / 0 SATISFIED / 0 CONTRADICTORY`

Only `INSTRUMENTS` and `TIMEFRAME` advance from `MISSING` to `PARTIAL`. `SPEC_READY=false` and implementation remains unauthorized.

## Authoritative recovery

- workflow: `Issue 75 Recovery`
- run: `31958765415`
- artifact: `9266676640`
- bounded targets: 7
- direct payloads captured: 1
- `ENVIRONMENT_ACCESS_FAILURE`: 6
- terminal acquisition validation: PASS
- pre-SPEC anti-bias regressions: PASS
- Telegram target recovered from SHA-bound public archive pages: PASS
- archive pages fetched: 36
- archive retrieval failures: 0

## Evidence admitted

The only newly admitted semantic evidence is the pre-outcome scope sentence from `TG_ARJOIOTRADING_80`:

> `I gathered the data on ES for Daily Order Blocks`

This supports only:

- `INSTRUMENTS = PARTIAL` — ES is explicitly used in the worked Order Block dataset;
- `TIMEFRAME = PARTIAL` — Daily Order Blocks are explicitly the worked timeframe.

It does **not** establish universal instrument eligibility, exclusions, substitutions, required markets, universal timeframe scope, hierarchy, higher-timeframe ownership, or whether Daily is mandatory for the Order Block/MT relationship.

## Outcome-data exclusion

Post #80 also contains a later statistical section. That section is excluded in full **before** lexical recovery. No count, percentage, probability, hold/fail outcome, or comparative result from that section receives semantic credit or influences predicate interpretation.

The recovery artifact therefore contains only the pre-outcome scope phrase for post #80. The shared anti-bias guard was also hardened against count-based outcome fragments and singular/plural probability wording.

## MT remains unresolved

`MT` remains an unresolved literal first-party token. This pass does not expand it to Momentum Theory or any other concept, and does not infer its construction from generic ICT/SMC knowledge or unrelated Arjo content.

Existing `PARTIAL` fields remain partial:

- `INPUTS`
- `PRECONDITIONS`
- `SETUP`
- `REQUIRED_CONDITIONS`

Still `MISSING`:

- `HIGHER_TIMEFRAME_CONTEXT`
- `DIRECTION`
- `TRIGGER`
- `ENTRY`
- `STOP`
- `TARGET`
- `INVALIDATION`
- `EXPIRY`
- `SESSION/TIME_RULE`
- `OPTIONAL_CONDITIONS`

## Zero-credit access debt

All six official YouTube targets were contacted directly and terminated as `ENVIRONMENT_ACCESS_FAILURE`. They receive zero semantic credit:

- `YT_SHORT_dG0_n6A3gVw`
- `YT_VIDEO_-IiaWZt3DxU`
- `YT_VIDEO_1uHafYQiyQU`
- `YT_VIDEO_MZZPsTkZxZ0`
- `YT_VIDEO_PUctccigOik`
- `YT_VIDEO_S_XEq7Is82I`

No cookies, authenticated scraping, stealth bypass, CAPTCHA bypass, or secondary-source semantic substitution was used.

## Safety boundary

No detector, trade-count analysis, backtest, optimizer, performance evaluator, paper/live execution, or broker logic is authorized by this recovery. The candidate still has ten missing fields and six partial fields; it remains far from executable closure.
