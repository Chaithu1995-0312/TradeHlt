# Chapter 08 — The CRT State Machine: the Spine

**Part III — Market Semantics**
Status of this chapter: Written

## Why this chapter exists

CRT (Candle Range Theory) is described everywhere in this repository as "the spine" — not because
it's the most powerful of the four scoring engines, but because unlike the other three, it isn't a
single number-producing function. It's a stateful lifecycle that gives a *sequence* of candles
structural meaning, and that structure is what the rest of Part IV's decision-making ultimately
reasons about.

## What problem it solves

A single candle's numeric features (Chapter 7) can't tell you "this is currently mid-setup, three
candles into a retest of a liquidity sweep." Only a state machine that persists across candles can.
CRT is that state machine.

## What you need to already know

[Chapter 6](06-market-ontology.md) and [Chapter 7](07-feature-pipeline.md) — CRT's frozen ontology
sections and its input vector are both prerequisites already covered.

## The idea

### Two files named "CRT engine" — know which one you're reading

There are two distinct modules worth telling apart precisely, because confusing them is an easy
mistake:

- **`src/config_layer/crt_engine_v2.py`** — the full deterministic state machine. Internally
  composed as `RangeDetector → StateMachine → (internal risk/execution helpers) → ...`, and this is
  the module that binds the ontology's frozen sections at import time (see [Chapter 6](06-market-ontology.md)).
- **`src/engines/crt_engine.py`** — a thinner wrapper that `EngineRunner` (Part IV) actually calls
  as one of the four scoring engines. Its `compute()` delegates to `engines/scoring_engine.py`'s
  `compute_scores`, and what it returns to Fusion is a single number — CRT's *score*, not its full
  state.

So: the **state** lives in `crt_engine_v2.py`; the **score** that Fusion sees comes from the thinner
`engines/crt_engine.py` wrapper. Both matter, but they answer different questions — "where is this
setup in its lifecycle" versus "how good does this setup look right now."

### The nine-state lifecycle

Already introduced in [Chapter 2](02-invariants-and-happy-flow.md):

```
RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION
```

plus two branches:
- `RANGE ↔ SHADOW_PENDING → SWEEP` — an early-detection branch that lets the engine track a
  candidate setup before it's confirmed.
- `EXPANSION → EXPIRED → RANGE` — a TTL-based soft-archive: a setup that goes stale before reaching
  RETEST ages out rather than lingering indefinitely.

This is the **entire** legal transition graph (invariant #6 from Chapter 2) — there is no path
through the state machine that isn't one of these edges. The authoritative transition table lives at
`state_identity.py:69` (extracted from `crt_engine_v2` to break an import cycle, re-exported for
compatibility) with an immutable view at `state_topology.py:109`, and is narrated in
`docs/architecture/event-taxonomy.md` §3.

### CRT is a closed research surface — what that does and doesn't mean

CRT carries the repository's only **CLOSED** status in the Closure & Authority Index (see
[Chapter 17](17-truth-maintenance.md) for what that index means in general). The declared boundary
is narrow and precise: *OHLCV → CRT `TRADE_OPENED`, and only that.* It does not mean "CRT is proven
profitable" — the Research Programs in Part VII repeatedly test CRT-adjacent hypotheses (completed
sweep→displacement→retest sequences, weekly-calendar sweep variants) and find no economic edge.
CLOSED here means: the *mechanism itself* — candle in, state transitions, `TRADE_OPENED` event out —
has been audited end-to-end and is considered a stable, trustworthy piece of machinery. Whether
what it detects is *worth trading* is a separate, open question, owned by Part VII.

## Classification

| Concept | Status |
|---|---|
| The 9-state CRT lifecycle + transition graph | Production, **CLOSED** (mechanism boundary only) |
| `crt_engine_v2.py` (full state machine) | Production |
| `engines/crt_engine.py` (score wrapper for `EngineRunner`) | Production |
| "Is a completed CRT structure economically tradeable" | Research — repeatedly tested, currently null (see [Ch.19](19-research-programs.md)) |

## Authoritative sources

- `src/config_layer/crt_engine_v2.py` — the full state machine.
- `src/engines/crt_engine.py`, `src/engines/scoring_engine.py` — the `EngineRunner`-facing score wrapper.
- `src/config_layer/state_identity.py:69`, `state_topology.py:109` — the authoritative transition graph.
- `docs/architecture/event-taxonomy.md` §3 — the narrated transition table.
- `docs/governance/crt_closure_report.md` — the CLOSED boundary declaration and its exact scope.
- `docs/topics/crt-spine.md` — the always-synced topic doc.

## Unresolved questions

None for the mechanism itself — CRT is the single most thoroughly audited surface in the repository.
Its *economic* status is intentionally left open here and answered properly in Part VII.

---
**Previous:** [Chapter 07 — The Feature Pipeline](07-feature-pipeline.md) · **Next:** [Chapter 09 — Interpreters and the Pattern Contract](09-interpreters-pattern-contract.md)
**Related:** [Chapter 10 — The Four Scoring Engines](10-four-scoring-engines.md) · [Chapter 17 — Truth Maintenance](17-truth-maintenance.md) · [Chapter 19 — The Research Programs](19-research-programs.md)
**Memory:** `docs/memory/engine-memory.md`.
