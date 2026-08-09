# Architecture Memory — Reverse-Engineered System Knowledge (DEEP DETAIL)

> **Navigation first:** thin indexes live under [`docs/memory/`](../memory/README.md)
> (`architecture-memory.md` + subsystem `*-memory.md`). Per
> [`ARCHITECTURE_MEMORY_POLICY.md`](../memory/ARCHITECTURE_MEMORY_POLICY.md), do **not**
> load this full map every turn — load only when file-level contracts/diagrams/glossary
> are required after the thin memory doc.
>
> **Purpose:** Persistent deep architectural map for coding sessions (optional cold-start detail).
> **Not** user documentation. **Not** a code review. Fact extraction only.
> **Source-verified** against `src/` on branch `feature/truth-registry-v2`, active config `v2_multi_2026_04` (Tier 0: `configs/production/ACTIVE_VERSION`).
> **Companions:** [`signal-flow.md`](signal-flow.md) · [`entry-exit-map.md`](entry-exit-map.md) · [`service-boundary-map.md`](service-boundary-map.md) · [`services/decision-spine.md`](services/decision-spine.md)
> **Generated:** 2026-08-07 · extraction pass (read-only reverse-engineering)
> **Code wins** if this document and implementation differ.

---

## 0. Overall architecture (one paragraph)

Tradelatest is a **file-backed, single-process Python ≥3.10 quantitative trading system**. M15 OHLCV candles are scored by four mandatory engines (CRT, Gaussian, Zone Gate, RR), fused under weighted completeness, approved by `DecisionEngine` (semantic opportunity only), planned by `ExecutionPlannerV1_2`, and capital-gated by `UltronRiskGate`. Behavior is driven by one active production JSON (`ACTIVE_VERSION` pointer). There is **no database, no message broker, no cloud runtime dependency**. External control enters via three surfaces only: CLI scripts, control-plane HTTP (`localhost:8787`), and the agent REPL. An optional LLM is advisory (intent classification, arg fill, fusion uncertainty band) — never execution authority.

---

## 1. Layer hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│  EXTERNAL SURFACES                                              │
│  CLI scripts · agent REPL · control-plane HTTP (:8787)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  AGENT LAYER          IntentRouter → PlanCompiler → Executor     │
│  MODES                pipeline · copilot · governance · findings │
│                       · log_query                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ triggers / taps
┌────────────────────────────▼────────────────────────────────────┐
│  GOVERNANCE           ConfigValidator · PromotionManager ·       │
│                       ShadowPromotionGate · Orchestrator ·       │
│                       registries (script/hypothesis/framework)   │
└────────────────────────────┬────────────────────────────────────┘
                             │ promotes config / models
┌────────────────────────────▼────────────────────────────────────┐
│  CONFIG LAYER         ACTIVE_VERSION · production JSON ·         │
│                       ConfigBuilder · market_router · CRTConfig  │
│                       · ontology/formula registry                │
└────────────────────────────┬────────────────────────────────────┘
                             │ injects into
┌────────────────────────────▼────────────────────────────────────┐
│  RUNTIME              BacktestRunner · LiveEngineHook ·          │
│                       MultiInstrumentRunner · baseline_capture   │
└────────────────────────────┬────────────────────────────────────┘
                             │ per candle
┌────────────────────────────▼────────────────────────────────────┐
│  FEATURES             FeaturePipeline · CANONICAL_FEATURES ·     │
│                       candle_math · derived_math · formula_reg   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  ENGINES              TrapValidator · CRT · Gaussian · ZoneGate  │
│                       · RR  (+ optional BitNet/TradeNet stubs)   │
└────────────────────────────┬────────────────────────────────────┘
                             │ scores
┌────────────────────────────▼────────────────────────────────────┐
│  CORE (DECISION SPINE)                                           │
│  EngineRunner → FusionEngine → DecisionEngine                    │
│    → ExecutionPlannerV1_2 → UltronRiskGate                       │
│  (+ RegimeGovernor, AcceptanceController, Collector)             │
└────────────────────────────┬────────────────────────────────────┘
                             │ APPROVE plan
┌────────────────────────────▼────────────────────────────────────┐
│  EXECUTION / LIVE     MT5 bridge · Telegram · execution loop     │
│  (live path built; production caller loop largely unexercised)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  TELEMETRY            event_fabric · collector.jsonl · journals  │
│  CONTROL PLANE        JobManager · CommandSpec registry · APIs   │
└─────────────────────────────────────────────────────────────────┘
```

**Dependency doctrine:** Ingestion → Features → Scoring → Decision Spine → Execution/Risk. Telemetry is fan-out only (no import-back). LLM is dotted (advisory). Governance feeds config/models as files; it does not sit inside the per-candle hot path.

---

## 2. Critical file catalog (decision-path + control surfaces)

For each file: Identity · Purpose · Responsibilities · Inputs · Outputs · Runtime role · Dependencies (why) · Call graph · Business contract · Important objects · Config · Failure · Lifecycle.

### 2.1 Agent layer

#### `src/agent/cli.py`
| Field | Content |
|---|---|
| **Layer / Subsystem / Owner** | External surface / Agent / Agent |
| **Purpose** | Interactive REPL entry for natural-language trading automation. |
| **Primary responsibilities** | Parse `--resume`; load `agent` config section; construct `AgentCore`; loop `input → core.turn`. |
| **Secondary** | Safe defaults if config section absent; session resume from disk. |
| **Inputs** | `get_prod_section("agent")`; stdin; optional session id. |
| **Outputs** | Printed plan/steps/summary; session JSON under `logs/agent_sessions/`. |
| **Runtime role** | Startup + interactive Execution. |
| **Dependencies** | `agent` package import triggers mode tool registration; `AgentCore`, `AgentState`, production config. |
| **Call graph** | Operator → `main()` → `AgentCore.turn`. Called by: human / process manager. |
| **Business contract** | Every turn either executes a deterministic plan under confirm gates or asks for clarification; never bypasses tool safety. |
| **Important objects** | `main`, `_load_config`. |
| **Config** | `agent.enabled`, `intent_router.*`, `write_tools_enabled`, `max_iterations_per_turn`, paths. |
| **Failure** | Turn exceptions printed; process continues until exit. Disabled agent exits 0. |
| **Lifecycle** | Process lifetime; session saved each reply. |

#### `src/agent/agent_core.py` — `AgentCore`
| Field | Content |
|---|---|
| **Purpose** | Own one conversational turn end-to-end: classify → plan → fill args → dispatch → summarize. |
| **Primary** | Intent classification; plan compile + skip filters; step loop with confirm; audit session summary. |
| **Secondary** | Metrics extraction from tool results; outcome derivation. |
| **Inputs** | User NL string; conversation messages; config. |
| **Outputs** | Assistant reply string; audit records; updated `AgentState`. |
| **Runtime role** | Planning + Execution (agent). |
| **Dependencies** | `IntentRouter` (classify), `PlanCompiler` (deterministic steps), `ArgFiller` (missing args), `Executor` (safe dispatch), `AuditLogger` (append-only truth), `llm_chat` (optional). |
| **Call graph** | `cli.main` → `turn`. Calls tools via Executor. |
| **Business contract** | LLM never chooses tools or order — only intent and arg fill. Max iterations enforced. |
| **Important objects** | `AgentCore`, `_SKIP_RULES`. |
| **Config** | Same as agent section. |
| **Failure** | Unknown intent → ask_user; unknown tool → skip step; refuse/deny → break plan. |
| **Lifecycle** | One instance per CLI process; state per session. |

#### `src/agent/intent_router.py` — `IntentRouter`
| Field | Content |
|---|---|
| **Purpose** | Map free text to `{mode, intent_key, confidence}` without selecting tools. |
| **Primary** | Regex table (`intent_patterns.json`) then LLM classifier if below floor. |
| **Inputs** | User text; conversation tail; patterns file; `llm_chat`. |
| **Outputs** | Classification dict; `ask_user` if unclassifiable. |
| **Runtime role** | Planning (first stage). |
| **Business contract** | Valid intent_key only from known lists (pipeline/copilot/governance/cross); unknown LLM keys → `ask_user`. |
| **Config** | `intent_router.use_llm`, `llm_confidence_floor`, `regex_fallback_table`. |
| **Failure** | Missing patterns → regex disabled; LLM fail → ask_user. Execution continues as clarification. |

#### `src/agent/plan_compiler.py` — `PlanCompiler`, `PLAN_REGISTRY`
| Field | Content |
|---|---|
| **Purpose** | Deterministic intent → ordered tool sequence. **Single source of truth** for agent step graphs. |
| **Primary** | `build(intent_key)` / `filter(skip)`. |
| **Inputs** | `intent_key`; optional skip set. |
| **Outputs** | `Plan` of `ToolStep`s (fresh default_args copies). |
| **Runtime role** | Planning. |
| **Business contract** | No LLM involvement; unknown intent → empty `ask_user` plan. |
| **Important objects** | `ToolStep`, `Plan`, `PLAN_REGISTRY` (14+ intents: tune/validate/promote/backtest/copilot/governance/findings). |

#### `src/agent/tool_registry.py`
| Field | Content |
|---|---|
| **Purpose** | Global name→handler catalog for agent tools. |
| **Primary** | `@register_tool`; `get_tool`; `get_schema_text` for LLM prompts. |
| **Outputs** | Module-level `REGISTRY: Dict[str, ToolSpec]`. |
| **Business contract** | Duplicate registration raises; each tool declares `write` and `allowlist`. |
| **Lifecycle** | Populated at import of `agent.modes` (side-effect registration). |

#### `src/agent/executor.py` — `Executor`
| Field | Content |
|---|---|
| **Purpose** | Safe dispatch of registered tools with allowlist, path guard, confirm gate, audit. |
| **Primary** | `dispatch` / `dispatch_denied`. |
| **Inputs** | Tool name + args; `AgentState`; `write_tools_enabled`. |
| **Outputs** | Tool result · `PendingConfirmation` · `REFUSED:…` string. |
| **Business contract** | Write tools cannot run without `confirmed=True`; write paths limited to `configs/production/`, `logs/`, `results/`. Every outcome audited. |
| **Failure** | Handler exception → outcome `fail`, returns after audit; does not crash process. |

#### `src/agent/tool_planner.py` — `ArgFiller`
| Field | Content |
|---|---|
| **Purpose** | Fill missing *required* tool args from conversation via one LLM call. |
| **Business contract** | Does not pick tools or order; may return `clarify` question. No LLM call if args complete. |

#### `src/agent/state.py` — `AgentState`, `ToolCall`
| Field | Content |
|---|---|
| **Purpose** | Session memory (messages, tool log, mode/intent/plan ids). |
| **Outputs** | `logs/agent_sessions/<session_id>.json`. |
| **Lifecycle** | Created at core init; saved after every reply; loadable via `--resume`. |

#### `src/agent/audit.py` — `AuditLogger`
| Field | Content |
|---|---|
| **Purpose** | Append-only audit of tool steps and session summaries. |
| **Outputs** | `logs/agent_audit.jsonl`, `logs/agent_intent_log.jsonl` (hashed args/results). |

#### `src/agent/groq_client.py`, `findings_synthesizer.py`, `log_query.py`
| Field | Content |
|---|---|
| **Purpose** | Optional Groq-backed findings synthesis; read-only log index queries for agent tools. |
| **Runtime role** | Reporting / Research assistance (agent modes). |

### 2.2 Modes (tool registration side-effects)

#### `src/agent/modes/__init__.py`
Imports all mode modules to register tools into `REGISTRY`.

#### `src/agent/modes/pipeline_mode.py`
| Field | Content |
|---|---|
| **Purpose** | Register pipeline tools that *trigger* offline workflow (tune → validate → promote → backtest → live dry-run). |
| **Tools** | `tuner.run_multi` (WRITE, subprocess auto_tuner), `validator.validate`, `promotion.promote_from_checkpoint` (WRITE), `backtest.run_v2`, `live_hook.dry_run` / enable. |
| **Business contract** | Does not bypass ConfigValidator or PromotionManager gates; write tools still confirm-gated. |

#### `src/agent/modes/copilot_mode.py`
| Field | Content |
|---|---|
| **Purpose** | Read-only live co-pilot tools: score → explain fusion → plan → risk check → advise veto/resize. |
| **Tools** | `engine.run`, `fusion.explain`, `planner.plan`, `risk.check`, `advise.veto`, `advise.resize`, `collector.tail`. |
| **Business contract** | Never places orders; Ultron remains capital authority; all `write=False`. |

#### `src/agent/modes/governance_mode.py`
| Field | Content |
|---|---|
| **Purpose** | Meta-governance tools: reflection merge, meta-governor dry-run, shadow stage, governance loop, audit tail. |
| **Write** | Only `governance.run_loop` is write (may promote via ShadowPromotionGate). |

#### `src/agent/modes/findings_mode.py` / `log_query_mode.py`
| Field | Content |
|---|---|
| **Purpose** | On-demand findings synthesis/list/explain; read-only run/trade log queries. |

### 2.3 Core (decision spine)

#### `src/core/engine_runner.py` — `EngineRunner`
| Field | Content |
|---|---|
| **Layer** | Core / Decision orchestration / Decision Spine |
| **Purpose** | Orchestrate one bar’s full score→fuse→decide path with completeness enforcement. |
| **Primary pipeline** | Trap adapter gate → four engines unconditional → completeness → (optional rr_fusion) → Fusion → Decision → RegimeGovernor (signal quality) → Collector; optional CognitiveBus async. |
| **Secondary** | Dual-engine regime routing; acceptance/convergence controllers; audit recorder; enveloped telemetry fail-open. |
| **Inputs** | Feature dict + context; full production config sections via strict `_cfg_require`; model artifacts (zone registry, optional rr_fusion). |
| **Outputs** | Decision dict (`ACCEPT`/`REJECT` + scores + reason + reject_stage); collector log line; optional JSONL telemetry. |
| **Runtime role** | Execution (hot path per bar when engine gate on). |
| **Dependencies** | Engines for scores; `FusionEngine` aggregates; `DecisionEngine` semantic gate; `Collector` observability; zone via `live_engine.get_zone_gate`; config production sections. |
| **Call graph** | Called by: `BacktestRunner` (when gate on), `live_engine_hook`, agent `engine.run`, strategies. Calls: engines, fusion, decision, governors. |
| **Business contract** | `EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}` all present before fusion; missing engine → hard reject (no silent partial fusion ACCEPT). |
| **Config** | `engine_runner.*` (weights nested fusion, dual_engine, zone_gate, rr_fusion.enabled, fusion_use_evaluate, ultron_gate_enabled for RegimeGovernor, etc.), `crt_engine.score_component_weights`, `fusion_engine.*`, `decision_engine.*`. |
| **Failure** | Returns structured REJECT; CognitiveBus fail non-blocking; telemetry fail-open. |
| **Lifecycle** | Constructed per runner with config; engines held for process lifetime of runner. |

#### `src/core/fusion_engine.py` — `FusionEngine`
| Field | Content |
|---|---|
| **Purpose** | Weighted multi-engine score combination + optional LLM uncertainty-band tie-breaker + dead-engine neutralization + rolling normalization. |
| **Business contract** | Clear scores outside LLM band never call LLM; LLM fail-open to neutral; dead engines (mean/var 0) excluded from average. |
| **Important objects** | `ScoreNormalizer`, `EngineHealthTracker`, `FusionConfig`, `GaussianAdapter`. |
| **Runtime role** | Inference / Execution (spine). |

#### `src/core/decision_engine.py` — `DecisionEngine`
| Field | Content |
|---|---|
| **Purpose** | Sole **semantic** execute-vs-reject authority (market opportunity), **not** economics. |
| **Business contract** | Gates fused score, p_win, zone validity, weak-component. **Does not** gate reward:risk (F-048: RR gate removed; economics owned by UltronRiskGate). |
| **Outputs** | Frozen `DecisionResult` (decision, reason, confidence, threshold_used, reject_stage). |
| **Config** | `decision_engine.score_threshold`, `p_win_threshold`, fallback_top_n, etc. — all strict. |

#### `src/core/ultron_risk_gate.py` — `UltronRiskGate`
| Field | Content |
|---|---|
| **Purpose** | Final **capital protection** layer: TTL, cost-taxed min RR, daily trade limit, kill switch, portfolio exposure, SL distance, final position size. |
| **Business contract** | Deterministic hard-reject on first failed check; no partial override; kill-switch state file `logs/kill_switch_state.json`. Distinct from `RegimeGovernor` (signal quality inside EngineRunner). |
| **Call graph** | After planner in live_engine_hook / copilot risk.check / backtest paths that invoke risk. |
| **Config** | `ultron_risk_gate.*` (max_risk_per_trade_pct, max_portfolio_risk_pct, max_trades_per_day, max_daily_loss_pct, min_rr_ratio, spread/slippage pips, min_sl_pips, disabled). |

#### `src/core/regime_governor.py` — `RegimeGovernor` / alias `UltronGovernor`
| Field | Content |
|---|---|
| **Purpose** | Signal-quality filter **inside** EngineRunner (regime penalties, quotas). Not capital gate. |

#### Other core modules (role summary)
| File | Business capability |
|---|---|
| `acceptance_controller.py` | Adaptive acceptance theta control from prod config. |
| `convergence_controller.py` | Stability/convergence behavior for fusion. |
| `collector.py` | Structured decision logging (`logs/collector.jsonl`). |
| `dynamic_threshold.py` | Percentile threshold calibration for DecisionEngine. |
| `gate_intelligence.py` | Intent/vol/liquidity/structure gate + CRT level computation (`compute_crt_levels`). |
| `model_registry.py` | Atomic model promotion + GOV-3 margin gate to `models/`. |
| `feature_store.py` | Feature storage/access for runners. |
| `signal_audit.py` | Debug-mode signal path audit. |
| `signal_belief_tracker.py` | Optional multi-bar conviction accumulation (injected, not owned). |
| `hierarchical_meta_fusion.py` | Higher-order fusion (sidecar/advanced). |
| `types.py` | Shared spine types (`EngineRunnerOutput`, `GateResult`, …). |
| `backtest_port.py` | Interface seam for governance→backtest inversion. |
| `governance_mode.py` (core) | Core-side governance mode helpers if present. |

### 2.4 Config layer

#### `src/config_layer/production_config.py`
| Field | Content |
|---|---|
| **Purpose** | **Tier-0 runtime config authority**: resolve active version, load registry JSON, verify params hash, build instrument CRTConfig, expose sections. |
| **Business contract** | Missing `ACTIVE_VERSION` or registry file → RuntimeError (never silent engine defaults). Hash mismatch → RuntimeError. `PROD_VERSION = get_active_version()` at import. |
| **Important APIs** | `get_active_version`, `get_prod_config(instrument)`, `get_prod_section(name)`, `load_prod_config_from_registry`. |
| **Dependencies** | `ConfigBuilder`, `CRTConfig`, filesystem under `configs/production/`. |

#### `src/config_layer/config_builder.py` — `ConfigBuilder`
| Field | Content |
|---|---|
| **Purpose** | Single factory for immutable `CRTConfig` (router base ± allowed overrides). |
| **Business contract** | All application CRTConfig creation goes through `build`; unknown override keys fail; frozen dataclass. |

#### `src/config_layer/market_router.py`
| Field | Content |
|---|---|
| **Purpose** | Classify instrument FOREX vs CRYPTO and supply base CRT profile knobs. |

#### `src/config_layer/config_validator.py` — `ConfigValidator`
| Field | Content |
|---|---|
| **Purpose** | Pre-promotion quality gate: backtest candidate params → fitness → hard/soft gates → `ValidationReport`. |
| **Business contract** | Only `decision == "APPROVE"` may promote; hard gates min trades / max DD / min fitness; soft WR/expectancy/cross-instrument variance. |
| **Dependencies** | Runs `BacktestRunner` per instrument (known upward import). |

#### `src/config_layer/execution_planner.py` — `ExecutionPlannerV1_2`
| Field | Content |
|---|---|
| **Purpose** | Classify trade intent, derive entry/TTL/execution_id, gate via GateIntelligence; levels via CRT path. |
| **Business contract** | Layer 2 of spine; pure/deterministic; unknown intent rejectable; required feature keys enforced. |
| **Config** | `execution_planner` TTLs, risk_percent, precision, gate weights/threshold. |

#### `src/config_layer/crt_engine_v2.py`
| Field | Content |
|---|---|
| **Purpose** | Authoritative CRT state machine (RANGE→…→RESOLUTION + SHADOW_PENDING + EXPIRED branches), candle/range/trade objects, live detection logic. |
| **Business contract** | Legal transitions only (`VALID_TRANSITIONS` via `state_identity`/`state_topology`); golden path + shadow/TTL branches. |
| **Runtime role** | Feature Engineering / Execution (spine CRT engine + backtest CRT path). |

#### Other config_layer (role)
| File | Capability |
|---|---|
| `state_identity.py` / `state_topology.py` / `state_contract*.py` | CRT state enums, legal transitions, contract loading. |
| `llm_inference_client.py` | Local llama.cpp + Groq chat/score; circuit open → neutral. |
| `llm_scorer.py` / `llm_narrative.py` | Score/narrative wrappers. |
| `model_paths.py` / `model_resolver.py` | WHO/HOW model path resolution + identity parity. |
| `rr/*` | RR dataset, pattern miner, fusion layer, inference. |
| `goal_schema.py` / `goal_validator.py` | Goal-layer schema validation. |
| `production_bundle.py` / `stack_version.py` | Bundle/version helpers. |
| `crt_gaussian_scorer.py` / `crt_sweep_taxonomy.py` | CRT-adjacent scoring taxonomy. |
| `insight_reporter.py` | Human-readable insight reporting. |

### 2.5 Engines

| File | Business capability | Spine role |
|---|---|---|
| `trap_validator_engine.py` | Hard adapter pre-gate (score ≤0 → reject). | Step 0 |
| `crt_engine.py` | CRT component score for fusion. | EXPECTED |
| `heuristic_gaussian_engine.py` | Live Gaussian channel (heuristic). | EXPECTED (default impl) |
| `ml_gaussian_engine.py` | ML Gaussian channel (shadow/alternate). | Optional via `gaussian_impl` |
| `zone_gate_engine.py` / `zone_cluster_score.py` | Geometric zone hard/soft scoring. | EXPECTED |
| `rr_engine.py` | RR polarity/score for fusion. | EXPECTED |
| `live_engine.py` | Zone gate factory + live engine base. | Support |
| `llm_engine.py` | LLM scoring engine (advisory/optional). | Optional |
| `tradenet_meta_engine.py` | TradeNet meta (built, fusion neural slot largely unwired F-005). | Sidecar |
| `scoring_engine.py` | Shared scoring helpers. | Support |

### 2.6 Features

| File | Business capability |
|---|---|
| `feature_schema.py` | **Canonical vector identity** (`CANONICAL_FEATURES`, SCHEMA_HASH, FEATURE_ORDER_HASH). |
| `feature_pipeline.py` | Batch/stream feature build → 38/39-dim vectors (config-driven periods). |
| `candle_math.py` | Immutable geometric primitives (body/range etc.). |
| `derived_math.py` | Scalar derived metrics (FM-xxx). |
| `formula_registry.py` + `registry/*` | Ontology-backed formula authority (no local re-derivation). |
| `feature_monitor.py` | Drift Z-score on trade opens. |
| `broker_clock.py` | Session timestamp basis (broker_local vs utc_corrected). |
| `crt_state_resolver.py` | Declarative CRT state resolution (parity program). |
| `dataset_builder.py` / `dataset_validator.py` | Training dataset construction/validation. |

### 2.7 Governance

| File | Business capability |
|---|---|
| `promotion_manager.py` | Move APPROVE’d config → production registry + ACTIVE_VERSION + promotion_log.jsonl + SHA-256. Never builds CRTEngine. |
| `shadow_promotion_gate.py` | Stage candidate + shadow backtest + promote-if-superior gates. |
| `orchestrator.py` | Full 4-step meta-governance loop (reflection → BitNet patch → shadow). |
| `reflection_buffer_advanced.py` | Merge collector+trades → meta prompt. |
| `bitnet_governance_executor.py` | BitNet inference + patch extract/validate for meta-governor. |
| `portfolio_validation.py` | Multi-instrument portfolio validation. |
| `strategy_backtest.py` | Strategy-level backtest helpers. |
| `config_integrity.py` | Integrity check utilities (runtime orphan noted F-006). |
| `script_registry.py` / `script_census.py` / `script_seed.py` | Script inventory governance (SITS). |
| `hypothesis_registry.py` / `framework_registry.py` / `findings_export.py` | Machine-readable research registries. |
| `multi_strategy_validator.py` | Multi-strategy validation. |
| `expansion_integration.py` | Expansion engine integration. |

### 2.8 Runtime

| File | Business capability |
|---|---|
| `backtest_v2.py` | **Primary exercised execution harness**: candle stream (L1/L2 integrity), features, CRT state machine, optional EngineRunner gate, capital/slippage/spread, metrics, reports. Classes: `CandleLoader`, `BacktestRunner`, `MultiInstrumentRunner`, `BacktestConfig`, trade/metrics/report writers. |
| `live_engine_hook.py` | Live candle → EngineRunner → planner → Ultron → MT5/Telegram. **Entry exists; production loop largely NO-CALLER (F-010/F-013).** |
| `baseline_capture.py` | Capture schema hash, model registry, config SHA for phase baselines. |
| `unified_replay_harness.py` | Deterministic replay harness. |
| `analyze_fusion_shadow.py` / `backtest_bitnet.py` / `crt_baseline_trace.py` / `exit_model_band.py` | Specialized runtime analysis arms. |

### 2.9 Control plane

| File | Business capability |
|---|---|
| `registry.py` | `CommandSpec` catalog (~45 commands) + workflow stages + quickstart notes — authority for CLI matrix. |
| `server.py` | ThreadingHTTPServer localhost:8787 — commands, runs, dashboard, reports, agent audit APIs. |
| `jobs.py` | JobManager process execution for command runs. |
| `dashboard_api.py` / `report_api.py` / `context_report.py` | HTTP API surfaces. |
| `code_context_extractor.py` / `dot_graph_context.py` | Code/graph context for UI. |
| `monitors.py` / `cp_types.py` | Monitors + ArgSpec/CommandSpec types. |

### 2.10 Adjacent subsystems (compressed)

| Subsystem | Path | Purpose |
|---|---|---|
| Data ingestion | `src/data_ingestion/` | OHLCV schema, L3 dataset integrity, historical fetch. |
| Inout fetchers | `src/inout/` | MT5/AlphaVantage/Hummingbot/perp funding → CSV. |
| Strategies | `src/strategies/` | S01–S10 wrappers + orchestrator/registry (portfolio path partly orphaned F-013). |
| Training | `src/training/` | Train pipeline, TradeNet v2, Phase-5 calibration, stage1 datasets. |
| BitNet | `src/bitnet/` | Zone/gate model stack (inert when `use_bitnet:false`). |
| Research | `src/research/` | Large offline research fleet (hypotheses, regimes, weekly sweep, etc.). |
| Interpreters | `src/interpreters/` | Ontology interpreters (P&F, regime observer). |
| Portfolio | `src/portfolio/` | Allocator, exposure, correlation (built; live often single-candle spine). |
| Replay memory | `src/replay/` | Similarity/drift/timing (sidecar). |
| Cognitive | `src/cognitive/` | CognitiveBus async advisory telemetry. |
| Events | `src/events/` | Canonical event envelopes. |
| Journal | `src/journal/` | Trade identity/provenance logging. |
| Live bridges | `src/live/` | MT5 + Telegram. |
| Execution | `src/execution/` | Loop, intents, alerts, override. |
| Expansion | `src/expansion/` | Bounded parameter search policies. |
| Scanner | `src/scanner/` | Universe scan → signal pool → spine adapter. |
| Analytics | `src/analytics/` | Metrics oracle, clustering, SL/TP compare. |
| Retrieval | `src/retrieval/` | RAG corpus/vector store for agent context. |
| Multi-LLM | `src/multi_llm/` + repo `multi_llm/` | Cross-model turn ledger / context packs. |
| UAT | `src/uat/` | Kill switch / Monte Carlo / UAT runner. |
| Utils | `src/utils/` | Logging, console_safe, trade_logger, integrity events. |
| Validation access | `src/validation_access/` | Authority ladder surfaces for research claims. |

---

## 3. Subsystem summaries

### 3.1 Agent Layer
| | |
|---|---|
| **Purpose** | Translate operator natural language into audited, confirm-gated tool execution without granting LLM execution authority. |
| **Responsibilities** | Intent classification; deterministic planning; arg fill; dispatch safety; session memory; audit. |
| **Entry points** | `python -m src.agent.cli`; control-plane agent APIs reading audit JSONL. |
| **Exit points** | Tool side-effects (subprocess scripts, promotion, JSONL); session/audit files. |
| **Dependencies** | Config layer (`agent` section, `llm_chat`); tool handlers reach core/governance/runtime. |
| **Runtime interactions** | Pipeline triggers offline workflow; copilot taps spine read-only; governance triggers meta-loop. |
| **Business importance** | Human operator surface for automation; safety boundary (path guard + y/N + allowlist). |

### 3.2 Modes
| | |
|---|---|
| **Purpose** | Partition tools by operational intent and register them into `REGISTRY` at import. |
| **Responsibilities** | Bind tool names to domain handlers; declare write flags; no business logic ownership beyond thin wrappers. |
| **Entry** | Import via `agent/__init__` → `modes/__init__`. |
| **Exit** | Registered handlers invoked by Executor. |
| **Relationships** | pipeline ⊃ tune/validate/promote/backtest; copilot ⊃ advise; governance ⊃ meta; findings/log_query cross-cutting. |

### 3.3 Core
| | |
|---|---|
| **Purpose** | Per-bar decision spine: complete scores → fusion → semantic decision → (planner external) → capital risk. |
| **Responsibilities** | Completeness policy; fusion weights; semantic APPROVE/REJECT; capital checks; decision logging. |
| **Entry** | `EngineRunner.run`, `UltronRiskGate.evaluate`, planner (config_layer). |
| **Exit** | Decision dicts, GateResult, collector/telemetry JSONL. |
| **Importance** | Load-bearing economic decision path; highest correctness sensitivity. |

### 3.4 Config Layer
| | |
|---|---|
| **Purpose** | Single production config truth + CRTConfig factory + validation gate + execution plan geometry. |
| **Responsibilities** | ACTIVE_VERSION resolution; hash verify; section access; CRTConfig build; pre-promotion validation; planner. |
| **Entry** | Import `production_config` (resolves version); `ConfigValidator.validate`; `ConfigBuilder.build`. |
| **Exit** | Immutable CRTConfig / dict sections / ValidationReport / ExecutionPlan. |
| **Importance** | Prevents split-brain (F-016 doctrine); fail-fast on missing/tampered config. |

### 3.5 Governance
| | |
|---|---|
| **Purpose** | Move research artifacts into production only under APPROVE + audit; meta-govern via shadow tests. |
| **Responsibilities** | Promote configs/models; shadow gate; reflection; script/hypothesis registries; portfolio validation. |
| **Entry** | CLI promotion_manager; agent tools; orchestrator CLI; control-plane commands. |
| **Exit** | `configs/production/*.json`, `ACTIVE_VERSION`, `promotion_log.jsonl`, model registries. |
| **Importance** | Sole path to change production behavior safely. |

### 3.6 Runtime
| | |
|---|---|
| **Purpose** | Exercise the spine over historical candles (backtest) or live ticks (hook). |
| **Responsibilities** | Stream integrity; feature build; CRT state; optional fusion gate; capital simulation; artifacts. |
| **Entry** | `backtest_v2.main` / `BacktestRunner.run`; `HookedLiveEngine.process`. |
| **Exit** | `results/*_trades.csv`, `*_summary.json`, `*_events.jsonl`; live orders if wired. |
| **Importance** | Primary proof surface for behavior; live path code-complete but under-called. |

### 3.7 Control Plane
| | |
|---|---|
| **Purpose** | Localhost catalog + job runner + dashboards over the same scripts agents invoke. |
| **Responsibilities** | CommandSpec registry; HTTP routes; job lifecycle; reports/context. |
| **Entry** | `server.py` on :8787. |
| **Exit** | Subprocess jobs; JSON API responses; no broker authority. |
| **Importance** | Operator UI for workflows; must stay localhost-only (no auth). |

---

## 4. Execution flows

### 4.1 Agent CLI startup → response
```
python -m src.agent.cli [--resume ses_…]
  → import agent → modes → @register_tool fills REGISTRY
  → get_prod_section("agent") | defaults
  → AgentCore(config)
  → [optional] AgentState.load(session_id)
  → REPL loop:
       user_input
         → IntentRouter.classify (regex ≥ floor else LLM)
         → if ask_user: clarify reply
         → PlanCompiler.build(intent_key)
         → filter skip phrases
         → for step in plan:
              ArgFiller.fill missing required args
              Executor.dispatch
                allowlist → path guard → confirm y/N if write
                handler(**args)  # may reach core/governance/scripts
              audit write_step
         → session summary audit + state.save
         → print summary
```

### 4.2 Candle → order (decision spine)
```
Candle (CSV stream | live trade_data)
  → FeaturePipeline / live feature map  (CANONICAL_FEATURES)
  → EngineRunner.run(features, context)
       TrapValidator (hard)
       CRT + Gaussian + ZoneGate + RR (all mandatory)
       completeness gate
       [optional] RRFusionLayer if enabled
       FusionEngine → final_score
       DecisionEngine → semantic GO/REJECT
       RegimeGovernor (if ultron_gate_enabled)  # signal quality, not capital
       Collector.log
  → [if GO] ExecutionPlannerV1_2.plan + gate_intelligence levels
  → UltronRiskGate.evaluate(plan, portfolio)  # capital
  → [if APPROVE] broker stub / MT5Bridge / backtest fill simulation
  → TRADE_OPENED / journal / events
```

### 4.3 Backtest flow
```
CLI / MultiInstrumentRunner / ConfigValidator / agent backtest.run_v2
  → BacktestConfig + load ACTIVE / versioned prod config
  → optional L3 validate_dataset (backtest_v2 path)
  → CandleLoader.stream (L1/L2 always)
  → FeaturePipeline (batch/stream)
  → per candle: CRTEngine state machine + optional EngineRunner (engine_gate_enabled)
  → capital curve, slippage, spread, distribution
  → ReportWriter → results/{instrument}_{trades,summary,events}
```

### 4.4 Governance / promotion flow
```
AutoTuner → results/tuner/checkpoint_multi.json
  → ConfigValidator.validate(params, csv_paths) → ValidationReport
  → PromotionManager.promote_* requires decision==APPROVE
  → merge onto full-config base (sentinel engine_runner)
  → write configs/production/{version}.json
  → update ACTIVE_VERSION
  → append configs/promotion_log.jsonl (PROMOTED | PROMOTION_FAILED)
  → SHA-256 config_hash embedded
```

### 4.5 Meta-governance (orchestrator) flow
```
ReflectionBuffer.load_and_merge(collector, trades)
  → generate_prompt_payload → meta_prompt.txt
  → MetaGovernorExecutor.run_inference (BitNet)
  → extract_and_validate_config patch
  → ShadowPromotionGate.stage_candidate
  → execute_shadow_test
  → promote_if_superior (sample + PnL gates)
```

### 4.6 Research flow (pattern)
```
scripts/research/* or src/research/*
  → load candles (often L1/L2 only — F-039)
  → hypothesis interpreters / scanners
  → measurement contracts (OPEN program)
  → findings → docs/current-findings.md (+ export JSONL)
  → NO automatic promotion authority (Authority Ladder §6.5)
```

### 4.7 Copilot flow
```
advise_signal | veto_query | resize_query
  → engine.run → fusion.explain → [planner.plan → risk.check] → advise.*
  → narrative only; no order placement
```

### 4.8 Pipeline flow (agent)
```
full_pipeline:
  tuner.run_multi → validator.validate → promotion.promote_from_checkpoint
  → backtest.run_v2 → live_hook.dry_run
(partial intents omit steps; skip phrases strip steps)
```

### 4.9 Findings / log query flows
```
findings_synthesize(run_id) → Groq synthesize → append logs/agent_findings.jsonl (WRITE confirm)
findings_list_recent / findings_explain → read
log.get_run / get_trade / query → read execution memory indices
```

### 4.10 Training kitchen (async feeder)
```
opportunities.jsonl (scanner)
  → phase5_calibration / discover_zones / rr_dataset + train_rr
  → ModelRegistry.promote (margin gate)
  → models/* artifacts consumed by engines at next load
```

---

## 5. Architecture diagrams

### 5.1 Dependency graph (runtime-critical)
```
production_config (ACTIVE_VERSION)
        │
        ▼
 ConfigBuilder / market_router ──► CRTConfig
        │
        ▼
 BacktestRunner / LiveEngineHook / EngineRunner
        │
        ├─► FeaturePipeline ──► CANONICAL_FEATURES
        │
        ├─► engines{crt,gaussian,zone,rr}
        │         │
        │         ▼
        ├─► FusionEngine ──► DecisionEngine
        │         │
        │         ▼
        ├─► ExecutionPlannerV1_2 ──► UltronRiskGate
        │
        └─► Collector / event_fabric ──► logs/*.jsonl

PromotionManager ──writes──► production_config files
ConfigValidator ──uses──► BacktestRunner
Agent Executor ──calls──► tools → (core|governance|scripts)
ControlPlane ──jobs──► same scripts as CLI
```

### 5.2 Runtime call graph (one bar, gate-ON)
```
BacktestRunner.step / HookedLiveEngine.process
  └─ EngineRunner.run
       ├─ TrapValidatorEngine
       ├─ crt_compute / Gaussian / ZoneGate / RREngine
       ├─ [RRFusionLayer.score?]
       ├─ FusionEngine.compute|evaluate
       ├─ DecisionEngine.evaluate
       ├─ RegimeGovernor.evaluate?
       └─ Collector.log
  └─ ExecutionPlannerV1_2.plan   (if accept path)
  └─ UltronRiskGate.evaluate
  └─ fill / order / journal
```

### 5.3 Subsystem communication
```
[Operator]
   │ NL          │ HTTP           │ CLI
   ▼             ▼                ▼
 Agent        ControlPlane     scripts/*
   │             │                │
   └─────┬───────┴────────────────┘
         ▼
   Governance / Training / Runtime
         │ files only (config, models, results)
         ▼
   Decision Spine (core+engines+features)
         │
         ▼
   Logs / Results / (optional) Broker
```

### 5.4 Mode relationships
```
              PLAN_REGISTRY intents
                     │
     ┌───────────────┼───────────────┬──────────────┐
     ▼               ▼               ▼              ▼
 pipeline         copilot       governance      findings/log
 (WRITE-capable)  (READ-only)   (mostly RO;     (RO + synthesize W)
  triggers         taps spine    run_loop W)
  kitchens
```

### 5.5 Configuration flow
```
ACTIVE_VERSION ──► {version}.json ──hash verify──► get_prod_section / get_prod_config
                                                      │
                    market_router base ◄──────────────┤
                                                      ▼
                                              ConfigBuilder.build → CRTConfig
                                                      │
                         injected into EngineRunner, planner, gates, backtest
```

### 5.6 Decision ownership (post F-048)
```
DecisionEngine     → semantic opportunity (score / p_win / zone / weak)
ExecutionPlanner   → intent + entry + TTL + levels path
UltronRiskGate     → economic RR (cost-taxed) + capital + size + kill switch
LLM                → advisory only (never capital authority)
```

---

## 6. Architecture glossary

| Term | Definition |
|---|---|
| **ACTIVE_VERSION** | Pointer file `configs/production/ACTIVE_VERSION`; Tier-0 runtime config identity. |
| **AgentCore** | Main agent turn loop owner. |
| **ArgFiller** | LLM helper that only fills missing required tool args. |
| **AuditLogger** | Append-only agent step/session audit. |
| **BacktestRunner** | Candle-by-candle historical harness with capital model. |
| **CANONICAL_FEATURES** | Ordered feature vector identity; schema hash load-bearing. |
| **CandleLoader** | Streaming OHLCV reader with L1/L2 integrity. |
| **CognitiveBus** | Async advisory telemetry bus; non-blocking; not in return dict. |
| **Collector** | Spine decision logger (`collector.jsonl`). |
| **CommandSpec** | Control-plane command catalog entry (argv template + params). |
| **ConfigBuilder** | Sole factory for frozen `CRTConfig`. |
| **ConfigValidator** | Pre-promotion backtest quality gate → ValidationReport. |
| **CRT / CRTEngine** | ICT/CRT-style state machine producing structural setup detection. |
| **CRTConfig** | Frozen dataclass of CRT behavioral/structural knobs. |
| **DecisionEngine** | Semantic opportunity gate only (not economics). |
| **DecisionResult** | Frozen decision output (decision/reason/confidence/stage). |
| **EngineRunner** | Orchestrator ensuring four engines + fusion + decision. |
| **EXPECTED_ENGINES** | `{crt, gaussian, zone_gate, rr}` completeness set. |
| **ExecutionPlannerV1_2** | Intent/entry/TTL planner layer before capital gate. |
| **Executor (agent)** | Confirm-gated tool dispatcher with path guard. |
| **FeaturePipeline** | Builds canonical feature frame/vectors from OHLCV. |
| **FusionEngine** | Weighted multi-engine score blender + optional LLM band. |
| **GateIntelligence** | Multi-factor approval score + CRT level computation. |
| **GovernanceOrchestrator** | 4-step meta loop: reflect → BitNet patch → shadow promote. |
| **IntentRouter** | Regex+LLM classifier → intent_key (not tools). |
| **JobManager** | Control-plane background job runner. |
| **MetaGovernorExecutor** | BitNet inference for config patch proposals. |
| **ModelRegistry** | Atomic model artifact promotion with margin gate. |
| **PLAN_REGISTRY** | Deterministic intent→tool sequence table. |
| **PlanCompiler** | Builds Plan from PLAN_REGISTRY. |
| **PromotionManager** | Sole production config promotion path. |
| **ReflectionBuffer** | Merges decisions+outcomes into meta-governor prompt. |
| **RegimeGovernor** | In-runner signal quality filter (not Ultron capital). |
| **REGISTRY (tools)** | Global agent ToolSpec map. |
| **RREngine / RRFusionLayer** | RR score engine; optional fusion layer (often disabled F-038). |
| **ShadowPromotionGate** | Shadow-test then conditional promote. |
| **ToolSpec** | Tool metadata (schema, handler, write, allowlist). |
| **TrapValidatorEngine** | Hard pre-adapter gate before engines. |
| **UltronRiskGate** | Final capital protection + sizing + kill switch. |
| **ValidationReport** | APPROVE/REJECT package from ConfigValidator. |
| **Zone Gate** | Geometric zone registry hard/soft filter. |

---

## 7. Architectural contracts

### 7.1 Single sources of truth
| Concern | Authority |
|---|---|
| Active production version | `configs/production/ACTIVE_VERSION` |
| Tunable behavior | Active production JSON (`v2_multi_2026_04` on this branch) |
| CRTConfig construction | `ConfigBuilder` (+ market_router profiles) |
| Feature vector identity | `features/feature_schema.py` `CANONICAL_FEATURES` |
| Feature math meaning | `configs/formulas/market_ontology.yaml` + `features/registry` |
| Agent tool sequences | `plan_compiler.PLAN_REGISTRY` |
| Agent tools | `tool_registry.REGISTRY` (modes register) |
| Control-plane commands | `control_plane/registry.py` |
| CRT legal transitions | `state_identity` / `state_topology` |
| Model intent | MIAR (`MODEL_INTENT_AUTHORITY_REGISTER`) |
| Conclusions | `docs/current-findings.md` |

### 7.2 Shared registries
- Production config registry dir + promotion_log.jsonl
- `models/*_registry.json` (gaussian, zone, rr, bitnet, tradenet)
- Agent `REGISTRY` (tools)
- Control-plane `CommandSpec` list
- Script / hypothesis / framework registries (governance seeds → `data/*.jsonl` generated)

### 7.3 Global / process state
- `PROD_VERSION` resolved at `production_config` import
- Module-level tool `REGISTRY`
- LLM fail counters / circuit open (advisory)
- Kill-switch file for Ultron
- Live engine hook singletons (MT5/Telegram/etc.)
- No shared DB

### 7.4 Runtime invariants
1. Four expected engines present before ACCEPT via fusion.
2. No lookahead in backtest stream (generator + integrity).
3. Config missing required keys → fail-fast (strict `_require`).
4. Promotion requires ValidationReport APPROVE.
5. Config hash must match stored hash on load.
6. LLM never sole execution authority.
7. DecisionEngine ≠ economics; Ultron owns capital RR.
8. Write agent tools require y/N + path roots.
9. Control plane localhost-only assumption.
10. Schema/feature hash changes invalidate baselines/models.

### 7.5 Initialization order (typical process)
1. Path bootstrap (`src/` on sys.path)
2. Import production_config → read ACTIVE_VERSION → load JSON
3. Build CRTConfig / inject sections into runners
4. Construct engines/models (lazy or at runner init)
5. Stream candles → per-bar spine
6. Flush reports/logs on completion

Agent-specific:
1. Import agent → modes register tools
2. Load agent config section
3. Construct AgentCore (audit, state, router, executor)
4. Per turn as §4.1

### 7.6 Critical dependencies
- Spine cannot ACCEPT without four engines.
- Promotion cannot proceed without ConfigValidator path (or equivalent APPROVE report).
- Live capital path depends on Ultron after planner.
- Agent write tools depend on Executor confirm.
- Feature consumers depend on schema identity match.

### 7.7 Execution assumptions
- File system is durable store for all truth artifacts.
- Single active config version per process.
- Backtest is the primary exercised economic path today.
- Live hook may be unwired at top-level loop (code present).
- Research results do not auto-grant production authority.

---

## 8. Failure behaviour matrix (spine + agent)

| Failure | Effect | Continue? |
|---|---|---|
| Missing ACTIVE_VERSION / hash fail | RuntimeError at config load | No (fail-fast) |
| Missing expected engine | EngineRunner REJECT | Yes (next bar) |
| Fusion/decision reject | Structured REJECT logged | Yes |
| Ultron reject | No order / no size | Yes |
| LLM timeout | Neutral 1.0 / skip LLM / ask_user | Yes (fail-open) |
| Agent write denied | Plan stops | Yes (session continues) |
| Tool handler exception | outcome=fail, audited | Yes |
| CognitiveBus fail | Warning only | Yes |
| Telemetry write fail | Swallowed fail-open | Yes |
| Promotion without APPROVE | PROMOTION_FAILED log | Yes (no prod change) |

---

## 9. CLAUDE.md-ready architecture knowledge (concise)

Pasteable thin section — see §9 block at end of extraction response; also intended as CLAUDE.md companion pointer to this file:

**Load this file when:** cold-starting on architecture, agent wiring, spine ownership, config authority, or “who calls whom”.

**Do not use this file for:** code review, refactor proposals, economic findings (use `current-findings.md`).

---

## 10. Authority notes (factual, not critique)

- Active config on extraction branch: **`v2_multi_2026_04`**.
- Live production caller for `live_engine_hook.process` is largely **absent** (entry-exit map).
- Fusion engine gate in backtest is config-keyed (`backtest.engine_gate_enabled`); historical research often measured CRT-only path.
- `rr_fusion.enabled` is **false** on active lineage (F-038).
- BitNet hard gate inert when `use_bitnet:false` (F-004).
- TradeNet fusion neural slot built but unwired (F-005).

---

*End of architecture memory extraction. Source of truth for behavior remains code + active config; this document is a map.*
