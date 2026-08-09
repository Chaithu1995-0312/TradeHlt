# Chapter 12 — The Decision Engine: Semantic Approval Only

**Part IV — Decision Making**
Status of this chapter: Written

## Why this chapter exists

Fusion (Chapter 11) produces one combined score. Something has to turn that score into a binary
ACCEPT/REJECT. This chapter covers that module — and a genuinely interesting piece of the
repository's history: a multi-year-old bug that made this exact module a structural no-op, found
and fixed by re-deciding *who owns what*, not by tuning a threshold.

## What problem it solves

Explains what the Decision Engine actually decides today (semantic validity, not economics), and
why that split exists.

## What you need to already know

[Chapter 11](11-fusion.md) — the Decision Engine consumes Fusion's output directly.

## The idea

### What it decides

`src/core/decision_engine.py`'s `DecisionEngine` is described in its own source as "central
execution authority — only this module decides execute vs reject." What it actually evaluates is
purely semantic: is this a valid market opportunity, based on the fused score, the win-probability
estimate, and zone validity? It uses a dynamically calibrated threshold (the 85th percentile of
recent scores, clamped to `[0.45, 0.65]`) rather than a single fixed cutoff.

### What it used to decide, and why that broke everything silently

Until it was fixed, the Decision Engine also carried a reward:risk gate — comparing an RR-like
signal against a `rr_threshold` of 1.5. The problem: the value it was actually comparing was candle
*polarity*, a quantity bounded in `[0.5, 1]` (this is the "commitment score" from
[Chapter 10](10-four-scoring-engines.md)'s RR engine discussion — a value that structurally can
never exceed 1). Compared against a threshold of 1.5, this gate rejected as `low_rr` on **every
single candle**: across a 70,002-candle test corpus, the gated code path executed zero times.

### How it was resolved — an ownership decision, not a threshold tweak

The fix (F-048, 2026-07-24) wasn't to adjust the threshold or fix the polarity/RR mismatch in place
— it was to ask *which module should own reward:risk economics at all*, and answer it cleanly: the
Decision Engine's RR gate was **removed**. The Decision Engine is now semantic-approval-only
(score / win-probability / zone / weak-component checks); real, cost-taxed reward:risk economics
(`min_rr_ratio`, computed after the Execution Planner has determined actual SL/TP geometry) are
owned solely by [`UltronRiskGate`](14-ultron-risk-gate.md). The old `rr_threshold` config key is
retained but retired (kept for hash-neutrality, no longer read for a decision). Because no real
production path had ever actually fed genuine economic RR into the Decision Engine — only test
injectors had — the removal was verified byte-identical against the live spine's historical output.

This is a good worked example of the repository's own governance discipline in Part VI: a bug that
had silently zeroed out a gate for years was resolved by clarifying architecture (who owns reward:risk)
rather than papering over the symptom (retuning a threshold that was comparing the wrong quantities
in the first place).

## Classification

| Concept | Status |
|---|---|
| `DecisionEngine.decide()`, semantic-approval-only | Production, **current** design (post F-048) |
| The old RR gate inside Decision Engine | **Removed** (F-048, 2026-07-24) — retained config key is retired, not read |
| Dynamic threshold calibration (85th percentile, clamped) | Production |

## Authoritative sources

- `src/core/decision_engine.py` — `DecisionEngine.decide()`.
- `docs/current-findings.md` F-048 — the full resolution, including the byte-identical parity proof.
- `docs/topics/fusion-decision.md` — the always-synced topic doc.
- [Chapter 14 — Ultron Risk Gate](14-ultron-risk-gate.md) — the module that now solely owns
  reward:risk economics.

## Unresolved questions

None — F-048 is an unusually well-documented, closed piece of history with its own parity proof
already on record.

---
**Previous:** [Chapter 11 — Fusion](11-fusion.md) · **Next:** [Chapter 13 — The Execution Planner](13-execution-planner.md)
**Related:** [Chapter 14 — Ultron Risk Gate](14-ultron-risk-gate.md) · [Chapter 16 — Config-First Doctrine and the Promotion Path](16-config-first-and-promotion.md) (the governance discipline this fix exemplifies)
**Memory:** `docs/memory/engine-memory.md`.
