# Feature identities — schema v6.0 (48 canonical slots)

Generated from `configs/formulas/market_ontology.yaml` + `CANONICAL_FEATURES`. Formula and description
are the REGISTERED text, verbatim (whitespace collapsed). Full columns (why_it_exists, interpretation,
caveat, depends_on, produced_by, scope, config_keys) are in `feature_identities_v6.xlsx`.

## Canonical vector (slots 0–47)

| slot | name | fm_id | formula | description |
|---|---|---|---|---|
| 0 | open | BASE_INPUT (no FM id) |  |  |
| 1 | high | BASE_INPUT (no FM id) |  |  |
| 2 | low | BASE_INPUT (no FM id) |  |  |
| 3 | close | BASE_INPUT (no FM id) |  |  |
| 4 | volume | BASE_INPUT (no FM id) |  |  |
| 5 | volume_ratio | FM-062 | volume / SMA(volume, <feature_pipeline.volume_ma_window>); 1.0 where the moving average is <= 0 # default 20 | This bar's volume as a multiple of its own trailing average. |
| 6 | double_sweep | FM-060 | any(liquidity_sweep > 0) and any(liquidity_sweep < 0) over rolling(<feature_pipeline.double_sweep_window>, min_periods=1) -> int8 {0, 1} # default 5 | Both sweep directions observed within a short trailing window. |
| 7 | ema_fast | FM-043 | close.ewm(span=<feature_pipeline.ema_fast_span>, adjust=False).mean() # default 9 | Exponentially weighted moving average of close over the fast span. |
| 8 | ema_slow | FM-044 | close.ewm(span=<feature_pipeline.ema_slow_span>, adjust=False).mean() # default 21 | Exponentially weighted moving average of close over the slow span. |
| 9 | ema_spread | FM-022 | (ema_fast - ema_slow) / atr if atr>0 else nan # emitted only when <feature_pipeline.normalization_basis> == 'atr_relative' (the default); 'atr_absolute' selects FM-030 instead | Separation between the fast and slow EMA, divided by close-relative ATR. |
| 10 | trend_bias | FM-054 | sign(ema_fast - ema_slow) -> float32 {-1, 0, +1} | Ternary direction of the fast EMA relative to the slow EMA. |
| 11 | trend_strength_z | FM-064 | rolling(<feature_pipeline.zscore_window>) z-score of SMA(<feature_pipeline.trend_strength_window>) of diff(SMA(<feature_pipeline.ma_periods[0]>) of close) # defaults 50, 10, 20 | Rolling z-score of the 10-bar smoothed slope of the 20-bar moving average of close. |
| 12 | momentum_score | FM-023 | close_delta / atr if atr>0 else nan # close_delta = close.diff(); emitted only when <feature_pipeline.normalization_basis> == 'atr_relative' (the default); 'atr_absolute' selects FM-031 instead | One-bar price change divided by close-relative ATR. |
| 13 | atr | FM-041 | SMA(<feature_pipeline.atr_period>) of true_range, close-relative: atr_14_raw / close (atr_14_raw = true_range.rolling(<feature_pipeline.atr_period>).mean()) # default 14 | Simple moving average of true_range over the configured period, divided by close (close-relative, dimensionless). |
| 14 | volatility_ratio | FM-024 | (high - low) / (atr * close) if atr>0 and close>0 else 1.0 | This bar's full range expressed in units of ATR-scaled price; 1.0 when undefined. |
| 15 | rsi_14 | FM-042 | 100 - 100/(1+RS); RS = SMA(<feature_pipeline.rsi_period>) gain / (SMA(<feature_pipeline.rsi_period>) loss + 1e-9); clipped [0,100] # default period 14 | Relative Strength Index on a [0, 100] scale, using SMA-averaged gains and losses. |
| 16 | macd_line | FM-047 | close.ewm(span=<feature_pipeline.macd_fast>, adjust=False).mean() - close.ewm(span=<feature_pipeline.macd_slow>, adjust=False).mean() # defaults 12, 26 | Difference between a fast and a slow EWM of close. |
| 17 | macd_signal | FM-048 | macd_line.ewm(span=<feature_pipeline.macd_signal>, adjust=False).mean() # default 9 | EWM smoothing of macd_line over the signal span. |
| 18 | macd_hist_raw | FM-049 | macd_line - macd_signal | macd_line minus macd_signal — the raw MACD histogram, in absolute price units. |
| 19 | macd_hist_z | FM-053 | rolling(<feature_pipeline.zscore_window>) z-score of macd_hist_raw # default 50 | Rolling z-score of macd_hist_raw over the configured window. |
| 20 | sweep_detected | FM-059 | liquidity_sweep != 0 -> int8 {0, 1} | Direction-agnostic presence of a liquidity sweep on this bar. |
| 21 | liquidity_sweep | FM-058 | +1 if high > ref_high and close <= ref_high; -1 if low < ref_low and close >= ref_low; else 0 -> int8 # ref_* = prev(last_swing_*_price) | A stop-run: price traded THROUGH a structural reference but closed back inside it. |
| 22 | break_of_structure | FM-057 | +1 if close > prev(last_swing_high_price); -1 if close < prev(last_swing_low_price); else 0 -> int8 | Directional break of structure, decided on the CLOSE rather than the extreme. |
| 23 | swing_high | FM-045 | causal DELAYED publication of a centered rolling-max swing high over width 2k+1 (FC1-A: math at t, published with k-bar delay, available_at = t+k); k = <feature_pipeline.swing_window> # default 2 | Flag marking that a local pivot high was confirmed, published k bars after the pivot itself. |
| 24 | swing_low | FM-046 | causal DELAYED publication of a centered rolling-min swing low over width 2k+1 (FC1-A); k = <feature_pipeline.swing_window> # default 2 | Flag marking that a local pivot low was confirmed, published k bars after the pivot itself. |
| 25 | higher_high | FM-055 | high > prev(last_swing_high_price) -> int8 {0, 1}; NaN reference compares False | Whether this bar's high exceeded the previous confirmed swing high. |
| 26 | lower_low | FM-056 | low < prev(last_swing_low_price) -> int8 {0, 1}; NaN reference compares False | Whether this bar's low undercut the previous confirmed swing low. |
| 27 | body_size | FM-001 | abs(close - open) | Absolute distance between the candle's open and close. |
| 28 | candle_range | FM-002 | high - low | Full high-to-low extent of the bar. |
| 29 | body_ratio | FM-010 |  | Fraction of the candle's full range occupied by its body, bounded [0, 1]. |
| 30 | volatility_regime | FM-050 | tercile(atr_14.rolling(<feature_pipeline.volatility_percentile_window>, min_periods=1).rank(pct=True)); atr_14 = SMA(14) of true_range (ABSOLUTE); cuts at <feature_pipeline.volatility_tercile_low>/<feature_pipeline.volatility_tercile_high> -> int8 {0,1,2} # defaults 200, 0.33/0.66 | Tercile bucket of the current absolute ATR against its own trailing rolling percentile. |
| 31 | session | FM-052 | window model over <feature_pipeline.session_windows_utc>, half-open [start, end): OVERLAP if in LONDON and NEWYORK; else NEWYORK; else LONDON; else ASIA; else CLOSED -> int8 # defaults ASIA [0,9) LONDON [7,16) NEWYORK [12,21) | Which major trading session the bar falls in, under a 5-value window model that can express the London/New-York overlap and a no-session CLOSED state. |
| 32 | hour_of_day | FM-051 | timestamp.dt.hour -> int8 | UTC hour of the bar's own timestamp, 0-23. |
| 33 | disp_strength | FM-020 | clip(body_size / (atr * close), <feature_pipeline.disp_strength_clip_low>, <feature_pipeline.disp_strength_clip_high>) if atr>0 and close>0 else nan # defaults 0.0, 3.0 | Candle body measured in units of ATR-scaled price, clipped to [0, 3]. |
| 34 | retest_depth | FM-021 | clip(abs(close - ema_fast) / (atr * close), <feature_pipeline.retest_depth_clip_low>, <feature_pipeline.retest_depth_clip_high>) if retest_flag==1 and atr>0 and close>0 else 0.0 # defaults 0.0, 1.0 | How far price sits from the fast EMA, in ATR-scaled units, on bars where a retest is active; 0.0 otherwise. |
| 35 | candles_since_sweep | FM-065 | cumcount of bars since the last liquidity_sweep event (groupby (liquidity_sweep != 0).cumsum()); 0 before the first sweep. Falls back to a retest_flag-keyed grouping ONLY when liquidity_sweep is absent from the frame (feature_pipeline.py:988-991) — non-authoritative, unreachable in production per the certification ledger. | Bars elapsed since the most recent liquidity_sweep event; 0 before any sweep has occurred. |
| 36 | liquidity_distance | FM-025 | min over levels of abs(close - level) / (atr * close), clipped >= 0; nan if atr*close<=0 or no finite level | ATR-normalized distance from close to the NEAREST liquidity reference (last swing high, last swing low, or last BOS level). |
| 37 | liquidity_pressure_score | FM-026 | clip(exp(<feature_pipeline.liquidity_decay_coeff> * liquidity_distance), 0.0, 1.0); nan distance -> treated as <feature_pipeline.liquidity_nan_sentinel> # defaults -0.5, 10.0 | Exponential decay of liquidity_distance into a bounded [0, 1] proximity score. |
| 38 | volume_spike | FM-063 | volume_ratio > rolling(<feature_pipeline.volume_spike_adaptive_window>, min_periods=<feature_pipeline.volume_spike_min_samples>).quantile(<feature_pipeline.volume_spike_percentile>/100); where that threshold is NaN fall back to <feature_pipeline.volume_spike_fixed_fallback> -> int8 {0, 1} # defaults 50, 20, 75, 1.5 | Whether volume_ratio exceeds an ADAPTIVE trailing percentile of its own distribution. |
| 39 | order_block_distance | FM-075 | tanh(sign * (close - order_block_zone_edge) / atr); 0.0 if no active OB or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest unmitigated order block's near edge. |
| 40 | fvg_distance | FM-076 | tanh(sign * (close - fvg_zone_edge) / atr); 0.0 if no active FVG or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest unfilled fair value gap's near edge. |
| 41 | breaker_distance | FM-077 | tanh(sign * (close - breaker_zone_edge) / atr); 0.0 if no active breaker or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest un-retested breaker block's near edge. |
| 42 | mitigation_block_distance | FM-078 | tanh(sign * (close - mitigation_zone_edge) / atr); 0.0 if no live mitigation block or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest live mitigation block's near edge — the tighter candle-BODY-only zone nested inside an order block whose OUTER zone has already been touched once. |
| 43 | pdh_distance | FM-079 | tanh(-(close - prev_day_high) / atr); 0.0 if no closed D1 parent yet or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the most recently closed D1 parent candle's high (Previous Day High). |
| 44 | pdl_distance | FM-080 | tanh((close - prev_day_low) / atr); 0.0 if no closed D1 parent yet or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the most recently closed D1 parent candle's low (Previous Day Low). |
| 45 | eqh_distance | FM-081 | tanh(-(close - eqh_level) / atr); 0.0 if no equal-highs cluster found or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest equal-highs cluster (2+ confirmed swing highs within a small ATR-scaled tolerance). |
| 46 | eql_distance | FM-082 | tanh((close - eql_level) / atr); 0.0 if no equal-lows cluster found or atr<=0 | Signed, ATR-normalized, tanh-bounded distance from close to the nearest equal-lows cluster (2+ confirmed swing lows within a small ATR-scaled tolerance). |
| 47 | change_of_character | FM-083 | break_of_structure if sign(break_of_structure) != sign(trend_bias) and both nonzero, else 0 | A break-of-structure event that goes AGAINST the prevailing trend_bias — a potential reversal signal, distinct from ordinary trend-continuation BOS. |

## Registered FM identities NOT in the vector (23)

| name | fm_id | section | scope | formula | description |
|---|---|---|---|---|---|
| upper_wick | FM-003 | primitives |  | high - max(open, close) | Distance from the bar's high down to the top of its body. |
| lower_wick | FM-004 | primitives |  | min(open, close) - low | Distance from the bottom of the bar's body down to its low. |
| total_wick | FM-005 | primitives |  | upper_wick + lower_wick | Combined length of both wicks; equivalently candle_range - body_size. |
| upper_wick_ratio | FM-011 | feature_compositions |  |  | Fraction of the candle's range consumed by the upper wick, bounded [0, 1]. |
| lower_wick_ratio | FM-012 | feature_compositions |  |  | Fraction of the candle's range consumed by the lower wick, bounded [0, 1]. |
| body_to_total_wick_ratio | FM-013 | feature_compositions |  |  | Body size relative to total wick length; unbounded above 1 when the body exceeds the wicks. |
| displacement_retrace | FM-027 | derived_metrics | EPISODE | clip(\|retest_close - disp_open\| / \|disp_close - disp_open\|, 0.0, 1.0); disp body 0 -> skip | How far the retest candle's close retraced back into the displacement candle's body, as a fraction of that body. |
| displacement_atr_ratio | FM-028 | derived_metrics | EPISODE | candle_range / atr_abs; atr_abs<=0 -> 0.0 # atr_abs = SMA(period) of true_range, ABSOLUTE price units (state.atr_abs, now registered as FM-074 atr_absolute), NOT the close-relative FM-041 `atr` | Candle range expressed as a multiple of ATR. |
| disp_strength_atr_rescale | FM-029 | derived_metrics |  | disp_strength / atr; atr<=0 -> 0.0 | The AS-WIRED quantity of scoring_engine.compute_scores: FM-020 divided again by close-relative ATR. |
| ema_spread_atr | FM-030 | derived_metrics |  | (ema_fast - ema_slow) / (atr * close) if atr>0 and close>0 else nan # emitted only when <feature_pipeline.normalization_basis> == 'atr_absolute'; the default 'atr_relative' selects FM-022 instead | EMA separation divided by ABSOLUTE ATR (atr * close) — the scale-invariant form of FM-022. |
| momentum_score_atr | FM-031 | derived_metrics |  | close_delta / (atr * close) if atr>0 and close>0 else nan # close_delta = close.diff(); emitted only when <feature_pipeline.normalization_basis> == 'atr_absolute'; the default 'atr_relative' selects FM-023 instead | One-bar price change divided by ABSOLUTE ATR (atr * close) — the scale-invariant form of FM-023. |
| true_range | FM-040 | rolling_indicators |  | max(high - low, abs(high - prev_close), abs(low - prev_close)) | Wilder's true range: the greatest of this bar's range and its two gap-inclusive extensions against the previous close. |
| retest_flag | FM-061 | structural_states |  | rolling_any(liquidity_sweep != 0, <feature_pipeline.retest_lookback>) and abs(close - ema_fast) <= <feature_pipeline.retest_atr_band_mult> * atr * close -> int8 {0, 1} # defaults 10, 1.0 | A recent sweep occurred AND price is currently within an ATR-scaled band of the fast EMA. |
| last_swing_high_price | FM-066 | rolling_indicators |  | forward-fill of high where the centered swing-high pivot fired, then shifted by k = <feature_pipeline.swing_window> (FC1-A causal publication) # default 2 | Price level of the most recent confirmed swing high, carried forward until a new one confirms. |
| last_swing_low_price | FM-067 | rolling_indicators |  | forward-fill of low where the centered swing-low pivot fired, then shifted by k = <feature_pipeline.swing_window> (FC1-A causal publication) # default 2 | Price level of the most recent confirmed swing low, carried forward until a new one confirms. |
| rsi_state | FM-068 | structural_states |  | +1 if rsi_14 > <feature_pipeline.rsi_overbought>; -1 if rsi_14 < <feature_pipeline.rsi_oversold>; else 0 -> int8 # defaults 70, 30 | Ternary interpretation of rsi_14 against its overbought/oversold thresholds. |
| displacement_flag | FM-069 | structural_states |  | body_size > candle_range * <feature_pipeline.displacement_strong_body_mult> and atr > 0 -> int8 {0, 1} # default 0.6 | Marks a candle whose body occupies more than the configured fraction of its range, on a bar with valid ATR. |
| candles_since_retest_state | FM-070 | derived_metrics |  | current_candle_index - retest_candle_index | Bars elapsed since the retest candle that triggered the current CRT engine confirmation window. |
| body_commitment | FM-071 | structural_states |  | bin(body_ratio; band_edges) -> int8 {0,1,2} # identity transform; edges ontology-owned | Discrete body-commitment magnitude state derived from continuous body_ratio (FM-010). |
| atr_magnitude | FM-072 | structural_states |  | bin(percentile_rank(atr \| series); band_edges) -> int8 {0,1,2} # series percentile of FM-041 relative atr | Discrete ATR intensity state from continuous close-relative ATR (FM-041), via series percentile rank. |
| momentum_magnitude | FM-073 | structural_states |  | bin(percentile_rank(\|momentum_score\| \| series); band_edges) -> int8 {0,1,2} # F-061: never fixed abs edges on legacy FM-023 | Discrete momentum intensity from \|momentum_score\| series percentile (F-061-safe). |
| atr_absolute | FM-074 | rolling_indicators |  | SMA(<feature_pipeline.atr_period>) of true_range, ABSOLUTE price units (no division by close): true_range.rolling(<feature_pipeline.atr_period>).mean() # default 14 | Simple moving average of true_range over the configured period, in absolute price units — the pre-division intermediate that FM-041 `atr` derives from (atr_14_raw / close = FM-041). |
| trend_strength_raw | FM-084 | rolling_indicators |  | SMA(<feature_pipeline.trend_strength_window>) of diff(SMA(<feature_pipeline.ma_periods[0]>) of close) # defaults 10, 20 | The 10-bar smoothed slope of the 20-bar moving average of close, in price units per bar. |
