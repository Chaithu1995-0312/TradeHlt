# Service: Decision Spine

> **Loadable context unit.** Understand and safely change the core decision path
> without loading the rest of the codebase. This is the exemplar that validates the
> [`_template.md`](_template.md). Status: lives in `src/core/` + `src/config_layer/`
> today; **already seam-ready** (config injected, dict returns). Anchored to
> `v2_multi_2026_04`.

## Purpose
Turn a scored market bar into an approved, sized trade plan — or a reasoned rejection.

## Inputs
- **Data:** `input_data` (feature map / 38-dim canonical vector; v2.0: 35), `context` (signal
  metadata: instrument, session, regime, strategy consensus), optional `actual_pnl`.
- **Config:** injected via each class `__init__` (fusion weights, decision thresholds,
  planner intents/TTLs, risk limits) — **not** read at import time.
- **Contracts in:** the four engine scores `{crt, gaussian, zone_gate, rr}` from the
  Scoring service.

## Internal flow (plain English)
1. **`EngineRunner.run(input_data, context, actual_pnl=None)`**
   (`core/engine_runner.py:519`) orchestrates the bar: gathers engine outputs, calls
   fusion, decision, and assembles the output dict.
2. **`FusionEngine.compute(engine_results, trade, weights, regime)`**
   (`core/fusion_engine.py:290`) blends scores under a weighted-completeness gate →
   `final_score`, `normalized_score`, RR, `weak_component`, `zone_gate_dead`. Layer 3
   is the **LLM uncertainty-band tie-breaker** (`:610`) — advisory only, fail-open to
   neutral. Clear signals never call the LLM.
3. **`DecisionEngine.evaluate(score, p_win, zone_gate, fusion, config)`**
   (`core/decision_engine.py:104`) applies the (dynamic, percentile-based) threshold →
   `DecisionResult` (`decision`, `reason`, `confidence`, `threshold_used`,
   `reject_stage`).
4. **`ExecutionPlannerV1_2.plan(engine_result, features, context)`**
   (`config_layer/execution_planner.py:129`) classifies intent and derives entry + TTL
   + `execution_id`. SL/TP/RR are injected afterward via `compute_crt_levels`
   (`core/gate_intelligence.py`).
5. **`UltronRiskGate.evaluate(trade, portfolio_state)`**
   (`core/ultron_risk_gate.py:156`) applies capital protection, position sizing, and the
   kill-switch → final `decision` (`APPROVE|REJECT`), `final_position_size`,
   `risk_reason`.

**Key branches:** any stage may REJECT (recorded with `reject_stage`); a hard drift
veto or kill-switch open short-circuits to REJECT; missing engines trip the
completeness gate (silent partial fusion is a known hazard — all four engines
mandatory).

## Outputs
- **Data:** `EngineRunnerOutput` (`core/types.py:54`) + `GateResult`
  (`decision: "APPROVE"|"REJECT"`, `core/types.py:95`) + execution plan.
- **Contracts out:** decision events to the Telemetry service; approved plan to the
  Execution/Risk service.

## Events emitted
- `DECISION_SNAPSHOT` (queued to `CognitiveBus`), `DECISION_LINEAGE`
  (`logs/decision_lineage.jsonl`), `ENGINE_TELEMETRY` (`logs/engine_telemetry.jsonl`).
  Trade ENTRY/EXIT/REJECT currently go to flat `logs/fusion_trades.jsonl`
  (`utils/trade_logger.py`) — being enveloped in **Trd-M1**.

## Replay notes
- Deterministic given the same engine scores + injected config. No wall-clock, no
  network, no lookahead in the spine itself. The only stochastic neighbor is slippage
  (seeded, `backtest_v2.py:379`) applied downstream in the runner, not in the spine.
- **Must not change to keep runs comparable:** the threshold computation inputs, the
  fusion weighting, and the engine-completeness rule. Changing any requires the
  determinism acceptance gate in [`replay-governance.md`](../replay-governance.md) §6.

## Upstream / downstream services
- **Upstream:** Feature/Ingestion (feature vector), Scoring Engines (4 scores).
- **Downstream:** Execution/Risk (approved plan), Telemetry/Event-Bus (events).

## Decomposition blockers
- Essentially none for the spine itself. The surrounding coupling is in the
  *orchestration* layer: strategy consensus is injected into `EngineRunner`'s context
  dict rather than passed as a typed input (Tier 3), and `live_engine_hook`
  singletons wrap the spine in live mode (Tier 1, `live_engine_hook.py:90-96`). See
  [`codebase-state-map.md`](../codebase-state-map.md) §3.
