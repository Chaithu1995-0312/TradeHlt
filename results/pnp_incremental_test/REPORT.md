# PNP incremental information test: XAUUSD M15 (measured result)

Status: **unsupported in the tested scope. Not promoted. No production change.** Machine-readable record: `evidence_record.json`; identities in `manifest.json`; rules in `spec.json` (hash in manifest); discovery freeze in `discovery_freeze.json`.

## Contract as executed
- Events: the exact events of `results/pnp_bar_census_full/events.csv` (census spec hash `b921284d...`; detector, thresholds and refractory untouched; pipeline and corpus hashes asserted equal to the census manifest). PNP and NPN are separate families. `trend_bias` and `ema_spread` events are identical and are counted once. 6 features × 2 patterns × 4 horizons = 48 tests per period.
- Controls: eligible non-event bars of the same period with the same H4 trend state (completed buckets only), volatility regime, session, hour of day, and the same current sign of the feature as the event's final phase. Nearest neighbour on prior 16-bar return, prior 64-bar return and `volatility_ratio` within a 0.5 SD caliper, 1:1 without replacement. Controls are at least 16 bars away from any event of the same feature. No outcome or post-confirmation variable entered matching; outcomes were read after matching.
- Outcome: 10000·ln(close[t+k]/close[t]) bps at k = 1, 4, 8, 16, signed by the final phase (+1 PNP, −1 NPN); the control inherits the event's sign. Pairs with a time gap in the forward window are dropped.
- Inference: paired difference with a 4,000-draw day-clustered bootstrap, Benjamini–Hochberg over the 48 tests per period, pooled OLS with day-clustered SE as a cross-check. Four sensitivity variants (caliper 0.25, 3 controls with replacement, 4-hour bucket instead of exact hour, events thinned to ≥ 16 bars apart).
- Periods: discovery 2024-05-24 to 2025-07-31, holdout 2025-08-01 to 2026-05-21. Discovery results were hashed into `discovery_freeze.json` before the holdout stage ran; the holdout stage refuses to run if the spec or discovery summary changed.

## Counts and balance (measured)
| | Events | Outcome window missing | Unmatched | Pairs |
|---|---|---|---|---|
| Discovery | 3,235 | 524 | 765 | 1,946 |
| Holdout | 2,166 | 360 | 530 | 1,276 |
Match rate about 78% in both. Mean absolute standardised mean difference of the matched covariates: 0.043 (discovery) and 0.073 (holdout), against 0.27 and 0.30 for the unmatched pool; the worst cell is `rsi_14` prior 16-bar return at 0.50 in the holdout. Per-cell values are in `balance_*.csv`; matched pairs are in `matched_events.csv` and `matched_controls.csv`.

## H1: context baseline
A context-only linear model fitted on discovery bars explains almost none of the next 1 to 16 bar movement on holdout bars: out-of-sample R² +0.0002, +0.0007, +0.0015, −0.0006 at 1, 4, 8, 16 bars (prediction-outcome correlation 0.02 to 0.04).

## H2: transition increment
- Discovery: 1 of 48 tests has q < 0.05 (`momentum_score` PNP at 1 bar, +2.8 bps, 95% CI 1.3 to 4.3) and 9 have q < 0.10.
- Holdout: **0 of 48 reach q < 0.05**; the smallest q is 0.072 (`macd_hist` PNP at 8 bars, −14.6 bps, CI −25.0 to −4.5, nominal p 0.007).
- The one discovery cell below q 0.05 changed sign in the holdout (−1.0 bps, CI −3.5 to 1.4).

## H3: stability
- 31 of 48 cells have the same sign in discovery and holdout (32 expected by chance if signs were independent). The correlation of the 48 effects between periods is −0.02.
- Of the 9 discovery cells with q < 0.10, 7 kept their sign and 1 had holdout nominal p < 0.05 (`macd_hist` PNP at 8 bars). That cell and `macd_hist` NPN, which share the same direction, are the only recurring pattern: events underperform matched controls by about 7 to 15 bps at 4 to 8 bars, and all four sensitivities agree in both periods. It does not pass the pre-registered rule (holdout q 0.17).
- No cell meets the promotion rule.

## Interpretation (not measured)
- The earlier census showed the sequence is frequent; this test finds no reliable extra information in it once the current state and matched context are held fixed.
- The `macd_hist` result is negative for both PNP (long-aligned) and NPN (short-aligned) events relative to controls. Controls were drawn from periods without a recent sign flip, so they come from persistent trends, which tend to continue. That reading is untested here and cannot be separated from a real transition effect with this design.
- Context explains almost nothing, so a context baseline is a weak yardstick: a feature with no true effect would also look "incremental" over it at the 1 to 5 bps scale, which is why multiple-testing control and the frozen holdout carry the conclusion.

## Limits
One instrument, one timeframe, one corpus; matching on observed variables only; overlapping forward windows (day-clustered, not removed); bps price moves without costs or stops; July 2025 was used in earlier unrelated trace work and sits in the discovery period; the cell counts are modest (21 to 330 pairs per cell).

## Decision and next experiment
Result: inconclusive to unsupported for incremental information within this scope. No feature, model, registry, configuration or execution policy was changed.
A separate frozen execution experiment (entry at the next bar open, stop and target in ATR units, spread and slippage from the existing `backtest` configuration, costs applied) has **not** been run: nothing survived the holdout, so there is no price-movement relationship to carry into it. If one of the `macd_hist` cells is pursued, the pre-condition is a new pre-registered holdout (later data or another instrument), not a re-test on this one.
