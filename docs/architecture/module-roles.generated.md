# module-roles.generated.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_code_map.py`. One role line per `src/` module, taken from the module docstring's first line. Package-level roles + key modules live in [`codebase-state-map.md`](codebase-state-map.md) §1; the import graph is [`code-map.generated.md`](code-map.generated.md).

_`(no module docstring)` flags a module that should get a one-line docstring — that is the actionable code gap, not a docs gap._

**Coverage: 576/625 modules carry a docstring role (92%).** 49 flagged `(no module docstring)`.

### `src/agent/`

| Module | Role (docstring line 1) |
| --- | --- |
| `agent` | GrokAgenticAI — multi-specialist kitchen agent (NL → intent → bounded tools → confirm-gated execution). |
| `agent.agent_core` | agent_core.py |
| `agent.audit` | audit.py |
| `agent.cli` | cli.py — GrokAgenticAI interactive REPL |
| `agent.executor` | executor.py |
| `agent.findings_synthesizer` | findings_synthesizer.py — Post-run findings via Groq Llama-3.1-70B |
| `agent.goal` | goal.py — AgentGoal contracts for GrokAgenticAI |
| `agent.goal_loop` | goal_loop.py — GrokAgenticAI goal execution |
| `agent.grok_agentic` | grok_agentic.py — GrokAgenticAI multi-agent registry |
| `agent.groq_client` | groq_client.py — Agent-tier Groq LLM client with request logging + redaction |
| `agent.intent_router` | intent_router.py |
| `agent.log_query` | log_query.py |
| `agent.modes` | Agent tool-registration modes (pipeline, copilot, governance, findings, log-query, ops). |
| `agent.modes.copilot_mode` | copilot_mode.py — Live Signal Co-pilot tool registrations |
| `agent.modes.findings_mode` | findings_mode.py — Post-run findings tool registrations |
| `agent.modes.governance_mode` | governance_mode.py — Governance Meta-reasoner tool registrations |
| `agent.modes.log_query_mode` | log_query_mode.py — Read-only log query tool registrations |
| `agent.modes.ops_mode` | ops_mode.py — GrokAgenticAI OpsDoctor tools (read-only + incident pack) |
| `agent.modes.pipeline_mode` | pipeline_mode.py — Pipeline Orchestrator tool registrations |
| `agent.modes.truth_mode` | truth_mode.py — GrokAgenticAI TruthJanitor tools |
| `agent.plan_compiler` | plan_compiler.py |
| `agent.recipes` | Bounded recipes for GrokAgenticAI specialists (no free tool choice). |
| `agent.recipes.campaign_pipeline` | CampaignRunner seed + Mode-B branch table (metric → next tools). |
| `agent.recipes.ops_diagnose` | OpsDoctor seed recipe — fixed read-only chain + incident pack. |
| `agent.recipes.truth_janitor` | TruthJanitor seed recipe — hygiene checks then rollup pack. |
| `agent.state` | state.py |
| `agent.tool_planner` | tool_planner.py — ArgFiller |
| `agent.tool_registry` | tool_registry.py |

### `src/analytics/`

| Module | Role (docstring line 1) |
| --- | --- |
| `analytics` | Offline trade analytics: SL/TP comparison, loss clustering, performance metrics. |
| `analytics.clustering` | TradeClustering: groups losing trades by condition to surface patterns. |
| `analytics.metrics_oracle` | Independent backtest-metric recompute oracle — Backtest Trust Layer (2026-06-10). |
| `analytics.performance` | PerformanceAnalyzer: win rate, expectancy, drawdown, and breakdown metrics. |
| `analytics.sl_tp_comparator` | sl_tp_comparator.py — Dual SL/TP method comparator for backtest productivity analysis. |

### `src/bitnet/`

| Module | Role (docstring line 1) |
| --- | --- |
| `bitnet` | bitnet/ |
| `bitnet._smoke_test` | Quick smoke test for BitNet module — run with: py bitnet/_smoke_test.py |
| `bitnet.adapters` | adapters.py |
| `bitnet.backbones` | backbones.py |
| `bitnet.bitnet_inference` | bitnet_inference.py |
| `bitnet.bitnet_registry` | bitnet_registry.py |
| `bitnet.bitnet_runner` | BitNet Runner |
| `bitnet.composition` | composition.py |
| `bitnet.contract_c_trainer` | contract_c_trainer.py |
| `bitnet.defaults` | defaults.py |
| `bitnet.encoders` | encoders.py |
| `bitnet.forward_tester` | bitnet/forward_tester.py |
| `bitnet.heads` | heads.py |
| `bitnet.label_contracts` | label_contracts.py |
| `bitnet.layers` | layers.py |
| `bitnet.model_bundle` | model_bundle.py |
| `bitnet.model_contract` | model_contract.py |
| `bitnet.population_label_audit` | population_label_audit.py |
| `bitnet.r25_kill_test` | r25_kill_test.py |
| `bitnet.runtime_types` | runtime_types.py |
| `bitnet.stability_checker` | bitnet/stability_checker.py |
| `bitnet.zone_cosine_searcher` | Zone Cosine Searcher |
| `bitnet.zone_validator` | bitnet/zone_validator.py |

### `src/charts/`

| Module | Role (docstring line 1) |
| --- | --- |
| `charts` | charts — INFRA-CPC-V1 Workstream A0: own OHLC charts from the corpus we consume. |
| `charts.chart_api` | chart_api.py — read-only payload builder for the dashboard's Trade Chart tab. |
| `charts.chart_series` | chart_series.py — INFRA-CPC-V1 A0 series builder (pure; no drawing). |
| `charts.crt_overlay` | crt_overlay.py — INFRA-CPC-V1 A0 Layer V1: resolve a per-bar CRTState track. |
| `charts.render` | render.py — INFRA-CPC-V1 A0 drawing layer (Layer V0 bars + Layer V1 CRTState colour). |
| `charts.resolver_overlay` | resolver_overlay.py — precompute + serve the CRTStateResolver per-bar track for a chart. |

### `src/cognitive/`

| Module | Role (docstring line 1) |
| --- | --- |
| `cognitive` | _(no module docstring)_ |
| `cognitive.cognitive_bus` | cognitive_bus.py |

### `src/config_layer/`

| Module | Role (docstring line 1) |
| --- | --- |
| `config_layer` | Config loaders, validators, and decision rules (CRT math, execution planner, LLM client). |
| `config_layer._crt_state_generated` | _crt_state_generated.py -- GENERATED FILE, DO NOT EDIT BY HAND. |
| `config_layer.config_builder` | config_builder.py |
| `config_layer.config_validator` | config_validator.py |
| `config_layer.crt_config_completeness` | crt_config_completeness.py |
| `config_layer.crt_config_provenance` | CRTConfig construction provenance — P1 OBSERVE (F-057 class). |
| `config_layer.crt_engine_v2` | ╔══════════════════════════════════════════════════════════════════╗ |
| `config_layer.crt_gaussian_scorer` | Central CRT Gaussian scorer. |
| `config_layer.crt_identity_schema` | crt_identity_schema.py |
| `config_layer.crt_sweep_taxonomy` | crt_sweep_taxonomy.py |
| `config_layer.execution_planner` | execution_planner.py |
| `config_layer.goal_schema` | goal_schema.py |
| `config_layer.goal_validator` | goal_validator.py |
| `config_layer.htf_state` | htf_state.py — CH-htf-state-objective (Stage 3): HTFState + Objective. |
| `config_layer.insight_reporter` | insight_reporter.py |
| `config_layer.llm_inference_client` | llm_inference_client.py |
| `config_layer.llm_narrative` | llm_narrative.py |
| `config_layer.llm_scorer` | llm_scorer.py |
| `config_layer.m15_structural_range` | M15 structural liquidity range — the CRT sweep envelope. |
| `config_layer.market_router` | Market-type CRT config profiles (crypto/forex) and the profile router. |
| `config_layer.model_paths` | model_paths.py — CODE layout authority for model artifacts (Phase 0). |
| `config_layer.model_resolver` | model_resolver.py — resolve family → registry active → artifact (+ WHO identity parity). |
| `config_layer.parent_crt` | parent_crt.py — CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the |
| `config_layer.production_bundle` | production_bundle.py — the executable production state, as one immutable object. |
| `config_layer.production_config` | production_config.py |
| `config_layer.rr` | Risk-reward fusion layer: RR dataset builder and RR model fusion. |
| `config_layer.rr.rr_dataset_builder` | rr_dataset_builder.py |
| `config_layer.rr.rr_fusion` | rr_fusion.py |
| `config_layer.rr.rr_pattern_miner` | rr_pattern_miner.py |
| `config_layer.stack_version` | stack_version.py — one composite identity over WHAT / HOW / WHO / EXECUTION. |
| `config_layer.state_contract` | state_contract.py |
| `config_layer.state_contract_loader` | state_contract_loader.py |
| `config_layer.state_identity` | state_identity.py |
| `config_layer.state_topology` | state_topology.py |

### `src/control_plane/`

| Module | Role (docstring line 1) |
| --- | --- |
| `control_plane` | Stdlib-HTTP control plane: localhost dashboard, command registry, job runner. |
| `control_plane.code_context_extractor` | code_context_extractor.py — AST-based code extraction for Context Reports. |
| `control_plane.context_report` | context_report.py — ContextReportAPI: Claude-powered ARCHITECTURE ANALYST for runs. |
| `control_plane.cp_types` | _(no module docstring)_ |
| `control_plane.dashboard_api` | dashboard_api.py |
| `control_plane.dot_graph_context` | dot_graph_context.py — flow resolution + architectural graph context for Context Reports. |
| `control_plane.jobs` | JobManager: queues and runs control-plane commands as subprocesses. |
| `control_plane.monitors` | Control-plane dashboard monitor specs (jsonl-tail/json/regex/file-stat sources). |
| `control_plane.registry` | CommandSpec registry: the catalog of control-plane commands. |
| `control_plane.report_api` | report_api.py — RunReportAPI: Excel generation + Groq LLM analysis for run history reports. |
| `control_plane.retrieval_api` | retrieval_api.py — KnowledgeAPI: truth-tier RAG surface for the control plane. |
| `control_plane.server` | Stdlib-HTTP control-plane server (localhost:8787 dashboard and API). |

### `src/core/`

| Module | Role (docstring line 1) |
| --- | --- |
| `core` | Decision spine: EngineRunner, FusionEngine, DecisionEngine, UltronRiskGate, Collector. |
| `core.acceptance_controller` | core/acceptance_controller.py — Adaptive Acceptance Control System |
| `core.backtest_port` | backtest_port.py — Trd-M4 dependency-inversion port. |
| `core.collector` | collector.py |
| `core.convergence_controller` | core/convergence_controller.py — Convergence Layer for FusionEngine |
| `core.decision_engine` | Central execution authority. |
| `core.dynamic_threshold` | dynamic_threshold.py |
| `core.engine_runner` | EngineRunner — orchestrates the full pipeline. |
| `core.feature_store` | core/feature_store.py |
| `core.fusion_engine` | fusion_engine.py |
| `core.gate_intelligence` | gate_intelligence.py — Pure signal gate for ExecutionPlanner. |
| `core.governance_mode` | governance_mode.py — Trd-M5 LLM-layer hardening: the GOVERNANCE_MODE switch. |
| `core.hierarchical_meta_fusion` | hierarchical_meta_fusion.py |
| `core.model_registry` | model_registry.py |
| `core.regime_governor` | src/core/regime_governor.py |
| `core.signal_audit` | core/signal_audit.py — Per-bar Signal Audit + Leak Detection |
| `core.signal_belief_tracker` | signal_belief_tracker.py |
| `core.types` | core/types.py |
| `core.ultron_live_adapter` | Live portfolio adapter around UltronRiskGate. Not a second risk engine. |
| `core.ultron_risk_gate` | ultron_risk_gate.py |
| `core.ultron_risk_gate_wrapper` | core/ultron_risk_gate_wrapper.py — UltronRiskGateWrapper |

### `src/data_ingestion/`

| Module | Role (docstring line 1) |
| --- | --- |
| `data_ingestion` | _(no module docstring)_ |
| `data_ingestion.clock_detector` | clock_detector.py — ADVISORY evidence for a human clock review. Never a verdict of record. |
| `data_ingestion.clock_registry` | clock_registry.py — declared, human-reviewed clock provenance for OHLCV corpora. |
| `data_ingestion.corpus_gate` | corpus_gate.py |
| `data_ingestion.corpus_store` | corpus_store.py — Parquet READ-CACHE over an admitted OHLCV corpus. |
| `data_ingestion.dataset_integrity` | dataset_integrity.py |
| `data_ingestion.dataset_registry` | R3 Dataset Identity registry + load-time admission. |
| `data_ingestion.historical_fetcher` | historical_fetcher.py |
| `data_ingestion.ohlcv_schema` | ohlcv_schema.py |
| `data_ingestion.session_autoderive` | session_autoderive.py — learn a provider's tradable session from the data itself. |
| `data_ingestion.xauusd_phase1_candidate` | XAUUSD M15 Phase-1 frozen candidate — fail-closed identity verification. |

### `src/engines/`

| Module | Role (docstring line 1) |
| --- | --- |
| `engines` | Scoring engines (CRT, Gaussian, Zone-Gate, RR) plus the trap-validation gate. |
| `engines.crt_engine` | crt_engine.py |
| `engines.gaussian_engine` | gaussian_engine.py — BACKWARD-COMPATIBILITY SHIM |
| `engines.heuristic_gaussian_engine` | heuristic_gaussian_engine.py |
| `engines.live_engine` | live_engine.py |
| `engines.llm_engine` | llm_engine.py |
| `engines.ml_gaussian_engine` | ml_gaussian_engine.py |
| `engines.rr_engine` | RREngine — Candle Polarity Index (formerly misnamed "RR Engine"). |
| `engines.scoring_engine` | _(no module docstring)_ |
| `engines.tradenet_meta_engine` | tradenet_meta_engine.py |
| `engines.trap_validator_engine` | TrapValidatorEngine — data integrity validator and pre-gating layer. |
| `engines.zone_cluster_score` | zone_cluster_score.py — pure zone cluster scoring shared by EngineRunner and |
| `engines.zone_gate_engine` | zone_gate_engine.py – BitNet Zone Gate with strict schema validation but fail‑open on registry errors. |

### `src/events/`

| Module | Role (docstring line 1) |
| --- | --- |
| `events` | _(no module docstring)_ |
| `events.event_fabric` | event_fabric.py |

### `src/execution/`

| Module | Role (docstring line 1) |
| --- | --- |
| `execution` | _(no module docstring)_ |
| `execution.alert_manager` | _(no module docstring)_ |
| `execution.execution_intent_v1_0` | execution_intent_v1_0 — the human-in-loop execution workflow state (Tier 0B). |
| `execution.loop` | _(no module docstring)_ |
| `execution.override_handler` | _(no module docstring)_ |

### `src/expansion/`

| Module | Role (docstring line 1) |
| --- | --- |
| `expansion` | Expansion Engine — controlled trade frequency scaling. |
| `expansion.config_mutator` | _(no module docstring)_ |
| `expansion.evaluator` | _(no module docstring)_ |
| `expansion.expansion_engine` | _(no module docstring)_ |
| `expansion.llm_pattern_extractor` | _(no module docstring)_ |
| `expansion.policy_schema` | _(no module docstring)_ |

### `src/features/`

| Module | Role (docstring line 1) |
| --- | --- |
| `features` | _(no module docstring)_ |
| `features.broker_clock` | broker_clock.py — converts MT5 broker-server timestamps to true UTC. |
| `features.calendar_periods` | calendar_periods.py — W1 (ISO week) and MN1 (calendar month) parent-candle aggregation. |
| `features.candle_math` | Candle geometry primitives — the single, immutable source of truth for candle math. |
| `features.causal_structure` | causal_structure.py — FC1-A delayed-confirmed structure publication helpers. |
| `features.crt_feature_builder` | CRT Feature Builder |
| `features.crt_state_resolver` | CRT State Resolver — Layer 5 of the semantic pipeline (2026-07-24). |
| `features.dataset_builder` | _(no module docstring)_ |
| `features.dataset_validator` | dataset_validator.py |
| `features.derived_math` | Derived-metric primitives — the immutable scalar source of truth for deterministic |
| `features.feature_builder` | FeatureBuilder — constructs the canonical input_data dict from raw tick/row data. |
| `features.feature_identity` | Phase-1 feature identity resolution — fail-closed lookup by feature_id. |
| `features.feature_monitor` | feature_monitor.py |
| `features.feature_pipeline` | feature_pipeline.py |
| `features.feature_schema` | _(no module docstring)_ |
| `features.feature_states` | Feature State layer — Layer 2 of the semantic pipeline (roadmap Phase 2C). |
| `features.fm_resolve` | fm_resolve.py |
| `features.formula_registry` | Formula registry — BACK-COMPAT FACADE over the registry package (src/features/registry/). |
| `features.gaussian_schema_contract` | gaussian_schema_contract.py |
| `features.magnitude_states` | Magnitude state layer — Phase 2A continuous VALUE → discrete STATE (shadow only). |
| `features.market_context` | Market Context layer — Layer 4 of the semantic pipeline (roadmap Phase 3). |
| `features.market_reality_contract` | market_reality_contract.py — read-only loader/validator for |
| `features.market_shape` | Market Shape layer — Layer 5 of the semantic pipeline (roadmap Phase 5). |
| `features.model_evidence` | Model Evidence layer — Layer 7 of the semantic pipeline. |
| `features.parent_candle` | parent_candle.py — CH-htfcrt-parent-candle-smc-v1: real, calendar-true HTF parent candles. |
| `features.registry` | Feature-math registry — the AUTHORITATIVE source of feature-mathematics implementation. |
| `features.registry._loader` | Ontology loader — leaf module (no intra-package deps) so registry submodules can share it |
| `features.registry.composition_registry` | Composition registry — trading-interpretation ratios (numerator/denominator over primitives). |
| `features.registry.derived_registry` | Derived registry — deterministic normalized metrics (ATR/price-relative). Maps declared impl |
| `features.registry.predicate_registry` | predicate_registry — the governed interpreter for `structural_predicates` definitions. |
| `features.registry.primitive_registry` | Primitive registry — the OHLC-identity layer. Maps declared primitive impl names to the |
| `features.resolver_supply` | resolver_supply.py |
| `features.schema_validator` | schema_validator.py |
| `features.session_classifier` | session_classifier.py — THE single owner of "what session is this?". |
| `features.smc` | features.smc — CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the 9 SMC |
| `features.smc._geometry` | features.smc._geometry — shared, pure helpers for the SMC primitive modules. |
| `features.smc.breaker` | features.smc.breaker — Breaker Block detection. |
| `features.smc.choch` | features.smc.choch — Change of Character (CHoCH). |
| `features.smc.fvg` | features.smc.fvg — Fair Value Gap (FVG) / imbalance detection. |
| `features.smc.levels` | features.smc.levels — Previous-Day High/Low (PDH/PDL) and Equal Highs/Lows (EQH/EQL). |
| `features.smc.mitigation` | features.smc.mitigation — Mitigation Block. |
| `features.smc.order_block` | features.smc.order_block — Order Block (OB) detection. |

### `src/feedback/`

| Module | Role (docstring line 1) |
| --- | --- |
| `feedback` | _(no module docstring)_ |
| `feedback.ai_feedback` | _(no module docstring)_ |

### `src/governance/`

| Module | Role (docstring line 1) |
| --- | --- |
| `governance` | _(no module docstring)_ |
| `governance.archive_manifest` | Archive manifest ledger — every file under ``archive/`` is accounted for, nothing is deleted. |
| `governance.bitnet_governance_executor` | _(no module docstring)_ |
| `governance.config_integrity` | config_integrity.py — governance guards for production-config lineage. |
| `governance.expansion_integration` | _(no module docstring)_ |
| `governance.findings_export` | Findings export — GENERATED machine-readable derived view of docs/current-findings.md. |
| `governance.framework_registry` | FrameworkRegistry — queryable, append-only map of the trading-system architecture. |
| `governance.hypothesis_registry` | HypothesisRegistry — queryable, append-only registry of research hypotheses (H-ids). |
| `governance.jsonl_claim_catalog` | JSONL claim catalog — loader + admissibility over the PRIMARY CAN/CANNOT vocabulary. |
| `governance.measurement_result_log` | Measurement result log — the committed record that a sealed MC-* contract actually EXECUTED. |
| `governance.module_attribution` | Module attribution registry core — governance-surface ownership for every ``src/`` module. |
| `governance.module_census` | Module attribution census core — discovery + path-stable stub merge for ``src/**/*.py``. |
| `governance.multi_strategy_validator` | multi_strategy_validator.py |
| `governance.orchestrator` | governance/orchestrator.py |
| `governance.portfolio_validation` | ╔══════════════════════════════════════════════════════════════════════╗ |
| `governance.promotion_manager` | promotion_manager.py |
| `governance.provenance_derivation` | provenance_derivation.py — the backfill engine (MPA v1, Phase 3). |
| `governance.provenance_record` | provenance_record.py — the Provenance Spine's append-only record (MPA v1, Phase 1). |
| `governance.provenance_resolver` | provenance_resolver.py — read-only slot resolution over the EXISTING record systems (Phase 2). |
| `governance.reflection_buffer_advanced` | _(no module docstring)_ |
| `governance.script_census` | SITS script census core (PR-6 extract from scripts/analysis/script_census.py). |
| `governance.script_registry` | ScriptRegistry — inventory / debt visibility for scripts (SITS). |
| `governance.script_seed` | SITS seed pipeline core (PR-6 extract from scripts/governance/seed_script_registry.py). |
| `governance.semantic_grounding` | semantic_grounding — closed-world claim grounder (Semantic OS L5 companion). |
| `governance.semantic_identity` | semantic_identity — Tier-3 derivation for the Semantic File Identity Layer. |
| `governance.semantic_objects` | semantic_objects — the GENERATED Object layer of the Semantic OS. |
| `governance.semantic_os` | SemanticOSRegistry — the hand-authored semantic layer (Concepts / Boundaries / Journeys). |
| `governance.semantic_query` | semantic_query — L5, the Semantic Query Engine. |
| `governance.shadow_promotion_gate` | governance/shadow_promotion_gate.py |
| `governance.strategy_backtest` | strategy_backtest.py |

### `src/identity/`

| Module | Role (docstring line 1) |
| --- | --- |
| `identity` | Identity store — Phase 4 writers/readers for the frozen layer identities. |
| `identity.certify` | Shadow XAUUSD identity certification. |
| `identity.check` | Identity Check — the only legal load path. |
| `identity.hashes` | Identity hashes. Algorithms are frozen in the identity contract, not imported from HEAD schema. |
| `identity.outcome` | L5 outcome record builder. |
| `identity.query` | Phase 5 — replay and query over PRESERVED identity records only. |
| `identity.store` | File-backed identity store: Class A snapshots, Class B records, Class C bindings. |
| `identity.tokens` | Closed vocabularies copied from the identity contract. Not imported from HEAD engines. |

### `src/inout/`

| Module | Role (docstring line 1) |
| --- | --- |
| `inout.alphavantage_candle_fetcher` | AlphaVantageCandleFetcher |
| `inout.hummingbot_candle_fetcher` | HummingbotCandleFetcher |
| `inout.live_rail` | Live-rail PR-1 contracts. Unwired — no HookedLiveEngine caller, no orders. |
| `inout.live_rail.bar_builder` | Aggregate ticks into 6-col Candle + optional spread extras. No lookahead. |
| `inout.live_rail.binance_ws_adapter` | Binance combined-stream paper-data. Crypto only. No orders. |
| `inout.live_rail.config` | live_rail config. Nested ``_require`` — no silent defaults. Not on ACTIVE_VERSION. |
| `inout.live_rail.factory` | Venue port factory. Paper order venue only. |
| `inout.live_rail.longport_adapter` | LongPort reservation. Zero repo presence — do not pretend an SDK is wired. |
| `inout.live_rail.ohlcv_replay_port` | Deterministic historical replay source for live-rail certification. |
| `inout.live_rail.resilience` | Reconnect backoff + fail-closed circuit breaker for live-rail I/O. |
| `inout.live_rail.tickdb_adapter` | File-backed JSONL tick replay. Default data venue. Zero network. Zero money. |
| `inout.live_rail.types` | Live-rail value types. PR-1 contracts — no EngineRunner, no orders. |
| `inout.mt5_candle_fetcher` | MT5CandleFetcher |
| `inout.perp_funding_fetcher` | PerpFundingFetcher |

### `src/interpreters/`

| Module | Role (docstring line 1) |
| --- | --- |
| `interpreters` | Interpreter Contract Layer (Level 4) — behavior-agnostic event/feature producers. |
| `interpreters.adapter` | adapter.py — the ONLY bridge from an Interpreter to the research measurement stack. |
| `interpreters.contract` | contract.py — the Interpreter Contract (frozen Schema 1.0). |
| `interpreters.point_and_figure` | point_and_figure.py — PNF-v1, the FIRST real interpreter (Plan 5). Shadow / measure-only. |
| `interpreters.reference` | reference.py — proof-of-contract interpreters. NOT real interpreters. |
| `interpreters.regime_observer` | regime_observer.py — non-directional volatility-regime reading (Program 4 / Program 4b). |

### `src/journal/`

| Module | Role (docstring line 1) |
| --- | --- |
| `journal` | _(no module docstring)_ |
| `journal.schema` | _(no module docstring)_ |
| `journal.trade_execution_link_v1_0` | trade_execution_link_v1_0 — transport correlation layer (Tier 0B, disposable). |
| `journal.trade_identity_v1_0` | trade_identity_v1_0 — the sacred minimum trade identity (Tier 0A). |
| `journal.trade_logger` | _(no module docstring)_ |
| `journal.trade_provenance_v1_0` | trade_provenance_v1_0 — governance lineage (Tier 0B, append, keyed by trade_id). |

### `src/live/`

| Module | Role (docstring line 1) |
| --- | --- |
| `live` | _(no module docstring)_ |
| `live.mt5_bridge` | mt5_bridge.py |
| `live.order_manager` | Layer-5 paper order I/O. Size is Ultron final_position_size only. |
| `live.telegram_bridge` | telegram_bridge.py |

### `src/llm_research/`

| Module | Role (docstring line 1) |
| --- | --- |
| `llm_research` | LLM Research Pipeline — offline pattern extraction → policy generation → forward validation. |
| `llm_research.evaluator` | _(no module docstring)_ |
| `llm_research.forward_tester` | _(no module docstring)_ |
| `llm_research.pattern_extractor` | _(no module docstring)_ |
| `llm_research.policy_builder` | _(no module docstring)_ |

### `src/monitoring/`

| Module | Role (docstring line 1) |
| --- | --- |
| `monitoring` | _(no module docstring)_ |
| `monitoring.health_checker` | health_checker.py |

### `src/msip/`

| Module | Role (docstring line 1) |
| --- | --- |
| `msip` | MSIP shadow continuous market-state package (OBSERVATION_ONLY). |
| `msip.disagreement` | Optional shadow vs CRT observation disagreement taxonomy (telemetry only). |
| `msip.interpretation_config` | HOW config for MSIP shadow — `msip_shadow` section only. |
| `msip.isolation` | Import / mutation isolation policy for the MSIP shadow package. |
| `msip.market_state_vector` | MarketStateVector value object — schema pin MARKET_STATE_VECTOR_SCHEMA_V1. |
| `msip.shadow_emitter` | Shadow MarketState assembly — pure build + append-only emit. |

### `src/multi_llm/`

| Module | Role (docstring line 1) |
| --- | --- |
| `multi_llm` | multi_llm — coordination layer for the hand-operated DeepSeek/Gemini/ChatGPT/Claude pipeline. |
| `multi_llm.context_pack` | context_pack.py — bounded, upload-ready context for ONE task (never the whole codebase). |
| `multi_llm.discussion` | discussion.py — reconstruct and REWIND the multi-LLM discussion (view-only time-travel). |
| `multi_llm.tokens` | tokens.py — honest token *estimate* (no external tokenizer dependency). |
| `multi_llm.turn_ledger` | turn_ledger.py — append-only, no-loss record of every multi-LLM turn. |

### `src/portfolio/`

| Module | Role (docstring line 1) |
| --- | --- |
| `portfolio` | _(no module docstring)_ |
| `portfolio.allocator` | _(no module docstring)_ |
| `portfolio.capital_policy` | _(no module docstring)_ |
| `portfolio.correlation_engine` | _(no module docstring)_ |
| `portfolio.exposure_tracker` | _(no module docstring)_ |
| `portfolio.replay` | replay.py — read-only shadow replay of PortfolioAllocator over a historical trade ledger. |

### `src/regime/`

| Module | Role (docstring line 1) |
| --- | --- |
| `regime` | _(no module docstring)_ |
| `regime.config_router` | _(no module docstring)_ |
| `regime.market_state_cluster_engine` | market_state_cluster_engine.py |
| `regime.regime_classifier` | _(no module docstring)_ |

### `src/replay/`

| Module | Role (docstring line 1) |
| --- | --- |
| `replay` | _(no module docstring)_ |
| `replay.replay_drift_governor` | replay_drift_governor.py |
| `replay.replay_memory_engine` | replay_memory_engine.py |
| `replay.replay_similarity_index` | replay_similarity_index.py |
| `replay.timing_advisor` | timing_advisor.py |
| `replay.timing_reconstructor` | timing_reconstructor.py |

### `src/research/`

| Module | Role (docstring line 1) |
| --- | --- |
| `research` | Edge Discovery Program — behavior-agnostic research platform. |
| `research.adapters` | adapters — bridges that let the isolated research harness consume the live spine. |
| `research.adapters.shape_signal_source` | shape_signal_source.py — precompute MarketShape directional signals per bar (Program 11 / B1). |
| `research.adapters.spine_signal_source` | spine_signal_source.py — run the production CRT spine, harvest its entries. |
| `research.adapters.structural_event_source` | structural_event_source.py — Phase E1 harvester: the full CRT structural-event population. |
| `research.band_tables` | band_tables.py — strict loader + classifiers for configs/research/band_tables.json. |
| `research.band_validation` | band_validation.py — do candidate band thresholds correspond to STABLE BEHAVIORAL REGIMES? |
| `research.candle_state` | candle_state — non-directional candle-state encoding + multi-timeframe conjunction. |
| `research.candle_state.encoder` | encoder.py — CandleStateEncoder: a candle window -> discrete state + continuous features. |
| `research.candle_state.info_robustness` | info_robustness.py — Stage-1 information-robustness kernels (FROZEN thresholds in pre-reg). |
| `research.candle_state.m5_incremental` | m5_incremental.py — Program-9 Stage-1 kernels: M5-base keys + the incremental gate. |
| `research.candle_state.mtf_conjunction` | mtf_conjunction.py — MultiTFConjunctionBuilder: M15 window -> {M15,H1,H4} state key. |
| `research.candle_state.reporting` | reporting.py — REPORTING-ONLY trade metrics (win-rate, losing streak, rolling-10). |
| `research.candle_state.transition_target` | transition_target.py — non-directional FORWARD target labelers (Stage-1 only). |
| `research.clean_labels` | Clean-label builders for TradeNet + EnvelopeNet (GATE-L / ENV-L research tooling). |
| `research.clean_labels.builder` | Shared clean-label builder: TradeNet Bernoulli heads + Envelope continuous targets. |
| `research.clean_labels.protocol` | Frozen experiment identity for the dual TradeNet + EnvelopeNet clean-label builder. |
| `research.cli` | cli.py — thin entrypoint for the research harness. |
| `research.conditional_entropy_grid` | conditional_entropy_grid.py — Phase B (B1): where, if anywhere, does next-direction |
| `research.config` | config.py — ResearchConfig: the single source of truth for the research harness. |
| `research.contracts` | contracts.py — frozen interfaces for the Edge Discovery Program. |
| `research.controls` | Falsification controls — the platform's immune system. |
| `research.controls.always_long` | always_long.py — the anti-drift control. |
| `research.controls.random_baseline` | random_baseline.py — null controls: random entries. |
| `research.costs` | costs.py — conservative flat cost model for the falsification phase (M1–M6). |
| `research.cross_sectional` | cross_sectional.py — Program 5: cross-sectional relative-value (dispersion) measurement. |
| `research.envelope_offline` | Envelope offline research training (ENV_OFFLINE_TRAIN_V1). |
| `research.envelope_offline.shadow` | Envelope shadow weight-0 logging — ENV_SHADOW_W0_V1. |
| `research.envelope_offline.train` | Narrow multi-head Envelope offline trainer — ENV_OFFLINE_TRAIN_V1. |
| `research.episode_agreement` | Phase 2C — typed AGREEMENT object (O14): fold over Phase 2B propositions. |
| `research.episode_propositions` | Phase 2B — typed same-event propositions (research shadow). |
| `research.episodes` | Opportunity Episode research substrate (protocol OE_L1). |
| `research.episodes.builder` | EpisodeBuilder — candles + entry geometry → observation timeline. |
| `research.episodes.events` | EventEngine — sparse semantic milestones DERIVED from an episode timeline. |
| `research.episodes.flat` | Tier-2 flat projection — one row per (episode, timestep). |
| `research.episodes.policy` | PolicyEvaluator — labels derived from an episode under a chosen exit policy. |
| `research.episodes.projectors` | Episode projectors — different sources, one canonical schema. |
| `research.episodes.projectors.detection` | DetectionProjector — opportunities.jsonl → DETECTION_STREAM episodes. |
| `research.episodes.projectors.spine` | SpineProjector — the accepted-trade ledger → SPINE_TRADE episodes. |
| `research.episodes.protocol` | Frozen contract for the Opportunity Episode research substrate. |
| `research.episodes.query` | Episode Query Engine v1 — selections over episodes + LabelSets + EventSets. |
| `research.episodes.schema` | OpportunityEpisode canonical types (protocol OE_L1). |
| `research.episodes.store` | Episode store — canonical serialization + I/O. |
| `research.episodes.tensors` | Tier-3 tensor materializer — [N, T, D] views for sequence models. |
| `research.evidence` | Queryable evidence layer over the XAUUSD parquet projections. |
| `research.evidence.__main__` | python -m research.evidence --out results/research/parquet_evidence_layer |
| `research.evidence.asymmetry_contract` | MC-ASYM-XAUUSD-M15-V1 — same-timestamp ΔMFE holdout. |
| `research.evidence.atlases` | Three atlases over the bar×direction outcome surface. |
| `research.evidence.catalog` | Grain catalog for the XAUUSD parquet evidence layer. |
| `research.evidence.context_attribution` | MC-CTXATTR-XAUUSD-M15-V1 — does any context family add value beyond CRT state alone? |
| `research.evidence.driver` | Load the four projections and emit an evidence report. |
| `research.evidence.magnitude_prior` | MC-MAGPRIOR-XAUUSD-M15-V1 — trend_bias as magnitude/time prior on a given side. |
| `research.evidence.mother_range_prior` | MC-MRPRIOR-XAUUSD-M15-V1 — sparse mother-range inside signal x FM-054 trend prior. |
| `research.evidence.queries` | Named evidence queries over column maps. |
| `research.evidence.records` | Evidence records — measurements, not predictions. |
| `research.evidence.rnet_overlay` | MC-RNET-OVERLAY-XAUUSD-M15-V1 — y_R_net size overlay on independent entry. |
| `research.evidence.run_close_out` | run_close_out.py — the shared close-out every sealed-contract experiment runs. |
| `research.evidence.visual_crt_prior` | MC-VCRTPRIOR-XAUUSD-M15-V1 — sparse Visual CRT entries x FM-054 trend prior. |
| `research.exit_grid` | exit_grid.py — Phase D pure core: SL/TP exit-geometry grid + the recoverable-value ceilings. |
| `research.experiment_spec` | experiment_spec.py — the immutable execution specification for the research platform. |
| `research.forensics` | forensics.py — Layer-6 root-cause analysis: WHY a behavior loses under intrabar truth. |
| `research.goal_alignment` | goal_alignment.py |
| `research.hypotheses` | Behavior hypotheses. Importing this package registers each one via its decorator. |
| `research.hypotheses.compression_box_straddle` | compression_box_straddle.py — Program-9 Stage-2 economic consumer (transition family). |
| `research.hypotheses.compression_breakout` | compression_breakout.py — Program-4b Stage-2 economic consumer (transition family). |
| `research.hypotheses.expansion_breakout` | expansion_breakout.py — continuation behavior (hypothesis #1, NOT privileged). |
| `research.hypotheses.market_shape_hypothesis` | market_shape_hypothesis.py — the semantic Market-Shape layer as a research Hypothesis (P11/B1). |
| `research.hypotheses.mean_reversion` | mean_reversion.py — the OPPOSITE behavior, shipped at M2 to prove no continuation bias. |
| `research.hypotheses.spine_hypothesis` | spine_hypothesis.py — the production spine, wrapped as a research Hypothesis. |
| `research.hypotheses.weekly_sweep_reversal` | weekly_sweep_reversal.py — Program 8 economic consumer of the weekly liquidity-sweep ontology. |
| `research.ic002_entry_evolution` | IC-002 / RC-005 Entry Evolution — post-entry OHLCV trajectories (research only). |
| `research.ic002_entry_evolution.build_trajectories` | Build IC-002 path-relative trajectories — one FeaturePipeline pass, then slice. |
| `research.ic002_entry_evolution.evaluate_separation` | IC-002 primary evaluation: path vs static baseline under time-ordered OOS. |
| `research.ic002_entry_evolution.io_util` | Load prereg JSON, entries, OHLCV path resolution, save trajectory batches. |
| `research.ic002_entry_evolution.schema` | IC-002 / RC-005 frozen schema — must match h-ic002 experiment definition JSON. |
| `research.ic003_shapes` | IC-003 trajectory shape library (research only). |
| `research.ic003_shapes.build_library` | Build IC-003 shape library from IC-002 trajectory batches. |
| `research.ic003_shapes.schema` | IC-003 frozen constants — match h-ic003 experiment definition (v1 scientific bar). |
| `research.ic003b_sequence_geometry` | IC-003B sequence geometry shape library (research only). |
| `research.ic003b_sequence_geometry.build_all` | Orchestrate IC-003B arms S / T / C and write artifacts. |
| `research.ic003b_sequence_geometry.cluster_dtw` | Arm T: DTW + k-medoids on 3-channel paths. |
| `research.ic003b_sequence_geometry.cluster_euclid` | Arm S: Euclidean library on path-summary vectors (IC-003 v1 gates). |
| `research.ic003b_sequence_geometry.continuum` | Arm C: PCA continuum diagnostic. |
| `research.ic003b_sequence_geometry.dtw` | Deterministic DTW with Sakoe-Chiba band (Arm T). |
| `research.ic003b_sequence_geometry.schema` | IC-003B frozen constants — match h-ic003b experiment definition. |
| `research.ic003b_sequence_geometry.summarize` | Arm S: path-summary vectorization (7 stats × D). |
| `research.indicators` | indicators.py — small, dependency-light technical helpers for hypotheses/controls. |
| `research.mc_kit` | mc_kit — shared low-level primitives for sealed-contract (MC-*) research drivers. |
| `research.mc_kit.bars` | bars.py — CSV bar loading shared by sealed-contract drivers. |
| `research.mc_kit.stats` | stats.py — per-cell statistics shared by sealed-contract drivers. |
| `research.mc_kit.trade` | trade.py — forward-walk step and exit classification shared by trade-contract drivers. |
| `research.measurement` | Measurement core — no-lookahead forward-walk + edge aggregation. |
| `research.measurement.bootstrap` | bootstrap.py — deterministic percentile bootstrap confidence interval. |
| `research.measurement.forward_walk` | forward_walk.py — no-lookahead forward simulation of a Signal. |
| `research.measurement.metrics` | metrics.py — EdgeAggregator: turn a list of Outcomes into an EdgeReport. |
| `research.measurement.mt00` | mt00.py — the E-MT-00 clean-path runner (MEASUREMENT_CONTRACT.md §2, E0–E2). |
| `research.model_runners` | Per-model historical offline runners (OBSERVATION_ONLY). |
| `research.model_runners.adapters` | Model adapters — call production engines only. |
| `research.model_runners.adapters.bitnet` | BitNet hard-reject gate adapter (off-spine observe; does not flip use_bitnet). |
| `research.model_runners.adapters.crt_score` | Fusion CRT scorer adapter — engines.crt_engine.compute → compute_scores. |
| `research.model_runners.adapters.crt_state_machine` | Full CRTEngine state machine on sequential candles (not fusion crt_score). |
| `research.model_runners.adapters.decision` | Stage-4 approval adapter (A4) — fusion evidence -> DecisionEngine.evaluate. |
| `research.model_runners.adapters.dual_engine` | Stage-1 dual-engine adapters: regime / trap / breakout (A1-A3). |
| `research.model_runners.adapters.envelope_net` | EnvelopeNet offline adapter — requires --artifact (bundle dir or envelope_bundle.json). |
| `research.model_runners.adapters.execution_plan` | Stage-5 execution-plan adapter (A5) — the full candle -> executable-trade chain. |
| `research.model_runners.adapters.fusion_compute` | Compose four live engines → FusionEngine.compute (no DecisionEngine). |
| `research.model_runners.adapters.gaussian` | Live HeuristicGaussianEngine adapter (spine gaussian slot). |
| `research.model_runners.adapters.gaussian_ml` | OFF-spine ML Gaussian (GaussianNB) adapter — independent of gaussian_impl. |
| `research.model_runners.adapters.rr_polarity` | Live RREngine (candle polarity) adapter. |
| `research.model_runners.adapters.rr_trained` | OFF-spine trained RR (NanoInference rr_model.json) — observe-only. |
| `research.model_runners.adapters.tradenet` | TradeNet v2 observe adapter (UNWIRED on spine; requires --artifact). |
| `research.model_runners.adapters.zone_gate` | Production ZoneGate cluster scorer adapter. |
| `research.model_runners.contracts` | Model catalog — all audit models; phase marks implement status. |
| `research.model_runners.envelope` | Output envelope schemas for model_runners (single serialization authority). |
| `research.model_runners.require_config` | Strict config accessors for model_runners — single source of truth only. |
| `research.model_runners.runner` | Orchestrate substrate × adapter → artifacts (OBSERVATION_ONLY). |
| `research.model_runners.schema_resolver` | Single live->trained feature-schema authority for model_runners (R1). |
| `research.model_runners.stats` | Pure summary stats over collected numeric arrays (no fill / no imputation). |
| `research.model_runners.substrate` | Historical OHLCV + FeaturePipeline substrate (one load path). |
| `research.mother_range` | Mother-range inside-close trade object (SEM-026). Research only. |
| `research.mother_range.__main__` | python -m research.mother_range --out results/mother_range/mc_mrange_xauusd_m15_v1 |
| `research.mother_range.driver` | Single-pass mother-range measurement. Bindings = MC-MRANGE-XAUUSD-M15-V1. |
| `research.mother_range.geometry` | t=0 mother-range inside-close geometry (SEM-026). |
| `research.mt5_cost_calibration` | mt5_cost_calibration |
| `research.ohlcv_open_close_label` | BC-2 executable open-vs-close label scorer. |
| `research.ohlcv_probe_report` | Shared emission contract for OHLCV corpus-authority probes (BC-2, BC-4, ...). |
| `research.ohlcv_tick_attribution` | BC-4 residual attribution: what explains tick_volume vs len(copy_ticks_range)? |
| `research.ohlcv_volume_semantics` | BC-4 volume-semantics scorer: does MT5 `volume` count ticks? |
| `research.opportunity_bands` | opportunity_bands.py — Phase-1 arithmetic derivation over one SEM-037 kernel row. |
| `research.oracle` | oracle — outcome-first (SEM-018) per-bar labelling under the SEM-017 exit geometry. |
| `research.oracle.exit_analysis` | exit_analysis.py — SEM-020 exit-capture decomposition: what any exit COULD achieve. |
| `research.oracle.exit_sweep` | exit_sweep.py — geometry x dynamic-stop-policy sweep over the dense bar universe. |
| `research.oracle.labeler` | labeler.py — Stage 1 of the profitable-entry oracle program (SEM-018). |
| `research.oracle.multi_tp_walk` | multi_tp_walk.py — SEM-017 two-target partial-exit forward walk. |
| `research.oracle.reference_walker` | reference_walker.py — deliberately naive twin of `multi_tp_walk`, for triangulation. |
| `research.oracle.scan` | scan.py — effect sizes, controls and partitioning for the oracle pattern search. |
| `research.oracle.stop_policy` | stop_policy.py — SEM-019 causal dynamic stop policies for the two-target object. |
| `research.path` | research.path — Program 10 (intrabar path) measurement layer. |
| `research.path.ambiguity_census` | ambiguity_census.py — Program 10 / Phase 0A pure core: how often does the same-bar |
| `research.probes` | Shared research probe helpers. |
| `research.probes.atlas_io` | Decision-atlas IO helpers extracted from build_decision_atlas.py. |
| `research.probes.corpus` | Candle corpus loading shared by analysis probes. |
| `research.probes.costs_path` | SEM-015 cost + TIMEOUT net-R path shared by economic probes. |
| `research.probes.excursion` | Uncapped ATR excursion via governed forward_walk (from p001 probe). |
| `research.probes.governance` | Probe artifact governance helpers. |
| `research.probes.horizon` | Hold-to-horizon gross R scoring shared by economic probes. |
| `research.probes.persistence` | Episode-chain persistence helpers shared by sweep/state probes. |
| `research.probes.phase1_replay` | Phase-1 resolver replay helpers shared by evidence + sample_acquisition CLIs. |
| `research.probes.scoreboard` | Generic probe scoreboard rows (n / coverage / expectancy / PF / win rate). |
| `research.probes.scriptmod` | Load a sibling .py file as a module (single importlib choke-point). |
| `research.probes.shadow_collapse` | SHADOW to EXP collapse capture - re-exports phase1_replay helpers. |
| `research.process_characterization` | process_characterization.py — statistical fingerprint of a raw OHLCV series. |
| `research.process_diagnostics` | process_diagnostics.py — significance tests over the Phase-1 process fingerprint. |
| `research.provenance` | provenance.py — versioned realism/method stamps for research artifacts. |
| `research.qualification` | qualification.py — M4 QualificationGate for the Edge Discovery Program. |
| `research.qualify_matrix` | qualify_matrix.py — shared scope-loop helpers for the QUALIFY family of research drivers. |
| `research.rc003_distinct_object` | RC-003 — are the directional-contract-violation bars a distinct object at all? |
| `research.rc003_distinct_object.driver` | RC-003 driver — executes the frozen pre-registration, nothing more. |
| `research.regime_conditioning` | regime_conditioning.py — Program 4 conditioning harness (the only new measurement). |
| `research.registry` | registry.py — hypothesis plugin registry (mirrors src/agent/tool_registry.py). |
| `research.resample` | resample.py — deterministic calendar OHLCV resampler (Program 3 harness; Program 9 |
| `research.runner` | runner.py — HypothesisRunner: stream CSVs → detect → forward_walk → EdgeReport. |
| `research.secondlow_v1` | SECONDLOW-v1 detector — canonical MT5 corpus + xlsx regression fixture. |
| `research.secondlow_v1.corpus` | XAUUSD M15 corpus paths for SECONDLOW research. |
| `research.secondlow_v1.depth_metrics` | Alternative purge-depth metrics (descriptive / pre-reg only — not production defaults). |
| `research.secondlow_v1.detector` | SECONDLOW-v1 purge detector (trading-day second_low_20d ladder). |
| `research.secondlow_v1.regime_metrics` | Lightweight volatility regime descriptors at purge time (descriptive only). |
| `research.selection_effect` | selection_effect.py — Phase S1 pure core: the spine's RETEST selection effect. |
| `research.shape_statistics` | Historical Statistics layer — Layer 6 of the semantic pipeline (roadmap Phase 5, statistics). |
| `research.structural_asymmetry` | structural_asymmetry.py — Program 2 / Phase E1 pure core: forward asymmetry of a structural-event |
| `research.sujan_crt` | Sujan nested veto chain (SEM-031). Research only. |
| `research.sujan_crt.__main__` | python -m research.sujan_crt --out docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1 |
| `research.sujan_crt.driver` | MC-SUJAN-XAUUSD-M15-V1 driver. Bindings frozen in the sealed instance. |
| `research.sujan_crt.geometry` | SEM-031 primitives: calendar parents, SP-001 sweep, SP-002 displacement, return, RR. |
| `research.sujan_crt.score` | SEM-023 comparison arm. Never admits or rejects a SEM-031 candidate. |
| `research.sujan_crt.vetoes` | SEM-031 nested veto chain. Conjunction is admission. SEM-023 never gates. |
| `research.sujan_manipulation` | Sujan manipulation detection, Phase 1 (SEM-033). Research only. |
| `research.sujan_manipulation.__main__` | SEM-033 Phase-1 CLI. Two modes, deliberately separate. |
| `research.sujan_manipulation.bulk_proxy` | SEM-034 — the bulk-candle proxy. APPROVED by the human bridge, UNVALIDATED. |
| `research.sujan_manipulation.driver` | SUJAN_MANIPULATION_RESEARCH_PHASE_1 run driver (SEM-033). Research only. |
| `research.sujan_manipulation.geometry` | SUJAN_MANIPULATION_RESEARCH_PHASE_1 primitives (SEM-033). Research only. |
| `research.sujan_manipulation.label_page` | Render the bulk-candle confirmation page — a CURATION TOOL, not a measurement instrument. |
| `research.sujan_manipulation.parent` | The FOUNDING layer for SEM-033 — still incomplete, now with an approved proxy. |
| `research.sujan_manipulation.parquet_check` | Cross-check the proxy's CSV-derived magnitudes against the Parquet projection. |
| `research.sujan_manipulation.state` | The Phase-1 state machine, implemented literally. |
| `research.synthetic` | research.synthetic — deterministic market-STORY library (ERP P1 golden fixtures). |
| `research.synthetic.ontology` | ontology.py — loader + six-layer binder for the market-story ontology. |
| `research.synthetic.stories` | stories — the Phase-A market-story library (4 active families). |
| `research.synthetic.stories.breakout` | breakout — compression resolves; a range boundary breaks, expands, retests, then continues. |
| `research.synthetic.stories.liquidity_reversal` | liquidity_reversal — resting liquidity swept, price reverses & reclaims (CRT golden path). |
| `research.synthetic.stories.range_rotation` | range_rotation — balanced range; edges fade to the mean (CRT-quiescent), plus a failed break. |
| `research.synthetic.stories.trend_continuation` | trend_continuation — an established trend pulls back to a retest, then continues. |
| `research.synthetic.story_builder` | story_builder.py — turn a StorySpec into an intended-vs-produced golden trace + six-layer binding. |
| `research.synthetic.story_registry` | story_registry.py — the single collection point for every registered StorySpec. |
| `research.synthetic.story_spec` | story_spec.py — frozen value objects for a deterministic market story. |
| `research.visual_crt` | visual_crt — the Visual CRT trade object (SEM-012), Lane 1 geometry. |
| `research.visual_crt.controls` | controls.py — the OOS split and control benchmarks MC-VCRT-XAUUSD-M15-V1 declared. |
| `research.visual_crt.driver` | driver.py — Visual CRT ledger driver. Default bindings = MC-VCRT-XAUUSD-M15-V1. |
| `research.visual_crt.geometry` | geometry.py — Visual CRT sweep + directional-displacement geometry (SEM-012). |
| `research.visual_crt.measure` | measure.py — run a sealed Visual CRT measurement contract end to end. |
| `research.visual_crt.pools` | pools.py — chart-visible liquidity pools for the Visual CRT trade object (SEM-012). |
| `research.visual_crt.retest` | retest.py — Arm B retest predicate for the Visual CRT trade object (SEM-012 v2). |
| `research.weekly_sweep` | weekly_sweep — Program 8: weekly liquidity-sweep ontology (pure geometry, no-lookahead). |
| `research.weekly_sweep.weekly_range` | weekly_range.py — Program 8: weekly accumulation range + sweep geometry. |
| `research.xau_metals_protocol` | xau_metals_protocol.py |
| `research.zone_label_audit` | zone_label_audit.py — F-041B Phase-5 ZoneGate label-provenance audit (MEASURE-ONLY). |
| `research.zone_mapping` | Historical zone mapping — pre-CRT geometry assignment (research tooling). |
| `research.zone_mapping.boundary_hypothesis_eval` | Geometry-boundary hypothesis test. |
| `research.zone_mapping.build_corpus_zone_map` | Map every bar of a CSV corpus with HistoricalZoneMapper and compute zone census. |
| `research.zone_mapping.collect_trade_opened_features` | Collect TRADE_OPENED-shaped feature dicts from a real XAUUSD CRT path. |
| `research.zone_mapping.crt_zone_crosstab` | CRT State × Zone cross-tabulation — relevance of geometry to CRT structure. |
| `research.zone_mapping.displacement_zone_event_study` | Lead/lag event study: CRT DISPLACEMENT starts vs zone assignments. |
| `research.zone_mapping.gaussian_delta_gap_eval` | H-GAUSS-DELTA-001 — calibration gap Δ = ML − H evaluation (measure-only). |
| `research.zone_mapping.gaussian_family_shadow_eval` | Gaussian family shadow measurement (H + ML via EngineRunner shadow_ml contract). |
| `research.zone_mapping.historical_zone_mapper` | HistoricalZoneMapper — every-bar (or batch) zone cluster assignment. |
| `research.zone_mapping.rare_zone_context_filter_eval` | Context-filter experiment: rare-zone entry × CRT state at signal time. |
| `research.zone_mapping.rare_zone_detection_eval` | Event-detection evaluation: rare-zone entry → CRT DISPLACEMENT within K bars. |
| `research.zone_mapping.rare_zone_fa_characterization` | False-alarm characterization for rare-zone → DISPLACEMENT detection. |
| `research.zone_mapping.zone_census` | Zone geometry census — baseline description of market geometry from a bar map. |

### `src/retrieval/`

| Module | Role (docstring line 1) |
| --- | --- |
| `retrieval` | retrieval/ — Truth-tier lexical RAG for the Tradelatest corpus. |
| `retrieval.chunking` | retrieval/chunking.py — Semantic chunking by language construct, not fixed token size. |
| `retrieval.claude_integration` | retrieval/claude_integration.py — Claude / control-plane integration for truth-tier RAG. |
| `retrieval.config` | retrieval/config.py — Configuration for the truth-tier retrieval pipeline. |
| `retrieval.corpus` | retrieval/corpus.py — Truth-classified document discovery. |
| `retrieval.divergence` | retrieval/divergence.py — Mechanical divergence checks over retrieval hits. |
| `retrieval.embedding` | retrieval/embedding.py — Embedding pipeline using sentence-transformers. |
| `retrieval.index_store` | retrieval/index_store.py — DuckDB/Parquet-backed lexical index. |
| `retrieval.lexical` | retrieval/lexical.py — BM25 over DuckDB/Parquet (hand-rolled, no fts extension). |
| `retrieval.monitor` | retrieval/monitor.py — Monitoring and metrics for the RAG pipeline. |
| `retrieval.retriever` | retrieval/retriever.py — Truth-tier retrieval + context assembly. |
| `retrieval.truth_tier` | retrieval/truth_tier.py — Truth classification for retrieval chunks. |
| `retrieval.vector_store` | retrieval/vector_store.py — ChromaDB-backed vector store with hybrid search. |

### `src/runtime/`

| Module | Role (docstring line 1) |
| --- | --- |
| `runtime` | _(no module docstring)_ |
| `runtime.analyze_fusion_shadow` | Analyze EngineRunner fusion shadow telemetry from collector logs. |
| `runtime.backtest_bitnet` | backtest_bitnet.py |
| `runtime.backtest_v2` | ╔═══════════════════════════════════════════════════════════════════════╗ |
| `runtime.bar_structure_snapshot` | bar_structure_snapshot.py — the v3 `BarStructureSnapshot`: one observation-only record per bar. |
| `runtime.baseline_capture` | baseline_capture.py |
| `runtime.crt_baseline_trace` | crt_baseline_trace.py — optional, behavior-preserving CRT baseline observation. |
| `runtime.crt_construction_trace` | crt_construction_trace.py — the v4 `CRTConstructionTrace`: engine vs ontology, per bar. |
| `runtime.crt_fail_reason_counters` | CRT try_* fail-reason counters — OBSERVATION_ONLY. |
| `runtime.exit_model_band` | exit_model_band.py |
| `runtime.live_engine_hook` | live_engine_hook.py |
| `runtime.live_rail_feeder` | Live-rail feature feeder (PR-4b). |
| `runtime.live_rail_orchestrator` | F-073 repair: missing caller of HookedLiveEngine.process. Paper TickDB only. |
| `runtime.parent_crt_feed` | parent_crt_feed.py — streaming adapter that closes F-075's caller gap. |
| `runtime.unified_replay_harness` | unified_replay_harness.py |

### `src/scanner/`

| Module | Role (docstring line 1) |
| --- | --- |
| `scanner` | _(no module docstring)_ |
| `scanner.ranker` | _(no module docstring)_ |
| `scanner.scanner` | _(no module docstring)_ |
| `scanner.signal_pool` | _(no module docstring)_ |
| `scanner.spine_adapter` | scanner/spine_adapter.py |
| `scanner.universe` | _(no module docstring)_ |

### `src/search/`

| Module | Role (docstring line 1) |
| --- | --- |
| `search.regime_weight_searcher` | regime_weight_searcher.py |

### `src/strategies/`

| Module | Role (docstring line 1) |
| --- | --- |
| `strategies` | strategies package — all 10 strategy modules (S1..S10) + orchestrator. |
| `strategies.base_strategy` | base_strategy.py |
| `strategies.intent_builder` | intent_builder.py |
| `strategies.s01_crt_wrapper` | s01_crt_wrapper.py |
| `strategies.s02_mean_reversion` | s02_mean_reversion.py |
| `strategies.s03_breakout` | s03_breakout.py |
| `strategies.s04_stat_arb` | s04_stat_arb.py |
| `strategies.s05_grid` | s05_grid.py |
| `strategies.s06_scalping` | s06_scalping.py |
| `strategies.s07_news_sentiment` | s07_news_sentiment.py |
| `strategies.s08_ml_ensemble` | s08_ml_ensemble.py |
| `strategies.s09_pattern_recog` | s09_pattern_recog.py |
| `strategies.s10_trap_strategy` | s10_trap_strategy.py |
| `strategies.strategy_intent` | strategy_intent.py |
| `strategies.strategy_orchestrator` | strategy_orchestrator.py |
| `strategies.strategy_package` | strategy_package.py |
| `strategies.strategy_registry` | strategy_registry.py |
| `strategies.strategy_result` | strategy_result.py |

### `src/structure/`

| Module | Role (docstring line 1) |
| --- | --- |
| `structure` | structure — the governed CRT structural kernel. |
| `structure.predicates` | Structural decision predicates — HOW-COMPUTATION for SP-001 / SP-002. |

### `src/training/`

| Module | Role (docstring line 1) |
| --- | --- |
| `training.bar_semantic_tracker` | bar_semantic_tracker.py |
| `training.evaluator` | evaluator.py |
| `training.phase5_calibration` | phase5_calibration.py |
| `training.stage1_dataset_builder` | stage1_dataset_builder.py |
| `training.trade_net_v2` | trade_net_v2.py |
| `training.train_pipeline` | train_pipeline.py |
| `training.trainer` | trainer.py |
| `training.training_trigger` | training_trigger.py |

### `src/uat/`

| Module | Role (docstring line 1) |
| --- | --- |
| `uat` | _(no module docstring)_ |
| `uat.kill_switch` | kill_switch.py |
| `uat.monte_carlo` | monte_carlo.py |
| `uat.uat_runner` | uat_runner.py |

### `src/ui/`

| Module | Role (docstring line 1) |
| --- | --- |
| `ui` | _(no module docstring)_ |

### `src/utils/`

| Module | Role (docstring line 1) |
| --- | --- |
| `utils.config_dumper` | config_dumper.py |
| `utils.console_safe` | Console-safe output helpers for mixed terminal encodings. |
| `utils.duckdb_query` | duckdb_query.py — optional DuckDB query surface over Parquet projections. |
| `utils.engine_telemetry` | engine_telemetry.py |
| `utils.episode_summarizer` | episode_summarizer.py |
| `utils.integrity_events` | integrity_events.py |
| `utils.isolated_config_root` | isolated_config_root.py — run a process against a chosen production config, safely. |
| `utils.jsonl_writer` | jsonl_writer.py — the canonical append-only JSONL helper. |
| `utils.llm_logger` | llm_logger.py |
| `utils.log_identity` | log_identity.py |
| `utils.log_index_writer` | log_index_writer.py |
| `utils.logging_config` | Centralized Logging Configuration for Trading System |
| `utils.parquet_store` | parquet_store.py — derived Parquet projections over append-only JSONL corpora. |
| `utils.pattern_hasher` | pattern_hasher.py |
| `utils.registry_refresh` | registry_refresh.py |
| `utils.run_linkage` | run_linkage.py — resolve every artifact linked to a backtest run_id. |
| `utils.run_manifest` | run_manifest.py — provenance manifest for research/tool runs (ERP testing-plan §3.3). |
| `utils.sweep_trace_logger` | Sweep Trace Logger — Layer 0 of the trace-first repair pipeline. |
| `utils.trade_logger` | trade_logger.py |
| `utils.validation_contract` | validation_contract.py — H1/H2/H3 guards over run manifests (ERP testing-plan §5/§6). |
| `utils.zone_schema_migrator` | zone_schema_migrator.py |

### `src/validation_access/`

| Module | Role (docstring line 1) |
| --- | --- |
| `validation_access` | Validation Access (VA-XAUUSD-M15) — dual-surface sequential ladder S→I→F→E. |
| `validation_access.ladder` | VA-XAUUSD-M15 sequential validation ladder: S → I → F → E. |
| `validation_access.surfaces` | Dual surfaces for VA-XAUUSD-M15: Surface A (CLI) and Surface B (evidence pack). |

