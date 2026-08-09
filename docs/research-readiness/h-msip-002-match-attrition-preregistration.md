# H-MSIP-002 / H-018 — H-017 Match Attrition and Estimand Robustness

> **PRE-REGISTERED before any outcome re-examination under alternative estimands.**  
> Status: **OPEN · EXPLORATORY_RESEARCH · RESEARCH_ONLY**  
> **Execution authorized: NO** (preregistration only)  
> Date: 2026-07-14

| Field | Value |
|-------|--------|
| Program alias | **H-MSIP-002** |
| Registry id | **H-018** |
| Title | H017_MATCH_ATTRITION_AND_ESTIMAND_ROBUSTNESS |
| Parent | H-017 / H-MSIP-001 (owner-accepted RESEARCH_SUPPORTIVE_MICRO_EFFECT) |
| Task class | EXPLORATORY_RESEARCH |
| Authority | RESEARCH_ONLY |
| Execution | **NOT AUTHORIZED** until separate owner grant |

Machine twin: `h-msip-002-experiment-definition.json`

---

## 1. Why this experiment exists

H-017 rejected the strongest form of the null for **one** pre-registered cell
(`P-BOS = +1`) under matched controls, permutation, BH, walk-forward / held-out sign
stability, calendar-spike guard, and `CRT_STATE_ONLY`.

Owner-accepted reading: **RESEARCH_SUPPORTIVE_MICRO_EFFECT** on the **matched subpopulation**.

Unresolved methodological issue:

```text
TREATMENT BARS  = 13,660
MATCHED         =  7,277
UNMATCHED       =  6,383
MATCH ATTRITION ≈ 46.7%
```

The successful estimate is valid for the matched subpopulation. It is **unknown** whether
±32-bar exact matching selected an unusually comparable subset or whether the residual
generalizes under broader-support control constructions.

**This experiment attacks match attrition — not new MSV partitions.**

---

## 2. Fixed target (frozen from H-017)

| Item | Value |
|------|--------|
| Partition | **P-BOS only** (`structure_state.break_of_structure`) |
| Level | **+1 only** |
| Primary outcome | **R_h at h=8** |
| Population corpus | Phase-1 XAUUSD M15 (same pin as H-017) |
| Occupancy definition | ACTIVE_STATES ∩ `candidate_episode_id ≠ null` (same as H-017) |

### Explicit non-goals (hard)

- No new MarketStateVector partitions  
- No new horizons  
- No threshold search  
- No post-hoc subgroup discovery  
- No continuous cutpoints / HOW labels  
- No CRT behavior change / MSIP authority / migration / production  

---

## 3. Primary question

Does the pre-registered H-017 **P-BOS=+1** residual remain **directionally and statistically
stable** when the treatment estimand is evaluated under **alternative pre-registered
control-construction methods** that reduce dependence on the original ±32-bar exact matching
procedure?

---

## 4. Pre-analysis composition diagnostics (before re-estimating H-017 outcomes)

**Mandatory order:** complete composition diagnostics **before** inspecting alternative-estimand
outcome results.

Compare **matched vs unmatched treatment** populations using **only** pre-treatment /
state-composition diagnostics (no outcome columns in this stage):

| Diagnostic | Purpose |
|------------|---------|
| Calendar distribution (month / fold) | time selection |
| CRT lifecycle-state composition | state mix |
| Episode duration / age at bar | lifecycle shape |
| Session | matching covariate |
| Volatility regime | matching covariate |
| Trend bias | matching covariate |
| P-BOS prevalence (and P-BOS=+1 share) | treatment-label composition |

**Report:** standardized mean differences / proportion differences; flag severe imbalance
(pre-registered: |SMD| > 0.25 on any matching covariate or P-BOS=+1 prevalence gap > 10 pp).

These diagnostics answer: *what population did the H-017 estimate actually represent?*

---

## 5. Three pre-registered estimands / control constructions

All estimands use the **same** treatment definition (occupancy bars with P-BOS=+1) and
**same** outcome R_8. Only control construction differs.

### E0 — Reference replication (H-017 matched subpopulation)

- Exact block match on `session × volatility_regime × trend_bias`
- Nearest RANGE control within **±32 bars**
- Contrast: mean(R_8 | treatment matched, P-BOS=+1) − mean(R_8 | matched RANGE)
- Purpose: **byte-protocol replication** of H-017 primary contrast for this cell

### E1 — Overlap / common-support weighted estimate (broader treatment)

- Treatment universe: **all** occupancy bars with P-BOS=+1 (including those unmatched under E0)
- Controls: RANGE bars
- Covariates: **only** original matching covariates  
  `{session, volatility_regime, trend_bias}`
- Propensity / overlap weights: logistic propensity of treatment vs RANGE on those covariates
  (or equivalent stabilized IPTW within common support)
- **Common support:** discard units with propensity outside [α, 1−α], α pre-registered **0.05**
- Contrast: weighted mean difference on R_8
- Purpose: reduce dependence on ±32-bar exact match while staying on original covariates

### E2 — Time-blocked stratified comparison

- Strata = original block keys: `session × volatility_regime × trend_bias`
- Within each stratum, further **calendar blocks** pre-specified as **contiguous equal-count
  quarters of eligible bars** (same 4-fold partition as H-017 folds 0–3)
- Within each (regime-block × calendar-block) cell with n_treatment≥20 and n_RANGE≥20:
  unweighted mean(R_8 | P-BOS=+1 occupancy) − mean(R_8 | RANGE)
- Aggregate: inverse-variance weighted mean of stratum deltas (or sample-size weighted if IV
  unavailable); report both
- Purpose: compare within regime and time without nearest-neighbor bar matching

### Shared statistical guards (all estimands)

| Guard | Rule |
|-------|------|
| Direction | Sign of Δ relative to H-017 reference (negative on R_8 for P-BOS=+1) |
| Held-out | Last calendar fold (fold 3) direction matches overall for that estimand |
| Permutation | 2000 within-block label shuffles, seed **20260714** (same seed as H-017), on estimand-specific sample |
| Support | Effective n (or ESS for weights) ≥ 80 per arm where applicable; else cell/estimand `INSUFFICIENT` |
| Overlap (E1) | Fraction of P-BOS=+1 treatment retained after common support ≥ 0.50; else severe overlap violation |

**No BH across partitions** — single fixed target. Optional reporting of E0/E1/E2 jointly is
descriptive; success uses the exit classes below.

---

## 6. Exit decision classes

```text
ROBUST
=
effect direction survives all pre-registered estimands (E0, E1, E2)
AND held-out direction survives for each estimand that is support-OK
AND no severe overlap violation (E1)

MATCHING_DEPENDENT
=
effect disappears or reverses under broader-support estimands (E1 and/or E2)
while E0 still shows the H-017 direction

INCONCLUSIVE
=
effective support or overlap is insufficient on critical estimands

PROTOCOL_FAILURE
=
causal alignment, provenance, or frozen-protocol violation
```

---

## 7. Success is not economic

Even `ROBUST` remains **research information only**.  
Does **not** authorize trading, MSIP authority change, CRT change, thresholds, or migration.

---

## 8. Execution gate

```text
FOLLOW_UP_EXECUTION_AUTHORIZED = NO  (at preregistration time)
```

When owner later grants RUN, harness may reuse H-017 panel artifacts where provenance-aligned;
must recompute estimands under this frozen definition without opening new partitions.

---

## 9. Related

| Asset | Path |
|-------|------|
| Parent findings | `docs/research-readiness/h-msip-001-run-findings.md` |
| Parent evidence | `results/research/h_msip_001/H_017_EXPERIMENT_EVIDENCE_V1.json` |
| Owner acceptance | `results/research/h_msip_001/H_017_OWNER_ACCEPTANCE_V1.json` |
| Experiment JSON | `docs/research-readiness/h-msip-002-experiment-definition.json` |
