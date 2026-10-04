# Research Function Census - 2026-09-27

Read-only forensic audit of `D:\Tradelatest` at HEAD `09ffcb1`. The working tree was already dirty before the audit (482 porcelain entries). No code or existing file was modified. This document is the only file the audit wrote.

**Evidence tags:** RUNTIME (actually executed, read-only, in memory) > STATIC (AST or source read) > DOC (repo docs, registry labels, docstrings) > UNKNOWN.
**Scope examined:** 1,201 `.py` files under `src/`, `scripts/`, `tools/`, `mt5_analytics/`, `manual_tools/`, and the repo root. The research census covers 671 non-`__init__` files: `src/research` (224), `scripts/research` (175), `scripts/analysis` (159), `src/analytics`, `src/replay`, `src/llm_research`, `scripts/{data,backtest,misc,training}`, `tools/`, `mt5_analytics/`, and root scripts. Three files could not be parsed and were skipped: `scripts/governance/crt_config_construction_census.py`, `audit.py`, and `count_audit_tmp.py`. Excluded: `.claude/worktrees/**`, `logs/**/scratch_roots/**`, `archive/`, `copiedSrcFiles/`, and packaged copies (`H-SECONDLOW-002_Complete_Package`, `msip_1_verification_package`).
**Method:** AST import resolution. The repo imports without a prefix (`from research...`, `from features...`), with `src/` on `sys.path`. Other methods: function-definition census, regex census of inline formulas, reachability from execution entry modules, and textual similarity (difflib) for suspected copies.
**Prior artifacts used:** `docs/current-findings.md` (F-039, F-069, F-075, F-077), `data/script_registry.jsonl` (492 rows), module docstrings, `scripts/analysis/layer_trace/*`. `pyan_call_flow.dot` is dated 2026-06-06, about 3.5 months before HEAD, so it was treated as stale and not relied on. Every claim below was re-derived from source.

---

## Verdict

**The research layer is a collection of independent scripts orbiting a small shared core. It is not a cohesive framework.** [STATIC]

- **Scripts, not a framework:**
  - The research import graph splits into 242 connected components. 232 are singletons. The largest component has 250 files, and it holds together only because many files import a handful of hub modules.
  - 132 of 492 research files (`src/research`, `scripts/research`, `scripts/analysis`) import nothing internal beyond `utils`/`provenance`.
  - The script registry labels 483 of 492 entries `LOGIC_IN_SCRIPT` [DOC]. Static import analysis agrees with that label.
- **The shared core:**
  - Hub modules and their non-test fan-in: `research.measurement.forward_walk` 35, `research.contracts` 47, `research.costs` 40, `research.provenance` 67, `research.qualification` 24, plus the execution modules `features.feature_pipeline` 84, `runtime.backtest_v2` 90 and `config_layer.crt_engine_v2` 75.
  - The core forms two genuinely coherent sub-frameworks:
    - the Edge-Discovery harness: `contracts -> registry -> hypotheses -> runner -> forward_walk -> metrics -> qualification`;
    - `research.model_runners`: a substrate plus 15 adapters that call production engines only.
- **Duplication outside the core:**
  - About 36 of 57 named OHLC loaders use no shared loader or validator.
  - There are 17 or more independent ATR implementations, using SMA, Wilder, median and range-proxy variants.
  - There are 16 independent TP/SL outcome walks, and at least one uses a different same-bar tie-break from the engine.
  - There are 10 permutation-test and 8 Benjamini-Hochberg implementations.
- **Layering:**
  - No `src/research` module is reachable from any execution entry module (`runtime`, `live`, `inout`, `engines`, `strategies`, `core`, `execution`, `portfolio`). Research depends on execution, never the reverse.
  - Execution-side duplicates of research logic are documented as intentional because of this rule (`features/calendar_periods.py` docstring) [STATIC+DOC].
- **Runtime check:** the measurement core was confirmed read-only in memory. `mc_kit.trade.forward_walk is research.measurement.forward_walk` returned True. The declared twin `reference_walk` agreed with `multi_tp_walk` on 300/300 synthetic paths. `forward_walk` resolves a same-bar SL+TP touch as `SL_HIT` [RUNTIME].

---

## 1. Research Function Census

Components are classified only by Input Object -> Transformation -> Output Object. Family membership counts use code-signal thresholds (imports, definitions, identifiers) [STATIC-heuristic]. 151 of 371 signal-bearing files match two or more families, so families are **not** cleanly separated at file level. 298 of 671 files show no rail signal: repo introspection, governance, LLM or context tooling. They produce no layer object and belong to no rail.

| Family | Input -> Transformation -> Output | Canonical object | Files with signal | Evidence |
|---|---|---|---|---|
| **R1 Data Construction** | OHLC/features/outcomes -> enumerate, label, persist -> datasets, episodes, opportunity logs, label sets, corpora | Opportunity row (`opportunities.jsonl`); clean-label dataset (`clean_labels.builder.BuildResult`); Episode (`research.episodes.schema`) | 79 | STATIC |
| **R2 State Construction** | OHLC + features -> classify or state-machine -> CRT/HTF/parent/candle/regime state timelines | CRT state: engine `StateMachine` (`config_layer/crt_engine_v2.py`) for execution; `CRTStateResolver` (`features/crt_state_resolver.py`, "Layer 5") for the semantic pipeline | 60 | STATIC; F-069 (DOC): the resolver cannot reach engine parity by configuration alone |
| **R3 Measurement** | Signal/entry geometry + future bars -> forward walk -> Outcome (rr, MFE, MAE, duration, exit reason); EdgeReport | `research.contracts.Outcome` via `forward_walk`; `OracleOutcome` via `multi_tp_walk` (two-target); `TradeRecord`/`TradePathStats` via `backtest_v2` on the execution path | 159 | STATIC + RUNTIME |
| **R4 Attribution** | Outcomes x context/feature partitions -> controls, permutation/BH, stratification, ablation -> qualification verdicts, lift, attribution tables | `research.qualification` (permutation p, BH, `QualConfig`); `research.controls` (random_baseline, always_long) | 104 | STATIC |
| **R5 Validation** | Two producers of the same object -> compare -> parity/agreement/confusion/certification reports | No single canonical object. Closest: `episode_agreement.Agreement` (O14) and per-feature certification JSON | 155 | STATIC |
| **R6 Decision Replay** *(new)* | Historical OHLC -> production engines run off-spine -> per-bar score, decision and execution-plan envelopes (L4-L7 objects) | `research.model_runners.envelope` ("single serialization authority") | ~25 | STATIC |

**Why R6 is added:** `src/research/model_runners` produces decision-layer objects that none of R1-R5 cover. It has an orchestrator, 15 adapters, a substrate and an envelope. Adapter docstring: "call production engines only". Adapters wrap `engines.crt_engine`, `core.decision_engine`, `core.fusion_engine`, `config_layer.execution_planner`, `engines.zone_cluster_score`, `training.trade_net_v2` and others. Consumers include `scripts/research/{run_model_offline, run_xauusd_all_models_report, execution_planner_replay, live_path_replay, model_shadow_protocol}` and the `*_shadow_*` scripts. It is not R2 (it outputs scores and decisions, not states) and not R3 (it outputs no measured outcome) [STATIC].

**Considered and not added:** cost calibration (`research.costs`, `research.mt5_cost_calibration`, `scripts/research/xauusd_mt5_cost_*`). It produces a `CostModel` whose only consumer is R3's net-R, so it is folded into R3 as an input sub-object [STATIC].

### Per-family automation census (observation only)

| Family | Status | Basis |
|---|---|---|
| R1 | Partially automated | 20 scripts are referenced by the control plane, agent or CLI. Among them: `scripts/research/opportunity_scanner`, `scripts/data/{prepare_data, unified_data_builder, build_rr_dataset, fetch_*}` and `scripts/training/*`. Every other builder is a manual `argparse` entry point (240 of 527 research-scope files use `argparse`) [STATIC] |
| R2 | Manual | No state-construction research script is wired to the control plane or CI [STATIC] |
| R3 | Partially automated | Reached through `research.cli` (`run`, `qualify`) -> `HypothesisRunner`. Everything else is invoked script by script [STATIC] |
| R4 | Partially automated | `research.cli qualify` plus `research.qualify_matrix` (11 `qualify_*` drivers). Other attribution studies are manual [STATIC] |
| R5 | Manual | Certification and parity probes are one-off scripts. Only 2 CI workflows exist (`erp-test-harness.yml`, `governance.yml`); tests cover some parity (e.g. `tests/research/test_resample_corpus_parity.py`) [STATIC] |
| R6 | Partially automated | Single orchestrator (`model_runners.runner`), invoked manually [STATIC] |

Fully automatable opportunities (belong to a future System Operations Layer outside L0-L9): R3/R4 through the existing `research.cli` pattern; R5 parity probes that already compare two in-repo producers deterministically (`verify_m5_resample_parity`, `crt_state_confusion_matrix`, `reference_walk` vs `multi_tp_walk`) [STATIC].

---

## 2. Producer Census

Column key: **Exec?** = on the execution path (reachable from `runtime`/`live`/`inout`/`engines`/`strategies`/`core`) | **Imp auth?** = imports the authority | **Reimpl?** = reimplements authority logic. All rows are STATIC unless tagged otherwise.

### R1 Data Construction

| Producer | Role | Object produced | Consumers | Research-only | Exec? | Imp auth? | Reimpl? |
|---|---|---|---|---|---|---|---|
| `src/research/clean_labels/builder.py:build_dataset/label_one_unit` | **Authority** (labels) | Bernoulli and continuous label datasets | `scripts/research/{build_clean_labels_tn_env, analyze_clean_labels_tn_env, build_rr_dataset_from_clean_labels}` | yes | no | yes (`forward_walk`, `horizon_excursion`) | no |
| `src/research/episodes/{builder,store,tensors,projectors}` | **Authority** (episodes) | Episode timeline, store and tensors | `scripts/research/build_episodes.py`, `episodes/query.py`, `evidence/*` | yes | no | `policy.py` imports `forward_walk` | no |
| `src/research/oracle/labeler.py:label_corpus` | **Authority** (oracle labels) | Every-bar two-direction labels | `oracle/scan.py`, `scripts/research/oracle_pattern_scan.py` | yes | no | yes (`forward_walk.AdverseFill`, `multi_tp_walk`) | no |
| `scripts/research/opportunity_scanner.py` | **Shadow** (+ producer) | `opportunities.jsonl` | `research.opportunity_bands`, `scripts/research/derive_opportunity_rr_bands.py`, `scripts/auto_train_from_opportunities.py`, `src/replay/timing_reconstructor.py` | yes | no | imports `feature_pipeline`; **not** `forward_walk` | yes: own trailing walk `_simulate` |
| `scripts/research/gate0_tn_env_feasibility.py` | **Shadow** | TN/ENV feasibility labels | reports only | yes | no | no | yes: `_bars_to_mfe` is 0.88 similar to `clean_labels.builder._bars_to_mfe`; `_stream_y` mirrors the builder's label rules |
| `scripts/research/{build_trace_corpus, build_bar_matrix, story_library_build}`, `src/research/{ic003_shapes, ic003b_sequence_geometry, ic002_entry_evolution, synthetic}` | **Unknown** (independent corpora, no shared authority exists) | Trace, shape and sequence corpora | own downstream scripts | yes | no | n/a | n/a |
| `scripts/data/{prepare_data, build_m15_unified, unified_data_builder, convert_binance_m1_to_m15}`, `scripts/misc/resample_m1_to_m15` | **Shadow** (L0 corpus) | On-disk M15 CSVs | `CandleLoader`-based consumers (UNKNOWN which corpora) | shared | no | no | yes: own `.resample()` (see Section 3) |
| `features/dataset_builder.py`, `config_layer/rr/rr_dataset_builder.py` | Execution-side training datasets | Training matrices | `training/*`, `engines/*` | no | adjacent | - | - |

### R2 State Construction

| Producer | Role | Object | Consumers | Research-only | Exec? | Imp auth? | Reimpl? |
|---|---|---|---|---|---|---|---|
| `config_layer/crt_engine_v2.py:StateMachine/RangeDetector/detect_sweep` | **Authority** (execution CRT state) | Engine CRT state and events | `backtest_v2`, live rail; 75 importers | no | **yes** | - | - |
| `features/crt_state_resolver.py:CRTStateResolver` | **Authority** (semantic L5); F-069 says it is structurally non-equivalent to the engine | Resolver state timeline | 13 importers (`scripts/research` x8) | no | yes (backtest_v2 closure) | partial | `build_htf_id_timeline` is a declared "byte-equivalent" reimplementation of `backtest_v2.HTFBuilder` |
| `config_layer/parent_crt.py` + `features/parent_candle.py` | **Authority** (parent C1/C2/C3), F-075 | Parent CRT bias | `runtime.parent_crt_feed`, backtest | no | yes | imports engine | no |
| `scripts/research/{run_crt_state_on_mt5_xauusd, validate_crt_state_resolver, xauusd_episode_semantic_reconstruction}`, `model_runners/adapters/crt_state_machine.py` | **Reuse** | State timelines | reports | yes | no | yes | no |
| `src/research/visual_crt/{geometry,retest,pools}.py`, `weekly_sweep/weekly_range.py` | **Reuse + re-expression** (engine constants imported; geometry re-expressed against chart pools, declared "MODELLING SUBSTITUTION") | Visual/weekly sweep states | `visual_crt.driver`, `qualify_weekly_sweep` | yes | no | yes (constants) | partial, declared |
| `src/research/sujan_crt/geometry.py` ("No CRT engine"), `sujan_manipulation/state.py`, `mother_range/geometry.py` ("No CRT engine"), `secondlow_v1/detector.py` | **Unknown / independent families** (declared independent objects, not engine copies; F-077: Sujan 4H CRT != repo ParentCRT) | Alternative CRT-like states | own drivers | yes | no | no | independent by declaration [DOC] |
| `src/research/candle_state/encoder.py:CandleStateEncoder` | **Authority** (candle state) | Discrete candle state + features | `candle_state/*`, 4 scripts | yes | no | reuses `research.indicators` | no |
| `scripts/research/crt_range_rebuild_probe.py`, `crt_state_confusion_matrix.py` (reconstructed engine timeline), `trace_sweep_geometry.py` (3 detectors), `retest_divergence_probe.py` | **Twin** (reconstruct in order to compare) | Confusion and divergence reports | none downstream | yes | no | yes (resolver) | yes, for validation |
| `tools/btcusdt_crt_v3_replay.py` | **Shadow** ("standalone reference harness") | BitNet CRT scoring replay | none | yes | no | `crt_sweep_taxonomy` only | yes (`_recent_sweep`, `_atr_proxy`) |
| `interpreters/regime_observer.py`, `features/feature_states.py` | Regime / feature-state producers | Regime labels, feature states | `mt5_analytics`, `scripts/research` x3 | mixed | partial | - | `_trailing_atr` own ATR |

### R3 Measurement

| Producer | Role | Object | Consumers | Research-only | Exec? | Imp auth? | Reimpl? |
|---|---|---|---|---|---|---|---|
| `src/research/measurement/forward_walk.py:forward_walk/forward_walk_oco/horizon_excursion` | **Authority** | `Outcome` (rr_achieved, mfe, mae, duration_candles, outcome) | 35 non-test importers: `runner`, `exit_grid`, `forensics`, `clean_labels`, `episodes.policy`, `path.ambiguity_census`, `trade_lifecycle_engine`, `zone_label_audit`, 12 `scripts/research`, `mt5_analytics/engines/features/mfe_mae_engine.py` | yes | **no** | - | - |
| `src/research/measurement/metrics.py:EdgeAggregator` | **Authority** | `EdgeReport` | runner, 14 scripts | yes | no | - | - |
| `src/research/mc_kit/trade.py:walk_horizon` | **Reuse** (thin wrapper; `mk.forward_walk is forward_walk` -> True [RUNTIME]) | Outcome | sujan_crt, mother_range, evidence priors | yes | no | yes | no |
| `src/research/oracle/multi_tp_walk.py` | **Authority** (two-target SEM-017; separate kernel) | `OracleOutcome` | `labeler`, `exit_sweep`, `exit_analysis`, `reference_walker`, 1 script | yes | no | no (independent by design) | overlaps forward_walk's single-target semantics |
| `src/research/oracle/reference_walker.py` | **Twin** (declared "deliberately naive twin") | OracleOutcome | parity tests | yes | no | constants only | intentional; 300/300 agreement [RUNTIME] |
| `src/research/oracle/exit_analysis.py:horizon_excursions` | **Twin** (declared vectorised counterpart of `horizon_excursion`) | MFE/MAE arrays | oracle program | yes | no | references both | intentional |
| `config_layer/crt_engine_v2.py:_intrabar_trigger_price` + `ExecutionEngine.update_trade` | **Authority** (execution exit; SL-first on a spanning bar) | Trade status | backtest, live | no | **yes** | - | - |
| `runtime/backtest_v2.py:_resolve_exit`, `TradePathStats` | **Authority** (execution booking, MFE/MAE) | `TradeRecord` | 90 importers | no | yes | engine | - |
| `src/analytics/sl_tp_comparator.py:simulate_exit` | **Shadow**. Docstring: "TP2 > SL > TP1 (same as BacktestRunner)". The engine resolves SL before TP on a spanning bar, so the claim conflicts with `_intrabar_trigger_price` | exit dict | `scripts/research/execution_planner_replay.py` | mixed | no | no | yes, divergent tie-break |
| `scripts/analysis/p3b_gate_expired_counterfactual_rr.py:simulate_exit`, `scripts/analysis/xauusd_excel_feature_state_trace.py:walk_plan_outcome`, `scripts/research/zone_x_o4_gap_study.py:first_passage_stop_events`, `scripts/backtest/manual_backtest.py:run`, `scripts/research/erp_synth_4h_trace.py:intended_spec`, `src/governance/strategy_backtest.py` | **Shadow** | rr/exit | own reports | yes | no | no | yes |
| `scripts/research/l003h_trail_exit_transition_replay.py:{fixed,trailing}_walk_events` | **Shadow (declared)**: "Duplicate forward_walk", "Duplicates opportunity_scanner._simulate" | events | report | yes | no | no | yes |
| `src/replay/timing_reconstructor.py:simulate_with_timing` | **Shadow** ("Mirrors scripts/research/opportunity_scanner", a shadow of a shadow) | outcome + timing | replay | yes | no | no | yes |
| `scripts/misc/trade_replay_validator.py:replay_single_trade` | **Twin** (validator; "SL-first matches BacktestRunner") | replay verdict | none | yes | no | no | intentional |
| MFE/MAE shadows: `src/identity/certify.py:_update_path`, `src/research/structural_asymmetry.py:measure_path`, `scripts/analysis/phase1_shadow_create_economic_census.py:_mfe_mae`, `scripts/research/high_acceptance_scan.py:compute_horizon`, `run_xau_metals_protocol_v1.py:build_outcomes`, `xauusd_gaussian_m4_qualify.py:build_outcomes_for_arm`, `jse003_...:main`, `_m8_cert_probe.py` | **Shadow** | MFE/MAE | own reports | yes | no | mostly no | yes |

### R4 Attribution

| Producer | Role | Object | Consumers | Imp auth? | Reimpl? |
|---|---|---|---|---|---|
| `src/research/qualification.py` (permutation_p_value, benjamini_hochberg, evaluate_pre_bh, finalize) | **Authority** | Qualification verdict | 20 `scripts/research` (`qualify_*`), `research.cli` | - | - |
| `src/research/controls/*`, `src/research/qualify_matrix.py` | **Authority** (controls, scope loop) | Control arms | 15 + 11 scripts | yes | no |
| `src/research/{regime_conditioning, selection_effect, conditional_entropy_grid, structural_asymmetry, candle_state/info_robustness, candle_state/m5_incremental, k23_table/table, oracle/scan, evidence/context_attribution}` | **Unknown->Shadow**: each defines its own permutation variant (label, stratified, block, within-coarse). The null models differ legitimately, but none imports `qualification` | p-values | own drivers | no | partial |
| BH shadows: `evidence/context_attribution.py:benjamini_hochberg` (0.30 similar to the authority), `scripts/research/high_acceptance_activity_conditioning.py:benjamini_hochberg` (0.13), `h_rr_threshold_001.py:_bh`, `ic003b_derive_information.py:_bh`, `mc_cpr_l0_residual_harness.py:_bh_fdr`, `run_h_msip_001.py:_bh`, `k23_table/table.py:bh_pass` | **Shadow** | FDR decisions | own reports | no | yes |
| `scripts/research/edge_attribution_study.py`, `accepted_trade_attribution.py`, `analysis/p4_execution_intent_attribution.py`, `analysis/p3a_zone_attribution_diag.py` | **Unknown** (attribution with no shared authority) | Attribution tables | reports | no | n/a |

### R5 Validation

| Producer | Role | Object compared |
|---|---|---|
| `src/research/oracle/reference_walker.py` | **Twin** | multi_tp_walk outcomes [RUNTIME 300/300] |
| `scripts/analysis/{fm021_retest_depth, fm027_displacement_retrace, session, volatility_regime, trend_strength, hour_of_day}_certification.py`, `feature_dag_{rolling,structural}_certification.py`, `b2a_feature_candidate_certification.py` | **Twin** (independent `oracle_*` recomputations of L1 features vs `feature_pipeline`) | L1 feature values |
| `scripts/research/verify_m5_resample_parity.py`, `tests/research/test_resample_corpus_parity.py` | **Twin** | `research.resample` output vs fetched on-disk bars |
| `scripts/research/{crt_parity_sweep, crt_parity_report, crt_parity_classifier}` (F-069), `crt_state_confusion_matrix.py`, `retest_divergence_probe.py`, `trace_sweep_geometry.py` | **Twin** | Engine vs resolver CRT state |
| `tools/tv_forensic/*`, `scripts/research/{tv_engine_odds, tv_structure_comparison, htf_parent_telemetry_extract}` | **Twin** (external reference: TradingView) | Engine vs TV structure |
| `scripts/analysis/{ledger_parity, v3_config_parity, zone_assignment_parity_probe, run_crt_local_math_parity_audit, feature_math_drift_probe}`, `scripts/misc/{run_parity, trade_replay_validator}`, `mt5_analytics/core/verify.py:reconcile` | **Twin** | Various |
| `src/research/episode_agreement.py` (+ `episode_propositions.py`) | **Authority** (typed Agreement object O14) | Cross-family episode agreement |
| `scripts/research/validate_oracle_harness.py` | **Twin** (harness gate) | Oracle join integrity |

No single validation authority or output schema exists. Each twin emits its own JSON or markdown [STATIC].

### R6 Decision Replay

| Producer | Role | Notes |
|---|---|---|
| `src/research/model_runners/{runner, substrate, envelope, require_config, schema_resolver}` + 15 adapters | **Authority** (Reuse of production engines) | `substrate.load_ohlcv_csv` is its own `pd.read_csv` loader, independent of `CandleLoader` [STATIC] |
| `scripts/research/{live_path_replay, execution_planner_replay, model_shadow_protocol, run_model_offline}`, `*_shadow_*` scripts | **Reuse** | Import `backtest_v2`, `execution_planner`, engines directly |

---

## 3. Duplication Hotspots (ranked by number of independent implementations)

"Independent" means the function computes the object itself instead of importing an existing implementation. Twins are counted separately. Counts are STATIC unless noted.

| Rank | Object (layer) | Independent impls | Authority(ies) | Notes / citations |
|---|---|---|---|---|
| 1 | **OHLC CSV loading** (L0) | **~36 of 57** named loaders use none of `CandleLoader` / `ohlcv_schema` / `xauusd_phase1_candidate` guard / `mc_kit.bars` | `runtime/backtest_v2.py:CandleLoader` (12 of 57 reuse it), `data_ingestion/ohlcv_schema.py` (4), phase-1 guard (6), `research/mc_kit/bars.py:load_bars` (3), `research/probes/corpus.py:load_corpus` | e.g. `src/research/{ic002_entry_evolution/build_trajectories.py:_load_ohlcv_df, model_runners/substrate.py:load_ohlcv_csv, secondlow_v1/detector.py:load_ohlcv, sujan_manipulation/driver.py:load_bars, zone_mapping/gaussian_family_shadow_eval.py:_load_candles}`, `scripts/analysis/{purge_delay_scan, purge_slice, run_msip_shadow, pit_swing_blast_radius, run_crt_local_math_parity_audit}`, `scripts/research/{zone_x_o4_gap_study, smc_visual_verification, validate_crt_state_resolver, crt_range_rebuild_probe, l003h_..., rr_l3_label_generation}`, `tools/btcusdt_crt_v3_replay.py:load_csv`, `mt5_analytics/evaluate_bar_features_outcome.py:load_bars`. `read_csv(` appears in 125 files. A few of the 36 load non-OHLC files (+/-5 uncertainty). F-039: only `backtest_v2` runs the `validate_dataset` pre-flight |
| 2 | **ATR / true range** (L1) | **>=17** named (+1 verbatim copy), plus inline TR in 26 files | Execution: `features/feature_pipeline.py` (`atr_14_raw` = SMA of TR, l.614). Engine: `config_layer/crt_engine_v2.py:compute_atr` (SMA). Research: `research/indicators.py:atr` (SMA; reused by `process_characterization`, `adapters/structural_event_source`, `sujan_crt.driver`, `visual_crt.controls`, `phase_e_structural_asymmetry`) | Independent: `interpreters/regime_observer.py:_trailing_atr`, `research/candle_state/transition_target.py:atr_per_bar`, `research/secondlow_v1/detector.py:compute_true_range_atr` (rolling, min_periods=p//2), `data_ingestion/corpus_gate.py:_median_true_range` (median), `scripts/analysis/p3b_...:compute_atr` (min_periods=1), `scripts/analysis/purge_delay_scan.py:_true_range`, `scripts/backtest/manual_backtest.py:atr`, `scripts/research/high_acceptance_scan.py:add_local_atr`, `high_acceptance_structural_scan.py:add_local_atr`, `high_acceptance_group_ablation.py:local_atr` (**1.00 identical** to `high_acceptance_normalization_control.py:local_atr`), `high_acceptance_regime_stability.py:local_atr`, `smc_visual_verification.py:compute_atr_absolute`, `zone_x_o4_gap_study.py:wilder_atr` (**Wilder**, different smoothing), `tools/btcusdt_crt_v3_replay.py:_atr_proxy` (5-bar range mean). Twin: `volatility_regime_certification.py:oracle_true_range` |
| 3 | **TP/SL hit + outcome walk** (L9) | **16** (+3 twins) | Research: `measurement/forward_walk.py` (SL-first). Two-target: `oracle/multi_tp_walk.py`. Execution: `crt_engine_v2._intrabar_trigger_price` (SL-first), `backtest_v2._resolve_exit` | Shadows: `analytics/sl_tp_comparator.py:simulate_exit` (**TP2-first**), `scripts/analysis/p3b_...:simulate_exit`, `scripts/analysis/xauusd_excel_feature_state_trace.py:walk_plan_outcome`, `scripts/research/opportunity_scanner.py:_simulate`, `replay/timing_reconstructor.py:simulate_with_timing`, `l003h_...:fixed_walk_events`, `l003h_...:trailing_walk_events`, `zone_x_o4_gap_study.py:first_passage_stop_events`, `scripts/backtest/manual_backtest.py:run`, `erp_synth_4h_trace.py:intended_spec`, `governance/strategy_backtest.py`. Twins: `oracle/reference_walker.py`, `scripts/misc/trade_replay_validator.py`, `oracle/exit_analysis.py` (excursions). Same-bar semantics differ (SL-first vs TP2-first vs trail-specific) |
| 4 | **Sweep detection** (L3) | **~14** (+2 twins) | Engine `crt_engine_v2.detect_sweep` / `RangeDetector`; resolver `_detect_htf_range_sweep`; parent `parent_crt._detect_parent_sweep`; L1 feature `feature_pipeline` liquidity-sweep | Independent: `research/sujan_crt/geometry.py:detect_parent_sweep`, `research/visual_crt/geometry.py:detect_pool_sweep` (re-expressed), `research/weekly_sweep/weekly_range.py:detect_weekly_sweep`, `scripts/research/crt_range_rebuild_probe.py:_detect_sweep`, `trace_geometry.py:_sweep`, `live_path_replay.py:_disp_sweep/_disp_sweep_full`, `run_h_g001_001_sweep_veto.py:_liquidity_sweep_series`, `tools/btcusdt_crt_v3_replay.py:_recent_sweep`, `config_layer/crt_sweep_taxonomy.py:classify_sweep`. Twins: `fm021_...:oracle_recent_sweep_online`, `feature_dag_structural_certification.py:_double_sweep` |
| 5 | **MFE/MAE** (L9) | **~13** | `forward_walk` (Outcome.mfe/mae, `horizon_excursion`); `backtest_v2.TradePathStats` | `identity/certify.py:_update_path`, `research/structural_asymmetry.py:measure_path`, `research/clean_labels/builder.py:_bars_to_mfe` + copy `scripts/research/gate0_tn_env_feasibility.py:_bars_to_mfe` (0.88), `research/episodes/events.py:_detect_new_mfe/_mae`, `scripts/analysis/phase1_shadow_create_economic_census.py:_mfe_mae`, `high_acceptance_scan.py:compute_horizon`, `run_xau_metals_protocol_v1.py:build_outcomes`, `xauusd_gaussian_m4_qualify.py:build_outcomes_for_arm`, `jse003_...:main`, `_m8_cert_probe.py`, `multi_tp_walk`/`reference_walker` |
| 6 | **Resampling / HTF bucketing** (L0) | **~11** | Research `research/resample.py:resample`; execution `features/calendar_periods.py` (documented duplicate of `research.resample._RULE_HOURS`) and `backtest_v2.HTFBuilder` (count-based id) | `features/crt_state_resolver.py:build_htf_id_timeline` ("byte-equivalent" to HTFBuilder), `scripts/research/trace_sweep_geometry.py:build_htf_ids` (third copy, 0.18 textual similarity), `scripts/data/build_m15_unified.py:resample_m15`, `scripts/data/prepare_data.py:resample_m15`, `scripts/data/convert_binance_m1_to_m15.py`, `scripts/misc/resample_m1_to_m15.py`, `scripts/research/high_acceptance_scan.py` (`.resample`), `scripts/analysis/purge_delay_scan.py` (`.resample`). `features/parent_candle.py` builds calendar parents via `calendar_periods` (reuse) |
| 7 | **Permutation tests / BH-FDR** (R4) | **10 permutation, 8 BH** (+4 bootstrap, 3 Wilson) | `research/qualification.py` | See the R4 table. `measurement/bootstrap.py:bootstrap_ci` exists, yet `zone_label_audit._bootstrap_ci`, `oracle/scan.block_bootstrap_mean_ci` and `rc003_distinct_object.block_bootstrap_prop_diff` reimplement bootstrap |
| 8 | **Session calculation** (L0) | **~7** (+1 twin) | `features/session_classifier.py` (+ `feature_pipeline.compute_canonical_session`); `features/broker_clock.py:exchange_sessions_at` (reused by `backtest_v2._session`) | `research/conditional_entropy_grid.py:hour_to_session`, `research/path/ambiguity_census.py:_session_of` (Asia 0-8), `scripts/analysis/bnbusdt_trade_anatomy.py:_session_from_hour` (Asia <7), `scripts/analysis/session_cost_audit.py:_session_from_hour` (inclusive end), `scripts/analysis/purge_delay_scan.py:_session` (Asia <7, London 7-12), `scripts/research/momentum_continuation_bnbusdt.py:get_session` (0-8/8-16/16-24), `scripts/analysis/crt_predicate_failure_census_6m.py:session_label` (UNKNOWN body). Window definitions disagree. Twin: `session_certification.py:oracle_session` |
| 9 | **Profit factor / win rate** (L9 aggregate) | **7 / 7** | `research/measurement/metrics.py:EdgeAggregator`; `analytics/metrics_oracle.py` | PF: `research/cross_sectional._profit_factor`, `probes/scoreboard.profit_factor`, `visual_crt/measure._profit_factor`, `scripts/analysis/consensus_sweep._profit_factor`, `phase1_resolver_replay_evidence._profit_factor`, `backtest_v2`. Win rate: `core/backtest_port`, `governance/multi_strategy_validator`, `llm_research/forward_tester`, `research/cross_sectional`, `candle_state/reporting`, `backtest_v2` |
| 10 | **Retest** (L3) | ~4 (+3 twins) | Engine `try_expansion_to_retest`; L1 `derived_math.retest_depth` | `research/visual_crt/retest.py:detect_pool_retest` (mirrors the engine, declared substitution), `run_xau_metals_protocol_v1.py:stream_retest_candidates`, `retest_divergence_probe.py:_engine_retest_raw_indices`, `crt_state_transition_audit_4m.py:_chain_for_retest`. Twins: `fm021_...:oracle_retest_flag/oracle_canonical_retest_depth`, `feature_dag_structural_certification.py:_candles_since_retest` |
| 11 | **EMA / RSI** (L1) | EMA ~4 (+2 twins); RSI 1 shadow (+3 twins) | `feature_pipeline` (`ewm(adjust=False)`, SMA-RSI l.595) | EMA: `scripts/research/gaussian_rr_scatter.py:compute_ema`, `momentum_continuation_bnbusdt.py:rolling_ema`, `_m8_cert_probe.py:recursive_ema`, engine `EngineState.update_emas`. RSI shadow: `momentum_continuation_bnbusdt.py` (l.185). Twins: `feature_38_lineage_census.py`, `feature_dag_rolling_certification.py`, `scripts/governance/feature_certification_state.py` |
| 12 | **Displacement** (L3) | ~4 (+1 twin) | Engine `try_sweep_to_displacement`; L1 `derived_math.displacement_atr_ratio/retrace` | `research/sujan_crt/geometry.py:detect_displacement`, `research/visual_crt/geometry.py:detect_directional_displacement`, `live_path_replay.py:_disp_sweep`. `zone_mapping/*displacement*` derive starts from the CRT state column (consumers, not reimplementations). Twin: `fm027_...:oracle_displacement_retrace` |
| 13 | **Body ratio** (L1) | 3 named + inline `body/range` in ~26 files (many are certification or probe comparisons) | `features/candle_math.py:body_ratio` | `config_layer/crt_engine_v2.py:body_ratio` (0.15 similar), `scripts/backtest/manual_backtest.py:body_ratio`, `runtime/live_engine_hook.py` (inline x4), `features/crt_feature_builder.py` (inline) |
| 14 | **CRT state construction** (L3) | 2 authorities + ~5 declared-independent families + 3 reconstruction twins | engine `StateMachine`; `CRTStateResolver` | See the R2 table. F-069: non-equivalent by construction |

---

## 4. Simplification Opportunities (observation only)

| Family | Producers mergeable? | Output formats mergeable? | Workflows could reuse one authority? | Duplicated business logic eliminable? |
|---|---|---|---|---|
| R1 | Partly. `opportunity_scanner` and `gate0_tn_env_feasibility` recompute what `forward_walk` + `clean_labels.builder` already produce | Research scope writes markdown (304 files), JSONL (157), CSV (40), JSON (33+), parquet (16) and Excel (5); there is no common dataset envelope beyond `research.provenance` (128 files) and `utils.run_manifest` (21) | L0 loading could route through one loader: 36 of 57 loaders bypass all shared ones | Yes for the gate0 label copy and the opportunity walk |
| R2 | No at the family level: engine vs resolver non-equivalence is a documented finding (F-069), and the Sujan, visual, weekly and mother-range objects are declared distinct (F-077) | Every state producer emits its own timeline schema | HTF-id construction exists 3 times (`HTFBuilder`, `build_htf_id_timeline`, `trace_sweep_geometry.build_htf_ids`) | HTF-id copies and `tools/btcusdt_crt_v3_replay` sweep/ATR |
| R3 | Yes for the 11 shadow walks. A single-target authority (`forward_walk`) and a two-target authority (`multi_tp_walk`) already exist and are reused by 35+ files | `Outcome` vs `OracleOutcome` vs `TradeRecord` vs ad-hoc exit dicts: 4+ schemas | Yes. `mc_kit.trade.walk_horizon` already shows the reuse pattern | Yes, and it matters: `sl_tp_comparator` (TP2-first) conflicts with the engine's SL-first tie-break |
| R4 | Yes for BH (8->1) and plain permutation. Block, stratified and within-coarse nulls are legitimately different variants, but they could share one module | Verdict objects differ per study | `qualification` + `qualify_matrix` is already the reuse path for 20 drivers | Yes for BH, bootstrap and Wilson |
| R5 | No. Twins are intentionally independent | Yes: every twin emits bespoke JSON/MD, with no common parity-report schema | Could share one comparison harness while keeping the twin implementations independent | No for twins. `session_certification`, `volatility_regime_certification` and the other certifications are twins by design |
| R6 | Already consolidated | Already single envelope | Already reuses production engines | Only `substrate.load_ohlcv_csv` duplicates L0 loading |

Cross-cutting observations:
- Research ATR (`research.indicators.atr`, SMA over the last `period+1` bars) and execution ATR (`feature_pipeline` rolling mean) are both SMA of true range. Whether they agree numerically bar-for-bar is UNKNOWN (not executed).
- `zone_x_o4_gap_study` uses Wilder smoothing and `secondlow_v1` uses `min_periods=p//2`, so they measure a different object while carrying the same name.
- Session windows disagree across the 7 shadows (Asia ends at 07, 08 or inclusive 07), so session-conditioned results from different scripts are not directly comparable [STATIC].

---

## 5. Open Questions to answer before L0 SYSTEM_FLOW analysis

1. **Canonical L0 loader for research.** Which is the research authority: `runtime.backtest_v2.CandleLoader` (execution), `research.mc_kit.bars.load_bars`, `research.probes.corpus.load_corpus`, or `model_runners.substrate.load_ohlcv_csv`? F-039 says only `backtest_v2` runs the `validate_dataset` pre-flight [DOC+STATIC].
2. **Canonical corpus identity.** The `xauusd_phase1_candidate` guard (`resolve_xauusd_m15_csv`, `guard_xauusd_csv_path`) is used by only 6 of 57 loaders. Which on-disk files are the governed L0 inputs, and were any produced by the 4 `scripts/data` resamplers rather than fetched? [UNKNOWN]
3. **Clock and timestamp basis.** `features.broker_clock.mt5_server_to_utc` exists, but research session shadows bucket raw `ts.hour`. Which basis do research CSVs carry (server time vs UTC)? `configs/data_provenance/ohlcv_clock_registry.json` is modified in the working tree. What state is authoritative? [UNKNOWN]
4. **HTF authority.** Is L0 HTF construction the count-based `HTFBuilder` id (F-075 calls it "an HTF clock, not an HTF candle") or calendar-true `calendar_periods` / `research.resample`? Which one do L3 consumers actually receive in each path? [DOC+STATIC]
5. **Layering contract.** Is the one-way rule "research may import execution, features must not import research" (stated in the `features/calendar_periods.py` docstring) a declared system contract? If it is, execution-side duplicates are intentional and should be excluded from duplication counts [DOC].
6. **L1 ATR identity.** Do `research.indicators.atr` and `feature_pipeline.atr_14_raw` produce identical values at the same bar, given the window alignment differences? Which is L1 authority for research outputs? [UNKNOWN; would need a read-only runtime comparison]
7. **L9 tie-break authority.** Is `analytics.sl_tp_comparator` (TP2-first, consumed by `scripts/research/execution_planner_replay.py`) meant to match the engine? Its docstring claims to, but the code disagrees with `crt_engine_v2._intrabar_trigger_price` [STATIC].
8. **Canonical L9 outcome object.** `Outcome` (ATR-multiple Signal), `OracleOutcome` (absolute levels, two targets) and `TradeRecord` (execution) all exist. Which is the L9 canonical object? [STATIC]
9. **Invisible edges.** Script-to-script imports via `sys.path` manipulation (e.g. `gate0_tn_env_feasibility` -> `bnbusdt_trade_anatomy`, `tv_engine_odds` -> `engine_data`) do not resolve as package imports. How many exist? They would lower the 232-singleton count [STATIC, partial].
10. **Stale graph artifacts.** `pyan_call_flow.dot` (2026-06-06) predates HEAD by about 3.5 months, while `data/script_registry.jsonl` is dated 2026-09-25. Should L0 analysis regenerate call graphs or rely on AST-only evidence? [STATIC]
11. **Subsystem boundary.** Is `mt5_analytics/` (own providers, `_bars`, schemas, verify) inside the L0-L9 flow or a separate system? It imports `forward_walk` only through `mfe_mae_engine` [STATIC].
12. **Dirty working tree.** 482 uncommitted entries, including `configs/formulas/market_crt_states.yaml`, `configs/production/v2_htfcrt_2026_08.json` and `docs/governance/*`. Should L0 analysis be pinned to HEAD `09ffcb1` or to the working tree? [STATIC]
