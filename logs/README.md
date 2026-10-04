# logs/ — LOCAL_TELEMETRY (INV-053)

Append-only JSONL streams. **Not in git.** See
[`docs/governance/GITIGNORE_SCHEMA.md`](../docs/governance/GITIGNORE_SCHEMA.md).

What a stream may *prove* is catalogued in
`docs/governance/jsonl_claim_catalog.yaml`. The catalog is not the stream.
`logs/crt_transitions.jsonl` has no RESET; folding it is a wrong series.

A clone recaptures telemetry. It does not recover a historical occupancy series
from git.

Run-id → artifact **binding** is not this tree. It lives at
[`docs/governance/run_linkage_registry.json`](../docs/governance/run_linkage_registry.json)
(TRACKED_BINDING). `src/utils/run_linkage.py` reads that file, not a gitignored
`logs/run_linkage_registry.json`.

**2026-10-01 archive.** Trees last written before 2026-09-01, plus the three
scratch copies `dual_construction`, `dual_construction_v2`, and
`dual_construction_f069_remeasure_20260909`, were packed to
`D:\Tradelatest-archives\2026-10-01\` and removed from this folder. The registry
copy `dual_construction_full_gapfix` stayed. Live append streams
(`sweep_lifecycle.jsonl`, `crt_transitions.jsonl`, `llm_episodes*.jsonl`,
`feature_snapshots.jsonl`, and the others at this root) stayed because a
backtest was still writing them. Manifest: `MANIFEST.jsonl` beside the packs.
