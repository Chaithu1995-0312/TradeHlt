# research_framework_phase1c_provenance_2026-09-14

- Plan: research-framework consolidation, Phase 1 (provenance helpers), batch 1c
- Policy: **no deletes** — every edited file copied here byte-exact first; SHA-256 before/after in `MANIFEST.csv`
- Change: Phase 1c dedup: private _sha256/_sha256_file (streaming 1MiB SHA-256, variant 58ea5a0042) -> same-named import of research.provenance.sha256_file; call sites unchanged

| File | Removed def | Now imported as same name from | `--help` stdout before/after |
|---|---|---|---|
| scripts/analysis/blind_label_sample.py | `_sha256` | `research.provenance.sha256_file` | identical `f57765bf1443405e` |
| scripts/analysis/crt_xauusd_runtime_trace.py | `_sha256` | `research.provenance.sha256_file` | identical `0a06d9a374eefa33` |
| scripts/analysis/feature_trace_report.py | `_sha256` | `research.provenance.sha256_file` | identical `80831e1b2c598d10` |
| scripts/analysis/mature_semantic_audit.py | `_sha256` | `research.provenance.sha256_file` | identical `e03a9a3fd5dfa2bb` |
| scripts/analysis/mother_range_inside_close.py | `_sha256` | `research.provenance.sha256_file` | identical `a5bcaf9fc804f55f` |
| scripts/analysis/semantic_layer_validation.py | `_sha256` | `research.provenance.sha256_file` | identical `e83b503ca8e1c92a` |
| scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py | `_sha256` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/xauusd_excel_feature_state_trace.py | `_sha256` | `research.provenance.sha256_file` | identical `6cee202cd90dfbdd` |
| scripts/research/mc_cpr_l0_residual_harness.py | `_sha256` | `research.provenance.sha256_file` | identical `f381a795f062b9da` |
| scripts/research/xauusd_episode_semantic_reconstruction.py | `_sha256` | `research.provenance.sha256_file` | identical `007bd0cde80af026` |
| scripts/analysis/implementation_model_validation_xauusd.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/phase1_resolver_replay_evidence.py | `_sha256_file` | `research.provenance.sha256_file` | identical `e9485eded7a91d78` |
| scripts/analysis/phase1_resolver_replay_sample_acquisition.py | `_sha256_file` | `research.provenance.sha256_file` | identical `e200abc1d47a7511` |
| scripts/analysis/phase1_shadow_memory_subsystem_probe.py | `_sha256_file` | `research.provenance.sha256_file` | identical `061ac4917c7d328a` |
| scripts/analysis/run_gaussian_xauusd_2m.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |

## Parity evidence

- Edit tool refuses any def whose AST-normalized body is not an approved variant of the shared function.
- Identity: in every edited module the private name `is` the shared `research.provenance` function (module imports).
- Shared functions pinned against verbatim copies of every replaced variant: `tests/research/test_provenance_helpers.py`.
- File line endings / BOM preserved; `py_compile` clean.
