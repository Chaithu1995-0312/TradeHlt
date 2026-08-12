# H-SECONDLOW-___ v0.1 — Pre-Registration Template

**Status:** DRAFT  
**Date:** YYYY-MM-DD  
**Hypothesis ID:** H-SECONDLOW-___

---

## Data Use Declaration

- [ ] Descriptive use on historical 36 events: ALLOWED
- [ ] Outcome analysis on sealed 21 PRE: requires explicit unsealing approval
- [ ] Outcome analysis on prospective ledger: PREFERRED

**Corpus:** `data/XAUUSD_M15.csv` · hash `________`  
**Detector:** `src/research/secondlow_v1/detector.py` (regression-pinned)

---

## Simplest Version First

> What is the simplest version of this idea, and why am I not testing that first?

---

## Research Question

---

## Exposure (Single Condition Preferred)

**EXPOSED if:**  
**Reference:** all other events in analysis universe

**Threshold justification (pre-data):**

---

## Primary Endpoint (one only)

---

## Primary Estimand

---

## Event Rate Planning

| Field | Value |
|---|---|
| Historical independent rate/year | ~15–20 |
| Expected EXPOSED in this study | |
| `minimum_events_for_decision` | |
| Study tier if below minimum | Tier 1 — Descriptive / Learning Only |

---

## Regime / Depth Role (pre-declared)

- [ ] No regime adjustment
- [ ] Regime as **filter** (specify):
- [ ] Regime as normalizer (justify):
- [ ] Regime as interaction (justify):

---

## Holdout Strategy

- [ ] Prospective only (`secondlow_prospective_events.jsonl`)
- [ ] Internal split (seed + manifest update before outcomes)

---

## Decision Rules (Tiered)

For prospective studies, attach **[`prospective-sequential-update-protocol-v1.md`](prospective-sequential-update-protocol-v1.md)** and complete the checklist in §8.

| Rule | Criterion |
|---|---|
| Stop | F-STOP and/or B-STOP per protocol §6.2 |
| Continue collecting | WATCH (F-WATCH / B-WATCH) per protocol §6.3 |
| Shadow candidate | F-TIER3 **and** B-TIER3 per protocol §6.4 |

**Starting prior (prospective Bayes track):** A (fresh N(0,2²)) · B (carry-forward) · C (hybrid) — declare before outcomes.

---

## Risk of Overfitting

**Level:** Low / Medium / High  
**Justification (one sentence):**

---

## Approval Gate

Status advances to APPROVED only on explicit user sign-off.