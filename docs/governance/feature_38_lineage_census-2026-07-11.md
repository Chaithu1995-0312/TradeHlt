# 38-Feature Lineage Census

Generated (UTC): `2026-07-11T11:49:55Z`

Schema dim: **38** · smoke: **PASS**

_Resync: FC1-A structure + FC1-D volregime + wick_size↔candle_range alias._

## PIT class rollup

```json
{
  "RAW_CONTEMPORANEOUS": 7,
  "RAW_OR_SYNTHETIC_SAME_BAR": 1,
  "CAUSAL_ROLLING": 5,
  "STRUCTURE_WITH_CAUSAL_SWING": 8,
  "CAUSAL_EWM": 4,
  "CAUSAL_DERIVED": 8,
  "CAUSAL_DELAYED_PUBLICATION": 2,
  "CALENDAR_SAME_BAR": 2,
  "CAUSAL_COUNTER": 1
}
```

## Per-feature chain

| # | Feature | Source OHLCV | Formula ID | PIT class | Primary impl |
|---:|---|---|---|---|---|
| 0 | `open` | open | RAW-OHLCV | `RAW_CONTEMPORANEOUS` | `src/features/feature_pipeline.py` |
| 1 | `high` | high | RAW-OHLCV | `RAW_CONTEMPORANEOUS` | `src/features/feature_pipeline.py` |
| 2 | `low` | low | RAW-OHLCV | `RAW_CONTEMPORANEOUS` | `src/features/feature_pipeline.py` |
| 3 | `close` | close | RAW-OHLCV | `RAW_CONTEMPORANEOUS` | `src/features/feature_pipeline.py` |
| 4 | `volume` | volume | RAW-OHLCV / T-003 | `RAW_OR_SYNTHETIC_SAME_BAR` | `src/features/feature_pipeline.py:203-233` |
| 5 | `volume_ratio` | volume, high, low | DERIVED-VOL | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py:219-228` |
| 6 | `double_sweep` | high, low, close | STRUCT-SWEEP | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 7 | `ema_fast` | close | FM-EMA-FAST | `CAUSAL_EWM` | `src/features/feature_pipeline.py:238-284` |
| 8 | `ema_slow` | close | FM-EMA-SLOW | `CAUSAL_EWM` | `src/features/feature_pipeline.py:238-284` |
| 9 | `ema_spread` | close | FM-022-ish / pipeline trend | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py` |
| 10 | `trend_bias` | close | DERIVED-TREND | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py:290-298` |
| 11 | `trend_strength` | close | DERIVED-TREND | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py:295-296` |
| 12 | `momentum_score` | close | FM-023 | `CAUSAL_DERIVED` | `src/features/derived_math.py` |
| 13 | `atr` | high, low, close | FM-ATR | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py:262-268` |
| 14 | `volatility_ratio` | high, low, close | FM-024 | `CAUSAL_DERIVED` | `src/features/derived_math.py` |
| 15 | `rsi_14` | close | RSI-14 | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py:246-255` |
| 16 | `macd_line` | close | MACD | `CAUSAL_EWM` | `src/features/feature_pipeline.py:278-283` |
| 17 | `macd_signal` | close | MACD | `CAUSAL_EWM` | `src/features/feature_pipeline.py:282` |
| 18 | `macd_hist` | close | MACD | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py:283` |
| 19 | `sweep_detected` | high, low, close | STRUCT-SWEEP | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 20 | `liquidity_sweep` | high, low, close | STRUCT-LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 21 | `break_of_structure` | high, low, close | STRUCT-BOS | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 22 | `swing_high` | high | STRUCT-SWING | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py` |
| 23 | `swing_low` | low | STRUCT-SWING | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py` |
| 24 | `higher_high` | high | STRUCT-HH | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 25 | `lower_low` | low | STRUCT-LL | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 26 | `body_size` | open, close | FM-001-ish / candle_math.body_size | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:25-27` |
| 27 | `wick_size` | high, low | FM-002 | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:30-32` |
| 28 | `body_ratio` | open, high, low, close | FM-010 | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:50-59` |
| 29 | `volatility_regime` | high, low, close | REGIME-VOL-ROLLING-CAUSAL | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py` |
| 30 | `session` | timestamp | CAL-SESSION | `CALENDAR_SAME_BAR` | `src/features/feature_schema.py:91-100` |
| 31 | `hour_of_day` | timestamp | CAL-HOUR | `CALENDAR_SAME_BAR` | `src/features/feature_pipeline.py` |
| 32 | `disp_strength` | open, high, low, close | FM-020 | `CAUSAL_DERIVED` | `src/features/derived_math.py` |
| 33 | `retest_depth` | high, low, close | FM-021 / FM-027 split (F-050) | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py` |
| 34 | `candles_since_retest` | high, low, close | STRUCT-COUNT | `CAUSAL_COUNTER` | `src/features/feature_pipeline.py` |
| 35 | `liquidity_distance` | high, low, close | FM-025/LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 36 | `liquidity_pressure_score` | high, low, close | FM-026/LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 37 | `volume_spike` | volume, high, low | VOL-SPIKE | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py:231` |

### Detail blocks

#### 0. `open`

- **Source OHLCV:** ['open']
- **Formula:** identity: open
- **Impl:** feature_pipeline / CSV column passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw; no lookback (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CandleLoader.Candle', 'CRTEngine']
- **Consumers (static sample):** ['src/agent/audit.py', 'src/agent/findings_synthesizer.py', 'src/agent/groq_client.py', 'src/agent/intent_router.py', 'src/agent/log_query.py', 'src/agent/modes/copilot_mode.py', 'src/agent/modes/governance_mode.py', 'src/agent/modes/log_query_mode.py', 'src/agent/modes/pipeline_mode.py', 'src/agent/state.py', 'src/analytics/sl_tp_comparator.py', 'src/bitnet/_smoke_test.py']

#### 1. `high`

- **Source OHLCV:** ['high']
- **Formula:** identity: high
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'CRT', 'candle_math']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/stability_checker.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py', 'src/config_layer/llm_scorer.py', 'src/control_plane/context_report.py', 'src/core/feature_store.py', 'src/core/fusion_engine.py', 'src/core/gate_intelligence.py', 'src/core/regime_governor.py', 'src/core/signal_audit.py']

#### 2. `low`

- **Source OHLCV:** ['low']
- **Formula:** identity: low
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'CRT', 'candle_math']
- **Consumers (static sample):** ['src/agent/groq_client.py', 'src/analytics/sl_tp_comparator.py', 'src/bitnet/_smoke_test.py', 'src/bitnet/stability_checker.py', 'src/bitnet/zone_cosine_searcher.py', 'src/bitnet/zone_validator.py', 'src/config_layer/config_validator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py', 'src/control_plane/registry.py', 'src/core/convergence_controller.py']

#### 3. `close`

- **Source OHLCV:** ['close']
- **Formula:** identity: close
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'indicators', 'CRT']
- **Consumers (static sample):** ['src/agent/agent_core.py', 'src/analytics/metrics_oracle.py', 'src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py', 'src/core/engine_runner.py', 'src/core/feature_store.py', 'src/core/model_registry.py', 'src/data_ingestion/dataset_integrity.py', 'src/data_ingestion/historical_fetcher.py']

#### 4. `volume`

- **Source OHLCV:** ['volume']
- **Formula:** identity or T-003 proxy high-low if all-zero
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:203-233']
- **PIT:** same-bar; proxy mutates volume column in-place when dead (`RAW_OR_SYNTHETIC_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline', 'volume_ratio', 'volume_spike']
- **Consumers (static sample):** ['src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/data_ingestion/dataset_integrity.py', 'src/data_ingestion/historical_fetcher.py', 'src/data_ingestion/ohlcv_schema.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py', 'src/features/feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py']
- **Mutation risk:** T-003 silent rename under same key

#### 5. `volume_ratio`

- **Source OHLCV:** ['volume', 'high', 'low']
- **Formula:** volume / rolling_mean(volume, 20)
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:219-228']
- **PIT:** rolling 20 past+current (trailing window) (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'volume_spike']
- **Consumers (static sample):** ['src/core/feature_store.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s02_mean_reversion.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py', 'src/strategies/s06_scalping.py', 'src/strategies/s07_news_sentiment.py', 'src/strategies/s08_ml_ensemble.py', 'src/strategies/s09_pattern_recog.py']

#### 6. `double_sweep`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** both sweep directions in short window on causal liquidity_sweep
- **Impl:** feature_pipeline structure/sweep block (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** production structure graph uses causal last_swing refs (available_at=t+k); rolling window of past sweeps only (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT-related features', 'FeatureStore live']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py']
- **Note:** FC1-A 2026-07-11: was STRUCTURE_WITH_CENTERED_SWING

#### 7. `ema_fast`

- **Source OHLCV:** ['close']
- **Formula:** EMA(close, span=fast) — pipeline uses ma aliases / ewm
- **Impl:** feature_pipeline.compute_indicators ewm/ma — ['src/features/feature_pipeline.py:238-284']
- **PIT:** ewm causal (adjust=False) (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'ema_spread', 'CRT cached']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/heuristic_gaussian_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py']

#### 8. `ema_slow`

- **Source OHLCV:** ['close']
- **Formula:** EMA(close, span=slow) / ma_50 path
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:238-284']
- **PIT:** causal rolling/ewm (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'ema_spread']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/heuristic_gaussian_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py']

#### 9. `ema_spread`

- **Source OHLCV:** ['close']
- **Formula:** derived_math.ema_spread / (ema_fast - ema_slow) normalized
- **Impl:** feature_pipeline + derived_math.ema_spread — ['src/features/feature_pipeline.py', 'src/features/derived_math.py', 'configs/formulas/market_ontology.yaml']
- **PIT:** depends on EMA history; ATR-gated NaN during warmup (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT cached_features']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s04_stat_arb.py', 'src/uat/uat_runner.py']

#### 10. `trend_bias`

- **Source OHLCV:** ['close']
- **Formula:** sign of MA relationship / rsi_state-like encoding to {-1,0,1}
- **Impl:** feature_pipeline.compute_trend_features / finalize encoding — ['src/features/feature_pipeline.py:290-298']
- **PIT:** causal MAs (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'Gaussian/BitNet inputs']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/dataset_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s01_crt_wrapper.py', 'src/strategies/s02_mean_reversion.py', 'src/strategies/s03_breakout.py', 'src/strategies/s04_stat_arb.py', 'src/strategies/s07_news_sentiment.py']

#### 11. `trend_strength`

- **Source OHLCV:** ['close']
- **Formula:** rolling mean of ma_20.diff()
- **Impl:** feature_pipeline.compute_trend_features — ['src/features/feature_pipeline.py:295-296']
- **PIT:** causal rolling 10 on ma_slope (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s07_news_sentiment.py', 'src/strategies/s08_ml_ensemble.py', 'src/training/stage1_dataset_builder.py', 'src/uat/uat_runner.py']

#### 12. `momentum_score`

- **Source OHLCV:** ['close']
- **Formula:** derived_math.momentum_score / pipeline momentum block
- **Impl:** feature_pipeline + derived_math — ['src/features/derived_math.py', 'src/features/feature_pipeline.py']
- **PIT:** causal lookback; ATR-gated warmup NaN possible (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT telemetry']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/core/model_registry.py', 'src/engines/heuristic_gaussian_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/governance/strategy_backtest.py']

#### 13. `atr`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** Wilder/rolling mean TrueRange(14)
- **Impl:** feature_pipeline.compute_indicators atr_14 — ['src/features/feature_pipeline.py:262-268']
- **PIT:** TR uses close.shift(1); rolling 14 causal (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline', 'disp_strength', 'retest_depth', 'liquidity_*']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/control_plane/registry.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/causal_structure.py']

#### 14. `volatility_ratio`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** atr / close or pipeline volatility ratio
- **Impl:** feature_pipeline + derived_math.volatility_ratio — ['src/features/derived_math.py', 'src/features/feature_pipeline.py']
- **PIT:** causal atr-based (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/governance/strategy_backtest.py', 'src/regime/market_state_cluster_engine.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s06_scalping.py', 'src/strategies/s07_news_sentiment.py', 'src/uat/uat_runner.py']

#### 15. `rsi_14`

- **Source OHLCV:** ['close']
- **Formula:** Wilder RSI(14) = 100 - 100/(1+RS)
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:246-255']
- **PIT:** diff + rolling 14 causal (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/control_plane/dashboard_api.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s02_mean_reversion.py', 'src/strategies/s04_stat_arb.py', 'src/strategies/s08_ml_ensemble.py', 'src/uat/uat_runner.py']

#### 16. `macd_line`

- **Source OHLCV:** ['close']
- **Formula:** EMA12 - EMA26
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:278-283']
- **PIT:** ewm causal (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'macd_hist']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/uat/uat_runner.py']

#### 17. `macd_signal`

- **Source OHLCV:** ['close']
- **Formula:** EMA9(macd_line)
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:282']
- **PIT:** ewm causal (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'macd_hist']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/uat/uat_runner.py']

#### 18. `macd_hist`

- **Source OHLCV:** ['close']
- **Formula:** macd_line - macd_signal
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:283']
- **PIT:** causal (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'NORMALIZE_COLS']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s06_scalping.py', 'src/strategies/s08_ml_ensemble.py', 'src/uat/uat_runner.py']

#### 19. `sweep_detected`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** liquidity_sweep != 0 (production liquidity_sweep is causal-graph)
- **Impl:** feature_pipeline compute_canonical_structure_features — ['src/features/feature_pipeline.py']
- **PIT:** derived from causal structure graph (FC1-A) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT score channel']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py']
- **Note:** FC1-A 2026-07-11

#### 20. `liquidity_sweep`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** sweep high/low vs causal last_swing refs (shift(1))
- **Impl:** feature_pipeline compute_structure_liquidity (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** causal last_swing_*_price; bar t uses info through t (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/feature_store.py', 'src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s10_trap_strategy.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11

#### 21. `break_of_structure`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** BOS vs causal last_swing refs
- **Impl:** feature_pipeline compute_structure_liquidity (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** causal last_swing refs + shift(1) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/regime/market_state_cluster_engine.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s01_crt_wrapper.py', 'src/strategies/s03_breakout.py', 'src/strategies/s07_news_sentiment.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11

#### 22. `swing_high`

- **Source OHLCV:** ['high']
- **Formula:** centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW=2
- **Impl:** feature_pipeline compute_structure_liquidity production bind (FC1-A) — ['src/features/feature_pipeline.py', 'src/features/causal_structure.py', 'SWING_WINDOW=2']
- **PIT:** production = causal_confirmed (available_at=t+k); research = swing_high_centered_batch (may leak) (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline', 'BOS/sweep features', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py', 'src/strategies/s10_trap_strategy.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11: production no longer CENTERED_SWING_LOOKAHEAD_IN_BATCH

#### 23. `swing_low`

- **Source OHLCV:** ['low']
- **Formula:** centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW=2
- **Impl:** feature_pipeline compute_structure_liquidity production bind (FC1-A) — ['src/features/feature_pipeline.py', 'src/features/causal_structure.py']
- **PIT:** production = causal_confirmed (available_at=t+k); research = swing_low_centered_batch (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline', 'BOS/sweep features', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py', 'src/strategies/s10_trap_strategy.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11

#### 24. `higher_high`

- **Source OHLCV:** ['high']
- **Formula:** high > causal last_swing_high_price.shift(1)
- **Impl:** feature_pipeline structure (FC1-A coherent graph) — ['src/features/feature_pipeline.py']
- **PIT:** depends on causal swing last prices (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s03_breakout.py', 'src/strategies/s10_trap_strategy.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11

#### 25. `lower_low`

- **Source OHLCV:** ['low']
- **Formula:** low < causal last_swing_low_price.shift(1)
- **Impl:** feature_pipeline structure (FC1-A coherent graph) — ['src/features/feature_pipeline.py']
- **PIT:** depends on causal swing last prices (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s03_breakout.py', 'src/strategies/s10_trap_strategy.py', 'src/uat/uat_runner.py']
- **Note:** FC1-A 2026-07-11

#### 26. `body_size`

- **Source OHLCV:** ['open', 'close']
- **Formula:** |close - open|
- **Impl:** candle_math.body_size + pipeline candle_body — ['src/features/candle_math.py:25-27', 'src/features/feature_pipeline.py']
- **PIT:** same-bar (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'body_ratio', 'CRT']
- **Consumers (static sample):** ['src/config_layer/crt_engine_v2.py', 'src/features/candle_math.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/primitive_registry.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/uat/uat_runner.py']

#### 27. `wick_size`

- **Source OHLCV:** ['high', 'low']
- **Formula:** exact alias of candle_range = high - low (vector key wick_size)
- **Impl:** candle_math.candle_range; ontology aliases.wick_size → candle_range — ['src/features/candle_math.py:30-32', 'configs/formulas/market_ontology.yaml primitives.candle_range']
- **PIT:** same-bar (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'body_ratio']
- **Consumers (static sample):** ['src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/features/candle_math.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/uat/uat_runner.py']
- **Note:** Not a second formula identity — exact equality to FM-002 candle_range

#### 28. `body_ratio`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** body_size / candle_range, 0 if range<=0
- **Impl:** candle_math.body_ratio + feature_pipeline parity — ['src/features/candle_math.py:50-59', 'configs/formulas/market_ontology.yaml body_ratio']
- **PIT:** same-bar geometry (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT displacement gate body_ratio>=0.70', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/fusion_engine.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py']

#### 29. `volatility_regime`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** tercile of ATR rolling percentile rank (N=200); production bind FC1-D
- **Impl:** feature_pipeline.compute_volatility_regime production → rolling_causal — ['src/features/feature_pipeline.py', 'SWING-adjacent: rolling window 200']
- **PIT:** rolling rank uses past+current only (min_periods=1); prefix-invariant interior (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector', 's05_grid', 'live_engine_hook pass-through']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/interpreters/regime_observer.py', 'src/replay/timing_advisor.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s05_grid.py', 'src/uat/uat_runner.py']
- **Note:** FC1-D 2026-07-11: production was GLOBAL_BATCH (non-PIT prefix ~43%). Adjudication FC-0.5 selected rolling N=200 causal; global preserved as volatility_regime_global_batch research/legacy only. Semantic is local ATR-percentile tercile context, not latent Regime Detection.

#### 30. `session`

- **Source OHLCV:** ['timestamp']
- **Formula:** session bucket from hour/tz assumptions → SESSION_MAP float
- **Impl:** feature_pipeline session encode + feature_schema.SESSION_MAP — ['src/features/feature_schema.py:91-100', 'src/features/feature_pipeline.py']
- **PIT:** same-bar timestamp; UTC-naive assumption (`CALENDAR_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline vector', 'session filters']
- **Consumers (static sample):** ['src/agent/agent_core.py', 'src/agent/audit.py', 'src/agent/cli.py', 'src/config_layer/config_validator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/config_layer/insight_reporter.py', 'src/config_layer/llm_narrative.py', 'src/config_layer/production_config.py', 'src/control_plane/dashboard_api.py', 'src/control_plane/registry.py', 'src/control_plane/server.py']

#### 31. `hour_of_day`

- **Source OHLCV:** ['timestamp']
- **Formula:** timestamp.hour (or fraction)
- **Impl:** feature_pipeline — ['src/features/feature_pipeline.py']
- **PIT:** same-bar (`CALENDAR_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/portfolio_validation.py', 'src/governance/strategy_backtest.py', 'src/runtime/backtest_v2.py', 'src/runtime/live_engine_hook.py', 'src/strategies/s06_scalping.py', 'src/uat/uat_runner.py']

#### 32. `disp_strength`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** clip(body_size / (atr * close), 0, 3) — FM-020 (pipeline vector definition)
- **Impl:** derived_math.disp_strength (scalar authority) + feature_pipeline vectorized — ['src/features/derived_math.py', 'configs/formulas/market_ontology.yaml FM-020', 'src/features/feature_pipeline.py']
- **PIT:** ATR lookback causal; same-bar body (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT cached_features', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py']
- **Note:** F-050 (FM-028 emission rename) + GD-004 (FM-029 registration): name collisions closed; this row is FM-020 only

#### 33. `retest_depth`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** FM-021 pipeline retest vs EMA/ATR; CRT has FM-027 displacement_retrace
- **Impl:** feature_pipeline + derived_math; CRT derived_math FM-027 — ['src/features/feature_pipeline.py', 'src/features/derived_math.py', 'configs/formulas/market_ontology.yaml']
- **PIT:** causal ATR/EMA; structure context (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/fusion_engine.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/llm_engine.py']

#### 34. `candles_since_retest`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** bars since last retest event flag
- **Impl:** feature_pipeline structure counters — ['src/features/feature_pipeline.py']
- **PIT:** causal counter from past events (`CAUSAL_COUNTER`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/bitnet_inference.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/live_engine.py', 'src/engines/scoring_engine.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py']

#### 35. `liquidity_distance`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** ATR-normalised distance to nearest liquidity level (causal swing refs)
- **Impl:** feature_pipeline liquidity block v3 + derived_math (FC1-A refs) — ['src/features/feature_pipeline.py', 'src/features/derived_math.py']
- **PIT:** depends on causal last_swing / BOS levels + shift(1) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 35']
- **Consumers (static sample):** ['src/core/hierarchical_meta_fusion.py', 'src/features/causal_structure.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/regime/market_state_cluster_engine.py']
- **Note:** FC1-A 2026-07-11

#### 36. `liquidity_pressure_score`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** clip(exp(-0.5 * liquidity_distance), 0, 1)
- **Impl:** feature_pipeline + derived_math.liquidity_pressure_score — ['src/features/feature_pipeline.py', 'src/features/derived_math.py']
- **PIT:** derived from causal liquidity_distance (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 36']
- **Consumers (static sample):** ['src/core/hierarchical_meta_fusion.py', 'src/engines/tradenet_meta_engine.py', 'src/features/causal_structure.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/regime/market_state_cluster_engine.py']
- **Note:** FC1-A 2026-07-11

#### 37. `volume_spike`

- **Source OHLCV:** ['volume', 'high', 'low']
- **Formula:** (volume_ratio > 1.5).astype(int8)
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:231']
- **PIT:** causal volume_ratio (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector index 37']
- **Consumers (static sample):** ['src/features/feature_pipeline.py', 'src/regime/market_state_cluster_engine.py']

## Smoke (frozen XAUUSD)

```json
{
  "status": "PASS",
  "corpus": "data/mt5/XAUUSD_M15.csv",
  "rows_out": 47197,
  "vector_rows": 47197,
  "canonical_columns_present": "38/38",
  "missing_columns": []
}
```

Machine twin: `feature_38_lineage_census-2026-07-11.json` (also refreshed stable `feature_38_lineage_census-2026-07-10.json`)
