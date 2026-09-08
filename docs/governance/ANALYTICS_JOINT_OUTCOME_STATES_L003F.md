# L-003F — Joint outcome state observation

> **L-003J — Ontology lock pointer:** `JOINT_OUTCOME_STATE` / `Y_joint` is now the **primary measured object** (docs framing). Components `scanner_outcome` / `oracle_outcome` are not rivals. Named joint populations are states, not errors. EARLY_STOP_CANDIDATE remains SAFE_ALIAS for JOINT_STATE_SL_TP only. **NOT** registry promotion. See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md` (run_id `l003j_joint_outcome_state_ontology_20260907_194325`).

**Status:** OBSERVED (measurement complete) — **EARLY_STOP_CANDIDATE = OBSERVED_CANDIDATE_POPULATION (NOT promoted)**  
**L-003 remains NOT frozen** · attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)  
**Date (UTC):** 2026-09-07T18:45:19.742273Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003f_joint_outcome_states_20260907_184519`  
**version / doctrine:** `L-003F.v1`

Machine-readable: `docs/governance/analytics_joint_outcome_states_l003f-2026-09-07.json`.

## Naming correction (L-003G Part0 — docs only)

- **Canonical identity:** `JOINT_STATE_SL_TP` = measured formula `scanner_outcome(art_outcome)==SL_HIT` & `oracle_outcome(outcome)==TP_HIT`.
- **Research alias (SAFE_ALIAS):** `EARLY_STOP_CANDIDATE` — provisional interpretation name only; does **not** assert the detector stopped early (that remains INFERENCE).
- Prior `run_id` machine keys retain `EARLY_STOP_CANDIDATE` for reproducibility; prose/canonical mapping uses `JOINT_STATE_SL_TP`.
- Child measurement: entry-time predictability — `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md`.

## Banner / discipline

**Observation → Measurement → Evidence → Promotion.**

- **Established (prior):** `Y_scanner ≠ Y_oracle` (HOMONYM / `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`) — L-003B.
- **NOT established:** `Y_oracle > Y_scanner`, “scanner wrong”, or that replacing scanner with oracle improves anything.
- **This pass:** construct joint outcome states `Y_joint = (scanner_outcome, oracle_outcome)` and characterize populations — especially `EARLY_STOP_CANDIDATE` as a **candidate research object name only**.

**Question answered:** what joint states exist and how large?  
**Question NOT answered:** which Y is correct / better / should replace the other.

## Terminology parity (L-003-TERM.v1)

| Canonical term | Formula / meaning | Dataset / column | Claim class |
|---|---|---|---|
| `scanner_outcome` | `opportunity_scanner._simulate` → SL_HIT / TP_HIT / TIMEOUT | anatomy `art_outcome` | measured label |
| `oracle_outcome` | `forward_walk(intrabar_fixed)` → SL_HIT / TP_HIT / TIMEOUT | anatomy `outcome` | measured label |
| `LABEL_MATCH` | `scanner_outcome == oracle_outcome` | anatomy join | measured equality; **not** process agreement |
| `LABEL_MISMATCH` | `scanner_outcome != oracle_outcome` | anatomy join | measured inequality |
| `LABEL_MISMATCH_SL_TP` | scanner SL_HIT × oracle TP_HIT | anatomy join | primary mismatch class (= joint state `EARLY_STOP_CANDIDATE`) |
| `JOINT_STATE_SL_TP` (alias `EARLY_STOP_CANDIDATE`) | joint state_id for SL_HIT × TP_HIT | anatomy join | **candidate label for a joint state** — NOT observation that detector stopped early (that remains **INFERENCE**) |
| path geometry | {`bars_to_peak_within_trade`, `mfe_r`, `time_to_bottom_path`, `favorable_first`, `|mae_r|`} | anatomy | measured (brief fingerprint only) |
| trailing-stop | trail activation/move/exit/touch | — | **hypothesis only (unmeasured)** |

**Attribution blockers (always name which):**
- `ATTRIBUTION_BLOCKER_IDENTITY` — 12 `opportunities.produced_by` UNKNOWN (L-001)
- `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` — scanner_outcome ≉ oracle_outcome as RVs (L-003B HOMONYM)

## Joint state machine (mechanical)

| scanner | oracle | state_id |
|---|---|---|
| TP_HIT | TP_HIT | BOTH_TP |
| SL_HIT | SL_HIT | BOTH_SL |
| TIMEOUT | TIMEOUT | BOTH_TIMEOUT |
| SL_HIT | TP_HIT | JOINT_STATE_SL_TP (alias EARLY_STOP_CANDIDATE) |
| TP_HIT | SL_HIT | FALSE_TP_CANDIDATE |
| TIMEOUT | TP_HIT | LATE_REALIZATION |
| TIMEOUT | SL_HIT | LATE_FAILURE |
| TP_HIT | TIMEOUT | SCANNER_TP_ORACLE_TIMEOUT |
| SL_HIT | TIMEOUT | SCANNER_SL_ORACLE_TIMEOUT |

Other combos → `OTHER_<scanner>_<oracle>`. Raw pair key retained as `scanner_outcome|oracle_outcome`.

## A. Population census (aggregate)

n = **559,768** (BNB+BTC+ETH+SOL).

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 367,923 | 65.73% |
| `EARLY_STOP_CANDIDATE` | 176,471 | 31.53% |
| `BOTH_TP` | 7,634 | 1.36% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 7,312 | 1.31% |
| `FALSE_TP_CANDIDATE` | 280 | 0.05% |
| `BOTH_TIMEOUT` | 148 | 0.03% |

### Confusion reconciliation (scanner × oracle) — aggregate

| scanner \ oracle | SL_HIT | TP_HIT | TIMEOUT | Row sum |
|---|---:|---:|---:|---:|
| **SL_HIT** | 367,923 | 176,471 | 7,312 | 551,706 |
| **TP_HIT** | 280 | 7,634 | 0 | 7,914 |
| **TIMEOUT** | 0 | 0 | 148 | 148 |

**L-003B reconcile:** EARLY_STOP_CANDIDATE aggregate n = **176,471** (expected LABEL_MISMATCH_SL_TP 176,471; match=True). BNB EARLY_STOP_CANDIDATE n = **44,791** (must = 44,791; match=True).

## B. Information asymmetry (descriptive — not “which is better”)

### 1. Scanner-unique mass (LABEL_MISMATCH rows)

n_mismatch = **184,063** (32.88% of all).

| state_id (mismatch only) | n | share of mismatch |
|---|---:|---:|
| `EARLY_STOP_CANDIDATE` | 176,471 | 95.88% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 7,312 | 3.97% |
| `FALSE_TP_CANDIDATE` | 280 | 0.15% |

### 2. Match mass (LABEL_MATCH by BOTH_*)

LABEL_MATCH n = **375,705** (67.12%).

| state_id | n | rate_of_all | rate_of_match |
|---|---:|---:|---:|
| `BOTH_SL` | 367,923 | 65.73% | 97.93% |
| `BOTH_TP` | 7,634 | 1.36% | 2.03% |
| `BOTH_TIMEOUT` | 148 | 0.03% | 0.04% |

### 3. Marginal comparison (description only — restated from L-003B)

| Label | scanner_outcome n / share | oracle_outcome n / share |
|---|---:|---:|
| SL_HIT | 551,706 / 98.56% | 368,203 / 65.78% |
| TP_HIT | 7,914 / 1.41% | 184,105 / 32.89% |
| TIMEOUT | 148 / 0.03% | 7,460 / 1.33% |

These are **label-distribution descriptions**, not a ranking of quality.

### 4. Optional mutual-information-style note

| Quantity | Value |
|---|---|
| fraction of rows in mismatch states | 32.88% |
| entropy H(Y_joint) bits | 1.0978 |
| entropy H(scanner_outcome) bits | 0.1106 |
| entropy H(oracle_outcome) bits | 1.0082 |

Descriptive only — not a claim of superiority.

## C. EARLY_STOP_CANDIDATE as research object (pre-promotion gates)

**Promotion flags: all false.** Status = **OBSERVED_CANDIDATE_POPULATION**. Do **NOT** promote to ontology/registry. Candidate name only; “detector stopped early” remains **INFERENCE**.

### Sample size + rate

| Scope | n_all | EARLY_STOP_CANDIDATE n | rate |
|---|---:|---:|---:|
| BNBUSDT | 139,942 | 44,791 | 32.01% |
| BTCUSDT | 139,942 | 43,392 | 31.01% |
| ETHUSDT | 139,942 | 43,725 | 31.25% |
| SOLUSDT | 139,942 | 44,563 | 31.84% |
| **AGGREGATE** | 559,768 | 176,471 | 31.53% |

Per-instrument rate: mean=31.53%, std=0.48%, range=[31.01%, 32.01%].

### Leave-one-instrument-out stability of rate

| Fold | n_train | ESC n | ESC rate |
|---|---:|---:|---:|
| holdout BNBUSDT | 419,826 | 131,680 | 31.37% |
| holdout BTCUSDT | 419,826 | 133,079 | 31.70% |
| holdout ETHUSDT | 419,826 | 132,746 | 31.62% |
| holdout SOLUSDT | 419,826 | 131,908 | 31.42% |

LOO rate mean=31.53%, std=0.16%, range=[31.37%, 31.70%] (Δ=0.33%).

**Holdout note:** no chronological train/holdout partition on anatomy CSV → instrument LOO as stability; time dimension remains **in-sample descriptive**.

### Reproducibility

| Field | Value |
|---|---|
| git_commit_sha | `d7c25f6e55616261b8b229b000875abd3bd315eb` |
| BNB dataset_sha256 | `f8bdabbe683fe43f54f3853dcce809f113fe22e9385828210d48c6cc2aa34934` |
| BTC dataset_sha256 | `09baca48253a50011a8869c991d6618bef79b99cc51764cb0ee71db2a2de0233` |
| ETH dataset_sha256 | `530c9a35f0db2c120cb9d3bcdbba7013ec4176c44109ae2d318a23556a39e1a0` |
| SOL dataset_sha256 | `69cdc70ea422b19937c9d50d4762e4fbbd0050a7f495707f548ad9b9238f5bbc` |
| usecols | `art_outcome, outcome, bars_to_peak_within_trade, mfe_r, time_to_bottom_path, favorable_first, mae_r, direction` |

### Path-geometry fingerprint (medians) — link L-003C/D/E; not a full re-study

| Metric | EARLY_STOP_CANDIDATE | BOTH_SL | BOTH_TP |
|---|---:|---:|---:|
| n | 176471 | 367923 | 7634 |
| bars_to_peak_within_trade median | 6.00 | 1.00 | 1.00 |
| mfe_r median | 4.56 | 1.74 | 6.49 |
| time_to_bottom_path (T_MAE) median | 40.00 | 45.00 | 32.00 |
| favorable_first rate | 69.95% | 17.37% | 82.68% |
| \|mae_r\| median | 0.86 | 3.63 | 0.98 |

Brief contrast only (aligns directionally with L-003C/D/E path geometry on LABEL_MISMATCH_SL_TP vs LABEL_MATCH). **No trailing-stop claimed as measured.**

## D. Latent-variable hypotheses (labeled hypotheses, not findings)

| ID | Statement | Claim class |
|---|---|---|
| H_SCANNER_CAPTUREABILITY | Y_scanner may reflect captureability under trailing process | **HYPOTHESIS** (untested) |
| H_ORACLE_PATH_REACHABILITY | Y_oracle may reflect path reachability under fixed exit | **HYPOTHESIS** (untested) |
| H_ESC_DISTINCT_PATH_STATE | EARLY_STOP_CANDIDATE may be a distinct path-state population | **HYPOTHESIS** (untested) |

These are untested interpretations of existing measurements — not promotions and not evidence of superiority.

## Per-instrument census

### BNBUSDT

| Field | Value |
|---|---|
| CSV | `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv` |
| dataset_sha256 | `f8bdabbe683fe43f54f3853dcce809f113fe22e9385828210d48c6cc2aa34934` |
| n | 139,942 |
| LABEL_MATCH rate | 66.94% |
| EARLY_STOP_CANDIDATE n / rate | 44,791 / 32.01% |
| L-003B reconcile ESC | 44791 (match=True) |

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 91,873 | 65.65% |
| `EARLY_STOP_CANDIDATE` | 44,791 | 32.01% |
| `BOTH_TP` | 1,789 | 1.28% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 1,427 | 1.02% |
| `FALSE_TP_CANDIDATE` | 41 | 0.03% |
| `BOTH_TIMEOUT` | 21 | 0.02% |

Confusion (scanner × oracle): SL×SL=91,873, SL×TP=44,791, SL×TO=1,427; TP×SL=41, TP×TP=1,789, TP×TO=0; TO×SL=0, TO×TP=0, TO×TO=21.

### BTCUSDT

| Field | Value |
|---|---|
| CSV | `results/research/btcusdt_trade_anatomy/trade_dataset_BTCUSDT.csv` |
| dataset_sha256 | `09baca48253a50011a8869c991d6618bef79b99cc51764cb0ee71db2a2de0233` |
| n | 139,942 |
| LABEL_MATCH rate | 67.22% |
| EARLY_STOP_CANDIDATE n / rate | 43,392 / 31.01% |
| L-003B reconcile ESC | 43392 (match=True) |

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 91,864 | 65.64% |
| `EARLY_STOP_CANDIDATE` | 43,392 | 31.01% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 2,392 | 1.71% |
| `BOTH_TP` | 2,169 | 1.55% |
| `FALSE_TP_CANDIDATE` | 90 | 0.06% |
| `BOTH_TIMEOUT` | 35 | 0.03% |

Confusion (scanner × oracle): SL×SL=91,864, SL×TP=43,392, SL×TO=2,392; TP×SL=90, TP×TP=2,169, TP×TO=0; TO×SL=0, TO×TP=0, TO×TO=35.

### ETHUSDT

| Field | Value |
|---|---|
| CSV | `results/research/ethusdt_trade_anatomy/trade_dataset_ETHUSDT.csv` |
| dataset_sha256 | `530c9a35f0db2c120cb9d3bcdbba7013ec4176c44109ae2d318a23556a39e1a0` |
| n | 139,942 |
| LABEL_MATCH rate | 67.30% |
| EARLY_STOP_CANDIDATE n / rate | 43,725 / 31.25% |
| L-003B reconcile ESC | 43725 (match=True) |

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 91,811 | 65.61% |
| `EARLY_STOP_CANDIDATE` | 43,725 | 31.25% |
| `BOTH_TP` | 2,310 | 1.65% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 1,941 | 1.39% |
| `FALSE_TP_CANDIDATE` | 101 | 0.07% |
| `BOTH_TIMEOUT` | 54 | 0.04% |

Confusion (scanner × oracle): SL×SL=91,811, SL×TP=43,725, SL×TO=1,941; TP×SL=101, TP×TP=2,310, TP×TO=0; TO×SL=0, TO×TP=0, TO×TO=54.

### SOLUSDT

| Field | Value |
|---|---|
| CSV | `results/research/solusdt_trade_anatomy/trade_dataset_SOLUSDT.csv` |
| dataset_sha256 | `69cdc70ea422b19937c9d50d4762e4fbbd0050a7f495707f548ad9b9238f5bbc` |
| n | 139,942 |
| LABEL_MATCH rate | 67.01% |
| EARLY_STOP_CANDIDATE n / rate | 44,563 / 31.84% |
| L-003B reconcile ESC | 44563 (match=True) |

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 92,375 | 66.01% |
| `EARLY_STOP_CANDIDATE` | 44,563 | 31.84% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 1,552 | 1.11% |
| `BOTH_TP` | 1,366 | 0.98% |
| `FALSE_TP_CANDIDATE` | 48 | 0.03% |
| `BOTH_TIMEOUT` | 38 | 0.03% |

Confusion (scanner × oracle): SL×SL=92,375, SL×TP=44,563, SL×TO=1,552; TP×SL=48, TP×TP=1,366, TP×TO=0; TO×SL=0, TO×TP=0, TO×TO=38.


## Explicit non-promotions

1. **EARLY_STOP_CANDIDATE** not promoted to ontology or registry — status remains `OBSERVED_CANDIDATE_POPULATION`.
2. No claim that scanner should be replaced by oracle (or vice versa).
3. No claim that EARLY_STOP_CANDIDATE proves the detector stopped early (INFERENCE without timestamps).
4. No trailing-stop measurement claimed.
5. L-003 not frozen; attribution not unblocked; economic claims not allowed.
6. No `src/` / registry / schema changes in this pass.

## Parent pointers

- L-003B population comparison: `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md`
- L-003C mismatch population: `docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md`
- L-003D path geometry: `docs/governance/ANALYTICS_OUTCOME_PATH_MECHANICS_L003D.md`
- L-003E adverse timing: `docs/governance/ANALYTICS_OUTCOME_ADVERSE_TIMING_L003E.md`
- Terminology parity: `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md`


---

**L-003G pointer:** Entry-time predictability of `JOINT_STATE_SL_TP` — `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md` (run_id `l003g_joint_state_entry_predictability_20260907_190242`; version L-003G.v1).

## Child measurement (L-003H)

- Trail/exit transition candle replay: `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md` (run_id `l003h_trail_exit_transitions_20260907_192115`).
