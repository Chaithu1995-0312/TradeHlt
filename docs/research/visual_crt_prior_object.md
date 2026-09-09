# Sparse Visual CRT entries × FM-054 trend prior (SEM-032)

Frozen **before** any arm's holdout contrast was computed. This is a **new**
named population of the sparse-signal + Parquet-prior class. It is **not**
SEM-030 / F-094 (mother-range inside-close) and **not** F-081 / F-084
(Visual CRT economic walk). Change any dimension → new `MC-*`.

## Why this object exists

F-094 closed P-EVID-01 for the **mother-range inside-close** population
(holdout agree n=9). The class “sparse independent SIGNAL + SEM-028 prior”
continues only on a **newly named** signal. User 2026-08-28 named
**Visual CRT** (SEM-012).

F-093 was every-bar × both sides + prior and collapsed. F-081/F-084 measured
SEM-012 as a **trade book** (`forward_walk` gross/net R). This object asks a
different question on the same entry set: does FM-054 **agreement** move that
entry’s **path MFE / time-to-MFE** (clean_labels `y_mfe_r` / `y_time_to_mfe`)?

```text
Sparse independent SIGNAL (SEM-012 Arm A and Arm B entries)
  +  Parquet magnitude/time prior (SEM-028 / FM-054 agree)
```

## Frozen field values

| Field | Frozen value |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Outcome surface | clean_labels `y_mfe_r` + `y_time_to_mfe` (TN_ENV_CLEAN_L2, max_forward=40) |
| Sparse SIGNAL | SEM-012 v2 entries from `visual_crt.driver.run_arm` (Arm A = displacement-close, Arm B = retest-close). Same duplicate rule as F-081: one shot per `(pool, direction)` until the pool is replaced, and at most one open trade at a time. |
| Unit | one SEM-012 entry resolved to its clean `(entry_ts, direction)` row with finite `y_mfe_r` and `trend_bias ∈ {+1,−1}` |
| Agreement | `agree` iff `sign(trend_bias)` matches entry `direction` (SEM-028 rule). `trend_bias=0` dropped from PRIMARY |
| Visual-CRT arms | A and B pre-registered **together**. Reporting one without the other, or picking after `y`, is forbidden. |
| Prior arms | S = `y_mfe_r`; T = `y_time_to_mfe` (nulls dropped). Four diagnostic gates: A-S, A-T, B-S, B-T. Bonferroni 4. Passing one does not pass another. |
| Success (per gate, diagnostic) | holdout agree **and** disagree cells **both** `n≥30` **AND** `sign(holdout contrast)==sign(train contrast)` |
| Holdout | **same calendar as MC-MRANGE/MC-ASYM/MC-MAGPRIOR/MC-MRPRIOR**: first holdout entry `2025-12-24 19:15:00`. Embargo 96 bars. Purge train entries whose 40-bar horizon overlaps holdout start. **Not** F-081’s last-20%-of-entries split. |
| F-086 | 236-bar stride holdout is **not** this split and stays unspent |
| Not | SEM-012 trade ledger SL/TP / F-081 y; SEM-030 mother-range; SEM-028 every-bar agree; SEM-029 `y_R_net` overlay; a side picker; G001; P-GOAL-04 |
| Kill | any outcome is registered; no retune of sparse signal, y, agree, split, which visual arm, or which prior arm after seeing holdout `y` |

This is an **information** object. `y_mfe_r` / `y_time_to_mfe` are path labels, not
book PnL. `economic_claims_allowed` is false while mt00/mt01 are UNRUN.

A sparse holdout cell `n<30` is `INSUFFICIENT` — an honest power boundary, not a
retune invitation (F-094 discipline).

Contract: `configs/research/measurement_contracts/instances/MC-VCRTPRIOR-XAUUSD-M15-V1.json`.
Runner: `src/research/evidence/visual_crt_prior.py`.
