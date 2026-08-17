# NQ Calibration Data Pipeline Contract

Issue: #140

Gate published by this work: `CALIBRATION_DATA_PIPELINE_READY`.

The provider contract is frozen to Databento `GLBX.MDP3`, continuous `NQ.v.0`, `ohlcv-1m`, `stype_in=continuous`, `stype_out=instrument_id`, from `2024-01-01T00:00:00Z` through the exclusive ceiling `2026-01-01T00:00:00Z`.

The protected holdout begins at `2026-01-01T00:00:00Z`; requests or normalization at or beyond that boundary fail closed. Continuous prices remain unadjusted and contract identity is retained through `instrument_id`. Local aggregation is deterministic from complete 1-minute buckets only and rejects a bucket that spans a contract roll or contains missing/duplicate minutes.

Licensed/raw DBN payloads stay outside git. CI runs only synthetic/offline tests and never receives a Databento credential.
