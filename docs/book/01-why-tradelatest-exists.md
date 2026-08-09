# Chapter 01 — Why Tradelatest Exists

**Part I — Foundations**
Status of this chapter: Written

## Why this chapter exists

Before any code, config, or governance rule makes sense, one question needs an answer: what is
this system actually *for*? Get that wrong and every later chapter reads as arbitrary engineering
detail. Get it right and the rest of the book — four independent scoring engines, a fusion gate, a
risk gate, a governance apparatus, a research program that mostly produces null results on
purpose — snaps into place as one coherent design.

## What problem it solves

Tradelatest reads M15 (15-minute) OHLCV candles for a handful of instruments, and for each candle
asks: is this a valid, risk-bounded trading opportunity? If yes, it plans the trade's entry, stop,
and target, and passes it through a final capital-safety check before anything is (in principle)
executed. That is the entire functional surface of the system, stated in one sentence — but *how*
it answers that question, and what it refuses to compromise on while answering it, is the real
subject of this book.

## What you need to already know

Nothing yet — this is the first chapter.

## The idea

### The one-paragraph goal

Tradelatest scores every M15 candle through four independent engines (CRT, Gaussian, Zone Gate,
RR), fuses their scores under a weighted-completeness gate, plans entry/SL/TP via an execution
planner, and approves the final position through a risk gate. Governance sits on top of all of
this: no configuration reaches production without passing a validator and leaving an append-only
audit trail. Everything is file-backed — there is no database, no message broker, no cloud
dependency. This same one-paragraph summary appears in `CLAUDE.md` §1 because it is the fixed point
the rest of the repository orbits.

### Profit is not the primary objective — read that literally

The single most important, least obvious fact about this repository: **profit is explicitly not
the top-priority goal.** The declared priority order, from `docs/architecture/goal.md`, is:

1. **Replay correctness** — the same inputs must always produce the same outputs.
2. **Explainability** — a human (or an LLM) must be able to say *why* a decision happened.
3. **Telemetry continuity** — historical data must remain interpretable as the system evolves.
4. **Advisory-AI** — language models assist and explain; they never trigger trades unsupervised.
5. Only then: economic performance, and even that comes with a caveat — *structure validity is not
   the same thing as execution validity.* A candle can be a textbook-valid CRT structure and still
   be a bad trade once realistic costs and slippage are applied.

This ordering explains a huge amount of what looks unusual elsewhere in the codebase: a research
program (Part VII) that closes hypothesis after hypothesis as *null* and treats that as a
successful outcome; a governance layer (Part VI) that will block a config from production over an
un-auditable change even if backtests look good; and a decision spine that fails closed rather than
guessing whenever something is ambiguous. The system is optimized to be **trustworthy first**,
profitable second — because a system you cannot trust cannot be safely made profitable, but a
system that lies convincingly about being profitable is actively dangerous.

### The economic target, when it does apply

There is still a real, machine-readable economic objective — it's just deliberately subordinate and
currently *advisory only*. It lives as the "Goal Layer" (id `G001`) inside the production config
and states concrete targets: 20–40 trades/month (max 80), average reward:risk ≥ 2.0, win rate ≥
0.35, max drawdown ≤ 10%, risk per trade 0.5%, expectancy ≥ 0.20R, M15 execution informed by H1
structure, reaction-only entries with human execution in the loop. Every backtest computes a
`goal_report` against these targets, but nothing currently *enforces* them — there is a `goal.enforce`
flag in the schema, and it stays off by design, because the system's honestly-measured current
performance (see the Research Programs in Part VII) does not yet clear these targets. Turning that
flag on prematurely would be exactly the kind of dishonesty the priority order above exists to
prevent.

### Pattern interpreters are measured, never asserted

One more design choice worth internalizing early: the system supports "interpreters" — modules that
claim to recognize classical chart patterns (Point & Figure, Wyckoff, Market Profile, Order Flow).
None of these are treated as intelligent by assumption. Each must satisfy an explicit Interpreter
Contract and is *measured* against the Goal Layer via a forward-walk + qualification gate before it
earns any influence — see [Chapter 9](09-interpreters-pattern-contract.md). This is the same
epistemic discipline as the priority order above, applied at the level of an individual idea rather
than the whole system.

## Classification

| Concept | Status |
|---|---|
| The one-paragraph goal (4 engines → fusion → decision → execution → risk gate) | Production |
| Goal Layer / `G001` economic targets | Production artifact, **advisory-only** (measure, don't gate) |
| `goal.enforce` hard-gating | Built, **dormant by design** |
| Interpreter Contract-qualified pattern interpreters | Research |

## Authoritative sources

- `docs/architecture/goal.md` §1, §1.1 — the north-star statement and the Goal Layer targets, in full.
- `src/config_layer/goal_schema.py`, `src/config_layer/goal_validator.py` — the Goal Layer's code.
- `docs/topics/goal-layer.md` — the concept-level topic doc (code ↔ tests ↔ entry points).
- `CLAUDE.md` §1 — the same one-paragraph summary, kept in sync by convention.

## Unresolved questions

None for this chapter — `goal.md` is a well-evidenced, internally consistent primary source.

---
**Previous:** [Chapter 00 — Quick Start](00-quick-start.md) · **Next:** [Chapter 02 — The Invariants and the Happy Flow](02-invariants-and-happy-flow.md)
**Related:** [Chapter 19 — The Research Programs](19-research-programs.md) (what "measured, never asserted" looks like in practice) · [Chapter 9 — Interpreters and the Pattern Contract](09-interpreters-pattern-contract.md)
**Memory:** none — this chapter summarizes a single primary doc rather than reverse-engineered code.
