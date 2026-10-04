# MC-MAGPRIOR-XAUUSD-M15-V1 holdout (2026-08-24)

> Point-in-time. Object: `docs/research/magnitude_prior_object.md` (SEM-028).
> Sealed contract: `configs/research/measurement_contracts/instances/MC-MAGPRIOR-XAUUSD-M15-V1.json`
> (sha256 `161119d4204a39e60d8700d005d6b8ed182fea31c5caac0a3bc65df2219d392c`).
> Metrics: `docs/research-readiness/magnitude_prior/mc_magprior_xauusd_m15_v1/metrics.json`.
> L3 `validate_dataset` APPROVE (with gap warnings) on `data/mt5/XAUUSD_M15.csv`.

**Arm S: DIAGNOSTIC_PASS. Arm T: DIAGNOSTIC_PASS.** Not economic. mt00/mt01 UNRUN. No G001.
P-GOAL-04 not opened. SEM-027 PRIMARY not retuned. Not a side picker.

Unit = `(decision_ts, side)` with `trend_bias ∈ {+1,−1}`. `agree` = sign matches side.

| Arm | y | Split | agree n / mean | disagree n / mean | contrast | P(y>0) agree / disagree |
|---|---|---|---|---|---:|---|
| S | `y_mfe_r` | Train | 37,619 / 4.067 | 37,619 / 3.802 | **+0.265** | 0.996 / 0.997 |
| S | `y_mfe_r` | Holdout | 9,453 / 3.946 | 9,453 / 3.737 | **+0.209** | 0.996 / 0.997 |
| T | `y_time_to_mfe` | Train | 36,988 / 4.928 | 36,984 / 5.137 | **−0.209** | 1.0 / 1.0 |
| T | `y_time_to_mfe` | Holdout | 9,350 / 4.627 | 9,337 / 4.847 | **−0.220** | 1.0 / 1.0 |

Embargo dropped 182 rows. F-086 stride unspent.

**E-001:** `P(y_mfe_r>0)≈0.996` is **not a hit rate**. Horizon MFE is almost always positive by construction. Arm S is extra **path size** (+0.21R on holdout), not extra wins.

**Time consumer is the opposite of “hold longer.”** Agreeing paths peak **0.21 bars sooner** (~3 minutes of M15). Sign is stable; the shift is a small fraction of a ~5-bar mean. Do not build a hold-time gate on this.

**Size overlay k=0.5 (diagnostic, not PRIMARY):** holdout E[y] 3.841 → E[w·y] 3.893 (**+0.052R**). Algebra: balanced `delta = 0.25 × contrast_S`. Reported, not gated.

Side is given. FM-054 does not choose it. A `y_R_net` size overlay is a different `MC-*` and still needs P-GOAL-04 before it is money.
