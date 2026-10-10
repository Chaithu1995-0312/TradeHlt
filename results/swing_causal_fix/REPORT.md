# Causal swing and structure features (step 1 of the agreed sequence)

Scope: make `swing_high`, `swing_low` and everything derived from them causal, keep the old implementation as a versioned research reference, and store event time and confirmation time separately. Not in scope here (by decision): the volatility-window semantics, the feature-definition version/hash, dataset rebuilds, retraining, live parity.

## 1. Where the leak was (exact code path)
All in `FeaturePipeline.compute_structure_liquidity` (`src/features/feature_pipeline.py`), which `run()` calls and which the backtest, training and the trace all go through (single implementation, confirmed earlier).
1. **Swing flag at event time with future bars:** `rolling(w, center=True)` flagged a swing at bar *s* using bars *s+1* and *s+2*, so `swing_high` / `swing_low` on row *s* were known only two bars later.
2. **Reference pulled in unconfirmed swings:** the reference was `last_swing_*_price.shift(1)`. The swing flagged on row *t-1* needs bar *t+1* to exist, so `higher_high`, `lower_low`, `break_of_structure` and `liquidity_sweep` on row *t* could use information from bar *t+1*.
3. **Dependent features inherited it:** `sweep_detected`, `double_sweep`, `retest_flag` → `retest_depth`, `candles_since_retest`.

## 2. Specification implemented (`structure_mode="causal_v2"`, default)
| Item | Definition |
|---|---|
| Swing event | Same as before: `high_s` is the maximum of bars *s-2 … s+2* (lows mirrored); ties flag all equal bars. |
| Confirmation | Event at bar *s* is confirmed at bar *c = s + SWING_CONFIRM_BARS* (= 2) once bar *c* has closed. Implemented with trailing windows only: `high.shift(2) == high.rolling(5).max()` on row *c*. No `center=True` remains in the default path. |
| Canonical `swing_high` / `swing_low` | 1 on the **confirmation row** (two bars after the swing). Same number of swings, shifted by two bars. |
| Event vs confirmation time | `swing_*_event_ts` = timestamp of the swing bar (set on the confirmation row), `swing_*_confirm_ts` = timestamp of the confirming row; `last_swing_*_{price,event_ts,confirm_ts}` forward-filled as of each row; `ref_swing_*_{event_ts,confirm_ts}` are the same values shifted one row. Non-canonical columns, not part of the vector. |
| Reference for bar *t* | Latest swing confirmed at or before bar *t-1* (shift(1) as before), so the earliest use of a swing at *s* is bar *s+3*. A swing confirmed on bar *t* never feeds bar *t*'s own decision. |
| Derived features | Formulas unchanged, now fed by the causal reference. |
| Warm-up / missing | First swing confirmed at bar 4, first reference at bar 5; before that the reference is NaN and the comparisons are 0, as before. NaN highs/lows give no swing. |
| Timestamp convention | Row timestamp = bar open time; "known" means after that bar closes. Confirmation counts bars, not elapsed time, so a weekend gap does not shorten it. |
| Reference mode | `FeaturePipeline(df, structure_mode="centred_v1")` runs the original code path unchanged. It logs a warning and is marked non-causal; `tests/golden/structure_centred_v1.json` pins its outputs. Invalid mode names raise. |

## 3. Verification
- `tests/test_swing_causality.py` (13 tests), all passing:
  - **Future-mutation test:** replace every bar after a cut (3 cuts) with different data; **all 35 canonical features** on rows up to the cut are unchanged.
  - **Truncation test:** drop the future (3 cuts); every canonical feature on **every row including the tail** equals the full-file value.
  - **Sensitivity check:** the same mutation on `centred_v1` does change earlier swing/structure values, so the tests would catch a leak.
  - **Preservation:** `centred_v1` reproduces the pinned original outputs byte for byte.
  - **Event/confirmation:** each flagged swing has `event_ts` two rows before `confirm_ts`, is a real 5-bar extreme, and `ref_swing_*_confirm_ts < timestamp` on every row.
  - The causal flag equals the centred flag delayed by 2 bars.
- **Real data (H1, 11,614 rows):** truncation at 6 cuts across the file, every row compared: **no canonical feature differs**. The earlier 7-cut tail check on both traced weeks: no differing feature (before this change: `swing_high`, `swing_low`, `lower_low`, `break_of_structure`, `sweep_detected`, `liquidity_sweep`).
- Full suite: **12 failed / 957 passed**, the same 12 failures as before (11 in `tests/inout/test_probability_engine.py`, 1 in `tests/test_control_plane_doc_alignment.py`).

## 4. What the change does to the features (H1 file; not just a causal copy)
| Feature | Non-zero bars old | new | Bars whose value changed |
|---|---|---|---|
| swing_high | 1,531 | 1,532 | 26.4% (shifted by 2 bars) |
| swing_low | 1,559 | 1,559 | 26.8% |
| higher_high | 2,735 | 3,877 | 9.8% |
| lower_low | 1,695 | 2,564 | 7.5% |
| break_of_structure | 3,284 | 4,637 | 11.7% |
| liquidity_sweep | 1,127 | 1,750 | 5.5% |
| double_sweep | 375 | 707 | 3.2% |
| retest_depth | 890 | 1,461 | 4.9% |
| candles_since_retest | 10,724 | 10,153 | 43.4% |

- Causal structure signals are **more frequent**. The old reference used swings that already looked like peaks in hindsight (nearer and higher), which made breaks and sweeps rarer and cleaner. The causal reference lags by three bars, so more bars exceed it. The previous cleanliness was partly look-ahead.
- `swing_high` / `swing_low` now mean "a swing was just confirmed", not "this bar is a swing". Any model or analysis that read the old flag as a bar property has a different input.

## 5. What this does not establish
- **Unchanged backtests are not validation of the new features.** M15 and H1 24-bar summaries and every trade row are identical to the frozen corrected baseline, as expected because the engine's decisions do not use these features. The structure columns in the trade journal do differ.
- Models trained on the old values (`models/gaussian_p5_*.json` list these features) are stale for both this change and the `volatility_regime` change. Nothing was retrained or re-captured.
- A causal correction removes leakage; it does not show predictive value.
- The earlier week-trace reports are frozen evidence of the old behaviour and were not regenerated.

## 6. Still open from the agreed sequence
2. Volatility window: bar-based (200 bars) vs time-based, compared on the same data. 3. Freeze the feature contract and add a feature-definition version/hash alongside the names-only `SCHEMA_HASH` (the `causal_v2` / `centred_v1` identifiers and `volatility_regime` definition are inputs to it). 4. Rebuild datasets, retrain once, capture new baselines without overwriting the originals. 5. Training/live parity: trace where the live hook's `volatility_regime` and swing inputs (`trade_data`, `bitnet_feature_builder` `state`) are produced.
