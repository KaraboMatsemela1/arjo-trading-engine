# Research Schemas

## Source registry

`research/source_registry.csv`

Required fields:

`SOURCE_ID`, `SOURCE_TYPE`, `TITLE`, `URL`, `PUBLICATION_DATE`, `AUTHOR`, `CHANNEL_ID`, `FIRST_PARTY_STATUS`, `RETRIEVAL_DATE`, `RAW_ARTIFACT_SHA256`, `TRANSCRIPT_AVAILABLE`, `FRAME_EXTRACTION_AVAILABLE`, `NOTES`.

## Acquisition manifest

`research/acquisition_manifest.jsonl`

Each line is a JSON object describing one retrieval attempt. Required semantic fields:

- `source_id`
- `artifact_type`
- `retrieval_time`
- `status`
- `locator`
- `sha256` when a payload was captured
- `notes`

Allowed acquisition status values:

- `ENVIRONMENT_ACCESS_FAILURE`
- `SOURCE_CONTACTED_NO_PAYLOAD`
- `PAYLOAD_CAPTURED`
- `SOURCE_REMOVED`
- `SOURCE_UNAVAILABLE_AFTER_CONTACT`

Transport failure must never be recorded as evidence absence.

## Evidence registry

`research/evidence_registry.jsonl`

Each atomic evidence record must contain:

- `EVIDENCE_ID`
- `SOURCE_ID`
- `TIMESTAMP`
- `MINIMAL_QUOTE`
- `FRAME_LOCATOR`
- `SUPPORTED_CONCEPT`
- `SUPPORTED_FIELD`
- `WHAT_IT_PROVES`
- `WHAT_IT_DOES_NOT_PROVE`
- `CONFIDENCE`

Allowed confidence values:

`DIRECT`, `STRONG_PARTIAL`, `CONTEXTUAL`, `INSUFFICIENT`.

## Predicate matrix

`research/predicate_matrix.csv`

Each row represents one predicate field and must use one of:

`SATISFIED`, `PARTIAL`, `MISSING`, `CONTRADICTORY`, `NOT_APPLICABLE`.

A `SATISFIED` field must reference at least one evidence ID. Evidence confidence is not silently promoted during synthesis.
