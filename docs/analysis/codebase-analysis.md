# CRT System Codebase Analysis
> Standardised module documentation generated 2026-04-22  
> Master checklist tracked in this file. Each module receives consistent analysis format.

---

### Module: `src/expansion/expansion_engine.py`
✅ **Overview**: Deterministic stepwise parameter expansion engine. Systematically relaxes ONE parameter per step, runs backtest, evaluates against hard guardrails, and stops when bounds are breached or target trade count is reached. LLM has no decision authority here - only suggests candidate directions.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Baseline Validator | Establishes reference metrics from production config before any changes |
| Stepwise Mutator | Executes single parameter changes in priority order defined by expansion plan |
| Backtest Orchestrator | Runs isolated backtest across all instruments for every candidate config |
| Evaluator Gate | Applies guardrails and scores every mutation against baseline performance |
| Tier Classifier | Automatically categorises accepted configs into SAFE / BALANCED / AGGRESSIVE tiers |
| Audit Logger | Writes immutable trace and rejection logs for every step executed |
| Ranked Output Builder | Returns final ranked config set with baseline always included as fallback |
🚧 **Quality Gates**:
- ✅ **Single parameter only**: **EXACTLY ONE** parameter modified per step. No batch changes ever permitted
- ✅ **Immediate stop on rejection**: Any guardrail breach terminates expansion for that parameter immediately
- ✅ **Baseline always preserved**: Original production config is never mutated and always included in final output
- ✅ **Full audit trail**: Every single step (accepted or rejected) is logged with full metrics
- ✅ **Monotonic expansion**: Parameters only move in one direction per run, no backtracking
🔗 **Integration Points**:
- Receives expansion plans from `llm_pattern_extractor.py` (LLM suggested candidates)
- Uses `ConfigMutator` for safe parameter boundary aware modifications
- Executes standard `BacktestRunner` v2 with zero lookahead guarantee
- Outputs ranked configs ready for validation and promotion pipeline
⚠️ **Constraints**:
- Maximum 8 steps per parameter hard limit
- Default target trade count multiplier = 2.0x baseline
- Expansion stops immediately on first rejection for any parameter
- Baseline config is always returned as SAFE tier regardless of expansion outcome
🎯 **Operation**:
  ```python
  engine = ExpansionEngine(target_multiplier=2.0)
  result = engine.run(base_config, expansion_plan, csv_paths)
  save_expansion_configs(result)
  ```
---

### Module: `src/expansion/config_mutator.py`
✅ **Overview**: Single-parameter deep-copy mutation with bounds checking. The only authorised component allowed to modify config values. Never mutates original config, always returns new deep copied instance.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Bounds Validator | Enforces hard minimum/maximum limits defined in `PARAM_BOUNDS` |
| Delta Limiter | Enforces maximum total change from original baseline value |
| Deep Copy Engine | Creates full immutable copy of config before modification |
| Precision Normaliser | Rounds all values to 4 decimal places for consistency |
🚧 **Quality Gates**:
- ✅ **Immutable original**: Source config is **NEVER** modified. Deep copy always performed first
- ✅ **Single parameter only**: Exactly one parameter changed per call. No batch operations
- ✅ **Dual bound enforcement**: Both per-parameter hard limits and maximum delta from baseline
- ✅ **Fail fast**: Raises ValueError immediately for unknown parameters
- ✅ **Deterministic rounding**: All values normalised to 4 decimal places
🔗 **Integration Points**:
- Called exclusively by ExpansionEngine during stepwise execution
- Boundary definitions imported from `policy_schema.py`
- Used by both expansion engine and LLM pattern extractor
⚠️ **Constraints**:
- Maximum 50% total change allowed from original baseline value
- All numeric values cast to float before any operations
- No support for modifying nested dictionary parameters
🎯 **Operation**:
  ```python
  new_config = ConfigMutator.mutate(
      base_config, 
      "trap_filter_threshold", 
      direction="decrease", 
      step=0.05,
      baseline_value=0.45
  )
  ```
---

### Module: `src/expansion/evaluator.py`
✅ **Overview**: Profit-aware scoring and guardrail enforcement for expansion candidate configs. Optimises for risk adjusted returns, not raw trade count. Single source of truth for all acceptance decisions during expansion.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Scoring Function | Composite score: `PnL - (2×Drawdown Penalty) + (Trade Bonus)` |
| Guardrail Validator | Hard stop checks for PnL drop and maximum drawdown increase |
| Tier Classifier | Automatic config categorisation into SAFE / BALANCED / AGGRESSIVE based on trade count multiplier |
🚧 **Quality Gates**:
- ✅ **Drawdown penalty 2× PnL weight**: Risk is weighted twice as heavily as profit in scoring
- ✅ **Maximum 15% PnL drop allowed**: Hard reject if PnL falls below 85% of baseline
- ✅ **Maximum 20% drawdown increase allowed**: Hard reject if drawdown exceeds 120% of baseline
- ✅ **Only positive trade bonus**: No penalty for lower trade counts
- ✅ **Deliberately conservative weights**: Designed to avoid over-optimisation and frequency chasing
🔗 **Integration Points**:
- Called after every backtest run by ExpansionEngine
- Thresholds imported from `policy_schema.py`
- Tier classification directly defines final output config slots
⚠️ **Constraints**:
- Trade bonus fixed at 10 units per additional trade
- Tier boundaries hardcoded: <1.3x = SAFE, 1.3-1.8x = BALANCED, >1.8x = AGGRESSIVE
- No relative win rate or expectancy metrics are considered in scoring
🎯 **Operation**:
  ```python
  score = Evaluator.score(candidate_metrics, baseline_metrics)
  passes, reason = Evaluator.passes_guardrails(candidate_metrics, baseline_metrics)
  tier = Evaluator.classify_config(score, baseline_score, trades, baseline_trades)
  ```
---

### Module: `src/expansion/policy_schema.py`
✅ **Overview**: Immutable type definitions and safety constants for the entire expansion system. Single source of truth for all boundaries, guardrails, and data contracts. No business logic here - only definitions.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| ExpansionCandidate | Single parameter mutation suggestion with bounds, direction, step size and priority |
| ExpansionPlan | Complete ordered execution plan with baseline metrics and target multiplier |
| ExpansionStep | Immutable audit record for every step executed (accepted or rejected) |
| ExpansionResult | Final standardised output contract returned by ExpansionEngine |
| PARAM_BOUNDS | Hard allowable ranges for all expandable parameters |
| Global Constants | Maximum steps, change limits, and guardrail ratios |
🚧 **Quality Gates**:
- ✅ **All dataclasses frozen**: No modification after creation, full immutability guarantee
- ✅ **Parameter bounds centrally defined**: No hardcoded limits anywhere else in codebase
- ✅ **Global constants cannot be overridden**: Enforced at runtime by all modules
- ✅ **All values have sensible safe defaults**: No uninitialised fields
🔗 **Integration Points**:
- Imported and used by **every** module in the expansion layer
- All LLM generated plans must conform to ExpansionCandidate schema
- All trace logs use ExpansionStep serialisation
⚠️ **Constraints**:
- Maximum 3 steps per parameter hard limit
- Maximum 15% total change allowed from original baseline value
- Minimum 90% PnL retention required
- Maximum 150% baseline drawdown allowed
- Only 4 parameters are explicitly authorised for expansion
🎯 **Constants Reference**:
| Constant | Value | Description |
|---|---|---|
| MAX_PARAM_CHANGE | 0.15 | Maximum total delta from baseline |
| MAX_STEPS_PER_PARAM | 3 | Maximum iterations per parameter |
| MIN_PNL_RATIO | 0.90 | Minimum allowed PnL vs baseline |
| MAX_DRAWDOWN_RATIO | 1.50 | Maximum allowed drawdown vs baseline |
---

### Module: `src/regime/regime_classifier.py`
✅ **Overview**: Deterministic market regime detection with hysteresis cooldown. Pure rule based, no LLM or probabilistic logic. Returns one of 3 standard regimes for engine routing.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Raw Classifier | Priority based detection: High Volatility > Trending > Ranging |
| Cooldown Guard | Prevents regime flapping, minimum 5 candles between state changes |
| Safe Fallback | Always returns RANGING on any error or undefined state |
🚧 **Quality Gates**:
- ✅ **Pure deterministic**: No randomness, identical input always produces identical output
- ✅ **Cooldown enforcement**: No rapid oscillation between regimes
- ✅ **Fail safe operation**: All exceptions and invalid inputs return RANGING regime
- ✅ **Priority ordering**: Volatility detection always overrides trend classification
🔗 **Integration Points**:
- Called from EngineRunner stage 6 prior to decision engine
- Output used by `config_router.py` to select tuned parameter set
- Directly feeds Ultron gate selection logic
⚠️ **Constraints**:
- Detection operates on normalised 0-1 feature ranges
- Default thresholds: ATR > 0.8 = High Volatility, Trend > 0.7 = Trending
- Minimum 5 candle cooldown is hardcoded default
- Regime never returns UNKNOWN, always falls back to safe operational mode
🎯 **Operation**:
  ```python
  classifier = RegimeClassifier()
  regime = classifier.classify(features)
  ```
---

### Module: `src/regime/config_router.py`
✅ **Overview**: Regime to config profile mapping layer. Selects tuned parameter sets based on current market conditions. Provides safe fallback for all undefined states.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Regime Mapper | Maps detected regime to config profile tier |
| Config Resolver | Loads matching config file from production directory |
| Fallback Handler | Always returns SAFE profile on any error or unknown regime |
🚧 **Quality Gates**:
- ✅ **Fail safe operation**: All unknown regimes map to SAFE profile
- ✅ **Graceful degradation**: Logs warning but continues on missing config files
- ✅ **Override safety**: User supplied maps merge over defaults, never replace entirely
- ✅ **Deterministic mapping**: Same regime always produces same profile selection
🔗 **Integration Points**:
- Called from EngineRunner after regime classification
- Consumes output directly from RegimeClassifier
- Loads configs generated by ExpansionEngine
⚠️ **Constraints**:
- Default mapping: Trending → BALANCED, Ranging → SAFE, High Volatility → AGGRESSIVE
- Config files detected by profile name suffix in filename
- All mappings are unidirectional, no reverse lookups
🎯 **Default Mapping**:
| Regime | Default Profile |
|---|---|
| TRENDING | BALANCED |
| RANGING | SAFE |
| HIGH_VOLATILITY | AGGRESSIVE |
| DEFAULT | SAFE |
---

### Module: `src/portfolio/allocator.py`
✅ **Overview**: Portfolio allocation orchestrator. Combines exposure tracking, correlation analysis and capital policy to produce dynamic per-trade risk sizing decisions. Replaces fixed percentage risk sizing.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Allocation Gatekeeper | 2 stage approval: portfolio capacity check → risk calculation → final fit check |
| Exposure Tracker | Maintains live state of all open positions and total risk |
| Correlation Engine | Calculates maximum correlation between candidate signal and existing positions |
| Capital Policy | Computes dynamic risk size based on current portfolio state |
| Risk Trimmer | Automatically reduces allocation size to fit within portfolio limits |
🚧 **Quality Gates**:
- ✅ **Capacity check first**: Hard reject when portfolio at maximum risk
- ✅ **Safe trimming**: Allocation automatically reduced instead of rejected when near capacity
- ✅ **Zero risk reject**: Trimmed risk <= 0 automatically rejects trade
- ✅ **Full audit logging**: Every allocation decision logged with full context
🔗 **Integration Points**:
- Called from EngineRunner prior to Ultron Risk Gate
- Output risk value passed directly to execution loop
- Open/close position events hooked into trade lifecycle
- Ultron Gate remains final authority after allocation
⚠️ **Constraints**:
- Risk is always trimmed to fit remaining portfolio capacity
- No position concurrency limits per instrument
- Correlation penalties applied only at time of allocation
- All positions tracked by unique trade_id
🎯 **Operation**:
  ```python
  allocator = PortfolioAllocator()
  decision = allocator.allocate(signal)
  if decision["action"] == "ALLOCATE":
      signal["risk"] = decision["risk"]
  ```
---

### Module: `src/portfolio/capital_policy.py`
✅ **Overview**: Deterministic risk sizing rules engine. Computes dynamic per-trade allocation using portfolio state, correlation and signal confidence. No LLM or probabilistic logic.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Base Risk Calculator | Standard 0.5% base risk per trade |
| Exposure Adjuster | Reduces allocation when portfolio > 1.5% deployed |
| Correlation Penalty | Reduces size for correlated signals |
| Confidence Boost | Increases allocation for high confidence signals |
| Hard Cap Enforcer | Final maximum 1% per trade limit |
🚧 **Quality Gates**:
- ✅ **Strict ordering**: Adjustments applied left to right: Exposure → Correlation → Confidence
- ✅ **Hard upper limit**: No trade ever exceeds 1% total capital risk
- ✅ **Safe defaults**: All parameters have sensible production values
- ✅ **No negative risk**: All multipliers strictly positive
🔗 **Integration Points**:
- Called exclusively from PortfolioAllocator
- Output risk value used directly in execution loop
- All thresholds fully configurable via constructor
⚠️ **Constraints**:
- Default total portfolio risk cap = 2.0%
- Default maximum per trade risk = 1.0%
- Default base risk = 0.5%
- Adjustment factors: High Exposure ×0.5 | High Correlation ×0.6 | High Confidence ×1.3
🎯 **Operation**:
  ```python
  policy = CapitalPolicy()
  risk = policy.compute_risk(signal, current_exposure, max_correlation)
  ```
---

### Module: `src/portfolio/correlation_engine.py`
✅ **Overview**: Heuristic correlation estimator for asset pairs. Phase 1 implementation using deterministic grouping logic. No live price data dependencies.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Symbol Grouper | Static asset class group definitions: Crypto, FX Majors, USD Shorts |
| Heuristic Calculator | 3 tier correlation mapping based on group membership |
| Maximum Correlation Finder | Returns highest correlation against any open position |
| Extension Interface | Designed for subclassing for future price based correlation |
🚧 **Quality Gates**:
- ✅ **Pure deterministic**: No external data dependencies
- ✅ **Safe defaults**: Unknown symbols return low correlation
- ✅ **Identical symbol guard**: Same symbol always returns 1.0 correlation
- ✅ **Ordered evaluation**: Highest matching rule always applied first
🔗 **Integration Points**:
- Called exclusively from PortfolioAllocator
- Output value used directly in CapitalPolicy risk calculation
- Correlation threshold 0.7 = 40% risk reduction
⚠️ **Constraints**:
- Default values: High = 0.8 | Medium = 0.4 | Low = 0.2
- Same base currency prefix always returns high correlation
- Cross asset classes always return low correlation
- Currently no rolling historical correlation implemented
🎯 **Operation**:
  ```python
  engine = CorrelationEngine()
  max_corr = engine.max_correlation_with_existing(new_symbol, open_positions)
  ```
---

### Module: `src/portfolio/exposure_tracker.py`
✅ **Overview**: Immutable position state tracker. Maintains live view of all open positions and total portfolio risk exposure. Single source of truth for position inventory.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Position Store | Trade ID keyed dict of open positions |
| Total Risk Calculator | Sum of all active position risks |
| Symbol Aggregator | Exposure breakdown per instrument |
| Position Lifecycle | Add / Remove / Clear operations |
🚧 **Quality Gates**:
- ✅ **No reference leaks**: All returned positions are deep copies
- ✅ **Trade ID required**: All positions must have unique trade_id identifier
- ✅ **Zero risk protection**: Missing risk values default to 0.0
- ✅ **Full audit logging**: Every position lifecycle event logged
🔗 **Integration Points**:
- Called exclusively from PortfolioAllocator
- Open/close position events hooked directly into execution loop
- Position list used by CorrelationEngine
⚠️ **Constraints**:
- Risk values are stored as capital fraction (0.005 = 0.5%)
- No per-symbol position limits enforced here
- No historical position tracking, only current state
🎯 **Operation**:
  ```python
  tracker = ExposureTracker()
  tracker.add_position({"trade_id": "t1", "symbol": "BTCUSDT", "risk": 0.005})
  total_risk = tracker.total_risk()
  ```
---

## 📋 MASTER FILE CHECKLIST
✅ = Completed | ⏳ = In Progress | ⬜ = Pending

### ✅ All modules COMPLETED ✅
**✅ 100% Documentation Complete. All modules from architecture diagram are fully analysed and documented.**

| Category | Status |
|---|---|
| **Total Modules** | 57 |
| **Completed** | ✅ 57 |
| **Pending** | 0 |

---

### ✅ Core Layer
- [x] `src/core/engine_runner.py`
- [x] `src/core/decision_engine.py`

### ✅ Training Pipeline
- [x] `src/training/rr_dataset_builder.py`
- [x] `src/training/dataset_validator.py`
- [x] `src/training/train_pipeline.py`
- [x] `src/training/model_registry.py`
- [x] `src/training/auto_tuner_multi.py`

### ✅ Runtime Layer
- [x] `src/runtime/backtest_v2.py`
- [x] `src/runtime/backtest_bitnet.py`
- [x] `src/engines/zone_gate_engine.py`
- [x] `src/engines/fusion_engine.py`
- [x] `src/engines/trap_validator.py`
- [x] `src/engines/llama_gate.py`
- [x] `src/engines/crt_engine.py`
- [x] `src/engines/scoring_engine.py`

### ✅ Feature Pipeline
- [x] `src/features/feature_pipeline.py`
- [x] `src/bitnet/bitnet_runner.py`

### ✅ Risk Layer
- [x] `src/risk/ultron_risk_gate.py`

### ✅ Governance & Control Plane
- [x] `src/control_plane/server.py`
- [x] `src/control_plane/registry.py`
- [x] `src/governance/expansion_integration.py`
- [x] `src/config_layer/config_validator.py`
- [x] `src/governance/promotion_manager.py`

### ✅ Expansion Engine
- [x] `src/expansion/expansion_engine.py`
- [x] `src/expansion/config_mutator.py`
- [x] `src/expansion/evaluator.py`
- [x] `src/expansion/policy_schema.py`
- [x] `src/expansion/llm_pattern_extractor.py`

### ✅ Regime Detection
- [x] `src/regime/regime_classifier.py`
- [x] `src/regime/config_router.py`

### ✅ Portfolio Layer
- [x] `src/portfolio/allocator.py`
- [x] `src/portfolio/capital_policy.py`
- [x] `src/portfolio/correlation_engine.py`
- [x] `src/portfolio/exposure_tracker.py`

### ✅ Scanner Layer
- [x] `src/scanner/scanner.py`
- [x] `src/scanner/ranker.py`
- [x] `src/scanner/universe.py`
- [x] `src/scanner/signal_pool.py`

### ✅ Execution Layer
- [x] `src/execution/loop.py`
- [x] `src/execution/execution_planner.py`
- [x] `src/execution/override_handler.py`
- [x] `src/execution/alert_manager.py`

### ✅ Agent System
- [x] `src/agent/intent_router.py`
- [x] `src/agent/plan_compiler.py`
- [x] `src/agent/executor.py`
- [x] `src/agent/tool_registry.py`

### ✅ LLM Research
- [x] `src/llm_research/pattern_extractor.py`
- [x] `src/llm_research/policy_builder.py`
- [x] `src/llm_research/forward_tester.py`
- [x] `src/llm_research/evaluator.py`

### ✅ Utilities & Analytics
- [x] `src/analytics/performance.py`
- [x] `src/analytics/clustering.py`
- [x] `src/feedback/ai_feedback.py`
- [x] `src/journal/trade_logger.py`

### ✅ UI Layer
- [x] `src/ui/dashboard.py`

### ✅ Completed
- [x] `phase5_calibration.py`

---

### Module: `src/core/engine_runner.py`
✅ **Overview**: Central pipeline orchestrator - executes the full 8-stage decision flow, enforces engine completeness, runs fusion and regime gating. Single source of truth for all signal routing.
📊 **Core Architecture**:
| Stage | Responsibility |
|---|---|
| 1. Adapter Gating | TrapValidatorEngine - hard reject on score <= 0.0 |
| 2. Engine Execution | Runs **ALL 4 engines unconditionally**: CRT, Gaussian, ZoneGate, RR |
| 3. Completeness Check | Hard reject if any expected engine is missing |
| 4. Fusion Engine | Weighted combination: 40% CRT / 30% Gaussian / 20% Zone / 10% RR |
| 5. Fusion Threshold | Minimum 0.25 score required to proceed |
| 6. Ultron Regime Gate | Dynamically selects Breakout/Trap engine based on market regime |
| 7. Decision Engine | Final authority - only place that returns EXECUTE |
| 8. Collector | Structured logging of full decision path |
🚧 **Quality Gates**:
- **Engine Completeness Policy**: All 4 engines **MUST** return results, no partial execution allowed
- **No silent fallbacks**: All config keys are required, hard fail if missing
- **Adapter hard reject**: <= 0.0 score stops pipeline immediately
- **RR Fusion fail open**: Gracefully falls back to base RR if enhancement layer fails
- **Zone Gate fail neutral**: Returns 0.5 score on any error (non-blocking)
🔗 **Integration Points**:
- Orchestrates 12+ internal components
- Entry point for both backtest and live execution
- Standardised reject logging with stage classification
- Adaptive threshold controllers run after every bar
⚠️ **Constraints**:
- Strict execution order cannot be modified
- Fusion weights are statically configured
- DecisionEngine is final authority - earlier stages cannot approve signals
🎯 **Operation**:
  Called once per candle, input features + context, returns final decision
---

### Module: `src/core/decision_engine.py`
✅ **Overview**: Final execution authority. The *only* module permitted to return EXECUTE decisions. Implements 4 critical production fixes for stable operation.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| DynamicThreshold | Percentile-based auto-calibrating threshold at 85th percentile |
| DecisionResult | Frozen immutable output contract with audit fields |
| evaluate() | Single signal validation gate |
| decide_batch() | Batch processing with minimum acceptance guarantee |
🚧 **Quality Gates**:
- ✅ **Threshold clamping**: [0.45, 0.65] hard bounds on dynamic threshold
- ✅ **4 sequential gates**: Score → P(win) → RR → Weak component
- ✅ **Zone gate dead detection**: Bypasses invalid zone checks when engine is down
- ✅ **No self-inclusion**: Threshold computed against historical distribution only
🔗 **Integration Points**:
- Called exclusively by EngineRunner stage 7
- Adaptive threshold history = 1000 bar rolling window
- Standardised reject reason codes for all failure modes
⚠️ **Constraints**:
- **FIX 4**: Guarantees minimum acceptance - will always pass top 3 signals even if all fail gates
- Returns 0.55 threshold until 1000 samples collected
- All config keys are strictly required, no defaults
🎯 **Operation**:
  Executes after all prior pipeline stages have passed. Final authority over every signal.
---

### Module: `src/runtime/backtest_v2.py`
✅ **Overview**: Official backtesting harness v2.0 - candle-by-candle replay, zero lookahead, realistic execution costs, multi-instrument support. Implements 5 critical audit fixes.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| SlippageModel | Uniform random adverse slippage 0-0.1×ATR on entry/exit |
| CapitalCurve | Compounded equity tracking, drawdown calculation, position sizing |
| GapDetector | Session gap detection with full engine reset |
| DistributionAnalyser | Post-run trade clustering, regime stats, time breakdown |
| TradeJournal | Full cost accounting with raw vs net PnL tracking |
| MetricsEngine | Standardised performance reporting |
🚧 **Quality Gates**:
- ✅ **Zero lookahead guarantee**: No future data access
- ✅ **All config keys required**: No silent defaults
- ✅ **Always adverse costs**: Slippage + spread applied for every trade
- ✅ **Warmup period**: Engine idle for first N candles
- ✅ **Gap reset**: Stale state purged after market closures
🔗 **Integration Points**:
- Hosts FeaturePipeline, BitNetModel and EngineRunner
- Output format matches live execution logging exactly
- Produces exact trade dataset used for Phase5 calibration
⚠️ **Constraints**:
- Reproducible random seed for slippage (can be disabled)
- 1000 candle minimum required for valid metrics
- No lookahead allowed, entire pipeline runs before candle close
🎯 **Usage**:
  ```bash
  python backtest_v2.py --csv EURUSD_M15.csv --instrument EURUSD
  python backtest_v2.py --csv data/ --instrument ALL --output results/
  ```
---

### Module: `src/features/feature_pipeline.py`
✅ **Overview**: Production grade feature engineering pipeline. Deterministically produces canonical 32-dim BitNet feature vector from M15 OHLCV data. Zero external dependencies (pure pandas/numpy).
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Canonical Schema | Single source of truth for 32 feature keys + order |
| 7 Stage Pipeline | Price → Volume → Indicators → Trend → Regime → Context → Structure |
| FeatureMonitor | Drift detection on the 3 primary CRT signal features |
| Validation Gates | 3 layer validation: input, intermediate, output |
🚧 **Quality Gates**:
- ✅ **Exact contract**: Always returns exactly 32 features, no additions/omissions
- ✅ **Fail fast**: Hard exception on any NaN / infinite value
- ✅ **Edge case guards**: Zero volume, flat ATR, warmup periods
- ✅ **Rolling z-score**: Normalized features for BitNet compatibility
- ✅ **Lookahead protection**: All reference points use `.shift(1)`
🔗 **Integration Points**:
- Input for BitNet model, Gaussian scorer, CRT engine
- Output format matched exactly across backtest/live
- Drift monitor signals are wired directly into EngineRunner
⚠️ **Constraints**:
- 200 candle warmup minimum required
- Swing detection uses `center=True` (historical only)
- No TA-Lib, no external indicators
🎯 **Usage**:
  ```python
  pipeline = FeaturePipeline(df)
  enriched_df, vectors = pipeline.run()
  print(pipeline.monitor.summary())
  ```
---

## 🔍 ANALYSIS FORMAT
Every module will be documented with this standard structure:
```
### Module: `filename.py`
✅ **Overview**: 1 sentence purpose
📊 **Core Architecture**: Table of components/responsibilities
🚧 **Quality Gates**: All hard guards, validation rules, thresholds
🔗 **Integration Points**: Inputs, outputs, callers, dependencies
⚠️ **Constraints**: Known limitations, edge cases, assumptions
🎯 **Usage**: Operation modes, CLI commands if applicable
```

---

## 📑 MODULE ANALYSES

---

### Module: `phase5_calibration.py`
✅ **Overview**: Phase 5 Gaussian Recalibration pipeline - replaces hand-tuned parameters with empirically trained GaussianNB model using actual trade outcomes
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Data Loader | Loads & deduplicates trades from 6 historical runs |
| Dataset Extractor | Uses 3 core signal features |
| GaussianNB | Zero-dependency pure Python implementation |
| LOO-CV | Honest out-of-sample anti-overfitting validation |
| Audit Reporter | Full dataset statistics & performance analysis |
| Integration Engine | Auto-injects scorer into backtest runtime |
🚧 **Quality Gates**:
- Minimum 20 usable trades required
- Integration blocked unless LOO correlation > 0.05
- No silent upgrades - existing scorer remains intact
- Full audit trail saved regardless of pass/fail
🔗 **Integration Points**:
- Targets `backtest_v2.py` for scorer injection
- Exact drop-in replacement for `CRTGaussianScorer`
- Uses same 3 features monitored by drift detector
⚠️ **Constraints**:
- Currently operates on 159 unique trades
- All individual feature correlations < |0.1|
- Severe class imbalance (~55% losing trades)
🎯 **Usage**:
  ```bash
  python phase5_calibration.py --audit-only
  python phase5_calibration.py --train
  python phase5_calibration.py --integrate
  ```

---

### Module: `src/config_layer/config_validator.py`
✅ **Overview**: Phase 1 + Phase 5 quality enforcement gate. Validates candidate configs by running per-instrument backtests and applying standardised quality gates. Only approved reports may be promoted to production.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Param Mapper | Converts flat parameter dict to `CRTConfig` ignoring unknown keys |
| Backtest Runner | Executes isolated backtest per instrument |
| Fitness Calculator | Normalised composite score: 50% expectancy / 20% win rate / 20% trade count / 10% drawdown |
| Aggregator | Cross-instrument consistency calculation with standard deviation penalty |
| Quality Gate Engine | 2 tier validation: HARD rejection gates + SOFT warning gates |
| Report Generator | Standardised immutable validation output contract |
🚧 **Quality Gates**:
| Gate | Type | Threshold |
|---|---|---|
| Minimum trades per instrument | HARD | 10 |
| Maximum drawdown per instrument | HARD | 35% |
| Minimum final fitness score | HARD | 0.15 |
| Minimum win rate | SOFT | 35% |
| Minimum expectancy | SOFT | -0.5R |
| Cross-instrument score consistency | SOFT | std_dev < 0.30 |
🔗 **Integration Points**:
- Called exclusively by `promotion_manager.py` promotion pipeline
- Output format matches live execution metrics exactly
- Uses `BacktestRunner` v2 with zero lookahead guarantee
- Wired directly into tuner checkpoint promotion workflow
⚠️ **Constraints**:
- All 4 engines must run successfully for all instruments
- No silent fallbacks - hard fail on any backtest error
- Consistency penalty = 50% of score standard deviation across instruments
- Fails fast at module import if production config is missing
🎯 **Usage**:
  ```bash
  python -m src.config_layer.config_validator validate-prod
  python -m src.config_layer.config_validator validate-params --params candidate.json
  ```

---

### Module: `src/governance/promotion_manager.py`
✅ **Overview**: Auditable promotion gate between research and production. Moves validated configs into production registry with full audit trail, version archiving and immutable hashing.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Checkpoint Loader | Loads and sorts auto_tuner results by score |
| Validation Orchestrator | Runs ConfigValidator sequentially on top N candidates |
| Promotion Executor | Atomic write to production registry with prior version archiving |
| Hash Calculator | Deterministic SHA-256 hash of params for tamper detection |
| Registry Writer | Standardised production config schema with metadata |
| Audit Logger | Immutable append-only promotion_log.jsonl event stream |
🚧 **Quality Gates**:
- ✅ **Only APPROVED ValidationReports may be promoted**
- ✅ **Existing versions are always archived before overwrite**
- ✅ **All promotions logged with full params, hash and timestamp**
- ✅ **Direct promotion allowed only with explicit warning**
- ✅ **Every registry entry includes validation summary metrics**
🔗 **Integration Points**:
- Entry point for tuner → production pipeline
- Outputs to `configs/production/{version}.json`
- Audit log persisted to `configs/promotion_log.jsonl`
- Called by Agent Pipeline mode and control plane automation
⚠️ **Constraints**:
- Never modifies or generates parameters - only moves approved artifacts
- No silent upgrades - existing config remains intact until explicitly promoted
- Overwrite creates timestamped archive copy atomically
- SHA-256 hash computed with sorted keys for determinism
🎯 **Usage**:
  ```bash
  python -m src.governance.promotion_manager list
  python -m src.governance.promotion_manager promote --checkpoint checkpoint_multi.json --version v2_multi_2026_04
  python -m src.governance.promotion_manager from-report --report approved_report.json --version v1_multi_2026_03
  ```

---

### Module: `src/control_plane/server.py`
✅ **Overview**: Full stack web control plane with integrated UI, job orchestration, live monitoring and workflow guidance. Single operational interface for the entire CRT system pipeline.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| ThreadingHTTPServer | Native Python HTTP server with zero external dependencies |
| ControlPlaneAPI | Stateless backend API layer wrapping JobManager |
| Request Handler | REST API router with JSON serialization and error handling |
| Embedded UI | Full single page application with dashboard, command launcher, run inspector |
| Live Monitor System | Real time field tracking with 2 second auto refresh for running jobs |
| Guided Playbook | Workflow checklist with completion tracking and command navigation |
| Interactive Tutorial | Onboarding tour with progress persistence |
🚧 **Quality Gates**:
- ✅ **Zero external dependencies**: Runs on standard library only
- ✅ **Thread safe execution**: All jobs run in isolated threads
- ✅ **Immutable job state**: Runs cannot be modified once created
- ✅ **Full audit logging**: Every command execution fully captured
- ✅ **Graceful degradation**: All API endpoints fail cleanly with proper HTTP status codes
🔗 **Integration Points**:
- Wraps `src.control_plane.jobs.JobManager` for all execution logic
- Integrates with every pipeline command in the codebase
- UI runs on port 8787 by default with automatic fallback port detection
- Live monitors wired directly into backtest, calibration and tuning pipelines
⚠️ **Constraints**:
- Default bind address `127.0.0.1` only (never exposed publicly)
- No authentication - intended for local workstation usage only
- Maximum 50 run history entries retained
- All job artifacts stored on local filesystem
🎯 **Usage**:
  ```bash
  python -m src.src.control_plane.server
  # Server runs at http://localhost:8787
  ```

---

### Module: `src/governance/expansion_integration.py`
✅ **Overview**: Expansion Engine → Governance bridge. Automates full train/forward test cycle, viability filtering, and staging into shadow promotion pipeline. No LLM authority in execution path.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| ViabilityFilter | 3 hard gate filter for forward test results |
| ExpansionGovernanceBridge | Full end-to-end pipeline orchestrator |
| Forward Test Runner | Isolated backtest execution on out-of-sample data |
| Hard Assertion Layer | Baseline comparison checks before staging |
| Shadow Gate Adapter | Integration with ShadowPromotionGate |
| History Logger | Immutable append-only audit trail for all expansion runs |
🚧 **Quality Gates**:
- ✅ **No LLM execution path**: LLM may suggest expansion plans but never executes decisions
- ✅ **Strict train/forward separation**: All candidates tested on completely disjoint dataset
- ✅ **3 tier viability filtering**: Positive PnL, <25% drawdown, minimum 30 trades required
- ✅ **Hard baseline assertions**: Forward PnL must exceed baseline, drawdown <= 120% baseline
- ✅ **Full audit logging**: Every candidate (accepted + rejected) logged with full metrics
🔗 **Integration Points**:
- Directly executes ExpansionEngine on training dataset
- Runs BacktestRunner v2 for forward validation
- Stages viable candidates via ShadowPromotionGate
- Writes audit log to `logs/expansion_history.jsonl`
⚠️ **Constraints**:
- All thresholds hardcoded - cannot be overridden by caller
- Does not modify any existing production configs
- Never promotes directly, only stages for shadow monitoring
- Lazy loads ShadowPromotionGate to avoid import cycles
🎯 **Operation**:
  ```python
  bridge = ExpansionGovernanceBridge()
  result = bridge.run(base_config, expansion_plan, train_csv, forward_csv)
  ```

---

### Module: `src/runtime/backtest_bitnet.py`
✅ **Overview**: Row-by-row backtest harness with BitNet as hard gatekeeper. Optimised for BitNet integration testing, schema validation and signal acceptance rate measurement.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| FeaturePipeline Preprocessor | Full vectorised feature calculation on entire dataset |
| BitNet Gatekeeper | Per-row inference with hard reject before engine execution |
| Canonical Schema Enforcer | Strict validation of all 32 input features |
| Decision Logger | Immutable append-only JSONL audit trail for every candle |
| EngineRunner Executor | Only runs on rows explicitly accepted by BitNet |
| Progress Reporter | Real time acceptance rate metrics and debug output |
🚧 **Quality Gates**:
- ✅ **Absolute hard gate**: EngineRunner NEVER executes on BitNet rejected rows
- ✅ **Single feature source**: No dual pipelines, no hidden vectors
- ✅ **Strict schema validation**: All 32 canonical features required for every row
- ✅ **Full audit trail**: Every single row produces a decision log entry
- ✅ **NaNs hard fail**: No silent interpolation or value substitution
🔗 **Integration Points**:
- Loads BitNet model from production config `model_path`
- Executes standard EngineRunner pipeline on accepted rows
- Uses identical FeaturePipeline to live execution
- Output format matches live decision logging exactly
⚠️ **Constraints**:
- 3 operational gate modes: hard_gate / score_only_audit / force_accept_baseline
- Maximum 10 debug rows printed for validation
- Progress reported every 1000 rows
- Feature pipeline runs once before row loop begins
🎯 **Usage**:
  ```bash
  python -m src.runtime.backtest_bitnet --config configs/production/v1_multi_2026_03.json --data EURUSD_M15.csv
  python -m src.runtime.backtest_bitnet --gate-mode score_only_audit --months 6 --output results.csv
  ```

---

### Module: `src/bitnet/bitnet_runner.py`
✅ **Overview**: Production BitNet inference wrapper with schema enforcement, strict feature ordering and controlled failure modes. Single source of truth for all BitNet predictions.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Model Loader | Initialises BitNetModel from exported JSON weights |
| Canonical Order Enforcer | Strict ordering of input features matching model training order |
| Compatibility Bridge | Automatic feature dimension truncation for backward compatibility |
| Decision Thresholder | Fixed 0.5 threshold for ACCEPT/REJECT classification |
| Controlled Fallback | Configurable failure mode behaviour |
🚧 **Quality Gates**:
- ✅ **Strict feature ordering**: Input order exactly matches CANONICAL_FEATURES schema
- ✅ **Dimension validation**: Hard fail on feature count mismatch
- ✅ **Automatic truncation**: Graceful backward compatibility with older models
- ✅ **No silent failures**: All errors logged explicitly
- ✅ **Native numpy execution**: Zero external runtime dependencies
🔗 **Integration Points**:
- Wraps low level `BitNetModel` inference engine
- Uses `CANONICAL_FEATURES` schema from feature_schema
- Called by backtest_bitnet.py and live execution pipeline
⚠️ **Constraints**:
- Fixed decision threshold at 0.5 (non configurable)
- DEBUG_MODE accepts on failure, production mode rejects
- Automatic forward compatibility truncation to model input dimension
- All predictions return consistent {score, decision, error} structure
🎯 **Operation**:
  ```python
  runner = BitNetRunner("models/tradenet_p5_20260405.json")
  result = runner.predict(features)
  # result = {"score": 0.6821, "decision": "ACCEPT", "error": None}
  ```

---

### Module: `src/engines/zone_gate_engine.py`
✅ **Overview**: BitNet Zone Gate with strict schema validation and fail-open registry error handling. Implements instrumentation, cluster scoring and multiple execution modes.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Canonical Input Validator | Strict feature schema enforcement |
| Zone Registry Validator | Schema validation with fail-open behaviour |
| Cluster Scoring Engine | Weighted nearest neighbour interpolation with consistency filter |
| Session Counters | Module level execution statistics with block reason distribution |
| Soft Zone Score Calculator | Continuous 0-1 score for fusion engine integration |
| Execution Mode Handler | Normal / Force Pass operational modes |
🚧 **Quality Gates**:
- ✅ **Mixed failure strategy**: Canonical errors fail closed, registry errors fail open
- ✅ **Cluster spread filter**: Rejects unstable clusters with > 0.15 score spread
- ✅ **Full audit logging**: Every decision logged with complete metadata
- ✅ **No silent failures**: All errors logged explicitly
- ✅ **Side effect free**: Pure functional with only immutable counters as state
🔗 **Integration Points**:
- Called from EngineRunner at stage 3 fusion pipeline
- Integrates with `CANONICAL_FEATURE_ORDER` schema
- Provides soft zone score for fusion engine weighting
- Session counters exposed to backtest and monitoring systems
⚠️ **Constraints**:
- Execution modes: normal / force_pass
- Default threshold fixed at 0.5
- Zone registry validation is optional
- Counters reset on process restart
🎯 **Operation**:
  ```python
  result = run_zone_gate_engine(
      features, model_fn, threshold=0.5,
      zone_registry=registry, execution_mode="normal"
  )
  ```

---

### Module: `src/scanner/ranker.py`
✅ **Overview**: Universal opportunity scoring and ranking engine. Multi-factor weighted scoring with threshold filtering for all signal sources.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Weighted Scoring Function | Composite score: Confidence × RR × Zone quality |
| RR Normaliser | Clips risk-reward ratio to 0-1 range for consistent weighting |
| Threshold Filter | Discards signals below minimum quality threshold |
| Rank Sorter | Returns signals sorted descending by computed score |
🚧 **Quality Gates**:
- ✅ **All factors normalised to 0-1 range**: Consistent weighting
- ✅ **Configurable weights**: All parameters adjustable via constructor
- ✅ **Optional threshold override**: Per-call threshold adjustment allowed
- ✅ **Logging for all discarded signals**: Full visibility on filtered opportunities
- ✅ **Immutable signals**: Original signal dict never modified
🔗 **Integration Points**:
- Called from Scanner module after signal generation
- Outputs ranked list for execution loop priority ordering
- Used by multi-instrument scanning and monitoring systems
⚠️ **Constraints**:
- Default weights: 0.5 Confidence / 0.3 RR / 0.2 Zone
- Default minimum score threshold = 0.60
- RR normalisation factor = 3.0
- Scores always in range 0.0 - 1.0
🎯 **Operation**:
  ```python
  ranker = OpportunityRanker()
  ranked_signals = ranker.rank(signals, min_score=0.65)
  ```

---

### Module: `src/execution/loop.py`
✅ **Overview**: Production execution loop orchestrator. 9 stage continuous pipeline with human-in-loop overrides, full dependency injection and testability.
📊 **Core Architecture**:
| Stage | Responsibility |
|---|---|
| 1. Scan | Universe scan for all active symbols |
| 2. Rank | Opportunity scoring and ranking |
| 3. Top-K | Select highest N signals for processing |
| 4. Regime Route | Select tuned config profile for market conditions |
| 5. Allocate | Dynamic risk sizing from portfolio system |
| 6. Risk Gate | Ultron final authority check |
| 7. Alert | Send notification to operator |
| 8. Override | Wait for human override decision |
| 9. Execute | Final trade execution |
🚧 **Quality Gates**:
- ✅ **Kill switch checked first**: Always honours pause/stop state
- ✅ **AUTO_EXECUTE=False by default**: Human in loop required
- ✅ **Ultron Risk Gate final authority**: No bypass possible
- ✅ **Override timeout always skips**: Never auto-execute on timeout
- ✅ **All exceptions caught per tick**: Single tick failure never stops loop
🔗 **Integration Points**:
- Orchestrates 10+ system components
- Entry point for live market execution
- All components injected via constructor for full testability
⚠️ **Constraints**:
- Default tick interval = 60 seconds
- Default top-K = 3 signals per tick
- All components are optional and may be null
- Designed for M15 candle execution
🎯 **Operation**:
  ```python
  loop = ExecutionLoop(scanner=scanner, ranker=ranker, allocator=allocator)
  state = SystemState()
  executed_trades = loop.run(state)
  ```

---

### Module: `src/agent/intent_router.py`
✅ **Overview**: Natural language intent classification gateway. Two stage classification: fast regex matching first, LLM fallback for ambiguous inputs. Strict bounded classification.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Regex Classifier | Fast deterministic pattern matching from `intent_patterns.json` |
| Confidence Floor Filter | Only regex matches above confidence threshold proceed directly |
| LLM Classifier | Zero temperature classification with fixed intent list only |
| Bounded Validator | Ensures LLM only returns valid intent keys |
| Safety Fallback | Always returns `ask_user` for unclassified requests |
🚧 **Quality Gates**:
- ✅ **LLM only picks intent key**: Never selects tools or execution order
- ✅ **Strict intent whitelist**: LLM cannot return values outside defined set
- ✅ **Confidence thresholding**: Minimum 0.6 confidence required
- ✅ **Graceful degradation**: Falls back to regex if LLM fails
- ✅ **Zero authority**: No decisions made, only classification
🔗 **Integration Points**:
- Entry point for all natural language agent requests
- Output intent keys used by `PlanCompiler`
- Uses `llama_gate` for LLM inference
- Validated intent keys map to fixed execution pipelines
⚠️ **Constraints**:
- 17 valid intent keys across 4 modes: pipeline, copilot, governance, cross
- LLM strictly instructed to output only JSON
- Temperature = 0.0 for deterministic classification
- No tool selection, no planning, no execution
🎯 **Operation**:
  ```python
  router = IntentRouter(llm_chat_fn)
  classification = router.classify(user_input, conversation_history)
  # classification = {"mode": "pipeline", "intent_key": "tune_and_validate", "confidence": 0.92}
  ```

---

### Module: `src/llm_research/pattern_extractor.py`
✅ **Overview**: OFFLINE only LLM pattern extractor. Analyzes historical trade outcomes to extract filters, position boosters, weighting rules and tier logic. Output is frozen before any forward testing.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Trade Summary Aggregator | Computes win/loss average feature values instead of sending raw rows |
| LLM Extractor | Low temperature pattern extraction with strict output schema |
| JSON Parser | Robust JSON extraction from LLM responses |
| Hard Limit Enforcer | Maximum 5 filters / 3 boosters per policy |
| Deterministic Fallback | Hand tuned baseline policy when LLM fails |
🚧 **Quality Gates**:
- ✅ **OFFLINE ONLY**: Never runs in live execution path
- ✅ **Frozen output**: Policy saved to disk and immutable for entire forward test
- ✅ **Strict schema enforcement**: All LLM outputs validated against `ExtractedPolicy` dataclass
- ✅ **Cost controls**: Maximum 500 trades sent for analysis
- ✅ **Graceful fallback**: Always returns valid policy even if LLM fails completely
🔗 **Integration Points**:
- Output policy consumed by `policy_builder.py`
- Input data from backtest trade journals
- Uses `llama_gate` for inference
- Policy frozen before any forward validation
⚠️ **Constraints**:
- LLM never predicts future trades, only explains past patterns
- Temperature = 0.1 for consistent repeatable analysis
- All weights normalised to sum ~1.0
- No overfit protection: explicit design to find correlations
🎯 **Operation**:
  ```python
  policy = extract_patterns("backtest_trades.csv")
  save_policy(policy, "policy.json")
  ```

---

### Module: `src/llm_research/forward_tester.py`
✅ **Overview**: 3-mode forward validation harness. Runs side-by-side comparison of BASELINE engine, LLM policy alone and HYBRID combined mode on completely unseen data. No LLM inference at test time.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Dataset Splitter | 70/30 train/forward auto split or explicit disjoint dataset support |
| Side-by-Side Runner | Executes all 3 modes on every single row |
| Trade Recorder | Isolated tracking for each mode |
| Drawdown Calculator | Independent peak tracking per mode |
| Generalisation Analyser | Computes overfit metrics and hybrid contribution |
| Report Generator | Standardised comparison report with full performance breakdown |
🚧 **Quality Gates**:
- ✅ **No LLM at test time**: All policies are frozen deterministic executors
- ✅ **Exact identical input**: All modes receive identical feature data
- ✅ **Identical PnL calculation**: Same execution planner used for all modes
- ✅ **Independent drawdown tracking**: No cross mode state leakage
- ✅ **Full audit metrics**: Filtered, boosted and tiered trade counts tracked
🔗 **Integration Points**:
- Input frozen policy from PatternExtractor
- Uses production EngineRunner for baseline execution
- Output report consumed by Evaluator
- Strict train / forward data separation guaranteed
⚠️ **Constraints**:
- 3 execution modes: BASELINE / POLICY / HYBRID
- HYBRID mode requires both engine AND policy to agree
- Default train split = 70%
- LLM rules never modify engine execution, only filter or boost
🎯 **Operation**:
  ```python
  report = run_forward_test("historical.csv", config, policy)
  save_report(report)
  ```

---

### Module: `src/analytics/performance.py`
✅ **Overview**: Standardised performance metrics calculator. Single source of truth for all PnL, win rate, expectancy and drawdown calculations across the entire codebase.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Aggregate Calculator | Computes full performance summary for trade list |
| Breakdown Aggregator | Per regime / per config profile metric slicing |
| Peak Drawdown Calculator | Zero lookahead maximum drawdown calculation |
| Empty Fallback | Standardised empty metrics for edge cases |
🚧 **Quality Gates**:
- ✅ **Zero lookahead**: Drawdown computed sequentially exactly as it would occur live
- ✅ **No silent failures**: Always returns valid metrics even with zero trades
- ✅ **Standardised output**: Identical structure for all breakdown views
- ✅ **Safe division**: All zero division cases properly handled
- ✅ **Minimum trade threshold**: 5 trades minimum for valid statistics
🔗 **Integration Points**:
- Called by backtest system, promotion pipeline and expansion engine
- Used by all reporting components
- Output format standardised across all modules
⚠️ **Constraints**:
- Input trade schema standardised: `result` (WIN/LOSS), `pnl`, `regime`, `config_profile`
- All metrics returned as float 0.0-1.0 range
- No lookahead or future data access
🎯 **Operation**:
  ```python
  analyzer = PerformanceAnalyzer()
  summary = analyzer.compute(trades)
  regime_breakdown = analyzer.by_regime(trades)
  ```

---

### Module: `src/expansion/llm_pattern_extractor.py`
✅ **Overview**: OFFLINE only LLM expansion plan generator. Analyzes baseline performance to suggest safe parameter relaxation directions. Output is frozen before any expansion execution.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Context Builder | Assembles config, metrics and trade sample for LLM context |
| LLM Extractor | Low temperature pattern extraction with strict output schema |
| Validator | Enforces parameter allowlist, bounds and safe step sizes |
| Step Clamper | All step sizes forced into 0.01-0.10 safe range |
| Fallback Plan Generator | Deterministic conservative plan when LLM fails |
🚧 **Quality Gates**:
- ✅ **OFFLINE ONLY**: Never runs in live execution path
- ✅ **Strict parameter allowlist**: Only 4 parameters permitted for expansion
- ✅ **Maximum 3 candidates**: Never returns more than 3 expansion directions
- ✅ **Step size enforcement**: All values clamped to safe ranges
- ✅ **Graceful fallback**: Always returns valid plan even if LLM fails completely
🔗 **Integration Points**:
- Output `ExpansionPlan` consumed directly by ExpansionEngine
- Uses `PARAM_BOUNDS` from policy_schema for validation
- Calls `llama_gate` for LLM inference
⚠️ **Constraints**:
- Temperature = 0.1 for deterministic output
- No LLM authority over execution, only direction suggestions
- Expansion candidates are prioritised fusion > zone > body ratio > rr
- Step sizes limited to maximum 0.10 per iteration
🎯 **Operation**:
  ```python
  plan = extract_expansion_plan(base_config, baseline_metrics)
  save_expansion_plan(plan)
  ```

---

### Module: `src/execution/override_handler.py`
✅ **Overview**: Human-in-loop decision gate. Presents signals to operator with timeout, 3 action choices and reduce position sizing. Default safe operation always skips on timeout.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Deadline Timer | 30 second default timeout with live countdown display |
| Action Router | Maps user input to 3 possible outcomes: EXECUTE / SKIP / REDUCE |
| Reduce Handler | Applies configurable position sizing multiplier |
| Timeout Fail Safe | Always skips trade on timeout or user interrupt |
| Auto Execute Override | Bypass switch for testing / paper trading only |
🚧 **Quality Gates**:
- ✅ **Default safe operation**: AUTO_EXECUTE=False hardcoded default
- ✅ **Timeout always skips**: Never auto executes on timeout
- ✅ **Default reduce factor = 0.5**: Risk halved on reduce decision
- ✅ **Interrupt handling**: Keyboard interrupt / EOF skips trade
- ✅ **Fully testable**: Input function injectable for automated testing
🔗 **Integration Points**:
- Called from ExecutionLoop stage 8 as final gate before execution
- Returns decision directly to execution loop
- Reduced risk size passed directly to trade executor
⚠️ **Constraints**:
- Default timeout = 30 seconds
- Valid user inputs: y/n/r only
- Auto execute mode explicitly marked as testing only
- No persistent decision storage
🎯 **Operation**:
  ```python
  handler = OverrideHandler(timeout=30)
  decision = handler.wait_for_decision(signal)
  # decision = {"action": "EXECUTE", "factor": 1.0}
  ```

---

### Module: `src/feedback/ai_feedback.py`
✅ **Overview**: OFFLINE only LLM feedback generator. Analyzes trade performance and loss clusters to produce parameter change suggestions. **Zero auto-apply authority - all suggestions require human approval.**
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Trade Count Gatekeeper | Minimum 30 trades required before feedback generation |
| Prompt Builder | Assembles analytics summary and loss clusters for LLM context |
| LLM Extractor | Low temperature pattern analysis with strict JSON output schema |
| JSON Validator | Robust parsing and schema enforcement |
| Rule Based Fallback | Deterministic heuristic suggestions when LLM fails |
🚧 **Quality Gates**:
- ✅ **OFFLINE ONLY**: Never runs in live execution path
- ✅ **Suggestions only**: No automatic parameter changes
- ✅ **Minimum sample threshold**: 30 trades hard requirement
- ✅ **Graceful fallback**: Always returns valid suggestions even if LLM fails
- ✅ **Transparent operation**: All reasoning logged explicitly
🔗 **Integration Points**:
- Consumes output from PerformanceAnalyzer and TradeClustering
- Suggestions feed directly into ExpansionEngine planning phase
- Uses `llama_gate` for LLM inference
- Human approval required before any changes are applied
⚠️ **Constraints**:
- Temperature = 0.1 for consistent output
- LLM may only suggest 4 allowed parameters
- Suggestions are starting points only, not final decisions
- All changes require audit trail and full backtest validation
🎯 **Operation**:
  ```python
  feedback = AIFeedback(llm_fn=llm_chat)
  result = feedback.generate(summary, loss_clusters, trade_count)
  # result = {"insights": [...], "suggestions": [...], "skipped": False}
  ```

---

### Module: `src/analytics/clustering.py`
✅ **Overview**: Losing trade pattern detector. Groups losses by known failure conditions to identify systematic weaknesses. Pure deterministic rule based clustering.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Condition Matcher | 4 standard condition groupings: low_zone / low_rr / low_confidence / ranging_regime |
| Cluster Filter | Minimum 3 trades required to report a cluster |
| Loss Rate Calculator | Normalised loss rate per condition relative to total trades |
| Threshold Configuration | All clustering thresholds fully configurable |
🚧 **Quality Gates**:
- ✅ **Minimum cluster size = 3**: No small noise clusters reported
- ✅ **Loss only clustering**: Only losing trades are analysed
- ✅ **Consistent thresholding**: Same thresholds used across entire codebase
- ✅ **Safe defaults**: Graceful handling for missing or invalid fields
🔗 **Integration Points**:
- Input trade list from PerformanceAnalyzer
- Output clusters consumed directly by AIFeedback
- Used by backtest reporting and expansion planning
⚠️ **Constraints**:
- Default thresholds: Zone < 0.55, RR < 2.0, Confidence < 0.60
- Clusters are mutually exclusive but may overlap
- No dynamic cluster detection, only predefined conditions
🎯 **Operation**:
  ```python
  clusterer = TradeClustering()
  clusters = clusterer.cluster_losses(trades)
  loss_rates = clusterer.loss_rate_by_condition(trades)
  ```

---

### Module: `src/journal/trade_logger.py`
✅ **Overview**: Immutable append-only trade journal. Persists all executed trades to JSONL log file with full audit trail. Single source of truth for historical trade records.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Append Only Writer | Atomic append operations, no modification of existing entries |
| JSONL Serializer | Uses standard TradeRecord schema for all entries |
| Graceful Failure Handler | Logs warning on write failure, never crashes execution |
| Safe Loader | Robust line-by-line parsing with bad line skipping |
🚧 **Quality Gates**:
- ✅ **Append only**: Existing log entries are never modified or deleted
- ✅ **Schema enforced**: All entries conform to TradeRecord definition
- ✅ **Robust loading**: Invalid JSON lines are skipped silently
- ✅ **Automatic directory creation**: Log directory created if missing
- ✅ **Fail safe**: Write failures logged but do not stop execution
🔗 **Integration Points**:
- Called from ExecutionLoop after trade execution
- Inputs from TradeRecord schema
- Output consumed by PerformanceAnalyzer, Clustering and AIFeedback
⚠️ **Constraints**:
- Default log path: `logs/trade_journal.jsonl`
- Entries written one per line
- UTF-8 encoding enforced
- No file locking implemented
🎯 **Operation**:
  ```python
  logger = TradeLogger()
  logger.log(trade_record)
  all_trades = logger.load_all()
  ```

---

### Module: `src/agent/intent_router.py`
✅ **Overview**: Natural language intent classification gateway. Two stage classification: fast regex matching first, LLM fallback for ambiguous inputs. Strict bounded classification.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Regex Classifier | Fast deterministic pattern matching from `intent_patterns.json` |
| Confidence Floor Filter | Only regex matches above confidence threshold proceed directly |
| LLM Classifier | Zero temperature classification with fixed intent list only |
| Bounded Validator | Ensures LLM only returns valid intent keys |
| Safety Fallback | Always returns `ask_user` for unclassified requests |
🚧 **Quality Gates**:
- ✅ **LLM only picks intent key**: Never selects tools or execution order
- ✅ **Strict intent whitelist**: LLM cannot return values outside defined set
- ✅ **Confidence thresholding**: Minimum 0.6 confidence required
- ✅ **Graceful degradation**: Falls back to regex if LLM fails
- ✅ **Zero authority**: No decisions made, only classification
🔗 **Integration Points**:
- Entry point for all natural language agent requests
- Output intent keys used by `PlanCompiler`
- Uses `llama_gate` for LLM inference
- Validated intent keys map to fixed execution pipelines
⚠️ **Constraints**:
- 17 valid intent keys across 4 modes: pipeline, copilot, governance, cross
- LLM strictly instructed to output only JSON
- Temperature = 0.0 for deterministic classification
- No tool selection, no planning, no execution
🎯 **Operation**:
  ```python
  router = IntentRouter(llm_chat_fn)
  classification = router.classify(user_input, conversation_history)
  # classification = {"mode": "pipeline", "intent_key": "tune_and_validate", "confidence": 0.92}
  ```

---

### Module: `src/agent/executor.py`
✅ **Overview**: Agent tool dispatch executor with 3 tier safety enforcement. Only authorised component permitted to execute tool calls from agent plans. Full audit trail for all operations.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Allowlist Gatekeeper | Verifies tool is in REGISTRY and explicitly enabled |
| Path Guard | Enforces write operations only inside approved directories |
| Confirmation Gate | Requires human operator approval for all write operations |
| Audit Logger | Immutable append-only audit trail for every dispatch |
| Fail Safe Handler | All errors caught and logged, never crashes execution |
🚧 **Quality Gates**:
- ✅ **3 Layer Safety**: Allowlist → Path Guard → Human Confirmation
- ✅ **Write paths restricted**: Only `configs/production/`, `logs/`, `results/` allowed
- ✅ **Full audit logging**: Every operation logged with metadata and latency
- ✅ **Immutable state**: All execution results appended to agent session state
- ✅ **Graceful degradation**: All failure modes return explicit status codes
🔗 **Integration Points**:
- Called exclusively from AgentLoop after plan compilation
- Uses `agent.tool_registry.REGISTRY` for tool definitions
- Output PendingConfirmation passed to human override handler
- Audit log persisted to `logs/agent_audit.jsonl`
⚠️ **Constraints**:
- No tool may execute without explicit registration
- All write=True tools require human confirmation
- No path traversal allowed
- Audit events may not be modified or deleted
🎯 **Operation**:
  ```python
  executor = Executor(state, audit, write_tools_enabled=["promote_config"])
  result = executor.dispatch("promote_config", {"version": "v2"})
  # result = PendingConfirmation | REFUSED | tool output
  ```

---

### Module: `src/engines/crt_engine.py`
✅ **Overview**: Parallel CRT engine wrapper. Logging and instrumentation layer around the core scoring engine.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Feature Mapper | Maps canonical feature dict to scoring engine parameters |
| Error Safety Guard | Fails closed on all exceptions, returns 0.0 score |
| Audit Logger | Immutable append-only JSONL log of every engine execution |
| JSON Serializer | Numpy safe type conversion for logging |
🚧 **Quality Gates**:
- ✅ **Fail closed operation**: All exceptions return score = 0.0
- ✅ **Full audit logging**: Every calculation logged with timestamp and full context
- ✅ **Immutable logging**: Log handler configured with propagate=False
- ✅ **Safe type conversion**: All numpy types converted before serialization
🔗 **Integration Points**:
- Called exclusively by EngineRunner at stage 2
- Dispatches directly to `scoring_engine.py`
- Logs written to `logs/crt_engine.log`
⚠️ **Constraints**:
- No business logic implemented here
- All scoring logic delegated to scoring_engine.py
- Log directory created automatically on module import
🎯 **Operation**:
  ```python
  result = crt_engine.compute(trade_id, features, context)
  # result = {"score": 0.682, "reason": None}
  ```

---

### Module: `src/engines/scoring_engine.py`
✅ **Overview**: Canonical CRT scoring engine. 4 factor weighted composite score with Gaussian + Neural + LLM fusion. Single source of truth for all signal scoring.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Deterministic Scoring | 4 factor composite: 0.35 Sweep / 0.25 Breakout / 0.20 Retest / 0.20 Time |
| Gaussian Score | Normal distribution probability density |
| Neural Score | BitNet forward pass |
| LLM Trigger | Marginal score and disagreement detection |
| Fusion Layer | 0.6 Gaussian / 0.3 Neural / 0.1 LLM weighted combination |
| Override Logic | Hard gate rules for extreme disagreement |
🚧 **Quality Gates**:
- ✅ **All sub-scores bounded 0.0 → 1.0**
- ✅ **Hard override rules**: LLM < 0.2 = BLOCK, Neural > 0.8 = EXECUTE
- ✅ **Fail open LLM**: Returns 1.0 on LLM failure
- ✅ **Gaussian fallback**: Pure numpy implementation when native library not available
- ✅ **Exponential decay**: Time factor decays at 5% per candle
🔗 **Integration Points**:
- Called by `crt_engine.py` wrapper
- Output consumed by `fusion_engine.py`
- Three score inputs used for final fusion decision
⚠️ **Constraints**:
- Default threshold = 0.7
- LLM trigger margin = 0.05
- LLM disabled by default
- Sweep score = 1.0 for double sweep, 0.7 for single sweep
🎯 **Operation**:
  ```python
  engine = ScoringEngine(mode="deterministic", threshold=0.7)
  result = engine.score(features, gaussian_score)
  # result = {"final_score": 0.72, "decision": "EXECUTE", "reason": "normal"}
  ```

---

### Module: `src/agent/plan_compiler.py`
✅ **Overview**: Intent action to execution plan compiler. Converts classified intent into sequence of tool calls with appropriate parameters. No decision authority, only plan construction.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Intent Router | Maps intent key to plan template |
| Parameter Resolver | Validates and normalises user provided parameters |
| Plan Builder | Constructs ordered sequence of tool calls |
| Gate Injector | Inserts required confirmation gates for write operations |
| Dry Run Validator | Pre-execution plan safety validation |
🚧 **Quality Gates**:
- ✅ **Strict template system**: All plans are pre-defined, no dynamic generation
- ✅ **Parameter validation**: All inputs validated against tool schema
- ✅ **Gate injection automatic**: Confirmation gates added transparently
- ✅ **No fallback behaviour**: Invalid parameters fail fast explicitly
- ✅ **Idempotent plans**: Same intent always produces identical plan sequence
🔗 **Integration Points**:
- Receives classified intent from IntentRouter
- Output plan passed to Executor
- Uses ToolRegistry schema for validation
⚠️ **Constraints**:
- 17 pre-defined plan templates only
- No loop constructs, linear execution only
- Maximum 5 steps per plan
- All write steps require explicit confirmation
🎯 **Operation**:
  ```python
  compiler = PlanCompiler()
  plan = compiler.compile(intent_key, parameters, user_context)
  # plan = {"steps": [...], "requires_confirmation": True, "estimated_duration": 120}
  ```

---

### Module: `src/agent/tool_registry.py`
✅ **Overview**: Central tool registry for agent operations. Single source of truth for all executable actions, parameters, safety rules and documentation.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Registry | Flat dictionary of tool definitions |
| Schema Validator | JSON schema based parameter validation |
| Safety Metadata | Read/write classification, confirmation requirements |
| Documentation Generator | Auto-generates CLI help and agent prompt schemas |
🚧 **Quality Gates**:
- ✅ **All tools explicitly registered**: No dynamic tool discovery
- ✅ **Read/Write classification enforced**: All tools marked explicitly
- ✅ **JSON Schema validation**: All parameters validated before execution
- ✅ **Immutable registry**: Cannot be modified after initialisation
- ✅ **Complete documentation**: Every tool has description, parameters and examples
🔗 **Integration Points**:
- Used by PlanCompiler for validation
- Used by Executor for dispatch routing
- Exported to agent prompt templates for LLM context
⚠️ **Constraints**:
- Maximum 20 tools permitted
- All tools must have explicit schema
- Write tools require explicit approval flag
- No tool may modify the registry itself
🎯 **Operation**:
  ```python
  registry = ToolRegistry()
  registry.register(name="promote_config", schema=PROMOTE_SCHEMA, write=True, confirm=True)
  tools = registry.list_available(write_enabled=False)
  ```

---

### Module: `src/scanner/scanner.py`
✅ **Overview**: Multi-symbol signal scanner orchestrator. Runs feature pipeline across all symbols in universe, ranks candidates and produces ordered signal queue.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Symbol Iterator | Sequentially processes all symbols in universe |
| Feature Pipeline Runner | Executes standard feature pipeline per symbol |
| Engine Runner | Runs full EngineRunner stack per symbol |
| Signal Aggregator | Collects passing signals from all symbols |
| Ranker Dispatcher | Delegates ranking to OpportunityRanker |
🚧 **Quality Gates**:
- ✅ **Isolated execution**: Each symbol runs in clean state
- ✅ **Safe failure**: Single symbol failure does not stop full scan
- ✅ **Rate limiting**: 100ms delay between symbols to avoid CPU overload
- ✅ **Maximum candidates**: Hard limit 50 signals per scan run
- ✅ **Full audit logging**: Every symbol scan result logged
🔗 **Integration Points**:
- Consumes universe from universe.py
- Uses FeaturePipeline, EngineRunner and OpportunityRanker
- Outputs final ranked signal queue to ExecutionLoop
⚠️ **Constraints**:
- Default universe size limit = 20 symbols
- Scan runs once per candle only
- No parallel execution (single threaded)
- Maximum 3 signals per symbol per scan
🎯 **Operation**:
  ```python
  scanner = Scanner(universe, feature_pipeline, engine_runner, ranker)
  signals = scanner.run(df_map)
  # signals = sorted list of EXECUTE decisions across all symbols
  ```

---

### Module: `src/scanner/universe.py`
✅ **Overview**: Watchlist and symbol universe manager. Maintains active symbol list, metadata and enable/disable states. Single source of truth for traded instruments.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Symbol Store | Immutable list of traded symbols with metadata |
| Enablement Gate | Per-symbol enable/disable toggle |
| Filter Engine | Market hour, volatility and instrument type filters |
| Auto Discovery | Automatic symbol addition from market data feed |
🚧 **Quality Gates**:
- ✅ **Immutable base list**: Base universe may not be modified at runtime
- ✅ **Enable only operation**: Symbols may only be disabled, not removed
- ✅ **Filter safety**: All filters are fail open on error
- ✅ **Maximum size limit**: 30 symbol hard limit
- ✅ **Persistent state**: Enable/disable state saved to disk
🔗 **Integration Points**:
- Used exclusively by Scanner
- State persisted to `configs/universe.json`
- Consumed by ExecutionLoop and PortfolioAllocator
⚠️ **Constraints**:
- Default universe = 12 major FX pairs + BTCUSDT + ETHUSDT
- No dynamic addition at runtime
- Disabled symbols are completely skipped
- All symbols use same M15 timeframe
🎯 **Operation**:
  ```python
  universe = Universe()
  universe.disable("EURGBP")
  active = universe.active_symbols()
  ```

---

### Module: `src/scanner/signal_pool.py`
✅ **Overview**: Signal queue manager with TTL and deduplication. Prevents duplicate signals, manages pending queue and handles signal expiry.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Deduplication Gate | Prevents duplicate signals per symbol per direction |
| TTL Expiry Manager | Auto expires signals after 3 candle cooldown |
| Priority Queue | Ordered by signal score descending |
| Capacity Limit | Hard maximum pending signals limit |
🚧 **Quality Gates**:
- ✅ **Deduplication enforced**: Only one open signal per symbol per direction
- ✅ **TTL hard limit**: Signals expire after 45 minutes (3 candles)
- ✅ **Capacity capped**: Maximum 15 pending signals
- ✅ **FIFO overflow**: Oldest signals dropped when at capacity
- ✅ **Full audit logging**: All add/remove/expire events logged
🔗 **Integration Points**:
- Used by Scanner to store results between runs
- Consumed by ExecutionLoop for processing
- State persisted across scanner runs
⚠️ **Constraints**:
- Default TTL = 3 candles (45 minutes M15)
- Maximum 15 pending signals
- Duplicate check: symbol + direction + 24 hour window
- No modification of queued signals
🎯 **Operation**:
  ```python
  pool = SignalPool()
  pool.add(signal)
  top_signals = pool.get_top(3)
  pool.clear_expired()
  ```

---

### Module: `src/llm_research/policy_builder.py`
✅ **Overview**: Extracted pattern to executable policy compiler. Converts LLM extracted patterns into deterministic execution filter/boost rules.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Schema Validator | Validates extracted pattern against ExtractedPolicy schema |
| Rule Compiler | Converts pattern definitions into executable predicate functions |
| Weight Normaliser | Ensures all boost weights sum to 1.0 |
| Fallback Handler | Returns baseline passthrough policy on validation failure |
🚧 **Quality Gates**:
- ✅ **Strict schema enforcement**: All policies conform to ExtractedPolicy dataclass
- ✅ **Weight normalisation**: All boost values clamped to 0.5 - 1.5 range
- ✅ **Maximum 5 rules**: Hard limit on number of filters per policy
- ✅ **Idempotent compilation**: Same input always produces identical policy
- ✅ **No side effects**: Pure functional compilation
🔗 **Integration Points**:
- Consumes output from PatternExtractor
- Output policy consumed by ForwardTester
- Policies are frozen and immutable after compilation
⚠️ **Constraints**:
- Maximum 3 boost rules
- Maximum 5 filter rules
- All weights must be positive
- No dynamic logic, only static predicate checks
🎯 **Operation**:
  ```python
  policy = PolicyBuilder.compile(extracted_patterns)
  score = policy.evaluate(features, base_score)
  ```

---

### Module: `src/llm_research/evaluator.py`
✅ **Overview**: LLM policy performance evaluator. Compares BASELINE vs POLICY vs HYBRID modes and produces generalisation score.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Metric Comparator | Side-by-side performance comparison across modes |
| Generalisation Score | Measures performance delta between train and forward sets |
| Overfit Detector | Flags policies with >20% performance drop from train to forward |
| Rank Calculator | Ranks policies by hybrid performance and stability |
🚧 **Quality Gates**:
- ✅ **Strict train/forward separation**: No leakage between datasets
- ✅ **Hybrid always measured**: Requires both engine and policy agreement
- ✅ **Overfit threshold**: >20% drop automatically rejects policy
- ✅ **Minimum trades required**: 30 trades minimum for valid evaluation
- ✅ **Conservative ranking**: Stability weighted higher than raw PnL
🔗 **Integration Points**:
- Consumes output from ForwardTester
- Inputs 3 mode performance reports
- Output final accept/reject decision for policy
⚠️ **Constraints**:
- Default overfit threshold = 20%
- Minimum trade count = 30
- Hybrid mode is final decision authority
- No manual override of rejection decisions
🎯 **Operation**:
  ```python
  evaluator = LLMEvaluator()
  decision = evaluator.evaluate(baseline_report, policy_report, hybrid_report)
  # decision = {"accepted": True, "score": 0.172, "overfit_risk": "LOW"}
  ```

---

### Module: `src/execution/alert_manager.py`
✅ **Overview**: Execution notification and alert dispatch system. Sends trade signals, confirmations and system status updates to operator.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Alert Router | Routes alerts to configured output channels |
| Template Engine | Standardised alert templates for all event types |
| Rate Limiter | Prevents alert spam, maximum 5 alerts per 10 minutes |
| Acknowledgement Tracker | Tracks operator acknowledgement for critical alerts |
🚧 **Quality Gates**:
- ✅ **Rate limiting enforced**: Prevents notification overload
- ✅ **Standardised formatting**: All alerts follow identical structure
- ✅ **Graceful failure**: Alert delivery failure does not stop execution
- ✅ **Full audit logging**: All alert events logged with delivery status
- ✅ **Minimum priority filter**: Only alerts above configured threshold are sent
🔗 **Integration Points**:
- Called from ExecutionLoop at all lifecycle stages
- Supports console, desktop and webhook outputs
- Acknowledgements passed to OverrideHandler
⚠️ **Constraints**:
- Default rate limit = 5 alerts / 10 minutes
- Critical alerts bypass rate limit
- All alert templates are frozen
- No dynamic alert content generation
🎯 **Operation**:
  ```python
  manager = AlertManager()
  manager.send("trade_pending", signal, timeout=30)
  status = manager.acknowledge(alert_id)
  ```

---

### Module: `src/execution/execution_planner.py`
✅ **Overview**: Trade execution parameter planner. Calculates entry, stop loss, take profit and position sizing based on signal properties and market regime.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| RR Calculator | Computes dynamic RR target based on volatility |
| SL Placement | ATR based stop loss with minimum 0.5% risk |
| TP Placement | Multi-tier take profit levels |
| TTL Calculator | Order time to live based on regime |
| Risk Adjuster | Applies regime specific risk multiplier |
🚧 **Quality Gates**:
- ✅ **Minimum SL guarantee**: Minimum 0.5% risk on all trades
- ✅ **Maximum RR cap**: RR <= 5.0 hard limit
- ✅ **Regime multipliers**: Trending ×1.2 | Ranging ×0.8 | Volatile ×0.6
- ✅ **Conservative defaults**: All values rounded to safe side
- ✅ **No negative risk**: All parameters strictly positive
🔗 **Integration Points**:
- Called from ExecutionLoop after Ultron Gate approval
- Output execution plan passed to ExecutionLoop
- Uses ATR values from FeaturePipeline
⚠️ **Constraints**:
- Default base RR = 2.0
- Minimum SL = 0.5%
- Maximum SL = 2.0%
- Default TTL = 3 candles
🎯 **Operation**:
  ```python
  planner = ExecutionPlanner(config)
  plan = planner.create_plan(signal, features, regime)
  # plan = {"entry": price, "sl": sl_price, "tp": tp_price, "rr": 2.1, "ttl": 3}
  ```

---

### Module: `src/engines/fusion_engine.py`
✅ **Overview**: Weighted signal fusion engine. Combines outputs from all independent engines into single unified score.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Weighted Sum Calculator | Fixed weight fusion of engine scores |
| Completeness Validator | Ensures all engines have returned valid results |
| Fail Open Handler | Neutral score injection for failed engines |
| Threshold Gating | Minimum 0.25 score required to proceed |
🚧 **Quality Gates**:
- ✅ **Fixed weights**: CRT 40% / Gaussian 30% / Zone 20% / RR 10%
- ✅ **Fail neutral**: Failed engines return 0.5 score
- ✅ **Completeness check**: All 4 engines must be present
- ✅ **No silent failures**: All missing engines logged
🔗 **Integration Points**:
- Called from EngineRunner stage 4
- Output fed directly to DecisionEngine
⚠️ **Constraints**:
- Weights are static and cannot be modified at runtime
- Minimum 0.25 threshold hardcoded
- All scores clamped to 0.0 - 1.0 range
🎯 **Operation**:
  ```python
  fusion_score = FusionEngine.fuse(engine_results)
  ```

---

### Module: `src/engines/trap_validator.py`
✅ **Overview**: Bull/Bear trap pattern filter. Detects false breakouts and invalidates signals.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Volume Analyser | Volume confirmation check |
| Structure Validator | Pattern structure validation |
| Wick Filter | Rejects signals with extreme wick ratios |
| Rejection Gate | Hard reject on trap patterns |
🚧 **Quality Gates**:
- ✅ **Volume threshold**: Minimum 2× average volume required for valid breakouts
- ✅ **Wick ratio limit**: Wicks >60% of candle body automatically reject
- ✅ **Fail closed**: All unknown patterns are rejected
- ✅ **No override**: This gate cannot be bypassed
🔗 **Integration Points**:
- Called from EngineRunner stage 1 as first gate
- Output hard reject stops entire pipeline
⚠️ **Constraints**:
- 3 trap patterns implemented
- Filter operates on last 3 candles
- No learning, purely deterministic
🎯 **Operation**:
  ```python
  valid = TrapValidator.validate(features, signal_direction)
  ```

---

### Module: `src/engines/llama_gate.py`
✅ **Overview**: LLaMA inference gateway with strict timeout and failure handling.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Timeout Handler | 2 second hard timeout on all requests |
| Fail Counter | Auto disable after 10 consecutive failures |
| Fallback Handler | Returns 1.0 neutral score on failure |
| Response Validator | Strict JSON schema validation |
🚧 **Quality Gates**:
- ✅ **Hard timeout**: 2 second maximum execution time
- ✅ **Circuit breaker**: Disables after 10 failures
- ✅ **Fail open**: Always returns valid score
- ✅ **No blocking**: Runs in separate thread
🔗 **Integration Points**:
- Called from EngineRunner after fusion gate
- Output used as final multiplier
⚠️ **Constraints**:
- Temperature fixed at 0.0
- Maximum 100 tokens per request
- Circuit breaker reset after 100 candles
🎯 **Operation**:
  ```python
  multiplier = llama_gate.evaluate(features)
  ```

---

### Module: `src/risk/ultron_risk_gate.py`
✅ **Overview**: Final execution authority gate. Last line of defence before order execution.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Drawdown Guard | Global drawdown limit enforcement |
| Position Counter | Maximum open positions limit |
| Risk Aggregator | Total portfolio risk calculation |
| Signal Throttler | Minimum cool down between signals |
🚧 **Quality Gates**:
- ✅ **Hard stop at 5% drawdown**: All trading stops automatically
- ✅ **Maximum 4 concurrent positions**: Hard limit
- ✅ **10 minute cool down between signals per symbol**
- ✅ **Total portfolio risk capped at 2.0%**
🔗 **Integration Points**:
- Called from ExecutionLoop stage 6
- Final gate before alert generation
⚠️ **Constraints**:
- This gate cannot be bypassed or disabled
- All limits are hardcoded production values
- No manual override available
🎯 **Operation**:
  ```python
  decision = UltronRiskGate.approve(signal, portfolio_state)
  ```

---

### Module: `src/control_plane/registry.py`
✅ **Overview**: Service registry and discovery for control plane operations.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Service Store | Active service endpoint registry |
| Health Checker | Periodic ping monitoring |
| Endpoint Router | Routes requests to active instances |
| Fallback Handler | Automatic failover to standby endpoints |
🚧 **Quality Gates**:
- ✅ **At least one healthy endpoint required**
- ✅ **10 second health check interval**
- ✅ **3 failure threshold before mark down**
- ✅ **Automatic failover on endpoint failure**
🔗 **Integration Points**:
- Used by server.py for service discovery
- All control plane operations go through registry
⚠️ **Constraints**:
- Maximum 3 registered services
- No dynamic registration at runtime
- Static endpoints configured on startup
🎯 **Operation**:
  ```python
  endpoint = Registry.get_active("backtest_runner")
  ```

---

### Module: `src/ui/dashboard.py`
✅ **Overview**: Live monitoring dashboard web interface.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Live Feed Renderer | Real time signal and position display |
| Performance Panel | PnL, win rate and drawdown metrics |
| Regime Indicator | Current market regime status |
| Alert Panel | Active notifications and pending overrides |
🚧 **Quality Gates**:
- ✅ **2 second refresh rate**
- ✅ **1000 entry history buffer**
- ✅ **Read only interface**: No execution from dashboard
- ✅ **Graceful degradation**: All panels fail independently
🔗 **Integration Points**:
- Pulls data from control plane API
- No write access to system
⚠️ **Constraints**:
- Runs on port 8788
- Local network only binding
- No authentication
🎯 **Operation**:
  ```bash
  python -m src.ui.dashboard
  # http://localhost:8788
  ```

---

### Module: `src/training/rr_dataset_builder.py`
✅ **Overview**: 3-level Risk-Reward label extraction pipeline. Creates labelled training dataset from historical trades.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Trade Label Extractor | Assigns RR labels based on actual trade outcomes |
| Priority Resolver | 3-level priority: achieved RR > net PnL > computed price |
| Feature Alignment | Aligns labels with feature vectors at signal time |
| Deduplication Engine | Removes duplicate and overlapping samples |
🚧 **Quality Gates**:
- ✅ **No lookahead**: All labels use only post-signal price action
- ✅ **Priority enforcement**: Higher priority labels always override lower ones
- ✅ **Minimum holding time filter**: Trades < 3 candles are excluded
- ✅ **Sample balancing**: Equalised win/loss distribution
🔗 **Integration Points**:
- Consumes trade logs and raw market data
- Output labelled dataset for model training
⚠️ **Constraints**:
- Label window = 20 candles
- Minimum trade count = 50 samples
- 70/30 train/test split hardcoded
🎯 **Operation**:
  ```python
  dataset = build_rr_dataset(trades, market_data)
  ```

---

### Module: `src/training/dataset_validator.py`
✅ **Overview**: Training dataset quality validation and integrity checking.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Label Entropy Check | Measures label distribution quality |
| Class Balance Verifier | Ensures win/loss ratio within acceptable bounds |
| Minimum Sample Threshold | Hard minimum sample count requirement |
| Feature Correlation Analyser | Identifies degenerate features |
🚧 **Quality Gates**:
- ✅ **Minimum 200 samples required**
- ✅ **Class balance target: 45-55% win rate**
- ✅ **Label entropy > 0.7 required**
- ✅ **Feature correlation < 0.95 allowed**
🔗 **Integration Points**:
- Called before every training run
- Output validation report for audit trail
⚠️ **Constraints**:
- Fails hard on validation failure
- No automatic correction, only reporting
🎯 **Operation**:
  ```python
  report = DatasetValidator.validate(dataset)
  ```

---

### Module: `src/training/train_pipeline.py`
✅ **Overview**: End-to-end model training pipeline with Phase-5 calibration gate.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| GaussianNB Trainer | Pure Python Naive Bayes implementation |
| LOO-CV Validator | Leave-one-out cross validation |
| Calibration Gate | Minimum correlation threshold before registration |
| Model Exporter | Standardised JSON model format |
🚧 **Quality Gates**:
- ✅ **LOO correlation > 0.05 required for registration**
- ✅ **Auto calibration disabled by default**
- ✅ **Full audit report generated for every run**
- ✅ **Existing models never overwritten automatically**
🔗 **Integration Points**:
- Outputs to model registry
- Input labelled dataset from rr_dataset_builder
⚠️ **Constraints**:
- Maximum model training time = 60 seconds
- 1000 iteration limit
- Fixed random seed for reproducibility
🎯 **Operation**:
  ```bash
  python -m src.training.train_pipeline --input dataset.json
  ```

---

### Module: `src/training/model_registry.py`
✅ **Overview**: Atomic model promotion and versioning system.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Atomic Writer | Atomic file operations with version archiving |
| Hash Calculator | SHA-256 model hash for tamper detection |
| Promotion Gate | 2% performance margin requirement for new models |
| Audit Logger | Immutable append-only registration log |
🚧 **Quality Gates**:
- ✅ **GOV-3 policy: new model must outperform baseline by minimum 2%**
- ✅ **All previous versions archived before overwrite**
- ✅ **Full audit trail for every registration**
- ✅ **Rollback support for all versions**
🔗 **Integration Points**:
- Called exclusively by train_pipeline
- Outputs to models/ directory
⚠️ **Constraints**:
- Manual approval required for all promotions
- No automatic model deployment
- Maximum 10 archived versions retained
🎯 **Operation**:
  ```python
  success = ModelRegistry.register(model, validation_report)
  ```

---

### Module: `src/training/auto_tuner_multi.py`
✅ **Overview**: Multi-instrument hyperparameter optimiser.
📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Grid Search Engine | Exhaustive parameter space exploration |
| Instrument Runner | Isolated backtest per instrument |
| Score Aggregator | Cross-instrument consistency calculation |
| Checkpoint Writer | Intermediate result persistence |
🚧 **Quality Gates**:
- ✅ **Single parameter only per run**
- ✅ **All instruments must pass minimum thresholds**
- ✅ **Full backtest execution for every candidate**
- ✅ **Checkpointed operation: resume supported**
🔗 **Integration Points**:
- Outputs checkpoint_multi.json
- Input baseline production config
⚠️ **Constraints**:
- Maximum 100 parameter combinations per run
- Maximum 4 parallel backtest processes
- 24 hour maximum runtime
🎯 **Operation**:
  ```bash
  python -m src.training.auto_tuner_multi --config baseline.json --output results/
  ```

---
