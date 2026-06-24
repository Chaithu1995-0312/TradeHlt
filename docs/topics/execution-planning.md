# Topic: Execution Planning

> **Topic-visibility unit.** How an accepted decision becomes a concrete trade plan (entry, and
> the scaffolding for SL/TP/RR/TTL). The step between "yes, trade" and "here's the order."
>
> Created: 2026-06-01 · Updated: 2026-06-03 · Status: living

## In plain language
Once the decision engine says "execute," the **execution planner** turns that decision into a
deterministic trade plan: validate the inputs, derive the entry, attach a trade intent, TTL, and
position-size hint, and produce a trace. It is intentionally *not* the scorer — it only consumes
decision outputs. One important nuance hidden in the name: the planner does **not** itself set
SL/TP/RR — those are injected downstream by `live_engine_hook` via `compute_crt_levels()`.

## Code covered
- [`src/config_layer/execution_planner.py:129`](../../src/config_layer/execution_planner.py) — `ExecutionPlannerV1_2`. Constructor merges caller config over `DEFAULT_CONFIG` ([`:147`](../../src/config_layer/execution_planner.py)). Public entry `plan(engine_result, features, context)` ([`:156`](../../src/config_layer/execution_planner.py)): required `engine_result` keys `decision/direction(1|-1)/confidence/regime`; required `context` keys `symbol/signal/score`; raises `ValueError` on missing feature keys or invalid prices. Returns `{decision, execution_id, trade_intent, entry_price, gate result, trace}`.
- **Per its own docstring ([`:179`](../../src/config_layer/execution_planner.py)):** "SL/TP/RR are NOT set here — injected by `live_engine_hook` via `compute_crt_levels()`."

## Ins / Outs
- **Ins:** `engine_result` (from `EngineRunner.run()`), canonical `features` dict, `context` (`symbol/signal/score`, optional `account_balance`); config section `execution_planner` (intent-specific TP multipliers, TTLs, `min_rr_ratio`, `default_sl_atr_mult`, `risk_percent`).
- **Outs:** trade plan dict (`execution_id`, `trade_intent`, `entry_price`, gate result, `trace`). SL/TP/RR populated later by the live hook.

## Entry points & validations
- **Reached via:** the decision surface downstream of `DecisionEngine`; consumed before `UltronRiskGate`. Profiles (conservative/standard/aggressive) expressed via `min_rr_ratio` / `default_sl_atr_mult` / `risk_percent` in the production config.
- **Validated by:** input validation (`ValueError` on missing feature keys / invalid prices); the produced plan is then gated by `UltronRiskGate` (see [`ultron-risk-gate.md`](ultron-risk-gate.md)).

## Tests
- [`tests/test_execution_planner.py`](../../tests/test_execution_planner.py) — planner behavior.
- [`tests/test_execution_contract_v1.py`](../../tests/test_execution_contract_v1.py) — execution contract.
- [`tests/test_sl_tp_comparator.py`](../../tests/test_sl_tp_comparator.py) — SL/TP comparison.

## Fits in architecture
Spine step 4 of 5: `… → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate` (`CLAUDE.md §10`). See [`fusion-decision.md`](fusion-decision.md), [`ultron-risk-gate.md`](ultron-risk-gate.md), [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` the name implies SL/TP/RR are planned here; they are not (injected by `live_engine_hook.compute_crt_levels()`). A reader trusting the class name could mis-trace where stops come from.
- **Challenges:** `2026-06-01` plan correctness depends on `engine_result` shape contracts that aren't typed (dict keys); a drift in `EngineRunner.run()` output silently breaks the planner via `ValueError`.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` **module drift** — [`codebase-analysis.md`](../analysis/codebase-analysis.md) documents `src/execution/execution_planner.py`, but the runtime/`ExecutionPlannerV1_2` lives in `src/config_layer/execution_planner.py` (confirmed: `class ExecutionPlannerV1_2` at `:129`). The `execution/` variant is a dead-code/drift candidate. Not resolved here (code change, out of scope).
- **Enhancements:** `2026-06-01` consider moving `compute_crt_levels()` SL/TP derivation adjacent to the planner (or documenting the split prominently) so the plan is self-contained.
- **Need more info:** `2026-06-01` where `compute_crt_levels()` is defined in `live_engine_hook` and its exact SL/TP inputs (read on next touch). → `2026-06-03` **resolved:** `compute_crt_levels()` lives in [`src/core/gate_intelligence.py:24`](../../src/core/gate_intelligence.py) and *mirrors* the backtest authority `build_trade` ([`src/config_layer/crt_engine_v2.py:1840`](../../src/config_layer/crt_engine_v2.py)). Key nuance: the **SL is anchored to the *displacement* candle extreme** (`sl = disp_{low|high} ∓ sl_atr_buffer·atr`), not the retest/entry candle; TP1 uses an **intent-specific** R-multiple, TP2 = `tp2_atr_multiplier`.
- **Findings:** `2026-06-03` the execution-planner **replay experiment** ([`execution-planner-replay-bnbusdt-2026-06-03.md`](../analysis/execution-planner-replay-bnbusdt-2026-06-03.md)) split the RETEST→EXECUTION edge: it is **SELECTION** (~+0.145R), not SL/TP structure (~+0.031R). The structure SL/TP is **risk-shaping** (WR 43%→57%, maxDD 6.0R→3.0R on selected) rather than an expectancy source, and does **not** rescue rejected candidates. Reinforces F-002; F-010 stays open (live planner/Ultron layer still unexercised). The experiment is fed by new additive `RETEST_REPLAY` telemetry from `crt_engine_v2.py` (schemas.md §9.4).
