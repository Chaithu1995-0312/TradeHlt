# MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1

**Status:** DRAFT — `FREEZE_BLOCKED` · 🅿️ **PARKED_CONTINUE_LATER** (PREP claims registered; Wave A not started)  
**Task class:** EXPLORATORY_RESEARCH_DESIGN_ONLY  
**Hypothesis id:** **NOT_ASSIGNED_UNTIL_PROTOCOL_IS_REVIEW_COMPLETE**  
**Execution authorized:** **NO**  
**Implementation authorized:** **NO**  
**Date:** 2026-07-14  
**Review plane:** [`docs/governance/protocol_review_experiment_plane/`](../governance/protocol_review_experiment_plane/README.md)  

Machine twin: `MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.json`  
Review checklist: `MSIP_WHOLE_REPRESENTATION_TECHNICAL_REVIEW_CHECKLIST_V1.md`  
Parent design boundary: `h-msip-msv-whole-representation-design-boundary.md`  
Prior closed thread: `h-msip-001-h018-thread-closure.md` (H-017/H-018)

---

## 0. Commissioning stamp

```text
NEXT_BOUNDARY = MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1
TASK_CLASS = EXPLORATORY_RESEARCH_DESIGN_ONLY
PRIMARY_QUESTION =
  Does the governed continuous MarketStateVector contain reproducible
  incremental predictive information about future market behavior beyond
  CRT lifecycle state and frozen baseline market controls?
HYPOTHESIS_ID = NOT_ASSIGNED_UNTIL_PROTOCOL_IS_REVIEW_COMPLETE
EXECUTION_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
RUN_AUTHORITY_IN_THIS_SESSION = NO
```

**Immediate action for this document:** independent technical review → freeze → owner acceptance.  
**Not authorized in the same session as acceptance:** RUN, harness implementation, H-id assignment for execution.

---

## 1. Motivation (Decision C)

H-017 produced a protocol-valid **matched-estimand micro residual** for one partition that H-018 showed is **MATCHING_DEPENDENT**. Partition-by-partition testing risks a feature-mining loop.

This preregistration tests the **representation as a whole** via nested information sets, with primary contrast **M2 − M1** (MSV incremental to CRT lifecycle + baselines), not “does M2 predict returns in isolation.”

---

## 2. Nested information sets (forced)

```text
M0 = BASELINE MARKET CONTROLS
M1 = M0 + CRT LIFECYCLE OBSERVATIONS
M2 = M1 + GOVERNED MARKETSTATEVECTOR
```

| Set | Contents (frozen) | Forbidden additions |
|-----|-------------------|---------------------|
| **M0** | Session (int 0/1/2), volatility_regime (int 0/1/2), trend_bias (int −1/0/1), hour_of_day (int 0–23), calendar-fold id as **covariate only if used as block not feature** (see §7) | Continuous free cutpoints; HOW labels; any MSV field |
| **M1** | M0 + CRT lifecycle observations: `crt_state` one-hot over 9 states; `occupancy_active` (bool); `candidate_episode_age` (bars since episode start, 0 if none); `log1p(episode_duration)` of current episode if active else 0; `bars_since_range_entry` if trackable else omit with missingness rule | CRT-private memory dumps (range refs, sweep_event objects, SL/TP, trade journals); EngineRunner fusion scores |
| **M2** | M1 + **governed MSV WHAT fields only** (§3) | HOW labels; crt_phase as identity of other dims; economic outputs; authority surfaces |

**Primary scientific contrast:**

```text
PRIMARY CONTRAST = M2 − M1
```

Secondary (descriptive only, not success): M1 − M0 (does CRT lifecycle add beyond market baselines?).

---

## 3. Eligible MSV dimensions and encodings (frozen)

Source of authority: `MARKET_STATE_VECTOR_SCHEMA_V1` + H-017 observational emission (COMPLETE provenance only).

### 3.1 Included in M2 (WHAT only)

| Family | Fields | Encoding |
|--------|--------|----------|
| Structure | higher_high, lower_low, break_of_structure, liquidity_sweep, sweep_detected | as emitted int; treat as categorical or integer features (no free binning) |
| Liquidity | liquidity_distance, liquidity_pressure_score | float32; standardize **within train fold only** (z-score) |
| Volatility | volatility_regime, atr, volatility_ratio | regime int; atr/ratio float z-score within train fold |
| Session | session, hour_of_day | int (also in M0 — **dedupe**: appear once in joint design matrix; M2 does not double-count) |
| Trend | trend_strength, trend_bias, ema_fast, ema_slow | bias int; others float z-score train-fold |
| Candle quality | body_ratio, body_size, wick_size | float z-score train-fold |

**Dedup rule:** Fields present in both M0 and MSV (session, volatility_regime, trend_bias, hour_of_day) enter the design matrix **once**. M2’s incremental block is the **set difference** of MSV WHAT fields not in M0/M1, plus any MSV fields already in M0 only if review requires explicit redundancy ablations (default: no double columns).

**Incremental MSV block for M2−M1 (default freeze):**

```text
structure: higher_high, lower_low, break_of_structure, liquidity_sweep, sweep_detected
liquidity: liquidity_distance, liquidity_pressure_score
volatility: atr, volatility_ratio   # regime already in M0
trend: trend_strength, ema_fast, ema_slow   # trend_bias already in M0
candle: body_ratio, body_size, wick_size
```

### 3.2 Excluded (hard)

| Class | Examples |
|-------|----------|
| HOW labels | structure_label, liquidity_band_label, volatility_band_label, session_policy_label, trend_band_label, candle_quality_label |
| Observational join only | crt_phase_observation as MSV identity feature of other dims (lifecycle already in M1) |
| CRT-private memory | active_range, sweep_event objects, pending_*, active_trade, SL/TP, journals |
| Economic outputs | expectancy, PnL, trade counts as features |
| Authority surfaces | fusion weights, decision scores, promotion flags |
| Post-hoc features | any field not listed in §3.1 |

---

## 4. Population and unit of analysis

| Item | Freeze |
|------|--------|
| Corpus | Phase-1 XAUUSD M15, sha256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Unit | **Bar** with COMPLETE MarketStateVector + CRT observation + valid forward horizon |
| Occupancy filter | **None for primary** — full eligible bar population (avoids H-017 occupancy-only estimand confusion). Optional **pre-registered sensitivity** (not success): occupancy-active subset only |
| Episode/bar dependence | Cluster-robust or block bootstrap at **candidate_episode_id** when non-null else bar_index singleton; OOS splits are temporal (§7) so leakage is primarily blocked by time |

---

## 5. Primary outcome and horizon (single)

| Item | Freeze |
|------|--------|
| Primary outcome family | Simple forward return `R_h = close[t+h]/close[t] − 1` |
| Primary horizon | **h = 8** (M15 → 2h) — same as H-017 primary for continuity |
| Secondary (report only; not in success conjunction) | R_h at {1,4,16,32}; optional MFE/MAE at {8,16} |
| Target transform | None for primary (raw R_8). Winsorize at train-fold 0.1%/99.9% **only if** review accepts; default **no winsorize** until review |

**Not primary:** classification of sign(R), trade PnL, expectancy, or costed returns (avoids conflating prediction with economics).

---

## 6. Model families and hyperparameter spaces (closed)

Only these families. **No** AutoML, stacking of winners, or post-hoc family addition.

| Family id | Model | Hyperparameter space (closed grid) | Capacity intent |
|-----------|-------|--------------------------------------|-----------------|
| F-LIN | Ridge regression | `alpha ∈ {0.1, 1.0, 10.0, 100.0}` | linear baseline |
| F-ENET | Elastic net | `alpha ∈ {0.1, 1.0, 10.0}`, `l1_ratio ∈ {0.2, 0.5, 0.8}` | sparse linear |
| F-TREE | Decision tree regressor | `max_depth ∈ {2, 3, 4}`, `min_samples_leaf ∈ {200, 500}` | shallow nonlinear |

**Forbidden:** random forests / gradient boosting / neural nets **in V1** (capacity explosion; reopen only via new prereg version).

**Fitting:** separate model per information set M0/M1/M2 with **identical** family and nested selection procedure.

---

## 7. Nested temporal OOS and model selection

### 7.1 Outer evaluation (final, frozen)

- **5 contiguous temporal folds** by eligible bar order (equal count).  
- Fold k trains on all bars strictly before fold k’s start; evaluates on fold k.  
- **Primary held-out metric:** mean outer-fold **ΔMSE** = MSE(M1) − MSE(M2) on R_8 (positive ⇒ M2 better).  
  Also report **ΔMAE** as secondary.  
- **Seed aggregation:** 5 seeds `{0,1,2,3,4}` for any stochastic path (tree split tie-break); report **median** outer ΔMSE across seeds as the primary aggregate; IQR as stability.

### 7.2 Inner selection (must not use outer test)

- Within each outer train block: **3 contiguous inner folds** (time-ordered).  
- Select hyperparameters by **inner mean ΔMSE(M2−M1)** if comparing M1 vs M2 for capacity fairness **within family**, else by inner MSE of that M-set alone then apply fixed hyperparams to all M-sets (freeze: **shared hyperparams** chosen by minimizing inner MSE on **M1**, then apply same hyperparams to M0/M1/M2 — prevents M2-specific hyperparameter peaking).

**Frozen selection rule (V1):**

```text
For each family F:
  1. On outer-train, use inner CV to pick hyperparameters of F that minimize MSE(M1).
  2. Fit F under those hyperparameters separately on M0, M1, M2 using full outer-train.
  3. Evaluate MSE on outer-test for M0, M1, M2.
  4. Record Δ = MSE(M1) − MSE(M2) on outer-test.
```

### 7.3 Primary model for GLOBAL SUCCESS

Among families, **do not** pick the best post-hoc for success.  
**Frozen:** GLOBAL SUCCESS requires the **pre-registered primary family F-LIN** to satisfy the success conjunction.  
F-ENET and F-TREE are **confirmatory** (must not reverse the qualitative M2−M1 story without flagging `FAMILY_DISAGREEMENT`; disagreement is not automatic failure if F-LIN passes, but is reported).

---

## 8. Global null and multiplicity

| Item | Freeze |
|------|--------|
| Global null | H₀: median_seed outer ΔMSE(M2−M1) ≤ 0 for F-LIN |
| Test | Block-permutation: permute **R_8** within outer-train calendar months, recompute full nested procedure **B = 200** times (seed 20260714); one-sided p = share of null Δ ≥ observed Δ |
| Multiplicity | Single primary contrast (F-LIN M2−M1). Secondary families/horizons/ablations reported with **descriptive** BH q=0.10 within secondary table only — **not** required for GLOBAL SUCCESS |
| Calendar dominance | Max absolute contribution of any calendar year-month to total outer-test residual sum of squares reduction &lt; 50% (same spirit as H-017 spike guard) |

---

## 9. Negative controls (must fail to reproduce increment)

All use same nested OOS skeleton; success requires **none** of these produce ΔMSE(M2−M1) ≥ primary observed Δ on F-LIN:

| ID | Control |
|----|---------|
| NC-YPERM | Permute R_8 globally within train (breaks y–X link) |
| NC-MSVPERM | Permute MSV incremental block rows within train (breaks MSV alignment; keep M0/M1) |
| NC-TIMESHIFT | Shift MSV incremental block forward by +8 bars (lookahead-style misalignment control inverted: uses past MSV for future — actually shift features **backward** by 8 so features are from t−8; tests stale MSV) |
| NC-CRTONLY | M2' = M1 (zero MSV columns) — Δ must be ≈ 0 by construction (sanity) |

**Pass condition for negative controls:** primary Δ exceeds the 95th percentile of NC-YPERM and NC-MSVPERM null distributions **or** formal p&lt;0.05 under §8 block-permutation (freeze: use §8 as formal; NC tables diagnostic).

---

## 10. Ablations (dimension family)

Pre-listed only. Fit M2 with one family removed; report Δ vs M1.

| Ablation id | Remove from incremental MSV block |
|-------------|-----------------------------------|
| A-STRUCT | structure fields |
| A-LIQ | liquidity fields |
| A-VOL | atr, volatility_ratio |
| A-TREND | trend_strength, ema_fast, ema_slow |
| A-CANDLE | body_ratio, body_size, wick_size |

**Success rule:** “No single MSV dimension family is required for all observed gain” means:

```text
For every ablation A-*:
  ΔMSE(M1 → M2_without_A) > 0
  OR  ΔMSE(M1 → M2_without_A) ≥ 0.5 × ΔMSE(M1 → M2_full)
```

i.e. full gain is not entirely concentrated in one family (if one ablation kills ≥50% of gain **and** flips sign of remainder, flag `SINGLE_FAMILY_DOMINANCE` → fails that success clause).

---

## 11. Missingness, support, standardization

| Rule | Freeze |
|------|--------|
| Eligibility | COMPLETE MSV + CRT observed + t+h exists |
| Missing feature | If any M2 incremental field missing → bar **excluded** (not imputed) |
| Min outer-test n per fold | ≥ 500 eligible bars else fold `INSUFFICIENT` |
| Min total eligible | ≥ 10,000 else experiment `INCONCLUSIVE_SUPPORT` |
| Standardization | Continuous features: mean/std on **outer-train only**, apply to inner/test |

---

## 12. Minimum research-relevance floor

Not economic expectancy. Predictive floor:

```text
median_seed outer ΔMSE(M2−M1) / MSE(M1)  ≥  0.005
```

i.e. **≥ 0.5% relative MSE reduction** on R_8 for F-LIN.  
(Review may amend this floor **before freeze**; cannot change after any outcome inspection.)

Also report absolute ΔMSE and equivalent R² increment for interpretation.

---

## 13. GLOBAL SUCCESS conjunction (representation-level)

**All** required:

```text
GLOBAL SUCCESS

1. M2 outperforms M1 on primary held-out metric
   (median_seed outer ΔMSE(M2−M1) > 0 for F-LIN)

2. Increment survives nested temporal OOS
   (strictly: all outer folds with sufficient n have ΔMSE ≥ 0,
    OR ≥ 4 of 5 folds with the failing fold’s |Δ| ≤ 0.5× median —
    FREEZE for review: prefer strict ≥4/5 non-negative folds)

3. Increment survives pre-registered seed aggregation
   (median over seeds > 0; at least 4/5 seeds > 0)

4. Negative controls fail to reproduce the increment
   (§8 block-permutation p < 0.05 one-sided for F-LIN)

5. Global null rejected under frozen multiplicity rule
   (same as 4 for V1 primary)

6. No single calendar period dominates
   (max month share of RSS reduction < 0.50)

7. No single MSV dimension family required for all observed gain
   (§10 ablation rule)

8. Effect exceeds pre-registered minimum research-relevance floor
   (§12 relative MSE ≥ 0.005)

9. Provenance / causal alignment / authority gates pass
   (COMPLETE MSV; CRT read-only; no HOW; no lookahead; task_class research-only)
```

**Failure if any clause fails** → not GLOBAL SUCCESS (use failure classes §14).

**Forbidden success modes:** one model family only (except F-LIN is primary by design); one seed; one fold; one ablation surviving alone; one MSV dimension cherry-pick.

---

## 14. Failure / result classes

| Class | Meaning |
|-------|---------|
| `REPRESENTATION_SUPPORTIVE` | GLOBAL SUCCESS conjunction true |
| `NO_INCREMENTAL_INFORMATION` | M2 ≉ better than M1; negative controls and support OK |
| `INSUFFICIENT_SAMPLE` | support floors fail |
| `UNSTABLE_TEMPORAL` | median Δ>0 but fold/seed stability fails |
| `MODEL_CAPACITY_LIMIT` | F-LIN fails floor but F-TREE passes all other clauses **and** review pre-approved capacity claim — **default V1: do not auto-promote**; classify as `FAMILY_DISAGREEMENT_NO_PRIMARY` |
| `REPRESENTATION_REDUNDANCY` | M2≈M1; ablations show MSV collinear with M1; diagnostics say redundancy |
| `PROTOCOL_FAILURE` | provenance, leakage, HOW contamination, authority violation, ordering violation |
| `INCONCLUSIVE` | residual cases |

---

## 15. Null-result value plan

If **M2 ≈ M1** (or GLOBAL SUCCESS fails), the report **must** fill:

| Diagnostic | How measured |
|------------|----------------|
| No incremental information | ΔMSE≈0; NC not exceeded; ablations flat |
| Insufficient sample | support floors; ESS if weighted (N/A default) |
| Unstable temporal generalization | fold sign flips; calendar dominance |
| Model-capacity limitation | F-TREE/F-ENET vs F-LIN gap (descriptive) |
| Representation redundancy | high VIF / correlation of MSV block with M1; ablation A-* ≈ full |
| Protocol failure | gate checklist fail |

This preserves Decision C learning even under null.

---

## 16. Artifact schema (when RUN later authorized)

```text
results/research/msip_whole_v1/
  RUN_AUTHORIZATION.json
  PROTOCOL_HASH.txt
  panel_manifest.json
  M0_M1_M2_feature_lists.json
  outer_fold_metrics.json
  seed_aggregation.json
  block_permutation_null.json
  negative_controls.json
  ablations.json
  calendar_dominance.json
  GLOBAL_SUCCESS_checklist.json
  EVIDENCE_V1.json
  CRITIQUE.md
  FINDINGS.md
  DECISION_LEDGER_ENTRY.json
```

---

## 17. Authority and stop boundaries

```text
TASK_CLASS = EXPLORATORY_RESEARCH_DESIGN_ONLY (until RUN grant)
AUTHORITY = RESEARCH_ONLY even after REPRESENTATION_SUPPORTIVE
CRT_BEHAVIOR_CHANGE = NO
MSIP_AUTHORITY_CHANGE = NO
THRESHOLD_RESEARCH = NO
MIGRATION_AUTHORIZED = NO
PRODUCTION_AUTHORITY = NO
ECONOMIC_EDGE_CLAIM = NO
```

**This session stop:**

```text
COMMISSION prereg V1
  → independent technical review
  → freeze protocol hash
  → owner acceptance of FREEZE
  → STOP
  → (later session) assign H-id + RUN only if explicitly granted
```

---

## 18. Items fixed for review (amend only before freeze)

Reviewers may amend **before any outcome-bearing run**:

1. Outer fold non-negative rule strictness (§13.2)  
2. Relative MSE floor 0.005 (§12)  
3. B=200 vs 500 permutations  
4. Winsorize yes/no  
5. Occupancy-active sensitivity as secondary  
6. Whether F-TREE may ever enter success conjunction (default no)

**Cannot amend after freeze:** M0/M1/M2 definitions, primary h=8, family list, exclusion list, GLOBAL SUCCESS conjunction structure, null-result value plan.

---

## 19. Related

| Artifact | Path |
|----------|------|
| Closed partition thread | `docs/research-readiness/h-msip-001-h018-thread-closure.md` |
| Design boundary pointer | `docs/research-readiness/h-msip-msv-whole-representation-design-boundary.md` |
| MSV schema | `docs/governance/msip_shadow_design_v1/MARKET_STATE_VECTOR_SCHEMA_V1.json` |
| Decision C posture | `docs/governance/msip_shadow_design_v1/MSIP_DECISION_C_FROZEN_POSTURE_V1.md` |
