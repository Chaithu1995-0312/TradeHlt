# SECONDLOW Forward Research Plan v1

**Version:** 1.0  
**Date:** 2026-07-06  
**Status:** ACTIVE  
**Companions:** [`CORPUS_POLICY.md`](CORPUS_POLICY.md) · [`SECONDLOW_RESEARCH_DATA_POLICY.md`](SECONDLOW_RESEARCH_DATA_POLICY.md)

---

## 1. Guiding Principles

- Never develop thresholds or exposure definitions by looking at outcomes first.
- Accept the low event rate (~15–20 independent events per year) as a hard constraint.
- Descriptive analysis on historical data is allowed and useful; outcome-linked testing requires pre-registration.
- Regime and depth adjustments are **design choices**, not rescue tools after negative results.
- Prospective data is the primary source of credible evidence. Historical data is for learning and infrastructure.

---

## 2. Event Rate Reality Check (Non-Negotiable)

- Assume **~15–20 independent second-low purge events per year** on `data/XAUUSD_M15.csv`.
- Any new hypothesis must be designed for this frequency.
- Hypotheses requiring 30+ EXPOSED events for a decision are unrealistic in the short-to-medium term.

**Required prereg field:** `minimum_events_for_decision` — if expected EXPOSED count is below this, label the study **Descriptive / Learning Only** from the start.

---

## 3. Hypothesis Design Rules

| Rule | Avoid | Require |
|---|---|---|
| Complexity | Conjunctions (A ∧ B) as default | Single-condition first; add conditions only with justification |
| Thresholds | Chosen after seeing data | Theory, round numbers, or external reference **before** inspection |
| Regime | Post-hoc normalizer after negative result | Pre-declare: **filter**, **normalizer**, or **interaction** |
| Endpoint | Mid-process changes | One locked primary endpoint before any outcome inspection |

**Required prereg question:**

> What is the simplest version of this idea, and why am I not testing that first?

---

## 4. Pre-Registration Requirements

Every new hypothesis must include:

| Field | Required |
|---|---|
| Exposure definition + justification | Yes |
| Single primary endpoint | Yes |
| Expected EXPOSED events (from historical rate) | Yes |
| `minimum_events_for_decision` | Yes |
| Holdout strategy (internal split or prospective only) | Yes |
| Decision rules including explicit **stop** conditions | Yes |
| Corpus hash + detector version pinned | Yes |
| `risk_of_overfitting` (Low / Medium / High) + one-sentence justification | Yes |

### Data Use Declaration (top of every prereg)

```text
Descriptive use on historical 36 events:     ALLOWED (no outcomes on sealed 21 without unseal)
Outcome analysis on sealed 21 PRE:           REQUIRES explicit unsealing approval per hypothesis
Outcome analysis on prospective ledger:      PREFERRED PATH
```

---

## 5. Data Handling Rules

| Artifact | Role |
|---|---|
| `data/XAUUSD_M15.csv` | Canonical OHLCV only |
| 36 historical independent events | Descriptive work only |
| `data/sealed_evaluation_set_v1.json` | 21 PRE timestamps — sealed for outcomes unless hypothesis-specific unseal |
| `data/secondlow_prospective_events.jsonl` | Append-only prospective event ledger |
| `data/XAUUSD_M15_1year.xlsx` | Detector regression fixture only |

---

## 6. Decision Framework (Tiered)

Replace universal hard gates (e.g. “≥12 EXPOSED”) with:

| Tier | Expected EXPOSED | Allowed claims | Example decision |
|---|---:|---|---|
| **Tier 1** | < 8 | Descriptive only | “Pattern worth monitoring” |
| **Tier 2** | 8–15 | Weak internal validation | “Worth collecting prospective data” |
| **Tier 3** | 15+ | Stronger internal validation | “Candidate for live shadow testing” |

Prospective OOS remains required before any production authority (per Authority Ladder).

---

## 7. Regime and Depth

- **Regime:** prefer **filter** (e.g. compressed vol only) over normalizer unless strongly justified.
- **Depth:** keep simple; limit alternative metrics per study; no post-hoc tweaks after negative results.
- New depth/regime variants → **fresh hypothesis ID + prereg**, not amendments to archived studies.

---

## 8. Infrastructure (Maintain)

- [`src/research/secondlow_v1/`](../../src/research/secondlow_v1/) — detector module
- [`tests/research/test_secondlow_v1_detector_regression.py`](../../tests/research/test_secondlow_v1_detector_regression.py)
- [`tests/research/test_secondlow_sealed_evaluation_set.py`](../../tests/research/test_secondlow_sealed_evaluation_set.py)
- Corpus + research data policies (this package)

**After every study:** append a one-page **Study Closure Note** (see [`study_closures/`](study_closures/)).

---

## 9. Prioritized Next Steps

| Priority | Action | Reason |
|---|---|---|
| **Highest** | Keep pause on new SECONDLOW outcome studies | Historical descriptive work complete |
| **High** | Populate `secondlow_prospective_events.jsonl` via forward MT5 fetch | Only clean new evidence |
| **Medium** | Draft minimal single-condition hypothesis template | Models good design |
| **Low** | New depth/regime ideas | Only after prospective data exists |

---

## 10. Minimal Hypothesis Template (Pointer)

See [`preregistration-template-H-SECONDLOW-v1.md`](preregistration-template-H-SECONDLOW-v1.md) for blank fields including tier, risk of overfitting, and data use declaration.

**Prospective sequential updates:** attach [`prospective-sequential-update-protocol-v1.md`](prospective-sequential-update-protocol-v1.md) (dual-track decision rules, starting-prior options, JSONL audit schema).

---

## Amendment Log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-07-06 | Initial forward plan incorporating tiered decisions, overfitting risk field, closure notes |