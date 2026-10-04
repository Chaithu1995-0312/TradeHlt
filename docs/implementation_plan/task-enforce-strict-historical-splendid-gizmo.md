# Enforce Strict Historical Data Schema (No Defaults)

## Context

Historical OHLCV ingestion across the codebase silently papers over missing data:
`CandleLoader` treats `volume` as optional, `FeaturePipeline` injects `volume = 0.0`
when the column is absent ("Forex safe fallback"), `historical_fetcher`/`sl_tp_comparator`
cascade `.get("open", .get("Open", 0))`, and the governance/runtime row-readers default
every field to `0.0`. The result: a malformed dataset (missing a whole column) produces
silent zero-filled candles instead of a hard failure, corrupting backtests, training data,
and live decisions without any signal that the source was broken.

**Goal:** any historical dataset missing one of the six mandatory columns must fail
immediately and loudly. No defaults, no auto-generation, no column substitution, no
zero/one-fill for `timestamp, open, high, low, close, volume`.

## Decisions (locked with user)

1. **Volume rule = column presence.** The `volume` column must physically exist or load
   fatal-errors. Remove only the silent *inject-when-absent* fallback. **Keep** the
   existing `compute_volume_features()` high-low proxy for files that genuinely carry an
   all-zero volume column (Forex). Real zero values in a present column are valid data.
2. **Scope = everything**: historical DataFrame loaders + CSV/dict row loaders + live
   intake (`live_engine_hook`) + strategy plugins `s01–s10`.
3. **Only the six OHLCV fields are governed.** Derived/auxiliary feature defaults
   (`ema_fast`, `atr`, `body_ratio`, `volume_ratio`, the 30 non-OHLCV canonical features,
   etc.) are **out of scope** and left untouched. Touch a `.get(field, default)` only when
   `field ∈ {timestamp, open, high, low, close, volume}`.
4. **Header aliasing is permitted normalization, not substitution.** Mapping `Open→open`,
   `o→open`, `tick_volume→volume`, `datetime→timestamp`, or merging real `date`+`time`
   columns is allowed (the column exists, just differently named). What is forbidden is
   inventing a column that has no alias present, or sourcing `timestamp` from the row index.

## New shared helper

**Create `src/data_ingestion/ohlcv_schema.py`** — single source of truth for the contract:

```python
REQUIRED_OHLCV_COLUMNS = frozenset({"timestamp", "open", "high", "low", "close", "volume"})

def require_ohlcv_columns(columns, *, source: str = "Historical dataset") -> None:
    missing = REQUIRED_OHLCV_COLUMNS - set(columns)
    if missing:
        raise ValueError(
            f"{source} missing required columns: " + ", ".join(sorted(missing))
        )
```

Error text matches the task spec exactly (e.g. `Historical dataset missing required columns: close, volume`).
No logging, no warning — raise. All loaders below import this constant/function rather
than re-declaring the set.

## Tier A — DataFrame loaders (call `require_ohlcv_columns` after header normalization)

- **`src/features/feature_pipeline.py:161-172` (`_validate_input`)** — replace the
  current 5-column `required` list + the `if "volume" not in ...: self.df["volume"] = 0.0`
  block with a single `require_ohlcv_columns(self.df.columns, source="FeaturePipeline")`.
  Keep the numeric coercion loop. **Keep `compute_volume_features()` (lines 200-214)
  unchanged** — the high-low proxy stays for genuine zero-volume files.
- **`src/runtime/backtest_v2.py:1346-1358`** — after header lowercasing and the
  real `date`+`time` merge (lines 1350-1356, preserved — that is reconstruction from real
  columns, not index synthesis), call `require_ohlcv_columns(raw_df.columns)` before
  constructing `FeaturePipeline`. This gives a clear top-level error before the pipeline.
- **`src/governance/strategy_backtest.py:146-196`** — after `pd.read_csv(...)` /
  `FeaturePipeline(df).run()`, call `require_ohlcv_columns(df.columns)`; then change the
  six-field reads at lines 192-196 from `float(row.get("open", 0.0))` etc. to
  `float(row["open"])` … `float(row["volume"])`. Leave the `CANONICAL_FEATURES`
  comprehension at line 189 as-is (covers the 30 non-OHLCV features).
- **`src/config_layer/rr/rr_dataset_builder.py`** — flows through `FeaturePipeline`
  (`_build_canonical_features_df`, line 87), so column presence is enforced transitively.
  No direct change unless it reads a raw CSV before the pipeline (verify during impl).

## Tier B — CSV / dict row loaders (validate headers, then strict access)

- **`src/runtime/backtest_v2.py:651-680` (`CandleLoader.stream`)** — after `_detect_column`
  for all fields, build the set of canonical fields that resolved to a header (treat
  `date`+`time` as satisfying `timestamp`) and call `require_ohlcv_columns(resolved)`.
  This makes **volume mandatory**: replace line 675
  `vol = float(row[v_col]) if v_col is not None else 0.0` with strict `vol = float(row[v_col])`,
  and the OHLC-only `ValueError` at 665-666 is superseded by the unified check. Keep
  `COLUMN_ALIASES` (header aliasing) and the per-row `(ValueError, IndexError) → continue`
  guard for malformed *values* (distinct from missing *columns*).
- **`src/data_ingestion/historical_fetcher.py:505-520` (`_load_from_csv`)** — validate
  `reader.fieldnames` (case-normalized, allowing `tick_volume`/`Volume` aliases) against
  the six via `require_ohlcv_columns`; then drop the `.get(field, .get(Field, 0))` cascades
  at 515-519 in favor of strict resolved-key access. DB path (`_load_from_db`, explicit
  SELECT) and MT5 path already strict — leave them.
- **`src/analytics/sl_tp_comparator.py:480-502` (`load_candles_from_csv`)** — validate
  `DictReader` headers, then replace `float(row.get("open") or row.get("Open", 0))` (and
  high/low/close, timestamp at 493) with strict resolved access. This loader reads OHLC
  only; still enforce all six columns *present* in the file (dataset contract), reading the
  subset it needs without defaults.
- **`src/replay/timing_reconstructor.py:167-199` (`load_candles`)** — validate the CSV
  header row against the six, then strict index access for high/low/close (already
  index-based; just add the presence check + remove any silent skips that mask a missing
  column).

## Tier C — Live intake + strategy plugins (six fields only, strict access)

- **`src/runtime/live_engine_hook.py`** — for the six OHLCV fields only, convert
  `_safe_float(trade_data.get(field), default)` to strict required access (raise
  `ValueError`/`KeyError` with the standard message if absent). Affected lines:
  `_build_engine_input` 282-285 + 299 (close/open/high/low/volume cascade and `volume→1.0`);
  `_build_ohlcv_and_auxiliary` 329-333 (same cascade + `volume→1.0`); the engine-input
  echo at 617-620 (`get("open",0.0)`…); `844` (`get("close",0.0)`); and the timestamp
  default at `531` (`get("timestamp", candle_idx)` — must not fall back to the index).
  **Leave** all auxiliary defaults (`ema_fast→close`, `atr→0.0`, `volume_ratio→1.0`,
  `disp_strength`, `session`, etc.) untouched — not governed.
  > Risk note: live feeds must now deliver full OHLCV per tick; single-price ticks that
  > previously reconstructed O/H/L from close will now raise. This is the user-chosen
  > strict behavior.
- **Strategy plugins `src/strategies/s01_*.py … s10_*.py`** — replace
  `float(candle.get("close", 0.0))` / `get("open"|"high"|"low", 0.0)` with strict
  `float(candle["close"])` etc. Representative hits: `s09_pattern_recog.py:121,196-199,234-237`,
  `s10_trap_strategy.py:113`, and the `close` reads in `s01`–`s08`. Leave `volume_ratio`
  defaults (`s09:103`, `s10:109`) — derived, not raw volume.
- **`src/runtime/backtest_v2.py:2470`** — `float(row.get("volume", 0.0))` → `float(row["volume"])`
  (rows come from the now-strict enriched_df). Leave the mixed `CANONICAL_FEATURES`
  comprehension at 2456 (30 non-OHLCV features legitimately default; the six are guaranteed
  present upstream).
- **`src/core/engine_runner.py:557-558,858`**, **`src/engines/zone_gate_engine.py:71`**,
  **`src/core/feature_store.py`**, **`src/features/crt_feature_builder.py:46-50`** — these
  read engine-input dicts already built by the strict paths above. Convert the six-field
  `.get(field, default)` to strict access for consistency; preserve the `close→price`
  cascade only if `price` is a legitimate alias (verify), otherwise make strict.

## Out of scope / explicitly preserved

- `compute_volume_features()` high-low proxy (forex zero-volume) — **kept**.
- `date`+`time` → `timestamp` merge from real columns — **kept** (not index synthesis).
- All non-OHLCV feature defaults (ema/atr/session/volume_ratio/30 canonical features).
- NaN-guard `np.nan` finalize-drop logic in `feature_pipeline.py` (rows dropped during
  warmup; not a column-level fallback).

## Tests

- **New `tests/data_ingestion/test_ohlcv_schema.py`** — table-driven: for each of the six
  columns, build a DataFrame/CSV omitting exactly that column and assert
  `require_ohlcv_columns` / each loader raises `ValueError` with the exact message
  (`...missing required columns: <name>`); plus a multi-missing case (`close, volume`) and
  a happy-path no-raise case. Covers self-review items 1-6.
- **`CandleLoader`** — new test: CSV without a volume column now raises (was silently 0.0).
- **`FeaturePipeline`** — update existing tests: a frame without `volume` now raises
  (previously auto-added). Add a test that a frame *with* an all-zero volume column still
  runs and triggers the proxy (forex compatibility preserved).
- **Migration cost (flagged):** existing test fixtures / inline CSVs that omit `volume`
  will now fail and must be updated to include the column. Grep `tests/` for `pd.read_csv`
  mocks and inline candle CSVs during impl (e.g. `tests/test_backtest_payload_integrity.py`
  already includes volume; others may not).
- Re-run the full suite per `docs/TESTING.md`; fix any fixture that relied on a synthesized
  column by adding real OHLCV values (never by re-introducing a default).

## Verification

1. `python -m pytest tests/data_ingestion/test_ohlcv_schema.py -v` — all six missing-column
   cases + multi-missing + happy path pass.
2. `python -m pytest tests/ -q` — full regression green (fixtures migrated, not defaults
   restored).
3. Manual: feed a CSV missing `volume` to `CandleLoader.stream()` and to
   `FeaturePipeline` → both raise `ValueError: ... missing required columns: volume`.
   Feed a forex CSV with an all-zero `volume` column → loads, proxy engages.
4. Determinism/replay check (`tests/runtime/test_replay_determinism.py`) still byte-identical
   on a complete dataset — strict enforcement must not alter valid-data behavior.

## Residual assumptions & known remaining fallbacks (to confirm during impl)

- Header aliasing (`tick_volume`, `vol`, `Open`, `datetime`, etc.) is retained as
  normalization — if the user wants *exact* lowercase names only, the alias maps must also
  be stripped (not assumed).
- The `close → price` alias in `engine_runner`/`zone_gate_engine` is verified before
  deciding strict-vs-alias.
- Non-OHLCV canonical-feature `0.0` defaults (e.g. `backtest_v2.py:2456`,
  `strategy_backtest.py:189`) remain by design (decision #3); call out if any of the six
  ever slips through one of those comprehensions.
