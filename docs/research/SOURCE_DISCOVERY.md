# First-Party Source Discovery

## Purpose

Phase 1 identifies the public source universe relevant to Arjo's trading methodology without interpreting strategy semantics.

## Replayable discovery surfaces

- YouTube `@Arjoio`: videos, shorts, streams, playlists via deterministic `yt-dlp` enumeration.
- Telegram `@ArjoioTrading`: public archive message locators via bounded pagination.
- Trading MMT website: bounded same-origin crawl seeded from the home page, public newsletter archive, and MMC resource hub.

Direct Drive/Notion resources linked by the official MMT site are registered as first-party-linked resources for provenance verification during acquisition.

## Access-limited but documented surfaces

- X `@arjoio`: root confirmed; unauthenticated item-level replayable enumeration currently unavailable.
- Instagram `@arjoio`: root confirmed through repeated first-party cross-links; unauthenticated item-level replayable enumeration currently unavailable.
- Public Trading MMT Discord: first-party linked; item discovery requires platform join/auth.
- `zaap.bio/arjo`: first-party-linked locator only and receives zero semantic closure credit.

Access limitation is not evidence absence. These surfaces remain eligible for later targeted recovery where a missing predicate field requires them.

## Completion rule

`SOURCE_UNIVERSE_DISCOVERED` may be earned only when all replayable discovery surfaces are `ENUMERATED_CLEAN` in `research/discovery/platform_surface_audit.json`.

A documented platform access boundary may coexist with the discovery gate, but it cannot be silently interpreted as absence of evidence or used for semantic closure.

## Anti-bias rule

Discovery records URLs, metadata, provenance status, and retrieval limitations only. It does not extract trading rules, rank concepts by profitability, inspect trade counts, or close predicate fields.
