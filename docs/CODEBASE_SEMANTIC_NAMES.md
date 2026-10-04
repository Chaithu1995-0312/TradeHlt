# Codebase Semantic Names (LLM Concept Catalog)

## Purpose

Parallel artifact to [`CODEBASE_NAVIGATION.md`](CODEBASE_NAVIGATION.md). Navigation answers **where** to open files; this catalog answers **what/why** — stable semantic handles for coding-LLM reasoning about business/domain responsibility.

## How an LLM should use this with the navigation map

1. Use **CODEBASE_NAVIGATION.md** to locate packages, entry points, and wiring.
2. Use **semantic_name** here as a concept handle when planning edits, tracing responsibility, or comparing modules.
3. Prefer `business_role` over filename when they disagree; filename↔content mismatches are noted in role text.
4. Machine twin: [`CODEBASE_SEMANTIC_NAMES.jsonl`](CODEBASE_SEMANTIC_NAMES.jsonl) (one JSON object per line, full fields).
5. This is a **naming catalog only** — not an L-003 ontology rewrite and not a fabricated API surface.

## Coverage stats

| Slice | Count |
|-------|------:|
| Total entries | 1707 |
| Content-read | 1707 |
| Path-only fallback | 0 |
| `src/` | 597 |
| `scripts/` | 425 |
| `tests/` | 543 |
| `tools/` | 17 |
| `configs/` | 92 |
| docs / root md | 33 |
| Filename↔content mismatches flagged | 68 |

### Entries by area

| area | count |
|------|------:|
| test | 543 |
| research | 458 |
| analytics | 174 |
| runtime | 157 |
| governance | 130 |
| config | 126 |
| script | 48 |
| tools | 37 |
| docs | 33 |
| other | 1 |

Scope note: 100% of inventoried `src/`, `scripts/`, `tests/`, `tools/` (py/js/ts/jsx), selected `configs/`, and architecture/governance markdown. Excluded: `data/`, `logs/`, `results/`, `.venv/`, `node_modules/`, `__pycache__/`, binaries, large JSONL dumps, parquet, png.

## Filename ↔ content mismatches (flagged)

| path | semantic_name | note |
|------|---------------|------|
| `src/agent/state.py` | `ToolCall` | path stem 'state' vs content focus 'ToolCall' |
| `src/config_layer/crt_config_provenance.py` | `ConstructionMode` | path stem 'crt_config_provenance' vs content focus 'ConstructionMode' |
| `src/config_layer/execution_planner.py` | `ExecutionPlannerV12Pure` | path stem 'execution_planner' vs content focus 'ExecutionPlannerV1_2' |
| `src/config_layer/m15_structural_range.py` | `M15StructuralLiquidityRange` | path stem 'm15_structural_range' vs content focus 'M15StructuralLiquidityRange' |
| `src/config_layer/state_identity.py` | `Direction` | path stem 'state_identity' vs content focus 'Direction' |
| `src/control_plane/cp_types.py` | `ControlPlaneRunRecord` | filename suggests cp_types; content centers on RunRecord |
| `src/core/types.py` | `CoreEngineContextCanonicalTypedDict` | path stem 'types' vs content focus 'EngineContext' |
| `src/data_ingestion/xauusd_phase1_candidate.py` | `Phase1CandidateBinding` | path stem 'xauusd_phase1_candidate' vs content focus 'Phase1CandidateBinding' |
| `src/expansion/policy_schema.py` | `ExpansionCandidate` | filename suggests policy_schema; content centers on ExpansionCandidate |
| `src/features/smc/_geometry.py` | `SwingPoint` | path stem '_geometry' vs content focus 'SwingPoint' |
| `src/features/feature_states.py` | `FeaturesStatefulFeatureSemanticPipelineRoadmap` | path stem 'feature_states' vs content focus 'StatefulFeature' |
| `src/features/fm_resolve.py` | `ResolvedFM` | path stem 'fm_resolve' vs content focus 'ResolvedFM' |
| `src/features/magnitude_states.py` | `FeaturesMagnitudeStateEncoderPhaseContinuous` | path stem 'magnitude_states' vs content focus 'MagnitudeStateEncoder' |
| `src/features/market_context.py` | `MarketContextBuilderSemanticPipeline` | path stem 'market_context' vs content focus 'MarketContextBuilder' |
| `src/features/market_shape.py` | `MarketShapeClassifierSemanticPipeline` | path stem 'market_shape' vs content focus 'MarketShapeClassifier' |
| `src/features/model_evidence.py` | `ModelEvidenceBuilderSemanticPipeline` | path stem 'model_evidence' vs content focus 'ModelEvidenceBuilder' |
| `src/governance/jsonl_claim_catalog.py` | `CatalogLoaderAdmissibility` | path stem 'jsonl_claim_catalog' vs content focus 'Catalog' |
| `src/governance/module_attribution.py` | `AttributionRegistryGovernanceSurface` | path stem 'module_attribution' vs content focus 'ModuleAttributionRegistry' |
| `src/governance/module_census.py` | `GovernanceDiscoveredDiscoveryPathStable` | path stem 'module_census' vs content focus 'DiscoveredModule' |
| `src/governance/orchestrator.py` | `GovernanceOrchestratorFullStep` | path stem 'orchestrator' vs content focus 'GovernanceOrchestrator' |
| `src/inout/live_rail/config.py` | `OrderManagerCfg` | path stem 'config' vs content focus 'OrderManagerCfg' |
| `src/inout/live_rail/resilience.py` | `ReconnectPolicy` | path stem 'resilience' vs content focus 'ReconnectPolicy' |
| `src/inout/live_rail/types.py` | `InoutClockBasisEngineRunnerOrders` | path stem 'types' vs content focus 'ClockBasis' |
| `src/interpreters/adapter.py` | `InterpreterHypothesis` | path stem 'adapter' vs content focus 'InterpreterHypothesis' |
| `src/interpreters/point_and_figure.py` | `PointFigureInterpreter` | path stem 'point_and_figure' vs content focus 'PointAndFigureInterpreter' |
| `src/interpreters/reference.py` | `NullInterpreter` | path stem 'reference' vs content focus 'NullInterpreter' |
| `src/journal/schema.py` | `TradeRecord` | filename suggests schema; content centers on TradeRecord |
| `src/journal/trade_execution_link_v1_0.py` | `TradeExecutionLinkV1Transport` | path stem 'trade_execution_link_v1_0' vs content focus 'TradeExecutionLinkV1' |
| `src/llm_research/pattern_extractor.py` | `ExtractedPolicy` | filename suggests pattern_extractor; content centers on ExtractedPolicy |
| `src/msip/interpretation_config.py` | `Disabled` | path stem 'interpretation_config' vs content focus 'Disabled' |
| `src/research/episodes/events.py` | `ResearchEventEngineSparseSemanticMilestones` | path stem 'events' vs content focus 'EventEngine' |
| `src/research/episodes/query.py` | `EpisodeQuerySelectionsEpisodes` | path stem 'query' vs content focus 'EpisodeQuery' |
| `src/research/episodes/schema.py` | `Observation` | path stem 'schema' vs content focus 'Observation' |
| `src/research/episodes/tensors.py` | `ResearchTensorBatchViewsSequenceModels` | path stem 'tensors' vs content focus 'TensorBatch' |
| `src/research/evidence/records.py` | `ResearchEvidenceRecordMeasurementsPredictions` | path stem 'records' vs content focus 'EvidenceRecord' |
| `src/research/ic002_entry_evolution/schema.py` | `TrajectoryBatch` | path stem 'schema' vs content focus 'TrajectoryBatch' |
| `src/research/measurement/metrics.py` | `ResearchEdgeAggregatorTurnListOutcomes` | path stem 'metrics' vs content focus 'EdgeAggregator' |
| `src/research/model_runners/adapters/execution_plan.py` | `ExecutionPlanAdapterFullCandle` | path stem 'execution_plan' vs content focus 'ExecutionPlanAdapter' |
| `src/research/model_runners/adapters/rr_trained.py` | `RRTrainedAdapterObserve` | path stem 'rr_trained' vs content focus 'RRTrainedAdapter' |
| `src/research/model_runners/contracts.py` | `ResearchModelContractAuditModelsPhase` | path stem 'contracts' vs content focus 'ModelContract' |
| `src/research/model_runners/runner.py` | `Run` | path stem 'runner' vs content focus 'RunRequest' |
| `src/research/oracle/labeler.py` | `Bar` | path stem 'labeler' vs content focus 'Bar' |
| `src/research/oracle/scan.py` | `Partition` | path stem 'scan' vs content focus 'Partition' |
| `src/research/path/ambiguity_census.py` | `ResearchP1EventProgramPhase` | path stem 'ambiguity_census' vs content focus 'P1Event' |
| `src/research/rc003_distinct_object/driver.py` | `Bar` | path stem 'driver' vs content focus 'Bar' |
| `src/research/sujan_crt/geometry.py` | `Bar` | path stem 'geometry' vs content focus 'Bar' |
| `src/research/sujan_crt/vetoes.py` | `ResearchSujanCandidateSEMNestedVeto` | path stem 'vetoes' vs content focus 'SujanCandidate' |
| `src/research/sujan_manipulation/geometry.py` | `ManipulationSide` | path stem 'geometry' vs content focus 'ManipulationSide' |
| `src/research/sujan_manipulation/parent.py` | `Bar` | path stem 'parent' vs content focus 'Bar' |
| `src/research/zone_mapping/zone_census.py` | `ResearchBarZoneLabelBaselineDescription` | path stem 'zone_census' vs content focus 'BarZoneLabel' |
| `src/research/contracts.py` | `ResearchHypothesisFrozenInterfacesEdge` | path stem 'contracts' vs content focus 'Hypothesis' |
| `src/research/costs.py` | `ResearchCostModelConservativeFlatFalsification` | path stem 'costs' vs content focus 'CostModel' |
| `src/research/process_characterization.py` | `ProcessManifest` | path stem 'process_characterization' vs content focus 'ProcessManifest' |
| `src/retrieval/corpus.py` | `RetrievalDocumentDiscoveryAcrossRepository` | path stem 'corpus' vs content focus 'Document' |
| `src/training/trainer.py` | `StandardScaler` | path stem 'trainer' vs content focus 'StandardScaler' |
| `src/uat/monte_carlo.py` | `MonteCarloEngineBootstrapResampling` | path stem 'monte_carlo' vs content focus 'MonteCarloEngine' |
| `src/utils/registry_refresh.py` | `RegistryWatcher` | path stem 'registry_refresh' vs content focus 'RegistryWatcher' |
| `src/utils/validation_contract.py` | `SummaryManifestMismatch` | path stem 'validation_contract' vs content focus 'SummaryManifestMismatch' |
| `scripts/governance/feature_dag_certify.py` | `OrderingViolation` | path stem 'feature_dag_certify' vs content focus 'OrderingViolation' |
| `scripts/maintenance/check_consolidation_due.py` | `Signal` | path stem 'check_consolidation_due' vs content focus 'Signal' |
| `scripts/research/crt_parity_classifier.py` | `MismatchContext` | path stem 'crt_parity_classifier' vs content focus 'MismatchContext' |
| `scripts/research/crt_resolver_economic_comparison.py` | `EngineTrade` | path stem 'crt_resolver_economic_comparison' vs content focus 'EngineTrade' |
| `scripts/research/crt_state_confusion_matrix.py` | `EngineTimeline` | path stem 'crt_state_confusion_matrix' vs content focus 'EngineTimeline' |
| `scripts/research/run_h_msip_001.py` | `BarRec` | path stem 'run_h_msip_001' vs content focus 'BarRec' |
| `scripts/research/trace_sweep_geometry.py` | `GeometryStats` | path stem 'trace_sweep_geometry' vs content focus 'GeometryStats' |
| `scripts/research/xauusd_gaussian_econ_ledger.py` | `Bar` | path stem 'xauusd_gaussian_econ_ledger' vs content focus 'Bar' |
| `scripts/training/auto_tuner_multi.py` | `Result` | path stem 'auto_tuner_multi' vs content focus 'ResultStore' |
| `tools/tv_forensic/annotate.py` | `Frame` | path stem 'annotate' vs content focus 'Frame' |

## Area: `runtime` (157)

### `scripts/backtest/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/backtest/backtest_debug_harness.py` | `BacktestDebugHarness` | Module at scripts/backtest/backtest_debug_harness.py. |
| `scripts/backtest/manual_backtest.py` | `DynamicThreshold` | Manual Backtest Runs the full CRT pipeline on any M15 CSV exactly per the spec: - ATR(14), HTF=16, sweep_age≤30, displacement 1.2×ATR / body≥0.70 / wick≥1.5×ATR - Expansion guar... |

### `scripts/live/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/live/run_live_rail.py` | `LiveRailPaperCliEntrypoint` | Thin CLI for paper live-rail arms (tickdb/bars/file) with zero broker network. |

### `src/core/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/core/__init__.py` | `CoreApi` | Decision spine: EngineRunner, FusionEngine, DecisionEngine, UltronRiskGate, Collector. |
| `src/core/acceptance_controller.py` | `AcceptanceControllerAdaptiveSystem` | Adaptive Acceptance Control System. |
| `src/core/backtest_port.py` | `BacktestPortTrdDependency` | Trd-M4 dependency-inversion port. |
| `src/core/collector.py` | `CollectorStoresStructured` | Stores structured records to logs/collector.jsonl. |
| `src/core/convergence_controller.py` | `ConvergenceControllerFusionEngine` | Convergence Layer for FusionEngine. |
| `src/core/decision_engine.py` | `CentralExecuteRejectAuthority` | Sole semantic authority that answers execute-vs-reject for a market opportunity. |
| `src/core/dynamic_threshold.py` | `DynamicThresholdPercentileBased` | Percentile-based adaptive threshold for the CRT decision engine. |
| `src/core/engine_runner.py` | `FourEnginePipelineOrchestrator` | Strict pipeline orchestrator: adapter gate then CRT/Gaussian/BitNet/RR completeness before fusion. |
| `src/core/feature_store.py` | `CanonicalFeatureStore` | Canonical feature store / single source for feature vectors consumed by engines. |
| `src/core/fusion_engine.py` | `MultiEngineScoreFusion` | Fuses multi-engine scores into a single decision-facing evidence vector. |
| `src/core/gate_intelligence.py` | `GateIntelligencePureSignal` | Pure signal gate for ExecutionPlanner. |
| `src/core/governance_mode.py` | `CoreTrdLLMHardeningGOVERNANCEMODE` | Trd-M5 LLM-layer hardening: the GOVERNANCE_MODE switch. |
| `src/core/hierarchical_meta_fusion.py` | `HierarchicalMetaFusionCapitalAllocation` | 6-layer hierarchical meta-fusion for capital allocation quality scoring. |
| `src/core/model_registry.py` | `ActiveModelRegistry` | Resolves and pins active model artifacts for runtime engines. |
| `src/core/regime_governor.py` | `UltronRegimeGovernor` | Ultron regime governor wrapping risk/regime controls around engine outputs. |
| `src/core/signal_audit.py` | `SignalAuditRecorderBarLeak` | Per-bar Signal Audit + Leak Detection. |
| `src/core/signal_belief_tracker.py` | `BeliefRegistry` | Temporal belief accumulator that gates DecisionEngine calls. |
| `src/core/types.py` | `CoreEngineContextCanonicalTypedDict` | Canonical TypedDict contracts for the execution spine (note: path stem 'types' vs content focus 'EngineContext'). |
| `src/core/ultron_live_adapter.py` | `UltronLiveAdapterPortfolioAround` | Live portfolio adapter around UltronRiskGate. |
| `src/core/ultron_risk_gate.py` | `UltronRiskGate` | Ultron risk gate enforcing hard risk constraints before execution. |
| `src/core/ultron_risk_gate_wrapper.py` | `UltronRiskGateCoreUltronRisk` | UltronRiskGateWrapper. |

### `src/engines/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/engines/__init__.py` | `EnginesApi` | Scoring engines (CRT, Gaussian, Zone-Gate, RR) plus the trap-validation gate. |
| `src/engines/crt_engine.py` | `CrtScoringEngine` | CRT strategy scoring engine consuming resolved CRT state and local math knobs. |
| `src/engines/gaussian_engine.py` | `GaussianSignalEngine` | Gaussian primary-signal scoring engine. |
| `src/engines/heuristic_gaussian_engine.py` | `HeuristicGaussianEngineProbabilityScoring` | Heuristic Gaussian probability scoring using EMA/momentum kernel. |
| `src/engines/live_engine.py` | `LiveDecisionTelegramAlertEngine` | Human-in-the-loop live decision and Telegram alert surface; no broker auto-orders. |
| `src/engines/llm_engine.py` | `EnginesCallsLLMScoreSafeLLM` | calls llm_score_safe() from llm_scorer.py. |
| `src/engines/ml_gaussian_engine.py` | `MLGaussianEngineBasedTrained` | ML-based Gaussian engine using a trained GaussianNBModel (32-dim). |
| `src/engines/rr_engine.py` | `RiskRewardScoringEngine` | Risk/reward scoring engine for opportunity quality. |
| `src/engines/scoring_engine.py` | `ScoringEngineEngines` | Defines ScoringEngine; exposes compute_scores, compute_gaussian_score. |
| `src/engines/tradenet_meta_engine.py` | `TradeNetMetaEngine` | TradeNet meta-engine aggregating model scores. |
| `src/engines/trap_validator_engine.py` | `TrapValidatorEngineDataIntegrity` | data integrity validator and pre-gating layer. |
| `src/engines/zone_cluster_score.py` | `EnginesPureZoneClusterScoringShared` | pure zone cluster scoring shared by EngineRunner and HistoricalZoneMapper. |
| `src/engines/zone_gate_engine.py` | `ZoneGateEngine` | Zone-gate engine filtering opportunities by zone membership. |

### `src/events/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/events/__init__.py` | `EventsApi` | Module at src/events/__init__.py. |
| `src/events/event_fabric.py` | `EventsCanonicalEventFabricTradelatestRuntime` | Canonical Event Fabric for the Tradelatest runtime. |

### `src/execution/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/execution/__init__.py` | `ExecutionApi` | Module at src/execution/__init__.py. |
| `src/execution/alert_manager.py` | `ExecutionAlertManager` | Manages execution-time alerts derived from intents and fills. |
| `src/execution/execution_intent_v1_0.py` | `ExecutionIntentV1Contract` | v1.0 execution intent schema/contract for downstream executors. |
| `src/execution/loop.py` | `ExecutionLoopDriver` | Execution loop that consumes intents and drives alert/order side effects. |
| `src/execution/override_handler.py` | `OverrideHandlerExecution` | Defines OverrideHandler. |

### `src/features/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/features/__init__.py` | `FeaturesApi` | Module at src/features/__init__.py. |
| `src/features/broker_clock.py` | `FeaturesConvertsMT5BrokerTimestamps` | converts MT5 broker-server timestamps to true UTC. |
| `src/features/calendar_periods.py` | `FeaturesISOWeekMN1Calendar` | W1 (ISO week) and MN1 (calendar month) parent-candle aggregation. |
| `src/features/candle_math.py` | `FeaturesImmutableCandleMath` | the single, immutable source of truth for candle math. |
| `src/features/causal_structure.py` | `FeaturesFC1DelayedConfirmedStructure` | FC1-A delayed-confirmed structure publication helpers. |
| `src/features/crt_feature_builder.py` | `CrtFeatureBuilder` | Builds CRT-specific features from resolved state and OHLCV context. |
| `src/features/crt_state_resolver.py` | `CrtStateMachineResolver` | Resolves CRT mother/break/retest state transitions from bar and range evidence. |
| `src/features/dataset_builder.py` | `FeaturesDatasetBuilderValidateFeatures` | exposes validate_features, extract_feature_vector, extract_bitnet_features, build_dataset_entry. |
| `src/features/dataset_validator.py` | `ValidationReport` | Validates fusion trade logs before any dataset build or model training. |
| `src/features/derived_math.py` | `FeaturesImmutableScalarNORMALIZEDFeatureMathematics` | the immutable scalar source of truth for deterministic NORMALIZED feature mathematics (ATR/price-relative quantities). |
| `src/features/feature_builder.py` | `FeatureBuilderConstructsCanonical` | constructs the canonical input_data dict from raw tick/row data. |
| `src/features/feature_identity.py` | `FeatureIdentityFailClosed` | fail-closed lookup by feature_id. |
| `src/features/feature_monitor.py` | `FeatureMonitorDriftDistribution` | Feature Drift + Distribution Tracking Layer. |
| `src/features/feature_pipeline.py` | `CanonicalM15FeatureVectorBuilder` | Deterministic M15 OHLCV feature pipeline emitting CANONICAL_FEATURE_DIM vectors. |
| `src/features/feature_schema.py` | `FeatureSchemaRegistry` | Defines SchemaObject, SchemaVersionError, FeatureSchemaRegistry; exposes schema_for_model, assert_schema_version, encode_session_ordinal, validate_vector. |
| `src/features/feature_states.py` | `FeaturesStatefulFeatureSemanticPipelineRoadmap` | Layer 2 of the semantic pipeline (roadmap Phase 2C) (note: path stem 'feature_states' vs content focus 'StatefulFeature'). |
| `src/features/fm_resolve.py` | `ResolvedFM` | FM id → callable via ontology + FORMULA_REGISTRY (note: path stem 'fm_resolve' vs content focus 'ResolvedFM'). |
| `src/features/formula_registry.py` | `FormulaRegistry` | Registry of named formulas used by feature construction. |
| `src/features/gaussian_schema_contract.py` | `FeaturesGaussianFeatureSchemaContractSCHEMA` | Gaussian NB feature-schema contract under SCHEMA-V4-VECTOR-MIGRATION (P0). |
| `src/features/magnitude_states.py` | `FeaturesMagnitudeStateEncoderPhaseContinuous` | Phase 2A continuous VALUE → discrete STATE (shadow only) (note: path stem 'magnitude_states' vs content focus 'MagnitudeStateEncoder'). |
| `src/features/market_context.py` | `MarketContextBuilderSemanticPipeline` | Layer 4 of the semantic pipeline (roadmap Phase 3) (note: path stem 'market_context' vs content focus 'MarketContextBuilder'). |
| `src/features/market_reality_contract.py` | `MarketRealityContractReadLoader` | read-only loader/validator for `configs/market_reality/market_reality_v1.yaml`. |
| `src/features/market_shape.py` | `MarketShapeClassifierSemanticPipeline` | Layer 5 of the semantic pipeline (roadmap Phase 5) (note: path stem 'market_shape' vs content focus 'MarketShapeClassifier'). |
| `src/features/model_evidence.py` | `ModelEvidenceBuilderSemanticPipeline` | Layer 7 of the semantic pipeline (note: path stem 'model_evidence' vs content focus 'ModelEvidenceBuilder'). |
| `src/features/parent_candle.py` | `ParentCandleBuilderHtfcrtSmc` | CH-htfcrt-parent-candle-smc-v1: real, calendar-true HTF parent candles. |
| `src/features/registry/__init__.py` | `FeaturesRegistryApi` | the AUTHORITATIVE source of feature-mathematics implementation. |
| `src/features/registry/_loader.py` | `FeaturesLeafIntraDepsRegistrySubmodules` | leaf module (no intra-package deps) so registry submodules can share it without import cycles. |
| `src/features/registry/composition_registry.py` | `FeaturesTradingInterpretationRatiosNumeratorDenominator` | trading-interpretation ratios (numerator/denominator over primitives). |
| `src/features/registry/derived_registry.py` | `FeaturesNormalizedMetricsATRPriceRelative` | deterministic normalized metrics (ATR/price-relative). |
| `src/features/registry/predicate_registry.py` | `FeaturesGovernedInterpreterStructuralPredicatesDefinitions` | the governed interpreter for `structural_predicates` definitions. |
| `src/features/registry/primitive_registry.py` | `FeaturesOHLCIdentity` | the OHLC-identity layer. |
| `src/features/resolver_supply.py` | `SupplyPlan` | The ONE way a caller feeds ``CRTStateResolver.resolve()``. |
| `src/features/schema_validator.py` | `FeaturesSTRICTFAILFASTValidatorCanonical` | STRICT FAIL-FAST validator for the canonical feature contract. |
| `src/features/session_classifier.py` | `SessionOrdinal` | THE single owner of "what session is this?". |
| `src/features/smc/__init__.py` | `FeaturesSmcApi` | CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the 9 SMC (smart-money-concepts) primitives absent from the codebase before this program (order block, fair value g... |
| `src/features/smc/_geometry.py` | `SwingPoint` | shared, pure helpers for the SMC primitive modules (note: path stem '_geometry' vs content focus 'SwingPoint'). |
| `src/features/smc/breaker.py` | `FeaturesBreakerBlockDetection` | Breaker Block detection. |
| `src/features/smc/choch.py` | `FeaturesChangeCharacterCHoCH` | Change of Character (CHoCH). |
| `src/features/smc/fvg.py` | `FeaturesFairValueGapFVGImbalance` | Fair Value Gap (FVG) / imbalance detection. |
| `src/features/smc/levels.py` | `FeaturesPreviousDayHighLowPDH` | Previous-Day High/Low (PDH/PDL) and Equal Highs/Lows (EQH/EQL). |
| `src/features/smc/mitigation.py` | `FeaturesMitigationBlock` | Mitigation Block. |
| `src/features/smc/order_block.py` | `FeaturesOrderBlockDetection` | Order Block (OB) detection. |

### `src/feedback/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/feedback/__init__.py` | `FeedbackApi` | Module at src/feedback/__init__.py. |
| `src/feedback/ai_feedback.py` | `AIFeedback` | Defines AIFeedback. |

### `src/inout/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/inout/alphavantage_candle_fetcher.py` | `InoutAlphaVantageFetcherConfigAlpha` | AlphaVantageCandleFetcher Fetches historical FX OHLCV candles from Alpha Vantage's FX_INTRADAY endpoint and writes CSV files directly consumable by Tradelatest's CandleLoader. |
| `src/inout/hummingbot_candle_fetcher.py` | `InoutHummingbotFetcherConfigHummingbotCandle` | HummingbotCandleFetcher Fetches historical OHLCV candles from any hummingbot-supported exchange (Binance, Bybit, OKX, KuCoin, Gate.io, etc.) and writes CSV files that are direct... |
| `src/inout/live_rail/__init__.py` | `InoutLiveRailApi` | no HookedLiveEngine caller, no orders. |
| `src/inout/live_rail/bar_builder.py` | `BarBuilderAggregateTicks` | Aggregate ticks into 6-col Candle + optional spread extras. |
| `src/inout/live_rail/binance_ws_adapter.py` | `BinanceWsAdapterCombinedStream` | Binance combined-stream paper-data. |
| `src/inout/live_rail/config.py` | `OrderManagerCfg` | no silent defaults (note: path stem 'config' vs content focus 'OrderManagerCfg'). |
| `src/inout/live_rail/factory.py` | `InoutVenuePortFactory` | Venue port factory. |
| `src/inout/live_rail/longport_adapter.py` | `LongPortAdapterPretendSDK` | do not pretend an SDK is wired. |
| `src/inout/live_rail/ohlcv_replay_port.py` | `OhlcvTickReplayPort` | Deterministic historical replay source for live-rail certification. |
| `src/inout/live_rail/resilience.py` | `ReconnectPolicy` | Reconnect backoff + fail-closed circuit breaker for live-rail I/O (note: path stem 'resilience' vs content focus 'ReconnectPolicy'). |
| `src/inout/live_rail/tickdb_adapter.py` | `TickDBAdapterBackedJsonl` | File-backed JSONL tick replay. |
| `src/inout/live_rail/types.py` | `InoutClockBasisEngineRunnerOrders` | no EngineRunner, no orders (note: path stem 'types' vs content focus 'ClockBasis'). |
| `src/inout/mt5_candle_fetcher.py` | `Mt5CandleFetcher` | Fetches OHLCV candles from MT5 for ingestion/runtime. |
| `src/inout/perp_funding_fetcher.py` | `InoutPerpFetcherConfigPerpFunding` | PerpFundingFetcher Acquires Binance USDⓈ-M **perpetual** carry/basis inputs and writes CSV files time-aligned to the existing Binance **spot** OHLCV in ``data/``:. |

### `src/live/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/live/__init__.py` | `LiveApi` | Module at src/live/__init__.py. |
| `src/live/mt5_bridge.py` | `Mt5BrokerBridgeAdapter` | MT5 connectivity bridge for market data and order intent plumbing. |
| `src/live/order_manager.py` | `LiveOrderLifecycleManager` | Tracks live order lifecycle state separately from semantic opportunity judgment. |
| `src/live/telegram_bridge.py` | `TelegramAlertTransportBridge` | Outbound Telegram transport for human-facing trade alerts. |

### `src/monitoring/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/monitoring/__init__.py` | `MonitoringApi` | Module at src/monitoring/__init__.py. |
| `src/monitoring/health_checker.py` | `HealthCheckerLightweightStdlib` | lightweight stdlib HTTP health endpoint on port 8788. |

### `src/portfolio/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/portfolio/__init__.py` | `PortfolioApi` | Module at src/portfolio/__init__.py. |
| `src/portfolio/allocator.py` | `PortfolioAllocator` | Portfolio allocation logic across symbols/strategies. |
| `src/portfolio/capital_policy.py` | `CapitalPolicyPortfolio` | Defines CapitalPolicy. |
| `src/portfolio/correlation_engine.py` | `PortfolioCorrelationEngine` | Correlation engine for portfolio exposure decisions. |
| `src/portfolio/exposure_tracker.py` | `PortfolioExposureTracker` | Tracks live/historical portfolio exposure. |
| `src/portfolio/replay.py` | `PortfolioReadShadowReplayPortfolioAllocator` | read-only shadow replay of PortfolioAllocator over a historical trade ledger. |

### `src/regime/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/regime/__init__.py` | `RegimeApi` | Module at src/regime/__init__.py. |
| `src/regime/config_router.py` | `RegimeConfigRouter` | Routes production/research config by detected regime. |
| `src/regime/market_state_cluster_engine.py` | `MarketStateClusterEngineNativeClassification` | Cluster-native market state classification. |
| `src/regime/regime_classifier.py` | `RegimeClassifier` | Classifies market regime for config routing. |

### `src/replay/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/replay/__init__.py` | `ReplayApi` | Module at src/replay/__init__.py. |
| `src/replay/replay_drift_governor.py` | `ReplayDriftGovernorMonitorsMemory` | Monitors replay memory for contamination, staleness, cluster drift, and anti-collapse signals. |
| `src/replay/replay_memory_engine.py` | `ReplayMemoryEngine` | Replay memory engine for historical pattern recall. |
| `src/replay/replay_similarity_index.py` | `ReplaySimilarityIndexSearchVectors` | Similarity search index for replay vectors. |
| `src/replay/timing_advisor.py` | `ReplayTimingAdvisor` | Timing advisor derived from replay memory. |
| `src/replay/timing_reconstructor.py` | `ReplayForwardWalkAugmentsOpportunityTrade` | Deterministic forward-walk that augments the opportunity/trade outcome simulation with first-crossing TIMING for favorable R-levels. |

### `src/runtime/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/runtime/__init__.py` | `RuntimeApi` | Module at src/runtime/__init__.py. |
| `src/runtime/analyze_fusion_shadow.py` | `RuntimeAnalyzeEngineRunnerFusionShadow` | Analyze EngineRunner fusion shadow telemetry from collector logs. |
| `src/runtime/backtest_bitnet.py` | `RuntimeRowBacktestRunnerBitNet` | Row-by-row backtest runner with BitNet as HARD GATEKEEPER. |
| `src/runtime/backtest_v2.py` | `BacktestV2Harness` | V2 backtest harness driving historical replay through the decision pipeline. |
| `src/runtime/bar_structure_snapshot.py` | `BarStructureEmitter` | the v3 `BarStructureSnapshot`: one observation-only record per bar. |
| `src/runtime/baseline_capture.py` | `RuntimeCaptureReproducibleBaselineManifestCurrent` | Capture a reproducible baseline manifest for the current repository state. |
| `src/runtime/crt_baseline_trace.py` | `CrtBaselineTraceEmitter` | Emits CRT baseline traces for parity and forensic comparison. |
| `src/runtime/crt_construction_trace.py` | `ConstructionTraceEmitter` | the v4 `CRTConstructionTrace`: engine vs ontology, per bar. |
| `src/runtime/crt_fail_reason_counters.py` | `RuntimeCRTFailReasonCountersOBSERVATION` | OBSERVATION_ONLY. |
| `src/runtime/exit_model_band.py` | `RuntimeDualBoundExitModelReport` | [trust-layer F2, 2026-06-10] Dual-bound exit-model report. |
| `src/runtime/live_engine_hook.py` | `HookedLiveEngine` | does NOT modify live_engine.py. |
| `src/runtime/live_rail_feeder.py` | `LiveRailBarFeeder` | Feeds closed bars / ticks into the live-rail processing path. |
| `src/runtime/live_rail_orchestrator.py` | `PaperLiveRailDrainOrchestrator` | Paper-only live-rail orchestrator that drains TickDB/bars into HookedLiveEngine.process. |
| `src/runtime/parent_crt_feed.py` | `ParentCRTFeedStreamingAdapter` | streaming adapter that closes F-075's caller gap. |
| `src/runtime/unified_replay_harness.py` | `UnifiedReplayHarness` | Unified replay harness for cross-engine historical parity runs. |

### `src/strategies/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/strategies/__init__.py` | `StrategiesApi` | all 10 strategy modules (S1..S10) + orchestrator. |
| `src/strategies/base_strategy.py` | `BaseStrategyInterface` | Base strategy interface for S01–S10 wrappers. |
| `src/strategies/intent_builder.py` | `StrategyIntentBuilderCentralAdapter` | central adapter that converts any StrategyResult into a StrategyIntent without modifying individual strategy files. |
| `src/strategies/s01_crt_wrapper.py` | `S01CRTStrategy` | CRT Strategy Wrapper. |
| `src/strategies/s02_mean_reversion.py` | `S02MeanReversionStrategy` | Mean Reversion Strategy. |
| `src/strategies/s03_breakout.py` | `S03BreakoutStrategy` | Breakout Strategy. |
| `src/strategies/s04_stat_arb.py` | `S04StatArbStatisticalArbitrage` | Statistical Arbitrage (EMA-Spread Z-Score). |
| `src/strategies/s05_grid.py` | `S05GridStrategy` | Grid Strategy. |
| `src/strategies/s06_scalping.py` | `S06ScalpingStrategyMACD` | Scalping Strategy (MACD + Momentum, session-filtered). |
| `src/strategies/s07_news_sentiment.py` | `S07NewsSentimentFilterTrend` | News / Sentiment Filter + Trend Follower. |
| `src/strategies/s08_ml_ensemble.py` | `S08MLEnsembleStrategyBit` | ML Ensemble Strategy (BitNet + Feature-Weighted Scorer). |
| `src/strategies/s09_pattern_recog.py` | `S09PatternRecogRecognitionStrategy` | Pattern Recognition Strategy. |
| `src/strategies/s10_trap_strategy.py` | `S10TrapStrategyCOREFOCUS` | Trap Strategy (CORE FOCUS). |
| `src/strategies/strategy_intent.py` | `InvalidationRule` | typed hypothesis contract produced by StrategyIntentBuilder for every non-NO_TRADE StrategyResult. |
| `src/strategies/strategy_orchestrator.py` | `StrategyOrchestrator` | Orchestrates registered strategies into a coordinated decision surface. |
| `src/strategies/strategy_package.py` | `StrategyTargetArchitecture` | target-strategy-architecture.md §8 Strategy Registry, the versioned view over "what we trade with": feature use + thresholds + model pins + risk + provenance. |
| `src/strategies/strategy_registry.py` | `StrategyIdRegistry` | Registers S01–S10 strategy wrappers and resolves strategy IDs to callables. |
| `src/strategies/strategy_result.py` | `StrategiesUniversalOutputContractStrategyModules` | universal output contract for all 10 strategy modules. |

## Area: `analytics` (174)

### `scripts/analysis/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/analysis/all_states_economic_probe.py` | `AnalysisGeneralizesSWEEPEconomicProbeEvery` | generalizes the SWEEP economic probe to every state-entry decision type with real full-corpus population. |
| `scripts/analysis/all_states_persistence_probe.py` | `AnalysisGeneralizesStillDwellingEveryState` | generalizes still_dwelling to every state-entry decision. |
| `scripts/analysis/analytics_evidence_class_census.py` | `AnalysisRegistryRowMechanicalEvidenceCensus` | EC-001: mechanical evidence-class census for analytics lineage rows. |
| `scripts/analysis/b2a_feature_candidate_certification.py` | `AnalysisB2CandidateFormulaCERTIFICATION` | B2A: candidate-formula CERTIFICATION for FM-030 `ema_spread_atr` and FM-031 `momentum_score_atr` (READ-ONLY, observe-only). |
| `scripts/analysis/behavior_census.py` | `AnalysisCONFIGFIRSTAUDITReadInventory` | CONFIG-FIRST AUDIT (read-only): inventory the BEHAVIORAL magic numbers still living as code literals in the live-spine source, and classify every module/class-level numeric cons... |
| `scripts/analysis/blind_label_rasterize.py` | `AnalysisRendersIndividualBlindLabelStimulus` | Renders individual blind-label stimulus SVGs from `results/blind_label/session_01.html` to PNG. |
| `scripts/analysis/blind_label_sample.py` | `AnalysisReadSAMPLERRENDERERBlindLabeling` | Read-only SAMPLER + RENDERER for the blind-labeling descriptive-fidelity test. |
| `scripts/analysis/blind_label_score.py` | `AnalysisReadSCORERBlindLabelingDescriptive` | Read-only SCORER for the blind-labeling descriptive-fidelity test. |
| `scripts/analysis/bnb_ema_gate_ab.py` | `AnalysisMEASUREDoesIsolatingEMADirectional` | MEASURE-ONLY A/B: does isolating the EMA directional gate help or hurt BNBUSDT under the GOVERNING intrabar exit model?. |
| `scripts/analysis/bnbusdt_trade_anatomy.py` | `AnalysisMEASURETradeAnatomySubstrateBNBUSDT` | MEASURE-ONLY trade-anatomy substrate for BNBUSDT. |
| `scripts/analysis/build_crt_input_authority_matrix.py` | `AnalysisCRTINPUTAUTHORITYMATRIXCRT` | Build CRT_INPUT_AUTHORITY_MATRIX_V1 + CRT_TRANSITION_COVERAGE_MATRIX_V1 from executable instrumentation evidence + code-declared guard surfaces. |
| `scripts/analysis/build_decision_atlas.py` | `AnalysisTransitionGrainedWarehouseDualConstruction` | transition-grained warehouse over the dual-construction streams. |
| `scripts/analysis/build_feature_contract_v1_seed.py` | `AnalysisSeedFeatureContractInstance` | Seed FeatureContract v1 instance (FC-0). |
| `scripts/analysis/build_pattern_library.py` | `AnalysisAggregatorPhaseMeasure` | aggregator (Phase 1b, measure-only). |
| `scripts/analysis/build_sweep_liquidity_fact.py` | `AnalysisLiquiditySMCContextJoinedOnto` | liquidity/SMC context joined onto SWEEP decisions. |
| `scripts/analysis/codebase_wiring_analysis.py` | `AnalysisAnalyzeGraphDotImportGraph` | Analyze graph.dot (module import graph) to extract architecture insights: - Dependency statistics per package - Cyclic dependency detection - Module centrality (most depended-on... |
| `scripts/analysis/compare_bitnet_cpp_python.py` | `AnalysisCompareBitnetCppClose` | exposes close. |
| `scripts/analysis/compare_guard_ablation_datasets.py` | `AnalysisCompareCRTGUARDABLATIONRankings` | Compare CRT_GUARD_ABLATION_V1 rankings across datasets. |
| `scripts/analysis/compress_logs_for_llm.py` | `AnalysisCompressOneOpportunityFusionJsonl` | Compress one or more opportunity / fusion JSONL logs into a token-efficient summary suitable for LLM review (governance orchestrator, hypertuning prompts). |
| `scripts/analysis/config_reachability.py` | `AnalysisClassifyEveryTunableKeyCodebase` | classify every tunable key by how the codebase actually consumes it. |
| `scripts/analysis/consensus_sweep.py` | `AnalysisFusionConsensusGateSensitivitySweep` | Fusion consensus gate sensitivity sweep (MEASURE-ONLY). |
| `scripts/analysis/crt_config_completeness_census.py` | `AnalysisREADAppliesPhaseCompletenessCheck` | READ-ONLY: applies the Phase C completeness check (src/config_layer/crt_config_completeness.py) to every file under configs/production/*.json, not just the active one. |
| `scripts/analysis/crt_declare_all_knobs_parity.py` | `AnalysisPhaseCRTPlanSession` | Phase B of the "CRT single source of truth" plan (2026-08-31 session). |
| `scripts/analysis/crt_episode_number_trace.py` | `ExecutionLogCapture` | Per-episode, named-value walkthrough of a CRT setup:. |
| `scripts/analysis/crt_fail_reason_diagnostic.py` | `AnalysisOBSERVATION` | OBSERVATION_ONLY. |
| `scripts/analysis/crt_funnel_diagnostic.py` | `AnalysisMEASUREThresholdCRTRedesign` | MEASURE ONLY (no threshold / CRT redesign). |
| `scripts/analysis/crt_guard_ablation_6m.py` | `AnalysisEpisodeLevelOnePredicateCounterfactual` | Episode-level one-predicate counterfactual ablations on the 6-month RB1 window. |
| `scripts/analysis/crt_guard_ablation_run.py` | `AnalysisParameterizedCRTGuardAblationProtocol` | Parameterized CRT guard ablation (identical protocol to 6m XAUUSD baseline). |
| `scripts/analysis/crt_local_math_authority_probe.py` | `AnalysisOBSERVATIONProbeSupportingCRTMATH` | OBSERVATION_ONLY probe supporting CRT_LOCAL_MATH_AUTHORITY_RESOLUTION_V1. |
| `scripts/analysis/crt_predicate_failure_census_6m.py` | `EdgeCensus` | Predicate-level failure census for CRT transitions on the 6-month RB1 window. |
| `scripts/analysis/crt_state_transition_audit_4m.py` | `AnalysisReadCRTStateTransitionAudit` | Read-only CRT state-transition audit for the 4-month XAUUSD window. |
| `scripts/analysis/crt_threshold_authority_census.py` | `AnalysisREADCensusEverySupplyCRT` | READ-ONLY census of every source that can supply a CRTConfig field's value, and what the real production resolver actually resolves it to. |
| `scripts/analysis/crt_xauusd_runtime_trace.py` | `AnalysisObservationalCRTOUTRuntimeTrace` | Observational CRT IN/OUT runtime trace for XAUUSD (canonical backtest path). |
| `scripts/analysis/daily_crypto_structure.py` | `AnalysisDailyMarketStructureAnalysisCrypto` | Daily market structure analysis for crypto (BTC/ETH) using opportunity logs. |
| `scripts/analysis/detection_sweep.py` | `AnalysisCRTDetectionSupplySweepMEASURE` | CRT detection-supply sweep (MEASURE-ONLY, attributed). |
| `scripts/analysis/early_invalidation_ab.py` | `AnalysisSignalLevelTimingBasedEARLY` | Signal-level A/B for the timing-based EARLY-INVALIDATION rule (Consumer A). |
| `scripts/analysis/early_invalidation_exectrade_ab.py` | `AnalysisOFFLINEDirectEffectMethodSpine` | OFFLINE direct-effect method (NO spine change). |
| `scripts/analysis/exit_model_band.py` | `AnalysisDualBoundExitModelReport` | [trust-layer F2] dual-bound exit-model report (thin CLI). |
| `scripts/analysis/export_xauusd_window.py` | `AnalysisExportTrailingWindowXAUUSDM` | export a trailing window of XAUUSD M15 candles to .xlsx. |
| `scripts/analysis/f048_decision_probe.py` | `AnalysisOBSERVATIONEmpiricalMeasurementDecision` | OBSERVATION-ONLY empirical measurement for the F-048 decision. |
| `scripts/analysis/feature_38_lineage_census.py` | `AnalysisCanonicalFeatureLineageCensusOHLCV` | Canonical-feature lineage census: OHLCV → formula → implementation → PIT → consumers. |
| `scripts/analysis/feature_dag_layers.py` | `AnalysisTopologicalFeatureDAGSemanticAssignment` | the authoritative topological feature-DAG + semantic layer assignment (READ-ONLY). |
| `scripts/analysis/feature_dag_rolling_certification.py` | `AnalysisSERIESLevelCertificationFirstRolling` | SERIES-level certification of the first-class rolling indicators FM-040..FM-046 (READ-ONLY). |
| `scripts/analysis/feature_dag_structural_certification.py` | `AnalysisSwingStructuralFamilyCertificationREAD` | L3 swing-structural family certification (READ-ONLY). |
| `scripts/analysis/feature_math_decision_flip_probe.py` | `AnalysisGateStepREAD` | Gate-2 Step 7c (READ-ONLY). |
| `scripts/analysis/feature_math_drift_probe.py` | `AnalysisGateDifferentialProbeREAD` | Gate-2 differential probe (READ-ONLY). |
| `scripts/analysis/feature_math_lint.py` | `AnalysisFEATUREMATHOWNERSHIPLINTRead` | FEATURE-MATH OWNERSHIP LINT (read-only): enforce that governed feature quantities may only ORIGINATE from registered implementations. |
| `scripts/analysis/feature_pipeline_fc05_closure.py` | `AnalysisSemanticClosureGateRead` | FC-0.5 Semantic Closure Gate (read-only). |
| `scripts/analysis/feature_semantic_adjudication_pass_a.py` | `AnalysisPASSRead` | PASS A (read-only). |
| `scripts/analysis/feature_surface_closure_audit.py` | `AnalysisFeatureSurfaceClosureAuditRead` | Feature Surface Closure Audit (read-only). |
| `scripts/analysis/feature_trace_report.py` | `AnalysisBarExplainabilityTraceRealXAUUSD` | Deterministic, per-bar explainability trace over the real XAUUSD M15 feature pipeline. |
| `scripts/analysis/fm021_retest_depth_certification.py` | `AnalysisRetestDepthGATEDProductionComposition` | retest_depth GATED production composition certification probe. |
| `scripts/analysis/fm027_displacement_retrace_certification.py` | `AnalysisDisplacementRetraceCertificationProbe` | FM-027 displacement_retrace independent certification probe. |
| `scripts/analysis/funnel_diagnosis.py` | `AnalysisCRTDetectionFunnelDiagnosisMEASURE` | CRT detection-funnel diagnosis (MEASURE-ONLY). |
| `scripts/analysis/funnel_xauusd_4m.py` | `AnalysisReadStageFunnelMonthXAUUSD` | Read-only stage funnel for the 4-month XAUUSD window search run. |
| `scripts/analysis/gate2b_adjudication.py` | `AnalysisFULLGATESemanticAdjudicationFrozen` | F-049 FULL GATE 2B semantic adjudication over the frozen Census-v3 surface. |
| `scripts/analysis/gate_contribution_audit.py` | `AnalysisStudyCRTFunnelStageCREATES` | Study 2: which CRT funnel stage CREATES vs DESTROYS edge?. |
| `scripts/analysis/gd004_disp_rescale_probe.py` | `AnalysisIdentityClosureCharacterizationProbeREAD` | GD-004 identity-closure characterization probe (READ-ONLY). |
| `scripts/analysis/gen_citation_map.py` | `AnalysisReverseMapSymbolCite` | Reverse map: code symbol -> the docs that cite it. |
| `scripts/analysis/gen_code_map.py` | `AnalysisLevelImportDependencyGraphTradelatest` | Module-level import-dependency graph for the Tradelatest `src/` tree. |
| `scripts/analysis/gen_dummy_trades.py` | `AnalysisGenerateDummyTradeCSVOHLCV` | Generate a dummy trade CSV from OHLCV data that includes all 32 canonical features. |
| `scripts/analysis/gen_flow_graphs.py` | `AnalysisFlowScopedDependencyGraphSlices` | Flow-scoped dependency-graph slices for the Tradelatest `src/` tree. |
| `scripts/analysis/gen_html_explorer.py` | `AnalysisGenerateInteractiveHTMLExplorerCodebase` | Generate an interactive HTML explorer for the codebase wiring analysis. |
| `scripts/analysis/gen_pyan.py` | `AnalysisGenPyan` | Module at scripts/analysis/gen_pyan.py. |
| `scripts/analysis/generate_cli_matrix.py` | `AnalysisGenerateMatrixMain` | exposes main. |
| `scripts/analysis/generate_script_matrix.py` | `AnalysisGenerateReferenceMatrixRegistrySITS` | Generate docs/reference/script-matrix.md from the Script Registry (SITS). |
| `scripts/analysis/geometry_census.py` | `AnalysisGATEReproducibleDurableGeometryDerivation` | F-049 GATE 1A–1F: reproducible, durable geometry-derivation census. |
| `scripts/analysis/graph_query.py` | `DependencyGraph` | Interactive query tool for the codebase dependency graph (graph.dot). |
| `scripts/analysis/hour_of_day_certification.py` | `AnalysisHourDayCertificationProbe` | hour_of_day independent certification probe. |
| `scripts/analysis/implementation_model_validation_xauusd.py` | `ModelReport` | IMPLEMENTATION VALIDATION (not a backtest / not profitability). |
| `scripts/analysis/ledger_parity.py` | `AnalysisAcceptanceGateTargetStrategyArchitecture` | F-057 acceptance gate (target-strategy-architecture.md sec13 item4 / sec14.A last item). |
| `scripts/analysis/legacy_feature_fingerprint.py` | `AnalysisLegacyFeaturePipelineFingerprintFrozen` | Deterministic legacy FeaturePipeline fingerprint on frozen XAUUSD Phase-1 candidate. |
| `scripts/analysis/mature_semantic_audit.py` | `AnalysisReadEVIDENCEEXTRACTORMatureBar` | Read-only EVIDENCE EXTRACTOR for the mature-bar semantic audit (XAUUSD M15). |
| `scripts/analysis/model_evidence_survey.py` | `AnalysisOBSERVATIONSurveyModelEvidence` | OBSERVATION-ONLY survey of the Layer-7 Model Evidence layer. |
| `scripts/analysis/module_census.py` | `AnalysisAttributionCensusCoreLivesSrc` | Thin CLI for the module attribution census (core lives in src/governance/module_census.py). |
| `scripts/analysis/mother_range_inside_close.py` | `AnalysisConfigurableMOTHERRANGEINSIDECLOSE` | Configurable MOTHER-RANGE / INSIDE-CLOSE detector over M15 OHLCV. |
| `scripts/analysis/ohlcv_census.py` | `AnalysisPHASEOHLCVClosurePASSCensus` | PHASE 1 (OHLCV Truth Closure) PASS-A census generator. |
| `scripts/analysis/p001_excursion_probe.py` | `AnalysisUncappedForwardExcursionCRTEnvelope` | uncapped forward excursion on the CRT envelope populations. |
| `scripts/analysis/p1_sweep_memory_diag.py` | `AnalysisPersistLastSweepDirectionAcross` | Persist last_sweep_direction across StateMachine.reset_to_range. |
| `scripts/analysis/p2_disp_exemption_diag.py` | `AnalysisDISPLACEMENTStateExemptionHTFResets` | DISPLACEMENT state exemption from HTF resets. |
| `scripts/analysis/p3a_zone_attribution_diag.py` | `AnalysisZoneSessionAttributionEnhancedFILTER` | Zone / Session attribution: enhanced FILTER_REJECTED logging. |
| `scripts/analysis/p3b_gate_expired_counterfactual_rr.py` | `AnalysisPhasePromotionGateCounterfactualExpired` | Phase 3b promotion gate: counterfactual RR for expired expansion episodes. |
| `scripts/analysis/p3b_session_relax_diag.py` | `AnalysisSessionRelaxationAddASIAOFF` | Session relaxation: add ASIA + OFF_SESSION to allowed_sessions. |
| `scripts/analysis/p3c1_build_trade_audit.py` | `AnalysisExecutionPreconditionsAudit` | Execution Preconditions Audit. |
| `scripts/analysis/p3c_zone_relax_diag.py` | `AnalysisZoneThresholdRelaxation` | Zone threshold relaxation. |
| `scripts/analysis/p4_execution_intent_attribution.py` | `AnalysisExecutionIntentAttribution` | Execution Intent Attribution. |
| `scripts/analysis/phase1_duplicate_formula_identity_closure.py` | `AnalysisPhaseDuplicateFormulaIdentityClosure` | Phase-1 duplicate implementation + formula identity closure. |
| `scripts/analysis/phase1_run15a_quantity_role_adjudication.py` | `AnalysisQuantityRoleAdjudicationRUNRecords` | Quantity role adjudication only (142 RUN-1 records). |
| `scripts/analysis/phase1_run1_feature_truth.py` | `AnalysisLegacyBaselineVerificationFeatureUniverse` | Legacy baseline verification (1A) + feature universe census (1B). |
| `scripts/analysis/pit_phaseC_feature_certification.py` | `AnalysisPITPhaseEmpiricalCertificationCanonical` | PIT Phase C: empirical certification of ALL 38 canonical features (READ-ONLY). |
| `scripts/analysis/pit_swing_blast_radius.py` | `AnalysisPITPhaseInvestigationCenteredSwing` | PIT Phase A (investigation): centered-swing causal blast radius. |
| `scripts/analysis/pit_swing_gateon_ab.py` | `CausalStructurePipeline` | PIT Phase A decisive instrument: gate-ON ledger A/B. |
| `scripts/analysis/process_characterizer.py` | `AnalysisMEASUREProcessCharacterisationRawOHLCV` | MEASURE-ONLY process characterisation of a raw OHLCV series. |
| `scripts/analysis/process_diagnostics.py` | `AnalysisMEASUREStatisticalDiagnosticsRawOHLCV` | MEASURE-ONLY statistical diagnostics over a raw OHLCV series (BNBUSDT-scoped use). |
| `scripts/analysis/purge_delay_scan.py` | `AnalysisDayPurgeDelayedEntryDetection` | 20-Day Purge + Delayed-Entry Detection (standalone, read-only). |
| `scripts/analysis/purge_slice.py` | `AnalysisConditionalMetaAnalysisDayPurge` | Conditional meta-analysis of the 20-day-purge event corpus (read-only post-processing). |
| `scripts/analysis/python_source_static_census.py` | `AnalysisStaticCensusCanonicalFiles` | exposes canonical_python_files, test_python_files, rel, code_loc. |
| `scripts/analysis/query_decision_atlas.py` | `AnalysisDuckDBQuerySurfaceDecision` | DuckDB query surface over the decision atlas. |
| `scripts/analysis/query_trace.py` | `AnalysisDuckDBQuerySurfaceTrace` | DuckDB query surface over Trace / research Parquet projections. |
| `scripts/analysis/reachability_validation_report.py` | `AnalysisConsolidatedRegenerableSnapshotReachabilityValidation` | a consolidated, regenerable snapshot of the reachability validation state at reports/reachability_validation.{json,md}. |
| `scripts/analysis/render_chart.py` | `AnalysisINFRACPCWorkstreamOwnOHLC` | CLI for INFRA-CPC-V1 Workstream A0 (own OHLC charts). |
| `scripts/analysis/research_dag_provenance.py` | `AnalysisResearchProvenanceDAGTraceEvery` | Research provenance DAG: trace every architectural decision backwards to its origin. |
| `scripts/analysis/rr_confidence_probe.py` | `AnalysisTrackREADEmpiricalProbeFusion` | Track 1 (READ-ONLY) empirical probe for the RR-fusion confidence gate. |
| `scripts/analysis/run_crt_local_math_parity_audit.py` | `AnalysisCRTMathParityAuditOBSERVATION` | CRT-local math parity audit (OBSERVATION_ONLY measurement). |
| `scripts/analysis/run_crt_trace_workflow.py` | `AnalysisOneCommandSURVEYLOCATEPROVE` | One command for the SURVEY -> LOCATE -> PROVE trace workflow. |
| `scripts/analysis/run_gaussian_xauusd_2m.py` | `AnalysisRunTrainedGaussianCheckpointsXAUUSD` | run trained Gaussian NB checkpoints on XAUUSD trailing 2 months. |
| `scripts/analysis/run_msip_shadow.py` | `AnalysisBatchMSIPShadowRunnerOBSERVATION` | Batch MSIP shadow runner (OBSERVATION_ONLY). |
| `scripts/analysis/run_rr_xauusd_2m.py` | `AnalysisRunTrainedNanoInferenceFusion` | run the trained RR (NanoInference / rr_fusion checkpoint) on XAUUSD trailing 2 months (same window as Gaussian + ZoneGate runs). |
| `scripts/analysis/run_zonegate_xauusd_2m.py` | `AnalysisRunProductionZoneGateTrained` | run the production ZoneGate trained registry on XAUUSD trailing 2 months (same window as run_gaussian_xauusd_2m.py). |
| `scripts/analysis/schema_audit.py` | `AnalysisQuickAuditSchemaConsistencyAcross` | Quick audit for schema consistency across outputs: - trade CSVs (schema_name/version). |
| `scripts/analysis/script_census.py` | `AnalysisSITSCensusCoreLivesSrc` | Thin CLI for SITS script census (PR-6: core lives in src/governance/script_census.py). |
| `scripts/analysis/search_xauusd_candidate_window.py` | `AnalysisFindSmallestTrailingXAUUSDWindow` | Find smallest trailing XAUUSD window with >= N CRT RETEST candidates. |
| `scripts/analysis/semantic_layer_validation.py` | `AnalysisReadSTATISTICSENGINESevenDay` | Read-only STATISTICS ENGINE for the seven-day semantic-layer validation study (XAUUSD M15). |
| `scripts/analysis/session_certification.py` | `AnalysisCanonicalFeaturePipelineSessionCertification` | canonical FeaturePipeline `session` certification. |
| `scripts/analysis/session_cost_audit.py` | `AnalysisReadSessionLevelCostBreakdown` | read-only session-level cost breakdown. |
| `scripts/analysis/session_filter_funnel_probe.py` | `Arm` | Why do XAUUSD CRT RETESTs die at the session filter, and when would one pass?. |
| `scripts/analysis/session_override_scoping_proof.py` | `AnalysisScopingNonRegressionProof` | B3 scoping + non-regression proof. |
| `scripts/analysis/session_sweep.py` | `AnalysisPhaseEmpiricalThroughputFloorStaged` | Phase 6c empirical-throughput floor (staged session experiment). |
| `scripts/analysis/shadow_cross_range_restoration_probe.py` | `AnalysisMEASUREProbeREADAnalysis` | MEASURE-ONLY probe (READ-ONLY w.r.t. |
| `scripts/analysis/soft_conf_ema_double_update_probe.py` | `AnalysisMEASUREProbeREADAnalysis_1` | MEASURE-ONLY probe (READ-ONLY w.r.t. |
| `scripts/analysis/src_business_functionality_inventory.py` | `Tree` | Inventory business functionality of the repository's non-test Python trees. |
| `scripts/analysis/sweep_conditional_magnitude_probe.py` | `AnalysisStatePathDifferentMagnitude` | same state path, different magnitude?. |
| `scripts/analysis/sweep_state_persistence_probe.py` | `AnalysisDidMovePERSISTSplitBreaker` | did the move PERSIST, split by breaker/OB structure. |
| `scripts/analysis/sweep_structure_economic_probe.py` | `AnalysisDoesStructuralGapSurviveReal` | does the TT/FF structural gap survive real costs?. |
| `scripts/analysis/test_functionality_excel.py` | `Suite` | Build an Excel inventory of tests/**/*.py business functionality. |
| `scripts/analysis/trend_strength_certification.py` | `AnalysisTrendStrengthCertification` | trend_strength certification. |
| `scripts/analysis/update_reachability_golden.py` | `AnalysisACCEPTCHANGESReachabilityGoldensMirror` | ACCEPT-CHANGES script for the reachability L3 goldens (mirror of scripts/update_config_hash.py: regenerate the committed truth so a drift is an EXPLICIT accepted change, never s... |
| `scripts/analysis/v3_config_parity.py` | `AnalysisProveDecisionEmissionNeutral` | prove v3 is decision-identical to v2, and that emission is neutral. |
| `scripts/analysis/volatility_regime_certification.py` | `AnalysisVolatilityRegimeCertification` | volatility_regime certification. |
| `scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py` | `AnalysisXAUUSDM15DualCorpus` | Deterministic XAUUSD M15 dual-corpus timestamp / gap / overlap analysis (R2 evidence). |
| `scripts/analysis/xauusd_crt_baseline_trace.py` | `AnalysisXAUUSDCRTBaselineBarM` | XAUUSD CRT baseline 16-bar (4h M15) executable trace runner. |
| `scripts/analysis/xauusd_crt_transition_trace.py` | `AnalysisTransitionRichExecutableCoverage` | transition-rich executable coverage. |
| `scripts/analysis/xauusd_excel_feature_state_trace.py` | `AnalysisObserveBarTraceMT5` | Observe-only per-bar trace over an MT5-exported XAUUSD workbook:. |
| `scripts/analysis/xauusd_phase1_finish_validation.py` | `AnalysisFinishXAUUSDOHLCVPhaseValidation` | Finish XAUUSD OHLCV Phase-1 validation on the frozen candidate (read-only). |
| `scripts/analysis/xauusd_strict_reject_forensic.py` | `AnalysisReplayStrictFetchREJECTRow` | Replay strict-fetch REJECT for the 50,169-row XAUUSD artifact (read-only). |
| `scripts/analysis/zone_assignment_parity_probe.py` | `AnalysisREADAnalysis` | READ-ONLY. |
| `scripts/analysis/zone_registry_builder.py` | `AnalysisZoneRegistryBuilderLoadTrades` | exposes load_trades, build_feature_matrix, filter_profitable, cluster_zones. |
| `scripts/analysis/zone_registry_provenance_probe.py` | `AnalysisREADAnalysis_1` | READ-ONLY. |

### `scripts/metrics/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/metrics/extract_metrics.py` | `MetricsPROSPECTIVEREADExtractorOptionalMetrics` | PROSPECTIVE, READ-ONLY extractor for the optional ``**Metrics**`` self-report block that may be appended to ``📝 SESSION LOG ENTRY`` blocks in ``assistant_project.md``. |

### `src/analytics/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/analytics/__init__.py` | `AnalyticsApi` | Offline trade analytics: SL/TP comparison, loss clustering, performance metrics. |
| `src/analytics/clustering.py` | `TradeClusteringGroupsLosing` | TradeClustering: groups losing trades by condition to surface patterns. |
| `src/analytics/metrics_oracle.py` | `BacktestMetricsRecomputeOracle` | Independent backtest-metric recompute oracle for the Backtest Trust Layer. |
| `src/analytics/performance.py` | `PerformanceAnalyzerWinRate` | PerformanceAnalyzer: win rate, expectancy, drawdown, and breakdown metrics. |
| `src/analytics/sl_tp_comparator.py` | `ComparisonReport` | Dual SL/TP method comparator for backtest productivity analysis. |

### `src/charts/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/charts/__init__.py` | `ChartsApi` | INFRA-CPC-V1 Workstream A0: own OHLC charts from the corpus we consume. |
| `src/charts/chart_series.py` | `ChartSeriesINFRACPCBuilder` | INFRA-CPC-V1 A0 series builder (pure; no drawing). |
| `src/charts/crt_overlay.py` | `CRTTrack` | INFRA-CPC-V1 A0 Layer V1: resolve a per-bar CRTState track. |
| `src/charts/render.py` | `ChartsINFRACPCDrawingBarsCRT` | INFRA-CPC-V1 A0 drawing layer (Layer V0 bars + Layer V1 CRTState colour). |

### `src/interpreters/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/interpreters/__init__.py` | `InterpretersApi` | behavior-agnostic event/feature producers. |
| `src/interpreters/adapter.py` | `InterpreterHypothesis` | the ONLY bridge from an Interpreter to the research measurement stack (note: path stem 'adapter' vs content focus 'InterpreterHypothesis'). |
| `src/interpreters/contract.py` | `InterpreterEvent` | the Interpreter Contract (frozen Schema 1.0). |
| `src/interpreters/point_and_figure.py` | `PointFigureInterpreter` | PNF-v1, the FIRST real interpreter (Plan 5) (note: path stem 'point_and_figure' vs content focus 'PointAndFigureInterpreter'). |
| `src/interpreters/reference.py` | `NullInterpreter` | proof-of-contract interpreters (note: path stem 'reference' vs content focus 'NullInterpreter'). |
| `src/interpreters/regime_observer.py` | `RegimeLabeler` | non-directional volatility-regime reading (Program 4 / Program 4b). |

### `src/journal/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/journal/__init__.py` | `JournalApi` | Module at src/journal/__init__.py. |
| `src/journal/schema.py` | `TradeRecord` | Defines TradeRecord (note: filename suggests schema; content centers on TradeRecord). |
| `src/journal/trade_execution_link_v1_0.py` | `TradeExecutionLinkV1Transport` | transport correlation layer (Tier 0B, disposable) (note: path stem 'trade_execution_link_v1_0' vs content focus 'TradeExecutionLinkV1'). |
| `src/journal/trade_identity_v1_0.py` | `TradeIdentityV1SacredMinimum` | the sacred minimum trade identity (Tier 0A). |
| `src/journal/trade_logger.py` | `TradeLoggerJournal` | Defines TradeLogger. |
| `src/journal/trade_provenance_v1_0.py` | `TradeProvenanceV1GovernanceLineage` | governance lineage (Tier 0B, append, keyed by trade_id). |

### `src/scanner/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/scanner/__init__.py` | `ScannerApi` | Module at src/scanner/__init__.py. |
| `src/scanner/ranker.py` | `OpportunityRanker` | Defines OpportunityRanker. |
| `src/scanner/scanner.py` | `MultiSymbolScanner` | Defines MultiSymbolScanner. |
| `src/scanner/signal_pool.py` | `SignalPoolScanner` | Defines SignalPool. |
| `src/scanner/spine_adapter.py` | `SpineAdapterPathScanner` | the ONLY path from scanner signals to a trade decision. |
| `src/scanner/universe.py` | `UniverseScanner` | Defines Universe. |

### `src/search/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/search/regime_weight_searcher.py` | `RegimeWeightSearcherAwareFusion` | Regime-aware fusion weight + BitNet threshold search system. |

### `src/structure/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/structure/__init__.py` | `StructureApi` | the governed CRT structural kernel. |
| `src/structure/predicates.py` | `StructureCOMPUTATION` | HOW-COMPUTATION for SP-001 / SP-002. |

### `src/uat/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/uat/__init__.py` | `UatApi` | Module at src/uat/__init__.py. |
| `src/uat/kill_switch.py` | `KillSwitchStatefulDaily` | stateful daily/weekly loss gate for live trading protection. |
| `src/uat/monte_carlo.py` | `MonteCarloEngineBootstrapResampling` | bootstrap resampling for strategy robustness validation (note: path stem 'monte_carlo' vs content focus 'MonteCarloEngine'). |
| `src/uat/uat_runner.py` | `UATRunnerOrchestratesAreas` | orchestrates all 7 UAT areas for the 10-strategy trading system. |

### `src/ui/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/ui/__init__.py` | `UiApi` | Module at src/ui/__init__.py. |

## Area: `governance` (130)

### `scripts/governance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/governance/_build_doc_tracking_index.py` | `GovernanceMetadataInventoryContentReads` | metadata-only inventory (no content reads). |
| `scripts/governance/behavioral_constant_authority_trace.py` | `GovernanceBehavioralConstantAuthorityTraceActive` | Behavioral Constant Authority Trace + Active CRT Closure Pass (READ-ONLY). |
| `scripts/governance/build_crt_architecture_adjudication_v1.py` | `GovernanceCRTArchitectureAdjudicationBuilder` | CRT Architecture Adjudication V1 package builder. |
| `scripts/governance/build_fm_ownership_matrix.py` | `GovernancePermanentOwnershipConsumerMatrix` | permanent FM ownership / consumer matrix. |
| `scripts/governance/build_g001_consumer_attribution.py` | `GovernanceG001ConsumerAttributionSemantic` | build_g001_consumer_attribution.py â€” semantic correctness vs economic contribution. |
| `scripts/governance/build_msip1_verification_package.py` | `GovernanceMSIPVerificationConstructionREAD` | MSIP-1 Verification Package Construction (READ-ONLY w.r.t. |
| `scripts/governance/build_msip_shadow_design_contract_v1.py` | `GovernanceMSIPSHADOWCONTINUOUSSTATEBuilder` | MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN_V1 package builder. |
| `scripts/governance/construction_protocol.py` | `GovernanceGateRepositoryConstructionContractValidator` | Gate-6 Repository Construction Contract validator. |
| `scripts/governance/coverage_dashboard.py` | `GovernanceRepositorySemanticCoverageDashboard` | Repository Semantic Coverage Dashboard. |
| `scripts/governance/crt_config_construction_census.py` | `GovernanceOBSERVEStaticOptionalLiveFingerprint` | P1 OBSERVE static + optional live fingerprint. |
| `scripts/governance/enrich_workbooks_with_semantic_identity.py` | `GovernanceAppendSemanticIdentityColumnsThree` | append Semantic File Identity columns to the three existing business-functionality workbooks. |
| `scripts/governance/export_findings.py` | `FindingsExportRenderer` | Regenerates data/findings.jsonl as derived view of docs/current-findings.md via findings_export. |
| `scripts/governance/feature_certification_state.py` | `GovernanceFeatureCertificationLedgerSeedResolver` | the per-feature certification ledger: seed + resolver. |
| `scripts/governance/feature_dag_certify.py` | `OrderingViolation` | bottom-up certification mutation engine + transitive invalidation (note: path stem 'feature_dag_certify' vs content focus 'OrderingViolation'). |
| `scripts/governance/feature_surface_query.py` | `FeatureSurfaceIndex` | LLM-facing read-only query API over the feature surface. |
| `scripts/governance/framework_gap_audit.py` | `GovernanceGenerateReportsFrameworkGapAudit` | Generate reports/framework_gap_audit.md (001_FRAMEWORK_REGISTRY.md §M3). |
| `scripts/governance/framework_registry_report.py` | `GovernanceGenerateReportsFrameworkRegistryReport` | Generate reports/framework_registry_report.md from the registry (001 §M2 Deliverable 2). |
| `scripts/governance/patch_msip_shadow_design_consistency_v1.py` | `GovernancePatchMSIPShadowConsistency` | Patch MSIP shadow design package for WHAT/HOW consistency. |
| `scripts/governance/promote_v2.py` | `GovernanceMultiStrategyGovernancePromotion` | thin CLI wrapper for the multi-strategy governance promotion. |
| `scripts/governance/provenance_query.py` | `GovernanceReadRecordProvenanceSpineMPA` | read/record CLI over the Provenance Spine (MPA v1). |
| `scripts/governance/query_hypotheses.py` | `GovernanceQueryHypothesisRegistrySiblingQuery` | Query the Hypothesis Registry (sibling of query_registry.py). |
| `scripts/governance/query_registry.py` | `GovernanceQueryFrameworkRegistryFRAMEWORKREGISTRY` | Query the Framework Registry (001_FRAMEWORK_REGISTRY.md §M2). |
| `scripts/governance/query_scripts.py` | `GovernanceQueryRegistrySITS` | Query the Script Registry (SITS). |
| `scripts/governance/query_semantic_os.py` | `GovernanceClosedSemanticAskGround` | closed Semantic OS ask + ground CLI. |
| `scripts/governance/remap_zone_registry_v4.py` | `GovernanceOneShotZoneGateRegistry` | one-shot ZoneGate registry remap, schema v3.0 -> v4.0. |
| `scripts/governance/review_ohlcv_clocks.py` | `GovernanceHumanReviewStepBehindOHLCV` | the human review step behind the OHLCV clock-provenance gate. |
| `scripts/governance/rr_l1_freeze_certificate.py` | `GovernanceValidateHashAssertSigned` | validate, hash, assert-signed. |
| `scripts/governance/scan_model_paths_literals.py` | `GovernanceDetectUnauthorizedModelsPathString` | detect unauthorized ``models/`` path string literals. |
| `scripts/governance/scan_runtime_boundary.py` | `GovernanceEnforceKernelResearchImportDirection` | enforce the kernel <-> research import direction, PLUS the narrower research -> promotion/validation authority boundary. |
| `scripts/governance/seed_framework_registry.py` | `GovernanceSeedDataFrameworkRegistryJsonl` | Seed data/framework_registry.jsonl from the curated codebase classification. |
| `scripts/governance/seed_hypothesis_registry.py` | `GovernanceSeedDataHypothesisRegistryJsonl` | Seed data/hypothesis_registry.jsonl from the curated research-hypothesis ledger. |
| `scripts/governance/seed_script_registry.py` | `GovernanceOverlaysSITSSeedMergeEngine` | Thin CLI + PRIMARY overlays for SITS seed (PR-6: merge engine in src/governance/script_seed.py). |
| `scripts/governance/seed_semantic_os.py` | `GovernanceCompileAuthoredSemanticYAMLs` | compile the hand-authored Semantic OS YAMLs into the JSONL projection. |
| `scripts/governance/three_authority_surplus_census.py` | `GovernanceThreeAuthorityDeclarationSurplusCensus` | Three-Authority Declaration Surplus Census (READ-ONLY). |
| `scripts/governance/update_registry.py` | `GovernanceAppendUpdatedRegistryLineComponent` | Append an updated registry line for a component (001_FRAMEWORK_REGISTRY.md §M4). |
| `scripts/governance/validation_access_cli.py` | `GovernanceXAUUSDM15DualSurface` | VA-XAUUSD-M15 dual-surface validation access. |
| `scripts/governance/who_numeric_dependency_census.py` | `GovernanceNumericDependencyCensusREAD` | WHO Numeric Dependency Census (READ-ONLY). |

### `scripts/maintenance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/maintenance/_compute_hash.py` | `MaintenanceVerifyProductionConfigParamsHash` | recompute (and verify) a production config's `params` hash. |
| `scripts/maintenance/_promote_v4_bnb_cutover.py` | `MaintenanceOneOffGOVERNEDCutover` | one-off GOVERNED cutover. |
| `scripts/maintenance/check_consolidation_due.py` | `Signal` | advisory growth monitor for the always-loaded substrate (note: path stem 'check_consolidation_due' vs content focus 'Signal'). |
| `scripts/maintenance/check_governance_invariants.py` | `MaintenanceGovernanceGateRunCuratedGreen` | Governance-invariant gate: run the curated green floor when governed paths change. |
| `scripts/maintenance/check_session_log_commit.py` | `MaintenanceCommitLinkageGuardCommitChanges` | Commit-linkage guard: a commit that changes governed code must ship a same-day SESSION LOG entry. |
| `scripts/maintenance/cleanup_logs.py` | `MaintenanceArchiveFlatLogFilesLogs` | Archive flat log files in logs/ that are older than --days days. |
| `scripts/maintenance/fix_bom.py` | `MaintenanceFixBom` | Module at scripts/maintenance/fix_bom.py. |
| `scripts/maintenance/g1_build_v4_crt_sot_config.py` | `MaintenancePhaseCRTPlanMaintenance` | Phase G1 of the CRT single-source-of-truth plan. |
| `scripts/maintenance/g2_v4_crt_sot_parity.py` | `MaintenancePhaseCRTPlanMaintenance_1` | Phase G2 of the CRT single-source-of-truth plan. |
| `scripts/maintenance/g3_append_v4_crt_sot_registration.py` | `MaintenancePhaseCRTPlanMaintenance_2` | Phase G3 of the CRT single-source-of-truth plan. |
| `scripts/maintenance/gen_crt_state_identity.py` | `MaintenanceGeneratesSrcConfigCRTState` | Generates `src/config_layer/_crt_state_generated.py` from `active_models.yaml`, making the ontology the single authored source for CRT state IDENTITY (the enum, the transition g... |
| `scripts/maintenance/jsonl_to_parquet.py` | `MaintenanceParquetProjectionsJsonlResearchCorpora` | build Parquet projections over JSONL research corpora. |
| `scripts/maintenance/reorganize_results.py` | `MaintenanceMoveStrayTopLevelRun` | Move stray top-level run_{ts}_{COIN}/ directories in results/ into results/{COIN}/run_{ts}_{COIN}/ (mirroring the portfolio_raw/ convention). |
| `scripts/maintenance/rotate_session_log.py` | `MaintenanceBoundUnboundedSESSIONLOGCLAUDE` | bound the unbounded SESSION LOG (CLAUDE.md §6 / the #3 context-ceiling). |

### `src/agent/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/agent/__init__.py` | `AgentApi` | multi-specialist kitchen agent (NL → intent → bounded tools → confirm-gated execution). |
| `src/agent/agent_core.py` | `InRepoAgentCore` | In-repo agent core loop coordinating intent, planning, and execution. |
| `src/agent/audit.py` | `AuditLoggerAppendJsonl` | Append-only JSONL audit logger with two output streams:. |
| `src/agent/cli.py` | `AgentGrokAgenticAIInteractiveREPL` | GrokAgenticAI interactive REPL Usage: python -m src.agent.cli python -m src.agent.cli --resume ses_1234567890 python -m src.agent.cli --agent ops_doctor python -m src.agent.cli ... |
| `src/agent/executor.py` | `AgentToolExecutor` | Executes compiled agent tool plans against the tool registry. |
| `src/agent/findings_synthesizer.py` | `AgentPostRunFindingsGroqLlama` | Post-run findings via Groq Llama-3.1-70B Pulls run record + log tails + relevant source slice, sends a redacted prompt to GroqClient, and appends a structured finding to ``logs/... |
| `src/agent/goal.py` | `SuccessCriterion` | AgentGoal contracts for GrokAgenticAI Goal-oriented campaign objects. |
| `src/agent/goal_loop.py` | `GoalLoopGrokAgenticAIExecution` | GrokAgenticAI goal execution Runs a specialist AgentGoal under existing Executor fences:. |
| `src/agent/grok_agentic.py` | `AgentGrokAgenticAIMultiAgent` | GrokAgenticAI multi-agent registry Product name: **GrokAgenticAI**. |
| `src/agent/groq_client.py` | `GroqClientAgentTier` | Agent-tier Groq LLM client with request logging + redaction Used by the findings_synthesizer (and any future agent-side LLM caller) when post-run reasoning over code + logs is r... |
| `src/agent/intent_router.py` | `AgentIntentRouter` | Routes natural-language or structured intents to agent modes/tools. |
| `src/agent/log_query.py` | `AgentReadableQueryInterfaceExecution` | Agent-readable query interface over the execution memory layer. |
| `src/agent/modes/__init__.py` | `AgentModesApi` | Agent tool-registration modes (pipeline, copilot, governance, findings, log-query, ops). |
| `src/agent/modes/copilot_mode.py` | `AgentLiveSignalPilotToolRegistrations` | Live Signal Co-pilot tool registrations All tools in this mode are read-only. |
| `src/agent/modes/findings_mode.py` | `AgentPostRunFindingsToolRegistrations` | Post-run findings tool registrations Tools: findings.synthesize, findings.list_recent, findings.explain. |
| `src/agent/modes/governance_mode.py` | `AgentGovernanceMetaReasonerToolRegistrations` | Governance Meta-reasoner tool registrations Tools: governance.run_loop, reflection.load_merge, reflection.generate_prompt, meta_governor.dry_run, shadow.stage_candidate, audit.t... |
| `src/agent/modes/log_query_mode.py` | `AgentReadLogQueryToolRegistrations` | Read-only log query tool registrations Tools: log.get_run, log.get_trade, log.query. |
| `src/agent/modes/ops_mode.py` | `AgentGrokAgenticAIOpsDoctor` | GrokAgenticAI OpsDoctor tools (read-only + incident pack) Tools: ops.throughput_snapshot — scan logs/results for recent trade/run signals ops.funnel_diagnose — wrap scripts/anal... |
| `src/agent/modes/pipeline_mode.py` | `AgentPipelineOrchestratorToolRegistrationsTools` | Pipeline Orchestrator tool registrations Tools: tuner.run_multi, validator.validate, promotion.promote_from_checkpoint, backtest.run_v2, live_hook.dry_run, live_hook.enable. |
| `src/agent/modes/truth_mode.py` | `AgentGrokAgenticAIJanitorTools` | GrokAgenticAI TruthJanitor tools Governance / documentation hygiene (async kitchen only). |
| `src/agent/plan_compiler.py` | `IntentToToolPlanCompiler` | Deterministic intent → tool sequence plan compiler. |
| `src/agent/recipes/__init__.py` | `AgentRecipesApi` | Bounded recipes for GrokAgenticAI specialists (no free tool choice). |
| `src/agent/recipes/campaign_pipeline.py` | `AgentCampaignRunnerSeedModeBranch` | CampaignRunner seed + Mode-B branch table (metric → next tools). |
| `src/agent/recipes/ops_diagnose.py` | `AgentFixedReadChainIncidentPack` | fixed read-only chain + incident pack. |
| `src/agent/recipes/truth_janitor.py` | `AgentHygieneChecksRollupPack` | hygiene checks then rollup pack. |
| `src/agent/state.py` | `ToolCall` | conversation memory, tool call log, pending confirmations (note: path stem 'state' vs content focus 'ToolCall'). |
| `src/agent/tool_planner.py` | `ArgFiller` | ArgFiller Uses the LLM to fill missing required args for a single ToolStep. |
| `src/agent/tool_registry.py` | `AgentToolRegistry` | Registry of agent tools with ToolSpec metadata. |

### `src/control_plane/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/control_plane/__init__.py` | `ControlPlaneApi` | Stdlib-HTTP control plane: localhost dashboard, command registry, job runner. |
| `src/control_plane/code_context_extractor.py` | `ControlPlaneASTBasedExtractionContext` | AST-based code extraction for Context Reports. |
| `src/control_plane/context_report.py` | `ContextReportAPIClaudePowered` | ContextReportAPI: Claude-powered ARCHITECTURE ANALYST for runs. |
| `src/control_plane/cp_types.py` | `ControlPlaneRunRecord` | Defines ArgSpec, CommandSpec, RunRecord (note: filename suggests cp_types; content centers on RunRecord). |
| `src/control_plane/dashboard_api.py` | `ControlPlaneDashboardApi` | Dashboard API surface over control-plane registries and job state. |
| `src/control_plane/dot_graph_context.py` | `ControlPlaneFlowResolutionArchitecturalGraph` | flow resolution + architectural graph context for Context Reports. |
| `src/control_plane/jobs.py` | `ControlPlaneJobManager` | Job manager for control-plane scheduled/on-demand work. |
| `src/control_plane/monitors.py` | `ControlPlaneControlPlaneDashboardMonitor` | Control-plane dashboard monitor specs (jsonl-tail/json/regex/file-stat sources). |
| `src/control_plane/registry.py` | `ControlPlaneCommandSpecRegistryCatalog` | CommandSpec registry: the catalog of control-plane commands. |
| `src/control_plane/report_api.py` | `RunReportAPIExcelGeneration` | RunReportAPI: Excel generation + Groq LLM analysis for run history reports. |
| `src/control_plane/server.py` | `ControlPlaneHttpServer` | Control-plane HTTP server hosting jobs, monitors, and dashboard APIs. |

### `src/governance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/governance/__init__.py` | `GovernanceApi` | Module at src/governance/__init__.py. |
| `src/governance/bitnet_governance_executor.py` | `MetaGovernorExecutor` | Defines MetaGovernorExecutor. |
| `src/governance/config_integrity.py` | `GovernanceGuardsProductionConfigLineage` | governance guards for production-config lineage. |
| `src/governance/expansion_integration.py` | `ExpansionGovernanceBridge` | Defines ViabilityFilter, ExpansionGovernanceBridge. |
| `src/governance/findings_export.py` | `GovernanceMachineReadableCurrentFindings` | GENERATED machine-readable derived view of docs/current-findings.md. |
| `src/governance/framework_registry.py` | `FrameworkRegistryQueryableAppend` | queryable, append-only map of the trading-system architecture. |
| `src/governance/hypothesis_registry.py` | `HypothesisRegistry` | Registry of research hypotheses and promotion state. |
| `src/governance/jsonl_claim_catalog.py` | `CatalogLoaderAdmissibility` | loader + admissibility over the PRIMARY CAN/CANNOT vocabulary (note: path stem 'jsonl_claim_catalog' vs content focus 'Catalog'). |
| `src/governance/measurement_result_log.py` | `GovernanceCommittedRecordSealedContractActually` | the committed record that a sealed MC-* contract actually EXECUTED. |
| `src/governance/module_attribution.py` | `AttributionRegistryGovernanceSurface` | governance-surface ownership for every ``src/`` module (note: path stem 'module_attribution' vs content focus 'ModuleAttributionRegistry'). |
| `src/governance/module_census.py` | `GovernanceDiscoveredDiscoveryPathStable` | discovery + path-stable stub merge for ``src/**/*.py`` (note: path stem 'module_census' vs content focus 'DiscoveredModule'). |
| `src/governance/multi_strategy_validator.py` | `MultiStrategyValidatorGovernanceValidationReport` | governance ValidationReport for the 10-strategy system. |
| `src/governance/orchestrator.py` | `GovernanceOrchestratorFullStep` | full 4-step governance loop (note: path stem 'orchestrator' vs content focus 'GovernanceOrchestrator'). |
| `src/governance/portfolio_validation.py` | `PortfolioAnalytics` | PORTFOLIO VALIDATION v1.0 ║ ║ Multi-market edge universality test ║ ║ ║ ║ Question: Is CRT + Gaussian a pattern or a law of markets?. |
| `src/governance/promotion_manager.py` | `PromotionManager` | Manages promotion of research artifacts into production pins. |
| `src/governance/provenance_derivation.py` | `GovernanceBackfillEngineMPAPhase` | the backfill engine (MPA v1, Phase 3). |
| `src/governance/provenance_record.py` | `GovernanceProvenanceSpineAppendRecordMPA` | the Provenance Spine's append-only record (MPA v1, Phase 1). |
| `src/governance/provenance_resolver.py` | `GovernanceReadSlotResolutionEXISTINGRecord` | read-only slot resolution over the EXISTING record systems (Phase 2). |
| `src/governance/reflection_buffer_advanced.py` | `ReflectionBuffer` | Defines ReflectionBuffer. |
| `src/governance/script_census.py` | `GovernanceDiscoveredSITSCensusCore` | SITS script census core (PR-6 extract from scripts/analysis/script_census.py). |
| `src/governance/script_registry.py` | `ScriptRegistry` | Governance registry of scripts with provenance and ownership metadata. |
| `src/governance/script_seed.py` | `GovernanceSITSSeedPipelineCoreExtract` | SITS seed pipeline core (PR-6 extract from scripts/governance/seed_script_registry.py). |
| `src/governance/semantic_grounding.py` | `GroundingClosedWorld` | closed-world claim grounder (Semantic OS L5 companion). |
| `src/governance/semantic_identity.py` | `GovernanceTierDerivationSemanticIdentity` | Tier-3 derivation for the Semantic File Identity Layer. |
| `src/governance/semantic_objects.py` | `GovernanceObjectSemantic` | the GENERATED Object layer of the Semantic OS. |
| `src/governance/semantic_os.py` | `SemanticOsConceptBoundaryRegistry` | Hand-authored Concepts/Boundaries/Journeys registry answering why-code-exists questions. |
| `src/governance/semantic_query.py` | `Answer` | L5, the Semantic Query Engine. |
| `src/governance/shadow_promotion_gate.py` | `ShadowPromotionGateGovernance` | Shadow Promotion Gate. |
| `src/governance/strategy_backtest.py` | `StrategyMetrics` | per-strategy historical performance measurement. |

### `src/identity/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/identity/__init__.py` | `IdentityApi` | Phase 4 writers/readers for the frozen layer identities. |
| `src/identity/certify.py` | `IdentityShadowXAUUSDIdentityCertification` | Shadow XAUUSD identity certification. |
| `src/identity/check.py` | `IdentityLegalLoadPath` | the only legal load path. |
| `src/identity/hashes.py` | `IdentityHashes` | Identity hashes. |
| `src/identity/outcome.py` | `IdentityOutcomeRecordBuilder` | L5 outcome record builder. |
| `src/identity/query.py` | `BarReplay` | replay and query over PRESERVED identity records only. |
| `src/identity/store.py` | `Identity` | File-backed identity store: Class A snapshots, Class B records, Class C bindings. |
| `src/identity/tokens.py` | `IdentityClosedVocabulariesCopiedIdentityContract` | Closed vocabularies copied from the identity contract. |

### `src/validation_access/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/validation_access/__init__.py` | `ValidationAccessApi` | dual-surface sequential ladder S→I→F→E. |
| `src/validation_access/ladder.py` | `ValidationAccessXAUUSDM15Sequential` | VA-XAUUSD-M15 sequential validation ladder: S → I → F → E. |
| `src/validation_access/surfaces.py` | `ValidationAccessDualSurfacesXAUUSDM` | Dual surfaces for VA-XAUUSD-M15: Surface A (CLI) and Surface B (evidence pack). |

## Area: `research` (458)

### `scripts/evaluation/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/evaluation/__init__.py` | `EvaluationApi` | RAG benchmark evaluation suite. |
| `scripts/evaluation/report.py` | `EvaluationGenerateHumanReadableReportBenchmark` | Generate a human-readable markdown report from a benchmark run JSON. |
| `scripts/evaluation/run_benchmark.py` | `EvaluationAutomatedRAGBenchmarkEvaluationRunner` | Automated RAG benchmark evaluation runner. |

### `scripts/export/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/export/export_bitnet_model.py` | `ExportCanonicalBitnetExportRandomWeights` | Canonical bitnet_v3 export (random weights smoke). |
| `scripts/export/generate_bootstrap_model.py` | `ExportGeneratesRandomWeightModelJson` | Generates a random-weight model.json for the legacy bitnet_score() path. |
| `scripts/export/regen_bitnet_35.py` | `ExportRegenerateModelExportFormatJson` | Regenerate model_export_format.json with input_dim=35 (legacy v2.0 schema) wrapped in the canonical bitnet_v3 envelope (schema_version + feature_dim + feature_order_hash + featu... |

### `scripts/research/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/research/_build_xauusd_library_and_eval.py` | `ResearchPhaseRepresentativeTraceLibraryEngine` | Phase 3+4: Representative Trace Library + Engine Evaluation. |
| `scripts/research/_corpus_inspect.py` | `ResearchQuickInspectionXAUUSDTraceCorpus` | Quick inspection of the XAUUSD trace corpus. |
| `scripts/research/_enrich_xauusd_corpus.py` | `ResearchPhaseEnrichXAUUSDTraceCorpus` | Phase 1: Enrich XAUUSD trace corpus with feature vectors. |
| `scripts/research/_enrich_xauusd_engines.py` | `ResearchPhaseEnrichXAUUSDTraceCorpus_1` | Phase 2: Enrich XAUUSD trace corpus with engine outputs. |
| `scripts/research/_fix_eval_auc.py` | `ResearchHotfixRegenerateENGINEEVALUATIONCorrect` | Hotfix: regenerate ENGINE_EVALUATION.md with correct AUC/IC computation. |
| `scripts/research/_patch_xauusd_report_tradenet.py` | `ResearchOneShotMarkTradeNet` | One-shot: mark TradeNet as BLOCKED (dim mismatch) in summary + report. |
| `scripts/research/_show_top_decile_n9.py` | `ResearchShowTopDecileHasProtocol` | Show why nb_top_decile has n=9 on protocol v1 units. |
| `scripts/research/_verify_outputs.py` | `ResearchVerifyEnrichmentOutputs` | Verify all enrichment outputs. |
| `scripts/research/_watch_h_rr.py` | `ResearchWatchTHRESHOLDUntilREPORTExists` | Watch H-RR-THRESHOLD-001 until REPORT.md exists or processes die. |
| `scripts/research/ablate_zone_thr_xauusd_fusion.py` | `ResearchFullFusionZoneGateThreshold` | Full-fusion ZoneGate threshold ablation on XAUUSD. |
| `scripts/research/accepted_trade_attribution.py` | `ResearchStudyDoesFeatureOutcomeEdge` | Study 1: does feature→outcome edge EMERGE after selection?. |
| `scripts/research/analyze_clean_labels_tn_env.py` | `ResearchFiveStageAnalysisENVCLEAN` | Five-stage analysis of TN_ENV_CLEAN_L1 clean labels (read-only). |
| `scripts/research/analyze_trace_corpus.py` | `ResearchDESCRIPTIVEDistributionsMathematicalTraceCorpus` | DESCRIPTIVE distributions over the Mathematical Trace Corpus (ERP). |
| `scripts/research/bitnet_population_label_audit.py` | `ResearchBalanceAfterEveryCONTRACTPreprocessing` | CLI: class balance after every CONTRACT-C preprocessing stage, multi-dataset. |
| `scripts/research/bitnet_r25_kill_test.py` | `ResearchBitNetKillTestHarness` | CLI for BitNet R2.5 kill-test harness (Spec v1.2.6). |
| `scripts/research/bitnet_shadow_diagnostic.py` | `ResearchMeasureEXISTINGBitNetGate` | measure the EXISTING BitNet gate's effect on the CRT spine. |
| `scripts/research/bnbusdt_analyze_report.py` | `ResearchStageAnalyzeEnrichedTradeDataset` | Stage 3: Analyze enriched trade dataset, produce report. |
| `scripts/research/bnbusdt_conditional_edge.py` | `ResearchREADSimpsonParadoxConditionalEdge` | READ-ONLY Simpson's-paradox / conditional-edge audit. |
| `scripts/research/bnbusdt_enrich_trades.py` | `ResearchStageEnrichTradesCSVMFE` | Stage 2: Enrich trades CSV with MFE/MAE/return horizons. |
| `scripts/research/bnbusdt_forensics.py` | `ResearchForensicRootCauseAnalysis` | Layer-6 forensic root-cause analysis (thin CLI). |
| `scripts/research/build_bar_matrix.py` | `ResearchStageProfitableEntryOracleProgram` | Stage 0 of the profitable-entry oracle program (SEM-018). |
| `scripts/research/build_boundary_hypothesis_eval.py` | `ResearchZoneBoundaryCenterHypothesisDISPLACEMENT` | CLI: zone-boundary vs center hypothesis for DISPLACEMENT enrichment. |
| `scripts/research/build_clean_labels_tn_env.py` | `ResearchDualTradeNetEnvelopeNet` | Thin CLI: dual TradeNet + EnvelopeNet clean-label builder (GATE-L / ENV-L). |
| `scripts/research/build_crt_zone_crosstab.py` | `ResearchCRTStateZoneCrossTabulation` | CLI: CRT State × Zone cross-tabulation on XAUUSD Phase-1 (or any OHLCV). |
| `scripts/research/build_displacement_zone_event_study.py` | `ResearchDISPLACEMENTLeadLagRareZone` | CLI: DISPLACEMENT lead/lag vs rare zone entries (1/4/5/6). |
| `scripts/research/build_episodes.py` | `ResearchOpportunityEpisodeCorpusProtocol` | Thin CLI: build an OpportunityEpisode corpus (protocol OE_L1). |
| `scripts/research/build_gaussian_delta_gap_eval.py` | `ResearchSignedCalibrationGapStudyMeasure` | signed Δ=ML−H calibration-gap study (measure-only). |
| `scripts/research/build_gaussian_family_shadow_eval.py` | `ResearchGaussianFamilyShadowAgreementGeometry` | CLI: Gaussian family shadow_ml agreement + geometry-conditioned economics. |
| `scripts/research/build_rare_zone_context_filter_eval.py` | `ResearchRareZoneEntryCRTContext` | CLI: rare-zone entry × CRT context (RANGE vs SWEEP) precision/recall/calibration. |
| `scripts/research/build_rare_zone_detection_eval.py` | `ResearchRareZoneEntryDISPLACEMENTEvent` | CLI: rare-zone entry as DISPLACEMENT event detector (precision/recall/baselines). |
| `scripts/research/build_rare_zone_fa_characterization.py` | `ResearchPartitionRareZoneFZone` | CLI: partition rare-zone FAs by zone; label 20-bar CRT evolution; vs TPs. |
| `scripts/research/build_resampled_data.py` | `ResearchProgramDataPrepM15` | Program 3 data prep: M15 -> {H1, H4} for the crypto majors. |
| `scripts/research/build_rr_dataset_from_clean_labels.py` | `ResearchAdapterENVCLEANLabel` | Adapter: TN_ENV_CLEAN_L2 clean-label rows -> rr_dataset.json payload shape. |
| `scripts/research/build_trace_corpus.py` | `ResearchMathematicalTraceCorpusToyFamily` | Mathematical Trace Corpus from toy-family (+ spine) executions (ERP). |
| `scripts/research/build_zone_census.py` | `ResearchFullCorpusHistoricalZoneMapper` | CLI: full-corpus HistoricalZoneMapper census (occupancy / dwell / transitions). |
| `scripts/research/candle_state_report.py` | `ResearchConsolidateProgramOneEvidenceTable` | consolidate Program 4b/4c/4d into one evidence table (incl. |
| `scripts/research/certify_xauusd_corpus.py` | `ResearchOfflineCertificationCanonicalXAUUSDM` | offline certification of the canonical XAUUSD M15 corpus (ERP T1). |
| `scripts/research/convert_zones_v1_to_gaussian.py` | `ResearchConvertDiscoverZonesRegistryGaussian` | Convert a `discover_zones` v1 registry into the `v2_gaussian` runtime schema. |
| `scripts/research/crt_parity_classifier.py` | `MismatchContext` | Mismatch Classifier (pure, F-069 program) READ-ONLY / PURE (note: path stem 'crt_parity_classifier' vs content focus 'MismatchContext'). |
| `scripts/research/crt_parity_report.py` | `ResearchReportGeneratorProgramResearch` | Report Generator (F-069 program) Research-only. |
| `scripts/research/crt_parity_sweep.py` | `ResearchSweepDriverProgramResearch` | Sweep Driver (F-069 program) Research-only. |
| `scripts/research/crt_range_rebuild_probe.py` | `RangeSnap` | CRT range-rebuild edge probe (OBSERVATION_ONLY, research shadow) Classifies residual SWEEP↔RANGE disagreement after B1 by comparing:. |
| `scripts/research/crt_resolver_economic_comparison.py` | `EngineTrade` | Economic Comparison (F-069 follow-up, relaxed trigger) READ-ONLY / observe-only w.r.t (note: path stem 'crt_resolver_economic_comparison' vs content focus 'EngineTrade'). |
| `scripts/research/crt_state_confusion_matrix.py` | `EngineTimeline` | Bar-aligned Confusion Matrix Transition-parity instrument (research only, no production authority) (note: path stem 'crt_state_confusion_matrix' vs content focus 'EngineTimeline'). |
| `scripts/research/crt_state_window_trace.py` | `ResearchBarENGINERESOLVERStateTrace` | Per-bar ENGINE vs RESOLVER state trace over named bar windows, with divergence causes. |
| `scripts/research/crt_variant_surface.py` | `VariantInput` | CRT Resolver Variant Comparison Surface (N parallel streams) Wiring-phase instrument. |
| `scripts/research/diagnose_gaussian_pivotality.py` | `ResearchDoesGaussianChannelChangeTrade` | does the Gaussian channel change ANY trade?. |
| `scripts/research/diagnose_zone_inertness.py` | `ResearchZoneClusterInertLiveSpine` | WHY is the zone cluster inert on the live spine?. |
| `scripts/research/dimensional_mix_shadow_diagnostic.py` | `ResearchMeasureCorrectionSpine` | measure the FM-022/023 -> FM-030/031 correction on the spine. |
| `scripts/research/discover_zones.py` | `ResearchClustersOpportunityRecordsZonesSimilar` | clusters opportunity records into "zones" of similar market context, producing a simple zone registry consumable by the runtime zone-gate engine. |
| `scripts/research/e1_retest_depth_max_probe.py` | `ResearchPhaseCRTPlanSession` | Phase E1 of the "CRT single source of truth" plan (2026-08-31 session). |
| `scripts/research/edge_attribution_study.py` | `ResearchEdgeAttributionSurvivabilityStudyResearch` | Edge Attribution + Survivability Study (research / measure-first). |
| `scripts/research/emit_bar_structure_snapshots.py` | `ResearchProduceBarStructureSnapshotStream` | produce the per-bar BarStructureSnapshot stream. |
| `scripts/research/emit_dual_construction_trace.py` | `ResearchRunBothDualConstructionEmitters` | run both v4 dual-construction emitters, proven neutral. |
| `scripts/research/erp_synth_4h_trace.py` | `BarResearch` | intentional synthetic 4h M15 OHLCV + intended-vs-produced trace. |
| `scripts/research/execution_planner_replay.py` | `ResearchSplitRETESTEXECUTIONEdgeSelection` | split the RETEST->EXECUTION edge into Selection vs SL/TP (measure-only). |
| `scripts/research/exit_geometry_scan.py` | `ResearchExitGeometryDynamicStopDecomposition` | exit-geometry & dynamic-stop decomposition (SEM-019 / SEM-020). |
| `scripts/research/feature_formula_coverage_report.py` | `ResearchOntologyTestCoverageSemanticParity` | ontology ↔ test-coverage semantic parity. |
| `scripts/research/feature_region_oos_study.py` | `ResearchPartCRTFeatureRegionsPersist` | Part 4A: do CRT feature regions persist out-of-sample?. |
| `scripts/research/gate0_tn_env_feasibility.py` | `ResearchGATEDualFeasibilityProbeTrade` | GATE-0 dual feasibility probe: TradeNet (TN) + EnvelopeNet (ENV). |
| `scripts/research/gate_measurement_m_gate_01.py` | `ResearchGateMeasurementCRTSTRUCTURESCOPE` | gate-ON re-measurement of RF-CRT-STRUCTURE (SCOPE measurement only). |
| `scripts/research/gate_o_nonlinear_probe.py` | `ResearchGATENonlinearLearnabilityProbesENV` | GATE-O nonlinear learnability probes on TN_ENV_CLEAN_L2 (research only). |
| `scripts/research/gaussian_rr_scatter.py` | `ResearchPhaseGaussianCouplingDiagnosticLoads` | Phase 1: Gaussian ↔ RR Coupling Diagnostic Loads OHLC data, runs both engines per-bar, and reports correlation, mean comparison, and distribution stats. |
| `scripts/research/h_rr_threshold_001.py` | `TaggedEntry` | H-RR-THRESHOLD-001 runner (thin CLI). |
| `scripts/research/high_acceptance_activity_conditioning.py` | `ResearchPhaseStudiesConditionActivityState` | Phase 3.5 Studies A/B/C: condition on the activity state instead of predicting through it (research, ontology-free). |
| `scripts/research/high_acceptance_gap_policy.py` | `ResearchPhaseDefinitionRepairRunPhase` | Phase 3.5 Definition Repair: re-run the phase-1 acceptance kernel under explicit GAP POLICIES (research, ontology-free). |
| `scripts/research/high_acceptance_group_ablation.py` | `ResearchPhaseStudyFeatureGroupAblation` | Phase 3.5 Study 0.5: feature-group ablation on the Ridge model (research, ontology-free). |
| `scripts/research/high_acceptance_multivariate_model.py` | `ResearchPhaseMultivariateModelStructuralCharacteristics` | Phase 3: multivariate model over the structural characteristics of high-acceptance candles (research, ontology-free). |
| `scripts/research/high_acceptance_normalization_control.py` | `ResearchPhaseStudyVolatilitySignalReal` | Phase 3.5 Study 0: is the volatility signal real, or a property of the metric's denominator?. |
| `scripts/research/high_acceptance_regime_stability.py` | `ResearchPhaseStudyRegimeStabilityWalk` | Phase 3.5 Study 0.6: regime stability + walk-forward decomposition of the surviving rank signal (research, ontology-free). |
| `scripts/research/high_acceptance_scan.py` | `ResearchHighAcceptanceCandleNumericalScan` | High-Acceptance-Candle Numerical Scan (research / phase 1, ontology-free). |
| `scripts/research/high_acceptance_structural_scan.py` | `ResearchPhaseStructuralCharacteristicsStrongestHigh` | Phase 2: structural characteristics of the strongest high-acceptance candles (research, ontology-free). |
| `scripts/research/htf_objective_gate_shadow.py` | `ResearchHTFAttributedOFFLedgerParent` | P-HTF-01: attributed OFF-vs-ON ledger for `parent_crt.objective_gate` (Stage 3 / F-078, HTFState + ObjectiveStatus). |
| `scripts/research/htf_parent_telemetry_extract.py` | `ResearchStructuredHTFParentCRTTelemetry` | structured HTF/parent-CRT telemetry for the Monthly TradingView <-> Active Production Semantic Comparison Report. |
| `scripts/research/ic002_build_trajectories.py` | `ResearchTrajectoriesIC002` | Build IC-002 trajectories (H-IC002-001). |
| `scripts/research/ic002_evaluate.py` | `ResearchEvaluatePathStaticBaselineIC` | Evaluate IC-002 path vs static baseline (H-IC002-001). |
| `scripts/research/ic003_build_shape_library.py` | `ResearchShapeLibraryTrajectoriesIC003` | Build IC-003 shape library from IC-002 trajectories (H-IC003-001). |
| `scripts/research/ic003b_build.py` | `ResearchSequenceGeometryLibraryIC003` | Build IC-003B sequence-geometry library (H-IC003B-001). |
| `scripts/research/ic003b_derive_information.py` | `ResearchDeriveNEWDescriptiveInformationProduced` | Derive NEW descriptive information from the produced IC-003B shape-library data. |
| `scripts/research/ingest_live_outcomes.py` | `ResearchPairsLiveAlertsLogsLive` | Pairs live alerts (logs/live_alerts.jsonl) with manually-supplied execution outcomes to produce trainable records suitable for the Pipeline-B Gaussian calibration path. |
| `scripts/research/inspect_old_runs.py` | `ResearchInspectOlderBNBUSDTRunsFind` | Inspect older BNBUSDT runs to find parameters that produced more trades. |
| `scripts/research/jse001_crt_context_join.py` | `ResearchJSEEngineStateAsofJoint` | JSE-001: engine_state_asof vs joint-state membership (BNB-only). |
| `scripts/research/jse002_engine_state_path_geometry.py` | `ResearchJSEDoesEngineStateAsof` | JSE-002: Does engine_state_asof predict path geometry?. |
| `scripts/research/jse003_engine_context_history_path_geometry.py` | `ResearchJSEEngineContextHistoryPath` | JSE-003: engine_context_history -> path geometry (BNB-only). |
| `scripts/research/l003h_trail_exit_transition_replay.py` | `ResearchCandleReplayTrailExitTransition` | Candle replay for trail/exit transition events (standalone). |
| `scripts/research/l003i_trail_baseline_inversion.py` | `ResearchL003ITrailBaseline` | exposes other_bucket, safe_div, compute_from_bjr, pct. |
| `scripts/research/live_path_replay.py` | `ResearchDoesBacktestEdgeSurviveLIVE` | R2: does the backtest edge survive the LIVE ExecutionPlanner + Ultron path?. |
| `scripts/research/m5_mtf_information.py` | `ResearchStageInformationGateProgramResearch` | Stage-1 information gate for Program 9 (thin CLI). |
| `scripts/research/mc_cpr_l0_residual_harness.py` | `ResearchCPRObserveResidualHarness` | MC-CPR-L0 observe-only residual harness. |
| `scripts/research/model_shadow_protocol.py` | `ResearchGeneralizedShadowOptionalModelSlot` | generalized shadow A/B for an optional model slot. |
| `scripts/research/momentum_continuation_bnbusdt.py` | `ResearchBNBUSDTM15` | BNBUSDT M15. |
| `scripts/research/opportunity_scanner.py` | `ResearchGeneratesUnbiasedGroundOpportunityLogs` | generates unbiased ground-truth opportunity logs. |
| `scripts/research/oracle_pattern_scan.py` | `ResearchStageProfitableEntryOracleProgram_1` | Stage 3 of the profitable-entry oracle program. |
| `scripts/research/p_struct_01_displacement_evidence.py` | `IllegalPredecessor` | CRT DISPLACEMENT evidence table (not a fingerprint). |
| `scripts/research/parent_crt_pivotality_probe.py` | `ResearchParentCRTBiasGatePIVOTAL` | is the F-075 parent-CRT bias gate PIVOTAL?. |
| `scripts/research/path_ambiguity_census.py` | `ResearchProgramPhase` | Program 10 / Phase 0A (thin CLI). |
| `scripts/research/phase0_economic_edge_diagnosis.py` | `ResearchPhaseEconomicEdgeDiagnosisFunding` | Phase-0 Economic Edge Diagnosis (the funding gate). |
| `scripts/research/phase6e_shadow_ab.py` | `ResearchPhaseGovernanceValidationMeasure` | Phase 6e governance re-validation (measure-only). |
| `scripts/research/phase_b_conditional_entropy.py` | `ResearchPhaseConditionalEntropyMapDriver` | Phase B (B1) conditional-entropy map (thin CLI driver). |
| `scripts/research/phase_d_exit_grid.py` | `ResearchPhaseMaximumRecoverableExpectancyExit` | Phase D: maximum recoverable expectancy from exit/cost structure (thin CLI). |
| `scripts/research/phase_e_structural_asymmetry.py` | `ResearchProgramPhaseDriver` | Program 2 / Phase E1 (thin CLI driver). |
| `scripts/research/phase_s_selection_effect.py` | `ResearchPhaseDoesSpineRETESTSelection` | Phase S1: does the spine's RETEST selection carry edge under the governing truth standard?. |
| `scripts/research/promotion_dryrun.py` | `ResearchODLG3ProofGoverned` | ODL-G3a/b proof + governed-promotion dry-run (SCRATCH registry, never the real one). |
| `scripts/research/qualify_carry.py` | `ResearchProgramCarryBasisSignalCross` | Program 6: carry/basis as a signal on cross-sectional spot dispersion — thin CLI. |
| `scripts/research/qualify_cross_sectional.py` | `ResearchProgramCrossSectionalRelativeValue` | Program 5: cross-sectional relative-value (dispersion) — thin CLI. |
| `scripts/research/qualify_fx_metals.py` | `ResearchRunGateFirstUniverse` | "Run the Gate First" on the FX universe (thin CLI). |
| `scripts/research/qualify_harvest.py` | `ResearchProgramCarryHARVESTFundingCashflow` | Program 6b: carry HARVEST (funding cashflow + price/basis) — thin CLI. |
| `scripts/research/qualify_htf.py` | `ResearchProgramHigherTimeframeQualification` | Program 3: higher-timeframe (H1/H4) M4 qualification (thin CLI). |
| `scripts/research/qualify_interpreter.py` | `ResearchProveInterpreterChainEnd` | prove the Interpreter chain end-to-end on REAL data. |
| `scripts/research/qualify_m5_straddle.py` | `ResearchStageEconomicGateProgramStraddle` | Stage-2 economic gate for the Program-9 straddle (thin CLI). |
| `scripts/research/qualify_majors.py` | `ResearchRunGateFirstCrossInstrument` | "Run the Gate First": cross-instrument M4 qualification (thin CLI). |
| `scripts/research/qualify_regime_conditioning.py` | `ResearchProgramDriverResearch` | Program 4 driver (thin CLI). |
| `scripts/research/qualify_regime_transition.py` | `ResearchProgramDriverResearch_1` | Program 4b driver (thin CLI). |
| `scripts/research/qualify_shape_xauusd.py` | `ResearchProgramSemanticMarketShapeHypothesis` | Program 11 (B1): the semantic Market-Shape hypothesis through the unchanged M4 gate on the XAUUSD frozen candidate. |
| `scripts/research/qualify_transitions.py` | `ResearchStageEconomicGateProgramTransition` | Stage-2 economic gate for the Program-4b transition consumer (thin CLI). |
| `scripts/research/qualify_weekly_sweep.py` | `ResearchProgramRunGateFirstWeekly` | Program 8: "Run the Gate First" on the weekly CRT-sweep ontology (FX). |
| `scripts/research/qualify_xauusd.py` | `ResearchNONPROMOTABLEResearchPassCertified` | thin, NON-PROMOTABLE M4 research pass on the certified XAUUSD corpus (ERP T1). |
| `scripts/research/qualify_zone_topk.py` | `ResearchMeasureG001EngineRunner` | measure ΔG001 of the engine_runner.zone_gate knobs (top_k / cluster_min_n / cluster_spread_max) across crypto majors. |
| `scripts/research/rc003_distinct_object.py` | `ResearchDirectionalContractViolationBarsDistinct` | are the directional-contract-violation bars a distinct object at all?. |
| `scripts/research/rerun_xau_metals_m4.py` | `ResearchRunXauMetalsProtocolFrozen` | Re-run M4 only for xau_metals_protocol_v1 from frozen units_scored.jsonl. |
| `scripts/research/rr_kill_test_clean_l3.py` | `ResearchPreregisteredFREEZECERTIFICATE` | preregistered under RR_L1_FREEZE_CERTIFICATE. |
| `scripts/research/rr_l2_feature_truth.py` | `ResearchFeatureMaterializationSIGNEDFreezeCertificate` | Feature truth materialization under a SIGNED L1 freeze certificate. |
| `scripts/research/rr_l3_label_generation.py` | `ResearchLabelGenerationSIGNEDFreezeCOMPLETE` | Label generation under SIGNED L1 freeze + COMPLETE L2 feature matrix. |
| `scripts/research/rr_l4_research_execution.py` | `ResearchExecutionCompositionGateSIGNED` | Research execution composition gate under SIGNED L1 + L2 + L3. |
| `scripts/research/rr_shadow_value.py` | `ResearchTrackKILLTESTREADDoes` | Track 4 KILL-TEST (READ-ONLY): does the RR model have ANY economic value?. |
| `scripts/research/run_crt_state_on_mt5_xauusd.py` | `ResearchRunCRTStateResolverFresh` | Run CRT State Resolver on fresh MT5 XAUUSD data. |
| `scripts/research/run_envelope_shadow_weight0.py` | `ResearchBatchShadowLogEnvelopePredictions` | batch shadow log of Envelope predictions (weight 0). |
| `scripts/research/run_evidence_layer.py` | `ResearchRunEvidence` | Thin CLI. |
| `scripts/research/run_h_g001_001_sweep_veto.py` | `FilteringSpine` | Liquidity Sweep Veto on XAUUSD (H-G001-001 / 001b). |
| `scripts/research/run_h_msip_001.py` | `BarRec` | EXPLORATORY_RESEARCH only (note: path stem 'run_h_msip_001' vs content focus 'BarRec'). |
| `scripts/research/run_h_msip_002.py` | `ResearchMatchAttritionEstimandRobustnessEXPLORATORY` | match attrition & estimand robustness (EXPLORATORY_RESEARCH). |
| `scripts/research/run_model_offline.py` | `ResearchTriggerOneModelHistoricalOHLCV` | Trigger one model on historical OHLCV (OBSERVATION_ONLY). |
| `scripts/research/run_xau_metals_protocol_v1.py` | `FixedUsdCostAdapter` | Execute frozen **xau_metals_protocol_v1** end-to-end (P0–P7). |
| `scripts/research/run_xauusd_all_models_report.py` | `ResearchRunEveryCataloguedModelData` | Run every catalogued model on data/mt5/XAUUSD_M15.csv and write a report. |
| `scripts/research/shape_statistics_survey.py` | `ResearchHistoricalStatistics` | CLI wrapper for the Historical Statistics layer. |
| `scripts/research/smc_feature_month_extract.py` | `ResearchSMCSmartMoneyConceptsFeature` | SMC (smart-money-concepts) feature spot-validation for the Monthly TradingView <-> Active Production Semantic Comparison Report. |
| `scripts/research/smc_visual_verification.py` | `Check` | close report row 8's open item on the SMC features. |
| `scripts/research/story_library_build.py` | `ResearchGenerateERPMarketSTORYGolden` | generate the ERP market-STORY golden library (P1 slice). |
| `scripts/research/trace_geometry.py` | `ResearchDESCRIPTIVEGeometryMathematicalTraceCorpus` | DESCRIPTIVE geometry over the Mathematical Trace Corpus (ERP). |
| `scripts/research/trace_knn.py` | `ResearchDESCRIPTIVESimilarityGraphTraceGeometry` | DESCRIPTIVE k-NN similarity graph over the Trace Geometry (ERP). |
| `scripts/research/trace_sweep_geometry.py` | `GeometryStats` | Engine vs Pipeline Research-only diagnostic (note: path stem 'trace_sweep_geometry' vs content focus 'GeometryStats'). |
| `scripts/research/trace_zone_gate_xauusd.py` | `ResearchRunTrainedZoneGateXAUUSD` | run trained ZoneGate on XAUUSD_M15 and trace IN/OUT. |
| `scripts/research/train_envelope_offline.py` | `ResearchENVOFFLINETRAINMultiHead` | CLI: ENV_OFFLINE_TRAIN_V1 multi-head Envelope offline train (research only). |
| `scripts/research/transition_information.py` | `ResearchStageInformationGateProgramResearch_1` | Stage-1 information gate for Program 4b/4c/4d (thin CLI). |
| `scripts/research/tv_engine_odds.py` | `ResearchDeduplicatedEngineTradingAgreementOdds` | deduplicated engine-vs-TradingView agreement odds for the one-month XAUUSD corpus. |
| `scripts/research/tv_structure_comparison.py` | `ResearchEngineResolverTradingLLMNarration` | engine vs resolver vs TradingView vs LLM narration, per shot. |
| `scripts/research/validate_crt_state_resolver.py` | `ResearchCRTStateResolverValidationValidates` | CRT State Resolver Validation Script Validates the config-driven CRT state resolver against real market data. |
| `scripts/research/validate_fm030_bands.py` | `ResearchBehavioralValidationBandThresholds2` | CLI for behavioral validation of FM-030 band thresholds (A2a). |
| `scripts/research/validate_oracle_harness.py` | `ResearchStageHARDGATEOracleProgram` | Stage 0.5 HARD GATE for the oracle program. |
| `scripts/research/vcrt_remeasure_v2.py` | `ResearchRunSealedVisualCRTMeasurement_1` | run a sealed Visual CRT measurement contract. |
| `scripts/research/verify_m5_resample_parity.py` | `ResearchProgramCorpusLevelResamplerValidation` | Program-9 corpus-level resampler validation (M1 gate). |
| `scripts/research/visual_state_questions.py` | `ResearchFrozenQuestionTextEngineVisual` | Frozen question text + engine-to-visual maps for visual CRT state fidelity. |
| `scripts/research/visual_state_sample.py` | `ResearchReadSAMPLERRENDERERVisualCRT` | Read-only SAMPLER + RENDERER for the visual CRT state-fidelity test. |
| `scripts/research/visual_state_score.py` | `ResearchReadSCORERVisualCRTState` | Read-only SCORER for the visual CRT state-fidelity test. |
| `scripts/research/xauusd_episode_coverage_census.py` | `ResearchCoverageCensusReconstructedXAUUSDSemantic` | Coverage census over reconstructed XAUUSD semantic episodes. |
| `scripts/research/xauusd_episode_semantic_reconstruction.py` | `ResearchFirstSemanticMarketReconstructionMeaningful` | Source-first semantic market reconstruction of meaningful XAUUSD M15 episodes. |
| `scripts/research/xauusd_gaussian_econ_ledger.py` | `BarResearch_1` | Phase E1 Economic ledger on E0 scored units (pre-registered arms) (note: path stem 'xauusd_gaussian_econ_ledger' vs content focus 'Bar'). |
| `scripts/research/xauusd_gaussian_econ_units.py` | `ResearchPhaseJournalAlignedScoredEconomic` | Phase E0 Build journal-aligned **scored economic units** for the XAUUSD Gaussian NB. |
| `scripts/research/xauusd_gaussian_m4_qualify.py` | `ResearchPhaseRunQualificationGateGates` | Phase E2 Run M4 QualificationGate (gates 1–7) on E1 ledger arms for the XAUUSD Gaussian. |
| `scripts/research/xauusd_mt5_cost_calibration.py` | `ResearchZONEDiagnosticExtractRealSpread` | ZONE-X O-1 diagnostic: extract real spread/commission/slippage/swap for XAUUSD from a locally running MT5 terminal. |
| `scripts/research/xauusd_mt5_cost_seed_stops.py` | `ResearchDEMOHelperZONEPlaceNear` | DEMO-ONLY helper for ZONE-X O-1: place near-market STOP orders on XAUUSD so `extract_slippage` can measure stop-order fill vs requested price. |
| `scripts/research/xauusd_price_cost_trace.py` | `ResearchTracePriceMovementCostLedger` | Trace **price movement** vs **cost ledger** for XAUUSD economic units. |
| `scripts/research/zone_gate_threshold_sweep.py` | `ResearchThresholdSweepZoneGateScores` | Threshold sweep over zone_gate scores.jsonl (no re-score). |
| `scripts/research/zone_label_audit.py` | `ResearchDriverPhaseZoneGateLabel` | thin driver for the F-041B Phase-5 ZoneGate label audit. |
| `scripts/research/zone_x_o4_gap_study.py` | `StopEvent` | DESCRIPTIVE gap penalty study (path (a) residual work). |

### `scripts/training/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/training/_write_hashes_closure_narrative.py` | `TrainingOneShotEmbedConversationWalkthrough` | One-shot: embed conversation walkthrough into HASHES_AND_CLOSURE.json. |
| `scripts/training/auto_tuner.py` | `ResultTraining` | Auto-Tuner (Ultron Phase-6 / Quant Research Infrastructure). |
| `scripts/training/auto_tuner_gemini_gate.py` | `ResultTraining_1` | Auto-Tuner with Gemini LLM gate (Ultron Phase-6 / Quant Research Infrastructure). |
| `scripts/training/auto_tuner_multi.py` | `ResultTraining_2` | Multi-Instrument Deterministic Optimizer (Ultron Phase-7) (note: path stem 'auto_tuner_multi' vs content focus 'ResultStore'). |
| `scripts/training/build_stage1_dataset.py` | `TrainingEntryPointStageDatasetBuilder` | CLI entry point for the Stage-1 Truth Dataset Builder. |
| `scripts/training/phase5_calibration.py` | `TradeDataset` | ╔══════════════════════════════════════════════════════════════════════╗ ║ CRT ENGINE -- PHASE-5: GAUSSIAN RECALIBRATION (v5 -- unified) ║ ║ ║ ║ SINGLE TRAINING VALIDATION SCRIP... |
| `scripts/training/show_xauusd_gaussian_promotion.py` | `TrainingReadGaussianRegistryJsonOptional` | Read gaussian_registry.json (+ optional train journal / LATEST manifest) and print whether the XAUUSD Gaussian NB is promoted/active. |
| `scripts/training/train_bitnet.py` | `TrainingTrainsModelJsonLegacyInput` | Trains model.json (legacy 6-input BitNet) from historical CSV data. |
| `scripts/training/train_bitnet_contract_c.py` | `TrainingCONTRACTBitNetTrainerSpec` | Thin CLI for CONTRACT-C BitNet trainer (Spec R1). |
| `scripts/training/train_gaussian_xauusd.py` | `BarTraining` | Train a GaussianNB model on the Phase-1 frozen XAUUSD corpus, then evaluate on the trailing 2-month window (same window as prior observation runs). |
| `scripts/training/train_pipeline.py` | `TrainingTrainPipeline` | thin wrapper only. |
| `scripts/training/train_rr_model.py` | `TrainingTrainPatternMinerModelExisting` | Train the RR Pattern Miner model from an existing RR dataset. |
| `scripts/training/train_trade_net_v2.py` | `TrainingHeadSurvivalClassifierLiveCanonical` | 3-head survival classifier on the **live** canonical feature vector (``CANONICAL_FEATURE_DIM`` / schema v4.0 = 39 dims). |

### `src/bitnet/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/bitnet/__init__.py` | `BitnetApi` | bitnet/ BitNet Parameter Range Discovery Engine. |
| `src/bitnet/_smoke_test.py` | `BitnetRunBitnetSmokeTest` | run with: py bitnet/_smoke_test.py. |
| `src/bitnet/adapters.py` | `BitNetPredictionAdapters` | Consumer-facing BitNet IAdapter implementations emitting Prediction only. |
| `src/bitnet/backbones.py` | `BitNetModelBackbones` | BitNet neural backbone implementations including LegacyMLPBackbone. |
| `src/bitnet/bitnet_inference.py` | `BitNetInferenceRuntime` | BitNet inference runtime path. |
| `src/bitnet/bitnet_registry.py` | `BitNetModelRegistry` | Registry of BitNet model artifacts and versions. |
| `src/bitnet/bitnet_runner.py` | `BitNetTrainInferRunner` | BitNet training/inference runner. |
| `src/bitnet/composition.py` | `SupportsAdapter` | IBitNetModel composition root: Encoder → Backbone → Heads → Adapter. |
| `src/bitnet/contract_c_trainer.py` | `BitnetCONTRACTTrainerBitLinearResidual` | CONTRACT-C trainer for BitLinear residual family (Spec R1). |
| `src/bitnet/defaults.py` | `BitnetVersionedNumericDefaultsBitNet` | Versioned numeric defaults for BitNet backbone family (Spec v1.2.1 L2). |
| `src/bitnet/encoders.py` | `BitNetFeatureEncoders` | BitNet feature encoders including Legacy6Encoder. |
| `src/bitnet/forward_tester.py` | `ForwardTesterOutSample` | Forward (out-of-sample) validation for zone registry. |
| `src/bitnet/heads.py` | `BitnetConfidenceSigmoidHeadIHeads` | IHeads implementations. |
| `src/bitnet/label_contracts.py` | `BitnetVersionedBitNetLabelDefinitions` | Versioned BitNet label definitions (CONTRACT-C). |
| `src/bitnet/layers.py` | `BitnetPureNumericPrimitivesBitNet` | Pure numeric primitives for BitNet runtime (no I/O). |
| `src/bitnet/model_bundle.py` | `BitnetWriteValidateCONTRACTModelBundle` | Write / validate CONTRACT-C model.bundle packages (Spec v1.2.4). |
| `src/bitnet/model_contract.py` | `BitnetSchemaBitnet` | schema v3 ("bitnet_v3"). |
| `src/bitnet/population_label_audit.py` | `BitnetGovernedPopulationLabelBalanceAudit` | Governed population + label balance audit (read-only; does NOT modify CONTRACT-C). |
| `src/bitnet/r25_kill_test.py` | `BitnetBitNetKillTestHarness` | BitNet R2.5 kill-test harness (Spec v1.2.6). |
| `src/bitnet/runtime_types.py` | `BitNetRuntimeTypeContracts` | Runtime type contracts such as FeatureIdentity for BitNet inference. |
| `src/bitnet/stability_checker.py` | `StabilityCheckerChecksZone` | Checks zone stability across temporal data splits. |
| `src/bitnet/zone_cosine_searcher.py` | `BitNetSearchEngine` | Zone Cosine Searcher Searches for closest matching zone vectors using cosine similarity. |
| `src/bitnet/zone_validator.py` | `ZoneValidatorValidatesCandidate` | Validates candidate zones against minimum quality criteria. |

### `src/cognitive/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/cognitive/__init__.py` | `CognitiveApi` | Module at src/cognitive/__init__.py. |
| `src/cognitive/cognitive_bus.py` | `CognitiveDecisionSnapshotAsynchronousCognitiveProcessing` | Asynchronous cognitive processing bus. |

### `src/data_ingestion/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/data_ingestion/__init__.py` | `DataIngestionApi` | Module at src/data_ingestion/__init__.py. |
| `src/data_ingestion/clock_detector.py` | `DataIngestionADVISORYEvidenceHumanClock` | ADVISORY evidence for a human clock review. |
| `src/data_ingestion/clock_registry.py` | `ClockRecord` | declared, human-reviewed clock provenance for OHLCV corpora. |
| `src/data_ingestion/corpus_gate.py` | `CorpusAdmissionGate` | Gate deciding whether market corpora may be used for research/runtime. |
| `src/data_ingestion/dataset_integrity.py` | `DatasetDecision` | whole-dataset SEQUENCE integrity (pre-flight gate). |
| `src/data_ingestion/dataset_registry.py` | `DatasetAdmissionRegistry` | Registry and admission gate for datasets entering the corpus. |
| `src/data_ingestion/historical_fetcher.py` | `HistoricalFetcherMultiPair` | Multi-pair OHLCV data ingestion into TimescaleDB. |
| `src/data_ingestion/ohlcv_schema.py` | `OhlcvSchemaValidator` | OHLCV schema and integrity validation for corpus admission. |
| `src/data_ingestion/session_autoderive.py` | `DataIngestionLearnProviderTradableSession` | learn a provider's tradable session from the data itself. |
| `src/data_ingestion/xauusd_phase1_candidate.py` | `Phase1CandidateBinding` | fail-closed identity verification (note: path stem 'xauusd_phase1_candidate' vs content focus 'Phase1CandidateBinding'). |

### `src/expansion/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/expansion/__init__.py` | `ExpansionApi` | controlled trade frequency scaling. |
| `src/expansion/config_mutator.py` | `ConfigMutatorExpansion` | Defines ConfigMutator. |
| `src/expansion/evaluator.py` | `EvaluatorExpansion` | Defines Evaluator. |
| `src/expansion/expansion_engine.py` | `ExpansionEngineSaveExpansionConfigs` | Defines ExpansionEngine; exposes save_expansion_configs. |
| `src/expansion/llm_pattern_extractor.py` | `ExpansionLlmPatternExtractorExtractExpansion` | exposes extract_expansion_plan, save_expansion_plan. |
| `src/expansion/policy_schema.py` | `ExpansionCandidate` | Defines ExpansionCandidate, ExpansionPlan, ExpansionStep (note: filename suggests policy_schema; content centers on ExpansionCandidate). |

### `src/llm_research/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/llm_research/__init__.py` | `LlmResearchApi` | offline pattern extraction → policy generation → forward validation. |
| `src/llm_research/evaluator.py` | `ResearchEvaluator` | Defines ResearchEvaluator; exposes save_evaluation. |
| `src/llm_research/forward_tester.py` | `ForwardTestReport` | Defines ModeResult, ForwardTestReport; exposes run_forward_test, save_report. |
| `src/llm_research/pattern_extractor.py` | `ExtractedPolicy` | Defines ExtractedPolicy; exposes extract_patterns, save_policy, load_policy (note: filename suggests pattern_extractor; content centers on ExtractedPolicy). |
| `src/llm_research/policy_builder.py` | `PolicyEngine` | Defines PolicyEngine. |

### `src/msip/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/msip/__init__.py` | `MsipApi` | MSIP shadow continuous market-state package (OBSERVATION_ONLY). |
| `src/msip/disagreement.py` | `DisagreementRecordOptionalShadow` | Optional shadow vs CRT observation disagreement taxonomy (telemetry only). |
| `src/msip/interpretation_config.py` | `Disabled` | `msip_shadow` section only (note: path stem 'interpretation_config' vs content focus 'Disabled'). |
| `src/msip/isolation.py` | `MsipImportMutationIsolationPolicyMSIP` | Import / mutation isolation policy for the MSIP shadow package. |
| `src/msip/market_state_vector.py` | `MsipMarketStateVector` | MSIP market-state vector representation. |
| `src/msip/shadow_emitter.py` | `MsipShadowEmitter` | Emits MSIP shadow market-state interpretation events. |

### `src/multi_llm/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/multi_llm/__init__.py` | `MultiLlmApi` | coordination layer for the hand-operated DeepSeek/Gemini/ChatGPT/Claude pipeline. |
| `src/multi_llm/context_pack.py` | `MultiLlmBoundedUploadReadyContext` | bounded, upload-ready context for ONE task (never the whole codebase). |
| `src/multi_llm/discussion.py` | `MultiLlmReconstructREWINDMultiLLM` | reconstruct and REWIND the multi-LLM discussion (view-only time-travel). |
| `src/multi_llm/tokens.py` | `MultiLlmHonestTokenEstimateExternal` | honest token *estimate* (no external tokenizer dependency). |
| `src/multi_llm/turn_ledger.py` | `TurnRecord` | append-only, no-loss record of every multi-LLM turn. |

### `src/research/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/research/__init__.py` | `ResearchApi` | behavior-agnostic research platform. |
| `src/research/adapters/__init__.py` | `ResearchAdaptersApi` | bridges that let the isolated research harness consume the live spine. |
| `src/research/adapters/shape_signal_source.py` | `ShapeSignalProtoPrecomputeMarketShape` | precompute MarketShape directional signals per bar (Program 11 / B1). |
| `src/research/adapters/spine_signal_source.py` | `SpineEntry` | run the production CRT spine, harvest its entries. |
| `src/research/adapters/structural_event_source.py` | `StructuralEventPhaseHarvester` | Phase E1 harvester: the full CRT structural-event population. |
| `src/research/band_validation.py` | `BandValidationParamsCandidateThresholds` | do candidate band thresholds correspond to STABLE BEHAVIORAL REGIMES?. |
| `src/research/candle_state/__init__.py` | `ResearchCandleStateApi` | non-directional candle-state encoding + multi-timeframe conjunction. |
| `src/research/candle_state/encoder.py` | `CandleStateEncoderWindowDiscrete` | CandleStateEncoder: a candle window -> discrete state + continuous features. |
| `src/research/candle_state/info_robustness.py` | `ResearchStageInformationRobustnessKernelsFROZEN` | Stage-1 information-robustness kernels (FROZEN thresholds in pre-reg). |
| `src/research/candle_state/m5_incremental.py` | `ResearchProgramStageKernelsBaseKeys` | Program-9 Stage-1 kernels: M5-base keys + the incremental gate. |
| `src/research/candle_state/mtf_conjunction.py` | `MultiTFConjunctionBuilder` | MultiTFConjunctionBuilder: M15 window -> {M15,H1,H4} state key. |
| `src/research/candle_state/reporting.py` | `ResearchREPORTINGTradeMetricsWinRate` | REPORTING-ONLY trade metrics (win-rate, losing streak, rolling-10). |
| `src/research/candle_state/transition_target.py` | `ResearchNonDirectionalFORWARDTargetLabelers` | non-directional FORWARD target labelers (Stage-1 only). |
| `src/research/clean_labels/__init__.py` | `ResearchCleanLabelsApi` | Clean-label builders for TradeNet + EnvelopeNet (GATE-L / ENV-L research tooling). |
| `src/research/clean_labels/builder.py` | `ResearchSharedCleanLabelBuilderTrade` | Shared clean-label builder: TradeNet Bernoulli heads + Envelope continuous targets. |
| `src/research/clean_labels/protocol.py` | `ResearchFrozenExperimentIdentityDualTrade` | Frozen experiment identity for the dual TradeNet + EnvelopeNet clean-label builder. |
| `src/research/cli.py` | `ResearchEntrypointResearchHarness` | thin entrypoint for the research harness. |
| `src/research/conditional_entropy_grid.py` | `BarFeatures` | Phase B (B1): where, if anywhere, does next-direction become conditionally predictable?. |
| `src/research/config.py` | `ResearchConfigResearchHarness` | ResearchConfig: the single source of truth for the research harness. |
| `src/research/contracts.py` | `ResearchHypothesisFrozenInterfacesEdge` | frozen interfaces for the Edge Discovery Program (note: path stem 'contracts' vs content focus 'Hypothesis'). |
| `src/research/controls/__init__.py` | `ResearchControlsApi` | the platform's immune system. |
| `src/research/controls/always_long.py` | `AlwaysLongAntiDrift` | the anti-drift control. |
| `src/research/controls/random_baseline.py` | `RandomBaselineNullControls` | null controls: random entries. |
| `src/research/costs.py` | `ResearchCostModelConservativeFlatFalsification` | conservative flat cost model for the falsification phase (M1–M6) (note: path stem 'costs' vs content focus 'CostModel'). |
| `src/research/cross_sectional.py` | `Panel` | Program 5: cross-sectional relative-value (dispersion) measurement. |
| `src/research/envelope_offline/__init__.py` | `ResearchEnvelopeOfflineApi` | Envelope offline research training (ENV_OFFLINE_TRAIN_V1). |
| `src/research/envelope_offline/shadow.py` | `ResearchENVSHADOW` | ENV_SHADOW_W0_V1. |
| `src/research/envelope_offline/train.py` | `HeadMetrics` | ENV_OFFLINE_TRAIN_V1. |
| `src/research/episode_agreement.py` | `AgreementTypedObject` | typed AGREEMENT object (O14): fold over Phase 2B propositions. |
| `src/research/episode_propositions.py` | `ResearchPropositionTypedEventPropositions` | typed same-event propositions (research shadow). |
| `src/research/episodes/__init__.py` | `ResearchEpisodesApi` | Opportunity Episode research substrate (protocol OE_L1). |
| `src/research/episodes/builder.py` | `ResearchCandlesEntryGeometryObservationTimeline` | candles + entry geometry → observation timeline. |
| `src/research/episodes/events.py` | `ResearchEventEngineSparseSemanticMilestones` | sparse semantic milestones DERIVED from an episode timeline (note: path stem 'events' vs content focus 'EventEngine'). |
| `src/research/episodes/flat.py` | `ResearchOneRowEpisodeTimestep` | one row per (episode, timestep). |
| `src/research/episodes/policy.py` | `LabelSet` | labels derived from an episode under a chosen exit policy. |
| `src/research/episodes/projectors/__init__.py` | `EpisodesProjectorsApi` | different sources, one canonical schema. |
| `src/research/episodes/projectors/detection.py` | `ResearchOpportunitiesJsonlDETECTIONSTREAMEpisodes` | opportunities.jsonl → DETECTION_STREAM episodes. |
| `src/research/episodes/projectors/spine.py` | `ResearchAcceptedTradeLedgerSPINETRADE` | the accepted-trade ledger → SPINE_TRADE episodes. |
| `src/research/episodes/protocol.py` | `ResearchFrozenContractOpportunityEpisodeResearch` | Frozen contract for the Opportunity Episode research substrate. |
| `src/research/episodes/query.py` | `EpisodeQuerySelectionsEpisodes` | selections over episodes + LabelSets + EventSets (note: path stem 'query' vs content focus 'EpisodeQuery'). |
| `src/research/episodes/schema.py` | `Observation` | OpportunityEpisode canonical types (protocol OE_L1) (note: path stem 'schema' vs content focus 'Observation'). |
| `src/research/episodes/store.py` | `ResearchCanonicalSerialization` | canonical serialization + I/O. |
| `src/research/episodes/tensors.py` | `ResearchTensorBatchViewsSequenceModels` | [N, T, D] views for sequence models (note: path stem 'tensors' vs content focus 'TensorBatch'). |
| `src/research/evidence/__init__.py` | `ResearchEvidenceApi` | Queryable evidence layer over the XAUUSD parquet projections. |
| `src/research/evidence/__main__.py` | `ResearchEvidenceOutResultsResearch` | python -m research.evidence --out results/research/parquet_evidence_layer. |
| `src/research/evidence/asymmetry_contract.py` | `ResearchTimestampMFEHoldout` | same-timestamp ΔMFE holdout. |
| `src/research/evidence/atlases.py` | `ResearchThreeAtlasesBarDirectionOutcome` | Three atlases over the bar×direction outcome surface. |
| `src/research/evidence/catalog.py` | `Surface` | Grain catalog for the XAUUSD parquet evidence layer. |
| `src/research/evidence/context_attribution.py` | `ResearchDoesContextFamilyAddValue` | does any context family add value beyond CRT state alone?. |
| `src/research/evidence/driver.py` | `ResearchLoadFourProjectionsEmitEvidence` | Load the four projections and emit an evidence report. |
| `src/research/evidence/magnitude_prior.py` | `ResearchTrendBiasMagnitudeTimePrior` | trend_bias as magnitude/time prior on a given side. |
| `src/research/evidence/mother_range_prior.py` | `ResearchSparseMotherRangeInsideSignal` | sparse mother-range inside signal x FM-054 trend prior. |
| `src/research/evidence/queries.py` | `ResearchNamedEvidenceQueriesColumnMaps` | Named evidence queries over column maps. |
| `src/research/evidence/records.py` | `ResearchEvidenceRecordMeasurementsPredictions` | measurements, not predictions (note: path stem 'records' vs content focus 'EvidenceRecord'). |
| `src/research/evidence/rnet_overlay.py` | `ResearchNetSizeOverlayEntry` | y_R_net size overlay on independent entry. |
| `src/research/evidence/run_close_out.py` | `ResearchSharedCloseOutEverySealed` | the shared close-out every sealed-contract experiment runs. |
| `src/research/evidence/visual_crt_prior.py` | `ResearchSparseVisualCRTEntriesTrend` | sparse Visual CRT entries x FM-054 trend prior. |
| `src/research/exit_grid.py` | `Entry` | Phase D pure core: SL/TP exit-geometry grid + the recoverable-value ceilings. |
| `src/research/experiment_spec.py` | `ResearchImmutableExecutionSpecificationResearchPlatform` | the immutable execution specification for the research platform. |
| `src/research/forensics.py` | `ResearchRootCauseAnalysisBehaviorLoses` | Layer-6 root-cause analysis: WHY a behavior loses under intrabar truth. |
| `src/research/goal_alignment.py` | `ResearchLoopG001AlignmentTarget` | Research-loop G001 alignment (target-strategy-architecture.md §13 item6 / §14.D "Expectancy/PF/DD/trades-per-month vs G001 reported every candidate"). |
| `src/research/hypotheses/__init__.py` | `ResearchHypothesesApi` | Behavior hypotheses. |
| `src/research/hypotheses/compression_box_straddle.py` | `CompressionBoxStraddleProgramStage` | Program-9 Stage-2 economic consumer (transition family). |
| `src/research/hypotheses/compression_breakout.py` | `CompressionBreakoutProgramStage` | Program-4b Stage-2 economic consumer (transition family). |
| `src/research/hypotheses/expansion_breakout.py` | `ExpansionBreakoutContinuationBehavior` | continuation behavior (hypothesis #1, NOT privileged). |
| `src/research/hypotheses/market_shape_hypothesis.py` | `ResearchMarketShapeHypothesisSemanticResearch` | the semantic Market-Shape layer as a research Hypothesis (P11/B1). |
| `src/research/hypotheses/mean_reversion.py` | `MeanReversionOPPOSITEBehavior` | the OPPOSITE behavior, shipped at M2 to prove no continuation bias. |
| `src/research/hypotheses/spine_hypothesis.py` | `ResearchSpineHypothesisProductionWrappedResearch` | the production spine, wrapped as a research Hypothesis. |
| `src/research/hypotheses/weekly_sweep_reversal.py` | `WeeklySweepReversalProgramEconomic` | Program 8 economic consumer of the weekly liquidity-sweep ontology. |
| `src/research/ic002_entry_evolution/__init__.py` | `ResearchIc002EntryEvolutionApi` | post-entry OHLCV trajectories (research only). |
| `src/research/ic002_entry_evolution/build_trajectories.py` | `ResearchOneFeaturePipelinePassSlice` | one FeaturePipeline pass, then slice. |
| `src/research/ic002_entry_evolution/evaluate_separation.py` | `ResearchEvaluationPathStaticBaselineTime` | IC-002 primary evaluation: path vs static baseline under time-ordered OOS. |
| `src/research/ic002_entry_evolution/io_util.py` | `ResearchLoadPreregJSONEntriesOHLCV` | Load prereg JSON, entries, OHLCV path resolution, save trajectory batches. |
| `src/research/ic002_entry_evolution/schema.py` | `TrajectoryBatch` | must match h-ic002 experiment definition JSON (note: path stem 'schema' vs content focus 'TrajectoryBatch'). |
| `src/research/ic003_shapes/__init__.py` | `ResearchIc003ShapesApi` | IC-003 trajectory shape library (research only). |
| `src/research/ic003_shapes/build_library.py` | `ResearchShapeLibraryTrajectoryBatches` | Build IC-003 shape library from IC-002 trajectory batches. |
| `src/research/ic003_shapes/schema.py` | `ResearchMatchIc003ExperimentDefinition` | match h-ic003 experiment definition (v1 scientific bar). |
| `src/research/ic003b_sequence_geometry/__init__.py` | `ResearchIc003BSequenceGeometry` | IC-003B sequence geometry shape library (research only). |
| `src/research/ic003b_sequence_geometry/build_all.py` | `ResearchOrchestrateArmsWriteArtifacts` | Orchestrate IC-003B arms S / T / C and write artifacts. |
| `src/research/ic003b_sequence_geometry/cluster_dtw.py` | `ResearchArmDTWMedoidsChannelPaths` | Arm T: DTW + k-medoids on 3-channel paths. |
| `src/research/ic003b_sequence_geometry/cluster_euclid.py` | `ResearchArmEuclideanLibraryPathSummary` | Arm S: Euclidean library on path-summary vectors (IC-003 v1 gates). |
| `src/research/ic003b_sequence_geometry/continuum.py` | `ResearchArmPCAContinuumDiagnostic` | Arm C: PCA continuum diagnostic. |
| `src/research/ic003b_sequence_geometry/dtw.py` | `ResearchDTWSakoeChibaBandArm` | Deterministic DTW with Sakoe-Chiba band (Arm T). |
| `src/research/ic003b_sequence_geometry/schema.py` | `ResearchMatchIc003BExperiment` | match h-ic003b experiment definition. |
| `src/research/ic003b_sequence_geometry/summarize.py` | `ResearchArmPathSummaryVectorizationStats` | Arm S: path-summary vectorization (7 stats × D). |
| `src/research/indicators.py` | `ResearchSmallDependencyLightTechnicalHelpers` | small, dependency-light technical helpers for hypotheses/controls. |
| `src/research/measurement/__init__.py` | `ResearchMeasurementApi` | no-lookahead forward-walk + edge aggregation. |
| `src/research/measurement/bootstrap.py` | `ResearchPercentileBootstrapConfidenceInterval` | deterministic percentile bootstrap confidence interval. |
| `src/research/measurement/forward_walk.py` | `AdverseFill` | no-lookahead forward simulation of a Signal. |
| `src/research/measurement/metrics.py` | `ResearchEdgeAggregatorTurnListOutcomes` | EdgeAggregator: turn a list of Outcomes into an EdgeReport (note: path stem 'metrics' vs content focus 'EdgeAggregator'). |
| `src/research/measurement/mt00.py` | `Probe` | the E-MT-00 clean-path runner (MEASUREMENT_CONTRACT.md §2, E0–E2). |
| `src/research/model_runners/__init__.py` | `ResearchModelRunnersApi` | Per-model historical offline runners (OBSERVATION_ONLY). |
| `src/research/model_runners/adapters/__init__.py` | `ModelRunnersAdaptersApi` | call production engines only. |
| `src/research/model_runners/adapters/bitnet.py` | `BitNetAdapterHardReject` | BitNet hard-reject gate adapter (off-spine observe; does not flip use_bitnet). |
| `src/research/model_runners/adapters/crt_score.py` | `CrtScoreAdapterEnginesEngine` | engines.crt_engine.compute → compute_scores. |
| `src/research/model_runners/adapters/crt_state_machine.py` | `CrtStateMachineAdapterFullCRT` | Full CRTEngine state machine on sequential candles (not fusion crt_score). |
| `src/research/model_runners/adapters/decision.py` | `DecisionAdapterFusionEvidence` | fusion evidence -> DecisionEngine.evaluate. |
| `src/research/model_runners/adapters/dual_engine.py` | `RegimeAdapter` | Stage-1 dual-engine adapters: regime / trap / breakout (A1-A3). |
| `src/research/model_runners/adapters/envelope_net.py` | `EnvelopeNetAdapterRequiresArtifact` | requires --artifact (bundle dir or envelope_bundle.json). |
| `src/research/model_runners/adapters/execution_plan.py` | `ExecutionPlanAdapterFullCandle` | the full candle -> executable-trade chain (note: path stem 'execution_plan' vs content focus 'ExecutionPlanAdapter'). |
| `src/research/model_runners/adapters/fusion_compute.py` | `FusionComputeAdapterComposeFour` | Compose four live engines → FusionEngine.compute (no DecisionEngine). |
| `src/research/model_runners/adapters/gaussian.py` | `GaussianAdapterLiveHeuristicGaussianEngine` | Live HeuristicGaussianEngine adapter (spine gaussian slot). |
| `src/research/model_runners/adapters/gaussian_ml.py` | `GaussianMLAdapterImpl` | independent of gaussian_impl. |
| `src/research/model_runners/adapters/rr_polarity.py` | `RRPolarityAdapterLiveRREngine` | Live RREngine (candle polarity) adapter. |
| `src/research/model_runners/adapters/rr_trained.py` | `RRTrainedAdapterObserve` | observe-only (note: path stem 'rr_trained' vs content focus 'RRTrainedAdapter'). |
| `src/research/model_runners/adapters/tradenet.py` | `TradeNetAdapterObserveUNWIRED` | TradeNet v2 observe adapter (UNWIRED on spine; requires --artifact). |
| `src/research/model_runners/adapters/zone_gate.py` | `ZoneGateAdapterProductionCluster` | Production ZoneGate cluster scorer adapter. |
| `src/research/model_runners/contracts.py` | `ResearchModelContractAuditModelsPhase` | all audit models; phase marks implement status (note: path stem 'contracts' vs content focus 'ModelContract'). |
| `src/research/model_runners/envelope.py` | `RunRecord` | Output envelope schemas for model_runners (single serialization authority). |
| `src/research/model_runners/require_config.py` | `ResearchRequireConfigRequireKey` | single source of truth only. |
| `src/research/model_runners/runner.py` | `Run` | Orchestrate substrate × adapter → artifacts (OBSERVATION_ONLY) (note: path stem 'runner' vs content focus 'RunRequest'). |
| `src/research/model_runners/schema_resolver.py` | `ResolvedSchema` | Single live->trained feature-schema authority for model_runners (R1). |
| `src/research/model_runners/stats.py` | `ResearchPureSummaryStatsCollectedNumeric` | Pure summary stats over collected numeric arrays (no fill / no imputation). |
| `src/research/model_runners/substrate.py` | `BarContext` | Historical OHLCV + FeaturePipeline substrate (one load path). |
| `src/research/mother_range/__init__.py` | `ResearchMotherRangeApi` | Mother-range inside-close trade object (SEM-026). |
| `src/research/mother_range/__main__.py` | `ResearchMotherRangeOutResults` | python -m research.mother_range --out results/mother_range/mc_mrange_xauusd_m15_v1. |
| `src/research/mother_range/driver.py` | `ResearchPassMotherRangeMeasurement` | Single-pass mother-range measurement. |
| `src/research/mother_range/geometry.py` | `BarMotherRange` | t=0 mother-range inside-close geometry (SEM-026). |
| `src/research/mt5_cost_calibration.py` | `Status` | mt5_cost_calibration READ-ONLY MT5 broker cost extraction for XAUUSD (ZONE-X programme, item O-1). |
| `src/research/ohlcv_open_close_label.py` | `BarSnap` | BC-2 executable open-vs-close label scorer. |
| `src/research/ohlcv_probe_report.py` | `ProbeSnapshot` | Shared emission contract for OHLCV corpus-authority probes (BC-2, BC-4, ...). |
| `src/research/ohlcv_tick_attribution.py` | `ResearchResidualAttributionExplainsTickVolume` | BC-4 residual attribution: what explains tick_volume vs len(copy_ticks_range)?. |
| `src/research/ohlcv_volume_semantics.py` | `ResearchVolumeSemanticsScorerDoesMT` | BC-4 volume-semantics scorer: does MT5 `volume` count ticks?. |
| `src/research/oracle/__init__.py` | `ResearchOracleApi` | outcome-first (SEM-018) per-bar labelling under the SEM-017 exit geometry. |
| `src/research/oracle/exit_analysis.py` | `ResearchSEMExitCaptureDecompositionExit` | SEM-020 exit-capture decomposition: what any exit COULD achieve. |
| `src/research/oracle/exit_sweep.py` | `ResearchGeometryDynamicStopPolicySweep` | geometry x dynamic-stop-policy sweep over the dense bar universe. |
| `src/research/oracle/labeler.py` | `BarOracle` | Stage 1 of the profitable-entry oracle program (SEM-018) (note: path stem 'labeler' vs content focus 'Bar'). |
| `src/research/oracle/multi_tp_walk.py` | `OracleOutcome` | SEM-017 two-target partial-exit forward walk. |
| `src/research/oracle/reference_walker.py` | `ResearchDeliberatelyNaiveTwinMultiWalk` | deliberately naive twin of `multi_tp_walk`, for triangulation. |
| `src/research/oracle/scan.py` | `Partition` | effect sizes, controls and partitioning for the oracle pattern search (note: path stem 'scan' vs content focus 'Partition'). |
| `src/research/oracle/stop_policy.py` | `StopPolicySEMCausal` | SEM-019 causal dynamic stop policies for the two-target object. |
| `src/research/path/__init__.py` | `ResearchPathApi` | Program 10 (intrabar path) measurement layer. |
| `src/research/path/ambiguity_census.py` | `ResearchP1EventProgramPhase` | Program 10 / Phase 0A pure core: how often does the same-bar SL-before-TP tie-break actually fire, and what is the worst case it could cost? (note: path stem 'ambiguity_census' ... |
| `src/research/process_characterization.py` | `ProcessManifest` | statistical fingerprint of a raw OHLCV series (note: path stem 'process_characterization' vs content focus 'ProcessManifest'). |
| `src/research/process_diagnostics.py` | `ResearchProcessDiagnosticsSignificanceTestsPhase` | significance tests over the Phase-1 process fingerprint. |
| `src/research/provenance.py` | `ResearchVersionedRealismMethodStampsResearch` | versioned realism/method stamps for research artifacts. |
| `src/research/qualification.py` | `ResearchQualificationGateEdgeDiscoveryProgram` | M4 QualificationGate for the Edge Discovery Program. |
| `src/research/rc003_distinct_object/__init__.py` | `ResearchRc003DistinctObjectApi` | are the directional-contract-violation bars a distinct object at all?. |
| `src/research/rc003_distinct_object/driver.py` | `BarRc003DistinctObject` | executes the frozen pre-registration, nothing more (note: path stem 'driver' vs content focus 'Bar'). |
| `src/research/regime_conditioning.py` | `ResearchProgramConditioningHarnessNewMeasurement` | Program 4 conditioning harness (the only new measurement). |
| `src/research/registry.py` | `ResearchHypothesisPluginRegistryMirrorsSrc` | hypothesis plugin registry (mirrors src/agent/tool_registry.py). |
| `src/research/resample.py` | `ResearchCalendarOHLCVResamplerProgramHarness` | deterministic calendar OHLCV resampler (Program 3 harness; Program 9 adds the minute-grid "M15" rule so an M5 base can build the M5->{M15,H1,H4} ladder). |
| `src/research/runner.py` | `HypothesisEdgeReportRunner` | Deterministic hypothesis runner: stream candles, detect, forward-walk, emit EdgeReport. |
| `src/research/secondlow_v1/__init__.py` | `ResearchSecondlowV1Api` | canonical MT5 corpus + xlsx regression fixture. |
| `src/research/secondlow_v1/corpus.py` | `ResearchXAUUSDM15CorpusPaths` | XAUUSD M15 corpus paths for SECONDLOW research. |
| `src/research/secondlow_v1/depth_metrics.py` | `ResearchProductionDefaults` | not production defaults). |
| `src/research/secondlow_v1/detector.py` | `SecondLowEvent` | SECONDLOW-v1 purge detector (trading-day second_low_20d ladder). |
| `src/research/secondlow_v1/regime_metrics.py` | `ResearchLightweightVolatilityRegimeDescriptorsPurge` | Lightweight volatility regime descriptors at purge time (descriptive only). |
| `src/research/selection_effect.py` | `ResearchPhasePureCoreSpineRETEST` | Phase S1 pure core: the spine's RETEST selection effect. |
| `src/research/shape_statistics.py` | `ResearchShapeStatisticsBuilderSemanticPipeline` | Layer 6 of the semantic pipeline (roadmap Phase 5, statistics). |
| `src/research/structural_asymmetry.py` | `PathMeasure` | Program 2 / Phase E1 pure core: forward asymmetry of a structural-event population, measured PURELY (no exits, no RR, no expectancy). |
| `src/research/sujan_crt/__init__.py` | `ResearchSujanCrtApi` | Sujan nested veto chain (SEM-031). |
| `src/research/sujan_crt/__main__.py` | `ResearchSujanCRTOutResearch` | python -m research.sujan_crt --out docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1. |
| `src/research/sujan_crt/driver.py` | `ResearchSUJANXAUUSDM15Driver` | MC-SUJAN-XAUUSD-M15-V1 driver. |
| `src/research/sujan_crt/geometry.py` | `BarSujanCrt` | SEM-031 primitives: calendar parents, SP-001 sweep, SP-002 displacement, return, RR (note: path stem 'geometry' vs content focus 'Bar'). |
| `src/research/sujan_crt/score.py` | `ResearchSEMComparisonArm` | SEM-023 comparison arm. |
| `src/research/sujan_crt/vetoes.py` | `ResearchSujanCandidateSEMNestedVeto` | SEM-031 nested veto chain (note: path stem 'vetoes' vs content focus 'SujanCandidate'). |
| `src/research/sujan_manipulation/__init__.py` | `ResearchSujanManipulationApi` | Sujan manipulation detection, Phase 1 (SEM-033). |
| `src/research/sujan_manipulation/__main__.py` | `ResearchSEMPhase` | SEM-033 Phase-1 CLI. |
| `src/research/sujan_manipulation/bulk_proxy.py` | `RankedCandidate` | the bulk-candle proxy. |
| `src/research/sujan_manipulation/driver.py` | `ResearchSUJANMANIPULATIONRESEARCHPHASERun` | SUJAN_MANIPULATION_RESEARCH_PHASE_1 run driver (SEM-033). |
| `src/research/sujan_manipulation/geometry.py` | `ManipulationSide` | SUJAN_MANIPULATION_RESEARCH_PHASE_1 primitives (SEM-033) (note: path stem 'geometry' vs content focus 'ManipulationSide'). |
| `src/research/sujan_manipulation/label_page.py` | `ResearchCURATIONTOOLMeasurementInstrument` | a CURATION TOOL, not a measurement instrument. |
| `src/research/sujan_manipulation/parent.py` | `BarSujanManipulation` | still incomplete, now with an approved proxy (note: path stem 'parent' vs content focus 'Bar'). |
| `src/research/sujan_manipulation/parquet_check.py` | `ParquetCheckUnavailableCrossProxy` | Cross-check the proxy's CSV-derived magnitudes against the Parquet projection. |
| `src/research/sujan_manipulation/state.py` | `ManipulationRunner` | The Phase-1 state machine, implemented literally. |
| `src/research/synthetic/__init__.py` | `ResearchSyntheticApi` | deterministic market-STORY library (ERP P1 golden fixtures). |
| `src/research/synthetic/ontology.py` | `StoryOntologyLoaderSix` | loader + six-layer binder for the market-story ontology. |
| `src/research/synthetic/stories/__init__.py` | `SyntheticStoriesApi` | the Phase-A market-story library (4 active families). |
| `src/research/synthetic/stories/breakout.py` | `ResearchCompressionResolvesRangeBoundaryBreaks` | compression resolves; a range boundary breaks, expands, retests, then continues. |
| `src/research/synthetic/stories/liquidity_reversal.py` | `ResearchRestingLiquiditySweptPriceReverses` | resting liquidity swept, price reverses & reclaims (CRT golden path). |
| `src/research/synthetic/stories/range_rotation.py` | `ResearchBalancedRangeEdgesFadeMean` | balanced range; edges fade to the mean (CRT-quiescent), plus a failed break. |
| `src/research/synthetic/stories/trend_continuation.py` | `ResearchEstablishedTrendPullsBackRetest` | an established trend pulls back to a retest, then continues. |
| `src/research/synthetic/story_builder.py` | `ResearchTurnStorySpecIntendedProduced` | turn a StorySpec into an intended-vs-produced golden trace + six-layer binding. |
| `src/research/synthetic/story_registry.py` | `ResearchCollectionPointEveryRegisteredStory` | the single collection point for every registered StorySpec. |
| `src/research/synthetic/story_spec.py` | `PhaseBar` | frozen value objects for a deterministic market story. |
| `src/research/visual_crt/__init__.py` | `ResearchVisualCrtApi` | the Visual CRT trade object (SEM-012), Lane 1 geometry. |
| `src/research/visual_crt/controls.py` | `ResearchOOSSplitControlBenchmarksVCRT` | the OOS split and control benchmarks MC-VCRT-XAUUSD-M15-V1 declared. |
| `src/research/visual_crt/driver.py` | `BarVisualCrt` | Visual CRT ledger driver. |
| `src/research/visual_crt/geometry.py` | `PoolSweepEvent` | Visual CRT sweep + directional-displacement geometry (SEM-012). |
| `src/research/visual_crt/measure.py` | `ResearchRunSealedVisualCRTMeasurement` | run a sealed Visual CRT measurement contract end to end. |
| `src/research/visual_crt/pools.py` | `ResearchLiquidityPoolChartVisiblePools` | chart-visible liquidity pools for the Visual CRT trade object (SEM-012). |
| `src/research/visual_crt/retest.py` | `RetestEventArmPredicate` | Arm B retest predicate for the Visual CRT trade object (SEM-012 v2). |
| `src/research/weekly_sweep/__init__.py` | `ResearchWeeklySweepApi` | Program 8: weekly liquidity-sweep ontology (pure geometry, no-lookahead). |
| `src/research/weekly_sweep/weekly_range.py` | `WeeklyRangeProgramAccumulation` | Program 8: weekly accumulation range + sweep geometry. |
| `src/research/xau_metals_protocol.py` | `ResearchLoaderPureHelpersXauMetals` | Loader + pure helpers for **xau_metals_protocol_v1** (pre-registered). |
| `src/research/zone_label_audit.py` | `ZoneAudit` | F-041B Phase-5 ZoneGate label-provenance audit (MEASURE-ONLY). |
| `src/research/zone_mapping/__init__.py` | `ResearchZoneMappingApi` | pre-CRT geometry assignment (research tooling). |
| `src/research/zone_mapping/boundary_hypothesis_eval.py` | `ResearchGeometryBoundaryHypothesisTest` | Geometry-boundary hypothesis test. |
| `src/research/zone_mapping/build_corpus_zone_map.py` | `ResearchMapEveryBarCSVCorpus` | Map every bar of a CSV corpus with HistoricalZoneMapper and compute zone census. |
| `src/research/zone_mapping/collect_trade_opened_features.py` | `ResearchTradeOpenedFeatureSampleCollect` | Collect TRADE_OPENED-shaped feature dicts from a real XAUUSD CRT path. |
| `src/research/zone_mapping/crt_zone_crosstab.py` | `BarJointLabel` | relevance of geometry to CRT structure. |
| `src/research/zone_mapping/displacement_zone_event_study.py` | `DisplacementEvent` | Lead/lag event study: CRT DISPLACEMENT starts vs zone assignments. |
| `src/research/zone_mapping/gaussian_delta_gap_eval.py` | `ResearchCalibrationGapEvaluationMeasure` | calibration gap Δ = ML − H evaluation (measure-only). |
| `src/research/zone_mapping/gaussian_family_shadow_eval.py` | `GaussianShadowBar` | Gaussian family shadow measurement (H + ML via EngineRunner shadow_ml contract). |
| `src/research/zone_mapping/historical_zone_mapper.py` | `HistoricalZoneMapperEveryBar` | every-bar (or batch) zone cluster assignment. |
| `src/research/zone_mapping/rare_zone_context_filter_eval.py` | `ContextualSignal` | Context-filter experiment: rare-zone entry × CRT state at signal time. |
| `src/research/zone_mapping/rare_zone_detection_eval.py` | `SignalEvent` | Event-detection evaluation: rare-zone entry → CRT DISPLACEMENT within K bars. |
| `src/research/zone_mapping/rare_zone_fa_characterization.py` | `PathTaxonomy` | False-alarm characterization for rare-zone → DISPLACEMENT detection. |
| `src/research/zone_mapping/zone_census.py` | `ResearchBarZoneLabelBaselineDescription` | baseline description of market geometry from a bar map (note: path stem 'zone_census' vs content focus 'BarZoneLabel'). |

### `src/retrieval/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/retrieval/__init__.py` | `RetrievalApi` | Enterprise RAG system for the Tradelatest codebase. |
| `src/retrieval/chunking.py` | `ChunkSemanticChunking` | Semantic chunking by language construct, not fixed token size. |
| `src/retrieval/claude_integration.py` | `EnterpriseGate` | Integration with Claude Code for RAG-grounded tasks. |
| `src/retrieval/config.py` | `RetrievalConfigurationRAGPipeline` | Configuration for the RAG pipeline. |
| `src/retrieval/corpus.py` | `RetrievalDocumentDiscoveryAcrossRepository` | Document discovery across the repository (note: path stem 'corpus' vs content focus 'Document'). |
| `src/retrieval/embedding.py` | `Embedder` | Embedding pipeline using sentence-transformers. |
| `src/retrieval/monitor.py` | `MetricsSnapshot` | Monitoring and metrics for the RAG pipeline. |
| `src/retrieval/retriever.py` | `ContextAssembly` | The Retriever: high-level retrieval interface with context assembly. |
| `src/retrieval/vector_store.py` | `VectorChromaDBBacked` | ChromaDB-backed vector store with hybrid search. |

### `src/training/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/training/bar_semantic_tracker.py` | `BarSemanticTrackerVersionedAppend` | Versioned, append-only **bar-level semantic journal** for training / eval pipelines. |
| `src/training/evaluator.py` | `TrainingModelEvaluationAccuracyConfidenceBuckets` | Model evaluation: accuracy, confidence buckets, score-outcome calibration. |
| `src/training/phase5_calibration.py` | `TrainingPostTrainingQualityCheckBefore` | post-training quality check before model registration. |
| `src/training/stage1_dataset_builder.py` | `RejectionLedger` | Stage-1 Truth Dataset Builder for TradingLLM. |
| `src/training/trade_net_v2.py` | `TradeNetV2Trainer` | TradeNet v2 training/model definition surface. |
| `src/training/train_pipeline.py` | `ModelTrainPipeline` | Training pipeline orchestration for model fits. |
| `src/training/trainer.py` | `StandardScaler` | Two model families: (note: path stem 'trainer' vs content focus 'StandardScaler'). |
| `src/training/training_trigger.py` | `TrainingTriggerProgrammaticGate` | Programmatic gate for invoking the auto-train pipeline. |

## Area: `config` (126)

### `configs/control_plane/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/control_plane/monitors.json` | `ControlPlaneConfigMonitorsJson` | config file monitors.json. |

### `configs/data_provenance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/data_provenance/ohlcv_clock_registry.json` | `DataProvenanceConfigOHLCVClockRegistry` | config file ohlcv_clock_registry.json. |

### `configs/experimental/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/experimental/config/output_format.json` | `ExperimentalConfigOutputFormatJson` | config file output_format.json. |
| `configs/experimental/spec/config/drift_thresholds.json` | `ExperimentalConfigDriftThresholdsJson` | config file drift_thresholds.json. |
| `configs/experimental/spec/config/feature_schema.json` | `ExperimentalConfigFeatureSchemaJson` | config file feature_schema.json. |
| `configs/experimental/spec/config/llm_schema.json` | `ExperimentalConfigLLMSchemaJson` | config file llm_schema.json. |
| `configs/experimental/spec/live_rail_tickdb_paper.json` | `ExperimentalConfigLiveRailTickdbPaper` | config file live_rail_tickdb_paper.json. |
| `configs/experimental/spec/live_rail_tickdb_paper_run.json` | `ExperimentalConfigLiveRailTickdbPaper_1` | config file live_rail_tickdb_paper_run.json. |

### `configs/formulas/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/formulas/crt_resolver_links.yaml` | `FormulasConfigCRTResolverLinksYaml` | config file crt_resolver_links.yaml. |
| `configs/formulas/crt_state_identity.yaml` | `FormulasConfigCRTStateIdentityYaml` | config file crt_state_identity.yaml. |
| `configs/formulas/market_crt_states.yaml` | `FormulasConfigMarketCRTStatesYaml` | config file market_crt_states.yaml. |
| `configs/formulas/market_ontology.yaml` | `FormulasConfigMarketOntologyYaml` | config file market_ontology.yaml. |
| `configs/formulas/market_shapes.yaml` | `FormulasConfigMarketShapesYaml` | config file market_shapes.yaml. |
| `configs/formulas/structure_profiles.yaml` | `FormulasConfigStructureProfilesYaml` | config file structure_profiles.yaml. |

### `configs/market_reality/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/market_reality/market_reality_v1.yaml` | `MarketRealityConfigMarketRealityYaml` | config file market_reality_v1.yaml. |

### `configs/production/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/production/ACTIVE_VERSION` | `ProductionConfigACTIVEVERSION` | config file ACTIVE_VERSION. |
| `configs/production/regime_map.json` | `ProductionConfigRegimeMapJson` | config file regime_map.json. |
| `configs/production/v1_multi_2026_03.json` | `ProductionConfigMultiJsonProduction` | config file v1_multi_2026_03.json. |
| `configs/production/v1_multi_2026_03_force_accept.json` | `ProductionConfigMultiForceAcceptJson` | config file v1_multi_2026_03_force_accept.json. |
| `configs/production/v2_dispkill_shadow_2026_08.json` | `ProductionConfigDispkillShadowJson` | config file v2_dispkill_shadow_2026_08.json. |
| `configs/production/v2_htfcrt_2026_08.json` | `ProductionConfigHtfcrtJson` | config file v2_htfcrt_2026_08.json. |
| `configs/production/v2_htfcrt_objgate_shadow_2026_08.json` | `ProductionConfigHtfcrtObjgateShadowJson` | config file v2_htfcrt_objgate_shadow_2026_08.json. |
| `configs/production/v2_multi_2026_04.json` | `ProductionConfigMultiJsonProduction_1` | config file v2_multi_2026_04.json. |
| `configs/production/v2_multi_2026_04_archived_20260430_080821.json` | `ProductionConfigMultiArchivedJsonProduction` | config file v2_multi_2026_04_archived_20260430_080821.json. |
| `configs/production/v2_multi_2026_04_archived_20260430_111839.json` | `ProductionConfigMultiArchivedJsonProduction_1` | config file v2_multi_2026_04_archived_20260430_111839.json. |
| `configs/production/v2_multi_2026_04_archived_20260501_100005.json` | `ProductionConfigMultiArchivedJsonProduction_2` | config file v2_multi_2026_04_archived_20260501_100005.json. |
| `configs/production/v2_multi_2026_04_archived_20260501_183742.json` | `ProductionConfigMultiArchivedJsonProduction_3` | config file v2_multi_2026_04_archived_20260501_183742.json. |
| `configs/production/v2_multi_2026_04_archived_20260502_181418.json` | `ProductionConfigMultiArchivedJsonProduction_4` | config file v2_multi_2026_04_archived_20260502_181418.json. |
| `configs/production/v2_multi_2026_04_archived_20260506_115338.json` | `ProductionConfigMultiArchivedJsonProduction_5` | config file v2_multi_2026_04_archived_20260506_115338.json. |
| `configs/production/v2_multi_2026_04_archived_20260506_193401.json` | `ProductionConfigMultiArchivedJsonProduction_6` | config file v2_multi_2026_04_archived_20260506_193401.json. |
| `configs/production/v2_multi_2026_04_deepdeektry_archived_20260627_160227.json` | `ProductionConfigMultiDeepdeektryArchivedJson` | config file v2_multi_2026_04_deepdeektry_archived_20260627_160227.json. |
| `configs/production/v2_multi_2026_04_v3session_probe.json` | `ProductionConfigMultiV3Session` | config file v2_multi_2026_04_v3session_probe.json. |
| `configs/production/v2_multi_bitnet_shadow_2026_07.json` | `ProductionConfigMultiBitnetShadowJson` | config file v2_multi_bitnet_shadow_2026_07.json. |
| `configs/production/v2_multi_dimfix_shadow_2026_07.json` | `ProductionConfigMultiDimfixShadowJson` | config file v2_multi_dimfix_shadow_2026_07.json. |
| `configs/production/v2_test.json` | `ProductionConfigTestJson` | config file v2_test.json. |
| `configs/production/v2_test_archived_20260411_200110.json` | `ProductionConfigTestArchivedJson` | config file v2_test_archived_20260411_200110.json. |
| `configs/production/v3_multi_2026_06.json` | `ProductionConfigMultiJsonProduction_2` | config file v3_multi_2026_06.json. |
| `configs/production/v3_unified_market_structure_2026_09.json` | `ProductionConfigUnifiedMarketStructureJson` | config file v3_unified_market_structure_2026_09.json. |
| `configs/production/v4_crt_sot_2026_08.json` | `ProductionConfigCRTSotJson` | config file v4_crt_sot_2026_08.json. |
| `configs/production/v4_dual_construction_2026_09.json` | `ProductionConfigDualConstructionJson` | config file v4_dual_construction_2026_09.json. |
| `configs/production/v4_multi_2026_06.json` | `ProductionConfigMultiJsonProduction_3` | config file v4_multi_2026_06.json. |

### `configs/research/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `configs/research/experiments/xauusd_implementation_validation.json` | `ResearchConfigXauusdValidationJson` | config file xauusd_implementation_validation.json. |
| `configs/research/market_story_ontology.yaml` | `ResearchConfigMarketStoryOntologyYaml` | config file market_story_ontology.yaml. |
| `configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json` | `ResearchConfigCPRXAUUSDM15` | config file MC-CPR-L0-XAUUSD-M15-UTC-V1.json. |
| `configs/research/measurement_contracts/crypto_majors.v1.json` | `ResearchConfigCryptoMajorsJson` | config file crypto_majors.v1.json. |
| `configs/research/measurement_contracts/drafts/MC-SUJAN-XAUUSD-M15-V1.json` | `ResearchConfigSUJANXAUUSDM15Drafts` | config file MC-SUJAN-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/fx_majors.v1.json` | `ResearchConfigMajorsJson` | config file fx_majors.v1.json. |
| `configs/research/measurement_contracts/instances/MC-ASYM-XAUUSD-M15-V1.json` | `ResearchConfigASYMXAUUSDM15` | config file MC-ASYM-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-CRT-SB-XAUUSD-M15-NS-V1.json` | `ResearchConfigCRTXAUUSDM15Instances` | config file MC-CRT-SB-XAUUSD-M15-NS-V1.json. |
| `configs/research/measurement_contracts/instances/MC-CRT-SB-XAUUSD-M15-SOFF-V1.json` | `ResearchConfigCRTXAUUSDM15Instances_1` | config file MC-CRT-SB-XAUUSD-M15-SOFF-V1.json. |
| `configs/research/measurement_contracts/instances/MC-CRT-SB-XAUUSD-M15-V1.json` | `ResearchConfigCRTXAUUSDM15Instances_2` | config file MC-CRT-SB-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-CTXATTR-XAUUSD-M15-V1.json` | `ResearchConfigCTXATTRXAUUSDM15` | config file MC-CTXATTR-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-MAGPRIOR-XAUUSD-M15-V1.json` | `ResearchConfigMAGPRIORXAUUSDM15` | config file MC-MAGPRIOR-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-MRANGE-XAUUSD-M15-V1.json` | `ResearchConfigMRANGEXAUUSDM15` | config file MC-MRANGE-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-MRPRIOR-XAUUSD-M15-V1.json` | `ResearchConfigMRPRIORXAUUSDM15` | config file MC-MRPRIOR-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-RNET-OVERLAY-XAUUSD-M15-V1.json` | `ResearchConfigRNETOVERLAYXAUUSDM` | config file MC-RNET-OVERLAY-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-SUJAN-XAUUSD-M15-V1.json` | `ResearchConfigSUJANXAUUSDM15Instances` | config file MC-SUJAN-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-VCRT-XAUUSD-M15-V1.json` | `ResearchConfigVCRTXAUUSDM15Instances` | config file MC-VCRT-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/instances/MC-VCRT-XAUUSD-M15-V2.json` | `ResearchConfigVCRTXAUUSDM15Instances_1` | config file MC-VCRT-XAUUSD-M15-V2.json. |
| `configs/research/measurement_contracts/instances/MC-VCRTPRIOR-XAUUSD-M15-V1.json` | `ResearchConfigVCRTPRIORXAUUSDM15` | config file MC-VCRTPRIOR-XAUUSD-M15-V1.json. |
| `configs/research/measurement_contracts/metals_mt5.v1.json` | `ResearchConfigMetalsMT5Json` | config file metals_mt5.v1.json. |
| `configs/research/provenance/measurement_execution.schema.json` | `ResearchConfigMeasurementExecutionSchemaJson` | config file measurement_execution.schema.json. |
| `configs/research/provenance/provenance_record.schema.json` | `ResearchConfigProvenanceRecordSchemaJson` | config file provenance_record.schema.json. |
| `configs/research/research_config.json` | `ResearchConfigResearchConfigJson` | config file research_config.json. |
| `configs/research/research_config_carry.json` | `ResearchConfigResearchConfigCarryJson` | config file research_config_carry.json. |
| `configs/research/research_config_cross_sectional.json` | `ResearchConfigResearchConfigCrossSectional` | config file research_config_cross_sectional.json. |
| `configs/research/research_config_fx_metals.json` | `ResearchConfigResearchConfigMetalsJson` | config file research_config_fx_metals.json. |
| `configs/research/research_config_harvest.json` | `ResearchConfigResearchConfigHarvestJson` | config file research_config_harvest.json. |
| `configs/research/research_config_htf_majors.json` | `ResearchConfigResearchConfigHtfMajors` | config file research_config_htf_majors.json. |
| `configs/research/research_config_m5_mtf_crypto.json` | `ResearchConfigResearchConfigMtfCrypto` | config file research_config_m5_mtf_crypto.json. |
| `configs/research/research_config_m5_mtf_fx.json` | `ResearchConfigResearchConfigMtfJson` | config file research_config_m5_mtf_fx.json. |
| `configs/research/research_config_majors.json` | `ResearchConfigResearchConfigMajorsJson` | config file research_config_majors.json. |
| `configs/research/research_config_mc_crt_sb_xauusd.json` | `ResearchConfigResearchConfigCRTXauusd` | config file research_config_mc_crt_sb_xauusd.json. |
| `configs/research/research_config_path_crypto.json` | `ResearchConfigResearchConfigPathCrypto` | config file research_config_path_crypto.json. |
| `configs/research/research_config_phase_b.json` | `ResearchConfigResearchConfigPhaseJson` | config file research_config_phase_b.json. |
| `configs/research/research_config_phase_d.json` | `ResearchConfigResearchConfigPhaseJson_1` | config file research_config_phase_d.json. |
| `configs/research/research_config_phase_e.json` | `ResearchConfigResearchConfigPhaseJson_2` | config file research_config_phase_e.json. |
| `configs/research/research_config_phase_s.json` | `ResearchConfigResearchConfigPhaseJson_3` | config file research_config_phase_s.json. |
| `configs/research/research_config_regime.json` | `ResearchConfigResearchConfigRegimeJson` | config file research_config_regime.json. |
| `configs/research/research_config_regime_transition.json` | `ResearchConfigResearchConfigRegimeTransition` | config file research_config_regime_transition.json. |
| `configs/research/research_config_shape_xauusd.json` | `ResearchConfigResearchConfigShapeXauusd` | config file research_config_shape_xauusd.json. |
| `configs/research/research_config_spine.json` | `ResearchConfigResearchConfigSpineJson` | config file research_config_spine.json. |
| `configs/research/research_config_spine_bitnet_shadow.json` | `ResearchConfigResearchConfigSpineBitnet` | config file research_config_spine_bitnet_shadow.json. |
| `configs/research/research_config_spine_dimfix_shadow.json` | `ResearchConfigResearchConfigSpineDimfix` | config file research_config_spine_dimfix_shadow.json. |
| `configs/research/research_config_spine_fx_metals.json` | `ResearchConfigResearchConfigSpineMetals` | config file research_config_spine_fx_metals.json. |
| `configs/research/research_config_spine_htf_majors.json` | `ResearchConfigResearchConfigSpineHtf` | config file research_config_spine_htf_majors.json. |
| `configs/research/research_config_spine_majors.json` | `ResearchConfigResearchConfigSpineMajors` | config file research_config_spine_majors.json. |
| `configs/research/research_config_spine_v3.json` | `ResearchConfigResearchConfigSpineJson_1` | config file research_config_spine_v3.json. |
| `configs/research/research_config_spine_v3session_probe.json` | `ResearchConfigResearchConfigSpineV` | config file research_config_spine_v3session_probe.json. |
| `configs/research/research_config_spine_xauusd.json` | `ResearchConfigResearchConfigSpineXauusd` | config file research_config_spine_xauusd.json. |
| `configs/research/research_config_weekly_sweep.json` | `ResearchConfigResearchConfigWeeklySweep` | config file research_config_weekly_sweep.json. |
| `configs/research/xau_metals_protocol_v1.json` | `ResearchConfigXauMetalsProtocolJson` | config file xau_metals_protocol_v1.json. |

### `src/config_layer/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/config_layer/__init__.py` | `ConfigApi` | Config loaders, validators, and decision rules (CRT math, execution planner, LLM client). |
| `src/config_layer/_crt_state_generated.py` | `ConfigCRTStateEDIT` | _crt_state_generated.py -- GENERATED FILE, DO NOT EDIT BY HAND. |
| `src/config_layer/config_builder.py` | `ConfigBuilderCRTConfigCreation` | SINGLE SOURCE OF TRUTH for CRTConfig creation. |
| `src/config_layer/config_validator.py` | `ConfigValidatorValidationGate` | Config Validation Gate -- Phase 1 + Phase 5 quality enforcement. |
| `src/config_layer/crt_config_completeness.py` | `ConfigStrictCompletenessCheckCRTConfig` | Strict completeness check for CRTConfig field declaration -- Phase C of the "CRT single source of truth" plan (2026-08-31 session). |
| `src/config_layer/crt_config_provenance.py` | `ConstructionMode` | P1 OBSERVE (F-057 class) (note: path stem 'crt_config_provenance' vs content focus 'ConstructionMode'). |
| `src/config_layer/crt_engine_v2.py` | `CrtEngineV2ConfigBinding` | CRT engine v2 config binding and candle/event contracts for production CRT. |
| `src/config_layer/crt_gaussian_scorer.py` | `CRTGaussianScorerCentral` | Central CRT Gaussian scorer. |
| `src/config_layer/crt_identity_schema.py` | `ConfigValidatorConfigsFormulasCRTState` | PR-1 validator for `configs/formulas/crt_state_identity.yaml`. |
| `src/config_layer/crt_sweep_taxonomy.py` | `ConfigPureGeometricClassifierCRTSweep` | Pure-function geometric classifier for CRT sweep candles. |
| `src/config_layer/execution_planner.py` | `ExecutionPlannerV12Pure` | pure intent classifier + gate (note: path stem 'execution_planner' vs content focus 'ExecutionPlannerV1_2'). |
| `src/config_layer/goal_schema.py` | `ConfigGOALEconomicObjectiveSchema` | the GOAL (economic-objective) schema. |
| `src/config_layer/goal_validator.py` | `GoalValidatorConfig` | the GOAL validator. |
| `src/config_layer/htf_state.py` | `ObjectiveStatus` | CH-htf-state-objective (Stage 3): HTFState + Objective. |
| `src/config_layer/insight_reporter.py` | `InsightReporterDynamicLLM` | Dynamic LLM-powered insight reporting for the CRT trading system. |
| `src/config_layer/llm_inference_client.py` | `ConfigEndpointManagementGroqAuditLogging` | endpoint management, Groq cloud fallback, audit logging, and multi-turn chat. |
| `src/config_layer/llm_narrative.py` | `ConfigPromptTemplatesGenerativeInsightFunctions` | prompt templates and generative-insight functions that produce prose reports for trade decisions, session summaries, model evaluations, backtest results, and regime alerts. |
| `src/config_layer/llm_scorer.py` | `LlmPromptScoreRouter` | Builds LLM scoring prompts and routes to llama.cpp primary or Groq fallback. |
| `src/config_layer/m15_structural_range.py` | `M15StructuralLiquidityRange` | the CRT sweep envelope (note: path stem 'm15_structural_range' vs content focus 'M15StructuralLiquidityRange'). |
| `src/config_layer/market_router.py` | `MarketInstrumentConfigRouter` | Routes instruments to CRT/market config profiles. |
| `src/config_layer/model_paths.py` | `ConfigModelPathsLayoutAuthorityArtifacts` | CODE layout authority for model artifacts (Phase 0). |
| `src/config_layer/model_resolver.py` | `ModelPathResolver` | Resolves model artifact paths from registries and active pins. |
| `src/config_layer/parent_crt.py` | `ParentRange` | CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the parent-timeframe 3-candle CRT construct. |
| `src/config_layer/production_bundle.py` | `ProductionBundleAssembler` | Assembles production config bundles for runtime pin resolution. |
| `src/config_layer/production_config.py` | `ProductionStackConfigLoader` | Loads and validates pinned production stack JSON referenced by ACTIVE_VERSION. |
| `src/config_layer/rr/__init__.py` | `ConfigRrApi` | Risk-reward fusion layer: RR dataset builder and RR model fusion. |
| `src/config_layer/rr/rr_dataset_builder.py` | `ConfigCanonicalDatasetBuilderBasedFeature` | Canonical RR dataset builder based on FeaturePipeline output. |
| `src/config_layer/rr/rr_fusion.py` | `RRFusionAdvisoryCanonical` | Advisory RR fusion layer using canonical 24-feature validation. |
| `src/config_layer/rr/rr_pattern_miner.py` | `NanoInferenceEngine` | Feature -> RR Pattern Miner trainer and pure-Python inference. |
| `src/config_layer/stack_version.py` | `StackVersionOneComposite` | one composite identity over WHAT / HOW / WHO / EXECUTION. |
| `src/config_layer/state_contract.py` | `StateContractSchema` | State contract schema for CRT/runtime state topology. |
| `src/config_layer/state_contract_loader.py` | `ConfigStateContractLoadingValidation` | State Contract Loading and Validation. |
| `src/config_layer/state_identity.py` | `Direction` | Enums, Baseline Transitions, and Configuration Schema (note: path stem 'state_identity' vs content focus 'Direction'). |
| `src/config_layer/state_topology.py` | `ConfigRuntimeCRTStateIdentityLegal` | runtime CRT state identity + legal transition graph from active_models.yaml (via StateContractBundle). |

## Area: `script` (48)

### `scripts/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/__init__.py` | `ScriptsApi` | Module at scripts/__init__.py. |
| `scripts/_gate5_compliance_pass.py` | `ScriptsGateReproducibilityCompliancePassCount` | Gate 5 reproducibility-compliance pass: count UNKNOWNs, extract exact record IDs. |
| `scripts/auto_train_from_opportunities.py` | `ScriptsNightlyPipelineOrchestrator` | Nightly Pipeline-B orchestrator. |
| `scripts/build_consolidated_docs.py` | `ScriptsCompleteConsolidatedDocumentsConcatenatingFiles` | Build complete consolidated markdown documents by concatenating source files. |
| `scripts/export_model_registry.py` | `ScriptsExportModelRegistry` | Module at scripts/export_model_registry.py. |
| `scripts/extract_folder_structure.py` | `ScriptsExtractFolderStructure` | Module at scripts/extract_folder_structure.py. |
| `scripts/rag_index.py` | `ScriptsEntryPointRAGPipeline` | CLI entry point for the RAG pipeline. |
| `scripts/tmp_cert_worktrees.py` | `ScriptsOneShotPreparePREPOST` | One-shot: prepare PRE/POST worktrees for Phase-1 certification parity. |
| `scripts/update_config_hash.py` | `ScriptsUpdateVerifyConfigHashField` | Update or verify the 'config_hash' field in a production config JSON file. |
| `scripts/validate_integration.py` | `ScriptsValidatesEveryIntegrationPointIntroduced` | Validates every integration point introduced in the Unified Execution Spine migration. |

### `scripts/context/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/context/build_context.py` | `ContextCompilerCompileTriggerRegenerate` | the Context Compiler ("Compile" trigger) Regenerate the **Portable Mind**: a small set of derived context files under context/ that you paste into any external model (DeepSeek /... |
| `scripts/context/discussion.py` | `ContextRewindReadMultiLLMDiscussion` | rewind / read the multi-LLM discussion (view-only time-travel). |
| `scripts/context/log_turn.py` | `ContextCaptureOneMultiLLMTurn` | capture one multi-LLM turn into the append-only ledger (manual paste workflow). |
| `scripts/context/pack_story.py` | `ContextEmitOneUploadReadyContext` | emit one upload-ready context pack for a story (Portable Mind + that story's files). |
| `scripts/context/seed_build_queue.py` | `ContextParsePlanFULLSPECIFICATIONMachine` | Parse docs/implementation_plan/FULL_BUILD_SPECIFICATION.md into the single machine-readable story backlog: multi_llm/build_queue.jsonl (one JSON object per line, append-only con... |

### `scripts/control_plane/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/control_plane/run_server.py` | `ControlPlaneRunMain` | exposes main. |

### `scripts/data/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/data/build_m15_unified.py` | `DataM15UnifiedLoadFiles` | exposes load_files, normalize_timezone, resample_m15, validate. |
| `scripts/data/build_rr_dataset.py` | `DataSaveDatasetJSONEither` | Build and save RR dataset JSON from either:. |
| `scripts/data/build_tradenet_dataset.py` | `DataConvertFusionJsonlTradeLogs` | Convert *_fusion.jsonl trade logs → data/training.json for train_pipeline.py tradenet. |
| `scripts/data/check_availability.py` | `DataCheckFullDataAvailabilityInstruments` | Check full data availability for all instruments. |
| `scripts/data/check_yfinance.py` | `DataCheckDataAvailableYfinance` | Check what data is available via yfinance. |
| `scripts/data/convert_binance_m1_to_m15.py` | `DataConvertBinanceM1M` | Module at scripts/data/convert_binance_m1_to_m15.py. |
| `scripts/data/convert_bnb_to_csv.py` | `DataConvertBnbCsvConvertExcel` | exposes convert_excel_to_csv. |
| `scripts/data/csv_to_excel.py` | `DataConvertFetchedM15CS` | Convert fetched M15 CSVs with real volume to Excel (.xlsx) files. |
| `scripts/data/fetch_and_verify_binance.py` | `DataCryptoCounterpartFetchVerifyMT` | the crypto counterpart of fetch_and_verify_mt5.py. |
| `scripts/data/fetch_and_verify_mt5.py` | `DataTrainInconsistentData` | "can't train on inconsistent data.". |
| `scripts/data/fetch_candles_alphavantage.py` | `DataFetchHistoricalOHLCVCandlesAlpha` | CLI: Fetch historical FX OHLCV candles from Alpha Vantage -> Tradelatest CSV. |
| `scripts/data/fetch_candles_hummingbot.py` | `DataFetchHistoricalOHLCVCandlesHummingbot` | CLI: Fetch historical OHLCV candles via hummingbot and write Tradelatest CSVs. |
| `scripts/data/fetch_candles_mt5.py` | `DataFetchHistoricalOHLCVCandlesRunning` | CLI: Fetch historical OHLCV candles from a running MetaTrader 5 terminal -> Tradelatest CSV. |
| `scripts/data/fetch_crypto_ccxt.py` | `DataFetchYearsCryptoM15` | Fetch 2+ years of crypto M15 OHLCV data via CCXT (Binance). |
| `scripts/data/fetch_forex_yfinance.py` | `DataFetchForexM15OHLCV` | Fetch forex M15 OHLCV data via Yahoo Finance using CME futures. |
| `scripts/data/fetch_perp_funding.py` | `DataFetchBinancePerpFundingRate` | CLI: Fetch Binance perp funding-rate + premium-index (basis) history -> CSV. |
| `scripts/data/generate_vectors.py` | `DataGenerateVectorsRandomRecord` | exposes random_record, main. |
| `scripts/data/prepare_data.py` | `DataPreparationConvertsRawData` | Data Preparation Script Converts raw M1 data -> clean M15 OHLCV CSVs ready for portfolio validation. |
| `scripts/data/split_bnb_excel.py` | `DataSplitBnbExcelSplitCsv` | exposes split_csv_to_excel. |
| `scripts/data/test_yf_periods.py` | `DataTestPeriodRangesWorkData` | Test what period ranges work for 15m data. |
| `scripts/data/unified_data_builder.py` | `DataUnifiedBatchDataIngestionPipeline` | Unified Batch Data Ingestion Pipeline Replaces: build_m15_unified.py, run_hisotircal_data_*.py, convert_binance_m1_to_m15.py. |
| `scripts/data/verify_output.py` | `DataVerifyOutputDataYfinanceCS` | Verify all output data/yfinance CSVs and data Excel files. |

### `scripts/groq_bridge/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/groq_bridge/apply_llm_suggestions.py` | `GroqBridgeReadsLLMHyperparameterSuggestions` | Reads LLM hyperparameter suggestions (JSON) and dispatches to the right training script. |
| `scripts/groq_bridge/ingest_response.py` | `GroqBridgePhaseGroqBridgeIngests` | Phase 1 Groq Bridge -- ingests Groq's JSON response, updates the session registry, writes structured insights to logs/groq_bridge/insights.jsonl, updates trace_index.md, and pri... |
| `scripts/groq_bridge/prepare_retrospective.py` | `GroqBridgePhaseGroqBridgeGenerates` | Phase 1 Groq Bridge -- generates a rich, structured prompt from backtest output files, registers a session in logs/groq_bridge/session_registry.jsonl, and writes the prompt to a... |

### `scripts/misc/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/misc/bitnet_ternary_inference.py` | `MiscBitnetTernaryInferenceClean` | exposes clean, normalize, binarize, forward. |
| `scripts/misc/build_zone_registry_from_trades.py` | `MiscZoneRegistryTradesMain` | exposes main. |
| `scripts/misc/resample_m1_to_m15.py` | `MiscResampleM1M15` | Module at scripts/misc/resample_m1_to_m15.py. |
| `scripts/misc/run_parity.py` | `MiscFullyAutomatedParityRunner` | fully automated C++/Python parity runner. |
| `scripts/misc/trade_replay_validator.py` | `MiscCandleReplayReplaysTradeCandle` | Deterministic Candle Replay Replays each trade candle-by-candle against the trade's entry / SL / TP1 / TP2 to recompute its realized RR, then compares against the persisted ``pn... |

### `scripts/multi_llm/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/multi_llm/initiate_plan.py` | `MultiLlmInitiateResearchLanePlan` | Initiate a Research Lane plan package for one LLM model. |

### `scripts/portfolio/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `scripts/portfolio/replay_allocator.py` | `PortfolioAllocatorShadowReplay` | CLI wrapper for the PortfolioAllocator shadow replay (F-013). |

## Area: `test` (543)

### `tests/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/conftest.py` | `PytestSharedFixturesTests` | Shared pytest fixtures and suite bootstrap for the repo test surface. |
| `tests/test_acceptance_controller.py` | `TestTestsAcceptanceController` | Pytest coverage for test_theta_upper_bound_respected, test_theta_lower_bound_respected, test_fusion_threshold_is_85th_percentile, test_returns_defaults_when_cold. |
| `tests/test_active_models_registry.py` | `TestTestsActiveModelsRegistry` | Pytest coverage for test_schema_version_and_layers, test_finding_ids_resolve, test_hypothesis_ids_resolve, test_machine_readable_sources_resolve. |
| `tests/test_agent_executor_confirm.py` | `TestTestsAgentExecutorConfirm` | Pytest coverage for test_read_tool_runs_inline, test_write_tool_returns_pending_without_confirm, test_write_tool_executes_after_confirm, test_path_outside_allowlist_refused. |
| `tests/test_agent_intent_router.py` | `TestTestsAgentIntentRouter` | Pytest coverage for test_regex_pipeline_tune_promote, test_regex_pipeline_backtest, test_regex_pipeline_validate, test_regex_copilot_advise. |
| `tests/test_agent_plan_compiler.py` | `TestTestsAgentPlanCompiler` | Pytest coverage for test_tune_and_promote_pipeline, test_backtest_only, test_governance_run_canonical_order, test_advise_signal_engine_first_veto_present. |
| `tests/test_agent_tool_registry.py` | `TestTestsAgentToolRegistry` | Pytest coverage for test_all_pipeline_tools_registered, test_all_copilot_tools_registered, test_all_governance_tools_registered, test_write_tools_correctly_flagged. |
| `tests/test_analytics.py` | `TestTestsAnalytics` | Pytest coverage for test_trade_record_to_dict, test_trade_record_from_dict_round_trip, test_trade_record_to_json, test_trade_logger_writes_to_file. |
| `tests/test_analytics_evidence_class_census.py` | `TestTestsAnalyticsEvidenceCensus` | Pytest coverage for test_corpus_observation_wins_over_code, test_foreign_events_are_not_admissible_corpus_proof, test_code_then_declared_then_unknown_precedence. |
| `tests/test_analyze_fusion_shadow.py` | `TestTestsAnalyzeFusionShadow` | Pytest coverage for test_analyze_log_reads_prefixed_json_lines, test_analyze_log_handles_empty_input. |
| `tests/test_auto_tuner_multi.py` | `TestTestsAutoTunerMulti` | Pytest coverage for test_determinism, test_forex_vs_crypto_config, test_multi_score_differs_from_single, test_multi_score_homogeneous. |
| `tests/test_b0b1_feature_semantic_migration.py` | `TestTestsB0B1` | Pytest coverage for test_F1_legacy_ema_spread_scales_with_price, test_F2_legacy_momentum_score_scales_with_price, test_corrected_ema_spread_atr_is_scale_invariant, test_correcte... |
| `tests/test_b2a_feature_candidate_certification.py` | `TestTestsB2FeatureCandidate` | Pytest coverage for test_three_path_reconstruction_agrees, test_scalar_vector_parity, test_nan_inf_discipline, test_candidate_scale_invariant_while_legacy_scales. |
| `tests/test_backtest_bitnet_console_encoding.py` | `TestTestsBacktestBitnetConsoleEncoding` | Pytest coverage for test_run_backtest_survives_cp1252_stdout. |
| `tests/test_backtest_declared_constants.py` | `TestTestsBacktestDeclaredConstants` | Pytest coverage for test_declared_key_present_in_active_config, test_strict_accessor_raises_when_key_absent, test_declared_values_equal_the_replaced_literals, test_trade_journal... |
| `tests/test_backtest_payload_integrity.py` | `TestTestsBacktestPayloadIntegrity` | Pytest coverage for test_backtest_keeps_input_canonical_and_routes_runtime_to_context, test_backtest_symbol_default_falls_back_to_filename. |
| `tests/test_bar_structure_snapshot.py` | `TestTestsBarStructureSnapshot` | Pytest coverage for test_every_bar_emits_exactly_one_gapless_record, test_identity_fields_present_on_every_record, test_key_order_is_stable_within_a_phase, test_zone_distance_is... |
| `tests/test_behavior_census.py` | `TestTestsBehaviorCensus` | Pytest coverage for test_report_has_expected_shape, test_migrated_module_maturities, test_external_injection_not_overreported, test_crt_engine_no_genuine_hardcoded. |
| `tests/test_behavioral_constant_authority_trace.py` | `TestTestsBehavioralConstantAuthorityTrace` | Pytest coverage for test_artifacts_exist, test_scope_rule_frozen_before_classification, test_closure_pass_id_present, test_spine_expanded_beyond_crt_engine_v2. |
| `tests/test_bitnet_composition.py` | `TestTestsBitnetComposition` | Pytest coverage for test_legacy_composition_matches_bitnet_model_forward, test_bitnet_score_matches_composition, test_legacy_encoder_fail_fast_missing_key, test_crt_serve_aliases. |
| `tests/test_bitnet_contract_c_trainer.py` | `TestTestsBitnetContractCTrainer` | Pytest coverage for test_label_contract_registry, test_train_synthetic_bundle_contract_c, test_train_reproducible_seed, test_missing_label_contract_rejected. |
| `tests/test_bitnet_inference.py` | `TestTestsBitnetInference` | Pytest coverage for test_predict_rejects_wrong_shape, test_predict_rejects_2d_array, test_predict_rejects_nan, test_predict_rejects_all_nan. |
| `tests/test_bitnet_parity.py` | `TestTestsBitnetParity` | Pytest coverage for test_cpp_python_parity, test_canonical_feature_dim, test_python_inference_shape. |
| `tests/test_bitnet_population_label_audit.py` | `TestTestsBitnetPopulationLabelAudit` | Pytest coverage for test_balance_block_extreme, test_balance_block_unlabeled, test_label_one_win_and_loss. |
| `tests/test_bitnet_r25_kill_test.py` | `TestTestsBitnetR25Kill` | Pytest coverage for test_ece_perfect_and_worst, test_r25_strong_signal_earns_pass, test_r25_no_signal_overall_does_not_earn_r3, test_thresholds_pre_registered_immutable_keys. |
| `tests/test_bitnet_registry_governance.py` | `TestTestsBitnetRegistryGovernance` | Pytest coverage for test_registry_file_is_catalogued_not_empty, test_dual_schema_fork_is_explicit, test_composition_default_resolves_to_legacy_model_json, test_assert_serve_allo... |
| `tests/test_blind_label_harness.py` | `TestTestsBlindLabelHarness` | Pytest coverage for test_html_leaks_no_answer_value, test_html_never_references_manifest, test_html_has_no_feature_column_names, test_context_window_never_reaches_past_target. |
| `tests/test_boundary_hypothesis_eval.py` | `TestTestsBoundaryHypothesisEval` | Pytest coverage for test_boundary_enrichment_when_disp_has_low_margin. |
| `tests/test_breakout_disp_threshold.py` | `TestTestsBreakoutDispThreshold` | Pytest coverage for test_config_defaults_are_1_5_noop, test_resolver_global_override_caseinsensitive_fallback, test_crt_intent_honors_threshold_and_static_caller_unchanged, test... |
| `tests/test_btcusdt_crt_v3_handover.py` | `TestTestsBtcusdtCrtV3` | Pytest module defining TestClassifySweep, TestWickBonus, TestBTCUSDTReplayGroundTruth. |
| `tests/test_calendar_periods.py` | `TestTestsCalendarPeriods` | Pytest coverage for test_hour_grid_table_matches_resample_exactly, test_period_key_agrees_with_bucket_floor, test_all_period_rules_is_exhaustive_and_sorted_hour_grid_first, test... |
| `tests/test_candle_math.py` | `TestTestsCandleMath` | Pytest coverage for test_worked_example_primitives, test_body_ratio_is_bounded_zero_one, test_total_wick_identity, test_degenerate_flat_bar_returns_zero. |
| `tests/test_chart_series.py` | `TestTestsChartSeries` | Pytest coverage for test_zac1_no_zonex_import_in_chart_code, test_timeframe_aggregation_agrees_on_every_emitted_bucket, test_trailing_partial_bucket_is_dropped, test_aggregation... |
| `tests/test_claude_intent_workbook.py` | `TestTestsClaudeIntentWorkbook` | Pytest coverage for test_tmp_row_count_matches_subprocess_collect, test_every_claude_test_module_appears, test_every_row_is_a_mapped_claude_family, test_house_style_holds_for_ev... |
| `tests/test_cli_matrix_sync.py` | `TestTestsMatrixSyncTests` | Pytest coverage for test_inputs_exist, test_cli_matrix_covers_every_registry_command. |
| `tests/test_closure_authority_index.py` | `TestTestsClosureAuthorityIndex` | Pytest coverage for test_registry_schema_and_invariant, test_required_surfaces_present_unique_ids, test_surface_fields_and_allowed_status, test_closed_surfaces_have_full_closure... |
| `tests/test_codebase_structure_doc.py` | `TestTestsCodebaseStructure` | Pytest coverage for test_state_map_exists, test_every_src_package_is_documented. |
| `tests/test_collector_fusion_persistence.py` | `TestTestsCollectorFusionPersistence` | Pytest coverage for test_collector_log_forwards_fusion_payload. |
| `tests/test_component_cost_model.py` | `TestTestsComponentCostModel` | Pytest coverage for test_stop_slippage_charged_only_on_stop_exit, test_take_profit_never_slips_favourably, test_leg_decomposition_is_not_twice_c_per_side, test_cost_r_is_ratio_t... |
| `tests/test_config_consumer_graph.py` | `TestTestsConfigConsumerGraph` | Pytest coverage for test_graph_is_a_pure_projection_of_the_report, test_graph_edges_are_deduplicated_and_well_formed, test_generated_graph_artifacts_exist_and_parse. |
| `tests/test_config_integrity.py` | `TestTestsConfigIntegrity` | Pytest coverage for test_fresh_summary_passes, test_stale_summary_fails, test_missing_fingerprint_fails, test_governed_active_passes. |
| `tests/test_config_reachability.py` | `TestTestsConfigReachability` | Pytest coverage for test_report_has_expected_shape, test_no_dead_config_keys. |
| `tests/test_console_safe.py` | `TestTestsConsoleSafe` | Pytest coverage for test_sanitize_for_console_preserves_utf8_text, test_safe_print_falls_back_on_unicode_encode_error, test_safe_print_supports_mixed_args, test_safe_stream_hand... |
| `tests/test_consolidation_due.py` | `TestTestsConsolidationDue` | Pytest coverage for test_none_due_when_all_under_threshold, test_due_signals_carry_a_remedy, test_boundary_is_strictly_greater, test_unmeasurable_count_is_not_due. |
| `tests/test_construction_protocol.py` | `TestTestsConstructionProtocol` | Pytest coverage for test_contracts_registry_wellformed, test_trace_observation_join_is_not_a_decision_path_class, test_construction_floor_targets_exist, test_unknown_mandatory_f... |
| `tests/test_context_compiler.py` | `TestTestsContextCompiler` | Pytest coverage for test_build_emits_expected_files, test_build_files_non_empty, test_build_is_deterministic, test_build_stamps_generated_header. |
| `tests/test_context_pack.py` | `TestTestsContextPack` | Pytest coverage for test_story_exists_in_queue, test_pack_has_header_and_manifest, test_pack_is_deterministic, test_tiny_budget_flags_truncation_not_silent. |
| `tests/test_context_report_providers.py` | `TestTestsContextReportProviders` | Pytest coverage for test_export_default_makes_no_llm_call, test_local_caller_yields_five_keys_and_coerces_list, test_groq_malformed_falls_back_to_five_key_shape, test_empty_outp... |
| `tests/test_control_plane_api.py` | `TestTestsControlPlaneApi` | Pytest coverage for test_api_run_lifecycle_and_artifacts, test_ui_route_returns_html. |
| `tests/test_control_plane_doc_alignment.py` | `TestTestsControlPlaneAlignment` | Pytest coverage for test_agents_path_alignment, test_cli_matrix_contains_all_core_command_ids. |
| `tests/test_control_plane_jobs.py` | `TestTestsControlPlaneJobs` | Pytest coverage for test_job_manager_executes_and_collects_artifacts, test_job_manager_persists_run_records. |
| `tests/test_control_plane_registry.py` | `TestTestsControlPlaneRegistry` | Pytest coverage for test_registry_contains_core_commands, test_tutorial_mapping_and_stage_order, test_render_command_module_mode, test_render_command_subcommand_scoping_validator. |
| `tests/test_control_plane_tutorial.py` | `TestTestsControlPlaneTutorial` | Pytest coverage for test_tour_persistence_keys_present_in_ui_html, test_tour_controls_present_in_ui_html. |
| `tests/test_convergence_controller.py` | `TestTestsConvergenceController` | Pytest coverage for test_calibrate_score_at_threshold, test_calibrate_score_above_threshold_returns_above_half, test_calibrate_score_below_threshold_returns_below_half, test_cal... |
| `tests/test_corpus_authority_decisions.py` | `TestTestsCorpusAuthorityDecisions` | Pytest coverage for test_schema_and_doctrine_exist, test_dataset_identity_star_freeze_tokens, test_seeded_row_count_matches_logical_rollup, test_volume_enum_matches_schema. |
| `tests/test_corpus_gate.py` | `TestTestsCorpusGate` | Pytest coverage for test_canonical_corpus_admits_without_rewrite, test_forensic_path_is_rejected_regardless_of_enforce, test_d1_lattice_constant_phase_passes, test_d1_mixed_phas... |
| `tests/test_correlation_engine_rolling.py` | `TestTestsCorrelationEngineRolling` | Pytest coverage for test_same_symbol_is_one, test_empty_symbol_is_zero, test_max_corr_empty_existing, test_no_fetcher_falls_back_to_heuristic. |
| `tests/test_cost_model_parity.py` | `TestTestsCostModelParity` | Pytest coverage for test_existing_config_sha_is_byte_identical, test_every_parsable_config_is_pinned, test_cost_model_defaults_to_flat_bps, test_declaring_cost_model_changes_the... |
| `tests/test_crt_adversarial_closure.py` | `TestTestsCrtAdversarialClosure` | Pytest coverage for test_control_body_ratio_matches_candle_math_fm010, test_adversarial_body_ratio_not_body_over_total_wick, test_control_displacement_retrace_is_fm027_not_fm021... |
| `tests/test_crt_baseline_trace.py` | `TestTestsCrtBaselineTrace` | Pytest coverage for test_baseline_trace_default_none_and_disabled_emits_nothing, test_trace_on_off_action_parity, test_trace_does_not_recompute_features_and_38_schema, test_shor... |
| `tests/test_crt_closure_report.py` | `TestTestsCrtClosureReport` | Pytest coverage for test_closure_report_exists, test_closure_status_reopened_after_directional_displacement, test_closure_report_lists_phase_artifacts. |
| `tests/test_crt_config_completeness.py` | `TestTestsCrtConfigCompleteness` | Pytest coverage for test_all_fields_count_matches_measured_crtconfig, test_excluded_set_is_exactly_five_fields, test_externally_owned_set_is_allowed_sessions, test_scalar_requir... |
| `tests/test_crt_config_completeness_census.py` | `TestTestsCrtConfigCompletenessCensus` | Pytest coverage for test_census_covers_24_production_config_files, test_zero_files_currently_pass_the_completeness_check, test_regime_map_is_skipped_not_counted_as_a_failure, te... |
| `tests/test_crt_config_provenance.py` | `TestTestsCrtConfigProvenance` | Pytest coverage for test_builder_stamps_router_base, test_prod_registry_restamps_production_merged, test_from_existing_stamps_explicit, test_fingerprint_diverges_router_vs_prod_... |
| `tests/test_crt_config_reachability.py` | `TestTestsCrtConfigReachability` | Pytest coverage for test_artifact_schema_and_field_coverage, test_no_unexpected_unreachable, test_intent_tp1_multipliers_dynamic, test_bnb_load_matches_prod_profile_keys. |
| `tests/test_crt_confusion_reconstruction.py` | `TestTestsCrtConfusionReconstruction` | Pytest coverage for test_stale_from_reset_does_not_truncate_active_state, test_matching_from_reset_is_applied, test_without_guard_the_bug_would_undercount. |
| `tests/test_crt_construction_trace.py` | `TestTestsCrtConstructionTrace` | Pytest coverage for test_state_name_accepts_enum_and_str_identically, test_ontology_m15_states_matches_yaml, test_from_prod_config_none_when_section_absent, test_from_prod_confi... |
| `tests/test_crt_construction_trace_envelope.py` | `TestTestsCrtConstructionTraceEnvelope` | Pytest coverage for test_schema_version_is_v2, test_v2_columns_present_on_live_row, test_v2_columns_present_on_warmup_row, test_legacy_lineage_columns_are_retained. |
| `tests/test_crt_executable_state_graph.py` | `TestTestsCrtExecutableStateGraph` | Pytest coverage for test_graph_file_exists_and_schema, test_graph_states_match_crtstate_exactly, test_valid_transitions_parity_code_vs_graph_edges, test_transition_methods_only_... |
| `tests/test_crt_fail_reason_counters.py` | `TestTestsCrtFailReasonCounters` | Pytest coverage for test_fail_counters_default_off_no_attachment, test_fail_counters_on_off_action_parity_small, test_record_guard_fail_open_on_serialization_error. |
| `tests/test_crt_feature_builder_v4_schema.py` | `TestTestsCrtFeatureBuilderV` | Pytest coverage for test_emits_exactly_the_canonical_key_set, test_all_values_are_finite_floats, test_v4_macd_split_transcribes_two_distinct_quantities, test_macd_hist_raw_is_no... |
| `tests/test_crt_fixes.py` | `TestTestsCrtFixes` | Pytest module defining TestScoreNormalizer, TestEngineHealthTracker, TestDynamicThreshold. |
| `tests/test_crt_gaussian_scorer_direction_compat.py` | `TestTestsCrtGaussianScorerDirection` | Pytest coverage for test_noop_scorer_accepts_direction_kwarg, test_noop_scorer_signature_includes_direction, test_calibrated_scorer_signature_includes_direction, test_direction_... |
| `tests/test_crt_object_relations.py` | `TestTestsCrtObjectRelations` | Pytest coverage for test_relation_table_is_closed_and_complete, test_each_relation_check, test_parent_track_type_is_not_the_m15_envelope, test_relations_closed_does_not_close_cr... |
| `tests/test_crt_parity_classifier.py` | `TestTestsCrtParityClassifier` | Pytest coverage for test_category_precedence_matches_module_constant, test_min_cell_n_matches_precedent. |
| `tests/test_crt_parity_sweep.py` | `TestTestsCrtParitySweep` | Pytest module defining TestDeltaApplication, TestCandidateMaterializationConfinement, TestStageIterationNamespacesDoNotCollide. |
| `tests/test_crt_session_filter.py` | `TestTestsCrtSessionFilter` | Pytest coverage for test_crtconfig_default_allowed_sessions, test_session_resolution_london, test_session_resolution_asia_blocked, test_session_resolution_off_session_blocked. |
| `tests/test_crt_state_generated_parity.py` | `TestTestsCrtStateParity` | Pytest coverage for test_enum_name_to_value_map_is_unchanged_by_generation, test_transition_graph_is_unchanged_by_generation, test_partition_is_unchanged_by_generation, test_com... |
| `tests/test_crt_state_identity.py` | `TestTestsCrtStateIdentity` | Pytest coverage for test_identity_file_exists, test_identity_validates, test_document_root_is_exactly_identity_key, test_state_list_matches_who_source_order. |
| `tests/test_crt_state_invariants.py` | `TestTestsCrtStateInvariants` | Pytest coverage for test_crt_state_invariants. |
| `tests/test_crt_state_resolver_b1h_polish.py` | `TestTestsCrtStateResolverB` | Pytest coverage for test_continuous_disp_to_expansion_default_off, test_continuous_disp_to_expansion_opt_in, test_engine_inject_shadow_pending_overrides_sweep, test_engine_injec... |
| `tests/test_crt_state_resolver_displacement_gate.py` | `TestTestsCrtStateResolverDisplacement` | Pytest coverage for test_displacement_gate_rejects_small_candle_range_like_engine, test_displacement_gate_admits_large_candle_range, test_displacement_gate_honours_pre_v4_wick_s... |
| `tests/test_crt_state_resolver_gate_parity.py` | `TestTestsCrtStateResolverGate` | Pytest coverage for test_sweep_allowed_from_range_sweep_shadow, test_sweep_rejected_mid_funnel, test_displacement_rejected_when_not_from_sweep, test_displacement_rejected_small_... |
| `tests/test_crt_state_resolver_sweep_geometry.py` | `TestTestsCrtStateResolverSweep` | Pytest coverage for test_htf_range_sweep_high_founding, test_htf_range_no_sweep_when_close_outside, test_pipeline_swing_still_uses_liquidity_sweep, test_detect_htf_range_sweep_u... |
| `tests/test_crt_states_yaml_state_names.py` | `TestTestsCrtStatesYamlState` | Pytest coverage for test_every_declared_state_name_is_a_real_crtstate, test_no_duplicate_state_names, test_the_nine_declared_states_are_exactly_the_non_parent_crt_states, test_r... |
| `tests/test_crt_states_yaml_transition_parity.py` | `TestTestsCrtStatesYamlTransition` | Pytest coverage for test_state_identity_sets_match, test_every_yaml_state_is_a_real_crtstate, test_edge_sets_match_modulo_declared_allowances, test_no_stale_allowances. |
| `tests/test_crt_threshold_authority_census.py` | `TestTestsCrtThresholdAuthorityCensus` | Pytest coverage for test_tool_is_importable_and_runnable, test_active_version_is_expected, test_authority_counts_match_measured_census, test_pinned_undeclared_set_is_exactly_two... |
| `tests/test_crt_threshold_refs.py` | `TestTestsCrtThresholdRefs` | Pytest coverage for test_thresholds_block_is_byte_identical_to_pre_phase_d, test_validator_accepts_the_real_file_clean, test_every_thresholds_key_has_exactly_one_refs_entry, tes... |
| `tests/test_crt_zone_crosstab.py` | `TestTestsCrtZoneCrosstab` | Pytest coverage for test_crosstab_counts_lift_and_entries. |
| `tests/test_current_findings.py` | `TestTestsCurrentFindings` | Pytest coverage for test_findings_doc_exists_and_is_dated, test_findings_have_required_fields, test_revalidation_window_respects_status_ceiling, test_nonterminal_findings_are_fr... |
| `tests/test_dataset_integrity.py` | `TestTestsDatasetIntegrity` | Pytest coverage for test_clean_dataset_approves, test_small_gap_reports_only_warn, test_duplicate_timestamp_raises, test_out_of_order_timestamp_raises. |
| `tests/test_dataset_registry.py` | `TestTestsDatasetRegistry` | Pytest coverage for test_registry_index_and_record_shape, test_bound_dataset_star_projections, test_mn1_is_not_child_of_w1, test_projection_is_not_a_file_resolve. |
| `tests/test_derived_math.py` | `TestTestsMath` | Pytest coverage for test_disp_strength_matches_pipeline, test_retest_depth_matches_pipeline, test_ema_spread_matches_pipeline, test_momentum_score_matches_pipeline. |
| `tests/test_directional_displacement.py` | `TestTestsDirectionalDisplacement` | Pytest coverage for test_long_rejects_bearish_dump_jul28_shape, test_long_accepts_bullish_impulse_away_from_sweep, test_long_rejects_bullish_bar_that_fails_to_leave_sweep, test_... |
| `tests/test_discover_zones_subset.py` | `TestTestsDiscoverZonesSubset` | Pytest coverage for test_default_is_the_full_canonical_order, test_default_vector_extraction_unchanged, test_exclusion_drops_exactly_the_named_dim_and_preserves_order, test_vect... |
| `tests/test_discussion.py` | `TestTestsDiscussion` | Pytest coverage for test_full_lists_all_turns, test_rewind_hides_later_turns, test_rewind_unknown_turn, test_digest_and_determinism. |
| `tests/test_disp_strength_filter.py` | `TestTestsDispStrengthFilter` | Pytest module defining TestDispStrengthFilter, TestCRTConfigDispStrengthField. |
| `tests/test_displacement_origin_kill.py` | `TestTestsDisplacementOriginKill` | Pytest coverage for test_long_kill_fires_when_close_is_below_the_displacement_origin, test_short_kill_fires_when_close_is_above_the_displacement_origin, test_a_wick_through_the_... |
| `tests/test_displacement_zone_event_study.py` | `TestTestsDisplacementZoneEventStudy` | Pytest coverage for test_find_displacement_starts_and_rare_entry_before. |
| `tests/test_doc_citations.py` | `TestTestsCitations` | Pytest coverage for test_mapped_docs_exist, test_active_models_citations_are_covered, test_every_code_citation_resolves. |
| `tests/test_dot_graph_context.py` | `TestTestsDotGraphContext` | Pytest coverage for test_file_to_module_basic, test_file_to_module_package_init, test_file_to_module_non_src_returns_none, test_resolve_flow_picks_runtime. |
| `tests/test_duckdb_query.py` | `TestDuckdbQueryViews` | Pytest coverage for DuckDB view helpers over Parquet projections. |
| `tests/test_engine_runner_dual_gate.py` | `TestTestsEngineRunnerDualGate` | Pytest coverage for test_dual_gate_trend_selects_breakout, test_dual_gate_range_selects_trap, test_dual_gate_neutral_low_confidence_rejects, test_layered_flow_fusion_runs_before... |
| `tests/test_engine_runner_rr_fusion.py` | `TestTestsEngineRunnerRrFusion` | Pytest coverage for test_rr_fusion_applies_score_before_fusion, test_rr_fusion_failure_falls_back_to_base_rr, test_rr_fusion_disabled_is_base_rr_identity, test_weighted_vote_fal... |
| `tests/test_episode_agreement.py` | `TestTestsEpisodeAgreement` | Pytest coverage for test_verdict_vocab, test_coherent_when_o11_same_event_and_o12_orthogonal, test_break_preserves_o11_conflict, test_partial_when_o11_insufficient. |
| `tests/test_episode_propositions.py` | `TestTestsEpisodePropositions` | Pytest coverage for test_relation_and_claim_vocab_closed, test_dir_sign_helpers, test_o11_same_event_when_dirs_align, test_o11_conflict_long_vs_bearish_shape. |
| `tests/test_evaluator.py` | `TestTestsEvaluator` | Pytest coverage for test_pearson_perfect_positive, test_pearson_perfect_negative, test_pearson_returns_zero_for_n_less_than_3, test_pearson_zero_variance_xs_returns_zero. |
| `tests/test_execution_contract_v1.py` | `TestTestsExecutionContractV1` | Pytest module defining TestBuildTradeGuards, TestBuildTradeImmutability, TestBuildTradeOutputCorrectness. |
| `tests/test_execution_loop.py` | `TestTestsExecutionLoop` | Pytest coverage for test_alert_send_returns_dict, test_alert_external_hook_called, test_alert_hook_failure_doesnt_crash, test_alert_stdout_print. |
| `tests/test_execution_planner.py` | `TestTestsExecutionPlanner` | Pytest coverage for test_breakout_long_approve, test_breakout_short_approve, test_pullback_long_approve, test_pullback_short_approve. |
| `tests/test_execution_planner_replay.py` | `TestTestsExecutionPlannerReplay` | Pytest coverage for test_retest_replay_appended_and_flushed, test_retest_replay_required_fields_present, test_accepted_record_has_no_reject_reason, test_structure_levels_long_an... |
| `tests/test_exit_model.py` | `TestTestsExitModel` | Pytest coverage for test_intrabar_trigger_sl_on_wick, test_intrabar_trigger_no_touch_returns_close, test_exit_model_default_is_intrabar, test_exit_model_config_close_only. |
| `tests/test_expansion_engine.py` | `TestTestsExpansionEngine` | Pytest coverage for test_mutate_decrease, test_mutate_increase, test_mutate_clips_to_floor, test_mutate_respects_max_param_change. |
| `tests/test_expansion_governance_bridge.py` | `TestTestsExpansionGovernanceBridge` | Pytest coverage for test_viability_passes_good_metrics, test_viability_fails_negative_pnl, test_viability_fails_zero_pnl, test_viability_fails_high_drawdown. |
| `tests/test_experiment_spec.py` | `TestTestsExperimentSpec` | Pytest coverage for test_authority_is_frozen_at_none, test_unknown_kind_rejected, test_unknown_selection_mode_rejected, test_explicit_mode_requires_versions. |
| `tests/test_extract_metrics.py` | `TestTestsExtractMetrics` | Pytest coverage for test_parses_one_block, test_stable_field_order, test_empty_input_is_empty, test_notes_optional. |
| `tests/test_f057_f058_config_authority.py` | `TestTestsF057F058` | Pytest coverage for test_classify_market_fails_closed_on_unknown_instrument, test_classify_market_crypto_majors_reclassified, test_classify_market_tolerates_filename_derived_hin... |
| `tests/test_fc1a_swing_causal.py` | `TestTestsFc1SwingCausal` | Pytest coverage for test_production_binds_to_causal_not_centered, test_centered_batch_preserved_byte_stable_vs_math, test_no_hybrid_graph_structure_uses_causal_refs, test_prefix... |
| `tests/test_fc1a_swing_oracle_parity.py` | `TestTestsFc1SwingOracle` | Pytest coverage for test_swing_features_declared, test_oracle_matches_pipeline_production_swings, test_oracle_matches_pipeline_centered_batch_identity, test_causal_is_centered_s... |
| `tests/test_fc1d_volregime_causal.py` | `TestTestsFc1DVolregime` | Pytest coverage for test_production_binds_to_rolling_not_global, test_prefix_invariance_production_volregime_interior, test_global_batch_preserved_as_research_column. |
| `tests/test_feature_certification_ledger.py` | `TestTestsFeatureCertificationLedger` | Pytest coverage for test_schema_file_is_valid_json, test_every_event_has_base_fields, test_per_event_required_extras, test_descriptive_only_no_authority_creep. |
| `tests/test_feature_contract_v1.py` | `TestTestsFeatureContractV1` | Pytest coverage for test_fc0_artifacts_exist, test_manifest_fc0_frozen, test_legacy_freeze_not_authoritative, test_fingerprint_shape. |
| `tests/test_feature_dag_invalidation.py` | `TestTestsFeatureDagInvalidation` | Pytest coverage for test_formula_hash_deterministic_and_sensitive, test_dependency_contract_hash_binds_to_promoted_dep_hash, test_ordering_gate_refuses_certify_with_unpromoted_d... |
| `tests/test_feature_dag_layers.py` | `TestTestsFeatureDagLayers` | Pytest coverage for test_is_acyclic_and_grounded, test_all_canonical_features_covered, test_layers_are_monotone, test_known_bugfixes_present. |
| `tests/test_feature_dag_rolling_certification.py` | `TestTestsFeatureDagRollingCertification` | Pytest coverage for test_series_parity_all_numeric_indicators, test_prefix_invariance, test_verdicts_certified. |
| `tests/test_feature_dag_structural_certification.py` | `TestTestsFeatureDagStructuralCertification` | Pytest coverage for test_both_oracles_match_pipeline, test_causal_online_oracle_is_prefix_invariant, test_inclusive_sweep_boundary_exercised_and_reproduced, test_double_sweep_wi... |
| `tests/test_feature_dependency_graph_fc05.py` | `TestTestsFeatureDependencyGraphFc` | Pytest coverage for test_fc05_artifacts_exist, test_dependency_graph_covers_all_contract_entries, test_known_swing_dependencies_present, test_pit_safe_not_claimed_over_leaking_t... |
| `tests/test_feature_layer_freeze.py` | `TestTestsFeatureFreeze` | Pytest coverage for test_freeze_policy_and_roadmap_exist, test_freeze_pin_schema_governance_class, test_feature_benchmark_is_xauusd_only, test_source_file_pins_match. |
| `tests/test_feature_lineage.py` | `TestTestsFeatureLineage` | Pytest coverage for test_registry_and_ontology_agree, test_every_entry_has_stable_id_version_lifecycle, test_formula_or_composition_present, test_registered_plus_resolve_impl. |
| `tests/test_feature_math_lint.py` | `TestTestsFeatureMathLint` | Pytest coverage for test_report_shape, test_floor_is_green, test_pins_have_no_stale_durable_keys, test_grandfather_set_monotonic. |
| `tests/test_feature_pipeline.py` | `TestTestsFeaturePipeline` | Pytest coverage for test_schema_completeness, test_vector_size, test_vector_row_count_matches_df, test_no_nan_in_vectors. |
| `tests/test_feature_rolling_indicators.py` | `TestTestsFeatureRollingIndicators` | Pytest coverage for test_rolling_indicator_declared_in_ontology, test_true_range_parity, test_atr_parity, test_rsi_14_parity. |
| `tests/test_feature_spec_schema.py` | `TestTestsFeatureSpecSchema` | Pytest coverage for test_validate_registry_is_clean, test_spec_schema_block_exists, test_every_entry_carries_all_spec_blocks, test_semantics_are_populated. |
| `tests/test_feature_states.py` | `TestTestsFeatureStates` | Pytest coverage for test_vector_bound_set_is_exactly_the_declared_one, test_nonvector_stateful_identities_are_known_but_not_vector_bound, test_bindings_derive_from_ontology_not_... |
| `tests/test_feature_structural_states.py` | `TestTestsFeatureStructuralStates` | Pytest coverage for test_trend_bias_ontology_id, test_trend_bias_matches_sign_of_ema_spread, test_trend_bias_forced_bullish_and_bearish, test_higher_high_lower_low_ontology_ids. |
| `tests/test_feature_structural_states_complex.py` | `TestTestsFeatureStructuralStatesComplex` | Pytest coverage for test_complex_structural_ontology_ids, test_break_of_structure_domain, test_liquidity_sweep_domain, test_double_sweep_domain. |
| `tests/test_feature_surface_query.py` | `TestTestsFeatureSurfaceQuery` | Pytest coverage for test_loads_39_vector_members, test_get_by_name_and_feature_id, test_wick_size_aliases_candle_range, test_joined_fields_present. |
| `tests/test_feature_temporal_context.py` | `TestTestsFeatureTemporalContext` | Pytest coverage for test_hour_of_day_is_timestamp_hour, test_hour_of_day_bounds_from_ontology, test_session_states_match_ontology_ordinals, test_every_hour_maps_to_ontology_sess... |
| `tests/test_feature_volume_spike_parity.py` | `TestTestsFeatureVolumeSpikeParity` | Pytest coverage for test_volume_spike_ontology_declared, test_adaptive_volume_spike_parity_promote_stage, test_adaptive_volume_spike_parity_full_pipeline, test_volume_spike_domain. |
| `tests/test_feature_warmup_coupling.py` | `TestTestsFeatureWarmupCoupling` | Pytest coverage for test_derived_warmup_matches_measured_drop, test_derived_warmup_is_prefix_only, test_warmup_scales_with_its_config_windows, test_active_config_warmup_covers_p... |
| `tests/test_finalize_survivorship.py` | `TestTestsFinalizeSurvivorship` | Pytest module defining TestFinalizeSurvivorship. |
| `tests/test_findings_export.py` | `TestTestsFindingsExport` | Pytest coverage for test_render_is_deterministic, test_every_finding_exported_exactly_once, test_meta_line_identifies_the_generator, test_nonterminal_records_carry_evidence. |
| `tests/test_flow_explorer.py` | `TestTestsFlowExplorer` | Pytest coverage for test_list_flows_has_ordered_modules_and_io, test_get_flow_and_flow_code, test_module_detail_code_role_and_io, test_module_helpers_fail_open. |
| `tests/test_flow_manifests.py` | `TestTestsFlowManifests` | Pytest coverage for test_manifests_present, test_manifest_shape, test_doc_exists, test_modules_and_entrypoint_resolve. |
| `tests/test_fm021_retest_depth_certification.py` | `TestTestsFm021RetestDepth` | Pytest coverage for test_dag_deps_include_close, test_intended_quantity_is_gated_not_kernel_only, test_oracle_independent_of_derived_math_source, test_gate_window_lag9_lag10. |
| `tests/test_fm027_displacement_retrace_certification.py` | `TestTestsFm027DisplacementRetrace` | Pytest coverage for test_oracle_does_not_import_derived_math_as_source, test_oracle_parity_with_derived_math_and_registry, test_zero_body_returns_zero, test_clip_high_and_bounds. |
| `tests/test_fm030_031_implementation_validation.py` | `TestTestsFm030031Validation` | Pytest coverage for test_all_four_questions_answered_yes, test_recorded_ledger_shas, test_regime_discrimination_recorded, test_entry_sets_nest_and_crt_is_invariant. |
| `tests/test_fm030_031_normalization_basis.py` | `TestTestsFm030031Normalization` | Pytest coverage for test_active_config_default_is_legacy_basis, test_legacy_arm_reproduces_legacy_formula, test_corrected_equals_legacy_over_close, test_scale_invariance_correct... |
| `tests/test_fm058_boundary_is_not_sp001.py` | `TestTestsFm058BoundarySp` | Pytest coverage for test_feature_family_producers_do_not_import_the_decision_kernel, test_the_two_boundaries_genuinely_disagree, test_resolver_still_exposes_both_families_as_a_c... |
| `tests/test_fm_ownership_matrix.py` | `TestTestsFmOwnershipMatrix` | Pytest coverage for test_ownership_matrix_artifact_exists, test_ownership_matrix_schema_and_invariants, test_ownership_matrix_builder_check_clean, test_g001_attribution_artifact... |
| `tests/test_fm_resolution_phase2.py` | `TestTestsFmResolutionPhase2` | Pytest coverage for test_resolve_fm002_identity_candle_range, test_resolve_fm027_identity_displacement_retrace, test_resolve_fm028_identity_displacement_atr_ratio, test_fm010_co... |
| `tests/test_fm_resolution_phase3.py` | `TestTestsFmResolutionPhase3` | Pytest coverage for test_phase3b_fm029_identity, test_bind_phase3b_scoring_callables, test_scoring_engine_module_binds_fm029, test_compute_scores_uses_fm029_math. |
| `tests/test_formula_registry.py` | `TestTestsFormulaRegistry` | Pytest coverage for test_ontology_file_exists_and_declares_authority, test_registry_and_ontology_agree, test_body_ratio_composition_is_canonical_body_over_range, test_compositio... |
| `tests/test_forward_walk_adverse_fill.py` | `TestTestsForwardWalkAdverseFill` | Pytest coverage for test_default_fixed_stop_is_exactly_minus_one_r, test_default_ignores_a_gap_open_entirely, test_default_works_without_an_open_attribute, test_long_gap_open_be... |
| `tests/test_framework_registry.py` | `TestTestsFrameworkRegistry` | Pytest coverage for test_registry_loads_valid_jsonl, test_every_evidence_path_exists, test_every_finding_exists, test_no_dangling_parent. |
| `tests/test_fusion_and_validator_regression.py` | `TestTestsFusionValidatorRegression` | Pytest coverage for test_fusion_accepts_engine_results_without_canonical_validation, test_convergence_layered_uses_weighted_score_not_flat_average, test_fusion_compute_passes_we... |
| `tests/test_fusion_weights_config_only.py` | `TestTestsFusionWeightsConfig` | Pytest coverage for test_cfg_require_raises_on_missing_weight, test_runtime_reads_each_weight_via_cfg_require_not_get, test_active_production_config_supplies_all_fusion_weights. |
| `tests/test_gate2b_closure.py` | `TestTestsGate2BClosure` | Pytest coverage for test_closure_ids_exact, test_every_record_complete, test_unknowns_carry_gate5_or_reason, test_family_registry_consistent. |
| `tests/test_gate5_lineage_report.py` | `TestTestsGate5LineageReport` | Pytest module defining TestGate5LineageReport. |
| `tests/test_gate_intelligence.py` | `TestTestsGateIntelligence` | Pytest module defining TestDeterminism, TestThreshold, TestComponents. |
| `tests/test_gate_sync.py` | `TestTestsGateSync` | Pytest coverage for test_fitness_weight_sync, test_fitness_weights_sum_to_one, test_tuner_fitness_weights_sum_to_one, test_expected_keys_present. |
| `tests/test_gaussian_impl_switch.py` | `TestTestsGaussianImplSwitch` | Pytest coverage for test_tradenet_schema_is_32, test_gaussian_schema_is_32, test_schema_object_attribute_and_dict_access, test_validate_vector_with_label. |
| `tests/test_gaussian_live_parameterization.py` | `TestTestsGaussianLiveParameterization` | Pytest coverage for test_no_registry_entry_carries_mu_or_sigma, test_registry_has_active_pointers_for_the_resolving_instruments, test_successful_registry_load_still_yields_defau... |
| `tests/test_gaussian_nb_schema_contract.py` | `TestTestsGaussianNbSchemaContract` | Pytest coverage for test_aliases_match_schema_v3_contract, test_resolve_trained_feature_name_aliases_and_live, test_resolve_v3_38_schema_is_alignable_subset, test_assert_model_s... |
| `tests/test_gaussian_registry_retry_cache.py` | `TestTestsGaussianRegistryRetryCache` | Pytest coverage for test_failed_registry_load_is_cached_not_retried_every_compute, test_preload_failure_also_sets_resolved, test_mtime_advance_allows_single_retry_after_miss, te... |
| `tests/test_gaussian_update_pipeline.py` | `TestTestsGaussianUpdatePipeline` | Pytest coverage for test_abort_on_insufficient_data, test_phase5_rejection_skips_registration, test_happy_path_approved_and_promoted, test_promote_false_skips_promotion. |
| `tests/test_gd004_gd005_identity_closure.py` | `TestTestsGd004Gd005` | Pytest coverage for test_fm029_scalar_parity_vs_old_inline, test_fm029_negative_move_passthrough, test_compute_scores_byte_identical, test_gd005_route_parity_vs_old_inline. |
| `tests/test_geometry_census.py` | `TestTestsGeometryCensus` | Pytest coverage for test_positive_fixture_detected, test_eps_floor_flagged, test_guarded_np_where_flagged, test_md1_alias_is_transport_not_derivation. |
| `tests/test_gitignore_schema.py` | `TestTestsGitignoreSchema` | Pytest coverage for test_schema_and_gitignore_exist, test_gitignore_declares_schema_classes, test_local_occupancy_is_ignored, test_tracked_bindings_are_not_ignored. |
| `tests/test_goal_alignment.py` | `TestTestsGoalAlignment` | Pytest coverage for test_metrics_dict_omits_trades_per_month_without_months, test_metrics_dict_computes_trades_per_month_when_months_given, test_avg_rr_proxy_matches_expectancy_... |
| `tests/test_goal_metrics.py` | `TestTestsGoalMetrics` | Pytest coverage for test_trades_per_month_span_derived, test_trades_per_month_zero_span_is_zero, test_goal_report_attached_as_telemetry. |
| `tests/test_goal_schema.py` | `TestTestsGoalSchema` | Pytest coverage for test_from_prod_config_parses_all_fields, test_partial_goal_allows_undeclared_bounds, test_disabled_spec_is_advisory_off, test_absent_section_fail_soft. |
| `tests/test_goal_validator.py` | `TestTestsGoalValidator` | Pytest coverage for test_disabled_spec_is_pass_noop, test_all_targets_met_passes, test_program1_reality_fails_frequency_and_expectancy, test_missing_metric_is_skip_not_fail. |
| `tests/test_governance_invariant_check.py` | `TestTestsGovernanceCheck` | Pytest coverage for test_requires_run_on_governed_prefixes, test_requires_run_on_governed_files, test_requires_run_skips_exempt_paths, test_policy_constants_are_named_and_typed. |
| `tests/test_grok_agentic_ai.py` | `TestTestsGrokAgenticAi` | Pytest coverage for test_product_name, test_strip_ask_prefix, test_detect_specialists, test_intent_maps. |
| `tests/test_grok_intent_workbook.py` | `TestTestsGrokIntentWorkbook` | Pytest coverage for test_tmp_row_count_matches_subprocess_collect, test_every_grok_test_module_appears, test_section9_goldens, test_collect_failed_stub_overwrites. |
| `tests/test_handoff_state.py` | `TestTestsHandoffState` | Pytest coverage for test_handoff_exists, test_protocol_and_roles_exist, test_required_keys_present, test_actors_are_real_roles. |
| `tests/test_historical_zone_mapper.py` | `TestTestsHistoricalZoneMapper` | Pytest coverage for test_from_prod_config_knobs, test_map_frame_length_and_schema, test_map_frame_import_isolation, test_parity_vs_zone_cluster_helper. |
| `tests/test_historical_zone_mapper_corpus_parity.py` | `TestTestsHistoricalZoneMapperCorpus` | Pytest coverage for test_corpus_parity_mapper_vs_engine_runner_zone_stage, test_corpus_sample_count_and_integrity, test_session_windows_hardening_accepts_string_bounds. |
| `tests/test_hour_of_day_certification.py` | `TestTestsHourDayCertification` | Pytest coverage for test_dag_deps_timestamp_only, test_intended_quantity_adjudicated, test_oracle_not_series_dt_hour, test_parity_and_boundaries. |
| `tests/test_htf_builder_window.py` | `TestTestsHtfBuilderWindow` | Pytest coverage for test_window_16_flips_only_on_every_16th_bar, test_window_4_flips_every_4th_bar. |
| `tests/test_htf_objective.py` | `TestTestsHtfObjective` | Pytest coverage for test_none_without_bias, test_long_exists_inside_range, test_long_achieved_at_or_above_href, test_long_invalidated_below_lref. |
| `tests/test_htf_objective_gate.py` | `TestTestsHtfObjectiveGate` | Pytest coverage for test_gate_off_ignores_none_objective, test_gate_on_denies_none_objective, test_gate_on_allows_exists, test_active_config_objective_gate_defaults_off. |
| `tests/test_htf_state.py` | `TestTestsHtfState` | Pytest coverage for test_htf_state_is_a_separate_enum, test_first_pair_reversal_prev_bull_broke_low, test_expansion_breaks_high_with_large_range, test_accumulation_small_inside. |
| `tests/test_hypothesis_registry.py` | `TestTestsHypothesisRegistry` | Pytest coverage for test_registry_loads_valid_jsonl, test_every_finding_exists, test_every_model_exists, test_every_code_hypothesis_exists. |
| `tests/test_identity_store.py` | `TestTestsIdentity` | Pytest coverage for test_no_recompute_producer_imports, test_l0_roundtrip_preserved, test_l0_missing_corpus_snapshot_unidentified, test_l0_hash_mismatch. |
| `tests/test_jsonl_claim_catalog.py` | `TestTestsJsonlClaimCatalog` | Pytest coverage for test_primary_catalog_loads_and_is_advisory, test_no_g001_or_promotion_keys_anywhere, test_ids_are_unique_and_namespaced, test_closed_enums_hold. |
| `tests/test_jsonl_claim_grounding.py` | `TestTestsJsonlClaimGrounding` | Pytest coverage for test_jsonl_is_a_claim_kind_and_refused_is_a_status, test_unknown_claim_kind_still_unanswerable, test_grounding_to_dict_carries_the_new_keys_on_every_kind, te... |
| `tests/test_jsonl_to_parquet_family.py` | `TestTestsJsonlParquetFamily` | Pytest coverage for test_crt_construction_defaults_to_engine_state_after, test_bar_structure_still_partitions_on_crt_state_after, test_unknown_family_has_no_partition, test_fore... |
| `tests/test_jsonl_writer.py` | `TestTestsJsonlWriter` | Pytest coverage for test_append_then_read_roundtrip, test_read_missing_returns_empty, test_read_skips_corrupt_lines, test_fail_silent_swallows_vs_raises. |
| `tests/test_layer_audit_manifest.py` | `TestTestsAuditManifest` | Pytest coverage for test_manifest_schema_shape, test_active_artifacts_exist_and_hashes_match, test_closure_verdict_guard, test_pass_a_leaves_ohlcv_unclosed. |
| `tests/test_live_hook_crt_config_plumbing.py` | `TestTestsLiveHookCrtConfig` | Pytest coverage for test_merged_config_carries_crt_engine, test_crt_engine_is_nested_not_flattened, test_sl_atr_buffer_resolves_strictly, test_tp_multipliers_reach_behaviour. |
| `tests/test_live_integration.py` | `TestTestsLiveIntegration` | Pytest module defining TestTelegramBridge, TestMT5Bridge, TestRegisterTradeOutcome. |
| `tests/test_live_rail_bar_builder.py` | `TestTestsLiveRailBarBuilder` | Pytest coverage for test_same_period_does_not_emit, test_period_boundary_emits_prior_bar, test_gap_does_not_synthesize_bars, test_time_reverse_fail_closed. |
| `tests/test_live_rail_binance_ws.py` | `TestTestsLiveRailBinanceWs` | Pytest coverage for test_factory_returns_binance_adapter, test_start_refuses_xauusd, test_start_refuses_non_utc_clock, test_start_refuses_without_websockets. |
| `tests/test_live_rail_cli.py` | `TestTestsLiveRail` | Pytest coverage for test_refuse_without_paper_flag, test_refuse_missing_config. |
| `tests/test_live_rail_contracts.py` | `TestTestsLiveRailContracts` | Pytest coverage for test_experimental_example_loads, test_missing_key_is_require_not_silent_default, test_timeframe_seconds_must_not_be_declared_on_bar_builder, test_emit_incomp... |
| `tests/test_live_rail_dm001_atr.py` | `TestTestsLiveRailDm001` | Pytest coverage for test_hook_crt_levels_arg_is_price_unit, test_xauusd_sl_buffer_uses_absolute_atr. |
| `tests/test_live_rail_dry_run_tool.py` | `TestTestsLiveRailDryRun` | Pytest coverage for test_source_has_no_live_engine_hook_or_simulate_one, test_missing_history_refuses, test_short_history_refuses_without_process, test_warm_history_calls_proces... |
| `tests/test_live_rail_feeder.py` | `TestTestsLiveRailFeeder` | Pytest coverage for test_warmup_matches_required_warmup_rows, test_not_ready_before_or_at_warmup_prefix, test_ready_on_first_bar_after_prefix, test_as_trade_data_has_all_require... |
| `tests/test_live_rail_hook_xor.py` | `TestTestsLiveRailHookXor` | Pytest coverage for test_decision_is_approve_is_case_insensitive, test_default_hook_submit_orders_is_false, test_xor_on_submits_when_approve_any_case, test_emit_live_io_xor_off_... |
| `tests/test_live_rail_orchestrator.py` | `TestTestsLiveRailOrchestrator` | Pytest coverage for test_from_config_refuses_without_env, test_from_config_refuses_when_disabled, test_factory_binance_returns_adapter, test_context_requires_feeder. |
| `tests/test_live_rail_order_manager.py` | `TestTestsLiveRailOrderManager` | Pytest coverage for test_submit_approve_paper_fill, test_submit_rejects_without_approve, test_submit_rejects_zero_size, test_no_atr_in_order_manager_source. |
| `tests/test_live_rail_replay_cert.py` | `TestTestsLiveRailReplayCert` | Pytest coverage for test_corpus_reader_rejects_missing_columns, test_corpus_reader_rejects_non_monotonic_timestamps, test_bar_to_ticks_round_trips_through_bar_builder, test_roun... |
| `tests/test_live_rail_tickdb.py` | `TestTestsLiveRailTickdb` | Pytest coverage for test_tickdb_replays_sample_via_tmp, test_tickdb_seq_gap_fail_closed, test_tickdb_time_reverse_fail_closed, test_tickdb_naive_ts_refused. |
| `tests/test_live_rail_ultron_adapter.py` | `TestTestsLiveRailUltronAdapter` | Pytest coverage for test_preflight_pass, test_preflight_kill_switch, test_preflight_duplicate_and_daily_limit. |
| `tests/test_llm_connectivity.py` | `TestTestsLlmConnectivity` | Pytest module defining TestBuildPrompt, TestLlmScore, TestGroqScore. |
| `tests/test_llm_project_assistant_log.py` | `TestTestsLlmProjectAssistantLog` | Pytest coverage for test_workflow_log_exists_and_is_doctrine_headed, test_every_entry_has_core_fields, test_every_entry_has_iso_date, test_entry_count_is_bounded. |
| `tests/test_m15_structural_range.py` | `TestTestsM15StructuralRange` | Pytest coverage for test_range_alias_is_the_named_object, test_from_child_window_matches_max_high_min_low, test_detect_legacy_name_is_same_object, test_htf_builder_is_not_the_ra... |
| `tests/test_magnitude_states.py` | `TestTestsMagnitudeStates` | Pytest coverage for test_registry_accepts_phase2a_magnitude_identities, test_ontology_declares_all_magnitude_identities, test_bin_ordered_half_open_edges, test_body_commitment_i... |
| `tests/test_market_context.py` | `TestTestsMarketContext` | Pytest coverage for test_dimensions_follow_vocabulary_order_and_membership, test_expected_dimensions_exist, test_unknown_key_raises, test_missing_required_state_raises_listing_t... |
| `tests/test_market_reality_contract.py` | `TestTestsMarketRealityContract` | Pytest coverage for test_real_contract_loads_cleanly, test_real_contract_has_no_duplicate_authority_key, test_dimensions_this_program_unblocked_carry_evidence, test_every_dimens... |
| `tests/test_market_shape.py` | `TestTestsMarketShape` | Pytest coverage for test_real_spec_loads_with_expected_shapes, test_unsatisfiable_trend_continuation_stays_blocked, test_malformed_specs_raise_at_load, test_shape_id_determinist... |
| `tests/test_markov_regime_forecaster.py` | `TestTestsMarkovRegimeForecaster` | Pytest coverage for test_forecast_series_deterministic, test_forecasts_are_valid_or_none, test_no_lookahead_truncation_stable, test_no_global_rank_leak. |
| `tests/test_measurement_contract.py` | `TestTestsMeasurementContract` | Pytest coverage for test_required_profiles_present, test_profile_shape_and_id_namespace, test_subordination_is_declared_and_points_at_the_frozen_schema, test_relationship_declar... |
| `tests/test_measurement_profile_calibration.py` | `TestTestsMeasurementProfileCalibration` | Pytest coverage for test_metals_calibration_is_measured, test_metals_provenance_manifest_exists_and_hash_matches, test_metals_values_match_the_source_manifest, test_metals_decla... |
| `tests/test_measurement_result_log.py` | `TestTestsMeasurementResultLog` | Pytest coverage for test_none_basis_is_n_a, test_complete_basis_is_declared, test_every_one_of_the_five_keys_is_required, test_l5_basis_tuple_really_is_three_keys_without_geometry. |
| `tests/test_meta_governor_executor.py` | `TestTestsMetaGovernorExecutor` | Pytest coverage for test_log_governance_event_writes_jsonl_with_required_fields, test_log_governance_event_normalizes_non_dict_payloads, test_log_governance_event_validates_requ... |
| `tests/test_metrics_v2.py` | `TestTestsMetricsV2` | Pytest coverage for test_long_tp_hit_matches_oracle, test_long_sl_hit_matches_oracle, test_short_tp_hit_matches_oracle, test_timeout_matches_oracle. |
| `tests/test_miar_registry.py` | `TestTestsMiarRegistry` | Pytest coverage for test_miar_charter_exists, test_miar_has_exactly_seventeen_entries, test_miar_required_fields_complete, test_miar_alignment_tokens_valid. |
| `tests/test_model_evidence.py` | `TestTestsModelEvidence` | Pytest coverage for test_missing_binding_field_is_a_load_error, test_duplicate_engine_key_is_a_load_error, test_non_string_engine_key_is_a_load_error, test_producer_without_outp... |
| `tests/test_model_paths_literals.py` | `TestTestsModelPathsLiterals` | Pytest coverage for test_debt_file_exists_and_schema, test_approved_modules_include_model_paths, test_model_paths_may_contain_models_root_constant, test_no_new_unauthorized_mode... |
| `tests/test_model_paths_resolver.py` | `TestTestsModelPathsResolver` | Pytest coverage for test_model_paths_point_at_existing_registries, test_resolve_zone_gate_runtime_matches_how_and_identity, test_resolve_zone_gate_how_mismatch_fail_closed, test... |
| `tests/test_model_registry.py` | `TestTestsModelRegistry` | Pytest coverage for test_assert_single_active_passes_with_zero, test_assert_single_active_passes_with_one, test_assert_single_active_raises_with_two, test_save_atomic_produces_v... |
| `tests/test_model_resolver_enumeration.py` | `TestTestsModelResolverEnumeration` | Pytest coverage for test_families_are_the_known_set, test_enumerate_finds_more_versions_than_are_selected, test_enumeration_is_deterministic, test_rows_are_registry_entries. |
| `tests/test_model_runners_adapters.py` | `TestTestsModelRunnersAdapters` | Pytest coverage for test_every_runnable_model_has_an_adapter_branch, test_new_stage1_and_stage4_ids_are_registered, test_execution_plan_registration_was_retracted_and_built, tes... |
| `tests/test_model_runners_execution_plan.py` | `TestTestsModelRunnersExecutionPlan` | Pytest coverage for test_execution_plan_is_runnable_not_blocked, test_balance_comes_from_config_not_an_invented_default, test_fails_closed_when_balance_key_absent, test_divergen... |
| `tests/test_model_runners_schema_resolver.py` | `TestTestsModelRunnersSchemaResolver` | Pytest coverage for test_registry_has_the_three_known_generations, test_canonical_39_is_the_live_schema, test_both_38_dim_schemas_share_live_names_but_differ_on_trained_names, t... |
| `tests/test_model_shadow_protocol.py` | `TestTestsModelShadowProtocol` | Pytest coverage for test_stats_computes_expectancy_and_pf, test_stats_empty_book, test_stats_to_edge_report_none_on_empty_book, test_stats_to_edge_report_shim_carries_only_measu... |
| `tests/test_module_attribution.py` | `TestTestsAttribution` | Pytest coverage for test_every_src_module_is_enumerated_exactly_once, test_no_module_is_claimed_twice, test_ids_are_unique_and_well_formed, test_census_discovers_no_build_residue. |
| `tests/test_msip_shadow_crt_phase_not_identity.py` | `TestTestsMsipShadowCrtPhase` | Pytest coverage for test_vector_complete_without_crt_observation, test_crt_state_change_does_not_change_what_fields. |
| `tests/test_msip_shadow_determinism.py` | `TestTestsMsipShadowDeterminism` | Pytest coverage for test_two_run_byte_identical. |
| `tests/test_msip_shadow_failure_modes.py` | `TestTestsMsipShadowFailureModes` | Pytest coverage for test_enabled_missing_config_id_fail_closed, test_enabled_wrong_schema_version_fail_closed, test_disabled_when_enabled_false, test_nan_feature_is_partial_not_... |
| `tests/test_msip_shadow_integration_pipeline.py` | `TestTestsMsipShadowIntegrationPipeline` | Pytest coverage for test_pipeline_to_shadow_emits_vectors. |
| `tests/test_msip_shadow_isolation_imports.py` | `TestTestsMsipShadowIsolationImports` | Pytest coverage for test_no_forbidden_mutation_calls_in_shadow_package, test_shadow_emitter_source_has_no_try_star, test_package_files_exist. |
| `tests/test_msip_shadow_neutrality_vs_crt.py` | `TestTestsMsipShadowNeutralityVs` | Pytest coverage for test_observe_crt_state_is_pure_and_optional, test_build_market_state_does_not_require_crt_for_identity, test_shadow_flags_always_false_on_and_off. |
| `tests/test_msip_shadow_schema_validation.py` | `TestTestsMsipShadowSchemaValidation` | Pytest coverage for test_schema_version_pin, test_shadow_flags_cannot_be_true, test_required_dimensions_present, test_missing_feature_marks_partial. |
| `tests/test_msip_shadow_what_how_separation.py` | `TestTestsMsipShadowSeparation` | Pytest coverage for test_how_labels_emit_provenance_and_twins, test_overrides_cannot_change_source_features, test_crt_local_source_features_forbidden, test_absent_section_is_dis... |
| `tests/test_ohlcv_clock_provenance.py` | `TestTestsOhlcvClockProvenance` | Pytest coverage for test_no_record_raises, test_unreviewed_record_raises, test_reviewed_and_matching_sha_passes, test_sha_drift_reopens_review. |
| `tests/test_ohlcv_corpus_freeze.py` | `TestTestsOhlcvCorpusFreeze` | Pytest coverage for test_freeze_policy_exists, test_freeze_pin_schema, test_freeze_pins_match_on_disk_or_authorized_decision. |
| `tests/test_ohlcv_open_close_label.py` | `TestTestsOhlcvOpenCloseLabel` | Pytest coverage for test_lattice, test_open_forming_mutation, test_close_forming_mutation, test_no_mutation_is_insufficient_not_close. |
| `tests/test_ohlcv_output_contract.py` | `TestTestsOhlcvOutputContract` | Pytest coverage for test_contract_schema_shape, test_proven_requires_non_narrative_evidence, test_proven_without_enforcer_needs_executable_evidence, test_fail_closed_verdict_con... |
| `tests/test_ohlcv_tick_attribution.py` | `TestTestsOhlcvTickAttribution` | Pytest coverage for test_c0_counts_everything, test_c1_excludes_the_upper_boundary_tick, test_c2_drops_planted_exact_duplicate_and_c1_does_not, test_c3_counts_only_price_changin... |
| `tests/test_ohlcv_volume_semantics.py` | `TestTestsOhlcvVolumeSemantics` | Pytest coverage for test_exact_match_confirms, test_small_directional_gap_is_approximate_not_confirmed, test_large_mismatch_contradicts, test_fewer_than_min_bars_is_insufficient. |
| `tests/test_ontology_config_parity.py` | `TestTestsOntologyConfigParity` | Pytest coverage for test_declared_config_keys_resolve, test_lookback_matches_singular_config_key, test_plural_config_keys_declare_and_match_lookback, test_formula_tokens_resolve. |
| `tests/test_oss_lab.py` | `TestTestsOssLab` | Pytest coverage for test_registry_loads_and_validates, test_external_t4_forbidden, test_dataset_manifest_matches_phase1_binding, test_tradelatest_adapter_normalizes_without_inve... |
| `tests/test_p4_observability.py` | `TestTestsP4Observability` | Pytest module defining TestCanglesSinceRetest, TestSafeFormatter, TestIntentLift. |
| `tests/test_p_struct_01_displacement_evidence.py` | `TestTestsPStruct01Displacement` | Pytest coverage for test_row_keys_do_not_grow_from_interesting_counts, test_legal_predecessors_are_sweep_only, test_happy_path_unknown_n_and_direction_join, test_age_one_is_stil... |
| `tests/test_parent_candle_builder.py` | `TestTestsParentCandleBuilder` | Pytest coverage for test_supported_rules_covers_h1_h4_d1_w1_mn1, test_unsupported_rule_raises_at_construction, test_parent_candle_is_none_until_first_close, test_parent_candle_n... |
| `tests/test_parent_crt_feed.py` | `TestTestsParentCrtFeed` | Pytest coverage for test_bias_none_until_first_parent_closes, test_first_closed_parent_is_c1_bias_still_none, test_golden_narrative_bias_only_after_c3_close, test_no_lookahead_o... |
| `tests/test_parent_crt_pivotality.py` | `TestTestsParentCrtPivotality` | Pytest coverage for test_config_ab_valid_when_only_parent_crt_enabled_differs, test_config_ab_invalid_when_params_differ, test_config_ab_invalid_when_config_hash_differs, test_c... |
| `tests/test_parent_crt_track.py` | `TestTestsParentCrtTrack` | Pytest coverage for test_initial_state_before_any_candle, test_first_candle_ever_becomes_c1_without_a_transition_check, test_golden_narrative_long_side, test_golden_narrative_sh... |
| `tests/test_parent_crt_wiring.py` | `TestTestsParentCrtWiring` | Pytest coverage for test_backtest_run_constructs_feed_and_threads_parent_state, test_opposing_parent_bias_rejects_at_execution_filter, test_agreeing_parent_bias_does_not_parent_... |
| `tests/test_parquet_store.py` | `TestParquetStoreProjections` | Pytest coverage for JSONL→Parquet projection store. |
| `tests/test_pattern_hasher.py` | `TestTestsPatternHasher` | Pytest module defining _FakeTransition, TestCRTPathCodes, TestEncodeCrtPath. |
| `tests/test_perp_funding_fetcher.py` | `TestTestsPerpFundingFetcher` | Pytest coverage for test_normalize_funding_schema, test_normalize_basis_schema, test_pagination_advances_no_dup, test_pagination_non_advancing_raises. |
| `tests/test_phase1_duplicate_formula_identity_closure.py` | `TestTestsPhase1DuplicateFormula` | Pytest coverage for test_frozen_candidate_gate, test_registry_loads_and_unique_ids, test_no_feature_id_multi_formula, test_source_tick_volume_identity_on_xauusd. |
| `tests/test_phase1_run15a_quantity_roles.py` | `TestTestsPhase1Run15` | Pytest coverage for test_artifacts_exist, test_denominator_exactly_142, test_no_quantity_id_disappears, test_exactly_one_primary_role_no_unknown. |
| `tests/test_phase1_run1_legacy_baseline.py` | `TestTestsPhase1Run1` | Pytest coverage for test_run1_artifacts_exist, test_prior_fc_artifacts_preserved, test_legacy_baseline_status_shape, test_universe_has_explicit_unknowns_and_classes. |
| `tests/test_phase5_calibration.py` | `TestTestsPhase5Calibration` | Pytest coverage for test_phase5_config_loads_defaults, test_phase5_config_honours_prod_config_values, test_make_calibration_fn_returns_callable, test_calibration_fn_result_has_r... |
| `tests/test_pit_prefix_invariance.py` | `TestTestsPitPrefixInvariance` | Pytest coverage for test_all_canonical_production_columns_prefix_invariant, test_no_unwindowed_rank_feeds_production. |
| `tests/test_plan001_retest_min_depth_how.py` | `TestTestsPlan001RetestMin` | Pytest coverage for test_dataclass_default_is_legacy_tenth, test_default_parity_matches_legacy_literal, test_dynamism_how_value_changes_floor, test_fail_closed_rejects_negative_... |
| `tests/test_plan002_dual_weights_how.py` | `TestTestsPlan002DualWeights` | Pytest coverage for test_dataclass_defaults_are_legacy, test_conf_weights_not_aliased, test_riskscore_final_default_parity, test_riskscore_dynamism_and_engine_injection. |
| `tests/test_portfolio_allocator.py` | `TestTestsPortfolioAllocator` | Pytest coverage for test_tracker_add_position, test_tracker_multiple_positions, test_tracker_remove_position, test_tracker_remove_nonexistent_returns_none. |
| `tests/test_predicate_definition_binding.py` | `TestTestsPredicateDefinitionBinding` | Pytest coverage for test_all_definitions_are_valid, test_sp003_is_declared_deferred_not_silently_missing, test_operator_vocabulary_is_pinned, test_sp001_definition_binds_to_stru... |
| `tests/test_production_bundle.py` | `TestTestsProductionBundle` | Pytest coverage for test_status_algebra_covers_all_four_quadrants, test_bundle_covers_every_family, test_bundle_reports_the_active_version, test_selected_is_not_the_same_questio... |
| `tests/test_promotion_engine_overrides.py` | `TestTestsPromotionEngineOverrides` | Pytest coverage for test_legacy_config_hash_is_params_only_and_unchanged, test_config_hash_full_present_and_covers_overrides, test_no_override_entry_is_backward_compatible, test... |
| `tests/test_provenance_ledger.py` | `TestTestsProvenanceLedger` | Pytest coverage for test_derived_without_a_derivation_block_is_rejected, test_derived_naming_an_unregistered_rule_is_rejected, test_derived_with_a_wrong_rule_version_is_rejected... |
| `tests/test_query_trace.py` | `TestTestsQueryTrace` | Pytest coverage for test_list_shows_crt_construction, test_sql_counts_live_rows, test_default_report_is_descriptive, test_events_discover_excludes_foreign_populations. |
| `tests/test_rare_zone_context_filter_eval.py` | `TestTestsRareZoneContextFilter` | Pytest coverage for test_context_precision_sweep_beats_range. |
| `tests/test_rare_zone_detection_eval.py` | `TestTestsRareZoneDetectionEval` | Pytest coverage for test_precision_recall_synthetic, test_evaluate_all_includes_baselines. |
| `tests/test_rare_zone_fa_characterization.py` | `TestTestsRareZoneFaCharacterization` | Pytest coverage for test_classify_range_to_sweep_and_tp_disp, test_characterize_partitions_fa_by_zone. |
| `tests/test_reachability_golden.py` | `TestTestsReachabilityGolden` | Pytest coverage for test_config_summary_matches_committed_report, test_registry_summary_matches_golden. |
| `tests/test_reasoning_capabilities.py` | `TestTestsReasoningCapabilities` | Pytest coverage for test_map_file_shape, test_completeness_every_model_accounted_for, test_overlap_is_declared_never_silent, test_no_capability_asserted_orthogonal_without_evide... |
| `tests/test_regime_classifier.py` | `TestTestsRegimeClassifier` | Pytest coverage for test_classify_high_volatility, test_classify_high_volatility_overrides_trending, test_classify_trending, test_classify_ranging_default. |
| `tests/test_regime_conditioning.py` | `TestTestsRegimeConditioning` | Pytest coverage for test_evaluate_scope_deterministic, test_verdict_vocabulary_and_structure, test_planted_regime_edge_is_exploitable, test_no_edge_cannot_be_exploitable. |
| `tests/test_regime_observer.py` | `TestTestsRegimeObserver` | Pytest coverage for test_label_series_deterministic, test_labels_are_valid_or_none, test_no_lookahead_truncation_stable, test_no_global_rank_leak. |
| `tests/test_resample_completeness.py` | `TestTestsResampleCompleteness` | Pytest coverage for test_complete_m15_yields_complete_h1_buckets, test_complete_m15_yields_complete_h4_bucket, test_resample_is_associative_h1_then_h4_equals_h4, test_missing_m1... |
| `tests/test_research_dag_provenance.py` | `TestTestsResearchDagProvenance` | Pytest coverage for test_every_rule_id_has_a_declared_class, test_e2_inline_citation_on_resolvable_finding, test_e1_structured_field_on_manifest_objective, test_i1_hypothesis_ba... |
| `tests/test_research_family_registry.py` | `TestTestsResearchFamilyRegistry` | Pytest coverage for test_registry_schema_and_invariant, test_layer_definitions_complete, test_execution_order_is_strict_and_records_the_rejected_alternative, test_required_famil... |
| `tests/test_resolver_metadata.py` | `TestTestsResolverMetadata` | Pytest coverage for test_behavior_neutral, test_metadata_does_not_advance_memory_on_its_own, test_l2_map_has_19_keys, test_l2_map_is_wider_than_classify_alone. |
| `tests/test_resolver_supply.py` | `TestTestsResolverSupply` | Pytest coverage for test_plan_sources_canonical_from_vector_and_only_nonvector_from_enriched, test_nothing_beyond_the_contract_is_passed, test_missing_nonvector_feature_fails_cl... |
| `tests/test_retrace_reset_direction.py` | `TestTestsRetraceResetDirection` | Pytest coverage for test_long_pullback_half_body_resets, test_long_continuation_does_not_reset, test_long_shallow_pullback_does_not_reset, test_short_pullback_half_body_resets. |
| `tests/test_retrieval_pipeline.py` | `TestTestsRetrievalPipeline` | Pytest module defining TestCorpusDiscoverer, TestChunker, TestEmbedder. |
| `tests/test_roi_gaps.py` | `TestTestsRoiGaps` | Pytest coverage for test_funnel_counts_field_exists, test_funnel_counts_populated_from_external_dict, test_crt_config_tp3_defaults_off, test_trade_tp3_price_default_zero. |
| `tests/test_roi_metrics.py` | `TestTestsRoiMetrics` | Pytest coverage for test_roi_block_basic_math, test_roi_block_no_losses_uses_sentinel, test_roi_block_divzero_guards, test_to_dict_exposes_roi_keys. |
| `tests/test_rr_confidence_gate.py` | `TestTestsRrConfidenceGate` | Pytest coverage for test_legacy_scalar_is_exact_threshold_parity, test_default_shipped_mode_matches_active_config, test_chi2_sf_known_values, test_chi2_sf_monotonic_decreasing. |
| `tests/test_rr_contract_wiring.py` | `TestTestsRrContractWiring` | Pytest coverage for test_decision_engine_constructs_without_rr_threshold, test_decision_engine_ignores_polarity_rr, test_decision_engine_does_not_gate_on_economic_rr, test_low_r... |
| `tests/test_rr_fusion_fail_closed_dim.py` | `TestTestsRrFusionFailClosed` | Pytest coverage for test_predict_rejects_overlong_vector_no_truncate, test_predict_rejects_short_vector, test_predict_exact_width_still_runs, test_live_canonical_vector_is_rejec... |
| `tests/test_rr_fusion_full_vector.py` | `TestTestsRrFusionFullVector` | Pytest coverage for test_score_dict_starves_the_model_to_three_features, test_score_full_feeds_many_features, test_config_knob_default_is_false. |
| `tests/test_runtime_benchmark_suite.py` | `TestTestsRuntimeBenchmarkSuite` | Pytest coverage for test_policy_and_token, test_pin_authority_separation_from_feature_freeze, test_rb1_gate_pair_provenance, test_rb1_artifacts_rehash_when_retained. |
| `tests/test_runtime_boundary.py` | `TestTestsRuntimeBoundary` | Pytest coverage for test_kernel_does_not_import_research, test_research_and_interpreters_are_research_side, test_kernel_packages_are_kernel_side, test_interpreters_classified_re... |
| `tests/test_scanner_ranker.py` | `TestTestsScannerRanker` | Pytest coverage for test_universe_returns_all_default_symbols, test_universe_filter_crypto, test_universe_filter_fx, test_universe_unknown_class_returns_empty. |
| `tests/test_schema_contracts.py` | `TestTestsSchemaContracts` | Pytest coverage for test_canonical_features_is_tuple, test_no_duplicates, test_feature_count, test_feature_index_map. |
| `tests/test_schema_v4_artifact_reconciliation.py` | `TestTestsSchemaV4Artifact` | Pytest coverage for test_schema_is_v4, test_v3_read_aliases_exist_for_historical_records, test_zone_v4_is_the_promoted_active_version, test_zone_v4_mu_sigma_are_byte_identical_t... |
| `tests/test_script_matrix_sync.py` | `TestTestsMatrixSyncTests_1` | Pytest coverage for test_inputs_exist, test_script_matrix_covers_every_registry_id, test_matrix_regenerates_byte_identical. |
| `tests/test_script_registry.py` | `TestTestsRegistry` | Pytest coverage for test_authority_pinned, test_category_has_no_terminal_names, test_validate_record_accepts_minimal_stub, test_validate_record_rejects_unknown_keys. |
| `tests/test_semantic_grounding.py` | `TestTestsSemanticGrounding` | Pytest coverage for test_claim_kinds_and_relations_are_closed, test_unknown_claim_kind_is_unanswerable, test_live_concept_noun_is_grounded, test_live_contract_noun_is_grounded. |
| `tests/test_semantic_identity.py` | `TestTestsSemanticIdentity` | Pytest coverage for test_live_registry_with_identities_is_clean, test_live_registry_with_identities_is_clean_in_strict_mode, test_identity_ids_are_unique_and_globally_disjoint, ... |
| `tests/test_semantic_identity_workbooks.py` | `TestTestsSemanticIdentityWorkbooks` | Pytest coverage for test_scripts_workbook_headers_appended_not_inserted, test_src_workbook_headers_appended_not_inserted, test_tests_workbook_headers_appended_not_inserted, test... |
| `tests/test_semantic_os.py` | `TestTestsSemanticOs` | Pytest coverage for test_live_registry_is_clean, test_live_registry_is_clean_in_strict_mode, test_registry_is_non_empty, test_every_concept_has_nonempty_why_it_exists. |
| `tests/test_semantic_os_objects.py` | `TestTestsSemanticOsObjects` | Pytest coverage for test_universe_is_disk_not_an_artifact, test_universe_covers_all_three_trees, test_all_universe_adds_tests, test_unknown_universe_is_rejected. |
| `tests/test_semantic_query.py` | `TestTestsSemanticQuery` | Pytest coverage for test_question_registry_is_closed, test_unknown_question_raises, test_authoritative_on_live_concept, test_missing_target_is_unanswerable_or_ambiguous. |
| `tests/test_semantic_registry.py` | `TestTestsSemanticRegistry` | Pytest coverage for test_structural_profiles_are_clean, test_semantic_registry_is_clean, test_frozen_registry_unchanged, test_spec_schema_declares_contract. |
| `tests/test_session_certification.py` | `TestTestsSessionCertification` | Pytest coverage for test_dag_deps_timestamp_only, test_intended_quantity_not_unadjudicated, test_exhaustive_24h, test_transitions. |
| `tests/test_session_classifier.py` | `TestTestsSessionClassifier` | Pytest coverage for test_every_hour_classifies_exactly_once, test_out_of_range_hour_raises, test_default_window_table_is_the_documented_one, test_all_five_values_are_reachable. |
| `tests/test_session_log.py` | `TestTestsSessionLog` | Pytest coverage for test_session_log_exists_and_is_doctrine_headed, test_every_entry_has_core_fields, test_session_log_entry_count_is_bounded, test_no_corrupted_markers. |
| `tests/test_session_log_commit_check.py` | `TestTestsSessionLogCommitCheck` | Pytest coverage for test_requires_log_only_for_governed_paths, test_nolog_escape_detection, test_valid_today_entry_requires_today_and_core_fields, test_check_decision_matrix. |
| `tests/test_session_override.py` | `TestTestsSessionOverride` | Pytest coverage for test_resolve_global_only_canonicalizes, test_resolve_override_wins_case_insensitive, test_resolve_unlisted_instrument_falls_back_to_global, test_resolve_retu... |
| `tests/test_session_timestamp_basis.py` | `TestTestsSessionTimestampBasis` | Pytest coverage for test_broker_local_is_byte_identical_to_raw_timestamp_hour, test_broker_local_matches_pin, test_missing_key_raises, test_unrecognised_value_raises. |
| `tests/test_shadow_cross_range_probe.py` | `TestTestsShadowCrossRangeProbe` | Pytest coverage for test_bucket_shadow_cross_range, test_bucket_never_folds_missing_id_into_same_range, test_build_contingency_counts_each_episode_once, test_self_consistency_ch... |
| `tests/test_shadow_promotion_gate.py` | `TestTestsShadowPromotionGate` | Pytest coverage for test_default_min_shadow_trades_is_positive, test_injected_governance_config_sets_min_trades, test_init_validates_min_trades_must_be_integer, test_init_valida... |
| `tests/test_shadow_ttl_lifecycle.py` | `TestTestsShadowTtlLifecycle` | Pytest coverage for test_creating_bar_does_not_decrement_ttl, test_non_htf_reset_before_creation_leaves_ttl_untouched, test_shadow_survives_configured_ttl_then_expires, test_mat... |
| `tests/test_shape_hypothesis_pit.py` | `TestTestsShapeHypothesisPit` | Pytest coverage for test_detect_raises_on_injected_stream_field, test_detect_emits_signal_on_clean_inputs, test_detect_silent_when_no_shape_signal, test_shape_identity_is_prefix... |
| `tests/test_shape_statistics.py` | `TestTestsShapeStatistics` | Pytest coverage for test_horizons_and_min_samples_are_required_keywords, test_bad_horizons_raise, test_bad_min_samples_raises, test_exclusions_are_counted_and_reconcile. |
| `tests/test_signal_audit.py` | `TestTestsSignalAudit` | Pytest coverage for test_audit_recorder_full_lifecycle, test_audit_leak_detection_triggers, test_audit_noop_when_debug_false, test_audit_multiple_bars_appended. |
| `tests/test_signal_belief_tracker.py` | `TestTestsSignalBeliefTracker` | Pytest module defining TestBeliefState, TestNeutralCandle, TestHighConvictionGate. |
| `tests/test_sl_tp_comparator.py` | `TestTestsSlTpComparator` | Pytest module defining TestDeriveIntent, TestComputeLegacyLevels, TestSimulateExit. |
| `tests/test_smc_break_event_memo.py` | `TestTestsSmcEventMemo` | Pytest coverage for test_precomputed_break_events_are_bit_identical, test_default_argument_still_recomputes, test_wrong_events_would_change_the_answer. |
| `tests/test_smc_primitives.py` | `TestTestsSmcPrimitives` | Pytest coverage for test_signed_atr_distance_zero_atr_returns_zero_not_nan, test_signed_atr_distance_bounded_by_tanh, test_detect_causal_swings_needs_full_window, test_is_mitiga... |
| `tests/test_soft_conf_ema_probe.py` | `TestTestsSoftConfEmaProbe` | Pytest coverage for test_double_update_equals_closed_form_alpha, test_alpha_eff_888_and_555_for_production_ema_periods, test_double_update_compresses_spread_in_monotone_trend, t... |
| `tests/test_sprint7_governance.py` | `TestTestsSprint7Governance` | Pytest module defining TestStrategyMetrics, TestStrategyBacktester, TestMultiStrategyValidator. |
| `tests/test_stack_version.py` | `TestTestsStackVersion` | Pytest coverage for test_determinism, test_churn_guarantee, test_sensitivity_to_active_formula_change, test_inert_model_insensitivity. |
| `tests/test_stage1_dataset_builder.py` | `TestTestsStage1DatasetBuilder` | Pytest coverage for test_rr_bucket_boundaries_inclusive_lower_exclusive_upper, test_duration_bucket_boundaries_inclusive_lower_exclusive_upper, test_bucket_version_is_stamped, t... |
| `tests/test_state_contracts.py` | `TestTestsStateContracts` | Pytest coverage for test_load_production_active_models_succeeds, test_state_set_parity_with_crtstate, test_transition_graph_parity_with_valid_transitions, test_fm_ids_resolve. |
| `tests/test_state_topology_phase.py` | `TestTestsStateTopologyPhase` | Pytest coverage for test_build_graph_from_production_bundle, test_crt_engine_injects_who_topology, test_restricted_graph_blocks_legal_module_edge, test_unknown_state_name_fail_c... |
| `tests/test_strategy_orchestrator.py` | `TestTestsStrategyOrchestrator` | Pytest coverage for test_strategy_instantiates, test_strategy_no_trade_path, test_s2_buy_signal, test_s3_buy_signal. |
| `tests/test_strategy_registry.py` | `TestTestsStrategyRegistry` | Pytest coverage for test_from_active_config_projects_governed_sections, test_content_hash_is_stable_and_order_independent, test_content_hash_changes_with_content, test_to_dict_f... |
| `tests/test_structural_profiles.py` | `TestTestsStructuralProfiles` | Pytest coverage for test_seed_profiles_validate, test_all_four_foundings_are_declared, test_the_incumbent_is_declared_alongside_research, test_profiles_do_not_disturb_the_existi... |
| `tests/test_structural_shape_lint.py` | `TestTestsStructuralShapeLint` | Pytest coverage for test_repository_has_no_structural_shape_copies, test_detector_fires_on_a_new_copy, test_detector_does_not_fire_on_innocent_compares, test_legitimate_producer... |
| `tests/test_structure_predicates.py` | `TestTestsStructurePredicates` | Pytest coverage for test_slice_is_the_pinned_one, test_sweep_parity_over_pinned_slice_with_non_vacuity_guard, test_impulse_parity_over_pinned_slice_with_non_vacuity_guard, test_... |
| `tests/test_three_authority_drift_adjudication.py` | `TestTestsThreeAuthorityDriftAdjudication` | Pytest coverage for test_artifacts_exist, test_exactly_six_drift_records, test_every_census_drift_represented_exactly_once, test_no_extra_drift_records. |
| `tests/test_three_authority_surplus_census.py` | `TestTestsThreeAuthoritySurplusCensus` | Pytest coverage for test_artifacts_exist, test_schema_and_status, test_freshness_summary_matches_live_scan, test_surplus_record_ids_stable. |
| `tests/test_topic_docs.py` | `TestTestsTopic` | Pytest coverage for test_topics_dir_exists_with_index_and_template, test_every_topic_doc_is_dated, test_every_topic_doc_has_required_sections. |
| `tests/test_trade_provenance_ledger.py` | `TestTestsTradeProvenanceLedger` | Pytest coverage for test_build_provenance_base_resolves_identity, test_build_provenance_base_honors_explicit_strategy_id, test_build_provenance_base_never_raises_on_bad_instrume... |
| `tests/test_tradenet_v2_pipeline.py` | `TestTestsTradenetV2Pipeline` | Pytest coverage for test_first_deploy_two_instruments_isolated, test_upgrade_one_instrument_does_not_touch_other, test_regression_guard_blocks_then_force_bypasses, test_rollback... |
| `tests/test_train_pipeline.py` | `TestTestsTrainPipeline` | Pytest coverage for test_validate_passes_on_sufficient_clean_data, test_validate_raises_below_minimum, test_validate_raises_on_empty_dataset, test_validate_skips_record_missing_... |
| `tests/test_trainer.py` | `TestTestsTrainer` | Pytest module defining TestStandardScaler, TestGaussianNBModel, TestTrainGaussian. |
| `tests/test_trap_validator.py` | `TestTestsTrapValidator` | standalone integration tests for trap_validator_engine. |
| `tests/test_trend_strength_certification.py` | `TestTestsTrendStrengthCertification` | Pytest coverage for test_dag_deps_close_only, test_intended_quantity_pinned, test_first_finite_index_29, test_constant_zero_and_linear_sign. |
| `tests/test_turn_ledger.py` | `TestTestsTurnLedger` | Pytest coverage for test_parse_handoff_block, test_append_stores_verbatim_and_indexes, test_append_only_no_shrink, test_verify_detects_tampering. |
| `tests/test_tv_forensic_smoke.py` | `TestTestsTvForensicSmoke` | Pytest coverage for test_entry_script_parses, test_all_top_level_scripts_parse, test_engine_data_imports_and_epoch_roundtrips, test_engine_data_resolve_offset_picks_the_matching... |
| `tests/test_uat_runner.py` | `TestTestsUatRunner` | Pytest coverage for test_mc_insufficient_data, test_mc_all_wins, test_mc_all_losses_high_ruin, test_mc_mixed_trades_structure. |
| `tests/test_ultron_gate.py` | `TestTestsUltronGate` | Pytest module defining TestPenaltyApplication, TestPercentileGate, TestDailyQuota. |
| `tests/test_ultron_risk_gate.py` | `TestTestsUltronRiskGate` | Pytest coverage for test_happy_path_approve, test_approve_updates_portfolio_state, test_approve_no_expires_at, test_approve_execution_id_propagated. |
| `tests/test_ultron_wrapper.py` | `TestTestsUltron` | Pytest coverage for test_wrapper_always_calls_through_to_gate, test_wrapper_calls_gate_on_rejection_too, test_wrapper_scales_risk_for_range_regime, test_wrapper_no_scaling_for_t... |
| `tests/test_unified_replay_harness.py` | `TestTestsUnifiedReplayHarness` | Pytest coverage for test_derive_symbol_from_filename. |
| `tests/test_validation_access.py` | `TestTestsValidationAccess` | Pytest coverage for test_s_fail_blocks_ife, test_i_fail_blocks_fe_after_s_pass, test_full_sequence_e_open_is_ladder_complete, test_f_partial_still_runs_e. |
| `tests/test_validator_session_overrides.py` | `TestTestsValidatorSessionOverrides` | Pytest coverage for test_validator_applies_per_instrument_override, test_validator_without_engine_runner_is_unchanged. |
| `tests/test_vector_fixture_freshness.py` | `TestTestsVectorFixtureFreshness` | Pytest coverage for test_fixture_exists, test_fixture_record_count, test_fixture_schema_matches, test_fixture_dimensions. |
| `tests/test_visual_state_harness.py` | `TestTestsVisualStateHarness` | Pytest coverage for test_engine_to_visual_maps_direction_not_state_name, test_labeling_html_leaks_no_answer, test_leaky_surface_is_rejected_mutation, test_context_window_never_r... |
| `tests/test_volatility_regime_certification.py` | `TestTestsVolatilityRegimeCertification` | Pytest coverage for test_dag_deps_ohlc_roots, test_intended_quantity_pinned, test_tr0_nan_and_atr_first_14, test_bin_boundaries. |
| `tests/test_who_numeric_dependency_census.py` | `TestTestsNumericDependencyCensus` | Pytest coverage for test_artifacts_exist, test_exactly_57_declarations, test_population_equals_surplus_census, test_unique_canonical_ids. |
| `tests/test_workflow_dag_coverage.py` | `TestTestsWorkflowDagCoverage` | Pytest coverage for test_every_pipeline_stage_is_represented_in_the_dag, test_replay_and_backtest_stage_present. |
| `tests/test_xau_metals_protocol_v1.py` | `TestTestsXauMetalsProtocolV` | Pytest coverage for test_protocol_id_and_status, test_cost_primary_is_fixed_usd_not_12bps, test_cost_r_math_and_net, test_entry_ontology_is_retest_not_sweep. |
| `tests/test_xauusd_gaussian_econ_ledger_e1.py` | `TestTestsXauusdGaussianEconLedger` | Pytest coverage for test_e1_quantiles_use_train_only, test_e1_top_decile_membership_uses_train_threshold, test_e1_kill_no_skill, test_e1_kill_skill_signal_still_not_authority. |
| `tests/test_xauusd_gaussian_econ_units_e0.py` | `TestTestsXauusdGaussianEconUnits` | Pytest coverage for test_e0_journal_holdout_and_label_counts, test_e0_model_n_features_is_39, test_e0_registry_active_pointer_xauusd, test_e0_script_module_exports. |
| `tests/test_xauusd_gaussian_m4_e2.py` | `TestTestsXauusdGaussianM4` | Pytest coverage for test_e2_module_constants, test_e2_build_outcomes_chronological, test_e2_m4_rejects_negative_expectancy. |
| `tests/test_xauusd_phase1_frozen_candidate.py` | `TestTestsXauusdPhase1Frozen` | Pytest coverage for test_binding_file_shape_and_forbidden_labels, test_module_constants_match_on_disk_and_binding, test_require_phase1_frozen_candidate_green, test_reject_wrong_... |
| `tests/test_zone_census.py` | `TestTestsZoneCensus` | Pytest coverage for test_census_occupancy_coverage_dwell_transitions. |
| `tests/test_zone_cluster_threshold_rename.py` | `TestTestsZoneClusterThresholdRename` | Pytest coverage for test_active_engine_runner_uses_zone_cluster_threshold, test_engine_runner_defaults_fixture_uses_new_key, test_engine_runner_source_reads_zone_cluster_thresho... |
| `tests/test_zone_gate.py` | `TestTestsZoneGate` | Pytest module defining TestComputeGaussianScore, TestCheckReturnContract. |
| `tests/test_zone_gate_alignment.py` | `TestTestsZoneGateAlignment` | Pytest coverage for test_name_anchored_equals_positional_at_current_schema, test_registry_feature_order_matches_live_schema_today, test_longer_order_is_not_truncated, test_short... |
| `tests/test_zone_gate_instrumentation.py` | `TestTestsZoneGateInstrumentation` | Pytest coverage for test_force_pass_overrides_block_but_logs_real, test_force_pass_high_score_real_passed_is_true, test_normal_mode_pass_counter_increments, test_normal_mode_blo... |
| `tests/test_zone_gate_min_samples.py` | `TestTestsZoneGateMinSamples` | Pytest module defining TestUnderpoweredBypass, TestPoweredRegistryEnforces, TestEdgeCases. |
| `tests/test_zone_gate_top_k.py` | `TestTestsZoneGateTopK` | Pytest coverage for test_top_n_slices_top_scores, test_top_n_capped_by_zone_count, test_top_scores_are_sorted_descending, test_default_top_n_is_three. |
| `tests/test_zone_label_audit.py` | `TestTestsZoneLabelAudit` | Pytest coverage for test_membership_verified_when_stats_reproduce, test_membership_permuted_same_size_is_not_verified, test_membership_count_mismatch_is_failed, test_bootstrap_c... |
| `tests/test_zone_manifest_runtime_parity.py` | `TestTestsZoneManifestRuntimeParity` | Pytest coverage for test_active_zone_manifest_matches_runtime. |
| `tests/test_zone_scale_free_mask.py` | `TestTestsZoneScaleFreeMask` | Pytest coverage for test_v3_weights_are_reproduced_exactly, test_v3_has_25_active_dims, test_both_names_for_the_candle_range_dim_are_masked, test_v4_schema_zeroes_candle_range. |

### `tests/Claude/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/Claude/__init__.py` | `ClaudeApi` | Independent semantic-auditor suite (Claude, families J-M). |
| `tests/Claude/_fixtures.py` | `TestClaudeFixtures` | Minimal fixtures for the Claude semantic-auditor suite. |
| `tests/Claude/test_J_directional_displacement.py` | `TestClaudeJDirectionalDisplacement` | Pytest coverage for test_sweep_to_displacement_edge_is_legal_but_geometry_still_refuses, test_wrong_sign_is_rejected_before_the_energy_gate, test_sweep_event_direction_outranks_... |
| `tests/Claude/test_K_smc_identity.py` | `TestClaudeKSmcIdentity` | Pytest coverage for test_schema_is_48_dim_v5_with_a_nine_slot_smc_tail, test_no_smc_feature_name_is_a_crt_state, test_no_crt_state_name_is_a_canonical_feature, test_smc_primitiv... |
| `tests/Claude/test_L_schema_artifact_staleness.py` | `TestClaudeLSchemaArtifactStaleness` | Pytest coverage for test_retired_schema_name_in_a_trained_order_raises, test_a_stale_registry_cannot_produce_a_pass, test_v3_aliases_are_migration_vocabulary_not_a_scoring_fallb... |
| `tests/Claude/test_M_reachability_vs_certification.py` | `TestClaudeMReachabilityVsCertification` | Pytest coverage for test_parent_crt_is_armed_on_the_active_config, test_objective_gate_stays_off_by_default, test_process_candle_parent_keywords_default_to_none, test_crt_closur... |

### `tests/Grok/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/Grok/__init__.py` | `GrokApi` | Independent semantic-auditor suite. |
| `tests/Grok/_fixtures.py` | `TestGrokFixtures` | Minimal CRT fixtures for semantic-auditor tests. |
| `tests/Grok/test_A_crt_journeys.py` | `TestGrokCrtJourneys` | Pytest coverage for test_declared_spine_edges_are_in_valid_transitions, test_impossible_direct_range_to_execution_is_rejected, test_impossible_retest_to_sweep_is_rejected, test_... |
| `tests/Grok/test_B_provenance.py` | `TestGrokBProvenance` | Pytest coverage for test_traced_short_sl_reproduces_from_named_operands, test_substitute_retest_atr_changes_sl, test_substitute_wrong_candle_extreme_changes_sl_and_guard, test_s... |
| `tests/Grok/test_C_parity.py` | `TestGrokCParity` | Pytest coverage for test_feature_windows_and_filter_windows_are_not_the_same_object, test_nineteen_hundred_is_feature_newyork_and_filter_off_session, test_score_time_counts_matc... |
| `tests/Grok/test_D_semantic_os.py` | `TestGrokDSemanticOs` | Pytest coverage for test_unknown_ownership_relation_does_not_invent_an_edge, test_invented_relation_is_unanswerable_not_a_new_kind, test_relationship_without_endpoints_is_unknow... |
| `tests/Grok/test_E_config_split_brain.py` | `TestGrokEConfigSplitBrain` | Pytest coverage for test_active_version_is_the_tier0_pointer, test_bare_builder_is_not_the_production_runtime_object, test_production_allowed_sessions_are_canonical_uppercase, t... |
| `tests/Grok/test_F_unit_scale.py` | `TestGrokFUnitScale` | Pytest coverage for test_relative_atr_as_sl_operand_is_not_a_protective_buffer, test_price_scaled_momentum_is_not_a_z_score, test_range_size_is_price_not_percent, test_rr_on_inv... |
| `tests/Grok/test_G_time_semantics.py` | `TestGrokGTimeSemantics` | Pytest coverage for test_filter_window_is_inclusive_on_both_ends, test_feature_window_is_half_open_on_the_hour, test_broker_summer_offset_is_minus_three_hours, test_utc_correcte... |
| `tests/Grok/test_H_ingestion.py` | `TestGrokHIngestion` | Pytest coverage for test_row_gate_rejects_high_lt_low, test_row_gate_rejects_close_above_high, test_row_gate_rejects_negative_volume, test_loader_stream_rejects_impossible_ohlc. |
| `tests/Grok/test_I_parent_htf_journeys.py` | `TestGrokIParentHtfJourneys` | Pytest coverage for test_parent_spine_edges_are_in_valid_transitions, test_range_c1_self_loop_is_legal_unlike_m15_range, test_m15_cannot_hop_into_parent_states, test_parent_cann... |

### `tests/analytics/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/analytics/test_golden_ledgers.py` | `TestAnalyticsGoldenLedgers` | Pytest coverage for test_fixture_A_mixed, test_fixture_B_all_losers, test_fixture_C_no_trades, test_fixture_D_single_winner. |
| `tests/analytics/test_metric_invariants.py` | `TestAnalyticsMetricInvariants` | Pytest coverage for test_profit_factor_identity, test_expectancy_two_forms_agree, test_win_rate_identity, test_max_drawdown_rr_matches_independent_walk. |
| `tests/analytics/test_metrics_oracle_parity.py` | `TestAnalyticsMetricsOracleParity` | Pytest coverage for test_trade_count_parity, test_win_rate_parity, test_profit_factor_parity, test_expectancy_parity. |

### `tests/cognitive/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/cognitive/test_cognitive_bus.py` | `TestCognitiveBus` | Pytest coverage for test_emit_nonblocking, test_drop_telemetry, test_health_keys, test_backpressure_flag. |

### `tests/config_layer/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/config_layer/test_instrument_overrides.py` | `TestConfigInstrumentOverrides` | Pytest coverage for test_resolver_hit_case_insensitive_and_coerced, test_resolver_miss_returns_empty, test_resolver_no_block_returns_empty, test_resolver_unknown_key_raises. |

### `tests/data_ingestion/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/data_ingestion/test_ohlcv_schema.py` | `TestDataIngestionOhlcvSchema` | Pytest coverage for test_require_columns_raises_on_each_missing, test_require_columns_multi_missing_sorted, test_require_columns_custom_source_in_message, test_require_columns_h... |
| `tests/data_ingestion/test_session_autoderive.py` | `TestDataIngestionSessionAutoderive` | Pytest coverage for test_mask_learns_weekday_only, test_is_tradable_by_mask_respects_holidays, test_autoderive_accepts_no_sunday_broker, test_autoderive_still_catches_weekday_hole. |
| `tests/data_ingestion/test_strict_fetch_gate.py` | `TestDataIngestionStrictFetchGate` | Pytest coverage for test_crypto_single_missing_5min_bar_hard_stops, test_fx_weekday_hole_hard_stops, test_fx_complete_grid_across_weekend_passes, test_holiday_closure_passes_onl... |

### `tests/engines/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/engines/test_tradenet_meta_engine.py` | `TestEnginesTradenetMetaEngine` | Pytest coverage for test_fallback_on_no_model, test_output_keys, test_quality_tiers, test_risk_authority_match. |

### `tests/events/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/events/test_event_fabric.py` | `TestEventsEventFabric` | Pytest coverage for test_envelope_fields_present, test_generation_monotonic, test_generation_thread_safe, test_schema_hash_present. |

### `tests/exec_telemetry/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/exec_telemetry/test_report.py` | `TestExecTelemetryReport` | Pytest coverage for test_retcode_name_map, test_fill_rate_and_retcode_histogram, test_slippage_side_normalized_adverse, test_latency_distribution. |

### `tests/execution/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/execution/test_execution_intent_v1_0.py` | `TestExecutionIntentV10` | Pytest coverage for test_minimal_state_set, test_propose_is_start_state, test_legal_transitions_return_new_frozen_snapshots, test_terminal_states_have_no_exit. |

### `tests/features/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/features/test_feature_schema_registry.py` | `TestFeaturesFeatureSchemaRegistry` | Pytest coverage for test_feature_order_hash_format, test_register_match, test_register_mismatch, test_unregistered_fail_closed. |
| `tests/features/test_liquidity_distance.py` | `TestFeaturesLiquidityDistance` | Pytest coverage for test_liquidity_distance_no_lookahead, test_value_range, test_pressure_score_range, test_zero_atr_handled. |

### `tests/governance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/governance/test_bar_structure_grounding.py` | `TestGovernanceBarStructureGrounding` | Pytest coverage for test_cannot_class_refuses_regardless_of_file_contents, test_gapless_identified_stream_grounds, test_a_coverage_hole_is_refused, test_missing_identity_is_refu... |
| `tests/governance/test_crt_divergence_taxonomy.py` | `TestGovernanceCrtDivergenceTaxonomy` | Pytest coverage for test_every_category_code_has_a_declared_correspondence, test_no_stale_correspondence_entries, test_named_reject_reasons_exist_in_the_live_enum, test_reject_r... |
| `tests/governance/test_crt_predicate_supply_contract.py` | `TestGovernanceCrtPredicateSupplyContract` | Pytest coverage for test_shipped_config_constructs_clean, test_feature_states_naming_a_non_stateful_feature_raises, test_feature_states_naming_an_unknown_ontology_state_raises, ... |
| `tests/governance/test_crt_resolver_links.py` | `TestGovernanceCrtResolverLinks` | Pytest coverage for test_default_is_every_link_off, test_base_variant_enables_nothing, test_base_variant_is_behaviourally_the_default, test_shipped_when_blocks_survive_filtering... |
| `tests/governance/test_crt_variant_surface.py` | `TestGovernanceCrtVariantSurface` | Pytest coverage for test_variant_without_rationale_is_refused, test_variant_without_id_is_refused, test_valid_variant_constructs, test_align_drops_out_of_range_source_indices. |
| `tests/governance/test_design_schema_identity_selectors.py` | `TestGovernanceSchemaIdentitySelectors` | Pytest coverage for test_files_exist, test_identity_selector_fields_block_byte_identical, test_identity_selector_fields_parsed_equal. |
| `tests/governance/test_documentation_drift_protocol.py` | `TestGovernanceDocumentationDriftProtocol` | Pytest coverage for test_protocol_doc_exists, test_protocol_doc_states_invariant, test_protocol_doc_has_five_steps, test_protocol_doc_has_gate_and_completion_criterion. |
| `tests/governance/test_epistemic_invariants.py` | `TestGovernanceEpistemicInvariants` | Pytest module defining TestEpistemicInvariantE001A, TestEpistemicInvariantE001E, TestEpistemicInvariantEvidenceLink. |
| `tests/governance/test_falsify_record_binding.py` | `TestGovernanceFalsifyRecordBinding` | Pytest coverage for test_every_artifact_is_git_tracked, test_rule1_measurement_object_cites_registered_id_or_declares_absence, test_rule2_population_id_is_registered, test_rule2... |
| `tests/governance/test_occupancy_series_identity.py` | `TestGovernanceOccupancySeriesIdentity` | Pytest coverage for test_frozen_v1_marker_survives, test_occupancy_series_identity_is_named, test_bar_occupancy_pk_unchanged, test_constructor_id_is_lineage_not_pk. |
| `tests/governance/test_provenance_remediation.py` | `TestGovernanceProvenanceRemediation` | Pytest module defining TestProvenanceRemediation. |
| `tests/governance/test_semantic_review_protocol.py` | `TestGovernanceSemanticReviewProtocol` | Pytest coverage for test_charter_exists, test_charter_declares_no_authority, test_charter_has_non_duplication_clause, test_charter_states_five_review_questions. |

### `tests/harness/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/harness/conftest.py` | `PytestSharedFixturesHarness` | Shared fixtures for the ERP anti-hallucination test harness (T0). |
| `tests/harness/test_anti_hallucination.py` | `TestHarnessAntiHallucination` | Pytest coverage for test_ah01_wrong_summary_fails, test_ah02_missing_manifest_raises, test_ah03_empty_or_failed_run_never_success, test_ah04_program_json_metrics_carry_artifact_... |
| `tests/harness/test_run_manifest.py` | `TestHarnessRunManifest` | Pytest coverage for test_build_manifest_populates_all_required_fields, test_build_manifest_fail_closed_on_missing_field, test_write_read_roundtrip_and_hash_ok, test_tampered_ass... |
| `tests/harness/test_validation_path.py` | `TestHarnessValidationPath` | Pytest coverage for test_vp01_manifest_records_lens_and_env, test_vp02_matching_manifest_has_no_violations, test_vp02_wrong_lens_is_flagged, test_vp03_wrong_label_source_is_flag... |

### `tests/helpers/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/helpers/__init__.py` | `HelpersApi` | Test helpers (not production code). |
| `tests/helpers/fc1a_swing_oracle.py` | `TestHelpersFc1SwingOracle` | pure pandas/numpy from OHLC + k. |

### `tests/inout/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/inout/test_inout-1.py` | `TestInout1` | Pytest module defining TestINOUTConfig, TestINOUTDatabase, TestINOUTScanner. |
| `tests/inout/test_probability_engine.py` | `TestInoutProbabilityEngine` | Pytest module defining TestDataExtractor, TestApproachA, TestApproachB. |

### `tests/interpreters/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/interpreters/test_interpreter_contract.py` | `TestInterpretersInterpreterContract` | Pytest coverage for test_reference_interpreters_satisfy_protocol, test_base_defaults_and_version, test_observation_time_is_last_bar_and_trace_id_deterministic, test_determinism_... |
| `tests/interpreters/test_invariant_guards.py` | `TestInterpretersGuards` | Pytest coverage for test_reference_explain_is_inert, test_meta_is_unused. |
| `tests/interpreters/test_pnf_shadow_e2e.py` | `TestInterpretersPnfShadowE2` | Pytest coverage for test_pnf_chain_runs_on_real_data, test_pnf_qualification_returns_verdict_not_promote, test_pnf_chain_deterministic_by_hash. |
| `tests/interpreters/test_point_and_figure.py` | `TestInterpretersPointFigure` | Pytest coverage for test_eventkind_has_pnf_members, test_double_top_breakout_detected, test_double_bottom_breakdown_detected, test_flat_series_no_signals. |
| `tests/interpreters/test_reference_interpreter_e2e.py` | `TestInterpretersReferenceInterpreterE2` | Pytest coverage for test_chain_runs_and_produces_edgereport, test_qualification_returns_a_verdict_not_promote, test_chain_is_deterministic_by_hash. |
| `tests/interpreters/test_reference_ma_cross.py` | `TestInterpretersReferenceMaCross` | Pytest coverage for test_fast_slow_validation, test_no_cross_emits_no_events, test_detects_both_directions_over_oscillation, test_observe_is_deterministic. |

### `tests/journal/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/journal/test_trade_execution_link_v1_0.py` | `TestJournalTradeExecutionLinkV` | Pytest coverage for test_requires_trade_id_and_venue, test_magic_not_required_identity_survives_missing_transport, test_is_frozen, test_dict_round_trip_with_optional_fields. |
| `tests/journal/test_trade_identity_v1_0.py` | `TestJournalTradeIdentityV1` | Pytest coverage for test_sacred_minimum_fields_only, test_new_mints_and_stamps, test_trade_id_is_opaque, test_trade_id_is_unique_per_intent_for_same_alert. |
| `tests/journal/test_trade_provenance_v1_0.py` | `TestJournalTradeProvenanceV1` | Pytest coverage for test_requires_trade_id_only, test_is_frozen, test_dict_round_trip. |

### `tests/manual/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/manual/live_smoke.py` | `TestManualLiveSmoke` | manual reality check against a REAL MetaTrader 5 terminal (Phase 5.5). |

### `tests/mt5_analytics/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/mt5_analytics/conftest.py` | `PytestSharedFixturesMt5Analytics` | Fixtures for the mt5_analytics torture suite (Phase 2a). |
| `tests/mt5_analytics/test_audit.py` | `TestMt5AnalyticsAudit` | Pytest coverage for test_append_audit_writes_line, test_append_only. |
| `tests/mt5_analytics/test_dashboard_data.py` | `TestMt5AnalyticsDashboardData` | Pytest coverage for test_summary_stats, test_session_and_regime_breakdown, test_points_and_durations_skip_none, test_empty_features_safe. |
| `tests/mt5_analytics/test_deal_characterizer.py` | `TestMt5AnalyticsDealCharacterizer` | Pytest coverage for test_all_patterns_counted, test_reopen_not_miscounted_as_partial, test_full_coverage_score_platinum, test_empty_stream_bronze. |
| `tests/mt5_analytics/test_entrypoints_import.py` | `TestMt5AnalyticsEntrypointsImport` | Pytest coverage for test_thin_shells_import. |
| `tests/mt5_analytics/test_feature_engine.py` | `TestMt5AnalyticsFeatureEngine` | Pytest coverage for test_mfe_mae_in_trade_R, test_realized_r_sign_and_magnitude, test_atr_fallback_when_no_sl, test_duration_metrics. |
| `tests/mt5_analytics/test_insight_report.py` | `TestMt5AnalyticsInsightReport` | Pytest coverage for test_cost_drag_from_episode_fields, test_cost_drag_zero_gross_returns_none_fraction, test_exit_efficiency_capture_and_giveback, test_exit_efficiency_skips_no... |
| `tests/mt5_analytics/test_live_smoke_importable.py` | `TestMt5AnalyticsLiveSmoke` | Pytest coverage for test_live_smoke_imports_without_terminal. |
| `tests/mt5_analytics/test_mt5_adapter_offset.py` | `TestMt5AnalyticsMt5` | Pytest coverage for test_positive_offset_three_hours, test_rounds_to_half_hour, test_negative_offset, test_zero_when_aligned. |
| `tests/mt5_analytics/test_pipeline_parity.py` | `TestMt5AnalyticsPipelineParity` | Pytest coverage for test_rebuild_equals_daemon_byte_identical. |
| `tests/mt5_analytics/test_position_reconstructor.py` | `TestMt5AnalyticsPositionReconstructor` | Pytest coverage for test_simple_long_win, test_simple_short_loss, test_partial_scale_out, test_premature_completion_guard. |
| `tests/mt5_analytics/test_providers.py` | `TestMt5AnalyticsProviders` | Pytest coverage for test_fixture_provider_time_slicing, test_fixture_provider_unknown_symbol_empty, test_fixture_provider_satisfies_protocol, test_bar_fields. |
| `tests/mt5_analytics/test_schema_episode.py` | `TestMt5AnalyticsSchemaEpisode` | Pytest coverage for test_to_iso_utc_epoch_and_iso_agree, test_to_iso_utc_normalizes_offset, test_make_episode_id_deterministic, test_make_episode_id_distinguishes_lifetimes. |
| `tests/mt5_analytics/test_shared_pipeline.py` | `TestMt5AnalyticsSharedPipeline` | Pytest coverage for test_pipeline_writes_episodes_and_features, test_pipeline_manifest_provenance, test_pipeline_idempotent. |
| `tests/mt5_analytics/test_storage.py` | `TestMt5AnalyticsStorage` | Pytest coverage for test_partition_layout_and_write, test_idempotent_rewrite_skips_duplicates, test_manifest_determinism_and_provenance. |
| `tests/mt5_analytics/test_verify.py` | `TestMt5AnalyticsVerify` | Pytest coverage for test_zero_trade_passes, test_balance_deposit_deal_ignored, test_happy_path_passes, test_tampered_pnl_fails. |

### `tests/portfolio/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/portfolio/test_replay_allocator.py` | `TestPortfolioReplayAllocator` | Pytest coverage for test_replay_is_deterministic, test_replay_imports_no_live_spine_module, test_allocated_realized_r_reconciles_with_metrics_oracle, test_missing_required_field... |

### `tests/regime/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/regime/test_market_state_cluster_engine.py` | `TestRegimeMarketStateClusterEngine` | Pytest coverage for test_trend_expansion_from_stats, test_range_trap_from_stats, test_cooldown_prevents_chattering, test_no_cluster_stats_transitional_chaos. |

### `tests/replay/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/replay/test_assign_cluster.py` | `TestReplayAssignCluster` | Pytest coverage for test_assign_picks_nearest_nonzero_zone, test_assign_does_not_collapse_to_zero, test_weighting_changes_winning_zone, test_legacy_centroid_key_supported. |
| `tests/replay/test_replay_memory_engine.py` | `TestReplayMemoryEngine` | Pytest coverage for test_load_empty_dir, test_query_no_records, test_cluster_stats_built, test_decay_weighting. |
| `tests/replay/test_replay_similarity_index.py` | `TestReplaySimilarityIndex` | Pytest coverage for test_cosine_self_similarity, test_decay_reduces_old_matches, test_cluster_filter, test_empty_index. |
| `tests/replay/test_timing_reconstructor.py` | `TestReplayTimingReconstructor` | Pytest coverage for test_progressive_winner_first_crossings, test_pure_loser_never_favorable, test_conservative_tiebreak_losing_stop_suppresses_credit, test_trail_in_profit_cred... |

### `tests/research/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/research/episodes/test_candidate_features.py` | `TestResearchCandidateFeatures` | Pytest coverage for test_protocol_declares_both_namespaces, test_freeze_block_records_the_namespace_contract, test_adding_candidate_features_does_not_change_content_hash, test_c... |
| `tests/research/episodes/test_episode_builder.py` | `TestResearchEpisodeBuilder` | Pytest coverage for test_entry_snapshot_geometry, test_tp_reward_mult_is_none_without_a_target, test_provenance_has_no_exit_policy_hash, test_derived_carries_no_policy_state. |
| `tests/research/episodes/test_episode_protocol.py` | `TestResearchEpisodeProtocol` | Pytest coverage for test_protocol_hash_is_deterministic, test_protocol_hash_is_scope_sensitive, test_freeze_block_is_json_serializable_and_ordered, test_governing_policy_is_intr... |
| `tests/research/episodes/test_episode_store.py` | `TestResearchEpisode` | Pytest coverage for test_round_trip_preserves_content_hash, test_round_trip_preserves_all_fields, test_observation_only_storage_preserves_identity, test_derived_cache_is_rebuild... |
| `tests/research/episodes/test_event_engine.py` | `TestResearchEventEngine` | Pytest coverage for test_eventset_carries_rulepack_identity, test_detection_is_deterministic, test_events_are_ordered_by_step, test_every_event_carries_a_real_bar_index. |
| `tests/research/episodes/test_flat_and_tensors.py` | `TestResearchFlatTensors` | Pytest coverage for test_one_row_per_timestep, test_entry_bar_carries_blank_derived_not_zeros, test_entry_bar_can_be_excluded, test_projection_is_idempotent. |
| `tests/research/episodes/test_policy_parity.py` | `TestResearchPolicyParity` | Pytest coverage for test_labelset_equals_direct_forward_walk, test_every_v1_policy_matches_its_kernel_mode, test_labelset_equals_clean_labels_builder, test_stretch_target_reprod... |
| `tests/research/episodes/test_policy_parity_corpus.py` | `TestResearchPolicyParityCorpus` | Pytest coverage for test_labelsets_match_clean_labels_on_the_real_corpus, test_events_agree_with_the_kernel_on_the_real_corpus, test_projector_and_clean_labels_select_the_same_p... |
| `tests/research/episodes/test_query_engine.py` | `TestResearchQueryEngine` | Pytest coverage for test_reference_query_reached_1r_within_6_bars_without_04r_adverse, test_reference_query_funnel_is_reported, test_reached_r_within_respects_the_bar_window, te... |
| `tests/research/episodes/test_spine_projector.py` | `TestResearchSpineProjector` | Pytest coverage for test_probe_reports_a_missing_path_oracle_rather_than_assuming_it, test_probe_detects_an_oracle_when_one_exists, test_probe_flags_missing_required_columns, te... |
| `tests/research/path/test_ambiguity_census.py` | `TestResearchAmbiguityCensus` | Pytest coverage for test_p1_signature_is_exact_vs_kernel, test_tiebreak_invariant_time_to_tp_equals_duration, test_clean_sl_and_clean_tp_are_not_p1, test_tp_on_earlier_bar_then_... |
| `tests/research/path/test_path_no_feedback.py` | `TestResearchPathFeedback` | Pytest coverage for test_no_consumer_imports_the_path_layer, test_firewall_scanner_actually_detects_an_import, test_path_package_declares_measure_only, test_forbidden_consumer_r... |
| `tests/research/test_asymmetry_contract.py` | `TestResearchAsymmetryContract` | Pytest coverage for test_measurer_does_not_import_spine, test_pair_rows_requires_both_sides_and_uses_mfe_not_stream, test_split_embargo_and_holdout_date, test_verdict_sign_match... |
| `tests/research/test_band_validation.py` | `TestResearchBandValidation` | Pytest coverage for test_bandspec_validates_edges_and_labels, test_assign_bands_maps_values_and_nonfinite, test_vectorized_persistence_matches_canonical_primitive, test_length_m... |
| `tests/research/test_candle_state_encoder.py` | `TestResearchCandleStateEncoder` | Pytest coverage for test_bull_strong_vs_bear_weak_vs_doji, test_compression_and_expansion_vs_trailing_atr, test_inside_and_outside_bar, test_trend_up_down. |
| `tests/research/test_carry.py` | `TestResearchCarry` | Pytest coverage for test_load_panel_ffill_and_basis, test_load_panel_missing_perp_raises, test_carry_basis_score_signs, test_carry_basis_scores_no_lookahead. |
| `tests/research/test_clean_labels_tn_env.py` | `TestResearchCleanLabelsTnEnv` | Pytest coverage for test_protocol_hash_stable, test_label_long_tp_path, test_tp2_stretch_harder_than_unit_tp_at_2r, test_label_long_sl_path. |
| `tests/research/test_compression_box_straddle.py` | `TestResearchCompressionBoxStraddle` | Pytest coverage for test_registered, test_fires_on_first_compression_bar_with_oco_signal, test_does_not_refire_inside_a_compression_run, test_no_signal_without_compression. |
| `tests/research/test_compression_breakout.py` | `TestResearchCompressionBreakout` | Pytest coverage for test_registered, test_emits_long_signal_on_compression_breakout, test_emits_short_signal, test_no_signal_without_compression_precondition. |
| `tests/research/test_conditional_entropy_grid.py` | `TestResearchConditionalEntropyGrid` | Pytest coverage for test_coinflip_partition_has_max_entropy_zero_ig, test_perfectly_conditional_partition_has_zero_entropy_unit_ig, test_informative_partition_is_significant, te... |
| `tests/research/test_config_entry_ttl.py` | `TestResearchConfigEntryTtl` | Pytest coverage for test_absent_entry_ttl_is_none_and_not_canonicalized, test_present_entry_ttl_is_parsed_and_hashed, test_every_existing_research_config_stays_sha_stable, test_... |
| `tests/research/test_context_attribution_contract.py` | `TestResearchContextAttributionContract` | Pytest coverage for test_contract_is_sealed_and_claims_no_economics, test_driver_declares_research_authority_only, test_declared_multiplicity_matches_the_enumerable_tests, test_... |
| `tests/research/test_controls.py` | `TestResearchControls` | Pytest coverage for test_controls_are_registered, test_always_long_profitable_on_uptrend, test_always_long_only_emits_longs, test_random_bias_distribution_and_determinism. |
| `tests/research/test_costs.py` | `TestResearchCosts` | Pytest coverage for test_cost_r_exact, test_tight_stop_pays_more_cost, test_aggregator_nets_by_haircut. |
| `tests/research/test_cross_sectional.py` | `TestResearchCrossSectional` | Pytest coverage for test_build_panel_rejects_misaligned_lengths, test_scores_are_invariant_to_future_data, test_forward_spread_invariant_to_data_after_exit, test_weight_construc... |
| `tests/research/test_crt_resolver_economic_comparison.py` | `TestResearchCrtResolverEconomicComparison` | Pytest module defining _FakeMemory, TestExpansionEntryDetection, TestDirectionFallback. |
| `tests/research/test_envelope_offline_train.py` | `TestResearchEnvelopeOfflineTrain` | Pytest coverage for test_time_split_ordered, test_refuses_wrong_protocol, test_train_synthetic_signal. |
| `tests/research/test_envelope_shadow_w0.py` | `TestResearchEnvelopeShadowW0` | Pytest coverage for test_shadow_weight_zero_and_complete, test_refuses_bad_rollup. |
| `tests/research/test_erp_teaching_dual_read.py` | `TestResearchErpTeachingDualRead` | Pytest coverage for test_ic001_closure_and_teaching_docs_exist, test_boundary_json_ic001_complete, test_dual_read_bar78_pair. |
| `tests/research/test_evidence_layer.py` | `TestResearchEvidence` | Pytest coverage for test_no_engine_or_trainer_import, test_illegal_join_refused, test_surfaces_name_roles_and_grains, test_evidence_record_cannot_grant_production_authority. |
| `tests/research/test_exit_ceilings.py` | `TestResearchExitCeilings` | Pytest coverage for test_vectorised_excursions_match_audited_scalar, test_bars_without_a_full_window_are_nan_not_truncated, test_excursions_are_sign_clamped_like_the_scalar_vers... |
| `tests/research/test_exit_grid.py` | `TestResearchExitGrid` | Pytest coverage for test_cell_metrics_basic, test_incumbent_cell_present, test_planted_edge_surfaces_as_lead, test_determinism. |
| `tests/research/test_exit_model_reconcile.py` | `TestResearchExitModelReconcile` | Pytest coverage for test_intrabar_fixed_is_default, test_fixed_holds_to_original_sl, test_trailing_ratchets_and_exits_early, test_bad_exit_model_raises. |
| `tests/research/test_forensics.py` | `TestResearchForensics` | Pytest coverage for test_classify_branches, test_expectancy_identity_reconciles, test_conversion_matrix_and_same_bar, test_loss_mechanisms_partition_and_rank. |
| `tests/research/test_forward_walk.py` | `TestResearchForwardWalk` | Pytest coverage for test_clean_tp_hit, test_trailing_sl_hit, test_timeout_marks_to_last_close, test_short_clean_tp. |
| `tests/research/test_forward_walk_oco.py` | `TestResearchForwardWalkOco` | Pytest coverage for test_long_fill_at_box_high_then_tp, test_short_fill_at_box_low_then_tp, test_both_edges_same_bar_cancels, test_reject_bar_checked_before_single_touch. |
| `tests/research/test_harvest.py` | `TestResearchHarvest` | Pytest coverage for test_load_panel_funding_settle_is_discrete, test_funding_accrual_excludes_entry_bar_settlement, test_long_low_short_high_income_is_positive, test_full_minus_... |
| `tests/research/test_ic002_entry_evolution.py` | `TestResearchIc002EntryEvolution` | Pytest coverage for test_prereg_matches_schema_constants, test_path_relative_and_flat_dims, test_build_for_N_synthetic, test_auc_perfect_and_chance. |
| `tests/research/test_ic003_shapes.py` | `TestResearchIc003Shapes` | Pytest coverage for test_prereg_k_grid, test_build_for_N_synthetic, test_build_all_writes_artifacts. |
| `tests/research/test_ic003b_derive_information.py` | `TestResearchIc003BDerive` | Pytest coverage for test_driver_imports_and_helpers_deterministic, test_artifact_descriptive_and_shaped. |
| `tests/research/test_ic003b_resume.py` | `TestResearchIc003BResume` | Pytest coverage for test_arm_complete_requires_verdict, test_write_paused_lists_completed, test_inventory_empty. |
| `tests/research/test_ic003b_sequence_geometry.py` | `TestResearchIc003BSequence` | Pytest coverage for test_prereg_g1_unchanged, test_path_summary_shape, test_dtw_identity_and_symmetry, test_arm_s_and_continuum_smoke. |
| `tests/research/test_information_class_registry.py` | `TestResearchInformationRegistry` | Pytest coverage for test_registry_twin_exists, test_measured_boundary_and_correction_recorded, test_open_information_classes_wellformed_and_in_md. |
| `tests/research/test_m5_incremental.py` | `TestResearchM5Incremental` | Pytest coverage for test_frozen_constants_match_preregistration, test_coarse_key_strips_base_component, test_coarse_only_target_is_redundant, test_fine_refinement_is_detected. |
| `tests/research/test_magnitude_prior.py` | `TestResearchMagnitudePrior` | Pytest coverage for test_measurer_does_not_import_spine, test_agree_is_side_given_not_side_picker, test_unit_rows_keep_side_and_drop_null_mfe, test_split_matches_mc_asym_calendar. |
| `tests/research/test_metrics.py` | `TestResearchMetrics` | Pytest coverage for test_basic_aggregation, test_max_drawdown_rr, test_empty_outcomes, test_profit_factor_no_losses_is_inf. |
| `tests/research/test_model_runners_contracts.py` | `TestResearchModelRunnersContracts` | Pytest coverage for test_catalog_has_live_four_and_blocked, test_get_contract_unknown, test_require_key_missing, test_require_section. |
| `tests/research/test_model_runners_smoke.py` | `TestResearchModelRunnersSmoke` | Pytest coverage for test_phase1_smoke_no_zone, test_zone_gate_smoke_if_artifact_present, test_cli_requires_flags. |
| `tests/research/test_mother_range_prior.py` | `TestResearchMotherRangePrior` | Pytest coverage for test_measurer_does_not_import_spine_or_trade_ledger, test_contract_and_sem_ids, test_unit_rows_empty_gracefully, test_arm_cells_contrast_and_agree_buckets. |
| `tests/research/test_mother_range_trade_object.py` | `TestResearchMotherRangeTradeObject` | Pytest coverage for test_no_crt_engine_import, test_inside_lower_half_is_long, test_outside_close_is_not_an_entry, test_small_mother_is_not_an_entry. |
| `tests/research/test_mtf_conjunction.py` | `TestResearchMtfConjunction` | Pytest coverage for test_key_format_and_axes, test_warmup_missing_htf_is_labeled_not_invented, test_no_lookahead_htf_state_matches_closed_buckets_only, test_appending_bars_in_sa... |
| `tests/research/test_mtf_conjunction_m5.py` | `TestResearchMtfConjunctionM5` | Pytest coverage for test_default_builder_emits_m15_base_keys, test_default_key_series_equals_build_regression, test_m5_base_key_format, test_m5_base_no_lookahead_within_m15_bucket. |
| `tests/research/test_multi_tp_walk_parity.py` | `TestResearchMultiTpWalkParity` | Pytest coverage for test_ledger_fixture_levels_reproduce_exactly, test_r_ladder, test_clean_stop_is_exactly_minus_one_r, test_runner_stop_pricing_bases_disagree_by_design. |
| `tests/research/test_oracle_labeler.py` | `TestResearchOracleLabeler` | Pytest coverage for test_tp1_multiplier_resolves_per_intent_with_fallback, test_unit_count_is_the_declared_cartesian_product, test_sl_geometry_matches_build_trade, test_targets_... |
| `tests/research/test_phase_s_selection.py` | `TestResearchPhaseSSelection` | Pytest coverage for test_fold_reason, test_delta_e_basic_and_empty, test_pooled_delta_weighting_and_skip, test_stratified_permutation_significant_when_planted. |
| `tests/research/test_process_characterization.py` | `TestResearchProcessCharacterization` | Pytest coverage for test_acf_iid_noise_near_zero, test_acf_ar1_decays_geometrically, test_acf_short_series_clamps, test_hurst_random_walk_near_half. |
| `tests/research/test_process_diagnostics.py` | `TestResearchProcessDiagnostics` | Pytest coverage for test_ljung_box_iid_fails_to_reject, test_ljung_box_ar1_rejects, test_arch_lm_garch_rejects, test_arch_lm_white_noise_fails_to_reject. |
| `tests/research/test_qualification.py` | `TestResearchQualification` | Pytest coverage for test_permutation_detects_real_separation, test_permutation_no_separation_high_p, test_permutation_deterministic, test_benjamini_hochberg_controls_fdr. |
| `tests/research/test_rc003_distinct_object.py` | `TestResearchRc003DistinctObject` | Pytest coverage for test_preregistration_exists_and_is_frozen, test_driver_constants_match_the_frozen_document, test_preregistration_declares_every_artifact_the_driver_writes, t... |
| `tests/research/test_registry.py` | `TestResearchRegistry` | Pytest coverage for test_both_behaviors_registered, test_opposite_behaviors_run_through_identical_pipeline, test_measurement_core_does_not_branch_on_family. |
| `tests/research/test_reporting_metrics.py` | `TestResearchReportingMetrics` | Pytest coverage for test_win_rate, test_streak_metrics, test_rolling_window_metrics, test_report_rollup. |
| `tests/research/test_resample.py` | `TestResearchResample` | Pytest coverage for test_h1_golden_bucket, test_index_is_emit_position_and_monotonic, test_trailing_partial_bucket_dropped_unconditionally, test_even_a_complete_final_bucket_is_... |
| `tests/research/test_resample_corpus_parity.py` | `TestResearchResampleCorpusParity` | Pytest coverage for test_resampled_m5_matches_fetched_file. |
| `tests/research/test_resample_m5.py` | `TestResearchResampleM5` | Pytest coverage for test_m15_golden_bucket, test_m15_buckets_align_to_quarter_hours, test_trailing_partial_m15_bucket_dropped, test_associativity_m5_m15_h1_equals_m5_h1. |
| `tests/research/test_rnet_overlay.py` | `TestResearchRnetOverlay` | Pytest coverage for test_measurer_does_not_import_spine, test_k_is_frozen_and_is_primary, test_unit_rows_require_y_r_net_not_mfe, test_overlay_delta_is_quarter_contrast_when_bal... |
| `tests/research/test_runner_determinism.py` | `TestResearchRunnerDeterminism` | Pytest coverage for test_edge_report_is_byte_identical_across_runs, test_report_carries_deterministic_provenance, test_pooled_aggregates_multiple_instruments. |
| `tests/research/test_runner_oco_routing.py` | `TestResearchRunnerOcoRouting` | Pytest coverage for test_market_direction_reports_identical_with_and_without_entry_ttl, test_edge_report_still_byte_identical_across_runs, test_oco_hypothesis_flows_through_coll... |
| `tests/research/test_secondlow_sealed_evaluation_set.py` | `TestResearchSecondlowSealedEvaluationSet` | Pytest coverage for test_manifest_unsealed_after_prereg_approval, test_manifest_matches_live_detector, test_manifest_forbids_outcome_fields_until_prereg. |
| `tests/research/test_secondlow_v1_detector_regression.py` | `TestResearchSecondlowV1Detector` | Pytest coverage for test_regression_fixture_hash_prefix, test_canonical_corpus_hash_prefix, test_regression_fixture_event_counts, test_canonical_corpus_partition_invariants. |
| `tests/research/test_shape_explanations.py` | `TestResearchShapeExplanations` | Pytest coverage for test_explanation_file_exists, test_carries_no_authority_and_robustness_caveats, test_documented_shapes_are_real, test_level3_mapping_references_real_families. |
| `tests/research/test_spine_hypothesis.py` | `TestResearchSpineHypothesis` | Pytest coverage for test_price_to_atr_conversion_roundtrips_exactly, test_detect_only_at_entry_bars, test_determinism_identical_signals, test_signal_feeds_forward_walk. |
| `tests/research/test_stop_policy.py` | `TestResearchStopPolicy` | Pytest coverage for test_policy_cannot_see_the_current_bar, test_same_bar_arm_is_a_band_not_an_optimism_bound, test_state_carries_only_completed_bars, test_no_modification_polic... |
| `tests/research/test_story_library_golden.py` | `TestResearchStoryLibraryGolden` | Pytest coverage for test_library_nontrivial, test_story_passes_all_six_layers_and_critical, test_story_is_deterministic, test_outcome_coverage_includes_losers. |
| `tests/research/test_story_ontology.py` | `TestResearchStoryOntology` | Pytest coverage for test_authority_is_descriptive_only, test_every_state_belongs_to_a_declared_layer, test_crt_bridge_rule_only_structure_states_map_to_crt, test_all_feature_sig... |
| `tests/research/test_structural_asymmetry.py` | `TestResearchStructuralAsymmetry` | Pytest coverage for test_barrier_race_rising_and_falling, test_mfe_mae_monotonic_in_horizon, test_aggregate_recovers_asymmetry, test_permutation_significant_when_planted. |
| `tests/research/test_sujan_crt_contract.py` | `TestResearchSujanCrtContract` | Pytest coverage for test_contract_conforms_to_the_frozen_schema, test_the_schema_checker_can_actually_fail, test_new_nodes_live_in_enforced_sections, test_registry_validators_ar... |
| `tests/research/test_sujan_manipulation.py` | `TestResearchSujanManipulation` | Pytest coverage for test_no_forbidden_imports, test_predicate_delegates_to_sp001, test_purge_high_closing_below_range_low_is_not_manipulation, test_purge_low_closing_above_range... |
| `tests/research/test_sujan_veto_chain.py` | `TestResearchSujanVetoChain` | Pytest coverage for test_no_spine_or_visual_crt_import, test_veto_params_have_no_silent_defaults, test_sem_023_weights_sum_to_100_and_undefined_is_not_zero, test_unmeasurable_ru... |
| `tests/research/test_trace_corpus.py` | `TestResearchTraceCorpus` | Pytest coverage for test_corpus_schema_and_no_edge_field, test_pit_alignment_features_join_by_stream_position, test_parallel_forward_walk_kernel_matches_sequential, test_distrib... |
| `tests/research/test_trace_geometry.py` | `TestResearchTraceGeometry` | Pytest coverage for test_geometry_clusters_and_descriptive_only, test_geometry_labels_are_deterministic. |
| `tests/research/test_trace_knn.py` | `TestResearchTraceKnn` | Pytest coverage for test_knn_graph_and_summary_descriptive, test_knn_is_deterministic. |
| `tests/research/test_transition_information.py` | `TestResearchTransitionInformation` | Pytest coverage for test_vol_expansion_target_detects_forward_blowup, test_vol_expansion_target_low_when_flat, test_range_expansion_target_shape, test_persistence_target. |
| `tests/research/test_vcrt_v2_contract.py` | `TestResearchVcrtV2Contract` | Pytest coverage for test_frozen_surfaces_are_byte_identical_to_v1, test_the_two_declared_surfaces_did_change, test_splits_are_carried_over_verbatim, test_metrics_changed_only_by... |
| `tests/research/test_visual_crt_prior.py` | `TestResearchVisualCrtPrior` | Pytest coverage for test_measurer_does_not_import_spine_or_trade_ledger, test_contract_and_sem_ids, test_unit_rows_empty_gracefully, test_arm_cells_contrast_and_agree_buckets. |
| `tests/research/test_visual_crt_trade_object.py` | `TestResearchVisualCrtTradeObject` | Pytest coverage for test_package_has_no_runtime_spine_import, test_isolation_check_actually_fails_on_a_violation, test_type_checking_import_of_candle_is_permitted, test_visible_... |
| `tests/research/test_weekly_sweep.py` | `TestResearchWeeklySweep` | Pytest coverage for test_range_lock_before_tuesday_closes, test_normal_week_range_and_high_sweep_direction_short, test_normal_week_low_sweep_direction_long, test_no_sweep_when_b... |
| `tests/research/test_weekly_sweep_hypothesis.py` | `TestResearchWeeklySweepHypothesis` | Pytest coverage for test_registered, test_emits_short_signal_on_high_sweep, test_emits_long_signal_on_low_sweep, test_no_signal_before_tuesday_closes. |
| `tests/research/test_xauusd_corpus_certification.py` | `TestResearchXauusdCorpusCertification` | Pytest coverage for test_guard_resolves_only_to_frozen_candidate, test_certify_driver_records_honest_decision_and_manifest. |
| `tests/research/test_xauusd_qualification_smoke.py` | `TestResearchXauusdQualificationSmoke` | Pytest coverage for test_research_pass_runs_and_is_non_promotable. |
| `tests/research/test_xauusd_spine_smoke.py` | `TestResearchXauusdSpineSmoke` | Pytest coverage for test_spine_collect_runs_on_frozen_candidate_without_active_version_drift. |

### `tests/runtime/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tests/runtime/test_replay_determinism.py` | `TestRuntimeReplayDeterminism` | Pytest coverage for test_trade_ledger_is_byte_identical, test_headline_metrics_are_identical, test_all_artifacts_byte_identical_across_runs. |

## Area: `tools` (37)

### `src/utils/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/utils/config_dumper.py` | `UtilsGuessingParamsActuallyActive` | no guessing which params were actually active. |
| `src/utils/console_safe.py` | `SafeStreamHandler` | Console-safe output helpers for mixed terminal encodings. |
| `src/utils/duckdb_query.py` | `ParquetProjectionDuckdbViews` | Ephemeral in-memory DuckDB views over regenerable Parquet projections of JSONL SoR. |
| `src/utils/engine_telemetry.py` | `EngineTelemetryStructuredObservability` | Structured observability wrapper for all engines. |
| `src/utils/episode_summarizer.py` | `EpisodeSummarizerRunInstrument` | Per-run, per-instrument CRT episode aggregator (M1 Part 2). |
| `src/utils/integrity_events.py` | `UtilsSeverityCanonicalIntegrityEvent` | Canonical integrity-event telemetry spine. |
| `src/utils/isolated_config_root.py` | `UtilsRunProcessAgainstChosenProduction` | run a process against a chosen production config, safely. |
| `src/utils/jsonl_writer.py` | `UtilsCanonicalAppendJsonlHelper` | the canonical append-only JSONL helper. |
| `src/utils/llm_logger.py` | `SignalRecord` | token-efficient structured logger for UAT/SIT sessions. |
| `src/utils/log_identity.py` | `UtilsMinimalMetadataContextHelperAgent` | Minimal metadata context helper for the agent-readable execution memory layer. |
| `src/utils/log_index_writer.py` | `UtilsAppendWritersSupplementalIndexLogs` | Append-only writers for the supplemental index layer at ``logs/index/``. |
| `src/utils/logging_config.py` | `FlowLogFilter` | Centralized Logging Configuration for Trading System Provides per-flow logging differentiation and aligned format across all modules. |
| `src/utils/parquet_store.py` | `JsonlToParquetProjectionStore` | Builds and manages regenerable Parquet sidecar projections from JSONL system-of-record. |
| `src/utils/pattern_hasher.py` | `UtilsStablePatternIdentificationUtilitiesCRT` | Stable pattern identification utilities for CRT trade replay and memory. |
| `src/utils/registry_refresh.py` | `RegistryWatcher` | Lightweight file-mtime tracker for in-session hot-reload of model and zone registries after promotion, without process restart (note: path stem 'registry_refresh' vs content foc... |
| `src/utils/run_manifest.py` | `UtilsProvenanceManifestResearchToolRuns` | provenance manifest for research/tool runs (ERP testing-plan §3.3). |
| `src/utils/sweep_trace_logger.py` | `SweepTraceLoggerFirstRepair` | Layer 0 of the trace-first repair pipeline. |
| `src/utils/trade_logger.py` | `TradeLoggerStructuredJsonl` | Structured JSONL trade logger for the CRT + Fusion pipeline. |
| `src/utils/validation_contract.py` | `SummaryManifestMismatch` | H1/H2/H3 guards over run manifests (ERP testing-plan §5/§6) (note: path stem 'validation_contract' vs content focus 'SummaryManifestMismatch'). |
| `src/utils/zone_schema_migrator.py` | `UtilsBitNetZoneSchemaMigration` | BitNet Zone Schema Migration Utility. |

### `tools/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tools/btcusdt_crt_v3_replay.py` | `BarTools` | Standalone reference harness reproducing the BitNet CRT Scoring Pipeline described in C:\Users\Hi\Downloads\Jarvis_CRT_Handover.docx (Patch v3). |

### `tools/tv_forensic/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `tools/tv_forensic/_dump_jul28_bars.py` | `TvForensicDumpJul28Bars` | Module at tools/tv_forensic/_dump_jul28_bars.py. |
| `tools/tv_forensic/_dump_jul30_bars.py` | `TvForensicDumpJul30Bars` | Module at tools/tv_forensic/_dump_jul30_bars.py. |
| `tools/tv_forensic/_probe_custom_range.py` | `TvForensicProbeCustomRangeInputs` | Probe Custom range inputs and interval menu. |
| `tools/tv_forensic/_probe_dialogs.py` | `TvForensicProbeDateIntervalMenu` | Probe Go-to-date, interval menu, and panel-close controls. |
| `tools/tv_forensic/_probe_tv.py` | `TvForensicOneOffProbeDump` | One-off probe: dump TradingView controls so the capture script can target them. |
| `tools/tv_forensic/annotate.py` | `Frame` | Draw engine events onto a captured shot, using the chart's own coordinates (note: path stem 'annotate' vs content focus 'Frame'). |
| `tools/tv_forensic/annotate_engine_events.py` | `TvForensicOverlayExistingM15` | Forensic overlay on the existing M15 full-window shot. |
| `tools/tv_forensic/annotate_shot05.py` | `TvForensicAnnotateShotSeparateSWEEP` | Annotate shot 05: separate SWEEP / DISPLACEMENT bodies. |
| `tools/tv_forensic/annotate_shot06.py` | `TvForensicAnnotateShotRETESTENTRY` | Annotate shot 06: RETEST / ENTRY / SL as separate M15 identities. |
| `tools/tv_forensic/build_disp_exp_plan.py` | `TvForensicEventCenteredM15` | Build event-centered M15 shot plans for P-VSTATE-02 (Option A). |
| `tools/tv_forensic/capture_tv.py` | `Shot` | Capture TradingView screenshots for engine-trace comparison. |
| `tools/tv_forensic/engine_data.py` | `BarTvForensic` | Engine-side bars, and the clock that ties them to TradingView. |
| `tools/tv_forensic/htf_bars.py` | `TvForensicSrcUnavailableHigherTimeframe` | Higher-timeframe engine bars, and the grid phase that ties them to TradingView. |
| `tools/tv_forensic/measure_corpus_clock.py` | `TvForensicMeasureOHLCVCorpusUTC` | Measure an OHLCV corpus's UTC offset against TradingView's declared-UTC series. |
| `tools/tv_forensic/tv_bridge.py` | `TVBridgeControlPublic` | Deterministic control of a public TradingView chart via its own widget API. |
| `tools/tv_forensic/ui_fallback.py` | `TvForensicOriginalDOMDrivenFraming` | The original DOM-driven framing path, kept as a fallback behind --via-ui. |

## Area: `docs` (33)

### `AGENTS.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `AGENTS.md` | `AGENTSMdAGENTS` | AGENTS.md. |

### `CLAUDE.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `CLAUDE.md` | `CLAUDEMdMasterContext` | Master Context File. |

### `CODEBASE_WIRING_QUICKREF.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `CODEBASE_WIRING_QUICKREF.md` | `CODEBASEWIRINGQUICKREFMdQuickReference` | Quick Reference. |

### `GROK.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `GROK.md` | `GROKMdGROK` | GROK.md. |

### `HANDOFF.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `HANDOFF.md` | `HANDOFFMdLiveMultiLLMState` | Live Multi-LLM State. |

### `MASTER_ARCHITECTURE_REFERENCE.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `MASTER_ARCHITECTURE_REFERENCE.md` | `MASTERARCHITECTUREREFERENCEMdMASTERARCHITECTURE` | MASTER ARCHITECTURE REFERENCE. |

### `README.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `README.md` | `READMEMdTradelatest` | Tradelatest. |

### `RESOLUTION_REGISTRY.md/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `RESOLUTION_REGISTRY.md` | `RESOLUTIONREGISTRYMdSweepDecisionMemory` | Fallback-sweep decision memory. |

### `docs/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `docs/CODEBASE_NAVIGATION.md` | `LlmCodebaseJumpMap` | First-open LLM jump map for entry points, packages, configs, tests, and governance surfaces. |
| `docs/PROJECT_HISTORY.md` | `ProjectHistoryAprilJune` | Project History (April – June 2026). |
| `docs/STRATEGIES.md` | `STRATEGIES` | STRATEGIES.md. |
| `docs/behavior_contracts.md` | `ExpectedForbidden` | Expected vs Forbidden. |
| `docs/intent_to_code_map.md` | `IntentMap` | Intent → Code Map. |
| `docs/knowledge-map.md` | `RecordSystemsConnect` | How the Record Systems Connect. |
| `docs/readme.md` | `DocumentationIndex` | Documentation index. |

### `docs/architecture/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `docs/architecture/code-map.md` | `ArchitectureWiredDeepDiveNavigation` | How the code is wired (deep-dive navigation). |
| `docs/architecture/codebase-wiring-guide.md` | `ArchitectureCodebaseWiringGuide` | Codebase Wiring Guide. |
| `docs/architecture/entry-exit-map.md` | `ArchitectureEntryExitPointMap` | Entry & Exit Point Map (docs ↔ code). |
| `docs/architecture/signal-flow.md` | `ArchitectureCandleOrderEnd` | Candle → Order, end to end. |
| `docs/architecture/three-layer-codebase-atlas.md` | `ArchitectureThreeCodebaseAtlas` | Three-Layer Codebase Atlas. |

### `docs/governance/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `docs/governance/CORPUS_AUTHORITY.md` | `GovernanceCorpusAuthorityDoctrine` | Corpus Authority Doctrine. |
| `docs/governance/GITIGNORE_SCHEMA.md` | `GovernanceGitignoreSchema` | Gitignore Schema v1. |
| `docs/governance/MEASUREMENT_CONTRACT.md` | `GovernanceMinimumExecutableEvidence` | Minimum Executable Evidence (E-MT-00 / E-MT-01). |
| `docs/governance/PHYSICAL_STORAGE_ARCHITECTURE.md` | `GovernancePhysicalStorageArchitecture` | Physical Storage Architecture. |
| `docs/governance/SEMANTIC_OS_CONTRACT.md` | `GovernanceSemanticContract` | Semantic OS Contract (v1). |

### `docs/operations/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `docs/operations/CURRENT_STATE.md` | `OperationsRollingStatus` | Rolling Status. |
| `docs/operations/DEPENDENCY_GRAPH.md` | `OperationsDependencyGraph` | Dependency Graph. |
| `docs/operations/TRUST_TIER_INDEX.md` | `OperationsDocumentTierIndex` | Document Trust Tier Index. |

### `docs/reference/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `docs/reference/cli-matrix.md` | `ReferenceMatrix` | CLI Matrix (Generated). |
| `docs/reference/config-reference.md` | `ReferenceCONFIGREFERENCE` | CONFIG_REFERENCE.md. |
| `docs/reference/governance.md` | `ReferenceGOVERNANCE` | GOVERNANCE.md. |
| `docs/reference/script-matrix.md` | `ReferenceSITS` | SITS). |
| `docs/reference/testing.md` | `ReferenceTESTING` | TESTING.md. |

## Area: `other` (1)

### `src/`

| path | semantic_name | business_role |
|------|---------------|---------------|
| `src/__init__.py` | `SrcApi` | Module at src/__init__.py. |

