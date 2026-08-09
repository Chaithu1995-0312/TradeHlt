# Chapter 00 — Quick Start: One Candle's Journey

**Part I — Foundations**
Status of this chapter: Written (Grok review pass, 2026-08-07)

## Why this chapter exists

The rest of this book is deliberately careful about *how* knowledge is classified, which record
system owns what, and what remains unfixed. That meta-layer is load-bearing for contributors who
will edit the repo — but it can overwhelm a reader who only needs to understand **what the trading
system does**. This chapter short-circuits the meta-layers and gives the core mechanics in one pass.

## What problem it solves

"I just need to understand the spine" without reading Chapters 3, 17, and 18 first.

## What you need to already know

Nothing. Jump back to [Chapter 1](01-why-tradelatest-exists.md) when you want the *why*, or
[Chapter 2](02-invariants-and-happy-flow.md) for the full invariant set.

## The idea

### The system in one sentence

Tradelatest takes **M15 OHLCV candles**, scores each bar through **four independent engines**
(CRT, Gaussian, Zone Gate, RR), **fuses** those scores, **decides** accept/reject on semantic
grounds, plans **entry geometry**, and finally allows or blocks the order through a **capital risk
gate**. Everything is file-backed: no database, no message broker, no cloud dependency.

### The happy path (one candle)

| Step | What happens | Where it lives |
|---|---|---|
| 1 | Load candle (CSV / MT5 / live feed) | `src/inout/*_candle_fetcher.py`, loaders in runtime |
| 2 | Build a **39-dim** feature vector (no lookahead) | `src/features/feature_pipeline.py` |
| 3 | CRT state machine advances (RANGE→…→EXECUTION) | `src/config_layer/crt_engine_v2.py` |
| 4 | Four engines score the bar independently | `src/engines/*` via `EngineRunner` |
| 5 | Fusion combines scores under a completeness gate | `src/core/fusion_engine.py` |
| 6 | Decision Engine: semantic approval only | `src/core/decision_engine.py` |
| 7 | Execution Planner: intent + entry; CRT owns SL/TP levels | `execution_planner.py` + `compute_crt_levels` |
| 8 | Ultron Risk Gate: final capital / RR / exposure check | `src/core/ultron_risk_gate.py` |
| 9 | Live path: `HookedLiveEngine.process` on each tick | `src/runtime/live_engine_hook.py` |

Backtests stream candle-by-candle through the same spine (`src/runtime/backtest_v2.py`). Live always
runs the fusion gate; research/backtest gate mode is config-driven (`backtest.engine_gate_enabled`).

### Priority order (not "profit first")

The system's declared priorities are, in order: **replay correctness → explainability → telemetry →
AI as advisory only → profit**. Profit is a consequence of a trustworthy process, not a license to
skip gates. See [Chapter 1](01-why-tradelatest-exists.md) for the full argument.

### What is actually load-bearing today

| Surface | Status (honest) |
|---|---|
| CRT state machine (mechanism) | **CLOSED** for OHLCV → `TRADE_OPENED` boundary |
| Feature code surface (39-dim) | **CLOSED** for formula/PIT/write-site hygiene — not economic proof |
| Gaussian engine | **AUDITED** — live score collapses near-constant ~0.8825 (F-060) |
| Zone Gate | **AUDITED** — geometric HARD gate; non-pivotal on fusion decisions (F-036) |
| RR / rr_fusion | **AUDITED** — base RR flows; rr_fusion **disabled** (F-038/F-044) |
| BitNet / TradeNet | Built; **inert or unwired** on the active production config |
| Research Programs 1–8 | **CLOSED nulls** under a fixed expectancy bar — discipline working |
| Active production config | `configs/production/ACTIVE_VERSION` → currently `v2_multi_2026_04` on this branch |

### How config becomes production

1. Tunables live in `configs/production/*.json` — no magic numbers in hot-path Python.
2. `ConfigValidator.validate()` runs hard + soft quality gates → `ValidationReport`.
3. Only `decision == "APPROVE"` may promote; SHA-256 hash + append-only `promotion_log.jsonl`.
4. Rollback = restore archived config + update `ACTIVE_VERSION`.

Details: [Chapter 16](16-config-first-and-promotion.md).

### How to read the rest of the book

| If you want… | Read |
|---|---|
| Full *why* + invariants | Ch.01 → Ch.02 |
| Ontology, features, CRT depth | Ch.06 → Ch.08 |
| Engines, fusion, decision honesty | Ch.10 → Ch.12 |
| Geometry + risk + live path | Ch.13 → Ch.15 |
| Governance / findings / closure | Ch.16 → Ch.18 |
| **Research programs + numeric results table** | **Ch.19 → Ch.20** (Part VII; also dedicated PDF `*Research-Grok.pdf`) |
| In-repo agent + multi-LLM ops | Ch.21 → Ch.23 |
| Open defects & book gaps | [A2](A2-unresolved-questions.md) |

**Rule on conflict:** this book is a map. Code and active config win.

### Known defects you should not ignore (even on a quick read)

1. **ATR unit mismatch, live execution path only** — `compute_crt_levels`
   (`src/core/gate_intelligence.py:24`) gets fed a relative ATR by `live_engine_hook.py`, producing
   SL buffers ~1000x too small; the backtest path (`crt_engine_v2.py::build_trade`, `state.atr_abs`)
   is confirmed correct and unaffected ([Ch.13](13-execution-planner.md) has proposed remediations;
   unfixed pending owner decision).
2. **CRTConfig split-brain (F-057)** — programmatic `BacktestRunner(cfg)` without `crt_config` can
   miss production JSON overrides.
3. **Doc-drift, fixed 2026-08-07** — `docs/reference/schemas.md` and `docs/reference/testing.md`
   used to lag the code (38-dim vs 39-dim; a stale test-count header); both now corrected. This book
   still tracks code as the faster-moving source of truth.

## Classification

| Concept | Status |
|---|---|
| Candle → order spine | Production |
| This Quick Start chapter | Orientation aid — not an authority surface |

## Authoritative sources

- `docs/architecture/signal-flow.md` — the 7-step walk with failure modes.
- `docs/architecture/goal.md` — purpose, invariants, priority order.
- `configs/production/ACTIVE_VERSION` — Tier-0 runtime truth.
- `src/core/engine_runner.py` — orchestrator every decision path passes through.

## Unresolved questions

None for this chapter — open items live in [A2](A2-unresolved-questions.md).

---
**Previous:** [Table of Contents](README.md) · **Next:** [Chapter 01 — Why Tradelatest Exists](01-why-tradelatest-exists.md)
**Related:** [Chapter 02 — The Invariants and the Happy Flow](02-invariants-and-happy-flow.md)
**Memory:** `docs/memory/architecture-memory.md` before editing the spine.
