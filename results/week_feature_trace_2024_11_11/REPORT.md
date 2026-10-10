# Second week: does the feature-sign picture generalize? — XAUUSD H1, Mon 2024-11-11 → Fri 11-15

> One more descriptive week, not a test of a trading edge. Method and code are the same as the first trace (`results/week_feature_trace_2025_07_21/`): `scripts/analysis/week_feature_trace.py`.

## 1. How the week was chosen (price-only rule, fixed before looking at any feature)
Full Mon–Fri weeks with 115 bars, at least 4 of 5 daily moves in the week's direction, and |net move| ≥ 70% of the week's high-low range, excluding 113-bar holiday weeks: 16 candidates. A seeded draw (`random.Random(42).choice`) picked **2024-11-11 → 11-15**. Verified in the data: 115 bars; daily moves Mon −66.3, Tue −20.8, Wed −25.1, Thu −10.3, Fri −3.2 (5 of 5 down); net **−123.8** against a week range of 149.4 (83%). The prior week was also down (−51.8), and the 16 candidates are 14 up weeks and 2 down weeks, so the draw landed on a down week by luck.

Hindsight ranges as before: the week's highest high is the **first bar** (Mon 01:00), so the LONG range is 1 bar and the SELL range is the other 114. This week tests the SELL side only.

## 2. Day by day: share of hour bars with a positive sign
| Day | Bars | Day move | trend_bias | ema_spread | trend_strength | momentum_score | macd_line | macd_hist | rsi_14 | break_of_structure | liquidity_sweep | structure_hh_ll |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024-11-11 Mon | 23 | -66.3 | 0% | 0% | 0% | 39% | 0% | 0% | 0% | 0% | 4% | 0% |
| 2024-11-12 Tue | 23 | -20.8 | 0% | 0% | 26% | 52% | 0% | 96% | 0% | 0% | 4% | 4% |
| 2024-11-13 Wed | 23 | -25.1 | 17% | 17% | 100% | 48% | 0% | 74% | 57% | 4% | 4% | 9% |
| 2024-11-14 Thu | 23 | -10.3 | 0% | 0% | 22% | 48% | 0% | 39% | 30% | 9% | 4% | 13% |
| 2024-11-15 Fri | 23 | -3.2 | 26% | 26% | 100% | 43% | 4% | 87% | 61% | 4% | 13% | 17% |

## 3. Hourly sign grids for two days
**2024-11-11 Mon**  (range labels: LSSSSSSSSSSSSSSSSSSSSSS)
```
hour              01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
bar (close-open)   +  -  -  -  -  +  -  +  -  +  -  -  +  -  -  -  -  +  -  +  +  +  -
trend_bias         -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
ema_spread         -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
trend_strength     -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
momentum_score     +  -  -  -  -  +  -  +  -  +  -  -  +  -  -  -  -  +  -  +  +  +  -
macd_line          -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
macd_hist          -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
rsi_14             -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
break_of_structure 0  0  -  -  0  0  0  0  0  0  -  -  -  -  -  -  -  -  -  -  0  0  0
liquidity_sweep    -  -  0  0  0  0  0  0  0  0  0  +  0  0  0  0  0  0  0  0  0  0  0
structure_hh_ll    -  -  -  -  0  0  0  0  0  0  -  0  -  -  -  -  -  -  -  -  0  0  0
```

**2024-11-13 Wed**  (range labels: SSSSSSSSSSSSSSSSSSSSSSS)
```
hour              01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23
bar (close-open)   +  +  +  +  -  -  -  -  +  +  +  +  +  -  +  -  +  -  -  -  -  -  -
trend_bias         -  -  -  -  -  -  -  -  -  -  -  -  +  +  +  +  -  -  -  -  -  -  -
ema_spread         -  -  -  -  -  -  -  -  -  -  -  -  +  +  +  +  -  -  -  -  -  -  -
trend_strength     +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +
momentum_score     +  +  +  +  -  -  -  -  +  +  +  +  +  -  +  -  +  -  -  -  -  -  -
macd_line          -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
macd_hist          +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  -  -  -  -  -  -
rsi_14             -  +  +  +  +  -  -  +  +  +  +  +  +  +  +  +  -  -  -  -  -  -  -
break_of_structure 0  0  0  0  0  0  0  0  0  0  0  0  0  0  +  -  -  -  -  0  0  -  -
liquidity_sweep    0  0  0  0  0  0  0  0  0  -  0  0  0  +  0  0  0  0  0  0  0  0  0
structure_hh_ll    0  0  0  0  0  0  0  0  0  -  0  0  0  +  +  -  -  -  -  0  0  -  -
```

- **Monday (−66.3, the big down day):** every smooth signal (`trend_bias`, `ema_spread`, `macd_line`, `rsi_14`) is already negative from the first bars. The trend features were inherited from the prior week's decline (−51.8); there was no "catching up".
- **Wednesday:** `trend_bias`/`ema_spread` are positive for 13:00–16:00 (4 bars) while price moved -7.1 in those hours (a 17.6 point range), then fall back negative at 17:00. `macd_hist` is positive for the day's first 17 bars (price +7.7 over them) and negative afterwards; over the whole week it is positive on 59% of bars of a down week, so its sign is not a direction label.

## 4. Two weeks side by side
A = rise-then-fall week (per hindsight range); B = this week (SELL range = the whole week):

| Feature | A (2025-07-21..2025-07-25) LONG range matches (+) | A SELL range matches (−) | B (2024-11-11..2024-11-15) SELL week matches | B longest counter-run (bars) | A next-bar hit | B next-bar hit |
|---|---|---|---|---|---|---|
| trend_bias | 100% | 79% | 91% | 6 | 68/114 (60%, p=0.05) | 59/113 (52%, p=0.71) |
| ema_spread | 100% | 79% | 91% | 6 | 68/114 (60%, p=0.05) | 59/113 (52%, p=0.71) |
| trend_strength | 78% | 68% | 50% | 32 | 58/114 (51%, p=0.93) | 54/113 (48%, p=0.71) |
| momentum_score | 61% | 59% | 54% | 5 | 58/114 (51%, p=0.93) | 54/112 (48%, p=0.78) |
| macd_line | 100% | 77% | 99% | 1 | 67/114 (59%, p=0.07) | 60/113 (53%, p=0.57) |
| macd_hist | 53% | 62% | 40% | 39 | 61/114 (54%, p=0.51) | 64/113 (57%, p=0.19) |
| rsi_14 | 78% | 85% | 70% | 14 | 61/114 (54%, p=0.51) | 56/113 (50%, p=1.00) |
| break_of_structure | 80% | 100% | 90% | 2 | 28/45 (62%, p=0.14) | 22/40 (55%, p=0.64) |
| liquidity_sweep | 50% | 100% | 42% | 1 | 4/9 (44%, p=1.00) | 7/13 (54%, p=1.00) |
| structure_hh_ll | 71% | 100% | 80% | 3 | 32/54 (59%, p=0.22) | 28/51 (55%, p=0.58) |

## 5. Verdict on the hypotheses written before this week was traced
| # | Hypothesis | Result |
|---|---|---|
| 1 | `trend_bias`, `ema_spread`, `macd_line` match the week's direction on ≥ 75% of bars | **Confirmed.** 91%, 91%, 99% (first week SELL range: 79%, 79%, 77%). |
| 2 | `rsi_14` averages below 50 in the down week | **Confirmed.** 37.8 (first week SELL range: 33.8); sign matches on 70% of bars. |
| 3 | `momentum_score`, `macd_hist`, `trend_strength` are inconsistent (< 70% match) | **Confirmed, and worse.** 54%, 40%, 50%; `macd_hist` is positive on 59% of the bars of a down week, its longest wrong-sign run is 39 bars. |
| 4 | Smooth features adopt the direction late | **Not testable here.** There is no turn: the features already carried the correct sign at the open. A "bars until they agree for good" metric is brittle (one late blip resets it), so I do not report it. The lag finding stands only on week A (about 15 hours after the peak). |
| 5 | Next-bar hit rate ≈ 55–60% for the smooth features, not significant after multiple testing | **Level not replicated, non-significance confirmed.** 52–53% here (p = 0.57–0.71) vs 59–60% in week A (p = 0.05–0.07). The best single feature this week is `macd_hist` at 57% (p = 0.19). Nothing in either week passes a Bonferroni threshold of p < 0.005. |
| 6 | Same non-causal set fails the truncation test | **Confirmed.** `volatility_regime` (21 of 21 rows differ), `swing_high`, `swing_low`, `lower_low`, plus `sweep_detected` and `liquidity_sweep` in one row each, which are derived from swings. All other canonical features were identical. |

| Feature | Rows that differ |
|---|---|
| volatility_regime | 21 / 21 |
| swing_high | 2 / 21 |
| swing_low | 2 / 21 |
| sweep_detected | 1 / 21 |
| liquidity_sweep | 1 / 21 |
| lower_low | 1 / 21 |

Causal (identical in every comparison): open, high, low, close, volume, volume_ratio, double_sweep, ema_fast, ema_slow, ema_spread, trend_bias, trend_strength, momentum_score, atr, volatility_ratio, rsi_14, macd_line, macd_signal, macd_hist, break_of_structure, higher_high, body_size, wick_size, body_ratio, hour_of_day, disp_strength, retest_depth, candles_since_retest

## 6. What generalizes and what does not
- **Generalizes (two cases):** the smooth level features carry the sign of the dominant direction, in both a LONG range and two different SELL ranges, and `rsi_14` sits on the right side of 50. This follows from how they are built (they summarize recent price), so it describes the past, not the future.
- **Generalizes:** the fast and z-scored features (`momentum_score`, `macd_hist`, `trend_strength`) are unreliable as a direction label, with `macd_hist` often having the wrong sign; the non-causal feature set is the same.
- **Does not generalize:** the 60% next-bar hit rate of `trend_bias` from week A. In week B it is 52%. That figure was noise-level in week A already (p = 0.05 among ten features) and should not be used.
- **Not tested:** the lag at a turn (only week A had one), and the LONG side of a one-directional week (week B is a down week).

## 7. Limits
- Two weeks, one instrument, one timeframe. "Generalizes" here means "not contradicted in a second case".
- Bars within a week are autocorrelated, so p-values over 114 bars overstate evidence; ten features and two weeks make chance matches likely.
- Selection of week B used price only; it was fixed before any feature was read. Week A was chosen with hindsight.
- The F4 scale problem is unchanged (signs valid, magnitudes of `ema_spread` and `momentum_score` unusable).
- Cheap extension, not run: an up-week (e.g. 2025-05-19, +137.9) would test the LONG side.
