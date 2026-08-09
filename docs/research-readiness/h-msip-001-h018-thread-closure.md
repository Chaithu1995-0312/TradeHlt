# H-017 / H-018 Thread Closure

**Date:** 2026-07-14  
**Authority:** RESEARCH_ONLY  

---

## Owner decisions (accepted)

```text
H-018_RESULT = ACCEPTED
H-018_VERDICT = MATCHING_DEPENDENT

H-017_RESULT = PRESERVED
H-017_EVIDENCE_SCOPE = ORIGINAL_±32_BAR_MATCHED_ESTIMAND_ONLY
H-017_GENERALIZATION_STATUS = NOT_SUPPORTED
H-017_THREAD_STATUS = SCOPE_CLOSED

P-BOS_PLUS_1_OCCUPANCY_WIDE_SIGNAL = NOT_SUPPORTED

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

## What is preserved

| Item | Status |
|------|--------|
| H-017 under frozen ±32-bar matched protocol | **Valid research result** (micro residual, one cell) |
| Guard stack integrity (match, perm, BH, WF, calendar, CRT_STATE_ONLY) | **Held** |
| Decision C architecture / observational MSIP layer | **Unchanged** |

## What is not supported

| Claim | Status |
|-------|--------|
| P-BOS=+1 occupancy-wide residual | **NOT_SUPPORTED** |
| Generalization beyond matched estimand | **NOT_SUPPORTED** |
| Economic / trading / MSIP authority | **NO** |

## Decisive evidence (H-018)

```text
E0  ORIGINAL MATCHED ESTIMAND     −7.261e−5   (reproduces H-017)
E1  BROADER OVERLAP ESTIMAND      +2.57e−4    (sign reverse; retained 89.4%; ESS≈3481; no severe overlap)
E2  TIME-BLOCKED STRATIFIED       +1.52e−4    (sign reverse; independent construction)
```

Composition diagnostics did **not** flag strong pre-registered selectivity — so the issue is not
obvious covariate imbalance. **Local temporal matching and broader-support estimands answer
different scientific questions.**

## Explicitly not next

- Rescue P-BOS=+1 (window, covariates, horizons, subgroups)  
- One-by-one MSV partition mining  
- Tradeability of −0.73 bps  

---

## Decision C program (remains open)

```text
H-017 / H-018 THREAD  →  CLOSED

DECISION C PROGRAM    →  REMAINS OPEN

NEXT SCIENTIFIC QUESTION (design/prereg only; no execution):
  Does the continuous governed MarketStateVector contain reproducible
  incremental information about future market behavior beyond CRT
  lifecycle state and baseline market controls?
```

Design placeholder (not authorized for run):  
`docs/research-readiness/h-msip-msv-whole-representation-design-boundary.md`
