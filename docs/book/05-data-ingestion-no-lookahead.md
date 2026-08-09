# Chapter 05 — Data Ingestion and the No-Lookahead Discipline

**Part II — Market Understanding**
Status of this chapter: Written

## Why this chapter exists

Everything downstream — features, engines, fusion, decisions — is only as trustworthy as the candle
stream feeding it. Invariant #1 from [Chapter 2](02-invariants-and-happy-flow.md), deterministic
replay, is only meaningful if the data itself never leaks future information into the past. This
chapter covers Step 1 of the spine: how a candle enters the system, and what stops it from cheating.

## What problem it solves

A backtest that can see the future is not a backtest — it's a curve-fit generator. This chapter
explains the layered defense against that failure mode, and is honest about where that defense is
strong versus merely adequate.

## What you need to already know

[Chapter 2](02-invariants-and-happy-flow.md)'s seven-step spine — this chapter is Step 1 of it.

## The idea

### Where a candle comes from

In backtest, `runtime/backtest_v2.py`'s `CandleLoader.stream()` reads historical OHLCV and yields
candles one at a time, in order. In live mode, `inout/scanner.py` plays the equivalent role, reading
from a broker/data feed. Either way, the unit that leaves this step and enters
[the feature pipeline](07-feature-pipeline.md) is a single `Candle`.

### The four-layer integrity stack

No-lookahead isn't one gate — it's the *conjunction* of four layers, and that framing matters: a
gap in any one layer doesn't necessarily mean data leaked, but it does mean the safety margin is
thinner than the others.

- **L1 — schema.** Every candle is validated against the expected OHLCV shape before it's used.
- **L2 — temporal.** Candles must arrive in strictly increasing chronological order; out-of-order or
  duplicate timestamps are rejected. This backstop is inline and always-on, everywhere `stream()` is
  consumed.
- **L3 — dataset-level pre-flight.** A heavier, whole-dataset integrity check
  (`dataset_integrity.validate_dataset`) that runs *before* a backtest starts, catching structural
  problems (gaps, session-boundary anomalies) that a candle-by-candle check can't see.
- **RT — real-time generator causal ordering.** In the live path, the generator itself is
  constructed to only ever emit a candle once it has actually closed.

### The honest caveat: L3 doesn't run everywhere

A repo-wide census found that the L3 pre-flight check runs at only **two call sites**, both inside
`backtest_v2` (`_preflight_dataset` and `validate_universe`). Every other consumer of
`CandleLoader.stream()` — the entire `src/research/` pipeline, analytics, governance, replay,
`config_validator`, and the broader `scripts/` research/training/analysis fleet — streams candles
with only the always-on L1/L2 inline backstop, not L3. This was captured as a documentation
correction: an earlier claim that L3 ran at "every backtest entry point" was itself an overclaim,
now corrected. The scope of what this means is narrow and important to get right: **L1/L2 alone did
still enforce schema and chronological ordering** on every one of those research runs — this is a
*single-layer fragility* finding (L3's extra dataset-wide safety margin is concentrated in two call
sites), not a claim that leakage occurred. It does not reopen or invalidate any research finding
built on those paths.

## Classification

| Concept | Status |
|---|---|
| L1 (schema) / L2 (temporal) inline backstop | Production, always-on everywhere `stream()` is used |
| L3 dataset pre-flight | Production, but scope-limited to two `backtest_v2` call sites |
| RT causal ordering (live generator) | Production |

## Authoritative sources

- `docs/architecture/signal-flow.md` §1, Step 1 — the four-layer table with module/failure-mode detail.
- `src/runtime/backtest_v2.py` — `CandleLoader.stream()`, `_preflight_dataset`, `validate_universe`.
- `src/inout/scanner.py` — the live-mode equivalent.
- `docs/current-findings.md` — F-039 (the L3-scope correction, `Certain` confidence, docs/research-only authority).

## Unresolved questions

None beyond what F-039 itself already scopes precisely — see the finding for exact call-site detail.

---
**Previous:** [Chapter 04 — Architecture at a Glance](04-architecture-at-a-glance.md) · **Next:** [Chapter 06 — The Market Ontology](06-market-ontology.md)
**Related:** [Chapter 07 — The Feature Pipeline](07-feature-pipeline.md)
**Memory:** `docs/memory/runtime-memory.md`.
