# Bar-first P→N→P census, XAUUSD M15 (measured result)

Commands: `python scripts/analysis/pnp_bar_census.py --csv data/XAUUSD_M15.csv --scope month --month 2025-07 --out results/pnp_bar_census_2025_07` (discovery month), then the same frozen detector with `--scope full --out results/pnp_bar_census_full`. Spec hash `b921284d...` is identical in both manifests, so the detector and tests were not changed between runs. Data sha256 `4d73f5ce...`; canonical 35-feature schema (checksum f9b806ea...); causal_v2 swings and causal volatility_regime in the feature pipeline. No trade was used to define the population.

## Unit and detector (fixed in `spec.json` before any outcome was computed)
- Population: every eligible M15 bar (all 7 feature values finite): 2,100 bars in July 2025, 47,061 in the full corpus (2024-05-24 to 2026-05-21).
- Detector: causal streaming state machine on the sign of 6 primary features plus `rsi_14 − 50`: a run of the leading sign of at least 2 bars, a middle run of the opposite sign lasting 2 to 10 bars, then the leading sign again; the event fires on the second bar of the final run. PNP is the positive-leading sequence; NPN is its mirror. Zeros are skipped; the state resets on any gap above 15 minutes. Events of the same feature and pattern within 8 bars count as one episode. Events from any feature within ±4 bars form one episode group.
- Detector tests (7) include a prefix test showing that no event depends on later bars.
- `macd_hist_z`, `trend_strength_z` and `fvg_distance` are not canonical names; `macd_hist` and `trend_strength` were used and `fvg_distance` was not tested.

## 1. Does it exist and repeat? (discovery month, then full corpus)
- July 2025: 259 events in 109 episode groups. Occurrences per 1,000 eligible bars: `momentum_score` 21 to 22 per pattern, `macd_hist` 10 to 12, `rsi_14` 11, `ema_spread` and `trend_bias` 5 to 6, `macd_line` 3, `trend_strength` 2 to 3. Events fall on 4 to 22 different days per feature.
- Full corpus: 5,949 events in 2,572 episode groups. `momentum_score` PNP appears at 24.9 ± 3.1 per 1,000 bars across 25 months (range 19.8 to 31.7), so it recurs steadily, not in clusters.
- `trend_bias` and `ema_spread` produce identical events (the same episodes on the same bars), so they are one signal, not two. `macd_line` is nearly the same family.
- Development time: the median middle (negative) phase is 2 to 8 bars depending on the feature; the median span from the start of the middle phase to confirmation is 3 to 9 bars (full-corpus quartiles of the span: 3, 5, 7).

## 2. Time structure
- Hour of day: 13 of 14 feature/pattern cells depart from the share of eligible bars at p < 0.05 (Monte-Carlo, 3,000 draws); most at p < 0.001. The busiest hour holds 5.5 to 10% of a cell's events against 4.2% if uniform. Bar position: 10 of 14. Minute of hour: 1 of 14. Calendar day in the full corpus: 0 of 14.
- So the sequences are not spread evenly through the day, but they appear across days and months. The chi-square treats events as independent, which overstates significance for clustered events.

## 3. Forward outcomes (kept separate from detection)
- Aligned return = sign of the final phase × forward log return in bps at 1, 4, 8, 16 bars (mean unconditional drift over the full corpus: +0.11, +0.40, +0.73, +1.07 bps).
- Against the random-timing null (5,000 draws), 3 of 56 cells reach nominal p < 0.05 (about 3 expected by chance). The smallest Benjamini–Hochberg q is 0.49 in the full corpus and 0.95 in the discovery month. The nominal best, `trend_strength` NPN at 8 bars (mean −8.5 bps aligned, p 0.039), has q 0.54.
- PNP aligned means are mostly positive and NPN aligned means mostly negative (price rose after both), which is what the corpus's upward drift predicts; this is why the null permutes signs over random bars.
- Chronological check for `trend_strength` at 8 bars: pre-discovery, discovery and holdout periods show the same signs (PNP +3.5, +15.4, +10.5 bps; NPN −11.2, −3.9, −5.4 bps) but with 5 to 54 events per period and no significant result.
- Month stability: the share of months (with at least 3 events) whose aligned mean is positive is 44 to 72% for PNP and 24 to 56% for NPN; no feature shows the same sign in most months beyond what drift gives.

## Interpretation (not measured)
- The detector works and the P→N→P sequence is common and reproducible on all eligible bars. The earlier nine-trade null was a sample-size problem, not evidence that the transition is absent.
- No feature's sequence has a demonstrated relation to the next 1 to 16 bars. A higher event count did not turn into an edge.

## Limits
- One instrument, one timeframe, one corpus. Forward windows overlap across nearby events; the null p-values treat events as independent and are therefore optimistic.
- Time-of-day tests use eligible-bar exposure and ignore volatility or session effects on the features themselves.
- No costs, no entry rule, no stop logic: these are price movements after confirmation, not trading results.
- July 2025 was used earlier for unrelated trace work; it was named as the discovery month before the run, and the full-corpus run used the identical frozen detector.

## Next steps
1. Test whether the sequence adds information beyond its context (direction of the larger trend, volatility regime, session), using conditional comparisons with matched controls.
2. Define outcomes closer to the trade (excursion before an adverse threshold) before proposing any rule.
3. Repeat on other instruments before drawing general conclusions.
