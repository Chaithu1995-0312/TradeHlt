# Topic: CRT Spine (candle → order)

> **Topic-visibility unit.** The system's core concept: how one M15 candle becomes an
> approved (or rejected) order. Read this for the grounded picture without loading the whole
> decision path.
>
> Created: 2026-06-01 · Updated: 2026-08-04 · Status: living
> _Updated 2026-06-01: linked the 3 verified downstream spine topic docs._
> _Updated 2026-06-05: repaired drifted citations (VALID_TRANSITIONS :1021→:1074, enforced :1046→:1099) to the dual `path:line · Symbol` form per §6.3._
> _Updated 2026-08-04: soft-confirmation double-EMA-update probe + shadow-TTL off-by-one fix (F-067/F-068 — see Discussion)._

## In plain language
The "spine" is the straight line every candle walks: score it through four engines, fuse the
scores into one decision, plan the trade (entry / stop / target), and let a risk gate approve or
reject. The CRT engine is the backbone of that line — it tracks market structure through a
fixed 9-state graph (`RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION →
RESOLUTION`, plus the `SHADOW_PENDING` and `EXPIRED` branches). Everything else hangs off this
spine; the async feeders (governance, training, agent, INOUT) join it but don't replace it.

## Code covered
- [`src/config_layer/state_identity.py`](../../src/config_layer/state_identity.py) — the CRT state-machine **identity layer** (extracted 2026-07-18 to break the `crt_engine_v2 ↔ state_contract_loader/state_topology` import cycle). The **authoritative legal-transition map** (9 states) is `src/config_layer/state_identity.py:69 · VALID_TRANSITIONS` (seed dict); the Phase-2 topology layer serves the immutable enforcement view at `src/config_layer/state_topology.py:109 · VALID_TRANSITIONS`. Enums `src/config_layer/state_identity.py:35 · CRTState` / `Direction` / `RejectReason` and the `state_identity.py:137 · CRTConfig` dataclass live here; `crt_engine_v2` re-exports all five for backward compatibility.
- [`src/config_layer/crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) — the CRT state machine engine (detector, `StateMachine`, `UltronRiskEngine`, `ExecutionEngine`, `CRTEngine` orchestrator); imports its enums/config/transitions from `state_identity`.
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
- **Trace → Parquet → DuckDB query layer (2026-09-06):** Additive read-only sidecars only. `jsonl_to_parquet.FAMILY_DEFAULTS` maps `_crt_construction.jsonl` → `engine_state_after`. New `src/utils/duckdb_query.open_views` + `scripts/analysis/query_trace.py` query projections under `logs/` and `results/`. JSONL remains system of record; no emitter enable flip; no spine wiring; `query_decision_atlas.py` unchanged. See `docs/reference/schemas.md` §9.17.
- **Risks:** `2026-06-01` removing/renaming an engine without updating `EXPECTED_ENGINES` produces silent partial fusion (`CLAUDE.md §4`).
- **Challenges:** `2026-06-01` per-step `tests/` file mapping not yet pinned here — relies on `testing.md` domains.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` "structure validity ≠ execution validity" (README priorities) — a valid CRT structure does not guarantee a valid trade; keep the two notions separate when discussing coverage.
- **Enhancements:** `2026-06-01` promote the four downstream stubs (fusion/decision/planner/risk-gate) to full topic docs as sessions touch them.
- **Enhancements:** `2026-06-02` the CRT session filter (`crt_engine_v2.py:2589-2611`, compares `_sess_name` vs `CRTConfig.allowed_sessions`) is now **instrument-scopable** — `engine_runner.allowed_sessions_overrides` in the prod config gives a named instrument its own session set (global fallback for the rest), resolved in `production_config.load_prod_config_from_registry`. Lets BNBUSDT run +ASIA +OFF_SESSION without touching ETH/BTC. Also fixed a latent canonicalization bug: the loader stripped underscores (`off_session`→`OFFSESSION`) which never matched the engine's `OFF_SESSION` literal; `_canon_session` now preserves it.
- **Need more info:** `2026-06-02` the **live** path (`live_engine_hook._normalize_session`, line ~199) does not yet consult `allowed_sessions_overrides` — backtest/validation/promotion honor it, live deployment would need the same per-symbol resolution before going live with a scoped config.
- **Need more info:** `2026-06-01` ~~exact `file:line` for `FusionEngine` / `DecisionEngine` / `UltronRiskGate` entry methods~~ — **resolved 2026-06-01**: verified and split into [`fusion-decision.md`](fusion-decision.md), [`execution-planning.md`](execution-planning.md), [`ultron-risk-gate.md`](ultron-risk-gate.md).
- **Findings (F-067, F-068):** `2026-08-04` a multi-model bug trace over the RETEST/soft-confirmation window surfaced two real defects, source-verified before acting (see [`docs/current-findings.md`](../current-findings.md)):
  - **F-067 (research/architecture, no code change this pass):** `EngineState.update_emas` fires TWICE on the same candle close during soft-confirmation — unconditionally at `crt_engine_v2.py:2629` (pre-chain, every candle) and again at `crt_engine_v2.py:2998` (inside `elif self.state.evaluating_soft_conf:`, every candle of the confirmation window; there is no `RETEST` state branch, so RETEST-state candles always fall through to this `elif`). Re-applying the update gives effective α = 2α−α², which COMPRESSES the fast/slow spread in a trend (not the "overly sensitive" inflation an earlier bug-trace claimed) — `f_mom` under-states momentum in exactly the setups it's meant to reward. Measured, not fixed: `scripts/analysis/soft_conf_ema_double_update_probe.py` (OBSERVATION_ONLY, no src edit) ran the full XAUUSD corpus, n=17 soft-conf evaluations, trend-compression confirmed (ratio 0.4673 vs ~0.457–0.467 predicted), 0 tier-bucket flips (ledger-neutral on this corpus), self-consistency error 0.0 (bit-exact reimplementation vs the real `compute_soft_confirmation` at `crt_engine_v2.py:1898`). Floor: `tests/test_soft_conf_ema_probe.py`. The decision to remove the duplicate call is a separate, still-open gated turn.
  - **F-068 (architecture, shipped):** shadow-memory TTL off-by-one — `reset_to_range`'s `[DEADLOCK FIX]` fall-through (comment at `crt_engine_v2.py:2653` area) means a shadow created via an HTF-reset (`crt_engine_v2.py:2655`) reaches the RANGE branch on the SAME candle, which used to decrement `pending_displacement_ttl` immediately — a configured TTL of N yielded only N−1 usable bars. Fixed with a new `EngineState.pending_displacement_created_idx` field (set once at creation, cleared on all four teardown paths — consumed/leak/expiry/non-HTF-reset) guarding the RANGE-branch decrement. XAUUSD before/after: `SHADOW_PENDING` resumptions 43→51 (+8), `SWEEP` 6995→6987 (−8), all other states byte-identical, `total_setups` unchanged at 1 (no economic claim possible at n=1). Floor: `tests/test_shadow_ttl_lifecycle.py` (written to fail against the pre-fix guard — verified by temporarily reverting it, confirming the fail, then restoring).
  - A prior bug-trace's claim that the TTL off-by-one was "documented in the code with the comment 'same bar burns 1'" was checked and found FALSE — no such comment existed in `crt_engine_v2.py` (only in a prior session log). The fix adds the comment that claim assumed already existed.
