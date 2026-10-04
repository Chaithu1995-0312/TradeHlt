# Topic: Execution Loop (multi-signal tick pipeline)

> **Topic-visibility unit.** The continuous, multi-signal tick orchestrator (scan → rank → regime →
> allocate → gate → alert → human-override → execute). Production-grade + tested, but **scaffolding**:
> no caller wires it in yet.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
This is the "trading floor loop" design: every tick, scan instruments for signals, rank them, take the
top few, classify regime, size them with the portfolio allocator, pass them through the risk gate,
alert the operator, wait for a human y/n/reduce decision (it does **not** auto-execute by default), then
place the trade. It's fully built and well-tested — but nothing in the codebase actually calls it yet,
so today it's dormant scaffolding for a future multi-signal live mode (distinct from the single-candle
`live_engine_hook` path that *is* wired).

## Code covered
- [`src/execution/loop.py:31`](../../src/execution/loop.py) — `ExecutionLoop` — `run()` at :82 (tick loop), `_process_signal()` at :144 (per-signal pipeline).
- [`src/execution/loop.py:9`](../../src/execution/loop.py) — `SystemState` — shared pause/run/positions/signals state.
- [`src/execution/alert_manager.py:15`](../../src/execution/alert_manager.py) — `AlertManager` — `send()` at :44 (log + optional stdout + external hook).
- [`src/execution/override_handler.py:13`](../../src/execution/override_handler.py) — `OverrideHandler` — `wait_for_decision()` at :41 (y/n/r/timeout; `AUTO_EXECUTE=False`).

## Ins / Outs
- **Ins:** injected collaborators (scanner, ranker, pool, regime_classifier, config_router, allocator, risk_gate, alert_manager, override_handler, trade_executor) + `tick_seconds`/`top_k`/`max_ticks`.
- **Outs:** a list of executed signal dicts (audit trail); alerts via AlertManager; per-signal enrichment (risk/regime/profile). Each stage can SKIP (allocator REJECT, risk BLOCK, override SKIP).

## Entry points & validations
- **Reached via:** _no production caller_ — `grep ExecutionLoop` finds only the package + its test. Intended as a future live multi-signal entry.
- **Validated by:** `UltronRiskGate` as final authority in the pipeline; human override default-on (no silent auto-execute); `test_execution_loop.py` exercises every guard/branch with mocks.

## Tests
- [`tests/test_execution_loop.py`](../../tests/test_execution_loop.py) — AlertManager routing, OverrideHandler decisions, ExecutionLoop guards (paused / allocator-reject / risk-block / override-skip / happy path / max_ticks).

## Fits in architecture
The multi-signal counterpart to the single-candle live path ([`live-execution.md`](live-execution.md)).
It composes [`portfolio-allocation.md`](portfolio-allocation.md), [`regime-classifier.md`](regime-classifier.md),
and [`ultron-risk-gate.md`](ultron-risk-gate.md) — but is dormant until wired into `core`/`agent` orchestration.

## Discussion (filled in-session)
- **Blockers:** 2026-06-05 — **not invoked anywhere** (scaffolding); the portfolio allocator it drives is therefore also off the live path. Wiring it in is a prerequisite for multi-signal live trading.
- **Risks:** 2026-06-05 — because it's untriggered, its guards are unexercised in production; treat "tested" as unit-level, not live-proven (F-010).
- **Reconciled:** 2026-06-05 — verdict **ORPHANED** confirmed (zero callers in `src/`); the whole scan→allocate→ExecutionLoop path is finding **F-013**. See `analysis/intent-vs-code-reconciliation-2026-06-05.md` item 6.
