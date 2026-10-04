# HUMAN-READABLE EXECUTION COGNITION
## Runtime Analysis: src/features, src/feedback, src/governance, src/inout

**Generated:** 2026-05-20  
**Source:** Direct code extraction only. No assumptions beyond immediate runtime scope.

---

# TABLE OF CONTENTS

1. [src/features — Feature Engineering Layer](#1-srcfeatures)
2. [src/feedback — AI Feedback Layer](#2-srcfeedback)
3. [src/governance — Governance & Promotion Layer](#3-srcgovernance)
4. [src/inout — Data Ingestion/Output Layer](#4-srcinout)

---

# 1. src/features

## 1.1 feature_schema.py

### File Purpose
Single source of truth for what a "feature vector" looks like. Every model trainer, inference engine, data builder, and validator imports from this file to agree on feature names, ordering, and dimensions. If this file says feature index 35 is `liquidity_distance`, every component that reads index 35 must be reading `liquidity_distance`.

### Runtime Role
Loaded at module import time by every component in the system. Not a runtime process — it's a data contract enforced via assertions at module load time.

### Classes

#### SchemaObject (lines 124-178)
- **Purpose:** Wraps a schema definition to support both `schema.n_features` and `schema["n_features"]` access patterns. Required because `training/trainer.py` uses attribute-style access.
- **Ownership:** Module-level. Created once at import for TRADENET_SCHEMA and GAUSSIAN_SCHEMA.
- **Runtime Responsibility:** Provides feature count, feature name list, checksum to any code that asks.

#### FeatureSchemaRegistry (lines 214-264)
- **Purpose:** Class-level registry that maps model version strings to their stored `feature_order_hash`. Enables runtime detection of schema drift between training time and inference time.
- **Ownership:** Class-level dict `_registry`. No instances needed.
- **Runtime Responsibility:** At model save time in trainer.py, `register()` stores the current hash. At inference time in engine code, `check_compatibility()` compares stored vs current hash. If different, the caller should truncate the vector to the model's training dimension.

### Methods/Functions

| Element | Details |
|---------|---------|
| **`_feature_order_hash(features)`** | |
| Human Purpose | Generate a deterministic 16-char SHA-256 hex digest of feature name ordering. Detects semantic corruption (same length but different features). |
| Invocation Sources | Called once at module import to produce FEATURE_ORDER_HASH. |
| Downstream Calls | hashlib.sha256, json.dumps |
| Runtime Flow | Serializes feature tuple as JSON (preserving order), SHA-256 hashes, takes first 16 hex chars. |
| Inputs | tuple of feature name strings (CANONICAL_FEATURES) |
| Outputs | str, 16 hex characters |
| State Mutations | None — pure function |
| Side Effects | None |
| Failure Modes | Non-deterministic if tuple order changes across runs — but tuple is hardcoded, so this is stable. |
| Determinism | YES — pure function |
| Trust | **CANONICAL** — loaded at import, not mutable at runtime |

| Element | Details |
|---------|---------|
| **`FeatureSchemaRegistry.register(version, hash)`** | |
| Human Purpose | Record the feature order hash a model was trained on. Called during model save. |
| Invocation Sources | trainer.py at model save time |
| Runtime Flow | Stores `version → feature_order_hash` in class-level dict |
| Failure Modes | No type checking — any string accepted |
| Corruption Risk | If caller passes wrong hash, schema mismatch detection is silent |

| Element | Details |
|---------|---------|
| **`FeatureSchemaRegistry.check_compatibility(version)`** | |
| Human Purpose | At inference time, check if the current runtime schema matches what the model was trained on. |
| Runtime Flow | Looks up stored hash for version. If missing → return True (fail-open — treats unknown model as compatible). If mismatch → return False (caller truncates). |
| Fallbacks | **CRITICAL FALLBACK:** If `version` was never registered, returns `True` even if the schema has changed. This means an unregistered model silently ignores schema drift. |
| Failure Modes | Silent compatibility when version was never registered |
| Corruption Risk | **GOVERNANCE CONTAMINATION:** Unregistered models skip truncation and may feed wrong-dimension vectors into inference. |

| Element | Description |
|---------|-------------|
| **`schema_for_model(model_type)`** | Simple dict lookup — returns SchemaObject for "tradenet" or "gaussian". Raises KeyError for unknown types. |
| **`assert_schema_version(model_type, version)`** | Validates schema version matches expected. Raises SchemaVersionError on mismatch. |
| **`validate_vector(vec, schema, label)`** | Checks vector length matches `n_features`. Raises ValueError on mismatch. |
| **`validate_features(features)`** | Delegates to `schema_validator.validate_features` with CANONICAL_FEATURES. |
| **`encode_session_ordinal(session)`** | Maps session string → int {0,1,2}. Returns -1 for None/unknown. Not used by canonical pipeline — legacy. |

### Data Structures

| Constant | Value | Purpose |
|----------|-------|---------|
| `CANONICAL_FEATURES` | 38-tuple of strings | Definitive feature ordering for all vector operations |
| `CANONICAL_FEATURE_DIM` | 38 | Assertion target — must match len(CANONICAL_FEATURES) |
| `SCHEMA_V2_FEATURE_DIM` | 35 | Backward-compat: old models used 35 features |
| `FEATURE_SCHEMA` | dict of name→type | Loose contract (not currently enforced at vector build time) |
| `SESSION_MAP` | 4 entries | "london"→0.0, "newyork"→1.0, "asian"→2.0, "overlap"→3.0 |
| `TREND_MAP` | 3 entries | "bullish"→1.0, "bearish"→-1.0, "neutral"→0.0 |
| `TRADENET_SCHEMA` | SchemaObject | 38 features, version 3.0 |
| `GAUSSIAN_SCHEMA` | SchemaObject | 38 features, version 3.0 |

### Hidden Defaults / Silent Fallbacks
- `_feature_order_hash()` uses SHA-256[:16] — 16 chars provides 64 bits of collision resistance. Acceptable for drift detection but not cryptographic.
- `check_compatibility()` fail-open for unregistered models: **This is a gap.** If a model is loaded without calling `register()` first, drift goes undetected.

### Trust Classification: **CANONICAL**
This file is the axis around which the entire feature system rotates. Every consumer depends on its constants. A change here propagates everywhere.

---

## 1.2 crt_feature_builder.py

### File Purpose
Converts three input structures (a CRT trade record, a raw OHLCV candle dict, and a market state dict) into a single dict containing ALL 38 canonical features. Strict contract: output must have exactly the same keys as `CANONICAL_FEATURES`, no extras, all floats.

### Runtime Role
Called by BitNet inference path when building the feature vector for a specific trade decision. **Not** called by the batch pipeline (FeaturePipeline.run()). This is a live/real-time code path.

### Functions

#### `build_bitnet_features(trade, candle, state) -> dict`

| Attribute | Detail |
|-----------|--------|
| **Human Purpose** | Given a trade's entry/SL/TP, the current candle's OHLCV+indicators, and market state flags, produce the exact 38-dim feature dict the BitNet model expects. |
| **Invocation Sources** | BitNet engine code (e.g., `ml_bitnet_engine.py` or similar) when making a trade decision |
| **Downstream Calls** | Imports `CANONICAL_FEATURES`, `SESSION_MAP`, `TREND_MAP` from feature_schema |
| **Runtime Flow** | 1. Extracts OHLCV from candle (default 0.0 if missing). 2. Extracts volume features. 3. Extracts trend features (ema_fast/slow, bias, strength). 4. Extracts momentum. 5. Extracts volatility (atr, volatility_ratio). 6. Extracts indicators (rsi_14, macd). 7. Extracts structure flags (sweep, liquidity_sweep, BOS). 8. Extracts swing features. 9. Computes body_size, wick_size, body_ratio from OHLC. 10. Extracts volatility_regime. 11. Encodes session/trend_bias via SESSION_MAP/TREND_MAP. 12. Extracts CRT-specific features (disp_strength, retest_depth, candles_since_retest). 13. NaN/inf guard → sets offending values to 0.0. 14. STRICT assertion: output keys == CANONICAL_FEATURES keys. |
| **Inputs** | `trade: dict` (entry, sl, tp), `candle: dict` (OHLCV + indicators), `state: dict` (market state flags) |
| **Outputs** | `dict` with exactly 38 float keys matching CANONICAL_FEATURES |
| **State Mutations** | None — pure function |
| **Side Effects** | Logger warning if NaN/inf detected |
| **File Writes** | None |
| **Network/API** | None |
| **Subprocess** | None |

### Hidden Defaults
- **ALL candle.get() calls default to 0.0.** If the candle dict is missing `open`, the feature vector silently gets `open=0.0`. Same for every other candle field.
- **ALL state.get() calls default to 0.0.** If state is empty, `double_sweep`, `trend_bias`, `momentum_score`, `volatility_ratio`, `sweep_detected`, `liquidity_sweep`, `break_of_structure`, `swing_high`, `swing_low`, `higher_high`, `lower_low`, `volatility_regime`, `disp_strength`, `retest_depth`, `candles_since_retest` all silently default to 0.0.
- `session` defaults to `"unknown"` from `candle.get("session", "unknown")`. SESSION_MAP.get("unknown", 0.0) → 0.0 because `.get()` on the SESSION_MAP dict returns 0.0 for unknown keys. So unknown sessions silently encode as 0.0 (London).
- `trend_bias` defaults to `"neutral"` from `state.get("trend_bias", "neutral")` → TREND_MAP["neutral"] = 0.0.
- **NaN guard silently replaces NaN/inf with 0.0.** This is a WARNING-level log but no caller reading the return value knows if a value was corrupted.

### Failure Modes
- **Silent 0.0 poisoning:** If `candle` or `state` dicts are incomplete (e.g. missing keys), the function silently returns 0.0 for those features. This produces a "valid" vector that models will happily score. **There is no minimum-data-quality check.**
- **AssertionError on schema drift:** If CANONICAL_FEATURES changes but this function isn't updated, the final assertion catches it.

### Trust Classification: **LIVE** (actively used in real-time inference path)
**DANGEROUS ASPECT:** The function silently coerces missing data to 0.0 without any mechanism to communicate data quality to the caller. The "no missing keys, no extra keys" assertion only catches structural schema drift, not data completeness.

---

## 1.3 feature_builder.py

### File Purpose
Pre-cursor to the CRT feature builder. Validates raw OHLCV fields and derived indicators (ATR, EMA_fast, EMA_slow, RSI) are present from the data source. Adds a `_data_integrity = "real"` sentinel when all required fields pass. Used by the non-BitNet pipeline path.

### Runtime Role
Called by the Collector/decision engine when constructing the input dict for scoring. Exists as a separate path from crt_feature_builder because it does NOT produce the full 38-dim canonical vector — it produces a raw dict that is later converted.

### Classes

#### FeatureBuilder

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Validate raw input fields and add integrity sentinel. |
| **Ownership** | Instantiated per config/run with config dict. |
| **Runtime Responsibility** | Validation gate — if missing required fields, raises ValueError. |

### Methods

#### `FeatureBuilder.build(raw) -> dict`

| Attribute | Detail |
|-----------|--------|
| **Human Purpose** | "Check that the raw data has all required OHLCV and indicator fields. If any are missing, crash immediately with a clear error. If all present, add a 'real data' tag and return." |
| **Invocation Sources** | Called by decision engine code when processing a new candle |
| **Runtime Flow** | 1. Checks REQUIRED_RAW_FIELDS ("close","high","low","open","volume") are in `raw`. 2. Checks REQUIRED_DERIVED_FIELDS ("atr","ema_fast","ema_slow","rsi") are in `raw`. 3. Copies raw fields to result. 4. Copies derived fields to result. 5. Sets `session = raw.get("session", "unknown")` — intentionally no default. 6. Sets `symbol = raw.get("symbol", "default")`. 7. Sets `_data_integrity = "real"`. |
| **Inputs** | `raw: dict` — must have close, high, low, open, volume, atr, ema_fast, ema_slow, rsi |
| **Outputs** | `dict` with 10 keys (5 raw + 4 derived + session + symbol + integrity) |
| **Failure Modes** | ValueError for missing raw fields. ValueError for missing derived fields — "Synthetic defaults are not permitted." |
| **Determinism** | YES |
| **Trust** | **CANONICAL** — strict fail-fast validation, no silent defaults on mandatory fields. |

### Hidden Defaults
- `session` defaults to `"unknown"` — not in the adapter's allowed_sessions list, so downstream will reject the row. This is an intentional anti-default.
- `symbol` defaults to `"default"` — unlikely to match any zone in the zone registry. If it does, it's a silent fallback.

### Trust Classification: **CANONICAL**
Clean validation contract. No data corruption path unless caller catches ValueError silently.

---

## 1.4 feature_pipeline.py

### File Purpose
The full batch feature engineering pipeline. Takes a DataFrame of raw OHLCV, computes all technical indicators (pandas/numpy only, no TA-lib), generates all 38 canonical features, applies NaN cleanup, and produces a cleaned feature matrix. Also runs drift monitoring via FeatureMonitor.

### Runtime Role
Called for batch processing:
- Historical backtesting (BacktestRunner)
- Dataset building for training
- Strategy governance validation (StrategyBacktester)

NOT called for single-candle live inference.

### Classes

#### FeaturePipeline

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Batch feature engineering from raw DataFrame to cleaned 38-dim matrix. |
| **Ownership** | Created per-dataframe with a copy of input. Maintains internal monitor for drift tracking across batches. |
| **Runtime Responsibility** | Orchestrate all 15 compute stages, clean NaN, produce (enriched_df, vectors) tuple. |

### Pipeline Stages (in run() order)

```
run() execution flow:
  1. compute_price_features()      → prev_close, delta, body, wicks, direction
  2. compute_volume_features()      → volume_ma20, volume_ratio, volume_spike (FX-safe)
  3. compute_indicators()           → MAs, RSI(14), ATR(14), Bollinger, MACD
  4. compute_trend_features()       → price_vs_MA20/50, ma_slope, trend_strength
  5. compute_volatility_regime()    → 3-class ATR percentile (LOW/MID/HIGH)
  6. compute_context()              → hour_of_day, day_of_week, session
  7. compute_structure_liquidity()  → swing_high/low, BOS, liquidity_sweep
  8. compute_normalization()        → Z-score of 5 columns (50-bar window)
  9. compute_canonical_price_features() → body_ratio, wick_size, body_size, price_position
  10. compute_canonical_volatility_features() → atr(relative), range_size, volatility_ratio
  11. compute_canonical_ema_features() → ema_fast/slow/spread, momentum_score
  12. compute_canonical_trend_features() → trend_bias (from EMA cross)
  13. compute_canonical_structure_features() → sweep_detected, displacement, retest, double_sweep
  14. compute_canonical_temporal_features() → disp_strength, retest_depth, candles_since_retest
  15. compute_liquidity_distance()  → liquidity_distance, liquidity_pressure_score (v3.0)
  16. promote_volume_spike()        → adaptive 75th %ile threshold (overwrites fixed)
  17. compute_canonical_session()   → int8 cast
  18. finalize()                    → replace inf→NaN, drop NaN rows
  19. log_critical_feature_health() → zero/nan rate for 8 critical features
  20. build_feature_vector()        → (N, 38) float32 numpy array
  21. FeatureMonitor update         → drift detection on retest_depth/body_ratio/disp_strength
```

### Key Methods

#### `_validate_input()` (line 161)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Checks timestamp, open, high, low, close exist. Adds volume=0.0 if missing (Forex safe fallback). Coerces all OHLCV to numeric. |
| **Hidden Default** | **Volume defaults to 0.0 if missing.** The volume substitution logic in compute_volume_features handles this. |
| **Failure Mode** | ValueError if timestamp/OHLC missing. Too lenient? |

#### `compute_volume_features()` (line 200)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Checks if ALL volume values are zero → substitutes intrabar range (high-low) as tick proxy. Uses rolling 20-bar MA for volume_ratio. |
| **Fallback** | When proxy_ma20 <= 0, volume_ratio = 1.0 |
| **Corruption Risk** | If volume has some zero and some non-zero values, it uses real volume. But a single non-zero value in 5000 rows triggers real-volume path for all rows. |

#### `compute_indicators()` (line 236)
| Attribute | Detail |
|-----------|--------|
| **RSI(14) formula** | Standard Wilder RSI: `100 - 100/(1+RS)`. Previous bug was using `100*(gain-loss)/(gain+loss)` which gave [-100,100] range. Fixed in this version. |
| **ATR(14)** | True Range = max(high-low, abs(high-prev_close), abs(low-prev_close)), then 14-bar SMA. |
| **MACD** | 12/26 EMA diff → signal line 9-EMA → histogram. |

#### `compute_structure_liquidity()` (line 336)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Uses 5-bar centered rolling window (SWING_WINDOW=2, so w=5) to detect swing highs/lows. Then uses ffill for reference prices. |
| **Lookahead risk** | `center=True` on rolling() means swing detection uses future bars. **DOCS ACKNOWLEDGE THIS:** "For historical backtesting this is acceptable. For live inference, replace with a trailing-only swing detector." |
| **Guard rails** | Assertions that swing_high != swing_low and higher_high != lower_low detect copy-paste bugs. |

#### `compute_canonical_temporal_features()` (line 523)
| Attribute | Detail |
|-----------|--------|
| **disp_strength** | `body_size / (atr * close)`. NaN when atr=0 or close=0. Clipped [0, 3.0]. |
| **retest_depth** | `abs(close - ema_fast) / (atr * close)`. Only computed when retest_flag=1. NaN otherwise. Clipped [0, 1.0]. |
| **candles_since_retest** | Uses `liquidity_sweep` events to count bars since the sweep that set up the retest. Falls back to `retest_flag` grouping if liquidity_sweep column missing. INT16. |

#### `compute_liquidity_distance()` (line 562)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Computes ATR-normalized distance to nearest of three levels: last swing high, last swing low, last BOS level. Then computes pressure score as exp(-0.5 * distance). |
| **Lookahead safety** | All reference levels use .shift(1) so they reflect pre-bar state. Safe. |
| **Fallback** | `atr_safe` becomes NaN when atr=0, producing NaN distance which gets clipped at lower=0.0. |
| **Pressure score fallback** | `fillna(10.0)` before exp → exp(-5.0) ≈ 0.0067. Not zero, but very low. |

#### `promote_volume_spike()` (line 617)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Overwrites fixed-threshold volume_spike with adaptive 75th percentile over 50-bar rolling window. Falls back to 1.5× threshold when < 20 samples. |
| **Overwrite behavior** | Silently replaces the column computed in step 2. |

#### `finalize()` (line 657)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Replaces inf/-inf with NaN, then drops ALL rows where ANY canonical feature is NaN. |
| **Impact** | With 200-bar MA warmup, first ~200 rows are dropped. With ATR-gated features like momentum_score and ema_spread emitting NaN during ATR warmup (14 bars), more rows may be dropped. |

#### `run()` (line 736)
| Attribute | Detail |
|-----------|--------|
| **What happens** | Executes all 17 compute stages in sequence, finalizes, builds vectors, updates FeatureMonitor. |
| **Return** | (enriched_df, vectors) where vectors is (N, 38) float32 ndarray. |

### FeatureMonitor Integration (lines 773-800)
After pipeline run, iterates every row checking `retest_depth`, `body_ratio`, `disp_strength` for Z-score drift. Logs warning if any drift detected. Only works when all three columns are present in the output df.

### Trust Classification: **CANONICAL**
This is the reference feature pipeline used by backtesting, training, and governance validation. Any bug here poisons all downstream analyses.

---

## 1.5 feature_monitor.py

### File Purpose
Rolling-window distribution tracker for the three most predictive CRT features: retest_depth, body_ratio, disp_strength. Detects out-of-distribution trades via Z-score and flags them.

### Runtime Role
Embedded in FeaturePipeline (updated on every batch run). Also importable standalone for live monitoring in engine code.

### Classes

#### FeatureMonitor

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Maintain rolling window of feature values, compute mean/std, detect drift. |
| **Ownership** | Created with configurable window size. Attached to FeaturePipeline or used standalone. |
| **Runtime Responsibility** | Update on every trade/row, check drift before accepting trades. |

### Methods

| Method | Key Behavior |
|--------|-------------|
| `update(features)` | Extracts retest_depth/body_ratio/disp_strength from dict (default 0.0 if missing). Appends to deque buffer (maxlen=window_size). Increments n_total. |
| `_compute_stats()` | Computes rolling mean/std from buffer. Returns None if < 30 samples. Replaces std=0.0 with 1.0. |
| `detect_drift(features, threshold=2.5)` | Returns True if ANY of 3 features has Z > threshold. Silently uses 0.0 for missing features. |
| `detect_drift_severity(features, soft=2.5, hard=3.0)` | Returns "none", "soft", or "hard" based on max Z-score of 3 features. |
| `stats()` | Returns mean, std, min, max for each feature plus sample counts. |
| `summary()` | JSON-formatted stats string. |
| `reset()` | Clears buffer, resets counters. |

### Hidden Defaults
- `features.get("retest_depth", 0.0)`, same for body_ratio and disp_strength — if the caller passes a dict missing these keys, the monitor silently records 0.0.
- Drift detection requires ≥ 30 samples before activating. Before that, both `detect_drift()` and `detect_drift_severity()` return False/"none" — **no warning that drift detection is inactive**.
- `_compute_stats()` replaces std=0.0 with 1.0 to avoid divide-by-zero. This means a degenerate buffer (all identical values) reports Z-scores as if std=1.0, which is completely wrong.

### Trust Classification: **LIVE** (used in backtest and live engine paths)

---

## 1.6 dataset_builder.py

### File Purpose
Build training datasets from feature dicts. Converts feature dicts to canonical vectors, creates labeled dataset entries, writes JSON files. Also handles the `rr_to_class()` 4-class label mapping for GaussianNB.

### Runtime Role
Called during training pipeline when building training datasets from fusion trade logs.

### Functions

| Function | Key Behavior |
|----------|-------------|
| `validate_features(features)` | UNUSED (line 65 commented out). Checks all FEATURE_SCHEMA keys present with correct types. |
| `extract_feature_vector(features)` | **Canonical vector builder.** Validates session/trend_bias/candle presence, builds list in CANONICAL_FEATURE_ORDER, asserts length, returns list. |
| `extract_bitnet_features(features)` | DEPRECATED. Delegates to extract_feature_vector. Emits DeprecationWarning. |
| `build_dataset_entry(features, label, meta)` | Calls extract_feature_vector, wraps in {features, label, meta} dict. |
| `build_dataset(records, output_path)` | Iterates records, builds entries, optionally writes JSON. |
| `compute_feature_hash(features)` | MD5 of sorted JSON vector. For dedup/integrity. |
| `rr_to_class(rr)` | Maps float RR to 4-class label: loss→0, small win→1, mid win→2, big win→3. |

### Trust Classification: **LIVE** (used in training pipeline)

---

## 1.7 dataset_validator.py

### File Purpose
Validates fusion trade logs (JSONL files with ENTRY/EXIT events) before dataset building. Pairs ENTRY and EXIT records by trade_id, validates feature vectors, produces a diagnostic report.

### Runtime Role
Called at start of training pipeline to filter and validate input data.

### Classes

#### ValidationReport (dataclass)
Collects counts and diagnostics: total_lines, entry_records, exit_records, paired_trades, valid_for_training, reject reasons.

### Functions

#### `validate_logs(*log_paths, verbose) -> (records, report)`
| Attribute | Detail |
|-----------|--------|
| **Human Purpose** | "Load JSONL fusion logs, pair each ENTRY with its corresponding EXIT by trade_id, validate feature vectors, and return only the valid paired records." |
| **Runtime Flow** | Pass 1: Load all lines, split by ENTRY/EXIT/REJECT event types. Index by trade_id. Pass 2: For each ENTRY, find matching EXIT. Skip if no exit, duplicate, all-zero features, or bad vector conversion. Build paired record with features + outcome. |
| **Hidden Defaults** | `MIN_RECORDS_TO_TRAIN = 200` from production config (falls back to 200). `MIN_RECORDS_RECOMMEND = 500` fallback. |
| **Failure Modes** | Silent skip on JSON parse errors (logged as warning). Silent skip on missing EXIT (logged in report counts). |

#### `validate_logs_multi_instrument(log_dir, pattern)` 
Convenience wrapper — globs *fusion.jsonl in log_dir.

### Trust Classification: **LIVE** (training pipeline)

---

## 1.8 schema_validator.py

### File Purpose
Strict fail-fast validators for the canonical feature contract. Three functions: key-set validation, value validation (NaN/None/inf), vector length validation.

### Runtime Role
Called by FeaturePipeline (validate_features), dataset_builder, and any code that needs to verify feature integrity.

### Functions

| Function | Behavior |
|----------|----------|
| `validate_features(features, schema)` | Checks feature_keys == schema_keys. Raises ValueError with missing/extra lists. |
| `validate_feature_values(features)` | Checks every value is not None, not NaN, not inf. Raises ValueError on violation. |
| `validate_vector(vector, schema)` | Checks vector is list and length matches schema. Raises AssertionError/TypeError. |

### Trust Classification: **CANONICAL**
Strict, fail-fast, no fallbacks. This is the enforcement layer for the canonical contract.

---

## 1.9 src/features/\_\_init\_\_.py

Empty file. Package marker only.

---

# 2. src/feedback

## 2.1 ai_feedback.py

### File Purpose
Generates offline LLM-based suggestions from trade analytics. Never applied automatically — human approval required. Falls back to rule-based feedback when LLM is unavailable.

### Runtime Role
Runs offline after sufficient trades (≥30) accumulate. Feeds suggestions to ExpansionEngine as a starting point. Not in the live execution path.

### Classes

#### AIFeedback

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Given analytics summary + loss clusters, produce insights and parameter suggestions either via LLM or rule-based fallback. |
| **Ownership** | Instantiated with an LLM callable (or None for rule-only). |
| **Runtime Responsibility** | Generate structured feedback dict. |

### Methods

| Method | Key Behavior |
|--------|-------------|
| `generate(summary, clusters, trade_count)` | Skips if trade_count < 30 → returns `{skipped: True, reason: "insufficient_trades"}`. If LLM available → formats prompt, calls LLM, parses JSON. If LLM fails or unavailable → falls back to rule-based. |
| `_rule_based_feedback(summary, clusters)` | Hardcoded rules: win_rate<0.40 → increase fusion_min_score. Negative expectancy → increase min_rr_ratio. Low zone → increase zone_gate_threshold. Low RR → increase min_rr_ratio. |

### Failure Modes
- LLM call exception → silently swallows, falls back to rule-based (WARNING level log).
- LLM returns non-JSON → json.loads() raises, caught by `except Exception`, falls back to rule-based.
- No LLM provided → _llm_fn is None → returns rule-based with log.info "no LLM available".

### Hidden Defaults
- `_MIN_TRADES = 30` hardcoded (overridable in __init__ via min_trades parameter).

### Trust Classification: **EXPERIMENTAL**
Not in live execution path. Rule-based fallback is deterministic and safe.

---

# 3. src/governance

## 3.1 orchestrator.py

### File Purpose
The full 4-step governance loop: Reflection → MetaGovernor → ShadowGate → Promotion. Orchestrates the entire governance lifecycle from reading trade logs to potentially overwriting the active production config.

### Runtime Role
CLI entry point for governance runs. Called manually via `python src/governance/orchestrator.py` with log paths. Also callable programmatically via GovernanceOrchestrator.run().

### Classes

#### GovernanceOrchestrator

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Execute the 4-step governance pipeline. |
| **Ownership** | Created with paths to active config, BitNet binary, model, audit log, prompt path. |
| **Runtime Responsibility** | Run Steps 1-4 and return {patch, promoted, reason}. |

### Methods

#### `run(collector_log, trades_csv, baseline_pnl, *, compressed_summary_path) -> dict`

**What ACTUALLY happens when this runs:**

```
Step 1+2 (ReflectionBuffer):
  - EITHER loads compressed_summary JSON (new path) 
  - OR loads collector.jsonl + trades CSV (legacy path)
  - Merges decisions with trade outcomes (by candle_idx)
  - Computes feature divergence between winning and losing trades
  - Writes meta_prompt.txt to disk
  - If insufficient win/loss data: returns {patch: None, promoted: False, reason}

Step 3 (MetaGovernorExecutor):
  - Reads meta_prompt.txt
  - Executes BitNet binary via subprocess:
      ./bitnet/bin/main -m model.gguf -p <prompt text> -n 256 --temp 0.1 -c 2048
  - Captures stdout
  - Regex-extracts first JSON object from output
  - Validates JSON has "fusion_min_score" key
  - Logs governance audit event to governance_audit.jsonl
  - If inference fails: logs INFERENCE_FAILED event, returns abort

Step 4 (ShadowPromotionGate):
  - Reads active production config
  - Merges patch into active config (overwrites fusion_min_score, decision_engine params)
  - Writes candidate.json
  - Executes shadow backtest via subprocess:
      python runtime/backtest_bitnet.py --config candidate.json --data <data_csv> --output <shadow_trades.csv>
  - Reads shadow_trades.csv, sums pnl_rr_net
  - Compares: if shadow_pnl > baseline_pnl AND n_trades >= min_shadow_trades:
      → COPIES candidate.json TO active config path (OVERWRITE!)
    Otherwise:
      → Deletes candidate.json
  - Logs PROMOTION_DECISION event
```

### Key Runtime Flows

**Success path:** The active production config is **overwritten** with the candidate config. The governance loop can self-modify production behavior.

**Fail paths:** 
- Reflection insufficient data → returns early with reason
- MetaGovernor output invalid (no JSON, missing fusion_min_score) → returns early, logs INFERENCE_FAILED
- Shadow backtest fails (exception) → returns with patch but promoted=False
- Performance gate fails → candidate deleted, no config change

### Side Effects
- **FILE WRITES:**
  - `logs/meta_prompt.txt` — prompt text
  - `configs/production/candidate.json` — staged patch
  - `logs/governance_audit.jsonl` — audit events appended
  - **`configs/production/v1_multi_2026_03.json`** — **OVERWRITTEN** on promotion
- **SUBPROCESS:**
  - BitNet inference binary execution
  - Backtest script execution
- **NETWORK:** None directly (BitNet binary may access files locally)

### Trust Classification: **LIVE** — CANONICAL for promotion path
Can modify production config. Must be treated as critical infrastructure.

---

## 3.2 bitnet_governance_executor.py

### File Purpose
Runs BitNet LLM inference for governance decisions. Takes a prompt file, executes the BitNet binary, extracts JSON config patch from output.

### Runtime Role
Step 3 of governance loop. Called by GovernanceOrchestrator.

### Classes

#### MetaGovernorExecutor

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Wrapper around BitNet inference binary for governance config generation. |
| **Ownership** | Created with binary path, model path, audit log path. |
| **Runtime Responsibility** | Run inference, extract config, log events. |

### Methods

| Method | Key Behavior |
|--------|-------------|
| `run_inference(prompt_path)` | Reads prompt text. Builds subprocess command: `[bitnet_bin, -m, model_path, -p, prompt, -n, 256, --temp, 0.1, -c, 2048]`. Executes, returns stdout. |
| `extract_and_validate_config(raw_output)` | Regex `r'\{.*\}'` with DOTALL to extract first JSON. Parses JSON. Checks "fusion_min_score" key. Returns config dict. |
| `log_governance_event(event_type, engine_id, metrics, decision, audit_log_path)` | Builds structured event dict with timestamp, type, engine_id, metrics, decision. Calls `os.fsync(f.fileno())` after write for durability. Writes to audit_log_path (default: logs/governance_audit.jsonl). |

### Hidden Defaults
- Token generation: `-n 256` (max 256 tokens output)
- Temperature: `--temp 0.1` (very low — near-deterministic)
- Context window: `-c 2048`
- Missing keys validation: only checks `"fusion_min_score"`. Does NOT check `"decision_engine"` sub-key.

### Failure Modes
- Regex `r'\{.*\}'` with DOTALL is greedy — matches from first `{` to LAST `}`. If output has multiple JSON objects, this concatenates them. json.loads will likely fail.
- Binary not found → subprocess raises FileNotFoundError, caught by caller.

### Subprocess
**YES** — executes BitNet binary every inference.

### Trust Classification: **LIVE** — DANGEROUS
Subprocess execution of external binary with unknown behavior. The governance loop trusts whatever the binary outputs as long as it contains valid JSON with `fusion_min_score`.

---

## 3.3 reflection_buffer_advanced.py

### File Purpose
Loads collector decisions + trade outcomes, computes feature divergence between winning and losing trades, and generates the governance prompt for MetaGovernor.

### Runtime Role
Steps 1-2 of governance loop. Called by GovernanceOrchestrator.

### Classes

#### ReflectionBuffer

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Load and merge decision logs with outcomes, compute win/loss feature divergence, generate prompt. |
| **Ownership** | Created per-run with log paths. |
| **Runtime Responsibility** | Provide merged DataFrame and prompt text. |

### Methods

| Method | Key Behavior |
|--------|-------------|
| `load_and_merge()` | If compressed_summary set → returns empty DataFrame. Otherwise: loads collector.jsonl (each line = decision with candle_idx, decision, final_score, features), loads trades CSV, merges on candle_idx (left join). Drops rows with missing candle_idx. |
| `generate_prompt_payload(df, output_path)` | If compressed_summary set → calls `_prompt_from_compressed_summary()`. Otherwise: filters ACCEPT decisions with pnl_rr_net available. Splits into wins (pnl_rr_net > 0) and losses. Computes mean of CANONICAL_FEATURES for each group. Computes absolute divergence. Takes top 3 features. Writes prompt to disk (logs/meta_prompt.txt). Returns None if < 1 win or < 1 loss row. |
| `_prompt_from_compressed_summary(output_path)` | Builds prompt from pre-computed summary dict (correlations, RR stats, anomalies). Skips raw log parsing. |

### Runtime Flow for generate_prompt_payload()
```
1. df = merged decisions + trades (from load_and_merge)
2. Filter: decision == 'ACCEPT', pnl_rr_net not NaN
3. Split: true_accepts (pnl_rr_net > 0), false_accepts (pnl_rr_net <= 0)
4. If either group empty → return None (insufficient data)
5. Compute mean of ALL CANONICAL_FEATURES for each group
6. Compute abs(fa_mean - ta_mean) for each feature
7. Sort descending, take top 3 features and their signed differences
8. Format prompt asking MetaGovernor to adjust fusion_min_score and weak_component_threshold
9. Write prompt to meta_prompt.txt
10. Return prompt string
```

### Hidden Defaults
- When compressed_summary is set, `load_and_merge()` returns EMPTY DataFrame. If any caller uses this DF for something other than `generate_prompt_payload()`, they get zero rows. Column access will raise KeyError.
- Merge is LEFT JOIN: decisions without matching trades get NaN for pnl_rr_net and exit_reason. These are dropped by `dropna(subset=['pnl_rr_net'])` later.
- Uses ALL CANONICAL_FEATURES (38 features) for divergence computation. This is expensive and includes irrelevant features.

### Trust Classification: **LIVE** (governance pipeline)

---

## 3.4 shadow_promotion_gate.py

### File Purpose
Stages a candidate config, runs a shadow backtest, and promotes if superior. This is the gatekeeper between experimental configs and production.

### Runtime Role
Step 4 of governance loop. Called by GovernanceOrchestrator.

### Classes

#### ShadowPromotionGate

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Test a candidate config via shadow backtest, promote only if it outperforms baseline. |
| **Ownership** | Created per-governance-run with active config path and governance config. |
| **Runtime Responsibility** | Stage config, run backtest, evaluate promotion. |

### Methods

| Method | Key Behavior |
|--------|-------------|
| `stage_candidate(patch)` | Reads active config JSON. Merges patch: `fusion_min_score` overwritten at top level, `decision_engine` sub-keys merged via `.update()`. Writes to candidate.json. |
| `execute_shadow_test()` | Runs subprocess: `python runtime/backtest_bitnet.py --config candidate.json --data <data_csv> --output shadow_trades.csv`. Reads CSV, sums pnl_rr_net, returns (total_pnl, n_trades). Raises FileNotFoundError if CSV not produced. |
| `promote_if_superior(baseline_pnl, shadow_pnl, n_shadow_trades)` | Gate 1: n_trades >= min_shadow_trades (default 30). Gate 2: shadow_pnl > baseline_pnl. If both pass: COPIES candidate.json OVER active config, deletes candidate.json. If either fails: deletes candidate.json. |

### Runtime Flow for promotion
```
1. Check n_shadow_trades >= min_shadow_trades (default 30)
   → FAIL: delete candidate.json, return {promoted: False, reason}
2. Check shadow_pnl > baseline_pnl
   → FAIL: delete candidate.json, return {promoted: False, reason}
3. PASS: shutil.copy(candidate.json → active_config.json) ← OVERWRITE
        os.unlink(candidate.json)
        return {promoted: True, reason}
```

### Hidden Defaults
- `min_shadow_trades` default: 30 (hardcoded fallback if neither governance_config nor config file supplies it)
- `data_csv` default: `data/AUDUSD_M15.csv`
- `output_csv` default: `results/shadow_trades.csv`
- `backtest_script` default: `runtime/backtest_bitnet.py`
- Governance config loaded from `active_config.json["governance"]`. If missing, all defaults apply silently.

### Side Effects
- **OVERWRITES production config on promotion** (`shutil.copy`)
- **Deletes candidate.json** (whether promoted or not)
- Subprocess execution of backtest script

### Trust Classification: **LIVE** — **DANGEROUS**
This class has the authority to overwrite the production configuration file. The promotion gate depends entirely on the shadow backtest's pnl_rr_net calculation.

---

## 3.5 promotion_manager.py

### File Purpose
Manages the promotion gate between validated configs and the production registry. Moves approved JSON files, builds registry entries with SHA-256 hashes, and maintains a promotion audit log.

### Runtime Role
Called by CLI or programmatically when promoting a config from validation to production. NOT called by GovernanceOrchestrator directly — this is a separate path for tuner-based promotion.

### Classes

#### PromotionManager (all static methods)

| Method | Key Behavior |
|--------|-------------|
| `promote_from_report(report_path, version, csv_paths, notes)` | Loads validation report, checks decision=="APPROVE", re-runs ConfigValidator to verify report is current, executes promotion. |
| `promote_from_tuner_checkpoint(checkpoint_path, version, csv_paths, notes, use_llm, top_n)` | Full workflow: load tuner checkpoint → validate top config(s) via ConfigValidator → promote first approved. |
| `promote_direct(params, version, notes)` | **BYPASSES validation** — direct write to registry with warning. For manually verified configs. |
| `list_versions(registry_dir)` | Lists all JSON files in production registry (excludes promotion_log files). |
| `load_version(version, registry_dir)` | Loads registry entry and **validates SHA-256 config_hash** against params dict. Raises RuntimeError on mismatch (tamper detection). |
| `_execute_promotion(report, version, notes)` | Core promotion logic: builds registry entry with validation summary (including score_std_dev for cross-instrument stability), writes to registry. |
| `_write_to_registry(entry, version)` | Merges promotion metadata into full base config (to preserve engine sections), archives old version, writes new version, updates ACTIVE_VERSION pointer file. |
| `_compute_config_hash(params)` | SHA-256 of canonical JSON (sort_keys=True). |
| `_build_registry_entry(params, version, validation_summary, notes, config_id)` | Builds the JSON structure stored in production_configs/{version}.json. |
| `_load_full_base_config(registry_dir)` | Searches for full config with `engine_runner` sentinel. Uses v1_multi_2026_03.json as preferred base. Falls back to scanning registry for any full config. |
| `_fail(reason)` | Logs PROMOTION_FAILED event. |
| `_log_event(event)` | Appends structured event to promotion_log.jsonl. |

### File Writes
- **configs/production/{version}.json** — promoted config (with all engine sections merged in)
- **configs/production/ACTIVE_VERSION** — plain text file containing version string
- **configs/promotion_log.jsonl** — append-only audit log
- **Archive**: old version gets copied to `{version}_archived_{timestamp}.json`

### Trust Classification: **LIVE** — **DANGEROUS**
Directly writes to the production registry. The merge strategy protects against sparse configs but the promotion decision itself is based on ConfigValidator output.

---

## 3.6 expansion_integration.py

### File Purpose
Bridge between ExpansionEngine (which generates SAFE/BALANCED/AGGRESSIVE config tiers) and ShadowPromotionGate (which can promote to production). Runs forward tests, applies viability filters, hard assertions, and stages candidates.

### Runtime Role
Called when ExpansionEngine has produced new config tiers and they need governance validation before potential promotion.

### Classes

#### ViabilityFilter
| Method | Behavior |
|--------|----------|
| `passes(metrics)` | Checks: pnl > 0, drawdown < 0.25, trades >= 30. Returns (bool, reason). |
| `filter_viable(forward_results)` | Applies passes() to all results, returns viable list. |

#### ExpansionGovernanceBridge
| Method | Key Behavior |
|--------|-------------|
| `run(base_config, expansion_plan, train_csv, forward_csv)` | 1. Runs ExpansionEngine on train_csv. 2. Forward-tests each tier on forward_csv using BacktestRunner. 3. Applies ViabilityFilter. 4. Hard assertions: forward_pnl > baseline_pnl; forward_drawdown <= baseline_dd * 1.2. 5. Stages viable via ShadowPromotionGate. 6. Logs all to expansion_history.jsonl. |
| `_forward_test_configs(configs, forward_csv, BacktestRunner)` | For each tier, runs BacktestRunner, extracts metrics. On exception, returns zeroed metrics with rejection reason. |
| `_diff_from_base(new_config, base_config)` | Computes minimal diff of changed keys. |
| `_stage_candidate(patch, metrics, baseline_pnl, n_trades)` | Calls ShadowPromotionGate.promote_if_superior(). On exception, returns failed gate_result. |

### File Writes
- **logs/expansion_history.jsonl** — all staged/rejected entries appended

### Failure Modes
- ExpansionEngine not importable → ExpansionGovernanceBridge.__init__ sets ExpansionEngine = None, but run() will fail with import error.
- Backtest fails per-tier → exception caught, zero metrics returned, rejected.

### Trust Classification: **EXPERIMENTAL**
Not in the main governance loop (orchestrator.py). Separate automation path.

---

## 3.7 multi_strategy_validator.py

### File Purpose
Governance validation for the 10-strategy system. Runs StrategyBacktester across instruments, applies hard and soft quality gates, produces ValidationReport for PromotionManager.

### Runtime Role
Called before promoting a multi-strategy config to production.

### Classes

#### MultiStrategyValidator

| Method | Key Behavior |
|--------|-------------|
| `validate(csv_paths, config_id)` | Runs StrategyBacktester per instrument. Collects per-strategy metrics across all instruments. Applies hard gates: min 5 trades/strategy, portfolio win rate >= 30%, max drawdown <= 75M INR. Applies soft warnings: low win rate, profit factor < 1.0, high timeout rate. Computes composite score. Returns ValidationReport. |

### Trust Classification: **PARTIAL** (10-strategy system, separate from CRT)

---

## 3.8 portfolio_validation.py

### File Purpose
Multi-market universality test. Runs the CRT engine across 8 instruments with an identical config (no per-instrument tuning). Tests whether CRT + Gaussian is a pattern or a law of markets.

### Runtime Role
Standalone script run by user, not part of the normal governance pipeline. Generates portfolio validation report.

### Classes

#### PortfolioAnalytics
| Method | Key Behavior |
|--------|-------------|
| `aggregate()` | Computes global metrics: win rate, avg RR, expectancy, profit factor, Sharpe, max drawdown, avg duration. |
| `instrument_breakdown()` | Per-instrument stats: trades, win rate, pnl, avg RR, scored trades. |
| `score_distribution()` | Win rate by Gaussian score bucket [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]. |
| `gaussian_correlation()` | Pearson correlation: gaussian_score vs binary win/loss. |
| `score_outcome_rr_correlation()` | Pearson correlation: gaussian_score vs continuous RR. |
| `universality_verdict()` | Applies Jarvis interpretation: positive EV across ≥2 instruments → Universal candidate. Gaussian corr > 0.15 → Predictive score. |

### File Writes
- `results/portfolio/portfolio_report.json`
- Per-instrument trade CSVs in results/portfolio/

### Monkey Patch
`_patch_runner_for_journal_access()` replaces `BacktestRunner.run()` to store closed trades after completion. Zero business logic change.

### Trust Classification: **EXPERIMENTAL**
Standalone research script, not part of governance/production path.

---

## 3.9 strategy_backtest.py

### File Purpose
Per-strategy historical performance measurement for the 10-strategy system. Loads CSV, runs FeaturePipeline, simulates strategies candle-by-candle with forward-scan for SL/TP hits.

### Runtime Role
Called by MultiStrategyValidator during governance validation.

### Classes

#### StrategyMetrics (dataclass)
Per-strategy backtest result: trade count, wins/losses, PnL (INR), drawdown, win rate, profit factor, composite score.

#### StrategyBacktester

| Method | Key Behavior |
|--------|-------------|
| `run(csv_path)` | 1. Loads CSV. 2. Runs FeaturePipeline to get enriched DataFrame. 3. Instantiates all registered strategy classes from `_STRATEGY_CLASSES`. 4. Iterates candles from warmup to n-max_fwd. 5. For each candle, builds canonical feature dict + strategy extras. 6. Calls `strategy.compute(feat, candle)`. 7. If actionable: forward-scans up to `max_forward_candles` bars for SL/TP hit. 8. Accumulates metrics per strategy. 9. Finalises (computes win rate, PF, score). |

### Trust Classification: **LIVE** (used by governance validation)

---

# 4. src/inout

## 4.1 hummingbot_candle_fetcher.py

### File Purpose
Fetches historical OHLCV candles from any hummingbot-supported exchange (Binance, Bybit, OKX, etc.) and writes CSV files compatible with Tradelatest's CandleLoader.

### Runtime Role
Standalone data ingestion tool. Not part of live execution or backtesting — used to acquire market data.

### Classes

#### HummingbotFetcherConfig (dataclass)
Config value object: exchange, trading_pair, interval, dates, output_dir, instruments list, max_records_per_request.

#### HummingbotCandleFetcher

| Method | Key Behavior |
|--------|-------------|
| `fetch(instrument)` | Synchronous wrapper: calls `asyncio.run(fetch_async())`. |
| `fetch_async(instrument)` | Creates CandlesConfig, gets candle connector via CandlesFactory, creates HistoricalCandlesConfig, calls `get_historical_candles()`. Writes CSV with datetime, timestamp, OHLCV columns. |
| `fetch_all_instruments()` | Iterates config.instruments list, calls fetch() for each. Collects paths, logs errors per instrument. |

### Network/API
**YES** — uses hummingbot's exchange connectors to fetch live market data.

### Bybit Compatibility Patch (lines 50-107)
Monkey-patches BybitSpotCandles and BybitPerpetualCandles `_get_rest_candles_params` methods. Bybit v5 API requires `start`/`end` parameters but hummingbot sends `startTime`/`endTime`. Without this patch, Bybit date filtering silently returns recent candles instead of requested range.

### Trust Classification: **LIVE** (data ingestion)
Used to generate input data for backtesting and training.

---

## 4.2 alphavantage_candle_fetcher.py

### File Purpose
Fetches historical FX OHLCV candles from Alpha Vantage's FX_INTRADAY endpoint. Writes Tradelatest-compatible CSV.

### Runtime Role
Same as hummingbot fetcher — standalone data ingestion. Used specifically for forex pairs where hummingbot's Kraken connector has limited historical depth.

### Classes

#### AlphaVantageFetcherConfig (dataclass)
Config: api_key, from_symbol, to_symbol, interval, dates, output_dir, request_delay (default 1.2s for rate limiting).

#### AlphaVantageCandleFetcher

| Method | Key Behavior |
|--------|-------------|
| `fetch()` | Generates list of (year, month) tuples in range. For each month: calls `_fetch_month()` with 1.2s delay between calls. Filters to [start_date, end_date). Sorts by timestamp. Writes CSV. |
| `_fetch_month(year, month)` | Builds URL: `https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=...&interval=...&month=YYYY-MM&apikey=...` | 
| `_months_in_range()` | Generates month tuples for date range. |

### Network/API
**YES** — HTTP requests to alphavantage.co REST API.

### Failure Modes
- API returns "Error Message" → raises RuntimeError
- "Information" key → raises RuntimeError (rate limit or info)
- "Note" key → raises RuntimeError (rate limit note)
- Missing time series key → raises RuntimeError with expected key name
- Network errors → raises RuntimeError
- Empty results → raises RuntimeError

### Trust Classification: **LIVE** (data ingestion)

---

# 5. CROSS-CUTTING ANALYSIS

## 5.1 Fail-Fast / Fallback Audit

### Silent Fallbacks

| File | Line(s) | Fallback | Impact |
|------|---------|----------|--------|
| crt_feature_builder.py | 39-43 | `candle.get("open", 0.0)` — all OHLCV default to 0.0 | Silently corrupts feature vector with zero values when candle data incomplete |
| crt_feature_builder.py | 48-124 | `state.get("feature", 0.0)` — all state features default to 0.0 | Same as above: missing state produces zero vector_
| crt_feature_builder.py | 117 | `SESSION_MAP.get(session, 0.0)` — unknown session defaults to 0.0 (London) | Unknown sessions silently treated as London session |
| feature_monitor.py | 88-92 | `features.get("retest_depth", 0.0)` — missing features default to 0.0 | Drift detection silently operates on zeros |
| feature_monitor.py | 104-106 | `_compute_stats()` returns None when < 30 samples | drift_detect() returns False with no warning that detection is inactive |
| feature_monitor.py | 119 | `std = [1.0 for v in var]` — zero-variance replaced by 1.0 | Degenerate buffers report incorrect Z-scores |
| feature_schema.py | 248-250 | `check_compatibility()` returns True for unregistered models | Schema drift goes undetected for models not registered |
| feature_pipeline.py | 168 | `self.df["volume"] = 0.0` if volume column absent | Forex safe fallback |
| feature_pipeline.py | 219, 226 | volume_ratio defaults to 1.0 when rolling MA is 0 | Arbitrary default when no volume history |
| bitnet_governance_executor.py | 35 | Regex `r'\{.*\}'` with DOTALL (greedy) | Misses last `}` if multiple JSON objects, or returns corrupted JSON |
| shadow_promotion_gate.py | 80-84 | Defaults for min_shadow_trades, data_csv, output_csv from hardcoded values | Different instruments may have different optimal requirements |

### Hidden Defaults

| File | Default | Location |
|------|---------|----------|
| feature_pipeline.py | `SWING_WINDOW = 2` | Line 57 — ±2 candles for swing detection |
| feature_pipeline.py | `NORMALIZE_COLS` = 5 columns | Lines 61-67 — rolling z-score on price_vs_ma20/50, bb_width, macd_hist, trend_strength |
| feature_pipeline.py | `_RETEST_LOOKBACK = 10` | Line 497 — 10-bar window for retest detection |
| feature_pipeline.py | `_ADAPTIVE_WINDOW = 50`, `_MIN_SAMPLES = 20`, `_PERCENTILE = 75` | Lines 633-636 — adaptive volume spike parameters |
| feature_monitor.py | `_MIN_SAMPLES_FOR_DRIFT = 30`, `DEFAULT_DRIFT_THRESHOLD = 2.5` | Lines 57, 60 |
| dataset_validator.py | `MIN_RECORDS_TO_TRAIN = 200`, `MIN_RECORDS_RECOMMEND = 500` | Lines 46-47 |
| reflection_buffer_advanced.py | `top_features = divergence.head(3)` | Line 82 — uses top 3 divergent features for prompt |
| bitnet_governance_executor.py | `-n 256`, `--temp 0.1`, `-c 2048` | Lines 26-28 — token count, temperature, context |
| shadow_promotion_gate.py | `_DEFAULT_MIN_SHADOW_TRADES = 30` | Line 49 |

### Swallowed Exceptions

| File | Line(s) | Exception | Handler |
|------|---------|-----------|---------|
| ai_feedback.py | 99-101 | Any exception in LLM call | `log.warning` → falls back to rule-based |
| shadow_promotion_gate.py | 104-109 | Any exception loading governance config | `log.warning` → returns empty dict, uses defaults |
| expansion_integration.py | 263-274 | Any BacktestRunner exception | `log.warning` → returns zero metrics |
| expansion_integration.py | 308-309 | Any ShadowPromotionGate exception | `log.warning` → returns failed gate_result |
| hummingbot_candle_fetcher.py | 125-126 | All hummingbot import errors | `pass` — silently marks not available |
| hummingbot_candle_fetcher.py | 69-70 | All Bybit patch errors | `log.debug` — silently skips patch |

## 5.2 Trust Classification Summary

| File | Classification | Reason |
|------|---------------|--------|
| **feature_schema.py** | **CANONICAL** | Central data contract. All consumers depend on it. |
| **crt_feature_builder.py** | **LIVE** — **DANGEROUS** | Used in real-time inference. Silently defaults missing data to 0.0. |
| **feature_builder.py** | **CANONICAL** | Clean fail-fast validation. |
| **feature_pipeline.py** | **CANONICAL** | Reference batch pipeline for all backtesting/training. |
| **feature_monitor.py** | **LIVE** | Runs in backtest and potentially live paths. |
| **dataset_builder.py** | **LIVE** | Training pipeline component. |
| **dataset_validator.py** | **LIVE** | Training pipeline component. |
| **schema_validator.py** | **CANONICAL** | Enforcement layer for canonical contract. |
| **ai_feedback.py** | **EXPERIMENTAL** | Offline only. Not in live path. |
| **orchestrator.py** | **LIVE** — **DANGEROUS** | Can overwrite production config. |
| **bitnet_governance_executor.py** | **LIVE** — **DANGEROUS** | Subprocess execution of external binary. |
| **reflection_buffer_advanced.py** | **LIVE** | Governance pipeline component. |
| **shadow_promotion_gate.py** | **LIVE** — **DANGEROUS** | Overwrites production config on promotion. |
| **promotion_manager.py** | **LIVE** — **DANGEROUS** | Writes to production registry. |
| **expansion_integration.py** | **EXPERIMENTAL** | Separate automation path. |
| **multi_strategy_validator.py** | **PARTIAL** | 10-strategy system, separate from CRT. |
| **portfolio_validation.py** | **EXPERIMENTAL** | Standalone research script. |
| **strategy_backtest.py** | **LIVE** | Used by governance validation. |
| **hummingbot_candle_fetcher.py** | **LIVE** | Data ingestion. |
| **alphavantage_candle_fetcher.py** | **LIVE** | Data ingestion. |

## 5.3 Corruption / Contamination Risks

### Replay/Live Drift
- **feature_pipeline.py** `center=True` rolling windows (line 341-342) introduce lookahead in swing detection. This is documented as acceptable for backtesting but wrong for live inference. If a live pipeline uses the same FeaturePipeline class, it will have lookahead.
- **crt_feature_builder.py** produces vectors with 0.0 defaults for missing data. If upstream data quality degrades, models silently score degenerate vectors.

### Governance Contamination
- **GovernanceOrchestrator** can overwrite `configs/production/v1_multi_2026_03.json` via `shutil.copy()`. If the shadow backtest produces a flawed config (e.g., overfit to a specific data window), the production system inherits those flaws until manually reverted.
- **MetaGovernorExecutor** trusts the BitNet binary's stdout. If the binary returns malformed JSON that happens to parse and contain `fusion_min_score`, the patch is accepted.
- **ReflectionBuffer** uses ALL 38 canonical features for divergence computation. If features have different scales, the top-3 divergence may be dominated by scaling artifacts rather than genuine predictive differences.

### Data Integrity
- **dataset_builder.py** `extract_feature_vector()` uses `float(features["session"])` (line 79) — expects session already encoded as float. The commented-out `validate_features()` call (line 65) means no type checking happens before float conversion.
- **StrategyBacktester** `_row_to_features()` maps int-encoded session values using a hardcoded map `{0: "asia", 1: "london", 2: "new_york", 3: "overlap"}` (line 268). If the FeaturePipeline session encoding changes, this hardcoded map desyncs.