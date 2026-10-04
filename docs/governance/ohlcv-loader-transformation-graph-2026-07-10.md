# OHLCV Loader / Transformation Graph — PHASE 1 (OHLCV Truth Closure) PASS A

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | A (Evidence Freeze) |
| Generated (UTC) | 2026-07-10T13:09:06Z |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY) |
| Branch | `feature/truth-registry-v2` |
| Siblings | census manifest (machine twin), lineage map, temporal report |
| Verdict | (none — PASS A emits evidence only) |

Every code path that can load / mutate / repair / substitute / resample / cache
/ persist OHLCV, as `T-*` records. Status: **ACTIVE** (reached by a current
runtime or maintained script path) · **LATENT** (exists; activation condition
not met by any current corpus/config) · **HISTORIC** (one-shot builder; not in
any current pipeline) · **DORMANT** (importable, no active caller exercises it).
Discovery method: `CandleLoader(` call-site sweep (~50 hits) + mutation-verb
grep (`ffill|bfill|fillna|interpolate|drop_duplicates|sort_values|resample(|
dropna|shift(`) over `src/` and `scripts/`, + census content-hash evidence.

---

### T-001 — `CandleLoader.stream` (the single CSV→runtime funnel)
- Producer: `src/runtime/backtest_v2.py:704-769` (class `:673`)
- Effect: utf-8-sig read; header aliasing via `COLUMN_ALIASES` (`:677-686`,
  incl. `tickvol/tick volume→volume`, split `date`+`time`); blank-line skip
  (`:736-737`); timestamp parse via shared `parse_ohlcv_timestamp`; **L2 inline
  backstop** — RAISES on duplicate ts (`:746-750`, `DatasetIntegrityError`) and
  out-of-order ts (`:751-755`, `ValueError`); per-row L1 value gate
  `validate_ohlcv_row` (`:764-768`). **No sorting, no dedup, no repair, no
  fill — fail-fast only.**
- Activation: unconditional for every consumer. Status: **ACTIVE**.
- PIT risk: none added (row-sequential, no lookahead).
- Consumers: ~50 call sites (see lineage map §8).

### T-002 — `dataset_integrity.validate_dataset` / `validate_universe` (L2/L3 pre-flight)
- Producer: `src/data_ingestion/dataset_integrity.py:257` (universe `:685`)
- Effect: NON-MUTATING gate — path-consistency vs `canonical_data_roots=["data"]`
  + `{symbol}_{timeframe}.csv` (`:309-313`); dup/order/future single pass
  (`:332-367`, future tolerance 0 min); modal-delta timeframe check (`:378-386`);
  session-aware gap threshold gate (`:397-406`); autoderive weekly mask
  (`:389-395`); writes fingerprint `reports/dataset_integrity/{sym}_{tf}.json`.
- Activation: ONLY `backtest_v2.py:2542/:2586` (runtime) + the two
  fetch-and-verify scripts (acquisition) + CLI/tests. Every other T-001 consumer
  streams WITHOUT this gate — **F-039**. Status: **ACTIVE** (narrow).
- PIT risk: none (gate).

### T-003 — FeaturePipeline zero-volume proxy substitution ★
- Producer: `src/features/feature_pipeline.py:202-233`; trigger `:207`
  (`vol_is_dead = raw_vol.fillna(0.0).max() == 0` — the ENTIRE column zero/NaN);
  substitution `:214-216` (`df["volume"] = high - low`), derived
  `volume_ma20`/`volume_ratio` from the proxy (`:217-222`).
- Upstream enabler: `validate_ohlcv_frame` explicitly PERMITS an all-zero
  numeric volume column (`feature_pipeline.py:171-174` comment;
  `ohlcv_schema.py:151` only rejects NEGATIVE volume).
- Activation: **census evidence — 0 of 224 current artifacts have an all-zero
  volume column** ⇒ cannot fire on any current corpus. Status: **LATENT**.
- Semantic effect when it fires: unit change (traded/tick volume → price range),
  silent at the schema level (column keeps the name `volume`). In-frame only —
  never written back to CSV.
- Consumers of the mutated frame: `config_layer/rr/rr_dataset_builder.py:87`
  (RR training corpus), live hook pipeline mode, vector-builder scripts.
- Tests: **none cover the substituted branch** (coverage gap; matrix seed
  SEED-OHLCV-19).

### T-004 — `research.resample` (calendar-bucket resampler)
- Producer: `src/research/resample.py:105-135` (`_emit :87-102`,
  `bucket_floor :73-84`).
- Effect: floor-to-calendar buckets (H1/H4 hour-aligned to 00:00; M15 minute
  grid); open=first/high=max/low=min/close=last; volume = `Decimal`-exact sum
  (`:93`); bucket emitted ONLY when the next bucket's first child arrives;
  **trailing partial bucket dropped unconditionally** (`:133-135`); never
  fabricates candles across gaps (`:24-27`). Timestamp = bucket START
  (open-time labeling).
- Activation: `scripts/research/build_resampled_data.py` (persists
  `data/resampled/`), `research/candle_state/mtf_conjunction.py:63,117`
  (in-memory), `research/secondlow_v1/detector.py`, `uat/monte_carlo.py`,
  parity script. Status: **ACTIVE** (research).
- PIT risk: designed-out (causality invariant). Persisted output re-enters via
  T-001.

### T-005 — `HTFBuilder` (COUNT-based HTF aggregation, backtest spine) ★
- Producer: `src/runtime/backtest_v2.py:780-808` (`push :797-805`).
- Effect: buffers every N consecutive candles (`candles_per_htf`) and emits the
  buffer as the completed HTF window — **count-based, NOT calendar-aligned**.
  After any data gap or session close, HTF boundaries drift off calendar hours;
  an "H4" window is "the last 16 M15 candles", not 00/04/08… wall-clock H4.
- Activation: backtest/live spine HTF context. Status: **ACTIVE**.
- Semantic divergence vs T-004 is REAL and coexisting: two different "HTF
  candle" definitions in one repository (contradiction CX-OHLCV-007).
- PIT risk: none (uses only completed candles), but boundary semantics differ.

### T-006 — yfinance synthetic cross construction (acquisition-time)
- Producer: `scripts/data/fetch_forex_yfinance.py:130-135` (cross:
  `High = leg1.High/leg2.Low`, `Low = leg1.Low/leg2.High`,
  `Volume = leg1.Volume.fillna(0)`); inversion `:148-149`
  (1/x with High/Low swap); `volume.fillna(0).astype(int)` `:157`;
  `drop_duplicates(subset=["timestamp"], keep="last")` + sort `:170-171`.
- Effect: SYNTHESIZES OHLC for crosses from two USD legs; volume is the leg's
  (or 0) — **not the instrument's traded volume**; silent at schema level.
- Activation: on fetch only. No verify gate wraps this family. Status:
  **HISTORIC/ACTIVE-on-fetch**.
- Downstream: census hash evidence — root `BTCUSDT/ETHUSDT/XRPUSDT/DOGEUSDT_M15`
  ≡ yfinance twins ⇒ this family's semantics REACH the canonical root corpus
  (for those crypto files, via direct fetch or copy — which is UNKNOWN).

### T-007 — `convert_binance_m1_to_m15.py` (pandas resample, historic)
- Producer: `scripts/data/convert_binance_m1_to_m15.py:15-28`:
  `to_datetime(open_time, unit="ms")` (tz-naive UTC), concat+sort,
  `resample("15min").agg(first/max/min/last/sum).dropna()`.
- Effect: M1→M15; pandas default `label="left", closed="left"` ⇒ open-time
  bucket labeling; `dropna()` drops empty buckets (no fabrication).
- Status: **HISTORIC** (one-shot; which root files it produced is UNKNOWN).

### T-008 — `build_m15_unified.py` (historic unified builder)
- Producer: `scripts/data/build_m15_unified.py:105-136`:
  `sort_values("timestamp").drop_duplicates()` (full-row), `resample("15T")`
  agg + `dropna()`.
- Status: **HISTORIC**; same UNKNOWN-attribution caveat.

### T-009 — `MT5CandleFetcher` (acquisition)
- Producer: `src/inout/mt5_candle_fetcher.py:170-199`:
  `copy_rates_range` → `fromtimestamp(r["time"], tz=UTC)` (`:186`) →
  defensive de-dupe keep-first (`:199`) → CSV. M5 depth-probe fallback
  (`:211-218`).
- Status: **ACTIVE** (maintained acquisition path, strict-gated by wrapper).

### T-010 — `PerpFundingFetcher` (non-OHLCV; excluded)
- Producer: `src/inout/perp_funding_fetcher.py` — dedup+sort on ms key, no fill
  (`:10`). Status: **ACTIVE**; outside OHLCV closure scope.

### T-011 — `HistoricalFetcher` (TimescaleDB ingestion chain) ★
- Producer: `src/data_ingestion/historical_fetcher.py:198` (`_DBConnection
  :170`, `fetch_and_store :227`, `load :286`, `detect_gaps :344`).
- Effect: a SECOND OHLCV ingestion/storage chain (DB-backed) that bypasses
  T-001/T-002 entirely.
- Activation: lazy import `src/portfolio/correlation_engine.py:77-78`;
  registered `control_plane/registry.py:800-805`. No evidence of current
  DB use; `docs/topics/readme.md` marks data ingestion DORMANT. Status:
  **DORMANT/LATENT** (contradiction CX-OHLCV-006 — "no database" doctrine).

### T-012 — `fetch_crypto_ccxt.py` (historic acquisition)
- Producer: `scripts/data/fetch_crypto_ccxt.py:127` (`sort_values` + reset
  index). Status: **HISTORIC**.

### T-013 — misc corpus builders (`prepare_data.py`, `unified_data_builder.py`,
  `resample_m1_to_m15.py`, `convert_bnb_to_csv.py`, `split_bnb_excel.py`)
- One-shot manipulation scripts; no generation logs; **HISTORIC**, attribution
  to specific on-disk files UNKNOWN.

---

## Negative results (preserved evidence)

1. **No forward-fill/backfill/interpolation of candle rows in `src/`** — all
   fill/shift hits are feature-column computations post-load
   (`feature_pipeline.py:373-385,637,655`), not OHLCV row repair.
2. **No silent dedup/sort at load time** — T-001 raises instead.
3. **No cache layer persists mutated OHLCV** — the only persisted derived OHLCV
   is `data/resampled/` (T-004, declared) and the historic builders' outputs.
4. **No code path reads `_rejected/` or `_archive_5wk/`** (grep: only the
   quarantine writers reference `_rejected`). Quarantine re-entry happens via
   byte-identical twins only (census DUP-008 — see contradiction report).
5. Census: 0/224 files currently violate row/sequence invariants; 0 files have
   all-zero volume (T-003 cannot fire today).

## What this graph did NOT do

No remediation (all ★ items stay as-is); no PASS-B adjudication; no Phase-2
candle-math tracing; no economic claims.

```text
OHLCV_TRANSFORMATIONS_REGISTERED = 13
OHLCV_TRANSFORMATIONS_LATENT_SUBSTITUTIONS = 2 (T-003 volume proxy; T-006 synthetic cross semantics reaching root corpus)
OHLCV_TRANSFORMATIONS_STATUS = EVIDENCE_FROZEN
```
