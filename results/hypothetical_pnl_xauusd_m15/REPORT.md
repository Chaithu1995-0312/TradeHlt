# Hypothetical P&L — XAUUSD M15, CRT spine (native timeframe, production config)

> **HYPOTHETICAL.** Historical simulation only. It is not a `ValidationReport`, not promotable, and not evidence of an edge.

## 1. Data and observation link
- File: `data/XAUUSD_M15.csv` (gitignored, not committed), 47,275 bars, 2024-05-22 01:00 → 2026-05-21 23:45. SHA-256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`.
- It matches the 5-day observation report: **450 bars for May 23–29 2024** (92 / 92 / 82 / 92 / 92 per day).
- The 79-slot observation feature set is not consumed here. `BacktestRunner` builds the 35-dim `CANONICAL_FEATURES` through `FeaturePipeline`.

## 2. Hypothesis (stated, not tuned)
The unchanged production `backtest` section of `configs/production/v1_multi_2026_03.json` (SHA-256 `c788992d…4985`) on its native timeframe. `htf=4` here means 1-hour ranges built from M15 bars. Costs: slippage random(0, 0.1×ATR) with seed 42, spread 0.0002, 1% risk with compounding, warmup 30, gap reset 120 min. Command:
`python src/runtime/backtest_v2.py --csv data/XAUUSD_M15.csv --instrument XAUUSD --output results/hypothetical_pnl_xauusd_m15/baseline`
Variant (clearly labeled): the section 6 runtime patch from the H1 report, so an HTF rollover cannot close a trade in `EXECUTION`. Nothing in `src/` or `configs/` was edited. Output: `exec_protected/`.

## 3. Results

| | Baseline (production) | EXECUTION protected (patch) |
|---|---|---|
| Trades | **10** (6 short, 4 long) | 10 (same entries) |
| Exits | RESET_CLOSE ×10 (1 bar each) | **TP1 ×5, STOPPED ×5** |
| Win rate | 40% | 50% |
| Net P&L | **−13.17R** (raw −13.10R) | **+0.18R** (raw +0.25R) |
| Expectancy / trade | −1.32R (SE 0.93R) | +0.02R (SE 0.31R) |
| Max DD | 13.97R (13.5%) | 2.42R (2.4%) |
| Avg hold | 1 candle | 17.4 candles |
| TP1 / TP2 | 0 / 0 | 5 / 0 |
| Cost drag | 0.07R | — |

Funnel (baseline): 3,665 RANGE→SWEEP, 267 →DISPLACEMENT, 19 →EXPANSION, 11 →RETEST, 11 →EXECUTION, 10 trades. Resets: 11,420 HTF rollovers, 121 session gap, 40 retrace, 1 extension. May 23–29 2024: **no trades**.

## 4. Why the baseline is −13R
- Every baseline trade was force-closed one bar after entry by an HTF rollover (same flaw as the H1 runs, `crt_engine_v2.py:1324-1327`). The close happens at the bar's close, which can lie beyond the stop.
- Two trades dominate: CRT-0002 (−7.89R) and CRT-0005 (−5.39R). In the protected run the same two entries are plain stop-outs at −0.81R and −0.53R. The baseline's forced-close price overshot the stop by many multiples of the risk.
- So the −13R mostly measures how the reset exit is priced, not the setups. Without those two trades the baseline is about +0.1R across 8 trades.

## 5. Interpretation and caveats
- Protected result: +0.02R per trade, SE 0.31R. That is consistent with zero edge. 10 trades is exactly at the validator's hard minimum.
- Timeframe makes little difference to the setups: M15 and the H1/htf=24 run both end up near zero once trades can play out. Neither result establishes an edge.
- Not promotable: no `ConfigValidator` run, and the exit change exists only as a monkeypatch. Re-run determinism is identical, and the unpatched script reproduces the baseline exactly.
- Possible follow-ups (none run): run the validator on the baseline as the real gate, or decide whether the EXECUTION-in-reset behavior is a bug to fix on its own merits, then re-validate.
