# Feature-schema trace of one week, hour by hour — XAUUSD H1, 2025-07-21 → 07-25

> Descriptive trace of one week. The week is a hindsight choice and the LONG/SELL ranges are hindsight labels, so nothing here is evidence of a predictive edge.

## 1. What was traced
- **Week:** Mon 2025-07-21 → Fri 07-25, 115 hour bars (23 per day), chosen because it holds both a rising and a falling stretch (W4 of the July weekly test, whose week moved −0.30R raw for a BUY).
- **Ranges (hindsight labels):** **LONG** = week open → the bar with the week's highest high (**Wed 07-23 03:00, 3438.82**), 49 bars; **SELL** = the next bar → Friday's end, 66 bars (week low 3325.04 on Fri 18:00). So the up-move ran into Wednesday's early hours, not just Mon–Tue: Mon +47.6, Tue +34.2, then Wed −45.2, Thu −20.1, Fri −31.8.
- **Features:** the 35 `CANONICAL_FEATURES` from `FeaturePipeline` (same code the backtest uses), full per-bar values in `trace.csv`. Signed features checked: `trend_bias`, `ema_spread`, `trend_strength`, `momentum_score`, `macd_line`, `macd_hist`, `rsi_14` (vs 50), `break_of_structure`, `liquidity_sweep`, and `structure_hh_ll` (= `higher_high` − `lower_low`). Full hourly sign grids for all five days: `tables.md`.
- Script: `scripts/analysis/week_feature_trace.py`.

## 2. Day by day: share of hour bars with a positive sign
| Day | Bars | Day move | trend_bias | ema_spread | trend_strength | momentum_score | macd_line | macd_hist | rsi_14 | break_of_structure | liquidity_sweep | structure_hh_ll |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-07-21 Mon | 23 | +47.6 | 100% | 100% | 100% | 65% | 100% | 70% | 83% | 26% | 4% | 30% |
| 2025-07-22 Tue | 23 | +34.2 | 100% | 100% | 52% | 61% | 100% | 35% | 70% | 26% | 4% | 30% |
| 2025-07-23 Wed | 23 | -45.2 | 74% | 74% | 61% | 43% | 78% | 9% | 35% | 0% | 4% | 4% |
| 2025-07-24 Thu | 23 | -20.1 | 0% | 0% | 0% | 35% | 0% | 35% | 0% | 0% | 0% | 0% |
| 2025-07-25 Fri | 23 | -31.8 | 0% | 0% | 43% | 43% | 0% | 74% | 22% | 0% | 0% | 0% |

Reading across the days: the level features (`trend_bias`, `ema_spread`, `macd_line`) are 100% positive Monday and Tuesday, 74–78% on Wednesday (the turn), then **0%** on Thursday and Friday. `rsi_14` goes 83% → 70% → 35% → 0% → 22% positive. The per-bar `momentum_score` just tracks each hour's direction (65%, 61%, 43%, 35%, 43%) and flips about every other bar.

## 3. The turning day, hour by hour (Wednesday; peak bar at 03:00)
**2025-07-23 Wed**  (range labels: LLLSSSSSSSSSSSSSSSSSSSS)
```
hour              01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
bar (close-open)   -  -  +  -  +  -  +  -  +  -  +  +  -  +  -  -  +  -  -  +  +  -  -
trend_bias         +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  -  -  -  -  -  -
ema_spread         +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  -  -  -  -  -  -
trend_strength     +  +  +  +  +  +  +  +  +  +  +  +  +  +  -  -  -  -  -  -  -  -  -
momentum_score     -  -  +  -  +  -  +  -  +  -  +  +  -  +  -  -  +  -  -  +  +  -  -
macd_line          +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  -  -  -  -  -
macd_hist          +  +  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
rsi_14             +  +  +  +  +  +  +  -  -  -  -  +  -  -  -  -  -  -  -  -  -  -  -
break_of_structure 0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  -  -  -  -  0  0  0  0
liquidity_sweep    0  0  +  0  0  0  0  -  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
structure_hh_ll    0  0  +  0  0  0  0  -  0  0  0  0  0  0  0  -  -  -  -  0  0  0  0
```

- Price topped at 03:00, but `trend_bias` and `ema_spread` stayed positive until **18:00** and `macd_line` until **19:00**. By then price had already fallen 40.5 of the 113.8 points between the peak and the week's low (36%); 73.2 points (64%) were still to come.
- `rsi_14` turned below 50 at 08:00 (briefly back above at 12:00), the earliest of the smooth signals; `break_of_structure` showed a bearish break from 16:00.
- `macd_hist` was already negative at 03:00 and stayed negative until Thursday 16:00. During the rising trend (`trend_bias` 100% positive) it was negative on 65% of Tuesday's bars (`macd_hist` is a 50-bar z-score of the histogram, so its sign does not follow the trend).

## 4. Are the features positive in the LONG range and negative in the SELL range?
| Feature | LONG: % positive | LONG: sign matches (+) | SELL: % positive | SELL: sign matches (−) | Next-bar hit (causal) | p |
|---|---|---|---|---|---|---|
| trend_bias | 100% | 100% | 21% | 79% | 68/114 = 60% | 0.05 |
| ema_spread | 100% | 100% | 21% | 79% | 68/114 = 60% | 0.05 |
| trend_strength | 78% | 78% | 32% | 68% | 58/114 = 51% | 0.93 |
| momentum_score | 61% | 61% | 41% | 59% | 58/114 = 51% | 0.93 |
| macd_line | 100% | 100% | 23% | 77% | 67/114 = 59% | 0.07 |
| macd_hist | 53% | 53% | 38% | 62% | 61/114 = 54% | 0.51 |
| rsi_14 | 78% | 78% | 15% | 85% | 61/114 = 54% | 0.51 |
| break_of_structure | 24% | 80% | 0% | 100% | 28/45 = 62% | 0.14 |
| liquidity_sweep | 6% | 50% | 0% | 100% | 4/9 = 44% | 1.00 |
| structure_hh_ll | 31% | 71% | 0% | 100% | 32/54 = 59% | 0.22 |

Mean values by range (signs are valid; the magnitudes of `ema_spread` and `momentum_score` are about 250× too large, see §5):

| Feature | LONG mean | SELL mean |
|---|---|---|
| trend_bias | +1.000 | -0.576 |
| ema_spread | +3576.325 | -2143.277 |
| trend_strength | +0.714 | -0.789 |
| momentum_score | +816.962 | -622.604 |
| macd_line | +8.045 | -4.669 |
| macd_hist | +0.013 | -0.188 |
| rsi_14 | +66.590 | +33.838 |
| break_of_structure | +0.184 | -0.455 |
| liquidity_sweep | +0.000 | -0.045 |
| structure_hh_ll | +0.184 | -0.500 |

- **Mostly yes for the smooth level features.** `trend_bias`, `ema_spread` and `macd_line` are positive on 100% of LONG-range bars and negative on 77–79% of SELL-range bars; `rsi_14` averages 66.6 vs 33.8. These features describe where price has been, and their sign is right in both ranges, but they turn late (§3).
- **No for the per-bar and z-scored ones.** `momentum_score` is only 61% positive in the LONG range and 59% negative in the SELL range; `macd_hist` is 53% positive in LONG and 62% negative in SELL; `trend_strength` flips mid-Tuesday to negative while price was still rising.
- **The structure flags are sparse.** `break_of_structure`, `liquidity_sweep` and `structure_hh_ll` are zero on most bars. When the SELL range shows them, they are always negative (100%), but the LONG range also contains bearish breaks (e.g. Tue 04:00 and 09:00). Part of this is non-causal (§5).
- **Next-bar check (causal, whole week, 114 bars):** the sign at bar t matches the next bar's direction 60% of the time for `trend_bias` and `ema_spread` (68/114, p = 0.05), 59% for `macd_line`, 51–54% for `trend_strength`, `momentum_score`, `macd_hist` and `rsi_14`, and 59–62% on the sparse structure flags (45–54 bars, p = 0.14–0.22). With 10 features tested, bars that are autocorrelated, and one week, this is not evidence of predictive power.

## 5. Quality flags found while tracing (checked in code and by truncation test)
1. **Non-causal features.** Rebuilding the features on data cut at 7 points in the week and comparing the last 3 rows with the full-file values (21 comparisons):
| Feature | Rows that differ |
|---|---|
| volatility_regime | 11 / 21 |
| swing_high | 2 / 21 |
| break_of_structure | 1 / 21 |
| swing_low | 1 / 21 |
| lower_low | 1 / 21 |

Causal (identical in every comparison): open, high, low, close, volume, volume_ratio, double_sweep, ema_fast, ema_slow, ema_spread, trend_bias, trend_strength, momentum_score, atr, volatility_ratio, rsi_14, macd_line, macd_signal, macd_hist, sweep_detected, liquidity_sweep, higher_high, body_size, wick_size, body_ratio, hour_of_day, disp_strength, retest_depth, candles_since_retest
   - `volatility_regime` ranks ATR over the whole file (`feature_pipeline.py:274`), so its value depends on future bars (11 of 21 rows differed).
   - `swing_high`/`swing_low` use a centred ±2-bar window (`feature_pipeline.py:311-312`, documented in the module header as "valid for historical backtesting"), so a swing is flagged two bars before it can be confirmed; `break_of_structure` and `lower_low` inherit that in the rows that differed. Any structure-based sign in §4 should be read with that in mind.
2. **Scale (known F4):** `ema_spread` and `momentum_score` divide a price difference by ATR÷close, giving values like +3,576 or −2,143 on average. The signs are right, so the sign analysis above is valid, but the magnitudes should not be used.
3. **Unsigned or session features** (`open/high/low/close/volume`, `volume_ratio`, `atr`, `volatility_ratio`, `body_*`, `wick_size`, `hour_of_day`, `session`, `disp_strength`, `retest_depth`, `candles_since_retest`, `double_sweep`, `sweep_detected`) have no negative-to-positive meaning, so they are in `trace.csv` only.

## 6. Reading it
- In this week the smooth trend features were negative in the SELL range and positive in the LONG range, as expected from their construction, but they lag the turn by about 15 hours and miss over a third of the move. Faster signals (`momentum_score`, `macd_hist`, `trend_strength`) are inconsistent in sign.
- This is one week, labels were chosen with hindsight, several features are non-causal, and none of it was tested out of sample.
