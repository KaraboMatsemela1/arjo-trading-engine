# Issue #48 — AoO / FVA / 2CR / FVG First-Party Recovery Result

**Mode:** bounded first-party semantic recovery only  
**Predicate:** `AOO_FVA_2CR_FVG_LONG_CONTEXT`  
**Disposition:** `MATERIAL_PARTIAL_ADVANCEMENT_REQUIRES_ATOMIC_ADMISSION`  
**SPEC_READY:** `false`

## Reproducible recovery run

The accepted recovery baseline is GitHub Actions run `31937350692`.

- artifact ID: `9261038445`
- artifact digest: `sha256:a91c847cc3fd869ad57f4c6c140bbb353e439896a97a44266431fcb4c80a229c`
- bounded targets: 17
- direct first-party payloads captured: 6 Telegram posts
- terminal environment-access failures: 11 website/YouTube routes
- canonical captured Telegram corpus scanned: 790 sources
- archive pages fetched and SHA-256 bound: 40
- archive retrieval failures: 0
- pre-SPEC outcome leakage after shared guard: 0 observed

Environment access failure is transport debt, not evidence absence. No website/YouTube failure receives semantic closure credit.

## Primary direct source

`TG_ARJOIOTRADING_778` was directly contacted and captured from the official public Telegram source.

- publication date: `2025-05-07`
- direct recovery payload SHA-256: `3c4d33d3667f3b1023998c07375c79b430f4ec56184a987ba511b4376c698ad7`
- corresponding captured archive page SHA-256: `b77e10fd873fd794fe7090ac7a410728c4fba6598267bef872156e1d286f5c88`

Short first-party windows establish a worked example with the following directly observable relationships:

- the example is explicitly **Gold**;
- it explicitly references **4h and 1h**;
- a run of the **Rejection High** precedes **FVA disrespect** in the stated parameter;
- the example then looks for **buys**;
- the stated entry uses **2CR from FVGs**.

These are worked-example facts. They are not upgraded into universal rules.

## Field impact

The current canonical matrix is `9 MISSING / 7 PARTIAL / 0 SATISFIED`.

This recovery provides enough direct worked-example evidence to support a later atomic admission of:

- `INSTRUMENTS`: `MISSING -> PARTIAL` — Gold is explicit in the worked AoO example, but universal instrument scope/exclusions are not defined.
- `TIMEFRAME`: `MISSING -> PARTIAL` — 4h and 1h are explicit in the worked example, but ownership/mapping and universal timeframe scope are not defined.

If those two atomic records are admitted and the deterministic Phase-5 state is regenerated, the expected candidate counts become:

```text
MISSING        7
PARTIAL        9
SATISFIED      0
CONTRADICTORY  0
```

The following remain `PARTIAL`, albeit with stronger contextual support: `DIRECTION`, `PRECONDITIONS`, `SETUP`, `TRIGGER`, `ENTRY`, plus the existing `INPUTS` and `REQUIRED_CONDITIONS`.

The following remain `MISSING`: `HIGHER_TIMEFRAME_CONTEXT`, `STOP`, `TARGET`, `INVALIDATION`, `EXPIRY`, `SESSION/TIME_RULE`, `OPTIONAL_CONDITIONS`.

`HIGHER_TIMEFRAME_CONTEXT` is deliberately not inferred from the mere presence of 4h and 1h. The source does not state a deterministic ownership hierarchy.

## Anti-bias and provenance boundary

Both direct-target and archive recovery now use the shared repository anti-bias guard from `scripts/evidence_antibias.py`. The earlier local regex that allowed explicit outcome wording has been removed.

The archive scanner now persists the exact public archive pages used for lexical routing inside the workflow artifact and records each page SHA-256. Archive-derived text remains recovery/locator context unless atomized through the normal direct first-party evidence admission path.

No trade counts, performance metrics, backtest results, optimizer output, generic ICT/SMC knowledge, paper execution, or live execution were consulted.

## Next deterministic step

Create a bounded atomic-admission/state-refresh task that:

1. admits short `INSTRUMENTS` and `TIMEFRAME` records for `TG_ARJOIOTRADING_778` with explicit worked-example limitations;
2. validates them through the normal first-party evidence/provenance boundary;
3. updates the AoO candidate field hypotheses from `MISSING` to `PARTIAL` only for those two fields;
4. regenerates the predicate matrix, closure ranking, recovery bundles and independent blocked-readiness audit;
5. leaves `SPEC_READY=false` unless a future complete evidence set passes the independent reconstruction gate.
