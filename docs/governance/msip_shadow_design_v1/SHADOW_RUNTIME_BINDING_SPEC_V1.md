# Shadow Runtime Binding Spec V1

## Hard invariants

- shadow_flags.affects_crt == false always
- shadow_flags.affects_execution == false always
- shadow must not call StateMachine.try_* or mutate EngineState
- shadow must not open/close trades
- shadow must not write production ACTIVE_VERSION configs

## Order

- 1. Load OHLCV bar
- 2. FeaturePipeline already-built series lookup OR incremental if live (design allows either; must be PIT)
- 3. Optionally run CRT process_candle for comparison observation only
- 4. Compute MarketStateVector from feature surface + interpretation config
- 5. Emit vector + provenance
- 6. Optionally record disagreement vs CRT observations
