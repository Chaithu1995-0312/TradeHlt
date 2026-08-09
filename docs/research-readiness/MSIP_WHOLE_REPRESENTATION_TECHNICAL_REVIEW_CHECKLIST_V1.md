# Technical Review Checklist — MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1

**Purpose:** Independent technical review before protocol freeze.  
**Outcome:** PASS → freeze hash + owner acceptance · FAIL → amend prereg · **no RUN**.

Reviewer: _______________  Date: _______________

## A. Scientific targeting

| # | Check | Pass? |
|---|--------|:-----:|
| A1 | Primary contrast is M2−M1, not M2 alone | |
| A2 | Nested M0/M1/M2 definitions are unambiguous | |
| A3 | Decision C claim is tested (MSV beyond CRT lifecycle) | |
| A4 | H-017/H-018 partition mining is not reopened | |

## B. Representation & exclusions

| # | Check | Pass? |
|---|--------|:-----:|
| B1 | MSV incremental field list complete and WHAT-only | |
| B2 | HOW labels / CRT-private / economic / authority surfaces excluded | |
| B3 | Dedup rule for session/vol/trend between M0 and MSV is clear | |
| B4 | No post-hoc feature selection path exists | |

## C. Outcome & estimand

| # | Check | Pass? |
|---|--------|:-----:|
| C1 | Single primary horizon h=8 and R_h family frozen | |
| C2 | Secondary outcomes cannot drive GLOBAL SUCCESS | |
| C3 | Full eligible population primary (not occupancy-only) is intentional | |
| C4 | Dependence handling (temporal OOS + episode notes) adequate | |

## D. Models & selection

| # | Check | Pass? |
|---|--------|:-----:|
| D1 | Closed family set; no GBM/NN/AutoML in V1 | |
| D2 | Hyperparameter grids closed | |
| D3 | Hyperparams selected on M1 only (no M2 peaking) | |
| D4 | F-LIN is sole primary for GLOBAL SUCCESS | |
| D5 | Nested OOS (outer 5 / inner 3) prevents selection leakage | |

## E. Nulls, controls, ablations

| # | Check | Pass? |
|---|--------|:-----:|
| E1 | Block permutation global null specified | |
| E2 | Negative controls sufficient (y-perm, MSV-perm, time-shift) | |
| E3 | Ablation families pre-listed; single-family dominance rule clear | |
| E4 | Calendar dominance guard present | |

## F. Success / failure / null value

| # | Check | Pass? |
|---|--------|:-----:|
| F1 | GLOBAL SUCCESS is a conjunction (not any-cell success) | |
| F2 | Research-relevance floor explicit and non-economic | |
| F3 | Failure classes cover null modes | |
| F4 | Null-result value plan forces diagnostic attribution | |

## G. Authority & process

| # | Check | Pass? |
|---|--------|:-----:|
| G1 | EXECUTION/IMPLEMENTATION/RUN not granted by this review alone | |
| G2 | H-id assignment deferred until review complete | |
| G3 | Amend-only-before-freeze list is complete | |
| G4 | Artifact schema sufficient for audit | |

## Review verdict

```text
TECHNICAL_REVIEW = PASS | FAIL | PASS_WITH_REQUIRED_AMENDMENTS
AMENDMENTS: ...
REVIEWER_SIGN_OFF: ...
```

**Next after PASS:** compute protocol hash → owner FREEZE acceptance → STOP (no RUN same session).
