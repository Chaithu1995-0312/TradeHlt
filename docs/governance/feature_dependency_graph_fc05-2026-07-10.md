# Feature Dependency Graph FC-0.5

Generated: `2026-07-10T15:48:17Z`

Counts: {
  "contract_entries": 41,
  "complete_direct_bindings": 41,
  "with_nonempty_direct_deps": 21,
  "with_nonempty_transitive_deps": 21,
  "pit_local_causal_or_raw": 27,
  "pit_transitive": {
    "PIT_LOCAL_OK": 25,
    "SEMANTIC_RISK": 3,
    "LEAKING": 12,
    "GLOBAL_FIT_DEPENDENCE": 1
  },
  "leaking": 12,
  "global_fit_dependent": 1,
  "semantic_risk": 3,
  "pit_safe_transitive": 25,
  "unknown_or_unproven": 0
}

## Critical discoveries

- Contract empty direct_feature_dependencies arrays are incomplete; 12+ structure features inherit swing lookahead
- liquidity_distance uses shift(1) on last_swing but last_swing is still non-causal under default center=True
- retest_depth/candles_since_retest inherit liquidity_sweep → swing leak
- volatility_regime global rank is GLOBAL_FIT independent of swing
- volume T-003 mutates source identity before volume_ratio/spike
- disp_strength (FM-020) is causal; retest_depth inherits swing leak via liquidity_sweep
- last_swing_high/last_swing_low are intermediates (not vector members) but feed HH/LL/BOS/liq features

## Nodes (summary)

| feature | direct deps | PIT transitive | lookahead |
|---|---|---|---|
| `open` | [] | `PIT_LOCAL_OK` | 0 |
| `high` | [] | `PIT_LOCAL_OK` | 0 |
| `low` | [] | `PIT_LOCAL_OK` | 0 |
| `close` | [] | `PIT_LOCAL_OK` | 0 |
| `volume` | [] | `SEMANTIC_RISK` | 0 |
| `volume_ratio` | ['volume'] | `SEMANTIC_RISK` | 0 |
| `double_sweep` | ['liquidity_sweep'] | `LEAKING` | 2 |
| `ema_fast` | [] | `PIT_LOCAL_OK` | 0 |
| `ema_slow` | [] | `PIT_LOCAL_OK` | 0 |
| `ema_spread` | ['ema_fast', 'ema_slow', 'atr'] | `PIT_LOCAL_OK` | 0 |
| `trend_bias` | ['ema_fast', 'ema_slow'] | `PIT_LOCAL_OK` | 0 |
| `trend_strength` | [] | `PIT_LOCAL_OK` | 0 |
| `momentum_score` | ['atr'] | `PIT_LOCAL_OK` | 0 |
| `atr` | [] | `PIT_LOCAL_OK` | 0 |
| `volatility_ratio` | ['atr'] | `PIT_LOCAL_OK` | 0 |
| `rsi_14` | [] | `PIT_LOCAL_OK` | 0 |
| `macd_line` | [] | `PIT_LOCAL_OK` | 0 |
| `macd_signal` | ['macd_line'] | `PIT_LOCAL_OK` | 0 |
| `macd_hist` | ['macd_line', 'macd_signal'] | `PIT_LOCAL_OK` | 0 |
| `sweep_detected` | ['liquidity_sweep'] | `LEAKING` | 2 |
| `liquidity_sweep` | ['swing_high', 'swing_low'] | `LEAKING` | 2 |
| `break_of_structure` | ['swing_high', 'swing_low'] | `LEAKING` | 2 |
| `swing_high` | [] | `LEAKING` | 2 |
| `swing_low` | [] | `LEAKING` | 2 |
| `higher_high` | ['swing_high'] | `LEAKING` | 2 |
| `lower_low` | ['swing_low'] | `LEAKING` | 2 |
| `body_size` | [] | `PIT_LOCAL_OK` | 0 |
| `wick_size` | [] | `PIT_LOCAL_OK` | 0 |
| `body_ratio` | ['body_size', 'wick_size'] | `PIT_LOCAL_OK` | 0 |
| `volatility_regime` | ['atr'] | `GLOBAL_FIT_DEPENDENCE` | full_batch |
| `session` | [] | `PIT_LOCAL_OK` | 0 |
| `hour_of_day` | [] | `PIT_LOCAL_OK` | 0 |
| `disp_strength` | ['atr'] | `PIT_LOCAL_OK` | 0 |
| `retest_depth` | ['liquidity_sweep', 'ema_fast', 'atr'] | `LEAKING` | 2 |
| `candles_since_retest` | ['liquidity_sweep'] | `LEAKING` | 2 |
| `liquidity_distance` | ['swing_high', 'swing_low', 'atr'] | `LEAKING` | 2 |
| `liquidity_pressure_score` | ['liquidity_distance'] | `LEAKING` | 2 |
| `volume_spike` | ['volume_ratio'] | `SEMANTIC_RISK` | 0 |
| `volume_range_proxy` | [] | `PIT_LOCAL_OK` | 0 |
| `displacement_retrace` | [] | `PIT_LOCAL_OK` | 0 |
| `displacement_atr_ratio` | [] | `PIT_LOCAL_OK` | 0 |
