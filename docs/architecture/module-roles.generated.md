# module-roles.generated.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_code_map.py`. One role line per `src/` module, taken from the module docstring's first line. Package-level roles + key modules live in [`codebase-state-map.md`](codebase-state-map.md) §1; the import graph is [`code-map.generated.md`](code-map.generated.md).

_`(no module docstring)` flags a module that should get a one-line docstring — that is the actionable code gap, not a docs gap._

**Coverage: 220/269 modules carry a docstring role (81%).** 49 flagged `(no module docstring)`.

### `src/agent/`

| Module | Role (docstring line 1) |
| --- | --- |
| `agent` | AI automation agent: natural language to intent to deterministic tool plan to confirm-gated execution. |
| `agent.agent_core` | agent_core.py |
| `agent.audit` | audit.py |
| `agent.cli` | cli.py — CRT Trading Agent interactive REPL |
| `agent.executor` | executor.py |
| `agent.findings_synthesizer` | findings_synthesizer.py — Post-run findings via Groq Llama-3.1-70B |
| `agent.groq_client` | groq_client.py — Agent-tier Groq LLM client with request logging + redaction |
| `agent.intent_router` | intent_router.py |
| `agent.log_query` | log_query.py |
| `agent.modes` | Agent tool-registration modes (pipeline, copilot, governance, findings, log-query). |
| `agent.modes.copilot_mode` | copilot_mode.py — Live Signal Co-pilot tool registrations |
| `agent.modes.findings_mode` | findings_mode.py — Post-run findings tool registrations |
| `agent.modes.governance_mode` | governance_mode.py — Governance Meta-reasoner tool registrations |
| `agent.modes.log_query_mode` | log_query_mode.py — Read-only log query tool registrations |
| `agent.modes.pipeline_mode` | pipeline_mode.py — Pipeline Orchestrator tool registrations |
| `agent.plan_compiler` | plan_compiler.py |
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
| `bitnet.bitnet_inference` | bitnet_inference.py |
| `bitnet.bitnet_runner` | BitNet Runner |
| `bitnet.forward_tester` | bitnet/forward_tester.py |
| `bitnet.model_contract` | model_contract.py |
| `bitnet.stability_checker` | bitnet/stability_checker.py |
| `bitnet.zone_cosine_searcher` | Zone Cosine Searcher |
| `bitnet.zone_validator` | bitnet/zone_validator.py |

### `src/cognitive/`

| Module | Role (docstring line 1) |
| --- | --- |
| `cognitive` | _(no module docstring)_ |
| `cognitive.cognitive_bus` | cognitive_bus.py |

### `src/config_layer/`

| Module | Role (docstring line 1) |
| --- | --- |
| `config_layer` | Config loaders, validators, and decision rules (CRT math, execution planner, LLM client). |
| `config_layer.config_builder` | config_builder.py |
| `config_layer.config_validator` | config_validator.py |
| `config_layer.crt_engine_v2` | ╔══════════════════════════════════════════════════════════════════╗ |
| `config_layer.crt_gaussian_scorer` | Central CRT Gaussian scorer. |
| `config_layer.crt_sweep_taxonomy` | crt_sweep_taxonomy.py |
| `config_layer.execution_planner` | execution_planner.py |
| `config_layer.goal_schema` | goal_schema.py |
| `config_layer.goal_validator` | goal_validator.py |
| `config_layer.insight_reporter` | insight_reporter.py |
| `config_layer.llm_inference_client` | llm_inference_client.py |
| `config_layer.llm_narrative` | llm_narrative.py |
| `config_layer.llm_scorer` | llm_scorer.py |
| `config_layer.market_router` | Market-type CRT config profiles (crypto/forex) and the profile router. |
| `config_layer.production_config` | production_config.py |
| `config_layer.rr` | Risk-reward fusion layer: RR dataset builder and RR model fusion. |
| `config_layer.rr.rr_dataset_builder` | rr_dataset_builder.py |
| `config_layer.rr.rr_fusion` | rr_fusion.py |
| `config_layer.rr.rr_pattern_miner` | rr_pattern_miner.py |

### `src/control_plane/`

| Module | Role (docstring line 1) |
| --- | --- |
| `control_plane` | Stdlib-HTTP control plane: localhost dashboard, command registry, job runner. |
| `control_plane.code_context_extractor` | code_context_extractor.py — AST-based code extraction for Context Reports. |
| `control_plane.context_report` | context_report.py — ContextReportAPI: Claude-powered operational intelligence for runs. |
| `control_plane.cp_types` | _(no module docstring)_ |
| `control_plane.dashboard_api` | dashboard_api.py |
| `control_plane.dot_graph_context` | dot_graph_context.py — flow resolution + architectural graph context for Context Reports. |
| `control_plane.jobs` | JobManager: queues and runs control-plane commands as subprocesses. |
| `control_plane.monitors` | Control-plane dashboard monitor specs (jsonl-tail/json/regex/file-stat sources). |
| `control_plane.registry` | CommandSpec registry: the catalog of control-plane commands. |
| `control_plane.report_api` | report_api.py — RunReportAPI: Excel generation + Groq LLM analysis for run history reports. |
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
| `core.ultron_risk_gate` | ultron_risk_gate.py |
| `core.ultron_risk_gate_wrapper` | core/ultron_risk_gate_wrapper.py — UltronRiskGateWrapper |

### `src/data_ingestion/`

| Module | Role (docstring line 1) |
| --- | --- |
| `data_ingestion` | _(no module docstring)_ |
| `data_ingestion.dataset_integrity` | dataset_integrity.py |
| `data_ingestion.historical_fetcher` | historical_fetcher.py |
| `data_ingestion.ohlcv_schema` | ohlcv_schema.py |

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
| `features.crt_feature_builder` | CRT Feature Builder |
| `features.dataset_builder` | _(no module docstring)_ |
| `features.dataset_validator` | dataset_validator.py |
| `features.feature_builder` | FeatureBuilder — constructs the canonical input_data dict from raw tick/row data. |
| `features.feature_monitor` | feature_monitor.py |
| `features.feature_pipeline` | feature_pipeline.py |
| `features.feature_schema` | _(no module docstring)_ |
| `features.schema_validator` | schema_validator.py |

### `src/feedback/`

| Module | Role (docstring line 1) |
| --- | --- |
| `feedback` | _(no module docstring)_ |
| `feedback.ai_feedback` | _(no module docstring)_ |

### `src/governance/`

| Module | Role (docstring line 1) |
| --- | --- |
| `governance` | _(no module docstring)_ |
| `governance.bitnet_governance_executor` | _(no module docstring)_ |
| `governance.config_integrity` | config_integrity.py — governance guards for production-config lineage. |
| `governance.expansion_integration` | _(no module docstring)_ |
| `governance.framework_registry` | FrameworkRegistry — queryable, append-only map of the trading-system architecture. |
| `governance.multi_strategy_validator` | multi_strategy_validator.py |
| `governance.orchestrator` | governance/orchestrator.py |
| `governance.portfolio_validation` | ╔══════════════════════════════════════════════════════════════════════╗ |
| `governance.promotion_manager` | promotion_manager.py |
| `governance.reflection_buffer_advanced` | _(no module docstring)_ |
| `governance.shadow_promotion_gate` | governance/shadow_promotion_gate.py |
| `governance.strategy_backtest` | strategy_backtest.py |

### `src/inout/`

| Module | Role (docstring line 1) |
| --- | --- |
| `inout.alphavantage_candle_fetcher` | AlphaVantageCandleFetcher |
| `inout.hummingbot_candle_fetcher` | HummingbotCandleFetcher |
| `inout.perp_funding_fetcher` | PerpFundingFetcher |

### `src/interpreters/`

| Module | Role (docstring line 1) |
| --- | --- |
| `interpreters` | Interpreter Contract Layer (Level 4) — behavior-agnostic event/feature producers. |
| `interpreters.adapter` | adapter.py — the ONLY bridge from an Interpreter to the research measurement stack. |
| `interpreters.contract` | contract.py — the Interpreter Contract (frozen Schema 1.0). |
| `interpreters.point_and_figure` | point_and_figure.py — PNF-v1, the FIRST real interpreter (Plan 5). Shadow / measure-only. |
| `interpreters.reference` | reference.py — proof-of-contract interpreters. NOT real interpreters. |
| `interpreters.regime_observer` | regime_observer.py — non-directional volatility-regime reading (Program 4). |

### `src/journal/`

| Module | Role (docstring line 1) |
| --- | --- |
| `journal` | _(no module docstring)_ |
| `journal.schema` | _(no module docstring)_ |
| `journal.trade_logger` | _(no module docstring)_ |

### `src/live/`

| Module | Role (docstring line 1) |
| --- | --- |
| `live` | _(no module docstring)_ |
| `live.mt5_bridge` | mt5_bridge.py |
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
| `research.adapters.spine_signal_source` | spine_signal_source.py — run the full production spine, harvest its entries. |
| `research.adapters.structural_event_source` | structural_event_source.py — Phase E1 harvester: the full CRT structural-event population. |
| `research.cli` | cli.py — thin entrypoint for the research harness. |
| `research.conditional_entropy_grid` | conditional_entropy_grid.py — Phase B (B1): where, if anywhere, does next-direction |
| `research.config` | config.py — ResearchConfig: the single source of truth for the research harness. |
| `research.contracts` | contracts.py — frozen interfaces for the Edge Discovery Program. |
| `research.controls` | Falsification controls — the platform's immune system. |
| `research.controls.always_long` | always_long.py — the anti-drift control. |
| `research.controls.random_baseline` | random_baseline.py — null controls: random entries. |
| `research.costs` | costs.py — conservative flat cost model for the falsification phase (M1–M6). |
| `research.cross_sectional` | cross_sectional.py — Program 5: cross-sectional relative-value (dispersion) measurement. |
| `research.exit_grid` | exit_grid.py — Phase D pure core: SL/TP exit-geometry grid + the recoverable-value ceilings. |
| `research.forensics` | forensics.py — Layer-6 root-cause analysis: WHY a behavior loses under intrabar truth. |
| `research.hypotheses` | Behavior hypotheses. Importing this package registers each one via its decorator. |
| `research.hypotheses.expansion_breakout` | expansion_breakout.py — continuation behavior (hypothesis #1, NOT privileged). |
| `research.hypotheses.mean_reversion` | mean_reversion.py — the OPPOSITE behavior, shipped at M2 to prove no continuation bias. |
| `research.hypotheses.spine_hypothesis` | spine_hypothesis.py — the production spine, wrapped as a research Hypothesis. |
| `research.indicators` | indicators.py — small, dependency-light technical helpers for hypotheses/controls. |
| `research.measurement` | Measurement core — no-lookahead forward-walk + edge aggregation. |
| `research.measurement.forward_walk` | forward_walk.py — no-lookahead forward simulation of a Signal. |
| `research.measurement.metrics` | metrics.py — EdgeAggregator: turn a list of Outcomes into an EdgeReport. |
| `research.process_characterization` | process_characterization.py — statistical fingerprint of a raw OHLCV series. |
| `research.process_diagnostics` | process_diagnostics.py — significance tests over the Phase-1 process fingerprint. |
| `research.provenance` | provenance.py — versioned realism/method stamps for research artifacts. |
| `research.qualification` | qualification.py — M4 QualificationGate for the Edge Discovery Program. |
| `research.regime_conditioning` | regime_conditioning.py — Program 4 conditioning harness (the only new measurement). |
| `research.registry` | registry.py — hypothesis plugin registry (mirrors src/agent/tool_registry.py). |
| `research.resample` | resample.py — deterministic M15 -> {H1, H4} OHLCV resampler (Program 3 harness). |
| `research.runner` | runner.py — HypothesisRunner: stream CSVs → detect → forward_walk → EdgeReport. |
| `research.selection_effect` | selection_effect.py — Phase S1 pure core: the spine's RETEST selection effect. |
| `research.structural_asymmetry` | structural_asymmetry.py — Program 2 / Phase E1 pure core: forward asymmetry of a structural-event |

### `src/runtime/`

| Module | Role (docstring line 1) |
| --- | --- |
| `runtime` | _(no module docstring)_ |
| `runtime.analyze_fusion_shadow` | Analyze EngineRunner fusion shadow telemetry from collector logs. |
| `runtime.backtest_bitnet` | backtest_bitnet.py |
| `runtime.backtest_v2` | ╔═══════════════════════════════════════════════════════════════════════╗ |
| `runtime.baseline_capture` | baseline_capture.py |
| `runtime.exit_model_band` | exit_model_band.py |
| `runtime.live_engine_hook` | live_engine_hook.py |
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
| `strategies.strategy_result` | strategy_result.py |

### `src/training/`

| Module | Role (docstring line 1) |
| --- | --- |
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
| `utils.engine_telemetry` | engine_telemetry.py |
| `utils.episode_summarizer` | episode_summarizer.py |
| `utils.integrity_events` | integrity_events.py |
| `utils.jsonl_writer` | jsonl_writer.py — the canonical append-only JSONL helper. |
| `utils.llm_logger` | llm_logger.py |
| `utils.log_identity` | log_identity.py |
| `utils.log_index_writer` | log_index_writer.py |
| `utils.logging_config` | Centralized Logging Configuration for Trading System |
| `utils.pattern_hasher` | pattern_hasher.py |
| `utils.registry_refresh` | registry_refresh.py |
| `utils.sweep_trace_logger` | Sweep Trace Logger — Layer 0 of the trace-first repair pipeline. |
| `utils.trade_logger` | trade_logger.py |
| `utils.zone_schema_migrator` | zone_schema_migrator.py |

