# logs/ — LOCAL_TELEMETRY (INV-053)

Append-only JSONL streams. **Not in git.** See
[`docs/governance/GITIGNORE_SCHEMA.md`](../docs/governance/GITIGNORE_SCHEMA.md).

What a stream may *prove* is catalogued in
`docs/governance/jsonl_claim_catalog.yaml`. The catalog is not the stream.
`logs/crt_transitions.jsonl` has no RESET; folding it is a wrong series.

A clone recaptures telemetry. It does not recover a historical occupancy series
from git.
