# Behavior Census — live-spine BEHAVIORAL constant inventory

_Generated 2026-07-29T05:17:49.387395+00:00 by `scripts/analysis/behavior_census.py` (read-only)._

**Totals** — BEHAVIORAL 75 · STRUCTURAL 87 · GOAL_SEEKING 14 · UNCLASSIFIED 99

**Maturity ladder** (behavior) — CONFIG_DRIVEN 32 · CONFIG_WIRED 10 · HARD_CODED 8  _(GOAL_SEEKING is orthogonal, not a rung)_

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
| `core/signal_audit.py` | 1 | 0 | 1 | HARD_CODED | - |
| `core/signal_belief_tracker.py` | 1 | 0 | 1 | HARD_CODED | - |
| `engines/live_engine.py` | 3 | 0 | 0 | CONFIG_WIRED | - |
| `features/crt_state_resolver.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `features/dataset_builder.py` | 1 | 0 | 1 | HARD_CODED | - |
| `features/feature_monitor.py` | 1 | 0 | 1 | HARD_CODED | - |
| `governance/expansion_integration.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `governance/multi_strategy_validator.py` | 1 | 0 | 1 | HARD_CODED | - |
| `governance/strategy_backtest.py` | 2 | 1 | 1 | HARD_CODED | - |
| `journal/trade_logger.py` | 1 | 0 | 1 | HARD_CODED | - |
| `runtime/backtest_v2.py` | 3 | 2 | 0 | CONFIG_WIRED | - |

## Future config opportunities (GENUINE HARD_CODED debt — excludes externally-wired)

- `core/hierarchical_meta_fusion.py:127 _DEFAULT_WEIGHTS={...numeric...}`
- `core/signal_audit.py:36 _TRADE_RATE_WARN=0.3`
- `core/signal_belief_tracker.py:76 _DEFAULT_DECAY=0.7`
- `features/dataset_builder.py:185 LAMBDA_DECAY_DEFAULT=0.0`
- `features/feature_monitor.py:60 DEFAULT_DRIFT_THRESHOLD=2.5`
- `governance/multi_strategy_validator.py:57 _MIN_PORTFOLIO_WIN_RATE=0.3`
- `governance/strategy_backtest.py:50 _WARMUP=60`
- `journal/trade_logger.py:25 MAX_CORRUPTION_RATIO=0.1`

## Per-module

### `config_layer/config_validator.py` — CONFIG_DRIVEN · config-wired

### `config_layer/crt_engine_v2.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: Candle.volume=0.0 (L81); Candle.index=0 (L82); SweepEvent.candle_index=0 (L175); RiskScore.breakout_score=0.0 (L186); RiskScore.retest_score=0.0 (L187); RiskScore.time_score=0.0 (L188); RiskScore.decay_factor=1.0 (L189); RiskScore.weights=[0.35, 0.25, 0.2, 0.2] (L195); Trade.risk_pct=0.01 (L219); Trade.pnl=0.0 (L223); Trade.partial_pnl=0.0 (L224); Trade.open_candle_index=0 (L227); EngineState.atr_abs=0.0 (L249); EngineState.retest_candle_index=0 (L252); EngineState.current_candle_index=0 (L253); EngineState.soft_conf_candles=0 (L258); EngineState.ema_fast_val=0.0 (L261); EngineState.ema_slow_val=0.0 (L262); EngineState.htf_remaining_candles=0 (L264); EngineState._displacement_entry_idx=0 (L265); EngineState.pending_displacement_ttl=0 (L269); EngineState.pending_displacement_formed_idx=0 (L271); EngineState.pending_displacement_age_at_reset=0 (L272)
- **GOAL_SEEKING**: RiskScore.sweep_score=0.0 (L185); EngineState._expansion_entry_idx=0 (L278)

### `config_layer/crt_gaussian_scorer.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: CRTGaussianScorer.RETEST_MIN=0.025 (L48); CRTGaussianScorer.RETEST_MAX=1.0 (L49); CRTGaussianScorer.DISP_MAX=3.67 (L50)

### `config_layer/crt_sweep_taxonomy.py` — CONFIG_DRIVEN · NOT config-wired
- **GOAL_SEEKING**: <module>.WICK_BONUS_FACTOR=0.35 (L33)

### `config_layer/llm_inference_client.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L112)

### `config_layer/llm_scorer.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L49)

### `config_layer/rr/rr_dataset_builder.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.MIN_SAMPLES=20 (L38)

### `config_layer/rr/rr_pattern_miner.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>.RR_SCORE_MIN=-3.0 (L46); <module>.RR_SCORE_MAX=5.0 (L47)

### `config_layer/state_identity.py` — CONFIG_WIRED · NOT config-wired
- **BEHAVIORAL**: CRTConfig.body_ratio_min=0.7 (L90); CRTConfig.atr_multiplier_min=1.5 (L91); CRTConfig.retest_depth_max=0.25 (L92); CRTConfig.risk_score_weights=[0.35, 0.25, 0.2, 0.2] (L120); CRTConfig.score_component_weights=[0.35, 0.25, 0.2, 0.2] (L121); CRTConfig.score_decay_lambda=0.05 (L132); CRTConfig.score_threshold=0.45 (L135); CRTConfig.max_spread_pct=0.05 (L136); CRTConfig.confirmation_body_min=0.6 (L139); CRTConfig.tp1_atr_multiplier=1.0 (L141); CRTConfig.tp2_atr_multiplier=2.0 (L142); CRTConfig.breakout_disp_threshold=1.5 (L152); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L154); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L155); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L157); CRTConfig.bitnet_main_threshold=0.55 (L158); CRTConfig.retrace_reset_pct=0.5 (L174); CRTConfig.conf_alpha=0.7 (L181); CRTConfig.conf_beta=0.3 (L182); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L183); CRTConfig.conf_floor=0.2 (L184); CRTConfig.weak_link_weight=0.3 (L185); CRTConfig.tier_1_threshold=0.75 (L190); CRTConfig.tier_2_threshold=0.3 (L191); CRTConfig.soft_conf_max_candles=3 (L192); CRTConfig.shadow_age_penalty_lambda=0.0 (L213)
- **STRUCTURAL**: CRTConfig.atr_period=14 (L95); CRTConfig.atr_buffer_multiplier=3 (L96); CRTConfig.sl_atr_buffer=0.2 (L140)
- **GOAL_SEEKING**: CRTConfig.max_sweep_age_candles=20 (L99); CRTConfig.expansion_atr_min_distance=0.2 (L102); CRTConfig.tp1_atr_multiplier_liq_sweep=1.2 (L156); CRTConfig.max_expansion_age_candles=495 (L204); CRTConfig.max_expansion_age_hours=124 (L205); CRTConfig.expansion_age_warn_candles=342 (L206)
- **UNCLASSIFIED**: CRTConfig.retest_atr_depth_fraction=0.5 (L105); CRTConfig.retest_min_depth_atr_fraction=0.1 (L110); CRTConfig.max_displacement_strength=2.0 (L129); CRTConfig.atr_min_displacement=1.2 (L138); CRTConfig.extension_reset_fib=1.618 (L175); CRTConfig.news_blackout_minutes=15 (L178); CRTConfig.ema_fast=2 (L186); CRTConfig.ema_slow=5 (L187); CRTConfig.pending_displacement_ttl_candles=4 (L197); CRTConfig.shadow_age_norm_candles=0 (L220)
- **EXTERNALLY-WIRED** (config-injected, not debt): CRTConfig.body_ratio_min=0.7 (L90); CRTConfig.atr_multiplier_min=1.5 (L91); CRTConfig.retest_depth_max=0.25 (L92); CRTConfig.risk_score_weights=[0.35, 0.25, 0.2, 0.2] (L120); CRTConfig.score_component_weights=[0.35, 0.25, 0.2, 0.2] (L121); CRTConfig.score_decay_lambda=0.05 (L132); CRTConfig.score_threshold=0.45 (L135); CRTConfig.max_spread_pct=0.05 (L136); CRTConfig.confirmation_body_min=0.6 (L139); CRTConfig.tp1_atr_multiplier=1.0 (L141); CRTConfig.tp2_atr_multiplier=2.0 (L142); CRTConfig.breakout_disp_threshold=1.5 (L152); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L154); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L155); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L157); CRTConfig.bitnet_main_threshold=0.55 (L158); CRTConfig.retrace_reset_pct=0.5 (L174); CRTConfig.conf_alpha=0.7 (L181); CRTConfig.conf_beta=0.3 (L182); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L183); CRTConfig.conf_floor=0.2 (L184); CRTConfig.weak_link_weight=0.3 (L185); CRTConfig.tier_1_threshold=0.75 (L190); CRTConfig.tier_2_threshold=0.3 (L191); CRTConfig.soft_conf_max_candles=3 (L192); CRTConfig.shadow_age_penalty_lambda=0.0 (L213)

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

### `core/signal_audit.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>._TRADE_RATE_WARN=0.3 (L36)
- **UNCLASSIFIED**: <module>._ZONE_PASS_WARN=0.8 (L34); <module>._FUSION_PASS_WARN=0.5 (L35)
- **GENUINE HARD_CODED**: <module>._TRADE_RATE_WARN=0.3 (L36)

### `core/signal_belief_tracker.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: SignalBeliefTracker._DEFAULT_DECAY=0.7 (L76)
- **UNCLASSIFIED**: SignalBeliefTracker._DEFAULT_HIGH_CONVICTION=0.65 (L77); SignalBeliefTracker._DEFAULT_MIN_CONFIRMS=2 (L78)
- **GENUINE HARD_CODED**: SignalBeliefTracker._DEFAULT_DECAY=0.7 (L76)

### `core/ultron_risk_gate_wrapper.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._DEFAULT_REGIME_FACTORS={...numeric...} (L48)

### `engines/live_engine.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: LiveEngineConfig.rr_threshold=1.5 (L469); LiveEngineConfig.confidence_min=0.55 (L470); LiveEngineConfig.ml_override_threshold=0.75 (L472)
- **UNCLASSIFIED**: LiveEngineConfig.confidence_strong=0.6 (L471); LiveEngineConfig.alert_cooldown_seconds=60 (L473); LiveEngineConfig.dedup_candles=4 (L474); <module>._BYPASS_CHECK_COUNTER=0 (L717); <module>._BYPASS_CHECK_EVERY_N=50 (L718)

### `engines/rr_engine.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._EPS=1e-09 (L33)

### `engines/scoring_engine.py` — CONFIG_DRIVEN · NOT config-wired

### `engines/zone_gate_engine.py` — CONFIG_DRIVEN · NOT config-wired

### `features/causal_structure.py` — CONFIG_DRIVEN · NOT config-wired

### `features/crt_feature_builder.py` — CONFIG_DRIVEN · NOT config-wired

### `features/crt_state_resolver.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: CRTStateMemory.htf_bars_in_window=0 (L123)
- **GOAL_SEEKING**: CRTStateMemory.sweep_candle_index=-1 (L108); CRTStateMemory.expansion_entry_index=-1 (L113)
- **UNCLASSIFIED**: CRTStateMemory.displacement_candle_index=-1 (L109); CRTStateMemory.displacement_candle_close=0.0 (L110); CRTStateMemory.displacement_direction=0 (L111); CRTStateMemory.retest_candle_index=-1 (L112); CRTStateMemory.pending_displacement_formed_idx=-1 (L116); CRTStateMemory.pending_displacement_ttl=0 (L118); CRTStateMemory.candle_index=0 (L120); CRTStateMemory.htf_reset_count=0 (L126); CRTStateMemory.gap_reset_count=0 (L127); CRTStateMemory.forced_reset_count=0 (L128)

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
- **STRUCTURAL**: <module>.SCHEMA_V2_FEATURE_DIM=35 (L108); <module>.CANONICAL_FEATURE_DIM=39 (L114); <module>.SCHEMA_V3_FEATURE_DIM=38 (L117)
- **UNCLASSIFIED**: <module>.SESSION_UNKNOWN=-1.0 (L167); <module>.TREND_MAP={...numeric...} (L169)

### `features/model_evidence.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: <module>._VALUE_PRECISION=6 (L64)

### `features/session_classifier.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: SessionOrdinal.ASIA=0 (L59); SessionOrdinal.LONDON=1 (L60); SessionOrdinal.NEWYORK=2 (L61); SessionOrdinal.OVERLAP=3 (L62); SessionOrdinal.CLOSED=4 (L63); <module>.DEFAULT_SESSION_WINDOWS_UTC={...numeric...} (L91)

### `governance/expansion_integration.py` — CONFIG_DRIVEN · NOT config-wired
- **GOAL_SEEKING**: <module>._MIN_TRADES=30 (L27); <module>._MAX_DRAWDOWN=0.25 (L28); <module>._MAX_DD_MULTIPLIER=1.2 (L31)

### `governance/framework_registry.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: <module>._DRIFT_WINDOW=30 (L60)
- **UNCLASSIFIED**: <module>._TYPE_LEVEL={...numeric...} (L44)

### `governance/multi_strategy_validator.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>._MIN_PORTFOLIO_WIN_RATE=0.3 (L57)
- **UNCLASSIFIED**: <module>._MIN_STRATEGY_TRADES=5 (L56); <module>._MAX_PORTFOLIO_DRAWDOWN=75000000.0 (L58)
- **GENUINE HARD_CODED**: <module>._MIN_PORTFOLIO_WIN_RATE=0.3 (L57)

### `governance/portfolio_validation.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: InstrumentConfig.htf_candles=16 (L57)

### `governance/promotion_manager.py` — CONFIG_DRIVEN · config-wired

### `governance/shadow_promotion_gate.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._DEFAULT_MIN_SHADOW_TRADES=30 (L49)

### `governance/strategy_backtest.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>._WARMUP=60 (L50); StrategyMetrics.win_rate=0.0 (L66)
- **UNCLASSIFIED**: <module>._USD_TO_INR=84.0 (L49); <module>._MAX_FWD=40 (L51); StrategyMetrics.trade_count=0 (L58); StrategyMetrics.win_count=0 (L59); StrategyMetrics.loss_count=0 (L60); StrategyMetrics.timeout_count=0 (L61); StrategyMetrics.total_pnl_inr=0.0 (L62); StrategyMetrics.gross_profit=0.0 (L63); StrategyMetrics.gross_loss=0.0 (L64); StrategyMetrics.max_drawdown=0.0 (L65); StrategyMetrics.profit_factor=0.0 (L67); StrategyMetrics.expectancy_inr=0.0 (L68); StrategyMetrics.score=0.0 (L69)
- **EXTERNALLY-WIRED** (config-injected, not debt): StrategyMetrics.win_rate=0.0 (L66)
- **GENUINE HARD_CODED**: <module>._WARMUP=60 (L50)

### `journal/schema.py` — CONFIG_DRIVEN · NOT config-wired
- **STRUCTURAL**: TradeRecord.confidence=0.0 (L20); TradeRecord.rr=0.0 (L21); TradeRecord.zone=0.0 (L22); TradeRecord.allocated_risk=0.0 (L25); TradeRecord.portfolio_exposure_before=0.0 (L26); TradeRecord.pnl=0.0 (L34); TradeRecord.duration_candles=0 (L35); TradeRecord.drawdown_at_entry=0.0 (L36)

### `journal/trade_logger.py` — HARD_CODED · NOT config-wired
- **BEHAVIORAL**: <module>.MAX_CORRUPTION_RATIO=0.1 (L25)
- **GENUINE HARD_CODED**: <module>.MAX_CORRUPTION_RATIO=0.1 (L25)

### `runtime/analyze_fusion_shadow.py` — CONFIG_DRIVEN · NOT config-wired

### `runtime/backtest_bitnet.py` — CONFIG_DRIVEN · NOT config-wired

### `runtime/backtest_v2.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: BacktestMetrics.max_drawdown_pct=0.0 (L1190); BacktestMetrics.total_return_pct=0.0 (L1205); BacktestMetrics.annualized_return_pct=0.0 (L1206)
- **STRUCTURAL**: TradePathStats.mfe_price=0.0 (L262); TradePathStats.mae_price=0.0 (L263); TradePathStats.bars_to_peak=0 (L264); TradePathStats.bars_to_trough=0 (L265); TradePathStats.bars_observed=0 (L266); TradePathStats.mfe_rr=0.0 (L268); TradePathStats.mae_rr=0.0 (L269); TradeRecord.entry_price_fill=0.0 (L302); TradeRecord.exit_price_fill=0.0 (L303); TradeRecord.candle_open=0 (L307); TradeRecord.candle_close=0 (L308); TradeRecord.pnl_pips_raw=0.0 (L310); TradeRecord.pnl_pips_net=0.0 (L311); TradeRecord.pnl_rr_raw=0.0 (L312); TradeRecord.pnl_rr_net=0.0 (L313); TradeRecord.slippage_pips=0.0 (L314); TradeRecord.spread_pips=0.0 (L315); TradeRecord.capital_before=0.0 (L317); TradeRecord.capital_after=0.0 (L318); TradeRecord.position_size=0.0 (L319); TradeRecord.risk_score=0.0 (L321); TradeRecord.risk_pct=0.0 (L322); TradeRecord.week_of_year=0 (L327); TradeRecord.day_of_week=0 (L328); TradeRecord.hour_of_day=0 (L329); TradeRecord.live_atr=0.0 (L335); TradeRecord.live_ema_fast=0.0 (L336); TradeRecord.live_ema_slow=0.0 (L337); TradeRecord.cached_retest_depth=0.0 (L338); TradeRecord.cached_body_ratio=0.0 (L339); TradeRecord.cached_disp_strength=0.0 (L340); TradeRecord.bitnet_score_at_entry=0.0 (L347); RejectionRecord.risk_score=0.0 (L379)
- **UNCLASSIFIED**: <module>._ROI_DEFAULTS={...numeric...} (L123); BacktestConfig.pip_size=0.0001 (L174); BacktestMetrics.total_candles=0 (L1178); BacktestMetrics.gap_resets=0 (L1179); BacktestMetrics.total_setups=0 (L1180); BacktestMetrics.approved_trades=0 (L1181); BacktestMetrics.rejected_trades=0 (L1182); BacktestMetrics.wins=0 (L1183); BacktestMetrics.losses=0 (L1184); BacktestMetrics.tp1_hits=0 (L1185); BacktestMetrics.tp2_hits=0 (L1186); BacktestMetrics.total_pnl_rr_raw=0.0 (L1187); BacktestMetrics.total_pnl_rr_net=0.0 (L1188); BacktestMetrics.max_drawdown_rr=0.0 (L1189); BacktestMetrics.max_win_streak=0 (L1191); BacktestMetrics.max_loss_streak=0 (L1192); BacktestMetrics.avg_trade_duration=0.0 (L1193); BacktestMetrics.hard_drift_pauses=0 (L1199); BacktestMetrics.gross_win_rr=0.0 (L1202); BacktestMetrics.gross_loss_rr=0.0 (L1203); BacktestMetrics.profit_factor=0.0 (L1204); BacktestMetrics.return_to_max_dd=0.0 (L1207); BacktestMetrics.trades_per_month=0.0 (L1208); MultiInstrumentRunner.INSTRUMENT_PIP={...numeric...} (L2888)
- **EXTERNALLY-WIRED** (config-injected, not debt): BacktestMetrics.max_drawdown_pct=0.0 (L1190); BacktestMetrics.total_return_pct=0.0 (L1205)

### `runtime/crt_fail_reason_counters.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: CRTFailReasonCounters.evaluations=0 (L38); CRTFailReasonCounters.events_at_start=0 (L47)

### `runtime/unified_replay_harness.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.INSTRUMENT_PIP={...numeric...} (L28)
