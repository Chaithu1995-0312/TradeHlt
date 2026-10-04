# Chapter 02 — The Invariants and the Happy Flow

**Part I — Foundations**
Status of this chapter: Written

## Why this chapter exists

Chapter 1 established *why* the system exists and what it refuses to compromise on in principle.
This chapter makes that concrete: the exact shape of a candle's journey through the system (the
"happy flow"), and the seven hard rules ("invariants") that every later chapter's design decisions
trace back to. Every subsequent Part of this book is, in effect, a zoomed-in view of one segment of
the diagram below.

## What problem it solves

Without a fixed reference diagram, it's easy to lose track of what's on the synchronous decision
path versus what merely *feeds* it asynchronously. This chapter draws that line once, clearly, so
later chapters don't have to re-justify it.

## What you need to already know

[Chapter 1](01-why-tradelatest-exists.md) — the priority order (replay correctness first, profit
last) is the reason these particular seven invariants were chosen.

## The idea

### The happy flow

One M15 candle closes. From there:

```
Candle → [4 engines score independently] → Fusion (all-four-or-reject)
       → Decision (threshold → ACCEPT/REJECT) → Execution Planner (entry/SL/TP/RR/TTL)
       → Risk Gate (Ultron) → order out, or a logged rejection at any stage
```

In code, this is the **decision spine**:

```
EngineRunner → FusionEngine.evaluate → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate.evaluate
```

Three of the four engines score the candle as a single number each. The fourth, CRT, is different
in kind: internally it's not a number generator, it's a **state machine** with nine legal states,
walking a lifecycle:

```
RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION
```

plus two branches: `RANGE ↔ SHADOW_PENDING → SWEEP` (an early-detection branch) and
`EXPANSION → EXPIRED → RANGE` (a TTL-based soft-archive branch when a setup goes stale before
retesting). CRT's *score* is what feeds Fusion; CRT's *state* is what makes it "the spine" — Part
III is dedicated to it.

### The seven invariants

These are the rules that must never break, regardless of how much throughput or profit a change
promises (`docs/architecture/goal.md` §3):

1. **Deterministic replay.** Same inputs → same outputs, always. This is invariant #1 for a reason:
   nothing else in the book — governance, research, agent advice — is trustworthy if replay isn't.
2. **All four engines or nothing.** `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` in
   `EngineRunner`. If any engine is missing, the candle is rejected outright — there is no silent
   partial fusion.
3. **The LLM is advice, never a trigger.** Any LLM-backed gate returns a neutral score after
   repeated failures rather than blocking or hallucinating a decision. A code path that cannot
   tolerate that neutral fallback is considered broken by design.
4. **No config reaches production without governance.** Every promotion needs an approved
   `ValidationReport`, a SHA-256 config hash, and an append-only `promotion_log.jsonl` entry — see
   [Chapter 16](16-config-first-and-promotion.md).
5. **Telemetry is additive only.** Fields get renamed forward, never silently removed — old JSONL
   records must stay interpretable.
6. **CRT state moves only along legal transitions.** The nine-state graph above is the *entire*
   legal transition set — there is no free-form state graph.
7. **No database, no broker, no cloud dependency.** Everything is file-backed. A request to "add a
   table" or "use the ORM" is a convention break, not a valid design option.

Every change is additionally scored against five governance questions: is it still deterministic?
Still comparable across runs? Auditable later? Can an LLM reason about it? Is execution authority
still isolated? A change that fails any of these needs explicit sign-off, not silent acceptance.

### The deviation policy

Not every deviation from "the ideal" is forbidden — the system distinguishes three tiers:
- ✅ **Acceptable** — improves throughput, speed, or quality while keeping all seven invariants intact.
- ⚠️ **Needs a flag** — trades off an invariant for throughput (must be explicit, reversible, and visible).
- ❌ **Not acceptable** — breaks determinism, governance, the LLM-as-advice rule, telemetry
  continuity, or partial-fusion protection, *regardless* of how much throughput or speed it buys.

### The async "kitchen feeders"

Four subsystems sit beside the synchronous spine, feeding it without ever calling into it directly
— they communicate only through files, never direct function calls:

- **Governance** — `AutoTuner → ConfigValidator → PromotionManager` writes new production configs
  that the spine reads at its next load. See Part VI.
- **Training** — raw trade JSONL → `DatasetValidator → Trainer → ModelRegistry` writes model
  artifacts that engines (mainly Gaussian and BitNet's zone gate) read. See [Chapter 10](10-four-scoring-engines.md).
- **AI Agent** — either drives the spine through a backtest loop (Pipeline mode) or taps it
  read-only at the Fusion/Decision step (Copilot mode) — it can never mutate a decision in flight.
  See [Chapter 21](21-ai-automation-agent.md).
- **INOUT** — a parallel live-execution strategy rail that joins the spine only at the very last
  step, `UltronRiskGate.evaluate()` — and is currently archived (`archive/inout_legacy/`). See
  [Chapter 15](15-live-execution-and-inout.md).

The full seven-step walk (data ingest → feature pipeline → scoring engines → fusion & decision →
execution planner → risk gate → execution), with per-step module/entry-point/failure-mode detail
and a Mermaid swim-lane diagram, lives in `docs/architecture/signal-flow.md` — this chapter's
diagram is the compressed version; that file is the canonical one.

## Classification

| Concept | Status |
|---|---|
| The 7-step synchronous spine | Production |
| The 9-state CRT lifecycle | Production, **CLOSED** (see [Ch.08](08-crt-state-machine.md)) |
| The 7 invariants + 5 governance questions | Doctrine — enforced by review discipline, not (all) by code |
| Governance / Training / Agent / INOUT feeders | Production (Governance, Training, Agent) / **Archived** (INOUT) |

## Authoritative sources

- `docs/architecture/goal.md` §2–§4 — the happy flow, invariants, and deviation policy verbatim.
- `docs/architecture/signal-flow.md` — the authoritative 7-step walk with module/entry/failure-mode
  detail per step and the Mermaid swim-lane diagram (§4).
- `src/core/engine_runner.py` — `EXPECTED_ENGINES` and the completeness gate.
- `src/config_layer/crt_engine_v2.py`, `docs/architecture/event-taxonomy.md` §3 — the CRT transition
  graph, also re-exported at `state_topology.py:109`.

## Unresolved questions

None — this chapter compresses two internally consistent, well-cross-referenced primary sources.

---
**Previous:** [Chapter 01 — Why Tradelatest Exists](01-why-tradelatest-exists.md) · **Next:** [Chapter 03 — How This Book Fits the Repository's Knowledge](03-how-this-book-fits.md)
**Related:** [Chapter 08 — The CRT State Machine](08-crt-state-machine.md) · [Chapter 16 — Config-First Doctrine and the Promotion Path](16-config-first-and-promotion.md)
**Memory:** `docs/memory/architecture-memory.md` (deep companion, load only when a full cross-package map is needed).
