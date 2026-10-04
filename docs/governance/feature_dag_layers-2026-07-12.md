# Feature DAG — Topological Layer Spine (bottom-up certification order)

_Generated 2026-07-12T14:16:44.695066+00:00 · READ-ONLY · 48 nodes, 38/38 canonical covered._

- is_dag: **True** · cycles: none
- ungrounded: none · layer-monotonicity violations: 0
- missing canonical: none
- bug-fixes applied: {'disp_strength_body_size_close_edge': True, 'double_sweep_single_entry': True}

## Layer histogram

- RAW_INPUT: 6
- L0_candle_primitive: 6
- L1_rolling_indicator: 8
- L2_direct_derived: 13
- L3_structural_event: 10
- L4_composite_context: 5

## Nodes by layer then topo index

### RAW_INPUT
- `close` (vec idx 3) ← raw
- `high` (vec idx 1) ← raw
- `low` (vec idx 2) ← raw
- `open` (vec idx 0) ← raw
- `timestamp` ← raw
- `volume` (vec idx 4) ← raw

### L0_candle_primitive
- `body_size` [FM-001] (vec idx 26) ← ['close', 'open']
- `lower_wick` [FM-004] ← ['close', 'low', 'open']
- `true_range` [FM-040] ← ['close', 'high', 'low']
- `upper_wick` [FM-003] ← ['close', 'high', 'open']
- `total_wick` [FM-005] ← ['lower_wick', 'upper_wick']
- `wick_size` [FM-002] (vec idx 27) ← ['high', 'low']

### L1_rolling_indicator
- `ema_fast` [FM-043] (vec idx 7) ← ['close']
- `ema_slow` [FM-044] (vec idx 8) ← ['close']
- `macd_line` (vec idx 16) ← ['close']
- `macd_signal` (vec idx 17) ← ['macd_line']
- `rsi_14` [FM-042] (vec idx 15) ← ['close']
- `swing_high` [FM-045] (vec idx 22) ← ['high']
- `swing_low` [FM-046] (vec idx 23) ← ['low']
- `atr` [FM-041] (vec idx 13) ← ['true_range']

### L2_direct_derived
- `macd_hist` (vec idx 18) ← ['macd_line', 'macd_signal']
- `trend_bias` [FM-TRB] (vec idx 10) ← ['ema_fast', 'ema_slow']
- `disp_strength` [FM-020] (vec idx 32) ← ['atr', 'body_size', 'close']
- `disp_strength_atr_rescale` [FM-029] ← ['atr', 'disp_strength']
- `ema_spread` [FM-022] (vec idx 9) ← ['atr', 'ema_fast', 'ema_slow']
- `ema_spread_atr` [FM-030] ← ['atr', 'close', 'ema_fast', 'ema_slow']
- `momentum_score` [FM-023] (vec idx 12) ← ['atr', 'close']
- `momentum_score_atr` [FM-031] ← ['atr', 'close']
- `volume_ratio` [FM-VOLR] (vec idx 5) ← ['volume']
- `volume_spike` [FM-VOLS] (vec idx 37) ← ['volume_ratio']
- `body_ratio` [FM-010] (vec idx 28) ← ['body_size', 'wick_size']
- `displacement_atr_ratio` [FM-028] ← ['atr', 'wick_size']
- `volatility_ratio` [FM-024] (vec idx 14) ← ['atr', 'close', 'wick_size']

### L3_structural_event
- `displacement_retrace` [FM-027] ← ['close', 'open']
- `higher_high` (vec idx 24) ← ['swing_high']
- `break_of_structure` (vec idx 21) ← ['swing_high', 'swing_low']
- `liquidity_sweep` (vec idx 20) ← ['swing_high', 'swing_low']
- `candles_since_retest` (vec idx 34) ← ['liquidity_sweep']
- `double_sweep` (vec idx 6) ← ['liquidity_sweep']
- `lower_low` (vec idx 25) ← ['swing_low']
- `sweep_detected` (vec idx 19) ← ['liquidity_sweep']
- `liquidity_distance` [FM-025] (vec idx 35) ← ['atr', 'break_of_structure', 'close', 'swing_high', 'swing_low']
- `retest_depth` [FM-021] (vec idx 33) ← ['atr', 'ema_fast', 'liquidity_sweep']

### L4_composite_context
- `hour_of_day` (vec idx 31) ← ['timestamp']
- `session` (vec idx 30) ← ['timestamp']
- `trend_strength` (vec idx 11) ← ['close']
- `liquidity_pressure_score` [FM-026] (vec idx 36) ← ['liquidity_distance']
- `volatility_regime` (vec idx 29) ← ['atr']

