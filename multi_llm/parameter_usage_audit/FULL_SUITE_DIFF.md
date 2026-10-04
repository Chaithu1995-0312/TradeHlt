# Full-suite BEFORE/AFTER name diff (conditioned)

Deselected both sides: `tests/research/test_trace_corpus.py::test_pit_alignment_features_join_by_stream_position`

BEFORE failed=48 passed=1887
AFTER  failed=61 passed=1874

## Became RED (expected: 2 provenance; else SIGNAL)
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_close_exactly_at_sweep_price_is_not_away_from_liquidity[Direction.LONG]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_close_exactly_at_sweep_price_is_not_away_from_liquidity[Direction.SHORT]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_direction_none_fails_closed_without_a_sweep_event
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_rejected_displacement_leaves_no_transition_trace[insufficient_energy]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_rejected_displacement_leaves_no_transition_trace[not_away_from_sweep]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_rejected_displacement_leaves_no_transition_trace[wrong_sign]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_sweep_event_direction_outranks_state_direction[False-Direction.LONG]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_sweep_event_direction_outranks_state_direction[False-Direction.SHORT]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_sweep_event_direction_outranks_state_direction[True-Direction.LONG]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_sweep_event_direction_outranks_state_direction[True-Direction.SHORT]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_sweep_to_displacement_edge_is_legal_but_geometry_still_refuses
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_wrong_sign_is_rejected_before_the_energy_gate[Direction.LONG]
- [SIGNAL] tests/Claude/test_J_directional_displacement.py::test_wrong_sign_is_rejected_before_the_energy_gate[Direction.SHORT]

## Became GREEN

## Still RED both sides (pre-existing; not diff signal)
- [SIGNAL] tests/Claude/test_K_smc_identity.py::test_schema_is_48_dim_v5_with_a_nine_slot_smc_tail
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_cagr_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_expectancy_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_max_drawdown_pct_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_max_drawdown_rr_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_profit_factor_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_return_to_max_dd_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_total_return_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_trade_count_parity
- [SIGNAL] tests/analytics/test_metrics_oracle_parity.py::test_win_rate_parity
- [SIGNAL] tests/config_layer/test_instrument_overrides.py::test_end_to_end_no_overrides_block_is_inert
- [SIGNAL] tests/config_layer/test_instrument_overrides.py::test_end_to_end_override_wins_over_params
- [SIGNAL] tests/features/test_liquidity_distance.py::test_canonical_dim
- [SIGNAL] tests/harness/test_anti_hallucination.py::test_ah05_real_producer_golden
- [SIGNAL] tests/interpreters/test_pnf_shadow_e2e.py::test_pnf_chain_deterministic_by_hash
- [SIGNAL] tests/interpreters/test_pnf_shadow_e2e.py::test_pnf_chain_runs_on_real_data
- [SIGNAL] tests/interpreters/test_pnf_shadow_e2e.py::test_pnf_qualification_returns_verdict_not_promote
- [SIGNAL] tests/interpreters/test_reference_interpreter_e2e.py::test_chain_is_deterministic_by_hash
- [SIGNAL] tests/interpreters/test_reference_interpreter_e2e.py::test_chain_runs_and_produces_edgereport
- [SIGNAL] tests/interpreters/test_reference_interpreter_e2e.py::test_qualification_returns_a_verdict_not_promote
- [SIGNAL] tests/replay/test_assign_cluster.py::test_generated_replay_registry_is_valid_zone_v1[zone_registry_BNBUSDT]
- [SIGNAL] tests/replay/test_assign_cluster.py::test_generated_replay_registry_is_valid_zone_v1[zone_registry_BTCUSDT]
- [SIGNAL] tests/replay/test_assign_cluster.py::test_generated_replay_registry_is_valid_zone_v1[zone_registry_ETHUSDT]
- [SIGNAL] tests/replay/test_assign_cluster.py::test_generated_replay_registry_is_valid_zone_v1[zone_registry_SOLUSDT]
- [SIGNAL] tests/replay/test_replay_memory_engine.py::test_cluster_stats_built
- [SIGNAL] tests/research/episodes/test_candidate_features.py::test_production_canonical_contract_is_unchanged
- [SIGNAL] tests/research/episodes/test_policy_parity_corpus.py::test_labelsets_match_clean_labels_on_the_real_corpus
- [SIGNAL] tests/research/test_clean_labels_tn_env.py::test_build_and_write
- [SIGNAL] tests/research/test_clean_labels_tn_env.py::test_label_long_sl_path
- [SIGNAL] tests/research/test_clean_labels_tn_env.py::test_label_long_tp_path
- [SIGNAL] tests/research/test_clean_labels_tn_env.py::test_tp2_stretch_harder_than_unit_tp_at_2r
- [SIGNAL] tests/research/test_config_entry_ttl.py::test_every_existing_research_config_stays_sha_stable
- [SIGNAL] tests/research/test_erp_teaching_dual_read.py::test_boundary_json_ic001_complete
- [expected-caused-by-A] tests/research/test_exit_model_reconcile.py::test_provenance_block_shape
- [SIGNAL] tests/research/test_ic002_entry_evolution.py::test_prereg_matches_schema_constants
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[H1-binance-BNBUSDT]
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[H1-mt5-EURUSD]
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[H4-binance-BNBUSDT]
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[H4-mt5-EURUSD]
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[M15-binance-BNBUSDT]
- [SIGNAL] tests/research/test_resample_corpus_parity.py::test_resampled_m5_matches_fetched_file[M15-mt5-EURUSD]
- [SIGNAL] tests/research/test_story_library_golden.py::test_story_passes_all_six_layers_and_critical[bear_flag_continuation_short]
- [SIGNAL] tests/research/test_story_library_golden.py::test_story_passes_all_six_layers_and_critical[bull_flag_continuation_long]
- [SIGNAL] tests/research/test_story_ontology.py::test_all_feature_signatures_are_canonical
- [SIGNAL] tests/research/test_story_ontology.py::test_family_key_features_are_canonical
- [SIGNAL] tests/research/test_trace_corpus.py::test_corpus_schema_and_no_edge_field
- [SIGNAL] tests/research/test_trace_geometry.py::test_geometry_clusters_and_descriptive_only
- [SIGNAL] tests/research/test_trace_geometry.py::test_geometry_labels_are_deterministic

SUMMARY became_red=13 expected_A=0 SIGNAL=13 became_green=0 still_red=48
