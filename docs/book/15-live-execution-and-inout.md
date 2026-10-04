# Chapter 15 — Live Execution and INOUT

**Part V — Execution**
Status of this chapter: Written (INOUT ambiguity **resolved** in Grok review pass, 2026-08-07)

## Why this chapter exists

Everything in Parts II–V so far describes the backtest path faithfully, and the live path *mostly*
the same way — but "mostly" is doing real work in that sentence, and this chapter is where the book
is most honest about the gap between the two. It closes Part V by describing what actually runs on a
live tick, and by resolving a naming collision that earlier drafts left open: `src/inout/` vs
`archive/inout_legacy/`.

## What problem it solves

Distinguishes "what the backtest replays" from "what a live tick actually triggers," and is explicit
about which of the two the rest of this book's Parts II–V chapters were describing (mostly the
former, since it's the better-evidenced, more heavily tested path).

## What you need to already know

[Chapter 14](14-ultron-risk-gate.md) — the one point where a live-execution rail rejoins the
synchronous spine.

## The idea

### The live tick entry point

The confirmed entry point for a live candle is `HookedLiveEngine.process` in
`src/runtime/live_engine_hook.py:582`. This is what actually gets called on a live tick, and it
draws on `src/live/`, `src/inout/`, and `src/execution/loop.py` as supporting modules.

### `src/execution/loop.py` — real code, no caller yet

`src/execution/loop.py` (plus `alert_manager.py`, `override_handler.py`) implements a multi-signal
execution loop, but per the repository's own topic tracking it is explicitly **scaffolding — no
caller yet**. It has tests (`test_execution_loop`) but isn't wired into a live path that actually
invokes it.

### INOUT naming collision — **RESOLVED** (Grok review pass, 2026-08-07)

Two paths share the word "inout" but are **not the same subsystem**. Direct comparison of both trees
resolves the earlier open question without inventing a third story:

| Path | What it actually is | Status |
|---|---|---|
| `archive/inout_legacy/ARCHIVED_2026_05_02/` | A **parallel execution pipeline** that bypassed the canonical spine: `scanner.py`, `state_machine.py`, `controller.py`, `executor.py`, `runner.py`, `probability_engine.py`, plus a SQLite `db.py` | **Legacy / Archived 2026-05-02** — README states it violated spine + no-DB conventions; no production `src/` importers at archival time |
| `src/inout/` | **Market-data I/O only** — candle/funding fetchers: `mt5_candle_fetcher.py`, `alphavantage_candle_fetcher.py`, `hummingbot_candle_fetcher.py`, `perp_funding_fetcher.py` (4 modules + package cache) | **Production data-ingestion helpers** — not a strategy rail, not a second decision path |

**Verdict:** `src/inout/` is **not** the successor of the archived INOUT rail. It is a **name reuse**
for a different responsibility (fetch OHLCV / funding into CSV loaders). The archived rail's
replacement for *execution* is stated in its own README: all valid live orchestration routes through
`src/runtime/live_engine_hook.py` → `HookedLiveEngine.process()`. CLAUDE.md's placement note that
"live-mode code" may land under `src/inout/` is therefore best read as historical folder convention
for *I/O*, not an invitation to revive the archived parallel spine.

`docs/architecture/goal.md`'s phrase "INOUT currently archived" correctly describes the **strategy
rail** now under `archive/inout_legacy/`. It does **not** mean the current `src/inout/` fetchers are
dead.

## Classification

| Concept | Status |
|---|---|
| `HookedLiveEngine.process` (live tick entry point) | Production |
| `src/execution/loop.py` (multi-signal execution loop) | **Partial** — built, tested, no live caller |
| INOUT strategy rail (`archive/inout_legacy/`) | **Legacy / Archived** (2026-05-02) |
| `src/inout/` data fetchers | **Production (I/O)** — distinct from the archived rail |

## Authoritative sources

- `src/runtime/live_engine_hook.py:582` — `HookedLiveEngine.process`.
- `src/execution/loop.py`, `alert_manager.py`, `override_handler.py`.
- `docs/topics/live-execution.md`, `docs/topics/execution-loop.md` — the always-synced topic docs.
- `docs/architecture/goal.md` §2 — "INOUT currently archived" (strategy rail, not fetchers).
- `archive/inout_legacy/ARCHIVED_2026_05_02/README.md` — archival reason + replacement path.
- `src/inout/*.py` — current fetcher modules (MT5 / Alpha Vantage / Hummingbot / perp funding).

## Unresolved questions

- Whether residual `tests/inout/` still exercise the archived pipeline (the archive README suggested
  moving them to `tests/archive/`) was not re-audited this pass — hygiene only, not a live-path risk.
- `src/execution/loop.py` remains scaffolding with no live caller (unchanged).

---
**Previous:** [Chapter 14 — Ultron Risk Gate](14-ultron-risk-gate.md) · **Next:** [Chapter 16 — Config-First Doctrine and the Promotion Path](16-config-first-and-promotion.md)
**Related:** [Chapter 02 — The Invariants and the Happy Flow](02-invariants-and-happy-flow.md) (where INOUT was first introduced as a kitchen feeder)
**Memory:** `docs/memory/runtime-memory.md`.
