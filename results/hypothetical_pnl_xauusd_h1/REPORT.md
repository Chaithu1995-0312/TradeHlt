# Hypothetical P&L — XAUUSD H1, CRT spine (unchanged production config)

> **HYPOTHETICAL.** This is a historical simulation. It is not a `ValidationReport`, not promotable, and not evidence of an edge.

## 1. Observation (not re-derived here)
The 5-day observation report covered **M15** bars from May 23–29 2024 (450 bars, 79 finite feature slots, 46 sweep bars, 16 double-sweep bars).
This run uses a **different corpus**: XAUUSD **H1**, 2024-05-22 01:00 → 2026-05-21 23:00, 11,828 bars.
- File: `data/XAUUSD_H1.csv` (gitignored, not committed). SHA-256 `18cdc82d3b43cd1c06a2305eaa63587bde4c512133b5e82480d255d464bd4ffa`.
- The report's 79-slot feature set is not consumed here. `BacktestRunner` builds the 35-dim `CANONICAL_FEATURES` through `FeaturePipeline`.

## 2. Hypothesis (stated, not tuned)
Rules: the CRT state machine `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION` (`src/config_layer/crt_engine_v2.py`), with engine-derived SL/TP1/TP2.
Costs and fills come from the `backtest` section of `configs/production/v1_multi_2026_03.json` (SHA-256 `c788992d…4985`):

| Param | Value |
|---|---|
| htf_candles_per_range | 4 (**on H1 this means H4 ranges**; the config was designed for M15 → H1) |
| warmup_candles | 30 |
| slippage | random(0, 0.1×ATR), seed 42 |
| spread | 0.0002 × price |
| risk / compounding | 1% / on, capital 100,000 |
| gap reset | 120 min |
| CRT CLI defaults | sweep_age 20, decay 0.10, threshold 0.75 |
| pip_size (XAUUSD) | 0.01 |

Command: `python src/runtime/backtest_v2.py --csv data/XAUUSD_H1.csv --instrument XAUUSD --output results/hypothetical_pnl_xauusd_h1`

## 3. Backtest result

| Metric | Baseline | `--no-slip` |
|---|---|---|
| Trades | **2** | 2 |
| Win rate | 50% | 50% |
| Avg RR (net) | −0.14R | −0.12R |
| Total PnL (net) | −0.29R | −0.23R |
| Max DD | 0.39R / 0.4% | 0.4% |
| Final capital | 99,713 | — |
| TP1 / TP2 hits | 0 / 0 | 0 / 0 |

Trades (both SHORT, both closed `RESET_CLOSE` after 1 candle, with no SL or TP hit):
- CRT-0001: 2024-07-17 08:00, entry 2467.86 → exit 2466.37 (+0.10R)
- CRT-0002: 2025-07-22 05:00, entry 3385.70 → exit 3392.40 (−0.39R)

The May 23–29 2024 slice had **zero trades**.

### Funnel: where setups die
| Transition | Count |
|---|---|
| RANGE → SWEEP | 930 |
| SWEEP → DISPLACEMENT | 58 |
| DISPLACEMENT → EXPANSION | 2 |
| EXPANSION → RETEST → EXECUTION | 2 |

Resets: **2,948 HTF-range rollovers**, 121 session-gap resets and 2 retrace resets. No rejections by the risk gate (2/2 approved). Feature drift: insufficient data (2 of the 30 samples needed).

Determinism: a re-run with seed 42 produced identical summary metrics. `pytest tests -k backtest`: 9 passed.

## 4. Interpretation and caveats
- **The result is structural, not a measure of edge.** With `htf=4` on H1 bars, the reference range rolls every 4 bars. Each rollover resets the state machine (2,948 times). Few setups get through SWEEP → DISPLACEMENT → EXPANSION → RETEST before the next reset, and both opened trades were force-closed by a reset one bar later.
- 2 trades is far below the `ConfigValidator` hard gate (min 10 trades). No statistical conclusion is possible.
- This run tests the M15-calibrated config on H1 data. It is a different hypothesis from the M15 observation report.

## 5. Possible next steps (each is a separate hypothesis; none was run)
1. Run the same config on the M15 corpus the observation report used (its native timeframe).
2. If H1 is the target, pick an htf-per-range that matches the timeframe (e.g. 24 → daily ranges). Set the value up front, not by sweeping, and treat it as a new config that needs `ConfigValidator` before it is trusted.
