# Topics — Topic Visibility Layer

> **What this is.** One file per *concept* (a "topic"), narrating in human language what code
> it covers, how it's reached, what tests it, and what's still open — and kept in sync with the
> code on **every working response** (`CLAUDE.md §6.4 Topic Sync Mandate`). This is the
> concept↔code↔tests↔validations index; the rest of `docs/` owns flow, schemas, and history.
>
> Created: 2026-06-01 · Updated: 2026-08-08
>
> **See also:** [`../knowledge-map.md`](../knowledge-map.md) — how the topics layer connects to the other record systems (SESSION LOG, plans, analysis, findings, structure maps).

## How to use this
- **Find a concept** in the table → open its doc for the grounded, citable picture.
- **Add a topic:** copy [`_template.md`](_template.md) → `docs/topics/<topic>.md`, fill it, add a row here.
- **Keep it true:** when you change code that a topic covers, update that topic's doc the same
  turn (only that file — token-aware). See `CLAUDE.md §6.1` and the `Sync` trigger in
  [`trigger-vocabulary.md`](../architecture/trigger-vocabulary.md).

## Relationship to idea-governance Bricks
This layer (concepts) and [`idea-governance-framework.md`](../architecture/idea-governance-framework.md)
(Bricks) are two implementations of the same idea — governed, auditable legibility — at different
grain. **Decision (2026-06-01): keep them parallel for now**; do not merge lifecycles. Revisit later
by *comparing which set drifts* against code — the drift signal decides whether a merge is worth it.

## Sources mined to seed topics (not reinvented)
- [`docs/human-language-analysis/`](../human-language-analysis/) — 20 package-grouped runtime narrations (the narration style + the candidate topic groupings).
- [`docs/analysis/codebase-analysis.md`](../analysis/codebase-analysis.md) — per-module structured analysis (the "code covered" cross-reference).
- [`src/control_plane/registry.py`](../../src/control_plane/registry.py) → [`cli-matrix.md`](../reference/cli-matrix.md) — the entry-point catalog.
- [`assistant_project.md`](../../assistant_project.md) — live session threads / open questions (the Discussion seeds).

## Topic index

| Topic | Domain | Source files (anchor) | Entry points | Tests | Status | Doc |
|---|---|---|---|---|---|---|
| Context Report | control-plane / LLM-advisory | `src/control_plane/context_report.py`, `code_context_extractor.py` | 🧠 button → `POST /runs/{id}/context/report` | — | living | [context-report.md](context-report.md) |
| Capital Pressure Ratio (CPR) | research / ontology (latent pre-OHLC) | `market_ontology.yaml` UNK-002…UNK-005 | ontology only (no runtime) | `test_semantic_registry` | living | [capital-pressure-ratio.md](capital-pressure-ratio.md) |
| CRT spine (candle→order) | core decision flow | `src/config_layer/crt_engine_v2.py`, `core/engine_runner.py` | `backtest_v2` CLI; control-plane backtest | `tests/` (crt / engine_runner) | living | [crt-spine.md](crt-spine.md) |
| Fusion + decision | core | `core/fusion_engine.py:253`, `core/decision_engine.py:85` | via engine_runner | `test_engine_runner_rr_fusion`, `test_fusion_and_validator_regression` | living | [fusion-decision.md](fusion-decision.md) |
| Execution planning | config_layer | `config_layer/execution_planner.py:129` (`ExecutionPlannerV1_2`) | via decision surface | `test_execution_planner`, `test_execution_contract_v1` | living | [execution-planning.md](execution-planning.md) |
| Ultron risk gate | risk (core) | `core/ultron_risk_gate.py:69` + `_wrapper.py:58` | terminal approve/reject | `test_ultron_risk_gate`, `test_ultron_gate`, `test_ultron_wrapper` | living | [ultron-risk-gate.md](ultron-risk-gate.md) |
| Config validation | config_layer / governance | `config_layer/config_validator.py:297` | `config_validator.py validate-prod` | `test_fusion_and_validator_regression` | living | [config-validation.md](config-validation.md) |
| Goal Layer (economic objective) | config_layer / governance | `config_layer/goal_schema.py`, `goal_validator.py` | every backtest (advisory `goal_report`); promotion when `goal.enforce` | `test_goal_schema`, `test_goal_validator`, `test_goal_metrics` | living | [goal-layer.md](goal-layer.md) |
| Metrics Layer V2 (RR/survival/efficiency) | runtime / analytics | `runtime/backtest_v2.py` (`TradePathStats`, `_metrics_v2_block`), `analytics/metrics_oracle.py` (Oracle V2+V3) | every backtest (`distribution.metrics_v2`); multi-instrument `symbol_attribution` | `test_metrics_v2` (+ determinism/forward_walk gate) | living | [metrics-layer.md](metrics-layer.md) |
| Interpreter Contract (Level 4) | interpreters / research | `interpreters/contract.py`, `adapter.py`, `reference.py` | `InterpreterHypothesis` → forward_walk + QualificationGate (reused oracle) | `tests/interpreters/test_interpreter_contract` | living | [interpreter-contract.md](interpreter-contract.md) |
| Promotion / governance | governance | `governance/promotion_manager.py:97` | `promotion_manager.py promote` | `test_shadow_promotion_gate`, `test_sprint7_governance` | living | [promotion-governance.md](promotion-governance.md) |
| Expansion engine | expansion | `src/expansion/expansion_engine.py:24`, `policy_schema.py:56` | governance expansion bridge | `test_expansion_engine`, `test_expansion_governance_bridge` | living | [expansion-engine.md](expansion-engine.md) |
| AI automation agent | agent | `src/agent/{intent_router,plan_compiler,tool_registry,executor}.py` | `python -m src.agent.cli` (REPL) | `test_agent_intent_router`, `test_agent_executor_confirm` | living | [ai-automation-agent.md](ai-automation-agent.md) |
| Training / calibration | training | `src/training/{train_pipeline,trainer,phase5_calibration}.py` | training CLI / `tuner.run_multi` | `test_train_pipeline`, `test_phase5_calibration` | living | [training-calibration.md](training-calibration.md) |
| Regime classifier | regime | `src/regime/regime_classifier.py:25`, `config_router.py:43` | live hook (pre-engine, per candle) | `test_regime_classifier` | living | [regime-classifier.md](regime-classifier.md) |
| Portfolio allocation | portfolio | `src/portfolio/{allocator,exposure_tracker,correlation_engine,capital_policy}.py` | ExecutionLoop (multi-signal) | `test_portfolio_allocator` | living | [portfolio-allocation.md](portfolio-allocation.md) |
| Analytics — SL/TP comparator | analytics | `src/analytics/sl_tp_comparator.py:300` | `sl_tp_comparator.py` CLI (offline) | `test_sl_tp_comparator` | living | [analytics-sltp.md](analytics-sltp.md) |
| Regime weight search | search | `src/search/regime_weight_searcher.py:36` | offline tuner (LLM-guided) | _none yet_ | living | [weight-search.md](weight-search.md) |
| Execution loop (multi-signal) | execution | `src/execution/loop.py:31`, `alert_manager.py:15`, `override_handler.py:13` | _scaffolding — no caller yet_ | `test_execution_loop` | living | [execution-loop.md](execution-loop.md) |
| Feature schema, pipeline & drift | features | `src/features/feature_schema.py:46`, `feature_pipeline.py:135`, `feature_monitor.py:63` | built in `backtest_v2` / live hook | `test_feature_pipeline`, `test_schema_contracts` | living | [feature-schema.md](feature-schema.md) |
| Scoring engines (Gaussian/Zone-Gate/RR) | engines | `src/engines/{heuristic_gaussian,ml_gaussian,zone_gate,rr}_engine.py` | via `engine_runner` | `test_gaussian_impl_switch`, `test_zone_gate`, `test_engine_runner_rr_fusion` | living | [scoring-engines.md](scoring-engines.md) |
| Model intent & feature ownership | engines / features | `src/engines/*`, `bitnet/*`, `core/engine_runner.py:144`, `features/feature_schema.py:46` | live spine + research measurement | `test_topic_docs`, `test_current_findings` (F-041) | living | [model-intent-and-feature-ownership.md](model-intent-and-feature-ownership.md) |
| BitNet gate | bitnet / crt | `src/bitnet/bitnet_inference.py:317`, `crt_engine_v2.py:1805` | inside CRT (pre-fusion gate) | `test_bitnet_inference`, `test_bitnet_parity` | living | [bitnet-gate.md](bitnet-gate.md) |
| Event fabric | events | `src/events/event_fabric.py:119` (`make_event_envelope`) | library call (all JSONL writes) | `tests/events/test_event_fabric` | living | [event-fabric.md](event-fabric.md) |
| Live execution (order/data path) | live / inout / execution | `src/runtime/live_engine_hook.py:582`, `src/live/`, `src/inout/`, `src/execution/loop.py` | `HookedLiveEngine.process` (live tick) | `test_live_integration`, `test_execution_loop` | living | [live-execution.md](live-execution.md) |
| Replay memory / Probability Surface | replay / cognitive | `src/replay/replay_memory_engine.py:394`, `src/cognitive/cognitive_bus.py:217` | `discover_zones.py --normalize` (registry) | `test_assign_cluster`, `test_replay_memory_engine` | living | [replay-memory.md](replay-memory.md) |
| Replay / determinism | replay | `src/replay/` | `trade_replay_validator.py` | — | stub | _todo_ |
| Research Measurement Contract | governance / research | `docs/governance/MEASUREMENT_CONTRACT.md`, `research_family_registry.json`, `configs/research/measurement_contracts/*.v1.json` | none yet — per-family runner specified (§6), not built; `gate_measurement_m_gate_01.py` is the one hand-written measurement | `test_measurement_contract`, `test_research_family_registry`, `test_current_findings` (Family/Contract), `test_closure_authority_index` | living | [research-measurement-contract.md](research-measurement-contract.md) |

### Dormant / sidecar subsystems (no deep-dive by design)

Real code, but **off the live decision path** — sidecar telemetry, inert, offline, or orphaned per the
findings. Listed for honesty/visibility; a full topic is deferred until one becomes live. Structure +
role for each is in [`../architecture/codebase-state-map.md`](../architecture/codebase-state-map.md) §1.

| Subsystem | Domain | Source | Why dormant (ref) | Status |
|---|---|---|---|---|
| Cognitive bus | cognitive | `src/cognitive/cognitive_bus.py` | sidecar telemetry, zero spine consumption (F-012) | DORMANT |
| Strategies S01–S10 | strategies | `src/strategies/` | consensus wired but inert (doesn't alter decisions) | DORMANT |
| Scanner | scanner | `src/scanner/scanner.py` | orphaned from live path (not imported by spine) | DORMANT |
| Feedback | feedback | `src/feedback/ai_feedback.py` | offline; feedback loop broken | DORMANT |
| LLM research | llm_research | `src/llm_research/` | offline experimentation only | DORMANT |
| Monitoring | monitoring | `src/monitoring/health_checker.py` | auxiliary health endpoint | DORMANT |
| Journal | journal | `src/journal/trade_logger.py` | auxiliary telemetry (broken feedback loop) | DORMANT |
| Data ingestion | data_ingestion | `src/data_ingestion/historical_fetcher.py` | offline data seeding | DORMANT |
| UAT | uat | `src/uat/uat_runner.py` | offline validation tooling | DORMANT |

> **Status legend:** `living` = maintained per §6.1 · `stub` = row only, doc not yet written ·
> `DORMANT` = off the live path (sidecar/inert/offline/orphaned); deep-dive deferred by design.
> Stubs are intentional — promote one to a full doc the first time a session touches that
> concept's code, following the `Sync` trigger.
