# L-003C — Label-mismatch population measurement (scanner_outcome=SL_HIT × oracle_outcome=TP_HIT)

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

- **finding_id:** L-003C
- **parent:** L-003B (`l003b_outcome_population_comparison_20260907_173349`)
- **run_id:** `l003c_disagreement_population_20260907_175248`
- **generated_at_utc:** 2026-09-07T17:52:48.821Z
- **git_commit_sha:** `d7c25f6e55616261b8b229b000875abd3bd315eb`
- **version:** `L-003C.v1`
- **status:** **MEASURED (observation)** — does **NOT** freeze L-003; does **NOT** unlock attribution

## Scope honesty

- Same anatomy corpora / join surface as L-003B (row-aligned `scanner_outcome`/`art_outcome` × `oracle_outcome`/`outcome`).
- **CRT state, HTF state, and manipulation status were NOT measured this pass** — those columns are **not present** on the anatomy `trade_dataset` join surface. L-003C is conditioned on **anatomy-available covariates only**. No CRT/HTF/manipulation joins were invented.
- Descriptive comparison only; **economic_claims_allowed: false**; **attribution_unblocked: false**.
- No chronological holdout partition in anatomy summaries → **in-sample descriptive** (same note as L-003B).

## Unavailable fields (requested but not on join surface)

- CRT state / CRT episode identity
- HTF state / parent CRT / HTF objective gate
- manipulation status / sujan manipulation labels
- Any CRT/HTF/manipulation columns on anatomy trade_dataset join surface

## Populations (mechanical)

1. **LABEL_MISMATCH_SL_TP** (synonym: former DISAGREE_SL_TP) = `scanner_outcome`/`art_outcome=='SL_HIT'` AND `oracle_outcome`/`outcome=='TP_HIT'`
2. **LABEL_MATCH** (synonym: former AGREE) = `scanner_outcome == oracle_outcome` (terminal label equality only; not process agreement)
3. **LABEL_MISMATCH_OTHER** (synonym: former DISAGREE_OTHER) = LABEL_MISMATCH and not LABEL_MISMATCH_SL_TP
4. **ALL** = full dataset

Primary contrast: LABEL_MISMATCH_SL_TP vs LABEL_MATCH (vs ALL for base rates).

> Table/JSON historical keys may still say AGREE/DISAGREE for reproducibility; prose uses LABEL_MATCH / LABEL_MISMATCH.

## A. Sizes

| Instrument | n_all | n_LABEL_MISMATCH_SL_TP | rate | n_LABEL_MATCH | label_match_rate | n_LABEL_MISMATCH_OTHER |
|---|---:|---:|---:|---:|---:|---:|
| BNBUSDT | 139942 | 44791 | 0.3201 | 93683 | 0.6694 | 1468 |
| BTCUSDT | 139942 | 43392 | 0.3101 | 94068 | 0.6722 | 2482 |
| ETHUSDT | 139942 | 43725 | 0.3125 | 94175 | 0.6730 | 2042 |
| SOLUSDT | 139942 | 44563 | 0.3184 | 93779 | 0.6701 | 1600 |
| **AGGREGATE** | 559768 | 176471 | 0.3153 | 375705 | 0.6712 | 7592 |

Sanity: BNB LABEL_MISMATCH_SL_TP = **44791** (L-003B expected 44791; match=True).

## B. Path geometry / path-shape metrics (LABEL_MISMATCH_SL_TP vs LABEL_MATCH) — aggregate

| Feature | LABEL_MISMATCH mean/rate | LABEL_MATCH mean/rate | Delta |
|---|---:|---:|---:|
| direction long_rate | 0.4909 | 0.5036 | -0.0127 |
| mfe_r mean | 5.8226 | 3.0758 | 2.7468 |
| mae_r mean | -2.1676 | -4.8113 | 2.6438 |
| capture_ratio mean | 0.8191 | -189.3445 | 190.1636 |
| giveback mean | 0.1809 | 190.3445 | -190.1636 |
| bars_to_first_1r mean | 3.6680 | 10.8728 | -7.2048 |
| bars_to_peak_within_trade mean | 8.3043 | 2.5788 | 5.7255 |
| art_rr mean | 0.5000 | -0.3009 | 0.8009 |
| rr_achieved mean | 2.0000 | -0.9387 | 2.9387 |
| duration_candles mean | 8.3043 | 5.3873 | 2.9170 |
| reached_0_5r_rate | 1.0000 | 0.8454 | 0.1546 |
| reached_1r_rate | 1.0000 | 0.7015 | 0.2985 |
| reached_2r_rate | 1.0000 | 0.4500 | 0.5499 |
| favorable_first_rate | 0.6995 | 0.1869 | 0.5126 |
| art_consistent_rate | 0.0000 | 0.5457 | -0.5457 |

## C. Session / regime lifts (LABEL_MISMATCH vs ALL) — aggregate top deltas

### session_derived

| Category | rate_disagree | rate_all | lift_vs_all | delta |
|---|---:|---:|---:|---:|
| ASIA | 0.3000 | 0.2915 | 1.0291 | 0.0085 |
| NEWYORK | 0.3250 | 0.3334 | 0.9749 | -0.0084 |
| OFF | 0.1222 | 0.1250 | 0.9777 | -0.0028 |
| LONDON | 0.2527 | 0.2500 | 1.0107 | 0.0027 |

### volatility_regime

| Category | rate_disagree | rate_all | lift_vs_all | delta |
|---|---:|---:|---:|---:|
| 1.0 | 0.3332 | 0.3300 | 1.0096 | 0.0032 |
| 2.0 | 0.3368 | 0.3397 | 0.9913 | -0.0029 |
| 0.0 | 0.3300 | 0.3303 | 0.9993 | -0.0002 |

### trend_bias

| Category | rate_disagree | rate_all | lift_vs_all | delta |
|---|---:|---:|---:|---:|
| 1.0 | 0.5124 | 0.5133 | 0.9983 | -0.0009 |
| -1.0 | 0.4876 | 0.4867 | 1.0018 | 0.0009 |
| 0.0 | 0.0000 | 0.0000 | 1.5860 | 0.0000 |

### weekday

| Category | rate_disagree | rate_all | lift_vs_all | delta |
|---|---:|---:|---:|---:|
| 4 | 0.1383 | 0.1427 | 0.9692 | -0.0044 |
| 0 | 0.1455 | 0.1427 | 1.0198 | 0.0028 |
| 6 | 0.1451 | 0.1427 | 1.0166 | 0.0024 |
| 3 | 0.1451 | 0.1439 | 1.0088 | 0.0013 |
| 5 | 0.1419 | 0.1427 | 0.9942 | -0.0008 |
| 1 | 0.1421 | 0.1427 | 0.9956 | -0.0006 |

### hour_bucket

| Category | rate_disagree | rate_all | lift_vs_all | delta |
|---|---:|---:|---:|---:|
| 00-05 | 0.2576 | 0.2499 | 1.0310 | 0.0078 |
| 12-17 | 0.2425 | 0.2500 | 0.9698 | -0.0076 |
| 18-23 | 0.2451 | 0.2500 | 0.9804 | -0.0049 |
| 06-11 | 0.2548 | 0.2500 | 1.0188 | 0.0047 |

## D. Structure features (LABEL_MISMATCH vs LABEL_MATCH) — aggregate

| Feature | LABEL_MISMATCH | LABEL_MATCH | Delta |
|---|---:|---:|---:|
| f_sweep_detected_rate | 0.0927 | 0.0937 | -0.0010 |
| f_liquidity_sweep_rate | 0.0481 | 0.0485 | -0.0004 |
| f_break_of_structure_rate | 0.1315 | 0.1353 | -0.0039 |
| f_double_sweep_rate | 0.0256 | 0.0265 | -0.0009 |
| f_volume_spike_rate | 0.2691 | 0.2759 | -0.0068 |
| f_higher_high_rate | 0.1796 | 0.1838 | -0.0042 |
| f_lower_low_rate | 0.1677 | 0.1737 | -0.0060 |
| f_disp_strength mean | 0.5102 | 0.5190 | -0.0089 |
| f_retest_depth mean | 0.2018 | 0.2025 | -0.0006 |
| f_liquidity_distance mean | 0.6831 | 0.6984 | -0.0153 |
| f_liquidity_pressure_score mean | 0.7448 | 0.7412 | 0.0036 |
| f_trend_strength mean | -0.0032 | -0.0029 | -0.0003 |
| f_atr mean | 0.0044 | 0.0044 | 0.0000 |
| f_volatility_ratio mean | 1.0042 | 1.0204 | -0.0162 |
| f_rsi_14 mean | 50.4168 | 50.3909 | 0.0259 |
| f_momentum_score mean | 95.5215 | 5.3357 | 90.1858 |

## E. Top 10 separators (LABEL_MISMATCH_SL_TP vs LABEL_MATCH) — aggregate

Descriptive association only — no causal claim, no attribution unlock. Separators are **path-shape metrics** (geometry), not a measured trailing-stop process. Trailing-stop remains a **hypothesis (unmeasured)**.

Ranking score: continuous uses scale-normalized |median delta| / (|mD|+|mA|+1); rates use absolute rate delta. LABEL_MATCH capture_ratio/giveback means are outlier-sensitive; medians preferred.

| Rank | Feature | Kind | LABEL_MISMATCH | LABEL_MATCH | Delta | Lift_vs_agree |
|---:|---|---|---:|---:|---:|---:|
| 1 | rr_achieved | continuous_median_delta | 2.0000 | -1.0000 | 3.0000 | n/a |
| 2 | capture_ratio | continuous_median_delta | 0.8577 | -1.8386 | 2.6963 | n/a |
| 3 | giveback | continuous_median_delta | 0.1423 | 2.8386 | -2.6963 | n/a |
| 4 | bars_to_peak_within_trade | continuous_median_delta | 6.0000 | 1.0000 | 5.0000 | n/a |
| 5 | reached_2r_rate | rate_delta | 1.0000 | 0.4500 | 0.5499 | 2.2220 |
| 6 | art_consistent_rate | rate_delta | 0.0000 | 0.5457 | -0.5457 | 0.0000 |
| 7 | favorable_first_rate | rate_delta | 0.6995 | 0.1869 | 0.5126 | 3.7430 |
| 8 | mae_r | continuous_median_delta | -0.8561 | -3.5975 | 2.7414 | n/a |
| 9 | mfe_r | continuous_median_delta | 4.5628 | 1.7799 | 2.7829 | n/a |
| 10 | bars_to_first_1r | continuous_median_delta | 3.0000 | 7.0000 | -4.0000 | n/a |

## F. Holdout / promotion

- chronological_holdout_used: **false** (in-sample descriptive on full anatomy corpus)
- economic_claims_allowed: **false**
- attribution_unblocked: **false**
- registry_column_added: **false**
- l003_frozen: **false**
- ANALYTICS_SCHEMA_REGISTRY / ANALYTICS_LINEAGE_REGISTRY edited: **false**

## Per-instrument top separators (brief)

### BNBUSDT (n_LABEL_MISMATCH_SL_TP=44791)

1. `rr_achieved` delta=3.0000 (D=2.0000 vs A=-0.9425)
2. `capture_ratio` delta=2.7063 (D=0.8241 vs A=-9.3195)
3. `giveback` delta=-2.7063 (D=0.1759 vs A=10.3195)
4. `bars_to_peak_within_trade` delta=5.0000 (D=8.1538 vs A=2.5644)
5. `art_rr` delta=1.3850 (D=0.5056 vs A=-0.3084)

### BTCUSDT (n_LABEL_MISMATCH_SL_TP=43392)

1. `f_momentum_score` delta=75.9400 (D=376.5111 vs A=24.0945)
2. `rr_achieved` delta=3.0000 (D=2.0000 vs A=-0.9305)
3. `capture_ratio` delta=2.6749 (D=0.8184 vs A=-718.7608)
4. `giveback` delta=-2.6749 (D=0.1816 vs A=719.7608)
5. `bars_to_peak_within_trade` delta=5.0000 (D=8.3196 vs A=2.5813)

### ETHUSDT (n_LABEL_MISMATCH_SL_TP=43725)

1. `rr_achieved` delta=3.0000 (D=2.0000 vs A=-0.9259)
2. `capture_ratio` delta=2.7020 (D=0.8052 vs A=-24.4745)
3. `giveback` delta=-2.7020 (D=0.1948 vs A=25.4745)
4. `bars_to_peak_within_trade` delta=5.0000 (D=8.4158 vs A=2.5815)
5. `reached_2r_rate` delta=0.5513 (D=1.0000 vs A=0.4487)

### SOLUSDT (n_LABEL_MISMATCH_SL_TP=44563)

1. `rr_achieved` delta=3.0000 (D=2.0000 vs A=-0.9559)
2. `capture_ratio` delta=2.7035 (D=0.8284 vs A=-5.9242)
3. `giveback` delta=-2.7035 (D=0.1716 vs A=6.9242)
4. `bars_to_peak_within_trade` delta=5.0000 (D=8.3313 vs A=2.5879)
5. `reached_2r_rate` delta=0.5543 (D=1.0000 vs A=0.4457)

## Explicit non-goals

- No doctrine redesign; no registry columns; no CRT/HTF join engineering
- No claiming label mismatch set is an edge; no Phase 5 attribution

## Cross-links

- L-003D (path geometry / path-shape metrics; finding id still L-003D): `docs/governance/ANALYTICS_OUTCOME_PATH_MECHANICS_L003D.md` (run `l003d_path_mechanics_20260907_180219`)

- L-003B: `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md`
- L-003: `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md`
- JSON: `docs/governance/analytics_outcome_disagreement_population_l003c-2026-09-07.json`
- Impact: `docs/governance/build_manifests/CH-l003c-disagreement-population.impact.json`

