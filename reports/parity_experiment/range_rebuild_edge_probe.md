# CRT Range-Rebuild Edge Probe (OBSERVATION_ONLY)

> Generated: 2026-08-05T13:02:35.093628
>
> **Authority:** research only. No production behavior change.
> Purpose: classify residual SWEEP↔RANGE cells after B1 as range-ref
> divergence vs sticky/lifecycle vs false-positive signal.

## Inputs

| Field | Value |
|-------|-------|
| OHLCV | `data\mt5\XAUUSD_M15.csv` |
| Events | `results\run_20260805_105350_XAUUSD\XAUUSD_events.jsonl` |
| Aligned bars | **47,197** |
| Sweep geometry | `htf_range` |
| range_atr_period | `14` |

## Agreement (aligned slice)

- Exact state match: **29,367 / 47,197 (62.22%)**
- Both ranges ready: **47,197**
- Range refs match (both ready + eps): **11,709** (24.81% of both-ready)

## Active-range reference error (both ready)

| Stat | Value |
|------|------:|
| n_both_ready | 47197 |
| frac_exact_match | 0.248088 |
| mean_abs_dh | 5.4082 |
| mean_abs_dl | 5.57427 |
| median_abs_dh | 0.07 |
| median_abs_dl | 0.05 |
| p90_abs_dh | 13.08 |
| p90_abs_dl | 14.72 |

## SWEEP residual classification

- Engine SWEEP → Resolver RANGE: **5,698**
- Engine RANGE → Resolver SWEEP: **5,724**

### Class histogram (all aligned bars)

| Class | N | % |
|-------|--:|--:|
| `AGREE_OTHER` | 28,330 | 60.03% |
| `E_RANGE_R_SWEEP__range_ref_diverge` | 5,312 | 11.25% |
| `NON_SWEEP_MISMATCH` | 5,291 | 11.21% |
| `E_SWEEP_R_RANGE__range_ref_diverge` | 3,916 | 8.30% |
| `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 1,782 | 3.78% |
| `AGREE_SWEEP` | 1,037 | 2.20% |
| `SWEEP_MIXED__eng_EXPANSION__res_SWEEP` | 730 | 1.55% |
| `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 411 | 0.87% |
| `SWEEP_MIXED__eng_SWEEP__res_EXPANSION` | 224 | 0.47% |
| `SWEEP_MIXED__eng_DISPLACEMENT__res_SWEEP` | 69 | 0.15% |
| `SWEEP_MIXED__eng_SWEEP__res_SHADOW_PENDING` | 48 | 0.10% |
| `SWEEP_MIXED__eng_SWEEP__res_DISPLACEMENT` | 29 | 0.06% |
| `SWEEP_MIXED__eng_SWEEP__res_RETEST` | 10 | 0.02% |
| `SWEEP_MIXED__eng_SHADOW_PENDING__res_SWEEP` | 3 | 0.01% |
| `SWEEP_MIXED__eng_RETEST__res_SWEEP` | 3 | 0.01% |
| `SWEEP_MIXED__eng_EXECUTION__res_SWEEP` | 1 | 0.00% |
| `E_RANGE_R_SWEEP__sticky_resolver` | 1 | 0.00% |

### Interpretation guide

| Class prefix | Meaning | Next lever |
|--------------|---------|------------|
| `range_ref_diverge` | h_ref/l_ref disagree | rebuild window / seed timing / protect-state carry |
| `sticky_or_lifecycle` | engine holds SWEEP without founding sig this bar | age/HTF exit parity |
| `resolver_fp_signal` | resolver detects HTF sweep, engine not in SWEEP | engine already in other state / reset race |
| `both_signal_engine_not_in_sweep` | geometry agrees, state machine disagrees | funnel / state legality |
| `resolver_range_not_ready` | resolver missing active_range | seed_ohlc coverage |

## Sample bars (first 25 of each residual cell)

### Engine SWEEP → Resolver RANGE

| idx | eng | res | class | eng_h | res_h | eng_l | res_l | eng_sig | res_sig | reset |
|----:|-----|-----|-------|------:|------:|------:|------:|--------:|--------:|:-----:|
| 79 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2395.0900 | 2395.1800 | 2386.7900 | 2382.2700 | 0 | 0 | 0 |
| 80 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2395.0900 | 2395.1800 | 2386.7900 | 2382.2700 | 0 | 0 | 0 |
| 81 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2395.1800 | 2395.1800 | 2378.6200 | 2382.2700 | 0 | 0 | 1 |
| 88 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2395.0900 | 2395.0900 | 2374.9800 | 2374.9800 | 0 | 0 | 0 |
| 89 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2394.3900 | 2395.0900 | 2374.9800 | 2374.9800 | 0 | 0 | 1 |
| 95 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2390.7600 | 2381.3500 | 2374.9800 | 2374.9800 | 0 | 0 | 0 |
| 99 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2382.2200 | 2382.7900 | 2376.8700 | 2376.8700 | 0 | 0 | 0 |
| 100 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2382.2200 | 2382.7900 | 2376.8700 | 2376.8700 | 0 | 0 | 0 |
| 101 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2383.7400 | 2382.7900 | 2377.5300 | 2376.8700 | 0 | 0 | 1 |
| 107 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2383.7400 | 2383.7400 | 2369.1100 | 2366.7700 | 0 | 0 | 0 |
| 108 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2383.7400 | 2383.7400 | 2369.1100 | 2366.7700 | 0 | 0 | 0 |
| 109 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2383.7400 | 2383.7400 | 2366.7700 | 2366.7700 | 0 | 0 | 1 |
| 123 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2375.7400 | 2373.9900 | 2367.9400 | 2358.3400 | 0 | 0 | 0 |
| 143 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2367.5500 | 2367.7900 | 2355.1800 | 2355.1800 | 1 | 0 | 0 |
| 144 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2367.5500 | 2367.7900 | 2355.1800 | 2355.1800 | 0 | 0 | 0 |
| 145 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2369.0800 | 2367.7900 | 2355.1900 | 2355.1800 | 0 | 0 | 1 |
| 148 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2369.0800 | 2369.4500 | 2355.1900 | 2356.2800 | 1 | 0 | 0 |
| 149 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2369.4500 | 2369.4500 | 2358.8800 | 2356.2800 | 0 | 0 | 1 |
| 156 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2369.9000 | 2369.9000 | 2360.5600 | 2350.7000 | 0 | 0 | 0 |
| 157 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2369.9000 | 2369.9000 | 2346.6700 | 2350.7000 | 0 | 0 | 1 |
| 171 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2363.9500 | 2351.0000 | 2334.7200 | 2332.0200 | 0 | 0 | 0 |
| 176 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2350.1300 | 2350.1300 | 2331.8600 | 2331.8600 | 0 | 0 | 0 |
| 177 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2350.1300 | 2350.1300 | 2331.8600 | 2331.8600 | 0 | 0 | 1 |
| 204 | SWEEP | RANGE | `E_SWEEP_R_RANGE__range_ref_diverge` | 2335.2400 | 2335.2400 | 2325.6400 | 2325.4300 | 0 | 0 | 0 |
| 205 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2335.2400 | 2335.2400 | 2325.4300 | 2325.4300 | 0 | 0 | 1 |

### Engine RANGE → Resolver SWEEP

| idx | eng | res | class | eng_h | res_h | eng_l | res_l | eng_sig | res_sig | reset |
|----:|-----|-----|-------|------:|------:|------:|------:|--------:|--------:|:-----:|
| 98 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2382.2200 | 2381.3500 | 2376.8700 | 2374.9800 | 0 | 0 | 0 |
| 102 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2383.7400 | 2382.7900 | 2377.5300 | 2376.8700 | 0 | 1 | 0 |
| 140 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2367.1900 | 2367.1900 | 2355.0000 | 2355.1800 | 1 | 1 | 0 |
| 141 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2367.5500 | 2367.1900 | 2355.1800 | 2355.1800 | 0 | 0 | 1 |
| 142 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2367.5500 | 2367.1900 | 2355.1800 | 2355.1800 | 0 | 0 | 0 |
| 146 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2369.0800 | 2367.7900 | 2355.1900 | 2355.1800 | 1 | 1 | 0 |
| 152 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2369.4500 | 2369.4500 | 2358.8800 | 2360.7800 | 0 | -1 | 0 |
| 154 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2369.9000 | 2369.4500 | 2360.5600 | 2360.7800 | 0 | 1 | 0 |
| 162 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2369.9000 | 2369.9000 | 2340.4300 | 2341.5900 | 0 | -1 | 0 |
| 168 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2369.9000 | 2369.5300 | 2340.4300 | 2340.0500 | -1 | -1 | 0 |
| 170 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2363.9500 | 2369.5300 | 2334.7200 | 2340.0500 | 0 | 0 | 0 |
| 174 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2350.1300 | 2351.0000 | 2331.8600 | 2332.0200 | 0 | 0 | 0 |
| 180 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2350.1300 | 2345.3600 | 2331.8600 | 2331.0100 | -1 | -1 | 0 |
| 181 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2342.9900 | 2345.3600 | 2330.6200 | 2331.0100 | 0 | 0 | 1 |
| 182 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2342.9900 | 2345.3600 | 2330.6200 | 2331.0100 | 0 | 0 | 0 |
| 202 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2335.2400 | 2335.2400 | 2325.6400 | 2326.8200 | -1 | -1 | 0 |
| 216 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2335.1800 | 2339.3600 | 2325.4300 | 2325.4300 | 0 | 1 | 0 |
| 217 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2339.5900 | 2339.3600 | 2328.5200 | 2325.4300 | 0 | 1 | 1 |
| 218 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2339.5900 | 2339.3600 | 2328.5200 | 2325.4300 | 0 | 0 | 0 |
| 222 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2340.6500 | 2339.5900 | 2330.5600 | 2329.4300 | 0 | 1 | 0 |
| 226 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2340.6500 | 2340.6500 | 2333.2400 | 2332.1200 | 1 | 1 | 0 |
| 229 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2343.2700 | 2341.0400 | 2335.2500 | 2334.2000 | 0 | 1 | 1 |
| 230 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2343.2700 | 2341.0400 | 2335.2500 | 2334.2000 | 0 | 0 | 0 |
| 234 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2343.9200 | 2343.2700 | 2336.1400 | 2335.2500 | 0 | 1 | 0 |
| 242 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2343.9200 | 2343.9200 | 2337.0200 | 2336.6800 | -1 | -1 | 0 |

## Engine reconstruction meta

```json
{
  "n_bars": 47275,
  "warmup": 78,
  "atr_period": 14,
  "htf_candles": 4,
  "n_seed": 1,
  "n_rebuild_reset": 10683,
  "n_ready": 47197,
  "timeline_notes": [
    "Skipped 163 RESET event(s) whose state_from disagreed with the reconstructed state (engine state_from is authoritative; these resets applied to a state the engine was not in at that bar). This is what reconciles reconstructed EXPANSION dwell with state_distribution.",
    "RESOLUTION appeared in events but not in exit timeline (check ordering)."
  ]
}
```

## Resolver meta

```json
{
  "n_raw": 47275,
  "n_resolved": 47197,
  "first_src": 78,
  "sweep_geometry": "htf_range",
  "range_atr_period": 14,
  "resolver_counts": {
    "RANGE": 36959,
    "SWEEP": 7567,
    "DISPLACEMENT": 353,
    "SHADOW_PENDING": 335,
    "EXPANSION": 1890,
    "RETEST": 93
  }
}
```

## Vision dual-geometry note

If `range_ref_diverge` dominates residual SWEEP cells, Vision/ontology should
register **two distinct sweep geometries** as separate nodes (HTF-range vs
last-swing), not one overloaded `liquidity_sweep` state. If sticky/lifecycle
dominates, the residual is state-machine memory, not geometry ontology.

