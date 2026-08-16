# Issue 87 — public first-party YouTube access recovery

## Outcome

The bounded transport-recovery investigation completed without unlocking a direct semantic YouTube payload.

Terminal classification:

`PUBLIC_PAGE_METADATA_AVAILABLE_BUT_SEMANTIC_PAYLOAD_UNAVAILABLE`

This is an external-access result, not evidence absence. `SPEC_READY=false` and implementation remains unauthorized.

## Authoritative probe

- workflow: `Issue 87 YouTube Access Recovery`
- run: `31960189800`
- artifact: `9267022847`
- canaries: 4 predicate-critical official Arjo videos
- allowed public routes per canary: watch, embed, oEmbed metadata
- direct semantic payloads captured: 0
- caption tracks exposed by successful public pages: 0
- regression tests: PASS
- safety-policy validation: PASS

Canaries:

- `YT_VIDEO_xTdSe_vJQ5s` — Target/Bias
- `YT_VIDEO_mlXBuNHO1c8` — Order Flow → Target
- `YT_VIDEO_sPGSHQNDCPU` — PD Arrays
- `YT_VIDEO_VwcuxpIBcsI` — FVA/AoO

## Route results

### Public watch page

All four watch requests returned HTTP 200 HTML, but every page contained YouTube's explicit `sign in to confirm you're not a bot` challenge. These are therefore terminal `ENVIRONMENT_ACCESS_FAILURE` results for semantic acquisition.

### Public embed page

All four official embed pages returned HTTP 200 public HTML without the challenge marker. These responses confirm public page availability, but no `captionTracks` payload was exposed. The embed HTML receives zero semantic closure credit.

### Official oEmbed metadata

All four official oEmbed calls returned HTTP 200 JSON. This confirms source availability/identity only. Titles and metadata receive zero semantic closure credit.

### Caption/transcript route

No official caption track URL was exposed by any successful public watch/embed response, so no caption request was attempted. No transcript or caption payload was captured.

## Why the investigation stops here

The issue explicitly bounded legitimate unauthenticated routes to ordinary public YouTube surfaces and caption URLs exposed by those surfaces. Those routes are now deterministically classified.

No cookies, account session, CAPTCHA bypass, stealth browser fingerprinting, proxy rotation, private/authenticated YouTube endpoint, third-party transcript mirror, or search-snippet semantic substitution is permitted. Expanding into those mechanisms would violate the research acquisition boundary rather than solve it.

## Research implication

The recurring YouTube debt is now better characterized:

- source existence and public embed/oEmbed availability are verifiable;
- standard watch-page semantic acquisition is blocked by YouTube's bot challenge in the GitHub runner environment;
- ordinary public embed responses do not expose captions for these canaries;
- no direct first-party transcript payload is available through the allowed public routes tested here.

Therefore completed predicate recoveries must continue treating inaccessible video semantics as unresolved. A future change in YouTube's public responses or a separately owner-authorized acquisition environment may justify a new bounded replay, but no current semantic credit is earned.

## Safety boundary

No detector, backtester, trade-count analysis, optimizer, performance evaluator, paper/live execution, or broker logic is authorized by this result.
