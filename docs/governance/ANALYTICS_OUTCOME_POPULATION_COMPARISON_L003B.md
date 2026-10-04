# L-003B Outcome Population Comparison (Phase B)

**Status:** OBSERVED (measurement complete) — **L-003 remains NOT frozen**  
**Date (UTC):** 2026-09-07T17:33:49.906Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003b_outcome_population_comparison_20260907_173349`  
**doctrine / measurement_version:** `L-003B.v1`

## Banner / discipline

**Observation → Measurement → Evidence → Promotion.**

- **Phase A (L-003):** DETECTION_STREAM vocabulary census only — incomplete for the semantic-boundary claim that `scanner_outcome` and `oracle_outcome` are the same (or aliasable) RV.
- **Phase B (this artifact):** scanner_outcome × oracle_outcome confusion matrix on the anatomy trade_dataset join surface — **required before any freeze / SAFE_ALIAS / promotion**.

**Label vocabulary (explicit):** Both `scanner_outcome` (column `art_outcome`) and `oracle_outcome` (column `outcome`) use **`SL_HIT` / `TP_HIT` / `TIMEOUT`**. Oracle is **`forward_walk(intrabar_fixed)` single TP**. **Do not invent TP1/TP2 labels.** Equality of those terminal tokens is **LABEL_MATCH** only (not process agreement).

Machine-readable pin: `docs/governance/analytics_outcome_population_comparison_l003b-2026-09-07.json`.

Parent Phase A (demoted): `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md`.

---

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

---

## Population definition

| Field | Value |
|---|---|
| Unit | One anatomy `trade_dataset` row = one detection opportunity with re-derived governing outcome |
| Scanner RV | `scanner_outcome` = column `art_outcome` (opportunities.jsonl / scanner `_simulate` trailing 0.5R) |
| Oracle RV | `oracle_outcome` = column `outcome` (`forward_walk(intrabar_fixed)` fixed-stop single TP) |
| Join rule | **ROW IDENTITY** in anatomy trade_dataset (same entry_index/timestamp/direction opportunity; oracle labels derived onto the detection population). **NOT** a fuzzy time join. |
| Holdout | Anatomy summaries expose descriptive splits (`by_year` / month / weekday / hour / session / vol) but **no chronological train/holdout**. This pass is an **in-sample descriptive comparison** on the full corpus; **no new holdout invented**. |
| Re-run policy | Existing measured join surface used; **forward_walk NOT re-run** this pass |

---

## Aggregate results (BNB + BTC + ETH + SOL)

| Metric | Value |
|---|---|
| n rows | 559,768 |
| LABEL_MATCH rate (diagonal / n) | **67.12%** (375,705 / 559,768) |
| Majority-class baseline (always Oracle=SL_HIT) | 65.78% |
| LABEL_MATCH − baseline | 1.34% |

### Aggregate scanner_outcome marginals

| Label | Count | Share |
|---|---:|---:|
| SL_HIT | 551,706 | 98.56% |
| TP_HIT | 7,914 | 1.41% |
| TIMEOUT | 148 | 0.03% |

### Aggregate oracle_outcome marginals

| Label | Count | Share |
|---|---:|---:|
| SL_HIT | 368,203 | 65.78% |
| TP_HIT | 184,105 | 32.89% |
| TIMEOUT | 7,460 | 1.33% |

### Aggregate confusion matrix (scanner_outcome × oracle_outcome)

| scanner_outcome \ oracle_outcome | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 367,923 | 176,471 | 7,312 | 551,706 |
| **TP_HIT** | 280 | 7,634 | 0 | 7,914 |
| **TIMEOUT** | 0 | 0 | 148 | 148 |
| **Col sum** | 368,203 | 184,105 | 7,460 | 559,768 |

### Aggregate precision/recall (scanner_outcome as predictor of oracle_outcome)

| Class | Precision | Recall | Det support | Oracle support | TP |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 66.69% | 99.92% | 551,706 | 368,203 | 367,923 |
| TP_HIT | 96.46% | 4.15% | 7,914 | 184,105 | 7,634 |
| TIMEOUT | 100.00% | 1.98% | 148 | 7,460 | 148 |

---

## Per-instrument results


### BNBUSDT

| Field | Value |
|---|---|
| CSV | `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv` (127,143,244 bytes; mtime 2026-06-13T06:54:28.523866Z) |
| Summary | `results/research/bnbusdt_trade_anatomy/anatomy_summary.json` |
| dataset_sha256 | `f8bdabbe683fe43f54f3853dcce809f113fe22e9385828210d48c6cc2aa34934` |
| n | 139,942 |
| Mapping rate (n_dataset / n_opportunities) | 100.00% |
| LABEL_MATCH rate | **66.94%** (93,683/139,942) |
| Majority baseline (always Ora=SL) | 65.68% |
| artifact_consistency_rate (summary; different metric) | 0.368 |
| art_consistent column rate | 36.80% |
| Sanity vs summary marginals | det_match=True, gov_match=True, n_match=True |

**scanner_outcome marginals:** SL=138,091 / TP=1,830 / TO=21  
**oracle_outcome marginals:** SL=91,914 / TP=46,580 / TO=1,448

| scanner_outcome \ oracle_outcome | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 91,873 | 44,791 | 1,427 | 138,091 |
| **TP_HIT** | 41 | 1,789 | 0 | 1,830 |
| **TIMEOUT** | 0 | 0 | 21 | 21 |
| **Col sum** | 91,914 | 46,580 | 1,448 | 139,942 |

| Class | Precision | Recall | Det support | Oracle support | TP |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 66.53% | 99.96% | 138,091 | 91,914 | 91,873 |
| TP_HIT | 97.76% | 3.84% | 1,830 | 46,580 | 1,789 |
| TIMEOUT | 100.00% | 1.45% | 21 | 1,448 | 21 |


### BTCUSDT

| Field | Value |
|---|---|
| CSV | `results/research/btcusdt_trade_anatomy/trade_dataset_BTCUSDT.csv` (128,163,817 bytes; mtime 2026-06-13T11:26:14.354477Z) |
| Summary | `results/research/btcusdt_trade_anatomy/anatomy_summary.json` |
| dataset_sha256 | `09baca48253a50011a8869c991d6618bef79b99cc51764cb0ee71db2a2de0233` |
| n | 139,942 |
| Mapping rate (n_dataset / n_opportunities) | 100.00% |
| LABEL_MATCH rate | **67.22%** (94,068/139,942) |
| Majority baseline (always Ora=SL) | 65.71% |
| artifact_consistency_rate (summary; different metric) | 0.3719 |
| art_consistent column rate | 37.19% |
| Sanity vs summary marginals | det_match=True, gov_match=True, n_match=True |

**scanner_outcome marginals:** SL=137,648 / TP=2,259 / TO=35  
**oracle_outcome marginals:** SL=91,954 / TP=45,561 / TO=2,427

| scanner_outcome \ oracle_outcome | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 91,864 | 43,392 | 2,392 | 137,648 |
| **TP_HIT** | 90 | 2,169 | 0 | 2,259 |
| **TIMEOUT** | 0 | 0 | 35 | 35 |
| **Col sum** | 91,954 | 45,561 | 2,427 | 139,942 |

| Class | Precision | Recall | Det support | Oracle support | TP |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 66.74% | 99.90% | 137,648 | 91,954 | 91,864 |
| TP_HIT | 96.02% | 4.76% | 2,259 | 45,561 | 2,169 |
| TIMEOUT | 100.00% | 1.44% | 35 | 2,427 | 35 |


### ETHUSDT

| Field | Value |
|---|---|
| CSV | `results/research/ethusdt_trade_anatomy/trade_dataset_ETHUSDT.csv` (128,643,376 bytes; mtime 2026-06-13T11:27:56.954963Z) |
| Summary | `results/research/ethusdt_trade_anatomy/anatomy_summary.json` |
| dataset_sha256 | `530c9a35f0db2c120cb9d3bcdbba7013ec4176c44109ae2d318a23556a39e1a0` |
| n | 139,942 |
| Mapping rate (n_dataset / n_opportunities) | 100.00% |
| LABEL_MATCH rate | **67.30%** (94,175/139,942) |
| Majority baseline (always Ora=SL) | 65.68% |
| artifact_consistency_rate (summary; different metric) | 0.3696 |
| art_consistent column rate | 36.96% |
| Sanity vs summary marginals | det_match=True, gov_match=True, n_match=True |

**scanner_outcome marginals:** SL=137,477 / TP=2,411 / TO=54  
**oracle_outcome marginals:** SL=91,912 / TP=46,035 / TO=1,995

| scanner_outcome \ oracle_outcome | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 91,811 | 43,725 | 1,941 | 137,477 |
| **TP_HIT** | 101 | 2,310 | 0 | 2,411 |
| **TIMEOUT** | 0 | 0 | 54 | 54 |
| **Col sum** | 91,912 | 46,035 | 1,995 | 139,942 |

| Class | Precision | Recall | Det support | Oracle support | TP |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 66.78% | 99.89% | 137,477 | 91,912 | 91,811 |
| TP_HIT | 95.81% | 5.02% | 2,411 | 46,035 | 2,310 |
| TIMEOUT | 100.00% | 2.71% | 54 | 1,995 | 54 |


### SOLUSDT

| Field | Value |
|---|---|
| CSV | `results/research/solusdt_trade_anatomy/trade_dataset_SOLUSDT.csv` (128,198,376 bytes; mtime 2026-06-13T11:28:54.424149Z) |
| Summary | `results/research/solusdt_trade_anatomy/anatomy_summary.json` |
| dataset_sha256 | `69cdc70ea422b19937c9d50d4762e4fbbd0050a7f495707f548ad9b9238f5bbc` |
| n | 139,942 |
| Mapping rate (n_dataset / n_opportunities) | 100.00% |
| LABEL_MATCH rate | **67.01%** (93,779/139,942) |
| Majority baseline (always Ora=SL) | 66.04% |
| artifact_consistency_rate (summary; different metric) | 0.3576 |
| art_consistent column rate | 35.76% |
| Sanity vs summary marginals | det_match=True, gov_match=True, n_match=True |

**scanner_outcome marginals:** SL=138,490 / TP=1,414 / TO=38  
**oracle_outcome marginals:** SL=92,423 / TP=45,929 / TO=1,590

| scanner_outcome \ oracle_outcome | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 92,375 | 44,563 | 1,552 | 138,490 |
| **TP_HIT** | 48 | 1,366 | 0 | 1,414 |
| **TIMEOUT** | 0 | 0 | 38 | 38 |
| **Col sum** | 92,423 | 45,929 | 1,590 | 139,942 |

| Class | Precision | Recall | Det support | Oracle support | TP |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 66.70% | 99.95% | 138,490 | 92,423 | 92,375 |
| TP_HIT | 96.61% | 2.97% | 1,414 | 45,929 | 1,366 |
| TIMEOUT | 100.00% | 2.39% | 38 | 1,590 | 38 |


---

## Interpretation gate (measure-before-promote)

Criteria (stated without overclaiming):

1. If LABEL_MATCH is **high** AND off-diagonals are concentrated in **interpretable aliases** → possible **SAFE_ALIAS** candidate (**still not auto-promote**).
2. If LABEL_MATCH is **~ chance** / off-diagonals show **systematically different** generative processes → **HOMONYM / separate populations** (supports **`ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`**).

### What we measured

- Aggregate LABEL_MATCH **67.12%** vs majority-class baseline **65.78%** (Δ ≈ 1.34%).
- Dominant off-diagonal: **LABEL_MISMATCH_SL_TP** = scanner_outcome=SL_HIT × oracle_outcome=TP_HIT (~176k aggregate) — consistent with a **trailing-stop hypothesis (unmeasured)** (`_simulate` trail) vs fixed-stop single-TP `forward_walk(intrabar_fixed)` as a **process difference**, not RV identity. Observation is the terminal label pair only; trail activation/move/exit/touch were **not** measured.
- scanner_outcome **TP_HIT recall** of oracle_outcome TP ≈ **4.15%** — scanner almost never names the oracle win class.
- Published **artifact_consistency_rate** cluster ~**0.36–0.37** is a **different** metric (internal artifact SL_HIT vs mae consistency) than LABEL_MATCH; both are reported; **do not conflate**.

### Verdict this pass

**HOMONYM / separate populations.** Shared tokens (`SL_HIT`/`TP_HIT`/`TIMEOUT`) do **not** make `scanner_outcome` the same random variable as `oracle_outcome`. Evidence supports continued **`ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`** for scanner-stream labels (distinct from L-001 `ATTRIBUTION_BLOCKER_IDENTITY`). **Not** a SAFE_ALIAS promotion candidate this pass. Observation is terminal label pairs only — “detector stopped early” would be an **INFERENCE** requiring unmeasured timestamps.

---

## Promotion flags (all false this pass)

| Flag | Value |
|---|---|
| registry_column_added | **false** |
| l003_frozen | **false** |
| attribution_unblocked | **false** |
| ANALYTICS_SCHEMA_REGISTRY edited | **false** |
| ANALYTICS_LINEAGE_REGISTRY edited | **false** |

---

## Explicit non-goals

- No `forward_walk` re-run (used existing anatomy join surface).
- No registry table edits; no `src/` changes; no venv; no git commit/add.
- No TP1/TP2 label invention.

---

## Cross-links

- Phase A (demoted): `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md`
- Semantics decision §5: `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md`
- F-022 / anatomy: `docs/current-findings.md`, `docs/analysis/cross-instrument-anatomy-2026-06-13.md`
- Impact: `docs/governance/build_manifests/CH-l003b-outcome-population-comparison.impact.json`

### Phase C pointer

See docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md (run l003c_disagreement_population_20260907_175248, doctrine L-003C.v1) - scanner_outcome=SL_HIT × oracle_outcome=TP_HIT LABEL_MISMATCH_SL_TP population characterization on anatomy covariates only (CRT/HTF/manipulation not measured; not on join surface).

---

**Child measurement (L-003F):** joint outcome states `Y_joint=(scanner_outcome,oracle_outcome)` census + EARLY_STOP_CANDIDATE as OBSERVED_CANDIDATE_POPULATION (NOT promoted) — `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` / run_id `l003f_joint_outcome_states_20260907_184519`.

> Alias note (L-003G): `EARLY_STOP_CANDIDATE` ≡ SAFE_ALIAS for canonical `JOINT_STATE_SL_TP` (scanner SL_HIT × oracle TP_HIT); docs-only naming.
