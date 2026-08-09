# Chapter 10 — The Four Scoring Engines

**Part IV — Decision Making**
Status of this chapter: Written

## Why this chapter exists

`EngineRunner` (invariant #2, [Chapter 2](02-invariants-and-happy-flow.md)) runs exactly four
engines against every candle, unconditionally, and rejects the candle outright if any one is
missing. This chapter is the canonical explanation of the other three — Gaussian, Zone Gate, RR —
since CRT already owns [Chapter 8](08-crt-state-machine.md). It's also where this book delivers its
most important warning about the decision spine: three of the four engines have been formally
audited and found to contribute far less signal than their names suggest.

## What problem it solves

Explains what each engine actually computes (as opposed to what its name implies), and gives each
its correctly scoped status — because getting this wrong is exactly how a system ends up trusting a
number that's secretly closer to a constant.

## What you need to already know

[Chapter 7](07-feature-pipeline.md) (the 39-dim vector every engine consumes) and
[Chapter 8](08-crt-state-machine.md) (CRT, already covered).

## The idea

### CRT — see Chapter 8

The CRT engine's score comes from `src/engines/crt_engine.py`, delegating to
`engines/scoring_engine.py`. Its full explanation, including the state-machine/score-wrapper
distinction, is [Chapter 8](08-crt-state-machine.md) — this chapter doesn't repeat it, per the
book's Canonical Concept Rule.

### Gaussian — a channel that has largely collapsed to a constant

Two implementations exist behind a config switch (`gaussian_impl`): `HeuristicGaussianEngine`
(`src/engines/heuristic_gaussian_engine.py`, the live default, an EMA/momentum kernel) and
`MLGaussianEngine` (`src/engines/ml_gaussian_engine.py`, a trained Naive-Bayes model, fail-open to
0.5 on any error). Both ultimately route through the central scorer,
`src/config_layer/crt_gaussian_scorer.py`.

The audited finding here is stark: the live Gaussian channel is an **unparameterized kernel that
degenerates to a near-constant score of roughly 0.8825.** All eleven entries in
`gaussian_registry.json` lack `mu`/`sigma`, so the score-normalization code's defaults (0/1) fire
even on a *successful* registry load — meaning no learned parameter reaches the score at all, not
even a mistrained one. Compounding this, `tanh(momentum_score)` saturates on 93–100% of bars because
of a since-registered dimensional-mix defect upstream in the feature math, discarding the sign of
momentum entirely. An ablation test (pinning the channel at its saturated value, at neutral 0.5, and
at live) produced byte-identical decisions across all three settings on four crypto majors — proof
the channel is currently non-pivotal on both an information axis and a level axis. The model
artifact that trained these registry entries was also confirmed to have trained on contaminated
labels (the same F-022 labeling artifact discussed in [Chapter 17](17-truth-maintenance.md)).

### Zone Gate — a real geometric hard gate, honestly measured as not adding edge

`src/engines/zone_gate_engine.py` scores candle geometry against `models/zone_registry.json` (8
zones), fail-open on registry errors, via `_compute_soft_zone_score()`. Unlike Gaussian, this
channel is not degenerate — it's a working geometric filter that passes roughly 85% of candles it
evaluates. But a fusion-weight and threshold sweep (weight ∈ {0, 0.2, 0.4, 0.6}, threshold ∈
{0, 0.25, 0.5}) produced byte-identical trade sets across every combination — the zone channel is
redundant with what the rest of fusion already decides, not under-weighted. A separate re-derivation
of its stored win/loss labels through an honest forward-walk (rather than the contaminated F-022
labeling) found the same story at the label level: zero of the eight zones clear a positive
expectancy honestly. None of this implies live risk — the gate is purely geometric and fails open —
but it does mean tuning its weight or threshold is currently a lever with no effect to pull.

### RR — not actually a reward:risk engine

`src/engines/rr_engine.py`'s own module header states, plainly: it is "formerly misnamed 'RR
Engine'" — it does not compute forward-looking reward:risk at all. What it actually scores is
candle-close-position *commitment*: `max(upper_body, lower_body)` against the candle's range, i.e.
how decisively a candle closed toward one extreme. The book keeps its file/class name (`RREngine`)
for traceability but flags the naming mismatch here so a reader doesn't go looking for reward:risk
math in the wrong file — the actual reward:risk economics for a trade live entirely in
[`UltronRiskGate`](14-ultron-risk-gate.md).

A parallel line of investigation found a second, distinct issue with a now-disabled sibling
component, `rr_fusion`: its confidence-gate math was mis-scaled for the dimensionality of its input
(a 27-degree-of-freedom Mahalanobis form whose in-distribution confidence floor sits near 1.4e-6,
far below its own 0.3 bypass threshold) — so severely that **100% of its own training data** failed
to pass its gate. That component stays disabled in the active config; a follow-up shadow test on its
underlying model (bypassing the broken gate) found apparent out-of-sample discrimination, but on
labels later confirmed to be F-022-contaminated — leaving its true economic value formally
indeterminate, not proven and not disproven.

## Classification

| Concept | Status |
|---|---|
| CRT score | Production — see [Ch.08](08-crt-state-machine.md) |
| Gaussian (`HeuristicGaussianEngine` / `MLGaussianEngine`) | Production (wired, live), **AUDITED: non-pivotal, near-constant** |
| Zone Gate | Production (wired, live), **AUDITED: redundant, no marginal edge** |
| RR / `RREngine` (candle-commitment score) | Production (wired, live), **AUDITED: correctly named commitment score, not RR** |
| `rr_fusion` (disabled sibling) | Built, **disabled**, economic value indeterminate |

## Authoritative sources

- `src/engines/heuristic_gaussian_engine.py`, `ml_gaussian_engine.py`, `src/config_layer/crt_gaussian_scorer.py`.
- `src/engines/zone_gate_engine.py`, `models/zone_registry.json`.
- `src/engines/rr_engine.py`.
- `docs/topics/scoring-engines.md` — the always-synced topic doc covering Gaussian/Zone-Gate/RR together.
- `docs/current-findings.md` — F-036 (Zone Gate redundancy), F-038 (RR-fusion mis-gate origin),
  F-041B (honest zone labels), F-044 (dof-aware gate diagnosis), F-045/F-059 (RR clean-label
  re-test), F-060 (Gaussian constant collapse), F-061 (dimensional-mix mechanism generalized).
- `docs/governance/gaussian_lineage_audit.md`, `zonegate_lineage_audit.md`, `rr_lineage_audit.md` —
  the full per-engine AUDITED closure artifacts (see [Chapter 17](17-truth-maintenance.md) for what
  "AUDITED" means as a closure status).

## Unresolved questions

- RR's clean-label re-test (F-059) reached a "keep-candidate, research-only" verdict — whether a
  future pass changes `rr_fusion`'s disabled status is an open governance decision, not something
  this book resolves.

---
**Previous:** [Chapter 09 — Interpreters and the Pattern Contract](09-interpreters-pattern-contract.md) · **Next:** [Chapter 11 — Fusion](11-fusion.md)
**Related:** [Chapter 08 — The CRT State Machine](08-crt-state-machine.md) · [Chapter 17 — Truth Maintenance](17-truth-maintenance.md)
**Memory:** `docs/memory/engine-memory.md`.
