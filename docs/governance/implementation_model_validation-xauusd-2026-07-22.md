# Implementation Model Validation — XAUUSD (Frozen Corpus)

> **Authoritative milestone freeze:** [`IMPLEMENTATION_VALIDATION_V1.md`](IMPLEMENTATION_VALIDATION_V1.md)  
> JSON: `results/implementation_validation/IMPLEMENTATION_VALIDATION_V1.json` · **FAIL_OPEN = 0**

**Date:** 20260722T165028Z  
**ACTIVE_VERSION:** `v2_multi_2026_04`  
**Corpus:** `data/mt5/XAUUSD_M15.csv` pin_match=True  
**Rows scored:** 47197 (schema **v4.0** dim=39)

> Scope: implementation correctness only. No profitability, no threshold optimisation, no promotion.

## 1. Execution Matrix

### Failure-mode taxonomy

| Status | Meaning | Action |
|---|---|---|
| PASS | Executed correctly | No action |
| FAIL_CLOSED | Correctly refused invalid contract | Fix schema/registry |
| FAIL_OPEN | Executed with invalid assumptions | **Critical** |
| DEGRADED | Executes with reduced information | Investigate |
| DISABLED | Configuration choice | None |
| ORPHAN | Outputs with no consumer | Architecture review |
| GOVERNANCE_INCOMPLETE | Runtime works; selection/registry incomplete | Complete registry |

| Model | Loaded | Executed | Features OK | Outputs Healthy | Failure Mode | Consumer | Raw Status |
|---|---|---|---|---|---|---|---|
| CRT | True | True | True | True | **`PASS`** | spine_primary (deterministic state machine → TRADE | `OK` |
| Gaussian_heuristic_live | True | True | True | True | **`DEGRADED`** | fusion slot 'gaussian' (EngineRunner; gaussian_imp | `OK` |
| Gaussian_trained_NB | True | True | True | True | **`ORPHAN`** | NOT on live spine when gaussian_impl=heuristic (or | `EXECUTED_ORPHAN` |
| ZoneGate | True | True | True | True | **`PASS`** | fusion slot 'zone_gate' + hard gate (zone_mode=har | `OK` |
| RR_polarity_engine | True | True | True | True | **`PASS`** | fusion slot 'rr' ALWAYS (base RREngine); DecisionE | `OK` |
| RR_Fusion | False | False | False | False | **`FAIL_CLOSED`** | DISABLED on active config (engine_runner.rr_fusion | `LOAD_FAIL` |
| TradeNet | True | True | False | True | **`ORPHAN`** | ORPHAN — fusion neural slot unwired (F-005); Trade | `EXECUTED_ORPHAN` |
| BitNet | True | True | True | True | **`DISABLED`** | CRT hard-reject gate WHEN use_bitnet=true (score<0 | `EXECUTED_DISABLED_ON_SPINE` |

## 2. Bug Report (severity-ranked)

### 1. [Critical] `GAUSSIAN_DEFAULT_MU_SIGMA` — Gaussian_heuristic_live

Live gaussian uses unparameterized defaults mu=0,sigma=1; trained checkpoint parameters never reach score

```json
{
  "mu": 0.0,
  "sigma": 1.0,
  "version": null
}
```

### 2. [Critical] `RR_FUSION_DIM_LOAD_REFUSED` — RR_Fusion

FeatureDimensionError: rr model n_features=38 != CANONICAL_FEATURE_DIM=39. Remap or retrain before enabling rr_fusion — refusing load (fail-closed; no silent truncate).

```json
{
  "fail_closed": true,
  "enabled_on_spine": false
}
```

### 3. [High] `GAUSSIAN_NEAR_CONSTANT` — Gaussian_heuristic_live

Heuristic gaussian outputs near-constant / low-variance (F-060 class)

```json
{
  "n": 47197,
  "mean": 0.882686984342225,
  "std": 0.004935733547731605,
  "min": 0.8789,
  "max": 1.0,
  "p01": 0.8815,
  "p50": 0.8825,
  "p99": 0.8835,
  "n_nan_or_inf": 0,
  "n_unique": 71,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0017585863508273831,
  "frac_le_0_01": 0.0
}
```

### 4. [High] `GAUSSIAN_NO_XAUUSD_REGISTRY` — Gaussian_heuristic_live

No active Gaussian registry entry for XAUUSD; heuristic falls back to mu=0,sigma=1 defaults

Evidence: `GaussianRegistry: no active version for instrument 'XAUUSD' in models\gaussian_registry.json`

### 5. [High] `RR_NAME_SEMANTIC_MISMATCH` — RR_polarity_engine

RREngine emits candle polarity ∈[0.5,1], not forward RR; DecisionEngine threshold 1.5 → structural low_rr (F-048)

```json
{
  "score_range": [
    0.5,
    1.0
  ],
  "decision_threshold": 1.5
}
```

### 6. [High] `TRADENET_META_LOAD_FAILED` — TradeNet

TradeNetMetaEngine preload failed — compute will return neutral fallback

```json
{
  "registry_active": {
    "v5_auto_2026_06_eth": {
      "version": "v5_auto_2026_06_eth",
      "model_file": "models\\ETHUSDT\\20260519_113806\\tradenet_v5_auto_2026_06_eth.pth",
      "metrics": {
        "accuracy": 0.625,
        "composite_score": 0.4575,
        "n_train": 71255,
        "n_test": 30539
      },
      "trained_at": "2026-05-19T07:54:18Z",
      "active": true,
      "instrument": "ETHUSDT",
      "run_id": "20260519_113806"
    }
  },
  "version": "v5_auto_2026_06_eth",
  "model_file": "models/ETHUSDT/20260519_113806/tradenet_v5_auto_2026_06_eth.pth",
  "exists": true,
  "sha256": "7d4a778a1b14d84ab741341234237cf53429e25c9d7b54f9d910622476c27972",
  "scaler_path": "models/ETHUSDT/20260519_113806/tradenet_v5_auto_2026_06_eth_scaler.json",
  "scaler_exists": true,
  "loader": "TradeNetV2",
  "n_features": 35,
  "meta_engine_loaded": false,
  "meta_version": null,
  "meta_n_features": null
}
```

### 7. [High] `TRADENET_SCHEMA_DIM_MISMATCH` — TradeNet

Selected TradeNet trained at dim=35; runtime schema is v4 dim=39 with renames — index slice is unsafe

```json
{
  "selection_feature_schema_dim": 35,
  "runtime_dim": 39,
  "runtime_hash": "0edda573414f0a64",
  "note": "TradeNetV2 slices/truncates by index; v4 39-dim \u2192 silent index misalignment risk"
}
```

### 8. [Medium] `RR_REGISTRY_PATH_DRIFT` — RR_Fusion

Registry active '202605_bnb_v2_bnbusdt' model_file=models/rr_model_202605_bnb_v2.json but engine_runner.rr_fusion.model_path=models/rr_model.json

```json
{
  "registry_file": "models/rr_model_202605_bnb_v2.json",
  "config_file": "models/rr_model.json"
}
```

### 9. [Low] `BITNET_DUAL_SCHEMA` — BitNet

INTENTIONAL dual-schema fork: composition_default=legacy_6input; HOW pin=export 35-dim. Documented in bitnet_registry governance — not unified until a single serve contract is chosen.

```json
{
  "legacy_dim": 6,
  "export_dim": 35
}
```

### 10. [Low] `GAUSSIAN_NAME_ANCHORED_OK` — Gaussian_trained_NB

Trained Gaussian p5_20260524T120449 loads via name-anchored subset (alignment=named_subset, n=38); not ambient-vector truncate.

```json
{
  "resolved_dim": 38,
  "live_dim": 39
}
```

### 11. [Low] `GAUSSIAN_NAME_ANCHORED_OK` — Gaussian_trained_NB

Trained Gaussian v5_auto_2026_06_eth loads via name-anchored subset (alignment=named_subset, n=35); not ambient-vector truncate.

```json
{
  "resolved_dim": 35,
  "live_dim": 39
}
```

## 3. Misalignment Report

### CRT

Feature alignment noted (see detail)

```json
{
  "note": "CRT consumes OHLCV + ATR/EMA via internal SM; not the 39-dim vector",
  "features_ok": true
}
```

### Gaussian_heuristic_live

Feature alignment noted (see detail)

```json
{
  "expected_dim": 3,
  "received_dim": 39,
  "expected": [
    "ema_fast",
    "ema_slow",
    "momentum_score"
  ],
  "received": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "missing": [],
  "extra": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "order_match_exact": false,
  "name_set_match": false,
  "alias_remapped_expected": [
    "ema_fast",
    "ema_slow",
    "momentum_score"
  ],
  "alias_remapped_missing": [],
  "alias_alignment_ok": true,
  "actual_consumed": [
    "ema_fast",
    "ema_slow",
    "momentum_score"
  ],
  "trained_checkpoint_features_used": false
}
```

### Gaussian_trained_NB

Feature alignment noted (see detail)

```json
{
  "p5_20260524T120449": {
    "expected_dim": 38,
    "received_dim": 39,
    "expected": [
      "open",
      "high",
      "low",
      "close",
      "volume",
      "volume_ratio",
      "double_sweep",
      "ema_fast",
      "ema_slow",
      "ema_spread",
      "trend_bias",
      "trend_strength",
      "momentum_score",
      "atr",
      "volatility_ratio",
      "rsi_14",
      "macd_line",
      "macd_signal",
      "macd_hist",
      "sweep_detected",
      "liquidity_sweep",
      "break_of_structure",
      "swing_high",
      "swing_low",
      "higher_high",
      "lower_low",
      "body_size",
      "wick_size",
      "body_ratio",
      "volatility_regime",
      "session",
      "hour_of_day",
      "disp_strength",
      "retest_depth",
      "candles_since_retest",
      "liquidity_distance",
      "liquidity_pressure_score",
      "volume_spike"
    ],
    "received": [
      "open",
      "high",
      "low",
      "close",
      "volume",
      "volume_ratio",
      "double_sweep",
      "ema_fast",
      "ema_slow",
      "ema_spread",
      "trend_bias",
      "trend_strength",
      "momentum_score",
      "atr",
      "volatility_ratio",
      "rsi_14",
      "macd_line",
      "macd_signal",
      "macd_hist_raw",
      "macd_hist_z",
      "sweep_detected",
      "liquidity_sweep",
      "break_of_structure",
      "swing_high",
      "swing_low",
      "higher_high",
      "lower_low",
      "body_size",
      "candle_range",
      "body_ratio",
      "volatility_regime",
      "session",
      "hour_of_day",
      "disp_strength",
      "retest_depth",
      "candles_since_retest",
      "liquidity_distance",
      "liquidity_pressure_score",
      "volume_spike"
    ],
    "missing": [
      "macd_hist",
      "wick_size"
    ],
    "extra": [
      "macd_hist_raw",
      "macd_hist_z",
      "candle_range"
    ],
    "order_match_exact": false,
    "name_set_match": false,
    "alias_remapped_expected": [
      "open",
      "high",
      "low",
      "close",
      "volume",
      "volume_ratio",
      "double_sweep",
      "ema_fast",
      "ema_slow",
      "ema_spread",
      "trend_bias",
      "trend_strength",
      "momentum_score",
      "atr",
      "volatility_ratio",
      "rsi_14",
      "macd_line",
      "macd_signal",
      "macd_hist_z",
      "sweep_detected",
      "liquidity_sweep",
      "break_of_structure",
      "swing_high",
      "swing_low",
      "higher_high",
      "lower_low",
      "bod
```

### ZoneGate

Feature alignment noted (see detail)

```json
{
  "expected_trained_order": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "received_live_order": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "trained_dim": 38,
  "live_dim": 39,
  "missing_from_live": [],
  "live_names_not_scored": [
    "macd_hist_raw"
  ],
  "renames_applied": {
    "wick_size": "candle_range",
    "macd_hist": "macd_hist_z"
  },
  "name_set_subset_ok": true,
  "has_macd_hist_z": true,
  "has_candle_range": true,
  "no_v3_names": true
}
```

### RR_polarity_engine

Feature alignment noted (see detail)

```json
{
  "expected_dim": 4,
  "received_dim": 39,
  "expected": [
    "open",
    "high",
    "low",
    "close"
  ],
  "received": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "missing": [],
  "extra": [
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "candle_range",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "order_match_exact": false,
  "name_set_match": false,
  "alias_remapped_expected": [
    "open",
    "high",
    "low",
    "close"
  ],
  "alias_remapped_missing": [],
  "alias_alignment_ok": true
}
```

### RR_Fusion

Feature alignment FAILED

```json
{
  "model_declared_schema": "canonical_38",
  "model_n_features": 38,
  "runtime_dim": 39,
  "runtime_feature_order_hash": "0edda573414f0a64",
  "v3_approx_order": [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast",
    "ema_slow",
    "ema_spread",
    "trend_bias",
    "trend_strength",
    "momentum_score",
    "atr",
    "volatility_ratio",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "sweep_detected",
    "liquidity_sweep",
    "break_of_structure",
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "body_size",
    "wick_size",
    "body_ratio",
    "volatility_regime",
    "session",
    "hour_of_day",
    "disp_strength",
    "retest_depth",
    "candles_since_retest",
    "liquidity_distance",
    "liquidity_pressure_score",
    "volume_spike"
  ],
  "v3_approx_dim": 38,
  "dim_match_v3": true,
  "note": "P0 fail-closed: RRFusionLayer refuses load when model n_features != CANONICAL_FEATURE_DIM; NanoInferenceEngine.predict raises FeatureDimensionError on width mismatch (no silent truncate)."
}
```

### TradeNet

Feature alignment FAILED

```json
{
  "selection_feature_schema_dim": 35,
  "runtime_dim": 39,
  "runtime_hash": "0edda573414f0a64",
  "note": "TradeNetV2 slices/truncates by index; v4 39-dim \u2192 silent index misalignment risk"
}
```

### BitNet

Feature alignment noted (see detail)

```json
{
  "legacy_6_input": [
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_retest",
    "double_sweep"
  ],
  "model_json_feature_order": [
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_retest",
    "double_sweep"
  ],
  "export_input_dim": 35,
  "note": "CRT serve path uses 6-key legacy; export format is 35-dim \u2014 two incompatible schemas"
}
```

## 4. Architecture Observations

- Runtime feature schema is v4.0 (39-dim): macd_hist split + wick_size→candle_range. All 38-dim trained artifacts (ZoneGate, RR fusion, Gaussian NB) predate this migration.
- Live Gaussian path is heuristic 3-feature kernel with mu/σ defaults — trained registry checkpoints are selected for BNB/ETH only and are not consumed when gaussian_impl=heuristic (F-060).
- ZoneGate is documented selected_and_enabled, but load-time ZoneFeatureOrderError now blocks EngineRunner construction under v4 — production hard-gate is currently unstartable without remap.
- RR fusion checkpoint loads and scores, but engine_runner.rr_fusion.enabled=false (F-038); confidence gate saturates bypass (F-044); index truncation under v4 is a new misalignment class.
- TradeNet is orphaned (F-005) — registry has an active ETH checkpoint but no spine consumer.
- BitNet registry is empty {}; use_bitnet=false — dual schema (legacy 6 vs export 35) remains.
- RREngine polarity vs DecisionEngine rr_threshold=1.5 is a structural consumer mismatch (F-048).
- CRT remains the only fully reachable, schema-independent decision generator on the spine.

## 5. Wiring Classification

```json
{
  "reachable": [
    "CRT",
    "Gaussian_heuristic_live",
    "ZoneGate",
    "RR_polarity_engine"
  ],
  "disabled": [
    "Gaussian_trained_NB",
    "RR_Fusion",
    "TradeNet",
    "BitNet"
  ],
  "unused_or_orphaned": [
    "Gaussian_trained_NB",
    "TradeNet",
    "BitNet"
  ],
  "dead_execution_paths": [
    "Gaussian_heuristic_live",
    "RR_Fusion"
  ],
  "rule_based_baseline": [
    "CRT",
    "RR_polarity_engine"
  ]
}
```

## 6. Cross-Model Comparison (Pearson on finite scores)

```json
{
  "pearson": {
    "CRT_state__Gaussian_heuristic": -0.003618365137492046,
    "CRT_state__Gaussian_trained": -0.015490230809192007,
    "CRT_state__ZoneGate": 0.004136114860167754,
    "CRT_state__RR_polarity": 0.002981654095711097,
    "CRT_state__TradeNet": 0.0025191062365690683,
    "CRT_state__BitNet": 0.007878469561575906,
    "Gaussian_heuristic__Gaussian_trained": -0.015038176168103925,
    "Gaussian_heuristic__ZoneGate": -0.003040471574663165,
    "Gaussian_heuristic__RR_polarity": -0.02035518374475341,
    "Gaussian_heuristic__TradeNet": -0.014523140044186275,
    "Gaussian_heuristic__BitNet": 0.031239975600095,
    "Gaussian_trained__ZoneGate": -0.3092728590788294,
    "Gaussian_trained__RR_polarity": 0.15692432972012443,
    "Gaussian_trained__TradeNet": 0.1927298837930296,
    "Gaussian_trained__BitNet": -0.31119375467196864,
    "ZoneGate__RR_polarity": -0.057187019818434055,
    "ZoneGate__TradeNet": -0.26716100902517664,
    "ZoneGate__BitNet": 0.24029668540130483,
    "RR_polarity__TradeNet": 0.03467667803186148,
    "RR_polarity__BitNet": -0.29984352198248826,
    "TradeNet__BitNet": 0.04807820841804034
  },
  "uniqueness": {
    "CRT_state": {
      "max_abs_corr_with_peer": 0.015490230809192007,
      "mean_abs_corr_with_peer": 0.006103990116784645
    },
    "Gaussian_heuristic": {
      "max_abs_corr_with_peer": 0.031239975600095,
      "mean_abs_corr_with_peer": 0.014635885378215635
    },
    "Gaussian_trained": {
      "max_abs_corr_with_peer": 0.31119375467196864,
      "mean_abs_corr_with_peer": 0.1667748723735413
    },
    "ZoneGate": {
      "max_abs_corr_with_peer": 0.3092728590788294,
      "mean_abs_corr_with_peer": 0.14684902662642932
    },
    "RR_polarity": {
      "max_abs_corr_with_peer": 0.29984352198248826,
      "mean_abs_corr_with_peer": 0.09532806456556213
    },
    "TradeNet": {
      "max_abs_corr_with_peer": 0.26716100902517664,
      "mean_abs_corr_with_peer": 0.09328133759147723
    },
    "BitNet": {
      "max_abs_corr_with_peer": 0.31119375467196864,
      "mean_abs_corr_with_peer": 0.15642176927257884
    }
  },
  "models_compared": [
    "CRT_state",
    "Gaussian_heuristic",
    "Gaussian_trained",
    "ZoneGate",
    "RR_polarity",
    "TradeNet",
    "BitNet"
  ]
}
```

## 7. Per-Model Output Statistics

### CRT (`OK`)

- kind: rule_based
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: spine_primary (deterministic state machine → TRADE_OPENED)

```json
{
  "state_id": {
    "n": 47197,
    "mean": 1.8697374833146174,
    "std": 1.4617550705407631,
    "min": 1.0,
    "max": 8.0,
    "p01": 1.0,
    "p50": 1.0,
    "p99": 5.0,
    "n_nan_or_inf": 0,
    "n_unique": 8,
    "is_constant": false,
    "is_saturated_near_bound": false,
    "frac_ge_0_99": null,
    "frac_le_0_01": 0.0
  },
  "state_distribution": {
    "SWEEP": 6722,
    "RANGE": 33514,
    "DISPLACEMENT": 355,
    "SHADOW_PENDING": 40,
    "EXPANSION": 6576,
    "RETEST": 17,
    "EXECUTION": 4,
    "EXPIRED": 18
  },
  "score_if_any": {
    "n": 0,
    "mean": null,
    "std": null,
    "min": null,
    "max": null,
    "p01": null,
    "p50": null,
    "p99": null,
    "n_nan_or_inf": 47197,
    "n_unique": 0,
    "is_constant": true,
    "is_saturated_near_bound": false
  },
  "n_valid_state_samples": 47197
}
```

### Gaussian_heuristic_live (`OK`)

- kind: heuristic
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: fusion slot 'gaussian' (EngineRunner; gaussian_impl=heuristic)

```json
{
  "n": 47197,
  "mean": 0.882686984342225,
  "std": 0.004935733547731605,
  "min": 0.8789,
  "max": 1.0,
  "p01": 0.8815,
  "p50": 0.8825,
  "p99": 0.8835,
  "n_nan_or_inf": 0,
  "n_unique": 71,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0017585863508273831,
  "frac_le_0_01": 0.0
}
```

### Gaussian_trained_NB (`EXECUTED_ORPHAN`)

- kind: trained
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: NOT on live spine when gaussian_impl=heuristic (orphan vs selection)

```json
{
  "n": 47197,
  "mean": 0.5162167224536782,
  "std": 0.06862096192903511,
  "min": 0.5,
  "max": 0.8175744761936437,
  "p01": 0.5,
  "p50": 0.5000000000000003,
  "p99": 0.8175744761936437,
  "n_nan_or_inf": 0,
  "n_unique": 1514,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0,
  "frac_le_0_01": 0.0
}
```

### ZoneGate (`OK`)

- kind: trained
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: fusion slot 'zone_gate' + hard gate (zone_mode=hard)

```json
{
  "n": 47197,
  "mean": 0.7543488716452479,
  "std": 0.07828892751220683,
  "min": 0.4196866969336664,
  "max": 0.9453615930633145,
  "p01": 0.568596846296407,
  "p50": 0.7572208777925095,
  "p99": 0.8986451305357895,
  "n_nan_or_inf": 0,
  "n_unique": 43495,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0,
  "frac_le_0_01": 0.0
}
```

### RR_polarity_engine (`OK`)

- kind: rule_based
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: fusion slot 'rr' ALWAYS (base RREngine); DecisionEngine low_rr gate (F-048)

```json
{
  "n": 47197,
  "mean": 0.7627357141343728,
  "std": 0.14554616073013796,
  "min": 0.5,
  "max": 1.0,
  "p01": 0.505696,
  "p50": 0.7676,
  "p99": 1.0,
  "n_nan_or_inf": 0,
  "n_unique": 4982,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.036972688942093775,
  "frac_le_0_01": 0.0
}
```

### RR_Fusion (`LOAD_FAIL`)

- kind: trained
- loaded/executed/features_ok/healthy: False/False/False/False
- consumer: DISABLED on active config (engine_runner.rr_fusion.enabled=false); would mutate fusion rr slot when enabled

```json
{}
```

### TradeNet (`EXECUTED_ORPHAN`)

- kind: trained
- loaded/executed/features_ok/healthy: True/True/False/True
- consumer: ORPHAN — fusion neural slot unwired (F-005); TradeNetMetaEngine not on live spine

```json
{
  "n": 47197,
  "mean": 0.46711204525711375,
  "std": 0.005280117529658464,
  "min": 0.46,
  "max": 0.4847,
  "p01": 0.4601,
  "p50": 0.466,
  "p99": 0.48230400000000007,
  "n_nan_or_inf": 0,
  "n_unique": 247,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0,
  "frac_le_0_01": 0.0
}
```

### BitNet (`EXECUTED_DISABLED_ON_SPINE`)

- kind: trained
- loaded/executed/features_ok/healthy: True/True/True/True
- consumer: CRT hard-reject gate WHEN use_bitnet=true (score<0.55); INERT on active (use_bitnet=false, F-004)

```json
{
  "n": 47197,
  "mean": 0.6868593031859771,
  "std": 0.16816393618692696,
  "min": 0.23543736773967297,
  "max": 0.9741829078667904,
  "p01": 0.26100275587250443,
  "p50": 0.7176872678488961,
  "p99": 0.9251466200228684,
  "n_nan_or_inf": 0,
  "n_unique": 37915,
  "is_constant": false,
  "is_saturated_near_bound": false,
  "frac_ge_0_99": 0.0,
  "frac_le_0_01": 0.0
}
```
