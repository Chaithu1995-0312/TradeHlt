# Prospective Sequential Update Protocol v1

**Version:** 1.2  
**Date:** 2026-07-07
**Status:** ACTIVE (appendix — attach to any SECONDLOW prereg using prospective data)  
**Companions:** [`SECONDLOW_Forward_Research_Plan_v1.md`](SECONDLOW_Forward_Research_Plan_v1.md) · [`preregistration-template-H-SECONDLOW-v1.md`](preregistration-template-H-SECONDLOW-v1.md)

---

## 1. Purpose

Pre-committed rules for **sequential belief updating** as new POST_DISCOVERY events
arrive in `data/secondlow_prospective_events.jsonl`. This appendix defines:

- when a starting prior may carry forward from a prior study
- dual-track decision rules (frequentist primary, Bayesian decision-support)
- mandatory audit logging per update batch
- explicit **STOP** and **CONTINUE** conditions

This protocol grants **no production authority**. Tier 3 unlocks shadow-candidate status
only; live/production promotion still requires prospective OOS stability and the
Authority Ladder (§6.5, `CLAUDE.md`).

---

## 2. Applicability

| Use this appendix when | Do not use when |
|---|---|
| Prereg declares `Holdout: prospective only` | Re-analyzing sealed 21 PRE without new prereg |
| Events enter via forward MT5 fetch + detector | Exposure definition differs from any carried prior |
| `minimum_events_for_decision` is set | Depth/regime rescue on archived negative studies |

**Program status (2026-07-07):** SECONDLOW outcome studies remain **PAUSED** until user
approves a new hypothesis prereg that explicitly attaches this appendix.

---

## 3. Data sources (locked)

| Artifact | Role |
|---|---|
| `data/XAUUSD_M15.csv` | Canonical OHLCV only |
| `data/secondlow_prospective_events.jsonl` | Append-only event ledger (one line per new independent event) |
| `data/secondlow_prospective_update_log.jsonl` | Append-only dual-track update snapshots (this protocol) |
| `data/sealed_evaluation_set_v1.json` | **Not** counted toward `n_prospective` for tier gates |

`n_prospective_EXPOSED` = cumulative EXPOSED count among events in the prospective ledger
only, under the **approved** exposure definition for the active hypothesis.

---

## 4. Starting prior (pre-declare one option)

Choose **exactly one** before inspecting any prospective outcome:

### Option A — Fresh skeptical prior (default)

Use when exposure definition is **new or simplified** (recommended for v0.2+).

| Parameter | Value |
|---|---|
| Prior on effect size (EXPOSED − Reference) | Normal(**μ = 0**, **σ = 2.0**) ATR |
| Justification | Mild skepticism: typical small edges near zero |

### Option B — Carry-forward prior (restricted)

Use **only if all** of the following match the archived study exactly:

- Same exposure conditions (field names, thresholds, conjunction logic)
- Same primary endpoint (`close_disp_atr` at +120 min)
- Same primary estimand family (median difference for frequentist track)
- Same detector regression pin

**Starting distribution:** posterior from the archived study, recorded in prereg:

```text
H-SECONDLOW-003 v0.1 carry-forward:
  Normal(μ = -1.08, σ = 1.34) on mean-difference scale (Bayesian track only)
```

The frequentist track **always** recomputes from prospective data only. The Bayesian
track may inherit the archived posterior **only** under Option B or C.

### Option C — Fresh prior on prospective only (hybrid)

Use when exposure is unchanged but you want sealed history to inform Bayes without
mixing sample counts: prior = Option B posterior, but tier gates use
`n_prospective` only (sealed events excluded from n thresholds).

**Prereg must state:** `starting_prior: A | B | C` and the numeric (μ, σ).

---

## 5. Statistical model (Bayesian track)

### 5.1 Batch update (conjugate Normal–Normal)

After each update cycle, let the current belief be Normal(μ₀, σ₀²). From the new
prospective batch compute:

- **μ̂** = mean(EXPOSED) − mean(Reference) within the batch
- **SE** = pooled standard error of the difference (document formula in prereg script)

**Zero-EXPOSED or zero-Reference batches:** Do not advance the Bayesian posterior.
Still append a **null update** snapshot to `secondlow_prospective_update_log.jsonl`
(`bayesian_update_skipped: true`, reason documented) so months without qualifying
EXPOSED events remain auditable. Re-run the full dual-track snapshot on the next batch
where both groups are non-empty.

**Model caveat:** The conjugate Normal–Normal model is an approximation. With very small
batches (< 3 EXPOSED in the batch), interpret updates cautiously until cumulative
`n_prospective_EXPOSED` ≥ 8.

Update:

```text
precision_post = 1/σ₀² + 1/SE²
σ_post = 1 / sqrt(precision_post)
μ_post = (μ₀/σ₀² + μ̂/SE²) / precision_post
```

Report: μ_post, σ_post, P(effect > 0), 95% credible interval (μ_post ± 1.96·σ_post).

### 5.2 Update cadence

| Trigger | Action |
|---|---|
| Every **≥ 3** new prospective events with ≥1 EXPOSED | Run dual-track snapshot |
| Calendar | At most **once per calendar month** unless batch trigger fires |
| `n_prospective_EXPOSED` **first reaches ≥ 6** | Historical robustness checkpoint (§5.4) |
| Manual | User-directed audit (logged) |

### 5.4 Historical robustness checkpoint (monitoring only)

When `n_prospective_EXPOSED` **first reaches ≥ 6** (and again at each subsequent tier
milestone **8** and **15** if not already run at that count), run the purged event k-fold
robustness check using parameters frozen in
[`historical-robustness-framework-v1.md`](historical-robustness-framework-v1.md)
(k=3 contiguous blocks on the canonical 50-event corpus, v0.2 exposure rule, purge ±120m,
embargo 120m, bootstrap median diff seed 42).

**Script:** `scripts/research/secondlow_purged_kfold_worked_example.py`

**Compare:** fold-level median-diff sign stability and bootstrap CIs against the current
v0.2 dual-track snapshot (`secondlow_prospective_update_log.jsonl` — frequentist median
diff + Bayesian μ_post / P(effect > 0)).

**Authority:** monitoring checkpoint only — label output
`EXPLORATORY_ROBUSTNESS_NOT_V02_CONFIRMATORY`. **No** automatic rule changes, tier
upgrades, or exposure-definition amendments. Disagreement between historical folds and
prospective snapshot → log **REVIEW** note; user decides.

### 5.5 Frequentist track (governance primary)

On **all cumulative prospective events** (not sealed PRE):

- Primary estimand: median(EXPOSED) − median(Reference)
- Bootstrap: 5000 resamples, seed **42** (match H-SECONDLOW-003 v0.1 unless prereg changes)
- Report percentile 95% CI on median difference

**Mean vs median:** The Bayesian track uses mean-difference batches; the frequentist
track uses median-difference + bootstrap. This apples-to-oranges pairing is accepted
for v1.1: medians are more robust in small samples on the governance track, while the
conjugate Normal update stays tractable on the Bayes track. A future protocol version
may align both tracks on medians if a reliable Bayesian median model is implemented
(e.g. ABC or non-conjugate bootstrap-Bayes). Both must be reported; **neither alone**
triggers tier promotion.

---

## 6. Dual-track decision rules (pre-committed)

### 6.1 Tier mapping (unchanged from forward plan)

| Tier | n_prospective_EXPOSED | Allowed claim |
|---|---:|---|
| **Tier 1** | < 8 | Descriptive / learning only |
| **Tier 2** | 8–15 | Weak validation — continue prospective collection |
| **Tier 3** | ≥ 15 | Shadow-candidate (internal validation only) |

**Timeline note:** At historical rates of ~15–20 independent events per year — and a
minority meeting any given EXPOSED definition — reaching Tier 2/3 thresholds may require
**multiple years** of prospective collection. This is accepted; the gates are set for
credibility, not speed.

### 6.2 STOP rules (either track may trigger review; both required for ARCHIVE)

| ID | Track | Criterion | Action |
|---|---|---|---|
| **F-STOP** | Frequentist | n_prospective_EXPOSED ≥ **12** AND bootstrap 95% CI **upper bound < 0** | **ARCHIVE** variant — stop prospective outcome collection for this exposure |
| **B-STOP** | Bayesian | n_prospective_EXPOSED ≥ **12** AND P(effect > 0) < **10%** AND μ_post < **−0.5** ATR | **ARCHIVE** (corroboration) |

If F-STOP and B-STOP disagree, status = **REVIEW** — no tier upgrade; user decides.

### 6.3 CONTINUE rules (default while collecting)

| ID | Track | Criterion | Status |
|---|---|---|---|
| **F-WATCH** | Frequentist | n ≥ 8 AND CI crosses zero | Continue collecting |
| **B-WATCH** | Bayesian | P(effect > 0) ∈ **[10%, 60%]** | Continue collecting |

### 6.4 Tier unlock rules (both tracks required)

| Target | Frequentist (F) | Bayesian (B) | Combined gate |
|---|---|---|---|
| **Tier 2** | n ≥ **8** AND CI lower bound > **0** | n ≥ **8** AND P(effect > 0) > **60%** AND σ_post < **1.0** | **F-TIER2 AND B-TIER2** |
| **Tier 3 / Shadow candidate** | n ≥ **15** AND CI lower bound > **+0.3** ATR | n ≥ **15** AND P(effect > 0) > **70%** AND σ_post < **0.8** AND CrI lower bound > **0** | **F-TIER3 AND B-TIER3** |

**Explicit exclusions:**

- Tier unlock never uses sealed 21 events in n or CI computation
- P(effect > 0) > 50% alone is **insufficient** for any tier upgrade
- Shadow-candidate ≠ production promotion

### 6.5 Decision precedence

```text
1. If F-STOP OR B-STOP → ARCHIVE (pending user sign-off on closure note)
2. Else if F-TIER3 AND B-TIER3 → SHADOW_CANDIDATE
3. Else if F-TIER2 AND B-TIER2 → TIER2_CONTINUE
4. Else → WATCH (Tier 1)
```

---

## 7. Audit logging

### 7.1 Event ledger line (`secondlow_prospective_events.jsonl`)

One JSON object per new independent event (append-only):

```json
{
  "purge_time": "2026-06-15T08:45:00",
  "corpus_hash_prefix": "4d73f5cebe33ec91",
  "detector": "secondlow_v1",
  "collected_at": "2026-07-07T12:00:00Z",
  "hypothesis_id": "H-SECONDLOW-___",
  "post_window_complete": true
}
```

Outcome fields (`close_disp_atr`, exposure labels) are added **only** after prereg
approval, via the analysis script — never at collection time.

### 7.2 Update snapshot line (`secondlow_prospective_update_log.jsonl`)

One JSON object per dual-track update:

```json
{
  "update_id": "prospective_update_001",
  "timestamp": "2026-07-07T12:00:00Z",
  "hypothesis_id": "H-SECONDLOW-___",
  "hypothesis_version": "0.2",
  "starting_prior": "A",
  "n_prospective_events": 18,
  "n_prospective_exposed": 6,
  "n_prospective_reference": 12,
  "batch_n_exposed": 2,
  "batch_n_reference": 4,
  "batch_mean_diff": -0.85,
  "batch_se": 1.55,
  "frequentist": {
    "median_diff": -1.10,
    "bootstrap_ci_95": [-3.20, 0.45],
    "n_boot": 5000,
    "seed": 42
  },
  "bayesian": {
    "prior_mu": 0.0,
    "prior_sd": 2.0,
    "posterior_mu": -0.72,
    "posterior_sd": 0.95,
    "p_effect_positive": 0.22,
    "credible_interval_95": [-2.58, 1.14]
  },
  "tier_status": "WATCH",
  "rules_triggered": ["B-WATCH", "F-WATCH"],
  "corpus_hash_prefix": "4d73f5cebe33ec91"
}
```

**Null update** (Bayesian skipped — no EXPOSED or no Reference in batch):

```json
{
  "update_id": "prospective_update_002",
  "timestamp": "2026-08-07T12:00:00Z",
  "hypothesis_id": "H-SECONDLOW-___",
  "n_prospective_events": 21,
  "n_prospective_exposed": 6,
  "bayesian_update_skipped": true,
  "skip_reason": "batch_n_exposed=0",
  "frequentist": {
    "median_diff": -1.10,
    "bootstrap_ci_95": [-3.20, 0.45]
  },
  "tier_status": "WATCH"
}
```

---

## 8. Preregistration checklist (copy into hypothesis doc)

Attach this block to any prospective SECONDLOW prereg:

```markdown
## Sequential Update Protocol (v1.2)

- [ ] Appendix attached: `prospective-sequential-update-protocol-v1.md` (version ≥ 1.2)
- [ ] `starting_prior`: A (fresh) | B (carry-forward) | C (hybrid)
- [ ] If B or C: archived posterior (μ, σ) and exposure parity attested
- [ ] Exposure definition identical to archived study: Yes / No / N/A
- [ ] `minimum_events_for_decision`: ___
- [ ] Update cadence: ≥3 events or monthly (default)
- [ ] Historical robustness checkpoint at n_prospective_EXPOSED ≥ 6 acknowledged (§5.4; monitoring only)
- [ ] STOP rules acknowledged: F-STOP, B-STOP
- [ ] Tier unlock requires BOTH tracks: Yes (mandatory)
- [ ] Log paths: `secondlow_prospective_events.jsonl`, `secondlow_prospective_update_log.jsonl`
```

---

## 9. Illustrative trajectory (not binding)

Hypothetical batches after v0.1 posterior N(−1.08, 1.34²), verified conjugate math:

| Stage | New EXPOSED in batch | Batch effect | μ_post | σ_post | P(>0) | Tier |
|---|---:|---:|---:|---:|---:|---|
| Start | — | — | −1.08 | 1.34 | 21% | Tier 1 (sealed) |
| 1 | +4 | −0.8 | −0.96 | 1.03 | 17% | WATCH |
| 2 | +5 | +0.4 | −0.53 | 0.85 | 27% | WATCH |
| 3 | +8 | −1.2 | −0.75 | 0.69 | 14% | WATCH |
| 4 | +10 | +0.6 | −0.31 | 0.57 | 29% | WATCH |

Even after 27 **hypothetical** new EXPOSED events, P(>0) remains below Tier 2 threshold
(60%). This illustrates why pre-committed gates matter.

---

## 10. Forbidden without new prereg

- Changing prior (μ, σ) after seeing prospective outcomes
- Lowering P(>0) or CI thresholds after a negative batch
- Counting sealed 21 PRE toward `n_prospective`
- Bayesian-only tier unlock (skipping frequentist track)
- Declaring PROMOTE from Tier 3 without separate OOS protocol

---

## Amendment Log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-07-07 | Initial appendix: dual-track rules, starting-prior options, JSONL schemas |
| 1.1 | 2026-07-07 | Review refinements: mean/median note, timeline note, null-update logging, Option B clarity, Normal-model caveat |
| 1.2 | 2026-07-07 | §5.4 historical robustness checkpoint at n_prospective_EXPOSED ≥ 6 (monitoring only; no tier authority) |