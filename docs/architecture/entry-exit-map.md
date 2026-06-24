# Entry & Exit Point Map (docs ↔ code)

> **What this is.** The single reconciled catalog of how the application is **invoked** (entry points)
> and every **external effect** it produces (exit points), each tied to its code location and the doc
> that owns it, with a drift verdict. Living structural doc — sibling to
> [`service-boundary-map.md`](service-boundary-map.md) (per-service ins/outs) and
> [`signal-flow.md`](signal-flow.md) (the candle→order flow).
>
> Created: 2026-06-06 · Updated: 2026-06-06
>
> **See also:** [`../knowledge-map.md`](../knowledge-map.md) · [`../reference/cli-matrix.md`](../reference/cli-matrix.md) · [`../reference/control-plane.md`](../reference/control-plane.md) · [`../reference/agent-reference.md`](../reference/agent-reference.md)

**Verdict vocab:** `MATCH` (doc ≈ code) · `DRIFT-DOC` (code present, doc partial/stale) · `UNDOCUMENTED`
(code present, no doc) · `BY-DESIGN` (intentionally not a public surface) · `NO-CALLER` (entry exists but
nothing invokes it today).

## Entry points — how control/data enters

CLAUDE.md §3.3 names the **three external-input surfaces**: CLI script · control-plane command · agent
tool. The runtime harnesses (backtest / live) are programmatic entries; candle fetchers seed data.

| Entry | Code (`path:line · Symbol`) | Artifact / invocation | Doc | Verdict |
|---|---|---|---|---|
| **CLI scripts** (~48) | `scripts/**/*.py` (`__main__`/argparse) | `python scripts/<cat>/<x>.py …` | [`cli-matrix.md`](../reference/cli-matrix.md) (registered cmds) | MATCH — 3 dev scripts (`manual_backtest.py`, `backtest_debug_harness.py`, `maintenance/fix_bom.py`) unregistered **BY-DESIGN** |
| **Control-plane commands** (45) | `src/control_plane/registry.py:197 · core_command_specs` | `localhost:8787` UI / `POST /commands/{id}/runs` | [`control-plane.md`](../reference/control-plane.md) | MATCH |
| **Control-plane HTTP routes** (~40) | `src/control_plane/server.py:1649 · do_GET`, `src/control_plane/server.py:2003 · do_POST` | GET/POST `/runs`,`/commands`,`/api/*`,`/catalog`,… | [`control-plane.md`](../reference/control-plane.md) (full route table) | was DRIFT-DOC → now MATCH (route table added) |
| **Agent tools** (25 / 17 intents) | `src/agent/cli.py:49 · main` (REPL) | `python -m src.agent.cli` | [`agent-reference.md`](../reference/agent-reference.md) | MATCH |
| **Backtest replay** | `src/runtime/backtest_v2.py:1528 · run` (→ `src/core/engine_runner.py:576 · run`) | CSV in `data/` → metrics; cmd `backtest.v2` | [`signal-flow.md`](signal-flow.md) §1 | MATCH (exercised path) |
| **Live tick** | `src/runtime/live_engine_hook.py:523 · process` | one candle → engines → planner → Ultron → order | [`live-execution.md`](../topics/live-execution.md) | **NO-CALLER** — no production loop invokes it today (F-010 live unverified; F-013) |
| **Candle / data ingestion** | `src/inout/` fetchers; `src/data_ingestion/historical_fetcher.py` | OHLCV → CSV (`data/`) | [`signal-flow.md`](signal-flow.md) §1 | DRIFT-DOC — fetcher/feed details thin |
| **TradingView webhook** | — (not implemented) | — | plan-only | BY-DESIGN (no code) |

## Exit points — external effects the app produces

| Exit | Writer (`path:line · Symbol`) | Artifact path | Doc | Verdict |
|---|---|---|---|---|
| **Broker order** | `src/live/mt5_bridge.py:150 · send_order`, `src/live/mt5_bridge.py:227 · close_position` | MetaTrader 5 (broker; dry-run-gated) | [`live-execution.md`](../topics/live-execution.md) | MATCH |
| **Telegram alert** | `src/live/telegram_bridge.py:102 · send_signal_alert`, `:131 · send_kill_switch`, `:150 · send_daily_summary` | Telegram Bot API | [`live-execution.md`](../topics/live-execution.md) | DRIFT-DOC — method list now noted |
| **Decision audit (spine)** | `src/core/collector.py:73 · collect` | `logs/collector.jsonl` | [`schemas.md`](../reference/schemas.md) §9 | MATCH |
| **Trade journal** | `src/journal/trade_logger.py` (`TradeLogger.log`) | `logs/trade_journal.jsonl` | [`schemas.md`](../reference/schemas.md) §9 | was DRIFT → catalogued |
| **Integrity events** | `src/utils/integrity_events.py:50 · emit_integrity_event` | `logs/integrity_events.jsonl` | [`schemas.md`](../reference/schemas.md) §9 | was UNDOCUMENTED → catalogued |
| **Canonical event envelope** | `src/events/event_fabric.py:119 · make_event_envelope` | per-channel JSONL (telemetry/audit) | [`event-fabric.md`](../topics/event-fabric.md), [`event-taxonomy.md`](event-taxonomy.md) | MATCH |
| **CRT sweep trace** | `src/utils/sweep_trace_logger.py` (`log_sweep_decision`) | `logs/sweep_lifecycle.jsonl`, `logs/execution/runs/{run}/sweep_trace.jsonl` | [`schemas.md`](../reference/schemas.md) §9 | was UNDOCUMENTED → catalogued |
| **Backtest outputs** | `src/runtime/backtest_v2.py:1434 · _write_trades`, `:1428 · _write_summary`, `:1444 · _write_events` | `results/…/{instrument}_{trades.csv,summary.json,events.jsonl}` | [`schemas.md`](../reference/schemas.md) §9 | was DRIFT → catalogued |
| **Model artifacts** | `src/core/model_registry.py` (`register`/`_save_atomic`, GOV-3) | `models/{registry.json,gaussian_*.json,zone_registry.json,rr_model*}` | [`governance.md`](../reference/governance.md), [`training-calibration.md`](../topics/training-calibration.md) | DRIFT-DOC — atomic/active.txt details thin |
| **Config promotion** | `src/governance/promotion_manager.py:499 · _write_to_registry`, `:723 · _log_event` | `configs/production/{version}.json`, `configs/promotion_log.jsonl`, `ACTIVE_VERSION` | [`governance.md`](../reference/governance.md) | MATCH |
| **HTTP responses** | `src/control_plane/server.py:1649 · do_GET` / `:2003 · do_POST` | JSON to `localhost:8787` clients | [`control-plane.md`](../reference/control-plane.md) | MATCH |
| **Generated docs** | `scripts/analysis/gen_code_map.py`, `scripts/analysis/gen_citation_map.py` | `graph.dot`, `docs/architecture/*.generated.md` | [`code-map.md`](code-map.md), `CLAUDE.md §6.3` | MATCH (tooling output) |

## Drift summary (post-reconciliation)

- **Closed this pass:** control-plane HTTP route table (~40 routes) added to `control-plane.md`; the
  JSONL exits `trade_journal.jsonl`, `integrity_events.jsonl`, `sweep_lifecycle.jsonl`, and backtest
  `*_events.jsonl`/`_summary.json`/`_trades.csv` added to `schemas.md §9`; Telegram method list noted.
- **Registry command drift (registry vs code/config — `cli-matrix.md` faithfully reflects the registry):**
  `live.inout_runner` invokes `-m inout.runner` but `src/inout/runner.py` is **archived/removed** (broken
  command); `governance.orchestrator`/`replay.unified`/`backtest.bitnet` default `--config` to
  `v2_multi_2026_04.json` are **correct on `patch`** — active = `v2_multi_2026_04` (F-016, which supersedes the
  earlier F-007 "v4 active" reading; v4 loads only on the post-TP3 line). The registry anchor is
  `src/control_plane/registry.py:197 · core_command_specs`.
- **Still thin (acceptable):** model-registry atomic-write/`active.txt` internals; historical-fetcher feed
  config — covered at role level, deep detail lives in code.
- **The load-bearing caveat:** the **live entry (`live_engine_hook.py:523 · process`) has no production
  caller loop** — the exercised entry is `backtest_v2`. So most *exit* points on the live arm (MT5,
  Telegram, live trade journal) are reachable in code but **not driven live today** (findings F-010, F-013).
  Backtest exits (CSV/JSONL/summary) and governance exits (promotion log, configs) **are** driven.

## Fits in architecture
This map is the I/O complement to [`signal-flow.md`](signal-flow.md) (the *path* between entry and exit)
and [`service-boundary-map.md`](service-boundary-map.md) (per-service ins/outs). For "what changed when"
use [`../timeline.md`](../timeline.md); for "what's already known" use [`../current-findings.md`](../current-findings.md).
