# Specification Workspace

This directory contains deterministic strategy specifications only after evidence synthesis.

Until `SPEC_READY = true`, documents here may contain schemas, audit procedures, unresolved field inventories, contradiction records, and **failed readiness audit artifacts**, but **must not** contain executable strategy rules presented as closed.

A passing specification must satisfy all required fields, contradiction handling, provenance completeness, the two-engineer test, and independent evidence-only reconstruction before it is frozen and versioned.

## Independent readiness audit

`docs/spec/SPEC_AUDIT.json` is the durable output of the independent evidence-only readiness audit. A successful CI/workflow run means the audit artifact is internally valid; it does **not** mean the strategy passed.

Interpret the artifact using its explicit fields:

- `spec_ready: true` and `overall_outcome: PASS` are required before implementation can be authorized;
- `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE` means the matrix is auditable but required semantics remain unresolved and bounded recovery work must continue;
- `INSUFFICIENT_EVIDENCE` means no safe evidence-only reconstruction can currently be made;
- a failed audit must have `implementation_authorized: false` and no frozen spec reference.

The auditor uses a separate code path from the Phase 5 matrix builder, verifies cited evidence against direct first-party acquisition/provenance, and refuses executable reconstruction while any canonical required field is `MISSING`, `PARTIAL`, or `CONTRADICTORY`.
