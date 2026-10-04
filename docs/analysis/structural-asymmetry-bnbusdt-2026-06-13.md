# Structural continuation asymmetry — Program 2 / Phase E1 (BNBUSDT)

> **Point-in-time analysis (history, not living truth).** Date: 2026-06-13 · Branch: `patch` ·
> Program 2 / Phase E1. Measure-only, **pure asymmetry (no profitability)**. Artifact:
> `results/research/phase_e/phase_e_structural_asymmetry.json` (deterministic). Driver:
> `scripts/research/phase_e_structural_asymmetry.py`; core: `src/research/structural_asymmetry.py`;
> harvester: `src/research/adapters/structural_event_source.py`. Promoted as **F-026**.

## Why this run

Program 1 (next-bar direction) is KILLED. The user opened **Program 2 = structural asymmetry** and its
leading branch — **Sweep → displacement → retest → continuation** — the one conditioning axis the prior
nulls never tested (F-020 used candle partitions; F-021/F-024 measured only the ~13 executed retests).
**The question, frozen and pre-registered:** *does the COMPLETED sweep→displacement→retest structure
possess forward directional asymmetry beyond sweep alone?* Pure measurement: multi-horizon `MFE_r/MAE_r`
(h∈{1,2,4,8,16}) + symmetric first-hit (L∈{0.25,0.5,1.0}R), four controls (A random / B session / C
volatility / **D sweep-only**), permutation + OOS + **in-pipeline calibration**. No SL/TP/RR/expectancy.

## Result — `VERDICT: INSUFFICIENT_POWER · POWER: INADEQUATE`

### E1.0 — the funnel (the most valuable output)
| Stage | Count | Transition |
|---|---:|---|
| SWEEP | **4,529** | — |
| DISPLACEMENT | 391 | **P(disp\|sweep) = 8.6%** |
| EXPANSION | 85 | |
| RETEST (completed) | **47** | **P(retest\|disp) = 12.0%** |
| EXECUTION | 16 | P(exec\|retest) = 34.0% |

**~1% of sweeps complete to a retest** (4,529 → 47). Extreme attrition: even if asymmetry existed,
47 retests over ~2 years is economically marginal. **Opportunity frequency is the binding constraint.**

### E1.1/E1.2 — asymmetry (test = completed retests, n=47)
- Excursion asymmetry `E[MFE] − E[MAE]` at h=8: **−0.319 R** (negative — MFE < MAE).
- First-hit `P(+0.5R first) − P(−0.5R first)`: **−0.106** (p+ 0.447 / p− 0.553; Wilson CI ±0.137).

### E1.3/E1.4 — vs the four controls (permutation, primary h=8 / L=0.5)
| Control | excursion Δ (test − ctrl) | p | first-hit Δ | p |
|---|---:|---:|---:|---:|
| A random | −1.331 | 0.98 | −0.170 | 0.84 |
| B session-matched | −0.564 | 0.74 | −0.043 | 0.66 |
| C volatility-matched | −1.016 | 0.93 | −0.085 | 0.74 |
| **D sweep-only** | **−0.331** | 0.80 | **−0.037** | 0.65 |

**Every delta is negative** — the completed retest structure shows **less** forward asymmetry than
sweep alone (D) and than every random control. Completing the trap does **not** add directional
information; the point estimate points the *wrong way*.

### E1.5 — calibration (the instrument is valid)
Planted `P(+0.5R first) = 0.55` → recovered **0.55** → **PASSED**. So a null/insufficient result is
*trustworthy*, not a broken measurement — the distinction Program 1's machinery taught us to enforce.

### E1.6 — OOS + verdict
OOS (n=14): excursion +0.64 but first-hit −0.14, **CI ±0.23** (sign-unstable vs IS). The OOS first-hit
CI half-width (0.23) exceeds the pre-set `power_ci_max` (0.07) → **POWER: INADEQUATE** → verdict
**`INSUFFICIENT_POWER`**.

## What this means (honestly)

1. **We cannot *prove* "no asymmetry"** — n=47 (14 OOS) gives CI ±0.14–0.23, so the four-way verdict
   correctly returns `INSUFFICIENT_POWER`, **not** a false `NULL`. This is the exact epistemic guard
   the protocol was built for: *absence of evidence ≠ evidence of absence.*
2. **But the point estimate is negative and loses to sweep-only (D).** The directional signal is the
   opposite of the thesis: completing displacement+retest does not concentrate forward asymmetry over
   the sweep alone. Combined with the four Program-1 falsifications (F-019/020/021/025), the weight of
   evidence is against the trap-continuation thesis on BNBUSDT M15.
3. **The funnel is the headline.** P(disp|sweep)=8.6%, P(retest|disp)=12% → ~1% completion. Even a
   real edge would be **throughput-starved** (47 retests/2yr) — the F-015 attrition story, now
   quantified at the structural level.
4. **Calibration passed** → the measurement instrument works; the inconclusive-but-negative outcome is
   real, not an artifact.

## Roadmap implication

Per the frozen protocol, **only `ASYMMETRY_SURVIVES` advances to E2** — this run does not, so **Program 2
does not proceed to conditioning/entries/exits.** The honest classification is `INSUFFICIENT_POWER` with
a **negative** point estimate and **~1% funnel completion**. Gaining power would require cross-instrument
pooling of the retest population, but the negative direction + the four prior falsifications make that
**low expected value** — Program 2 likely **ends here** (frozen), reopenable only if a *new* structural
ontology or a pooled population shows a *non-negative*, adequately-powered signal. No threshold search,
no E2 on this result (that would be the exact failure mode the protocol forbids).

## Reproduce
```
python scripts/research/phase_e_structural_asymmetry.py
```
Deterministic: JSON body carries no wall-clock; a second run is byte-identical. Frozen sets:
h∈{1,2,4,8,16}, L∈{0.25,0.5,1.0}R, 4 controls, n_perm=2000, OOS 70/30, power CI ≤0.07.
