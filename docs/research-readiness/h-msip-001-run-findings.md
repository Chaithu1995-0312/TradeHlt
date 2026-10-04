# H-MSIP-001 / H-017 Run Findings (maintained)

**Date:** 2026-07-14  
**Owner verdict:** `RESEARCH_SUPPORTIVE_MICRO_EFFECT` (**PRESERVED**)  
**Evidence scope:** **ORIGINAL_±32_BAR_MATCHED_ESTIMAND_ONLY**  
**Generalization:** **NOT_SUPPORTED** (H-018)  
**Thread status:** **SCOPE_CLOSED**  
**Authority:** RESEARCH_ONLY  

---

## Thread closure (2026-07-14)

```text
H-017_RESULT = PRESERVED
H-017_EVIDENCE_SCOPE = ORIGINAL_±32_BAR_MATCHED_ESTIMAND_ONLY
H-017_GENERALIZATION_STATUS = NOT_SUPPORTED
H-017_THREAD_STATUS = SCOPE_CLOSED

H-018_RESULT = ACCEPTED
H-018_VERDICT = MATCHING_DEPENDENT

P-BOS_PLUS_1_OCCUPANCY_WIDE_SIGNAL = NOT_SUPPORTED
```

Closure note: `docs/research-readiness/h-msip-001-h018-thread-closure.md`  
H-018 findings: `docs/research-readiness/h-msip-002-run-findings.md`

**Do not rescue** P-BOS=+1 (window, covariates, horizons, subgroups).  
**Do not** claim economic edge.

---

## Owner acceptance of micro effect (still valid under matched estimand)

```text
ECONOMIC_EDGE_CLAIM = NO
TRADING_AUTHORITY = NO
MSIP_AUTHORITY_CHANGE = NO
CRT_BEHAVIOR_CHANGE = NO
THRESHOLD_RESEARCH = NO
MIGRATION_AUTHORIZED = NO
PRODUCTION_AUTHORITY = NO
FOLLOW_UP_EXECUTION_AUTHORIZED = NO
```

---

## Population & match attrition

| Item | Value |
|------|------:|
| Eligible bars | 47,165 |
| Active occupancy | 13,660 |
| Matched | 7,277 |
| Unmatched | 6,383 |
| Attrition | ≈46.7% |

## Primary result under H-017 protocol (R_h @ h=8)

| Cell | Full success under matched protocol |
|------|-------------------------------------|
| P-BOS level +1 | YES (Δ≈−7.26e−5, p_perm=0.0215, BH+WF) — **matched estimand only** |

## H-018 robustness (accepted MATCHING_DEPENDENT)

| Estimand | Δ | Direction |
|----------|--:|-----------|
| E0 matched | −7.261e−5 | negative (rep) |
| E1 overlap | +2.57e−4 | **reverse** |
| E2 stratified | +1.52e−4 | **reverse** |

## Decision C

Program **remains open**. Next boundary is **MSV-as-a-whole** design/prereg only:  
`docs/research-readiness/h-msip-msv-whole-representation-design-boundary.md`  
**No execution authorized.**
