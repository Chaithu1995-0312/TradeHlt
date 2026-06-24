# Dependency Graph

> **Who consumes what, what breaks if you change something.**
>
> For each major subsystem: consumed-from relationships, emitted-to relationships,
> config dependencies, critical invariants, and test coverage.
>
> Last updated: 2026-06-10

---

## Conventions

- **Consumes From** — Modules or config sections this subsystem reads at runtime
- **Emits To** — Modules that call or receive data from this subsystem
- **Config Section** — The key(s) in `v2_multi_2026_04.json` that affect this subsystem
- **Critical Invariant** — A condition that, if violated, causes silent corruption (not just a crash)
- **Tests** — Test files that cover this subsystem

---

## Core Trading Spine

### EngineRunner

| Field | Value |
|-------|-------|
| **Module** | `src/core/engine_runner.py` |
| **Role** | Top-level orchestrator. Every decision path passes through here. |
| **Consumes From** | CRTEngine, HeuristicGaussianEngine/MLGaussianEngine, ZoneGateEngine, RREngine, FusionEngine, DecisionEngine, TrapValidatorEngine, RegimeGovernor, input_data dict |
| **Emits To** | FusionEngine.compute(), DecisionEngine.evaluate(), Collector.log(), AcceptanceController |
| **Config Section** | `engine_runner`, `engine_runner.dual_engine` |
| **Key Config Keys** | `ultron_gate_enabled` (reads: line 421, checks: line 853), `fusion_compare_evaluate`, `fusion_use_evaluate`, `model_path` |
| **Critical Invariant** | `EXPECTED_ENGINES` set must always match the 4 engines actually run. Adding/removing an engine requires updating this set AND the FusionEngine weight matrix. |
| **Critical Invariant** | `ultron_gate_enabled: false` in backtest ≠ `true` in live. Backtest results are non-representative. |
| **Critical Invariant** | `input_data["direction"]` must be set for direction-aware Gaussian scoring. Defaults to "long" when absent. |
| **Tests** | `test_engine_runner_dual_gate.py`, `test_engine_runner_rr_fusion.py` |
| **Breakage If** | You change the FusionEngine output shape, add/remove an engine from EXPECTED_ENGINES, or change how input_data is constructed upstream. |

**8-Step Execution Order (from SIGNAL_FLOW.md):**
1. TrapValidatorEngine gate
2. 4 engines run unconditionally (+ optional RRFusionLayer)
3. Completeness check (EXPECTED_ENGINES set diff)
4. FusionEngine.compute() + optional evaluate() shadow
5. Fusion baseline gate (fusion_min_score=0.25)
6. Dual-engine regime gate (RegimeGovernor)
7. DecisionEngine.evaluate() — sole emitter of "execute"|"reject"
8. Collector.log() + AcceptanceController update

---

### CRTEngine

| Field | Value |
|-------|-------|
| **Module** | `src/config_layer/crt_engine_v2.py` (+ `crt_engine.py` logging wrapper) |
| **Role** | CRT state machine: sweep detection, displacement, expansion, retest, execution. 9 states. |
| **Consumes From** | OHLCV candle data, CRTConfig (from prod config), SweepEvent, RangeDetector, StateMachine |
| **Emits To** | ScoringEngine.compute_scores() → fusion score, TelemetryCollector events, BacktestRunner.on_trade_opened() |
| **Config Section** | `crt_engine` |
| **Key Config Keys** | `shadow_age_penalty_lambda`, `shadow_advisory_only`, `pending_displacement_ttl_candles`, `session_windows`, `sizing_bands`, all state-machine params, `use_bitnet` |
| **Critical Invariant** | State transitions must follow the 9-state graph exactly. VALID_TRANSITIONS at `crt_engine_v2.py:981-991`. |
| **Critical Invariant** | SHADOW_LEAK must be 0 — no shadow candidate escapes without going through the full SHADOW_PENDING → expansion path. |
| **Critical Invariant** | TelemetryCollector is a passive sidecar — zero behavior change. It must never modify engine state. |
| **Tests** | CRT-related tests, `test_crt_fixes.py`, `test_crt_session_filter.py`, `test_p4_observability.py` |
| **Breakage If** | You change state transitions without updating VALID_TRANSITIONS and EVENT_TAXONOMY.md. |

---

### FusionEngine

| Field | Value |
|-------|-------|
| **Module** | `src/core/fusion_engine.py` |
| **Role** | Combines 4 engine scores (CRT, Gaussian, Zone Gate, RR) into weighted fusion output. |
| **Consumes From** | EngineRunner (4 engine results), config weights, optional StrategyOrchestrator consensus |
| **Emits To** | EngineRunner Step 5 (fusion baseline gate), DecisionEngine |
| **Config Section** | `fusion_engine` |
| **Key Config Keys** | `weight_crt=0.4`, `weight_gaussian=0.2`, `weight_zone_gate=0.2`, `weight_rr=0.2`, `regime_fusion_weights.*` (NOT consumed), `weight_strategy_consensus=0.0` |
| **Critical Invariant** | `weight_strategy_consensus=0.0` means `fuse_strategy_results()` is dormant. Changing this weight activates the multi-strategy fusion path. |
| **Critical Invariant** | `regime_fusion_weights` block exists in config but is NOT read by FusionConfig constructor. Regime-adaptive weighting is decoratively configured but not activated. |
| **Critical Invariant** | `fusion_use_evaluate: false` means the evaluate() shadow path is never used. The compute() path is the live gate. |
| **Tests** | `test_engine_runner_rr_fusion.py`, fusion-related tests |
| **Breakage If** | You change the 4-engine score output format, change weight keys in config, or activate regime-adaptive weights without testing per-regime behavior. |

---

### DecisionEngine

| Field | Value |
|-------|-------|
| **Module** | `src/core/decision_engine.py` |
| **Role** | Applies thresholds to fusion output. Sole emitter of "execute" or "reject". |
| **Consumes From** | FusionEngine output, DynamicThreshold, config thresholds |
| **Emits To** | EngineRunner Step 7 (execute/reject decision) |
| **Config Section** | `decision_engine` |
| **Key Config Keys** | `score_threshold: 0.45` (H-Shadow — NOT used, only serves as DynamicThreshold clamp min), `p_win_threshold: 0.4` (used), `rr_threshold: 1.5` (used) |
| **Critical Invariant** | `score_threshold` is an illusion. Effective threshold = DynamicThreshold percentile(scores, 85) clamped [0.45, 0.65]. Changing the config value only changes the clamp floor. |
| **Critical Invariant** | `p_win_threshold` and `rr_threshold` ARE live — read at DecisionEngine init, checked in evaluate(). |
| **Tests** | DecisionEngine tests |
| **Breakage If** | You change DynamicThreshold percentile or clamp values, or change how engine scores enter the evaluate() path. |

---

### ExecutionPlannerV1_2

| Field | Value |
|-------|-------|
| **Module** | `src/config_layer/execution_planner.py` |
| **Role** | Plans trade entry (SL, TP, TTL) per intent. |
| **Consumes From** | config sections, gate_intelligence.compute_crt_levels() |
| **Emits To** | UltronRiskGate (planned trade) |
| **Config Section** | `execution_planner` |
| **Key Config Keys** | Per-intent TP/SL/TTL multipliers |
| **Critical Invariant** | CONFIG_REFERENCE.md §4 is WRONG about `min_rr_ratio`, `default_sl_atr_mult`, `liquidity_*` keys. Planner does NOT read these. SL/TP/RR delegated to gate_intelligence.compute_crt_levels(). Source-confirmed: `execution_planner.py:79-96, 240-241`. |
| **Tests** | `test_execution_planner.py`, `test_execution_planner_replay.py` |
| **Breakage If** | You change gate_intelligence output format or add new SL/TP/TTL parameters. |

---

### UltronRiskGate

| Field | Value |
|-------|-------|
| **Module** | `src/core/ultron_risk_gate.py` |
| **Role** | Capital protection — 7-check waterfall before trade approval. |
| **Consumes From** | ExecutionPlanner output (TradePlan), portfolio state, config |
| **Emits To** | EngineRunner (approve/reject), KillSwitch state file |
| **Config Section** | `ultron_risk_gate` |
| **Key Config Keys** | `disabled: false`, `max_trades_per_day: 10`, `max_daily_loss_pct: 3.0`, `min_rr_ratio: 1.5`, `spread_pips: 0.0`, `slippage_pips: 0.0`, `min_sl_pips: 0.0` |
| **Critical Invariant** | Kill-switch state file path is HARDCODED (`ultron_risk_gate.py:44`), NOT read from config. The `capital_management.kill_switch_daily_loss_inr` config key is dead. |
| **Critical Invariant** | `disabled: true` bypasses ALL risk checks — TTL, RR floor, daily limit, kill switch, portfolio exposure, SL distance. |
| **Tests** | UltronRiskGate tests |
| **Breakage If** | You change the 7-check order, add new checks without updating evaluate(), or change kill-switch file path. |

---

### RegimeGovernor (formerly UltronGovernor)

| Field | Value |
|-------|-------|
| **Module** | `src/core/ultron_gate.py` |
| **Role** | Regime signal filter inside EngineRunner Step 6. CANONICAL NAME: RegimeGovernor. |
| **Consumes From** | Regime classification, dual-engine results, config |
| **Emits To** | EngineRunner Step 6 gate result |
| **Config Section** | `engine_runner` |
| **Key Config Keys** | `ultron_gate_enabled` (controls THIS, not UltronRiskGate) |
| **Critical Invariant** | `ultron_gate_enabled` controls THE GOVERNOR, NOT the risk gate. This was the original naming confusion (fixed 2026-04-28). |
| **Critical Invariant** | At `false`, EngineRunner uses `_regime_governor_legacy()` — no daily quota, no percentile filter, no trade cap. |
| **Tests** | `test_ultron_gate.py` |
| **Breakage If** | You confuse this with UltronRiskGate. They are different modules with different roles. |

---

## Governance Pipeline

### ConfigValidator

| Field | Value |
|-------|-------|
| **Module** | `src/config_layer/config_validator.py` |
| **Role** | Defines what "valid" means. Applies hard gates (min trades, max DD, min fitness) and soft gates. |
| **Consumes From** | Backtest metrics, production config |
| **Emits To** | ValidationReport → PromotionManager |
| **Config Section** | `config_validator` |
| **Key Config Keys** | `min_trades=10`, `max_drawdown=0.35`, `score_threshold=0.15`, `fitness_weights` (keys: expectancy_rr, trade_count_norm, drawdown) |
| **Critical Invariant** | `fitness_weights` in SCHEMAS.md §5.1 is WRONG. Actual keys used by `config_validator.py:132-136` are `expectancy_rr`, `trade_count_norm`, `drawdown` — matching config, not docs. |
| **Tests** | `test_config_integrity.py`, `test_fusion_and_validator_regression.py` |
| **Breakage If** | You change hard gate thresholds without testing, or change fitness_weights key names without updating config. |

### PromotionManager

| Field | Value |
|-------|-------|
| **Module** | `src/governance/promotion_manager.py` |
| **Role** | The ONLY path to production. Promotes configs through governance gate. |
| **Consumes From** | ConfigValidator (ValidationReport), tuner checkpoints, base config |
| **Emits To** | Registry files, promotion_log.jsonl |
| **Config Section** | `governance` |
| **Key Config Keys** | `promotion_margin_pct` (MISSING — hardcoded 2% in model_registry.py) |
| **Critical Invariant** | Sparse tuner entries must NOT be written as full configs. `_load_full_base_config()` must be called before writing. (Bug fixed 2026-04-29.) |
| **Critical Invariant** | Every promoted config carries SHA-256 hash. Rollback: copy not move, update PROD_VERSION, append ROLLBACK to log. |
| **Tests** | Governance tests, `test_sprint7_governance.py` |
| **Breakage If** | You bypass the merge-into-base logic, change registry file format, or skip hash verification. |

---

## Strategy Layer

### StrategyOrchestrator

| Field | Value |
|-------|-------|
| **Module** | `src/strategies/strategy_orchestrator.py` |
| **Role** | Runs all 10 strategies per candle, gates output by completeness + consensus. |
| **Consumes From** | OHLCV data, 10 strategy modules, config weights |
| **Emits To** | EngineRunner context (strategy_consensus_score, strategy_consensus_direction) |
| **Config Section** | `strategy_engine.s01..s10` |
| **Key Config Keys** | `min_signal_strategies=2`, `min_agreement_ratio=0.60`, per-strategy weights and thresholds |
| **Critical Invariant** | `weight_strategy_consensus=0.0` means orchestrator output is NOT consumed by FusionEngine. Orchestrator can be removed without changing trading behavior. |
| **Critical Invariant** | Per-strategy fail-open: an exception in S1 does not crash S2 or the orchestrator. |
| **Tests** | `test_strategy_orchestrator.py` (36 tests) |
| **Breakage If** | You change the strategy interface, add/remove a strategy without updating all 10, or change consensus/complete gates. |

### Strategies S1–S10

| Module | Path | Role |
|--------|------|------|
| S1 CRT Wrapper | `src/strategies/s01_crt_wrapper.py` | Adapter over engines.crt_engine.compute() |
| S2 Mean Rev | `src/strategies/s02_mean_reversion.py` | RSI+BB mean reversion |
| S3 Breakout | `src/strategies/s03_breakout.py` | BOS + swing level + volume ratio |
| S4 Stat Arb | `src/strategies/s04_stat_arb.py` | EMA-spread Z-score |
| S5 Grid | `src/strategies/s05_grid.py` | ATR-grid on swing range |
| S6 Scalping | `src/strategies/s06_scalping.py` | MACD-hist + momentum + session filter |
| S7 News | `src/strategies/s07_news_sentiment.py` | Volatility ratio + zone/trend |
| S8 ML Ensemble | `src/strategies/s08_ml_ensemble.py` | Optional BitNet + weighted feature scorer |
| S9 Pattern | `src/strategies/s09_pattern_recog.py` | Hammer/ShootingStar/Engulfing/Marubozu |
| S10 Trap | `src/strategies/s10_trap_strategy.py` | Bull/bear trap + LIQ_SWEEP |

**Critical Invariant:** All 10 strategies must be importable and instantiatable. The orchestrator assumes all 10 exist.

---

## Training & ML

### Phase5Calibration

| Module | `src/training/phase5_calibration.py` |
|--------|--------------------------------------|
| **Role** | 4-gate quality check on Gaussian models before promotion |
| **Config Section** | `phase5_calibration` (top-level — may be stale), `training` (active) |
| **Key Config Keys** | `val_ratio=0.30`, `min_val_samples=30`, `min_corr=0.10`, `max_cal_error=0.25`, `cv_corr_std_max=0.05`, `cv_n_folds=3` |
| **Critical Invariant** | Top-level `phase5_calibration.min_val_samples` may NOT be consumed. Actual config source may be `training` section. |
| **Critical Invariant** | Direction-mirroring: `--mirror-short-features` must be True for combined long+short training. Without it, training signal cancels (corr drops from +0.2066 to +0.0062). |

### ModelRegistry / GaussianScorer

| Module | `src/core/model_registry.py` |
|--------|------------------------------|
| **Role** | Registry for Gaussian models. Loads active model, applies direction-aware scoring. |
| **Config Section** | None — model loaded from `models/gaussian_registry.json` |
| **Critical Invariant** | Active model: v4_mirrored (corr=+0.2066). Inference-side mirroring constants (`_GMIRROR_NEGATE`, `_GMIRROR_SWAP`) must match training-side constants (`_MIRROR_NEGATE_FEATURES`, `_MIRROR_SWAP_PAIRS`). |
| **Critical Invariant** | Default Gaussian path uses HeuristicGaussianEngine (direction-agnostic). MLGaussianEngine (direction-aware) requires `GAUSSIAN_IMPL=ml` env var. |

---

## AI Agent

### Agent Core

| Module | Path |
|--------|------|
| IntentRouter | `src/agent/intent_router.py` — regex + LLM classification, 14 intents |
| PlanCompiler | `src/agent/plan_compiler.py` — deterministic PLAN_REGISTRY (LLM cannot choose tools or order) |
| Executor | `src/agent/executor.py` — confirm-gate + path-whitelist |
| Tool Registry | `src/agent/tool_registry.py` — 17 tools across 3 modes |
| Audit | `src/agent/audit.py` — per-step + per-session records to `logs/agent_audit.jsonl` |

**Critical Invariants:**
- LLM is advisory only. Every write-tool requires per-call y/N confirmation.
- Path whitelist: only `configs/production/`, `logs/`, `results/` — nothing outside.
- PLAN_REGISTRY is hardcoded. LLM classifies intent and fills args but does not choose execution order.
- 14 intents registered, each with non-empty step list.

---

## Edge Discovery (Research)

| Module | Path | Role |
|--------|------|------|
| Contracts | `src/research/contracts.py` | Signal, Outcome, EdgeReport, MetaProfile |
| Forward Walk | `src/research/measurement/forward_walk.py` | Trailing-stop simulation, no-lookahead |
| Metrics | `src/research/measurement/metrics.py` | EdgeAggregator: WR, PF, expectancy, MFE-MAE |
| Costs | `src/research/measurement/costs.py` | CostModel: flat 12 bps round-trip |
| Controls | `src/research/controls/` | random_baseline, always_long |
| Hypotheses | `src/research/hypotheses/` | expansion_breakout, mean_reversion (both @register_hypothesis) |
| Registry | `src/research/registry.py` | HYPOTHESIS_REGISTRY (instance-based, behavior-blind) |
| Runner | `src/research/runner.py` | HypothesisRunner: deterministic, byte-identical reruns |
| CLI | `src/research/cli.py` | CLI entry point |

**Critical Invariants:**
- Edge Discovery imports ZERO modules from `engine_runner`, `promotion_manager`, or `config_validator`. Isolation is hard-guaranteed (not by convention).
- Determinism: `HypothesisRunner` produces byte-identical `edge_report.json` across runs (proven: 346,082 signals × 2 runs = same sha256).
- Cost model applies NET qualification: all gates run on cost-adjusted RR, not gross.
- Measurement core contains NO `.family` reference — completely behavior-agnostic.

---

## Control Plane

| Component | Path | Role |
|-----------|------|------|
| Registry | `src/control_plane/registry.py` | CommandSpec definitions |
| Job Manager | `src/control_plane/job_manager.py` | Threaded async execution |
| API | `src/control_plane/api.py` | HTTP routes |
| UI | `src/control_plane/ui/` | Browser interface (port 8787) |
| HealthChecker | `src/monitoring/health_checker.py` | HTTP on port 8788 |

**Critical Invariant:** All CLI commands registered in the control plane must match actual `scripts/` entry points. CLI_MATRIX.md is auto-generated from the registry.

---

## Infrastructure

| Component | Path/Role |
|-----------|-----------|
| Dockerfile | Python 3.10-slim, EXPOSE 8787/8788, PYTHONPATH=/app/src |
| Live hook | `src/runtime/live_engine_hook.py` — StrategyOrchestrator + KillSwitch + Telegram + MT5 |
| ConsoleSafe | `src/utils/console_safe.py` — Unicode-safe output for Windows cp1252 |
| Telemetry | Inline in `crt_engine_v2.py` — passive sidecar, 5 event types |

---

## Cross-Module Dependency Summary

```
Candle CSV → CandleLoader
  → FeaturePipeline (35-dim canonical features)
    → EngineRunner
      → TrapValidatorEngine (gate)
      → CRTEngine → ScoringEngine (score: 0.35×sweep + 0.25×breakout + 0.20×retest + 0.20×time)
      → GaussianEngine (heuristic or ML, direction-aware)
      → ZoneGateEngine (BitNet hard mode or soft distance)
      → RREngine (real distance-based)
      → FusionEngine.compute() (weighted fusion)
      → FusionEngine baseline gate (fusion_min_score=0.25)
      → RegimeGovernor (ultron_gate_enabled)
      → DecisionEngine.evaluate() (thresholds + DynamicThreshold)
        → ExecutionPlannerV1_2 (SL/TP/TTL per intent)
          → UltronRiskGate (7-check waterfall)
            → TradeRecord + Collector + telemetry
```

**Async feeders (join at specific spine steps):**
- Governance: AutoTuner → ConfigValidator → PromotionManager → production_config → feeds Steps 3-6
- Training: Trades → DatasetValidator → Trainer → ModelRegistry → models/ → feeds Step 3
- Agent: NL → IntentRouter → PlanCompiler → Executor; Pipeline triggers Steps 1-7, Copilot taps Step 4 read-only
- INOUT: Parallel rail joining only at Step 6 (archived 2026-05-02, may still be active via alternative path)

---

## Source Files for Verification

If this graph conflicts with actual code, the code wins. Key source files to check:

| Subsystem | Primary Source |
|-----------|---------------|
| EngineRunner 8-step order | `src/core/engine_runner.py` lines ~400-900 |
| CRT state transitions | `src/config_layer/crt_engine_v2.py` lines ~981-991 (VALID_TRANSITIONS) |
| FusionConfig constructor | `src/core/fusion_engine.py` or `engine_runner.py` lines ~374-390 |
| DynamicThreshold | `src/core/dynamic_threshold.py` |
| Gateway intelligence wiring | `src/core/gate_intelligence.py` |
| PromotionManager merge | `src/governance/promotion_manager.py` |
| ConfigValidator fitness_weights | `src/config_layer/config_validator.py` lines ~132-136 |
| Research isolation | `src/research/` — no imports of engine_runner/promotion_manager/config_validator |
| Direction mirroring constants | `src/core/model_registry.py` + `scripts/training/phase5_calibration.py` |