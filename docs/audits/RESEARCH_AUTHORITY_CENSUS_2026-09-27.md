# Research Authority Census - 2026-09-27

Scope: READ-ONLY census of `D:\Tradelatest` at HEAD `09ffcb1` (working tree dirty; see git status note at end). This is a companion to `docs/audits/RESEARCH_FUNCTION_CENSUS_2026-09-27.md`, which this document does not modify. It contains no refactor, governance, manifest, promotion, versioning or implementation plans.

Evidence tags (every claim carries one):
- **RUNTIME**: observed by executing repo code or reading data in memory during this audit (Python run with `-B`, `PYTHONDONTWRITEBYTECODE=1`, no file writes).
- **STATIC**: read from source / import graph / file listing.
- **DOC**: stated in repo docs (`docs/current-findings.md`, module docstrings, architecture docs), not independently re-verified here.
- **UNKNOWN**: not determined.

Role definitions used in this document:
- **Authority**: the producer other code is expected to use for that object (highest fan-in and/or declared governing).
- **Twin**: a reimplementation or thin wrapper that is proven or built to agree with an Authority (delegates to it, or parity-tested against it).
- **Shadow**: a reimplementation whose output feeds downstream labels, metrics, qualification/certification, or replay.
- **Experiment**: a one-off, study-local implementation whose output feeds no other producer and no label/training/qualification path.
- **Unknown**: consumers could not be determined.
- "Expected" duplication = Twin + Experiment. "Drift" = Shadow + competing Authority.

---

## Headline results

1. **Q7 (tie-break) quantified - RUNTIME.** Replaying real backtest setups (1,534 deduplicated trades, 11 symbols, M15) through `sl_tp_comparator.simulate_exit` (TP2-first) versus an SL-first relabel: **20 trades (1.3%) change label**; win rate -1.30 pp, profit factor 1.230 -> 1.173, expectancy +0.117R -> +0.091R (-0.027R). The effect is concentrated: XAUUSD 5.0% affected (-0.082R), BNBUSDT 1.4% (-0.034R), SOLUSDT 2.4%; FX pairs 0%. On the exact inputs of `execution_planner_replay` for BNBUSDT, the SL-first rule flips cell D (rejected, structure SL) from **+0.172R to -0.040R** and **more than doubles the reported structure-side selection effect (0.185 -> 0.398)**.
2. **Q8 (canonical L9 object) - STATIC.** There is no single canonical L9 outcome object. `research.contracts.Outcome` (produced only by `forward_walk`) is the de-facto research Authority for labels, qualification and training. `TradeRecord` is the execution ledger object (defined three times under the same name). `OracleOutcome` is oracle-local. Conversions exist in one direction only (ledger -> episode/label, ad-hoc dict -> diagnostic column); no converter maps between Outcome and TradeRecord. Two scripts mix Outcome-family and TradeRecord-family objects in one analysis.
3. **Expected vs drift - STATIC.** Across the four layers tabled (L9, L0, HTF, R2): **59 expected** (26 Twin + 33 Experiment), **31 drift** (26 Shadow + 5 competing Authority), **6 Unknown**, plus 9 non-competing Authorities. Drift by layer: L9 8, L0 16, HTF 5, R2 2.
4. **R0 Research Substrate - CONFIRMED as an implicit layer, but only partly used.** High fan-in (provenance 67, contracts 47, costs 40, forward_walk 35, qualification 24; STATIC). It is not declared as a layer anywhere (DOC); only a fragment is declared ("governing exit kernel = forward_walk", with a "do not invent a fourth simulator" rule, in the Opportunity Episode substrate doc). The main label paths use it; consumers bypass it at L0 (31 of 53 loaders use no shared loader) and at L9 (8 Shadow walks).

---

## A. Authority census

### A.1 L9: walk / MFE / MAE / TP-SL producers

Tie-break semantics referenced below: "SL-first" = on a bar that touches both stop and target, stop wins. "TP2-first" = target wins. The two can only disagree on a bar spanning both the stop and TP2 (SL+TP1 on one bar resolves to SL under both rules; STATIC, `sl_tp_comparator.py:149-205`, `crt_engine_v2.py:_intrabar_trigger_price`).

| # | Producer | Layer | Object | Role | Evidence | Consumers | Justification |
|---|---|---|---|---|---|---|---|
| 1 | `research/measurement/forward_walk.py:forward_walk` (+`forward_walk_oco`, which delegates to it) | L9 | `research.contracts.Outcome` | **Authority** (research) | STATIC fan-in 35 modules / 32 non-test importers; RUNTIME SL-first (same-bar touch -> `SL_HIT`, rr -1.0); DOC "GOVERNING" (`docs/architecture/opportunity-episode-research-substrate.md` s.5) | `clean_labels.builder` (TN/Envelope labels), `episodes.policy` (LabelSet), `rr_l3_label_generation`, `train_gaussian_xauusd`, `runner`, `qualification` via `metrics`/`EdgeAggregator`, `phase_s_selection_effect`, 20+ studies | Declared governing kernel; sole producer of `Outcome`. |
| 2 | `research/oracle/multi_tp_walk.py:multi_tp_walk` | L9 | `OracleOutcome` | **Authority** (oracle, two-target) | STATIC: `tie_break` param, default `production` (SL-first), `optimistic` = comparator convention; DOC module docstring | `oracle/labeler` (labels BOTH tie-breaks per unit; primary arm = production; reports `tie_break_divergence`), `oracle/exit_sweep` (production) | Different scope from #1 (partial TP1, trail, runner pricing); tie-break is explicit and recorded per row, so not in conflict with #1. |
| 3 | `config_layer/crt_engine_v2.py:_intrabar_trigger_price` + `ExecutionEngine.update_trade` | L9 (execution) | engine trade state | **Authority** (execution) | STATIC: SL tested before TP1 (OPEN) and SL/BE before TP2 (TP1 status) | `backtest_v2` hot loop | The effective production rule is SL-first; `update_trade`'s declared TP2>SL>TP1 order almost never binds (DOC `multi_tp_walk` docstring). |
| 4 | `runtime/backtest_v2.py:_resolve_exit` / `TradePathStats` | L9 (execution) | `TradeRecord` (+ `.path`) | **Authority** (execution ledger) | STATIC; DOC (`episodes/projectors/spine.py` docstring: path stats are not persisted per trade, only as aggregates in summary.json) | `*_trades.csv` / summary.json -> `episodes/projectors/spine`, `governance/portfolio_validation`, 42 `BacktestRunner` importers | Same pipeline as #3 (not competing): #3 steps the trade, #4 prices it into the ledger. |
| 5 | `research/oracle/reference_walker.py` | L9 | oracle outcome | **Twin** of #2 | RUNTIME (task-1 census): 300/300 agreement | `oracle/__init__` | Independent parity walker. |
| 6 | `scripts/misc/trade_replay_validator.py` | L9 | replay check | **Twin** of #3/#4 | STATIC | `scripts/backtest/manual_backtest.py` | Validation-only replay. |
| 7 | `research/oracle/exit_analysis.py:horizon_excursions` | L9 | MFE/MAE | **Twin** | STATIC; requires `tie_break`, `exit_object`, `cost_basis` as metadata | `scripts/research/exit_geometry_scan.py` | Declares its basis explicitly. |
| 8 | `analytics/sl_tp_comparator.py:simulate_exit` | L9 | ad-hoc exit dict `{exit_reason, exit_price, realized_rr, candles_held}` | **Shadow** | STATIC TP2-first, hard-wired (docstring claims "matches BacktestRunner", contradicted by #3 and by DOC `multi_tp_walk`); RUNTIME divergence quantified in s.D | `scripts/research/execution_planner_replay.py` -> `replay_*.json` -> `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md` -> F-002, F-010 evidence (DOC) | Its output feeds replay attribution cited in findings, and it uses the opposite tie-break from the execution Authority. |
| 9 | `scripts/research/opportunity_scanner.py:_simulate` | L9 | `opportunities.jsonl` rows (outcome, rr_achieved) | **Shadow** | STATIC (trailing model); task-1 census consumers | `opportunity_bands`, `derive_opportunity_rr_bands`, `auto_train_from_opportunities` (training), `replay/timing_reconstructor`, `trade_lifecycle_engine`; `clean_labels.builder` reads the stream outcome as a DIAGNOSTIC column only (STATIC `builder.py:68-72,163-171`) | Feeds a training path. |
| 10 | `replay/timing_reconstructor.py:simulate_with_timing` | L9 | timing replay | **Shadow** | STATIC 3 importers | `build_pattern_library`, `early_invalidation_ab`, `early_invalidation_exectrade_ab` | Feeds replay studies and a pattern library. |
| 11 | `scripts/analysis/xauusd_excel_feature_state_trace.py:walk_plan_outcome` | L9 | trace outcome | **Shadow** | STATIC 4 importers | `crt_episode_number_trace`, `run_crt_trace_workflow`, `session_filter_funnel_probe`, `trade_intent_ownership_shadow` | Output feeds other producers (trace workflow). |
| 12 | `governance/strategy_backtest.py` | L9 | strategy backtest result | **Shadow** | STATIC 2 importers | `governance/multi_strategy_validator`, `scripts/validate_integration` | Feeds a validation path. |
| 13 | `scripts/research/run_xau_metals_protocol_v1.py:build_outcomes` | L9 | MFE/MAE + `Outcome` | **Shadow** | STATIC (imports `Outcome`, `forward_walk`, `EdgeAggregator`) | Its own qualification report (EdgeReport) | Reimplements MFE/MAE next to `forward_walk` and feeds qualification. |
| 14 | `scripts/research/xauusd_gaussian_m4_qualify.py:build_outcomes_for_arm` | L9 | MFE/MAE + `Outcome` | **Shadow** | STATIC (imports `Outcome`, `EdgeAggregator`) | Qualification report | Same as #13. |
| 15 | `scripts/research/gate0_tn_env_feasibility.py:_bars_to_mfe` (+ its label rules) | L9 | label feasibility metrics | **Shadow** | STATIC (uses `forward_walk` but re-derives bars-to-MFE and label rules) | Gate-0 feasibility decision for TN/Envelope labels (DOC-level; artifact consumers UNKNOWN) | Feeds a label-feasibility gate. |
| 16 | `research/measurement/trade_lifecycle_engine.py` (`WalkResult`, `AuthorityOutcome`, `LifecycleMeasurement`) | L9 | own result types | **Experiment** | STATIC 0 importers (imports `forward_walk`, `opportunity_scanner`) | none | Unused wrapper; its types are consumed nowhere. |
| 17 | `scripts/analysis/p3b_gate_expired_counterfactual_rr.py:simulate_exit` | L9 | ad-hoc dict | **Experiment** | STATIC 0 importers | none found | Study-local counterfactual. |
| 18 | `scripts/research/l003h_trail_exit_transition_replay.py:{fixed,trailing}_walk_events` | L9 | events | **Experiment** | STATIC 0 importers; DOC declared "Duplicate forward_walk" | none found | Declared, study-local. |
| 19 | `scripts/research/zone_x_o4_gap_study.py:first_passage_stop_events` | L9 | events | **Experiment** | STATIC 0 importers | none found | Study-local. |
| 20 | `scripts/backtest/manual_backtest.py:run` | L9 | manual trades | **Experiment** | STATIC 0 importers | none found | Manual tool. |
| 21 | `scripts/research/erp_synth_4h_trace.py:intended_spec` | L9 | trace | **Experiment** | STATIC 0 importers | none found | Study-local. |
| 22 | `research/structural_asymmetry.py:measure_path` | L9 | MFE/MAE | **Experiment** | STATIC 1 importer (`scripts/research/phase_e_structural_asymmetry.py`, its own driver) | its driver only | Library + one study. |
| 23 | `scripts/analysis/phase1_shadow_create_economic_census.py:_mfe_mae` | L9 | MFE/MAE | **Experiment** | STATIC 0 importers | none found | Census study. |
| 24 | `scripts/research/high_acceptance_scan.py:compute_horizon` | L9 | MFE/MAE horizon | **Experiment** | STATIC 0 importers | none found | Scan study. |
| 25 | `scripts/research/jse003_engine_context_history_path_geometry.py:main` | L9 | path geometry | **Experiment** | STATIC 0 importers | none found | Study-local. |
| 26 | `identity/certify.py:_update_path` | L9 | MFE/MAE in certification | **Unknown** | STATIC 0 importers; artifact consumers UNKNOWN | UNKNOWN | Certification semantics suggest a qualification-like path, but no consumer found. |
| 27 | `_m8_cert_probe` (named in task-1 census) | L9 | MFE/MAE | **Unknown** | UNKNOWN: the file was not re-located by filename search in this pass | UNKNOWN | |

Count reconciliation (STATIC): the task-1 census headline "16 (+3 twins)" counted independent implementations. This table lists every named producer: 4 Authorities, 3 Twins, 8 Shadows, 10 Experiments, 2 Unknown. The exact mapping of the 23 non-Authority rows onto the earlier "16" is UNKNOWN.

**L9 summary (STATIC):** expected = 13 (3 Twin + 10 Experiment); drift = 8 Shadow + 0 competing Authority; Unknown = 2. Label-producing paths: `clean_labels.builder`, `episodes.policy`, `rr_l3_label_generation`, `train_gaussian_xauusd` all go through `forward_walk` (SL-first); `oracle/labeler` goes through `multi_tp_walk` with both tie-breaks recorded (STATIC). **No label path found uses the comparator.** The label-risk Shadows are #9 (training via opportunities.jsonl, trailing model), #13-#15 (qualification / feasibility), and #8 (replay attribution cited in findings).

### A.2 L0: OHLC loaders

This pass re-derived the loader list statically (a `def load_*/read_*` with OHLC/timestamp handling in the body, under `src`, `scripts`, `tools`, `mt5_analytics`, excluding tests) and found **53 files** (plus the execution `CandleLoader` class). The task-1 census reported 57 with a looser heuristic; the 4-row difference is UNKNOWN. "Shared" = uses one of `CandleLoader`, `ohlcv_schema`/`require_reviewed_clock`, `xauusd_phase1_candidate` guard, `mc_kit`, `validate_dataset`. The "Imp" column counts importers by module basename, so it is unreliable for generic names such as `driver` (STATIC caveat).

| # | Producer (loader fn) | Shared | Imp | Role | Evidence | Justification / consumers |
|---|---|---|---|---|---|---|
| 0 | `runtime/backtest_v2.py:CandleLoader` | clock gate (`require_reviewed_clock(..., basis=_resolved_session_ts_basis())`) | 90 (backtest_v2) | **Authority** (execution) | STATIC line 935; RUNTIME refuses unreviewed `data/BNBUSDT_M15.csv` via the same gate | Only `BacktestRunner` adds `validate_dataset` (DOC F-039). |
| 1 | `inout/live_rail/ohlcv_replay_port.py:read_corpus_rows/load_corpus_bars` | none | 2 | **Authority** (live-rail, separate scope) | STATIC | Execution-side live replay, not a research competitor. |
| 2 | `research/mc_kit/bars.py:load_bars` | none | 4 | **competing Authority** | STATIC | Research-side shared loader; consumers add `validate_dataset`. |
| 3 | `research/probes/corpus.py:load_corpus` | none | 19 | **competing Authority** | STATIC | Research probe hub loader. |
| 4 | `research/model_runners/substrate.py:load_ohlcv_csv` | none | 16 | **competing Authority** | STATIC | R6 loader (task-1: "only substrate duplicates L0"). |
| 5 | `research/runner.py:_load_candles` | CandleLoader | 18 | **Twin** | STATIC `runner.py:173-174` | Measurement runner reuses execution loader. |
| 6 | `research/visual_crt/driver.py:load_bars` | CandleLoader, validate_dataset | - | **Twin** | STATIC | |
| 7 | `research/mother_range/driver.py:load_bars` | mc_kit, validate_dataset | - | **Twin** (of #2) | STATIC | |
| 8 | `research/sujan_crt/driver.py:load_bars` | mc_kit, validate_dataset | - | **Twin** (of #2) | STATIC | |
| 9 | `research/evidence/mother_range_prior.py:load_bars` | mc_kit, validate_dataset | 0 | **Twin** (of #2) | STATIC | |
| 10 | `scripts/research/build_resampled_data.py:_load_m15` | CandleLoader | 0 | **Twin** | STATIC | |
| 11 | `scripts/research/h_rr_threshold_001.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | |
| 12 | `scripts/research/path_ambiguity_census.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | |
| 13 | `scripts/research/phase_b_conditional_entropy.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | |
| 14 | `scripts/research/phase_d_exit_grid.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | |
| 15 | `scripts/research/qualify_regime_conditioning.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | Qualification path, but through the Authority loader. |
| 16 | `scripts/research/qualify_regime_transition.py:_load_candles` | CandleLoader | 0 | **Twin** | STATIC | Same. |
| 17 | `scripts/analysis/implementation_model_validation_xauusd.py:load_corpus` | CandleLoader, guard | 0 | **Twin** | STATIC | |
| 18 | `scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py:load_corpus` | ohlcv_schema | 0 | **Twin** | STATIC | |
| 19 | `analytics/sl_tp_comparator.py:load_candles_from_csv` | ohlcv_schema + clock gate (no `validate_dataset`) | 1 | **Shadow** | STATIC `:491-521`; RUNTIME refuses `data/BNBUSDT_M15.csv` (clock UNREVIEWED) | Own parser; feeds `execution_planner_replay`. |
| 20 | `replay/timing_reconstructor.py:load_candles` | ohlcv_schema | 3 | **Shadow** | STATIC | Feeds replay studies. |
| 21 | `scripts/analysis/bnbusdt_trade_anatomy.py:load_candles` | none | 4 | **Shadow** | STATIC; used by `build_clean_labels_tn_env.py:26,90` | **Label path** (TN/Envelope clean labels) on an ungated naive-timestamp parser. |
| 22 | `scripts/research/rr_l3_label_generation.py:_load_candles` | none | 0 | **Shadow** | STATIC `:59-76` | **Label path** (RR L3 labels). |
| 23 | `scripts/research/opportunity_scanner.py:_load_csv` | guard (XAU only), `pd.read_csv` | 1 | **Shadow** | STATIC `:49,185` | Feeds opportunities.jsonl -> training. |
| 24 | `scripts/research/build_bar_matrix.py:_load_candles` | validate_dataset | 0 | **Shadow** | STATIC | Bar matrix feeds `oracle/labeler` (labeler re-reads `bm_manifest["corpus_path"]` with `pd.read_csv`, `labeler.py:403`). |
| 25 | `scripts/research/run_h_g001_001_sweep_veto.py:_load_ohlcv` | guard | 0 | **Shadow** | STATIC (imports `EdgeAggregator`) | Qualification report. |
| 26 | `scripts/research/_enrich_xauusd_corpus.py:load_ohlcv/load_corpus` | none | 0 | **Shadow** | STATIC | Produces a derived corpus. |
| 27 | `scripts/analysis/b2a_feature_candidate_certification.py:_load_corpus` | none | 0 | **Shadow** | STATIC | Feature certification. |
| 28 | `scripts/analysis/pit_phaseC_feature_certification.py:_load_corpus` | none | 0 | **Shadow** | STATIC | Feature certification. |
| 29 | `research/secondlow_v1/detector.py:load_ohlcv` | none | 3 | **Shadow** | STATIC | Research driver with consumers. |
| 30 | `research/sujan_manipulation/driver.py:load_bars` | validate_dataset | - | **Shadow** | STATIC | Own parser, validated. |
| 31 | `research/zone_mapping/gaussian_family_shadow_eval.py:_load_candles` | none | 2 | **Shadow** | STATIC | Feeds zone-mapping evaluation metrics. |
| 32 | `scripts/analysis/pit_swing_blast_radius.py:_load_corpus` | none | 1 | **Unknown** | STATIC | One importer; purpose not confirmed. |
| 33 | `scripts/research/rr_l2_feature_truth.py:_load_candles` | none | 0 | **Unknown** | STATIC | Whether its output feeds L3 labels is UNKNOWN. |
| 34 | `scripts/research/xauusd_gaussian_econ_ledger.py:load_bars` | guard | 0 | **Unknown** | STATIC | Economic ledger; downstream UNKNOWN. |
| 35 | `research/ic002_entry_evolution/build_trajectories.py:_load_ohlcv_df` | none | 1 | **Unknown** | STATIC | |
| 36-53 | `mt5_analytics/evaluate_bar_features_outcome:load_bars`; `scripts/analysis/{blind_label_sample:_load_frame, feature_semantic_adjudication_pass_a:_load_ohlcv (guard), purge_delay_scan:_load_ohlcv, purge_slice:load_corpus, run_crt_local_math_parity_audit:_load_ohlcv, run_msip_shadow:_load_ohlcv}`; `scripts/research/{_build_xauusd_library_and_eval:load_corpus, crt_range_rebuild_probe:load_ohlcv, l003h_trail_exit_transition_replay:load_candles, mc_cpr_l0_residual_harness:_load_ohlcv, run_crt_state_on_mt5_xauusd:load_ohlcv, smc_visual_verification:load_bars, validate_crt_state_resolver:_load_dataframe, visual_state_sample:load_csv_rows, xauusd_episode_semantic_reconstruction:_load_csv, zone_x_o4_gap_study:load_ohlcv}`; `tools/btcusdt_crt_v3_replay:load_csv` (18 files) | none (1 guard) | 0 | **Experiment** | STATIC 0 importers each | Study-local; no label/training/qualification consumer found. |

**L0 summary (STATIC):** 2 Authorities (execution + live-rail, non-competing); expected = 32 (14 Twin + 18 Experiment); drift = 16 (13 Shadow + 3 competing research Authorities); Unknown = 4. Two of the Shadows are on label paths (#21, #22) and one feeds oracle labels (#24).

### A.3 HTF / resample producers

| Producer | Object | Role | Evidence | Justification |
|---|---|---|---|---|
| `runtime/backtest_v2.py:HTFBuilder` | HTF id per LTF candle; `count` (N candles) or `calendar` (via `features.calendar_periods.period_key`) | **Authority** (execution) | STATIC `:271` default `htf_clock_basis="count"`; no JSON/YAML under `configs/` sets `htf_clock_basis` (STATIC search), so count is effective everywhere except research CLI overrides (`execution_planner_replay --htf_clock_basis`) | DOC F-075: the count id is "an HTF clock, not an HTF candle". |
| `research/resample.py:resample` | calendar-true HTF candles | **competing Authority** (research) | STATIC; task-1 | Different object (calendar candle) from the execution default (count id). Two authorities for "HTF". |
| `features/calendar_periods.py` | calendar period key | **Twin** of `research.resample._RULE_HOURS` | DOC/STATIC (documented duplicate, layering rule) | Declared duplicate. |
| `features/crt_state_resolver.py:build_htf_id_timeline` | HTF id timeline | **Twin** of `HTFBuilder` | STATIC/DOC (task-1: byte-equivalent) | Also used by `build_bar_matrix` (-> oracle labels). |
| `trace_sweep_geometry.build_htf_ids` | HTF ids | **Twin** | STATIC | Reconstruction probe. |
| `scripts/research/build_resampled_data.py` | resampled CSVs | **Twin** | STATIC (CandleLoader) | |
| `.resample` in `high_acceptance_scan`, `purge_delay_scan` | pandas resample | **Experiment** (2) | STATIC | Study-local. |
| `scripts/data/{build_m15_unified, prepare_data, convert_binance_m1_to_m15}`, `scripts/misc/resample_m1_to_m15` | M15 corpora from M1 | **Shadow** (4) | STATIC; task-1 | Four producers of the base corpora every loader reads. |

**HTF summary (STATIC):** 1 Authority; expected = 6 (4 Twin + 2 Experiment); drift = 5 (4 Shadow + 1 competing Authority).

### A.4 R2 state producers (in light of F-069 and F-077)

| Producer | Object | Role | Evidence | Justification / consumers |
|---|---|---|---|---|
| `config_layer/crt_engine_v2.py` `StateMachine` (`try_displacement_to_expansion`) | CRT state (execution) | **Authority** | STATIC | Execution truth. |
| `features/crt_state_resolver.py:CRTStateResolver` | CRT state (declarative) | **competing Authority** | DOC F-069 (VALIDATED 2026-08-05): 88.16% bar agreement with the engine on 47,197 XAUUSD M15 bars, EXPANSION recall 10.77%, "cannot reach engine parity through configuration alone"; STATIC ~31 importers including `runtime/backtest_v2` (construction trace), `build_bar_matrix` (-> oracle labels), `crt_resolver_economic_comparison` | Non-equivalent state object with its own execution-side and label-side consumers. |
| `parent_crt` (`config_layer/htf_state`, `runtime/parent_crt_feed`) | calendar-true H4 parent CRT | **Authority** (parent-TF bias gate) | DOC F-075 (ON by default on the active config) | Different object from the M15 state. |
| Sujan 4H CRT (`research/sujan_crt`), `mother_range`, `secondlow_v1` | independent CRT-like objects | **Experiment** (3; declared independent) | DOC F-077: "Romeo/Sujan 4H CRT is not the same object as repo H4 ParentCRT or the M15 episode - equivalence is NOT established" | Declared distinct objects, so not drift. Their L0 loaders are separately counted in A.2. |
| visual / weekly re-expressions (`research/visual_crt`, weekly) | re-expressed state | **Twin** | STATIC (task-1) | Re-expressions of engine output. |
| `crt_range_rebuild_probe`, `crt_state_confusion_matrix`, `trace_sweep_geometry`, `retest_divergence_probe` | reconstruction | **Twin** (4) | STATIC (task-1) | Parity/reconstruction probes. |
| `tools/btcusdt_crt_v3_replay.py` | own state replay | **Shadow** | STATIC (task-1) | Independent state replay; artifact consumers UNKNOWN. |

**R2 summary:** 2 Authorities; expected = 8 (5 Twin, with visual/weekly counted as one family, + 3 declared-independent Experiments); drift = 2 (CRTStateResolver as competing Authority, btcusdt_crt_v3_replay as Shadow). `tools/btcusdt_crt_v3_replay` also appears in A.2 as an Experiment *loader*; the two rows are different objects (OHLC loading vs state).

### A.5 Expected vs drift totals

| Layer | Authority (non-competing) | Twin | Experiment | Shadow | competing Authority | Unknown | Expected | Drift |
|---|---|---|---|---|---|---|---|---|
| L9 | 4 | 3 | 10 | 8 | 0 | 2 | 13 | 8 |
| L0 | 2 | 14 | 18 | 13 | 3 | 4 | 32 | 16 |
| HTF | 1 | 4 | 2 | 4 | 1 | 0 | 6 | 5 |
| R2 | 2 | 5 | 3 | 1 | 1 | 0 | 8 | 2 |
| **Total** | **9** | **26** | **33** | **26** | **5** | **6** | **59** | **31** |

(STATIC; role assignment is this audit's judgement against the definitions above.)

---

## B. R0 Research Substrate

**Verdict: CONFIRMED as an implicit layer, partly bypassed.**

Evidence for a layer (STATIC unless noted):
- Fan-in: `provenance` 67, `contracts` 47, `costs` 40, `forward_walk` 35, `registry` 28, `config` 26, `qualification` 24, `indicators` 24, `metrics` 20, `controls` 16, `runner` 15 (task-1 import graph).
- One-way dependency: no `src/research` module is reachable from execution modules; research depends on execution, never the reverse (task-1, STATIC).
- The label paths go through it: `clean_labels.builder`, `episodes.policy`, `rr_l3_label_generation`, `train_gaussian_xauusd` all call `forward_walk`. 20 modules consume `EdgeAggregator`/`EdgeReport` for qualification.

Evidence that it is implicit, not declared (DOC):
- No doc declares a layer covering provenance + contracts + costs + measurement + qualification.
- The declared "Opportunity Episode Research Substrate" (`docs/architecture/opportunity-episode-research-substrate.md`, `research/episodes`, protocol OE_L1) is narrower. It names `forward_walk` the "Governing exit kernel" and states a hard rule: "one policy kernel family (forward_walk modes). Do not invent a fourth simulator." Its package has 1 importer outside `episodes/` (`scripts/research/build_episodes.py`, STATIC).

Evidence of bypass:
- L0: 31 of 53 loaders use no shared loader or validator; 3 research loaders compete with `CandleLoader` (STATIC, A.2).
- L9: 8 Shadow walks reimplement outcome/MFE logic outside `forward_walk`/`multi_tp_walk` (STATIC, A.1), including one on a training path (opportunity_scanner) and two in qualification scripts that also use `EdgeAggregator` (they use R0 for aggregation but bypass it for the walk).
- Clock gate: `CandleLoader` and the comparator loader enforce `require_reviewed_clock`; the label-path loaders `bnbusdt_trade_anatomy.load_candles` and `rr_l3_label_generation._load_candles` do not (STATIC). RUNTIME: `data/BNBUSDT_M15.csv` is clock UNREVIEWED (detector guess "LOOKS_UTC", low confidence) and is refused by the gated loaders; the ungated loaders would read it.

---

## C. Q8: canonical L9 outcome object

| Object | Defined in | Producers | Consumers | Evidence |
|---|---|---|---|---|
| `Outcome` | `research/contracts.py` (fields: signal, outcome, rr_achieved, mfe, mae, duration_candles, time_to_tp, time_to_failure, reached_1r) | `forward_walk`, `forward_walk_oco` only | **Training/labels:** `clean_labels.builder`, `episodes.policy` (LabelSet fields "mirror research.contracts.Outcome"), `rr_l3_label_generation`, `train_gaussian_xauusd`. **Evaluation:** `metrics`, `runner`, `regime_conditioning`. **Qualification:** `qualification` + 20 `EdgeAggregator` consumers. **Promotion studies:** `xauusd_gaussian_m4_qualify`, `run_xau_metals_protocol_v1`, `crt_resolver_economic_comparison`. **Replay:** `phase_s_selection_effect` (RETEST_REPLAY -> forward_walk) | STATIC |
| `OracleOutcome` | `research/oracle/multi_tp_walk.py` | `multi_tp_walk` (twin: `reference_walker`) | `oracle/labeler` (oracle labels, tie-break per row), `oracle/exit_sweep` | STATIC |
| `TradeRecord` (x3 distinct classes, same name) | `runtime/backtest_v2.py`; `journal/schema.py`; `analytics/sl_tp_comparator.py` | backtest ledger; journal `trade_logger`; comparator | backtest: `governance/portfolio_validation`, `*_trades.csv` readers, `episodes/projectors/spine`; journal: `scripts/validate_integration`; comparator: its own report | STATIC |
| Ad-hoc dicts | comparator `simulate_exit`; `p3b...simulate_exit`; `opportunity_scanner` rows; `trade_lifecycle_engine` types (0 users) | respective scripts | `execution_planner_replay` (comparator dicts -> `_aggregate_variant_results`); opportunities.jsonl -> training and `clean_labels` diagnostic column | STATIC |
| `Outcome` (name collision) | `governance/identity_chain.py` | governance | governance | STATIC; unrelated class with the same name |

**Conversions (STATIC):**
- Ledger -> episode: `episodes/projectors/spine.py` reads `{INSTRUMENT}_trades.csv` (a TradeRecord projection), joins on timestamp (records a measured +1 `candle_idx` offset), then re-labels under a single-TP policy via `forward_walk`. The ledger outcome is kept verbatim as `metadata.ledger` with an explicit "not comparable" warning.
- Stream -> label diagnostic: `clean_labels.builder` maps stream `outcome`/`exit_reason` strings (TP1/TP2/TP_HIT...) into `stream_y_tp1/stream_y_tp2`, documented as "diagnostic agreement only - never primary y".
- No converter was found between `Outcome` and `TradeRecord`, or between `OracleOutcome` and `Outcome` (UNKNOWN whether one exists under a non-obvious name).

**Mixers (STATIC):**
- `scripts/research/crt_resolver_economic_comparison.py`: `BacktestRunner` (TradeRecord family) + `forward_walk`/`Outcome` + `EdgeAggregator` in one analysis.
- `scripts/research/execution_planner_replay.py`: `BacktestRunner` ledger (real `pnl_rr_net`, SL fidelity check) + comparator ad-hoc dicts (TP2-first, no partial/trail/costs). Its own trust gate comment says the two differ by exit model and that the difference "cancels in every delta"; s.D shows the tie-break does not cancel.

**Answer:** no single canonical object exists. De facto, `research.contracts.Outcome` is canonical for research labels/qualification/training, and `TradeRecord` (backtest_v2) is canonical for executed trades. The two are bridged only one-way (ledger -> episode) with an explicit non-comparability flag.

---

## D. Q7 quantified: TP2-first (comparator) vs SL-first (engine)

### D.1 Method (RUNTIME, in memory)
- TP2-first: `analytics.sl_tp_comparator.simulate_exit(entry_fill, dir, sl, tp1, tp2, forward, max_candles=100)` imported and called unchanged.
- SL-first: same result, relabelled when the comparator returned `TP2` and the exit bar (`forward[candles_held-1]`) also touches SL -> `SL`, rr = -1.0. Because SL+TP1 on one bar is already SL under both rules, this is exactly the engine's `_intrabar_trigger_price` / `forward_walk` precedence for a two-target, no-partial walk. **Caveat:** it does not model the engine's partial TP1 / half-way trail / costs (neither does the comparator).
- Entry bar = candle whose timestamp equals `opened_at`; forward bars start at the next candle (the same convention as `execution_planner_replay._simulate_cell` and `episodes/projectors/spine`).
- Metrics: WR = share rr>0; avgWinR = mean rr of winners; PF = sum(rr>0) / |sum(rr<0)|; expectancy E = mean rr (the comparator's own `avg_realized_rr` and `expectancy_rr` are the same number).
- No files written. Corpora were read with `csv.DictReader` (the comparator's `load_candles_from_csv` refuses `data/BNBUSDT_M15.csv` because its clock is UNREVIEWED, RUNTIME).

### D.2 Inputs
- Setups, set 1: the largest *joinable* `*_trades.csv` per symbol (trades whose `opened_at` exists in the corpus), e.g. `results/phase6e_shadow_ab/treat_shadowFalse_V3/run_20260601_223310_BNBUSDT/BNBUSDT_trades.csv` (89), `results/k23_shadow/run_20260924_194133_XAUUSD__20240522..20260521_v2_htfcrt_k23_shadow_2026_09_7de09f62/XAUUSD_trades.csv` (27), `results/validation_tmp/run_20260602_091841_SOLUSDT/SOLUSDT_trades.csv` (31), `results/ETHUSDT/run_20260523_102200_ETHUSDT/ETHUSDT_trades.csv` (31), `results/session_sweep/_runs/run_20260601_175144_BTCUSDT/BTCUSDT_trades.csv` (23), and small FX/XRP files (233 trades total).
- Setups, set 2: all 1,328 `results/**/*_trades.csv`, 897 with joinable rows, deduplicated on (symbol, opened_at, direction, sl, tp2, entry_fill) -> **1,534 unique setups**.
- Corpora: `data/{AUDUSD,BNBUSDT,BTCUSDT,ETHUSDT,EURCAD,EURUSD,GBPUSD,SOLUSDT,USDJPY,XRPUSDT}_M15.csv` (2024-05-22..2026-05-21) and `data/mt5/XAUUSD_M15.csv` (47,275 bars, 2024-05-22..2026-05-21). Timeframe: M15 only (no other TF had joinable trades).
- Replay set: `results/execution_planner_replay/_run/run_20260603_201914_BNBUSDT/BNBUSDT_crt_telemetry.jsonl` (134 RETEST_REPLAY records: 35 selected / 99 rejected) + `data/BNBUSDT_M15.csv`; `results/research/execution_planner_replay_xauusd_postfix/_run/run_20260913_183517_XAUUSD/XAUUSD_crt_telemetry.jsonl` (23 records) + `data/mt5/XAUUSD_M15.csv`. Helper functions (`_norm_ts`, `_load_replay`, `_structure_levels`, `_vanilla_levels`, `_simulate_cell`) were extracted from `scripts/research/execution_planner_replay.py` by AST and executed in memory (the script itself was not run).

### D.3 Results: pooled deduplicated setups (set 2, RUNTIME)

| Symbol (M15) | n | Affected | Share | WR TP2-first -> SL-first | avgWinR | PF | E (R) | dE |
|---|---|---|---|---|---|---|---|---|
| **ALL** | **1534** | **20** | **1.3%** | **49.0 -> 47.7 (-1.30 pp)** | 1.279 -> 1.286 | **1.230 -> 1.173** | **+0.1172 -> +0.0906** | **-0.0266** |
| XAUUSD | 80 | 4 | 5.0% | 50.0 -> 45.0 | 1.185 -> 1.247 | 1.185 -> 1.020 | +0.0926 -> +0.0110 | -0.0816 |
| SOLUSDT | 165 | 4 | 2.4% | 46.1 -> 43.6 | 1.113 -> 1.157 | 0.951 -> 0.896 | -0.0266 -> -0.0587 | -0.0321 |
| BNBUSDT | 794 | 11 | 1.4% | 50.3 -> 48.9 | 1.313 -> 1.308 | 1.326 -> 1.250 | +0.1622 -> +0.1278 | -0.0343 |
| BTCUSDT | 94 | 1 | 1.1% | 41.5 -> 40.4 | 1.319 -> 1.335 | 0.935 -> 0.906 | -0.0379 -> -0.0559 | -0.0180 |
| ETHUSDT | 135 | 0 | 0% | 60.7 | 1.218 | 1.885 | +0.3473 | 0 |
| AUDUSD | 194 | 0 | 0% | 42.3 | 1.208 | 0.884 | -0.0669 | 0 |
| EURUSD | 46 | 0 | 0% | 52.2 | 1.733 | 1.891 | +0.4262 | 0 |
| EURCAD / GBPUSD / USDJPY / XRPUSDT | 10 / 9 / 5 / 2 | 0 | 0% | unchanged | | | | 0 |

### D.4 Results: largest joinable file per symbol (set 1, RUNTIME)
ALL n=233: affected 6 (2.6%); WR 47.2 -> 44.6 (-2.58 pp); PF 1.171 -> 1.057; E +0.0902 -> +0.0315 (-0.0587R). BNBUSDT (89): 4 affected (4.5%), PF 1.348 -> 1.089, E +0.168 -> +0.047. SOLUSDT (31): 2 affected (6.5%), E -0.096 -> -0.189. The other files had 0 affected trades.

### D.5 Results: `execution_planner_replay` cells (RUNTIME)
BNBUSDT: the TP2-first recomputation reproduces the stored `results/execution_planner_replay/replay_bnbusdt.json` exactly (A 0.2857, B 0.3571, C 0.1818, D 0.1717; selection_effect_structure 0.1854).

| Cell | n | Affected | E TP2-first | E SL-first | PF TP2-first -> SL-first |
|---|---|---|---|---|---|
| A selected / vanilla | 35 | 0 | +0.2857 | +0.2857 | 1.500 |
| B selected / structure | 35 | 0 | +0.3571 | +0.3571 | 1.833 |
| C rejected / vanilla | 99 | 0 | +0.1818 | +0.1818 | 1.300 |
| D rejected / structure | 99 | **7 (7.1%)** | **+0.1717** | **-0.0404** | 1.340 -> 0.930 |

Attribution under SL-first: sltp_effect_on_rejected -0.0101 -> -0.2222; selection_effect_structure 0.1854 -> 0.3975; average selection effect 0.1447 -> 0.2507; average SL/TP effect +0.0307 -> -0.0754. The stored verdict (`dominant_effect: selection`) is unchanged, but the magnitudes move by more than 2x. The stored `avg_selection_effect` 0.1447 matches the "+0.145R selection edge" attributed to F-002 (DOC: `docs/current-findings.md` F-021 "Reversal" line and the `phase_s_selection_effect.py` docstring, which call that figure STALE).

XAUUSD postfix: 3 selected, 0 affected. All 20 rejected RETEST_REPLAY records carry `entry=0.0, disp_low=0.0, disp_high=0.0` (RUNTIME). The stored XAUUSD replay JSONs (`execution_planner_replay_xauusd{,_postfix}` C/D = -1.0 on 20, `_calendar` C/D = -1.0 on 26) are therefore computed from zero-price levels, and their `avg_selection_effect` of 1.0 / 2.0 is an artifact of that (RUNTIME for postfix telemetry; the same cause for the `_calendar` file is inferred, UNKNOWN).

### D.6 Ambiguous-bar frequency
Real setups were available, so the fallback metric was not needed. For reference, the ambiguous exit-bar frequency among the replayed setups equals the affected share: 1.3% pooled, 0-5% per symbol (RUNTIME). A corpus-wide scan of every bar was not run.

### D.7 Who consumes the comparator's output (STATIC unless noted)
- `scripts/research/execution_planner_replay.py` is the only non-test importer (plus `tests/test_sl_tp_comparator.py`).
- Outputs: `results/execution_planner_replay/replay_bnbusdt.json`; `results/research/execution_planner_replay_xauusd{,_calendar,_postfix}/replay_bnbusdt.json` (same filename reused for XAUUSD).
- Documents citing them: `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md`, which is cited as evidence in `docs/current-findings.md` **F-002** and **F-010** (DOC); `docs/analysis/selection-effect-crypto6-2026-06-13.md`, `backtest-trust-audit-2026-06-10.md`, `topics/analytics-sltp.md` (mentions, STATIC).
- Code reusing the script's helpers but NOT the comparator output: `phase_s_selection_effect` (imports `_load_replay`, `_norm_ts`, `_run_backtest`; walks with `forward_walk`, so SL-first), `research/adapters/structural_event_source` (imports `_run_backtest`, `_norm_ts`), `live_path_replay` (mirrors `_run_backtest`).
- `research/oracle/{multi_tp_walk, reference_walker, exit_sweep}` reference the comparator's convention only as the `optimistic` tie-break option (text reference, no import).
- No label, training or qualification path consumes comparator output (STATIC).

---

## E. Q1 / Q4: loader, HTF construction and timezone basis per Authority and label path

| Path | Role | Loader | Clock gate | HTF construction | Timezone basis | Evidence |
|---|---|---|---|---|---|---|
| `backtest_v2.BacktestRunner` / engine | Authority (exec) | `CandleLoader` + `validate_dataset` | yes (`basis=_resolved_session_ts_basis()`) | `HTFBuilder`, count (no config sets `calendar`) | declared per corpus in clock registry; sessions via `features.broker_clock` | STATIC |
| `research/runner` (measurement) | Authority user | `CandleLoader` (`runner.py:173`) | yes | none of its own (HTF only through engine features) | as CandleLoader | STATIC |
| `forward_walk` / `multi_tp_walk` | Authorities | none (take candles from caller) | caller's | n/a | caller's | STATIC |
| `clean_labels.builder` via `build_clean_labels_tn_env` | label path | `bnbusdt_trade_anatomy.load_candles` (csv.DictReader, naive `fromisoformat`); XAU guard only | **no** | none | naive timestamps as stored | STATIC |
| `rr_l3_label_generation` | label path | own `_load_candles` (naive) | **no** | none | naive | STATIC |
| `train_gaussian_xauusd` | training | `CandleLoader` + phase-1 guard | yes | `HTFBuilder(candles_per_htf=htf_n)` (count) | as CandleLoader | STATIC `:160-177` |
| `oracle/labeler` | label path | `pd.read_csv` of bar-matrix `corpus_path` (matrix built by `build_bar_matrix` with `validate_dataset`) | **no** (in labeler) | `crt_state_resolver.build_htf_id_timeline` (via bar matrix; count-equivalent to HTFBuilder) | naive, `parse_dates` | STATIC |
| `episodes` (spine projector / policy) | label path | caller-provided candles; joins ledger by timestamp | inherits caller | none | ledger timestamps | STATIC |
| `opportunity_scanner` | training feed | `pd.read_csv` (+ XAU guard) | **no** | none | naive | STATIC |
| `execution_planner_replay` | replay | `CandleLoader` (backtest) + comparator loader | yes (both) | `HTFBuilder` count, or `--htf_clock_basis calendar` | as CandleLoader | STATIC; RUNTIME the comparator loader refuses `data/BNBUSDT_M15.csv` today |

Findings (Q1/Q4):
- **Q1 (loader):** the execution Authority and `train_gaussian_xauusd` use `CandleLoader`. Three of five label paths (`clean_labels` TN/Env, `rr_l3`, `oracle/labeler`), plus the `opportunity_scanner` training feed, use ungated ad-hoc readers (STATIC).
- **Q4 (HTF):** every path that builds an HTF uses the count-based id (`HTFBuilder` or its byte-equivalent twin). The calendar basis is reachable only through research CLI overrides and `research.resample` (STATIC). F-075's calendar-true parent CRT is a separate object (DOC).
- **Timezone:** no loader on these paths converts time zones (no `tz_localize`/`tz_convert` found in them, STATIC). All read the stored naive timestamps. The difference is declaration and gating, not conversion: gated loaders refuse corpora whose clock is not reviewed (RUNTIME: `data/BNBUSDT_M15.csv` UNREVIEWED, `data/mt5/XAUUSD_M15.csv` REVIEWED), while the ungated label loaders accept any corpus. Session-hour logic differs: `features/session_classifier` + `broker_clock` in execution, raw `ts.hour` windows in research shadows (task-1, STATIC).

---

## F. Remaining open questions (re-prioritized)

1. **(High, label integrity)** Should `sl_tp_comparator` remain TP2-first while its docstring says "matches BacktestRunner"? The RUNTIME delta (-0.027R pooled, -0.08R on XAUUSD, and a 2x swing in replay attribution) shows the difference does not cancel across cells.
2. **(High)** XAUUSD RETEST_REPLAY rejected records carry zero prices. Are the stored XAUUSD replay attributions (selection effect 1.0 / 2.0) cited anywhere as evidence? (UNKNOWN; only the BNBUSDT doc was traced.)
3. **(High, label integrity)** Three label paths load candles without the clock gate. Do any of them currently consume unreviewed corpora (e.g. BNBUSDT)? (UNKNOWN which corpora their last runs used.)
4. **(High)** Oracle labels are built on `CRTStateResolver` state via the bar matrix, and F-069 shows only 88% agreement with engine state (10.8% EXPANSION recall). Which oracle label families depend on resolver state? (UNKNOWN.)
5. **(Medium)** `opportunity_scanner` (trailing, own walk) feeds `auto_train_from_opportunities`. Is that training path still live, and what is its label divergence from `forward_walk` on the same setups? (Not measured here.)
6. **(Medium)** Qualification scripts `run_xau_metals_protocol_v1` and `xauusd_gaussian_m4_qualify` compute MFE/MAE outside `forward_walk`. Are their outcomes numerically equal to `forward_walk`'s on the same signals? (Not measured.)
7. **(Medium)** Which of the three research loaders (`mc_kit.bars`, `probes.corpus`, `model_runners.substrate`) is the intended research-side Authority, if any? (UNKNOWN; none uses the clock gate.)
8. **(Low)** Reconcile the loader count (53 here vs 57 in task 1) and locate `_m8_cert_probe`.
9. **(Low)** The `identity/certify._update_path` consumer chain.
10. **(Low)** The `TradeRecord` name used by three unrelated classes and `Outcome` by two. Does any consumer import the wrong one? (No instance found, STATIC.)

---

Git status note: before this audit the repo showed 483 porcelain entries at HEAD `09ffcb1` (including the untracked task-1 census doc). This document is the only file added by this audit.
