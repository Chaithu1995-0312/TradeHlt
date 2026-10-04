# research_framework_phase1a_provenance_2026-09-14

- Plan: research-framework consolidation, Phase 1 (provenance helpers), batch 1a
- Policy: **no deletes** — every edited file copied here byte-exact first; SHA-256 before/after in `MANIFEST.csv`

## Change

1. `src/research/provenance.py` — additive: `git_commit()`, `sha256_file(path)`, `utc_stamp_compact()`,
   `utc_now_iso()`. Existing `truth_standard_block` / `production_config_block` / `provenance_block` untouched.
2. Private `_git_commit` (AST-normalized body variant `9b89feee8d`, i.e. `git rev-parse HEAD` from process cwd,
   `"unknown"` on failure) replaced in place by
   `from research.provenance import git_commit as _git_commit  # noqa: E402 — research-framework Phase 1 dedup`:

| File | Removed lines |
|---|---|
| scripts/research/qualify_carry.py | 6 |
| scripts/research/qualify_cross_sectional.py | 6 |
| scripts/research/qualify_fx_metals.py | 6 |
| scripts/research/qualify_harvest.py | 6 |
| scripts/research/qualify_htf.py | 6 |
| scripts/research/qualify_m5_straddle.py | 6 |
| scripts/research/qualify_majors.py | 6 |
| scripts/research/qualify_regime_conditioning.py | 6 |
| scripts/research/qualify_regime_transition.py | 6 |
| scripts/research/qualify_transitions.py | 6 |
| scripts/research/qualify_weekly_sweep.py | 6 |
| scripts/research/qualify_zone_topk.py | 6 |
| scripts/research/transition_information.py | 6 |
| src/research/cli.py | 6 |

Not folded in (different behavior, left local): the 3 `_git_commit` copies that pass `cwd=_ROOT` + `timeout=5`
(`scripts/analysis/bnb_ema_gate_ab.py`, `process_characterizer.py`, `process_diagnostics.py`) and 2 single variants.

## Parity evidence

- Edit tool refuses any def whose AST-normalized body is not an approved variant (no same-name-different-behavior swap).
- `--help`: stdout SHA-256 and exit code identical before/after for all 14 CLIs.
- Identity: in every edited module `_git_commit is research.provenance.git_commit` (import succeeds).
- `tests/research/test_provenance_helpers.py` (10 tests) pins the shared helpers against verbatim copies of every
  replaced variant (sizes 0 … 3 MiB+7, str/Path, missing file, in/out of a git repo, stamp formats).
- `tests/research/test_carry.py`, `tests/research/test_harvest.py` green.
- Line endings preserved (tool writes back with the file's own EOL / BOM).
