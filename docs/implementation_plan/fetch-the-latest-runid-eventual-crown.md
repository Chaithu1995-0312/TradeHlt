# Full-corpus XAUUSD feature frame → Parquet + DuckDB views + .xlsx

## Context
User wants the entire XAUUSD M15 feature frame (all 91 pipeline columns, full corpus) saved as
Parquet, queryable in DuckDB, and as an Excel file. Exploration found most of this already exists:
`scripts/research/build_bar_matrix.py` (SCR-412) wrote
`results/research/bar_matrix/XAUUSD_M15/bar_matrix.parquet` on 2026-09-09 — 47,197 rows × 124 cols,
manifest-pinned (`corpus_sha256 4d73f5ce…`, schema v5.0, `feature_order_hash 160c96c52b198a16`,
`parquet_written: true`), already a `bar_matrix` family in `scripts/analysis/query_trace.py`.
Its first 91 columns ARE the pipeline block (90 feature cols + `_pos`, the raw-corpus position it
attaches before `FeaturePipeline.run()`); the other 33 are `atr_abs`, 19 `state__*`, CRT/parent/
candle/regime/intent. A read-only check matched my fresh pipeline run on the first 50 rows exactly,
but `src/features/` has commits since 09-09, so that is not full-corpus proof.

User decisions (AskUserQuestion): (1) rebuild bar_matrix + verify the full corpus, AND (3) a separate
features-only Parquet; DuckDB = views over Parquet (repo convention, no .db file); install openpyxl
and write a full .xlsx.

Also owed (E-001 correction, this session): I told the user `trades.csv` had "90 cols" and wrote that
into `docs/topics/feature-schema.md`; the header actually has **86**. And "91 columns" for my scratch
dump was 90 + my own `row_after_warmup` index (the bar_matrix pipeline block is genuinely 91 because
of `_pos`).

## Approach — extend the existing builder, no new script

### 1. `scripts/research/build_bar_matrix.py` (one pipeline pass, three outputs)
- In `build_bar_matrix()`, right after the pipeline checks (~line 183, before `atr_abs` is added at
  :187), snapshot `feature_cols = list(enriched.columns)` (the 91-col block). Record in manifest:
  `feature_columns`, `feature_column_count`.
- Add code identity to the manifest (concurrent sessions + dirty tree make "which code built this"
  otherwise unanswerable): `git_sha` and `tree_dirty` via existing `utils.run_manifest._git`
  (`src/utils/run_manifest.py:49`).
- In `main()`, after the existing `bar_matrix.parquet` write (:368-373), mirror its exact
  optional-writer pattern:
  - `frame[feature_cols].to_parquet(out_dir / "features.parquet", index=False)` →
    `features_parquet_written` / `features_parquet_skipped_reason`.
  - New opt-in flag `--xlsx` (default off, so smoke/limit runs stay fast and default outputs are
    unchanged): `frame[feature_cols].to_excel(out_dir / "features.xlsx", index=False,
    sheet_name="features")` inside try/except → `features_xlsx_written` /
    `features_xlsx_skipped_reason` (missing openpyxl or >1,048,575 rows recorded, never raised).
- No change to bar_matrix.csv / bar_matrix.parquet content or column order.

### 2. `scripts/analysis/query_trace.py` (DuckDB views)
- Add family `"bar_matrix_features": ("results/research/bar_matrix/**/features.parquet",)` and add it
  to `_NON_PROJECTION_FAMILIES`.
- Generalize `_bar_matrix_parquet_ok(projection)` to pick the manifest flag by filename
  (`bar_matrix.parquet` → `parquet_written`, `features.parquet` → `features_parquet_written`), so a
  skipped features write is REFUSED exactly like a skipped bar_matrix write.
- Lineage (`assert_view_lineage`, ~:292): `if fam in _NON_PROJECTION_FAMILIES` instead of
  `== "bar_matrix"` — both read `corpus_sha256` from the same sibling `manifest.json`.
- `tests/test_query_trace.py`: add `test_bar_matrix_features_refused_when_parquet_not_written`,
  modelled on the existing `test_bar_matrix_refused_when_parquet_not_written` (:244).

### 3. Environment
- `venv/Scripts/python.exe -m pip install openpyxl` (user-authorized). Not adding a pyproject extra:
  `pyproject.toml` has another session's uncommitted edits; the writer is optional-guarded anyway.

### 4. Build (background, ~6–10 min; prior build 321 s + xlsx)
- Preflight per CLAUDE.md: `git status --porcelain`, confirm `sys.prefix` = `D:\Tradelatest\venv`.
- Move the 09-09 artifacts aside (reversible, not deleted): copy `bar_matrix.parquet` +
  `manifest.json` to the scratchpad as `*_20260909` for the old-vs-new diff.
- `venv/Scripts/python.exe scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15 --xlsx`

### 5. Doc sync + log
- `docs/topics/feature-schema.md` Discussion entry: `trades.csv (90 cols` →
  `trades.csv (86 cols; CORRECTED 2026-09-16: was "90")`; add one dated line naming `features.parquet`
  / `features.xlsx` / the `bar_matrix_features` query family.
- Append a SESSION LOG ENTRY to `assistant_project.md` (Edit-append only; concurrently modified file).

## Verification
1. **Full-corpus independent check** (scratchpad script, separate process): fresh
   `FeaturePipeline(raw_with__pos).run()` vs `features.parquet` over all 47,197 rows × 91 cols —
   numeric `allclose(rtol=1e-9, equal_nan)`, strings/timestamps exact; `_pos` strictly increasing;
   48/48 `CANONICAL_FEATURES` present, no NaN.
2. **Old vs new bar_matrix**: column-by-column diff of the 09-09 copy vs rebuilt parquet → report which
   columns (if any) changed, i.e. whether the 09-09 artifact was stale.
3. **features.parquet == bar_matrix.parquet[:91 cols]** exactly (same pass, must be identical).
4. **DuckDB**: `venv/Scripts/python.exe scripts/analysis/query_trace.py --family bar_matrix_features
   --sql "select count(*), count(distinct _pos), min(timestamp), max(timestamp) from bar_matrix_features"`
   → 47197 / 47197 / 2024-05-22 20:30:00 / 2026-05-21 23:45:00; also a two-view query joining
   `bar_matrix` ⋈ `bar_matrix_features` on `_pos` (lineage banner must pass, same corpus_sha256).
5. **xlsx**: reopen with openpyxl `read_only=True` → 47,198 rows (incl. header) × 91 cols; first and
   last data rows equal the parquet.
6. **Floors**: `pytest tests/test_query_trace.py -q` and
   `pytest tests/test_topic_docs.py tests/test_doc_citations.py -q` green.
7. Send `features.xlsx` path + DuckDB query output to the user (SendUserFile for the xlsx, ~40MB).

## Out of scope
No change to FeaturePipeline, schema, active config, or bar_matrix column content. No persistent
.duckdb file. No commit unless asked.
