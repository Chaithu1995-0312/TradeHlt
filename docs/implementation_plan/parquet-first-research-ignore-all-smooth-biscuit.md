# High-Acceptance-Candle Numerical Study (Phase 1, ontology-free)

## Context

The user wants a pure numerical/statistical study of whether a candle's HIGH ever gets
revisited (traded back below) within various forward horizons — explicitly **without** any
CRT/SMC/ontology vocabulary, classification, or trading-meaning attached. This is phase 1 of a
two-phase investigation; phase 2 ("what structural characteristics are common among the
strongest acceptance candles") is explicitly deferred until phase 1's output exists and is
reviewed, so it is **out of scope** for this implementation.

Research during planning surfaced one factual correction to the request's framing: **no raw
OHLCV parquet dataset exists in the repo today** — only CSV (`data/mt5/*.csv`). The only parquet
files on disk are derived research artifacts (decision ledgers, CRT event/telemetry logs), not
plain candle series. Per the user's answer, this plan converts the raw CSV to parquet first
(a trivial `pandas.to_parquet` dump, no schema-versioning machinery needed) and treats *that*
parquet file as the numerical input, matching the "parquet dataset" framing literally.

Scope, per the user's answer: **XAUUSD M15 only** (`data/mt5/XAUUSD_M15.csv`, 47,275 rows,
columns `timestamp,open,high,low,close,volume` — confirmed via `head`/`wc -l`). No ATR column
exists in the raw data; ATR-normalization will use a small locally-computed rolling ATR
(standard TR/SMA), explicitly labeled non-canonical (not registered as an `FM-*` ontology
feature) since it exists only to normalize a display metric, not to drive any decision — the
same "observe-only, no `src/` registration" pattern already used by prior diagnostic probes
(e.g. F-067's EMA probe).

This is a standalone, read-only diagnostic script under `scripts/research/` — the same category
as ~212 existing scripts there (no shared framework/base class; loose docstring + path-constant
convention, e.g. `scripts/research/edge_attribution_study.py:1-59`). It makes **no economic or
trading claim**, so it does not require a sealed Measurement Contract (`MC-*`) under
`docs/governance/MEASUREMENT_CONTRACT.md` — that gate applies to economic/promotable claims, not
descriptive statistics. It does still need SITS script registration (CLAUDE.md §3.1 item 1b)
since it's a new file under `scripts/**`.

## Implementation

### 1. New script: `scripts/research/high_acceptance_scan.py`

Standalone, no `src/` imports beyond stdlib/pandas/numpy — deliberately does not touch
`CandleLoader` or the feature pipeline, to stay ontology-free and dependency-light. Structure:

- **Step A — CSV → parquet.** Read `data/mt5/XAUUSD_M15.csv` with pandas (parse `timestamp` as
  datetime), write untouched to `results/research/high_acceptance/xauusd_m15.parquet`
  (`to_parquet`, pyarrow engine — already a project dependency). This is the "parquet dataset."
- **Step B — Load parquet**, sorted by timestamp, reset to a plain integer index `i`.
- **Step C — Local rolling ATR** (14-period Wilder or SMA of True Range — pick SMA(14) for
  simplicity, document the choice inline) purely for the normalization columns in step D;
  candle `range = high - low` also computed for range-normalization.
- **Step D — Per-horizon vectorized computation**, for `N in [5,10,20,50,100,250,500]`, using
  `numpy.lib.stride_tricks.sliding_window_view` over `low`/`high` shifted by one bar so each
  candidate `i` gets an O(n) (not O(n²)) computation of its forward window
  `[i+1, i+N]` (rows where `i+N >= len(df)` are excluded for that horizon — insufficient future
  data, not silently zero-filled):
  - `future_min_low = window_low.min()`
  - `acceptance_score = future_min_low - candidate_high`
  - `reclaim_mask = window_low < candidate_high`; if any True → `survival_bars` = offset of
    first True (1-based bar count), `first_reclaim_ts` = timestamp at that offset; else
    `survival_bars = N`, `first_reclaim_ts = NaT` (survived the whole horizon)
  - `mfe = window_high.max() - candidate_high` (how far price extended further above the high)
  - `mae = candidate_high - future_min_low` (max adverse move below the high; note this is
    `-acceptance_score` when negative, always reported as a nonnegative magnitude)
  - `acceptance_score_atr_norm = acceptance_score / atr[i]`
  - `acceptance_score_range_norm = acceptance_score / range[i]`
- **Step E — Long-format candidate table**: one row per `(candidate_index, horizon)` with
  columns `instrument, timeframe, candidate_ts, candidate_high, N, future_min_low,
  acceptance_score, survival_bars, first_reclaim_ts, mfe, mae, acceptance_score_atr_norm,
  acceptance_score_range_norm`. Write to
  `results/research/high_acceptance/xauusd_m15_candidates.parquet` **and** `.csv` — this is the
  "separate table containing only the candidate timestamps and acceptance metrics" the user
  asked for.
- **Step F — Descriptive statistics** (per horizon, computed from the long table, no
  classification/labels attached):
  1. Distribution of `acceptance_score` (`describe()` + histogram bin counts)
  2. Top 1% / 5% / 10% candles by `acceptance_score` (and separately by
     `acceptance_score_atr_norm`)
  3. Longest surviving highs — top 50 by `survival_bars` at `N=500` (highest-resolution horizon)
  4. Acceptance score percentiles: 1/5/10/25/50/75/90/95/99
  5. Clusters of accepted highs through time — weekly bucket, count and fraction with
     `acceptance_score > 0` per bucket, per horizon
  6. Consecutive accepted-high sequences — run-length-encode the `acceptance_score > 0` flag
     over adjacent candidate bars; report max run length + top 10 longest runs (start/end
     timestamp) per horizon
  7. (Covered inline in step E) ATR- and range-normalized acceptance score, already columns in
     the candidate table
  8. Instrument-level statistics — single-row summary block (`instrument="XAUUSD",
     timeframe="M15"`), scoped for straightforward extension to more instruments later
  - Write all of the above to `results/research/high_acceptance/xauusd_m15_summary.json`
- No `docs/analysis/*.md` write-up in this phase — the user explicitly said not to classify or
  attach trading meaning, so there is no conclusion yet to narrate; the JSON + parquet/csv
  artifacts are the phase-1 deliverable.

### 2. SITS script registration (repo hygiene, CLAUDE.md §3.1 item 1b)

After the script is added, run the standard three-step registration so it doesn't fail the
GREEN_FLOOR coverage test:
```
python scripts/analysis/script_census.py --write-stubs
python scripts/governance/seed_script_registry.py
python scripts/governance/generate_script_matrix.py
```

## Verification

- Run `python scripts/research/high_acceptance_scan.py` end-to-end; confirm it exits 0 and
  produces all three artifacts under `results/research/high_acceptance/`.
- Sanity-check the candidate table: for a handful of hand-picked bars, manually verify
  `future_min_low`/`acceptance_score`/`survival_bars` against a plain pandas slice for one
  horizon (e.g. N=20) to confirm the vectorized sliding-window logic matches a naive loop.
- Confirm horizon-boundary rows (last N bars of the series) are correctly excluded per horizon,
  not zero- or NaN-filled into misleading stats.
- Spot-check the summary JSON's percentile/top-decile tables against `describe()` output on the
  same column directly in a REPL.
- Run the SITS registration commands and confirm `python scripts/governance/construction_protocol.py check`
  (or the relevant GREEN_FLOOR test) passes with the new script counted.
