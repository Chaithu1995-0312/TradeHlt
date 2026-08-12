# CRT State Resolver — Fresh Run on MT5 XAUUSD M15

> **Generated:** 2026-08-05 10:55:13
> **Data source:** `data/mt5/XAUUSD_M15.csv`
> **CRT states config:** `configs/formulas/market_crt_states.yaml`
> **Resolver:** `src/features/crt_state_resolver.py`

## Summary

| Metric | Value |
|--------|-------|
| Raw OHLCV rows | 47275 |
| Enriched rows (after warmup) | 47197 |
| Resolved bars | 47197 |
| State transitions | 6580 |
| Warmup bars dropped | 78 |

## Per-State Bar Counts

| State | Count | %% of Total |
|-------|-------|------------|
| DISPLACEMENT | 240 | 0.51% |
| EXPANSION | 1125 | 2.38% |
| RANGE | 39308 | 83.28% |
| RETEST | 57 | 0.12% |
| SHADOW_PENDING | 254 | 0.54% |
| SWEEP | 6213 | 13.16% |

## State Funnel (Progression)

| Step | State | Count | %% of Total | Retention from Prev |
|------|-------|-------|------------|---------------------|
| 1 | RANGE | 39308 | 83.28% | — |
| 2 | SWEEP | 6213 | 13.16% | 15.81% |
| 3 | DISPLACEMENT | 240 | 0.51% | 3.86% |
| 4 | EXPANSION | 1125 | 2.38% | 468.75% |
| 5 | RETEST | 57 | 0.12% | 5.07% |
| 6 | EXECUTION | 0 | 0.00% | 0.00% |
| 7 | RESOLUTION | 0 | 0.00% | 0.00% |

## Key Ratios

- **SWEEP/RANGE rate**: 15.81% (6213 sweeps per 39308 range bars)
- **DISPLACEMENT/SWEEP rate**: 3.86% (240 displacements per 6213 sweeps)
- **EXPANSION/DISPLACEMENT rate**: 468.75% (1125 expansions per 240 displacements)
- **RETEST/EXPANSION rate**: 5.07% (57 retests per 1125 expansions)
- **EXECUTION/RETEST rate**: 0.00% (0 executions per 57 retests)

## Top State Transitions

| From | To | Count |
|------|----|-------|
| RANGE | SWEEP | 2989 |
| SWEEP | RANGE | 2814 |
| SWEEP | DISPLACEMENT | 188 |
| DISPLACEMENT | RANGE | 176 |
| RANGE | SHADOW_PENDING | 176 |
| SHADOW_PENDING | RANGE | 154 |
| SHADOW_PENDING | SWEEP | 22 |
| EXPANSION | RETEST | 19 |
| RETEST | RANGE | 19 |
| DISPLACEMENT | EXPANSION | 12 |
| SWEEP | EXPANSION | 9 |
| EXPANSION | RANGE | 2 |

## State Sequence (first 50 bars)

```
RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → SWEEP → SWEEP → SWEEP → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE
```

## Feature State Distribution (sample)

The CRT resolver uses these feature states from `market_ontology.yaml`:

- **break_of_structure**: NoBreak=630, BullishBreak=186, BearishBreak=184
- **displacement_flag**: NoDisplacement=691, Displacement=309
- **double_sweep**: NoDoubleSweep=911, DoubleSweep=89
- **higher_high**: NoHigherHigh=713, HigherHigh=287
- **liquidity_sweep**: NoSweep=823, BuySideSweep=101, SellSideSweep=76
- **lower_low**: NoLowerLow=739, LowerLow=261
- **retest_flag**: RetestActive=611, NoRetest=389
- **rsi_state**: NeutralMomentum=764, Oversold=122, Overbought=114
- **session**: ASIA=264, LONDON=220, NEWYORK=218, OVERLAP=176, CLOSED=122
- **sweep_detected**: NoSweep=823, SweepDetected=177
- **swing_high**: NoSwingHigh=864, SwingHighConfirmed=136
- **swing_low**: NoSwingLow=866, SwingLowConfirmed=134
- **trend_bias**: Bearish=519, Bullish=480, Neutral=1
- **volatility_regime**: LowVolatility=377, HighVolatility=340, NormalVolatility=283
- **volume_spike**: NoSpike=748, VolumeSpike=252
