# research_framework_phase1e_provenance_2026-09-14

- Plan: research-framework consolidation, Phase 1 (provenance helpers), batch 1e
- Policy: **no deletes** — every edited file copied here byte-exact first; SHA-256 before/after in `MANIFEST.csv`
- Change: Phase 1e dedup: private _sha (streaming 1MiB SHA-256, variant 6ac2da0004) -> same-named import of research.provenance.sha256_file; call sites unchanged

| File | Removed def | Now imported as same name from | `--help` stdout before/after |
|---|---|---|---|
| scripts/analysis/feature_pipeline_fc05_closure.py | `_sha` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/feature_semantic_adjudication_pass_a.py | `_sha` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/phase1_run1_feature_truth.py | `_sha` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/xauusd_phase1_finish_validation.py | `_sha` | `research.provenance.sha256_file` | not executed (no argparse) |

## Parity evidence

- Edit tool refuses any def whose AST-normalized body is not an approved variant of the shared function.
- Identity: in every edited module the private name `is` the shared `research.provenance` function (module imports).
- Shared functions pinned against verbatim copies of every replaced variant: `tests/research/test_provenance_helpers.py`.
- File line endings / BOM preserved; `py_compile` clean.
