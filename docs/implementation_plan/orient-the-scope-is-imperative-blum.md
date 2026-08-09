# Plan — Verify & correct the backtest OHLCV file-read trace

## Context

A prior session produced a narrative trace of "how the backtest reads/validates OHLCV from
files." The user asked to **verify that trace against the real source and correct any drift
before it gets documented** (chosen deliverable: *Verify trace vs code*).

Verification (2 Explore sweeps + direct reads of the cited lines) found the narrative carried
several material errors, AND surfaced two genuine pre-existing drifts inside the repo itself
(a stale code comment and a stale doc citation). Per CLAUDE.md §6.2 this is **documentation
entropy (DOC_DRIFT), not a new economic/governance finding** — so the fix is surgical doc/comment
corrections into the docs that already own this material (existing-doc-first, no new doc, no new
F-id).

Ground truth established (file:line):
- `Candle` dataclass → `src/config_layer/crt_engine_v2.py:94-102`
  (`volume: float = 0.0`, `index: int = 0` have **defaults**; has `body_size`/`wick_size` props).
- CSV reader → `CandleLoader.stream()` in `src/runtime/backtest_v2.py:704-769`
  (lives **in** the runtime module, not data_ingestion). It delegates only *per-field validation
  helpers* to `src/data_ingestion/ohlcv_schema.py`: `require_unique_ohlcv_headers`,
  `require_ohlcv_columns`, `parse_ohlcv_timestamp`, `validate_ohlcv_row`, `OHLCV_DATE_FORMATS`.
- Always-on inline integrity in `stream()`: L1 duplicate-header reject (line 710) + L2
  duplicate/out-of-order timestamp backstop (lines 745-755) + Phase-1 column / Phase-2 value
  validation (raises, no silent skip).
- Full pre-flight gate → `dataset_integrity.validate_dataset()` returning
  `DatasetDecision.{APPROVE,WARN,REJECT}` (`src/data_ingestion/dataset_integrity.py:90-96`),
  called only by `MultiInstrumentRunner._preflight_dataset` (`backtest_v2.py:2542`), NOT by a
  standalone `BacktestRunner`; `backtest_bitnet.py` skips it (relies on the inline backstop).
- Feature enrichment → `FeaturePipeline.run()` (`feature_pipeline.py:805`) is **batch** over a
  DataFrame returning `(enriched_df, vectors)`; methods are `run()` + `finalize()` — there is **no**
  `transform(candle, history)`.
- Canonical vector = **38-dim**, indices 0-4 = open/high/low/close/volume
  (`feature_schema.py:46-76`, hard-asserted).
- `FeatureMonitor` (Z>3.0 hard → WARNING, updated on `TRADE_OPENED`) and
  `EXPECTED_ENGINES = {"crt","gaussian","zone_gate","rr"}` (`engine_runner.py:52`) — **verified accurate**.

## Changes

### 1. Code comment fix (hash-neutral, comment-only) — `src/features/feature_schema.py:45`
`# Total vector dimension = 32.` → `# Total vector dimension = 38.`
(The constant `CANONICAL_FEATURE_DIM = 38` on line 76 and two `assert`s already enforce 38; only the
comment is stale.) No rehash — comment change, not a `params` edit.

### 2. `docs/architecture/signal-flow.md` — Step 1 & Step 2 (real drift)
- **Step 2 entry point** (line 41): `FeaturePipeline.transform(candle, history)` →
  `FeaturePipeline.run()` (batch enrich → `(enriched_df, vectors)`). Remove the non-existent
  `transform` symbol so `tests/test_doc_citations.py` (±30-line window) resolves to a real symbol.
- **Step 2 dim** (line 42): `CANONICAL_FEATURES (35-dim)` → `(38-dim)`.
- **Step 2 emit framing** (line 44): clarify enrichment is **batch up-front**, then candles are
  streamed per-bar by `CandleLoader.stream()` into the engine loop — reconcile with the doc's
  "runs once per candle" framing (the per-bar unit is the *candle stream*, not a per-candle feature
  call).
- **Step 1** (lines 29-36): name the actual reader `CandleLoader.stream()` and the two-tier
  integrity model (always-on inline L1/L2 backstop in `stream()` + optional pre-flight
  `dataset_integrity.validate_dataset` via `MultiInstrumentRunner`). Keep edits surgical.

### 3. `docs/reference/schemas.md §2.1` Candle (minor alignment) — lines 27-36
Add the real defaults and fix the inline comment so the documented dataclass matches source:
`volume: float = 0.0`, `index: int = 0  # candle position; [PATCH 4] time-based rules`.
(Module citation `crt_engine_v2.py` is already correct — no change there.)

### 4. Topic sync (§6.4) — conditional
If a `docs/topics/` file covers feature-schema/ingestion, apply the 35→38 + `transform`→`run`
correction there too (only that file; bump `Updated:`). If none exists, skip — do **not** create one.

## Out of scope
- No new doc, no new `F-id` (this is DOC_DRIFT cleanup, §6.2 rule 1/5).
- No behavior change, no config edit, no rehash.
- The "two-tier integrity" and "rr=gaussian duplicate (F-038)" architecture questions are already
  tracked elsewhere — not reopened here.

## Verification
1. `python -m pytest tests/test_doc_citations.py -q` — Step-2 citation must resolve to a real
   symbol (`FeaturePipeline.run`) within the ±30-line window.
2. `python -m pytest tests/test_topic_docs.py -q` — if a topic file was touched.
3. `python -c "import src.features.feature_schema"` — import still passes the 38-dim asserts
   (sanity; comment change can't break it but confirms no accidental edit).
4. Grep guard: `rg "transform\(candle" docs/` and `rg "35-dim|dimension = 32" docs src/` return
   nothing after the edits.
5. Append the §6 SESSION LOG entry to `assistant_project.md` recording the DOC_DRIFT corrections
   (codebase log — it touches governed docs + a code comment).
