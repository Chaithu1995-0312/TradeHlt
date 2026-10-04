# XAUUSD CRT Baseline Trace v1 — Summary

**run_id:** `xauusd-crt-trace-20260731T184653Z-1f028143`  
**target:** 2024-05-22 20:30:00 → 2024-05-23 01:15:00 (16 bars)  
**prefix bars (non-target after init):** 0  
**state at target start/end:** RANGE → RANGE  
**trace sha256:** `90d699a3d230b61ffc23187d8af09653c8b8f33c3a51724bc69f42c602dda00a`  
**completeness:** PARTIAL

## 16-bar matrix

| ts | OHLC | before | guards | true | after | events | class | status |
|---|---|---|---|---|---|---|---|---|
| 2024-05-22 20:30:00 | 2389.44/2390.07/2386.79/2387.55 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 20:45:00 | 2387.53/2388.98/2387.01/2388.29 | RANGE | 1 | 0 | RANGE | 1 | DIVERTED | PARTIAL |
| 2024-05-22 21:00:00 | 2388.27/2390.76/2385.18/2386.13 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 21:15:00 | 2386.13/2386.57/2378.62/2379.39 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 21:30:00 | 2379.38/2381.06/2376.08/2377.0 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 21:45:00 | 2377.26/2379.62/2374.98/2377.86 | RANGE | 1 | 0 | RANGE | 1 | DIVERTED | PARTIAL |
| 2024-05-22 22:00:00 | 2377.89/2380.12/2377.17/2378.2 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 22:15:00 | 2378.2/2379.65/2377.61/2379.38 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 22:30:00 | 2379.38/2379.66/2376.87/2377.33 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 22:45:00 | 2377.33/2379.83/2377.33/2379.37 | RANGE | 1 | 0 | RANGE | 1 | DIVERTED | PARTIAL |
| 2024-05-22 23:00:00 | 2379.3/2380.16/2378.37/2379.07 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 23:15:00 | 2379.07/2380.68/2378.47/2379.09 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 23:30:00 | 2379.09/2379.42/2377.61/2378.36 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-22 23:45:00 | 2378.45/2379.06/2377.53/2378.58 | RANGE | 1 | 0 | RANGE | 1 | DIVERTED | PARTIAL |
| 2024-05-23 01:00:00 | 2379.77/2380.95/2378.47/2379.38 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |
| 2024-05-23 01:15:00 | 2379.36/2380.83/2379.24/2380.56 | RANGE | 1 | 0 | RANGE | 0 | NO_OUTPUT | PARTIAL |

## Canonical feature variation (changed only)

- `open`: min=2377.260009765625 max=2389.43994140625 first=2389.43994140625 last=2379.360107421875
- `high`: min=2379.06005859375 max=2390.760009765625 first=2390.070068359375 last=2380.830078125
- `low`: min=2374.97998046875 max=2387.010009765625 first=2386.7900390625 last=2379.239990234375
- `close`: min=2377.0 max=2388.2900390625 first=2387.550048828125 last=2380.56005859375
- `volume`: min=504.0 max=3461.0 first=1935.0 last=504.0
- `volume_ratio`: min=0.2771972417831421 max=1.1314895153045654 first=0.6250807642936707 last=0.2771972417831421
- `double_sweep`: min=0.0 max=1.0 first=1.0 last=0.0
- `ema_fast`: min=2379.53564453125 max=2391.158935546875 first=2391.158935546875 last=2379.740478515625
- `ema_slow`: min=2383.391357421875 max=2395.874755859375 first=2395.874755859375 last=2383.391357421875
- `ema_spread`: min=-3721.747314453125 max=-2230.502197265625 first=-2230.502197265625 last=-2713.55712890625
- `trend_strength`: min=-1.726539134979248 max=0.06438601762056351 first=-1.726539134979248 last=0.06438601762056351
- `momentum_score`: min=-3593.457763671875 max=1252.392333984375 first=-931.7762451171875 last=877.0484008789062
- `atr`: min=0.001345421769656241 max=0.0021142414771020412 first=0.0021142414771020412 last=0.001345421769656241
- `volatility_ratio`: min=0.45102208852767944 max=1.7813700437545776 first=0.6497806310653687 last=0.49643173813819885
- `rsi_14`: min=16.832971572875977 max=54.890220642089844 first=38.6295166015625 last=31.6039981842041
- `macd_line`: min=-6.809027671813965 max=-4.853909969329834 first=-5.449422359466553 last=-4.853909969329834
- `macd_signal`: min=-6.379249572753906 max=-5.533614158630371 first=-5.617049694061279 last=-5.701376438140869
- `macd_hist_raw`: min=-0.7426271438598633 max=0.847466766834259 first=0.16762718558311462 last=0.847466766834259
- `macd_hist_z`: min=-0.48400425910949707 max=1.4381531476974487 first=0.6037610173225403 last=1.4381531476974487
- `sweep_detected`: min=0.0 max=1.0 first=0.0 last=1.0
- `liquidity_sweep`: min=0.0 max=1.0 first=0.0 last=1.0
- `break_of_structure`: min=-1.0 max=0.0 first=-1.0 last=0.0
- `swing_high`: min=0.0 max=1.0 first=0.0 last=0.0
- `swing_low`: min=0.0 max=1.0 first=0.0 last=1.0
- `higher_high`: min=0.0 max=1.0 first=0.0 last=1.0
- `lower_low`: min=0.0 max=1.0 first=1.0 last=0.0
- `body_size`: min=0.019999999552965164 max=6.739999771118164 first=1.8899999856948853 last=1.2000000476837158
- `candle_range`: min=1.5299999713897705 max=7.949999809265137 first=3.2799999713897705 last=1.590000033378601
- `body_ratio`: min=0.009049774147570133 max=0.847798764705658 first=0.5762194991111755 last=0.7547169923782349
- `volatility_regime`: min=1.0 max=2.0 first=2.0 last=1.0
- `session`: min=0.0 max=4.0 first=2.0 last=0.0
- `hour_of_day`: min=1.0 max=23.0 first=20.0 last=1.0
- `disp_strength`: min=0.00558770727366209 max=1.51024329662323 first=0.3744162917137146 last=0.3746654689311981
- `retest_depth`: min=0.0 max=0.9801406860351562 first=0.714944064617157 last=0.2558720111846924
- `candles_since_retest`: min=0.0 max=14.0 first=1.0 last=0.0
- `liquidity_distance`: min=0.03746654465794563 max=2.9104526042938232 first=0.3843214809894562 last=0.03746654465794563
- `liquidity_pressure_score`: min=0.2333475649356842 max=0.9814411401748657 first=0.8251742124557495 last=0.9814411401748657

## CRT input usage

- `high` class=RAW_OHLC bars=16 canonical=True prov=PROVEN
- `low` class=RAW_OHLC bars=16 canonical=True prov=PROVEN
- `close` class=RAW_OHLC bars=16 canonical=True prov=PROVEN
- `h_ref` class=STATE_MEMORY bars=16 canonical=False prov=PROVEN
- `l_ref` class=STATE_MEMORY bars=16 canonical=False prov=PROVEN

## Config usage


## Executable coupling note

FeaturePipeline 38-vector is **decoupled** from CRT guard evaluation. CRT uses RAW_OHLC + CRT_LOCAL_DERIVED (ATR, body_ratio, wick_size) + STATE_MEMORY + CRTConfig.

