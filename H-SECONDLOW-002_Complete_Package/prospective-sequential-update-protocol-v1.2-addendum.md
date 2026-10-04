# Prospective Sequential Update Protocol — v1.2 Addendum

**Version:** 1.2 (addendum to v1.1)  
**Date:** 2026-07-07  
**Status:** ACTIVE (shadow Bayes track — tier gates unchanged)  
**Parent:** [`prospective-sequential-update-protocol-v1.md`](prospective-sequential-update-protocol-v1.md) (v1.2; tier gates unchanged)

---

## 1. What v1.2 adds

v1.1 locks the **Normal–Normal conjugate** Bayes track for governance tier rules (§6.2).
v1.2 adds an optional **Student-t likelihood** shadow track for the same batch mean
difference — reported alongside v1.1, never alone for tier unlock.

| Track | Model | Tier authority |
|---|---|---|
| **Frequentist** | Bootstrap median diff (seed 42, 5000) | Primary (unchanged) |
| **Bayes v1.1** | Normal prior × Normal likelihood | **Governance Bayes** (unchanged) |
| **Bayes v1.2** | Normal prior × Student-t likelihood | **Decision-support only** |

---

## 2. Student-t specification (frozen)

**Prior:** unchanged from prereg `starting_prior` (H-SECONDLOW-004 uses **A**: N(0, 2²)).

**Likelihood:** batch mean difference μ̂ with pooled SE (same as v1.1 §5.1):

```text
μ̂ | δ ~ Student-t(ν, loc=δ, scale=SE)
```

**Default ν (df):** **4** — pre-committed; change only via new protocol version + prereg.

**Posterior:** numerical grid integration on δ ∈ [−12, +12] ATR, 12,001 points.
Report: μ_post, σ_post, P(δ > 0), 95% credible interval (2.5% / 97.5% grid quantiles).

**Script:** `scripts/research/run_h_secondlow_004_prospective_update_student_t.py`

**Zero-EXPOSED / zero-Reference batches:** same null-update rule as v1.1 §5.1.

---

## 3. Logging (v1.2 snapshot shape)

Append to `data/secondlow_prospective_update_log.jsonl`. Required fields:

| Field | Value |
|---|---|
| `protocol_appendix` | `"v1.2-exploratory"` |
| `bayesian_normal_v11` | Full v1.1 conjugate snapshot (`governance_primary: true`) |
| `bayesian` | Student-t snapshot (`bayesian_model: "student_t"`) |
| `tier_governance_track` | `"normal_conjugate_v11"` |
| `tier_status` / `rules_triggered` | Evaluated from **v1.1 Normal only** |

Frequentist block unchanged from v1.1.

---

## 4. When Student-t becomes the default Bayes track

Student-t does **not** replace Normal for tier gates until **all** of:

1. **n_prospective_EXPOSED ≥ 8** under the active hypothesis exposure rule.
2. This addendum is promoted from `exploratory` to `governance` in a **new prereg**
   (or hypothesis amendment explicitly attaching v1.2 as mandatory).
3. At least **two** logged updates show material disagreement is possible in principle
   (defined: \|μ_post,t − μ_post,normal\| > 0.15 ATR **or**
   \|P_t(>0) − P_normal(>0)\| > 0.05) — if never observed, promotion is **declined**
   as complexity without governance value.

Until then: v1.1 Normal conjugate remains the **only** Bayes input to §6.2 STOP/TIER rules.

**Empirical note (2026-07-07, n=3 EXPOSED):** first paired run showed negligible
difference (μ_post −0.083 vs −0.080; P(>0) 47.8% vs 47.7%). No promotion trigger.

---

## 5. What v1.2 does **not** include

- **Mildly informative priors** (e.g. N(0, 1²), N(−0.5, 1²)) — forbidden without new
  prereg per parent §10; not bundled in v1.2.
- **Tier rule changes** — thresholds unchanged.
- **ABC / SMC-ABC** — deferred per method investment ladder (parent companion docs).

---

## 6. Prereg checklist addition (copy when attaching v1.2)

```markdown
## Sequential Update Protocol (v1.2 addendum)

- [ ] Parent v1.1 attached and tier gates acknowledged
- [ ] v1.2 addendum attached: `prospective-sequential-update-protocol-v1.2-addendum.md`
- [ ] Student-t df = 4 (default) or explicit override pre-committed
- [ ] Tier gates use Normal v1.1 only until §4 promotion criteria met
- [ ] Log includes both `bayesian_normal_v11` and `bayesian` (student_t)
```

---

## 7. Update cadence (unchanged)

Same as parent v1.2 §5.2: run when ≥3 new prospective events with ≥1 EXPOSED, or monthly
audit. At `n_prospective_EXPOSED ≥ 6`, also run the §5.4 historical robustness checkpoint
(purged k-fold; monitoring only). v1.2 Student-t may be run in the **same** session as v1.1
Normal conjugate (single script emits both).