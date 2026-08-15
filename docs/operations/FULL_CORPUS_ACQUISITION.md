# Full Corpus Acquisition

## Gate

This workflow runs only after `ACQUISITION_TOOLING_READY`.

## Deterministic sharding

The canonical item-level source set is sorted by `SOURCE_ID` and partitioned by stable index modulo 24. Locator-only roots are excluded from acquisition coverage because they do not represent item payloads.

Each shard:

1. checks out the same registry revision;
2. records its deterministic plan;
3. contacts each selected public source using the source-type adapter;
4. emits exactly one terminal acquisition record per selected source;
5. validates the shard manifest;
6. uploads only the terminal manifest as a short-lived workflow artifact.

Raw source payloads are not bulk-uploaded or committed to this public repository. Captured content is hashed into a content-addressed transient cache; durable repo state stores the source URL, terminal disposition, SHA-256, content address and provenance metadata.

## Aggregate gate

The aggregate job refuses to advance if:

- any shard fails to produce a valid terminal manifest;
- two shards produce conflicting records for the same source;
- any canonical item-level source is missing;
- an unexpected source appears;
- a terminal state is invalid;
- semantic extraction was performed during acquisition.

A successful aggregate creates:

- `research/acquisition_manifest.jsonl`
- `research/corpus_coverage.json`

and pushes a bounded `automation/corpus-acquisition-<run-id>` branch for normal CI/PR review.

## Meaning of `CORPUS_ACQUIRED`

The gate means terminal acquisition coverage is complete, not that every source yielded content. An `ENVIRONMENT_ACCESS_FAILURE`, removal, or unavailable source is a valid terminal transport disposition but has zero semantic closure credit.

Downstream concept/evidence work may use only captured first-party payloads. Missing payloads remain missing and can create targeted recovery work later.

## Anti-bias boundary

This workflow must never produce strategy interpretations, predicates, trade counts, backtests, optimization, performance metrics, or execution behavior.
