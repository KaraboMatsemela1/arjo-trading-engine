# Issue 101 — incremental first-party source discovery

## Outcome

A fresh current-day incremental scan found **zero genuinely new first-party source URLs** relative to the canonical 1,181-row source registry.

This confirms that the current semantic bottleneck is an **evidence/access ceiling**, not a stale source-universe snapshot.

`SPEC_READY=false`; strategy implementation remains unauthorized.

## Authoritative scan

- workflow: `Issue 101 Incremental First-Party Discovery`
- run: `31962154795`
- artifact: `9267525569`
- artifact SHA-256: `399b64580c6fa12ca5a6f47bdbd19cf3f76940eb7df2efd060b3dc42f0259789`
- generated: `2026-08-16T17:38:32Z`
- baseline registry rows: 1,181
- scanned registry rows: 1,181
- new sources: **0**
- source registry mutation: **none**
- semantic closure during discovery: **none**

## YouTube

All four official discovery surfaces completed successfully:

- videos
- shorts
- streams
- playlists

Result:

- discovered locators: **381**
- new locators: **0**
- discovery failures: **0**

This does not change Issue #87's semantic-access result: source locators remain discoverable, while direct watch-page semantic acquisition is bot-challenged in the runner and allowed public embed/oEmbed routes expose no caption payload.

## Telegram

The full public `ArjoioTrading` archive replay completed cleanly:

- archive pages fetched: **40**
- discovered posts: **790**
- new posts: **0**
- failures: **0**

Therefore there is no newly published public Telegram payload to route through acquisition/evidence review in this pass.

## Trading MMT website

All three known public first-party seeds remain unavailable in the runner environment:

- `https://tradingmmt.com/`
- `https://tradingmmt.com/newsletter/`
- `https://tradingmmt.com/mmc/`

Each returned HTTP 403 to the normal browser-shaped HTTP client and remained behind a public browser challenge under the stock headless browser fallback. All are classified `ENVIRONMENT_ACCESS_FAILURE`; this is not evidence absence.

No CAPTCHA solving, stealth flags, proxy rotation, authenticated session, or private endpoint was used.

## Research decision

The six bounded predicate-recovery passes are exhausted, the fresh source universe contains no new public locators, and the allowed public YouTube/website acquisition routes do not provide new semantic payload.

Accordingly, the research project should remain at `NEW_FIRST_PARTY_EVIDENCE_REQUIRED` until one of these conditions changes:

1. Arjo publishes a genuinely new first-party source;
2. an existing first-party source becomes directly accessible through an allowed public route; or
3. the owner explicitly authorizes a separate compliant acquisition environment or supplies first-party material directly.

The existing scheduled New Source Detection workflow can continue checking for future first-party changes. Re-running the same exhausted semantic source sets without a new payload/access condition is not authorized as progress.

## Safety boundary

No generic ICT/SMC substitution, detector, backtester, performance analysis, optimization, paper/live execution, or broker logic is authorized by this result.
