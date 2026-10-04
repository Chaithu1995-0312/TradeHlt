# Visual CRT × SEM-028 prior holdout (MC-VCRTPRIOR-XAUUSD-M15-V1)

Point-in-time. Sealed before holdout `y`. Not current truth — F-096 is.

**Object:** SEM-032. Sparse SIGNAL = SEM-012 Visual CRT Arm A (displacement-close) and Arm B (retest-close) from `run_arm` (same duplicate rule as F-081). Prior = SEM-028 / FM-054 agree. `y` = clean_labels `y_mfe_r` / `y_time_to_mfe`. Not F-081 walk R. Not SEM-030.

**Split:** holdout entry_ts ≥ `2025-12-24 19:15:00`. Embargo 96, purge 40. F-086 stride unspent. F-081 entry-fraction OOS unspent.

**n:** A 941 (train 759 / holdout 180); B 462 (train 375 / holdout 86). Combined 1403.

| Gate | Train contrast | Holdout contrast | Holdout agree n | Holdout disagree n | Verdict |
|---|---:|---:|---:|---:|---|
| A-S (`y_mfe_r`) | −0.060 | +0.619 | 72 | 108 | **DIAGNOSTIC_FAIL** (sign flip; powered) |
| A-T (`y_time_to_mfe`) | −0.260 | −0.717 | 71 | 108 | **DIAGNOSTIC_PASS** (agree prints MFE faster) |
| B-S | −0.342 | −0.967 | **24** | 62 | **INSUFFICIENT** (agree n<30) |
| B-T | +0.300 | +1.242 | **24** | 60 | **INSUFFICIENT** (agree n<30) |

Bonferroni 4. Passing A-T does not pass A-S. Do not drop Arm B after seeing n=24.

**E-001:** F-092’s every-bar magnitude prior (agree lifts MFE, sign-stable) does **not** transfer to this Visual CRT Arm A set. A-T’s faster-peak is the same *sign* as F-092 Arm T and is information only. `y_mfe_r` P(>0) ≈ 1 by construction of path MFE — this is not a win-rate.

mt00 FAIL on E1-03-POPULATION-FINGERPRINT (same class as MC-MRPRIOR). mt01 UNRUN. `economic_claims_allowed` false. No G001. No production. No P-GOAL-04.

Metrics: `docs/research-readiness/visual_crt_prior/mc_vcrtprior_xauusd_m15_v1/metrics.json`.
