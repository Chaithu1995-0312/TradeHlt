# Resume IC-003B (H-IC003B-001) from on-disk checkpoints

## Context

IC-003B is the sequence-geometry **shape library** research program (representation
redesign after IC-003 v1 was archived `LIBRARY_FAIL`). It was **safely paused** on
2026-07-16 before a system restart, mid-run. All worker PIDs were killed intentionally;
state survives only via disk checkpoints. This session must **finish the run** — not
re-plan, not restart from scratch.

Verified state (read-only checks this session):
- `checkpoint.json` → `"status": "PAUSED"`, `completed_units: [S_N4, T_N4]`.
- On disk & intact: `arm_S_N4/{shapes.json,assignment.jsonl}`, `arm_T_N4/{shapes.json,assignment.jsonl}`.
- Pending: `C_N4, S_N16, T_N16, C_N16, S_N8, T_N8, C_N8`.
- `scripts/research/ic003b_build.py` exposes `--resume` (default), `--fresh`, `--mark-paused`.

The long pole is **Arm T N=16** — pure-Python banded DTW over ~4.5M upper-triangle
pairs (subsample 3000), GIL-bound to ~1 core, ~2.5–3.5h. Total remaining ~3–4h.

## Plan

**Step 1 — P0 resume (the mandatory action).** Run:
```powershell
cd D:\Tradelatest
$env:PYTHONPATH='src'
python scripts/research/ic003b_build.py --resume
```
Run it **in the background** (3–4h job) so the session is notified on completion rather
than blocking. Confirm the log shows `SKIP Arm S N=4` / `SKIP Arm T N=4` (checkpoint hit)
early — if it recomputes N=4 instead of skipping, stop and investigate (do **not** let it
silently overwrite the N=4 checkpoints).

**Step 2 — On completion, record the verdict.** Expected outputs:
`REPORT.md`, `report.json`, `SHAPE_LIBRARY.md`, and `checkpoint.json → "RUN_COMPLETE"`.
Read `REPORT.md`; record `program_verdict` ∈ {`IC003B_LIBRARY_OK`, `IC003B_PARTIAL`,
`IC003B_FAIL`}. **Accept `FAIL` as-is** — do not touch G1.

**Step 3 (optional, only if asked) — P1 DTW profile.** Per
`docs/research-readiness/erp-geometry-compute-doctrine.md` Stage 1: profile Arm T to
measure the % wall in `dtw_euclidean`/`pairwise_dtw` vs assign vs JSON. No algorithm
swap, no `DistanceEngine` build, no GPU unless the user explicitly asks and Stage-1
evidence supports it.

## Hard constraints (from the handoff — must obey)

1. **RESEARCH_ONLY** — no production config change from IC-003B.
2. **G1 = 0.85** for Arm S — never amend gates to force `LIBRARY_OK`.
3. **No `--fresh`** unless the user explicitly accepts losing the N=4 checkpoints.
4. **No GPU rental** this week without Stage-1 profile evidence.
5. **`LIBRARY_OK ≠ expectancy / production authority`** (§6.5).
6. Append the §6 SESSION LOG block to `assistant_project.md` on completion.

## Files

- Driver: `scripts/research/ic003b_build.py`
- Orchestrator/checkpoint: `src/research/ic003b_sequence_geometry/build_all.py`
- DTW wall: `src/research/ic003b_sequence_geometry/dtw.py`, `cluster_dtw.py`
- Gates/schema (G1=0.85): `src/research/ic003b_sequence_geometry/schema.py`
- Prereg (frozen): `docs/research-readiness/h-ic003b-sequence-geometry-preregistration.md`

## Verification

- Early: resume log shows `SKIP` for both N=4 arms (checkpoint honored).
- End: `checkpoint.json` `status == "RUN_COMPLETE"` and `REPORT.md` + `report.json` +
  `SHAPE_LIBRARY.md` exist with a `program_verdict`.
- If a mid-run pause is needed: `python scripts/research/ic003b_build.py --mark-paused`
  (per-arm artifacts already flush after each finished S/T/C unit).
