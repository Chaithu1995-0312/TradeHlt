# CRT Range-Rebuild Edge Probe (OBSERVATION_ONLY)

> Generated: 2026-08-05T13:16:59.899507
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

- Exact state match: **35,891 / 47,197 (76.05%)**
- Both ranges ready: **47,197**
- Range refs match (both ready + eps): **42,449** (89.94% of both-ready)

## Active-range reference error (both ready)

| Stat | Value |
|------|------:|
| n_both_ready | 47197 |
| frac_exact_match | 0.8994 |
| mean_abs_dh | 3.32214 |
| mean_abs_dl | 3.32144 |
| median_abs_dh | 0 |
| median_abs_dl | 0 |
| p90_abs_dh | 0 |
| p90_abs_dl | 0 |

## SWEEP residual classification

- Engine SWEEP → Resolver RANGE: **3,061**
- Engine RANGE → Resolver SWEEP: **3,427**

### Class histogram (all aligned bars)

| Class | N | % |
|-------|--:|--:|
| `AGREE_OTHER` | 32,204 | 68.23% |
| `NON_SWEEP_MISMATCH` | 3,792 | 8.03% |
| `AGREE_SWEEP` | 3,687 | 7.81% |
| `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 3,391 | 7.18% |
| `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 3,057 | 6.48% |
| `SWEEP_MIXED__eng_EXPANSION__res_SWEEP` | 719 | 1.52% |
| `SWEEP_MIXED__eng_SWEEP__res_DISPLACEMENT` | 248 | 0.53% |
| `SWEEP_MIXED__eng_SHADOW_PENDING__res_SWEEP` | 42 | 0.09% |
| `E_RANGE_R_SWEEP__range_ref_diverge` | 36 | 0.08% |
| `SWEEP_MIXED__eng_DISPLACEMENT__res_SWEEP` | 17 | 0.04% |
| `E_SWEEP_R_RANGE__range_ref_diverge` | 4 | 0.01% |

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
| 99 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2382.7900 | 2382.7900 | 2376.8700 | 2376.8700 | 0 | 0 | 1 |
| 103 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2383.7400 | 2383.7400 | 2377.5300 | 2377.5300 | 0 | 0 | 1 |
| 143 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2367.7900 | 2367.7900 | 2355.1800 | 2355.1800 | 0 | 0 | 1 |
| 147 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2369.4500 | 2369.4500 | 2356.2800 | 2356.2800 | 0 | 0 | 1 |
| 155 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2369.9000 | 2369.9000 | 2350.7000 | 2350.7000 | 0 | 0 | 1 |
| 163 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2369.9000 | 2369.9000 | 2340.4300 | 2340.4300 | 0 | 0 | 1 |
| 171 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2351.0000 | 2351.0000 | 2332.0200 | 2332.0200 | 0 | 0 | 1 |
| 175 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2350.1300 | 2350.1300 | 2331.8600 | 2331.8600 | 0 | 0 | 1 |
| 183 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2339.0500 | 2339.0500 | 2327.0300 | 2327.0300 | 0 | 0 | 1 |
| 219 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2339.5900 | 2339.5900 | 2329.4300 | 2329.4300 | 0 | 0 | 1 |
| 223 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2340.6500 | 2340.6500 | 2332.1200 | 2332.1200 | 0 | 0 | 1 |
| 227 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2341.0400 | 2341.0400 | 2334.2000 | 2334.2000 | 0 | 0 | 1 |
| 231 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2343.2700 | 2343.2700 | 2335.2500 | 2335.2500 | 0 | 0 | 1 |
| 235 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2343.9200 | 2343.9200 | 2336.1400 | 2336.1400 | 0 | 0 | 1 |
| 243 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2343.9200 | 2343.9200 | 2335.6200 | 2335.6200 | 0 | 0 | 1 |
| 247 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2347.4200 | 2347.4200 | 2335.6200 | 2335.6200 | 0 | 0 | 1 |
| 251 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2347.4200 | 2347.4200 | 2335.5600 | 2335.5600 | 0 | 0 | 1 |
| 271 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2336.7900 | 2336.7900 | 2331.9100 | 2331.9100 | 0 | 0 | 1 |
| 279 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2340.7000 | 2340.7000 | 2331.9100 | 2331.9100 | 0 | 0 | 1 |
| 283 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2340.7500 | 2340.7500 | 2331.9100 | 2331.9100 | 0 | 0 | 1 |
| 295 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2346.4800 | 2346.4800 | 2334.5100 | 2334.5100 | 0 | 0 | 1 |
| 299 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2347.6300 | 2347.6300 | 2334.5100 | 2334.5100 | 0 | 0 | 1 |
| 315 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2344.6600 | 2344.6600 | 2338.1700 | 2338.1700 | 0 | 0 | 1 |
| 319 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2346.2400 | 2346.2400 | 2338.1700 | 2338.1700 | 0 | 0 | 1 |
| 343 | SWEEP | RANGE | `E_SWEEP_R_RANGE__sticky_or_lifecycle` | 2358.5600 | 2358.5600 | 2343.2500 | 2343.2500 | 0 | 0 | 1 |

### Engine RANGE → Resolver SWEEP

| idx | eng | res | class | eng_h | res_h | eng_l | res_l | eng_sig | res_sig | reset |
|----:|-----|-----|-------|------:|------:|------:|------:|--------:|--------:|:-----:|
| 96 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2381.3500 | 2381.3500 | 2374.9800 | 2374.9800 | 1 | 1 | 0 |
| 102 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2382.7900 | 2382.7900 | 2376.8700 | 2376.8700 | 1 | 1 | 0 |
| 124 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2373.9900 | 2373.9900 | 2358.3400 | 2358.3400 | -1 | -1 | 0 |
| 140 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2367.1900 | 2367.1900 | 2355.1800 | 2355.1800 | 1 | 1 | 0 |
| 146 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2367.7900 | 2367.7900 | 2355.1800 | 2355.1800 | 1 | 1 | 0 |
| 152 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2369.4500 | 2369.4500 | 2360.7800 | 2360.7800 | -1 | -1 | 0 |
| 161 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2369.9000 | 2369.9000 | 2341.5900 | 2341.5900 | -1 | -1 | 0 |
| 168 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2369.5300 | 2369.5300 | 2340.0500 | 2340.0500 | -1 | -1 | 0 |
| 172 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2351.0000 | 2351.0000 | 2332.0200 | 2332.0200 | -1 | -1 | 0 |
| 180 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2345.3600 | 2345.3600 | 2331.0100 | 2331.0100 | -1 | -1 | 0 |
| 196 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2333.6900 | 2333.6900 | 2327.0300 | 2327.0300 | -1 | -1 | 0 |
| 202 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2335.2400 | 2335.2400 | 2326.8200 | 2326.8200 | -1 | -1 | 0 |
| 216 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2339.3600 | 2339.3600 | 2325.4300 | 2325.4300 | 1 | 1 | 0 |
| 221 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2339.5900 | 2339.5900 | 2329.4300 | 2329.4300 | 1 | 1 | 0 |
| 226 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2340.6500 | 2340.6500 | 2332.1200 | 2332.1200 | 1 | 1 | 0 |
| 229 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2341.0400 | 2341.0400 | 2334.2000 | 2334.2000 | 1 | 1 | 0 |
| 234 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2343.2700 | 2343.2700 | 2335.2500 | 2335.2500 | 1 | 1 | 0 |
| 242 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2343.9200 | 2343.9200 | 2336.6800 | 2336.6800 | -1 | -1 | 0 |
| 244 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2343.9200 | 2343.9200 | 2335.6200 | 2335.6200 | 1 | 1 | 0 |
| 249 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2347.4200 | 2347.4200 | 2335.6200 | 2335.6200 | -1 | -1 | 0 |
| 269 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2336.9800 | 2336.9800 | 2332.0000 | 2332.0000 | -1 | -1 | 0 |
| 277 | RANGE | SWEEP | `E_RANGE_R_SWEEP__range_ref_diverge` | 2338.2900 | 2336.7900 | 2331.9100 | 2331.9100 | 0 | 1 | 0 |
| 281 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2340.7000 | 2340.7000 | 2331.9100 | 2331.9100 | 1 | 1 | 0 |
| 293 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2340.7500 | 2340.7500 | 2334.5100 | 2334.5100 | 1 | 1 | 0 |
| 296 | RANGE | SWEEP | `E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep` | 2346.4800 | 2346.4800 | 2334.5100 | 2334.5100 | 1 | 1 | 0 |

## Engine reconstruction meta

```json
{
  "n_bars": 47275,
  "warmup": 78,
  "atr_period": 14,
  "htf_candles": 4,
  "n_seed": 1,
  "n_rebuild_reset": 10839,
  "n_ready": 47197,
  "timeline_notes": [
    "RESOLUTION appeared in events but not in exit timeline (check ordering)."
  ],
  "index_remap": {
    "n_events": 18147,
    "n_miss_timestamp": 0,
    "delta_mode": [
      74,
      18026
    ],
    "delta_histogram_top": [
      [
        74,
        18026
      ],
      [
        0,
        121
      ]
    ]
  }
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
    "RANGE": 38462,
    "SWEEP": 7892,
    "DISPLACEMENT": 335,
    "SHADOW_PENDING": 46,
    "EXPANSION": 447,
    "RETEST": 15
  },
  "engine_reset_injection": 10840
}
```

## Vision dual-geometry note

If `range_ref_diverge` dominates residual SWEEP cells, Vision/ontology should
register **two distinct sweep geometries** as separate nodes (HTF-range vs
last-swing), not one overloaded `liquidity_sweep` state. If sticky/lifecycle
dominates, the residual is state-machine memory, not geometry ontology.

