# 2 · Implemented System Map (Phase B)

> Point-in-time audit, 2026-06-02. Code-first (ignored docs). `Exists / Wired / Active / Tested /
> Used-in-Prod` per subsystem, each with ≥1 `file:line`. "Active" = runs by default under the ACTIVE
> config (`v2_multi_2026_04 - deepdeektry`). "Used-in-Prod" = output actually consumed by the decision/
> execution path (strict).

## Spine (signal → decision)

| System | Exists | Wired | Active | Tested | Used-in-Prod | Evidence |
|--------|:---:|:---:|:---:|:---:|:---:|----------|
| **EngineRunner** (orchestrator) | YES | YES | YES | YES | YES | `engine_runner.py:286,576`; run @ backtest_v2.py:1956 |
| **CRT engine v2** | YES | YES | YES | YES | YES | `crt_engine_v2.py`; call @ engine_runner.py:655 |
| **Gaussian scorer** | YES | YES | YES | YES | YES | `gaussian_impl="ml"` in ACTIVE config; call @ engine_runner.py:666 |
| **ZoneGate (BitNet)** | YES | YES | YES | YES | YES | `engine_runner.py:632`; ~20% fusion weight |
| **RR engine** | YES | YES | YES | YES | YES | base RREngine @ rr_engine.py:37; call @ engine_runner.py:684 |
| **RRFusionLayer** | YES | YES | COND | YES | COND | `engine_runner.py:690`; **fail-open passthrough** if model missing (rr_fusion.py:64) |
| **FusionEngine** | YES | YES | COND | YES | YES | `fusion_engine.py:253`; compute() active, evaluate() shadowed (`fusion_use_evaluate=false`) |
| **DecisionEngine** | YES | YES | YES | YES | YES | `decision_engine.py:85`; only emitter of execute/reject |
| **RegimeGovernor** | YES | YES | **NO** | YES | NO | `ultron_gate_enabled=false` → legacy path, no quota cap (engine_runner.py:877,915) |
| **ExecutionPlannerV1_2** | YES | LIVE-only | LIVE-only | YES | LIVE-only | `execution_planner.py:129`; **absent from backtest spine** |
| **UltronRiskGate** | YES | LIVE-only | LIVE-only | YES | LIVE-only | `ultron_risk_gate.py:69`; **not instantiated in backtest** |

## Intelligence / sidecar / dormant

| System | Exists | Wired | Active | Tested | Used-in-Prod | Evidence |
|--------|:---:|:---:|:---:|:---:|:---:|----------|
| **StrategyOrchestrator (S1–S10)** | YES | YES | YES | YES | **NO*** | `strategy_orchestrator.py`; *enabling it = byte-identical inert (consensus path doesn't alter decisions)* |
| **CognitiveBus** | YES | YES | **NO** | NO | NO | `engine_runner.py:439-446`; gated by absent `cognitive_layer` in ACTIVE config; DecisionSnapshot telemetry only (:1059) |
| **ReplayMemory (RME)** | YES | YES | **NO** | YES (repaired) | NO | `replay_memory_engine.py`; consumed only via CognitiveBus (off); registries wired in v1 only |
| **TradeNet** | YES (v1) | **STUB** | NO | partial | **NO** | fusion neural slot designated-but-stubbed (`fusion_engine.py:8`); v2 3-head unimplemented |
| **Zone EXPECTANCY (mean_rr)** | YES | sidecar | NO | – | **NO** | stored on zones, ignored by spine (geometric gate only) |
| **MarketStateCluster / HMF** | YES | sidecar | NO | – | NO | cognitive sidecar (off) |
| **Concept-drift detector** | YES | YES | YES | partial | **NO (no gate)** | `live_engine_hook.py:676` logs "Trade signal unreliable" — **trade proceeds** |
| **Scanner / SignalPool** | YES | **NO** | NO | NO | NO | not imported in any live path |
| **ForwardTester (×2)** | YES | **NO** | NO | NO | NO | `bitnet/`, `llm_research/`; offline-only |
| **Probability Surface** | **NO** | – | – | – | – | plan SCOPED, never built |
| **BitNet score @ entry** | YES (compute) | **NO (persist)** | – | – | **NO** | not on TradeRecord (`backtest_v2.py:200`; CSV 70 cols, 0× `bitnet_*`) |

## Governance / validation

| System | Exists | Wired | Active | Tested | Used-in-Prod | Evidence |
|--------|:---:|:---:|:---:|:---:|:---:|----------|
| **ConfigValidator** | YES | YES | YES | YES | YES | `config_validator.py:288-339`; hard+soft gates; **crt_engine-fidelity gap** |
| **PromotionManager** | YES | YES | YES | YES | **BYPASSED** | `promotion_manager.py:138-170`; active config never went through it |
| **config_integrity guards** | YES | NO (not a gate) | NO | YES (7) | NO | `config_integrity.py`; flags deepdeektry correctly but not enforced |
| **ShadowPromotionGate** | YES | YES (promo only) | NO (runtime) | YES | NO | `shadow_promotion_gate.py:52`; min_shadow_trades + PnL gates |
| **MetaGovernorExecutor** | YES | NO (decision loop) | NO | – | NO | `bitnet_governance_executor.py`; audit-log only |
| **PortfolioValidation** | YES | YES | advisory | YES | NO (not a gate) | `portfolio_validation.py:100`; post-hoc |

\* **Used-in-Prod = NO\*** for the orchestrator means: wired and "enabled" but its output is **not consumed**
(turning it on produced a byte-identical backtest). This is the headline **enablement ≠ consumption** pattern.

## Read of the map
- The **profitable spine is small and fully live**: CRT + Gaussian(ML) + ZoneGate + RR → Fusion → Decision.
- The **capital gate and entry planner are live-only** — measured (backtest) ROI does not exercise them.
- The **intelligence surface is mostly built-but-not-consumed** (TradeNet stub, ReplayMemory off,
  zone-expectancy ignored, drift detected-not-gated, BitNet score not persisted). → Constraint 3.
