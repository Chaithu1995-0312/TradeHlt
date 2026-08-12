# OHLCV Data Lineage & Feature Usage Forensics

**Generated:** 2026-06-26  
**Methodology:** File-level evidence audit across 40+ source files  
**Status:** Complete

---

## Phase 1: Raw OHLCV Ingestion

### Source 1: CandleLoader (Production Backtest Path)

**File:** `src/runtime/backtest_v2.py`  
**Class:** `CandleLoader`  
**Function:** `CandleLoader.stream()` (line 704)

**Output schema:** `Candle` dataclass (defined in `src/config_layer/crt_engine_v2.py`, line 95)
```python
@dataclass
class Candle:
    timestamp: datetime
    open:  float
    high:  float
    low:   float
    close: float
    volume: float = 0.0
    index: int = 0
```

**Columns:** timestamp, open, high, low, close, volume

**Consumers:**
- `HTFBuilder.push(candle)` — aggregates into higher-timeframe ranges
- `CRTEngine.on_candle(candle)` — state machine tick
- `TradeJournal.on_trade_opened()` — records features at entry
- `TradeJournal.observe_open_bar()` — MFE/MAE path tracking

**Used in production?** YES — this is the primary backtest ingestion path. Loaded via `--csv` flag.

**Evidence:** Line 704 — `def stream(self) -> Iterator[Candle]:` — the CSV reader is the hot loop inlet.

---

### Source 2: HistoricalFetcher (TimescaleDB + MT5 + CSV)

**File:** `src/data_ingestion/historical_fetcher.py`  
**Class:** `HistoricalFetcher`  
**Functions:**
- `fetch_and_store()` (line 227) — incremental DB ingestion
- `_fetch_from_mt5()` (line 462) — MT5 API
- `_load_from_csv()` (line 493) — CSV fallback
- `load()` (line 286) — query from DB

**Output schema:** `OHLCVRow` (line 127)
```python
class OHLCVRow:
    __slots__ = ("ts", "pair", "timeframe", "open", "high", "low", "close", "volume")
```

**Columns:** ts, pair, timeframe, open, high, low, close, volume

**Consumers:**
- `load_pairs()` (line 315) — multi-pair bulk loader
- External callers via `HistoricalFetcher.load()` / `.load_pairs()`

**Used in production?** YES — TimescaleDB is the primary production data store. MT5 is secondary (conditional on `mt5_enabled`). CSV is tertiary fallback.

**Evidence:**
- Line 98-108 — config keys are required (`_CFG = _load_ingestion_cfg()`)
- Line 453 — `_fetch_rows` tries MT5 first, then CSV
- Line 286-313 — `load()` tries DB, falls back to CSV

---

### Source 3: FeaturePipeline (Batch DataFrame Processor)

**File:** `src/features/feature_pipeline.py`  
**Class:** `FeaturePipeline`  
**Function:** `run()` (line 805)

**Output schema:** 38-dim canonical feature vector + enriched DataFrame

**Input contract:** DataFrame with open, high, low, close, volume columns (`_validate_input()` at line 162-174)

**Consumers:**
- `build_features()` (standalone, line 75) — dict extraction for single rows
- `build_feature_vector()` (line 767) — numpy array for ML
- `FeatureMonitor` — drift detection on retest_depth, body_ratio, disp_strength

**Used in production?** YES — called by training pipelines and research scripts. DataFrame input from HistoricalFetcher or CSV loaders.

**Evidence:** Line 165 — `require_ohlcv_columns(self.df.columns, source="FeaturePipeline")` enforces the six mandatory columns.

---

### Source 4: Research Scripts (Non-Production)

| Script | Source | Production? | Evidence |
|--------|--------|-------------|----------|
| `scripts/data/fetch_crypto_ccxt.py` | CCXT exchange API | NO — research only | Script directory, no import chain to production modules |
| `scripts/data/fetch_forex_yfinance.py` | Yahoo Finance | NO — research only | Script directory, yfinance not in production deps |
| `scripts/data/fetch_candles_hummingbot.py` | Hummingbot | NO — research only | Standalone script |
| `scripts/data/check_yfinance.py` | Yahoo Finance | NO — research only | Data verification script |
| `scripts/data/convert_bnb_to_csv.py` | Excel/CSV conversion | NO — data migration | One-time conversion script |

---

## Phase 2: Complete Feature Lineage

### Feature: open

**Depends On:** Raw OHLCV
**Formula:** Direct column copy
**Generated In:** `FeaturePipeline.run()` → from input DataFrame
**Consumed By:** All engines that access feature dict
**Actually Used?** PARTIAL — consumed via feature vector in ZoneGate, but no engine directly reads `open` for scoring. CRT engine uses `Candle.open` directly (not the canonical feature).

### Feature: high, low, close, volume

**Depends On:** Raw OHLCV  
**Generated In:** FeaturePipeline  
**Consumed By:** RREngine (`high`, `low`, `close`), ZoneGate (full vector)  
**Actually Used?** PARTIAL — RREngine reads `close`, `high`, `low` from raw features. CRT engine uses Candle properties (not canonical feature dict). Volume is only used as intermediate for volume_ratio.

### Feature: volume_ratio

**Depends On:** volume, ma_20 of volume
**Formula:** `volume / volume_ma20` (with FX dead-volume proxy: `(high-low) / proxy_ma20`)
**Generated In:** `FeaturePipeline.compute_volume_features()` (line 202)
**Consumed By:** Only via canonical vector (ZoneGate)
**Actually Used?** NO — no engine explicitly reads `volume_ratio`

### Feature: double_sweep

**Depends On:** liquidity_sweep
**Formula:** `seen_up & seen_down` over 5-bar window
**Generated In:** `FeaturePipeline.compute_canonical_structure_features()` (line 511)
**Consumed By:** `ScoringEngine.compute_scores()`, `bitnet_score()`, `crt_engine.py::compute()`, CRTEngine state machine
**Actually Used?** YES — active in CRT scoring and BitNet inference.

### Feature: ema_fast, ema_slow

**Depends On:** close
**Formula:** EMA(close, 9) and EMA(close, 21) (in FeaturePipeline)  
**Also computed internally** in CRTEngine.state.update_emas(close, fast=2, slow=5) (line 292)
**Generated In:** FeaturePipeline + CRTEngine state
**Consumed By:** `HeuristicGaussianEngine.compute()` (pipeline version), `UltronRiskEngine.compute_soft_confirmation()` (engine version)
**Actually Used?** YES — Gaussian engine uses them. CRT engine uses different periods (2/5 vs 9/21).

**NOTE:** FeaturePipeline computes EMA(9,21) for canonical features. CRTEngine computes EMA(2,5) internally for live state. These are DIFFERENT values — the canonical features are NOT what CRTEngine uses for confirmation.

### Feature: ema_spread

**Depends On:** ema_fast, ema_slow, atr
**Formula:** `(ema_fast - ema_slow) / atr`
**Generated In:** `FeaturePipeline.compute_canonical_ema_features()` (line 482)
**Consumed By:** `detect_regime()`, `breakout_engine()` in engine_runner.py
**Actually Used?** YES — used in regime detection and fusion scoring.

### Feature: trend_bias

**Depends On:** ema_fast, ema_slow
**Formula:** `1 if ema_fast > ema_slow else -1 if ema_fast < ema_slow else 0`
**Generated In:** `FeaturePipeline.compute_canonical_trend_features()` (line 503)
**Consumed By:** `breakout_engine()`, `trap_engine()` in engine_runner.py
**Actually Used?** YES — dual-engine breakout/trap detection uses it.

### Feature: trend_strength

**Depends On:** ma_slope_20 → rolling 10-bar mean
**Generated In:** `FeaturePipeline.compute_trend_features()` (line 290)
**Consumed By:** Only as `NORMALIZE_COLS` → z-scored, then dropped to CANONICAL_FEATURES subset. It IS in CANONICAL_FEATURES (index 11).
**Actually Used?** VIA CANONICAL VECTOR — consumed by ZoneGate, but no engine reads it explicitly.

### Feature: momentum_score

**Depends On:** close.diff(), atr
**Formula:** `close.diff() / atr`
**Generated In:** `FeaturePipeline.compute_canonical_ema_features()` (line 497)
**Consumed By:** `HeuristicGaussianEngine.compute()`, `detect_regime()`, `breakout_engine()`, `trap_engine()`, `ExecutionEngine._derive_trade_intent()`
**Actually Used?** YES — consumed by multiple paths.

### Feature: atr

**Depends On:** ATR(14) → `atr_14_raw / close`
**Formula:** `atr_14_raw / close` (close-relative ATR)
**Generated In:** `FeaturePipeline.compute_canonical_volatility_features()` (line 458)
**Consumed By:** `ScoringEngine.compute_scores()`, `bitnet_score()`, `crt_engine.py::compute()`, engine_runner regime detection, ExecutionEngine.build_trade()
**Actually Used?** YES — core feature.

**NOTE:** CRTEngine also computes ATR internally (line 1002-1015) from Candle data with same period (14). The internal ATR is used for state machine decisions (displacement, expansion, retest gates). The canonical `atr` is used for post-hoc scoring. These SHOULD match if computed over same data but may diverge in implementation (pandas vs manual rolling).

### Feature: volatility_ratio

**Depends On:** atr, close, high, low
**Formula:** `(high - low) / (atr * close)`
**Generated In:** `FeaturePipeline.compute_canonical_volatility_features()` (line 476)
**Consumed By:** `detect_regime()` (line 147)
**Actually Used?** YES — in regime classification.

### Feature: rsi_14

**Depends On:** close (14-bar Wilder RSI)
**Formula:** `100 - 100/(1 + RS)` where RS = avg_gain/avg_loss
**Generated In:** `FeaturePipeline.compute_indicators()` (line 252)
**Consumed By:** ZoneGate (via full vector), possibly ML models
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine explicitly reads it.

### Feature: macd_line, macd_signal, macd_hist

**Depends On:** close (EMA 12, 26, signal 9)
**Generated In:** `FeaturePipeline.compute_indicators()` (line 278-283)
**Consumed By:** ZoneGate (via full vector)
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine explicitly reads any MACD field. Potentially DEAD features consumed only by the zone gate model.

### Feature: sweep_detected

**Depends On:** liquidity_sweep
**Formula:** `liquidity_sweep != 0`
**Generated In:** `FeaturePipeline.compute_canonical_structure_features()` (line 515)
**Consumed By:** `crt_engine.py::compute()`, `trap_engine()`, `ExecutionEngine._derive_trade_intent()`
**Actually Used?** YES — CRT scoring and intent classification.

### Feature: liquidity_sweep, break_of_structure

**Depends On:** swing high/low reference prices, close
**Formula:** Sweep: `high > ref_high & close <= ref_high` (or low). BOS: `close > ref_high` (or `close < ref_low`)
**Generated In:** `FeaturePipeline.compute_structure_liquidity()` (lines 404-415)
**Consumed By:** `ExecutionEngine._derive_trade_intent()` uses `double_sweep` (derived from liquidity_sweep)
**Actually Used?** PARTIAL — `liquidity_sweep` is intermediate for double_sweep. `break_of_structure` is canonical but no engine reads it.

### Feature: swing_high, swing_low, higher_high, lower_low

**Depends On:** high, low (rolling ±2 pivot detection)
**Generated In:** `FeaturePipeline.compute_structure_liquidity()` (lines 357-366, 393-395)
**Consumed By:** ZoneGate (via full vector)
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine explicitly reads any swing indicator.

### Feature: body_size, wick_size, body_ratio

**Depends On:** open, high, low, close
**Formula:** `|close-open|`, `high-low`, `body_size/wick_size`
**Generated In:** `FeaturePipeline.compute_canonical_price_features()` (lines 439-456)
**Consumed By:** `ScoringEngine.compute_scores()` → body_ratio, `ScoringEngine.compute()` → body_ratio, `bitnet_score()` → body_ratio, `crt_engine.py::compute()` → body_ratio, FeatureMonitor drift detection
**Actually Used?** YES — `body_ratio` is a core CRT feature. `body_size` and `wick_size` are only consumed via canonical vector.

### Feature: volatility_regime

**Depends On:** atr_14 (global percentile rank)
**Formula:** `0 (low) < 33rd pctile, 1 (mid) < 66th pctile, 2 (high)`
**Generated In:** `FeaturePipeline.compute_volatility_regime()` (line 303)
**Consumed By:** ZoneGate (via full vector). Also has trust-layer A/B/C measurement hook (F-029).
**Actually Used?** VIA CANONICAL VECTOR ONLY — but has Program-B measurement indicating it IS decision-reachable (s05_grid.py blocks LONG in TRENDING regime).

### Feature: session, hour_of_day

**Depends On:** timestamp
**Formula:** Session: Asia=0, London=1, NY=2 from hour. Hour: `timestamp.hour`.
**Generated In:** `FeaturePipeline.compute_context()` (lines 334-348)
**Consumed By:** CRTEngine session gating, `detect_regime()` (indirect), Trading session filtering
**Actually Used?** YES — CRT engine checks `allowed_sessions`.

### Feature: disp_strength

**Depends On:** body_size, atr, close
**Formula:** `body_size / (atr * close)`, clipped [0, 3]
**Generated In:** `FeaturePipeline.compute_canonical_temporal_features()` (line 559)
**Consumed By:** `ScoringEngine.compute_scores()`, `bitnet_score()`, `crt_engine.py::compute()`, `trap_engine()`, `ExecutionEngine._derive_trade_intent()`, FeatureMonitor drift detection
**Actually Used?** YES — core CRT feature, consumed by multiple paths.

### Feature: retest_depth

**Depends On:** close, ema_fast, atr
**Formula:** `|close - ema_fast| / (atr * close)`, clipped [0, 1]
**Generated In:** `FeaturePipeline.compute_canonical_temporal_features()` (line 573)
**Consumed By:** `ScoringEngine.compute_scores()`, `bitnet_score()`, `crt_engine.py::compute()`, FeatureMonitor drift detection, `ExecutionEngine._derive_trade_intent()`
**Actually Used?** YES — core CRT feature.

### Feature: candles_since_retest

**Depends On:** liquidity_sweep, cumcount grouping
**Formula:** `groupby(sweep_groups).cumcount()`
**Generated In:** `FeaturePipeline.compute_canonical_temporal_features()` (line 593)
**Consumed By:** `ScoringEngine.compute_scores()`, `bitnet_score()`, `crt_engine.py::compute()`, `UltronRiskEngine.approve()`
**Actually Used?** YES — used in scoring and BitNet validation.

### Feature: liquidity_distance (v3.0, index 35)

**Depends On:** close, last_swing_high_price, last_swing_low_price, break_of_structure level, atr
**Formula:** `min(|close - ref_high|, |close - ref_low|, |close - bos_level|) / (atr * close)`
**Generated In:** `FeaturePipeline.compute_liquidity_distance()` (line 599)
**Consumed By:** ZoneGate (via full vector)
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine reads it explicitly.

### Feature: liquidity_pressure_score (v3.0, index 36)

**Depends On:** liquidity_distance
**Formula:** `exp(-0.5 * liquidity_distance)`, clipped [0, 1]
**Generated In:** `FeaturePipeline.compute_liquidity_distance()` (line 648)
**Consumed By:** ZoneGate (via full vector)
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine reads it explicitly.

### Feature: volume_spike (v3.0, index 37)

**Depends On:** volume_ratio (adaptive 75th percentile)
**Formula:** `volume_ratio > rolling_75th_percentile`
**Generated In:** `FeaturePipeline.promote_volume_spike()` (line 654)
**Consumed By:** ZoneGate (via full vector)
**Actually Used?** VIA CANONICAL VECTOR ONLY — no engine reads it explicitly.

---

## Phase 3: Canonical Feature Graph

```
OHLCV
├── Price Features
│   ├── open*         [VECTOR_ONLY]
│   ├── high*         [ACTIVE — RREngine, CRT engine]
│   ├── low*          [ACTIVE — RREngine, CRT engine]
│   ├── close*        [ACTIVE — RREngine, CRT engine, multiple scorers]
│   ├── volume*       [INTERMEDIATE — only for volume_ratio]
│   ├── body_size     [VECTOR_ONLY]
│   ├── wick_size     [VECTOR_ONLY]
│   └── body_ratio    [ACTIVE — CRT core, BitNet, ScoringEngine]
│
├── Volume Features
│   ├── volume_ratio  [VECTOR_ONLY — no explicit consumer]
│   └── volume_spike  [VECTOR_ONLY — v3.0, no explicit consumer]
│
├── Trend Features
│   ├── ema_fast      [ACTIVE — GaussianEngine, regime detection]
│   ├── ema_slow      [ACTIVE — GaussianEngine, regime detection]
│   ├── ema_spread    [ACTIVE — regime detection, breakout engine]
│   ├── trend_bias    [ACTIVE — breakout/trap engines]
│   ├── trend_strength[VECTOR_ONLY]
│   └── momentum_score[ACTIVE — GaussianEngine, regime, intent classification]
│
├── Volatility Features
│   ├── atr           [ACTIVE — CRT core, BitNet, ScoringEngine]
│   ├── volatility_ratio[ACTIVE — regime detection]
│   └── volatility_regime[VECTOR_ONLY — but decision-reachable per F-029]
│
├── Structure Features
│   ├── swing_high    [VECTOR_ONLY]
│   ├── swing_low     [VECTOR_ONLY]
│   ├── higher_high   [VECTOR_ONLY]
│   ├── lower_low     [VECTOR_ONLY]
│   ├── break_of_structure [VECTOR_ONLY]
│   ├── sweep_detected [ACTIVE — CRT scoring, trap detection]
│   ├── liquidity_sweep [INTERMEDIATE for double_sweep]
│   ├── double_sweep  [ACTIVE — CRT scoring, BitNet]
│   ├── liquidity_distance [VECTOR_ONLY — v3.0, no explicit consumer]
│   └── liquidity_pressure_score [VECTOR_ONLY — v3.0, no explicit consumer]
│
├── Session Features
│   ├── session       [ACTIVE — CRT engine gating]
│   └── hour_of_day   [ACTIVE — session encoding, CandleLoader metadata]
│
├── CRT Context Features
│   ├── disp_strength [ACTIVE — CRT core, BitNet, ScoringEngine]
│   ├── retest_depth  [ACTIVE — CRT core, BitNet, ScoringEngine]
│   └── candles_since_retest [ACTIVE — CRT scoring, BitNet]
│
└── Indicator Features
    ├── rsi_14        [VECTOR_ONLY — no explicit consumer]
    ├── macd_line     [VECTOR_ONLY — no explicit consumer]
    ├── macd_signal   [VECTOR_ONLY — no explicit consumer]
    └── macd_hist     [VECTOR_ONLY — no explicit consumer]
```

**Classification Key:**
- **ACTIVE** — explicitly read by at least one engine/scoring function
- **VECTOR_ONLY** — only consumed via the canonical 38-dim vector by ZoneGate (model-driven consumption)
- **INTERMEDIATE** — not in CANONICAL_FEATURES or consumed only as a building block

---

## Phase 4: Engine Consumption Map

### Engine: CRT Engine (crt_engine_v2.py)

**File:** `src/config_layer/crt_engine_v2.py`

**Consumes (from Candle objects, live state):**
- Candle.open, Candle.high, Candle.low, Candle.close (raw OHLCV)
- Candle.body_ratio, Candle.body_size, Candle.wick_size (derived Candle properties)
- ATR (computed internally, line 1002-1015)
- EMAs (computed internally, line 292-300)
- Range/Sweep detection (lines 985-1066)

**Required Features:** None from canonical dict — uses its own internal state machine.

**Optional Features (for scoring fusion):**
- body_ratio, disp_strength, atr, retest_depth, candles_since_retest, sweep_detected, double_sweep — used in `UltronRiskEngine.compute_score()` (line 1604) and `compute_soft_confirmation()` (line 1639)

**Unused Inputs:** Most canonical features — the CRT engine is self-contained.

**Decorative Configs:**
- `session_windows` — defined but only `allowed_sessions` is actively checked
- `atr_buffer_multiplier` — buffer = atr_period * this (config setting)
- `breakout_disp_threshold` — only used if intent classification reaches for it

**Evidence:** Lines 1052-1066 (detect_sweep uses only Candle + Range), lines 1604-1625 (UltronRiskEngine.compute_score uses only engine state, not canonical features), lines 1639-1652 (soft confirmation reads body_ratio from candle, not feature dict).

---

### Engine: HeuristicGaussianEngine

**File:** `src/engines/heuristic_gaussian_engine.py`

**Consumes (from canonical feature dict):**
- `ema_fast` (line 306)
- `ema_slow` (line 307)
- `momentum_score` (line 308)

**Required Features:** 3 (ema_fast, ema_slow, momentum_score)

**Optional Features:** ALL OTHER canonical features — accepted but ignored (line 301-302: only 3 keys are accessed)

**Unused Inputs:** 35 of 38 canonical features (91% unused)

**Decorative Configs:**
- `gaussian_mu` / `gaussian_sigma` — config overrides that ARE used if present
- `gaussian_registry_path` — hot-reload watcher

**Evidence:** Line 306-308 — only 3 features extracted from input dict. Line 300-302 asserts minimum length but ignores all others.

---

### Engine: RR Engine (Candle Polarity Index)

**File:** `src/engines/rr_engine.py`

**Consumes (from raw features dict):**
- `close` (line 47)
- `high` (line 48)
- `low` (line 49)

**Required Features:** 3 raw OHLCV fields

**Optional Features:** `min_rr` from config — RETAINED but NOT used in scoring (line 43, semantic fix comment)

**Unused Inputs:** All canonical features except close/high/low

**Decorative Configs:**
- `min_rr` — retained for backward compat, NO LONGER used (line 43)

**Evidence:** Lines 45-50 — only close/high/low accessed. Line 43 — `min_rr` config key read but never used in formula.

---

### Engine: ZoneGateEngine

**File:** `src/engines/zone_gate_engine.py`

**Consumes (full canonical vector):**
- All 38 canonical features via `_extract_vector()` (line 170-191)

**Required Features:** MUST have all `CANONICAL_KEYS` (line 163-167 — `filter_canonical_inputs`)

**Optional Features:** None — gate requires ALL canonical features.

**Unused Inputs:** The zone gate model itself may not use all features; this is opaque to the code.

**Evidence:** Line 163-167 — `filter_canonical_inputs` requires all CANONICAL_KEYS. Line 170-191 — full vector extraction.

---

### Engine: BitNet (bitnet_score)

**File:** `src/bitnet/bitnet_inference.py`

**Consumes (from canonical feature dict):**
- `body_ratio` (line 324)
- `retest_depth` (line 325)
- `disp_strength` (line 326)
- `atr` (line 327)
- `candles_since_retest` (line 328)
- `double_sweep` (line 329)

**Required Features:** 6

**Unused Inputs:** 32 of 38 canonical features (84% unused)

**Evidence:** Lines 323-331 — `bitnet_score()` builds a 6-dim vector from the feature dict.

---

### Engine: FusionEngine

**File:** `src/core/fusion_engine.py` (referenced from `engine_runner.py`)

**Consumes:**
- CRT score (`engine_results["crt"]`)
- Gaussian score (`engine_results["gaussian"]`)
- Zone Gate score (`engine_results["zone_gate"]`)
- RR score (`engine_results["rr"]`)

**Weights (from config):** weight_crt=0.4, weight_gaussian=0.3, weight_zone_gate=0.2, weight_rr=0.1

**Required:** ALL 4 engines must be present (enforced at line 53 — `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}`)

**Decorative Configs:**
- `rr_fusion.enabled` → FALSE (line 106)
- `fusion_use_evaluate` → FALSE (line 104)
- `fusion_compare_evaluate` → TRUE but observational only (line 103)
- Various FusionConfig fields like `llm_weight`, `neural_weight`, `llm_lower_band`, `llm_upper_band` — may be unused if `enable_llm=false`
- `gaussian_weight` — unused, overridden by weight_gaussian

**Evidence:** Lines 53, 106, 381-400 (FusionConfig construction), line 349 (`rr_fusion.enabled` gate).

---

### Engine: DecisionEngine

**File:** `src/core/decision_engine.py` (referenced)

**Consumes:** `fusion_result["final_score"]`
**Required:** Only the fused score.

---

### Engine: RegimeGovernor / UltronGovernor

**File:** `src/core/regime_governor.py` (referenced in `engine_runner.py` line 42)

**Consumes:** Dual-engine results (breakout/trap), regime classification string

**Required Features:** Features used in `detect_regime()`:
- `ema_spread` (line 145)
- `momentum_score` (line 146)
- `volatility_ratio` (line 147)

**Evidence:** Lines 144-157 — `detect_regime()` reads 3 features.

---

## Phase 5: Unused Feature Detection

### A: Generated but Never Consumed

These features ARE in `CANONICAL_FEATURES` (38-dim vector) but no engine explicitly reads them:

| Feature | Index | Status |
|---------|-------|--------|
| `macd_line` | 16 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `macd_signal` | 17 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `macd_hist` | 18 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `swing_high` | 22 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `swing_low` | 23 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `higher_high` | 24 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `lower_low` | 25 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `break_of_structure` | 21 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `rsi_14` | 15 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `volume_ratio` | 5 | **VECTOR_ONLY** — consumed only by ZoneGate model |
| `volume_spike` | 37 | **VECTOR_ONLY** — v3.0, consumed only by ZoneGate |
| `liquidity_distance` | 35 | **VECTOR_ONLY** — v3.0, consumed only by ZoneGate |
| `liquidity_pressure_score` | 36 | **VECTOR_ONLY** — v3.0, consumed only by ZoneGate |
| `trend_strength` | 11 | **VECTOR_ONLY** — consumed only by ZoneGate |
| `body_size` | 26 | **VECTOR_ONLY** — consumed only by ZoneGate |
| `wick_size` | 27 | **VECTOR_ONLY** — consumed only by ZoneGate |

### B: Intermediate Columns Generated but NOT in CANONICAL_FEATURES

These are computed by FeaturePipeline but dropped by `finalize()`:

| Column | File | Line |
|--------|------|------|
| `prev_close` | feature_pipeline.py | 182 |
| `delta_close` | feature_pipeline.py | 183 |
| `candle_body` | feature_pipeline.py | 185 |
| `upper_wick` | feature_pipeline.py | 186 |
| `lower_wick` | feature_pipeline.py | 187 |
| `direction` | feature_pipeline.py | 189 |
| `volume_ma20` | feature_pipeline.py | 217/224 |
| `ma_20`, `ma_50`, `ma_200` | feature_pipeline.py | 242-244 |
| `rsi_state` | feature_pipeline.py | 257 |
| `true_range` | feature_pipeline.py | 266 |
| `atr_14_raw` | feature_pipeline.py | 267 |
| `bb_upper`, `bb_lower` | feature_pipeline.py | 273-274 |
| `bb_width` | feature_pipeline.py | 275 |
| `bb_position` | feature_pipeline.py | 276 |
| `price_vs_ma20` | feature_pipeline.py | 293 |
| `price_vs_ma50` | feature_pipeline.py | 294 |
| `ma_slope_20` | feature_pipeline.py | 295 |
| `range_size` | feature_pipeline.py | 471 |
| `price_position` | feature_pipeline.py | 452 |
| `last_swing_high_price` | feature_pipeline.py | 373 |
| `last_swing_low_price` | feature_pipeline.py | 374 |
| `displacement_flag` | feature_pipeline.py | 518 |
| `retest_flag` | feature_pipeline.py | 535 |

### C: FEATURE_SCHEMA Dict (Legacy, Possibly Dead)

**File:** `src/features/feature_schema.py`, lines 17-42

The `FEATURE_SCHEMA` dict declares fields that are NEVER produced by `FeaturePipeline.run()`:

| Field | Type | Produced? |
|-------|------|-----------|
| `candle` | dict | NO — never built |
| `zone_strength` | float | NO — never populated |
| `trend_bias` | str | VIA CANONICAL — but as float, not str |
| `rejection_wick` | bool | NO — never computed |
| `volatility_flag` | bool | NO — compute_volatility_regime produces int8, not bool |
| `is_inside_bar` | bool | NO — never computed |
| `spread_pct` | float | NO — never computed in FeaturePipeline |
| `pattern_score` | float | NO — never computed |
| `sl_distance` | float | NO — never computed |
| `tp_ratio` | float | NO — never computed |

**Status:** **DECORATIVE/DORMANT** — `FEATURE_SCHEMA` exists but `CANONICAL_FEATURES` is the actual production schema. These fields are a legacy declaration.

### D: Decorative Configs

**File:** `configs/production/v2_multi_2026_04 - deepdeektry.json` (referenced) + `engine_runner.py` defaults

| Config Key | Value | Status | Evidence |
|------------|-------|--------|----------|
| `rr_fusion.enabled` | false | **DECORATIVE** | Line 349 — hard-gated, no code path sets to true |
| `fusion_engine.enable_llm` | false | **DECORATIVE** | All LLM weights exist but gated off |
| `fusion_engine.llm_weight` | 0.1 | **DECORATIVE** | Not applied when enable_llm=false |
| `fusion_engine.neural_weight` | 0.2 | **DECORATIVE** | Not applied unless neural_fn provided |
| `rr_fusion.full_feature_vector` | false | **DECORATIVE** | rr_fusion is disabled |
| `gaussian_impl` | "heuristic" | **ACTIVE** | Determines which Gaussian engine loads |
| `dual_engine.*` thresholds | various | **ACTIVE** | Used by breakout/trap/detect_regime |

---

## Phase 6: Modules Without OHLCV Dependencies

### CORE_INFRASTRUCTURE

| Module | File | No OHLCV? | Expected? | Should Consume? |
|--------|------|-----------|-----------|-----------------|
| Control Plane | `src/control_plane/registry.py` | YES | YES | NO — lifecycle/registry |
| Events | `src/events/event_fabric.py` | YES | YES | NO — telemetry envelope |
| Governance | `src/governance/` (in docs/) | YES | YES | NO — documentation |
| Cognitive Bus | `src/cognitive/cognitive_bus.py` | YES | YES | NO — async advisory |
| Utils | `src/utils/` | YES | YES | NO — logging, integrity |

### ANALYTICS

| Module | File | No OHLCV? | Expected? | Should Consume? |
|--------|------|-----------|-----------|-----------------|
| MT5 Analytics | `mt5_analytics/` | PARTIAL | YES | YES — analytics on trading data, not OHLCV features |
| SignalAudit | `src/core/signal_audit.py` | YES | YES | NO — decision audit trail |
| Collector | `src/core/collector.py` | YES | YES | NO — decision logging |

### AGENT

| Module | File | No OHLCV? | Expected? | Should Consume? |
|--------|------|-----------|-----------|-----------------|
| Agent | `src/agent/` | UNKNOWN | YES | NO — autonomous agent operates on decisions |
| Manual Tools | `manual_tools/trade_generator.py` | YES | YES | NO — manual trade entry |

### RESEARCH

| Module | File | No OHLCV? | Expected? | Should Consume? |
|--------|------|-----------|-----------|-----------------|
| Research Scrips | `scripts/research/` | PARTIAL | MAYBE | Research-specific OHLCV analysis is expected |
| Training | `scripts/training/` | PARTIAL | YES | Training consumes features FROM OHLCV |

---

## Phase 7: Dependency Tree

```
RAW OHLCV (CSV/TimescaleDB/MT5) [ACTIVE]
│
├─► CandleLoader.stream() [ACTIVE]
│   │
│   ├─► HTFBuilder [ACTIVE]
│   │   └─► CRTEngine.on_candle() [ACTIVE]
│   │       ├── StateMachine [ACTIVE]
│   │       ├── UltronRiskEngine [ACTIVE]
│   │       │   ├── compute_score() — uses state (not features)
│   │       │   └── approve_with_soft_conf() — uses state + bitnet_score()
│   │       └── ExecutionEngine [ACTIVE]
│   │           └── build_trade() → Trade
│   │
│   └─► FeaturePipeline.run() [ACTIVE]
│       │
│       ├── compute_price_features() [ACTIVE]
│       ├── compute_volume_features() [ACTIVE]
│       ├── compute_indicators() [ACTIVE]
│       ├── compute_trend_features() [ACTIVE]
│       ├── compute_volatility_regime() [ACTIVE]
│       ├── compute_context() [ACTIVE]
│       ├── compute_structure_liquidity() [ACTIVE]
│       ├── compute_normalization() [ACTIVE]
│       ├── compute_canonical_*() [ACTIVE] — 6 sub-methods
│       └── finalize() [ACTIVE] — drops NaNs, returns enriched DF
│           │
│           └── CANONICAL_FEATURES (38-dim vector) [ACTIVE]
│               │
│               ├── HeuristicGaussianEngine [ACTIVE]
│               │   └── uses 3/38 (ema_fast, ema_slow, momentum_score)
│               │
│               ├── ZoneGateEngine [ACTIVE]
│               │   └── uses 38/38 (full vector → model_fn)
│               │
│               ├── RREngine [ACTIVE]
│               │   └── uses 3 raw (close, high, low) — NOT canonical vector
│               │
│               ├── CRTEngine.cached_features [ACTIVE]
│               │   └── uses 6 (body_ratio, disp_strength, retest_depth, atr,
│               │                candles_since_retest, double_sweep)
│               │
│               ├── BitNet.bitnet_score() [ACTIVE if use_bitnet]
│               │   └── uses 6 (same 6 as cached_features)
│               │
│               ├── detect_regime() [ACTIVE]
│               │   └── uses 3 (ema_spread, momentum_score, volatility_ratio)
│               │
│               ├── breakout_engine() [ACTIVE]
│               │   └── uses 3 (trend_bias, momentum_score, ema_spread)
│               │
│               ├── trap_engine() [ACTIVE]
│               │   └── uses 3 (sweep_detected, disp_strength, trend_bias)
│               │
│               └── ExecutionEngine._derive_trade_intent() [ACTIVE]
│                   └── uses 5 (sweep_detected, double_sweep, retest_depth,
│                                candles_since_retest, momentum_score,
│                                body_ratio, disp_strength)
│
├─► Research Scripts [DORMANT]
│   ├── fetch_crypto_ccxt.py
│   ├── fetch_forex_yfinance.py
│   ├── fetch_candles_hummingbot.py
│   └── bnbusdt_* analysis scripts
│
└─► Training Pipelines [ACTIVE]
    └── Uses FeaturePipeline output + feature vectors
```

**Status Key:**
- **ACTIVE** — confirmed in production backtest/live path
- **DORMANT** — code exists but not in active call chain
- **DECORATIVE** — present in config but no behavioral effect
- **BROKEN** — references non-existent features or config keys

---

## Phase 8: Final Report

### 1. OHLCV Producers

| Producer | File | Function | Schema | Production? |
|----------|------|----------|--------|-------------|
| CSV CandleLoader | `backtest_v2.py` | `CandleLoader.stream()` | Candle (ts,OHLC,V) | YES |
| HistoricalFetcher DB | `historical_fetcher.py` | `fetch_and_store()` / `load()` | OHLCVRow (ts,pair,tf,OHLC,V) | YES |
| HistoricalFetcher MT5 | `historical_fetcher.py` | `_fetch_from_mt5()` | OHLCVRow | CONDITIONAL |
| HistoricalFetcher CSV | `historical_fetcher.py` | `_load_from_csv()` | OHLCVRow | FALLBACK |
| FeaturePipeline | `feature_pipeline.py` | `run()` | 38-dim vector | YES |
| CCXT fetcher | `scripts/data/fetch_crypto_ccxt.py` | — | CSV | RESEARCH |
| Yahoo Finance | `scripts/data/fetch_forex_yfinance.py` | — | CSV | RESEARCH |
| Hummingbot | `scripts/data/fetch_candles_hummingbot.py` | — | CSV | RESEARCH |

### 2. Feature Inventory

| # | Feature | Depends On | Active Consumer | Status |
|---|---------|------------|-----------------|--------|
| 0 | open | OHLCV | ZoneGate vector | VECTOR_ONLY |
| 1 | high | OHLCV | RREngine, ZoneGate, CRTengine (separate) | ACTIVE |
| 2 | low | OHLCV | RREngine, ZoneGate, CRTengine (separate) | ACTIVE |
| 3 | close | OHLCV | RREngine, ZoneGate, CRTengine (separate) | ACTIVE |
| 4 | volume | OHLCV | ZoneGate (as canonical), FeaturePipeline (intermediate) | INTERMEDIATE |
| 5 | volume_ratio | volume, proxy | ZoneGate vector | VECTOR_ONLY |
| 6 | double_sweep | liquidity_sweep | ScoringEngine, BitNet, CRTengine | ACTIVE |
| 7 | ema_fast | close(9) | HeuristicGaussian, regime | ACTIVE |
| 8 | ema_slow | close(21) | HeuristicGaussian, regime | ACTIVE |
| 9 | ema_spread | ema_fast, ema_slow, atr | detect_regime, breakout_engine | ACTIVE |
| 10 | trend_bias | ema_fast(9), ema_slow(21) | breakout_engine, trap_engine | ACTIVE |
| 11 | trend_strength | ma_slope_20 | ZoneGate vector | VECTOR_ONLY |
| 12 | momentum_score | close.diff(), atr | HeuristicGaussian, regime, intent | ACTIVE |
| 13 | atr | ATR(14)/close | ScoringEngine, BitNet, CRT, regime | ACTIVE |
| 14 | volatility_ratio | high, low, atr | detect_regime | ACTIVE |
| 15 | rsi_14 | close | ZoneGate vector | VECTOR_ONLY |
| 16 | macd_line | close EMA12/26 | ZoneGate vector | VECTOR_ONLY |
| 17 | macd_signal | macd_line | ZoneGate vector | VECTOR_ONLY |
| 18 | macd_hist | macd_line, signal | ZoneGate vector | VECTOR_ONLY |
| 19 | sweep_detected | liquidity_sweep | CRTengine, trap_engine | ACTIVE |
| 20 | liquidity_sweep | swing levels | CRTengine (via double_sweep) | INTERMEDIATE |
| 21 | break_of_structure | swing levels, close | ZoneGate vector | VECTOR_ONLY |
| 22 | swing_high | high (rolling) | ZoneGate vector | VECTOR_ONLY |
| 23 | swing_low | low (rolling) | ZoneGate vector | VECTOR_ONLY |
| 24 | higher_high | high, swing_high | ZoneGate vector | VECTOR_ONLY |
| 25 | lower_low | low, swing_low | ZoneGate vector | VECTOR_ONLY |
| 26 | body_size | open, close | ZoneGate vector | VECTOR_ONLY |
| 27 | wick_size | high, low | ZoneGate vector | VECTOR_ONLY |
| 28 | body_ratio | open, high, low, close | ScoringEngine, BitNet, CRT | ACTIVE |
| 29 | volatility_regime | atr_14 percentile | ZoneGate vector, decision-reachable | VECTOR_ONLY |
| 30 | session | hour | CRTengine allowed_sessions | ACTIVE |
| 31 | hour_of_day | timestamp | CRTengine | ACTIVE |
| 32 | disp_strength | body_size, atr | ScoringEngine, BitNet, CRT, trap | ACTIVE |
| 33 | retest_depth | close, ema_fast, atr | ScoringEngine, BitNet, CRT | ACTIVE |
| 34 | candles_since_retest | sweep groups | ScoringEngine, BitNet, CRT | ACTIVE |
| 35 | liquidity_distance | swing levels, BOS, atr | ZoneGate vector | VECTOR_ONLY |
| 36 | liquidity_pressure_score | liquidity_distance | ZoneGate vector | VECTOR_ONLY |
| 37 | volume_spike | volume_ratio | ZoneGate vector | VECTOR_ONLY |

### 3. Active Feature Consumers (By Engine)

| Engine | Features Consumed | Count | % of 38 |
|--------|------------------|-------|---------|
| CRTEngine | body_ratio, disp_strength, atr, retest_depth, candles_since_retest, sweep_detected, double_sweep + raw OHLCV (separate) | 7 + 4 raw | 18% |
| HeuristicGaussianEngine | ema_fast, ema_slow, momentum_score | 3 | 8% |
| RREngine | close, high, low (raw) | 3 | 8% |
| BitNet (bitnet_score) | body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep | 6 | 16% |
| detect_regime | ema_spread, momentum_score, volatility_ratio | 3 | 8% |
| breakout_engine | trend_bias, momentum_score, ema_spread | 3 | 8% |
| trap_engine | sweep_detected, disp_strength, trend_bias | 3 | 8% |
| _derive_trade_intent | double_sweep, retest_depth, candles_since_retest, momentum_score, body_ratio, disp_strength | 6 | 16% |
| ZoneGate (model_fn) | ALL 38 (opaque model consumption) | 38 | 100% |

### 4. Dead Features

| Feature | Located In | Why Dead |
|---------|-----------|----------|
| `FEATURE_SCHEMA["candle"]` | `feature_schema.py:28` | Declared as dict type, never built by FeaturePipeline |
| `FEATURE_SCHEMA["zone_strength"]` | `feature_schema.py:29` | Never populated |
| `FEATURE_SCHEMA["rejection_wick"]` | `feature_schema.py:32` | Never computed |
| `FEATURE_SCHEMA["volatility_flag"]` | `feature_schema.py:33` | volatility_regime exists, volatility_flag does not |
| `FEATURE_SCHEMA["is_inside_bar"]` | `feature_schema.py:34` | Never computed |
| `FEATURE_SCHEMA["pattern_score"]` | `feature_schema.py:38` | Never computed |
| `FEATURE_SCHEMA["sl_distance"]` | `feature_schema.py:39` | Never computed |
| `FEATURE_SCHEMA["tp_ratio"]` | `feature_schema.py:40` | Never computed |
| `FEATURE_SCHEMA["spread_pct"]` | `feature_schema.py:35` | Not computed by FeaturePipeline (only in CRTConfig) |
| `bb_upper` / `bb_lower` | feature_pipeline.py | Computed but never used (not canonical) |
| `bb_width` / `bb_position` | feature_pipeline.py | Computed, normalized, then dropped by finalize() |
| `rsi_state` | feature_pipeline.py | Computed then dropped by finalize() |

### 5. Decorative Configs

| Config Path | Value | Status | Evidence |
|-------------|-------|--------|----------|
| `engine_runner.rr_fusion.enabled` | false | DECORATIVE | engine_runner.py line 349 |
| `engine_runner.fusion_engine.enable_llm` | false in defaults | DECORATIVE | engine_runner.py line 394 |
| `engine_runner.fusion_engine.llm_weight` | 0.1 | DECORATIVE | Only relevant if enable_llm=true |
| `engine_runner.fusion_engine.neural_weight` | 0.2 | DECORATIVE | Only relevant if neural_fn provided |
| `rr_engine.min_rr` | 1.5 | DECORATIVE | rr_engine.py line 43 — retained but NOT used |
| `engine_runner.fusion_use_evaluate` | false | DECORATIVE | engine_runner.py line 416 |
| `engine_runner.cognitive_layer.enabled` | false by default | DECORATIVE | engine_runner.py line 455 |
| `crt_config.session_windows` | London/NY/Asia | DECORATIVE-PARTIAL | Used by score_time() but allowed_sessions is the actual gate |

### 6. Modules Without OHLCV Dependencies

| Module | Directory | Category | Expected? |
|--------|-----------|----------|-----------|
| Control Plane Registry | `src/control_plane/` | CORE_INFRASTRUCTURE | YES |
| Event Fabric | `src/events/` | CORE_INFRASTRUCTURE | YES |
| Cognitive Bus | `src/cognitive/` | AGENT | YES |
| Governance docs | `docs/governance/` | GOVERNANCE | YES |
| SignalAudit | `src/core/signal_audit.py` | ANALYTICS | YES |
| Collector | `src/core/collector.py` | ANALYTICS | YES |
| AcceptanceController | `src/core/acceptance_controller.py` | RISK | YES |
| ConvergenceController | `src/core/convergence_controller.py` | RISK | YES |
| Integrity Events | `src/utils/integrity_events.py` | CORE_INFRASTRUCTURE | YES |
| Logging Config | `src/utils/logging_config.py` | CORE_INFRASTRUCTURE | YES |
| Sweep Trace Logger | `src/utils/sweep_trace_logger.py` | ANALYTICS | YES |

### 7. Actual Production Data Flow

```
                    ╔═══════════════════════════════════════╗
                    ║        RAW OHLCV (CSV / DB / MT5)     ║
                    ╚═══════════════════════════════════════╝
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
      ┌───────────────────────┐     ┌───────────────────────┐
      │  CandleLoader.stream()│     │ FeaturePipeline.run() │
      │  (Candle objects)     │     │ (38-dim vector)       │
      └───────────┬───────────┘     └───────────┬───────────┘
                  │                             │
                  ▼                             │
      ┌───────────────────────┐                 │
      │   CRTEngine.on_candle │                 │
      │   (internal ATR, EMA, │                 │
      │    Range, Sweep,      │                 │
      │    State Machine)     │                 │
      └───────────┬───────────┘                 │
                  │                             │
                  │  body_ratio, disp_strength, │
                  │  retest_depth, atr,         │
                  │  candles_since_retest,      │
                  │  double_sweep               │
                  ▼                             ▼
      ┌───────────────────────────────────────────────┐
      │           EngineRunner.run(features)           │
      │                                                │
      │  ┌─────────┐  ┌──────────┐  ┌──────┐  ┌────┐ │
      │  │ CRT (2) │  │ Gaussian │  │Zone  │  │ RR │ │
      │  │scoring  │  │ (heuristic│  │Gate  │  │(Cndl│ │
      │  │         │  │ ema/mom) │  │(full │  │Pol) │ │
      │  └────┬────┘  └────┬─────┘  │ vec) │  └──┬──┘ │
      │       │             │        └──┬───┘     │    │
      │       └──────┬──────┘           │         │    │
      │              ▼                  ▼         ▼    │
      │       ┌──────────────────────────────────┐     │
      │       │        FusionEngine              │     │
      │       │  0.4*CRT + 0.3*Gaussian +        │     │
      │       │  0.2*ZoneGate + 0.1*RR           │     │
      │       └──────────────┬───────────────────┘     │
      │                      ▼                         │
      │       ┌────────────────────────┐               │
      │       │    DecisionEngine      │               │
      │       │  (threshold vs score)  │               │
      │       └───────────┬────────────┘               │
      │                   ▼                             │
      │       ╔═══════════════════════════╗             │
      │       ║  ACCEPT / REJECT / BLOCK ║             │
      │       ╚═══════════════════════════╝             │
      └───────────────────────────────────────────────┘
```

### 8. Recommended Cleanup

#### Remove (No Impact)
- `FEATURE_SCHEMA` dict (lines 17-42 of feature_schema.py) — superseded by `CANONICAL_FEATURES`
- `rsi_state` from `FeaturePipeline.compute_indicators()` — never consumed
- `bb_width`, `bb_position`, `bb_upper`, `bb_lower` — never consumed (not canonical)
- `price_vs_ma20`, `price_vs_ma50`, `ma_slope_20` — intermediate, not canonical
- `true_range`, `atr_14_raw` — already folded into atr
- `direction` (int8) — not consumed anywhere
- `upper_wick`, `lower_wick` — not canonical, used only for structure detection
- `prev_close`, `delta_close`, `candle_body` — intermediate only
- `price_position` and `range_size` — computed but never read
- `displacement_flag` and `retest_flag` — intermediate for canonical features

#### Deprecate
- `rr_fusion` config section — never enabled (`enabled: false`)
- `min_rr` in RREngine config — retained but not used in formula
- `session_windows` in CRTConfig — `allowed_sessions` is the actual gate
- `fusion_use_evaluate` / `fusion_compare_evaluate` — always false/observational
- `llm_weight`, `neural_weight` — not applied when `enable_llm=false`
- `volatility_regime` with GLOBAL percentile ranking (env option TRUST_VOLREGIME_CAUSAL exists but default is non-causal) — known lookahead issue per F-029

#### Wire (Needs Investigation)
- **14 features consumed ONLY by ZoneGate model vector** — are they actually influencing decisions? The model_fn may ignore them. Without model introspection, **these are at risk of being dead weight in the pipeline.**
- `swing_high/low` with `center=True` — known lookahead (TRUST_SWING_CAUSAL env var exists but is off). Should be made causal by default.
- `candles_since_retest` — was previously bugged (used retest_flag.cumsum() instead of sweep_groups.cumsum()), now fixed. Verify no models were trained on bugged data.

#### Validate
- That CRTEngine's internal ATR(14) and FeaturePipeline's `atr_14` produce identical values. Slight implementation differences (manual vs pandas rolling) could cause state machine / scoring divergence.
- That EMA(2,5) used by CRTEngine for live confirmation is NOT the same as EMA(9,21) in canonical features. Any code path mixing these would produce incorrect scores.

#### Investigate
- **Why does FeaturePipeline compute 38 features when only ~10 are explicitly consumed?** The ZoneGate model is the sole consumer of the remaining 28. If the ZoneGate model's weight is 0.2 in fusion, 73% of computational cost goes into features that affect only 20% of the final score.
- **Research scripts** (`scripts/data/fetch_*`, `scripts/research/bnbusdt_*`) — verify they are documented as non-production. They appear dormant.
- **`SCHEMA_V2_FEATURE_DIM = 35`** — v3.0 added 3 features (liquidity_distance, liquidity_pressure_score, volume_spike). Verify no models were trained on 35-dim vectors that are now receiving truncated 38-dim vectors. `FeatureSchemaRegistry` has a check but it's opt-in via `register()`.
- **FEATURE_SCHEMA dict** — line 42 has `"candle": dict` but FeaturePipeline never creates it. Was it supposed to expand to open, high, low, close? Is something reading it?

---

*End of OHLCV Data Lineage & Feature Usage Forensics Report*