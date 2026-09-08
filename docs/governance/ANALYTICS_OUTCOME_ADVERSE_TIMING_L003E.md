# L-003E — Early MAE timing / early-path minimum measurement (falsification-oriented)

> **Ontology note (L-003J):** Primary measured object is `JOINT_OUTCOME_STATE` / `Y_joint = (Y_scanner, Y_oracle)`. `scanner_outcome` and `oracle_outcome` are **components**, not rival labels. Named joint populations (e.g. `JOINT_STATE_SL_TP`, `BOTH_SL`) are **states**, not errors. `LABEL_MATCH` / `LABEL_MISMATCH` remain terminal-label equality only; prefer state membership over "who is right". See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

## Terminology parity (L-003-TERM.v1) — documentation correction only

> **No new measurements this pass.** Numbers below are unchanged; prose/labels are corrected for ontology↔implementation parity.

| Canonical term | Formula / meaning | Dataset / column | Claim class |
|---|---|---|---|
| `scanner_outcome` | `opportunity_scanner._simulate` → SL_HIT / TP_HIT / TIMEOUT | opportunities / anatomy `art_outcome` | measured label |
| `oracle_outcome` | `forward_walk(intrabar_fixed)` → SL_HIT / TP_HIT / TIMEOUT | anatomy column `outcome` | measured label |
| `live_outcome` | `ingest_live_outcomes` → WIN / LOSS / BREAKEVEN | live ingest twin | measured label (separate pop.) |
| `attribution_target` | trade edge realization (implicit; not a scanner/oracle label) | — | eligibility target |
| `LABEL_MATCH` | `scanner_outcome == oracle_outcome` (terminal label equality only) | anatomy join | measured equality; **not** process agreement |
| `LABEL_MISMATCH` | `scanner_outcome != oracle_outcome` | anatomy join | measured inequality |
| `LABEL_MISMATCH_SL_TP` | scanner SL_HIT × oracle TP_HIT | anatomy join | primary mismatch class |
| path-shape metrics / path geometry | measured set {`time_to_peak`/`bars_to_peak_within_trade`, MFE/`mfe_r`, T_MAE/`time_to_bottom_path`} | anatomy | measured |
| T_MAE | timing of deepest adverse on PEAK_HORIZON path (= `time_to_bottom_path`) | anatomy | measured timing (not magnitude+timing; not first stop-threat) |
| trailing-stop / path-mechanics hypothesis | unmeasured trail activation/move/exit/touch | — | **hypothesis only** |
| early-stop / “detector stopped early” | would need `detector_exit_ts < oracle_tp_ts` | — | **INFERENCE**, not observation |

**Historical synonyms (machine keys kept in JSON for reproducibility):** former prose AGREE/DISAGREE meant LABEL_MATCH / LABEL_MISMATCH (label equality only). Former LABEL_MISMATCH_SL_TP = LABEL_MISMATCH_SL_TP. CSV `art_outcome` = scanner_outcome; CSV `outcome` = oracle_outcome. Bare `outcome` is reserved for none of the three RVs in new prose.

**Attribution blockers (always name which):**
- `ATTRIBUTION_BLOCKER_IDENTITY` — 12 `opportunities.produced_by` UNKNOWN (L-001)
- `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` — scanner_outcome ≠ oracle_outcome as RVs (L-003B HOMONYM)

- **finding_id:** L-003E
- **parent:** L-003D (`l003d_path_mechanics_20260907_180219`)
- **run_id:** `l003e_adverse_timing_20260907_181752`
- **generated_at_utc:** 2026-09-07T18:17:52.190Z
- **git_commit_sha:** `d7c25f6e55616261b8b229b000875abd3bd315eb`
- **version:** `L-003E.v1`
- **status:** **MEASURED** — does **NOT** freeze L-003; does **NOT** unlock attribution

## CRITICAL — column semantics (early MAE timing / early-path minimum — not FAE)

| Name used here | Source column | Meaning |
|---|---|---|
| **T_MAE** | `time_to_bottom_path` | **Timing** of deepest adverse excursion on the exit-agnostic **PEAK_HORIZON (~96 bars)** path — **not** a magnitude+timing composite; **not** first stop-threat |
| Peak / time_to_peak | `bars_to_peak_within_trade` | Favorable peak within governing trade duration (KEEP — good separator) |
| `favorable_first` | same | Binary order signal from `horizon_excursion` |

**Preferred prose:** early MAE timing / early-path minimum.
**T_MAE is a proxy for adverse-path timing. It is NOT "first time stop was threatened" and NOT true FAE-to-stop.**
True first-adverse-vs-stop would require candle replay — **out of scope**; not invented here.
Source: `scripts/analysis/bnbusdt_trade_anatomy.py`.

## Falsification criteria (stated upfront)

Leading **path-mechanics hypothesis** after L-003D: duration-driven **path geometry**; **trailing-stop hypothesis (unmeasured)** still unproven.

**Trailing-stop hypothesis (unmeasured) predicts** LABEL_MISMATCH_SL_TP enrichment for:
1. **early MAE timing / early-path minimum** (low T_MAE) combined with **late** peak (high `bars_to_peak_within_trade`)
2. higher rate of early-path-minimum-before-completion patterns vs LABEL_MATCH

**Would weaken / falsify** that story if:
1. LABEL_MISMATCH_SL_TP T_MAE distribution is similar to LABEL_MATCH (**or later, not earlier**)
2. Early T_MAE buckets do **not** show elevated LABEL_MISMATCH_SL_TP rate after conditioning on peak duration
3. Sequence pattern "early bottom + late peak" is **not** enriched in label mismatch

This run measures to try to **break** the hypothesis, then reports which way evidence leans (**descriptive only**).

## Populations / data

- **LABEL_MISMATCH_SL_TP:** `scanner_outcome`/`art_outcome==SL_HIT` & `oracle_outcome`/`outcome==TP_HIT`
- **LABEL_MATCH:** `scanner_outcome == oracle_outcome` (terminal label equality only)
- **ALL:** full rows
- Instruments: BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT under `results/research/*_trade_anatomy/trade_dataset_*.csv`
- Aggregate n = **559768**; LABEL_MISMATCH_SL_TP n = **176471** (rate **0.3153**)
- BNB sanity: LABEL_MISMATCH_SL_TP n = **44791** (expected 44791; match=True)

## A. T_MAE distribution (right-skewed)

| Population | n_finite | median | p25 | p75 | mean | max |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 557535 | 44.0 | 14.0 | 77.0 | 45.64 | 96.0 |
| LABEL_MISMATCH_SL_TP | 174508 | 40.0 | 5.0 | 77.0 | 42.68 | 96.0 |
| LABEL_MATCH | 375445 | 45.0 | 17.0 | 77.0 | 46.93 | 96.0 |

LABEL_MISMATCH median T_MAE (**40.0**) is **earlier** than LABEL_MATCH (**45.0**) by 5 bars (means 42.7 vs 46.9). Direction matches the early-MAE-timing / early-path-minimum prediction (modest median shift; larger share differences below).

## B. T_MAE marginals — LABEL_MISMATCH_SL_TP rate (ALL)

### B1. User-style short buckets (expect mass in >10)

| Bucket | n | n_LABEL_MISMATCH_SL_TP | rate |
|---|---:|---:|---:|
| T_MAE <= 2 | 50343 | 35864 | 0.7124 |
| T_MAE 3-5 | 32062 | 9659 | 0.3013 |
| T_MAE 6-10 | 37681 | 7366 | 0.1955 |
| T_MAE >10 | 437449 | 121619 | 0.2780 |
| T_MAE missing/non-finite | 2233 | 1963 | 0.8791 |

**Note:** Mass is overwhelmingly in >10 (n=437449), but the **≤2** cell is sparse-relative yet **highest rate (0.7124)**.

### B2. Distribution-aware buckets (documented choice)

Chosen for right-skew (median ~40–45, max 96): **≤5, 6–20, 21–40, 41–70, >70**.

| Bucket | n | n_LABEL_MISMATCH_SL_TP | rate |
|---|---:|---:|---:|
| T_MAE <= 5 | 82405 | 45523 | 0.5524 |
| T_MAE 6-20 | 94610 | 19234 | 0.2033 |
| T_MAE 21-40 | 88255 | 22953 | 0.2601 |
| T_MAE 41-70 | 123025 | 35282 | 0.2868 |
| T_MAE >70 | 169240 | 51516 | 0.3044 |
| T_MAE missing/non-finite | 2233 | 1963 | 0.8791 |

**Pattern:** Early bucket (≤5) rate **0.5524** >> mid/late (~0.20–0.30). After ≤5, rates are relatively flat / slightly rising — not a smooth early→late decline across the whole support, but a clear **early elevation**.

### B3. Composition within LABEL_MISMATCH vs LABEL_MATCH (dist buckets)

| Bucket | LABEL_MISMATCH n | LABEL_MISMATCH share | LABEL_MATCH n | LABEL_MATCH share |
|---|---:|---:|---:|---:|
| T_MAE <= 5 | 45523 | 0.2580 | 35543 | 0.0946 |
| T_MAE 6-20 | 19234 | 0.1090 | 74302 | 0.1978 |
| T_MAE 21-40 | 22953 | 0.1301 | 64719 | 0.1723 |
| T_MAE 41-70 | 35282 | 0.1999 | 86065 | 0.2291 |
| T_MAE >70 | 51516 | 0.2919 | 114816 | 0.3056 |
| missing | 1963 | 0.0111 | 260 | 0.0007 |

Early (≤5) share: LABEL_MISMATCH **0.2580** vs LABEL_MATCH **0.0946** (~2.7× enrichment).

## C. Sequence / interaction with peak (L-003D separator)

### C1. Cross: T_MAE short × peak (n / LABEL_MISMATCH_SL_TP rate)

| T_MAE \ Peak | Peak<=2 | Peak 3-5 | Peak 6-10 | Peak>10 |
|---|---:|---:|---:|---:|
| T_MAE<=2 | 17462 / 0.2970 | 13136 / 0.9717 | 10736 / 0.9830 | 7873 / 0.9350 |
| T_MAE 3-5 | 19371 / 0.0279 | 3143 / 0.3840 | 3893 / 0.9723 | 4519 / 0.9130 |
| T_MAE 6-10 | 22430 / 0.0482 | 7670 / 0.1952 | 2429 / 0.5101 | 3951 / 0.8980 |
| T_MAE>10 | 221473 / 0.0779 | 96166 / 0.4059 | 61639 / 0.5663 | 45449 / 0.6695 |

Hottest non-degenerate cells: early T_MAE (≤2 or 3–5) × longer peaks often **>0.90** LABEL_MISMATCH_SL_TP. Peak≤2 stays low even with early T_MAE except T_MAE≤2 (0.297).

### C2. Binary: `early_mae` = T_MAE ≤ **5**; `late_peak` = peak > **10**

| Combo | n | n_LABEL_MISMATCH_SL_TP | rate |
|---|---:|---:|---:|
| early_mae AND late_peak | 12392 | 11487 | 0.9270 |
| early_mae AND NOT late_peak | 67741 | 34036 | 0.5024 |
| NOT early_mae AND late_peak | 49400 | 33978 | 0.6878 |
| neither | 411807 | 95007 | 0.2307 |
| baseline ALL | 559768 | 176471 | 0.3153 |

**early_mae × late_peak rate = 0.9270** vs baseline **0.3153**.

Pattern share (finite T_MAE & peak):
- LABEL_MISMATCH share early+late: **0.0658** (n=11487)
- LABEL_MATCH share early+late: **0.0000** (n=12)

Strong enrichment of the predicted sequence cell in label mismatch (near-absent in LABEL_MATCH).

## D. favorable_first (reconfirm L-003C)

| Population | n | n_favorable_first | rate |
|---|---:|---:|---:|
| LABEL_MISMATCH_SL_TP | 176471 | 123444 | 0.6995 |
| LABEL_MATCH | 375705 | 70214 | 0.1869 |
| ALL | 559768 | 197475 | 0.3528 |

Reconfirmed: LABEL_MISMATCH much more often favorable-first (**~0.70** vs **~0.19**).

## E. mae_r depth (milder adverse in label mismatch?)

| Population | n | median mae_r | abs median | mean mae_r | abs mean |
|---|---:|---:|---:|---:|---:|
| LABEL_MISMATCH_SL_TP | 176471 | -0.8561 | 0.8561 | -2.1676 | 2.1676 |
| LABEL_MATCH | 375705 | -3.5975 | 3.5975 | -4.8113 | 4.8113 |
| ALL | 559768 | -2.7658 | 2.7658 | -3.9237 | 3.9237 |

**Yes — label mismatch is shallower adverse** (abs median **0.86R** vs LABEL_MATCH **3.60R**), consistent with L-003C. Compatible with a **trailing-stop hypothesis (unmeasured)** on paths that still expand favorably; **not** observation of trail touch/activation; not proof.

## F. Instrument stability (leave-one-out rank of T_MAE-bucket disLABEL_MATCH rates)

| Held out | T_MAE dist Spearman ρ | T_MAE short Spearman ρ |
|---|---:|---:|
| BNBUSDT | 1.0000 | 1.0000 |
| BTCUSDT | 1.0000 | 1.0000 |
| ETHUSDT | 1.0000 | 1.0000 |
| SOLUSDT | 1.0000 | 1.0000 |

- dist LOO ρ min/mean: **1.0000** / **1.0000** (stable)
- short LOO ρ min/mean: **1.0000** / **1.0000** (stable; note mass concentration in >10)
- No chronological IS/OOS available in anatomy corpus.

### Per-instrument sizes

| Instrument | n_all | n_LABEL_MISMATCH_SL_TP | rate | median T_MAE |
|---|---:|---:|---:|---:|
| BNBUSDT | 139942 | 44791 | 0.3201 | 44.0 |
| BTCUSDT | 139942 | 43392 | 0.3101 | 44.0 |
| ETHUSDT | 139942 | 43725 | 0.3125 | 42.0 |
| SOLUSDT | 139942 | 44563 | 0.3184 | 45.0 |

## G. Conditioning on peak (does T_MAE still separate?)

Within each L-003D peak bucket, early_mae (T_MAE≤5) vs not:

| Peak | n | baseline rate | early_mae n/rate | not-early n/rate | delta | dist rate span |
|---|---:|---:|---|---|---:|---:|
| Peak <= 2 | 281644 | 0.0877 | 36833 / 0.1555 | 243903 / 0.0752 | 0.0803 | 0.0969 |
| Peak 3-5 | 120859 | 0.4571 | 16279 / 0.8582 | 103836 / 0.3903 | 0.4679 | 0.5921 |
| Peak 6-10 | 79108 | 0.6433 | 14629 / 0.9801 | 64068 / 0.5642 | 0.4159 | 0.5576 |
| Peak >10 | 61962 | 0.7364 | 12392 / 0.9270 | 49400 / 0.6878 | 0.2392 | 0.3388 |

Unconditional early vs not delta: **0.2810**.
Mean |within-peak early vs not delta|: **0.3008**.
L-003D peak marginal span (reference): **0.6487**.

**Verdict on conditioning:** Peak does **not** absorb all signal. T_MAE (early vs not) still separates LABEL_MISMATCH_SL_TP **inside every peak bucket** (deltas +0.08 to +0.47). Interaction cell early×late_peak is the hottest. Peak remains the larger marginal separator (L-003D); T_MAE adds a **substantial orthogonal / interactive** lift on this proxy.

## H. Falsification assessment (descriptive lean)

Binary checks against the candidate prediction:

| Check | Result |
|---|---|
| LABEL_MISMATCH earlier T_MAE than LABEL_MATCH | **True** (medians 40 vs 45) |
| Early T_MAE bucket elevated vs late | **True** (≤5 rate 0.55 vs 41+/ >70 ~0.29/0.30) |
| early×late_peak elevated vs baseline | **True** (0.927 vs 0.315) |
| early×late enriched in LABEL_MISMATCH vs LABEL_MATCH | **True** |
| T_MAE separates within peak | **True** |

Support count: **5/5**.

### Evidence lean

**leans SUPPORT early MAE timing / early-path minimum enrichment on T_MAE proxy (still not causal; not FAE)**

Attempted falsification did **not** break the early-path-minimum + late-expansion enrichment prediction on available proxies. That is **consistent with** (does not prove) a **trailing-stop hypothesis (unmeasured)** alongside duration-driven **path geometry** from L-003D.

**Still not FAE. Still not causal trailing-stop proof. Early-stop / “detector stopped early” remains INFERENCE only** (would need detector_exit_ts < oracle_tp_ts). Candle-replay first-adverse-to-stop remains out of scope.

## I. Promotion flags

- chronological_holdout_used: **false**
- economic_claims_allowed: **false**
- attribution_unblocked: **false**
- registry_column_added: **false**
- registry_edits: **false**
- l003_frozen: **false**
- ANALYTICS_SCHEMA_REGISTRY / ANALYTICS_LINEAGE_REGISTRY edited: **false**

## Explicit non-claims

- T_MAE ≠ FAE-to-stop (early MAE timing / early-path minimum proxy only; no candle replay; not magnitude+timing; not first stop-threat)
- No causal proof or disproof of trailing-stop (**hypothesis only; unmeasured**)
- No CRT/HTF
- No edge / attribution unlock
- No registry promotion
- Descriptive measurement only

## Cross-links

- L-003D: `docs/governance/ANALYTICS_OUTCOME_PATH_MECHANICS_L003D.md`
- L-003C: `docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md`
- L-003B: `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md`
- L-003: `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md`
- JSON: `docs/governance/analytics_outcome_adverse_timing_l003e-2026-09-07.json`
- Impact: `docs/governance/build_manifests/CH-l003e-adverse-timing.impact.json`
