# research_framework_phase1b_provenance_2026-09-14

- Plan: research-framework consolidation, Phase 1 (provenance helpers), batch 1b
- Policy: **no deletes** — every edited file copied here byte-exact first; SHA-256 before/after in `MANIFEST.csv`
- Change: Phase 1b dedup: private _git_commit (variant 9b89feee8d) -> research.provenance.git_commit; private _utc_now (variant 8a3c0b1dff) -> research.provenance.utc_now_iso; same-named imports, call sites unchanged

| File | Removed def | Now imported as same name from | `--help` stdout before/after |
|---|---|---|---|
| scripts/research/m5_mtf_information.py | `_git_commit` | `research.provenance.git_commit` | identical `1057b456874b08c8` |
| scripts/research/phase_b_conditional_entropy.py | `_git_commit` | `research.provenance.git_commit` | identical `4994b1aaf62f6240` |
| scripts/research/phase_d_exit_grid.py | `_git_commit` | `research.provenance.git_commit` | identical `3bb2014cd3ff2b71` |
| scripts/research/phase_e_structural_asymmetry.py | `_git_commit` | `research.provenance.git_commit` | identical `e6809a570c3ca0b0` |
| scripts/research/phase_s_selection_effect.py | `_git_commit` | `research.provenance.git_commit` | identical `a9c9e4c4cf880214` |
| scripts/research/rr_kill_test_clean_l3.py | `_utc_now` | `research.provenance.utc_now_iso` | identical `931079a9d6e22f0f` |
| scripts/research/rr_l2_feature_truth.py | `_utc_now` | `research.provenance.utc_now_iso` | identical `4d500ced9b2dca1b` |
| scripts/research/rr_l3_label_generation.py | `_utc_now` | `research.provenance.utc_now_iso` | identical `ccb4132dbb2ffa61` |
| scripts/research/rr_l4_research_execution.py | `_utc_now` | `research.provenance.utc_now_iso` | identical `8f50852bca346207` |

## Parity evidence

- Edit tool refuses any def whose AST-normalized body is not an approved variant of the shared function.
- Identity: in every edited module the private name `is` the shared `research.provenance` function (module imports).
- Shared functions pinned against verbatim copies of every replaced variant: `tests/research/test_provenance_helpers.py`.
- File line endings / BOM preserved; `py_compile` clean.
