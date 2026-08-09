# FM Ownership / Consumer Matrix

> Generated: `2026-07-31T18:36:26Z` · schema v1
>
> **Source script:** `scripts/governance/build_fm_ownership_matrix.py`
>
> **Invariant:** feature-layer `economic_authority` is always `NONE`.
> G001 contribution is tracked only in [`g001_consumer_attribution.md`](g001_consumer_attribution.md).

## Summary

- Features: **52**
- resolve_fm bound: **9**
- With parity floor: **46**
- Without parity floor: **6**

## Consumers (runtime modules)

| Consumer | Path | Role | Bound FMs |
|---|---|---|---|
| `crt_engine_v2` | `src/config_layer/crt_engine_v2.py` | CRT state machine + scoring inputs (hot path) | FM-002, FM-010, FM-027, FM-028, FM-070 |
| `scoring_engine` | `src/engines/scoring_engine.py` | CRT composite score (breakout uses FM-029) | FM-029 |
| `feature_pipeline` | `src/features/feature_pipeline.py` | Batch/live feature vector producer (primary computation for series FMs) | — |
| `causal_structure` | `src/features/causal_structure.py` | Online FC1-A structure + liquidity for FeatureStore | FM-025, FM-026 |
| `crt_feature_builder` | `src/features/crt_feature_builder.py` | BitNet feeder transcriber (historically 0 live callers) | FM-001, FM-002, FM-010 |
| `engine_runner_fusion` | `src/core/engine_runner.py` | Fusion of crt/gaussian/zone_gate/rr scores (consumes scores, not raw FM math) | — |
| `feature_state_encoder_shadow` | `src/features/feature_states.py` | Shadow: numeric → state names (research; not trading gate) | — |

## Features

| FM | Name | Section | Authority | resolve_fm | Semantic | Economic | Tests |
|---|---|---|---|---|---|---|---|
| FM-001 | `body_size` | primitives | FORMULA_REGISTRY | phase3a_feature_builder | SCALAR_PARITY | NONE | test_candle_math.py |
| FM-002 | `candle_range` | primitives | FORMULA_REGISTRY | phase2_crt,phase3a_feature_builder | SCALAR_PARITY | NONE | test_candle_math.py |
| FM-003 | `upper_wick` | primitives | FORMULA_REGISTRY | — | PARITY_FLOOR_PRESENT | NONE | test_candle_math.py |
| FM-004 | `lower_wick` | primitives | FORMULA_REGISTRY | — | PARITY_FLOOR_PRESENT | NONE | test_candle_math.py |
| FM-005 | `total_wick` | primitives | FORMULA_REGISTRY | — | PARITY_FLOOR_PRESENT | NONE | test_candle_math.py |
| FM-010 | `body_ratio` | feature_compositions | COMPOSITION | phase2_crt,phase3a_feature_builder | SCALAR_PARITY | NONE | test_candle_math.py;test_fm_resolution_phase2.py |
| FM-011 | `upper_wick_ratio` | feature_compositions | COMPOSITION | — | NO_PARITY_FLOOR | NONE | — |
| FM-012 | `lower_wick_ratio` | feature_compositions | COMPOSITION | — | NO_PARITY_FLOOR | NONE | — |
| FM-013 | `body_to_total_wick_ratio` | feature_compositions | COMPOSITION | — | NO_PARITY_FLOOR | NONE | — |
| FM-020 | `disp_strength` | derived_metrics | FORMULA_REGISTRY | — | SCALAR_PARITY | NONE | test_derived_math.py |
| FM-021 | `retest_depth` | derived_metrics | FORMULA_REGISTRY | — | SCALAR_PARITY | NONE | test_derived_math.py |
| FM-022 | `ema_spread` | derived_metrics | FORMULA_REGISTRY | — | SCALAR_PARITY | NONE | test_derived_math.py |
| FM-023 | `momentum_score` | derived_metrics | FORMULA_REGISTRY | — | SCALAR_PARITY | NONE | test_derived_math.py |
| FM-024 | `volatility_ratio` | derived_metrics | FORMULA_REGISTRY | — | SCALAR_PARITY | NONE | test_derived_math.py |
| FM-025 | `liquidity_distance` | derived_metrics | FORMULA_REGISTRY | phase3c_causal_structure | SCALAR_PARITY | NONE | test_liquidity_distance.py;test_fm_resolution_phase3.py |
| FM-026 | `liquidity_pressure_score` | derived_metrics | FORMULA_REGISTRY | phase3c_causal_structure | SCALAR_PARITY | NONE | test_liquidity_distance.py;test_fm_resolution_phase3.py |
| FM-027 | `displacement_retrace` | derived_metrics | FORMULA_REGISTRY | phase2_crt | SCALAR_PARITY | NONE | test_fm027_displacement_retrace_certification.py |
| FM-028 | `displacement_atr_ratio` | derived_metrics | FORMULA_REGISTRY | phase2_crt | SCALAR_PARITY | NONE | test_crt_adversarial_closure.py;test_fm_resolution_phase2.py |
| FM-029 | `disp_strength_atr_rescale` | derived_metrics | FORMULA_REGISTRY | phase3b_scoring | SCALAR_PARITY | NONE | test_gd004_gd005_identity_closure.py;test_fm_resolution_phase3.py |
| FM-030 | `ema_spread_atr` | derived_metrics | FORMULA_REGISTRY | — | PARITY_FLOOR_PRESENT | NONE | test_b2a_feature_candidate_certification.py |
| FM-031 | `momentum_score_atr` | derived_metrics | FORMULA_REGISTRY | — | PARITY_FLOOR_PRESENT | NONE | test_b2a_feature_candidate_certification.py |
| FM-040 | `true_range` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-041 | `atr` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-042 | `rsi_14` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-043 | `ema_fast` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-044 | `ema_slow` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-045 | `swing_high` | rolling_indicators | PIPELINE | — | ORACLE_PARITY | NONE | test_fc1a_swing_oracle_parity.py |
| FM-046 | `swing_low` | rolling_indicators | PIPELINE | — | ORACLE_PARITY | NONE | test_fc1a_swing_oracle_parity.py |
| FM-047 | `macd_line` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-048 | `macd_signal` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-049 | `macd_hist_raw` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-050 | `volatility_regime` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py;test_fc1d_volregime_causal.py |
| FM-051 | `hour_of_day` | temporal_context | CALENDAR | — | TEMPORAL_PARITY | NONE | test_feature_temporal_context.py |
| FM-052 | `session` | temporal_context | CALENDAR | — | TEMPORAL_PARITY | NONE | test_feature_temporal_context.py;test_session_classifier.py |
| FM-053 | `macd_hist_z` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-054 | `trend_bias` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-055 | `higher_high` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-056 | `lower_low` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-057 | `break_of_structure` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_PLUS_ORACLE_SCENARIO | NONE | test_feature_structural_states_complex.py;test_fc1a_swing_oracle_parity.py |
| FM-058 | `liquidity_sweep` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_PLUS_ORACLE_SCENARIO | NONE | test_feature_structural_states_complex.py;test_fc1a_swing_oracle_parity.py |
| FM-059 | `sweep_detected` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-060 | `double_sweep` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_PLUS_ORACLE_SCENARIO | NONE | test_feature_structural_states_complex.py |
| FM-061 | `retest_flag` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_PLUS_ORACLE_SCENARIO | NONE | test_feature_structural_states_complex.py |
| FM-062 | `volume_ratio` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_rolling_indicators.py |
| FM-063 | `volume_spike` | rolling_indicators | PIPELINE | — | SERIES_PARITY | NONE | test_feature_volume_spike_parity.py |
| FM-064 | `trend_strength` | rolling_indicators | PIPELINE | — | NO_PARITY_FLOOR | NONE | — |
| FM-065 | `candles_since_retest` | rolling_indicators | PIPELINE | — | NO_PARITY_FLOOR | NONE | — |
| FM-066 | `last_swing_high_price` | rolling_indicators | PIPELINE | — | ORACLE_PARITY | NONE | test_fc1a_swing_oracle_parity.py |
| FM-067 | `last_swing_low_price` | rolling_indicators | PIPELINE | — | ORACLE_PARITY | NONE | test_fc1a_swing_oracle_parity.py |
| FM-068 | `rsi_state` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-069 | `displacement_flag` | structural_states | STRUCTURAL_PIPELINE | — | PARITY_FLOOR_PRESENT | NONE | test_feature_structural_states.py |
| FM-070 | `candles_since_retest_state` | derived_metrics | FORMULA_REGISTRY | phase2_crt | NO_PARITY_FLOOR | NONE | — |

## How to regenerate

```bash
python scripts/governance/build_fm_ownership_matrix.py
python scripts/governance/build_fm_ownership_matrix.py --check
```
