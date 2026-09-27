# Behavior Census — live-spine BEHAVIORAL constant inventory

_Generated 2026-09-18T07:16:53.615260+00:00 by `scripts/analysis/behavior_census.py` (read-only)._

**Totals** — BEHAVIORAL 74 · STRUCTURAL 134 · GOAL_SEEKING 14 · UNCLASSIFIED 77

**Maturity ladder** (behavior) — CONFIG_DRIVEN 47 · CONFIG_WIRED 13 · HARD_CODED 5  _(GOAL_SEEKING is orthogonal, not a rung)_

## Maturity by module (behavioral modules)

_Behavioral = all behavioral literals; Hardcoded = genuine debt (neither in-file- nor externally-wired); Ext-wired = config-injected by a consumer/schema class._

| Module | Behavioral | Ext-wired | Hardcoded | Maturity | Goal-seeking |
|---|---|---|---|---|---|
| `config_layer/crt_engine_v2.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `config_layer/crt_gaussian_scorer.py` | 3 | 0 | 0 | CONFIG_WIRED | - |
| `config_layer/crt_sweep_taxonomy.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `config_layer/rr/rr_pattern_miner.py` | 2 | 0 | 0 | CONFIG_WIRED | - |
| `config_layer/state_identity.py` | 26 | 26 | 0 | CONFIG_WIRED | yes |
| `core/acceptance_controller.py` | 2 | 0 | 0 | CONFIG_WIRED | - |
| `core/convergence_controller.py` | 9 | 0 | 0 | CONFIG_WIRED | - |
| `core/dynamic_threshold.py` | 0 | 0 | 0 | CONFIG_DRIVEN | - |
| `core/fusion_engine.py` | 13 | 13 | 0 | CONFIG_WIRED | - |
| `core/hierarchical_meta_fusion.py` | 1 | 0 | 1 | HARD_CODED | - |
| `core/model_registry.py` | 1 | 0 | 0 | CONFIG_WIRED | - |
| `core/regime_governor.py` | 4 | 0 | 0 | CONFIG_WIRED | - |
| `core/signal_audit.py` | 1 | 0 | 0 | CONFIG_WIRED | - |
| `core/signal_belief_tracker.py` | 1 | 0 | 0 | CONFIG_WIRED | - |
| `engines/live_engine.py` | 3 | 0 | 0 | CONFIG_WIRED | - |
| `features/crt_state_resolver.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `features/dataset_builder.py` | 1 | 0 | 1 | HARD_CODED | - |
| `features/feature_monitor.py` | 1 | 0 | 1 | HARD_CODED | - |
| `governance/expansion_integration.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `governance/multi_strategy_validator.py` | 2 | 0 | 0 | CONFIG_WIRED | - |
| `governance/semantic_os.py` | 2 | 0 | 2 | HARD_CODED | - |
| `governance/strategy_backtest.py` | 1 | 0 | 1 | HARD_CODED | - |
| `journal/trade_logger.py` | 1 | 0 | 0 | CONFIG_WIRED | - |

## Future config opportunities (GENUINE HARD_CODED debt — excludes externally-wired)

- `core/hierarchical_meta_fusion.py:127 _DEFAULT_WEIGHTS={...numeric...}`
- `features/dataset_builder.py:185 LAMBDA_DECAY_DEFAULT=0.0`
- `features/feature_monitor.py:60 DEFAULT_DRIFT_THRESHOLD=2.5`
- `governance/semantic_os.py:124 SUMMARY_50_MAX=320`
- `governance/semantic_os.py:125 SUMMARY_200_MAX=1400`
- `governance/strategy_backtest.py:50 _WARMUP=60`

## Per-module

### `config_layer/config_validator.py` — CONFIG_DRIVEN · config-wired

### `config_layer/crt_config_provenance.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._MAX_OBSERVE_EVENTS=5000 (L23)

### `config_layer/crt_engine_v2.py` — CONFIG_DRIVEN · config-wired
- **STRUCTURAL**: Candle.volume=0.0 (L94); Candle.index=0 (L95); SweepEvent.candle_index=0 (L165); RiskScore.breakout_score=0.0 (L176); RiskScore.retest_score=0.0 (L177); RiskScore.time_score=0.0 (L178); RiskScore.decay_factor=1.0 (L179); RiskScore.weights=[0.35, 0.25, 0.2, 0.2] (L185); Trade.risk_pct=0.01 (L209); Trade.pnl=0.0 (L213); Trade.partial_pnl=0.0 (L214); Trade.open_candle_index=0 (L217); EngineState.atr_abs=0.0 (L246); EngineState.retest_candle_index=0 (L249); EngineState.current_candle_index=0 (L250); EngineState.soft_conf_candles=0 (L255); EngineState.ema_fast_val=0.0 (L258); EngineState.ema_slow_val=0.0 (L259); EngineState.htf_remaining_candles=0 (L261); EngineState._displacement_entry_idx=0 (L262); EngineState.pending_displacement_ttl=0 (L266); EngineState.pending_displacement_formed_idx=0 (L268); EngineState.pending_displacement_age_at_reset=0 (L269); EngineState.pending_displacement_created_idx=0 (L275)
- **GOAL_SEEKING**: RiskScore.sweep_score=0.0 (L175); EngineState._expansion_entry_idx=0 (L280)

### `config_layer/crt_gaussian_scorer.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: CRTGaussianScorer.RETEST_MIN=0.025 (L48); CRTGaussianScorer.RETEST_MAX=1.0 (L49); CRTGaussianScorer.DISP_MAX=3.67 (L50)

### `config_layer/crt_sweep_taxonomy.py` — CONFIG_DRIVEN · NOT config-wired
- **GOAL_SEEKING**: <module>.WICK_BONUS_FACTOR=0.35 (L33)

### `config_layer/llm_inference_client.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L112)

### `config_layer/llm_scorer.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L49)

### `config_layer/m15_structural_range.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: M15StructuralLiquidityRange.child_count=0 (L46)

### `config_layer/rr/rr_dataset_builder.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.MIN_SAMPLES=20 (L38)

### `config_layer/rr/rr_pattern_miner.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>.RR_SCORE_MIN=-3.0 (L46); <module>.RR_SCORE_MAX=5.0 (L47)

### `config_layer/stack_version.py` — CONFIG_DRIVEN · NOT config-wired

### `config_layer/state_identity.py` — CONFIG_WIRED · NOT config-wired
- **BEHAVIORAL**: CRTConfig.body_ratio_min=0.7 (L140); CRTConfig.atr_multiplier_min=1.5 (L141); CRTConfig.retest_depth_max=0.25 (L142); CRTConfig.risk_score_weights=[0.35, 0.25, 0.2, 0.2] (L170); CRTConfig.score_component_weights=[0.35, 0.25, 0.2, 0.2] (L171); CRTConfig.score_decay_lambda=0.05 (L182); CRTConfig.score_threshold=0.45 (L185); CRTConfig.max_spread_pct=0.05 (L186); CRTConfig.confirmation_body_min=0.6 (L189); CRTConfig.tp1_atr_multiplier=1.0 (L191); CRTConfig.tp2_atr_multiplier=2.0 (L192); CRTConfig.breakout_disp_threshold=1.5 (L202); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L204); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L205); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L207); CRTConfig.bitnet_main_threshold=0.55 (L208); CRTConfig.retrace_reset_pct=0.5 (L226); CRTConfig.conf_alpha=0.7 (L233); CRTConfig.conf_beta=0.3 (L234); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L235); CRTConfig.conf_floor=0.2 (L236); CRTConfig.weak_link_weight=0.3 (L237); CRTConfig.tier_1_threshold=0.75 (L242); CRTConfig.tier_2_threshold=0.3 (L243); CRTConfig.soft_conf_max_candles=3 (L244); CRTConfig.shadow_age_penalty_lambda=0.0 (L289)
- **STRUCTURAL**: CRTConfig.atr_period=14 (L145); CRTConfig.atr_buffer_multiplier=3 (L146); CRTConfig.sl_atr_buffer=0.2 (L190)
- **GOAL_SEEKING**: CRTConfig.max_sweep_age_candles=20 (L149); CRTConfig.expansion_atr_min_distance=0.2 (L152); CRTConfig.tp1_atr_multiplier_liq_sweep=1.2 (L206); CRTConfig.max_expansion_age_candles=495 (L280); CRTConfig.max_expansion_age_hours=124 (L281); CRTConfig.expansion_age_warn_candles=342 (L282)
- **UNCLASSIFIED**: CRTConfig.retest_atr_depth_fraction=0.5 (L155); CRTConfig.retest_min_depth_atr_fraction=0.1 (L160); CRTConfig.max_displacement_strength=2.0 (L179); CRTConfig.atr_min_displacement=1.2 (L188); CRTConfig.extension_reset_fib=1.618 (L227); CRTConfig.news_blackout_minutes=15 (L230); CRTConfig.ema_fast=2 (L238); CRTConfig.ema_slow=5 (L239); CRTConfig.pending_displacement_ttl_candles=4 (L250); CRTConfig.shadow_age_norm_candles=0 (L296)
- **EXTERNALLY-WIRED** (config-injected, not debt): CRTConfig.body_ratio_min=0.7 (L140); CRTConfig.atr_multiplier_min=1.5 (L141); CRTConfig.retest_depth_max=0.25 (L142); CRTConfig.risk_score_weights=[0.35, 0.25, 0.2, 0.2] (L170); CRTConfig.score_component_weights=[0.35, 0.25, 0.2, 0.2] (L171); CRTConfig.score_decay_lambda=0.05 (L182); CRTConfig.score_threshold=0.45 (L185); CRTConfig.max_spread_pct=0.05 (L186); CRTConfig.confirmation_body_min=0.6 (L189); CRTConfig.tp1_atr_multiplier=1.0 (L191); CRTConfig.tp2_atr_multiplier=2.0 (L192); CRTConfig.breakout_disp_threshold=1.5 (L202); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L204); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L205); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L207); CRTConfig.bitnet_main_threshold=0.55 (L208); CRTConfig.retrace_reset_pct=0.5 (L226); CRTConfig.conf_alpha=0.7 (L233); CRTConfig.conf_beta=0.3 (L234); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L235); CRTConfig.conf_floor=0.2 (L236); CRTConfig.weak_link_weight=0.3 (L237); CRTConfig.tier_1_threshold=0.75 (L242); CRTConfig.tier_2_threshold=0.3 (L243); CRTConfig.soft_conf_max_candles=3 (L244); CRTConfig.shadow_age_penalty_lambda=0.0 (L289)

### `core/acceptance_controller.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._THETA_MIN=0.5 (L34); <module>._THETA_MAX=0.95 (L35)
- **UNCLASSIFIED**: <module>._MIN_HISTORY=10 (L38); <module>._DEFAULTS={...numeric...} (L41)

### `core/convergence_controller.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._WARMUP_BARS=10 (L39); <module>._THRESH_MIN=0.3 (L42); <module>._THRESH_MAX=0.9 (L43); <module>._THRESH_STEP=0.02 (L44); <module>._ACCEPT_RATE_HIGH=0.3 (L47); <module>._ACCEPT_RATE_LOW=0.1 (L48); <module>._ABS_QUALITY_FLOOR=0.3 (L54); <module>._SIG_K=8.0 (L57); <module>._SIG_T=0.6 (L58)

### `core/decision_engine.py` — CONFIG_DRIVEN · config-wired
- **STRUCTURAL**: DecisionResult.threshold_used=0.0 (L56)
- **UNCLASSIFIED**: <module>._FALLBACK_TOP_N=3 (L44)

### `core/dynamic_threshold.py` — CONFIG_DRIVEN · config-wired

### `core/engine_runner.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.DUAL_ENGINE_DEFAULTS={...numeric...} (L80)

### `core/fusion_engine.py` — CONFIG_WIRED · NOT config-wired
- **BEHAVIORAL**: FusionConfig.gaussian_weight=0.6 (L139); FusionConfig.neural_weight=0.4 (L140); FusionConfig.llm_weight=0.2 (L141); FusionConfig.llm_lower_band=0.45 (L142); FusionConfig.llm_upper_band=0.65 (L143); FusionConfig.tier_full=0.75 (L147); FusionConfig.tier_half=0.6 (L148); FusionConfig.tier_quarter=0.5 (L149); FusionConfig.weight_crt=0.3 (L152); FusionConfig.weight_gaussian=0.25 (L153); FusionConfig.weight_zone_gate=0.25 (L154); FusionConfig.weight_rr=0.2 (L155); FusionConfig.weight_strategy_consensus=0.0 (L158)
- **STRUCTURAL**: FusionResult.normalized_score=0.0 (L197); FusionResult.threshold_used=0.0 (L198)
- **UNCLASSIFIED**: FusionConfig.min_consensus_signals=2 (L172); FusionConfig.min_consensus_agreement=0.6 (L173)
- **EXTERNALLY-WIRED** (config-injected, not debt): FusionConfig.gaussian_weight=0.6 (L139); FusionConfig.neural_weight=0.4 (L140); FusionConfig.llm_weight=0.2 (L141); FusionConfig.llm_lower_band=0.45 (L142); FusionConfig.llm_upper_band=0.65 (L143); FusionConfig.tier_full=0.75 (L147); FusionConfig.tier_half=0.6 (L148); FusionConfig.tier_quarter=0.5 (L149); FusionConfig.weight_crt=0.3 (L152); FusionConfig.weight_gaussian=0.25 (L153); FusionConfig.weight_zone_gate=0.25 (L154); FusionConfig.weight_rr=0.2 (L155); FusionConfig.weight_strategy_consensus=0.0 (L158)

### `core/gate_intelligence.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: GateIntelligence._CONFIG_DEFAULTS={...numeric...} (L115)

### `core/hierarchical_meta_fusion.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: HierarchicalMetaFusion._DEFAULT_WEIGHTS={...numeric...} (L127)
- **UNCLASSIFIED**: <module>._STATE_SCORES={...numeric...} (L38)
- **GENUINE HARD_CODED**: HierarchicalMetaFusion._DEFAULT_WEIGHTS={...numeric...} (L127)

### `core/model_registry.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>.PROMOTION_MARGIN=0.02 (L40)

### `core/regime_governor.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: UltronGovernor.REGIME_PENALTY={...numeric...} (L105); UltronGovernor.REGIME_ACCEPT_PERCENTILE={...numeric...} (L111); UltronGovernor.DIRECTION_PENALTY=0.1 (L117); UltronGovernor.FALLBACK_THRESHOLD=0.45 (L118)
- **STRUCTURAL**: UltronGovernor.WINDOW_MAXLEN=100 (L120)
- **UNCLASSIFIED**: UltronGovernor.MAX_TRADES_PER_BATCH=3 (L103); UltronGovernor.WINDOW_MIN_SAMPLES=10 (L119)

### `core/signal_audit.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._TRADE_RATE_WARN=0.3 (L36)
- **UNCLASSIFIED**: <module>._ZONE_PASS_WARN=0.8 (L34); <module>._FUSION_PASS_WARN=0.5 (L35)

### `core/signal_belief_tracker.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: SignalBeliefTracker._DEFAULT_DECAY=0.7 (L79)
- **UNCLASSIFIED**: SignalBeliefTracker._DEFAULT_HIGH_CONVICTION=0.65 (L80); SignalBeliefTracker._DEFAULT_MIN_CONFIRMS=2 (L81)

### `core/ultron_live_adapter.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: LivePosition.unrealized_pct=0.0 (L25); LivePortfolioState.realized_pnl=0.0 (L36); LivePortfolioState.equity=0.0 (L37)

### `core/ultron_risk_gate_wrapper.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._DEFAULT_REGIME_FACTORS={...numeric...} (L48)

### `engines/live_engine.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: LiveEngineConfig.rr_threshold=1.5 (L466); LiveEngineConfig.confidence_min=0.55 (L467); LiveEngineConfig.ml_override_threshold=0.75 (L469)
- **UNCLASSIFIED**: LiveEngineConfig.confidence_strong=0.6 (L468); LiveEngineConfig.alert_cooldown_seconds=60 (L470); LiveEngineConfig.dedup_candles=4 (L471); <module>._BYPASS_CHECK_COUNTER=0 (L714); <module>._BYPASS_CHECK_EVERY_N=50 (L715)

### `engines/rr_engine.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._EPS=1e-09 (L33)

### `engines/scoring_engine.py` — CONFIG_DRIVEN · NOT config-wired

### `engines/zone_gate_engine.py` — CONFIG_DRIVEN · NOT config-wired

### `features/calendar_periods.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.HOUR_GRID_HOURS={...numeric...} (L61)

### `features/causal_structure.py` — CONFIG_DRIVEN · NOT config-wired

### `features/crt_feature_builder.py` — CONFIG_DRIVEN · NOT config-wired

### `features/crt_state_resolver.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: CRTStateMemory.htf_bars_in_window=0 (L162)
- **GOAL_SEEKING**: CRTStateMemory.sweep_candle_index=-1 (L146); CRTStateMemory.expansion_entry_index=-1 (L151)
- **UNCLASSIFIED**: CRTStateMemory.displacement_candle_index=-1 (L147); CRTStateMemory.displacement_candle_close=0.0 (L148); CRTStateMemory.displacement_direction=0 (L149); CRTStateMemory.retest_candle_index=-1 (L150); CRTStateMemory.pending_displacement_formed_idx=-1 (L154); CRTStateMemory.pending_displacement_ttl=0 (L156); CRTStateMemory.pending_displacement_created_idx=-1 (L157); CRTStateMemory.candle_index=0 (L159); CRTStateMemory.htf_reset_count=0 (L165); CRTStateMemory.gap_reset_count=0 (L166); CRTStateMemory.forced_reset_count=0 (L167); CRTStateMemory.range_h_ref=0.0 (L170); CRTStateMemory.range_l_ref=0.0 (L171)

### `features/dataset_builder.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>.LAMBDA_DECAY_DEFAULT=0.0 (L185)
- **UNCLASSIFIED**: <module>.MIN_GAUSSIAN_SAMPLES=20 (L184)
- **GENUINE HARD_CODED**: <module>.LAMBDA_DECAY_DEFAULT=0.0 (L185)

### `features/dataset_validator.py` — CONFIG_DRIVEN · config-wired
- **STRUCTURAL**: ValidationReport.total_lines=0 (L56); ValidationReport.entry_records=0 (L57); ValidationReport.exit_records=0 (L58); ValidationReport.reject_records=0 (L59); ValidationReport.paired_trades=0 (L60); ValidationReport.valid_for_training=0 (L61); ValidationReport.skipped_no_outcome=0 (L62); ValidationReport.skipped_bad_features=0 (L63); ValidationReport.skipped_duplicate=0 (L64); ValidationReport.skipped_parse_error=0 (L65)

### `features/feature_monitor.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>.DEFAULT_DRIFT_THRESHOLD=2.5 (L60)
- **UNCLASSIFIED**: <module>._MIN_SAMPLES_FOR_DRIFT=30 (L57)
- **GENUINE HARD_CODED**: <module>.DEFAULT_DRIFT_THRESHOLD=2.5 (L60)

### `features/feature_pipeline.py` — CONFIG_DRIVEN · config-wired

### `features/feature_schema.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: <module>.SCHEMA_V2_FEATURE_DIM=35 (L160); <module>.CANONICAL_FEATURE_DIM=48 (L166); <module>.SCHEMA_V3_FEATURE_DIM=38 (L169); <module>.SCHEMA_V4_FEATURE_DIM=39 (L176)
- **UNCLASSIFIED**: <module>.SESSION_UNKNOWN=-1.0 (L226); <module>.TREND_MAP={...numeric...} (L228)

### `features/market_context.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: MarketContext.completeness_ratio=0.0 (L166)

### `features/model_evidence.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: <module>._VALUE_PRECISION=6 (L82)

### `features/resolver_supply.py` — CONFIG_DRIVEN · NOT config-wired

### `features/session_classifier.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: SessionOrdinal.ASIA=0 (L59); SessionOrdinal.LONDON=1 (L60); SessionOrdinal.NEWYORK=2 (L61); SessionOrdinal.OVERLAP=3 (L62); SessionOrdinal.CLOSED=4 (L63); <module>.DEFAULT_SESSION_WINDOWS_UTC={...numeric...} (L91)

### `governance/archive_manifest.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: Report.rows=0 (L133); Report.manifests=0 (L134); Report.archive_files=0 (L135)

### `governance/expansion_integration.py` — CONFIG_DRIVEN · NOT config-wired
- **GOAL_SEEKING**: <module>._MIN_TRADES=30 (L27); <module>._MAX_DRAWDOWN=0.25 (L28); <module>._MAX_DD_MULTIPLIER=1.2 (L31)

### `governance/framework_registry.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: <module>._DRIFT_WINDOW=30 (L60)
- **UNCLASSIFIED**: <module>._TYPE_LEVEL={...numeric...} (L44)

### `governance/module_census.py` — CONFIG_DRIVEN · NOT config-wired

### `governance/multi_strategy_validator.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._MIN_PORTFOLIO_WIN_RATE=0.3 (L58); <module>._WARMUP_CANDLES=60 (L60)
- **UNCLASSIFIED**: <module>._MIN_STRATEGY_TRADES=5 (L57); <module>._MAX_PORTFOLIO_DRAWDOWN=75000000.0 (L59); <module>._MAX_FORWARD_CANDLES=40 (L61)

### `governance/portfolio_validation.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: InstrumentConfig.htf_candles=16 (L57)

### `governance/promotion_manager.py` — CONFIG_DRIVEN · config-wired

### `governance/script_census.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.THIN_MAX_NON_IMPORT_LOC=40 (L34)

### `governance/script_seed.py` — CONFIG_DRIVEN · NOT config-wired

### `governance/semantic_os.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>.SUMMARY_50_MAX=320 (L124); <module>.SUMMARY_200_MAX=1400 (L125)
- **STRUCTURAL**: <module>._DRIFT_WINDOW=30 (L224)
- **GENUINE HARD_CODED**: <module>.SUMMARY_50_MAX=320 (L124); <module>.SUMMARY_200_MAX=1400 (L125)

### `governance/semantic_query.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._CLASS_RANK={...numeric...} (L42)

### `governance/shadow_promotion_gate.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._DEFAULT_MIN_SHADOW_TRADES=30 (L49)

### `governance/strategy_backtest.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>._WARMUP=60 (L50)
- **STRUCTURAL**: StrategyMetrics.trade_count=0 (L58); StrategyMetrics.win_count=0 (L59); StrategyMetrics.loss_count=0 (L60); StrategyMetrics.timeout_count=0 (L61); StrategyMetrics.total_pnl_inr=0.0 (L62); StrategyMetrics.gross_profit=0.0 (L63); StrategyMetrics.gross_loss=0.0 (L64); StrategyMetrics.max_drawdown=0.0 (L65); StrategyMetrics.win_rate=0.0 (L66); StrategyMetrics.profit_factor=0.0 (L67); StrategyMetrics.expectancy_inr=0.0 (L68); StrategyMetrics.score=0.0 (L69)
- **UNCLASSIFIED**: <module>._USD_TO_INR=84.0 (L49); <module>._MAX_FWD=40 (L51)
- **GENUINE HARD_CODED**: <module>._WARMUP=60 (L50)

### `journal/schema.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: TradeRecord.confidence=0.0 (L20); TradeRecord.rr=0.0 (L21); TradeRecord.zone=0.0 (L22); TradeRecord.allocated_risk=0.0 (L25); TradeRecord.portfolio_exposure_before=0.0 (L26); TradeRecord.pnl=0.0 (L34); TradeRecord.duration_candles=0 (L35); TradeRecord.drawdown_at_entry=0.0 (L36)

### `journal/trade_logger.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>.MAX_CORRUPTION_RATIO=0.1 (L28)

### `runtime/analyze_fusion_shadow.py` — CONFIG_DRIVEN · NOT config-wired

### `runtime/backtest_bitnet.py` — CONFIG_DRIVEN · NOT config-wired

### `runtime/backtest_v2.py` — CONFIG_DRIVEN · config-wired
- **STRUCTURAL**: TradePathStats.mfe_price=0.0 (L346); TradePathStats.mae_price=0.0 (L347); TradePathStats.bars_to_peak=0 (L348); TradePathStats.bars_to_trough=0 (L349); TradePathStats.bars_observed=0 (L350); TradePathStats.mfe_rr=0.0 (L352); TradePathStats.mae_rr=0.0 (L353); TradeRecord.entry_price_fill=0.0 (L386); TradeRecord.exit_price_fill=0.0 (L387); TradeRecord.candle_open=0 (L391); TradeRecord.candle_close=0 (L392); TradeRecord.pnl_pips_raw=0.0 (L394); TradeRecord.pnl_pips_net=0.0 (L395); TradeRecord.pnl_rr_raw=0.0 (L396); TradeRecord.pnl_rr_net=0.0 (L397); TradeRecord.slippage_pips=0.0 (L398); TradeRecord.spread_pips=0.0 (L399); TradeRecord.capital_before=0.0 (L401); TradeRecord.capital_after=0.0 (L402); TradeRecord.position_size=0.0 (L403); TradeRecord.risk_score=0.0 (L405); TradeRecord.risk_pct=0.0 (L406); TradeRecord.week_of_year=0 (L411); TradeRecord.day_of_week=0 (L412); TradeRecord.hour_of_day=0 (L413); TradeRecord.live_atr=0.0 (L419); TradeRecord.live_ema_fast=0.0 (L420); TradeRecord.live_ema_slow=0.0 (L421); TradeRecord.cached_retest_depth=0.0 (L422); TradeRecord.cached_body_ratio=0.0 (L423); TradeRecord.cached_disp_strength=0.0 (L424); TradeRecord.bitnet_score_at_entry=0.0 (L431); RejectionRecord.risk_score=0.0 (L469); BacktestMetrics.total_candles=0 (L1381); BacktestMetrics.gap_resets=0 (L1382); BacktestMetrics.total_setups=0 (L1383); BacktestMetrics.approved_trades=0 (L1384); BacktestMetrics.rejected_trades=0 (L1385); BacktestMetrics.wins=0 (L1386); BacktestMetrics.losses=0 (L1387); BacktestMetrics.tp1_hits=0 (L1388); BacktestMetrics.tp2_hits=0 (L1389); BacktestMetrics.total_pnl_rr_raw=0.0 (L1390); BacktestMetrics.total_pnl_rr_net=0.0 (L1391); BacktestMetrics.max_drawdown_rr=0.0 (L1392); BacktestMetrics.max_drawdown_pct=0.0 (L1393); BacktestMetrics.max_win_streak=0 (L1394); BacktestMetrics.max_loss_streak=0 (L1395); BacktestMetrics.avg_trade_duration=0.0 (L1396); BacktestMetrics.hard_drift_pauses=0 (L1402); BacktestMetrics.gross_win_rr=0.0 (L1405); BacktestMetrics.gross_loss_rr=0.0 (L1406); BacktestMetrics.profit_factor=0.0 (L1407); BacktestMetrics.total_return_pct=0.0 (L1408); BacktestMetrics.annualized_return_pct=0.0 (L1409); BacktestMetrics.return_to_max_dd=0.0 (L1410); BacktestMetrics.trades_per_month=0.0 (L1411); BacktestMetrics.htf_candles_per_range=0 (L1419)
- **UNCLASSIFIED**: <module>._ROI_DEFAULTS={...numeric...} (L127); BacktestConfig.pip_size=0.0001 (L220); MultiInstrumentRunner.INSTRUMENT_PIP={...numeric...} (L3885)

### `runtime/bar_structure_snapshot.py` — CONFIG_DRIVEN · config-wired

### `runtime/crt_fail_reason_counters.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: CRTFailReasonCounters.evaluations=0 (L38); CRTFailReasonCounters.events_at_start=0 (L47)

### `runtime/layer_trace.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.DEFAULT_FLUSH_EVERY=200 (L75)

### `runtime/unified_replay_harness.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.INSTRUMENT_PIP={...numeric...} (L28)
