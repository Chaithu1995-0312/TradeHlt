# Historical Robustness Framework v1 — WFE vs Purged Event CV

**Version:** 1.0  
**Date:** 2026-07-07  
**Status:** REFERENCE (exploratory-only; **no authority** for H-SECONDLOW-004 v0.2 confirmatory)  
**Companions:** `preregistration-H-SECONDLOW-004-v0.2.md` · `prospective-sequential-update-protocol-v1.md` · `preregistration-H-SECONDLOW-006-count-only-exploration-v0.1.md`

---

## 1. Purpose

This document **finishes** the methodological comparison between:

1. **Walk-Forward Evaluation (WFE)** — chronological out-of-sample evaluation of a **fixed** exposure rule  
2. **Purged event-level cross-validation** — k-fold splits with explicit purge/embargo to prevent window overlap leakage  

For SECONDLOW event studies (sparse independent purges, +120m outcome window, 120min spacing).

**Authority ladder:**

| Method | Tier | May unlock H-004 tiers? |
|--------|------|-------------------------|
| Prospective ledger | **Confirmatory** | Yes (per protocol v1.1) |
| Purged event CV (historical) | Exploratory robustness | **No** |
| Walk-forward evaluation (historical) | Exploratory robustness | **No** |
| Full in-sample historical backtest | Forbidden for v0.2 | **No** |

---

## 2. Why “WFO” is the wrong label here

**Walk-Forward Optimization** re-estimates parameters each in-sample window. H-SECONDLOW exposure rules are **frozen** at prereg:

- v0.2: `purge_depth_atr ≥ 1.0`
- R5 (if ever 007): `depth ≥ X OR pre_2h ≤ −1.5`

There is nothing to optimize walk-forward. The correct term is **Walk-Forward Evaluation (WFE)**: apply the same boolean rule on rolling calendar test windows.

If a study **does** optimize thresholds per IS window, it is a **different hypothesis** and must be preregistered as such — not labeled robustness for v0.2.

---

## 3. Event window geometry (leakage model)

Per event at purge time \(t\):

```text
Pre window:   [t − 120m, t)           8 M15 bars
Purge bar:    t                       exposure defined
Post window:  (t, t + 120m]           8 M15 bars → close_disp_atr
```

**Independence rule (detector):** next purge \(t' - t \geq 120\) minutes.

**Leakage risk:** event \(i\)’s post window can overlap event \(j\)’s pre window when spacing is tight (exactly 120 min). Conservative **embargo** for CV purge: treat windows as overlapping if:

```text
overlap(i, j) ⟺ [t_i − 120m, t_i + 120m] ∩ [t_j − 120m, t_j + 120m] ≠ ∅
```

With 120 min purge-to-purge spacing, overlap is limited but **not zero** at the pre/post boundary — purging is still required for rigorous CV.

### Leakage taxonomy (SECONDLOW)

| ID | Failure mode | WFE | Purged CV | Prospective |
|----|--------------|-----|-----------|-------------|
| L1 | Label window overlap across train/test | Manual IS/OOS gap | **Explicit purge** | Real time |
| L2 | Threshold mined on same outcomes | Prereg freeze | Prereg freeze | Prereg freeze |
| L3 | Variant screen (006) → outcome on same events | Forbidden as confirmatory | Forbidden as confirmatory | N/A |
| L4 | Sealed 21 PRE recycled | Excluded | Excluded | Excluded |
| L5 | Discovery window mixed with POST | Calendar split | Block split | POST only |

---

## 4. Walk-Forward Evaluation (WFE)

### 4.1 Variants

| Variant | In-sample | Out-of-sample | Use when |
|---------|-----------|---------------|----------|
| **Rolling** | Fixed calendar length \(W_{IS}\) | Fixed \(W_{OOS}\), advance both | Stable regime length assumed |
| **Expanding** | \(T_0\) → \(t_k\) grows | \((t_k, t_{k+1}]\) | More early data helps stability (descriptive only here) |

**Train window role (fixed rule):** no parameter fit. IS may be used only for **descriptive** stability reports (event rate, session mix). **All outcome estimands reported from OOS events only.**

### 4.2 Algorithm (fixed rule)

```text
INPUT:  events E sorted by purge_time, exposure rule R, calendar windows {(IS_k, OOS_k)}
OUTPUT: per-fold OOS metrics

for each fold k:
    OOS_k_events = { e ∈ E : purge_time(e) ∈ OOS_k }
    apply R → EXPOSED / REFERENCE on OOS_k_events only
    if n_EXPOSED(OOS_k) < n_min: verdict_k = INSUFFICIENT
    else: compute median_diff, bootstrap CI on OOS_k_events
aggregate: weighted by n_EXPOSED across folds with verdict ≠ INSUFFICIENT
```

### 4.3 SECONDLOW power table (empirical, corpus 2026-07-07)

| Universe | n events | n EXPOSED (v0.2) | Notes |
|----------|----------|------------------|-------|
| All independent | 50 | 12 | Includes PRE + discovery |
| PRE + discovery | 36 | 9 | **Not** v0.2 confirmatory |
| POST_DISCOVERY | 14 | 3 | Prospective ledger |
| POST in 2026 only | 14 | 3 | **Single calendar year** |

**Implication:** any multi-fold WFE on POST data today collapses to **one effective OOS block** (May–Jun 2026). Rolling WFE with 6–12 month OOS windows yields **0–1 EXPOSED** per fold → `INSUFFICIENT` under `n_min = 3`.

WFE becomes informative only after **several years** of POST accrual, and still secondary to the prospective ledger.

### 4.4 WFE strengths and weaknesses

| Strengths | Weaknesses |
|-----------|------------|
| Matches live deployment narrative | Mostly empty OOS folds at current n |
| Simple audit story (calendar) | IS window misleading name without optimization |
| Natural alignment with monthly prospective append | Fold length cherry-pick risk unless preregistered |
| Good **timeline sanity check** when years accrue | Double-count if IS/OOS event sets overlap |

---

## 5. Purged event-level cross-validation

### 5.1 Why event-level (not bar-level)

Bar-level purged CV (López de Prado) assumes many overlapping labels on a dense index. SECONDLOW has **~50 points in 2 years** — the unit of analysis is the **purge event**, not each M15 bar.

### 5.2 Algorithm

```text
INPUT:  independent events E = {e_1,…,e_n} sorted by time
        k contiguous time blocks B_1,…,B_k (equal event count or equal calendar span — preregister)
        purge overlap rule, embargo E_min minutes
        exposure rule R, n_min

for fold f in 1..k:
    TEST  = events in B_f
    TRAIN = events in ∪_{j≠f} B_j

    PURGE: remove from TRAIN any e where overlap(window(e), window(t)) for any t ∈ TEST

    EMBARGO: remove from TRAIN any e with purge_time in
             (min_purge(TEST) − E_min, min_purge(TEST))

    # Fixed rule — no training step
    METRIC_f = median_diff(close_disp_atr | R on TEST only)

    if n_EXPOSED(TEST) < n_min: verdict_f = INSUFFICIENT
    else: bootstrap CI on TEST

POOL: combine METRIC_f weighted by n_EXPOSED(TEST), folds with INSUFFICIENT excluded from pooling
```

### 5.3 Choosing k

| k | Pros | Cons (SECONDLOW) |
|---|------|------------------|
| 3 | More power per fold | Only ~4–5 events/fold |
| 5 | Standard ML practice | ~2–3 events/fold on POST → almost all INSUFFICIENT |
| 2 | Coarse pre/post era split | Becomes single chronological split |

**Recommendation:** if historical robustness is run on **full 50 events**, use **k = 3** chronological blocks on PRE+discovery only as **exploratory**; on **POST only**, k ≥ 2 is **not viable** until n_POST ≥ 20+.

### 5.4 Purged CV strengths and weaknesses

| Strengths | Weaknesses |
|-----------|------------|
| Every event appears in exactly one test fold | Block boundaries arbitrary unless preregistered |
| Explicit overlap control (L1) | Does not mimic month-by-month deployment as cleanly as WFE |
| Better than in-sample full backtest | k folds ⇒ k comparisons — report all, no cherry-pick |
| Compatible with fixed rule | Still underpowered at current n |

---

## 6. Head-to-head comparison (complete)

| Criterion | WFE (rolling/expanding) | Purged event k-fold | Prospective ledger |
|-----------|-------------------------|---------------------|--------------------|
| **Primary purpose** | Timeline OOS narrative | Leakage-safe historical replication | **Confirmatory evidence** |
| **Parameter optimization** | Must be **none** (else not v0.2) | None | N/A |
| **Overlap / leakage control** | Requires manual non-overlap | **Built-in purge + embargo** | Forward real time |
| **Uses all events as OOS once** | No (late eras only in late folds) | **Yes** | Accrues forward |
| **Timeline realism** | **High** | Moderate | **Highest** |
| **Power at n_POST=14, n_EXP=3** | **INSUFFICIENT** | **INSUFFICIENT** | Tier 1 WATCH (governed) |
| **Auditability** | Good | Good (if k, purge, embargo fixed) | **Best** |
| **Data snooping risk** | Medium (window sizes) | Medium (k, blocks) | **Lowest** |
| **Fit for v0.2 confirmatory** | **No** | **No** | **Yes** |
| **Fit for 007+ exploratory** | Secondary timeline check | **Primary historical robustness** | Still primary if parallel ledger |

### Verdict

1. **H-SECONDLOW-004 v0.2:** neither WFE nor purged CV on historical outcomes — **prospective-primary** stands.  
2. **Future historical robustness (007+):** **purged event k-fold first**, WFE second as calendar sanity check.  
3. **Never** full in-sample historical outcome backtest as confirmatory after 006 variant screening.

---

## 7. Worked example — POST_DISCOVERY (14 events, v0.2)

**Corpus:** `486cf3616415ff86` · POST events all in **2026-05/06**.

### WFE (expanding, yearly OOS)

| Fold | OOS calendar | n events | n EXPOSED | Verdict |
|------|--------------|----------|-----------|---------|
| 1 | 2026 H1 | 14 | 3 | INSUFFICIENT (n_EXP < 8 for tier; < 3 per fold if split monthly) |

Monthly rolling OOS: each month 0–2 events, 0–1 EXPOSED → all **INSUFFICIENT**.

### Purged 3-fold (POST only — illustrative)

Cannot form 3 contiguous POST blocks with n≥3 events each — **POST universe too small**. Purged CV on POST is **deferred** until n_POST ≥ 20 (rule of thumb).

### Purged 3-fold (full 50 events — **exploratory only**, not v0.2 confirmatory)

| Block | Approx era | Events | EXPOSED | Note |
|-------|------------|--------|---------|------|
| B1 | 2024 | ~15 | ~3 | PRE |
| B2 | 2025 | ~20 | ~5 | PRE |
| B3 | 2026 | ~15 | ~4 | includes POST |

When B3 is TEST, TRAIN purges events whose ±120m windows overlap May–Jun 2026 test purges. **Still exploratory** — v0.2 forbids using PRE outcomes for confirmatory claims.

**Worked example results (k=3 on 50 events)** are available at:
[`results/purged_kfold_worked_example/purged_kfold_50_events_summary.md`](results/purged_kfold_worked_example/purged_kfold_50_events_summary.md)
(full JSON: `purged_kfold_50_events.json` in the same directory). This run is labeled
**EXPLORATORY_ROBUSTNESS_NOT_V02_CONFIRMATORY**. Re-run on the monitoring checkpoint
defined in prospective protocol v1.2 §5.4 when `n_prospective_EXPOSED` first reaches ≥ 6.

---

## 8. Combined protocol (007+ exploratory)

```text
PRIMARY:     prospective ledger → protocol v1.2 dual-track
ROBUSTNESS:  purged k-fold (k, blocks, purge, embargo preregistered)
SANITY:      2-fold expanding WFE on calendar years (report only if n_EXP ≥ n_min)
SYNTHESIS:   if robustness disagrees with prospective → REVIEW, never auto-promote
```

### Aggregation rule (pre-register)

```text
pooled_median_diff = Σ_f w_f · median_f
where w_f = n_EXPOSED_f / Σ n_EXPOSED_f over non-INSUFFICIENT folds only
```

Report **every fold**, including INSUFFICIENT.

---

## 9. Pre-registration checklist (historical robustness appendix)

Attach to a **new** hypothesis ID only:

- [ ] `authority = EXPLORATORY_ROBUSTNESS` (no tier unlock)
- [ ] Exposure rule identical to confirmatory stream (frozen)
- [ ] Endpoint = `close_disp_atr` +120m (same as v0.2)
- [ ] Estimand = median diff + bootstrap (5000, seed 42)
- [ ] `n_min_exposed_per_fold = 3` (below → INSUFFICIENT)
- [ ] Purged CV: `k`, block definition (calendar vs count), purge overlap rule, `embargo_minutes ≥ 120`
- [ ] WFE (optional): rolling vs expanding, `W_IS`, `W_OOS`, calendar anchors
- [ ] Exclusions: sealed 21, discovery window policy, 006-mined variants
- [ ] Forbidden: threshold tuning per fold, switching EXPOSED definition per fold
- [ ] Outputs: `results/<hypothesis>/historical_robustness.json`

---

## 10. Current standing orders (unchanged)

```text
H-SECONDLOW-004 v0.2  →  quiet prospective collection (confirmatory)
H-SECONDLOW-006       →  count + descriptive only on history
Historical WFE/CV     →  not run for v0.2 outcomes; framework ready for 007+ if ever needed
```

---

## 11. References (concepts)

- López de Prado, *Advances in Financial Machine Learning* — purged k-fold, embargo (bar-level; adapted here to event-level)
- Bailey & López de Prado — walk-forward analysis and overfitting in backtests
- SECONDLOW prospective protocol v1.2 — confirmatory authority