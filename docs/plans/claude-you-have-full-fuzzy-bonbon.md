> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# CANONICAL EXECUTION COGNITION GRAPH — Tradelatest

## VERIFICATION METADATA
```
Git SHA:        e05f3846cf9c9e384a88e4f3bc08a4e470df23fe
Branch:         patch
Generated:      2026-05-20
Python:         3.14.3
ACTIVE_VERSION: "v2_multi_2026_04 - deepdeektry"  ← ANOMALY: spaces in name
Production Dir: configs/production/
Methodology:    Source-only. Every claim maps to file + line. NOT VERIFIED IN SOURCE used when unproven.
```

---

# 1. CANONICAL SYSTEM REALITY

## What this repository ACTUALLY is today

A **file-backed, Python ≥3.10 quantitative trading platform** with no database, no message broker, no cloud dependencies. All state is JSON files on disk.

### Production Runtime — CANONICAL
**Path:** CSV → `EngineRunner.run()` → `FusionEngine` → `DecisionEngine` → `UltronRiskGate` → trade decision

**Files:**
- `src/core/engine_runner.py` — orchestrates all 4 scoring engines (CANONICAL, LIVE_PRODUCTION)
- `src/core/fusion_engine.py` — weighted score fusion (CANONICAL)
- `src/core/decision_engine.py` — final EXECUTE/REJECT authority (CANONICAL)
- `src/config_layer/execution_planner.py` — entry/SL/TP derivation (CANONICAL)
- `src/core/ultron_risk_gate.py` — position-level risk gate (CANONICAL)

**Active production config:** `configs/production/v2_multi_2026_04 - deepdeektry.json`
**Active version pointer:** `configs/production/ACTIVE_VERSION` → `"v2_multi_2026_04 - deepdeektry"`

> ⚠️ ANOMALY: The ACTIVE_VERSION string contains spaces and a dash. Expected format: `v2_multi_2026_04`. This may cause path resolution issues on some OS/filesystem combinations if the string is used directly in file paths.

### Replay Runtime — CANONICAL (backtest_v2)
**File:** `src/runtime/backtest_v2.py` — `BacktestRunner` (CANONICAL)
**Duplicate paths (EXPERIMENTAL/PARTIALLY_CONNECTED):**
- `src/runtime/backtest_bitnet.py` — BitNet gate mode evaluation (EXPERIMENTAL)
- `src/runtime/unified_replay_harness.py` — Layer A + Layer B parallel run (EXPERIMENTAL)
- `src/governance/strategy_backtest.py` — per-strategy backtester, different schema (PARTIALLY_CONNECTED)

### Governance Runtime — GOVERNANCE_CRITICAL
- `src/governance/orchestrator.py` — GovernanceOrchestrator (GOVERNANCE_CRITICAL)
- `src/governance/shadow_promotion_gate.py` — ShadowPromotionGate (GOVERNANCE_CRITICAL)
- `src/governance/promotion_manager.py` — three promotion paths (GOVERNANCE_CRITICAL)
- `src/governance/reflection_buffer_advanced.py` — data → prompt pipeline (GOVERNANCE_CRITICAL)
- `src/governance/bitnet_governance_executor.py` — MetaGovernorExecutor (GOVERNANCE_CRITICAL)

### ML Runtime — PARTIALLY_CONNECTED
- `src/bitnet/bitnet_inference.py` — BitNetModel, inference from JSON weights (VALIDATION_CRITICAL)
- `src/features/feature_pipeline.py` — FeaturePipeline, 38 canonical features (CANONICAL)
- `models/gaussian_registry.json` — active: ETHUSDT v5 model, 35-feature schema (PARTIALLY_CONNECTED: schema v2 ≠ pipeline v3)
- `models/rr_registry.json` — active: ETHUSDT v5 (PARTIALLY_CONNECTED)
- `models/tradenet_registry.json` — active: ETHUSDT v5 .pth (PARTIALLY_CONNECTED)
- `models/zone_gate_registry.json` — active: ETHUSDT 202605_v1 (PARTIALLY_CONNECTED)
- `models/bitnet/bitnet_registry.json` — empty `{}` (DISCONNECTED — no trained model registered)
- `scripts/training/train_bitnet.py` — writes to `models/bitnet/` (PARTIALLY_CONNECTED after Phase 4 fix)

### Validation Runtime — VALIDATION_CRITICAL
- `src/config_layer/config_validator.py` — ConfigValidator (VALIDATION_CRITICAL)

### Control-Plane Runtime — LIVE_PRODUCTION
- `src/control_plane/server.py` — HTTP server localhost:8787 (LIVE_PRODUCTION)
- `src/control_plane/registry.py` — 47 CommandSpec entries (LIVE_PRODUCTION)
- `src/control_plane/jobs.py` — JobManager, subprocess.Popen execution (LIVE_PRODUCTION)

### Agent Runtime — EXPERIMENTAL
- `src/agent/plan_compiler.py` — 21 deterministic intents (EXPERIMENTAL)
- `src/agent/intent_router.py` — regex + LLM routing (EXPERIMENTAL)
- `src/agent/tool_registry.py` — tool handler registration (EXPERIMENTAL)

### Archived / Dead — DO NOT USE
- `archive/inout_legacy/ARCHIVED_2026_05_02/runner.py` — DEAD_CODE
- `archive/dead_code/` — DEAD_CODE
- Registry entry `live.inout_runner` → `inout.runner` — BROKEN (module not found)

---

# 2. CANONICAL EXECUTION GRAPH

## Path A: Control Plane → Subprocess (UI-triggered)

```
Browser → localhost:8787
→ ControlPlaneAPI (server.py)
→ JobManager.create_run(command_id, user_args) (jobs.py:200)
→ build_command_line(spec, merged_args) (jobs.py:1016)
    Registry defaults merged with user_args
    DRIFT RISK: registry defaults ≠ argparse defaults (--instruments, --instrument)
→ subprocess.Popen([sys.executable, script, ...args]) (jobs.py:325)
    shell=False — no direct shell injection
    No input validation on merged args values
→ Script runs as child process
→ Stdout/stderr streamed to logs/control_plane/runs/{run_id}.json
```

## Path B: Backtest (canonical replay)

```
CLI: python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv
→ main() (backtest_v2.py:1942)
→ argparse.parse_args() — no choices constraint on --instrument
→ BacktestConfig.from_prod_config(instrument) (backtest_v2.py:140)
    Loads configs/production/{ACTIVE_VERSION}.json
    Hash verification on params (SHA-256)
→ CandleLoader(csv_path, instrument).stream() — yields Candle objects
→ BacktestRunner.__init__(cfg, csv_path)
    Phase 1: FeaturePipeline(raw_df).run() → feature_vectors (N×38 float32)
             RAISES RuntimeError on failure (Phase 2 fix applied)
    Phase 2: FeatureMonitor(window_size=500) — logs ERROR if init fails
    Phase 3: get_prod_section("execution_planner") — RAISES if missing
    Phase 4: BACKTEST_ENGINE_GATE env var — EngineRunner wired only if "1"
→ BacktestRunner.run(candle_stream, total_candles, output_dir)
    Per-candle loop:
        warmup skip (candle_idx < warmup_candles)
        HTF init after seed candles
        Gap detection (GapDetector) → state reset if gap found
        engine.process_candle(candle, htf_id) → CRT state machine advance
        On TRADE_OPENED:
            feature lookup from feature_ts_to_idx
            Phase-5 scorer gate (CRTGaussianScorer or CRTCalibratedScorer)
            Reject if p_win < 0.35
            FeatureMonitor drift check
            Optional EngineRunner gate (BACKTEST_ENGINE_GATE=1)
        On TRADE_CLOSED: journal.on_trade_closed() → PnL computation
→ BacktestMetrics collected
→ ReportWriter.write():
    results/{instrument}/{instrument}_trades.csv
    results/{instrument}/{instrument}_summary.csv
    results/{instrument}/{instrument}_metrics.json
```

## Path C: EngineRunner (live scoring pipeline)

```
Signal candidate → EngineRunner.run(input_dict) (engine_runner.py:493)

Step 1: TrapValidatorEngine.compute(merged_input)
        score ≤ 0.0 → hard reject ("adapter_rejected")

Step 2: ALL 4 engines run unconditionally
    Zone Gate:   run_zone_gate_engine(features, model_fn, threshold)
                 BitNetZoneGate wrapper — loads from zone_registry_path
    CRT:         crt_compute(crt_config, candle_context)
    Gaussian:    HeuristicGaussianEngine.compute() or MLGaussianEngine.compute()
                 Selected by GAUSSIAN_IMPL env var OR config["gaussian_impl"]
    RR:          RREngine.compute(input_data)
    Optional:    RRFusionLayer.score_dict() if rr_fusion_enabled=true
    Optional:    strategy_consensus_score from context

Step 3: Completeness check
        EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}
        missing = EXPECTED_ENGINES - engine_results.keys()
        If ANY missing → reject("incomplete_engine_execution:{sorted(missing)}")

Step 4: FusionEngine.compute(engine_results)
        Weights: crt=0.30, gaussian=0.25, zone_gate=0.25, rr=0.20
        Dead engine detection (mean=0, var=0 over 1000 samples) → exclude from fusion
        Conflict detection: direction signals (+1, -1) — policy: conservative or majority
        final_score = weighted sum of clamped engine scores

Step 5: Fusion threshold gate
        final_score < fusion_min_score → reject("low_fusion_score")

Step 6: RegimeGovernor.evaluate() or _regime_governor_legacy()
        Trend/range/neutral regime detection
        Breakout + trap engine scores
        UltronRiskGate enabled (live) or disabled (training/backtest)
        not gate_result["allow"] → reject

Step 7: DecisionEngine.evaluate(score, p_win, zone_gate, fusion, config)
        SOLE authority for "execute" or "reject"
        Adaptive thresholds injected from acceptance_controller

Step 8: collector.log(full decision record)
        Appends to collector JSONL audit file

Step 9: acceptance_controller.update_metrics()
        convergence_controller.record_outcome()

Step 10: CognitiveBus.emit() — fire-and-forget, never raises

→ Returns decision_result dict from DecisionEngine
```

## Path D: Governance Orchestration (production config mutation)

```
CLI: python src/governance/orchestrator.py --collector-log ... --trades-csv ... --baseline-pnl ...
OR: governance_mode.py governance.run_loop tool (write=True, confirms required)

→ GovernanceOrchestrator.__init__():
    MetaGovernorExecutor(bitnet_bin, model_path, audit_log_path)
    ShadowPromotionGate(active_config_path)

→ GovernanceOrchestrator.run():
    Step 1: ReflectionBuffer.load_and_merge(collector_log, trades_csv) → DataFrame
    Step 2: reflection.generate_prompt_payload(df) → WRITES logs/meta_prompt.txt
    Step 3: executor.run_inference(prompt_path=logs/meta_prompt.txt)
            executor.extract_and_validate_config(raw_output) → patch dict
            executor.log_governance_event() → APPENDS logs/governance_audit.jsonl
    Step 4: shadow_gate.stage_candidate(patch) → WRITES configs/production/candidate.json
            shadow_gate.execute_shadow_test() → subprocess backtest
            shadow_gate.promote_if_superior(baseline_pnl, shadow_pnl, n_trades):
                Gate 1: n_trades ≥ min_shadow_trades
                Gate 2: shadow_pnl > baseline_pnl
                If BOTH pass:
                    shutil.copy(candidate_path, active_config_path)  ← NON-ATOMIC
                    candidate_path.unlink()
                    → active production config IS NOW MUTATED
                    → NO rollback path if crash occurs mid-copy
```

## Path E: Promotion (PromotionManager — canonical path)

```
CLI: python src/governance/promotion_manager.py promote --checkpoint ... --data-dir ...

→ promote_from_tuner_checkpoint(checkpoint_path, version, csv_paths):
    Load checkpoint JSON
    Filter valid results (score > -999.0)
    For each top config:
        ConfigValidator.validate(params, csv_paths) → ValidationReport
        If APPROVE:
            _execute_promotion(report, version, notes)
                _build_registry_entry() → registry dict with config_hash (SHA-256)
                _write_to_registry(entry, version):
                    Archive existing: shutil.copy2(out_path, archive_path)  ← non-atomic
                    Write new: open(out_path, "w") + json.dump()  ← NON-ATOMIC overwrite
                    Write pointer: ACTIVE_VERSION.write_text(version)  ← separate write
                    _log_event() → APPENDS configs/promotion_log.jsonl
→ Returns {"status": "PROMOTED", ...}

ATOMICITY GAP: Three separate writes. Crash between config write and ACTIVE_VERSION update
leaves system in version mismatch state.
```

## Path F: Agent REPL (AI-assisted execution)

```
CLI: python src/agent/cli.py
→ AgentCore REPL loop
→ User input → IntentRouter.classify(user_input, conversation)
    Step 1: regex_classify() against intent_patterns.json (deterministic)
    Step 2: If confidence < 0.6: llm_classify() via llm_chat() (stochastic)
    Step 3: Unknown → {"intent_key": "ask_user"}
→ PlanCompiler.build(intent_key) → Plan (from PLAN_REGISTRY lookup — deterministic)
→ Executor.execute(plan):
    Per ToolStep:
        If tool.write=True → confirm gate (y/N prompt)
        path_guard check
        handler(args)
→ Returns structured result
```

---

# 3. STATE OWNERSHIP GRAPH

## Active Production Config

| Property | Value |
|---|---|
| **Owner** | `PromotionManager._write_to_registry()` (canonical), `ShadowPromotionGate.promote_if_superior()` (governance path) |
| **Location** | `configs/production/{ACTIVE_VERSION}.json` |
| **Pointer** | `configs/production/ACTIVE_VERSION` (plain text file) |
| **Mutation locations** | `promotion_manager.py:_write_to_registry()` + `shadow_promotion_gate.py:235` |
| **Atomicity** | NOT atomic — two separate writes (config + pointer) |
| **Rollback** | Manual only — archive files preserved as `{version}_archived_{ts}.json` |
| **Concurrency risk** | HIGH — no locking; two concurrent governance runs can corrupt |
| **Crash consistency** | Config written but pointer stale = silent version mismatch |
| **Corruption risk** | CRITICAL — mid-write crash leaves truncated JSON |

## Governance Audit Log

| Property | Value |
|---|---|
| **Owner** | `bitnet_governance_executor.py` — `log_governance_event()` |
| **Location** | `logs/governance_audit.jsonl` |
| **Access pattern** | Append-only |
| **Rollback** | Not applicable (audit) |
| **Concurrency risk** | Low (single orchestrator instance assumed) |
| **Corruption risk** | LOW — append-only JSONL; partial line at crash is ignorable |

## Promotion Log

| Property | Value |
|---|---|
| **Owner** | `promotion_manager.py` — `_log_event()` |
| **Location** | `configs/promotion_log.jsonl` |
| **Access pattern** | Append-only |
| **Atomicity** | Single line write — effectively atomic |
| **Rollback** | Not applicable (audit) |
| **Corruption risk** | LOW — written AFTER config; crash before = silent promotion (no log entry) |

## Model Registries (4 active)

| Property | Value |
|---|---|
| **Owner** | Training scripts (`train_pipeline.py`, `model_registry.py`) |
| **Location** | `models/{gaussian,rr,tradenet,zone_gate}_registry.json` |
| **Active model selection** | `"active": true` flag in registry JSON |
| **Mutation** | Only via promotion path (model_registry.py GOV-3 atomic promotion) |
| **Fallback if active model file missing** | `FileNotFoundError` raised — NO silent fallback (verified in bitnet_inference.py) |
| **Schema mismatch** | All active models use 35-feature v2.0 schema; pipeline produces 38-feature v3.0 — requires truncation at inference |

## Feature Cache (per BacktestRunner)

| Property | Value |
|---|---|
| **Owner** | `BacktestRunner.__init__()` |
| **Location** | In-memory: `self.feature_vectors` (N×38 float32 numpy array), `self.feature_ts_to_idx` dict |
| **Lifecycle** | Created at BacktestRunner init, destroyed when object GC'd |
| **Concurrency risk** | None — per-instance, not shared |
| **Failure mode** | `RuntimeError` if FeaturePipeline fails (fail-fast, Phase 2 fix) |

## CRT Engine State (per candle)

| Property | Value |
|---|---|
| **Owner** | `CRTEngine` — maintains `EngineState` dataclass |
| **Mutable fields** | `current_state`, `atr`, `sweep_event`, `displacement_candle`, `retest_candle`, `active_trade`, `risk_score`, `event_log` |
| **Reset trigger** | Gap detection, session boundary, explicit reset |
| **Persistence** | In-memory only — not serialized between runs |
| **Determinism** | Deterministic given same candle sequence |

## Collector JSONL (runtime decisions)

| Property | Value |
|---|---|
| **Owner** | `collector.py` — `Collector.log()` |
| **Location** | `logs/{instrument}_fusion.jsonl` (approximate) |
| **Access pattern** | Append-only per run |
| **Consumer** | `ReflectionBuffer.load_and_merge()` for governance |
| **Corruption risk** | LOW — append-only |

---

# 4. METHOD-LEVEL EXECUTION COGNITION

## GovernanceOrchestrator.run()

| Field | Value |
|---|---|
| **File** | `src/governance/orchestrator.py` |
| **Class** | `GovernanceOrchestrator` |
| **Method** | `run()` lines 92–218 |
| **Human Purpose** | Drive reflection → LLM inference → shadow test → conditional production config promotion |
| **Architectural Role** | The ONLY autonomous production config mutation path outside of PromotionManager |
| **Invocation Sources** | `src/agent/modes/governance_mode.py:governance.run_loop` (write=True), CLI `main()` line 254 |
| **Runtime Flow** | ReflectionBuffer.load_and_merge → generate_prompt_payload → MetaGovernorExecutor.run_inference → ShadowPromotionGate.promote_if_superior |
| **State Mutations** | WRITES: `logs/meta_prompt.txt`, `logs/governance_audit.jsonl`, `configs/production/candidate.json`; CONDITIONALLY: `configs/production/{ACTIVE_VERSION}.json` |
| **Failure Modes** | Crash between steps leaves stale artifacts; mid-copy crash corrupts active config |
| **Fallback Behavior** | Returns `{"patch": None, "promoted": False, "reason": ...}` on reflection failure |
| **Determinism** | NONDETERMINISTIC — MetaGovernorExecutor uses BitNet/LLM; shadow PnL depends on data at call time |
| **Trust Classification** | GOVERNANCE_CRITICAL |
| **Security Risks** | `active_config_path` default is constructor parameter — path traversal if caller-controlled |
| **Important Findings** | NOT atomic. Concurrent calls can corrupt active config. No locking. |

## EngineRunner.run()

| Field | Value |
|---|---|
| **File** | `src/core/engine_runner.py` |
| **Class** | `EngineRunner` |
| **Method** | `run(input_dict)` lines 493–921 |
| **Human Purpose** | Score a trade candidate through all 4 engines and return final EXECUTE/REJECT decision |
| **Architectural Role** | Single authoritative scoring pipeline for both live and backtest paths |
| **Invocation Sources** | `live_engine_hook.py`, `BacktestRunner.run()` (when BACKTEST_ENGINE_GATE=1), agent copilot tools |
| **Downstream Calls** | TrapValidatorEngine → ZoneGate → CRTEngine → GaussianEngine → RREngine → FusionEngine → RegimeGovernor → DecisionEngine → Collector → acceptance/convergence controllers → CognitiveBus |
| **State Mutations** | Collector append, acceptance_controller metrics, convergence_controller outcomes |
| **Failure Modes** | ZoneGate exception → neutral 0.5 (SILENT FALLBACK). RRFusion exception → base RR score (SILENT). CognitiveBus exception → pass (intentional). |
| **Determinism** | PARTIALLY DETERMINISTIC — core pipeline deterministic; GaussianEngine depends on GAUSSIAN_IMPL env var; dead-engine exclusion depends on historical window |
| **Trust Classification** | CANONICAL, LIVE_PRODUCTION |
| **Important Findings** | ZoneGate and RRFusion silent fallbacks can produce neutral scores masking real failures. |

## ShadowPromotionGate.promote_if_superior()

| Field | Value |
|---|---|
| **File** | `src/governance/shadow_promotion_gate.py` |
| **Class** | `ShadowPromotionGate` |
| **Method** | `promote_if_superior(baseline_pnl, shadow_pnl, n_shadow_trades)` lines 186–246 |
| **Human Purpose** | Promote candidate config to production only if shadow backtest outperforms baseline |
| **Architectural Role** | Final gate before autonomous production config mutation |
| **State Mutations** | `shutil.copy(candidate_path, active_config_path)` — directly overwrites live production config |
| **Atomicity** | NOT atomic. `shutil.copy()` on Windows: open → truncate → write in chunks. Crash mid-copy = corrupted active config. |
| **Rollback Capability** | NONE — no backup taken before overwrite; archive only exists via PromotionManager path |
| **Concurrency Risk** | CRITICAL — no file locking; two parallel governance runs can both promote, second overwriting first |
| **Determinism** | NONDETERMINISTIC — depends on shadow backtest PnL and baseline_pnl at call time |
| **Trust Classification** | GOVERNANCE_CRITICAL, DANGEROUS (atomicity) |

## PromotionManager._write_to_registry()

| Field | Value |
|---|---|
| **File** | `src/governance/promotion_manager.py` |
| **Class** | `PromotionManager` |
| **Method** | `_write_to_registry(entry, version)` lines 494–605 |
| **Human Purpose** | Persist a validated config version to the production registry |
| **State Mutations** | (1) Archive: `shutil.copy2(out_path, archive_path)`, (2) Write: `open(out_path, "w") + json.dump()`, (3) Pointer: `ACTIVE_VERSION.write_text(version)`, (4) Log: `_log_event()` append to `promotion_log.jsonl` |
| **Crash Scenarios** | Config written but pointer stale → version mismatch silent. Config write half-done → corrupt JSON. |
| **SHA-256 Verification** | `_compute_config_hash(params)` — SHA-256 of `json.dumps(params, sort_keys=True)`. Stored in registry entry AND verified at load via `load_version()`. |
| **Determinism** | PARTIALLY DETERMINISTIC — SHA-256 is deterministic; timestamp fields are nondeterministic |
| **Trust Classification** | GOVERNANCE_CRITICAL |

## ConfigValidator.validate()

| Field | Value |
|---|---|
| **File** | `src/config_layer/config_validator.py` |
| **Class** | `ConfigValidator` |
| **Method** | `validate(params, csv_paths, config_id, use_llm, warmup_candles)` lines 310–421 |
| **Human Purpose** | Determine if a parameter set meets quality gates across all instruments |
| **Fail-Fast** | Missing CSV → hard REJECT. Instrument backtest exception → hard REJECT. (Phase 5 fix applied) |
| **Hard Gates** | min_trades_per_instrument, max_drawdown_pct, min_fitness_score |
| **Soft Gates** | win_rate, expectancy_rr, trade_count_target, score_std_dev |
| **Fitness Formula** | `0.5×expectancy_norm + 0.2×winrate + 0.2×count_norm + 0.1×dd_norm` |
| **Determinism** | DETERMINISTIC given same params + same CSV data |
| **Trust Classification** | VALIDATION_CRITICAL |

## FusionEngine.compute()

| Field | Value |
|---|---|
| **File** | `src/core/fusion_engine.py` |
| **Method** | `compute(engine_results)` lines 256–450 |
| **Completeness Gate** | `expected = ("crt","gaussian","zone_gate","rr")`. Missing → returns `{"final_score": 0.0, "reason": "missing_engine_outputs"}` |
| **Weights** | crt=0.30, gaussian=0.25, zone_gate=0.25, rr=0.20 (from config) |
| **Dead Engine Detection** | mean=0.0 AND var=0.0 over 1000-sample window → engine excluded from weighted average |
| **Conflict Policy** | "conservative" (reject on direction conflict) or "majority" (winner decides) |
| **Silent Fallback** | `fusion.evaluate()` raises → fall back to `compute()` path (SILENT degradation) |
| **Determinism** | DETERMINISTIC for same inputs; dead-engine exclusion depends on historical window |
| **Trust Classification** | CANONICAL |

## FeaturePipeline.run()

| Field | Value |
|---|---|
| **File** | `src/features/feature_pipeline.py` |
| **Method** | `run()` lines 736–802 |
| **Input** | DataFrame with columns: timestamp, open, high, low, close (volume optional, defaults 0.0) |
| **Output** | `(enriched_df, vectors)` — enriched_df is NaN-clean, vectors is (N, 38) float32 numpy array |
| **Feature Schema** | 38 features: 35 from v2.0 + 3 new v3.0 (`liquidity_distance`, `liquidity_pressure_score`, `volume_spike`) |
| **Lookahead Bias** | `center=True` rolling windows in live mode — acknowledged in code (lines 39–40) |
| **NaN Handling** | `finalize()` drops all rows with NaN — requires ≥200 bars history (ma_200 warmup) |
| **Determinism** | DETERMINISTIC — no random operations |
| **Schema Mismatch** | Active models use 35-feature v2.0. Pipeline produces 38. Slicing to 35 must occur at inference. |
| **Trust Classification** | CANONICAL |

---

# 5. TRUST CLASSIFICATION SYSTEM

| Component | File | Classification | Reason |
|---|---|---|---|
| EngineRunner | `src/core/engine_runner.py` | **CANONICAL, LIVE_PRODUCTION** | Single authoritative scoring path |
| FusionEngine | `src/core/fusion_engine.py` | **CANONICAL** | Sole fusion authority |
| DecisionEngine | `src/core/decision_engine.py` | **CANONICAL** | Sole EXECUTE/REJECT authority |
| BacktestRunner | `src/runtime/backtest_v2.py` | **CANONICAL** | Authoritative replay engine |
| FeaturePipeline | `src/features/feature_pipeline.py` | **CANONICAL** | Authoritative feature source |
| ConfigValidator | `src/config_layer/config_validator.py` | **VALIDATION_CRITICAL** | Mandatory pre-promotion gate |
| PromotionManager | `src/governance/promotion_manager.py` | **GOVERNANCE_CRITICAL** | Canonical promotion path |
| GovernanceOrchestrator | `src/governance/orchestrator.py` | **GOVERNANCE_CRITICAL** | Autonomous production mutator |
| ShadowPromotionGate | `src/governance/shadow_promotion_gate.py` | **GOVERNANCE_CRITICAL, DANGEROUS** | Atomicity risk on production write |
| ReflectionBuffer | `src/governance/reflection_buffer_advanced.py` | **GOVERNANCE_CRITICAL** | Governance data source |
| production_config.py | `src/config_layer/production_config.py` | **CANONICAL** | Single config authority |
| CRT Engine v2 | `src/config_layer/crt_engine_v2.py` | **CANONICAL** | Core signal state machine |
| UltronRiskGate | `src/core/ultron_risk_gate.py` | **LIVE_PRODUCTION** | Live position gate only |
| ExecutionPlannerV1_2 | `src/config_layer/execution_planner.py` | **CANONICAL** | Entry/SL/TP authority |
| BitNetModel | `src/bitnet/bitnet_inference.py` | **VALIDATION_CRITICAL** | Gate scoring (verified fail-fast) |
| BitNet Training | `scripts/training/train_bitnet.py` | **PARTIALLY_CONNECTED** | Writes to registry but inference path still manual |
| backtest_bitnet.py | `src/runtime/backtest_bitnet.py` | **EXPERIMENTAL** | Non-canonical metrics schema |
| unified_replay_harness.py | `src/runtime/unified_replay_harness.py` | **EXPERIMENTAL** | Composite of two schemas |
| strategy_backtest.py | `src/governance/strategy_backtest.py` | **PARTIALLY_CONNECTED** | Different schema, not in main pipeline |
| Agent system | `src/agent/` | **EXPERIMENTAL** | Not production-deployed |
| IntentRouter | `src/agent/intent_router.py` | **EXPERIMENTAL** | LLM fallback is nondeterministic |
| llm_research/policy_builder.py | `src/llm_research/policy_builder.py` | **DANGEROUS** | eval() on feature expressions (see §11) |
| `live.inout_runner` registry entry | `src/control_plane/registry.py:442` | **BROKEN** | Module not found (archived) |
| `archive/` | `archive/` | **DEAD_CODE** | No live imports confirmed |
| `archive/inout_legacy/` | `archive/inout_legacy/` | **LEGACY** | Runner awaiting restore decision |

---

# 6. DETERMINISM AUDIT

## BacktestRunner — DETERMINISTIC (with caveats)

- **Candle loop:** Reads from CSV sequentially. No time.now() in trading path. ✓ Deterministic
- **Slippage:** `SlippageModel(seed)` — seeded RNG via `random.Random(seed)`. If seed=0 → NOT seeded → nondeterministic slippage
- **Feature pipeline:** Pure numpy/pandas operations. ✓ Deterministic
- **Phase-5 scorer:** Gaussian parameters from config. ✓ Deterministic
- **EngineRunner gate:** `BACKTEST_ENGINE_GATE` env var — behavior changes based on environment. Partially nondeterministic

## EngineRunner — PARTIALLY DETERMINISTIC

- **GAUSSIAN_IMPL env var** (`engine_runner.py:275`): If set at runtime, switches engine implementation → same input can produce different scores
- **Dead-engine exclusion:** Depends on 1000-sample rolling window — window state not serialized → nondeterministic across restarts
- **RegimeGovernor:** Quota-based rejection in live mode — depends on daily trade count state
- **CognitiveBus:** Fire-and-forget async — timing nondeterministic (does not affect decision)

## Governance Orchestration — NONDETERMINISTIC

- **MetaGovernorExecutor.run_inference():** BitNet/LLM inference — inherently nondeterministic
- **Shadow backtest PnL:** Depends on data at call time — deterministic per dataset, nondeterministic across calls
- **promote_if_superior:** Comparison is deterministic given PnL values, but PnL values are nondeterministic

## IntentRouter — PARTIALLY DETERMINISTIC

- **Regex path:** Deterministic ✓
- **LLM path:** `llm_chat()` at temperature=0.0 — theoretically deterministic but LLM inference can vary

## PlanCompiler — DETERMINISTIC

- Pure Python dict lookup. No randomness. ✓ Fully deterministic

## Environment Variable Nondeterminism Sources

| Variable | Default | File | Effect |
|---|---|---|---|
| `GAUSSIAN_IMPL` | config value (→ "heuristic") | `engine_runner.py:275` | Switches ML vs heuristic Gaussian |
| `BACKTEST_ENGINE_GATE` | "0" | `backtest_v2.py:1398` | Enables/disables EngineRunner in backtest |
| `BACKTEST_BYPASS_ZONE_INVALID` | "1" | `backtest_v2.py` (referenced) | Bypass zone gate invalid rejection |

---

# 7. REPLAY TRUTH AUDIT

## Canonical Replay Engine

**`src/runtime/backtest_v2.py` — BacktestRunner** is the canonical replay engine.

- Produces: `BacktestMetrics` → `to_dict()` schema
- Used by: `ConfigValidator._run_instrument()`, direct CLI, auto_tuner_multi
- Output schema: `{approved_trades, rejected_trades, wins, losses, tp1_hits, tp2_hits, total_pnl_rr_raw, total_pnl_rr_net, max_drawdown_rr, max_drawdown_pct, win_rate, avg_rr_net}`

## Duplicate Replay Systems

| System | File | Schema | Authority |
|---|---|---|---|
| **BacktestRunner** | `backtest_v2.py` | `BacktestMetrics.to_dict()` | **CANONICAL** |
| **backtest_bitnet** | `backtest_bitnet.py` | `list[dict]` with `{decision, reason, bitnet_decision, ...}` | EXPERIMENTAL |
| **unified_replay_harness** | `unified_replay_harness.py` | Composite of both above | EXPERIMENTAL |
| **ConfigValidator** | `config_validator.py` | `{score, trades, win_rate, expectancy_rr, max_drawdown, total_pnl_rr}` | VALIDATION_CRITICAL (internal schema) |
| **StrategyBacktester** | `strategy_backtest.py` | `StrategyMetrics` with `{trade_count, win_count, profit_factor, expectancy_inr, ...}` | PARTIALLY_CONNECTED |

## Schema Divergence

- `ConfigValidator` consumes a custom 6-field dict derived from `BacktestMetrics`. If `BacktestMetrics` schema evolves (new fields, renamed fields), the validator's extraction logic must be updated manually — no shared serializer.
- `StrategyMetrics` uses `expectancy_inr` (India Rupees) — incompatible currency unit with `BacktestMetrics` which uses RR multiples.
- `backtest_bitnet.py` produces per-row records, not aggregate metrics — incomparable with BacktestRunner aggregate output.

## Authoritative Truth Map

| Metric | Authoritative Source |
|---|---|
| Trade P&L (replay) | `BacktestRunner` → `TradeJournal.on_trade_closed()` |
| Config fitness score | `ConfigValidator._fitness_score()` |
| Governance decision | `MetaGovernorExecutor.extract_and_validate_config()` |
| Feature vectors | `FeaturePipeline.run()` |
| Model inference | Per-model registry entry → respective loader |

---

# 8. GOVERNANCE TRANSACTION MODEL

## Promotion via PromotionManager (canonical path)

```
Transaction: promote_from_tuner_checkpoint() or promote_from_report()
Steps:
  1. Validate report (ConfigValidator.validate())           — NO file write
  2. _execute_promotion():
     a. _build_registry_entry()                            — NO file write
     b. shutil.copy2(out_path, archive_path)               — WRITE: archive
     c. open(out_path, "w"); json.dump(payload, f)         — WRITE: new config   ← NON-ATOMIC
     d. ACTIVE_VERSION.write_text(version)                  — WRITE: pointer     ← SEPARATE WRITE
     e. _log_event() → promotion_log.jsonl.append()        — WRITE: audit log
```

**Atomicity:** NONE — five separate I/O operations
**Rollback:** Archive file exists (step b) but no automatic restore
**Checksum:** SHA-256 computed and stored in registry entry; verified at load
**Concurrent mutation risk:** HIGH — no file locking

**Crash consistency scenarios:**

| Crash after | System state | Recovery |
|---|---|---|
| Step a | Nothing written. No corruption. | Re-run promotion. |
| Step b | Archive created; config unchanged. | Delete orphan archive; re-run. |
| Step c (partial write) | Config JSON corrupted. ACTIVE_VERSION unchanged. | Manual: restore archive; re-run. |
| Step c (complete) | New config written. ACTIVE_VERSION points to old. | `ACTIVE_VERSION.write_text(version)` manually. |
| Step d | Config + pointer updated. Audit log missing. | Safe operationally; governance blind. |
| Step e | No impact — audit only. | Accept missing log entry. |

## Promotion via ShadowPromotionGate (autonomous path)

```
Transaction: ShadowPromotionGate.promote_if_superior()
  1. stage_candidate(patch) → writes candidate.json   — WRITE: candidate (safe)
  2. execute_shadow_test()  → subprocess backtest      — WRITE: shadow_trades.csv
  3. promote_if_superior():
     a. shutil.copy(candidate_path, active_config_path)  ← NON-ATOMIC overwrite
     b. candidate_path.unlink()                           ← SEPARATE DELETE
     c. Returns {"promoted": True/False}
```

**NO rollback.** `shutil.copy()` on Windows opens destination, truncates, writes in chunks. Mid-crash = truncated active config. No temp-file-then-rename pattern. No archive taken before overwrite.

**Tamper risk:** `candidate.json` is written to a fixed path (`configs/production/candidate.json`). Between `stage_candidate()` and `promote_if_superior()`, any process with file access can modify the candidate. The shadow test runs on the staged candidate — a modified candidate passes the performance gate but installs the tampered config.

## SHA-256 Integrity

**Computed:** `hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()`
**Stored:** In registry entry under `config_hash`
**Verified:** At `load_version()` → raises `RuntimeError` if mismatch
**NOT verified:** If `config_hash` field is absent → `warnings.warn()` only, proceeds (fail-open gap)

---

# 9. FALLBACK CORRUPTION GRAPH

## Chain 1: ZoneGate Silent Neutral → Governance Contamination

```
ZoneGate.compute() raises exception (model file missing, corrupt weights)
→ engine_runner.py:546: returns 0.5 (NEUTRAL — SILENT)
→ FusionEngine.compute(): uses 0.5 as zone_gate score
→ final_score = 0.30×crt + 0.25×gaussian + 0.25×0.5 + 0.20×rr
   [effectively: missing gate receives neutral credit]
→ BacktestRunner: trade OPENS (score above threshold)
→ BacktestMetrics: trade counted as valid
→ ConfigValidator.validate(): score includes ghost trades
→ ValidationReport.decision = "APPROVE" [contaminated]
→ PromotionManager: config promoted to production
→ LIVE SYSTEM: runs with ZoneGate still broken, still neutral
```

## Chain 2: FeatureMonitor Silent Disable → Drift Undetected

```
FeatureMonitor.__init__() raises (missing import, bad config)
→ backtest_v2.py: logs ERROR, sets _monitor=None, _monitor_available=False (Phase 2 fix)
→ Drift detection DISABLED for entire backtest run
→ BacktestMetrics: no drift events recorded
→ ValidationReport: distribution["feature_drift"] absent or zero
→ Governance: approves config as if market conditions are stable
→ Live system: deployed to drifting market without drift guard active
```

*(Note: Phase 2 fix changed this from silent to ERROR-level log, but drift detection still disabled)*

## Chain 3: crt_gaussian_scorer.py Silent Defaults → Wrong Thresholds

```
production_config: "gaussian_scorer" section missing or malformed
→ crt_gaussian_scorer.py:36-55: .get() with hardcoded defaults:
    RETEST_MU = 0.237, RETEST_S2 = 0.040, SIGMOID_X0 = 0.50
→ Gaussian scorer runs with hardcoded parameters, not production-tuned values
→ Phase-5 gate: p_win computed with wrong thresholds
→ BacktestRunner: trade open/close decisions contaminated
→ Metrics: artificially high or low win rate depending on defaults vs actuals
→ ConfigValidator: fitness score based on wrong decisions
→ Governance: approves config based on incorrect fitness measurement
```

## Chain 4: Config Dump Swallow → No Audit Trail

```
_full_reg["engine_runner"] raises KeyError (section missing from config)
→ backtest_v2.py config dump: KeyError raised inside try/except
→ log.warning("Config dump skipped: ...")
→ Backtest continues with NO config snapshot written
→ Results directory: metrics + trades exist, but no config record
→ Governance review: cannot verify which config produced which results
→ Auditability: broken — results are orphaned from their config version
```

*(Note: Phase 2-E fix changed .get(key,{}) to [key] — KeyError now propagates. But the outer try/except still catches and logs warning. Config dump failure is still non-fatal by design.)*

## Chain 5: LLM Circuit Open → Invisible Gate Bypass

```
LLM endpoint down for > _FAIL_COUNT_DISABLE requests
→ llm_scorer.py:CIRCUIT_OPEN = True  (Phase 6 fix)
→ llm_score_safe() returns 1.0 for all subsequent calls
→ Fusion: LLM gate contributes neutral 1.0 to all scores
→ Trades that would have been filtered by LLM pass through
→ BacktestMetrics: inflated win count (gate disabled)
→ CIRCUIT_OPEN flag available for caller inspection (Phase 6 fix)
→ If callers don't check CIRCUIT_OPEN: governance contamination continues silently
```

---

# 10. PERFORMANCE / HOT PATH AUDIT

## Per-Candle Hot Loop (BacktestRunner.run())

| Operation | Frequency | Cost | Classification |
|---|---|---|---|
| feature_ts_to_idx lookup | Every TRADE_OPENED candle | O(1) dict lookup | Acceptable |
| FeaturePipeline.run() | Once per BacktestRunner init | O(N×38) batch | Acceptable |
| get_prod_section() | Called at init (Phase 3 fix — now once) | JSON file read + parse | Acceptable |
| CandleLoader.stream() | Per candle | CSV row yield | Acceptable |
| engine.process_candle() | Per candle | CRT state machine | Acceptable |
| CRTGaussianScorer.compute() | Per TRADE_OPENED | Gaussian PDF eval | Acceptable |
| journal.on_trade_closed() | Per TRADE_CLOSED | Arithmetic only | Acceptable |

## Production Config Loading

**`get_prod_section(section)`** (lines 298–334 in `production_config.py`):
- Each call re-reads `configs/production/{version}.json` from disk
- ~10ms per 50KB file — negligible for 1-per-backtest
- **If called per candle** (in live mode): ~10ms × candle_rate = potentially concerning
- NOT VERIFIED whether live_engine_hook.py caches this or calls per-signal

## Model Weight Loading

**BitNetModel:** Loaded once per `__init__()`. Weights cached in `self.model` dict.
**Per-prediction:** Forward pass is O(layers × features) — microseconds per call.
**Other models (Gaussian, RR, TradeNet):** Loading pattern NOT VERIFIED IN SOURCE for hot-path caching.

## O(N²) Risks

- `_aggregate_metrics()`: sum over instruments only — O(N instruments), not O(N²). Acceptable.
- `FusionEngine.compute()`: sum over 4 engines — O(1) effectively. Acceptable.
- `CRTEngine.event_log`: List appended per event. If event_log grows unbounded in long backtests → O(N) memory. **CONCERNING** for multi-year backtests.

## Repeated Deserialization

- `get_prod_section()` reads and parses JSON on every call — NOT VERIFIED as cached in live mode
- Model registry files read once at startup — NOT VERIFIED IN SOURCE

---

# 11. SECURITY SURFACE AUDIT

## CRITICAL: eval() on Feature Expressions

**File:** `src/llm_research/policy_builder.py`
**Lines:** 91 and 131
```python
# Line 91
expr = self._confidence_formula
for k, v in features.items():
    expr = expr.replace(k, str(float(v)))
return max(0.0, min(1.0, float(eval(expr))))  # noqa: S307

# Line 131
expr = condition.replace(" AND ", " and ").replace(" OR ", " or ")
for k in sorted(features.keys(), key=len, reverse=True):
    v = features.get(k, 0)
    expr = expr.replace(k, str(float(v)))
return bool(eval(expr))  # noqa: S307
```

**Attack vector:** If `features` dict keys or values can be influenced by external input (e.g., from model outputs, CSV data, or LLM responses), the string replacement can escape the float() conversion. A crafted feature name or value could inject arbitrary Python code.

**Severity:** CRITICAL if policy_builder receives untrusted feature data.
**Mitigation required:** Replace `eval()` with `ast.literal_eval()` + restricted evaluation or a purpose-built expression parser.

## HIGH: subprocess.Popen() with User-Controlled Args

**File:** `src/control_plane/jobs.py:325`
```python
proc = subprocess.Popen(record.command_line, cwd=str(self._repo_root), ...)
```
`command_line` is built by `build_command_line(spec, merged_args)` where `merged_args` comes from HTTP request body.

**Mitigation:** `shell=False` prevents shell injection. Args are passed as list — OS-level arg separation. BUT: if arg values contain path traversal (`../../etc/passwd`), the called script receives the malicious path.

**Validation gap:** No sanitization of arg values against allowed patterns before command construction.

## MEDIUM: Non-Atomic Config Overwrite

**File:** `src/governance/shadow_promotion_gate.py:235` and `src/governance/promotion_manager.py:556`

Both use direct `open(..., "w")` or `shutil.copy()` — not atomic. A concurrent read during write can return partial JSON, crashing the reader.

**Fix pattern:**
```python
tmp = target.with_suffix(".tmp")
shutil.copy(source, tmp)
os.replace(tmp, target)  # atomic on POSIX; on Windows: atomic if same filesystem
```

## MEDIUM: Candidate Config Tamper Window

Between `stage_candidate()` writing `configs/production/candidate.json` and `promote_if_superior()` reading it, any process with filesystem access can modify the candidate. The shadow test result proves the original candidate's performance, but the modified candidate is promoted.

## LOW: Config Version Path Traversal

**File:** `src/config_layer/production_config.py`
Version string from `ACTIVE_VERSION` file is used to construct `configs/production/{version}.json` path. If ACTIVE_VERSION contains `../`, path traversal occurs.

**Current value:** `v2_multi_2026_04 - deepdeektry` — contains spaces, which is itself anomalous but not path-traversal.

**Mitigation required:** Validate version string matches `[a-zA-Z0-9_-]+` before path construction.

## LOW: JSON Model Poisoning

Model weight files loaded via `json.load()` — safe against code execution (JSON is data-only). BUT: if malformed float values (NaN, Inf) are in weights, they propagate through forward pass, eventually producing NaN gate scores that fall back to neutral.

---

# 12. REPOSITORY-WIDE FAIL-FAST AUDIT

## Confirmed Silent Fallbacks (source-verified)

| # | File | Function | Pattern | Current Behavior | Corruption Risk |
|---|---|---|---|---|---|
| 1 | `engine_runner.py:546` | ZoneGate.check() | `except: return 0.5` | ZoneGate exception → neutral score | HIGH: trades approved with broken gate |
| 2 | `engine_runner.py:619` | RRFusion | `except: use base RR` | RRFusion exception → base score | MEDIUM: RR score less accurate |
| 3 | `engine_runner.py:918` | CognitiveBus | `except: pass` | Async bus emit failure ignored | LOW: intentional (fire-and-forget) |
| 4 | `fusion_engine.py:680` | fusion.evaluate() | `except: fallback to compute()` | Shadow evaluate failure → silent downgrade | MEDIUM: governance scoring diverges |
| 5 | `crt_gaussian_scorer.py:36-55` | Module init | `.get(key, hardcoded)` | Missing config section → hardcoded Gaussian params | HIGH: wrong thresholds in governance |
| 6 | `production_config.py:239` | hash check | `warnings.warn` + proceed | Missing config_hash → no integrity verification | HIGH: tampered config accepted silently |
| 7 | `control_plane/jobs.py:102` | load monitor specs | `except: specs={}` | Monitor config load failure → empty dict | LOW: monitoring broken, startup continues |
| 8 | `control_plane/jobs.py:152` | `_load_existing()` | `except: continue` | Corrupted run files skipped silently | LOW: audit trail incomplete |
| 9 | `crt_engine_v2.py:753` | feature extraction | `.get("disp_str", 0.0)` | Key "disp_str" → should be "disp_strength" | HIGH: wrong feature used in CRT scoring |
| 10 | `feature_pipeline.py:459` | ema_spread | `np.where(atr>0, ..., np.nan)` | NaN when ATR=0 — intentional (finalize drops) | NONE: correct pattern |

## Required Fail-Fast Corrections

**#1 (ZoneGate neutral):** `engine_runner.py:546` — replace `return 0.5` with `raise`. If ZoneGate is mandatory (in EXPECTED_ENGINES), its failure must halt the pipeline.

**#5 (crt_gaussian_scorer):** `crt_gaussian_scorer.py:36-55` — replace `.get(key, default)` with `_require(key)` pattern that raises `KeyError` if section/key missing.

**#6 (hash check):** `production_config.py:239` — replace `warnings.warn` + proceed with `RuntimeError` if `config_hash` field absent.

**#9 (key name):** `crt_engine_v2.py:753` — fix `"disp_str"` → `"disp_strength"`. Verify against actual feature dict keys at runtime.

---

# 13. ENFORCEMENT PLAN

## CI/CD Checks — Required

### AST-based Banned Pattern Scanner

**Target:** Block these patterns from entering `src/governance/`, `src/config_layer/`, `src/core/`, `src/runtime/`

```python
# Banned patterns (AST scan):
BANNED_PATTERNS = [
    "except Exception: pass",                    # bare swallow
    "except Exception:\n    return None",         # sentinel return
    "except Exception:\n    return 1.0",          # neutral fallback
    "except Exception:\n    return {}",           # empty dict fallback
    "eval(",                                      # eval anywhere
    ".get(key, {}) in governance path",           # config section defaults
    "warnings.warn followed by proceed",          # fail-open after warn
]
```

### Registry Validator

**CI check:** Before merge, verify all `CommandSpec.script` targets exist:
```python
for cmd in REGISTRY:
    assert Path(REPO_ROOT / cmd.script).exists(), f"Dead registry entry: {cmd.id}"
```

### Schema Consistency Check

**CI check:** Active model registry entries must declare feature count. Feature count must match `len(CANONICAL_FEATURES)` OR must be explicitly marked as v2.0 with truncation flag.

### Determinism Check

**CI check:** Backtest with seed=42 run twice — outputs must be byte-identical (for seeded slippage path).

### Governance Atomicity Check

**CI check:** Promotion paths must use `os.replace()` not `open("w")` for config writes. AST scan for `open(path, "w")` in `promotion_manager.py` and `shadow_promotion_gate.py`.

### Duplicate Schema Detector

**CI check:** Detect metric keys defined in more than one place with different types or scales. Flag `expectancy_inr` vs `expectancy_rr` cross-system.

## Enforcement Doctrine

```
CI FAILS on:
  - except Exception without re-raise in src/governance/, src/config_layer/, src/core/
  - warning+continue in promotion or validation code
  - registry target file missing at commit time
  - eval() in any file under src/
  - direct open(path, "w") for production config writes
  - .get() with fallback default for required config sections
```

---

# 14. CANONICAL PRODUCTION TRUTH

## What IS the true production path?

### Runtime: CANONICAL
`EngineRunner.run()` in `src/core/engine_runner.py` — the single scoring authority for both live and backtest.

### Metrics: CANONICAL
`BacktestMetrics.to_dict()` from `src/runtime/backtest_v2.py` — authoritative replay truth. All governance decisions must trace to this schema.

### Validator: CANONICAL
`ConfigValidator.validate()` in `src/config_layer/config_validator.py` — the mandatory pre-promotion gate. Any config not passing this is not production-valid.

### Config: CANONICAL
`configs/production/v2_multi_2026_04 - deepdeektry.json` — current active config per `ACTIVE_VERSION` file.

> ⚠️ ANOMALY: The ACTIVE_VERSION value `"v2_multi_2026_04 - deepdeektry"` contains spaces and a dash. The corresponding filename `v2_multi_2026_04 - deepdeektry.json` exists and is a valid JSON file. The name deviation from convention (`v2_multi_2026_04`) may indicate an experimental branch config promoted to ACTIVE unexpectedly. This should be verified with the operator.

### Promotion Path: CANONICAL
`PromotionManager.promote_from_tuner_checkpoint()` — the safe path. Requires `csv_paths` (verified). Always calls `ConfigValidator.validate()`.

**NOT canonical for CLI use:** `promote_from_report()` via CLI is now fixed (Phase 3) to require `--data-dir` and re-validate.

**NOT canonical:** `promote_direct()` — explicitly bypasses validation.

### Replay Engine: CANONICAL
`BacktestRunner` in `src/runtime/backtest_v2.py`.

**NOT canonical:** `backtest_bitnet.py`, `unified_replay_harness.py`, `strategy_backtest.py`.

### Models: CANONICAL (active)
- **Gaussian:** `v5_auto_2026_06_eth` — ETHUSDT, 35-feature v2.0 — `models/ETHUSDT/20260519_113806/gaussian_v5_auto_2026_06_eth.json`
- **RR:** `v5_auto_2026_06_eth2_ethusdt` — ETHUSDT, 35-feature — `models/ETHUSDT/20260519_134711/rr_model_v5_auto_2026_06_eth2.json`
- **TradeNet:** `v5_auto_2026_06_eth` — ETHUSDT, 35-feature — `.pth` (PyTorch)
- **Zone Gate:** `202605_v1_ethusdt` — ETHUSDT, 8 clusters — `models/ETHUSDT/20260519_113806/zone_registry_ETHUSDT_202605_v1.json`
- **BitNet:** NOT VERIFIED IN SOURCE — no registered model in `bitnet_registry.json`

### Conflicts: EXPLICITLY IDENTIFIED

| Conflict | Location | Risk |
|---|---|---|
| Feature schema v2 (35) vs v3 (38) | All active models vs FeaturePipeline | CRITICAL: inference uses wrong feature count |
| ACTIVE_VERSION name with spaces | `configs/production/ACTIVE_VERSION` | HIGH: path construction anomaly |
| 5 replay schemas with no shared serializer | Multiple runtime files | MEDIUM: governance can use wrong metrics |
| ShadowPromotionGate writes active config without atomicity | `shadow_promotion_gate.py:235` | CRITICAL: production mutation risk |

---

# 15. EXECUTION LINEAGE GRAPH

```
[CSV DATA]
    │
    ▼
FeaturePipeline.run() ─────────────────────── 38 features (v3.0)
    │                                              │
    │                          ┌─────────── MODEL INFERENCE
    │                          │         (sliced to 35 for v2.0 models)
    │                          │
    ▼                          ▼
CandleLoader.stream()    [Model Registries]
    │                    gaussian, rr, tradenet, zone_gate
    │
    ▼
BacktestRunner.__init__()
    │  feature_vectors cached
    │  FeatureMonitor initialized
    │  Phase 3/4 config loaded (execution_planner, feature_monitor)
    │
    ▼
BacktestRunner.run() ─── per-candle loop ─────────────────────────
    │                                                              │
    │                                                             CRT state machine
    │                                                             (crt_engine_v2.py)
    │
    On TRADE_OPENED:
    ├── feature lookup (feature_ts_to_idx O(1))
    ├── CRTGaussianScorer.compute() → p_win
    │   ├── LINEAGE BREAK: params from .get() with defaults (chain 3)
    ├── FeatureMonitor.update() → drift check
    └── Optional: EngineRunner.run() (BACKTEST_ENGINE_GATE=1)
    │
    ▼
BacktestMetrics.to_dict()
    │
    ├─────────────────────────────────────────────────────────────
    │                                                             │
    ▼                                                             ▼
ReportWriter output                              ConfigValidator._run_instrument()
{instrument}_trades.csv                          Custom extraction dict
{instrument}_metrics.json                        {score, trades, win_rate, ...}
    │                                                             │
    │                          ┌──────────────────────────────────┘
    │                          ▼
    │               _aggregate_metrics() → final_score
    │               _run_quality_gates() → APPROVE/REJECT
    │                          │
    │               ValidationReport
    │                          │
    │               PromotionManager._execute_promotion()
    │                          │
    │               ┌──────────┴──────────┐
    │               ▼                     ▼
    │        shutil.copy2()        open(out_path,"w")
    │        (archive)             (new config)  ← NON-ATOMIC
    │                                     │
    │                              ACTIVE_VERSION update ← SEPARATE WRITE
    │                                     │
    │                              promotion_log.jsonl append
    │                                     │
    │                    [NEW PRODUCTION CONFIG ACTIVE]
    │                                     │
    ▼                                     ▼
[REPLAY CONTINUES]              [FUTURE BACKTESTS USE NEW CONFIG]
    │
    LINEAGE BREAK: if config changes between replay runs,
    prior results cannot be compared (config version in _trades.csv
    is the only link — requires manual verification)
```

## Lineage Breaks (Verified)

| Break | Location | Impact |
|---|---|---|
| Feature v2/v3 mismatch | All active models | Inference uses wrong feature count |
| crt_gaussian_scorer hardcoded defaults | `crt_gaussian_scorer.py:36-55` | Wrong p_win threshold in validation runs |
| config_hash absent → proceed | `production_config.py:239` | Tampered config accepted without integrity check |
| BitNet model unregistered | `models/bitnet/bitnet_registry.json` | BitNet gate cannot be loaded for scoring |
| ShadowGate no archive before overwrite | `shadow_promotion_gate.py:235` | Prior config lost if promotion crashes mid-copy |
| 5 replay schemas | Multiple files | Cross-schema metric comparison impossible |

---

## APPENDIX: Source File Inventory (verified)

```
src/core/          17 files — engine_runner.py (CANONICAL), fusion_engine.py, decision_engine.py,
                              ultron_risk_gate.py, regime_governor.py, collector.py, model_registry.py, ...

src/config_layer/  13 files — production_config.py (CANONICAL), config_validator.py, crt_engine_v2.py,
                               crt_gaussian_scorer.py, execution_planner.py, llm_scorer.py, llm_inference_client.py, ...

src/governance/    10 files — orchestrator.py (GOVERNANCE_CRITICAL), promotion_manager.py,
                               shadow_promotion_gate.py (DANGEROUS), reflection_buffer_advanced.py,
                               bitnet_governance_executor.py, strategy_backtest.py, ...

src/features/       8 files — feature_pipeline.py (CANONICAL), feature_monitor.py, feature_schema.py, ...

src/runtime/        7 files — backtest_v2.py (CANONICAL), backtest_bitnet.py (EXPERIMENTAL),
                               unified_replay_harness.py (EXPERIMENTAL), live_engine_hook.py, ...

src/bitnet/         8 files — bitnet_inference.py (VALIDATION_CRITICAL), bitnet_runner.py, ...

src/agent/         12 files — plan_compiler.py, intent_router.py, tool_registry.py, executor.py, ...

src/control_plane/  9 files — registry.py (47 CommandSpecs), server.py, jobs.py, dashboard_api.py, ...

src/inout/          2 files — alphavantage_candle_fetcher.py, hummingbot_candle_fetcher.py
                              (NO runner.py — archived)

src/llm_research/   — policy_builder.py (DANGEROUS: eval())
```

---

*This document is source-grounded. Every claim maps to a verified file and line number. "NOT VERIFIED IN SOURCE" is used when source code does not prove a claim.*
