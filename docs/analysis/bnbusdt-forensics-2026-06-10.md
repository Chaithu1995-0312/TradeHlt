# BNBUSDT Forensics — WHY no edge under intrabar truth

> **Date:** 2026-06-10 · **Scope:** Layer-6 root-cause analysis, BNBUSDT only, both shipped
> behaviors, under the governing `intrabar_fixed` model with `close_only` as a measure-only
> optimistic counterfactual. **Explanation only — no optimization, no new hypotheses, no
> promotion.** Point-in-time analysis. Source: `results/research/bnbusdt_forensics.json`
> (FORENSICS_VERSION 1.0, truth_standard 2.0).

## 1. Verdict in one line

**The entry signals carry essentially no gross directional edge (gross E[R] ≈ 0); the
round-trip cost — large because 1×ATR stops are tight relative to BNB's price — then converts
break-even-gross into a decisive net loss. Intrabar realism makes it worse, but is secondary:
even the optimistic close-only bound is decisively negative.**

## 2. The numbers (net of 12bps unless noted)

| | expansion_breakout | mean_reversion |
|---|---|---|
| n (BNBUSDT only) | 12,666 | 22,368 |
| win rate | 33.4% | 33.7% |
| avg winner / avg loser (net R) | 1.55 / 1.44 | 1.56 / 1.41 |
| **E[R] gross** | **−0.002** | **+0.008** |
| **E[R] net** | **−0.439** | **−0.409** |
| **cost drag (R/trade)** | **0.437** | **0.417** |
| PF close-only → intrabar | 0.60 → 0.54 | 0.67 → 0.56 |
| E[R] close-only → intrabar | −0.36 → −0.44 | −0.29 → −0.41 |

(n here is BNBUSDT-only; the M4 pooled run's 55k/121k spanned 11 instruments.)

## 3. Three measured causes, in order

**(1) No gross edge — the dominant cause.** Gross expectancy is ≈ 0 for *both* behaviors
(−0.002R, +0.008R). At a 1:2 SL:TP geometry, a 33% win rate is almost exactly the break-even
line (0.33·2 − 0.67·1 ≈ 0). The detectors produce outcomes statistically indistinguishable
from random entries with this geometry — there is no directional information to harvest. This
is consistent with the `loss_mechanisms` ranking: **`plain_stop_loss` is ~90% of all R lost**
(expansion 90.4%, mean_reversion 89.5%) — i.e. losses are overwhelmingly *the bet was simply
wrong*, not an execution artifact.

**(2) Cost is the swing factor.** With gross ≈ 0, the **0.44R / 0.42R per-trade cost drag**
*is* the entire net loss. The 12bps round-trip becomes ~0.44R because the stop distance
(1×ATR) is small relative to BNB's price level (cost_R = bps/1e4 · entry / risk_distance).
> **Honest nuance:** the narrow `cost_drag` loss-mechanism bucket (gross-positive trades that
> cost flipped to losers) is ~0% — only 5/32 trades. That bucket counts only *sign flips*; it
> does NOT capture the pervasive erosion of every winner (2R→1.55R) and deepening of every
> loser (1R→1.44R). The `expectancy_decomposition.cost_drag_rr` (0.44/0.42) is the truer
> causal figure. The two sections answer different questions and must be read together.

**(3) Intrabar damage is real but secondary.** `same_bar_conflict` (close-only would have hit
TP, intrabar wick stopped it first) is 787 / 1,516 trades = **~9–10% of R lost**; it shaves
PF 0.60→0.54 / 0.67→0.56 and E[R] by ~0.08–0.12R. So intrabar realism degrades an
already-losing system — but **the optimistic close-only bound is still decisively negative
(E −0.36 / −0.29)**. This refutes the hypothesis that intrabar mechanics killed an otherwise
good edge: there was no edge to kill.

## 4. Clustering

Loss clusters are severe and dominated by long runs (`4+` is the largest bucket): max
**22** consecutive losses (expansion), **53** (mean_reversion). Win clusters are shorter
(max 9 / 19). This asymmetry is what you expect from a no-edge, negative-drift process — not
from a real edge being intermittently disrupted.

## 5. What this means for the (future, separate) Experiment-2

The #1 R-destroyer is **plain_stop_loss (no entry edge)** — so the next hypothesis space is
**entry/signal predictiveness**, NOT bar-quality / intrabar filters (only ~10%) and NOT
execution-cost tweaks alone (cost on a zero-gross-edge signal is rearranging deck chairs).
Two measured, separable leads:
- **Entry edge** (primary): the detectors have ~0 gross information; a viable hypothesis must
  demonstrate gross E[R] > 0 *before* costs. Without that, nothing downstream matters.
- **Cost/stop-geometry interaction** (secondary, structural): 1×ATR stops on a high-priced
  instrument make 12bps cost ~0.44R. Even a real edge would need to clear that; worth a
  deliberate stop-distance/cost sensitivity study — but only *after* a gross edge exists.

**This stays a finding, not an action.** No parameters changed, no hypotheses added, no
promotion. The choice of Experiment-2 is a separate, deliberate decision seeded by these
measurements — not taken here.

---

## 6. Layer-2 opportunity profile — World A vs World B (added 2026-06-10, FORENSICS_VERSION 1.1)

To distinguish **World A** (entries carry no information) from **World B** (information exists
but exits squander it), an **exit-agnostic** `horizon_excursion` measures max favorable/adverse
excursion over the full 40-bar horizon *ignoring* SL/TP, with path-quality (`favorable_first` =
+1R before −0.5R) and speed (`bars_to_first_1r`). Profiled per cut, the sharpest discriminator
being `by_exit_reason.sl_hit`.

**First glance looked like World B:** SL-losers reach +1R ~70%, +1.5R ~57%, mfe_p95 8–12R. But
two internal caveats undercut it — `favorable_first` is only **~25%** (price goes −0.5R adverse
*first* in ~75% of cases; the +1R arrives *after* the drawdown that stopped us out) and
`capture_ratio_p50 ≈ −0.78`. The huge two-sided MFE over 40 bars looked like raw volatility, not
timing edge.

**The control baseline settles it.** Running the identical opportunity profile on random entries
(`always_long`, `random_uniform`) on the same BNBUSDT data — SL-loser slice:

| | reach 1R | reach 1.5R | reach 2R | favorable_first | mfe_r_p50 | capture_p50 |
|---|---|---|---|---|---|---|
| expansion_breakout | 69.4% | 56.6% | 45.2% | 25.1% | 1.78 | −0.77 |
| mean_reversion | 71.4% | 57.0% | 43.6% | 27.4% | 1.74 | −0.78 |
| **always_long (control)** | 69.5% | 55.5% | 43.1% | 24.9% | 1.71 | −0.80 |
| **random_uniform (control)** | 69.5% | 55.7% | 43.6% | 25.0% | 1.73 | −0.80 |

**The hypotheses are statistically indistinguishable from random entries on every opportunity
metric.** The "70% reach +1R" is purely BNB's volatility over a 40-bar window — *any* entry,
including a coin flip, produces it. `favorable_first ≈ 25%` (not >50%) confirms the entries do
not even time direction: adverse comes first as often as for random.

### Verdict: **World A — entries carry no directional information.**
Not World B. There is no captured-but-squandered edge because there is no edge. This required
the control comparison to see — the raw "opportunity" numbers alone would have been misleading
(exactly the narrative-fallacy trap). Decision impact for the *future, separate* Experiment-2:
the lever is **entry/signal predictiveness**, definitively NOT exit/target redesign and NOT
"widen stops" (wider stops would only hold random losing positions longer). A viable hypothesis
must demonstrate `favorable_first` and reach-rates **materially above the random control** —
that is now the explicit bar.

**Known measurement limitation (does not affect the verdict):** `sl_hit_slow` (duration ≥ 96
candles) is structurally empty because `max_forward = 40` caps duration < 96; the fast/slow
threshold must be set below `max_forward` to be meaningful. The control comparison is the
decisive evidence regardless.

---

## 7. Adversarial audit & self-correction (2026-06-10)

An adversarial JSONL audit was run to try to *falsify* the §6 World-A verdict. Result: the
**conclusion holds, but §6's stated reasoning was partly wrong** — recorded here in full.

- **Integrity clean:** 0 duplicate `trade_id`, 0 missing fields, 0 `bars_to_first_1r < 1` (no
  off-by-one/look-ahead); `always_long` is 100% long, `random_uniform` 49.9/50.1; hypotheses
  fire selectively (12,666 / 22,368 vs 70,049 every-bar). No pipeline artifact produced the
  result.
- **Valid evidence = net-expectancy permutation (BNBUSDT-only):** `expansion_breakout`
  E=−0.439 vs random −0.415 (p=0.96, *worse*); `mean_reversion` E=−0.409 vs −0.415 (Δ=+0.006R,
  **p=0.29 — not significant**). Neither beats random on the powered axis.
- **⚠ Correction to §6's reasoning:** the opportunity profile is **volatility-dominated and
  low-power** — it cannot distinguish `always_long` (100% long) from `random_uniform` (50/50):
  reach1R 79.8%≈79.8%, favfirst 35.1%≈35.4%. Therefore "opportunity profile ≈ random ⇒ World A"
  (the inference §6 leaned on) is **invalid**; and the favfirst≈25% cited there is just the BNB
  baseline, not hypothesis-specific. The profile measures BNB's volatility, **not** entry
  information. The World-A verdict stands **only** on the net-expectancy permutation above.
- **Reconciliation with M4:** M4's `mean_reversion` p=0.0005 was **pooled across 11 instruments**
  (n=120,972); on BNBUSDT alone (n=22,368) it is p=0.29. No contradiction — different scope.

**Precise defensible claim (replaces the looser §6 wording):** *On BNBUSDT, neither behavior
shows a statistically significant edge over random on realized net expectancy. The opportunity
profile is low-power and speaks only to BNB volatility, not entry information. No claim is made
beyond BNBUSDT; `mean_reversion` carries a real but net-negative signal somewhere in the pooled
universe.* The Experiment-2 bar is corrected accordingly: a hypothesis must beat the random
control on **realized net expectancy** (a powered test), not on the opportunity profile.

A conditional-edge / Simpson's-paradox audit (per-bucket net-expectancy vs the same-bucket
random control, BH-corrected, effect-size-floored) follows in
`docs/analysis/bnbusdt-conditional-edge-2026-06-10.md` to check whether the aggregate result
hides a pocket.
