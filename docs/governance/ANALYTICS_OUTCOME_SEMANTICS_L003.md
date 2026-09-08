# L-003 Outcome Semantics (measure-before-promote)

**Status:** OBSERVED_PARTIAL (Phase A incomplete) — **NOT FROZEN**; Phase B confusion matrix required before freeze — **NOT** a registry promotion
**Date (UTC):** 2026-09-07T17:21:43.552Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`

## Identity

| Field | Value |
|---|---|
| finding_id | L-003 |
| run_id | `l003_outcome_semantics_20260907_172143` |
| git_commit_sha | `d7c25f6e55616261b8b229b000875abd3bd315eb` |
| classifier / doctrine_version | `L-003.v1` |
| status | OBSERVED_PARTIAL (Phase A = detection vocab only; NOT FROZEN pending Phase B) — NOT a registry promotion |

Opened in `docs/governance/ANALYTICS_LINEAGE_ANOMALY_REVIEW.md` (L-003). Already frozen in `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md` §5: `opportunities.outcome` / `rr_achieved` are **NOT eligible** for attribution (detection-stream).

Machine-readable pin: `docs/governance/analytics_outcome_semantics_l003-2026-09-07.json`.

> **BANNER — demoted from FROZEN (user discipline correction)**  
> **Phase A (this document):** DETECTION_STREAM vocabulary census only. Incomplete for the claim that detection and governing oracle are the same (or aliasable) random variable.  
> **Phase B (required before freeze):** `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` + `docs/governance/analytics_outcome_population_comparison_l003b-2026-09-07.json` (scanner_outcome × oracle_outcome confusion matrix on anatomy trade_dataset). Phase A below = detection vocab only — **incomplete** for the semantic-boundary / same-RV claim.
> Discipline: Observation → Measurement → Evidence → Promotion. Promotion flags remain false.  
> Label note: both sides use SL_HIT / TP_HIT / TIMEOUT (not TP1/TP2); governing is forward_walk(intrabar_fixed) single TP.



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

## Populations (must keep separate)

Three distinct outcome populations (plus one architectural neighbor). **Do not collapse.** Canonical RV names: `scanner_outcome` (DETECTION_STREAM), `oracle_outcome` (GOVERNING_ORACLE), `live_outcome` (LIVE_INGEST_TWIN). Bare `outcome` is not used as an RV name in new prose.

### 1. DETECTION_STREAM

| | |
|---|---|
| **Emitter** | `scripts/research/opportunity_scanner.py` → `_simulate` |
| **RV name** | `scanner_outcome` (CSV/JSON field often named `outcome` on opportunities; anatomy join column `art_outcome`) |
| **Label model** | Trailing stop `trail_mult=0.5` (0.5R). Labels: `SL_HIT` / `TP_HIT` / `TIMEOUT` |
| **Filename** | `**/opportunities.jsonl` |
| **Attribution eligible?** | **No** |

These are detection-time path labels (`scanner_outcome`). They are **not** `oracle_outcome` / governing trade-ledger truth (F-022).

### 2. GOVERNING_ORACLE

| | |
|---|---|
| **RV name** | `oracle_outcome` (anatomy CSV column literally named `outcome`) |
| **Emitter / oracle** | `forward_walk(intrabar_fixed)` and related research re-derivation (anatomy pipeline; e.g. `scripts/analysis/bnbusdt_trade_anatomy.py`) |
| **Label model** | Fixed-stop governing exit; realized SL/TP/TIMEOUT **derived** |
| **Evidence** | F-022 published distributions + consistency rates (cited below; not re-invented) |
| **Attribution eligible?** | Still gated — governing path is required for eligibility, but this artifact does **not** unlock Phase 5 Attribution |

### 3. LIVE_INGEST_TWIN

| | |
|---|---|
| **RV name** | `live_outcome` |
| **Emitter** | `scripts/research/ingest_live_outcomes.py` |
| **Label model** | `WIN` / `LOSS` / `BREAKEVEN` (+ `source=live_alerts`) |
| **Filename** | e.g. `logs/live_training.jsonl` — **different basename** |
| **Family** | Outside `opportunities` unless `FAMILY_DEFAULTS` intentionally expanded (**S-002**) |
| **Attribution eligible?** | **No** (separate population; not measured as opportunities) |

### 4. Neighbor (do not collapse): SPINE_LEDGER / TRADE_OPENED

Production spine `TRADE_OPENED` / events-family ledger is an **architectural neighbor** of the scanner detection stream (anomaly review **S-004**), not an alternate writer of `opportunities.jsonl`. Keep populations separate.

---

## Measured vocabulary census (Phase A — incomplete for same-RV / freeze claim)

Commit-pinned measurement at `d7c25f6e55616261b8b229b000875abd3bd315eb` / run `l003_outcome_semantics_20260907_172143`. Stdlib JSON stream only.

### DETECTION_STREAM (`**/opportunities.jsonl`)

Aggregate over 5 local files (run_header excluded):

| Label | Aggregate count |
|---|---|
| SL_HIT | 644643 |
| TP_HIT | 9258 |
| TIMEOUT | 199 |
| **n_outcome_rows_total** | **654100** |

Per-file pins:

| Path | instrument / run_id | n | SL_HIT | TP_HIT | TIMEOUT |
|---|---|---|---|---|---|
| `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl` | XAUUSD / `xauusd_phase1_20260723` | 94332 | 92937 | 1344 | 51 |
| `logs/BNBUSDT/20260530_011521/opportunities.jsonl` | BNBUSDT / `20260530_011521` | 139942 | 138091 | 1830 | 21 |
| `logs/BTCUSDT/anatomy_BTCUSDT_20260613/opportunities.jsonl` | BTCUSDT / `anatomy_BTCUSDT_20260613` | 139942 | 137648 | 2259 | 35 |
| `logs/ETHUSDT/anatomy_ETHUSDT_20260613/opportunities.jsonl` | ETHUSDT / `anatomy_ETHUSDT_20260613` | 139942 | 137477 | 2411 | 54 |
| `logs/SOLUSDT/anatomy_SOLUSDT_20260613/opportunities.jsonl` | SOLUSDT / `anatomy_SOLUSDT_20260613` | 139942 | 138490 | 1414 | 38 |

**Observation:** `SL_HIT` / `TP_HIT` / `TIMEOUT` dominate exactly as expected for `_simulate` trailing-stop labels. No other outcome tokens observed in sampled opportunities streams.

### LIVE_INGEST_TWIN (local presence check)

| Path | outcome rows measured | notes |
|---|---|---|
| `logs/live_alerts.jsonl` | 0 | file present; no `outcome` field in scanned rows |
| `logs/live_rail.jsonl` | 0 | file present; no `outcome` field in scanned rows |
| `logs/live_training.jsonl` | ABSENT | default CLI output from ingest script; not on disk this pass |

**Code-declared vocab** (from `ingest_live_outcomes.py`, not corpus-observed here): `WIN` / `LOSS` / `BREAKEVEN`.

### Published F-022 consistency (docs only — do not invent)

From `docs/current-findings.md` (F-022) and `docs/analysis/cross-instrument-anatomy-2026-06-13.md`:

| Instrument | artifact_consistency_rate |
|---|---|
| BNBUSDT | **0.368** |
| BTCUSDT | **0.372** |
| ETHUSDT | **0.370** |
| SOLUSDT | **0.358** |

Cluster ~**0.36–0.37**. Scanner stream (`scanner_outcome`) reads ~98–99% `SL_HIT` while `oracle_outcome` fixed-stop exit is ~66% SL / ~33% TP. Oracle path named: **`forward_walk(intrabar_fixed)`**.

BNB evidence pin (F-022): `results/research/bnbusdt_trade_anatomy/anatomy_summary.json` — scanner_outcome `138,091 SL / 1,830 TP / 21 TIMEOUT` vs oracle_outcome `91,914 SL / 46,580 TP / 1,448 TIMEOUT`.

---

## Semantic rules (mechanical / falsifiable)

1. **R-L003-001 (PROHIBITED_ALIAS / HOMONYM):** `scanner_outcome` (DETECTION_STREAM; column `outcome`/`art_outcome`) MUST NOT be aliased to `oracle_outcome` (GOVERNING_ORACLE; column `outcome`).
2. **R-L003-002 (ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS):** `DETECTION_STREAM.rr_achieved` / `scanner_outcome` MUST NOT feed attribution eligibility (homonym vs `oracle_outcome`). Distinct from `ATTRIBUTION_BLOCKER_IDENTITY` (L-001 UNKNOWN `produced_by`).
3. **R-L003-003 (CONTAMINATION_INHERITANCE):** Training/calibration that reads opportunities `scanner_outcome` (field `outcome`) / `rr_achieved` without `oracle_outcome` re-derivation inherits **F-022** contamination. Already-documented examples: **F-045** (RR-model kill-test indeterminate on contaminated labels); Gaussian lineage consumers (`docs/governance/gaussian_lineage_audit.md`) — not reopened here.
4. **R-L003-004 (ATTRIBUTION_GATE):** UNKNOWN / unresolved governing/`oracle_outcome` path ⇒ attribution blocked via **`ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`** and/or unresolved oracle path (existing doctrine). Always name the blocker class.
5. **R-L003-005 (POPULATION_SEPARATION):** `LIVE_INGEST_TWIN` stays outside `opportunities` unless FAMILY_DEFAULTS intentionally expanded (S-002).
6. **R-L003-006 (COMPANION_BOUND):** `mfe` / `mae` / `duration_candles` on opportunities inherit DETECTION_STREAM semantics (same `_simulate` emitter).

---

## Holdout / promotion gate

**This pass promotes nothing into registries.**

| Question | Answer |
|---|---|
| Registry column added? | **false** |
| Attribution unblocked? | **false** |
| ANALYTICS_SCHEMA_REGISTRY edited? | **false** |
| ANALYTICS_LINEAGE_REGISTRY edited? | **false** |

### What could be promoted *later* (doctrine-only until gated)

- An optional annotation such as `outcome_population` / `outcome_semantics` **if and only if**:
  1. Measured **variance across populations** remains material (already evidenced: SL_HIT/TP_HIT/TIMEOUT vs WIN/LOSS/BREAKEVEN vs governing redistributions), **and**
  2. A concrete **consumer** needs the distinction in-query (not just narrative clarity).

### What must stay doctrine-only for now

- The prohibition on stream-outcome → edge claims.
- Refusal to treat opportunities `scanner_outcome` (field `outcome`) / `rr_achieved` as attribution-eligible (`ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`).
- Population separation DETECTION vs GOVERNING vs LIVE.

### EC-001 holdout lesson (sibling pattern)

EC-001 census: **268/268 CORPUS_VERIFIED** → **no** `evidence_class` column promoted (`docs/governance/analytics_evidence_class_census-2026-09-07.md`). Same Phase B / measure-before-promote discipline applies to L-003: observation artifact now; column later only if variance + consumer warrant.

---

## Explicit non-goals

- No `produced_by` fills (still blocked on **L-001** doctrine choice).
- No Phase 5 Attribution unlock.
- No `src/` changes.
- No venv / infrastructure work in this pass.
- No ANALYTICS_SCHEMA_REGISTRY or ANALYTICS_LINEAGE_REGISTRY table mutations.

---

## Cross-links

- `docs/governance/ANALYTICS_LINEAGE_ANOMALY_REVIEW.md` — L-003 opening
- `docs/current-findings.md` — **F-022**, **F-045**
- `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md` — §5 attribution eligibility
- `docs/governance/analytics_evidence_class_census-2026-09-07.md` / `.json` — EC-001 sibling measurement pattern
- `docs/analysis/cross-instrument-anatomy-2026-06-13.md` — cross-instrument consistency table
- `docs/analysis/BNBUSDT_TRADE_ANATOMY_2026_06_13.md` — BNB anatomy
- `docs/governance/gaussian_lineage_audit.md` — contaminated-label consumer example
- Impact note: `docs/governance/build_manifests/CH-l003-outcome-semantics.impact.json`

---

## Verdict

L-003 Phase A measurement artifact exists and is commit-pinned, but status is **OBSERVED_PARTIAL — NOT FROZEN**. Phase A only measured DETECTION_STREAM / `scanner_outcome` vocabulary; it did **not** measure whether `scanner_outcome` is the same RV as `oracle_outcome`. **Phase B** (`ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md`) supplies the Detection × Oracle confusion matrices. Scanner-stream labels (`scanner_outcome`) remain **non-attributable**. `oracle_outcome` remains the truth derivation for realized exits. `live_outcome` remains a separate population. **No registry promotion. Attribution remains blocked under `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` (and separately `ATTRIBUTION_BLOCKER_IDENTITY` for L-001). l003_frozen = false.**

### Phase B pointer

See `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` and `docs/governance/analytics_outcome_population_comparison_l003b-2026-09-07.json` (run `l003b_outcome_population_comparison_20260907_173349`, doctrine `L-003B.v1`).

### Phase C pointer

See docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md (run l003c_disagreement_population_20260907_175248, doctrine L-003C.v1) - scanner_outcome=SL_HIT × oracle_outcome=TP_HIT LABEL_MISMATCH_SL_TP population characterization on anatomy covariates only (CRT/HTF/manipulation not measured; not on join surface).
