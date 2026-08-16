# Issue 91 — Equilibrium / Stop Run bounded first-party recovery

## Outcome

The bounded recovery pass for `EQUILIBRIUM_STOP_RUN_CONTEXT` is complete with **no field-state advancement**.

Candidate state remains:

- `13 MISSING / 3 PARTIAL / 0 SATISFIED / 0 CONTRADICTORY`

All 16 fields remain unresolved. `SPEC_READY=false` and implementation remains unauthorized.

## Authoritative recovery

- workflow: `Issue 91 Recovery`
- run: `31960905391`
- artifact: `9267214340`
- semantic source set: exactly `TG_ARJOIOTRADING_16`
- canonical acquisition SHA: `65ea7c0cec45e16fe568bd1f3dd83867b3fd11051c3f2914c336dbb2634d0a79`
- public Telegram archive pages fetched: 40
- archive retrieval failures: 0
- target recovered: 1 / 1
- shared pre-SPEC anti-bias boundary: PASS
- excerpt cap: 20 words

## New contextual detail recovered

The wider safe context directly shows a worked example in which price stays around `0.5`, followed by Arjo identifying that area as equilibrium and associating equilibrium with a likely stop run before continuation.

This does **not** define:

- what parent range the `0.5` belongs to;
- how the range anchors are selected;
- whether `0.5` is universally the construction or only this example;
- tolerance around equilibrium;
- instrument or timeframe scope;
- direction of continuation;
- trigger, entry, target, protective stop, invalidation, or expiry rules.

Therefore `INPUTS`, `PRECONDITIONS`, and `SETUP` remain `PARTIAL`; none can become `SATISFIED`, and none of the 13 `MISSING` fields can advance.

## Evidence handling

No new evidence shard is admitted. The recovered relationship is already represented by:

- `EV_72FA00B0C191C4291B6BD9AA` — direct Equilibrium / likely stop-run context;
- `EV_8B32047911C6EC4FB51D8CCB` — explicit deterministic-construction gap.

The additional `0.5` context strengthens the limitation analysis but does not alter the field-state matrix.

## YouTube access

No YouTube source was retried. Issue #87 already established that the allowed unauthenticated public YouTube routes expose page/metadata availability but no semantic caption payload in the GitHub runner environment. Repeating those probes would not create new first-party semantic evidence.

## Safety boundary

No generic ICT/SMC equilibrium construction was imported. No detector, backtester, trade-count analysis, optimizer, performance evaluator, paper/live execution, or broker logic is authorized by this recovery.
