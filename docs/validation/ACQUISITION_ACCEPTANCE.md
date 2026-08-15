# Acquisition Tooling Acceptance

Issue #4 passes only when all of the following hold:

1. deterministic Python compilation passes;
2. offline fixture smoke test passes;
3. acquisition manifest schema validation passes;
4. project dependency/claim/gate/provenance guards pass;
5. the Issue #4 PR has no unresolved review threads;
6. after merge, `Acquisition Tooling Smoke` contacts one registered first-party YouTube item and records `PAYLOAD_CAPTURED` with SHA-256 provenance;
7. the smoke record has `semantic_extraction_performed=false`.

Only then may `ACQUISITION_TOOLING_READY` unlock corpus acquisition Issue #5.
