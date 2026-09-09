# CRT State Resolver — Fresh Run on MT5 XAUUSD M15

> **Generated:** 2026-09-04 17:25:36
> **Data source:** `D:\Tradelatest\data\mt5\XAUUSD_M15.csv`
> **dataset_id:** `XAUUSD_MT5_PHASE1_20260521` (bound=True, decision=WARN)
> **file_hash:** `sha256:4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`
> **plausibility:** `{'rows': 47275, 'lattice_phase_seconds': [0], 'lattice_phase_constant': True, 'frozen_bars': 0, 'frozen_pct': 0.0, 'zero_volume_bars': 0, 'zero_volume_pct': 0.0, 'median_true_range': 4.24, 'gap_p99_tr': 0.1604, 'gap_max_tr': 17.7972, 'gap_over_3tr': 25}`
> **supply_set:** `canonical_v5_plus_nonvector` / `77d31663c1fa9126` (nan_policy=propagate)
> **CRT states config:** `configs/formulas/market_crt_states.yaml`
> **Resolver:** `src/features/crt_state_resolver.py`

## Summary

| Metric | Value |
|--------|-------|
| Raw OHLCV rows | 47275 |
| Enriched rows (after warmup) | 47197 |
| Resolved bars | 47197 |
| State transitions | 4030 |
| Warmup bars dropped | 78 |

## Per-State Bar Counts

| State | Count | %% of Total |
|-------|-------|------------|
| DISPLACEMENT | 3127 | 6.63% |
| EXPANSION | 7092 | 15.03% |
| RANGE | 21745 | 46.07% |
| SHADOW_PENDING | 47 | 0.10% |
| SWEEP | 15186 | 32.18% |

## State Funnel (Progression)

| Step | State | Count | %% of Total | Retention from Prev |
|------|-------|-------|------------|---------------------|
| 1 | RANGE | 21745 | 46.07% | — |
| 2 | SWEEP | 15186 | 32.18% | 69.84% |
| 3 | DISPLACEMENT | 3127 | 6.63% | 20.59% |
| 4 | EXPANSION | 7092 | 15.03% | 226.80% |
| 5 | RETEST | 0 | 0.00% | 0.00% |
| 6 | EXECUTION | 0 | 0.00% | 0.00% |
| 7 | RESOLUTION | 0 | 0.00% | 0.00% |

## Key Ratios

- **SWEEP/RANGE rate**: 69.84% (15186 sweeps per 21745 range bars)
- **DISPLACEMENT/SWEEP rate**: 20.59% (3127 displacements per 15186 sweeps)
- **EXPANSION/DISPLACEMENT rate**: 226.80% (7092 expansions per 3127 displacements)
- **RETEST/EXPANSION rate**: 0.00% (0 retests per 7092 expansions)

## Top State Transitions

| From | To | Count |
|------|----|-------|
| RANGE | SWEEP | 1715 |
| SWEEP | RANGE | 1261 |
| SWEEP | DISPLACEMENT | 456 |
| DISPLACEMENT | RANGE | 455 |
| RANGE | SHADOW_PENDING | 47 |
| SHADOW_PENDING | EXPANSION | 31 |
| EXPANSION | RANGE | 29 |
| SHADOW_PENDING | RANGE | 16 |
| EXPANSION | SWEEP | 1 |
| DISPLACEMENT | SWEEP | 1 |

## State Sequence (first 50 bars)

```
RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → RANGE → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → SWEEP → DISPLACEMENT → DISPLACEMENT → DISPLACEMENT → DISPLACEMENT → DISPLACEMENT → DISPLACEMENT → DISPLACEMENT → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE → RANGE
```

## Feature State Distribution (sample)

The CRT resolver uses these feature states from `market_ontology.yaml`:

- **break_of_structure**: NoBreak=630, BullishBreak=186, BearishBreak=184
- **change_of_character**: NoCHoCH=931, BullishCHoCH=37, BearishCHoCH=32
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
