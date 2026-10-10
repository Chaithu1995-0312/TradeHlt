# `volatility_regime`: causal trailing percentile (spec, code-path check, verification)

## 1. Code path inspected before changing anything
- The weekly trace calls `week_feature_trace.load_features` → `FeaturePipeline(raw).run()`. I confirmed by import that the module is `src/features/feature_pipeline.py`, the same file `BacktestRunner` (`backtest_v2.py`) uses; `train_pipeline.py` and `rr_dataset_builder.py` also call it. There is no other `FeaturePipeline` or `compute_volatility_regime` in the repo.
- In `run()`, `compute_volatility_regime()` sat at line 592 and computed `df["atr_14"].rank(pct=True)` over the whole input frame (old line 274). That ranks every bar against the entire file, including future bars, and the result also depends on how much data the caller passes in.
- The live path does not compute the feature: `live_engine_hook.py` reads `volatility_regime` from `trade_data`, and `bitnet_feature_builder.py` from `state`. So the defect lives in the batch pipeline, which is what the trace, the backtest journal and training use.
- Empirical cross-check: the truncation test (rebuild the features on data cut at 7 points, compare the last 3 rows with the full-file values) showed `volatility_regime` differing in 11 of 21 rows in week one and 21 of 21 in week two. After the change it differs in 0 of 21 in both.

## 2. Specification (decided before implementing)
| Question | Decision | Why |
|---|---|---|
| Window | 200 bars (`VOL_REGIME_WINDOW`, module constant like `SWING_WINDOW`) | As proposed. Note it is a bar count: 200 H1 bars ≈ 8.7 trading days, 200 M15 bars ≈ 2.1 days. |
| Does the current bar participate? | **No.** Reference for bar t is ATR of bars t−200 … t−1, and bar t is compared against it. | Still causal either way (ATR_t is known at bar close), but excluding it avoids self-comparison, lets the result reach exactly 0 and 1, and matches a streaming caller that holds a buffer of past values and queries with the new value. |
| Ties | Mid-rank: (count below + 0.5 × count equal) / 200 | Symmetric; a value equal to every reference value gets exactly 0.5 (pandas `rank(pct=True)` includes the current bar and averages ties). |
| Warm-up | Undefined (`NaN`) until a full 200-bar window of valid ATR exists. First defined bar = ATR(14) start (index 14) + 200 = index 214. `finalize()` drops those rows, so **136 more rows are lost than before** (11,614 vs 11,750 on H1; 47,061 vs 47,197 on M15). | A fake class (e.g. neutral 1) would put invented labels into training data. |
| Missing values | `NaN` or ±inf (current bar or **any** value in the reference window) → `NaN` → row dropped. Zero ATR is a valid value. | No filling, no partial windows. |
| Classes | Unchanged edges: percentile < 0.33 → 0, < 0.66 → 1, else 2 (`VOL_REGIME_LOW_PCT/HIGH_PCT`); column cast back to `int8` after `finalize()`. | Only the reference changes. |
| Input series | Unchanged: ATR(14) in price units. | One change at a time. In a strong uptrend of price (gold 2,300 → 4,500) price-unit ATR drifts up, so a ratio such as ATR ÷ close would be less biased; not changed here. |

Implementation: `trailing_atr_percentile(values, window)` in `src/features/feature_pipeline.py`; `compute_volatility_regime()` maps the percentile to 0/1/2. Dependence is only on the last 201 ATR values, so a live or streaming caller can reproduce it.

## 3. Verification
- 10 new tests in `tests/test_volatility_regime.py`: warm-up NaN, short series, current bar excluded (exactly 0.0 and 1.0 reachable), mid-rank ties, NaN/inf handling, causality when future bars are removed, pipeline dtype `int8` and values in {0,1,2}, truncation and slice independence at pipeline level.
- Full suite: **12 failed / 944 passed**; the same 12 failures as before (11 in `tests/inout/test_probability_engine.py`, 1 in `tests/test_control_plane_doc_alignment.py`).
- Truncation test on the two traced weeks: `volatility_regime` 0 of 21 differing in both (was 11 and 21). Still non-causal: `swing_high`, `swing_low`, `lower_low`, and the swing-derived flags (`break_of_structure`, `sweep_detected`, `liquidity_sweep`); not touched here.
- Backtest regression (plain CLI, M15 production defaults and H1 `--htf 24`): summaries and every trade row are **identical** to the frozen corrected baseline except the `volatility_regime` column itself. The engine's decisions do not use that feature; it feeds the trade journal, FeatureMonitor and training.

## 4. What the change does to the feature (not just a causal copy)
| | Old (full-file rank) | New (trailing 200) |
|---|---|---|
| H1 class shares 0 / 1 / 2 | 32.9% / 32.9% / 34.2% | 34.4% / 29.8% / 35.7% |
| M15 class shares | 33.0% / 33.0% / 34.0% | 34.1% / 31.0% / 35.0% |
| Label agreement old vs new on common bars | — | **41.6% (H1), 44.9% (M15)**; chance for three balanced classes is about 33% |

The old label compared every bar to two years of history; the new one compares it to the last ~9 trading days (H1) or ~2 days (M15). They are different features that share a name, so:
- **Models and baselines trained on the old values are out of date.** `models/gaussian_p5_*.json` list `volatility_regime`; `train_pipeline.py` and `rr_dataset_builder.py` build their data through this pipeline. I did not retrain, re-capture baselines (`baseline_capture.py`) or touch the model registry. `SCHEMA_HASH` is built from names only and is unchanged.
- A window defined in bars means different time spans on M15 and H1. If that matters, a time-based window (e.g. N trading days) is a follow-up decision.
- `docs/SCHEMAS.md` §4.1 now records the new definition.

## 5. Not done
Centred swing detection (`center=True`, `feature_pipeline.py:311-312`), the F4 scale of `ema_spread` / `momentum_score`, retraining, and the earlier trace reports (they describe the code as it was when run; their `volatility_regime` columns are not regenerated).
