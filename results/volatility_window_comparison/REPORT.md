# Volatility-window comparison - report v1 (protocol v1)

Status: **comparison only.** No change to production code or configuration, no retraining, no feature-contract freeze. The causal swing/structure fix is untouched. No trading metric was computed or used; the recommendation rests on coverage, stability, causality and semantics only.
Base commit: `a6a482a` (the comparison script, tests and this report are committed on top of it). Script: `scripts/analysis/volatility_window_comparison.py`; metrics: `metrics.json`.

## 1. Candidates and frozen rules
All candidates use the same ATR(14) (computed by the production pipeline's own steps), only observations strictly before the current bar, mid-rank ties, class edges 0.33 / 0.66, and `NaN` (never a neutral class) for insufficient or invalid reference data. Window lengths and `N_MIN` were fixed before any result and were not changed afterwards.

| | A - bar-based | B - H1 time-based | C - M15 time-based |
|---|---|---|---|
| Reference set | previous 200 bars | bars with t - 9 d <= timestamp < t | bars with t - 2 d <= timestamp < t |
| "Elapsed" means | n/a | **calendar** time; closures are not filled with synthetic bars | same |
| Minimum history | 200 bars | window start must not precede the first bar (full elapsed coverage) and >= **N_MIN = 100** bars inside | same |
| ATR validity | all 200 reference ATRs finite | every ATR inside the window finite | same |
| Applied to | H1 and M15 | H1 only | M15 only |
| Streaming state | last 200 ATR values | timestamped ATR buffer covering 9 (2) days | same |

Data: `data/XAUUSD_H1.csv` (11,828 rows) and `data/XAUUSD_M15.csv` (47,275 rows), 2024-05-22 to 2026-05-21, sha256 `18cdc82d...4ffa` / `4d73f5ce...ba56`, the same files for every candidate.

## 2. Causality (every candidate, every run)
Prefix invariance = rebuild ATR and the candidate on data truncated at a cut and compare **all** rows up to the cut; future mutation = replace every bar after the cut with different data and compare all earlier rows; replay = run twice and hash.

| TF | Cand. | Cuts / rows | Prefix fails | Mutation fails | Replay | Hash |
|---|---|---|---|---|---|---|
| H1 | A | 6 cuts, 43,142 row comparisons | 0 | 0 | identical | `4d7a1f10659e` |
| H1 | B | 6 cuts, 43,142 row comparisons | 0 | 0 | identical | `91feeb2d67c1` |
| M15 | A | 6 cuts, 172,913 row comparisons | 0 | 0 | identical | `fbe9a2463ffa` |
| M15 | C | 6 cuts, 172,913 row comparisons | 0 | 0 | identical | `95d597b06810` |

All candidates are causal on real data. 12 unit tests (`tests/test_volatility_window_candidates.py`) cover the window boundaries (start inclusive, current bar excluded), minimum count, full-coverage rule, closures, invalid ATR in the window, ties and the class edges.

## 3. Coverage
| TF | Cand. | Valid rows | Warm-up rows | Interior NaN rows (after first valid) | Class share 0 / 1 / 2 |
|---|---|---|---|---|---|
| H1 | A | 11,614 (98.19%) | 214 | 0 (0.00%) | 34.4% / 29.8% / 35.7% |
| H1 | B | 11,601 (98.08%) | 173 | 54 (0.46%) | 35.0% / 29.6% / 35.4% |
| M15 | A | 47,061 (99.55%) | 214 | 0 (0.00%) | 34.1% / 31.0% / 35.0% |
| M15 | C | 36,293 (76.77%) | 198 | 10,784 (22.91%) | 33.8% / 30.1% / 36.2% |

NaN share by weekday (Mon ... Fri; includes the warm-up rows at the start of the file, which is why A shows 1-2% on the weekdays the file starts on):

| TF | Cand. | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|
| H1 | A | 1.9% | 1.3% | 1.9% | 1.9% | 2.0% |
| H1 | B | 3.2% | 1.0% | 1.9% | 1.9% | 1.6% |
| M15 | A | 0.0% | 0.0% | 1.0% | 1.0% | 0.3% |
| M15 | C | 100.0% | 9.5% | 1.0% | 2.9% | 2.3% |

- **C loses 22.9% of M15 rows after warm-up: every Monday bar and 9.5% of Tuesday.** A 2-day calendar window on a Monday contains only the Monday bars so far (at most 92 on this data), which can never reach `N_MIN` = 100. The weekend closure is what empties the window.
- B on H1 is affected much less (0.46% interior NaN, Monday 3.2%) because 9 days still contains the previous trading week.
- A has no interior NaN (apart from warm-up) and the highest coverage on both timeframes.

## 4. Effective history: bars versus elapsed time
| | median | 5th - 95th percentile |
|---|---|---|
| A on H1: calendar days spanned by 200 bars | 12.7 d | 10.7 - 13.7 d |
| B on H1: bars inside 9 calendar days | 159 | 117 - 161 (max 161) |
| A on M15: calendar days spanned by 200 bars | 2.2 d | 2.2 - 4.3 d |
| C on M15: bars inside 2 calendar days | 184 | 23 - 184 (max 184) |

(The bar-count rows include the warm-up and closure-affected windows; the 5th percentile of the C row is the closure effect.)

- The starting point "9 days ~ 200 H1 bars" holds in **trading** time (200 hours ~ 8.7 trading days) but not in calendar time: 9 calendar days contain about 159 bars, and 200 H1 bars span about 12.7 calendar days. The two definitions describe different horizons, as you expected.
- A 2-day M15 window holds at most 184 bars (a market day has 92 M15 bars here), never 200.
- A's calendar span is stable on H1 (10.7 - 13.7 d) but stretches to 4.3 d on M15 whenever the window crosses a weekend.

## 5. Stability
| TF | Cand. | Flip rate (consecutive valid bars) | Run length median / mean / p90 (bars) | Lag-1 autocorr of the percentile |
|---|---|---|---|---|
| H1 | A | 12.8% | 5 / 7.8 / 15 | 0.964 |
| H1 | B | 13.4% | 5 / 7.4 / 15 | 0.961 |
| M15 | A | 10.0% | 6 / 10.0 / 23 | 0.979 |
| M15 | C | 9.8% | 6 / 9.9 / 24 | 0.980 |
| H1 | X (candle range, not a candidate) | 51.4% | - | 0.462 |
| M15 | X (candle range, not a candidate) | 49.1% | - | 0.511 |

Share of **high (2)** labels by session (UTC windows from the engine's `CRTConfig`):

| TF | Cand. | ASIA | LONDON | NEWYORK | OTHER |
|---|---|---|---|---|---|
| H1 | A | 39% | 21% | 27% | 43% |
| H1 | B | 40% | 21% | 26% | 42% |
| M15 | A | 14% | 14% | 29% | 44% |
| M15 | C | 11% | 14% | 30% | 46% |

Responsiveness to ATR transitions (events defined from ATR only: ATR >= 1.5x its value one day earlier = surge, <= 1/1.5 = decay; debounced one day). Label **high** after a surge at 0 / quarter-day / one day, and label **low** after a decay at the same horizons:

| TF | Cand. | Surge / decay events | High after surge (0 / 1/4 d / 1 d) | Low after decay (0 / 1/4 d / 1 d) |
|---|---|---|---|---|
| H1 | A | 119 / 119 | 76% / 69% / 44% | 68% / 68% / 43% |
| H1 | B | 119 / 119 | 78% / 72% / 42% | 70% / 73% / 45% |
| M15 | A | 275 / 291 | 72% / 39% / 47% | 56% / 45% / 48% |
| M15 | C | 275 / 291 | 76% / 46% / 45% | 57% / 42% / 47% |

- A and B (H1), and A and C (M15), behave almost identically: flip rates differ by under one percentage point, labels persist for a median of 5 (H1) to 6 (M15) bars, and the percentile is very smooth (lag-1 autocorrelation 0.96-0.98).
- One day after a surge the label is high only about 40-47% of the time for every candidate: the window adapts to the new level, which is what a relative measure does.
- C's event coverage is lower on M15 because events falling on Mondays have no label.

## 6. Semantic consistency: ATR context, not the current candle
Counterfactual: double the current candle's true range (ATR rises by TR/14, nothing else changes) and count how many labels change. The strawman X, which labels each bar by the percentile of its own true range (not a candidate), is shown for contrast.

| TF | Cand. | Labels that flip when the current candle is doubled | Mean abs. change in percentile | Spearman vs the candle-range percentile X |
|---|---|---|---|---|
| H1 | A | 18.6% | 0.079 | 0.36 |
| H1 | B | 19.7% | 0.083 | 0.36 |
| M15 | A | 16.3% | 0.063 | 0.52 |
| M15 | C | 16.0% | 0.063 | 0.51 |
| H1 | X (candle range) | 61.6% | 0.320 | 1.00 |
| M15 | X (candle range) | 62.1% | 0.327 | 1.00 |

- All candidates classify **ATR(14) context**: a doubled candle moves 16-20% of labels, against about 62% for the strawman, and their labels are far smoother (autocorrelation 0.96-0.98 vs 0.46-0.51; flip rate 10-13% vs 49-51%).
- They are not immune: ATR(14) gives the current candle a 1/14 weight, so a large candle near a class edge can flip the label. The time-based window is slightly more sensitive on H1 (19.7% vs 18.6%) and about equal on M15 (16.0% vs 16.3%).
- On M15 the labels correlate more with the current candle's range (Spearman 0.52) than on H1 (0.36), because ATR(14) covers only 3.5 hours there. That is a property of the feature on M15, not of the window choice.

## 7. Agreement between candidates (identical rows)
| Pair | Common valid rows | Label agreement | Cohen's kappa | Mean abs. percentile difference | Agreement Mon-Tue / Wed-Fri | Valid only in A / only in other |
|---|---|---|---|---|---|---|
| A vs B (H1) | 11,560 | 89.0% | 0.834 | 0.046 | 87.1% / 90.2% | 54 / 41 |
| A vs C (M15) | 36,277 | 92.9% | 0.894 | 0.029 | 87.7% / 94.6% | 10,784 / 16 |

Where both are defined, the candidates disagree on 11.0% (H1) and 7.1% (M15) of the rows, and more on Monday-Tuesday, when closures distort the elapsed-time windows.

## 8. Downstream impact (diagnostic only; nothing was retrained or rebuilt)
- **Rows whose label depends on the choice (versus A):** H1 11.0% of common rows, plus 54 rows valid only under A and 41 only under B; M15 7.1% of common rows, plus **10,784 rows that exist under A but are NaN (dropped by `finalize()`) under C**.
- **Code that builds or consumes the feature:** `FeaturePipeline` (single implementation) feeding the `BacktestRunner` journal, `train_pipeline.py`, `rr_dataset_builder.py` and `FeatureMonitor`; `live_engine_hook.py` and `bitnet_feature_builder.py` only read the value from their input (live parity is step 5); `tools/cpp/cpp_runner.cpp` and `model_export_format.json` carry the feature name and read precomputed rows.
- **Models carrying stale feature meaning:** all 12 `models/gaussian_p5_*.json` list `volatility_regime` and store its training mean and standard deviation in their scaler (latest file: 1.173 / 0.796); the 5 `models/tradenet_p5_*.pth` checkpoints are bound to the same schema (not opened); `models/bitnet/` contains per-instrument directories (`*_M15`). They are stale because of this feature and the swing fix, whichever window is chosen.
- **Data needed for the rebuild is not all in this checkout:** only the two XAUUSD files are in `data/`; the multi-instrument M15 sources behind the Gaussian models (n_train ~ 85k) were not inspected here.

## 9. Findings and trade-offs
| | A - bar-based (200) | B - H1 time-based (9 d) | C - M15 time-based (2 d) |
|---|---|---|---|
| Causal | yes | yes | yes |
| Coverage | highest on both TFs | within 0.1 pp of A on H1 | **fails: 22.9% of rows NaN, all Mondays** |
| Fixed sample for every percentile | yes (resolution 0.5%) | no (117-161 bars) | no (a closure can leave a handful of bars) |
| Horizon in calendar time | varies with closures (H1 10.7-13.7 d, M15 2.2-4.3 d) | fixed 9 d, but ~ 6.4 trading days and 117-161 bars | fixed 2 d, but empty after weekends |
| Same horizon across timeframes | no (200 bars = 8.7 trading days on H1, 2.2 on M15) | n/a | n/a |
| Streaming cost | trivial | timestamp-indexed buffer | same |
| Semantics (ATR context, not candle) | yes | yes | yes |

Recommendation (for your decision; not applied):
1. **Prefer A for the contract.** It is complete, has a constant statistical resolution, needs the simplest live state, and is the least affected by closures. Its weakness is that 200 bars is a different market horizon on M15 (about 50 trading hours) and H1 (about 200 trading hours), so the label means "relative to the last 200 bars of this timeframe"; that should be written into the contract.
2. **B is a viable alternative on H1** (89% label agreement with A, almost the same coverage), but its calendar-day horizon is partly an artefact of the weekend, its sample size varies, and it costs more to run live; it offers little over A.
3. **C should not be adopted as specified.** The failure is structural: a short calendar window on a 24x5 market is empty after every closure. I did not tune `N_MIN` to repair it, because the rules were frozen.
4. If the aim is the **same market horizon on every timeframe**, neither calendar-time candidate delivers it. The honest fix is a trading-time horizon with per-timeframe bar counts (for example 200 H1 bars ~ 200 market hours, which is 800 M15 bars). That is a different candidate, not tested here, and would need its own pre-registered comparison before it could be chosen.

## 10. Decision gate
Open for you: (a) fixed observation count (A) versus a trading-time horizon (new candidate); (b) whether H1 and M15 should share one horizon; (c) then freeze the feature-definition version/hash for `volatility_regime`, the swing-structure mode and the rules above. Rebuilding datasets and the single retraining run stay blocked until those are decided.
