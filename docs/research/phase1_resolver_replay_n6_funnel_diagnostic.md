# Phase-1 resolver replay — n=6 funnel diagnostic

**Status:** DIAGNOSTIC ONLY · `economic_claims_allowed=false` · no Case reopening · no promotion  
**Date:** 2026-09-09  
**Corpus:** Phase-1 XAUUSD · csv sha256 `4d73f5ce…` (same as replay scoreboard)

## Question

Why did an expected ~31 resolver EXP entries become **n=6** scored observations?

## Short answer

**There was no 31→6 scoring collapse on this replay.**  
Under the frozen resolver object (`SHADOW→EXP` / `SHADOW_EXPANSION_CONFIRMED`), the engine produced **exactly 6** collapses. All 6 had `pending_displacement_dir`, all 6 scored on both Memory and TrendBias (coverage 100%).  

So **n=6 is the size of the measurement object**, not an unintended post-filter bottleneck that discarded ~25 otherwise-scorable resolver entries.

Whether a prior verbal/freeze expectation of ≈31 referred to a *different* object is open — no repo freeze artifact found that pins this SHADOW→EXP universe at 31.

## Funnel (measured)

| Stage | Count | Notes |
|------:|------:|-------|
| Phase-1 bars / Always-Long stride-H20 universe | 2364 | control path |
| Always-Long scored | 2359 | coverage 99.79% |
| Enter EXPANSION (any predecessor) | 148 | 142 DISPLACEMENT→EXP + 6 SWEEP→EXP |
| Of which shadow-resume SWEEP→EXP (`Shadow resume…`) | **6** | = resolver collapses |
| `funnel_counts.SHADOW_PENDING` (bt summary) | **6** | occupancy of shadow state |
| Captured `SHADOW_EXPANSION_CONFIRMED` | **6** | `collapses.json` |
| Memory eligible / scored | 6 / 6 | skips: none |
| TrendBias eligible / scored | 6 / 6 | skips: none |

Memory and TrendBias share the **same six candle indices**: 1459, 2197, 2325, 10787, 24371, 37381.

## Cross-check with prior probe

`results/analysis/shadow_cross_range_restoration.LATEST.*` on the same corpus:

- `n_restorations_total: 6`
- contingency: all 6 SAME_RANGE → RESET_BEFORE_EXECUTION (descriptive only)

Replay did not invent a narrower filter than the earlier shadow restoration probe.

## Contract vs bottleneck

| Reading | Supported? |
|---------|------------|
| **Contract-expected rarity** of SHADOW→EXP on Phase-1 XAUUSD | **Yes** — object n=6 at capture and at score |
| **Unintended measurement bottleneck** dropping ~31→6 inside scoring (strict_memory / ATR / horizon trunc) | **No** — zero skip codes on the six rows |
| **≈31 was this same object** | **Not evidenced in-repo** — search did not find a freeze doc fixing resolver SHADOW→EXP n≈31; nearby numbers: EXPANSION entries=148, all_states H20 EXPANSION n=148, SHADOW_PENDING excluded historically for n=6 < 30 floor |

## Implication for Case B

Unchanged from the evidence note:

- Observed ordering on these six: TrendBias > Always-Long > Memory → **Case B pattern**
- Power **INSUFFICIENT** (n=6 ≪ 30)
- `economic_claims_allowed=false`

The n=6 problem is **object scarcity under the frozen SHADOW→EXP definition**, not a bug that secretly threw away scored resolver EXP trades.

## What would be required to approach n≥30

Anything that **widens the unit** beyond frozen `SHADOW→EXP + …` (e.g. counting all EXPANSION entries, flipping `continuous_disp_to_expansion`, wiring CHoCH, reopening occupancy) is **outside authorization** under the standing freeze.  

Allowed path to larger n without changing the object: **more corpus / more instruments under the same SHADOW→EXP capture** — still may not reach 30 if the event is this rare. That is an authorization decision, not a silent redesign.

## Artifacts

- This note: `docs/research/phase1_resolver_replay_n6_funnel_diagnostic.md`
- Replay: `results/analysis/phase1_resolver_replay/`
- Prior shadow probe: `results/analysis/shadow_cross_range_restoration.LATEST.json`
