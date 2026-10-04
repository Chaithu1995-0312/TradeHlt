# Topic: Ultron Risk Gate

> **Topic-visibility unit.** The terminal authority on the spine: the last check that approves a
> trade and sets its final size, or rejects it. The LLM never reaches here.
>
> Created: 2026-06-01 · Updated: 2026-09-03 (Trd-M5) · Status: living

## In plain language
`UltronRiskGate` is the **sole execution authority** — the final, deterministic gate that consumes
the execution plan plus portfolio state and returns approve/reject with the final position size.
It runs seven checks in a fixed order and rejects on the first failure, so a trade only passes if
*every* risk condition holds. Its kill-switch state is persisted to disk so it can't be bypassed by
re-instantiating the object (a real hardening fix, "FRAG-1").

## Code covered
- [`src/core/ultron_risk_gate.py:69`](../../src/core/ultron_risk_gate.py) — `UltronRiskGate`. Check order ([`:74-82`](../../src/core/ultron_risk_gate.py)): **(1) TTL expiry → (2) RR floor → (3) daily trade limit → (4) kill switch (daily loss) → (5) portfolio exposure → (6) SL distance (÷0 guard) → (7) position sizing**. Required config keys `_REQUIRED_KEYS` ([`:90`](../../src/core/ultron_risk_gate.py)): `max_risk_per_trade_pct`, `max_portfolio_risk_pct`, `max_trades_per_day`, `max_daily_loss_pct`, `min_rr_ratio`, `disabled`. Persisted kill-switch loaded in `__init__` ([`:113`](../../src/core/ultron_risk_gate.py), FRAG-1). Public API `evaluate(trade, portfolio_state)`.
- [`src/core/ultron_risk_gate_wrapper.py:58`](../../src/core/ultron_risk_gate_wrapper.py) — `UltronRiskGateWrapper`, the adapter used alongside the gate.
- Both imported by the live path: [`src/runtime/live_engine_hook.py:25-26`](../../src/runtime/live_engine_hook.py).
- **Trd-M5 (2026-06-01):** `evaluate()` opens with an **execution-authority isolation assertion** (`core/governance_mode.assert_isolated`): the inbound plan must carry no LLM-derived execution verdict (`llm_decision`/`llm_gated`/`llm_verdict`), enforcing that this gate stays rule-based and the advisory LLM never reaches execution. `GOVERNANCE_MODE=strict` raises; `advisory` (default) warns + continues.

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/core/ultron_live_adapter.py`](../../src/core/ultron_live_adapter.py)

## Ins / Outs
- **Ins:** `trade` (execution-plan dict: entry/SL/TP/RR/TTL), `portfolio_state` (open exposure, daily P&L, trade count); config section `ultron_risk_gate`.
- **Outs:** `{decision: APPROVE|REJECT, reject_reason?, final_position_size}`; on approve, the trade is sized and released; kill-switch state may be written to disk.

## Entry points & validations
- **Reached via:** terminal step of `EngineRunner`/live decision path, after `ExecutionPlannerV1_2`. Imported in `live_engine_hook` for live mode and in the backtest decision path.
- **Validated by:** the seven ordered checks (first failure rejects); persisted kill-switch prevents cross-instantiation bypass; SL-distance ÷0 guard.

## Tests
- [`tests/test_ultron_risk_gate.py`](../../tests/test_ultron_risk_gate.py) — gate checks + `DEFAULT_CONFIG`.
- [`tests/test_ultron_gate.py`](../../tests/test_ultron_gate.py) — gate behavior.
- [`tests/test_ultron_wrapper.py`](../../tests/test_ultron_wrapper.py) — `UltronRiskGateWrapper`.

## Fits in architecture
Spine step 5 of 5 (terminal authority): `… → ExecutionPlannerV1_2 → UltronRiskGate` (`CLAUDE.md §10`; `goal.md` "execution authority isolated"). LLM is advisory and never enters this gate (`llm-governance-layer.md`). See [`execution-planning.md`](execution-planning.md), [`crt-spine.md`](crt-spine.md).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` the gate is the single point where capital risk is enforced — any check reordering or a config key drift (`_REQUIRED_KEYS`) changes real risk posture. Treat edits as high-blast-radius.
- **Challenges:** `2026-06-01` kill-switch persistence path must be writable in every environment (live + backtest) or FRAG-1 protection silently no-ops.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` **module drift (3-way)** — runtime uses `core/ultron_risk_gate.py` (+ `core/ultron_risk_gate_wrapper.py`, both imported at [`live_engine_hook.py:25-26`](../../src/runtime/live_engine_hook.py)), but [`codebase-analysis.md`](../analysis/codebase-analysis.md) documents `src/risk/ultron_risk_gate.py`. The `risk/` variant is a dead-code/drift candidate. An archived legacy import also exists (`archive/inout_legacy/...`). Not resolved here (code change, out of scope).
- **Enhancements:** `2026-06-01` emit a structured per-check trace (which of the 7 fired) into telemetry for replay-auditable rejections.
- **Need more info:** `2026-06-01` exact line of `evaluate()` and the position-sizing formula (check 7) — read on next touch.
- **2026-09-03 — spine citation pass:** named 1 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
