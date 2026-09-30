# ATR private copies inventory (2026-09-27, read-only)

Authority: docs/audits/RESEARCH_FUNCTION_CENSUS_2026-09-27.md section 3 hotspot #2 ('>=17 named (+1 verbatim copy)'), cross-checked with git grep over src/ scripts/ tools/ (tests, worktrees, .venv, archive excluded). Queue: multi_llm/build_queue.jsonl STORY-83.9 'WP-I S2b: private ATR copies -> FM-041/FM-074' (pending).

Canonical: `src/features/feature_pipeline.py:610-615` - TR with prev close (bar0 NaN), SMA rolling(`feature_pipeline.atr_period`), `atr_14_raw` absolute; published FM-041 `atr` = atr_14_raw/close.

Count: **17 found = census 17** (#13 is the verbatim copy of #12; #3 and #4 are wrappers of #2). Plus 1 twin oracle (#18). Only 3 are genuinely different formulas: #6 median TR, #16 Wilder, #17 5-bar range proxy.

| # | File:line | Function | Business role | Formula | Period source | Path | Matches canonical? | Outcome risk |
|---|---|---|---|---|---|---|---|---|
| 1 | `src/config_layer/crt_engine_v2.py:903` | `RangeDetector.compute_atr (-> state.atr_abs)` | The engine's own volatility yardstick in price units for every CRT gate and the trade build. | SMA of last `period` TRs with prev close, over a bounded buffer of atr_period*atr_buffer_multiplier (=42) candles; buffer never reset; partial-window mean when <period TRs (returns 0.0 if <2 candles) | config crt_engine.atr_period=14 (configs/production/v2_htfcrt_2026_08.json:230) via config_builder/validator; CRTConfig dataclass default 14 (state_identity.py:147) and method default period=14 exist | LIVE (runtime + backtest) | SAME from 15th candle in buffer; DIFFERENT on first 14 candles of a session (partial mean vs canonical NaN) | HIGH-impact site (SL/TP/entry filters) but LOW divergence risk: formula identical in steady state; risk limited to warm-up and to the absolute-vs-relative unit boundary |
| 2 | `src/research/indicators.py:12` | `atr` | Research-side ATR used by hypotheses, controls, interpreters and regime labeling (reused by ~20 modules: regime_observer, process_characterization, candle_state, sujan_crt, visual_crt, adapters, hypotheses/*, controls/*, interpreters/reference, point_and_figure). | SMA of TR over last period+1 bars (prev close), partial window when fewer bars, 0.0 if <2 bars | function default period=14; callers pass atr_period constructor args mostly defaulted to 14 (not from config) | RESEARCH/offline | SAME from bar 14; partial values on bars 1..13 | MEDIUM for research verdicts (drives simulated SL/TP), none for live trades |
| 3 | `src/interpreters/regime_observer.py:58` | `RegimeLabeler._trailing_atr` | Per-bar ATR series to classify each bar as Compression/Normal/Expansion by trailing 480-bar ATR terciles. | WRAPPER: calls research.indicators.atr on bars[i-period:i+1]; atr[0]=0 | dataclass default atr_period=14 (hardcoded default) | RESEARCH (OBSERVATION event, no production weight) | SAME (delegates to #2) | LOW (regime labels only) |
| 4 | `src/research/candle_state/transition_target.py:25` | `atr_per_bar` | ATR series used to build forward volatility-expansion TARGETS (is next-k-bar ATR > theta x current ATR?). | WRAPPER over research.indicators.atr; zeros in warm-up | default period=14 (hardcoded) | RESEARCH | SAME (delegates to #2) | LOW; lookahead is by design in the target, must never be used as a feature |
| 5 | `src/research/secondlow_v1/detector.py:61` | `compute_true_range_atr` | Normalizes purge depth, pre-2h return and post-purge displacement into ATR units; also ATR14/100/200 regime metrics (depth_metrics.py, regime_metrics.py). | pandas concat-max TR (bar0 = H-L), rolling(period, min_periods=period//2) | module constant ATR_PERIOD=14 (hardcoded); 100/200 hardcoded in callers | RESEARCH | SAME from bar 14; 8 early partial values (min_periods=7) | LOW |
| 6 | `src/data_ingestion/corpus_gate.py:117` | `_median_true_range` | Yardstick for 'is this price gap implausible?' when admitting an OHLCV corpus: gaps are expressed in multiples of the corpus median TR. | MEDIAN (not mean) of all positive TRs over the whole corpus; bar0 TR=H-L; single scalar, no rolling window | no period (whole corpus); thresholds from gate cfg | LIVE data path (admission before backtest/cache build), not trade math | DIFFERENT by design (median, global) | NONE for trades; affects which corpora are admitted |
| 7 | `scripts/analysis/p3b_gate_expired_counterfactual_rr.py:49` | `compute_atr` | Approximate counterfactual RR for expansion episodes the 495-candle TTL guard expired: were they alpha or stale? | pandas concat-max TR, rolling(14, min_periods=1) | hardcoded period=14 at call site l.278 | RESEARCH/offline | SAME from bar 14; 14 early partial values | LOW (offline gate evidence), but it informed a promotion decision |
| 8 | `scripts/analysis/purge_delay_scan.py:81` | `_true_range (+ rolling at l.121)` | Filters micro-breaks of the 20-day high/low and measures purge penetration/depth in ATR units. | pandas concat-max TR, rolling(atr_window) default min_periods -> first valid bar 13; includes the purge bar's own TR | CLI --atr-window default 14 (declared arg with silent default) | RESEARCH/offline | SAME from bar 14 (1 early value) | LOW |
| 9 | `scripts/backtest/manual_backtest.py:99` | `atr` | Re-implements the full CRT spec outside the engine: displacement 1.2xATR, wick 1.5xATR, expansion guard 0.2xATR, retest ceiling 0.5xATR, SL = displacement extreme +/-0.2xATR, TP1=1xATR, TP2=2xATR, slippage U(0,0.08xATR). | SMA of last min(14,len) TRs over a 42-bar buffer (same shape as engine); 1-candle fallback = H-L | module constant ATR_PERIOD=14 (hardcoded) | OFFLINE backtest (not the production backtest_v2) | SAME as engine (#1) incl. warm-up behaviour | MEDIUM if its PnL is ever quoted as engine evidence; formula matches, but the rest of the pipeline is a parallel copy |
| 10 | `scripts/research/high_acceptance_scan.py:71` | `add_local_atr` | Normalizes the acceptance score by local ATR so candles in volatile vs quiet periods are comparable (display/normalization only). | pandas concat-max TR, rolling(14, min_periods=14) | module constant ATR_PERIOD=14, labelled 'display-only, not a registered ontology feature' | RESEARCH | SAME from bar 14 (1 early value at bar 13) | COSMETIC |
| 11 | `scripts/research/high_acceptance_structural_scan.py:82` | `add_local_atr` | Volatility features for the acceptance model: atr_local, atr_zscore, range_to_atr. | same as #10 with literal 14 | hardcoded 14 | RESEARCH | SAME from bar 14 | LOW |
| 12 | `scripts/research/high_acceptance_group_ablation.py:79` | `local_atr` | Recomputes ATR for the volatility feature group and a stability-normalized target in ablation runs. | same as #11 | hardcoded 14 | RESEARCH | SAME from bar 14 | LOW |
| 13 | `scripts/research/high_acceptance_normalization_control.py:95` | `local_atr` | Control study: does ATR-normalizing the acceptance score remove the volatility confound (spearman(atr_local, raw score) = -0.486)? | VERBATIM copy of #12 | hardcoded 14 | RESEARCH | SAME from bar 14 | LOW |
| 14 | `scripts/research/high_acceptance_regime_stability.py:92` | `local_atr` | ATR for trailing-tercile Compressed/Normal/Expanded regimes; mirrors regime_observer construction but in pandas. | pandas concat-max TR, rolling(ATR_PERIOD, min_periods=ATR_PERIOD); terciles over 480 bars | module constant ATR_PERIOD=14 | RESEARCH | SAME from bar 14; regime cut rule approx equal to #3 (pandas rolling quantile vs np.percentile) | LOW |
| 15 | `scripts/research/smc_visual_verification.py:135` | `compute_atr_absolute` | Replays the pipeline's SMC zone loop in absolute price units to visually verify detected OB/FVG zones vs a trader's chart. | pandas concat-max TR, rolling(period) then fillna(0) | CONFIG: feature_pipeline.atr_period read from production config (l.499) | RESEARCH | SAME from bar 14 (1 early value at bar 13; zeros before) | COSMETIC/verification |
| 16 | `scripts/research/zone_x_o4_gap_study.py:89` | `wilder_atr` | Measures realized adverse excursion at stop resolution in ATR units vs nominal m, especially on gapping bars (XAUUSD M15). | WILDER smoothing (alpha=1/period) seeded by SMA of first 14 TRs; bar0 TR=H-L | module constant ATR_PERIOD=14 | RESEARCH (RESEARCH_ONLY/DESCRIPTIVE) | DIFFERENT: measured mean rel diff 14%, p95 44% vs canonical | MEDIUM for conclusions: ATR-unit results are not transferable to engine ATR multiples without rescaling |
| 17 | `tools/btcusdt_crt_v3_replay.py:151` | `_atr_proxy` | Reproduces a handover doc's worked scoring examples; 'ATR' there is a proxy used for relative range and scores. | RANGE PROXY: mean(H-L) of previous 5 bars (no prev close, excludes current bar); fallback full_range or 0.001 | hardcoded 5 bars (per doc Table 8) | VALIDATION tool, explicitly not wired to production | DIFFERENT: measured mean rel diff 20%, p95 48% | NONE for live; do not reuse as ATR |
| 18 | `scripts/analysis/volatility_regime_certification.py:40` | `oracle_true_range` | Independent re-implementation of the pipeline TR used to certify volatility-regime features against feature_pipeline. | TR identical to pipeline incl. bar0 NaN propagation | n/a | OFFLINE certification | SAME by design (it is the parity oracle) | NONE |

## Parity check (measured)

read-only replication on data/mt5/XAUUSD_M15.csv first 6000 bars (2024-05-22..), research.indicators.atr imported, others re-implemented verbatim; 2026-09-27

- **research.indicators.atr / engine compute_atr / manual_backtest**: exact (max_abs 0) from bar 14; non-zero partial-window mean on bars 1..13 where canonical is NaN
- **pandas rolling(14,min_periods=14) with concat-max TR (high_acceptance x5, smc_visual)**: exact from bar 14; 1 extra early value at bar 13 (bar0 TR=H-L instead of NaN)
- **secondlow min_periods=7**: exact from bar 14; 8 early partial values
- **p3b min_periods=1**: exact from bar 14; 14 early partial values
- **zone_x wilder14**: DIFFERENT: mean rel diff 13.97%, p95 43.6%, max_abs 3.56 (XAU price units)
- **btcusdt range_proxy5**: DIFFERENT: mean rel 19.9%, p95 47.7%
- **corpus_gate median TR**: not comparable (single corpus-wide scalar, median not mean)

## Grouping by business function

- **A. Trade construction and entry filters (SL/TP/displacement/wick/expansion/retest)**: #1, #9
- **B. Research hypothesis simulation (SL/TP in ATR multiples, counterfactual RR)**: #2, #7
- **C. Volatility regime classification**: #3, #14
- **D. Research normalization / features (express a measurement in ATR units)**: #5, #8, #10, #11, #12, #13, #15, #16
- **E. Research targets/labels**: #4
- **F. Data quality / corpus admission**: #6
- **G. Validation / doc replay tools**: #17
- **H. Certification twin**: #18

## Top risks

- R1 (live, SL/TP/entry): engine compute_atr (#1) equals canonical only after 14 TRs are in its buffer. On the first 14 candles of a run it uses a partial-window mean where the pipeline has NaN, so displacement/wick/expansion gates and SL buffer can fire on an unstable ATR. Buffer is never reset on HTF/gap reset (steady state stays exact).
- R2 (units): engine and scripts use ABSOLUTE ATR; the published pipeline `atr` (FM-041) is CLOSE-RELATIVE. Consumers convert with atr*close (execution_planner l.425, crt_state_resolver l.1907 behind a .get(...,True) default). A missed conversion changes SL/TP by a factor of the price (F-072 class). This is a bigger outcome risk than the formula copies.
- R3 (silent defaults): engine period is config-declared (crt_engine.atr_period=14) but CRTConfig/compute_atr/research.indicators/regime_observer/hypotheses all carry default 14; resolver range_atr_period uses thr.get(...,14); purge_delay --atr-window default 14. A missing key silently yields 14 instead of failing.
- R4 (research evidence transfer): zone_x_o4 Wilder ATR (#16) differs ~14% mean / 44% p95 from the SMA ATR. Its ATR-unit stop-excursion results cannot be applied to engine sl_atr_buffer/tp multiples without rescaling.
- R5 (parallel pipeline): manual_backtest (#9) matches engine ATR but duplicates the whole CRT trade logic; its PnL is not engine evidence.
- R6 (not ATR): btcusdt range proxy (#17) is labelled ATR but is mean(H-L) of 5 prior bars; it should never be reused as ATR.

## Reuse sites (not copies)

- src/research/process_characterization.py:53 atr_series
- src/research/sujan_crt/driver.py:56 _atr_series
- src/research/visual_crt/controls.py:259 _atr_at
- src/research/adapters/structural_event_source.py:64 _atr
- src/research/conditional_entropy_grid.py:99
- src/research/candle_state/encoder.py:189
- src/research/hypotheses/* and src/research/controls/* (atr(window, atr_period))
- src/interpreters/reference.py, point_and_figure.py
- src/research/secondlow_v1/depth_metrics.py, regime_metrics.py (reuse #5)

## Unit-conversion sites (not copies)

- src/config_layer/execution_planner.py:425 atr_abs = atr*close (unit conversion of canonical FM-041)
- src/features/crt_state_resolver.py:1893 _atr_abs (canonical atr*close when thresholds.expansion_atr_is_relative, default True via .get)
- src/research/model_runners/adapters/execution_plan.py:280 (same conversion)
- scripts/analysis/b2a_feature_candidate_certification.py, crt_local_math_authority_probe.py, gd004_disp_rescale_probe.py (parity probes)

## Open

- Engine CRTConfig loader: not verified whether a missing crt_engine.atr_period raises or falls back to dataclass default 14
- Whether backtest_v2 feeds the engine the same first candles as the pipeline (determines if the R1 warm-up window overlaps tradable bars)
- src/features/feature_states.py '_trailing_atr' named in census line 99 was not found by name in that file (may have been renamed)
