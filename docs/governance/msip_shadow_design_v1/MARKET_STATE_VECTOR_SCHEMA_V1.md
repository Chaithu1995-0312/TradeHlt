# MarketStateVector Schema V1

Version `1.0.0` · Decision **C** · Not implemented

## Dimensions

### MSD-STRUCTURE — `structure_state`

Causal swing/structure regime snapshot (HH/LL/BOS/sweep presence)

- feeds: `['swing_high', 'swing_low', 'higher_high', 'lower_low', 'break_of_structure', 'liquidity_sweep', 'sweep_detected', 'double_sweep']`
- not in vector: `['CRT active_range refs', 'CRT sweep_event object', 'candidate_id']`

### MSD-LIQUIDITY — `liquidity_state`

ATR-normalized distance/pressure to structural levels

- feeds: `['liquidity_distance', 'liquidity_pressure_score', 'atr', 'close']`
- not in vector: `['CRT range h_ref/l_ref as private levels unless published as WHAT']`

### MSD-VOLATILITY — `volatility_state`

Canonical volatility regime + supporting ATR/vol ratio

- feeds: `['volatility_regime', 'atr', 'true_range', 'volatility_ratio']`
- not in vector: `['CRT-local atr until parity audit PASS']`

### MSD-SESSION — `session_state`

Canonical pipeline session code + hour

- feeds: `['session', 'hour_of_day', 'timestamp']`
- not in vector: `['SESSION_MAP permutations', 'dashboard 1-based labels', 'CRT allowed_sessions policy decisions']`

### MSD-TREND — `trend_state`

Canonical trend strength + bias; not dual_engine abs(ema_spread)

- feeds: `['trend_strength', 'trend_bias', 'ema_fast', 'ema_slow']`
- not in vector: `['dual_engine local trend_strength', 'CRT EMA until parity PASS']`

### MSD-CANDLE_QUALITY — `candle_quality_state`

Body/range geometry quality (FM-010 body_ratio and related)

- feeds: `['body_ratio', 'body_size', 'wick_size', 'upper_wick', 'lower_wick']`
- not in vector: `['CRT displacement gate decision (HOW)']`

### MSD-CRT_PHASE_OBS — `crt_phase_observation`

READ-ONLY observation of current CRT state name if available to shadow runner

- feeds: `[]`
- not in vector: `['ability to mutate CRT', 'candidate private memory dump']`

## Explicitly excluded

- CRT EngineState private fields (sweep_event, displacement_candle, pending_*, active_trade)
- candidate_id / death_reason / single-candidate ownership
- entry/SL/TP/order intents
- EngineRunner fusion scores as market state
- economic expectancy / PnL
- session admission decisions (HOW)
- thresholds themselves (HOW lives in interpretation config)
- SUPERSEDED vector slots as authority (ema_spread/momentum_score are historical 38-dim, not MSIP authority)
