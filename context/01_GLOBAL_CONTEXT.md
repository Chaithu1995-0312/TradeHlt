# 01 · Global Context

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/context/build_context.py` (the `Compile` trigger).
>
> A *derived view*, not a source of truth (MULTI_LLM_PROTOCOL.md §2: Shared Context is never authoritative on conflict). Edit the source, then re-Compile.
>
> **Sources:** docs/architecture/goal.md, CLAUDE.md


## Goal (plain language)

## 1. The goal in one paragraph

Tradelatest reads M15 price candles, scores each candle through four independent engines,
combines those scores into one decision, plans the trade (entry / stop / target), and lets
a risk gate approve or reject it. Nothing reaches production without passing governance
(validation, hashing, an audit trail). On top of that, the system is being migrated toward
an **event-driven, replay-governed, explainable, advisory-AI architecture** so that a
future LLM can load *one service at a time* instead of the whole codebase.

**Profit is not the primary objective.** The priorities, in order, are:

> **replay correctness > explainability > telemetry continuity > advisory-AI > (structure validity ≠ execution validity)**

In plain words: the system must reproduce the same results from the same inputs, be
explainable, never lose its measurement history, treat the LLM as advice (never a trigger),
and never confuse "the pattern is valid" with "the trade is safe to take."

### 1.1 Canonical economic targets (machine-readable — the Goal Layer)

The priority ordering above is the *governance* objective. The **economic** objective — what
the system is trying to achieve in business terms — lives as a machine-readable `goal` section
in the active production config (`configs/production/<ACTIVE_VERSION>.json`), id **G001**. It is
the economic-objective dimension that sits **alongside, never above**, the invariant ordering:
a config that hits every business target but breaks replay correctness is still rejected.

Current G001 targets (editable in the config — *not* hardcoded): 20–40 trades/month (max 80),
avg RR ≥ 2.0, win rate ≥ 0.35, max drawdown ≤ 10%, risk/trade 0.5%, expectancy ≥ 0.20R, on
M15 execution / H1 structure, reaction-only + human-execution.

Authority is **advisory-first**: every backtest emits a `goal_report` (measure-only telemetry
comparing measured metrics to G001 — see `BacktestMetrics.distribution["goal_report"]`), and a
dormant `goal.enforce` flag (default `false`) can later turn goal failure into a hard promotion
gate. It is dormant on purpose: under realistic exits the spine currently produces ~0.8
trades/month with negative expectancy (Program 1 closed, F-019→F-027), so the Goal Layer's job
today is to *quantify the gap to G001*, not to block. Full topic:
[`docs/topics/goal-layer.md`](../topics/goal-layer.md). Schema: `src/config_layer/goal_schema.py`.

**Interpreters are measured against this goal, never asserted.** Any future interpreter (P&F,
Wyckoff, Market Profile, Order Flow) must satisfy the frozen Interpreter Contract
(`src/interpreters/contract.py`) and is measured by bridging to a research `Hypothesis`
(`InterpreterHypothesis`) through the existing `forward_walk` + `QualificationGate` — so "does it
help G001?" is answered by Δ vs baseline, not by how smart it sounds. See
[`docs/topics/interpreter-contract.md`](../topics/interpreter-contract.md).

## What the system is

## 1. Project Summary

**Tradelatest** is a Python >=3.10 quantitative trading system that ingests M15 OHLCV candles, scores each bar through four independent engines (CRT, Gaussian, Zone Gate, RR), fuses the scores under a weighted-completeness gate, plans entry/SL/TP via `ExecutionPlannerV1_2`, and approves the final position through `UltronRiskGate`. Governance sits on top: no config reaches production without an approved `ValidationReport` from `ConfigValidator.validate()`, SHA-256 hashing, and an append-only `promotion_log.jsonl` audit trail. An AI automation agent (REPL, BitNet 3B, deterministic `PLAN_REGISTRY`), an expansion engine for bounded parameter search, and a stdlib HTTP control plane complete the system. Everything is file-backed — **no database, no message broker, no cloud deps**.

## Operating doctrines (full text in CLAUDE.md — read there, do not re-derive)

- §4.0 ORIENT_RUNTIME + Runtime Truth Precedence (branch-scoped, file-driven)
- §6.1 Intelligence Compounding (zero intelligence loss; goal-first ROI)
- §6.2 Repository Truth Maintenance (zero silent truth divergence)
- §6.5 Config-First + Authority Ladder (evidence > doctrine; authority is earned)
- §12 Trigger Vocabulary · §13 Multi-LLM Layer
