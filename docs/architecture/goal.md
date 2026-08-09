# goal.md — What Tradelatest Is For (North-Star + Happy Flow)

> **Read this to remember the point.** This is the plain-language goal document: what the
> system is trying to do, the one path everything flows through when things go right (the
> "happy flow"), the rules that must stay true, and what counts as an acceptable vs.
> unacceptable deviation. It is the baseline we check changes against.
>
> Companion detail lives in [`docs/architecture/signal-flow.md`](signal-flow.md) (step-by-step flow),
> [`codebase-state-map.md`](codebase-state-map.md) (module map),
> [`service-boundary-map.md`](service-boundary-map.md) (service contracts),
> [`event-taxonomy.md`](event-taxonomy.md) (events), and
> [`target-strategy-architecture.md`](target-strategy-architecture.md) (**city plan**: market semantics vs
> strategy, Strategy Lifecycle research→promotion→ledger, not-yet-built checklist).
>
> **Role of this file:** the **constitution** — *why we exist* and *what must never change*
> (priorities, happy flow, invariants). It intentionally avoids strategy-packaging detail.
> Evolution without violating this constitution is owned by `target-strategy-architecture.md`.
> This doc stays high-level on purpose.

---

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

---

## 2. The happy flow (what happens when everything goes right)

```
M15 candle in
   │
   ▼
[1] Four engines score the candle, independently:
      • CRT        — a score from the CRT setup (engines/crt_engine.py → compute_scores()).
                     NOTE: this is just one number. The CRT *state machine* that drives the
                     whole walk is the spine, not this engine — see below.
      • Gaussian   — statistical scorer
      • Zone Gate  — cluster / zone membership
      • RR         — risk-reward model

   The CRT state machine (the spine that decides when a setup exists) walks a 9-state
   lifecycle. Golden path: RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION →
   RESOLUTION. Plus two branches off it: SHADOW_PENDING (a held sweep, Phase 1) and EXPIRED
   (a stale EXPANSION timed out by the TTL guard, Phase 3b). Full legal graph: §3 #6 /
   event-taxonomy.md §3.
   │
   ▼
[2] Fusion — all four scores combined under a weighted-completeness gate.
      (All four engines must be present, or it's a hard reject — no partial fusion.)
   │
   ▼
[3] Decision — threshold applied to the fused score → ACCEPT / REJECT.
   │
   ▼
[4] Execution planner (ExecutionPlannerV1_2) — derives entry, stop-loss, take-profit,
      risk-reward and time-to-live from the accepted signal.
   │
   ▼
[5] Risk gate (UltronRiskGate) — final approve / reject on the planned position.
   │
   ▼
Order out (approved) — or a logged rejection (not approved)
```

The decision spine in code:
`EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate`.

**Three live async side-feeders** observe this spine without ever steering it in real time:
Governance (promotion/validation), Training (model refresh), and AI Agent (REPL/automation).
A fourth — INOUT (live-execution mode) — is **currently archived** (`archive/inout_legacy/ARCHIVED_2026_05_02`;
see [`docs/analysis/integration-audit.md`](../analysis/integration-audit.md)). They join the
spine off the hot path — see [`docs/architecture/signal-flow.md`](signal-flow.md).

**Governance gate (how a config reaches production):** a config is only promoted with an
approved `ValidationReport`, a SHA-256 hash, and an append-only entry in
`promotion_log.jsonl`. No approval → no promotion.

---

## 3. The invariants (what must stay true — "this is a deviation")

These are the rules the happy flow depends on. Breaking one is a real deviation:

1. **Same inputs → same outputs.** Replay is deterministic (seeded slippage, candle-time
   keys, no lookahead). Comparison ignores wall-clock time / random IDs.
2. **All four engines or nothing.** `EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}`.
   A missing engine is a hard reject, never a quiet partial fusion.
3. **The LLM is advice, never a trigger.** It can break ties; it can never approve or
   place a trade. After repeated failures it returns neutral and the system carries on.
4. **No config to production without governance.** Approved `ValidationReport` + hash +
   audit log. Always.
5. **Telemetry is additive.** New events/fields are added; old ones aren't silently
   removed (rename old→new with a note). Measurement history stays comparable.
6. **CRT state moves only along legal transitions.** The state graph is fixed (see
   [`event-taxonomy.md`](event-taxonomy.md) §3); illegal jumps are rejected.
7. **No database, no broker, no cloud dependency.** Everything is file-backed.

The migration adds five questions every change is scored against:
**(1)** still deterministic? **(2)** still comparable across runs? **(3)** auditable later?
**(4)** can an LLM reason about it? **(5)** is execution authority still isolated?

---

## 4. Deviation policy (what's OK, what's not)

- ✅ **Acceptable deviation:** a change that departs from the current shape **but improves
  throughput / speed / quality** *and* keeps all the invariants in §3 and passes the five
  questions. Allow it; just note what changed and why.
- ⚠️ **Needs a flag / your call:** a change that trades off an invariant for throughput
  (e.g., faster but less reproducible). Surface it, don't silently take it.
- ❌ **Not acceptable:** breaks determinism, skips governance, lets the LLM trigger a
  trade, removes telemetry without a replacement, or allows partial fusion — regardless of
  any speed gain.

**Monitoring:** changes are checked against §3 invariants and §2 happy flow. A deviation is
reported in plain language (what moved, which invariant it touches, throughput effect)
rather than blocked outright when it only improves the tool.

---

## 5. Where the system is heading (the migration target)

End state: **event-driven LLM-event-microservices.** Each service has documented
ins → internal flow → outs, so context can be loaded one service at a time (context
economy). Telemetry is curated into per-episode "LLM logs" so the history a future LLM
reads stays compact instead of growing forever. Sequencing (trading-arch track): **Trd-M0** map/doctrine ✅ →
**Trd-M1** telemetry normalization ✅ → **Trd-M2** event extraction ✅ → **Trd-M3** orchestration
de-coupling → **Trd-M4** dependency inversion → **Trd-M5** LLM-layer hardening. Detail in
[`docs/plans/`](../plans) and the doctrine header in
`assistant_project.md`.
