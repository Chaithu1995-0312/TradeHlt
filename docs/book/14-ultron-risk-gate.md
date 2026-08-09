# Chapter 14 — Ultron Risk Gate: the Final Capital Check

**Part V — Execution**
Status of this chapter: Written

## Why this chapter exists

Everything before this point in the spine — ontology, features, four engines, fusion, a semantic
decision, a planned entry — can be exactly right and the trade can still be wrong for the
*portfolio*. This chapter covers the last, deterministic checkpoint before an order would leave the
system, and the one module every other live-trading path in the repository is required to pass
through.

## What problem it solves

Separates "is this a valid opportunity" (Decision Engine, semantic) from "can we safely afford this
trade right now" (Ultron, capital/portfolio). Chapter 12 already explained why that separation
exists structurally (F-048); this chapter covers the module that resulted from it.

## What you need to already know

[Chapter 12](12-decision-engine.md) — specifically, why reward:risk economics live here and not in
the Decision Engine.

## The idea

### What it checks

`src/core/ultron_risk_gate.py`'s `UltronRiskGate.evaluate()` is the final capital-protection layer:
position sizing, drawdown caps, exposure limits, daily-trade limits, and correlation thresholds
across open positions. It is deterministic and hard-rejects on any breach — its own documentation is
explicit that **no fallback path is permitted** here. Where the LLM gate in Fusion ([Chapter 11](11-fusion.md))
is allowed to fail open to a neutral score, Ultron is not allowed to fail open at all; a breach is a
breach.

### Where reward:risk economics actually live

Per [Chapter 12](12-decision-engine.md)'s account of F-048: real, cost-taxed reward:risk economics
(`min_rr_ratio`, computed after the Execution Planner has determined actual SL/TP geometry) are
owned solely here, not in the Decision Engine. This makes Ultron the single place in the spine where
"is this trade good enough, economically, net of costs" is actually answered.

### The one module INOUT touches

Of the four async "kitchen feeders" from [Chapter 2](02-invariants-and-happy-flow.md), INOUT (the
parallel live-execution strategy rail, currently archived — see [Chapter 15](15-live-execution-and-inout.md))
is unusual: it doesn't feed the spine asynchronously the way Governance or Training do. It joins the
*synchronous* spine directly, but only at this one point — `UltronRiskGate.evaluate()` — meaning
whatever INOUT proposes still has to clear the exact same capital-safety check as the main CRT
spine. It is explicitly not one of the four `EXPECTED_ENGINES`; it's a second decision source
feeding the same final gate.

## Classification

| Concept | Status |
|---|---|
| `UltronRiskGate.evaluate()` | Production — the terminal approve/reject authority |
| Reward:risk ownership (`min_rr_ratio`, cost-taxed) | Production, here since F-048 |
| Shared join-point with INOUT | Production mechanism; INOUT itself is archived (see Ch.15) |

## Authoritative sources

- `src/core/ultron_risk_gate.py` — `UltronRiskGate.evaluate()`.
- `src/core/_wrapper.py` — the wrapper referenced by the topic doc's entry-point trace.
- `docs/topics/ultron-risk-gate.md` — the always-synced topic doc.
- `docs/architecture/signal-flow.md` §2.4 — the INOUT join-point documentation.
- `docs/current-findings.md` F-048 — reward:risk ownership.

## Unresolved questions

None for this chapter — Ultron's own scope is unusually crisply documented (a hard-reject-only
module by explicit design), and its relationship to F-048 and to INOUT is already covered precisely
by other chapters this one links to.

---
**Previous:** [Chapter 13 — The Execution Planner](13-execution-planner.md) · **Next:** [Chapter 15 — Live Execution and INOUT](15-live-execution-and-inout.md)
**Related:** [Chapter 12 — The Decision Engine](12-decision-engine.md)
**Memory:** `docs/memory/architecture-memory.md`.
