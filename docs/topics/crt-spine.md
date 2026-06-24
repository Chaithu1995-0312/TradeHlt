# Topic: CRT Spine (candle → order)

> **Topic-visibility unit.** The system's core concept: how one M15 candle becomes an
> approved (or rejected) order. Read this for the grounded picture without loading the whole
> decision path.
>
> Created: 2026-06-01 · Updated: 2026-06-05 · Status: living
> _Updated 2026-06-01: linked the 3 verified downstream spine topic docs._
> _Updated 2026-06-05: repaired drifted citations (VALID_TRANSITIONS :1021→:1074, enforced :1046→:1099) to the dual `path:line · Symbol` form per §6.3._

## In plain language
The "spine" is the straight line every candle walks: score it through four engines, fuse the
scores into one decision, plan the trade (entry / stop / target), and let a risk gate approve or
reject. The CRT engine is the backbone of that line — it tracks market structure through a
fixed 9-state graph (`RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION →
RESOLUTION`, plus the `SHADOW_PENDING` and `EXPIRED` branches). Everything else hangs off this
spine; the async feeders (governance, training, agent, INOUT) join it but don't replace it.

## Code covered
- [`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) — the CRT state machine. The **authoritative legal-transition map** (9 states) is `src/config_layer/crt_engine_v2.py:1073 · VALID_TRANSITIONS`; enforced at `src/config_layer/crt_engine_v2.py:1098 · VALID_TRANSITIONS`. Enums `CRTState` / `Direction` / `RejectReason` live here.
- [`src/core/engine_runner.py`](../../src/core/engine_runner.py) — the orchestrator every decision passes through. `EXPECTED_ENGINES = {"crt","gaussian","zone_gate","rr"}` ([`:52`](../../src/core/engine_runner.py)); the completeness check that prevents silent partial fusion is at [`:718`](../../src/core/engine_runner.py).
- Downstream of engine_runner (runtime order, per `CLAUDE.md §10`): `FusionEngine` → `DecisionEngine` → `ExecutionPlannerV1_2` → `UltronRiskGate`. Each now has its own topic doc with verified citations: [`fusion-decision.md`](fusion-decision.md) (`core/fusion_engine.py:253` + `core/decision_engine.py:85`), [`execution-planning.md`](execution-planning.md) (`config_layer/execution_planner.py:129`), [`ultron-risk-gate.md`](ultron-risk-gate.md) (`core/ultron_risk_gate.py:69` + `_wrapper.py:58`).

## Ins / Outs
- **Ins:** an M15 `Candle` stream (see [`docs/reference/schemas.md`](../reference/schemas.md)); production config sections (`crt_engine`, `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`) via `get_prod_section(...)`.
- **Outs:** per-candle decision → optional `ExecutionPlan` (entry/SL/TP/RR/TTL) → terminal APPROVE/REJECT; events streamed to `logs/` JSONL (e.g. `TRADE_OPENED`, `EXPANSION_EXPIRED`).

## Entry points & validations
- **Reached via:** `python src/runtime/backtest_v2.py --csv ... --output results` (the canonical entry, [`README.md`](../../README.md) Quick Start); also the control-plane backtest command and `live_engine_hook.py` for live mode.
- **Validated by:** four-engine completeness gate ([`engine_runner.py:718`](../../src/core/engine_runner.py)); `VALID_TRANSITIONS` rejects illegal state moves; no-lookahead streaming in `BacktestRunner`; determinism/replay gate (`docs/architecture/replay-governance.md`).

## Tests
- `tests/` CRT + engine-runner domains (see [`docs/reference/testing.md`](../reference/testing.md) for the 10-domain layout). Cross-reference there for the exact files. **TODO:** pin the specific `test_*.py` paths on next touch.

## Fits in architecture
This *is* the spine in [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md)
(Steps 1–7) and the 9-state graph in
[`docs/architecture/event-taxonomy.md`](../architecture/event-taxonomy.md) §3. Those two docs are
authoritative for flow and states; this topic is the human-language entry point that links to them.

## Discussion (filled in-session)
- **Risks:** `2026-06-01` removing/renaming an engine without updating `EXPECTED_ENGINES` produces silent partial fusion (`CLAUDE.md §4`).
- **Challenges:** `2026-06-01` per-step `tests/` file mapping not yet pinned here — relies on `testing.md` domains.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` "structure validity ≠ execution validity" (README priorities) — a valid CRT structure does not guarantee a valid trade; keep the two notions separate when discussing coverage.
- **Enhancements:** `2026-06-01` promote the four downstream stubs (fusion/decision/planner/risk-gate) to full topic docs as sessions touch them.
- **Enhancements:** `2026-06-02` the CRT session filter (`crt_engine_v2.py:2589-2611`, compares `_sess_name` vs `CRTConfig.allowed_sessions`) is now **instrument-scopable** — `engine_runner.allowed_sessions_overrides` in the prod config gives a named instrument its own session set (global fallback for the rest), resolved in `production_config.load_prod_config_from_registry`. Lets BNBUSDT run +ASIA +OFF_SESSION without touching ETH/BTC. Also fixed a latent canonicalization bug: the loader stripped underscores (`off_session`→`OFFSESSION`) which never matched the engine's `OFF_SESSION` literal; `_canon_session` now preserves it.
- **Need more info:** `2026-06-02` the **live** path (`live_engine_hook._normalize_session`, line ~199) does not yet consult `allowed_sessions_overrides` — backtest/validation/promotion honor it, live deployment would need the same per-symbol resolution before going live with a scoped config.
- **Need more info:** `2026-06-01` ~~exact `file:line` for `FusionEngine` / `DecisionEngine` / `UltronRiskGate` entry methods~~ — **resolved 2026-06-01**: verified and split into [`fusion-decision.md`](fusion-decision.md), [`execution-planning.md`](execution-planning.md), [`ultron-risk-gate.md`](ultron-risk-gate.md).
