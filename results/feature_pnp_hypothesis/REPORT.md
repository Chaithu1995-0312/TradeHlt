# P→N→P as a phase-anchored hypothesis (XAUUSD M15, 9 trades): measured result

Command: `python scripts/analysis/feature_pnp_hypothesis.py --csv data/XAUUSD_M15.csv --trades results/gaussian_training/backtest/run_20261011_055447_XAUUSD/XAUUSD_trades.csv --out results/feature_pnp_hypothesis`. Rules in `spec.json` (written before measuring). Hashes in `meta.json`. Schema: canonical 35-feature `CANONICAL_FEATURES` (checksum f9b806ea...), same data and trades as `results/feature_transition_research/`.

## Definition used
Positive state established at entry (>=2 bars, run starting at or before the entry bar) → a negative run of >=2 bars that starts after entry (adverse phase) → a positive run of >=2 bars that starts at or before the exit (recovery). Tested in raw and direction-aligned (x −1 for SHORT) form, per direction.

## Schema mapping
`macd_hist_z`, `trend_strength_z` and `fvg_distance` are not canonical features. Tested `macd_hist` and `trend_strength`; `fvg_distance` is not tested. `rsi_14` uses sign(rsi − 50).

## Measured
- The full sequence occurred in **2 of 9 trades**: CRT-0009 (LONG, 74 bars; 8 feature/representation cells) and CRT-0006 (SHORT, 15 bars; 1 cell, raw `macd_hist`). Both were profitable. In the 4 LONG and 5 SHORT trades, no losing trade showed it.
- All 4 losing trades lasted 1 to 3 bars (CRT-0002 and 0004: 1; CRT-0005: 2; CRT-0001: 3). Two 2-bar runs plus an entry state need at least about 4 bars after entry, so a losing trade cannot show this sequence in this sample. The profitable/losing contrast is therefore confounded with trade duration.
- Raw: 5 trade-feature cells with the sequence (5 profitable, 0 losing); aligned: 4 (4 profitable, 0 losing). Cells per feature are 0 or 1 per direction, so no frequency or effect size is estimable.
- Redundancy over the 47,061-row corpus (Spearman): `ema_spread`–`macd_line` 0.95, `trend_bias`–`ema_spread` 0.86, `trend_bias`–`macd_line` 0.83. These three carry largely the same information. `momentum_score` (|rho| < 0.09 with them) and `macd_hist` (|rho| < 0.21) are mostly independent of them. `trend_strength` is moderately related (0.54 to 0.63). Per-trade sign strings are in `per_trade_feature.csv`.

## Interpretation (not measured)
- The hypothesis cannot be accepted or rejected with 9 trades. Both trades that show it are also the long profitable ones, which the duration confound explains without any feature effect.
- For the full experiment, compare trades matched on duration (or condition on survival to the same bar), count `ema_spread`/`macd_line`/`trend_bias` as one family when correcting for multiple tests, and use a chronological holdout.

## Not done (needs data)
Ranking validation on a larger chronological holdout, an incremental-information test beyond the correlated features, and multiple-testing correction across a meaningful number of trades. No trade population large enough exists in the repository.
