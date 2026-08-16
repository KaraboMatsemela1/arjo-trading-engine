# Issue 85 — Order Flow / Target / Bias bounded first-party recovery

## Outcome

The bounded recovery pass for `ORDER_FLOW_TARGET_BIAS` is complete with **no field-state advancement**.

Candidate state remains:

- `12 MISSING / 4 PARTIAL / 0 SATISFIED / 0 CONTRADICTORY`

All 16 fields remain unresolved. `SPEC_READY=false` and implementation remains unauthorized.

## Authoritative recovery

- workflow: `Issue 85 Recovery`
- run: `31959673355`
- artifact: `9266896625`
- bounded targets: 9
- direct payloads captured: 3
- `ENVIRONMENT_ACCESS_FAILURE`: 6
- terminal acquisition validation: PASS
- pre-SPEC recovery regression tests: PASS
- Telegram targets recovered from SHA-bound public archive pages: 3 / 3
- archive retrieval failures: 0

## Captured first-party sources

The three bounded Telegram posts were recovered directly:

- `TG_ARJOIOTRADING_785` — states that the lesson focuses on knowing the Target in price / Bias;
- `TG_ARJOIOTRADING_786` — links Bias with knowing where to trade;
- `TG_ARJOIOTRADING_790` — states that Order Flow tells the Target.

These relationships are already represented in the canonical evidence registry by `EV_682019305394DD960FBEFCE4`, `EV_8AD848A97EBC1DC159B34765`, `EV_22D0263AE5E535F475633161`, and construction-gap record `EV_9B5480162CFA86DA4C049ACD`.

No duplicate evidence shard is admitted.

## Why no field advanced

The captured text reinforces the existing four `PARTIAL` fields but does not close their deterministic semantics:

- `INPUTS` — Order Flow is upstream, but its observable inputs and algorithm are not defined;
- `DIRECTION` — Bias/where-to-trade language exists, but deterministic bullish/bearish mapping is not defined;
- `TARGET` — Order Flow is said to tell the Target, but target selection and price construction are not defined;
- `REQUIRED_CONDITIONS` — the Order Flow-to-Target relationship is direct, but no complete prerequisite set is defined.

Still `MISSING`:

- `INSTRUMENTS`
- `TIMEFRAME`
- `HIGHER_TIMEFRAME_CONTEXT`
- `PRECONDITIONS`
- `SETUP`
- `TRIGGER`
- `ENTRY`
- `STOP`
- `INVALIDATION`
- `EXPIRY`
- `SESSION/TIME_RULE`
- `OPTIONAL_CONDITIONS`

## Zero-credit access debt

All six official first-party YouTube targets were contacted directly and terminated as `ENVIRONMENT_ACCESS_FAILURE`. They receive zero semantic credit:

- `YT_VIDEO_mlXBuNHO1c8` — Order Flow Shows You the Target - Ep.1
- `YT_VIDEO_7PT8zRItzhM` — Do yourself a favor; learn Order Flow.
- `YT_VIDEO_NvufvH990aQ` — Secrets of an Order Flow Leg
- `YT_VIDEO_X3IDEQ_xTJo` — Entries using Order Flow
- `YT_VIDEO_xTdSe_vJQ5s` — No Need To Guess, Start Knowing 'The Target'
- `YT_SHORT_8RuafyGCuuA` — Know your Order Flow Legs

Titles and search-index snippets remain locator-only and receive zero closure credit. No cookies, authenticated scraping, stealth bypass, CAPTCHA bypass, or secondary-source semantic substitution was used.

## Next engineering implication

This is the fourth bounded predicate-recovery lane to show the same structural limitation: directly captured Telegram text provides relationship/context evidence, while the deterministic construction is concentrated in inaccessible official YouTube lessons.

The next high-leverage task should therefore be a **bounded first-party YouTube access-recovery investigation** rather than immediately cycling into another weak predicate. The purpose is transport recovery only; it must not bypass authentication, CAPTCHA, anti-bot controls, or use secondary-source transcripts as semantic evidence.

## Safety boundary

No detector, backtester, trade-count analysis, optimizer, performance evaluator, paper/live execution, or broker logic is authorized by this recovery.
