# Plan — Code-first system understanding walk (read-only, no docs built)

## Context
User wants to understand the whole system before any further building. Docs exist in abundance
(book, signal-flow, atlas, memory, master refs) but overlap and freshness is UNVERIFIED; user's
standing priority is "system flow first" (runtime trace 0/342). Chosen approach: follow the CODE,
using `docs/architecture/signal-flow.md` only as a map — source wins on conflict.

Deliverable = **chat discussion only**. No docs, no code edits, no config edits. (Only the
mandatory SESSION LOG append to `assistant_project.md` per CLAUDE.md §6, if user allows.)

## Pre-flight facts (verified this turn)
- `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08` on branch `semanticos_impl`
  (CLAUDE.md §4.0 text says `v2_multi_2026_04` for `patch` — branch-scoped, not a conflict to fix now; will note).
- Two rails exist (F-103): backtest rail and live rail.

## Walk order (one stop per turn, discuss before moving on)
**Rail A — Backtest (what research measures)**
1. Entry: `src/runtime/backtest_v2.py` → `BacktestRunner` (CLI, config load, data load).
2. Features: `src/features/feature_pipeline.py` (48-dim canonical vector, warmup drop).
3. CRT state machine: `src/config_layer/crt_engine_v2.py` (`process_candle`, states, TRADE_OPENED).
4. Fusion gate (post-commit): `src/core/engine_runner.py` → `fusion_engine.py` → `decision_engine.py`.
5. Exit/ledger: trade walk + PnL inside `backtest_v2`.

**Rail B — Live (what would trade)**
6. `src/runtime/live_rail_orchestrator.py` / `live_rail_feeder.py` / `src/inout/live_rail/*`.
7. `src/runtime/live_engine_hook.py` → `EngineRunner` → `src/config_layer/execution_planner.py`
   (`ExecutionPlannerV1_2`) → `src/core/ultron_risk_gate.py`.

**Close:** one-screen picture of both rails: what is wired, what is dormant, where they diverge.

## Method per stop
- Grep/read only the functions on the path (not whole files); cite `path:line`.
- State: inputs → what it decides → outputs → who consumes it → which config keys drive it.
- Mark each claim VERIFIED (read in source) or UNVERIFIED.

## Verification
Read-only; correctness = every stated claim backed by a `path:line` read this session.
