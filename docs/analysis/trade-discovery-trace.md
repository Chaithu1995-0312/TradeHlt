# TRADE_DISCOVERY_TRACE

## Runtime Artifact Boundary

Run requested: `run_20260525_133555`

Matched runtime artifacts:

- Result folder: `results/run_20260525_133607_BNBUSDT`
- Log folder: `logs/run_20260525_133555/BNBUSDT`
- Config dump: `logs/config_dumps/BNBUSDT_run_20260525_080607_config.json`
- Input CSV: `data/yfinance/BNBUSDT_20240522_20260521_Part_1_Isolated.csv`

Artifact availability:

- Accepted trades: present in `BNBUSDT_trades.csv`
- State transitions: present in `BNBUSDT_events.jsonl`
- Entry journal: present in `BNBUSDT_fusion.jsonl`
- EngineRunner collector telemetry: UNKNOWN; no `flow_collector.log` exists under `logs/run_20260525_133555/BNBUSDT`
- EngineRunner runtime log: UNKNOWN; no `flow_engine_runner.log` exists under `logs/run_20260525_133555/BNBUSDT`
- BitNet runtime evaluation: not evaluated; latest config has `crt_engine.use_bitnet=false`

Index note:

- `BNBUSDT_trades.csv.candle_idx` is the backtest loop/raw-row-oriented candle index written by `BacktestRunner`.
- `BNBUSDT_events.jsonl.candle_index` is the CRT engine event index after its own runtime indexing.
- Raw OHLC is matched by timestamp, not by event-log numeric index.

Source flow verified:

`src/runtime/backtest_v2.py -> CRTEngine.process_candle -> state_path append -> TRADE_OPENED journal -> BNBUSDT_trades.csv`

Source references:

- `src/runtime/backtest_v2.py`: `engine.process_candle(candle, htf.current_htf_id)` then `state_path.append(...)`
- `src/runtime/backtest_v2.py`: on `TRADE_OPENED`, timestamp-keyed feature vector lookup is used
- `src/config_layer/crt_engine_v2.py`: soft-confirmation approval calls `approve_with_soft_conf`
- `src/config_layer/crt_engine_v2.py`: `approve_with_soft_conf` accepts `Tier 1` when `S >= tier_1_threshold`, `Tier 2` when `S >= tier_2_threshold`
- `src/core/fusion_engine.py`: EngineRunner Fusion equation is weighted score over CRT, Gaussian, ZoneGate, RR, and optional strategy consensus

Run compression:

- CSV candles: `14016`
- Feature pipeline output: `13938`
- Feature rows dropped: `78`
- State distribution:
  - `RANGE`: `6689`
  - `SWEEP`: `1095`
  - `DISPLACEMENT`: `184`
  - `EXPANSION`: `6005`
  - `RETEST`: `7`
  - `EXECUTION`: `6`
- Accepted executable opportunities: `2`
- Rejected trades in summary: `0`

## Fusion Equation From Source

EngineRunner Fusion source equation from `src/core/fusion_engine.py`:

```text
total_w =
  w_crt + w_gaussian + w_zonegate + w_rr + w_consensus

weighted_fusion_score =
  (
    w_crt       * score_crt +
    w_gaussian  * score_gaussian +
    w_zonegate  * score_zonegate +
    w_rr        * score_rr +
    w_consensus * score_consensus
  ) / total_w
```

Config weights from `BNBUSDT_run_20260525_080607_config.json`:

```text
UNKNOWN regime profile default:
w_crt       = 0.4
w_gaussian  = 0.2
w_zone_gate = 0.2
w_rr        = 0.2
w_consensus = 0.0
```

Latest run artifact status:

```text
EngineRunner Fusion input scores: UNKNOWN
Reason: latest run folder has no EngineRunner collector/runtime log, and entry records contain "fusion": {}.
```

## BitNet Gate From Source

Source gate in `src/config_layer/crt_engine_v2.py`:

```text
if config.use_bitnet:
    bitnet_main_score = bitnet_score(features)
    reject if bitnet_main_score < 0.55
```

Latest config:

```text
crt_engine.use_bitnet = false
```

Therefore for both accepted trades:

```text
BitNet input vector: UNKNOWN / not evaluated
BitNet confidence: UNKNOWN / not evaluated
BitNet threshold: 0.55 in source, but inactive in this run
BitNet decision: UNKNOWN / not evaluated
```

## Trade CRT-0001

### 1. Candle Index + Timestamp

Accepted trade row:

```text
trade_id: CRT-0001
trade_csv.candle_idx: 5993
opened_at: 2024-07-23T10:00:00
direction: SHORT
event_log.TRADE_OPENED.candle_index: 5966
event_log.TRADE_OPENED.timestamp: 2024-07-23T10:00:00
raw CSV timestamp row: 2024-07-23 10:00:00
```

### 2. Raw OHLC Around Discovery Window

Raw rows are matched by timestamp from the input CSV.

| raw_idx_0_based | timestamp | open | high | low | close | volume |
|---:|---|---:|---:|---:|---:|---:|
| 5985 | 2024-07-23 08:15:00 | 580.4 | 582.9 | 579.8 | 582.7 | 3615.782 |
| 5986 | 2024-07-23 08:30:00 | 582.7 | 586.3 | 582.6 | 584.9 | 6009.85 |
| 5987 | 2024-07-23 08:45:00 | 585.0 | 586.8 | 584.2 | 585.7 | 1832.053 |
| 5988 | 2024-07-23 09:00:00 | 585.7 | 587.6 | 585.5 | 586.4 | 4708.594 |
| 5989 | 2024-07-23 09:15:00 | 586.5 | 589.3 | 586.0 | 588.8 | 2848.809 |
| 5990 | 2024-07-23 09:30:00 | 588.9 | 589.4 | 587.6 | 587.8 | 2694.549 |
| 5991 | 2024-07-23 09:45:00 | 587.8 | 588.0 | 586.1 | 586.4 | 1686.497 |
| 5992 | 2024-07-23 10:00:00 | 586.3 | 587.6 | 585.2 | 587.1 | 1241.164 |
| 5993 | 2024-07-23 10:15:00 | 587.1 | 587.6 | 585.5 | 587.4 | 1816.076 |
| 5994 | 2024-07-23 10:30:00 | 587.4 | 588.0 | 586.1 | 586.2 | 951.837 |
| 5995 | 2024-07-23 10:45:00 | 586.3 | 586.3 | 584.4 | 584.4 | 1763.042 |
| 5996 | 2024-07-23 11:00:00 | 584.4 | 584.7 | 581.4 | 583.6 | 3461.004 |

### 3. CRT State Transitions

Event-log path:

| event_idx | timestamp | transition/event | reason |
|---:|---|---|---|
| 5961 | 2024-07-23T08:45:00 | RESET RANGE -> RANGE | HTF changed: BNBUSDT-HTF-001496 -> BNBUSDT-HTF-001497 |
| 5962 | 2024-07-23T09:00:00 | RANGE -> SWEEP | Sweep @ 587.60000 idx=5962 |
| 5963 | 2024-07-23T09:15:00 | SWEEP -> DISPLACEMENT | Displacement \| body_ratio=0.697 wick=3.30000 |
| 5964 | 2024-07-23T09:30:00 | DISPLACEMENT -> EXPANSION | Bearish expansion \| close=587.80000 disp_close=588.80000 |
| 5965 | 2024-07-23T09:45:00 | EXPANSION -> RETEST | Retest \| depth_abs=0.40000 ceiling=6.80000 |
| 5965 | 2024-07-23T09:45:00 | BEGIN_SOFT_CONF | Retest locked; evaluating soft confirmation manifold |
| 5966 | 2024-07-23T10:00:00 | RETEST -> EXECUTION | Risk approved; entering execution |
| 5966 | 2024-07-23T10:00:00 | TRADE_OPENED | SHORT @ 586.4 |

Runtime metadata at `TRADE_OPENED`:

```text
S_score: 0.5620503975511629
sl: 589.7714285714285
tp1: 583.0285714285715
tp2: 579.657142857143
risk_pct: 0.005
session_name: LONDON
```

### 4. Feature Vector Snapshot

Canonical feature order from `features.feature_schema.CANONICAL_FEATURES`.

```text
open: 586.2999877929688
high: 587.5999755859375
low: 585.2000122070312
close: 587.0999755859375
volume: 1241.1639404296875
volume_ratio: 0.3940555453300476
double_sweep: 0.0
ema_fast: 585.7247314453125
ema_slow: 584.9380493164062
ema_spread: 195.94107055664062
trend_bias: 1.0
trend_strength: 0.17976096272468567
momentum_score: 174.3509063720703
atr: 0.004014891572296619
volatility_ratio: 1.0181818008422852
rsi_14: 69.46107482910156
macd_line: 0.07540281116962433
macd_signal: -0.9684103727340698
macd_hist: 1.8997602462768555
sweep_detected: 0.0
liquidity_sweep: 0.0
break_of_structure: 0.0
swing_high: 0.0
swing_low: 1.0
higher_high: 0.0
lower_low: 0.0
body_size: 0.800000011920929
wick_size: 2.4000000953674316
body_ratio: 0.3333333432674408
volatility_regime: 2.0
session: 1.0
hour_of_day: 10.0
disp_strength: 0.3393939435482025
retest_depth: 0.0
candles_since_retest: 28.0
liquidity_distance: 0.9757575988769531
liquidity_pressure_score: 0.6139272451400757
volume_spike: 0.0
```

CRT cached decision features at retest:

```text
retest_depth: 0.043478260869575965
body_ratio: 0.6969696969696928
disp_strength: 1.374999999999994
retest_index: 5965
session: UNKNOWN
double_sweep: false
```

### 5. Fusion Inputs

Latest-run artifact status:

```text
CRT score: UNKNOWN
Gaussian score: UNKNOWN
RR score: UNKNOWN
Zone score: UNKNOWN
strategy consensus: UNKNOWN
```

Reason:

```text
logs/run_20260525_133555/BNBUSDT has no flow_collector.log and no flow_engine_runner.log.
logs/run_20260525_133555/BNBUSDT/BNBUSDT_fusion.jsonl entry has "fusion": {}.
```

Available CRT soft-confirmation score:

```text
S_score: 0.5620503975511629
```

### 6. Final Fusion Score Equation

EngineRunner Fusion equation from source:

```text
final_score =
  (
    0.4 * CRT_score +
    0.2 * Gaussian_score +
    0.2 * Zone_score +
    0.2 * RR_score +
    0.0 * strategy_consensus
  ) / 1.0
```

Runtime substitution:

```text
final_score =
  (
    0.4 * UNKNOWN +
    0.2 * UNKNOWN +
    0.2 * UNKNOWN +
    0.2 * UNKNOWN +
    0.0 * UNKNOWN
  ) / 1.0
= UNKNOWN
```

CRT soft-confirmation source equation:

```text
S = G^conf_alpha * C^conf_beta
```

Runtime CRT soft-confirmation result:

```text
S = 0.5620503975511629
```

### 7. BitNet Input Vector

```text
UNKNOWN / not evaluated
```

Reason:

```text
crt_engine.use_bitnet=false
state.bitnet_main_score absent
trade row bitnet_score_at_entry=0.0
trade row bitnet_decision_at_entry=""
```

### 8. BitNet Confidence + Threshold + ACCEPT/REJECT

```text
BitNet confidence: UNKNOWN / not evaluated
BitNet source threshold: 0.55
BitNet runtime threshold applied: not applied
BitNet ACCEPT/REJECT: UNKNOWN / not evaluated
```

### 9. Risk Tier Selected

Source tier thresholds:

```text
tier_1_threshold = 0.75
tier_2_threshold = 0.30
```

Runtime:

```text
S_score = 0.5620503975511629
0.30 <= S_score < 0.75
risk tier selected: TIER 2
risk_pct: 0.005
```

### 10. Final Entry / SL / TP

From accepted trade row and `TRADE_OPENED` event:

```text
entry_raw: 586.4
entry_fill: 586.3938816606701
sl: 589.7714285714285
tp1: 583.0285714285715
tp2: 579.657142857143
position_size: 296.07
capital_before: 100000.0
capital_after: 100498.78
```

### 11. Why Neighboring Candles Were Rejected / Not Executable

No explicit `REJECTED` trade event exists for this discovery window. Neighboring candle outcomes from artifacts:

| timestamp | event outcome | artifact reason |
|---|---|---|
| 2024-07-23T08:45:00 | RESET | HTF changed; state reset to RANGE |
| 2024-07-23T09:00:00 | RANGE -> SWEEP | Discovery began; not executable yet |
| 2024-07-23T09:15:00 | SWEEP -> DISPLACEMENT | Structure progressed; not executable yet |
| 2024-07-23T09:30:00 | DISPLACEMENT -> EXPANSION | Structure progressed; not executable yet |
| 2024-07-23T09:45:00 | EXPANSION -> RETEST | Retest locked; soft confirmation began; not executable yet |
| 2024-07-23T10:00:00 | RETEST -> EXECUTION + TRADE_OPENED | Accepted |
| 2024-07-23T10:15:00 | UNKNOWN | No rejection artifact; active trade already open |
| 2024-07-23T11:15:00 | EXECUTION -> RESOLUTION | Trade closed TP1 in CRT event log |
| 2024-07-23T11:45:00 | RESET | Post-resolution reset after STOPPED event |

Compression reason for this window:

```text
Rows before 10:00 were structural setup rows, not executable rows.
The executable opportunity existed only after RETEST -> EXECUTION at 10:00.
Neighboring rows did not emit TRADE_OPENED.
```

## Trade CRT-0002

### 1. Candle Index + Timestamp

Accepted trade row:

```text
trade_id: CRT-0002
trade_csv.candle_idx: 6373
opened_at: 2024-07-27T09:00:00
direction: SHORT
event_log.TRADE_OPENED.candle_index: 6346
event_log.TRADE_OPENED.timestamp: 2024-07-27T09:00:00
raw CSV timestamp row: 2024-07-27 09:00:00
```

### 2. Raw OHLC Around Discovery Window

Raw rows are matched by timestamp from the input CSV.

| raw_idx_0_based | timestamp | open | high | low | close | volume |
|---:|---|---:|---:|---:|---:|---:|
| 6365 | 2024-07-27 07:15:00 | 586.8 | 587.5 | 585.9 | 587.3 | 3174.519 |
| 6366 | 2024-07-27 07:30:00 | 587.4 | 587.9 | 587.3 | 587.8 | 838.683 |
| 6367 | 2024-07-27 07:45:00 | 587.8 | 588.0 | 586.9 | 587.2 | 2831.92 |
| 6368 | 2024-07-27 08:00:00 | 587.2 | 588.4 | 587.1 | 587.7 | 1541.761 |
| 6369 | 2024-07-27 08:15:00 | 587.6 | 587.7 | 586.5 | 586.6 | 973.408 |
| 6370 | 2024-07-27 08:30:00 | 586.7 | 586.9 | 585.9 | 586.2 | 603.132 |
| 6371 | 2024-07-27 08:45:00 | 586.3 | 587.5 | 585.9 | 587.4 | 716.944 |
| 6372 | 2024-07-27 09:00:00 | 587.3 | 588.3 | 587.2 | 588.1 | 756.754 |
| 6373 | 2024-07-27 09:15:00 | 588.1 | 588.1 | 587.4 | 588.0 | 349.752 |
| 6374 | 2024-07-27 09:30:00 | 588.0 | 588.2 | 587.7 | 588.0 | 404.918 |
| 6375 | 2024-07-27 09:45:00 | 588.1 | 588.6 | 587.8 | 588.5 | 526.985 |
| 6376 | 2024-07-27 10:00:00 | 588.5 | 588.9 | 588.2 | 588.9 | 585.61 |

### 3. CRT State Transitions

Event-log path:

| event_idx | timestamp | transition/event | reason |
|---:|---|---|---|
| 6341 | 2024-07-27T07:45:00 | RESET SWEEP -> RANGE | HTF changed: BNBUSDT-HTF-001591 -> BNBUSDT-HTF-001592 |
| 6342 | 2024-07-27T08:00:00 | RANGE -> SWEEP | Sweep @ 588.40000 idx=6342 |
| 6343 | 2024-07-27T08:15:00 | SWEEP -> DISPLACEMENT | Displacement \| body_ratio=0.833 wick=1.20000 |
| 6344 | 2024-07-27T08:30:00 | DISPLACEMENT -> EXPANSION | Bearish expansion \| close=586.20000 disp_close=586.60000 |
| 6345 | 2024-07-27T08:45:00 | EXPANSION -> RETEST | Retest \| depth_abs=0.60000 ceiling=4.08000 |
| 6345 | 2024-07-27T08:45:00 | BEGIN_SOFT_CONF | Retest locked; evaluating soft confirmation manifold |
| 6346 | 2024-07-27T09:00:00 | RETEST -> EXECUTION | Risk approved; entering execution |
| 6346 | 2024-07-27T09:00:00 | TRADE_OPENED | SHORT @ 587.4 |

Runtime metadata at `TRADE_OPENED`:

```text
S_score: 0.553263110788448
sl: 587.9300000000001
tp1: 586.8699999999999
tp2: 586.3399999999998
risk_pct: 0.005
session_name: LONDON
```

### 4. Feature Vector Snapshot

Canonical feature order from `features.feature_schema.CANONICAL_FEATURES`.

```text
open: 587.2999877929688
high: 588.2999877929688
low: 587.2000122070312
close: 588.0999755859375
volume: 756.7540283203125
volume_ratio: 0.6389337778091431
double_sweep: 0.0
ema_fast: 586.981201171875
ema_slow: 585.5807495117188
ema_spread: 716.1787719726562
trend_bias: 1.0
trend_strength: 1.665470838546753
momentum_score: 357.9739074707031
atr: 0.001955449813976884
volatility_ratio: 0.9565216898918152
rsi_14: 73.91304016113281
macd_line: 1.585381269454956
macd_signal: 1.590051531791687
macd_hist: -0.30063819885253906
sweep_detected: 0.0
liquidity_sweep: 0.0
break_of_structure: 0.0
swing_high: 1.0
swing_low: 0.0
higher_high: 0.0
lower_low: 0.0
body_size: 0.800000011920929
wick_size: 1.100000023841858
body_ratio: 0.7272727489471436
volatility_regime: 0.0
session: 1.0
hour_of_day: 9.0
disp_strength: 0.6956521272659302
retest_depth: 0.0
candles_since_retest: 10.0
liquidity_distance: 0.260869562625885
liquidity_pressure_score: 0.8777137398719788
volume_spike: 0.0
```

CRT cached decision features at retest:

```text
retest_depth: 0.20000000000004547
body_ratio: 0.8333333333333017
disp_strength: 1.0120481927711213
retest_index: 6345
session: UNKNOWN
double_sweep: false
```

### 5. Fusion Inputs

Latest-run artifact status:

```text
CRT score: UNKNOWN
Gaussian score: UNKNOWN
RR score: UNKNOWN
Zone score: UNKNOWN
strategy consensus: UNKNOWN
```

Reason:

```text
logs/run_20260525_133555/BNBUSDT has no flow_collector.log and no flow_engine_runner.log.
logs/run_20260525_133555/BNBUSDT/BNBUSDT_fusion.jsonl entry has "fusion": {}.
```

Available CRT soft-confirmation score:

```text
S_score: 0.553263110788448
```

### 6. Final Fusion Score Equation

EngineRunner Fusion equation from source:

```text
final_score =
  (
    0.4 * CRT_score +
    0.2 * Gaussian_score +
    0.2 * Zone_score +
    0.2 * RR_score +
    0.0 * strategy_consensus
  ) / 1.0
```

Runtime substitution:

```text
final_score =
  (
    0.4 * UNKNOWN +
    0.2 * UNKNOWN +
    0.2 * UNKNOWN +
    0.2 * UNKNOWN +
    0.0 * UNKNOWN
  ) / 1.0
= UNKNOWN
```

CRT soft-confirmation source equation:

```text
S = G^conf_alpha * C^conf_beta
```

Runtime CRT soft-confirmation result:

```text
S = 0.553263110788448
```

### 7. BitNet Input Vector

```text
UNKNOWN / not evaluated
```

Reason:

```text
crt_engine.use_bitnet=false
state.bitnet_main_score absent
trade row bitnet_score_at_entry=0.0
trade row bitnet_decision_at_entry=""
```

### 8. BitNet Confidence + Threshold + ACCEPT/REJECT

```text
BitNet confidence: UNKNOWN / not evaluated
BitNet source threshold: 0.55
BitNet runtime threshold applied: not applied
BitNet ACCEPT/REJECT: UNKNOWN / not evaluated
```

### 9. Risk Tier Selected

Source tier thresholds:

```text
tier_1_threshold = 0.75
tier_2_threshold = 0.30
```

Runtime:

```text
S_score = 0.553263110788448
0.30 <= S_score < 0.75
risk tier selected: TIER 2
risk_pct: 0.005
```

### 10. Final Entry / SL / TP

From accepted trade row and `TRADE_OPENED` event:

```text
entry_raw: 587.4
entry_fill: 587.3562093497139
sl: 587.9300000000001
tp1: 586.8699999999999
tp2: 586.3399999999998
position_size: 1751.49
capital_before: 100498.78
capital_after: 99579.16
```

### 11. Why Neighboring Candles Were Rejected / Not Executable

No explicit `REJECTED` trade event exists for this discovery window. Neighboring candle outcomes from artifacts:

| timestamp | event outcome | artifact reason |
|---|---|---|
| 2024-07-27T07:45:00 | RESET | HTF changed; prior sweep reset to RANGE |
| 2024-07-27T08:00:00 | RANGE -> SWEEP | Discovery began; not executable yet |
| 2024-07-27T08:15:00 | SWEEP -> DISPLACEMENT | Structure progressed; not executable yet |
| 2024-07-27T08:30:00 | DISPLACEMENT -> EXPANSION | Structure progressed; not executable yet |
| 2024-07-27T08:45:00 | EXPANSION -> RETEST | Retest locked; soft confirmation began; not executable yet |
| 2024-07-27T09:00:00 | RETEST -> EXECUTION + TRADE_OPENED | Accepted |
| 2024-07-27T09:15:00 | EXECUTION -> RESOLUTION + RESET | Trade stopped; post-resolution reset |
| 2024-07-27T09:30:00 | RESET RANGE -> RANGE | HTF changed |
| 2024-07-27T09:45:00 | RESET RANGE -> RANGE | HTF changed |
| 2024-07-27T10:15:00 | RANGE -> SWEEP | New sweep began, not executable |
| 2024-07-27T10:45:00 | RESET SWEEP -> RANGE | HTF changed before executable sequence completed |

Compression reason for this window:

```text
Rows before 09:00 were structural setup rows, not executable rows.
The executable opportunity existed only after RETEST -> EXECUTION at 09:00.
Neighboring rows either reset on HTF changes, remained pre-execution state, or occurred after the trade had already resolved.
```

