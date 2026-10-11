# Profitable-zone feature transitions: measured result

Command: `python scripts/analysis/feature_transition_research.py --csv data/XAUUSD_M15.csv --trades results/gaussian_training/backtest/run_20261011_055447_XAUUSD/XAUUSD_trades.csv --out results/feature_transition_research`, then `python scripts/analysis/build_transition_explorer.py`.
Hashes, git commit, schema identity and counts are in `manifest.json`; the rules are in `spec.json` (hash in the manifest), written by the script before any outcome statistic is computed.

## 1. Schema authority (measured)
- Authoritative: `CANONICAL_FEATURES` in `src/features/feature_schema.py`, 35 ordered names. `dataset_builder.CANONICAL_FEATURE_ORDER` and `model_export_format.json` (input_dim 35) match it exactly. `GAUSSIAN_SCHEMA` and `TRADENET_SCHEMA` (v2.0, checksum `f9b806ea...`) are built from it.
- Discrepancies (documented, nothing changed): version labels disagree (module `SCHEMA_VERSION` 1.0, SchemaObject 2.0, export file `v5`); two incompatible hashes (names-only `f80ca4bd...` vs checksum); legacy 24-key `FEATURE_SCHEMA` is a different structure; `SESSION_MAP` disagrees with the pipeline's session encoding (pipeline values used).
- Production config `configs/production/v1_multi_2026_03.json` sha256 `59a4b186...`; features from `FeaturePipeline` with `causal_v2` swings and the causal `volatility_regime`. Batch values at each entry bar match the backtest's own trade snapshot.

## 2. Data (measured)
- Corpus: XAUUSD M15, 47,275 bars (2024-05-22 to 2026-05-21), 47,061 feature rows after warm-up.
- Trades: **9** production-config M15 trades regenerated with current code (the only trade set the repo holds for this corpus); no two episodes overlap.
- Outcomes: 5 profitable, 4 losing. Only **1 trade reaches MFE >= 1R** and **0 are "gave back"**. TP1 closes the whole trade at about 0.8 to 0.9R net, so a +1R excursion is rarely observable. Reaching +1R and giving back cannot be tested.
- Window completeness: before and after windows exist for all 9 trades; during-trade windows exist for only 4 (W=8), 3 (12), 2 (16), 2 (20) trades because most trades are shorter than the window.

## 3. What was tested
35 features x 4 patterns (NPN, PNP, plus upward and downward single crossings) x 3 phases x 4 windows = 1,680 rows, each compared by trade outcome group, with train/test split on entry time (first 6 trades train, last 3 test). 300 rows have at least 2 trades with and 2 without the pattern; only those get a permutation test.

## 4. Measured observations
- Smallest permutation p over all 300 testable rows is 0.027; among the 166 causal (before-entry) rows it is 0.094. With 300 tests, BH q is 1.0 for every row and 0 rows reach q < 0.10. The Bonferroni threshold is 1.7e-4, and the smallest p any row can reach with 5,000 permutations is 2e-4.
- Group prevalence tests (profitable vs losing): best Fisher p 0.048, 1 of 1,120 rows below 0.05, which is what chance gives. +1R vs not: best p 0.11 (only 1 trade in the +1R group). Gave-back vs held: not computable.
- Pattern frequency vs corpus base rate: 42 of 1,680 rows differ at p < 0.05 (about 84 expected by chance if all rows were independent, so no excess). Example: `liquidity_sweep` PNP appears in 22% of 20-bar entry windows against a 0.9% corpus rate (p 0.003), a statement about where the engine enters, not about profit.
- Train-selected rows: 197 met the train rule; on the 3 test trades 65 kept the sign, 68 flipped and 64 could not be evaluated. That split is what noise looks like.
- Strongest causal descriptive row: `trend_strength` single downward crossing, 20-bar window: 6 trades with it, 3 without, difference -1.22R, permutation p 0.094, q 1.0.

## 5. Interpretation (not measured)
- No repeatable transition pattern is supported. Nine trades cannot support an edge claim; a result like the one above is expected from noise at this sample size.
- The research design works end to end and will produce usable evidence when the trade count is large enough. Rough scale: detecting a 0.3R difference with 5 to 10 trades per cell needs several hundred trades.

## 6. Limits and disclosures
- Selection of window, run length (2 bars), median length (96) and the MFE give-back threshold (0.5R) were fixed in advance, not tuned.
- Deviation: the first run counted the whole exit bar toward MAE/MFE, which gave MAE up to 9R for stopped trades. I changed the exit-bar rule (STOPPED and TP exits count only their realised excursion) after seeing that run's top rows. The rule is in `spec.json`, and the change affects outcome groups, not the transition detection.
- Observation to check separately: CRT-0005 shows adverse movement of 2.1R before a TP1 exit although its stop is 1R away, suggesting stops may be evaluated on closes. Not investigated here.
- Features are not sign-flipped for SHORT trades. Raw price columns (open/high/low/close) are included as schema members; their median-relative signs mostly describe price trend.
- During-trade and after-exit rows are descriptive only. Entry-time use is limited to the before-entry phase.

## 7. Recommendations
1. Do not trade, promote or build thresholds from these rows.
2. Get a larger trade population (multi-instrument or longer M15 history) before repeating; keep `spec.json` and rerun the script unchanged.
3. Decide whether the +1R MFE question can be asked at all while TP1 ends trades below 1R.
