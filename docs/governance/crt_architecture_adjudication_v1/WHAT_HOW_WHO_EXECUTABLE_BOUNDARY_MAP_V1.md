# WHAT / HOW / WHO Executable Boundary Map V1

_Generated 2026-07-14T08:12:37.280834+00:00_

## Answers

- **where_WHAT_computed:** FeaturePipeline + candle_math/derived_math/ontology; also CRT-local parallel math
- **where_WHAT_duplicated:** CRT body_ratio/wick/atr/ema paths vs pipeline FM identities
- **where_HOW_encoded:** CRTConfig + reset/TTL/session/soft-conf policy in crt_engine_v2
- **HOW_config_driven:** most thresholds via prod config merge
- **HOW_hardcoded:** some control-flow structure / VALID_TRANSITIONS graph (STRUCTURAL)
- **WHO_reads_governed_WHAT:** Backtest journal, models (when enabled), research — not CRT transitions
- **WHO_bypasses_governed_WHAT:** CRT transition guards (local math)
- **bypass_legitimate:** partial — private lifecycle state YES; market math parallel recomputation is split authority
- **candidate_lifecycle_belongs:** WHO/CRT EngineState — not MarketStateVector
- **continuous_market_state_belongs:** WHAT + interpretation layer (MSIP shadow), independent of opportunity ownership

## Boundaries

### FeaturePipeline → BacktestRunner journal @ TRADE_OPENED (ALIGNED)

- quantity: `CANONICAL_FEATURES[38]`
- layer: WHAT
- actual: timestamp lookup into feature_vectors
- consequence: 38-vector is real WHAT; not CRT transition surface
- evidence: backtest_v2.py TRADE_OPENED path; baseline path verification

### FeaturePipeline → CRTEngine.process_candle (MISSING_BINDING)

- quantity: `CANONICAL_FEATURES[38]`
- layer: WHAT
- actual: NONE for transition guards
- consequence: Split authority: continuous WHAT vs CRT-local math
- evidence: XAUUSD baseline trace; process_candle(candle, htf_id)

### CRTEngine local (Candle props / ATR / EMA) → StateMachine.try_* (DUPLICATED_AUTHORITY)

- quantity: `body_ratio, wick_size, atr, emas, move`
- layer: WHAT (market math) implemented inside WHO
- actual: CRT-local recompute
- consequence: MARKET_MATH_LEAK_INTO_WHO; parity unproven vs pipeline
- evidence: crt_engine_v2 try_sweep_to_displacement; CRT_INPUT_AUTHORITY_MATRIX

### CRT EngineState → CRTEngine (LEGITIMATE_PRIVATE_STATE)

- quantity: `active_range, sweep_event, displacement_candle, candidate memory`
- layer: WHO private lifecycle state (not WHAT)
- actual: EngineState fields
- consequence: Must not force into MarketStateVector
- evidence: TelemetryCollector._active_candidate; EngineState

### CRTConfig / production JSON → CRTEngine (ALIGNED)

- quantity: `thresholds, TTL, sessions, conf weights`
- layer: HOW
- actual: CRTConfig fields
- consequence: Policy recalibration is HOW, not architecture replacement
- evidence: v2_multi_2026_04; fail-reason active geometry

### session_windows / allowed_sessions → CRT soft-conf / FILTER_REJECTED (ALIGNED)

- quantity: `session admission`
- layer: HOW
- actual: CRTConfig session policy
- consequence: Tertiary funnel residual OFF_SESSION (12/17)
- evidence: funnel diagnostic FILTER_REJECTED

### HTFBuilder + reset_lg → CRTEngine (POLICY_LEAK_INTO_WHAT)

- quantity: `HTF range lifecycle / reset`
- layer: HOW + WHO coupling
- actual: reset_to_range force
- consequence: HTF reset dominates candidate death (3323/3433)
- evidence: funnel diagnostic RESET_HTF

### EngineRunner fusion stack → trade journal (ALIGNED)

- quantity: `downstream admission`
- layer: WHO
- actual: optional BACKTEST_ENGINE_GATE
- consequence: Not primary collapse surface on measured run
- evidence: rejected_trades=0

