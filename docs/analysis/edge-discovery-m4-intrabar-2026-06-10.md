# Edge Discovery M4 — QualificationGate Run under Intrabar Truth → PROMOTE: none

> **Date:** 2026-06-10 · **Scope:** Phase B / Edge Discovery Program M4 — first
> behavior-agnostic edge search run under the unified intrabar truth standard (Phase A's
> governing exit model). Point-in-time analysis (not a living doc).
> **Verdict: PROMOTE: none — a successful, honest experiment.**

## 1. What ran

`python -m research.cli qualify` over the 11-instrument universe, under the reconciled
realism (`forward_walk.exit_model = intrabar_fixed`, flat 12bps cost). The 7-gate
`QualificationGate` (sample → expectancy → PF → beats-control → OOS-retention →
permutation-significance → Benjamini-Hochberg) evaluated the two shipped hypotheses against
the winning falsification control.

Provenance (stamped in `results/research/qualification/qualification_report.json`):
`qualification_version=1.0`, `permutation_method_version=1.0`, `permutation_count=2000`,
`bh_method_version=1.0`, `alpha=0.05`, `truth_standard={intrabar_fixed, flat_12bps,
SL_before_TP, v2.0}`, `research_cost_model_version=1.0`, `spine_cost_model_version=1.0`,
`config_sha256=a7492591…`.

## 2. Verdict

| Subject | n | PF (net) | E[R] (net) | perm p | Gate | Verdict |
|---|---|---|---|---|---|---|
| `random_uniform` (winning control) | — | — | **−0.351** | — | baseline | — |
| `expansion_breakout` | 55,055 | 0.517 | **−0.468** | 1.0000 | gate 2 (expectancy) | **REJECT** |
| `mean_reversion` | 120,972 | 0.743 | **−0.215** | 0.0005 | gate 2 (expectancy) | **REJECT** |

**PROMOTE: none.**

## 3. Reading the result

- **The null is sound.** Even the best control (`random_uniform`) has negative expectancy
  (−0.35R) under intrabar exits + costs — random trading loses, as it must. The machinery is
  not rejecting everything by accident; it is measuring a real negative-sum environment.
- **Significance ≠ profitability.** `mean_reversion` is *statistically significant* vs the
  control (permutation p=0.0005 — reliably **less bad** than random) yet still has negative
  expectancy, so gate 2 rejects it before significance (gate 6) or BH (gate 7) ever matter.
  This is exactly the ordering the gate is designed for: profitability gates precede
  statistical gates, so a "significant loser" cannot leak through.
- **No Outcome C.** No control was evaluated as (or masqueraded as) a qualifying hypothesis →
  no gate bug. The falsification baseline behaved as a baseline.
- **Corroborates Phase A** from an independent, behavior-agnostic angle: under the unified
  intrabar truth standard, neither continuation (`expansion_breakout`) nor mean-reversion
  shows positive expectancy. The CRT-config falsification was not idiosyncratic to CRT.

## 4. Engineering note (the permutation fix)

The first attempt hung: the naive `shuffle(pool)` permutation was `O(perm × pool)` and the
controls emit ~1 signal/bar (~346k pooled). The rewrite samples only the *smaller* group's
sum per iteration → `O(perm × min(nh,nc))`, the **identical** permutation statistic. Run now
completes in normal time. Faithfulness is unit-tested (per-permutation algebraic identity +
Monte-Carlo convergence vs a brute-force reference). `PERMUTATION_METHOD_VERSION` stays `1.0`
(optimization, not a method change); `permutation_count` is tracked separately.

## 5. What this does NOT license

- **No B2+.** There is no qualified edge to map into CRT parameters / sweep / promote.
- **No hypothesis-stuffing to force a pass** (Goodhart). Adding hypotheses until something
  clears would convert the rejection gate into a false-discovery engine.
- The honest next move, *if any*, is a **deliberate** expansion of the hypothesis space or
  the data universe — a fresh, separately-scoped decision, not a continuation of this run.
  When the hypothesis set starts churning, add `HYPOTHESIS_SPACE_VERSION` (the BH universe is
  itself governance).

**Status:** Edge Discovery M4 = DONE. M4.5 (meta-analysis) and M4.7 (economic-explanation
gate) remain the required guardrails before any future promotion.
