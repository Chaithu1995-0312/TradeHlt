# L-003D — Attribute divergence to path geometry / path-shape metrics (descriptive measurement)

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

- **finding_id:** L-003D
- **parent:** L-003C (`l003c_disagreement_population_20260907_175248`)
- **run_id:** `l003d_path_mechanics_20260907_180219`
- **generated_at_utc:** 2026-09-07T18:02:19.282Z
- **git_commit_sha:** `d7c25f6e55616261b8b229b000875abd3bd315eb`
- **version:** `L-003D.v1`
- **status:** **MEASURED (observation)** — does **NOT** freeze L-003; does **NOT** unlock attribution

## Scope honesty

- Primary population: full anatomy rows (all `scanner_outcome`/`art_outcome` × `oracle_outcome`/`outcome`), n=559768 across BNB/BTC/ETH/SOL.
- Primary metric: **LABEL_MISMATCH_SL_TP** = `scanner_outcome==SL_HIT` AND `oracle_outcome==TP_HIT` (also report overall LABEL_MISMATCH optionally).
- Buckets: time-to-peak (`bars_to_peak_within_trade`) and MFE (`mfe_r`); Peak × MFE cross grid — these are **path-shape metrics / path geometry**.
- Leading **path-mechanics hypothesis / trailing-stop hypothesis (unmeasured)** after L-003C (candidate only): LABEL_MISMATCH is consistent with trailing-stop / exit-process divergence on favorable paths, **not** market-structure/regime. Trail activation/move/exit/touch were **not** measured.
- Descriptive measurement only; **economic_claims_allowed: false**; **attribution_unblocked: false**; **l003_frozen: false**.
- No CRT/HTF; no registry promotion; no causal proof of trailing-stop. “Detector stopped early” is **INFERENCE**, not observation (would need detector_exit_ts < oracle_tp_ts).

## Holdout / survival

- `anatomy_summary.json` has by_year / by_month / by_session splits but **no chronological IS/OOS** (or train/holdout) partition usable here.
- Therefore: **in-sample descriptive** on full corpus + **instrument leave-one-out** stability of bucket rankings (Spearman).
- Do **not** invent a new time split.

## A. Sizes (sanity)

| Instrument | n_all | n_LABEL_MISMATCH_SL_TP | rate_LABEL_MISMATCH_SL_TP |
|---|---:|---:|---:|
| BNBUSDT | 139942 | 44791 | 0.3201 |
| BTCUSDT | 139942 | 43392 | 0.3101 |
| ETHUSDT | 139942 | 43725 | 0.3125 |
| SOLUSDT | 139942 | 44563 | 0.3184 |
| **AGGREGATE** | 559768 | 176471 | 0.3153 |

Sanity: BNB LABEL_MISMATCH_SL_TP = **44791** (expected 44791; match=True).
Overall DISLABEL_MATCH rate (art!=outcome) aggregate: **0.3288**; LABEL_MATCH rate: **0.6712**.

## B. Peak marginal — LABEL_MISMATCH_SL_TP rate (aggregate)

| Peak bucket | n | n_LABEL_MISMATCH_SL_TP | rate | LABEL_MATCH rate | reached_2r rate |
|---|---:|---:|---:|---:|---:|
| Peak <= 2 bars | 281644 | 24704 | 0.0877 | 0.9104 | 0.5201 |
| Peak 3-5 | 120859 | 55246 | 0.4571 | 0.5364 | 0.6863 |
| Peak 6-10 | 79108 | 50892 | 0.6433 | 0.3409 | 0.7650 |
| Peak >10 | 61962 | 45629 | 0.7364 | 0.1824 | 0.7804 |
| Peak missing/non-finite | 16195 | 0 | 0.0000 | 1.0000 | 0.4661 |

**Pattern:** LABEL_MISMATCH_SL_TP rate rises monotonically with longer time-to-peak (8.8% → 45.7% → 64.3% → 73.6%). Short-peak paths overwhelmingly LABEL_MATCH.

## C. MFE marginal — LABEL_MISMATCH_SL_TP rate (aggregate)

| MFE bucket | n | n_LABEL_MISMATCH_SL_TP | rate | LABEL_MATCH rate | reached_2r rate |
|---|---:|---:|---:|---:|---:|
| MFE < 2R | 213919 | 0 | 0.0000 | 0.9658 | 0.0000 |
| MFE 2R-4R | 148563 | 73456 | 0.4944 | 0.5051 | 0.9998 |
| MFE 4R-6R | 84957 | 44008 | 0.5180 | 0.4812 | 1.0000 |
| MFE 6R+ | 112329 | 59007 | 0.5253 | 0.4734 | 1.0000 |
| MFE missing/non-finite | 0 | 0 | n/a | n/a | n/a |

**Pattern:** MFE < 2R has **0** LABEL_MISMATCH_SL_TP (definitional: oracle TP_HIT requires favorable extension to TP). Above 2R, rates are high and relatively flat (~49–53%). Peak duration separates more sharply than MFE magnitude once ≥2R.

## D. Peak × MFE cross — n and LABEL_MISMATCH_SL_TP rate (aggregate)

Cell format: `n / rate` (LABEL_MATCH rate in parentheses).

| Peak \ MFE | MFE <2R | MFE 2R–4R | MFE 4R–6R | MFE 6R+ |
|---|---:|---:|---:|---:|
| Peak <=2 | 135163 / 0.0000 (A=0.9979) | 60851 / 0.1365 (A=0.8625) | 35460 / 0.1700 (A=0.8284) | 50170 / 0.2067 (A=0.7907) |
| Peak 3-5 | 37915 / 0.0000 (A=0.9799) | 32292 / 0.6012 (A=0.3986) | 20660 / 0.6739 (A=0.3259) | 29992 / 0.7306 (A=0.2690) |
| Peak 6-10 | 18589 / 0.0000 (A=0.9331) | 25554 / 0.8063 (A=0.1937) | 15333 / 0.8500 (A=0.1500) | 19632 / 0.8789 (A=0.1208) |
| Peak >10 | 13606 / 0.0000 (A=0.6305) | 26688 / 0.9418 (A=0.0582) | 11699 / 0.9424 (A=0.0574) | 9969 / 0.9499 (A=0.0501) |

### Hottest cells (n≥1000, exclude missing)

| Peak | MFE | n | LABEL_MISMATCH_SL_TP rate | LABEL_MATCH rate |
|---|---|---:|---:|---:|
| Peak >10 | MFE 6R+ | 9969 | 0.9499 | 0.0501 |
| Peak >10 | MFE 4R-6R | 11699 | 0.9424 | 0.0574 |
| Peak >10 | MFE 2R-4R | 26688 | 0.9418 | 0.0582 |
| Peak 6-10 | MFE 6R+ | 19632 | 0.8789 | 0.1208 |
| Peak 6-10 | MFE 4R-6R | 15333 | 0.8500 | 0.1500 |
| Peak 6-10 | MFE 2R-4R | 25554 | 0.8063 | 0.1937 |

Hottest: **Peak >10 × MFE 6R+** → LABEL_MISMATCH_SL_TP **0.9499** (n=9969). Long, extended favorable paths almost always show art=SL vs oracle=TP.

### Coldest non-trivial cells

| Peak | MFE | n | LABEL_MISMATCH_SL_TP rate | LABEL_MATCH rate |
|---|---|---:|---:|---:|
| Peak <= 2 bars | MFE < 2R | 135163 | 0.0000 | 0.9979 |
| Peak 3-5 | MFE < 2R | 37915 | 0.0000 | 0.9799 |
| Peak 6-10 | MFE < 2R | 18589 | 0.0000 | 0.9331 |
| Peak >10 | MFE < 2R | 13606 | 0.0000 | 0.6305 |
| Peak <= 2 bars | MFE 2R-4R | 60851 | 0.1365 | 0.8625 |

## E. Per-instrument peak rates (LABEL_MISMATCH_SL_TP)

| Instrument | <=2 | 3-5 | 6-10 | >10 |
|---|---:|---:|---:|---:|
| BNBUSDT | 0.0908 | 0.4740 | 0.6547 | 0.7458 |
| BTCUSDT | 0.0897 | 0.4501 | 0.6304 | 0.7196 |
| ETHUSDT | 0.0868 | 0.4442 | 0.6347 | 0.7378 |
| SOLUSDT | 0.0835 | 0.4597 | 0.6534 | 0.7429 |

## F. Per-instrument MFE rates (LABEL_MISMATCH_SL_TP)

| Instrument | <2R | 2R–4R | 4R–6R | 6R+ |
|---|---:|---:|---:|---:|
| BNBUSDT | 0.0000 | 0.4937 | 0.5291 | 0.5382 |
| BTCUSDT | 0.0000 | 0.4996 | 0.5053 | 0.4989 |
| ETHUSDT | 0.0000 | 0.4930 | 0.5118 | 0.5243 |
| SOLUSDT | 0.0000 | 0.4917 | 0.5248 | 0.5428 |

## G. Instrument holdout stability (leave-one-out Spearman on bucket ranks)

| Held out | Peak Spearman ρ | MFE Spearman ρ |
|---|---:|---:|
| BNBUSDT | 1.0000 | 1.0000 |
| BTCUSDT | 1.0000 | 0.4000 |
| ETHUSDT | 1.0000 | 1.0000 |
| SOLUSDT | 1.0000 | 1.0000 |

- Peak ranking: **perfectly stable** (LOO ρ min=1.0000, mean=1.0000). Order always >10 > 6-10 > 3-5 > <=2.
- MFE ranking: **mostly stable** but flatter (LOO ρ min=0.4000, mean=0.8500). BTC reorders the near-tied ≥2R buckets (~0.50); <2R always lowest (0).

## H. Secondary — composition within LABEL_MISMATCH_SL_TP vs LABEL_MATCH

### Peak composition shares

| Peak | share of LABEL_MISMATCH_SL_TP | share of LABEL_MATCH |
|---|---:|---:|
| <=2 | 0.1400 | 0.6825 |
| 3-5 | 0.3131 | 0.1726 |
| 6-10 | 0.2884 | 0.0718 |
| >10 | 0.2586 | 0.0301 |
| missing | 0.0000 | 0.0431 |

### MFE composition shares

| MFE | share of LABEL_MISMATCH_SL_TP | share of LABEL_MATCH |
|---|---:|---:|
| <2R | 0.0000 | 0.5499 |
| 2R–4R | 0.4162 | 0.1997 |
| 4R–6R | 0.2494 | 0.1088 |
| 6R+ | 0.3344 | 0.1415 |

LABEL_MISMATCH_SL_TP mass concentrates in longer peaks (86% in peak≥3) and MFE≥2R (100%); LABEL_MATCH mass concentrates in peak≤2 (68%) and MFE<2R (55%).

> **Ontology note (L-003J):** Peak-duration / path-geometry results are **associations** with joint-state membership — not drives/causes. Prefer JOINT state framing over mismatch-as-error.

## I. Descriptive verdict (non-causal)

**Does evidence support “path duration + extension” (path geometry) over regime?** **Yes, descriptively** (observation only):

1. Peak duration shows a **large, monotonic** LABEL_MISMATCH_SL_TP gradient (≈9% → 74%), stable across all four instruments.
2. MFE shows a **hard threshold** at 2R (0% below; ~50% above) with a weaker within-≥2R gradient — extension necessary but duration-to-peak is the sharper separator.
3. Cross cells with long peak **and** MFE≥2R reach **>80–95%** LABEL_MISMATCH_SL_TP.
4. L-003C session/volatility/trend lifts were ~±1pp — orders of magnitude smaller than path-bucket spreads here.

This is **consistent with** a **trailing-stop hypothesis (unmeasured)** / exit-process divergence on favorable paths as a **candidate** explanation. It is **not** an observation of trail mechanics; **not** causal proof; no attribution unlock; no edge claim. Measured vars remain time_to_peak / MFE / (later T_MAE) only.

## J. Promotion flags

- chronological_holdout_used: **false**
- economic_claims_allowed: **false**
- attribution_unblocked: **false**
- registry_column_added: **false**
- l003_frozen: **false**
- ANALYTICS_SCHEMA_REGISTRY / ANALYTICS_LINEAGE_REGISTRY edited: **false**

## Explicit non-claims

- No causal proof of trailing-stop (**trailing-stop hypothesis (unmeasured)** remains candidate only)
- No CRT/HTF
- No edge / attribution unlock
- No registry promotion

## Cross-links
- L-003E (early MAE timing / early-path minimum proxy T_MAE=`time_to_bottom_path`, not FAE / not first stop-threat): `docs/governance/ANALYTICS_OUTCOME_ADVERSE_TIMING_L003E.md`

- L-003C: `docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md`
- L-003B: `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md`
- L-003: `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md`
- JSON: `docs/governance/analytics_outcome_path_mechanics_l003d-2026-09-07.json`
- Impact: `docs/governance/build_manifests/CH-l003d-path-mechanics.impact.json`

