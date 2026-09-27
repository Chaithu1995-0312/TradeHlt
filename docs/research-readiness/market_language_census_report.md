# Market Language Census (deterministic)

Generated: `2026-09-19T21:00:11.494921+00:00`

## Authority files (every emitted word is cited to one of these)
- `configs/formulas/market_ontology.yaml`
- `configs/formulas/market_crt_states.yaml`
- `configs/formulas/crt_state_identity.yaml`
- `configs/formulas/market_shapes.yaml`
- `src/features/feature_schema.py`

## S1 — Feature schema
| name | fm_id | section | lifecycle | formula/source | vector_index | n_states |
|---|---|---|---|---|---|---|
| open | FM-085 | source_inputs | registered | 'identity — raw bar-open price as ingested from the broker/data feed; no transform' | 0 | 0 |
| high | FM-086 | source_inputs | registered | 'identity — raw bar-high price as ingested from the broker/data feed; no transform' | 1 | 0 |
| low | FM-087 | source_inputs | registered | 'identity — raw bar-low price as ingested from the broker/data feed; no transform' | 2 | 0 |
| close | FM-088 | source_inputs | registered | 'identity — raw bar-close price as ingested from the broker/data feed; no transform' | 3 | 0 |
| volume | FM-089 | source_inputs | registered | 'identity — raw bar volume as ingested from the broker/data feed; no transform' | 4 | 0 |
| body_size | FM-001 | primitives | consumable | 'abs(close - open)' | 27 | 0 |
| candle_range | FM-002 | primitives | consumable | 'high - low' | 28 | 0 |
| upper_wick | FM-003 | primitives | parity_verified | 'high - max(open, close)' | [] | 0 |
| lower_wick | FM-004 | primitives | parity_verified | 'min(open, close) - low' | [] | 0 |
| total_wick | FM-005 | primitives | parity_verified | 'upper_wick + lower_wick' | [] | 0 |
| body_ratio | FM-010 | feature_compositions | consumable | 'body_size/candle_range' | 29 | 0 |
| body_to_total_wick_ratio | FM-013 | feature_compositions | registered | 'candle_math.body_to_total_wick_ratio' | [] | 0 |
| upper_wick_ratio | FM-011 | feature_compositions | research | 'upper_wick/candle_range' | [] | 0 |
| lower_wick_ratio | FM-012 | feature_compositions | research | 'lower_wick/candle_range' | [] | 0 |
| disp_strength | FM-020 | derived_metrics | parity_verified | 'clip(body_size / (atr * close), <feature_pipeline.disp_strength_clip_low>, <feature_pipeline.disp_strength_clip_high>) if atr>0 and close>0 else nan  # defaults 0.0, 3.0' | 33 | 0 |
| retest_depth | FM-021 | derived_metrics | parity_verified | 'clip(abs(close - ema_fast) / (atr * close), <feature_pipeline.retest_depth_clip_low>, <feature_pipeline.retest_depth_clip_high>) if retest_flag==1 and atr>0 and close>0 else 0.0  # defaults 0.0, 1.0' | 34 | 0 |
| ema_spread | FM-022 | derived_metrics | parity_verified | "(ema_fast - ema_slow) / atr if atr>0 else nan   # emitted only when <feature_pipeline.normalization_basis> == 'atr_relative' (the default); 'atr_absolute' selects FM-030 instead" | 9 | 0 |
| momentum_score | FM-023 | derived_metrics | parity_verified | "close_delta / atr if atr>0 else nan   # close_delta = close.diff(); emitted only when <feature_pipeline.normalization_basis> == 'atr_relative' (the default); 'atr_absolute' selects FM-031 instead" | 12 | 0 |
| ema_spread_atr | FM-030 | derived_metrics | parity_verified | "(ema_fast - ema_slow) / (atr * close) if atr>0 and close>0 else nan   # emitted only when <feature_pipeline.normalization_basis> == 'atr_absolute'; the default 'atr_relative' selects FM-022 instead" | [] | 0 |
| momentum_score_atr | FM-031 | derived_metrics | parity_verified | "close_delta / (atr * close) if atr>0 and close>0 else nan   # close_delta = close.diff(); emitted only when <feature_pipeline.normalization_basis> == 'atr_absolute'; the default 'atr_relative' selects FM-023 instead" | [] | 0 |
| volatility_ratio | FM-024 | derived_metrics | parity_verified | '(high - low) / (atr * close) if atr>0 and close>0 else 1.0' | 14 | 0 |
| liquidity_distance | FM-025 | derived_metrics | registered | 'min over levels of abs(close - level) / (atr * close), clipped >= 0; nan if atr*close<=0 or no finite level' | 36 | 0 |
| liquidity_pressure_score | FM-026 | derived_metrics | registered | 'clip(exp(<feature_pipeline.liquidity_decay_coeff> * liquidity_distance), 0.0, 1.0); nan distance -> treated as <feature_pipeline.liquidity_nan_sentinel>  # defaults -0.5, 10.0' | 37 | 0 |
| displacement_retrace | FM-027 | derived_metrics | registered | 'clip(|retest_close - disp_open| / |disp_close - disp_open|, 0.0, 1.0); disp body 0 -> skip' | [] | 0 |
| displacement_atr_ratio | FM-028 | derived_metrics | registered | 'candle_range / atr_abs; atr_abs<=0 -> 0.0  # atr_abs = SMA(period) of true_range, ABSOLUTE price units (state.atr_abs, now registered as FM-074 atr_absolute), NOT the close-relative FM-041 `atr`' | [] | 0 |
| disp_strength_atr_rescale | FM-029 | derived_metrics | registered | 'disp_strength / atr; atr<=0 -> 0.0' | [] | 0 |
| candles_since_retest_state | FM-070 | derived_metrics | registered | 'current_candle_index - retest_candle_index' | [] | 0 |
| order_block_distance | FM-075 | derived_metrics | registered | 'tanh(sign * (close - order_block_zone_edge) / atr); 0.0 if no active OB or atr<=0' | 39 | 0 |
| fvg_distance | FM-076 | derived_metrics | registered | 'tanh(sign * (close - fvg_zone_edge) / atr); 0.0 if no active FVG or atr<=0' | 40 | 0 |
| breaker_distance | FM-077 | derived_metrics | registered | 'tanh(sign * (close - breaker_zone_edge) / atr); 0.0 if no active breaker or atr<=0' | 41 | 0 |
| mitigation_block_distance | FM-078 | derived_metrics | registered | 'tanh(sign * (close - mitigation_zone_edge) / atr); 0.0 if no live mitigation block or atr<=0' | 42 | 0 |
| pdh_distance | FM-079 | derived_metrics | registered | 'tanh(-(close - prev_day_high) / atr); 0.0 if no closed D1 parent yet or atr<=0' | 43 | 0 |
| pdl_distance | FM-080 | derived_metrics | registered | 'tanh((close - prev_day_low) / atr); 0.0 if no closed D1 parent yet or atr<=0' | 44 | 0 |
| eqh_distance | FM-081 | derived_metrics | registered | 'tanh(-(close - eqh_level) / atr); 0.0 if no equal-highs cluster found or atr<=0' | 45 | 0 |
| eql_distance | FM-082 | derived_metrics | registered | 'tanh((close - eql_level) / atr); 0.0 if no equal-lows cluster found or atr<=0' | 46 | 0 |
| true_range | FM-040 | rolling_indicators | registered | 'max(high - low, abs(high - prev_close), abs(low - prev_close))' | [] | 0 |
| atr | FM-041 | rolling_indicators | registered | 'SMA(<feature_pipeline.atr_period>) of true_range, close-relative: atr_14_raw / close (atr_14_raw = true_range.rolling(<feature_pipeline.atr_period>).mean())  # default 14' | 13 | 0 |
| atr_absolute | FM-074 | rolling_indicators | registered | 'SMA(<feature_pipeline.atr_period>) of true_range, ABSOLUTE price units (no division by close): true_range.rolling(<feature_pipeline.atr_period>).mean()  # default 14' | [] | 0 |
| rsi_14 | FM-042 | rolling_indicators | registered | '100 - 100/(1+RS); RS = SMA(<feature_pipeline.rsi_period>) gain / (SMA(<feature_pipeline.rsi_period>) loss + 1e-9); clipped [0,100]  # default period 14' | 15 | 0 |
| ema_fast | FM-043 | rolling_indicators | registered | 'close.ewm(span=<feature_pipeline.ema_fast_span>, adjust=False).mean()  # default 9' | 7 | 0 |
| ema_slow | FM-044 | rolling_indicators | registered | 'close.ewm(span=<feature_pipeline.ema_slow_span>, adjust=False).mean()  # default 21' | 8 | 0 |
| swing_high | FM-045 | rolling_indicators | registered | 'causal DELAYED publication of a centered rolling-max swing high over width 2k+1 (FC1-A: math at t, published with k-bar delay, available_at = t+k); k = <feature_pipeline.swing_window>  # default 2' | 23 | 2 |
| swing_low | FM-046 | rolling_indicators | registered | 'causal DELAYED publication of a centered rolling-min swing low over width 2k+1 (FC1-A); k = <feature_pipeline.swing_window>  # default 2' | 24 | 2 |
| macd_line | FM-047 | rolling_indicators | registered | 'close.ewm(span=<feature_pipeline.macd_fast>, adjust=False).mean() - close.ewm(span=<feature_pipeline.macd_slow>, adjust=False).mean()  # defaults 12, 26' | 16 | 0 |
| macd_signal | FM-048 | rolling_indicators | registered | 'macd_line.ewm(span=<feature_pipeline.macd_signal>, adjust=False).mean()  # default 9' | 17 | 0 |
| macd_hist_raw | FM-049 | rolling_indicators | registered | 'macd_line - macd_signal' | 18 | 0 |
| macd_hist_z | FM-053 | rolling_indicators | registered | 'rolling(<feature_pipeline.zscore_window>) z-score of macd_hist_raw  # default 50' | 19 | 0 |
| trend_strength_z | FM-064 | rolling_indicators | registered | 'rolling(<feature_pipeline.zscore_window>) z-score of SMA(<feature_pipeline.trend_strength_window>) of diff(SMA(<feature_pipeline.ma_periods[0]>) of close)  # defaults 50, 10, 20' | 11 | 0 |
| trend_strength_raw | FM-084 | rolling_indicators | registered | 'SMA(<feature_pipeline.trend_strength_window>) of diff(SMA(<feature_pipeline.ma_periods[0]>) of close)  # defaults 10, 20' | [] | 0 |
| volatility_regime | FM-050 | rolling_indicators | registered | 'tercile(atr_14.rolling(<feature_pipeline.volatility_percentile_window>, min_periods=1).rank(pct=True)); atr_14 = SMA(14) of true_range (ABSOLUTE); cuts at <feature_pipeline.volatility_tercile_low>/<feature_pipeline.volatility_tercile_high> -> int8 {0,1,2}  # defaults 200, 0.33/0.66' | 30 | 3 |
| volume_ratio | FM-062 | rolling_indicators | registered | 'volume / SMA(volume, <feature_pipeline.volume_ma_window>); 1.0 where the moving average is <= 0  # default 20' | 5 | 0 |
| volume_spike | FM-063 | rolling_indicators | registered | 'volume_ratio > rolling(<feature_pipeline.volume_spike_adaptive_window>, min_periods=<feature_pipeline.volume_spike_min_samples>).quantile(<feature_pipeline.volume_spike_percentile>/100); where that threshold is NaN fall back to <feature_pipeline.volume_spike_fixed_fallback> -> int8 {0, 1}  # defaults 50, 20, 75, 1.5' | 38 | 2 |
| candles_since_sweep | FM-065 | rolling_indicators | registered | 'cumcount of bars since the last liquidity_sweep event (groupby (liquidity_sweep != 0).cumsum()); 0 before the first sweep. Falls back to a retest_flag-keyed grouping ONLY when liquidity_sweep is absent from the frame (feature_pipeline.py:988-991) — non-authoritative, unreachable in production per the certification ledger.' | 35 | 0 |
| last_swing_high_price | FM-066 | rolling_indicators | registered | 'forward-fill of high where the centered swing-high pivot fired, then shifted by k = <feature_pipeline.swing_window> (FC1-A causal publication)  # default 2' | [] | 0 |
| last_swing_low_price | FM-067 | rolling_indicators | registered | 'forward-fill of low where the centered swing-low pivot fired, then shifted by k = <feature_pipeline.swing_window> (FC1-A causal publication)  # default 2' | [] | 0 |
| hour_of_day | FM-051 | temporal_context | registered | 'timestamp.dt.hour -> int8' | 32 | 0 |
| session | FM-052 | temporal_context | registered | 'window model over <feature_pipeline.session_windows_utc>, half-open [start, end): OVERLAP if in LONDON and NEWYORK; else NEWYORK; else LONDON; else ASIA; else CLOSED -> int8  # defaults ASIA [0,9) LONDON [7,16) NEWYORK [12,21)' | 31 | 5 |
| trend_bias | FM-054 | structural_states | registered | 'sign(ema_fast - ema_slow) -> float32 {-1, 0, +1}' | 10 | 3 |
| higher_high | FM-055 | structural_states | registered | 'high > prev(last_swing_high_price) -> int8 {0, 1}; NaN reference compares False' | 25 | 2 |
| lower_low | FM-056 | structural_states | registered | 'low < prev(last_swing_low_price) -> int8 {0, 1}; NaN reference compares False' | 26 | 2 |
| break_of_structure | FM-057 | structural_states | registered | '+1 if close > prev(last_swing_high_price); -1 if close < prev(last_swing_low_price); else 0 -> int8' | 22 | 3 |
| liquidity_sweep | FM-058 | structural_states | registered | '+1 if high > ref_high and close <= ref_high; -1 if low < ref_low and close >= ref_low; else 0 -> int8   # ref_* = prev(last_swing_*_price)' | 21 | 3 |
| sweep_detected | FM-059 | structural_states | registered | 'liquidity_sweep != 0 -> int8 {0, 1}' | 20 | 2 |
| double_sweep | FM-060 | structural_states | registered | 'any(liquidity_sweep > 0) and any(liquidity_sweep < 0) over rolling(<feature_pipeline.double_sweep_window>, min_periods=1) -> int8 {0, 1}  # default 5' | 6 | 2 |
| retest_flag | FM-061 | structural_states | registered | 'rolling_any(liquidity_sweep != 0, <feature_pipeline.retest_lookback>) and abs(close - ema_fast) <= <feature_pipeline.retest_atr_band_mult> * atr * close -> int8 {0, 1}  # defaults 10, 1.0' | [] | 2 |
| rsi_state | FM-068 | structural_states | registered | '+1 if rsi_14 > <feature_pipeline.rsi_overbought>; -1 if rsi_14 < <feature_pipeline.rsi_oversold>; else 0 -> int8  # defaults 70, 30' | [] | 3 |
| displacement_flag | FM-069 | structural_states | registered | 'body_size > candle_range * <feature_pipeline.displacement_strong_body_mult> and atr > 0 -> int8 {0, 1}  # default 0.6' | [] | 2 |
| body_commitment | FM-071 | structural_states | research | 'bin(body_ratio; band_edges) -> int8 {0,1,2}  # identity transform; edges ontology-owned' | [] | 3 |
| atr_magnitude | FM-072 | structural_states | research | 'bin(percentile_rank(atr | series); band_edges) -> int8 {0,1,2}  # series percentile of FM-041 relative atr' | [] | 3 |
| momentum_magnitude | FM-073 | structural_states | research | 'bin(percentile_rank(|momentum_score| | series); band_edges) -> int8 {0,1,2}  # F-061: never fixed abs edges on legacy FM-023' | [] | 3 |
| change_of_character | FM-083 | structural_states | registered | 'break_of_structure if sign(break_of_structure) != sign(trend_bias) and both nonzero, else 0' | 47 | 3 |

## S2 — State schema (four distinct vocabularies, never merged)
### `crt_machine` — CRT engine/resolver lifecycle states (constructor-neutral identity).  (12)
| state | parent | activation | source |
|---|---|---|---|
| RANGE |  | "liquidity_sweep=['NoSweep'] AND break_of_structure=['NoBreak'] AND sweep_detected=['NoSweep'] AND displacement_flag=['NoDisplacement'] AND double_sweep=['NoDoubleSweep'] AND higher_high=['NoHigherHigh'] AND lower_low=['NoLowerLow'] AND retest_flag=['NoRetest'] AND swing_high=['NoSwingHigh'] AND swing_low=['NoSwingLow']" | configs/formulas/crt_state_identity.yaml |
| SHADOW_PENDING |  | None | configs/formulas/crt_state_identity.yaml |
| SWEEP |  | "liquidity_sweep=['SellSideSweep', 'BuySideSweep'] AND break_of_structure=['NoBreak'] AND displacement_flag=['NoDisplacement']" | configs/formulas/crt_state_identity.yaml |
| DISPLACEMENT |  | "displacement_flag=['Displacement'] AND change_of_character={'states': ['BullishCHoCH', 'BearishCHoCH'], 'link': 'LINK-001'}" | configs/formulas/crt_state_identity.yaml |
| EXPANSION |  | "displacement_flag=['Displacement']" | configs/formulas/crt_state_identity.yaml |
| EXPIRED |  | None | configs/formulas/crt_state_identity.yaml |
| RETEST |  | "retest_flag=['RetestActive'] AND sweep_detected=['SweepDetected'] AND break_of_structure=['NoBreak']" | configs/formulas/crt_state_identity.yaml |
| EXECUTION |  | "retest_flag=['RetestActive'] AND trend_bias=['Bullish', 'Bearish'] AND rsi_state=['NeutralMomentum'] AND session=['LONDON', 'NEWYORK', 'OVERLAP']" | configs/formulas/crt_state_identity.yaml |
| RESOLUTION |  | None | configs/formulas/crt_state_identity.yaml |
| RANGE_C1 |  | None | configs/formulas/crt_state_identity.yaml |
| MANIPULATION_C2 |  | None | configs/formulas/crt_state_identity.yaml |
| DISTRIBUTION_C3 |  | None | configs/formulas/crt_state_identity.yaml |

### `feature_enum` — Feature-value -> meaning map declared in ontology states blocks (name/value/condition/description shape).  (36)
| state | parent | activation | source |
|---|---|---|---|
| Bearish | trend_bias | 'ema_fast < ema_slow' | configs/formulas/market_ontology.yaml |
| Neutral | trend_bias | 'ema_fast == ema_slow' | configs/formulas/market_ontology.yaml |
| Bullish | trend_bias | 'ema_fast > ema_slow' | configs/formulas/market_ontology.yaml |
| NoHigherHigh | higher_high | 'high <= previous last_swing_high_price, or no reference exists yet' | configs/formulas/market_ontology.yaml |
| HigherHigh | higher_high | 'high > previous last_swing_high_price' | configs/formulas/market_ontology.yaml |
| NoLowerLow | lower_low | 'low >= previous last_swing_low_price, or no reference exists yet' | configs/formulas/market_ontology.yaml |
| LowerLow | lower_low | 'low < previous last_swing_low_price' | configs/formulas/market_ontology.yaml |
| BearishBreak | break_of_structure | 'close < previous last_swing_low_price' | configs/formulas/market_ontology.yaml |
| NoBreak | break_of_structure | 'close within the prior structural range' | configs/formulas/market_ontology.yaml |
| BullishBreak | break_of_structure | 'close > previous last_swing_high_price' | configs/formulas/market_ontology.yaml |
| SellSideSweep | liquidity_sweep | 'low < ref_low and close >= ref_low' | configs/formulas/market_ontology.yaml |
| NoSweep | liquidity_sweep | 'neither sweep condition met' | configs/formulas/market_ontology.yaml |
| BuySideSweep | liquidity_sweep | 'high > ref_high and close <= ref_high' | configs/formulas/market_ontology.yaml |
| NoSweep | sweep_detected | 'liquidity_sweep == 0' | configs/formulas/market_ontology.yaml |
| SweepDetected | sweep_detected | 'liquidity_sweep != 0' | configs/formulas/market_ontology.yaml |
| NoDoubleSweep | double_sweep | 'at most one sweep direction present in the trailing window' | configs/formulas/market_ontology.yaml |
| DoubleSweep | double_sweep | 'both a positive and a negative liquidity_sweep within the trailing window' | configs/formulas/market_ontology.yaml |
| NoRetest | retest_flag | 'no sweep within retest_lookback bars, or |close - ema_fast| outside the ATR band' | configs/formulas/market_ontology.yaml |
| RetestActive | retest_flag | 'sweep within retest_lookback bars AND |close - ema_fast| <= retest_atr_band_mult * atr * close' | configs/formulas/market_ontology.yaml |
| Oversold | rsi_state | 'rsi_14 < rsi_oversold' | configs/formulas/market_ontology.yaml |
| NeutralMomentum | rsi_state | 'rsi_oversold <= rsi_14 <= rsi_overbought' | configs/formulas/market_ontology.yaml |
| Overbought | rsi_state | 'rsi_14 > rsi_overbought' | configs/formulas/market_ontology.yaml |
| NoDisplacement | displacement_flag | 'body_size <= candle_range * displacement_strong_body_mult, or atr <= 0' | configs/formulas/market_ontology.yaml |
| Displacement | displacement_flag | 'body_size > candle_range * displacement_strong_body_mult and atr > 0' | configs/formulas/market_ontology.yaml |
| LowCommitment | body_commitment | 'body_ratio < band_edges[0] (default 0.33)' | configs/formulas/market_ontology.yaml |
| MediumCommitment | body_commitment | 'band_edges[0] <= body_ratio < band_edges[1]' | configs/formulas/market_ontology.yaml |
| HighCommitment | body_commitment | 'body_ratio >= band_edges[1] (default 0.70, CRT displacement-coherent)' | configs/formulas/market_ontology.yaml |
| LowAtrMagnitude | atr_magnitude | 'percentile_rank(atr) < band_edges[0]' | configs/formulas/market_ontology.yaml |
| MediumAtrMagnitude | atr_magnitude | 'band_edges[0] <= percentile_rank(atr) < band_edges[1]' | configs/formulas/market_ontology.yaml |
| HighAtrMagnitude | atr_magnitude | 'percentile_rank(atr) >= band_edges[1]' | configs/formulas/market_ontology.yaml |
| LowMomentumMagnitude | momentum_magnitude | 'percentile_rank(|momentum_score|) < band_edges[0]' | configs/formulas/market_ontology.yaml |
| MediumMomentumMagnitude | momentum_magnitude | 'band_edges[0] <= percentile_rank(|momentum_score|) < band_edges[1]' | configs/formulas/market_ontology.yaml |
| HighMomentumMagnitude | momentum_magnitude | 'percentile_rank(|momentum_score|) >= band_edges[1]' | configs/formulas/market_ontology.yaml |
| BearishCHoCH | change_of_character | 'break_of_structure < 0 and trend_bias > 0' | configs/formulas/market_ontology.yaml |
| NoCHoCH | change_of_character | 'break_of_structure == 0 or trend_bias == 0 or sign(break_of_structure) == sign(trend_bias)' | configs/formulas/market_ontology.yaml |
| BullishCHoCH | change_of_character | 'break_of_structure > 0 and trend_bias < 0' | configs/formulas/market_ontology.yaml |

### `smc_choch` — SMC structural signal (CHoCH) — a signed combination, NOT a state machine.  (1)
| state | parent | activation | source |
|---|---|---|---|
| change_of_character |  | 'break_of_structure != 0 and trend_bias != 0 and sign(break_of_structure) != sign(trend_bias)' | src/features/smc/choch.py |

## S6 — Duplicates / overlaps (surfaced, not normalised)
### Exact-name overlaps (same word reused in >=2 vocabularies)
| word | appears in |
|---|---|
| DISPLACEMENT | state/crt_machine, state/feature_enum |

### Concept-token overlaps (linguistic stem shared across vocabularies)
| stem | vocabularies | member words |
|---|---|---|
| atr | feature/derived_metrics, feature/rolling_indicators, feature/structural_states, state/feature_enum | atr, atr_absolute, atr_magnitude, disp_strength_atr_rescale, displacement_atr_ratio, ema_spread_atr, highatrmagnitude, lowatrmagnitude, mediumatrmagnitude, momentum_score_atr |
| bearish | shape/shape_layer, state/feature_enum | bearish, bearishbreak, bearishbreakoutexpansion, bearishchoch, bearishstructuralbreak |
| body | feature/feature_compositions, feature/primitives, feature/structural_states | body_commitment, body_ratio, body_size, body_to_total_wick_ratio |
| break | feature/structural_states, shape/shape_layer, state/feature_enum | bearishbreak, bearishstructuralbreak, break_of_structure, bullishbreak, bullishstructuralbreak, nobreak |
| breakout | shape/shape_layer, trade/intent | bearishbreakoutexpansion, breakout, bullishbreakoutexpansion |
| bullish | shape/shape_layer, state/feature_enum | bullish, bullishbreak, bullishbreakoutexpansion, bullishchoch, bullishstructuralbreak |
| buy | shape/shape_layer, state/feature_enum | buysideliquiditygrab, buysidesweep |
| candles | feature/derived_metrics, feature/rolling_indicators, trade/record_field | candles_since_retest_state, candles_since_sweep, duration_candles |
| commitment | feature/structural_states, state/feature_enum | body_commitment, highcommitment, lowcommitment, mediumcommitment |
| detected | feature/structural_states, state/feature_enum | sweep_detected, sweepdetected |
| displacement | feature/derived_metrics, feature/structural_states, state/crt_machine, state/feature_enum | displacement, displacement_atr_ratio, displacement_flag, displacement_retrace, nodisplacement |
| double | feature/structural_states, shape/shape_layer, state/feature_enum | double_sweep, doublesweep, doublesweeptrap, nodoublesweep |
| ema | feature/derived_metrics, feature/rolling_indicators | ema_fast, ema_slow, ema_spread, ema_spread_atr |
| entry | trade/geometry, trade/intent, trade/record_field | drawdown_at_entry, entry_price, entry_price_fill, entry_price_plan |
| expansion | shape/shape_layer, state/crt_machine | bearishbreakoutexpansion, bullishbreakoutexpansion, expansion |
| high | feature/rolling_indicators, feature/source_inputs, feature/structural_states, state/feature_enum | high, highatrmagnitude, highcommitment, higher_high, higherhigh, highmomentummagnitude, last_swing_high_price, nohigherhigh, swing_high |
| higher | feature/structural_states, state/feature_enum | higher_high, higherhigh, nohigherhigh |
| liquidity | feature/derived_metrics, feature/structural_states, shape/shape_layer | buysideliquiditygrab, liquidity_distance, liquidity_pressure_score, liquidity_sweep, sellsideliquiditygrab |
| low | feature/rolling_indicators, feature/source_inputs, feature/structural_states, state/feature_enum | last_swing_low_price, low, lowatrmagnitude, lowcommitment, lower_low, lowerlow, lowmomentummagnitude, nolowerlow, swing_low |
| lower | feature/feature_compositions, feature/primitives, feature/structural_states, state/feature_enum | lower_low, lower_wick, lower_wick_ratio, lowerlow, nolowerlow |
| magnitude | feature/structural_states, state/feature_enum | atr_magnitude, highatrmagnitude, highmomentummagnitude, lowatrmagnitude, lowmomentummagnitude, mediumatrmagnitude, mediummomentummagnitude, momentum_magnitude |
| momentum | feature/derived_metrics, feature/structural_states, state/feature_enum | highmomentummagnitude, lowmomentummagnitude, mediummomentummagnitude, momentum_magnitude, momentum_score, momentum_score_atr, neutralmomentum |
| of | feature/structural_states, feature/temporal_context, state/smc_choch | break_of_structure, change_of_character, hour_of_day |
| price | feature/rolling_indicators, trade/geometry, trade/intent | entry_price, entry_price_fill, entry_price_plan, last_swing_high_price, last_swing_low_price, sl_price, tp1_price, tp2_price |
| range | feature/primitives, feature/rolling_indicators, state/crt_machine | candle_range, range, range_c1, true_range |
| ratio | feature/derived_metrics, feature/feature_compositions, feature/rolling_indicators, trade/geometry | body_ratio, body_to_total_wick_ratio, displacement_atr_ratio, lower_wick_ratio, rr_ratio, upper_wick_ratio, volatility_ratio, volume_ratio |
| regime | feature/rolling_indicators, trade/record_field | regime, volatility_regime |
| retest | feature/derived_metrics, feature/structural_states, state/crt_machine, state/feature_enum | candles_since_retest_state, noretest, retest, retest_depth, retest_flag, retestactive |
| risk | trade/geometry, trade/record_field | allocated_risk, risk_pct |
| rr | trade/geometry, trade/record_field | rr, rr_ratio |
| rsi | feature/rolling_indicators, feature/structural_states | rsi_14, rsi_state |
| sell | shape/shape_layer, state/feature_enum | sellsideliquiditygrab, sellsidesweep |
| side | shape/shape_layer, state/feature_enum | buysideliquiditygrab, buysidesweep, sellsideliquiditygrab, sellsidesweep |
| since | feature/derived_metrics, feature/rolling_indicators | candles_since_retest_state, candles_since_sweep |
| state | feature/derived_metrics, feature/structural_states | candles_since_retest_state, rsi_state |
| strength | feature/derived_metrics, feature/rolling_indicators | disp_strength, disp_strength_atr_rescale, trend_strength_raw, trend_strength_z |
| sweep | feature/rolling_indicators, feature/structural_states, shape/shape_layer, state/crt_machine, state/feature_enum, trade/intent | buysidesweep, candles_since_sweep, double_sweep, doublesweep, doublesweeptrap, liq_sweep, liquidity_sweep, nodoublesweep, nosweep, sellsidesweep, sweep, sweep_detected, sweepdetected |
| total | feature/feature_compositions, feature/primitives | body_to_total_wick_ratio, total_wick |
| trade | trade/geometry, trade/record_field | trade, trade_id |
| trend | feature/rolling_indicators, feature/structural_states | trend_bias, trend_strength_raw, trend_strength_z |
| upper | feature/feature_compositions, feature/primitives | upper_wick, upper_wick_ratio |
| volatility | feature/derived_metrics, feature/rolling_indicators | volatility_ratio, volatility_regime |
| volume | feature/rolling_indicators, feature/source_inputs | volume, volume_ratio, volume_spike |
| wick | feature/feature_compositions, feature/primitives | body_to_total_wick_ratio, lower_wick, lower_wick_ratio, total_wick, upper_wick, upper_wick_ratio |

## S7 — Orphans
- features with no declared state: `atr, atr_absolute, body_ratio, body_size, body_to_total_wick_ratio, breaker_distance, candle_range, candles_since_retest_state, candles_since_sweep, disp_strength, disp_strength_atr_rescale, displacement_atr_ratio, displacement_retrace, ema_fast, ema_slow, ema_spread, ema_spread_atr, eqh_distance, eql_distance, fvg_distance, hour_of_day, last_swing_high_price, last_swing_low_price, liquidity_distance, liquidity_pressure_score, lower_wick, lower_wick_ratio, macd_hist_raw, macd_hist_z, macd_line, macd_signal, mitigation_block_distance, momentum_score, momentum_score_atr, order_block_distance, pdh_distance, pdl_distance, retest_depth, rsi_14, total_wick, trend_strength_raw, trend_strength_z, true_range, upper_wick, upper_wick_ratio, volatility_ratio, volume_ratio`
- shape predicates referencing an undefined feature-state: `[{'shape': 'BearishBreakoutExpansion', 'ref_key': 'break_of_structure'}, {'shape': 'BearishBreakoutExpansion', 'ref_key': 'volatility_regime'}, {'shape': 'BearishStructuralBreak', 'ref_key': 'break_of_structure'}, {'shape': 'BullishBreakoutExpansion', 'ref_key': 'break_of_structure'}, {'shape': 'BullishBreakoutExpansion', 'ref_key': 'volatility_regime'}, {'shape': 'BullishStructuralBreak', 'ref_key': 'break_of_structure'}, {'shape': 'BuySideLiquidityGrab', 'ref_key': 'liquidity_sweep'}, {'shape': 'Compression', 'ref_key': 'break_of_structure'}, {'shape': 'Compression', 'ref_key': 'double_sweep'}, {'shape': 'Compression', 'ref_key': 'higher_high'}, {'shape': 'Compression', 'ref_key': 'liquidity_sweep'}, {'shape': 'Compression', 'ref_key': 'lower_low'}, {'shape': 'Compression', 'ref_key': 'volatility_regime'}, {'shape': 'DoubleSweepTrap', 'ref_key': 'double_sweep'}, {'shape': 'SellSideLiquidityGrab', 'ref_key': 'liquidity_sweep'}]`

## S8 — Canonical vocabulary
| word | type | parent | vocabulary | source_file |
|---|---|---|---|---|
| allocated_risk | trade |  | trade/record_field | src/journal/schema.py |
| atr | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| atr_absolute | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| atr_magnitude | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| Bearish | state | trend_bias | feature_enum | configs/formulas/market_ontology.yaml |
| BearishBreak | state | break_of_structure | feature_enum | configs/formulas/market_ontology.yaml |
| BearishBreakoutExpansion | shape | BreakoutExpansion | shape_layer | configs/formulas/market_shapes.yaml |
| BearishCHoCH | state | change_of_character | feature_enum | configs/formulas/market_ontology.yaml |
| BearishStructuralBreak | shape | StructuralBreak | shape_layer | configs/formulas/market_shapes.yaml |
| body_commitment | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| body_ratio | feature | feature_compositions | feature_schema | configs/formulas/market_ontology.yaml |
| body_size | feature | primitives | feature_schema | configs/formulas/market_ontology.yaml |
| body_to_total_wick_ratio | feature | feature_compositions | feature_schema | configs/formulas/market_ontology.yaml |
| breaker_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| BREAKOUT | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| break_of_structure | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| Bullish | state | trend_bias | feature_enum | configs/formulas/market_ontology.yaml |
| BullishBreak | state | break_of_structure | feature_enum | configs/formulas/market_ontology.yaml |
| BullishBreakoutExpansion | shape | BreakoutExpansion | shape_layer | configs/formulas/market_shapes.yaml |
| BullishCHoCH | state | change_of_character | feature_enum | configs/formulas/market_ontology.yaml |
| BullishStructuralBreak | shape | StructuralBreak | shape_layer | configs/formulas/market_shapes.yaml |
| BuySideLiquidityGrab | shape | LiquidityGrab | shape_layer | configs/formulas/market_shapes.yaml |
| BuySideSweep | state | liquidity_sweep | feature_enum | configs/formulas/market_ontology.yaml |
| candles_since_retest_state | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| candles_since_sweep | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| candle_range | feature | primitives | feature_schema | configs/formulas/market_ontology.yaml |
| change_of_character | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| change_of_character | state |  | smc_choch | src/features/smc/choch.py |
| close | feature | source_inputs | feature_schema | configs/formulas/market_ontology.yaml |
| Compression | shape | Compression | shape_layer | configs/formulas/market_shapes.yaml |
| confidence | trade |  | trade/record_field | src/journal/schema.py |
| config_profile | trade |  | trade/record_field | src/journal/schema.py |
| CONTINUATION | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| DISPLACEMENT | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| Displacement | state | displacement_flag | feature_enum | configs/formulas/market_ontology.yaml |
| displacement_atr_ratio | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| displacement_flag | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| displacement_retrace | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| disp_strength | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| disp_strength_atr_rescale | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| DISTRIBUTION_C3 | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| DoubleSweep | state | double_sweep | feature_enum | configs/formulas/market_ontology.yaml |
| DoubleSweepTrap | shape | LiquidityTrap | shape_layer | configs/formulas/market_shapes.yaml |
| double_sweep | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| drawdown_at_entry | trade |  | trade/record_field | src/journal/schema.py |
| duration_candles | trade |  | trade/record_field | src/journal/schema.py |
| ema_fast | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| ema_slow | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| ema_spread | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| ema_spread_atr | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| engine_action | trade |  | trade/record_field | src/journal/schema.py |
| entry_price | trade | Trade | trade/geometry | src/config_layer/crt_engine_v2.py |
| entry_price_fill | trade | Trade | trade/geometry | src/runtime/backtest_v2.py |
| entry_price_plan | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| eqh_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| eql_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| EXECUTION | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| EXPANSION | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| EXPIRED | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| fvg_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| high | feature | source_inputs | feature_schema | configs/formulas/market_ontology.yaml |
| HighAtrMagnitude | state | atr_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| HighCommitment | state | body_commitment | feature_enum | configs/formulas/market_ontology.yaml |
| HigherHigh | state | higher_high | feature_enum | configs/formulas/market_ontology.yaml |
| higher_high | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| HighMomentumMagnitude | state | momentum_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| hour_of_day | feature | temporal_context | feature_schema | configs/formulas/market_ontology.yaml |
| last_swing_high_price | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| last_swing_low_price | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| liquidity_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| liquidity_pressure_score | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| liquidity_sweep | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| LIQ_SWEEP | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| low | feature | source_inputs | feature_schema | configs/formulas/market_ontology.yaml |
| LowAtrMagnitude | state | atr_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| LowCommitment | state | body_commitment | feature_enum | configs/formulas/market_ontology.yaml |
| LowerLow | state | lower_low | feature_enum | configs/formulas/market_ontology.yaml |
| lower_low | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| lower_wick | feature | primitives | feature_schema | configs/formulas/market_ontology.yaml |
| lower_wick_ratio | feature | feature_compositions | feature_schema | configs/formulas/market_ontology.yaml |
| LowMomentumMagnitude | state | momentum_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| macd_hist_raw | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| macd_hist_z | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| macd_line | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| macd_signal | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| MANIPULATION_C2 | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| MediumAtrMagnitude | state | atr_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| MediumCommitment | state | body_commitment | feature_enum | configs/formulas/market_ontology.yaml |
| MediumMomentumMagnitude | state | momentum_magnitude | feature_enum | configs/formulas/market_ontology.yaml |
| mitigation_block_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| momentum_magnitude | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| momentum_score | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| momentum_score_atr | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| Neutral | state | trend_bias | feature_enum | configs/formulas/market_ontology.yaml |
| NeutralMomentum | state | rsi_state | feature_enum | configs/formulas/market_ontology.yaml |
| NoBreak | state | break_of_structure | feature_enum | configs/formulas/market_ontology.yaml |
| NoCHoCH | state | change_of_character | feature_enum | configs/formulas/market_ontology.yaml |
| NoDisplacement | state | displacement_flag | feature_enum | configs/formulas/market_ontology.yaml |
| NoDoubleSweep | state | double_sweep | feature_enum | configs/formulas/market_ontology.yaml |
| NoHigherHigh | state | higher_high | feature_enum | configs/formulas/market_ontology.yaml |
| NoLowerLow | state | lower_low | feature_enum | configs/formulas/market_ontology.yaml |
| NoRetest | state | retest_flag | feature_enum | configs/formulas/market_ontology.yaml |
| NoSweep | state | liquidity_sweep | feature_enum | configs/formulas/market_ontology.yaml |
| NoSweep | state | sweep_detected | feature_enum | configs/formulas/market_ontology.yaml |
| open | feature | source_inputs | feature_schema | configs/formulas/market_ontology.yaml |
| order_block_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| Overbought | state | rsi_state | feature_enum | configs/formulas/market_ontology.yaml |
| override_action | trade |  | trade/record_field | src/journal/schema.py |
| Oversold | state | rsi_state | feature_enum | configs/formulas/market_ontology.yaml |
| pdh_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| pdl_distance | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| pnl | trade |  | trade/record_field | src/journal/schema.py |
| portfolio_exposure_before | trade |  | trade/record_field | src/journal/schema.py |
| PULLBACK | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| RANGE | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| RANGE_C1 | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| regime | trade |  | trade/record_field | src/journal/schema.py |
| RESOLUTION | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| result | trade |  | trade/record_field | src/journal/schema.py |
| RETEST | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| RetestActive | state | retest_flag | feature_enum | configs/formulas/market_ontology.yaml |
| retest_depth | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| retest_flag | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| REVERSAL | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| risk_pct | trade | Trade | trade/geometry | src/runtime/backtest_v2.py |
| rr | trade |  | trade/record_field | src/journal/schema.py |
| rr_ratio | trade | Trade | trade/geometry | src/runtime/backtest_v2.py |
| rsi_14 | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| rsi_state | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| SellSideLiquidityGrab | shape | LiquidityGrab | shape_layer | configs/formulas/market_shapes.yaml |
| SellSideSweep | state | liquidity_sweep | feature_enum | configs/formulas/market_ontology.yaml |
| session | feature | temporal_context | feature_schema | configs/formulas/market_ontology.yaml |
| SHADOW_PENDING | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| sl_price | trade | Trade | trade/geometry | src/config_layer/crt_engine_v2.py |
| SWEEP | state |  | crt_machine | configs/formulas/crt_state_identity.yaml |
| SweepDetected | state | sweep_detected | feature_enum | configs/formulas/market_ontology.yaml |
| sweep_detected | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| swing_high | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| swing_low | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| symbol | trade |  | trade/record_field | src/journal/schema.py |
| timestamp | trade |  | trade/record_field | src/journal/schema.py |
| total_wick | feature | primitives | feature_schema | configs/formulas/market_ontology.yaml |
| tp1_price | trade | Trade | trade/geometry | src/config_layer/crt_engine_v2.py |
| tp2_price | trade | Trade | trade/geometry | src/runtime/backtest_v2.py |
| Trade | trade |  | trade/geometry | src/config_layer/crt_engine_v2.py |
| trade_id | trade |  | trade/record_field | src/journal/schema.py |
| trend_bias | feature | structural_states | feature_schema | configs/formulas/market_ontology.yaml |
| trend_strength_raw | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| trend_strength_z | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| true_range | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| UNKNOWN | trade | intent | trade/intent | src/config_layer/execution_planner.py |
| upper_wick | feature | primitives | feature_schema | configs/formulas/market_ontology.yaml |
| upper_wick_ratio | feature | feature_compositions | feature_schema | configs/formulas/market_ontology.yaml |
| volatility_ratio | feature | derived_metrics | feature_schema | configs/formulas/market_ontology.yaml |
| volatility_regime | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| volume | feature | source_inputs | feature_schema | configs/formulas/market_ontology.yaml |
| volume_ratio | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| volume_spike | feature | rolling_indicators | feature_schema | configs/formulas/market_ontology.yaml |
| zone | trade |  | trade/record_field | src/journal/schema.py |
