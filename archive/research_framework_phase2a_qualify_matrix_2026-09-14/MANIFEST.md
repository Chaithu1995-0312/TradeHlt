# research_framework_phase2a_qualify_matrix_2026-09-14

- Plan: research-framework consolidation, Phase 2 (QUALIFY-family scope loop), batch 2a
- Policy: **no deletes** — every edited file copied here byte-exact first; the new module recorded `created`

## Change

1. New `src/research/qualify_matrix.py`: `csv_map(cfg, instruments)`, `winning_control(per_by_hyp, control_names,
   scope_instruments, agg, cost)`. Adds no statistics.
2. Private `_csv_map` replaced in place by
   `from research.qualify_matrix import csv_map as _csv_map  # noqa: E402 — research-framework Phase 1 dedup`:

| File | Removed lines |
|---|---|
| scripts/research/qualify_carry.py | 9 |
| scripts/research/qualify_cross_sectional.py | 9 |
| scripts/research/qualify_harvest.py | 9 |
| scripts/research/qualify_regime_conditioning.py | 9 |
| scripts/research/qualify_regime_transition.py | 9 |

## Parity evidence

- AST-normalized-body fingerprint gate refused any def not structurally identical to the approved variant.
- `--help` stdout SHA-256 + exit code identical before/after for all 5 CLIs.
- Identity: `_csv_map is research.qualify_matrix.csv_map` in all 5 modules.
- `tests/research/test_qualify_matrix.py` (new, 6 tests) + `tests/research/test_carry.py` + `test_harvest.py` green.
- See `archive/ARCHIVE_INDEX.md` for the full Phase 2 corpus A/B evidence.
