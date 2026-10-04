# L-003 Terminology Parity Audit (ontology ↔ implementation)

> **L-003J — Ontology lock pointer:** Prefer `JOINT_OUTCOME_STATE` membership over rival-label / who-is-right framing. LABEL_MATCH/MISMATCH stay equality-only helpers. See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

- **finding_id / version:** `L-003-TERM.v1`
- **run_id:** `l003_terminology_parity_20260907_182845`
- **generated_at_utc:** `2026-09-07T18:28:45.866Z`
- **git_commit_sha:** `d7c25f6e55616261b8b229b000875abd3bd315eb`
- **status:** DOCUMENTATION CORRECTION ONLY — **no new measurements**
- **companion JSON:** `docs/governance/analytics_l003_terminology_parity_audit-2026-09-07.json`

## Purpose

Apply user-specified terminology corrections across L-001→L-003E analytics outcome docs so prose matches ontology and measured formulas — without inventing science, without registry/schema edits, without re-running anatomy / forward_walk.

## Highest-priority correction callout

**LABEL_MATCH / LABEL_MISMATCH (formerly AGREE / DISAGREE)**

- Formula: `scanner_outcome == oracle_outcome` is **terminal label equality only**.
- It is **not** semantic agreement, process agreement, or proof that scanner and oracle are the same RV.
- Primary mismatch class: **LABEL_MISMATCH_SL_TP** = scanner SL_HIT × oracle TP_HIT (formerly DISAGREE_SL_TP).
- JSON machine keys `AGREE` / `DISAGREE` / `DISAGREE_SL_TP` are **retained** for prior `run_id` reproducibility; MD prose uses canonical terms + synonym notes.

## Term ↔ Formula ↔ Dataset ↔ Claim

| Term | Formula / definition | Dataset / column | Claim class |
|---|---|---|---|
| `scanner_outcome` | `opportunity_scanner._simulate` → SL_HIT/TP_HIT/TIMEOUT | opportunities field `outcome`; anatomy `art_outcome` | measured label |
| `oracle_outcome` | `forward_walk(intrabar_fixed)` → SL_HIT/TP_HIT/TIMEOUT | anatomy column `outcome` | measured label |
| `live_outcome` | `ingest_live_outcomes` → WIN/LOSS/BREAKEVEN | live twin streams | measured label (separate pop.) |
| `attribution_target` | trade edge realization (implicit) | — | eligibility target (not a terminal label RV) |
| bare `outcome` | — | — | **reserved for none** of the three RVs in new prose |
| `LABEL_MATCH` | scanner_outcome == oracle_outcome | anatomy join | measured equality only |
| `LABEL_MISMATCH` | scanner_outcome != oracle_outcome | anatomy join | measured inequality |
| `LABEL_MISMATCH_SL_TP` | SL_HIT × TP_HIT (scanner × oracle) | anatomy join | primary mismatch class |
| path geometry / path-shape metrics | {time_to_peak, MFE, T_MAE} | anatomy | measured set |
| `time_to_peak` / peak duration | `bars_to_peak_within_trade` | anatomy | measured (**KEEP — good**) |
| `T_MAE` | `time_to_bottom_path` = timing of deepest adverse on PEAK_HORIZON path | anatomy | measured timing only (not magnitude+timing; not first stop-threat) |
| trailing-stop / path-mechanics hypothesis | trail activation/move/exit/touch | — | **hypothesis only (unmeasured)** |
| “detector stopped early” | would need detector_exit_ts < oracle_tp_ts | — | **INFERENCE**, not observation |
| `ATTRIBUTION_BLOCKER_IDENTITY` | 12 opportunities.produced_by UNKNOWN | L-001 | blocker class |
| `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` | scanner_outcome ≠ oracle_outcome as RVs | L-003B HOMONYM | blocker class |

## Match / Exceeds evidence (user summary alignment)

### Match (docs now state consistently)

1. Three outcome RVs disambiguated: scanner / oracle / live (+ attribution_target).
2. LABEL_MATCH = label equality only; HOMONYM still stands from L-003B numbers.
3. Primary off-diagonal named LABEL_MISMATCH_SL_TP.
4. Trailing-stop / path-mechanics language downgraded to **hypothesis (unmeasured)** where it appeared as story.
5. T_MAE described as early MAE timing / early-path minimum (timing of deepest adverse), not FAE / first stop-threat / magnitude+timing.
6. Measured path set preferred as **path geometry / path-shape metrics**.
7. Attribution blocked always split into IDENTITY vs OUTCOME_SEMANTICS when named.
8. Early-stop / “detector stopped early” marked **INFERENCE** (unmeasured timestamps).
9. time_to_peak / peak duration **kept** as good measured separator.

### Exceeds evidence (intentionally avoided)

- No new anatomy joins, no forward_walk re-run, no trail-touch instrumentation.
- No claim that LABEL_MATCH implies process agreement.
- No promotion / freeze / attribution unlock.
- No registry table / schema / `src/` changes.

## Files touched + what changed

| File | Change |
|---|---|
| `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md` | §5 L-003 / eligibility prose: scanner_outcome; attribution blocker split; TERM audit pointer |
| `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md` | RV names on populations; rules cite scanner/oracle; attribution blocker classes; TERM banner |
| `docs/governance/ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` | LABEL_MATCH language; scanner×oracle matrix headers; HOMONYM → ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS; hypothesis note on trailing |
| `docs/governance/ANALYTICS_OUTCOME_DISAGREEMENT_POPULATION_L003C.md` | AGREE/DISAGREE → LABEL_MATCH/LABEL_MISMATCH (+ synonym); path geometry wording |
| `docs/governance/ANALYTICS_OUTCOME_PATH_MECHANICS_L003D.md` | Title/body → path geometry; trailing as hypothesis; LABEL_* renames; early-stop inference note |
| `docs/governance/ANALYTICS_OUTCOME_ADVERSE_TIMING_L003E.md` | Early MAE timing framing; T_MAE definition tightened; hypothesis/inference discipline; LABEL_* renames |
| `docs/governance/analytics_outcome_semantics_l003-2026-09-07.json` | Added `terminology_parity` + `label_vocabulary` (keys preserved) |
| `docs/governance/analytics_outcome_population_comparison_l003b-2026-09-07.json` | same |
| `docs/governance/analytics_outcome_disagreement_population_l003c-2026-09-07.json` | same |
| `docs/governance/analytics_outcome_path_mechanics_l003d-2026-09-07.json` | same |
| `docs/governance/analytics_outcome_adverse_timing_l003e-2026-09-07.json` | same |
| `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md` | **new** (this file) |
| `docs/governance/analytics_l003_terminology_parity_audit-2026-09-07.json` | **new** |
| `docs/governance/build_manifests/CH-l003-terminology-parity.impact.json` | **new** |

## Historical synonyms left in place (with note)

- JSON object keys / metric field names: `AGREE`, `DISAGREE`, `DISAGREE_SL_TP`, `n_AGREE`, `art_outcome`, anatomy `outcome` — **unchanged** for reproducibility of prior run_ids (`l003*`).
- Finding ids L-003C/D/E titles retain lineage; prose uses corrected terms.
- Finding filename `...PATH_MECHANICS...` retained; measured-set references prefer path geometry.

## Explicit non-goals (this pass)

- No new measurements
- No `src/` edits
- No registry table schema changes
- No git commit/add
- No venv

## Verdict

Documentation parity for L-001→L-003E outcome vocabulary is applied. Measured numbers and prior run_ids are intact. Attribution remains blocked; L-003 remains unfrozen.

---

**Child measurement (L-003F):** joint outcome states `Y_joint=(scanner_outcome,oracle_outcome)` census + EARLY_STOP_CANDIDATE as OBSERVED_CANDIDATE_POPULATION (NOT promoted) — `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` / run_id `l003f_joint_outcome_states_20260907_184519`.

## L-003G naming note (docs only — 2026-09-07)

- Canonical joint-state identity for scanner SL_HIT × oracle TP_HIT: **`JOINT_STATE_SL_TP`**.
- Research alias (SAFE_ALIAS style): **`EARLY_STOP_CANDIDATE`** (provisional interpretation; machine keys / prior run_ids unchanged).
- Primary doc updated: `ANALYTICS_JOINT_OUTCOME_STATES_L003F.md` + companion JSON terminology mapping.
- No registry/ontology promotion; no re-measurement in this naming note.

## L-003M noun-parity pointer (docs only — 2026-09-07)

- **finding / version:** `L-003M.v1` · **status:** `NOUN_PARITY_LOCKED` · **run_id:** `l003m_noun_parity_20260907_201028`
- Canonical StateIDs are coordinate-only `STATE_*` (`STATE_SL_TP` etc.); L-003F / pre-L-003M names (`JOINT_STATE_SL_TP`, `EARLY_STOP_CANDIDATE`, …) = **research aliases only**.
- Prefer `MATCH_RELATION` (LABEL_MATCH/MISMATCH = terminal-label equality); never `CORRECTNESS_RELATION`.
- Prefer `scanner_terminal_label` / `oracle_terminal_label` when MeasurementObject not named; Process-vs-Variable rewrite: `Y_* emitted by <process>(...)`.
- Measured path noun: **path geometry descriptors** `{time_to_peak, MFE, T_MAE, exit-order inequality}`.
- Artifact: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` + `docs/governance/analytics_noun_parity_l003m-2026-09-07.json`.
- No end-to-end rewrite of this file; no src/schema/measurement/commit.
