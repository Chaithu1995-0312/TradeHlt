# SWEEP Geometry Trace — Engine vs Pipeline

> Generated: 2026-07-24T13:33:19.713790
>
> Research-only. Explains SWEEP↔RANGE residual on the CRT state resolver.

## Executive summary

Two **different reference frames** define a 'sweep':

| Layer | Reference | Close rule | When evaluated |
|-------|-----------|------------|----------------|
| **Engine** `RangeDetector.detect_sweep` | HTF range `h_ref/l_ref` (init: completed HTF window max/min; on HTF reset: last `atr_period` bars) | `close < h_ref` / `close > l_ref` (strict) | Only in state **RANGE** (state machine admits) |
| **Pipeline** FM-058 `liquidity_sweep` | `prev(last_swing_*_price)` causal swing k=`swing_window` | `close <= ref` / `close >= ref` | **Every bar** |

Resolver SWEEP entry uses the **pipeline** flag. Confusion-matrix SWEEP↔RANGE residual is therefore expected even with perfect funnel/lifecycle.

## Formula trace

### Engine (`crt_engine_v2.RangeDetector`)

```
detect_htf_range(candles):
    h_ref = max(c.high for c in candles)
    l_ref = min(c.low  for c in candles)

detect_sweep(candle, active_range):
    swept_high = high > h_ref and close < h_ref   # → SHORT
    swept_low  = low  < l_ref and close > l_ref   # → LONG
```

- **Init range** (`backtest` + `initialise_range`): candles = completed HTF window (`htf_candles_per_range`=4).
- **On HTF reset** (`process_candle` ~2620): reseed from `candle_buffer[-atr_period:]` (atr_period=14) — **not** the 4-bar HTF window.
- **State gate:** sweep only attempted when `current_state == RANGE`.
- **Same-bar after reset:** fall-through allows sweep on freshly seeded range (deadlock fix comment at 2626–2629).

### Pipeline (`feature_pipeline.compute_structure_liquidity`)

```
k = swing_window  # default 2; pivot width 2k+1, causal delay k
last_swing_*_price = causal delayed ffill of centered pivots
ref_high = last_swing_high_price.shift(1)
ref_low  = last_swing_low_price.shift(1)
sweep_high = (high > ref_high) & (close <= ref_high)  # +1
sweep_low  = (low  < ref_low)  & (close >= ref_low)   # -1
liquidity_sweep = where(sweep_high, 1, where(sweep_low, -1, 0))
sweep_detected  = liquidity_sweep != 0
```

- Reference = **last confirmed local pivot**, not HTF session range.
- Publication delay k means ref is older than the live engine HTF box.
- Evaluated on **all** bars; no RANGE state gate.

## Quantitative comparison

| Measure | Count / value |
|---------|---------------|
| Bars | 47,275 |
| Engine geometry fires | 5,001 |
| Pipeline `liquidity_sweep` fires | 7,542 |
| Engine STATE_TRANSITION → SWEEP | 3,428 |
| Both geometries (intersection) | 2,611 |
| Engine-only geometry | 2,390 |
| Pipeline-only geometry | 4,931 |
| **Jaccard (engine geom ∩ pipeline)** | **0.263** |
| Direction agree on both | 2,568 / 2,611 |

### Against engine admitted SWEEP events

| Detector | Precision | Recall | F1 |
|----------|-----------|--------|-----|
| Pipeline liquidity_sweep | 0.073 | 0.160 | 0.100 |
| Engine geometry (no state gate) | 0.068 | 0.100 | 0.081 |

| Event ∩ pipeline | 547 |
| Event ∩ engine geom | 342 |
| Event missing from pipeline | 2,881 |
| Event missing from engine geom replay | 3,086 |

### Range span (engine active_range when present)

| Stat | Value |
|------|-------|
| Bars with range | 47,272 |
| Mean H−L span | 25.5852 |
| Median span | 17.4300 |
| P90 span | 51.3360 |
| Seeded from HTF-4 | 4 |
| Reseeded atr_period | 47,268 |

## Interpretation (why resolver SWEEP↔RANGE persists)

1. **Different anchors:** swing pivot ≠ HTF box. Pipeline can fire on a local wick through a 5-bar pivot while price is deep inside the engine HTF range.
2. **Different cadence:** pipeline fires every bar; engine only admits from RANGE (and after HTF reset fall-through). Geometry fire count ≫ admitted events.
3. **Close rule:** `<=` vs `<` is minor; anchor mismatch dominates.
4. **Range reseed dualism (engine-internal):** init uses 4-bar HTF window; HTF-change reseed uses last 14 ATR bars — refs jump in size/level.
5. **Resolver implication:** funnel/lifecycle can only enforce *state legality*; they cannot make last-swing sweeps equal HTF-range sweeps. SWEEP bar parity requires either sharing `active_range` with the engine or a new FM that uses the same HTF box.

## Sample disagreements

### Engine geometry only (pipeline silent)

| idx | HTF | high | low | close | h_ref | l_ref | eng | pipe | event |
|-----|-----|------|-----|-------|-------|-------|-----|------|-------|
| 8 | XAUUSD-HTF-000002 | 2423.11 | 2421.64 | 2421.91 | 2422.32 | 2420.9 | 1 | 0 | 0 |
| 10 | XAUUSD-HTF-000002 | 2422.92 | 2420.79 | 2421.75 | 2422.32 | 2420.9 | 1 | 0 | 0 |
| 12 | XAUUSD-HTF-000003 | 2423.03 | 2419.93 | 2422.17 | 2423.2 | 2420.46 | -1 | 0 | 0 |
| 13 | XAUUSD-HTF-000003 | 2423.40 | 2421.11 | 2421.52 | 2423.2 | 2420.46 | 1 | 0 | 0 |
| 18 | XAUUSD-HTF-000004 | 2424.73 | 2420.67 | 2421.96 | 2423.4 | 2419.39 | 1 | 0 | 0 |
| 22 | XAUUSD-HTF-000005 | 2419.11 | 2415.75 | 2416.33 | 2426.54 | 2416.0 | -1 | 0 | 0 |
| 24 | XAUUSD-HTF-000006 | 2414.94 | 2412.36 | 2412.93 | 2426.54 | 2412.64 | -1 | 0 | 0 |
| 25 | XAUUSD-HTF-000006 | 2416.08 | 2412.48 | 2415.76 | 2426.54 | 2412.64 | -1 | 0 | 0 |

### Pipeline only (engine geometry silent)

| idx | HTF | high | low | close | h_ref | l_ref | eng | pipe | event |
|-----|-----|------|-----|-------|-------|-------|-----|------|-------|
| 92 | XAUUSD-HTF-000023 | 2380.95 | 2378.47 | 2379.38 | 2390.76 | 2374.98 | 0 | 1 | 0 |
| 93 | XAUUSD-HTF-000023 | 2380.83 | 2379.24 | 2380.56 | 2390.76 | 2374.98 | 0 | 1 | 1 |
| 143 | XAUUSD-HTF-000036 | 2367.79 | 2365.78 | 2366.44 | 2367.79 | 2355.18 | 0 | 1 | 0 |
| 167 | XAUUSD-HTF-000042 | 2341.83 | 2340.05 | 2341.03 | 2369.53 | 2340.05 | 0 | -1 | 1 |
| 191 | XAUUSD-HTF-000048 | 2333.69 | 2331.89 | 2332.04 | 2334.23 | 2327.03 | 0 | 1 | 0 |
| 192 | XAUUSD-HTF-000048 | 2332.42 | 2330.73 | 2331.41 | 2334.23 | 2327.03 | 0 | 1 | 0 |
| 200 | XAUUSD-HTF-000050 | 2334.60 | 2332.33 | 2333.43 | 2335.24 | 2326.82 | 0 | 1 | 0 |
| 227 | XAUUSD-HTF-000057 | 2341.04 | 2339.58 | 2340.20 | 2341.04 | 2334.2 | 0 | 1 | 0 |

### Engine admitted SWEEP, pipeline silent

| idx | HTF | high | low | close | h_ref | l_ref | eng | pipe | event |
|-----|-----|------|-----|-------|-------|-------|-----|------|-------|
| 21 | XAUUSD-HTF-000005 | 2419.52 | 2417.46 | 2418.78 | 2426.54 | 2416.0 | 0 | 0 | 1 |
| 27 | XAUUSD-HTF-000007 | 2413.90 | 2412.19 | 2412.93 | 2426.54 | 2412.19 | 0 | 0 | 1 |
| 49 | XAUUSD-HTF-000012 | 2418.01 | 2415.68 | 2415.99 | 2418.49 | 2410.68 | 0 | 0 | 1 |
| 65 | XAUUSD-HTF-000016 | 2395.58 | 2384.09 | 2386.33 | 2416.66 | 2404.79 | 0 | 0 | 1 |
| 71 | XAUUSD-HTF-000018 | 2393.09 | 2388.08 | 2392.12 | 2415.1 | 2382.27 | 0 | 0 | 1 |
| 77 | XAUUSD-HTF-000019 | 2393.26 | 2388.58 | 2389.52 | 2412.8 | 2382.27 | 0 | 0 | 1 |
| 86 | XAUUSD-HTF-000021 | 2379.66 | 2376.87 | 2377.33 | 2395.09 | 2374.98 | 0 | 0 | 1 |
| 97 | XAUUSD-HTF-000024 | 2382.22 | 2380.81 | 2382.08 | 2381.35 | 2374.98 | 0 | 0 | 1 |

## Recommendations

| Option | Effect | Cost |
|--------|--------|------|
| **A. Freeze** SWEEP as soft-aligned | Honest about geometry gap; keep funnel | Zero |
| **B. HTF-range FM** (new feature) | Pipeline can match engine geom | Ontology + pipeline work |
| **C. Feed engine `active_range` into resolver** | Exact geom if engine runs | Couples research layer to engine |
| **D. Threshold-tune liquidity_sweep** | Will not close Jaccard gap | Wasted |

**Recommended default:** A unless a program explicitly needs SWEEP bar-parity. Do not threshold-tune (D).

## Authority

Research / documentation only. Does not enable `crt_state`. Does not change production CRT engine.

