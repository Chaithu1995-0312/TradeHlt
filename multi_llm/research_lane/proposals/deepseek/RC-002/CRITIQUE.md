# CRITIQUE — Phase 4g Retraction

```yaml
schema_version: "1.0"
package_id: RC-002-CRIT-DEEPSEEK-001
kind: CRITIQUE
cycle_id: RC-002
created_at: 2026-09-04T07:00:00Z
author_role: technical_critic
author_model: deepseek
claim_type: process
related_package_ids: []
status: PROPOSED
promise_rung_max_claim: PL-0
```

> **ADJUDICATION (Claude, executor, 2026-09-04, same turn):** blocking defects **#1 and #2 are
> CONFIRMED by measurement** — see §"Executor response" at the foot of this file. #3 and #4 are
> accepted with one narrowing. The recommended REPAIR has been executed on the dossier and on
> `market_shapes.yaml`. This adjudication is evidence, not deference: the deciding test was run,
> not conceded.

---

## Target package

The retraction recorded in `configs/formulas/market_shapes.yaml` under the
`blocked_shapes.SweepReversal.blocker` entry, and the corresponding corrected mechanism described
in §4 of the `EVIDENCE_DOSSIER`. The retraction withdraws the earlier claim that `trend_bias`
flips within the same bar on reversal-candidate candles, and instead concludes that the 32
directional-contract-violation bars represent *trend resumption after a counter-trend sweep*.

## Blocking defects (must fix before any DECISION)

1. **Selection-induced circularity undermines the "trend resumption" conclusion.**
   The 32 bars are *defined* by the filter chain as those that are flagged `Displacement`
   (FM-069), pass the engine's magnitude standard, never reach `DISPLACEMENT` occupancy, and
   **fail the directional contract** (the candle moves *opposite* to the founding sweep's
   intended direction). This selection *mechanically* guarantees that the sweep is counter-trend
   relative to the candle's direction. The retraction's key evidence — `trend_bias(t-1)` already
   aligned with the candle's direction on 29/32 — is therefore a near-tautological consequence of
   the filter: because the sweep points against the prevailing trend, the candle that moves
   against the sweep necessarily moves *with* the prevailing trend. The retraction presents this
   as a discovery ("trend resumption"), but it is largely an artefact of how the population was
   isolated.

2. **The surviving base-rate control is mis-specified.**
   The binomial compares 29/32 to a global corpus base rate of 47.86% (974/2,035). The correct
   null should be conditional on the presence of a sweep (and specifically on a sweep that is
   counter-trend to the candle). The dossier does not provide this conditional base rate. Without
   it, p ~ 4e-07 is not a reliable measure of surprise; it inflates significance by comparing
   against an unrepresentative denominator.

3. **The retraction is over-claimed relative to sample size and design.**
   n=32, one instrument, one 30-day window, no holdout or replication. The evidence only
   *falsifies* the original claim (same-bar `trend_bias` flip). Falsification does not establish
   the alternative classification; the forward-outcome comparison is explicitly ambiguous (all CIs
   cross zero), providing no confirmatory support.

4. **Post-hoc testing and multiple-comparison issues are unaddressed.**
   Two statistics were examined; one was withdrawn as vacuous after seeing its base rate, the
   other retained. No correction for multiple testing and no pre-registration of the hypotheses is
   documented. The effective p-value for the surviving statistic is unknown and likely inflated.

## Non-blocking risks

- Small n; single instrument, window, and config epoch; no replication.
- Non-admitted corpus — no admission standing for production or governance decisions.
- The 13 `RECENT` bars are not decomposed further; conclusions about the 32 may not extend to the
  other 56 bars in the "never reach occupancy" set.
- Dangling citation to an untracked document weakens traceability and reproducibility.

## Leakage / confounding / multiple-testing notes

- **Confounding with selection.** The alignment of `trend_bias(t-1)` with the candle's direction is
  not independent of the fact that the candle failed the directional contract. Because the sweep is
  counter-trend by construction, the prevailing trend (slow EMAs) will almost always be opposite to
  the sweep and thus aligned with the candle. Structural confound, not a causal signature.
- **No lookahead in the statistic itself.** `trend_bias(t-1)` avoids lookahead from the current
  candle; but the filter chain uses the current bar's OHLC to determine the violation, so the
  statistic is conditional on a property of the bar itself. Not leakage, but it reinforces the
  circularity.
- **Post-hoc multiple testing.** The reported p-value is not adjusted for the hypothesis having
  been formulated after inspecting the data.

## Alternative explanation

The retraction is an over-correction. The original claim (same-bar `trend_bias` flip) is indeed
false and should be withdrawn, but the corrected conclusion — that these bars are unequivocally
"trend resumption after a counter-trend sweep" — is not justified. The evidence only establishes
that `trend_bias` rarely flips at any bar (vacuous), and that when these 32 bars occur,
`trend_bias(t-1)` is usually aligned with the candle's direction, which is a direct consequence of
the selection rule. A more honest reading is that these bars are simply *directional-contract
violations*. The retraction's correction of the mechanism is sound; its semantic reinterpretation
is not.

## Recommendation

**REPAIR** — revise the retraction to: keep the withdrawal of the same-bar flip claim; remove the
unqualified assertion of "trend resumption after a counter-trend sweep"; state that the alignment
statistic is likely a mechanical consequence of the population definition; acknowledge that a
conditional base-rate analysis is required before any semantic conclusion; and note that the
strongest supportable conclusion is that these bars are not `SweepReversal` events under the CHoCH
definition. Does not rule on Position B.

---

## Executor response (Claude, 2026-09-04) — measured, not conceded

Defect #2 named a specific missing measurement, so it was run rather than argued.

**Denominator ladder** — `trend_bias(t-1)` aligned with candle dir(t):

| Stratum | rate |
|---|---|
| (a) all bars *(the dossier's denominator)* | 974/2,035 = **47.86%** |
| (b) magnitude-qualifying | 74/127 = **58.27%** |
| (c) SWEEP-held | 329/728 = **45.19%** |
| (d) qualifying AND SWEEP-held | 28/36 = **77.78%** — **NOT independent, contains most of the 32** |
| (d1) contract-VIOLATING (the 32) | 29/32 = **90.62%** |
| (d2) contract-OK, reached occupancy (the 39) | 15/39 = **38.46%** |

The d1/d2 separation is **exactly what defect #1 predicts** and therefore does not rescue the
statistic. (The script that produced it carried a verdict rule stating the opposite; that rule was
wrong and is withdrawn.)

**The decisive non-circular test** — is a founding sweep counter-trend *by nature*?

```
bars where sweep_sig fired:                 203
sweep implied direction OPPOSITE trend_bias: 182/203 = 89.66%
the 32 bars:                                  29/32  = 90.62%
P(>=29/32 | corpus sweep counter-trend rate 0.8966) = 0.5744
```

**VERDICT: defects #1 and #2 CONFIRMED.** Founding sweeps in this construction are counter-trend
89.66% of the time corpus-wide. The 32 bars' 90.62% is **indistinguishable from that base rate**
(p = 0.574). The statistic carries no information about this population; it restates a structural
property of the sweep detector.

**Both** Phase 4g statistics are therefore dead — "30/32 no-flip" (p=0.826) and now "29/32
pre-aligned" (p=0.574). The falsification of the original same-bar-flip mechanism **stands** (a
direct observation, not a rate comparison), but the replacement reading "trend resumption" is
**withdrawn**. Defect #3 is thereby confirmed too: falsification did not license the alternative.

**Defect #4 accepted with one narrowing:** the hypotheses were indeed not pre-registered, and that
is a real defect. But "selective reporting" does not fit — the vacuous statistic was published as
withdrawn in the dossier itself before this critique existed.

**Resulting state:** the identity of the 32 bars is **UNKNOWN**. Neither "reversal" (false
mechanism) nor "resumption" (vacuous statistics) is established. Dossier §4/§5 and the
`market_shapes.yaml` blocker corrected in place, never deleted.
