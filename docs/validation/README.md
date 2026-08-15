# Validation Workspace

Validation is staged and gate-controlled.

Before `SPEC_READY`, validation is limited to provenance, schema, contradiction, deterministic reconstruction, and gate-integrity checks. Strategy activity or performance evaluation is forbidden.

After preregistration, validation proceeds in order:

1. DEV activity
2. DEV performance
3. one-time OOS
4. one-time CONFIRM

Protected datasets must be guarded deterministically and may not be opened early.
