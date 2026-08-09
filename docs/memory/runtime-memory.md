# Runtime Memory (navigation)

> **Last generation:** 2026-08-07  
> **Code-first:** `src/runtime/**` is authoritative on conflict.

## Purpose

Index historical replay and live hook harnesses that exercise (or wrap) the decision spine over candles.

## Responsibilities

- Stream M15 OHLCV with integrity (L1/L2 always; L3 preflight on backtest paths).  
- Build features and drive CRT / optional EngineRunner gate.  
- Simulate capital, slippage, spread; emit trades/metrics/reports.  
- Live path: candle → spine → planner → Ultron → bridges (when called).  
- Capture baselines / unified replay for determinism work.

## Runtime role

**Execution harness** for backtest (primary exercised path) and live (code present; production loop often uncalled — see entry-exit map / F-010/F-013).

## Entry points

| Entry | Symbol / path |
|---|---|
| Backtest CLI / runner | `src/runtime/backtest_v2.py` · `main`, `BacktestRunner`, `MultiInstrumentRunner`, `CandleLoader` |
| Live hook | `src/runtime/live_engine_hook.py` · `HookedLiveEngine.process` |
| Baseline | `src/runtime/baseline_capture.py` |
| Replay harness | `src/runtime/unified_replay_harness.py` |
| Control-plane cmd | `backtest.v2` in `src/control_plane/registry.py` |
| Agent tool | `backtest.run_v2`, `live_hook.dry_run` (pipeline mode) |

## Exit points

| Exit | Artifact |
|---|---|
| Backtest reports | `results/.../{instrument}_trades.csv`, `_summary.json`, `_events.jsonl` |
| Live | MT5 / Telegram / journals (when bridges invoked) |
| Baseline manifests | under `results/baseline/` (via baseline_capture) |
| Logs | fusion/collector/trade streams depending on path |

## Important contracts

1. **No lookahead** in stream consumers — generator + integrity conjunction.  
2. **L3** `dataset_integrity` is **not** universal (F-039): many research paths are L1/L2 only.  
3. **`backtest.engine_gate_enabled`** controls whether EngineRunner fusion gate runs in backtest.  
4. Live capital path: EngineRunner → ExecutionPlanner → **UltronRiskGate** (not RegimeGovernor).  
5. Config: `backtest` section + ACTIVE production version; programmatic `BacktestRunner` without CRTConfig can hit ConfigBuilder split-brain (F-057 — see findings).

## Reading order

1. This file.  
2. `docs/architecture/signal-flow.md` §1 (spine steps).  
3. `src/runtime/backtest_v2.py` — `CandleLoader`, `BacktestRunner.run`.  
4. If live: `live_engine_hook.py` + `docs/topics/live-execution.md`.  
5. Gate/engine path: [`engine-memory.md`](engine-memory.md) + `src/core/engine_runner.py`.

## Related documents

| Doc | Role |
|---|---|
| [`../architecture/signal-flow.md`](../architecture/signal-flow.md) | Candle→order |
| [`../architecture/entry-exit-map.md`](../architecture/entry-exit-map.md) | Live NO-CALLER note |
| [`../topics/live-execution.md`](../topics/live-execution.md) | Live topic |
| [`engine-memory.md`](engine-memory.md) | Scoring engines |
| [`feature-memory.md`](feature-memory.md) | Feature build |
| [`architecture-memory.md`](architecture-memory.md) | Layers |

## Known coverage

| Scope | Status |
|---|---|
| `src/runtime/` (~10 files) | High name visibility in deep map |
| Full backtest internals | Code authority — large module |
| Live production loop | Documented as largely uncalled |
| All scripts wrapping backtest | Not listed here — `cli-matrix` / script registry |

## Last generation timestamp

2026-08-07
