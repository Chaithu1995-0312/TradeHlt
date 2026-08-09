# Current Architecture Problem Statement V1

## Proven facts

- CRT is a 9-state opportunity lifecycle with directed VALID_TRANSITIONS + force-reset surface
- CRT transition guards do not use the complete 38-feature vector as primary transition surface
- CRT includes local market math (body_ratio, wick, atr, move, emas) and private state memory
- One active candidate lifecycle is tracked (TelemetryCollector._active_candidate)
- XAUUSD full run: 3390 RANGE→SWEEP, 315 SWEEP→DISP, 60 expansion episodes, 17 retest, 5 exec, 1 trade
- HTF reset dominates candidate deaths (3323/3433)
- Expansion episodes: 17 retest / 43 reset / 0 TTL expired
- Downstream rejected_trades=0 on measured run
- Fail-reason sample shows depth_below_min, depth_above_ceiling, move_below_atr_min active
- Soft-conf score gate approved 17/17; 12 FILTER_REJECTED off_session

## Strong inferences

- **Single-candidate ownership suppresses overlapping opportunity observation**  
  support: singular _active_candidate; long expansion dwell max 346; HTF deaths  
  unproven: how many concurrent opportunities would have been economic
- **Current CRT mixes continuous market observation with opportunity lifecycle ownership**  
  support: dual OHLCV path; local math in try_*; state memory ownership  
  unproven: optimal split surface for every quantity
- **Threshold recalibration alone cannot resolve architectural split authority**  
  support: even perfect thresholds leave CRT-local WHAT vs pipeline WHAT dual implementation  
  unproven: instrument-specific retune magnitude of throughput change
- **Binding CRT directly to MarketStateVector would be a consumer migration**  
  support: CRT currently does not consume 38-vector for guards  
  unproven: future migration cost

## Open questions

- CRT ATR/EMA/body_ratio parity vs FeaturePipeline (decision-critical only for future BIND, not for choosing C)
- Whether concurrent candidates should be phase-2 under CRT HOW after shadow continuous state exists
- Session policy placement: CRT HOW vs shared policy layer

## Non-problems

- One trade / low trade count alone does not prove architecture failure
- Historical output hash changes are not automatic failures under BEHAVIOR_CHANGE_AUTHORIZED
- 38 features need not all be consumed by every WHO
- CRT private lifecycle state is not automatically an authority violation
- Downstream fusion rejection is not the measured primary collapse
- TTL non-firing (0 expired) does not alone prove TTL should be shortened without ownership redesign
