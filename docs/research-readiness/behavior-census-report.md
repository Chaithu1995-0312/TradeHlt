# Behavior Census — live-spine BEHAVIORAL constant inventory

_Generated 2026-06-14T19:39:18.000858+00:00 by `scripts/analysis/behavior_census.py` (read-only)._

**Totals** — BEHAVIORAL 62 · STRUCTURAL 29 · GOAL_SEEKING 9 · UNCLASSIFIED 35

**Maturity ladder** (behavior) — CONFIG_DRIVEN 11 · CONFIG_WIRED 8 · HARD_CODED 3  _(GOAL_SEEKING is orthogonal, not a rung)_

## Maturity by module (behavioral modules)

_Behavioral = all behavioral literals; Hardcoded = genuine debt (neither in-file- nor externally-wired); Ext-wired = config-injected by a consumer/schema class._

| Module | Behavioral | Ext-wired | Hardcoded | Maturity | Goal-seeking |
|---|---|---|---|---|---|
| `config_layer/crt_engine_v2.py` | 24 | 24 | 0 | CONFIG_WIRED | yes |
| `config_layer/crt_gaussian_scorer.py` | 3 | 0 | 0 | CONFIG_WIRED | - |
| `config_layer/crt_sweep_taxonomy.py` | 0 | 0 | 0 | CONFIG_DRIVEN | yes |
| `core/acceptance_controller.py` | 2 | 0 | 0 | CONFIG_WIRED | - |
| `core/convergence_controller.py` | 9 | 0 | 0 | CONFIG_WIRED | - |
| `core/dynamic_threshold.py` | 0 | 0 | 0 | CONFIG_DRIVEN | - |
| `core/fusion_engine.py` | 13 | 13 | 0 | CONFIG_WIRED | - |
| `core/hierarchical_meta_fusion.py` | 1 | 0 | 1 | HARD_CODED | - |
| `core/model_registry.py` | 1 | 0 | 0 | CONFIG_WIRED | - |
| `core/regime_governor.py` | 4 | 0 | 0 | CONFIG_WIRED | - |
| `core/signal_audit.py` | 1 | 0 | 1 | HARD_CODED | - |
| `core/signal_belief_tracker.py` | 1 | 0 | 1 | HARD_CODED | - |
| `engines/live_engine.py` | 3 | 1 | 0 | CONFIG_WIRED | - |

## Future config opportunities (GENUINE HARD_CODED debt — excludes externally-wired)

- `core/hierarchical_meta_fusion.py:127 _DEFAULT_WEIGHTS={...numeric...}`
- `core/signal_audit.py:36 _TRADE_RATE_WARN=0.3`
- `core/signal_belief_tracker.py:76 _DEFAULT_DECAY=0.7`

## Per-module

### `config_layer/crt_engine_v2.py` — CONFIG_WIRED · NOT config-wired
- **BEHAVIORAL**: CRTConfig.body_ratio_min=0.7 (L310); CRTConfig.atr_multiplier_min=1.5 (L311); CRTConfig.retest_depth_max=0.25 (L312); CRTConfig.score_decay_lambda=0.05 (L336); CRTConfig.score_threshold=0.45 (L339); CRTConfig.max_spread_pct=0.05 (L340); CRTConfig.confirmation_body_min=0.6 (L343); CRTConfig.tp1_atr_multiplier=1.0 (L345); CRTConfig.tp2_atr_multiplier=2.0 (L346); CRTConfig.breakout_disp_threshold=1.5 (L356); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L358); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L359); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L361); CRTConfig.bitnet_main_threshold=0.55 (L362); CRTConfig.retrace_reset_pct=0.5 (L378); CRTConfig.conf_alpha=0.7 (L385); CRTConfig.conf_beta=0.3 (L386); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L387); CRTConfig.conf_floor=0.2 (L388); CRTConfig.weak_link_weight=0.3 (L389); CRTConfig.tier_1_threshold=0.75 (L394); CRTConfig.tier_2_threshold=0.3 (L395); CRTConfig.soft_conf_max_candles=3 (L396); CRTConfig.shadow_age_penalty_lambda=0.0 (L417)
- **STRUCTURAL**: Candle.volume=0.0 (L101); Candle.index=0 (L102); SweepEvent.candle_index=0 (L192); RiskScore.breakout_score=0.0 (L203); RiskScore.retest_score=0.0 (L204); RiskScore.time_score=0.0 (L205); RiskScore.decay_factor=1.0 (L206); Trade.risk_pct=0.01 (L230); Trade.pnl=0.0 (L234); Trade.partial_pnl=0.0 (L235); Trade.open_candle_index=0 (L238); EngineState.atr=0.0 (L255); EngineState.retest_candle_index=0 (L258); EngineState.current_candle_index=0 (L259); EngineState.soft_conf_candles=0 (L264); EngineState.ema_fast_val=0.0 (L267); EngineState.ema_slow_val=0.0 (L268); EngineState.htf_remaining_candles=0 (L270); EngineState._displacement_entry_idx=0 (L271); EngineState.pending_displacement_ttl=0 (L275); EngineState.pending_displacement_formed_idx=0 (L277); EngineState.pending_displacement_age_at_reset=0 (L278); CRTConfig.atr_period=14 (L315); CRTConfig.atr_buffer_multiplier=3 (L316); CRTConfig.sl_atr_buffer=0.2 (L344)
- **GOAL_SEEKING**: RiskScore.sweep_score=0.0 (L202); EngineState._expansion_entry_idx=0 (L284); CRTConfig.max_sweep_age_candles=20 (L319); CRTConfig.expansion_atr_min_distance=0.2 (L322); CRTConfig.tp1_atr_multiplier_liq_sweep=1.2 (L360); CRTConfig.max_expansion_age_candles=495 (L408); CRTConfig.max_expansion_age_hours=124 (L409); CRTConfig.expansion_age_warn_candles=342 (L410)
- **UNCLASSIFIED**: CRTConfig.retest_atr_depth_fraction=0.5 (L325); CRTConfig.max_displacement_strength=2.0 (L333); CRTConfig.atr_min_displacement=1.2 (L342); CRTConfig.extension_reset_fib=1.618 (L379); CRTConfig.news_blackout_minutes=15 (L382); CRTConfig.ema_fast=2 (L390); CRTConfig.ema_slow=5 (L391); CRTConfig.pending_displacement_ttl_candles=4 (L401); CRTConfig.shadow_age_norm_candles=0 (L424)
- **EXTERNALLY-WIRED** (config-injected, not debt): CRTConfig.body_ratio_min=0.7 (L310); CRTConfig.atr_multiplier_min=1.5 (L311); CRTConfig.retest_depth_max=0.25 (L312); CRTConfig.score_decay_lambda=0.05 (L336); CRTConfig.score_threshold=0.45 (L339); CRTConfig.max_spread_pct=0.05 (L340); CRTConfig.confirmation_body_min=0.6 (L343); CRTConfig.tp1_atr_multiplier=1.0 (L345); CRTConfig.tp2_atr_multiplier=2.0 (L346); CRTConfig.breakout_disp_threshold=1.5 (L356); CRTConfig.tp1_atr_multiplier_breakout=1.5 (L358); CRTConfig.tp1_atr_multiplier_pullback=0.8 (L359); CRTConfig.tp1_atr_multiplier_reversal=1.0 (L361); CRTConfig.bitnet_main_threshold=0.55 (L362); CRTConfig.retrace_reset_pct=0.5 (L378); CRTConfig.conf_alpha=0.7 (L385); CRTConfig.conf_beta=0.3 (L386); CRTConfig.conf_weights=[0.35, 0.35, 0.15, 0.15] (L387); CRTConfig.conf_floor=0.2 (L388); CRTConfig.weak_link_weight=0.3 (L389); CRTConfig.tier_1_threshold=0.75 (L394); CRTConfig.tier_2_threshold=0.3 (L395); CRTConfig.soft_conf_max_candles=3 (L396); CRTConfig.shadow_age_penalty_lambda=0.0 (L417)

### `config_layer/crt_gaussian_scorer.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: CRTGaussianScorer.RETEST_MIN=0.025 (L44); CRTGaussianScorer.RETEST_MAX=1.0 (L45); CRTGaussianScorer.DISP_MAX=3.67 (L46)

### `config_layer/crt_sweep_taxonomy.py` — CONFIG_DRIVEN · NOT config-wired
- **GOAL_SEEKING**: <module>.WICK_BONUS_FACTOR=0.35 (L33)

### `config_layer/llm_inference_client.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L112)

### `config_layer/llm_scorer.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.FAIL_COUNT=0 (L49)

### `config_layer/market_router.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.CRYPTO_CONFIG={...numeric...} (L12); <module>.FOREX_CONFIG={...numeric...} (L20)

### `config_layer/rr/rr_dataset_builder.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>.MIN_SAMPLES=20 (L37)

### `core/acceptance_controller.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._THETA_MIN=0.5 (L34); <module>._THETA_MAX=0.95 (L35)
- **UNCLASSIFIED**: <module>._MIN_HISTORY=10 (L38); <module>._DEFAULTS={...numeric...} (L41)

### `core/convergence_controller.py` — CONFIG_WIRED · config-wired
- **BEHAVIORAL**: <module>._WARMUP_BARS=10 (L39); <module>._THRESH_MIN=0.3 (L42); <module>._THRESH_MAX=0.9 (L43); <module>._THRESH_STEP=0.02 (L44); <module>._ACCEPT_RATE_HIGH=0.3 (L47); <module>._ACCEPT_RATE_LOW=0.1 (L48); <module>._ABS_QUALITY_FLOOR=0.3 (L54); <module>._SIG_K=8.0 (L57); <module>._SIG_T=0.6 (L58)

### `core/decision_engine.py` — CONFIG_DRIVEN · config-wired
- **STRUCTURAL**: DecisionResult.threshold_used=0.0 (L45)
- **UNCLASSIFIED**: <module>._FALLBACK_TOP_N=3 (L33)

### `core/dynamic_threshold.py` — CONFIG_DRIVEN · config-wired

### `core/engine_runner.py` — CONFIG_DRIVEN · config-wired
- **UNCLASSIFIED**: <module>.DUAL_ENGINE_DEFAULTS={...numeric...} (L78)

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
- **BEHAVIORAL**: LiveEngineConfig.rr_threshold=1.5 (L364); LiveEngineConfig.confidence_min=0.55 (L365); LiveEngineConfig.ml_override_threshold=0.75 (L367)
- **UNCLASSIFIED**: LiveEngineConfig.confidence_strong=0.6 (L366); LiveEngineConfig.alert_cooldown_seconds=60 (L368); LiveEngineConfig.dedup_candles=4 (L369); <module>._BYPASS_CHECK_COUNTER=0 (L612); <module>._BYPASS_CHECK_EVERY_N=50 (L613)
- **EXTERNALLY-WIRED** (config-injected, not debt): LiveEngineConfig.rr_threshold=1.5 (L364)

### `engines/rr_engine.py` — CONFIG_DRIVEN · NOT config-wired
- **UNCLASSIFIED**: <module>._EPS=1e-09 (L33)
