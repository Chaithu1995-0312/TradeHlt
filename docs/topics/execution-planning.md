# Topic: Execution Planning

> **Topic-visibility unit.** How an accepted decision becomes a concrete trade plan (entry, and
> the scaffolding for SL/TP/RR/TTL). The step between "yes, trade" and "here's the order."
>
> Created: 2026-06-01 · Updated: 2026-09-03 · Status: living

## In plain language
Once the decision engine says "execute," the **execution planner** turns that decision into a
deterministic trade plan: validate the inputs, derive the entry, attach a trade intent, TTL, and
position-size hint, and produce a trace. It is intentionally *not* the scorer — it only consumes
decision outputs. One important nuance hidden in the name: the planner does **not** itself set
SL/TP/RR — those are injected downstream by `live_engine_hook` via `compute_crt_levels()`.

**The trade object is two-target with a partial exit — and one config key lies about it.**
Downstream of the planner, production does not run a single stop and a single target. On the
TP1 transition, `ExecutionEngine.update_trade` ([`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py))
closes `partial_tp_fraction` (0.5) of the position and reassigns the stop to the **half-way
point** between entry and TP1, letting the remainder run to TP2. The governing config key is
named `partial_tp_breakeven_enabled` — **it does not move the stop to breakeven**; the half-way
point is already in profit. Key name and behaviour disagree, and the code is what runs. See
ontology node `SEM-017`, finding **F-088**, and
[`config-reference.md`](../reference/config-reference.md) for why the key is retained-as-named.

## Code covered
- [`src/config_layer/execution_planner.py:129`](../../src/config_layer/execution_planner.py) — `ExecutionPlannerV1_2`. Constructor merges caller config over `DEFAULT_CONFIG` ([`:147`](../../src/config_layer/execution_planner.py)). Public entry `plan(engine_result, features, context)` ([`:156`](../../src/config_layer/execution_planner.py)): required `engine_result` keys `decision/direction(1|-1)/confidence/regime`; required `context` keys `symbol/signal/score`; raises `ValueError` on missing feature keys or invalid prices. Returns `{decision, execution_id, trade_intent, entry_price, gate result, trace}`.
- **Per its own docstring ([`:179`](../../src/config_layer/execution_planner.py)):** "SL/TP/RR are NOT set here — injected by `live_engine_hook` via `compute_crt_levels()`."

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/execution/__init__.py`](../../src/execution/__init__.py)
- [`src/execution/execution_intent_v1_0.py`](../../src/execution/execution_intent_v1_0.py)

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
- **Findings:** `2026-08-21` two programs measured this exit object end-to-end for the first time (XAUUSD M15, 47,157 bars). **F-088** — every outcome-bearing result in repo history was measured on a *different* object than this one: `forward_walk` models one TP with no partial and no trail, so `src/research/oracle/multi_tp_walk.py` was built and certified (18-test parity floor + independent twin on 20,000 paths + a real ledger row to 1e-10) to express the production trade. It also corrected the same-bar tie-break: the effective rule is **SL-first** (`_intrabar_trigger_price`), not the `TP2 > SL > TP1` branch order declared at `crt_engine_v2.py:2456`, so the backtest path was already conservative. **F-087** — the half-way trail was audited against 12 alternative stop policies and a do-nothing control: it is the **worst point estimate 8 of 8** on the tight geometries production actually runs, by a stable ≈−0.012R. That is ~15–25% of one confidence interval on a grid whose entire policy spread sits below the noise floor, so it is **not** a licence to disable it (needs measured ΔG001, §6.5) — no config was touched. The binding lever is stop **width**, through `cost_r = cost_price / risk_distance`, not stop policy.
- **Findings:** `2026-06-03` the execution-planner **replay experiment** ([`execution-planner-replay-bnbusdt-2026-06-03.md`](../analysis/execution-planner-replay-bnbusdt-2026-06-03.md)) split the RETEST→EXECUTION edge: it is **SELECTION** (~+0.145R), not SL/TP structure (~+0.031R). The structure SL/TP is **risk-shaping** (WR 43%→57%, maxDD 6.0R→3.0R on selected) rather than an expectancy source, and does **not** rescue rejected candidates. Reinforces F-002; F-010 stays open (live planner/Ultron layer still unexercised). The experiment is fed by new additive `RETEST_REPLAY` telemetry from `crt_engine_v2.py` (schemas.md §9.4).
- **2026-09-03 — spine citation pass:** named 2 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
