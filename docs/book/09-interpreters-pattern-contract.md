# Chapter 09 — Interpreters and the Pattern Contract

**Part III — Market Semantics**
Status of this chapter: Written

## Why this chapter exists

CRT (Chapter 8) is one way of giving candle sequences structural meaning. It is not the only
pattern vocabulary a trader might reach for — Point & Figure, Wyckoff, Market Profile, Order Flow
are all classical alternatives. This chapter covers how this repository lets such ideas in *without*
letting them claim intelligence they haven't earned.

## What problem it solves

Prevents "we added a pattern detector" from silently becoming "we trust this pattern detector."
Every interpreter has to prove itself the same way, before it can influence anything.

## What you need to already know

[Chapter 1](01-why-tradelatest-exists.md)'s "measured, never asserted" principle, and
[Chapter 8](08-crt-state-machine.md) — interpreters are a parallel idea to CRT, not a replacement.

## The idea

### The Interpreter Contract (Level 4)

`src/interpreters/contract.py`, `adapter.py`, and `reference.py` define a fixed contract any
pattern-recognition module must satisfy before it's allowed to matter. A candidate pattern is
wrapped as an `InterpreterHypothesis` and run through the same `forward_walk` evaluation plus
`QualificationGate` machinery used elsewhere in the research pipeline — the same yardstick, reused,
not a bespoke one invented per interpreter. This is deliberate: it means "does this pattern help"
is answered the same way every time, and a pattern can't get a friendlier evaluation just because
its author believed in it more.

### The one interpreter that's actually been run through it

Point & Figure (P&F, implementation id `PNF-v1`, double-top/double-bottom patterns) is the first
interpreter to complete this process on real data. The result was a clean **REJECT**: shadow-measured
on crypto majors, it carried no standalone edge, and scored worse than random controls (a negative
delta-expectancy of about −0.039). This is reported here not as a failure of the interpreter
framework but as evidence the framework *works as intended* — it correctly declined to grant
authority to an idea that didn't earn it, exactly the discipline [Chapter 1](01-why-tradelatest-exists.md)
described. Per the repository's own research discipline, this closes P&F under the current ontology;
reopening it needs a genuinely new ontology, not another sweep of the same one.

### What this means for other interpreters

Nothing else currently in `src/interpreters/` has cleared the contract — until one does, the honest
status of the whole subsystem is: infrastructure exists, one candidate has been tested and rejected,
the rest are unevaluated. None of them influence the live decision spine.

## Classification

| Concept | Status |
|---|---|
| Interpreter Contract (`contract.py`/`adapter.py`/`reference.py`) | Production infrastructure |
| P&F / `PNF-v1` | Research — **tested, REJECTED** (F-028) |
| Wyckoff, Market Profile, Order Flow interpreters | Unknown / not yet run through the contract |

## Authoritative sources

- `src/interpreters/contract.py`, `adapter.py`, `reference.py` — the contract itself.
- `docs/topics/interpreter-contract.md` — the always-synced topic doc, entry point, and test references.
- `docs/current-findings.md` F-028 — the P&F result, with its exact scope and confidence.
- `docs/architecture/goal.md` — the "measured against the Goal Layer, never asserted" framing this
  chapter draws its principle from.

## Unresolved questions

- Whether Wyckoff/Market Profile/Order Flow interpreters have any code beyond scaffolding, and if
  so how far along the contract pipeline they are, wasn't verified in this pass — flagged in
  [A2](A2-unresolved-questions.md).

---
**Previous:** [Chapter 08 — The CRT State Machine](08-crt-state-machine.md) · **Next:** [Chapter 10 — The Four Scoring Engines](10-four-scoring-engines.md)
**Related:** [Chapter 19 — The Research Programs](19-research-programs.md) (the same falsification discipline, at system scale)
**Memory:** `docs/memory/engine-memory.md`.
