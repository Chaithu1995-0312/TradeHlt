# Execution Quality Observatory (Phase C-op) — execution science, NOT edge validation

## Context
Decision (user, Option 2, scope-reduced): a small **execution-telemetry extension** to the
already-complete system — capture what `order_send` knows and the deal history never will. **NOT**
strategy/edge validation, **NOT** F-010, **NOT** a router. The spine is research-null (F-019…F-039);
this layer characterizes *execution risk* (slippage / latency / retcodes / fill behavior) now, on
demo, at zero capital, so when a qualified strategy eventually exists only *strategy* risk is new.

**Two independent truths (keep them separate):**
```
Financial truth → mt5_analytics   (deals, commission, swap, margin, INOUT, partials — ALREADY DONE)
Execution truth → exec_telemetry  (requested vs filled price, send→fill latency, retcode/failure)
```
**Execution-time facts disappear forever after `order_send`** — pre-send price, send/fill timestamps,
retcode, fill price, failure reason are *permanently unknowable* unless captured at execution time.
That, and only that, is what this layer adds. Commission/swap/margin/symbol are already captured per
broker (v0.3–v0.5) — **do not re-measure them here.**

**Doctrine guards (non-negotiable):**
- **OPERATIONAL-ONLY.** This harness measures latency / slippage / retcodes / fills — **never** profit,
  expectancy, win-rate, or R (those belong to the truth + insight engines). Conflating execution
  robustness with strategy robustness is the prohibited error; every output carries that header.
- **Read-model invariant (structural):** `execution telemetry → HUMAN`, **never**
  `execution telemetry → execution decisions`. No router/planner/recommender ever consumes it.
- **Demo-gated, fingerprint-pinned, lot-capped** (inherited from `trade_generator`). First *repeated
  autonomous* order-placer ⇒ hard gate stays: refuse any non-DEMO account; **no real capital; no
  concurrent multi-terminal router / trade-copier / capital allocator (Phase D+, real-money — NOT
  built).** "Can ≠ should."

## Architecture (minimal; reuse-heavy)
```
MT5 Terminal → manual_tools/trade_generator.py → order_send()
                         ├── Deal History → mt5_analytics      (financial truth — exists)
                         └── ExecutionEvent → runtime/exec_telemetry/<broker>/orders.jsonl   (M1)
                                              → exec_telemetry/report.py  (M2, read-only) → HUMAN
```
"Multi-broker" = run the pattern set **per connected demo terminal** (MT5 Python attaches to one
terminal at a time — sequential-per-terminal is the correct model, matching today's manual flow); each
`ExecutionEvent` is self-describing (carries its broker fingerprint + margin_mode), so per-broker logs
aggregate in M2. **No concurrent N-terminal copier.**

## M0 — `ExecutionEvent` schema (frozen; same discipline as DealRecord/PositionEpisode/FeatureRecord)
**New `exec_telemetry/schemas/execution_event_v1.py`** — without a schema, JSONL → ad-hoc dicts →
silent drift → broken reports (a lesson already paid for in the truth engine).
```python
@dataclass(frozen=True)
class ExecutionEvent:
    ts: str                 # ISO-8601 UTC (str, JSONL-safe — mirrors PositionEpisode.entry_time)
    broker_fingerprint: str; company: str; server: str; login: int; margin_mode: int
    symbol: str; side: str
    requested_price: float; filled_price: float; slippage_points: float
    latency_ms: float
    retcode: int; retcode_name: str
    filling_mode: str; volume: float
    schema_version: str = "1.0"
```
`margin_mode` is on the row (not just the dir) so a row is fully self-describing outside its partition.

## M1 — telemetry capture (extend the generator; additive, gates unchanged)
In `manual_tools/trade_generator.py` `_send()`, around the existing `mt5.order_send(request)`:
capture pre-send tick (`symbol_info_tick` ask/bid for the side) = requested; time `order_send`
(`time.perf_counter()`) → latency_ms; read `result.{retcode,price,volume,deal}`; slippage_points =
signed `(filled − requested)/point`; build an `ExecutionEvent` and append it to
**`runtime/exec_telemetry/<company>_<server>_mm<margin_mode>/orders.jsonl`** (gitignored; keyed by
margin_mode so MetaQuotes-Demo *hedging* ≠ *netting* never collide — the v0.4.0 lesson). Opt-in via
**`--exec-log`** (absent ⇒ byte-identical to today). DEMO/L1 + fingerprint/L2 + lot-cap unchanged;
dry-run sends + logs nothing.

## M2 — Operational report (new, read-only, testable)
**New `exec_telemetry/report.py`** — `build_exec_report(events, *, min_n=30) -> ExecReport` (frozen),
per broker key: **fill-success rate** + **retcode histogram** (DONE / REQUOTE / MARKET_CLOSED /
CLIENT_DISABLES_AT / INVALID_FILL / …) · **slippage** median/p90/worst (signed) · **latency**
median/p90/worst · **filling-mode used** + **symbol accepted**. Reuse `analytics.metrics_oracle.median`
/`percentile` (no new math). Same **sufficiency discipline** as v0.6 (`n` + SUFFICIENT/INSUFFICIENT;
below `min_n`, counts only, no distributional claim). OPERATIONAL-ONLY header. **No profit/expectancy/R.**

## Critical files
- **New** `exec_telemetry/__init__.py`, `exec_telemetry/schemas/execution_event_v1.py`,
  `exec_telemetry/report.py`, `tests/exec_telemetry/test_report.py`
- **Edit** `manual_tools/trade_generator.py` (M1 capture + `--exec-log`)
- **Edit** `.gitignore` (add `runtime/exec_telemetry/`)
- **Reuse** `analytics.metrics_oracle` (`median`/`percentile`)
- **No change** to `mt5_analytics/` kernel/schema/insight, `src/live/mt5_bridge.py`, or any spine code

## Verification
- **Unit (`tests/exec_telemetry/test_report.py`):** fixtures of `ExecutionEvent`s → assert
  slippage/latency percentiles, retcode histogram, fill-rate, sufficiency gating (n<min_n ⇒
  INSUFFICIENT), determinism. (Note: like `manual_tools`, no `tests/exec_telemetry/__init__.py` — avoid
  the sys.path-shadow gotcha.)
- **M1 live:** dry-run logs nothing; a tiny `--confirm --exec-log` run on the IC Markets demo appends
  real `ExecutionEvent`s (non-null slippage/latency/retcode). Demo-gated, lot-capped.
- **Regression:** existing **85 mt5_analytics tests stay green**; generator without `--exec-log`
  byte-identical to today.

## NOT doing
No edge/expectancy/strategy/F-010 claim (OPERATIONAL-ONLY). **No router, trade-copier, capital
allocator, execution planner, or anything strategy-aware** (Phase D+, deferred). No real-capital
execution. No kernel/insight/spine change. No re-capture of commission/swap/margin/symbol (already
owned by the truth engine + coverage). Telemetry never feeds decisions — HUMAN only.

## Later (only when a qualified strategy exists — not now)
`Qualified strategy → existing hardened execution infra → F-010 comparator (backtest vs live)`. This
observatory de-risks the execution half in advance, so eventual F-010 closure carries only *strategy*
risk, not strategy+execution risk.
