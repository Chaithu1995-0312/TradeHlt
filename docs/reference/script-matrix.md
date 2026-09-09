# Script Matrix (Generated — SITS)

Generated from the Script Registry (stubs + overlays).

Regenerate:

```text
python scripts/governance/seed_script_registry.py
python scripts/analysis/generate_script_matrix.py
```

Authority: **inventory only** (no promote power). Thin-wrapper purity is **not**
CI-enforced in v1 — rows track `logic_in_script` / `implementation_status` only.

**Records:** 448

| ID | Category | Lifecycle | Impl status | Path | Purpose |
|---|---|---|---|---|---|
| `SCR-001` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `__init__.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-002` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_find_callers.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-003` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_find_context_calls.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-004` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_fm026_cert_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-005` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_gate0_check.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-006` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_gate0b_check.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-007` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_gate0de_check.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-008` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_m6r_remediation.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-009` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_m7v_presession.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-010` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_m8_cert_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-011` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_m8_checkpoint.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-012` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_m8_ledger_mutate.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-013` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `analyze_crt_pipeline.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-014` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-015` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `build_zone_registry_forced.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-016` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `build_zone_registry_from_trades.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-017` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `count_audit_tmp.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-018` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `run_phase_a_tests.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-019` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `run_regime_search.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-020` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `run_tests_capture.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-021` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/__init__.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-022` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/_gate5_compliance_pass.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-023` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/b2a_feature_candidate_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-024` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/behavior_census.py` | AST behavior-census for config-first maturity (HARD_CODED→CONFIG_DRIVEN). |
| `SCR-025` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/blind_label_sample.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-026` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/blind_label_score.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-027` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/bnb_ema_gate_ab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-028` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/bnbusdt_trade_anatomy.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-029` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/build_crt_input_authority_matrix.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-030` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/build_feature_contract_v1_seed.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-031` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/build_pattern_library.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-032` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/codebase_wiring_analysis.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-033` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/compare_bitnet_cpp_python.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-034` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/compare_guard_ablation_datasets.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-035` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/compress_logs_for_llm.py` | Stream opportunity JSONL logs into a token-efficient JSON summary for LLM gov... |
| `SCR-036` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/config_reachability.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-037` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/consensus_sweep.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-038` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_fail_reason_diagnostic.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-039` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_funnel_diagnostic.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-040` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_guard_ablation_6m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-041` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_guard_ablation_run.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-042` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_local_math_authority_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-043` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_predicate_failure_census_6m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-044` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_state_transition_audit_4m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-045` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_xauusd_runtime_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-046` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/daily_crypto_structure.py` | Extract daily market structure from BTC/crypto JSONL collector logs into a CS... |
| `SCR-047` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/detection_sweep.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-048` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/early_invalidation_ab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-049` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/early_invalidation_exectrade_ab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-050` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/exit_model_band.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-051` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/export_xauusd_window.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-052` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/f048_decision_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-053` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_38_lineage_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-054` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_dag_layers.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-055` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_dag_rolling_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-056` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_dag_structural_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-057` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_math_decision_flip_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-058` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_math_drift_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-059` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_math_lint.py` | Ownership lint for feature-math re-derivation (semantics-not-syntax). |
| `SCR-060` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_pipeline_fc05_closure.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-061` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_semantic_adjudication_pass_a.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-062` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_surface_closure_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-063` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/feature_trace_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-064` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/fm021_retest_depth_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-065` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/fm027_displacement_retrace_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-066` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/funnel_diagnosis.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-067` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/funnel_xauusd_4m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-068` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gate2b_adjudication.py` | Gate-2b feature-math divergence adjudication ledger helper. |
| `SCR-069` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gate_contribution_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-070` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gd004_disp_rescale_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-071` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_citation_map.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-072` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_code_map.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-073` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_dummy_trades.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-074` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_flow_graphs.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-075` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_html_explorer.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-076` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/gen_pyan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-077` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/generate_cli_matrix.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-078` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/geometry_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-079` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/graph_query.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-080` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/hour_of_day_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-081` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/implementation_model_validation_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-082` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/ledger_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-083` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/legacy_feature_fingerprint.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-084` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/mature_semantic_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-085` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/model_evidence_survey.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-086` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/mother_range_inside_close.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-087` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/ohlcv_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-088` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p1_sweep_memory_diag.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-089` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p2_disp_exemption_diag.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-090` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p3a_zone_attribution_diag.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-091` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p3b_gate_expired_counterfactual_rr.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-092` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p3b_session_relax_diag.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-093` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p3c1_build_trade_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-094` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p3c_zone_relax_diag.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-095` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p4_execution_intent_attribution.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-096` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/phase1_duplicate_formula_identity_closure.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-097` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/phase1_run15a_quantity_role_adjudication.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-098` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/phase1_run1_feature_truth.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-099` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/pit_phaseC_feature_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-100` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/pit_swing_blast_radius.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-101` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/pit_swing_gateon_ab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-102` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/process_characterizer.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-103` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/process_diagnostics.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-104` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/purge_delay_scan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-105` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/purge_slice.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-106` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/python_source_static_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-107` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/reachability_validation_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-108` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/rr_confidence_probe.py` | In-sample RR Mahalanobis confidence distribution probe (F-044). |
| `SCR-109` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_crt_local_math_parity_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-110` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_gaussian_xauusd_2m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-111` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_msip_shadow.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-112` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_rr_xauusd_2m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-113` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_zonegate_xauusd_2m.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-114` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/schema_audit.py` | Audit trades CSV files for schema consistency against CANONICAL_FEATURES. |
| `SCR-115` | CANONICAL_CLI | ACTIVE | TESTED | `scripts/analysis/script_census.py` | Thin CLI for SITS census; core in src/governance/script_census.py. |
| `SCR-116` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/search_xauusd_candidate_window.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-117` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/semantic_layer_validation.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-118` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/session_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-119` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/session_cost_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-120` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/session_override_scoping_proof.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-121` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/session_sweep.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-122` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/trend_strength_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-123` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/update_reachability_golden.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-124` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/volatility_regime_certification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-125` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-126` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_crt_baseline_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-127` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_crt_transition_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-128` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_phase1_finish_validation.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-129` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_strict_reject_forensic.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-130` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/zone_assignment_parity_probe.py` | ZoneGate assignment parity probe (F-041 runtime↔label). |
| `SCR-131` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/zone_registry_builder.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-132` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/zone_registry_provenance_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-133` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/auto_train_from_opportunities.py` | Full Pipeline-B nightly loop: scan opportunities → compress → Gaussian traini... |
| `SCR-134` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/backtest/backtest_debug_harness.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-135` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/backtest/manual_backtest.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-136` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/build_consolidated_docs.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-137` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/context/build_context.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-138` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/context/discussion.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-139` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/context/log_turn.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-140` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/context/pack_story.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-141` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/context/seed_build_queue.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-142` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/control_plane/run_server.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-143` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/build_m15_unified.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-144` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/build_rr_dataset.py` | Build RR training dataset from opportunity scanner JSONL (unbiased) or legacy... |
| `SCR-145` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/build_tradenet_dataset.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-146` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/check_availability.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-147` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/check_yfinance.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-148` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/convert_binance_m1_to_m15.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-149` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/convert_bnb_to_csv.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-150` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/csv_to_excel.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-151` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_and_verify_binance.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-152` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_and_verify_mt5.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-153` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_candles_alphavantage.py` | Download M15 forex OHLCV candles from Alpha Vantage FX_INTRADAY API into data/. |
| `SCR-154` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_candles_hummingbot.py` | Download M15 crypto OHLCV candles from exchange via Hummingbot connector into... |
| `SCR-155` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_candles_mt5.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-156` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_crypto_ccxt.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-157` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_forex_yfinance.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-158` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/fetch_perp_funding.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-159` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/generate_vectors.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-160` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/prepare_data.py` | Convert and validate raw source files into normalized M15 outputs. |
| `SCR-161` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/split_bnb_excel.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-162` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/test_yf_periods.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-163` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/unified_data_builder.py` | Build unified multi-instrument data outputs for CRT workflows. |
| `SCR-164` | DATA | ACTIVE | LOGIC_IN_SCRIPT | `scripts/data/verify_output.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-165` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/evaluation/__init__.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-166` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/evaluation/report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-167` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/evaluation/run_benchmark.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-168` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/export/export_bitnet_model.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-169` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/export/generate_bootstrap_model.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-170` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/export/regen_bitnet_35.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-171` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/export_model_registry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-172` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/extract_folder_structure.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-173` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/behavioral_constant_authority_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-174` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/build_crt_architecture_adjudication_v1.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-175` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/build_fm_ownership_matrix.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-176` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/build_g001_consumer_attribution.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-177` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/build_msip1_verification_package.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-178` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/build_msip_shadow_design_contract_v1.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-179` | GOVERNANCE | ACTIVE | ACCEPTED_COLOCATED | `scripts/governance/construction_protocol.py` | Gate-6 construction protocol validator (accepted colocated governance tooling... |
| `SCR-180` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/export_findings.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-181` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/feature_certification_state.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-182` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/feature_dag_certify.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-183` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/feature_surface_query.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-184` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/framework_gap_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-185` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/framework_registry_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-186` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/patch_msip_shadow_design_consistency_v1.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-187` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/promote_v2.py` | Thin wrapper for v2 multi-instrument promotion — validate and write productio... |
| `SCR-188` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/query_hypotheses.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-189` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/query_registry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-190` | CANONICAL_CLI | ACTIVE | WIRED | `scripts/governance/query_scripts.py` | Thin CLI over ScriptRegistry query/debt/parity APIs. |
| `SCR-191` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/remap_zone_registry_v4.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-192` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/rr_l1_freeze_certificate.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-193` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/scan_model_paths_literals.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-194` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/scan_runtime_boundary.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-195` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/seed_framework_registry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-196` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/seed_hypothesis_registry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-197` | CANONICAL_CLI | ACTIVE | TESTED | `scripts/governance/seed_script_registry.py` | Thin CLI + PRIMARY overlays; merge engine in src/governance/script_seed.py. |
| `SCR-198` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/three_authority_surplus_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-199` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/update_registry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-200` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/who_numeric_dependency_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-201` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/groq_bridge/apply_llm_suggestions.py` | Phase-1 Groq Bridge: apply LLM hyperparameter suggestions from a JSON respons... |
| `SCR-202` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/groq_bridge/ingest_response.py` | Phase-1 Groq Bridge: ingest LLM JSON response and optionally apply config/tra... |
| `SCR-203` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/groq_bridge/prepare_retrospective.py` | Phase-1 Groq Bridge: prepare a retrospective prompt from trades/opportunities... |
| `SCR-204` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/_compute_hash.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-205` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/_promote_v4_bnb_cutover.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-206` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/check_consolidation_due.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-207` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/check_governance_invariants.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-208` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/check_session_log_commit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-209` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/cleanup_logs.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-210` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/fix_bom.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-211` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/reorganize_results.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-212` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/rotate_session_log.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-213` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/metrics/extract_metrics.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-214` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/misc/bitnet_ternary_inference.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-215` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/misc/build_zone_registry_from_trades.py` | Rebuild per-instrument zone registry JSON files from *_trades.csv output. |
| `SCR-216` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/misc/resample_m1_to_m15.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-217` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/misc/run_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-218` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/misc/trade_replay_validator.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-219` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/multi_llm/initiate_plan.py` | Prepare model-separated PROPOSAL + plan-design PROMPT + curated CONTEXT_BUNDL... |
| `SCR-220` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/portfolio/replay_allocator.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-221` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/rag_index.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-222` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_build_xauusd_library_and_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-223` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_corpus_inspect.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-224` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_enrich_xauusd_corpus.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-225` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_enrich_xauusd_engines.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-226` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_fix_eval_auc.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-227` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_patch_xauusd_report_tradenet.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-228` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_show_top_decile_n9.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-229` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_verify_outputs.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-230` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/_watch_h_rr.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-231` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ablate_zone_thr_xauusd_fusion.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-232` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/accepted_trade_attribution.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-233` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/analyze_clean_labels_tn_env.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-234` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/analyze_trace_corpus.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-235` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bitnet_population_label_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-236` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bitnet_r25_kill_test.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-237` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bitnet_shadow_diagnostic.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-238` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bnbusdt_analyze_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-239` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bnbusdt_conditional_edge.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-240` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bnbusdt_enrich_trades.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-241` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/bnbusdt_forensics.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-242` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_boundary_hypothesis_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-243` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_clean_labels_tn_env.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-244` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_crt_zone_crosstab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-245` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_displacement_zone_event_study.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-246` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_episodes.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-247` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_gaussian_delta_gap_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-248` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_gaussian_family_shadow_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-249` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_rare_zone_context_filter_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-250` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_rare_zone_detection_eval.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-251` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_rare_zone_fa_characterization.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-252` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_resampled_data.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-253` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_rr_dataset_from_clean_labels.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-254` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_trace_corpus.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-255` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_zone_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-256` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/candle_state_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-257` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/certify_xauusd_corpus.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-258` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/convert_zones_v1_to_gaussian.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-259` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_state_confusion_matrix.py` | Bar-aligned CRT resolver-vs-engine confusion-matrix instrument. Extended this... |
| `SCR-260` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/diagnose_gaussian_pivotality.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-261` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/diagnose_zone_inertness.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-262` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/dimensional_mix_shadow_diagnostic.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-263` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/discover_zones.py` | Cluster opportunity logs into zone registry for the Zone Gate engine via KMea... |
| `SCR-264` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/edge_attribution_study.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-265` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/erp_synth_4h_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-266` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/execution_planner_replay.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-267` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/feature_formula_coverage_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-268` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/feature_region_oos_study.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-269` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/gate0_tn_env_feasibility.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-270` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/gate_o_nonlinear_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-271` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/gaussian_rr_scatter.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-272` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/h_rr_threshold_001.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-273` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ic002_build_trajectories.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-274` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ic002_evaluate.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-275` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ic003_build_shape_library.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-276` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ic003b_build.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-277` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ic003b_derive_information.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-278` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/ingest_live_outcomes.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-279` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/inspect_old_runs.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-280` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/live_path_replay.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-281` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/m5_mtf_information.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-282` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/model_shadow_protocol.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-283` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/momentum_continuation_bnbusdt.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-284` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/opportunity_scanner.py` | Generate unbiased opportunity logs for Gaussian/Zone model training (Pipeline... |
| `SCR-285` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/path_ambiguity_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-286` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase0_economic_edge_diagnosis.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-287` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase6e_shadow_ab.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-288` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase_b_conditional_entropy.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-289` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase_d_exit_grid.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-290` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase_e_structural_asymmetry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-291` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/phase_s_selection_effect.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-292` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/promotion_dryrun.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-293` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_carry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-294` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_cross_sectional.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-295` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_fx_metals.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-296` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_harvest.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-297` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_htf.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-298` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_interpreter.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-299` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_m5_straddle.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-300` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_majors.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-301` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_regime_conditioning.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-302` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_regime_transition.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-303` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_shape_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-304` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_transitions.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-305` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_weekly_sweep.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-306` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-307` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/qualify_zone_topk.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-308` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rerun_xau_metals_m4.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-309` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rr_kill_test_clean_l3.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-310` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rr_l2_feature_truth.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-311` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rr_l3_label_generation.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-312` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rr_l4_research_execution.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-313` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rr_shadow_value.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-314` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_crt_state_on_mt5_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-315` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_envelope_shadow_weight0.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-316` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_h_g001_001_sweep_veto.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-317` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_h_msip_001.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-318` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_h_msip_002.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-319` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_model_offline.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-320` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_xau_metals_protocol_v1.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-321` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_xauusd_all_models_report.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-322` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/shape_statistics_survey.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-323` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/story_library_build.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-324` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/trace_geometry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-325` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/trace_knn.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-326` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/trace_sweep_geometry.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-327` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/trace_zone_gate_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-328` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/train_envelope_offline.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-329` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/transition_information.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-330` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/validate_crt_state_resolver.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-331` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/validate_fm030_bands.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-332` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/verify_m5_resample_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-333` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_gaussian_econ_ledger.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-334` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_gaussian_econ_units.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-335` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_gaussian_m4_qualify.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-336` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_price_cost_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-337` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/zone_gate_threshold_sweep.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-338` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/zone_label_audit.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-339` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/tmp_cert_worktrees.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-340` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/_write_hashes_closure_narrative.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-341` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/auto_tuner.py` | Run single/multi instrument tuner for parameter optimization. |
| `SCR-342` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/auto_tuner_gemini_gate.py` | CRT Engine auto-tuner with Gemini gate variant — multi-instrument Bayesian op... |
| `SCR-343` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/auto_tuner_multi.py` | Run multi-instrument tuner and emit checkpoint artifacts. |
| `SCR-344` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/build_stage1_dataset.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-345` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/phase5_calibration.py` | Train and calibrate the Gaussian model from unbiased opportunity logs. Replac... |
| `SCR-346` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/show_xauusd_gaussian_promotion.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-347` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_bitnet.py` | Train legacy BitNet ternary model from M15 CSV data. |
| `SCR-348` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_bitnet_contract_c.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-349` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_gaussian_xauusd.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-350` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_pipeline.py` | Run TradeNet binary classifier training or Gaussian registry update from fusi... |
| `SCR-351` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_rr_model.py` | Train the RR Pattern Miner from a versioned RR dataset. Saves a uniquely-vers... |
| `SCR-352` | TRAINING | ACTIVE | LOGIC_IN_SCRIPT | `scripts/training/train_trade_net_v2.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-353` | CANONICAL_CLI | ACTIVE | LOGIC_IN_SCRIPT | `scripts/update_config_hash.py` | Recompute and write the SHA-256 hash for a production config JSON. Run after ... |
| `SCR-354` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/validate_integration.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-355` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/generate_script_matrix.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-356` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `_scripts_functionality_export.py` | One-shot exporter: scripts/**/*.py -> Excel (name, summary, project imports). |
| `SCR-357` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/soft_conf_ema_double_update_probe.py` | OBSERVATION_ONLY probe (F-067): measures the CRT soft-confirmation double Eng... |
| `SCR-358` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/src_business_functionality_inventory.py` | Inventory business functionality of every src/**/*.py file -> xlsx. |
| `SCR-359` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/test_functionality_excel.py` | Build an Excel inventory of tests/**/*.py business functionality (read-only). |
| `SCR-360` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_parity_classifier.py` | Pure mismatch classifier (A/B/C/D taxonomy) for CRT semantic parity confusion... |
| `SCR-361` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_parity_report.py` | Generates reports/crt_semantic_parity_report.md from the Stage-A sweep ledger... |
| `SCR-362` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_parity_sweep.py` | Stage A/B sweep driver for CRT semantic parity: coordinate-descent over resol... |
| `SCR-363` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_range_rebuild_probe.py` | OBSERVATION_ONLY probe: classifies residual SWEEP<->RANGE disagreement after ... |
| `SCR-364` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_resolver_economic_comparison.py` | One-off economic comparison: CRTStateResolver (EXPANSION-entry, relaxed trigg... |
| `SCR-365` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_mt5_cost_calibration.py` | ZONE-X O-1 diagnostic: extracts real spread/commission/slippage/swap for XAUU... |
| `SCR-366` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_mt5_cost_seed_stops.py` | ZONE-X O-1 DEMO-ONLY helper: places near-market STOP orders on XAUUSD so a co... |
| `SCR-367` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/zone_x_o4_gap_study.py` | ZONE-X O-4 DESCRIPTIVE gap-penalty study: on XAUUSD M15, how realized adverse... |
| `SCR-368` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/gate_measurement_m_gate_01.py` | M-GATE-01 SCOPE measurement (authority: NONE): two-arm gate-OFF vs gate-ON re... |
| `SCR-369` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/_build_doc_tracking_index.py` | Build DOC_TRACKING_INDEX.xlsx — a metadata-only inventory of docs/ (path, top... |
| `SCR-370` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/validation_access_cli.py` | VA-XAUUSD-M15 dual-surface validation access: Surface A human CLI ladder (std... |
| `SCR-371` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/crt_config_construction_census.py` | P1 OBSERVE census of CRTConfig construction: static AST scan for ConfigBuilde... |
| `SCR-372` | GOVERNANCE | ACTIVE | TESTED | `scripts/analysis/module_census.py` | Module attribution census: enumerate src/**/*.py and report closure-surface c... |
| `SCR-373` | GOVERNANCE | ACTIVE | EXTRACTED_TO_SRC | `scripts/governance/seed_semantic_os.py` | Compile the hand-authored Semantic OS YAMLs (docs/governance/semantic_os/conc... |
| `SCR-374` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/coverage_dashboard.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-375` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/mc_cpr_l0_residual_harness.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-376` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/enrich_workbooks_with_semantic_identity.py` | Append Semantic File Identity columns (Semantic ID / Semantic Name / Filename... |
| `SCR-377` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_episode_coverage_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-378` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/xauusd_episode_semantic_reconstruction.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-379` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_dedent.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-380` | PROBE | EPHEMERAL | LOGIC_IN_SCRIPT | `_run_mr.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-381` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/all_states_economic_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-382` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/all_states_persistence_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-383` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/blind_label_rasterize.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-384` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/build_decision_atlas.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-385` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/build_sweep_liquidity_fact.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-386` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_config_completeness_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-387` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_declare_all_knobs_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-388` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_episode_number_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-389` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/crt_threshold_authority_census.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-390` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/p001_excursion_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-391` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/query_decision_atlas.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-392` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/query_trace.py` | READ-ONLY DuckDB query surface over Trace/research Parquet projections (crt_c... |
| `SCR-393` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/render_chart.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-394` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/research_dag_provenance.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-395` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/run_crt_trace_workflow.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-396` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/session_filter_funnel_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-397` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/shadow_cross_range_restoration_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-398` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/sweep_conditional_magnitude_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-399` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/sweep_state_persistence_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-400` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/sweep_structure_economic_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-401` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/v3_config_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-402` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/xauusd_excel_feature_state_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-403` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/provenance_query.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-404` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/query_semantic_os.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-405` | GOVERNANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/governance/review_ohlcv_clocks.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-406` | ORPHAN | ACTIVE | LOGIC_IN_SCRIPT | `scripts/live/run_live_rail.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-407` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/g1_build_v4_crt_sot_config.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-408` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/g2_v4_crt_sot_parity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-409` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/g3_append_v4_crt_sot_registration.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-410` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/gen_crt_state_identity.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-411` | MAINTENANCE | ACTIVE | LOGIC_IN_SCRIPT | `scripts/maintenance/jsonl_to_parquet.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-412` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/build_bar_matrix.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-413` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_state_window_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-414` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/crt_variant_surface.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-415` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/e1_retest_depth_max_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-416` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/emit_bar_structure_snapshots.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-417` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/emit_dual_construction_trace.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-418` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/exit_geometry_scan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-419` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_activity_conditioning.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-420` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_gap_policy.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-421` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_group_ablation.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-422` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_multivariate_model.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-423` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_normalization_control.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-424` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_regime_stability.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-425` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_scan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-426` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/high_acceptance_structural_scan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-427` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/htf_objective_gate_shadow.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-428` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/htf_parent_telemetry_extract.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-429` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/oracle_pattern_scan.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-430` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/p_struct_01_displacement_evidence.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-431` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/parent_crt_pivotality_probe.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-432` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/rc003_distinct_object.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-433` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/run_evidence_layer.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-434` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/smc_feature_month_extract.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-435` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/smc_visual_verification.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-436` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/tv_engine_odds.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-437` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/tv_structure_comparison.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-438` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/validate_oracle_harness.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-439` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/vcrt_remeasure_v2.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-440` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/visual_state_questions.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-441` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/visual_state_sample.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-442` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/visual_state_score.py` | GRANDFATHER_UNCLASSIFIED |
| `SCR-443` | DIAGNOSTIC | ACTIVE | LOGIC_IN_SCRIPT | `scripts/analysis/analytics_evidence_class_census.py` | EC-001 observation-only evidence-class census over analytics lineage rows (CO... |
| `SCR-444` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/jse001_crt_context_join.py` | JSE-001 measure-only: engine_state_asof vs joint-state membership (BNB-only).... |
| `SCR-445` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/jse002_engine_state_path_geometry.py` | JSE-002 measure-only: does engine_state_asof predict path geometry (BNB-only)... |
| `SCR-446` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/jse003_engine_context_history_path_geometry.py` | JSE-003 measure-only: engine_context_history vs path geometry (BNB-only). Com... |
| `SCR-447` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/l003h_trail_exit_transition_replay.py` | L-003H measure-only candle replay for trail/exit transition events (standalon... |
| `SCR-448` | RESEARCH_RUNNER | ACTIVE | LOGIC_IN_SCRIPT | `scripts/research/l003i_trail_baseline_inversion.py` | L-003I measure-only baseline direction / base-rate inversion derived from L-0... |

---

*Generator: `scripts/analysis/generate_script_matrix.py` · schema: `docs/reference/schemas.md` §9.8 · authority=`inventory`*
