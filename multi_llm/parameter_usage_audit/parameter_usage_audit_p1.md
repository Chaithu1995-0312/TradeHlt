# Parameter Usage Audit â€” P1 (read sites)

> Generated: 2026-09-19T16:35:08.484644+00:00
> **Measurement only.** No parameter/threshold/behavior changes. P3 replay not run yet.

## Summary

- Python files scanned: **1113**
- Parameters inventoried: **51**
- By P1 status:
  - `dead_candidate`: 5
  - `duplicated_fallback_mismatch`: 18
  - `read`: 25
  - `unreferenced_hint`: 3

## YAML sources
- `configs/formulas/market_crt_states.yaml`
- `configs/formulas/market_ontology.yaml`
- `configs/formulas/crt_state_identity.yaml`
- `configs/formulas/crt_resolver_links.yaml`

## Drift class notes (pending P3)
- **Shadowed** (binds but upstream limiter preempts) â€” needs P3; not asserted in P1.
- **Duplicated** â€” flagged when YAML declared value â‰  `.get(..., fallback)`.
- **Dead candidate** â€” no direct_read/get_with_fallback site found in src/scripts/tools.

## Parameters

### `allowed_sessions`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `['["asia", "london", "new_york"]', '[]']`
- Read sites (107; direct=12):
  - `scripts/analysis/build_crt_input_authority_matrix.py:308` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:11` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:12` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:33` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:87` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:103` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:104` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:308` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:309` (direct_read)
  - `scripts/analysis/crt_threshold_authority_census.py:21` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:22` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:68` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:69` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:71` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:74` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:126` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:127` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:173` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:3` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:14` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:18` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:90` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:110` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:113` (mention)
  - `scripts/analysis/p3b_session_relax_diag.py:328` (mention)
  - â€¦ +82 more

### `atr_min_displacement`
- P1 status: **read**
- Declared values: `['1.2']`
- Fallback values: `['1.2']`
- Read sites (41; direct=1):
  - `scripts/analysis/build_crt_input_authority_matrix.py:164` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:297` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:83` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:97` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:98` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:46` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:47` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:286` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:176` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:177` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:178` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:314` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:332` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:505` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:622` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:164` (mention)
  - `scripts/analysis/detection_sweep.py:11` (mention)
  - `scripts/analysis/detection_sweep.py:60` (mention)
  - `scripts/analysis/detection_sweep.py:143` (mention)
  - `scripts/analysis/gate2b_adjudication.py:100` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:113` (mention)
  - `scripts/research/crt_parity_classifier.py:81` (mention)
  - `scripts/research/crt_parity_sweep.py:93` (mention)
  - `scripts/training/train_gaussian_xauusd.py:625` (mention)
  - `src/config_layer/crt_config_provenance.py:74` (mention)
  - â€¦ +16 more

### `atr_multiplier_min`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['1.0']`
- Fallback values: `['1.5']`
- **Mismatch:** `[{'declared': '1.0', 'fallback': '1.5'}]`
- Read sites (44; direct=1):
  - `scripts/analysis/build_crt_input_authority_matrix.py:134` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:298` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:107` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:108` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:56` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:57` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:288` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:195` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:196` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:197` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:315` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:333` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:504` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:624` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:165` (mention)
  - `scripts/analysis/ledger_parity.py:15` (mention)
  - `scripts/backtest/backtest_debug_harness.py:31` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:115` (mention)
  - `scripts/groq_bridge/prepare_retrospective.py:474` (mention)
  - `scripts/research/crt_parity_classifier.py:80` (mention)
  - `scripts/research/crt_parity_sweep.py:95` (mention)
  - `scripts/training/auto_tuner.py:117` (mention)
  - `scripts/training/auto_tuner_gemini_gate.py:83` (mention)
  - `scripts/training/auto_tuner_multi.py:102` (mention)
  - `src/config_layer/crt_config_provenance.py:70` (mention)
  - â€¦ +19 more

### `bias_gate_mode`
- P1 status: **unreferenced_hint**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (3; direct=0):
  - `src/runtime/parent_crt_feed.py:22` (mention)
  - `src/runtime/parent_crt_feed.py:157` (mention)
  - `src/runtime/parent_crt_feed.py:160` (mention)

### `body_ratio_min`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['0.65']`
- Fallback values: `['0.70']`
- **Mismatch:** `[{'declared': '0.65', 'fallback': '0.70'}]`
- Read sites (69; direct=2):
  - `scripts/analysis/build_crt_input_authority_matrix.py:119` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:296` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:82` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:87` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:102` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:103` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:51` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:52` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:287` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:188` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:189` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:190` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:330` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:337` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:503` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:623` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:163` (mention)
  - `scripts/analysis/ledger_parity.py:15` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:58` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:106` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:213` (direct_read)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:114` (mention)
  - `scripts/governance/build_msip_shadow_design_contract_v1.py:300` (mention)
  - `scripts/governance/three_authority_surplus_census.py:389` (mention)
  - `scripts/governance/three_authority_surplus_census.py:456` (mention)
  - â€¦ +44 more

### `breakout_disp_threshold`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (20; direct=3):
  - `scripts/analysis/crt_episode_number_trace.py:642` (mention)
  - `scripts/analysis/trade_intent_ownership_shadow.py:50` (mention)
  - `scripts/analysis/trade_intent_ownership_shadow.py:143` (mention)
  - `scripts/analysis/trade_intent_ownership_shadow.py:146` (mention)
  - `scripts/analysis/trade_intent_ownership_shadow.py:308` (mention)
  - `scripts/analysis/trade_intent_ownership_shadow.py:355` (mention)
  - `scripts/research/build_bar_matrix.py:138` (direct_read)
  - `scripts/research/build_bar_matrix.py:322` (mention)
  - `scripts/research/promotion_dryrun.py:25` (mention)
  - `scripts/research/promotion_dryrun.py:105` (mention)
  - `src/config_layer/crt_engine_v2.py:2321` (mention)
  - `src/config_layer/crt_engine_v2.py:2324` (mention)
  - `src/config_layer/crt_engine_v2.py:2355` (mention)
  - `src/config_layer/crt_engine_v2.py:2416` (mention)
  - `src/config_layer/execution_planner.py:117` (mention)
  - `src/config_layer/execution_planner.py:394` (direct_read)
  - `src/config_layer/production_config.py:197` (mention)
  - `src/config_layer/production_config.py:212` (mention)
  - `src/config_layer/production_config.py:213` (direct_read)
  - `src/config_layer/state_identity.py:202` (mention)

### `consumed`
- P1 status: **dead_candidate**
- Declared values: `['false', 'true']`
- Fallback values: `â€”`
- Read sites (64; direct=0):
  - `scripts/analysis/config_reachability.py:19` (mention)
  - `scripts/analysis/config_reachability.py:35` (mention)
  - `scripts/analysis/config_reachability.py:80` (mention)
  - `scripts/analysis/config_reachability.py:122` (mention)
  - `scripts/analysis/config_reachability.py:200` (mention)
  - `scripts/analysis/config_reachability.py:298` (mention)
  - `scripts/analysis/config_reachability.py:309` (mention)
  - `scripts/analysis/config_reachability.py:317` (mention)
  - `scripts/analysis/config_reachability.py:405` (mention)
  - `scripts/analysis/config_reachability.py:406` (mention)
  - `scripts/analysis/config_reachability.py:408` (mention)
  - `scripts/analysis/config_reachability.py:442` (mention)
  - `scripts/analysis/config_reachability.py:443` (mention)
  - `scripts/analysis/config_reachability.py:453` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:10` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:234` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:873` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:117` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:90` (mention)
  - `scripts/analysis/feature_math_decision_flip_probe.py:10` (mention)
  - `scripts/analysis/feature_math_lint.py:149` (mention)
  - `scripts/analysis/feature_math_lint.py:428` (mention)
  - `scripts/analysis/gate2b_adjudication.py:37` (mention)
  - `scripts/analysis/implementation_model_validation_xauusd.py:1214` (mention)
  - `scripts/analysis/implementation_model_validation_xauusd.py:1786` (mention)
  - â€¦ +39 more

### `continuous_disp_to_expansion`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['false']`
- Fallback values: `['False']`
- **Mismatch:** `[{'declared': 'false', 'fallback': 'False'}]`
- Read sites (10; direct=1):
  - `scripts/analysis/p001_excursion_probe.py:364` (mention)
  - `scripts/analysis/phase1_resolver_replay_evidence.py:37` (mention)
  - `scripts/analysis/phase1_resolver_replay_sample_acquisition.py:40` (mention)
  - `scripts/research/crt_parity_report.py:48` (mention)
  - `scripts/research/crt_parity_sweep.py:26` (mention)
  - `scripts/research/crt_parity_sweep.py:87` (mention)
  - `scripts/research/retest_divergence_probe.py:31` (mention)
  - `scripts/research/retest_divergence_probe.py:317` (mention)
  - `src/features/crt_state_resolver.py:1489` (mention)
  - `src/features/crt_state_resolver.py:1500` (get_with_fallback)

### `double_sweep_window`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (17; direct=1):
  - `scripts/analysis/feature_math_lint.py:99` (mention)
  - `scripts/analysis/semantic_layer_validation.py:456` (mention)
  - `src/features/causal_structure.py:28` (mention)
  - `src/features/causal_structure.py:30` (mention)
  - `src/features/causal_structure.py:80` (mention)
  - `src/features/causal_structure.py:87` (mention)
  - `src/features/causal_structure.py:91` (mention)
  - `src/features/causal_structure.py:156` (mention)
  - `src/features/causal_structure.py:209` (mention)
  - `src/features/causal_structure.py:213` (mention)
  - `src/features/causal_structure.py:216` (mention)
  - `src/features/causal_structure.py:223` (mention)
  - `src/features/causal_structure.py:228` (mention)
  - `src/features/feature_pipeline.py:90` (mention)
  - `src/features/feature_pipeline.py:289` (mention)
  - `src/features/feature_pipeline.py:1038` (mention)
  - `src/features/feature_pipeline.py:1043` (direct_read)

### `expansion_atr_is_relative`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['true']`
- Fallback values: `['True']`
- **Mismatch:** `[{'declared': 'true', 'fallback': 'True'}]`
- Read sites (2; direct=1):
  - `src/features/crt_state_resolver.py:1897` (mention)
  - `src/features/crt_state_resolver.py:1904` (get_with_fallback)

### `expansion_atr_min_distance`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['0.30']`
- Fallback values: `['0.20']`
- **Mismatch:** `[{'declared': '0.30', 'fallback': '0.20'}]`
- Read sites (45; direct=2):
  - `scripts/analysis/build_crt_input_authority_matrix.py:300` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:117` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:118` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:66` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:67` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:290` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:216` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:217` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:218` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:361` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:363` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:507` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:626` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:166` (mention)
  - `scripts/analysis/detection_sweep.py:10` (mention)
  - `scripts/analysis/detection_sweep.py:59` (mention)
  - `scripts/analysis/detection_sweep.py:142` (mention)
  - `scripts/analysis/ledger_parity.py:16` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:131` (direct_read)
  - `scripts/groq_bridge/prepare_retrospective.py:473` (mention)
  - `scripts/research/crt_parity_classifier.py:84` (mention)
  - `scripts/research/crt_parity_sweep.py:90` (mention)
  - `scripts/training/auto_tuner.py:118` (mention)
  - `scripts/training/auto_tuner_gemini_gate.py:84` (mention)
  - `scripts/training/auto_tuner_multi.py:103` (mention)
  - â€¦ +20 more

### `gap_reset_enabled`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['true']`
- Fallback values: `['True']`
- **Mismatch:** `[{'declared': 'true', 'fallback': 'True'}]`
- Read sites (11; direct=3):
  - `scripts/backtest/backtest_debug_harness.py:49` (mention)
  - `scripts/training/auto_tuner_multi.py:334` (mention)
  - `src/features/crt_state_resolver.py:911` (get_with_fallback)
  - `src/features/crt_state_resolver.py:953` (direct_read)
  - `src/governance/portfolio_validation.py:344` (mention)
  - `src/runtime/backtest_v2.py:209` (mention)
  - `src/runtime/backtest_v2.py:282` (mention)
  - `src/runtime/backtest_v2.py:317` (direct_read)
  - `src/runtime/backtest_v2.py:2650` (mention)
  - `src/runtime/backtest_v2.py:2843` (mention)
  - `src/runtime/backtest_v2.py:4134` (mention)

### `gap_reset_minutes`
- P1 status: **read**
- Declared values: `['120']`
- Fallback values: `['120']`
- Read sites (11; direct=3):
  - `scripts/backtest/backtest_debug_harness.py:50` (mention)
  - `scripts/training/auto_tuner_multi.py:335` (mention)
  - `src/features/crt_state_resolver.py:41` (mention)
  - `src/features/crt_state_resolver.py:912` (get_with_fallback)
  - `src/features/crt_state_resolver.py:982` (mention)
  - `src/features/crt_state_resolver.py:991` (direct_read)
  - `src/governance/portfolio_validation.py:345` (mention)
  - `src/runtime/backtest_v2.py:210` (mention)
  - `src/runtime/backtest_v2.py:282` (mention)
  - `src/runtime/backtest_v2.py:318` (direct_read)
  - `src/runtime/backtest_v2.py:2650` (mention)

### `gate_approval_threshold`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/config_layer/execution_planner.py:97` (mention)
  - `src/config_layer/execution_planner.py:123` (mention)
  - `src/core/gate_intelligence.py:112` (mention)
  - `src/core/gate_intelligence.py:120` (mention)
  - `src/core/gate_intelligence.py:131` (direct_read)

### `gate_weight_intent`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/config_layer/execution_planner.py:93` (mention)
  - `src/config_layer/execution_planner.py:119` (mention)
  - `src/core/gate_intelligence.py:108` (mention)
  - `src/core/gate_intelligence.py:116` (mention)
  - `src/core/gate_intelligence.py:127` (direct_read)

### `gate_weight_liquidity`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/config_layer/execution_planner.py:95` (mention)
  - `src/config_layer/execution_planner.py:121` (mention)
  - `src/core/gate_intelligence.py:110` (mention)
  - `src/core/gate_intelligence.py:118` (mention)
  - `src/core/gate_intelligence.py:129` (direct_read)

### `gate_weight_structure`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/config_layer/execution_planner.py:96` (mention)
  - `src/config_layer/execution_planner.py:122` (mention)
  - `src/core/gate_intelligence.py:111` (mention)
  - `src/core/gate_intelligence.py:119` (mention)
  - `src/core/gate_intelligence.py:130` (direct_read)

### `gate_weight_vol`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/config_layer/execution_planner.py:94` (mention)
  - `src/config_layer/execution_planner.py:120` (mention)
  - `src/core/gate_intelligence.py:109` (mention)
  - `src/core/gate_intelligence.py:117` (mention)
  - `src/core/gate_intelligence.py:128` (direct_read)

### `htf_candles_per_range`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['4']`
- Fallback values: `['4', 'htf_candles']`
- **Mismatch:** `[{'declared': '4', 'fallback': 'htf_candles'}]`
- Read sites (78; direct=21):
  - `scripts/analysis/build_crt_input_authority_matrix.py:179` (mention)
  - `scripts/analysis/crt_fail_reason_diagnostic.py:46` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:94` (mention)
  - `scripts/analysis/implementation_model_validation_xauusd.py:375` (direct_read)
  - `scripts/analysis/implementation_model_validation_xauusd.py:380` (direct_read)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:444` (mention)
  - `scripts/analysis/xauusd_crt_baseline_trace.py:142` (mention)
  - `scripts/analysis/xauusd_crt_transition_trace.py:298` (mention)
  - `scripts/analysis/xauusd_crt_transition_trace.py:402` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:987` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1059` (direct_read)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1169` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1205` (mention)
  - `scripts/backtest/backtest_debug_harness.py:40` (mention)
  - `scripts/research/build_bar_matrix.py:137` (direct_read)
  - `scripts/research/build_bar_matrix.py:321` (mention)
  - `scripts/research/crt_range_rebuild_probe.py:275` (get_with_fallback)
  - `scripts/research/crt_resolver_economic_comparison.py:250` (get_with_fallback)
  - `scripts/research/crt_state_confusion_matrix.py:399` (get_with_fallback)
  - `scripts/research/crt_state_confusion_matrix.py:517` (mention)
  - `scripts/research/crt_state_confusion_matrix.py:863` (mention)
  - `scripts/research/crt_state_confusion_matrix.py:1269` (mention)
  - `scripts/research/link001_choch_measurement.py:146` (get_with_fallback)
  - `scripts/research/retest_divergence_probe.py:145` (get_with_fallback)
  - `scripts/research/run_crt_state_on_mt5_xauusd.py:96` (direct_read)
  - â€¦ +53 more

### `htf_protect_execution`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['true']`
- Fallback values: `['True']`
- **Mismatch:** `[{'declared': 'true', 'fallback': 'True'}]`
- Read sites (4; direct=3):
  - `scripts/research/crt_parity_sweep.py:105` (mention)
  - `src/features/crt_state_resolver.py:640` (direct_read)
  - `src/features/crt_state_resolver.py:910` (get_with_fallback)
  - `src/features/crt_state_resolver.py:966` (direct_read)

### `htf_protect_states`
- P1 status: **read**
- Declared values: `['[EXPANSION, RETEST]']`
- Fallback values: `â€”`
- Read sites (5; direct=2):
  - `scripts/research/crt_parity_sweep.py:102` (mention)
  - `src/features/crt_state_resolver.py:639` (direct_read)
  - `src/features/crt_state_resolver.py:907` (mention)
  - `src/features/crt_state_resolver.py:908` (mention)
  - `src/features/crt_state_resolver.py:965` (direct_read)

### `htf_reset_enabled`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['true']`
- Fallback values: `['True']`
- **Mismatch:** `[{'declared': 'true', 'fallback': 'True'}]`
- Read sites (3; direct=3):
  - `src/features/crt_state_resolver.py:905` (get_with_fallback)
  - `src/features/crt_state_resolver.py:960` (direct_read)
  - `src/features/crt_state_resolver.py:1013` (direct_read)

### `initial_capital`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `['0', '100_000.0']`
- Read sites (29; direct=3):
  - `scripts/backtest/backtest_debug_harness.py:42` (mention)
  - `scripts/training/auto_tuner_multi.py:331` (mention)
  - `src/analytics/metrics_oracle.py:20` (mention)
  - `src/analytics/metrics_oracle.py:106` (mention)
  - `src/analytics/metrics_oracle.py:108` (mention)
  - `src/analytics/metrics_oracle.py:183` (mention)
  - `src/analytics/metrics_oracle.py:190` (mention)
  - `src/analytics/metrics_oracle.py:194` (mention)
  - `src/analytics/metrics_oracle.py:195` (mention)
  - `src/governance/portfolio_validation.py:41` (get_with_fallback)
  - `src/governance/portfolio_validation.py:312` (mention)
  - `src/governance/portfolio_validation.py:337` (mention)
  - `src/runtime/backtest_v2.py:204` (mention)
  - `src/runtime/backtest_v2.py:281` (mention)
  - `src/runtime/backtest_v2.py:314` (direct_read)
  - `src/runtime/backtest_v2.py:482` (mention)
  - `src/runtime/backtest_v2.py:483` (mention)
  - `src/runtime/backtest_v2.py:484` (mention)
  - `src/runtime/backtest_v2.py:487` (mention)
  - `src/runtime/backtest_v2.py:488` (mention)
  - `src/runtime/backtest_v2.py:494` (mention)
  - `src/runtime/backtest_v2.py:537` (mention)
  - `src/runtime/backtest_v2.py:541` (mention)
  - `src/runtime/backtest_v2.py:1895` (get_with_fallback)
  - `src/runtime/backtest_v2.py:2639` (mention)
  - â€¦ +4 more

### `kind`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['crtconfig_duplicate', 'crtconfig_duplicate_dead', 'dead_unconsumed', 'name_alias_documented', 'resolver_only']`
- Fallback values: `['"?"', '"UNKNOWN"', "'def'"]`
- **Mismatch:** `[{'declared': 'crtconfig_duplicate', 'fallback': '"?"'}, {'declared': 'crtconfig_duplicate', 'fallback': '"UNKNOWN"'}, {'declared': 'crtconfig_duplicate', 'fallback': "'def'"}, {'declared': 'crtconfig_duplicate_dead', 'fallback': '"?"'}, {'declared': 'crtconfig_duplicate_dead', 'fallback': '"UNKNOWN"'}, {'declared': 'crtconfig_duplicate_dead', 'fallback': "'def'"}, {'declared': 'dead_unconsumed', 'fallback': '"?"'}, {'declared': 'dead_unconsumed', 'fallback': '"UNKNOWN"'}, {'declared': 'dead_unconsumed', 'fallback': "'def'"}, {'declared': 'name_alias_documented', 'fallback': '"?"'}, {'declared': 'name_alias_documented', 'fallback': '"UNKNOWN"'}, {'declared': 'name_alias_documented', 'fallback': "'def'"}, {'declared': 'resolver_only', 'fallback': '"?"'}, {'declared': 'resolver_only', 'fallback': '"UNKNOWN"'}, {'declared': 'resolver_only', 'fallback': "'def'"}]`
- Read sites (935; direct=43):
  - `scripts/_tmp_measure_rag_ranking.py:23` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:30` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:31` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:33` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:55` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:62` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:70` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:120` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:130` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:134` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:148` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:150` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:151` (mention)
  - `scripts/_tmp_measure_rag_ranking.py:154` (mention)
  - `scripts/analysis/crt_funnel_diagnostic.py:132` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:59` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:94` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:490` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:493` (mention)
  - `scripts/analysis/feature_math_lint.py:154` (mention)
  - `scripts/analysis/feature_math_lint.py:490` (mention)
  - `scripts/analysis/feature_math_lint.py:493` (mention)
  - `scripts/analysis/feature_math_lint.py:507` (mention)
  - `scripts/analysis/feature_math_lint.py:515` (mention)
  - `scripts/analysis/feature_math_lint.py:516` (mention)
  - â€¦ +910 more

### `lifecycle`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `["''", "'?'"]`
- Read sites (223; direct=10):
  - `scripts/analysis/crt_funnel_diagnostic.py:170` (mention)
  - `scripts/analysis/crt_funnel_diagnostic.py:484` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:182` (mention)
  - `scripts/analysis/fm027_displacement_retrace_certification.py:536` (mention)
  - `scripts/analysis/generate_script_matrix.py:65` (get_with_fallback)
  - `scripts/analysis/p1_sweep_memory_diag.py:222` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:441` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:404` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:426` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:461` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:466` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:502` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:602` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:603` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:614` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:641` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:644` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:659` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:683` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:698` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:863` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:880` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:882` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:892` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:922` (mention)
  - â€¦ +198 more

### `max_displacement_age_candles`
- P1 status: **dead_candidate**
- Declared values: `['3']`
- Fallback values: `â€”`
- Read sites (2; direct=0):
  - `scripts/research/crt_parity_classifier.py:83` (mention)
  - `scripts/research/crt_parity_sweep.py:92` (mention)

### `max_expansion_age_candles`
- P1 status: **read**
- Declared values: `['495']`
- Fallback values: `['495']`
- Read sites (12; direct=1):
  - `scripts/analysis/build_crt_input_authority_matrix.py:307` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:147` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:150` (mention)
  - `scripts/research/crt_parity_classifier.py:87` (mention)
  - `scripts/research/crt_parity_sweep.py:98` (mention)
  - `scripts/research/e1_retest_depth_max_probe.py:16` (mention)
  - `src/config_layer/crt_engine_v2.py:3196` (mention)
  - `src/config_layer/crt_engine_v2.py:3512` (mention)
  - `src/config_layer/crt_engine_v2.py:3513` (mention)
  - `src/config_layer/crt_engine_v2.py:3519` (mention)
  - `src/config_layer/state_identity.py:280` (mention)
  - `src/features/crt_state_resolver.py:2095` (get_with_fallback)

### `max_expansion_age_hours`
- P1 status: **read**
- Declared values: `['124']`
- Fallback values: `['124']`
- Read sites (6; direct=1):
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:150` (mention)
  - `scripts/research/crt_parity_sweep.py:99` (mention)
  - `src/config_layer/crt_engine_v2.py:3197` (mention)
  - `src/config_layer/state_identity.py:278` (mention)
  - `src/config_layer/state_identity.py:281` (mention)
  - `src/features/crt_state_resolver.py:2096` (get_with_fallback)

### `max_risk_per_trade_pct`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (5; direct=1):
  - `src/core/ultron_risk_gate.py:49` (mention)
  - `src/core/ultron_risk_gate.py:91` (mention)
  - `src/core/ultron_risk_gate.py:293` (direct_read)
  - `src/core/ultron_risk_gate.py:396` (mention)
  - `src/strategies/strategy_package.py:92` (mention)

### `max_sweep_age_candles`
- P1 status: **read**
- Declared values: `['20']`
- Fallback values: `['20']`
- Read sites (40; direct=2):
  - `scripts/analysis/build_crt_input_authority_matrix.py:194` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:299` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:112` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:113` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:61` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:62` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:289` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:182` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:183` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:184` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:506` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:625` (mention)
  - `scripts/backtest/backtest_debug_harness.py:29` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:116` (mention)
  - `scripts/research/crt_parity_classifier.py:82` (mention)
  - `scripts/research/crt_parity_sweep.py:91` (mention)
  - `src/config_layer/config_builder.py:27` (mention)
  - `src/config_layer/crt_engine_v2.py:8` (mention)
  - `src/config_layer/crt_engine_v2.py:1300` (mention)
  - `src/config_layer/crt_engine_v2.py:1308` (mention)
  - `src/config_layer/crt_engine_v2.py:1315` (mention)
  - `src/config_layer/crt_engine_v2.py:1316` (mention)
  - `src/config_layer/crt_engine_v2.py:1317` (mention)
  - `src/config_layer/crt_engine_v2.py:1325` (mention)
  - `src/config_layer/crt_engine_v2.py:1331` (mention)
  - â€¦ +15 more

### `note`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['>', 'See rsi_overbought.']`
- Fallback values: `['""', "''", "'calendar not separable'", "'no usable overlap with the reference'", "'seasonal step not determinable'"]`
- **Mismatch:** `[{'declared': '>', 'fallback': "'calendar not separable'"}, {'declared': '>', 'fallback': "'no usable overlap with the reference'"}, {'declared': '>', 'fallback': "'seasonal step not determinable'"}, {'declared': 'See rsi_overbought.', 'fallback': "'calendar not separable'"}, {'declared': 'See rsi_overbought.', 'fallback': "'no usable overlap with the reference'"}, {'declared': 'See rsi_overbought.', 'fallback': "'seasonal step not determinable'"}]`
- Read sites (749; direct=52):
  - `scripts/analysis/b2a_feature_candidate_certification.py:338` (mention)
  - `scripts/analysis/bnb_ema_gate_ab.py:104` (mention)
  - `scripts/analysis/bnbusdt_trade_anatomy.py:396` (mention)
  - `scripts/analysis/bnbusdt_trade_anatomy.py:422` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:290` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:374` (mention)
  - `scripts/analysis/build_decision_atlas.py:473` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:55` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:69` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:107` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:118` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:141` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:157` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:172` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:186` (mention)
  - `scripts/analysis/config_reachability.py:100` (mention)
  - `scripts/analysis/config_reachability.py:105` (mention)
  - `scripts/analysis/config_reachability.py:268` (mention)
  - `scripts/analysis/config_reachability.py:272` (mention)
  - `scripts/analysis/config_reachability.py:275` (mention)
  - `scripts/analysis/config_reachability.py:276` (mention)
  - `scripts/analysis/config_reachability.py:280` (mention)
  - `scripts/analysis/config_reachability.py:422` (direct_read)
  - `scripts/analysis/config_reachability.py:430` (direct_read)
  - `scripts/analysis/corpus_read_lint.py:141` (mention)
  - â€¦ +724 more

### `pending_displacement_ttl_candles`
- P1 status: **read**
- Declared values: `['4']`
- Fallback values: `['4']`
- Read sites (22; direct=4):
  - `scripts/analysis/phase1_shadow_memory_create_expire_mine.py:252` (mention)
  - `scripts/analysis/phase1_shadow_memory_create_expire_mine.py:324` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:142` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:404` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:409` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:413` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:421` (mention)
  - `scripts/analysis/phase1_shadow_memory_subsystem_probe.py:442` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1004` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1081` (direct_read)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1083` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1202` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1204` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:98` (direct_read)
  - `scripts/research/crt_parity_classifier.py:89` (mention)
  - `scripts/research/crt_parity_sweep.py:114` (mention)
  - `src/config_layer/crt_engine_v2.py:1901` (mention)
  - `src/config_layer/state_identity.py:250` (mention)
  - `src/config_layer/state_identity.py:294` (mention)
  - `src/features/crt_state_resolver.py:916` (mention)
  - `src/features/crt_state_resolver.py:917` (get_with_fallback)
  - `src/features/crt_state_resolver.py:1044` (direct_read)

### `per_trade_investment_inr`
- P1 status: **unreferenced_hint**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (0; direct=0):
  - _(none)_

### `range_atr_period`
- P1 status: **read**
- Declared values: `['14']`
- Fallback values: `['14']`
- Read sites (6; direct=1):
  - `scripts/research/crt_parity_sweep.py:107` (mention)
  - `scripts/research/crt_range_rebuild_probe.py:392` (mention)
  - `scripts/research/crt_range_rebuild_probe.py:505` (mention)
  - `src/features/crt_state_resolver.py:376` (get_with_fallback)
  - `src/features/crt_state_resolver.py:378` (mention)
  - `src/features/crt_state_resolver.py:541` (mention)

### `ref`
- P1 status: **dead_candidate**
- Declared values: `['"backtest.gap_reset_minutes"', '"backtest.htf_candles_per_range"', 'atr_min_displacement', 'atr_multiplier_min', 'atr_period', 'body_ratio_min', 'expansion_atr_min_distance', 'max_expansion_age_candles', 'max_expansion_age_hours', 'max_sweep_age_candles', 'null', 'pending_displacement_ttl_candles', 'retest_atr_depth_fraction', 'retest_depth_max', 'score_threshold', 'soft_conf_max_candles']`
- Fallback values: `â€”`
- Read sites (141; direct=0):
  - `scripts/analysis/bnbusdt_trade_anatomy.py:159` (mention)
  - `scripts/analysis/config_reachability.py:414` (mention)
  - `scripts/analysis/corpus_read_census.py:218` (mention)
  - `scripts/analysis/corpus_read_census.py:219` (mention)
  - `scripts/analysis/corpus_read_census.py:221` (mention)
  - `scripts/analysis/corpus_read_census.py:222` (mention)
  - `scripts/analysis/corpus_read_census.py:229` (mention)
  - `scripts/analysis/corpus_read_census.py:230` (mention)
  - `scripts/analysis/corpus_read_census.py:233` (mention)
  - `scripts/analysis/corpus_read_census.py:235` (mention)
  - `scripts/analysis/corpus_read_census.py:296` (mention)
  - `scripts/analysis/corpus_read_census.py:297` (mention)
  - `scripts/analysis/corpus_read_census.py:300` (mention)
  - `scripts/analysis/corpus_read_census.py:301` (mention)
  - `scripts/analysis/corpus_read_census.py:303` (mention)
  - `scripts/analysis/corpus_read_census.py:305` (mention)
  - `scripts/analysis/corpus_read_census.py:308` (mention)
  - `scripts/analysis/corpus_read_census.py:310` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:641` (mention)
  - `scripts/analysis/feature_dag_structural_certification.py:235` (mention)
  - `scripts/analysis/feature_math_decision_flip_probe.py:169` (mention)
  - `scripts/analysis/feature_math_lint.py:636` (mention)
  - `scripts/analysis/feature_math_lint.py:644` (mention)
  - `scripts/analysis/ohlcv_census.py:600` (mention)
  - `scripts/analysis/p3b_gate_expired_counterfactual_rr.py:14` (mention)
  - â€¦ +116 more

### `refs`
- P1 status: **dead_candidate**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (68; direct=0):
  - `scripts/analysis/build_feature_contract_v1_seed.py:22` (mention)
  - `scripts/analysis/build_feature_contract_v1_seed.py:23` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:553` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:125` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:285` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:296` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:300` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:475` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:477` (mention)
  - `scripts/analysis/feature_dag_structural_certification.py:12` (mention)
  - `scripts/analysis/feature_surface_closure_audit.py:234` (mention)
  - `scripts/analysis/geometry_census.py:10` (mention)
  - `scripts/analysis/pit_swing_blast_radius.py:74` (mention)
  - `scripts/analysis/pit_swing_blast_radius.py:123` (mention)
  - `scripts/analysis/pit_swing_blast_radius.py:141` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:227` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:332` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:344` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:353` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:582` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:594` (mention)
  - `scripts/analysis/src_business_functionality_inventory.py:595` (mention)
  - `scripts/analysis/test_functionality_excel.py:294` (mention)
  - `scripts/analysis/test_functionality_excel.py:303` (mention)
  - `scripts/analysis/test_functionality_excel.py:309` (mention)
  - â€¦ +43 more

### `retest_atr_depth_fraction`
- P1 status: **dead_candidate**
- Declared values: `['0.50']`
- Fallback values: `â€”`
- Read sites (42; direct=0):
  - `scripts/analysis/build_crt_input_authority_matrix.py:269` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:302` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:128` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:77` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:293` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:236` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:239` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:401` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:509` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:629` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:73` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:79` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:115` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:121` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:168` (mention)
  - `scripts/analysis/fm027_displacement_retrace_certification.py:313` (mention)
  - `scripts/analysis/ledger_parity.py:16` (mention)
  - `scripts/analysis/p3b_gate_expired_counterfactual_rr.py:331` (mention)
  - `scripts/analysis/soft_conf_ema_double_update_probe.py:105` (mention)
  - `scripts/governance/behavioral_constant_authority_trace.py:999` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:140` (mention)
  - `scripts/groq_bridge/prepare_retrospective.py:474` (mention)
  - `scripts/research/crt_parity_classifier.py:86` (mention)
  - `scripts/research/crt_parity_sweep.py:111` (mention)
  - `scripts/research/retest_divergence_probe.py:23` (mention)
  - â€¦ +17 more

### `retest_depth_max`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['0.15']`
- Fallback values: `['0.25']`
- **Mismatch:** `[{'declared': '0.15', 'fallback': '0.25'}]`
- Read sites (57; direct=2):
  - `scripts/analysis/build_crt_input_authority_matrix.py:269` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:301` (mention)
  - `scripts/analysis/crt_guard_ablation_6m.py:128` (mention)
  - `scripts/analysis/crt_guard_ablation_run.py:77` (mention)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:292` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:236` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:238` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:400` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:508` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:628` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:73` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:76` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:112` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:167` (mention)
  - `scripts/analysis/fm027_displacement_retrace_certification.py:312` (mention)
  - `scripts/analysis/ledger_parity.py:15` (mention)
  - `scripts/analysis/soft_conf_ema_double_update_probe.py:104` (mention)
  - `scripts/governance/behavioral_constant_authority_trace.py:999` (mention)
  - `scripts/governance/build_crt_architecture_adjudication_v1.py:139` (mention)
  - `scripts/groq_bridge/prepare_retrospective.py:473` (mention)
  - `scripts/maintenance/_compute_hash.py:7` (mention)
  - `scripts/research/crt_parity_classifier.py:85` (mention)
  - `scripts/research/crt_parity_sweep.py:110` (mention)
  - `scripts/research/e1_retest_depth_max_probe.py:6` (mention)
  - `scripts/research/e1_retest_depth_max_probe.py:15` (mention)
  - â€¦ +32 more

### `risk_percent`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `['0.0', '0.5']`
- Read sites (26; direct=8):
  - `scripts/research/live_path_replay.py:25` (mention)
  - `scripts/research/live_path_replay.py:488` (get_with_fallback)
  - `scripts/research/live_path_replay.py:544` (direct_read)
  - `scripts/research/live_path_replay.py:547` (mention)
  - `scripts/research/live_path_replay.py:565` (mention)
  - `src/config_layer/execution_planner.py:87` (mention)
  - `src/config_layer/execution_planner.py:110` (mention)
  - `src/core/regime_governor.py:18` (mention)
  - `src/core/types.py:86` (mention)
  - `src/core/ultron_risk_gate.py:173` (mention)
  - `src/core/ultron_risk_gate.py:292` (get_with_fallback)
  - `src/core/ultron_risk_gate.py:295` (mention)
  - `src/core/ultron_risk_gate.py:451` (mention)
  - `src/core/ultron_risk_gate_wrapper.py:10` (mention)
  - `src/core/ultron_risk_gate_wrapper.py:16` (mention)
  - `src/core/ultron_risk_gate_wrapper.py:91` (mention)
  - `src/core/ultron_risk_gate_wrapper.py:112` (get_with_fallback)
  - `src/core/ultron_risk_gate_wrapper.py:114` (direct_read)
  - `src/research/model_runners/adapters/execution_plan.py:129` (mention)
  - `src/research/model_runners/adapters/execution_plan.py:167` (mention)
  - `src/research/model_runners/adapters/execution_plan.py:180` (mention)
  - `src/research/model_runners/adapters/execution_plan.py:309` (direct_read)
  - `src/runtime/live_engine_hook.py:1089` (direct_read)
  - `src/runtime/live_engine_hook.py:1093` (direct_read)
  - `src/runtime/live_engine_hook.py:1155` (mention)
  - â€¦ +1 more

### `rsi_overbought`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['70']`
- Fallback values: `['70', '70.0', 'thr_defaults["rsi_overbought"]']`
- **Mismatch:** `[{'declared': '70', 'fallback': 'thr_defaults["rsi_overbought"]'}]`
- Read sites (18; direct=9):
  - `scripts/research/crt_range_rebuild_probe.py:272` (get_with_fallback)
  - `scripts/research/crt_resolver_economic_comparison.py:246` (mention)
  - `scripts/research/crt_resolver_economic_comparison.py:247` (get_with_fallback)
  - `scripts/research/crt_state_confusion_matrix.py:381` (mention)
  - `scripts/research/crt_state_confusion_matrix.py:392` (get_with_fallback)
  - `scripts/research/link001_choch_measurement.py:143` (get_with_fallback)
  - `scripts/research/retest_divergence_probe.py:176` (get_with_fallback)
  - `scripts/research/validate_crt_state_resolver.py:355` (mention)
  - `scripts/research/validate_crt_state_resolver.py:391` (mention)
  - `scripts/research/validate_crt_state_resolver.py:468` (mention)
  - `scripts/research/validate_crt_state_resolver.py:511` (mention)
  - `scripts/research/validate_crt_state_resolver.py:530` (get_with_fallback)
  - `scripts/research/validate_crt_state_resolver.py:718` (get_with_fallback)
  - `src/features/feature_pipeline.py:88` (mention)
  - `src/features/feature_pipeline.py:598` (mention)
  - `src/features/feature_pipeline.py:602` (direct_read)
  - `src/strategies/s02_mean_reversion.py:14` (mention)
  - `src/strategies/s02_mean_reversion.py:84` (get_with_fallback)

### `rsi_oversold`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['30']`
- Fallback values: `['30', '30.0', 'thr_defaults["rsi_oversold"]']`
- **Mismatch:** `[{'declared': '30', 'fallback': 'thr_defaults["rsi_oversold"]'}]`
- Read sites (18; direct=9):
  - `scripts/research/crt_range_rebuild_probe.py:273` (get_with_fallback)
  - `scripts/research/crt_resolver_economic_comparison.py:246` (mention)
  - `scripts/research/crt_resolver_economic_comparison.py:248` (get_with_fallback)
  - `scripts/research/crt_state_confusion_matrix.py:381` (mention)
  - `scripts/research/crt_state_confusion_matrix.py:393` (get_with_fallback)
  - `scripts/research/link001_choch_measurement.py:144` (get_with_fallback)
  - `scripts/research/retest_divergence_probe.py:177` (get_with_fallback)
  - `scripts/research/validate_crt_state_resolver.py:356` (mention)
  - `scripts/research/validate_crt_state_resolver.py:391` (mention)
  - `scripts/research/validate_crt_state_resolver.py:469` (mention)
  - `scripts/research/validate_crt_state_resolver.py:512` (mention)
  - `scripts/research/validate_crt_state_resolver.py:531` (get_with_fallback)
  - `scripts/research/validate_crt_state_resolver.py:719` (get_with_fallback)
  - `src/features/feature_pipeline.py:88` (mention)
  - `src/features/feature_pipeline.py:598` (mention)
  - `src/features/feature_pipeline.py:603` (direct_read)
  - `src/strategies/s02_mean_reversion.py:9` (mention)
  - `src/strategies/s02_mean_reversion.py:83` (get_with_fallback)

### `schema`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['threshold_refs/v1']`
- Fallback values: `['"legacy_6input"', '_SCHEMA', '{}']`
- **Mismatch:** `[{'declared': 'threshold_refs/v1', 'fallback': '"legacy_6input"'}, {'declared': 'threshold_refs/v1', 'fallback': '_SCHEMA'}, {'declared': 'threshold_refs/v1', 'fallback': '{}'}]`
- Read sites (700; direct=14):
  - `scripts/analysis/behavior_census.py:32` (mention)
  - `scripts/analysis/behavior_census.py:82` (mention)
  - `scripts/analysis/behavior_census.py:95` (mention)
  - `scripts/analysis/behavior_census.py:96` (mention)
  - `scripts/analysis/behavior_census.py:171` (mention)
  - `scripts/analysis/behavior_census.py:194` (mention)
  - `scripts/analysis/behavior_census.py:309` (mention)
  - `scripts/analysis/behavior_census.py:361` (mention)
  - `scripts/analysis/behavior_census.py:436` (mention)
  - `scripts/analysis/build_crt_input_authority_matrix.py:280` (mention)
  - `scripts/analysis/build_decision_atlas.py:22` (mention)
  - `scripts/analysis/build_pattern_library.py:19` (mention)
  - `scripts/analysis/build_pattern_library.py:197` (mention)
  - `scripts/analysis/consensus_sweep.py:333` (mention)
  - `scripts/analysis/detection_sweep.py:173` (mention)
  - `scripts/analysis/early_invalidation_ab.py:128` (mention)
  - `scripts/analysis/early_invalidation_exectrade_ab.py:147` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:7` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:506` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:539` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:550` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:561` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:572` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:583` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:594` (mention)
  - â€¦ +675 more

### `score_threshold`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['0.45']`
- Fallback values: `['0.45', '_DEFAULTS["score_threshold"]']`
- **Mismatch:** `[{'declared': '0.45', 'fallback': '_DEFAULTS["score_threshold"]'}]`
- Read sites (37; direct=3):
  - `scripts/analysis/crt_state_transition_audit_4m.py:257` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:261` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:263` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:264` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:433` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:512` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:631` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:691` (mention)
  - `scripts/analysis/crt_state_transition_audit_4m.py:695` (mention)
  - `scripts/analysis/crt_xauusd_runtime_trace.py:172` (mention)
  - `scripts/analysis/funnel_xauusd_4m.py:249` (mention)
  - `scripts/backtest/backtest_debug_harness.py:28` (mention)
  - `scripts/research/crt_parity_classifier.py:88` (mention)
  - `src/config_layer/config_builder.py:27` (mention)
  - `src/config_layer/config_builder.py:252` (mention)
  - `src/config_layer/config_validator.py:84` (mention)
  - `src/config_layer/crt_engine_v2.py:707` (mention)
  - `src/config_layer/crt_engine_v2.py:721` (mention)
  - `src/config_layer/crt_engine_v2.py:722` (mention)
  - `src/config_layer/crt_engine_v2.py:2269` (mention)
  - `src/config_layer/crt_engine_v2.py:3334` (mention)
  - `src/config_layer/state_identity.py:185` (mention)
  - `src/core/acceptance_controller.py:42` (mention)
  - `src/core/acceptance_controller.py:54` (mention)
  - `src/core/acceptance_controller.py:110` (mention)
  - â€¦ +12 more

### `session_windows`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (64; direct=8):
  - `scripts/analysis/build_crt_input_authority_matrix.py:308` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:9` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:310` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:311` (direct_read)
  - `scripts/analysis/crt_episode_number_trace.py:495` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:533` (direct_read)
  - `scripts/analysis/crt_predicate_failure_census_6m.py:127` (mention)
  - `scripts/analysis/crt_threshold_authority_census.py:57` (mention)
  - `scripts/analysis/p3c_zone_relax_diag.py:228` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:90` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:93` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:104` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:211` (direct_read)
  - `scripts/analysis/session_certification.py:220` (mention)
  - `scripts/analysis/session_cost_audit.py:28` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:32` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:40` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:163` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:204` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:205` (direct_read)
  - `scripts/analysis/session_filter_funnel_probe.py:337` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:339` (mention)
  - `scripts/analysis/session_filter_funnel_probe.py:474` (mention)
  - `scripts/analysis/session_sweep.py:18` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1012` (mention)
  - â€¦ +39 more

### `shadow_on_htf_displacement_reset`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['true']`
- Fallback values: `['True']`
- **Mismatch:** `[{'declared': 'true', 'fallback': 'True'}]`
- Read sites (8; direct=2):
  - `scripts/analysis/phase1_resolver_replay_evidence.py:257` (mention)
  - `scripts/analysis/phase1_resolver_replay_evidence.py:945` (mention)
  - `scripts/analysis/phase1_resolver_replay_evidence.py:972` (mention)
  - `scripts/research/crt_parity_sweep.py:106` (mention)
  - `src/features/crt_state_resolver.py:44` (mention)
  - `src/features/crt_state_resolver.py:913` (mention)
  - `src/features/crt_state_resolver.py:914` (get_with_fallback)
  - `src/features/crt_state_resolver.py:1037` (direct_read)

### `sl_atr_buffer`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (84; direct=12):
  - `scripts/analysis/behavior_census.py:68` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:604` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:614` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:625` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:630` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:835` (direct_read)
  - `scripts/analysis/crt_episode_number_trace.py:969` (direct_read)
  - `scripts/analysis/crt_episode_number_trace.py:970` (mention)
  - `scripts/analysis/crt_episode_number_trace.py:1024` (direct_read)
  - `scripts/analysis/run_crt_trace_workflow.py:58` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:105` (mention)
  - `scripts/analysis/run_crt_trace_workflow.py:212` (direct_read)
  - `scripts/analysis/shadow_cross_range_restoration_probe.py:210` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:53` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:422` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:439` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:442` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:460` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:516` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:570` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:613` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:704` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1020` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1027` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1064` (mention)
  - â€¦ +59 more

### `soft_conf_max_candles`
- P1 status: **read**
- Declared values: `['3']`
- Fallback values: `['3']`
- Read sites (9; direct=2):
  - `scripts/analysis/behavior_census.py:176` (mention)
  - `src/config_layer/crt_engine_v2.py:3543` (mention)
  - `src/config_layer/crt_engine_v2.py:3548` (mention)
  - `src/config_layer/state_identity.py:244` (mention)
  - `src/features/crt_state_resolver.py:1429` (mention)
  - `src/features/crt_state_resolver.py:2006` (mention)
  - `src/features/crt_state_resolver.py:2007` (get_with_fallback)
  - `src/features/crt_state_resolver.py:2014` (get_with_fallback)
  - `src/strategies/intent_builder.py:42` (mention)

### `sweep_geometry`
- P1 status: **read**
- Declared values: `['htf_range']`
- Fallback values: `['"htf_range"']`
- Read sites (12; direct=1):
  - `scripts/analysis/phase1_resolver_replay_evidence.py:347` (mention)
  - `scripts/analysis/phase1_resolver_replay_evidence.py:359` (mention)
  - `scripts/research/crt_range_rebuild_probe.py:391` (mention)
  - `scripts/research/crt_range_rebuild_probe.py:504` (mention)
  - `src/features/crt_state_resolver.py:60` (mention)
  - `src/features/crt_state_resolver.py:353` (get_with_fallback)
  - `src/features/crt_state_resolver.py:356` (mention)
  - `src/features/crt_state_resolver.py:469` (mention)
  - `src/features/crt_state_resolver.py:584` (mention)
  - `src/features/crt_state_resolver.py:1278` (mention)
  - `src/features/crt_state_resolver.py:1628` (mention)
  - `src/structure/predicates.py:50` (mention)

### `swing_window`
- P1 status: **read**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (30; direct=6):
  - `scripts/analysis/feature_38_lineage_census.py:39` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:40` (mention)
  - `scripts/analysis/feature_dag_structural_certification.py:296` (mention)
  - `scripts/analysis/feature_pipeline_fc05_closure.py:560` (mention)
  - `scripts/analysis/legacy_feature_fingerprint.py:94` (mention)
  - `scripts/analysis/phase1_run1_feature_truth.py:264` (mention)
  - `scripts/analysis/pit_swing_blast_radius.py:261` (mention)
  - `scripts/analysis/semantic_layer_validation.py:456` (mention)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:600` (direct_read)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1237` (direct_read)
  - `scripts/analysis/xauusd_excel_feature_state_trace.py:1278` (direct_read)
  - `scripts/research/smc_visual_verification.py:35` (mention)
  - `scripts/research/smc_visual_verification.py:497` (direct_read)
  - `scripts/research/smc_visual_verification.py:500` (mention)
  - `scripts/research/smc_visual_verification.py:612` (mention)
  - `scripts/research/trace_sweep_geometry.py:15` (mention)
  - `scripts/research/trace_sweep_geometry.py:360` (mention)
  - `scripts/research/trace_sweep_geometry.py:392` (mention)
  - `src/features/feature_pipeline.py:48` (mention)
  - `src/features/feature_pipeline.py:94` (mention)
  - `src/features/feature_pipeline.py:107` (mention)
  - `src/features/feature_pipeline.py:143` (mention)
  - `src/features/feature_pipeline.py:261` (mention)
  - `src/features/feature_pipeline.py:267` (mention)
  - `src/features/feature_pipeline.py:274` (mention)
  - â€¦ +5 more

### `total_capital_inr`
- P1 status: **unreferenced_hint**
- Declared values: `â€”`
- Fallback values: `â€”`
- Read sites (1; direct=0):
  - `src/strategies/base_strategy.py:58` (mention)

### `version`
- P1 status: **duplicated_fallback_mismatch**
- Declared values: `['1']`
- Fallback values: `['""', '"unknown"', "'?'", 'key', 'p.stem', 'version']`
- **Mismatch:** `[{'declared': '1', 'fallback': '"unknown"'}, {'declared': '1', 'fallback': "'?'"}, {'declared': '1', 'fallback': 'key'}, {'declared': '1', 'fallback': 'p.stem'}, {'declared': '1', 'fallback': 'version'}]`
- Read sites (1075; direct=45):
  - `scripts/analysis/all_states_persistence_probe.py:52` (mention)
  - `scripts/analysis/bnb_ema_gate_ab.py:106` (mention)
  - `scripts/analysis/config_reachability.py:37` (mention)
  - `scripts/analysis/config_reachability.py:76` (mention)
  - `scripts/analysis/config_reachability.py:253` (mention)
  - `scripts/analysis/config_reachability.py:254` (mention)
  - `scripts/analysis/config_reachability.py:355` (mention)
  - `scripts/analysis/consensus_sweep.py:61` (mention)
  - `scripts/analysis/consensus_sweep.py:62` (mention)
  - `scripts/analysis/corpus_read_lint.py:153` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:15` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:135` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:136` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:143` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:146` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:149` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:169` (mention)
  - `scripts/analysis/crt_declare_all_knobs_parity.py:171` (mention)
  - `scripts/analysis/feature_38_lineage_census.py:714` (mention)
  - `scripts/analysis/feature_pipeline_fc05_closure.py:753` (mention)
  - `scripts/analysis/feature_trace_report.py:599` (mention)
  - `scripts/analysis/feature_trace_report.py:910` (mention)
  - `scripts/analysis/gen_pyan.py:13` (mention)
  - `scripts/analysis/implementation_model_validation_xauusd.py:560` (mention)
  - `scripts/analysis/implementation_model_validation_xauusd.py:592` (mention)
  - â€¦ +1050 more

## Tier-1 bind summary (P2)

| param | authority | engine bind path | illegal fallback/default sites (count / headline) | drift class | bind note |
|---|---|---|---|---|---|
| `body_ratio_min` | **0.65** (`params` + YAML thr) | live: `self.config.body_ratio_min` (`crt_engine_v2` SWEEPâ†’DISP); resolver: `thr.get("body_ratio_min", 0.70)` | CRTConfig default **0.70**; resolver `.get(..., 0.70)`; router FOREX 0.6 | **Shadowed** | `body_ratio_min_bind.md` (P2 prior) |
| `atr_multiplier_min` | **1.0** | live: `self.config.atr_multiplier_min` (`crt_engine_v2.py:1367`); resolver: `thr.get(..., 1.5)` | CRTConfig **1.50**; resolver `.get(..., 1.5)`; FOREX router 1.5; prose (1.5); `manual_backtest` 1.5 | **Shadowed** | `atr_multiplier_min_bind.md` |
| `expansion_atr_min_distance` | **0.30** | live: `self.config.expansion_atr_min_distance` (`:1551`); resolver: `thr.get(..., 0.20)` | CRTConfig **0.20**; resolver `.get(..., 0.20)`; FOREX router 0.08; `manual_backtest` 0.20 | **Shadowed** | `expansion_atr_min_distance_bind.md` |
| `retest_depth_max` | **0.15** | live: `self.config.retest_depth_max` (`:1633` et al.); resolver: `thr.get(..., 0.25)` | CRTConfig **0.25**; resolver/probe `.get(..., 0.25)`; FOREX router 0.35 | **Shadowed** | `retest_depth_max_bind.md` |

### Dead / companion notes (touched in P2)

| key | brief status |
|---|---|
| `max_displacement_age_candles` | **Dead** â€” YAML declare only; `threshold_refs.dead_unconsumed`; not CRTConfig; not read by resolver (TTL is `lifecycle.pending_displacement_ttl_candles`). |
| `retest_atr_depth_fraction` | **Dead@resolver** / **Live@engine** â€” YAML 0.50 vs prod params **0.3**; engine uses `self.config.retest_atr_depth_fraction` in adaptive retest ceiling; resolver never `thr.get`s this name. |

Evidence SHA for bind write-up: `1890785daf31e9376c59b27e9f4d0e0998b99377` (`feature/trace-parquet-duckdb-query`). Re-pin if Windows HEAD differs.

