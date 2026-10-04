# Canonical-Feature Lineage Census (48-dim, schema v5.0)

Generated (UTC): `2026-09-05T09:39:54Z`

Schema dim: **48** · smoke: **PASS**

_Resync: FC1-A structure + FC1-D volregime + wick_size↔candle_range alias._

## PIT class rollup

```json
{
  "RAW_CONTEMPORANEOUS": 7,
  "RAW_OR_SYNTHETIC_SAME_BAR": 1,
  "CAUSAL_ROLLING": 5,
  "STRUCTURE_WITH_CAUSAL_SWING": 14,
  "CAUSAL_EWM": 4,
  "CAUSAL_DERIVED": 9,
  "CAUSAL_DELAYED_PUBLICATION": 5,
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
| 18 | `macd_hist_raw` | close | FM-049 | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py:283` |
| 19 | `macd_hist_z` | close | FM-053 | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py` |
| 20 | `sweep_detected` | high, low, close | STRUCT-SWEEP | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 21 | `liquidity_sweep` | high, low, close | STRUCT-LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 22 | `break_of_structure` | high, low, close | STRUCT-BOS | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 23 | `swing_high` | high | STRUCT-SWING | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py` |
| 24 | `swing_low` | low | STRUCT-SWING | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py` |
| 25 | `higher_high` | high | STRUCT-HH | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 26 | `lower_low` | low | STRUCT-LL | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 27 | `body_size` | open, close | FM-001-ish / candle_math.body_size | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:25-27` |
| 28 | `candle_range` | high, low | FM-002 | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:30-32` |
| 29 | `body_ratio` | open, high, low, close | FM-010 | `RAW_CONTEMPORANEOUS` | `src/features/candle_math.py:50-59` |
| 30 | `volatility_regime` | high, low, close | REGIME-VOL-ROLLING-CAUSAL | `CAUSAL_ROLLING` | `src/features/feature_pipeline.py` |
| 31 | `session` | timestamp | CAL-SESSION | `CALENDAR_SAME_BAR` | `src/features/feature_schema.py:91-100` |
| 32 | `hour_of_day` | timestamp | CAL-HOUR | `CALENDAR_SAME_BAR` | `src/features/feature_pipeline.py` |
| 33 | `disp_strength` | open, high, low, close | FM-020 | `CAUSAL_DERIVED` | `src/features/derived_math.py` |
| 34 | `retest_depth` | high, low, close | FM-021 / FM-027 split (F-050) | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py` |
| 35 | `candles_since_retest` | high, low, close | STRUCT-COUNT | `CAUSAL_COUNTER` | `src/features/feature_pipeline.py` |
| 36 | `liquidity_distance` | high, low, close | FM-025/LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 37 | `liquidity_pressure_score` | high, low, close | FM-026/LIQ | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py` |
| 38 | `volume_spike` | volume, high, low | VOL-SPIKE | `CAUSAL_DERIVED` | `src/features/feature_pipeline.py:231` |
| 39 | `order_block_distance` | open, high, low, close | SMC-OB | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1283` |
| 40 | `fvg_distance` | high, low, close | SMC-FVG | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py:1284` |
| 41 | `breaker_distance` | open, high, low, close | SMC-BREAKER | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1285` |
| 42 | `mitigation_block_distance` | open, high, low, close | SMC-MITIGATION | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1286` |
| 43 | `pdh_distance` | high, close | SMC-PDH | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py:1287` |
| 44 | `pdl_distance` | low, close | SMC-PDL | `CAUSAL_DELAYED_PUBLICATION` | `src/features/feature_pipeline.py:1287` |
| 45 | `eqh_distance` | high, close | SMC-EQH | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1290` |
| 46 | `eql_distance` | low, close | SMC-EQL | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1290` |
| 47 | `change_of_character` | high, low, close | FM-083/SMC-CHOCH | `STRUCTURE_WITH_CAUSAL_SWING` | `src/features/feature_pipeline.py:1303` |

### Detail blocks

#### 0. `open`

- **Source OHLCV:** ['open']
- **Formula:** identity: open
- **Impl:** feature_pipeline / CSV column passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw; no lookback (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CandleLoader.Candle', 'CRTEngine']
- **Consumers (static sample):** ['src/agent/audit.py', 'src/agent/findings_synthesizer.py', 'src/agent/groq_client.py', 'src/agent/intent_router.py', 'src/agent/log_query.py', 'src/agent/modes/copilot_mode.py', 'src/agent/modes/governance_mode.py', 'src/agent/modes/log_query_mode.py', 'src/agent/modes/pipeline_mode.py', 'src/agent/modes/truth_mode.py', 'src/agent/state.py', 'src/analytics/sl_tp_comparator.py']

#### 1. `high`

- **Source OHLCV:** ['high']
- **Formula:** identity: high
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'CRT', 'candle_math']
- **Consumers (static sample):** ['src/agent/modes/pipeline_mode.py', 'src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/label_contracts.py', 'src/bitnet/population_label_audit.py', 'src/bitnet/r25_kill_test.py', 'src/bitnet/stability_checker.py', 'src/charts/chart_series.py', 'src/charts/render.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py']

#### 2. `low`

- **Source OHLCV:** ['low']
- **Formula:** identity: low
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'CRT', 'candle_math']
- **Consumers (static sample):** ['src/agent/cli.py', 'src/agent/groq_client.py', 'src/agent/modes/pipeline_mode.py', 'src/analytics/sl_tp_comparator.py', 'src/bitnet/_smoke_test.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/label_contracts.py', 'src/bitnet/population_label_audit.py', 'src/bitnet/stability_checker.py', 'src/bitnet/zone_cosine_searcher.py', 'src/bitnet/zone_validator.py', 'src/charts/chart_series.py']

#### 3. `close`

- **Source OHLCV:** ['close']
- **Formula:** identity: close
- **Impl:** passthrough — ['src/features/feature_pipeline.py']
- **PIT:** same-bar raw (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'Candle', 'indicators', 'CRT']
- **Consumers (static sample):** ['src/agent/agent_core.py', 'src/agent/modes/pipeline_mode.py', 'src/analytics/metrics_oracle.py', 'src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/label_contracts.py', 'src/bitnet/population_label_audit.py', 'src/charts/chart_series.py', 'src/charts/render.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/crt_sweep_taxonomy.py']

#### 4. `volume`

- **Source OHLCV:** ['volume']
- **Formula:** identity or T-003 proxy high-low if all-zero
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:203-233']
- **PIT:** same-bar; proxy mutates volume column in-place when dead (`RAW_OR_SYNTHETIC_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline', 'volume_ratio', 'volume_spike']
- **Consumers (static sample):** ['src/agent/modes/pipeline_mode.py', 'src/charts/chart_series.py', 'src/charts/render.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/data_ingestion/clock_detector.py', 'src/data_ingestion/corpus_gate.py', 'src/data_ingestion/dataset_integrity.py', 'src/data_ingestion/historical_fetcher.py', 'src/data_ingestion/ohlcv_schema.py']
- **Mutation risk:** T-003 silent rename under same key

#### 5. `volume_ratio`

- **Source OHLCV:** ['volume', 'high', 'low']
- **Formula:** volume / rolling_mean(volume, 20)
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:219-228']
- **PIT:** rolling 20 past+current (trailing window) (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'volume_spike']
- **Consumers (static sample):** ['src/core/feature_store.py', 'src/data_ingestion/corpus_gate.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/research/ic002_entry_evolution/schema.py', 'src/research/zone_mapping/historical_zone_mapper.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/strategies/s02_mean_reversion.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py']

#### 6. `double_sweep`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** both sweep directions in short window on causal liquidity_sweep
- **Impl:** feature_pipeline structure/sweep block (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** production structure graph uses causal last_swing refs (available_at=t+k); rolling window of past sweeps only (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT-related features', 'FeatureStore live']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/defaults.py', 'src/bitnet/encoders.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py']
- **Note:** FC1-A 2026-07-11: was STRUCTURE_WITH_CENTERED_SWING

#### 7. `ema_fast`

- **Source OHLCV:** ['close']
- **Formula:** EMA(close, span=fast) — pipeline uses ma aliases / ewm
- **Impl:** feature_pipeline.compute_indicators ewm/ma — ['src/features/feature_pipeline.py:238-284']
- **PIT:** ewm causal (adjust=False) (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'ema_spread', 'CRT cached']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/charts/chart_series.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/config_layer/state_identity.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/heuristic_gaussian_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py']

#### 8. `ema_slow`

- **Source OHLCV:** ['close']
- **Formula:** EMA(close, span=slow) / ma_50 path
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:238-284']
- **PIT:** causal rolling/ewm (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'ema_spread']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/charts/chart_series.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/config_layer/state_identity.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py', 'src/engines/heuristic_gaussian_engine.py', 'src/engines/trap_validator_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py']

#### 9. `ema_spread`

- **Source OHLCV:** ['close']
- **Formula:** derived_math.ema_spread / (ema_fast - ema_slow) normalized
- **Impl:** feature_pipeline + derived_math.ema_spread — ['src/features/feature_pipeline.py', 'src/features/derived_math.py', 'configs/formulas/market_ontology.yaml']
- **PIT:** depends on EMA history; ATR-gated NaN during warmup (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT cached_features']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/feature_states.py', 'src/features/registry/derived_registry.py', 'src/governance/strategy_backtest.py', 'src/research/band_validation.py', 'src/research/evidence/catalog.py', 'src/research/model_runners/adapters/dual_engine.py', 'src/research/model_runners/contracts.py']

#### 10. `trend_bias`

- **Source OHLCV:** ['close']
- **Formula:** sign of MA relationship / rsi_state-like encoding to {-1,0,1}
- **Impl:** feature_pipeline.compute_trend_features / finalize encoding — ['src/features/feature_pipeline.py:290-298']
- **PIT:** causal MAs (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'Gaussian/BitNet inputs']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/crt_state_resolver.py', 'src/features/dataset_builder.py', 'src/features/feature_pipeline.py', 'src/features/model_evidence.py', 'src/features/smc/choch.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/episode_propositions.py']

#### 11. `trend_strength`

- **Source OHLCV:** ['close']
- **Formula:** rolling mean of ma_20.diff()
- **Impl:** feature_pipeline.compute_trend_features — ['src/features/feature_pipeline.py:295-296']
- **PIT:** causal rolling 10 on ma_slope (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/synthetic/stories/trend_continuation.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/strategies/s07_news_sentiment.py', 'src/strategies/s08_ml_ensemble.py']

#### 12. `momentum_score`

- **Source OHLCV:** ['close']
- **Formula:** derived_math.momentum_score / pipeline momentum block
- **Impl:** feature_pipeline + derived_math — ['src/features/derived_math.py', 'src/features/feature_pipeline.py']
- **PIT:** causal lookback; ATR-gated warmup NaN possible (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT telemetry']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/core/model_registry.py', 'src/engines/heuristic_gaussian_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/magnitude_states.py']

#### 13. `atr`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** Wilder/rolling mean TrueRange(14)
- **Impl:** feature_pipeline.compute_indicators atr_14 — ['src/features/feature_pipeline.py:262-268']
- **PIT:** TR uses close.shift(1); rolling 14 causal (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline', 'disp_strength', 'retest_depth', 'liquidity_*']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/defaults.py', 'src/bitnet/encoders.py', 'src/bitnet/population_label_audit.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/config_layer/state_identity.py', 'src/control_plane/registry.py', 'src/core/feature_store.py', 'src/core/gate_intelligence.py']

#### 14. `volatility_ratio`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** atr / close or pipeline volatility ratio
- **Impl:** feature_pipeline + derived_math.volatility_ratio — ['src/features/derived_math.py', 'src/features/feature_pipeline.py']
- **PIT:** causal atr-based (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/engine_runner.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/regime/market_state_cluster_engine.py', 'src/research/ic002_entry_evolution/schema.py', 'src/research/model_runners/adapters/dual_engine.py', 'src/research/model_runners/contracts.py']

#### 15. `rsi_14`

- **Source OHLCV:** ['close']
- **Formula:** Wilder RSI(14) = 100 - 100/(1+RS)
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:246-255']
- **PIT:** diff + rolling 14 causal (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/bitnet/contract_c_trainer.py', 'src/control_plane/dashboard_api.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/registry/__init__.py', 'src/governance/strategy_backtest.py', 'src/research/ic002_entry_evolution/schema.py', 'src/research/ic003_shapes/schema.py', 'src/research/ic003b_sequence_geometry/schema.py', 'src/research/zone_mapping/historical_zone_mapper.py', 'src/runtime/live_engine_hook.py']

#### 16. `macd_line`

- **Source OHLCV:** ['close']
- **Formula:** EMA12 - EMA26
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:278-283']
- **PIT:** ewm causal (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'macd_hist_raw']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/uat/uat_runner.py']

#### 17. `macd_signal`

- **Source OHLCV:** ['close']
- **Formula:** EMA9(macd_line)
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:282']
- **PIT:** ewm causal (`CAUSAL_EWM`)
- **Consumers (curated):** ['FeaturePipeline', 'macd_hist_raw']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/uat/uat_runner.py']

#### 18. `macd_hist_raw`

- **Source OHLCV:** ['close']
- **Formula:** macd_line - macd_signal (FM-049) -- the DECLARED formula, unchanged from v3.0
- **Impl:** feature_pipeline.compute_indicators — ['src/features/feature_pipeline.py:283']
- **PIT:** causal (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector', 'macd_hist_z']
- **Consumers (static sample):** ['src/config_layer/production_bundle.py', 'src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/gaussian_schema_contract.py', 'src/governance/strategy_backtest.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/live_engine_hook.py']
- **Note:** v4.0 rename of the v3.0 `macd_hist` entry -- same math, index moved 18->18 (this identity) while the z-scored value it used to silently carry moved to its own slot, macd_hist_z (index 19).

#### 19. `macd_hist_z`

- **Source OHLCV:** ['close']
- **Formula:** rolling(50) z-score of macd_hist_raw (FM-053)
- **Impl:** feature_pipeline.compute_normalization (NORMALIZE_TO_NEW_COL) — ['src/features/feature_pipeline.py']
- **PIT:** causal rolling(50) (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/gaussian_schema_contract.py', 'src/governance/strategy_backtest.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/strategies/s06_scalping.py', 'src/strategies/s08_ml_ensemble.py', 'src/training/trainer.py']
- **Note:** v4.0 new slot (index 19) -- what v3.0's single `macd_hist` column actually EMITTED (compute_normalization overwrote it in place); now has its own canonical identity distinct from macd_hist_raw.

#### 20. `sweep_detected`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** liquidity_sweep != 0 (production liquidity_sweep is causal-graph)
- **Impl:** feature_pipeline compute_canonical_structure_features — ['src/features/feature_pipeline.py']
- **PIT:** derived from causal structure graph (FC1-A) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'CRT score channel']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py']
- **Note:** FC1-A 2026-07-11

#### 21. `liquidity_sweep`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** sweep high/low vs causal last_swing refs (shift(1))
- **Impl:** feature_pipeline compute_structure_liquidity (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** causal last_swing_*_price; bar t uses info through t (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/feature_store.py', 'src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/crt_state_resolver.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/msip/disagreement.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py']
- **Note:** FC1-A 2026-07-11

#### 22. `break_of_structure`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** BOS vs causal last_swing refs
- **Impl:** feature_pipeline compute_structure_liquidity (FC1-A) — ['src/features/feature_pipeline.py']
- **PIT:** causal last_swing refs + shift(1) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/smc/choch.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/regime/market_state_cluster_engine.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py', 'src/research/ic002_entry_evolution/schema.py']
- **Note:** FC1-A 2026-07-11

#### 23. `swing_high`

- **Source OHLCV:** ['high']
- **Formula:** centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW=2
- **Impl:** feature_pipeline compute_structure_liquidity production bind (FC1-A) — ['src/features/feature_pipeline.py', 'src/features/causal_structure.py', 'SWING_WINDOW=2']
- **PIT:** production = causal_confirmed (available_at=t+k); research = swing_high_centered_batch (may leak) (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline', 'BOS/sweep features', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/research/evidence/catalog.py', 'src/research/synthetic/stories/breakout.py', 'src/research/synthetic/stories/range_rotation.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py']
- **Note:** FC1-A 2026-07-11: production no longer CENTERED_SWING_LOOKAHEAD_IN_BATCH

#### 24. `swing_low`

- **Source OHLCV:** ['low']
- **Formula:** centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW=2
- **Impl:** feature_pipeline compute_structure_liquidity production bind (FC1-A) — ['src/features/feature_pipeline.py', 'src/features/causal_structure.py']
- **PIT:** production = causal_confirmed (available_at=t+k); research = swing_low_centered_batch (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline', 'BOS/sweep features', 'FeatureStore live']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/research/evidence/catalog.py', 'src/research/synthetic/stories/range_rotation.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py', 'src/strategies/s03_breakout.py', 'src/strategies/s05_grid.py', 'src/strategies/s10_trap_strategy.py']
- **Note:** FC1-A 2026-07-11

#### 25. `higher_high`

- **Source OHLCV:** ['high']
- **Formula:** high > causal last_swing_high_price.shift(1)
- **Impl:** feature_pipeline structure (FC1-A coherent graph) — ['src/features/feature_pipeline.py']
- **PIT:** depends on causal swing last prices (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py', 'src/research/ic002_entry_evolution/schema.py', 'src/research/synthetic/stories/breakout.py', 'src/runtime/live_engine_hook.py']
- **Note:** FC1-A 2026-07-11

#### 26. `lower_low`

- **Source OHLCV:** ['low']
- **Formula:** low < causal last_swing_low_price.shift(1)
- **Impl:** feature_pipeline structure (FC1-A coherent graph) — ['src/features/feature_pipeline.py']
- **PIT:** depends on causal swing last prices (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/core/model_registry.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py', 'src/research/ic002_entry_evolution/schema.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** FC1-A 2026-07-11

#### 27. `body_size`

- **Source OHLCV:** ['open', 'close']
- **Formula:** |close - open|
- **Impl:** candle_math.body_size + pipeline candle_body — ['src/features/candle_math.py:25-27', 'src/features/feature_pipeline.py']
- **PIT:** same-bar (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'body_ratio', 'CRT']
- **Consumers (static sample):** ['src/bitnet/contract_c_trainer.py', 'src/config_layer/crt_engine_v2.py', 'src/features/candle_math.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/fm_resolve.py', 'src/features/registry/primitive_registry.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/sujan_manipulation/bulk_proxy.py']

#### 28. `candle_range`

- **Source OHLCV:** ['high', 'low']
- **Formula:** high - low (FM-002)
- **Impl:** candle_math.candle_range — ['src/features/candle_math.py:30-32', 'configs/formulas/market_ontology.yaml primitives.candle_range']
- **PIT:** same-bar (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'body_ratio', 'volatility_ratio', 'displacement_atr_ratio']
- **Consumers (static sample):** ['src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/engines/rr_engine.py', 'src/features/candle_math.py', 'src/features/crt_feature_builder.py', 'src/features/crt_state_resolver.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/fm_resolve.py', 'src/features/gaussian_schema_contract.py', 'src/features/registry/primitive_registry.py', 'src/governance/strategy_backtest.py']
- **Note:** v4.0 rename (feature_schema.py:89, Semantic Layer Certification Audit 2026-07-31, Tier 1 items 1-2): this entry was `wick_size` in v3.0 -- pure identity rename, math never changed (always high-low, never a wick magnitude -- see F-046 / candle_math.py). `wick_size` survives only as a read-side alias for historical records (SCHEMA_V3_ALIASES); never emitted.

#### 29. `body_ratio`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** body_size / candle_range, 0 if range<=0
- **Impl:** candle_math.body_ratio + feature_pipeline parity — ['src/features/candle_math.py:50-59', 'configs/formulas/market_ontology.yaml body_ratio']
- **PIT:** same-bar geometry (`RAW_CONTEMPORANEOUS`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT displacement gate body_ratio>=0.70', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/defaults.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/crt_sweep_taxonomy.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/fusion_engine.py', 'src/core/gate_intelligence.py']

#### 30. `volatility_regime`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** tercile of ATR rolling percentile rank (N=200); production bind FC1-D
- **Impl:** feature_pipeline.compute_volatility_regime production → rolling_causal — ['src/features/feature_pipeline.py', 'SWING-adjacent: rolling window 200']
- **PIT:** rolling rank uses past+current only (min_periods=1); prefix-invariant interior (`CAUSAL_ROLLING`)
- **Consumers (curated):** ['FeaturePipeline vector', 's05_grid', 'live_engine_hook pass-through']
- **Consumers (static sample):** ['src/config_layer/htf_state.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/governance/strategy_backtest.py', 'src/interpreters/regime_observer.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/replay/timing_advisor.py', 'src/research/band_validation.py', 'src/research/evidence/asymmetry_contract.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py']
- **Note:** FC1-D 2026-07-11: production was GLOBAL_BATCH (non-PIT prefix ~43%). Adjudication FC-0.5 selected rolling N=200 causal; global preserved as volatility_regime_global_batch research/legacy only. Semantic is local ATR-percentile tercile context, not latent Regime Detection.

#### 31. `session`

- **Source OHLCV:** ['timestamp']
- **Formula:** session bucket from hour/tz assumptions → SESSION_MAP float
- **Impl:** feature_pipeline session encode + feature_schema.SESSION_MAP — ['src/features/feature_schema.py:91-100', 'src/features/feature_pipeline.py']
- **PIT:** same-bar timestamp; UTC-naive assumption (`CALENDAR_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline vector', 'session filters']
- **Consumers (static sample):** ['src/agent/audit.py', 'src/agent/cli.py', 'src/charts/chart_series.py', 'src/charts/crt_overlay.py', 'src/config_layer/config_validator.py', 'src/config_layer/crt_config_completeness.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/execution_planner.py', 'src/config_layer/insight_reporter.py', 'src/config_layer/llm_narrative.py', 'src/config_layer/m15_structural_range.py', 'src/config_layer/production_config.py']

#### 32. `hour_of_day`

- **Source OHLCV:** ['timestamp']
- **Formula:** timestamp.hour (or fraction)
- **Impl:** feature_pipeline — ['src/features/feature_pipeline.py']
- **PIT:** same-bar (`CALENDAR_SAME_BAR`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/session_classifier.py', 'src/governance/portfolio_validation.py', 'src/governance/strategy_backtest.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py', 'src/research/zone_mapping/historical_zone_mapper.py', 'src/runtime/backtest_v2.py', 'src/runtime/live_engine_hook.py']

#### 33. `disp_strength`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** clip(body_size / (atr * close), 0, 3) — FM-020 (pipeline vector definition)
- **Impl:** derived_math.disp_strength (scalar authority) + feature_pipeline vectorized — ['src/features/derived_math.py', 'configs/formulas/market_ontology.yaml FM-020', 'src/features/feature_pipeline.py']
- **PIT:** ATR lookback causal; same-bar body (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT cached_features', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/defaults.py', 'src/bitnet/encoders.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/engine_runner.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/scoring_engine.py']
- **Note:** F-050 (FM-028 emission rename) + GD-004 (FM-029 registration): name collisions closed; this row is FM-020 only

#### 34. `retest_depth`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** FM-021 pipeline retest vs EMA/ATR; CRT has FM-027 displacement_retrace
- **Impl:** feature_pipeline + derived_math; CRT derived_math FM-027 — ['src/features/feature_pipeline.py', 'src/features/derived_math.py', 'configs/formulas/market_ontology.yaml']
- **PIT:** causal ATR/EMA; structure context (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline', 'CRT', 'FeatureMonitor']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/contract_c_trainer.py', 'src/bitnet/defaults.py', 'src/bitnet/encoders.py', 'src/bitnet/population_label_audit.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/config_layer/rr/rr_fusion.py', 'src/core/collector.py', 'src/core/engine_runner.py', 'src/core/fusion_engine.py']

#### 35. `candles_since_retest`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** bars since last retest event flag
- **Impl:** feature_pipeline structure counters — ['src/features/feature_pipeline.py']
- **PIT:** causal counter from past events (`CAUSAL_COUNTER`)
- **Consumers (curated):** ['FeaturePipeline vector']
- **Consumers (static sample):** ['src/analytics/sl_tp_comparator.py', 'src/bitnet/defaults.py', 'src/config_layer/crt_engine_v2.py', 'src/config_layer/crt_gaussian_scorer.py', 'src/config_layer/execution_planner.py', 'src/core/collector.py', 'src/core/gate_intelligence.py', 'src/engines/crt_engine.py', 'src/engines/live_engine.py', 'src/engines/scoring_engine.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py']

#### 36. `liquidity_distance`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** ATR-normalised distance to nearest liquidity level (causal swing refs)
- **Impl:** feature_pipeline liquidity block v3 + derived_math (FC1-A refs) — ['src/features/feature_pipeline.py', 'src/features/derived_math.py']
- **PIT:** depends on causal last_swing / BOS levels + shift(1) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 35']
- **Consumers (static sample):** ['src/core/hierarchical_meta_fusion.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/fm_resolve.py', 'src/features/registry/derived_registry.py', 'src/features/smc/__init__.py', 'src/features/smc/levels.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/regime/market_state_cluster_engine.py']
- **Note:** FC1-A 2026-07-11

#### 37. `liquidity_pressure_score`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** clip(exp(-0.5 * liquidity_distance), 0, 1)
- **Impl:** feature_pipeline + derived_math.liquidity_pressure_score — ['src/features/feature_pipeline.py', 'src/features/derived_math.py']
- **PIT:** derived from causal liquidity_distance (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 36']
- **Consumers (static sample):** ['src/core/hierarchical_meta_fusion.py', 'src/engines/tradenet_meta_engine.py', 'src/features/causal_structure.py', 'src/features/crt_feature_builder.py', 'src/features/derived_math.py', 'src/features/feature_pipeline.py', 'src/features/fm_resolve.py', 'src/features/registry/derived_registry.py', 'src/features/smc/levels.py', 'src/msip/interpretation_config.py', 'src/msip/market_state_vector.py', 'src/regime/market_state_cluster_engine.py']
- **Note:** FC1-A 2026-07-11

#### 38. `volume_spike`

- **Source OHLCV:** ['volume', 'high', 'low']
- **Formula:** (volume_ratio > 1.5).astype(int8)
- **Impl:** feature_pipeline.compute_volume_features — ['src/features/feature_pipeline.py:231']
- **PIT:** causal volume_ratio (`CAUSAL_DERIVED`)
- **Consumers (curated):** ['FeaturePipeline vector index 37']
- **Consumers (static sample):** ['src/data_ingestion/corpus_gate.py', 'src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/regime/market_state_cluster_engine.py', 'src/research/evidence/atlases.py', 'src/research/evidence/queries.py', 'src/research/synthetic/stories/breakout.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']

#### 39. `order_block_distance`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** tanh(signed ATR distance from close to nearest UNMITIGATED order-block edge); OB = last opposite-colour candle before a causal-swing break, k=SWING_WINDOW=2
- **Impl:** feature_pipeline.compute_smc_features -> smc.order_block.order_block_distance — ['src/features/feature_pipeline.py:1283', 'src/features/smc/order_block.py', 'src/features/smc/_geometry.py', 'SWING_WINDOW=2']
- **PIT:** break events use detect_causal_swings(bars[:i], k) — no lookahead (order_block.py:38-50); window grows only to bar i (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 39']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/features/smc/order_block.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); PIT classified 2026-09-05, classification only — grants no closure and no authority

#### 40. `fvg_distance`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** tanh(signed ATR distance from close to nearest UNFILLED fair-value-gap near edge); 3-candle test bars[i-1].high < bars[i+1].low (bullish) / bars[i-1].low > bars[i+1].high (bearish)
- **Impl:** feature_pipeline.compute_smc_features -> smc.fvg.fvg_distance — ['src/features/feature_pipeline.py:1284', 'src/features/smc/fvg.py']
- **PIT:** zone is STAMPED at the middle candle (formed_at_index) but only becomes detectable once bars[i+1] has closed — publication lag 1; the interior loop range(1, n-1) never reads past the caller's window, so the EMITTED value at bar i uses only bars <= i (fvg.py:23-37) (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline vector index 40']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/features/smc/fvg.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); the delayed publication is on the zone's backdated stamp, not on the emitted distance. PIT classified 2026-09-05

#### 41. `breaker_distance`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** tanh(signed ATR distance to nearest un-retested BREAKER — an order block whose far edge was fully closed through, polarity flipped), k=SWING_WINDOW=2
- **Impl:** feature_pipeline.compute_smc_features -> smc.breaker.breaker_distance — ['src/features/feature_pipeline.py:1285', 'src/features/smc/breaker.py', 'src/features/smc/order_block.py']
- **PIT:** reuses order_block._find_break_events (causal swings, bars[:i]); breaker requires a LATER close-through, so it is strictly backward-looking (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 41']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/features/smc/breaker.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); PIT classified 2026-09-05

#### 42. `mitigation_block_distance`

- **Source OHLCV:** ['open', 'high', 'low', 'close']
- **Formula:** tanh(signed ATR distance to the BODY-only inner zone of the active OB origin whose outer zone was already touched), k=SWING_WINDOW=2
- **Impl:** feature_pipeline.compute_smc_features -> smc.mitigation.mitigation_block_distance — ['src/features/feature_pipeline.py:1286', 'src/features/smc/mitigation.py', 'src/features/smc/order_block.py']
- **PIT:** same causal break-event scan as order_block; the outer-zone touch it gates on is a past event (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 42']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/registry/derived_registry.py', 'src/features/smc/mitigation.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); deliberately a DIFFERENT distance from order_block_distance, not an alias. PIT classified 2026-09-05

#### 43. `pdh_distance`

- **Source OHLCV:** ['high', 'close']
- **Formula:** tanh(signed ATR distance from close to the most recently CLOSED D1 parent's high); 0.0 before the first D1 parent closes
- **Impl:** feature_pipeline.compute_smc_features (ParentCandleBuilder('D1')) -> smc.levels.pdh_pdl_distance — ['src/features/feature_pipeline.py:1287', 'src/features/smc/levels.py', 'src/features/parent_candle.py']
- **PIT:** reads parent_history[-1] = the last COMPLETED daily candle, never the forming one (levels.py:26-35); reference is a prior calendar unit, so it is delayed relative to the bar that publishes it (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline vector index 43']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/smc/levels.py', 'src/research/clean_labels/builder.py', 'src/research/evidence/context_attribution.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); NOT CALENDAR_SAME_BAR — session/hour_of_day derive from the bar's OWN timestamp, this derives from a previous completed day. PIT classified 2026-09-05

#### 44. `pdl_distance`

- **Source OHLCV:** ['low', 'close']
- **Formula:** tanh(signed ATR distance from close to the most recently CLOSED D1 parent's low); 0.0 before the first D1 parent closes
- **Impl:** feature_pipeline.compute_smc_features (ParentCandleBuilder('D1')) -> smc.levels.pdh_pdl_distance — ['src/features/feature_pipeline.py:1287', 'src/features/smc/levels.py', 'src/features/parent_candle.py']
- **PIT:** reads parent_history[-1] = the last COMPLETED daily candle, never the forming one (levels.py:26-35) (`CAUSAL_DELAYED_PUBLICATION`)
- **Consumers (curated):** ['FeaturePipeline vector index 44']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/smc/levels.py', 'src/research/clean_labels/builder.py', 'src/research/evidence/context_attribution.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); PIT classified 2026-09-05

#### 45. `eqh_distance`

- **Source OHLCV:** ['high', 'close']
- **Formula:** tanh(signed ATR distance to the most recent member of an EQUAL-HIGHS cluster — 2+ confirmed swing highs within tolerance_atr=0.1 * atr), k=SWING_WINDOW=2
- **Impl:** feature_pipeline.compute_smc_features -> smc.levels.eqh_eql_distance — ['src/features/feature_pipeline.py:1290', 'src/features/smc/levels.py', 'src/features/smc/_geometry.py']
- **PIT:** collect_causal_swings only returns pivots confirmed by k closed later bars (_geometry.py:79-101) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 45']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/smc/levels.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); cluster extension of the single-swing FM-025/026 liquidity reading. PIT classified 2026-09-05

#### 46. `eql_distance`

- **Source OHLCV:** ['low', 'close']
- **Formula:** tanh(signed ATR distance to the most recent member of an EQUAL-LOWS cluster — 2+ confirmed swing lows within tolerance_atr=0.1 * atr), k=SWING_WINDOW=2
- **Impl:** feature_pipeline.compute_smc_features -> smc.levels.eqh_eql_distance — ['src/features/feature_pipeline.py:1290', 'src/features/smc/levels.py', 'src/features/smc/_geometry.py']
- **PIT:** collect_causal_swings only returns pivots confirmed by k closed later bars (_geometry.py:79-101) (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 46']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/feature_pipeline.py', 'src/features/smc/levels.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); PIT classified 2026-09-05

#### 47. `change_of_character`

- **Source OHLCV:** ['high', 'low', 'close']
- **Formula:** break_of_structure if sign(break_of_structure) != sign(trend_bias) and both nonzero, else 0.0
- **Impl:** feature_pipeline.compute_smc_features -> smc.choch.change_of_character — ['src/features/feature_pipeline.py:1303', 'src/features/smc/choch.py']
- **PIT:** stateless algebra over two already-classified canonical slots; inherits the weaker parent (break_of_structure = STRUCTURE_WITH_CAUSAL_SWING), trend_bias is CAUSAL_DERIVED (`STRUCTURE_WITH_CAUSAL_SWING`)
- **Consumers (curated):** ['FeaturePipeline vector index 47']
- **Consumers (static sample):** ['src/features/crt_feature_builder.py', 'src/features/crt_state_resolver.py', 'src/features/feature_pipeline.py', 'src/features/smc/choch.py', 'src/research/clean_labels/builder.py', 'src/research/model_runners/schema_resolver.py', 'src/runtime/bar_structure_snapshot.py', 'src/runtime/live_engine_hook.py', 'src/runtime/live_rail_feeder.py']
- **Note:** schema v5.0 (F-076); adds NO new BOS/CHoCH detection state machine (choch.py:6-15). Registered FM-083 and STATEFUL in the ontology, but named in NO resolver `when:` clause. PIT classified 2026-09-05

## Smoke (frozen XAUUSD)

```json
{
  "status": "PASS",
  "corpus": "data/mt5/XAUUSD_M15.csv",
  "rows_out": 47197,
  "vector_rows": 47197,
  "canonical_columns_present": "48/48",
  "missing_columns": []
}
```

Machine twin: `feature_38_lineage_census-2026-09-05.json` (also refreshed stable `feature_38_lineage_census-2026-07-10.json`)
