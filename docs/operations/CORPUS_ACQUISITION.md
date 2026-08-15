# Corpus Acquisition Operations

## Purpose

Acquire public first-party source payloads reproducibly without interpreting strategy semantics. Acquisition and evidence synthesis are separate phases.

## Durable state

`research/acquisition_manifest.jsonl` is the terminal-disposition ledger. Each record carries source identity, transport, terminal status, whether first-party infrastructure was actually contacted, semantic closure credit, artifact hashes, and failure details.

Allowed terminal states are exactly:

- `ENVIRONMENT_ACCESS_FAILURE`
- `SOURCE_CONTACTED_NO_PAYLOAD`
- `PAYLOAD_CAPTURED`
- `SOURCE_REMOVED`
- `SOURCE_UNAVAILABLE_AFTER_CONTACT`

A transport failure is never evidence that a strategy rule is absent.

## Raw artifact policy

Raw payloads default to `.research-cache/artifacts/<sha-prefix>/<sha256>.<ext>` and are gitignored. The public repository therefore stores durable hashes/manifests rather than bulk copies of educational content. Later field-level evidence should use minimal legally appropriate excerpts.

## Commands

Plan without network contact:

```bash
python scripts/acquire_corpus.py --plan
```

Acquire one bounded source:

```bash
python scripts/acquire_corpus.py --source-id YT_VIDEO_<id>
```

Acquire a bounded type batch:

```bash
python scripts/acquire_corpus.py --source-type YOUTUBE_VIDEO --limit 10
```

Validate:

```bash
python scripts/check_acquisition_manifest.py
python scripts/check_provenance.py
```

## YouTube

The adapter uses `yt-dlp` with download disabled and attempts public info JSON, description, official subtitles and auto subtitles. Any captured artifact is SHA-256 bound. Fixture mode exists only for offline CI and is explicitly marked `ZERO_FIXTURE_ONLY` because no first-party contact occurs.

## Locator-only roots

Platform roots, link hubs and first-party-linked locator resources are excluded by default. If explicitly included they are marked `ZERO_LOCATOR_ONLY`; direct item-level acquisition is required before semantic closure.

## Trading MMT website

Discovery established a GitHub-runner `ENVIRONMENT_ACCESS_FAILURE`. Acquisition must preserve that distinction. Secondary/search-index pages may locate first-party URLs but receive zero semantic closure credit; direct first-party payload acquisition is required before website content can support a semantic field.

## Forbidden here

- strategy synthesis or interpretation;
- trade counts or performance metrics;
- detector/backtester/optimizer logic;
- secondary/community semantic closure;
- private/authenticated source access;
- live brokerage access.
