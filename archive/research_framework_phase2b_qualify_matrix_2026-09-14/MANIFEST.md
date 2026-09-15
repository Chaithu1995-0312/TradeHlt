# research_framework_phase2b_qualify_matrix_2026-09-14

- Plan: research-framework consolidation, Phase 2 (QUALIFY-family scope loop), batch 2b
- Policy: **no deletes** — every edited file copied here byte-exact first

## Change

Private `_csv_map` / `_winning_control` replaced in place by same-named imports of
`research.qualify_matrix.csv_map` / `.winning_control`:

| File | Defs replaced |
|---|---|
| scripts/research/qualify_fx_metals.py | `_csv_map`, `_winning_control` |
| scripts/research/qualify_htf.py | `_winning_control` (its `_csv_map` takes a `tf` arg — a genuinely different function, left local) |
| scripts/research/qualify_m5_straddle.py | `_csv_map`, `_winning_control` |
| scripts/research/qualify_majors.py | `_csv_map`, `_winning_control` |
| scripts/research/qualify_transitions.py | `_csv_map`, `_winning_control` |
| scripts/research/qualify_weekly_sweep.py | `_csv_map`, `_winning_control` |

## Parity evidence

- AST-normalized-body fingerprint gate refused any def not structurally identical to the approved variant.
- `--help` stdout SHA-256 + exit code identical before/after for all 6 CLIs.
- Identity: private name `is` the shared `research.qualify_matrix` function in all 6 modules (11/11 defs).
- `tests/research/test_qualify_matrix.py` green.
- End-to-end corpus A/B on `qualify_majors.py` (original archived bytes vs live, same argv): both exit 1 at the
  identical pre-existing clock-provenance gate line, byte-identical output trees — see `archive/ARCHIVE_INDEX.md`
  for the full account (`winning_control` is not reached before that gate; its parity rests on the AST-identity
  proof + the dedicated unit tests in `test_qualify_matrix.py`).
