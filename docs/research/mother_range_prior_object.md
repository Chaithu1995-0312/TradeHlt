# Sparse mother-range inside signal x FM-054 trend prior (SEM-030, P-EVID-01)

Frozen **before** either arm's holdout contrast was computed. This is the
**P-EVID-01** frontier object: a **sparse** independent signal + a Parquet-derived
prior. Change any dimension → new `MC-*`.

## Why this is the untested object

`docs/research/parquet_evidence_layer.md` § *Demonstrated vs unproven* locked the
distinction. **F-093 was** `independent entry + state prior`, but its independent
entry was **every-bar × both sides** — the grain F-086 showed structurally losing,
so the overlay survived only as a +0.006R lift on a −0.55R book and **did not
harvest**. The object that was *untested* is:

```text
Sparse independent SIGNAL (SEM-026 mother inside entries)  +  Parquet magnitude prior (SEM-028)
```

The sparse signal is the causal SEM-026 inside-close entry set: a few touching
blocks per instrument-month, **not** every bar.

## Frozen field values

| Field | Frozen value |
|---|---|
| Cast | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Outcome surface | clean_labels `y_mfe_r` + `y_time_to_mfe` (TN_ENV_CLEAN_L2, max_forward=40) — **Parquet layer** |
| Sparse SIGNAL | `detect_inside_close_entries(bars)` under SEM-026 (causal; uses bars ≤ test-last close) |
| Unit | one SEM-026 entry resolved to its clean `(entry_ts, direction)` row with finite `y_mfe_r` and `trend_bias ∈ {+1,−1}` |
| Agreement | `agree` iff `sign(trend_bias)` matches entry `direction` (same rule as SEM-028). `trend_bias=0` dropped from PRIMARY |
| Arm S (magnitude) | `y = y_mfe_r`. `contrast_S = E[y \| agree] − E[y \| disagree]` |
| Arm T (time) | `y = y_time_to_mfe` (drop nulls). `contrast_T = E[y \| agree] − E[y \| disagree]` |
| Success (per arm, diagnostic) | holdout agree **and** disagree cells **both** `n≥30` **AND** `sign(holdout contrast)==sign(train contrast)` |
| Holdout | same as MC-MRANGE/MC-ASYM/MC-MAGPRIOR: first test entry `2025-12-24 19:15:00`. Embargo 96 bars. Purge train entries whose 40-bar horizon overlaps holdout start |
| F-086 | 236-bar stride holdout is **not** this split and stays unspent |
| Not | the SEM-026 trade ledger SL/TP walk, SEM-029 `y_R_net` overlay, the F-093 every-bar grain, a side picker, a one-open trade suppression, G001, P-GOAL-04 |
| Kill | any outcome is registered; no retuning of sparse signal, y, agree, split, or which arm after seeing holdout y |

Two arms are pre-registered together. Each is scored independently. Passing S does
not pass T. A sparse holdout agree cell `n<30` is `INSUFFICIENT` — an honest
power boundary, not a retune invitation.

This is an **information** object. `y_mfe_r` / `y_time_to_mfe` are path labels, not
book PnL. `economic_claims_allowed` is false while mt00/mt01 are UNRUN.
Contract: `configs/research/measurement_contracts/instances/MC-MRPRIOR-XAUUSD-M15-V1.json`.
Runner: `src/research/evidence/mother_range_prior.py`.