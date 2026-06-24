# codebase-state-map.md

> **Purpose (LLM context economy):** This is the top-level map a future LLM loads
> *first* to orient. It states what each layer does **today** (not aspirations),
> where the hidden coupling is, and where the future microservice seams lie — so the
> LLM can then load only the one service doc it needs from
> [`services/`](services) without re-reading the whole tree.
>
> Companion docs: [`event-taxonomy.md`](event-taxonomy.md) ·
> [`service-boundary-map.md`](service-boundary-map.md) ·
> [`replay-governance.md`](replay-governance.md) ·
> [`llm-governance-layer.md`](llm-governance-layer.md) ·
> [`roadmap.md`](roadmap.md) (two-track milestone map — governance vs trading; what comes next).
> Citations are `file:line` against the tree at authoring time (config version
> `v2_multi_2026_04`). Spot-check before acting — line numbers drift.

---

## 0. One-paragraph system

M15 OHLCV candles stream one bar at a time into a replay/backtest loop. Each bar is
scored by four engines (CRT, Gaussian, Zone-Gate, RR), fused under a weighted gate,
turned into a decision, planned into entry/SL/TP, and approved by a risk gate.
Governance sits on top (no config reaches production without an `APPROVE`
ValidationReport + SHA-256 hash + append-only audit). An advisory LLM layer and a
file-backed agent/control-plane complete it. **No DB, no broker, no cloud** — all
state is files (JSON configs + JSONL event logs).

---

## 1. Package tree (role per module)

> **Role of this table:** the human "what each package is *for*" map — all 32 `src/` packages, one
> role line each. For the **authoritative, complete tree + import graph** (mechanically generated,
> never drifts) see [`code-map.generated.md`](code-map.generated.md) + `graph.dot`. This table is kept
> in sync with the package set by `tests/test_codebase_structure_doc.py` (a new `src/` package fails
> that test until it gets a row here).

| Package | Role | Key modules (one-line) |
|---|---|---|
| `src/core/` | Decision spine + risk | `engine_runner.py` (orchestrator), `fusion_engine.py` (weighted fusion), `decision_engine.py` (threshold/accept), `ultron_risk_gate.py` (capital gate, kill-switch), `model_registry.py` (atomic model load), `collector.py` (structured decision log), `types.py` (`EngineRunnerOutput`, `GateResult`) |
| `src/engines/` | Scoring engines | `crt_engine.py`, `heuristic_gaussian_engine.py`, `ml_gaussian_engine.py`, `zone_gate_engine.py`, `rr_engine.py`, `trap_validator_engine.py` (hard adapter gate), `live_engine.py` (zone-gate singleton harness) |
| `src/config_layer/` | Config + execution planning + CRT math + LLM client | `production_config.py` (`get_prod_section`, `ACTIVE_VERSION`), `execution_planner.py` (`ExecutionPlannerV1_2`), `crt_engine_v2.py` (`CRTState`, CRT computation), `config_validator.py` (`ConfigValidator`), `llm_inference_client.py` (LLaMA/Groq client), `llm_scorer.py` (circuit-breaker scorer) |
| `src/runtime/` | Replay + live orchestration | `backtest_v2.py` (`BacktestRunner`, the candle loop), `live_engine_hook.py` (`LiveEngineHook`, live orchestration + singletons), `baseline_capture.py`, `unified_replay_harness.py` |
| `src/governance/` | Promotion + portfolio validation | `promotion_manager.py` (only path to prod), `orchestrator.py`, `portfolio_validation.py`, `shadow_promotion_gate.py`, `multi_strategy_validator.py` |
| `src/features/` | Feature engineering + drift | `feature_pipeline.py`, `feature_schema.py` (`CANONICAL_FEATURES`, `FEATURE_ORDER_HASH`), `feature_monitor.py` (`FeatureMonitor` drift), `dataset_validator.py` |
| `src/events/` | **Canonical event fabric** | `event_fabric.py` (`make_event_envelope`, `EventType`, generation counter, schema-hash) |
| `src/multi_llm/` | Multi-LLM coordination (off-spine) | `turn_ledger.py` (verbatim no-loss turn ledger), `discussion.py` (view-only rewind), `context_pack.py` (bounded per-story packs), `tokens.py`; see `multi_llm/` + CLAUDE.md §13 |
| `src/interpreters/` | Interpreter Contract Layer (Level-4 event producers) | `contract.py` (pure/deterministic/no-lookahead interpreter contract), `adapter.py` (bridge to `forward_walk` + QualificationGate), `reference.py`, `point_and_figure.py` (P&F, F-028 — measured REJECT) |
| `src/cognitive/` | Cognitive bus / meta-fusion | `cognitive_bus.py` (`CognitiveBus`, emits `COGNITIVE_TELEMETRY`) |
| `src/replay/` | Replay memory + drift audit | `replay_drift_governor.py` (`ReplayDriftGovernor`, emits `DRIFT_AUDIT`) |
| `src/utils/` | Telemetry + logging | `engine_telemetry.py` (`ENGINE_TELEMETRY`/`DECISION_LINEAGE`), `integrity_events.py` (lightweight integrity spine), `trade_logger.py` (`fusion_trades.jsonl`), `sweep_trace_logger.py` |
| `src/strategies/` | S01–S10 entry families | `strategy_orchestrator.py` (consensus), `s01..s10_*.py`, `base_strategy.py` |
| `src/agent/` | Advisory LLM agent | `executor.py` (path-guard + confirm-gate), `audit.py`, modes (`copilot`/`governance`/`pipeline`/`findings`) |
| `src/control_plane/` | localhost HTTP control | `server.py`, `jobs.py`, `registry.py` (no auth/TLS, localhost-only) |
| `src/bitnet/` | BitNet GGUF inference | `bitnet_inference.py` (zone scoring + validation + stability check); GGUF model load |
| `src/regime/` | Market-regime classifier | `regime_classifier.py` (deterministic TRENDING/RANGING/HIGH_VOLATILITY + config router) |
| `src/portfolio/` | Capital allocation + exposure | `allocator.py`, exposure tracker, `correlation_engine.py`, risk-sizing policy |
| `src/expansion/` | Bounded parameter explorer | `expansion_engine.py` (deterministic stepwise mutation, LLM-suggested direction, hard `PARAM_BOUNDS` guardrails) |
| `src/search/` | Fusion-weight / threshold search | `regime_weight_searcher.py` (regime-aware fusion-weight + BitNet-threshold searcher, LLM-guided) |
| `src/scanner/` | Opportunity scanner | `scanner.py` (multi-symbol signal ranking + universe management) |
| `src/training/` | Model training orchestrators | `train_pipeline.py`, `trainer.py` (TradeNet + Gaussian-NB), Phase-5 calibration gate |
| `src/analytics/` | Trade analytics + SL/TP study | `sl_tp_comparator.py` (clustering + SL/TP method comparison for backtest optimization), `metrics_oracle.py` (independent metric recompute oracle) |
| `src/research/` | Edge Discovery research platform | `runner.py` (`HypothesisRunner`, deterministic `EdgeReport`), `registry.py` (hypotheses), `process_characterization.py`; isolated from the live spine |
| `src/llm_research/` | Offline LLM research pipeline | pattern extraction → policy builder → forward test → evaluator |
| `src/feedback/` | Offline LLM trade feedback | `ai_feedback.py` (LLM param suggestions from trade journals) |
| `src/data_ingestion/` | Historical OHLCV fetch | `historical_fetcher.py` (multi-pair OHLCV → file) |
| `src/inout/` | Live-data candle adapters | `alphavantage_candle_fetcher.py`, Hummingbot fetcher (execution pipeline archived 2026-05-02 → `archive/inout_legacy/`) |
| `src/execution/` | Tick execution loop | `loop.py` (continuous tick-based loop + alert manager + override handler) |
| `src/live/` | Broker / alert bridges | `mt5_bridge.py` (order execution), `telegram_bridge.py` (alerts) |
| `src/journal/` | Trade journal persistence | `trade_logger.py` (journal schema + persistent JSONL logging) |
| `src/monitoring/` | Health checker | `health_checker.py` (lightweight stdlib-HTTP health endpoint) |
| `src/uat/` | Acceptance-test runner | `uat_runner.py` (signal accuracy, trade sim, alerts, scorecard, Monte-Carlo, kill-switch, edge cases) |
| `src/ui/` | Dashboard API | minimal Flask-lite dashboard API (near-empty package; React UI lives in `ui_kits/`) |
| `src/logs/` | Runtime-log placeholder | no modules — runtime JSONL output lands in the top-level `logs/` directory |

---

## 2. The decision spine (the trace to know)

`EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate`
(per dependency graph). All five take config by **injection** and return **structured
dicts** — they are already microservice-shaped.

| Stage | Class (file:line) | Main method (file:line) | Consumes → Produces |
|---|---|---|---|
| Orchestrate | `EngineRunner` (`core/engine_runner.py:285`) | `run(input_data, context, actual_pnl=None)` (`:546`) | features + context → decision + 4 engine scores + fusion + regime |
| Fuse | `FusionEngine` (`core/fusion_engine.py:253`) | `compute(engine_results, trade, weights, regime)` (`:290`); `evaluate(...)` (`:551`) | engine scores → `final_score`, `normalized_score`, RR, `weak_component`, `zone_gate_dead` |
| Decide | `DecisionEngine` (`core/decision_engine.py:85`) | `evaluate(score, p_win, zone_gate, fusion, config)` (`:104`) | fused score → `DecisionResult` (decision/reason/confidence/threshold_used/reject_stage) |
| Plan | `ExecutionPlannerV1_2` (`config_layer/execution_planner.py:129`) | `plan(engine_result, features, context)` (`:156`) | accepted signal → intent, entry, TTL, execution_id (SL/TP injected after via `compute_crt_levels`) |
| Approve | `UltronRiskGate` (`core/ultron_risk_gate.py:69`) | `evaluate(trade, portfolio_state)` (`:156`) | plan + portfolio → approval + `final_position_size` + risk_reason |

`GateResult` decision contract: `"APPROVE" | "REJECT"` (`core/types.py:95`, checked at
`:118`).

---

## 3. Hidden-coupling inventory (decomposition blockers)

> These are the things that make "extract a service" hard. Tiered by blast radius.

### Tier 1 — hard blockers
1. **Module-level config loads at import** — importing the module triggers a prod-config
   read before any instance exists:
   - ✅ RESOLVED `config_layer/llm_inference_client.py` — eager `_LG_CFG = _get_section("llama_gate")`
     replaced by lazy `_lg_consts()` + PEP 562 `__getattr__` (Trd-M5 §5.2b); siblings
     `llm_scorer.py` / `llm_narrative.py` no longer snapshot the constants at import.
   - ✅ RESOLVED `config_layer/config_validator.py` — `_VALIDATOR_CFG` replaced by lazy `_gates()` (Trd-M3 §3.2).
   - all `strategies/S01..S10` + `strategy_orchestrator.py` import `get_prod_section` at module level
2. **Engine ↔ `core.model_registry` bidirectional coupling** —
   `engines/ml_gaussian_engine.py:53` and `engines/tradenet_meta_engine.py:228` import
   model registry; engines can't ship as a standalone lib without it.
3. **Upward governance/analytics → `runtime.backtest_v2`** —
   `governance/portfolio_validation.py:28`, `config_layer/config_validator.py:146`,
   `analytics/sl_tp_comparator.py:589` all import `BacktestRunner`. Wrong dependency
   direction for a service split (governance should not depend on the runtime impl).
4. **`live_engine_hook` module-level singletons** —
   `runtime/live_engine_hook.py:85` (`_ENGINE_CONFIG_CACHE`) and `:90–96`
   (`_orchestrator`, `_kill_switch`, `_telegram`, `_mt5`, `_regime_classifier`,
   `_config_router`). Cannot run two isolated live contexts in one process.

### Tier 2 — medium
5. **Hardcoded relative paths in business logic** — `core/ultron_risk_gate.py:44`
   (`logs/kill_switch_state.json`), `engines/heuristic_gaussian_engine.py:83`
   (registry path). Blocks multi-instance / multi-dir runs.
6. **Mutable module-level circuit state** — `config_layer/llm_scorer.py`
   (`FAIL_COUNT`, `CIRCUIT_OPEN` globals).
7. **Strategy consensus injected into `EngineRunner` context** rather than passed as a
   typed input (`strategy_orchestrator` → engine_runner context dict).

### Tier 3 — lower
8. `FeaturePipeline` instantiated inside `BacktestRunner.__init__` (feature build
   coupled to replay).
9. Per-decision file writes scattered across `signal_audit.py`, `live_engine.py`.

---

## 4. Per-layer scorecard (the five lenses)

| Layer | Current behavior | Hidden coupling | Replay risk | Missing telemetry | Event boundary | Microservice seam |
|---|---|---|---|---|---|---|
| **Ingestion/Features** | CSV → lagged feature vectors, timestamp-keyed | `FeaturePipeline` built in `BacktestRunner` | `center=True` rolling in `feature_pipeline.py:341` is **live-unsafe** | No `FEATURE_SNAPSHOT` emitted (declared, unused) | feature-vector-ready | Feature service w/ frozen schema |
| **Scoring engines** | 4 engines score independently | engine→model_registry, engine→llm_scorer | none (pure given inputs) | `ENGINE_TELEMETRY` exists ✓ | per-engine score event | Scoring service (stateless) |
| **Decision spine** | inject-config, dict-returns | low — already clean | deterministic | `DECISION_SNAPSHOT`/`DECISION_LINEAGE` exist ✓ | decision event | **Already seam-ready** |
| **Execution/Risk** | planner + risk gate + kill-switch | kill-switch file path hardcoded | deterministic | partial — kill-switch transitions under-logged | approve/reject event | Execution service |
| **Governance** | promote only on APPROVE | imports runtime upward | n/a (offline) | promotion log ✓ | promotion event | Governance service (needs dep inversion) |
| **Replay/Telemetry** | event fabric + drift governor | none | n/a | trade writers not enveloped (see Trd-M1) | **the bus itself** | Telemetry/Event-bus service |
| **LLM advisory** | tie-breaker + agent | llm_scorer globals | **off hot path ✓** | LLM calls not all enveloped | advisory event | LLM advisory service |

---

## 5. Orchestration & entry points

- **Replay loop:** `runtime/backtest_v2.py` — `BacktestRunner` (class ~`:1255`,
  `run()` ~`:1393`, candle loop ~`:1524`). One bar per iteration; timestamp-keyed feature lookup
  (`feature_ts_to_idx` populated `:1307`).
- **Live:** `runtime/live_engine_hook.py` — `LiveEngineHook.process()`; approves only
  when `ultron_result["decision"] == "APPROVE"` and kill-switch clear (`:836`, `:861`).
- **Config load:** `config_layer/production_config.py` — `ACTIVE_VERSION` pointer →
  `PROD_VERSION` → `get_prod_section(name)`. Active version today:
  `configs/production/v2_multi_2026_04.json` on the `patch` branch (F-016; branch-scoped —
  `v4_multi_2026_06` is post-TP3-line only, not loadable here).
- **CLI / control plane:** thin `scripts/` wrappers; `src/control_plane/server.py`
  (localhost-only); agent CLI in `src/agent/`.

---

## 6. Known constraints (load-bearing)

- Python ≥ 3.10. Single active prod config at a time. Four engines mandatory
  (`EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}`). No lookahead in backtests.
  LLM is a tie-breaker, never a hot-path dependency. `CRTState` transitions follow a
  fixed legal graph (see [`event-taxonomy.md`](event-taxonomy.md)). Schema hash is
  load-bearing — changing `CANONICAL_FEATURES`/`FEATURE_ORDER_HASH` invalidates the
  baseline.
