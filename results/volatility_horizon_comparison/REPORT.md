# Shared-horizon comparison (candidate D) - report v2 (protocol v2)

Status: **comparison only.** A is unchanged and remains the reference. No production code, configuration, model or dataset was changed, the feature contract is not frozen, and nothing was retrained. No trading metric was computed or used.
Base commit: `ad00ca5`. Script: `scripts/analysis/volatility_horizon_comparison.py` (reuses protocol v1 unchanged); metrics: `metrics.json`; tests: `tests/test_volatility_horizon_candidates.py` (5).

## 1. Candidates and frozen rules
| | H1 | M15 |
|---|---|---|
| A - reference | previous 200 bars | previous 200 bars |
| D - shared observation horizon | previous 200 bars (identical to A; asserted) | previous **800** bars |

200 H1 bars and 800 M15 bars are both 200 hours of bar intervals. That is nominal bar time; the report below measures what each covers in calendar and market terms. Everything else is as in protocol v1: the same ATR(14) from the production pipeline's own steps, only strictly-prior observations, mid-rank ties, edges 0.33 / 0.66, and NaN (never imputed) unless all W reference ATRs are finite.

Definitions added for this comparison: *closure* = consecutive-bar gap > 3 bar intervals (M15 > 45 min, H1 > 3 h); *missing bar* = gap > 1 and <= 3 intervals; cross-timeframe pairing = the H1 bar opening at T with the M15 bar opening at T + 45 min (both close at T + 1 h).

**Deviation, recorded:** after the first run I saw that the closure rule counts the 75-minute daily break on M15 (516 closures) but not the 2-hour daily gap on H1 (121 closures; 394 gaps counted as missing bars), so "closures per window" is not comparable across timeframes. I added two descriptive metrics (long closures >= 24 h, and agreement with the retired full-file label). No candidate, window or threshold was changed.

## 2. Causality
| TF | Cand. | Rows compared (6 cuts) | Prefix fails | Mutation fails | Replay | Hash |
|---|---|---|---|---|---|---|
| H1 | A | 43,142 | 0 | 0 | identical | `4d7a1f10659e` |
| H1 | D | 43,142 | 0 | 0 | identical | `4d7a1f10659e` |
| M15 | A | 172,913 | 0 | 0 | identical | `fbe9a2463ffa` |
| M15 | D | 172,913 | 0 | 0 | identical | `ad9fc49e0206` |

All causal: rebuilding ATR and the label on truncated data reproduces every earlier row, replacing every future bar changes no earlier row, and replay is bit-identical. A's hashes are identical to protocol v1; D on H1 has the same hash as A.

## 3. Coverage and occupancy
| TF | Cand. | Window | Valid rows | Warm-up rows | First valid | Interior NaN | Class share 0 / 1 / 2 |
|---|---|---|---|---|---|---|---|
| H1 | A | 200 | 11,614 (98.19%) | 214 | 2024-06-04 10:00 | 0 | 34.4% / 29.8% / 35.7% |
| M15 | A | 200 | 47,061 (99.55%) | 214 | 2024-05-24 08:30 | 0 | 34.1% / 31.0% / 35.0% |
| M15 | D | 800 | 46,461 (98.28%) | 814 | 2024-06-03 23:00 | 0 | 33.6% / 30.8% / 35.6% |

- D costs **600 more warm-up rows** on M15 (814 bars, about 8.8 trading days, against 214); 600 rows are valid only under A. There are no interior NaN rows for either (M15 has no missing-bar gaps; closures do not invalidate a window under these rules).
- Class occupancy stays close to thirds for both (A 34.1% / 31.0% / 35.0%; D 33.6% / 30.8% / 35.6%).

## 4. Stability and transitions
| TF | Cand. | Flip rate | Run length median / mean / p90 (bars) | Lag-1 autocorr | Labels that flip when the current candle is doubled | Stay probability by class |
|---|---|---|---|---|---|---|
| H1 | A | 12.80% | 5 / 7.8 / 15 | 0.964 | 18.6% | 0->0: 90.5%; 1->1: 78.8%; 2->2: 91.0% |
| M15 | A | 10.03% | 6 / 10.0 / 23 | 0.979 | 16.3% | 0->0: 92.4%; 1->1: 83.9%; 2->2: 93.0% |
| M15 | D | 8.45% | 7 / 11.8 / 26 | 0.985 | 13.6% | 0->0: 93.6%; 1->1: 86.3%; 2->2: 94.2% |

D is smoother on M15: flips 8.4% of bars against 10.0%, longer runs, and 13.6% of labels flip when the current candle is doubled against 16.3%. Both still measure ATR context, not candle size.

Share of **high (2)** labels by session:

| TF | Cand. | ASIA | LONDON | NEWYORK | OTHER |
|---|---|---|---|---|---|
| H1 | A | 39% | 21% | 27% | 43% |
| M15 | A | 14% | 14% | 29% | 44% |
| M15 | D | 16% | 15% | 30% | 45% |

## 5. Market closures, missing bars and reopening
| TF | Cand. | Calendar days spanned by the window: median (5th-95th) | Windows with 0 / 1 / 2 / 3+ long closures (>= 24 h) | Median closures of any size in window | Label change across a closure | Flip rate: all bars / first 4 h after reopening |
|---|---|---|---|---|---|---|
| H1 | A | 12.7 (10.7 - 13.7) | 0% / 24% / 71% / 5% | 2 | 16.1% | 12.80% / 12.92% |
| M15 | A | 2.2 (2.2 - 4.3) | 55% / 44% / 1% / 0% | 2 | 12.8% | 10.03% / 8.50% |
| M15 | D | 12.7 (10.7 - 13.7) | 0% / 24% / 72% / 5% | 9 | 13.0% | 8.45% / 7.12% |

- **D spans the same wall-clock time as H1's 200 bars**: on the aligned instants the span ratio M15-D / H1 is 1.00 (5th-95th 1.00 - 1.00), while M15-A / H1 is 0.20 (0.17 - 0.33). Its windows also contain the same pattern of weekends (0/1/2/3+ long closures: 0% / 24% / 72% / 5% against 0% / 24% / 71% / 5% for H1).
- M15-A's window is short (median 2.2 days) and holds no weekend in 55% of windows, so its reference changes character depending on whether a weekend falls inside it.
- Labels change across a closure somewhat more often than between ordinary consecutive bars (12.8% for A and 13.0% for D over ~510 closures, against all-bar flip rates of 10.0% and 8.4%); that is expected, since a gap is elapsed time and the daily-break and weekend gaps are included. There is no extra instability after reopening: the flip rate in the first four hours is no higher than elsewhere (8.5% for A, 7.1% for D).
- Missing bars: none on M15; on H1 the 394 one-bar gaps (daily 00:00) are tolerated because windows are counted in bars.

## 6. Responsiveness to ATR transitions
Events defined from ATR only (surge: ATR >= 1.5x its value one day earlier; decay: <= 1/1.5). Label **high** after a surge, **low** after a decay, at 0 / quarter-day / one day:

| TF | Cand. | Surge / decay events | High after surge | Low after decay |
|---|---|---|---|---|
| H1 | A | 119 / 119 | 76% / 69% / 44% | 68% / 68% / 43% |
| M15 | A | 275 / 291 | 72% / 39% / 47% | 56% / 45% / 48% |
| M15 | D | 275 / 291 | 61% / 37% / 45% | 51% / 40% / 47% |

D reacts more slowly on M15: right at a surge it is labelled high 61% of the time against 72% for A, and low at a decay 51% against 56%, because a longer reference absorbs a surge more slowly. After one day the two are within a few points.

## 7. A versus D on M15
75.1% label agreement on 46,461 common rows (kappa 0.626, mean absolute percentile difference 0.101); 97.1% of the disagreements are one class step; agreement is flat across weekdays (74% - 77%). Choosing D would change the M15 label on about a quarter of the rows.

## 8. Is the meaning consistent across timeframes? (the main question)
Aligned H1 and M15 labels for the same instant (11,810 pairs, 11,597 where both are valid):

| Pairing | Pairs | Label agreement | Cohen's kappa | Spearman of percentiles | Mean abs. percentile difference |
|---|---|---|---|---|---|
| A: H1 200 bars vs M15 200 bars | 11,597 | 43.9% | 0.157 | 0.38 | 0.274 |
| D: H1 200 bars vs M15 800 bars | 11,597 | 53.4% | 0.299 | 0.58 | 0.220 |
| diagnostic only: D with M15 ATR(56) (= 14 hours) | 11,597 | 86.7% | 0.800 | 0.97 | 0.054 |

- **D helps, but only partly.** Equalising the reference window raises cross-timeframe agreement from 43.9% to 53.4% (kappa 0.16 to 0.30).
- **The remaining gap comes from ATR(14) itself.** ATR(14) spans 14 hours on H1 but 3.5 hours on M15. The diagnostic that also stretches the M15 ATR to 56 bars (14 hours) reaches 86.7% agreement (kappa 0.80, Spearman 0.97). That is not a candidate: ATR(14) is a fixed part of the feature, and changing it is a contract change that was not authorized.
- **The same timeframe-local ATR(14) sits inside other canonical features** (`atr`, `volatility_ratio`, `disp_strength`, `retest_depth`, `ema_spread`, `momentum_score`), so making only `volatility_regime` timeframe-consistent would not make the feature vector timeframe-consistent.
- Neither A nor D is closer to the retired full-file label: both agree with it on 44.9% of M15 rows, close to chance for three classes. The existing models are stale under either.

## 9. Trade-offs and recommendation (for your decision; nothing applied)
| | A (200 / 200) | D (200 / 800) |
|---|---|---|
| Causality | pass | pass |
| M15 valid rows / warm-up | 99.55% / 214 bars | 98.28% / 814 bars |
| Reference horizon M15 vs H1 (calendar) | 0.20x | 1.00x |
| Smoothness / stability on M15 | flip 10.0% | flip 8.4% (smoother) |
| Responsiveness to surges on M15 | faster | slower |
| Cross-timeframe label agreement | 44% | 53% |
| Streaming state | 200 values | 800 values |
| Change to existing M15 labels | - | 25% of rows |

1. **Keep A as the contract reference unless cross-timeframe reuse is a requirement.** The system ingests M15 candles (CLAUDE.md) and the per-instrument model directories are named `*_M15` (the Gaussian models' training timeframe was not verified), and A is complete, fast to respond and cheapest to run. State plainly in the contract that `volatility_regime` means "relative to the previous 200 bars of this timeframe" (50 hours on M15, 200 hours on H1).
2. **D is a half-measure.** It aligns the reference window in wall-clock terms and is smoother, but it leaves the ATR horizon timeframe-local, so cross-timeframe agreement is still only about half the rows, and it adds a 600-row warm-up cost and slower surge response.
3. **If a model must read the same meaning on H1 and M15,** the consistent definition would put both the ATR lookback and the reference window in time (the diagnostic reaches 87% agreement) and would also have to re-state the other ATR-based features. That is a separate pre-registered comparison and a schema-level decision, not a tweak to this feature.

## 10. What stays open
Pick the semantics: (a) timeframe-local A, or (b) a fully time-defined feature set. Then freeze the feature-definition version/hash (causal swing mode, volatility window, ranking rules, class boundaries, missing-value behaviour), complete the training/live parity trace, inventory every affected model and dataset (not only the 12 Gaussian files), rebuild, retrain once and capture versioned baselines. None of that has started.
