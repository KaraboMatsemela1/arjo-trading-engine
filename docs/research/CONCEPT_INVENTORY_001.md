# Concept Inventory 001

## Scope

This inventory is derived only from confirmed first-party `@ArjoioTrading` Telegram posts whose acquisition records are `PAYLOAD_CAPTURED`, SHA-256 bound, and marked `DIRECT_FIRST_PARTY_PAYLOAD`.

The inventory does **not** import generic ICT/SMC definitions. The 380 YouTube-family access failures, four website no-payload records, and one removed source remain evidence debt and contribute zero semantic closure credit.

## First-party hierarchy spine

The strongest directly stated hierarchy currently available is:

`PD Arrays -> Trend -> Order Flow -> Candle Science -> Order Flow Transition -> Delirium Trading Plan`

The repository records the first five stages as concepts. The final trading-plan label is not yet treated as an executable strategy specification because the directly available text does not define its complete rule set.

Additional directly stated relationships include:

- Order Flow is said to tell the Target.
- Target/Bias is framed as the price objective that should be known before participation.
- Candle Science and 2 Candle Rejection are used with PD Arrays to tell direction.
- Opposing PD Arrays are described as resistance; 2CR is used to identify their failure.
- A No Resistance Area is described as a brief fast-moving market state after opposing resistance fails.
- AoO is used to reason about where to get involved; the available Gold example connects Rejection High, FVA disrespect, and 2CR-from-FVG participation.
- Tape Reading is directly defined as real-time observation for experience without forcing participation.

## Inventory disposition

The v1 inventory contains 21 concepts.

### Strong/directly described concepts

- `PD_ARRAYS`
- `ORDER_FLOW`
- `TARGET_BIAS`
- `CANDLE_SCIENCE`
- `TWO_CANDLE_REJECTION`
- `LIQUIDITY_RUN_SWEEP`
- `NO_RESISTANCE_AREA`
- `AREA_OF_OPPORTUNITY`
- `TAPE_READING`
- `NARRATIVE`
- `MMBM_LRLR`
- `ARGUMENTS_FRAMEWORK`

These concepts have direct first-party roles, examples, definitions, or relationships, but most still lack deterministic construction details.

### Named/contextual concepts with unresolved construction

- `TREND`
- `FAIR_VALUE_AREA`
- `FAIR_VALUE_GAP`
- `ORDER_BLOCK`
- `MT`
- `DOL`
- `SMT`
- `PREMIUM_ARRAY`
- `ORDER_FLOW_TRANSITION`

`MT`, `DOL`, `SMT`, `MMBM`, and `LRLR` are **not expanded from external knowledge** unless Arjo's acquired first-party material explicitly supplies the expansion.

## Evidence debt that blocks executable semantics

Major unresolved fields include:

- PD Array taxonomy and geometry;
- Trend construction;
- Order Flow observable inputs and algorithm;
- Target/Bias selection and timeframe ownership;
- Candle Science measurements;
- exact 2CR two-candle predicate;
- Liquidity Run-vs-Sweep meaning of `Comfortable`;
- AoO universal construction;
- FVA/FVG geometry and respect/disrespect rules;
- Order Block and MT construction;
- DOL and SMT definitions;
- MMBM/LRLR construction and directional symmetry;
- Premium Array construction;
- Arguments-framework scoring/threshold rules;
- Order Flow Transition state/trigger.

These are intentionally preserved as ambiguity rather than completed through inference.

## Anti-bias handling

A first-party Order Block post contains historical percentages. Those values are not used to rank concepts, choose definitions, or promote strategy candidates because pre-`SPEC_READY` trade/performance selection is forbidden.

## Completeness challenge

The committed inventory is not accepted solely because these 21 concepts were manually reconciled. `scripts/build_telegram_concept_review.py` performs a full-channel lexical audit over the public Telegram archive and emits:

- occurrence counts for every source-discovered catalog term;
- bounded source IDs and short excerpts for review;
- uncatalogued acronym/quoted-term candidates.

The review artifact is deliberately separate from the semantic inventory. A lexical hit never becomes a definition automatically.

## Phase boundary

No record in `research/concept_inventory.jsonl` claims an executable trading rule. Phase 4 evidence extraction must atomize what each source proves and does not prove before predicate synthesis may begin.
