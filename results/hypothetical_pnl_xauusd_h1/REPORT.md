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

## 6. Experiment: protect EXECUTION from HTF-rollover reset (monkeypatched, hypothetical)
Change: at runtime, `ResetLogic.should_reset` ignores an "HTF changed" reset while the state is `EXECUTION`. No file in `src/` or `configs/` was edited. Output: `exp_execution_protected/`. The patch script is a scratchpad file, not in the repo.

| | Baseline | EXECUTION protected |
|---|---|---|
| Trades | 2 | 2 (same entries) |
| Exits | RESET_CLOSE ×2 (1 bar) | **STOPPED ×2** (8 and 10 bars) |
| Win rate | 50% | 0% |
| Net P&L | −0.29R | **−1.98R** |
| Max DD | 0.4% | 2.0% |
| TP1 / TP2 | 0 / 0 | 0 / 0 |

- Trade count did not change. The bottleneck is upstream (930 sweeps → 58 displacements → 2 entries), not the reset after entry.
- Once allowed to run, both shorts were stopped out (2024-07-17 16:00, 2025-07-22 15:00). The baseline's +0.10R on trade 1 came from the early forced close, not from the setup.
- Controls: a re-run is identical (deterministic), and the unpatched run via the same script reproduces the baseline exactly.
- Two trades prove nothing in either direction, and the count is still below the validator's hard gate of 10. This does not justify changing `crt_engine_v2.py`.

## 7. Hypothesis: 24-bar ranges (`--htf 24`, daily ranges on H1) — single pre-chosen value, not tuned
Command: `python src/runtime/backtest_v2.py --csv data/XAUUSD_H1.csv --instrument XAUUSD --htf 24 --output results/hypothetical_pnl_xauusd_h1/htf24`. Everything else is at production defaults. Output: `htf24/`.

| | htf=4 (baseline) | htf=24 |
|---|---|---|
| Trades | 2 | **13** (9 SHORT, 4 LONG) |
| Win rate | 50% | 38.5% |
| Net P&L | −0.29R | +1.87R (raw +2.20R, cost drag 0.33R) |
| Max DD | 0.4% | 1.4% (1.37R) |
| Max loss streak | 1 | 6 |
| TP1 / TP2 / stop hits | 0 / 0 / 0 | 0 / 0 / 0 |
| Avg trade duration | 1 candle | 1 candle |

Funnel: 455 RANGE→SWEEP, 185 →DISPLACEMENT, 66 →EXPANSION, 14 →RETEST, 14 →EXECUTION, 13 trades opened. Resets: 481 HTF rollovers, 146 retrace, 121 session gap, 46 sweep expired, 3 extension.

**Do not read the +1.87R as a result.** Every one of the 13 trades was force-closed after exactly one candle: 12 by an HTF rollover, 1 by a retrace reset (`RESET_CLOSE` ×12, `GAP_RESET_CLOSE` ×1). The cause is the one in section 6: the HTF rollover reset is not suppressed in `EXECUTION` (`crt_engine_v2.py:1324-1327`). No stop, TP1 or TP2 was ever reached. The P&L is the sum of one-bar price changes after entry. By session, 7 of the 13 trades opened off-session (0% wins, −1.67R) and 4 opened in New York (100% wins, +3.80R). At these counts that split is noise.

What did change: 24-bar ranges let setups get through (13 trades against 2), so the bottleneck moved from range length to the exit logic.

Caveats: 13 trades is just above the validator's hard gate of 10, and the run is not promotable. A re-run is identical (deterministic). Section 6's protected-EXECUTION patch was **not** combined with htf=24; that run would be the first one in which trades can reach their stops and targets.

## 8. Hypothesis: 24-bar ranges + EXECUTION protected from HTF-rollover resets (monkeypatched, hypothetical)
Combines section 7 (`--htf 24`) with the section 6 runtime patch (HTF-rollover resets ignored in `EXECUTION`; nothing in `src/` or `configs/` edited). Output: `htf24_exec_protected/`. The patch script is a scratchpad file, not in the repo. The entries are the same 13 setups as section 7. Only the exits differ.

| | §7: htf=24 | §8: htf=24 + EXECUTION protected |
|---|---|---|
| Trades | 13 | 13 |
| Exits | RESET_CLOSE ×12, GAP ×1 (all 1 bar) | **TP1 ×6, STOPPED ×3, GAP_RESET_CLOSE ×3, RESET_CLOSE ×1** |
| Win rate | 38.5% | 53.8% |
| Net P&L | +1.87R | **+2.35R** (raw +2.68R, cost drag 0.33R) |
| Expectancy / trade | +0.14R | +0.18R |
| Max DD | 1.4% (1.37R) | 3.0% (3.07R) |
| Max win / loss streak | 4 / 6 | 4 / 4 |
| Avg duration | 1 candle | 15.8 candles |
| TP1 / TP2 | 0 / 0 | 6 (46%) / 0 |

- **First run where trades could play out.** Six hit TP1 (about +0.85R to +1.03R net each), three hit the stop (about −0.98R to −1.03R), three were closed by a weekend or session-gap reset (−0.18R, −0.53R, −0.51R), and one by a reset after one bar.
- **TP2 was never reached.**
- **Statistical weight is low.** Mean +0.18R per trade, standard deviation 0.88R, standard error 0.25R, t ≈ 0.74. A rough 95% interval for expectancy is −0.35R to +0.71R, which includes zero. Thirteen trades over about two years cannot establish an edge, and the count is only just above the validator's hard gate of 10.
- **Pockets:** New York 4/4 wins (+3.86R) and off-session 29% wins (−1.86R). With 4 and 7 trades these are noise, and cutting by session after seeing this would be overfitting.
- Controls: a re-run is identical (deterministic), and the unpatched run through the same script reproduces §7 exactly.
- Not promotable: no `ConfigValidator` run, and the engine change exists only as a monkeypatch. Whether to make it permanent is a separate decision that needs validation on the M15 data the config was built for.
