# Specification Workspace

This directory contains deterministic strategy specifications only after evidence synthesis.

Until `SPEC_READY = true`, documents here may contain schemas, audit procedures, unresolved field inventories, contradiction records, and **failed readiness audit artifacts**, but **must not** contain executable strategy rules presented as closed.

A passing specification must satisfy all required fields, contradiction handling, provenance completeness, an independent two-engineer test, and independent evidence-only reconstruction before it is frozen and versioned.

## Independent readiness audit

`docs/spec/SPEC_AUDIT.json` is the durable output of the independent evidence-only readiness audit. A successful CI/workflow run means the audit artifact is internally valid; it does **not** mean the strategy passed.

Interpret the artifact using its explicit fields:

- `spec_ready: true` and `overall_outcome: PASS` are required before implementation can be authorized;
- `BLOCKED_NEEDS_FIRST_PARTY_EVIDENCE` means required semantics remain unresolved and bounded recovery work must continue;
- `BLOCKED_NEEDS_INDEPENDENT_RECONSTRUCTION_PACKET` means the matrix may be structurally evidence-complete but still lacks the separately reviewed independent reconstruction/two-engineer packet required for promotion;
- `INSUFFICIENT_EVIDENCE` means no safe evidence-only reconstruction can currently be made;
- a failed audit must have `implementation_authorized: false` and no frozen spec reference.

The Phase-5 `two_engineer_preflight.json` artifact is a deterministic **two-code-path reconstruction preflight only**. It verifies reproducibility of the persisted Phase-5 representation; it is not the independent two-engineer test and cannot by itself satisfy `SPEC_READY`.

The independent auditor uses a separate code path from the Phase-5 matrix builder, verifies cited evidence against direct first-party acquisition/provenance, validates exactly one row for each of the 16 canonical fields, and refuses independent executable reconstruction while any required field is `MISSING`, `PARTIAL`, or `CONTRADICTORY`.

A future evidence-complete candidate must still provide an explicit, independently reviewed reconstruction/two-engineer packet before `independent_two_engineer_test=PASS`, `independent_reconstruction=PASS`, or `SPEC_READY=true` can be asserted.
