# state_ontology.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_bridge_layer.py`.

"Features measure. States interpret." The single source of state truth is `configs/formulas/market_ontology.yaml`; the interpreter is `src/features/feature_states.py::FeatureStateEncoder`. That file owns **no numeric cuts** — it maps values it is GIVEN and raises on a missing input (no defaults).

An out-of-domain value is never coerced and never dropped: it becomes an explicit, greppable marker — `X_UNMAPPED(<value>)` for a finite value outside the declared domain, `X_NON_FINITE(<value>)` for NaN/inf.

## Vector-bound stateful identities

| Vector idx | Feature | FM-ID | Category | Declared states |
|---:|---|---|---|---|
| 6 | `double_sweep` | `FM-060` | Liquidity | `NoDoubleSweep`=0; `DoubleSweep`=1 |
| 10 | `trend_bias` | `FM-054` | Trend | `Bearish`=-1; `Neutral`=0; `Bullish`=1 |
| 20 | `sweep_detected` | `FM-059` | Liquidity | `NoSweep`=0; `SweepDetected`=1 |
| 21 | `liquidity_sweep` | `FM-058` | Liquidity | `SellSideSweep`=-1; `NoSweep`=0; `BuySideSweep`=1 |
| 22 | `break_of_structure` | `FM-057` | MarketStructure | `BearishBreak`=-1; `NoBreak`=0; `BullishBreak`=1 |
| 23 | `swing_high` | `FM-045` | MarketStructure | `NoSwingHigh`=0; `SwingHighConfirmed`=1 |
| 24 | `swing_low` | `FM-046` | MarketStructure | `NoSwingLow`=0; `SwingLowConfirmed`=1 |
| 25 | `higher_high` | `FM-055` | MarketStructure | `NoHigherHigh`=0; `HigherHigh`=1 |
| 26 | `lower_low` | `FM-056` | MarketStructure | `NoLowerLow`=0; `LowerLow`=1 |
| 30 | `volatility_regime` | `FM-050` | Volatility | `LowVolatility`=0; `NormalVolatility`=1; `HighVolatility`=2 |
| 31 | `session` | `FM-052` | Time | `ASIA`=0; `LONDON`=1; `NEWYORK`=2; `OVERLAP`=3; `CLOSED`=4 |
| 38 | `volume_spike` | `FM-063` | Volume | `NoSpike`=0; `VolumeSpike`=1 |
| 47 | `change_of_character` | `FM-083` | MarketStructure | `BearishCHoCH`=-1; `NoCHoCH`=0; `BullishCHoCH`=1 |

## Declared but NOT vector-bound

These identities carry declared states but occupy **no canonical vector slot** (`lineage.vector_key: []`). A caller must supply them explicitly; the encoder will never invent them from their inputs, because that would be re-derivation.

| Feature | FM-ID | Category | Declared states |
|---|---|---|---|
| `atr_magnitude` | `FM-072` | Volatility | `LowAtrMagnitude`=0; `MediumAtrMagnitude`=1; `HighAtrMagnitude`=2 |
| `body_commitment` | `FM-071` | CandleGeometry | `LowCommitment`=0; `MediumCommitment`=1; `HighCommitment`=2 |
| `displacement_flag` | `FM-069` | Volatility | `NoDisplacement`=0; `Displacement`=1 |
| `momentum_magnitude` | `FM-073` | Momentum | `LowMomentumMagnitude`=0; `MediumMomentumMagnitude`=1; `HighMomentumMagnitude`=2 |
| `retest_flag` | `FM-061` | Retest | `NoRetest`=0; `RetestActive`=1 |
| `rsi_state` | `FM-068` | Momentum | `Oversold`=-1; `NeutralMomentum`=0; `Overbought`=1 |

## Continuous — measured, not interpreted

**35** canonical features carry no `states:` block. They are values, not labels. Banding any of them requires a declared state map in the ontology FIRST; the encoder refuses to cut a band on its own.

`open`, `high`, `low`, `close`, `volume`, `volume_ratio`, `ema_fast`, `ema_slow`, `ema_spread`, `trend_strength_z`, `momentum_score`, `atr`, `volatility_ratio`, `rsi_14`, `macd_line`, `macd_signal`, `macd_hist_raw`, `macd_hist_z`, `body_size`, `candle_range`, `body_ratio`, `hour_of_day`, `disp_strength`, `retest_depth`, `candles_since_sweep`, `liquidity_distance`, `liquidity_pressure_score`, `order_block_distance`, `fvg_distance`, `breaker_distance`, `mitigation_block_distance`, `pdh_distance`, `pdl_distance`, `eqh_distance`, `eql_distance`

## Orthogonality note

State ontology (this file) is **not** the Decision ontology. A feature state is a description of one measurement; a CRT state is a position in a governed transition graph. `examples`: `trend_bias = Bullish` is a feature state; `CRTState.RETEST` is a decision state. See `crt_state_resolver_bridge.md` for the constructor that maps between them.

