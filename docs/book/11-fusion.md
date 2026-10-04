# Chapter 11 — Fusion: Combining Independent Signals

**Part IV — Decision Making**
Status of this chapter: Written

## Why this chapter exists

Four engines each produce a number ([Chapter 10](10-four-scoring-engines.md)). Something has to
turn four numbers into one. This chapter covers that step — and the one place in the entire
synchronous spine where a language model is allowed to touch a live decision, under tightly
constrained conditions.

## What problem it solves

Explains how Fusion combines scores, why a neural-model slot exists but does nothing yet, and
exactly how narrow the LLM's involvement is — directly enforcing invariant #3 from
[Chapter 2](02-invariants-and-happy-flow.md) ("the LLM is advice, never a trigger").

## What you need to already know

[Chapter 10](10-four-scoring-engines.md) — Fusion's primary input is the Gaussian channel, whose
audited near-constant behavior matters directly to how much this step is really doing.

## The idea

### A layered scorer, not a weighted average

`src/core/fusion_engine.py`'s `FusionEngine.evaluate()` is structured as a sequence of layers rather
than a flat weighted sum:

1. **Gaussian scorer as the primary anchor.** Given [Chapter 10](10-four-scoring-engines.md)'s
   finding that Gaussian has largely collapsed to a near-constant, this is worth sitting with: the
   layer Fusion leans on hardest is currently the least informative of the four.
2. **A neural-model slot** — reserved for TradeNet v2, which is **built but never wired in**
   (F-005). This is a permanent, intentional stub, not an oversight in progress; wiring it up is a
   separate, explicitly gated qualification protocol (`TN_QUAL_V1`), not something that happens by
   accident.
3. **An LLM gate as an uncertainty tie-breaker** — and only that. It fires exclusively in a narrow
   confidence band, default `[0.45, 0.65]`. Any signal that's clearly strong or clearly weak never
   reaches the LLM at all. This is the concrete mechanism behind invariant #3: the LLM never decides
   a clear case, only helps break a tie in an ambiguous one, and (per Chapter 2) falls back to a
   neutral score after repeated failures rather than blocking.

### What Fusion is, honestly, right now

Given the state of the channels feeding it — Gaussian near-constant, Zone Gate redundant with the
rest of fusion (Chapter 10), RR correctly understood as a commitment score rather than reward:risk —
Fusion's practical job today is closer to "pass CRT's signal through, sanity-checked by a narrow LLM
tie-breaker on ambiguous cases" than "genuinely synthesize four independent opinions." That's not a
criticism of the design — the architecture is exactly right for a system meant to *add* independent
signal as each one earns its keep (Authority Ladder, [Chapter 17](17-truth-maintenance.md)) — it's
just the honest current state, which the Research Programs in Part VII are directly aimed at
changing.

## Classification

| Concept | Status |
|---|---|
| `FusionEngine.evaluate()` layered structure | Production |
| Gaussian-as-anchor | Production, but anchor is itself AUDITED near-constant (Ch.10) |
| Neural-model slot (TradeNet v2) | **Partial** — built, unwired (F-005) |
| LLM tie-breaker gate | Production, narrow-band only, fail-open |

## Authoritative sources

- `src/core/fusion_engine.py` — `FusionEngine.evaluate()`.
- `docs/topics/fusion-decision.md` — the always-synced topic doc (covers Fusion and Decision together).
- `docs/current-findings.md` F-005 (TradeNet stub) and F-060 (Gaussian anchor's audited status).
- `docs/governance/tradenet_lineage_audit.md`, `docs/governance/tradenet_qualification_protocol.md`
  — the wire-up path for the neural slot, if it's ever taken.
- `docs/architecture/goal.md` §3, invariant #3 — the LLM-as-advice rule this chapter's gate enforces.

## Unresolved questions

None for this pass — Fusion's structure and its channels' statuses are both well-evidenced by
Chapter 10's audits and the TradeNet lineage audit.

---
**Previous:** [Chapter 10 — The Four Scoring Engines](10-four-scoring-engines.md) · **Next:** [Chapter 12 — The Decision Engine](12-decision-engine.md)
**Related:** [Chapter 21 — The AI Automation Agent](21-ai-automation-agent.md) (the other place an LLM touches this repository, entirely off the synchronous spine)
**Memory:** `docs/memory/engine-memory.md`, `docs/memory/architecture-memory.md`.
