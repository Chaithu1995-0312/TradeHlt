# BNBUSDT Conditional-Edge / Simpson's-Paradox Audit — no hidden pocket

> **Date:** 2026-06-10 · **Scope:** read-only test of whether BNBUSDT's aggregate "no edge"
> hides a conditional pocket where a behavior beats the `random_uniform` control on **realized
> net expectancy**. Strictly measurement — no optimization, no new hypotheses, no promotion.
> Source: `results/research/bnbusdt_conditional_edge.json`. Companion to
> `bnbusdt-forensics-2026-06-10.md` §7.

## Method (disciplined, per the adversarial-audit lessons)
Per behavior (`expansion_breakout`, `mean_reversion`), bucket by `direction`, `atr_quartile`,
`hour`, `day_of_week`, `month`, `trend_proxy`. Each bucket's hypothesis net-RR is permutation-
tested (two-sided, reusing M4's `permutation_p_value`) against `random_uniform` **in the same
bucket** (never vs zero). Buckets with `min(n) < 50` skipped; `power_warning` flags `min(n) <
100`. **Benjamini-Hochberg across all 130 tests.** A survivor requires **both** `bh_q < 0.05`
**and** `|ΔE| > 0.05R` (economic floor); survivors (either sign) additionally get a year
breakdown. The opportunity profile is deliberately **not** used (it was shown low-power).

## Result

```
tests = 130 | BH survivors = 0 | negative survivors = 0 | conditional World-A = TRUE
```

**No bucket — across direction, volatility quartile, hour, day, month, or trend regime — beats
(or systematically loses to) the random control with both statistical significance and economic
effect size.** The aggregate "no edge" does **not** hide a pocket.

## Why the discipline mattered (the trap, caught)
Several buckets have seductive *raw* numbers that dissolve under correction:

| behavior | bucket | ΔE | p_raw | bh_q | verdict |
|---|---|---|---|---|---|
| mean_reversion | month 2026-03 | **+0.186R** | **0.001** | 0.130 | dissolved by BH |
| mean_reversion | month 2025-04 | +0.160R | 0.004 | 0.182 | dissolved |
| expansion_breakout | hour 14 | −0.177R | 0.007 | 0.182 | dissolved |
| mean_reversion | hour 15 | −0.134R | 0.006 | 0.182 | dissolved |

In isolation, "mean_reversion makes +0.186R in March 2026 at p=0.001" would have launched a
chase. Across 130 comparisons it is **expected noise** (BH `q=0.130`). Two further tells confirm
it is regime noise, not structure: the strong deltas are **monthly** (time-specific, not a
mechanism), and they are **mixed-sign** — 2026-03 is +0.186R for mean_reversion but −0.162R for
expansion_breakout in the very same month. Opposite behaviors "winning" the same month is the
signature of regime variance, not edge.

## Verdict
**Conditional World A holds.** BNBUSDT shows no edge at the aggregate level *and* no edge at the
conditional level (direction / volatility / time / regime). There is no hidden pocket to exploit
and no systematic failure mechanism to avoid. The burden of proof now moves **entirely onto
future hypothesis generation** — there is nothing left to harvest from the current behaviors on
this instrument.

This closes the diagnostic arc: Phase A (exit-model inflation) → Phase B M4 (PROMOTE: none) →
Forensics L1 (gross E≈0 + cost) → L2 + controls (opportunity is volatility, not entry info) →
adversarial audit (corrected the evidence; World A holds on the powered axis) → **conditional
audit (no hidden pocket).** Any future Experiment-2 is a separate, deliberate decision; its bar
is explicit and now twice-validated: **beat the random control on realized net expectancy, with
multiple-comparison control** — not on a low-power metric, not in a single cherry-picked bucket.
