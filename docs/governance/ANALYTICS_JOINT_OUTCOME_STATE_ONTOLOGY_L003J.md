# L-003J â€” Ontology lock: JOINT_OUTCOME_STATE is primary

> **PACKAGE FREEZE (L-003-FREEZE.v1):** status **L003_PACKAGE_FROZEN** — further L-003 doctrine/noun/ontology edits **PROHIBITED** except errata. New research -> `docs/research/JOINT_STATE_EXPLAINABILITY.md`. run_id `l003_package_freeze_20260907_201945`. Pin `d7c25f6e55616261b8b229b000875abd3bd315eb`.

**Status:** ONTOLOGY_LOCKED (measurement-object framing) · package **L003_PACKAGE_FROZEN** â€” **NOT** registry promotion  
**L-003 package status: L003_PACKAGE_FROZEN** â€” attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)  
**Date (UTC):** 2026-09-07T19:43:25.602796Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003j_joint_outcome_state_ontology_20260907_194325`  
**version / doctrine:** `L-003J.v1`

Machine-readable: `docs/governance/analytics_joint_outcome_state_ontology_l003j-2026-09-07.json`.  
Impact: `docs/governance/analytics_joint_outcome_state_ontology_l003j_impact-2026-09-07.json`.

## Banner / discipline

**Observation â†’ Measurement â†’ Evidence â†’ Promotion.**

This pass is **docs/ontology only**:

- Promote **JOINT_OUTCOME_STATE** (`Y_joint = (Y_scanner, Y_oracle)`) to the **primary measured object** in framing.
- Does **NOT** promote analytics registry columns, EARLY_STOP to ontology-as-fact, attribution unlock, or causal upgrades.
- Keep **measure-before-promote** for schema columns.

## Claim board (encoded)

| Claim | Status |
|---|---|
| Y_scanner = Y_oracle | **FALSIFIED** |
| Label mismatch means error | **FALSIFIED** |
| JOINT_STATE_SL_TP stable population | **OBSERVED** |
| Entry-time predicts JOINT | **FALSIFIED** (L-003G) |
| Path geometry associates with JOINT | **OBSERVED** |
| Trail activation causes JOINT | **NOT DEMONSTRATED** |
| Trail activation associated with JOINT | **OBSERVED** |
| Trail exit ordering associated with JOINT | **OBSERVED** |
| Scanner exit_bar earlier than oracle on path | **OBSERVED** |
| Why that happened | **NOT ESTABLISHED** |

## Ontology rules (frozen framing)

1. **Primary observable:** `JOINT_OUTCOME_STATE` / `Y_joint`.
2. **Components:** `scanner_outcome` (`art_outcome`), `oracle_outcome` (`outcome`) â€” not rivals; not noisy versions of each other.
3. **Named populations are states, not errors:** `BOTH_SL`, `JOINT_STATE_SL_TP`, `BOTH_TP`, `SCANNER_SL_ORACLE_TIMEOUT`, `BOTH_TIMEOUT`, â€¦
4. **LABEL_MATCH / LABEL_MISMATCH** = terminal label equality only (kept). Research questions should prefer **state membership** over "who is right".
5. **EARLY_STOP_CANDIDATE** remains research alias for `JOINT_STATE_SL_TP` only (SAFE_ALIAS) â€” not observation that the detector stopped early.
6. **Forbidden upgrades without new evidence:**
   - trail causality
   - "detector stopped early" as observation beyond measured `exit_bar` inequality
   - `T_MAE` as FAE
   - "drives/causes" for peak duration (association only)

## What "promote" means here

| Allowed now | Forbidden now |
|---|---|
| Docs framing: joint state is primary measured object | Analytics registry schema column promotion |
| Prefer state_id membership in research questions | EARLY_STOP promotion beyond SAFE_ALIAS |
| Keep LABEL_MATCH/MISMATCH as equality helpers | Attribution unlock |
| Point prior L-003* docs at this lock | Causal language upgrade (causes/drives) |
| | New measurements / `src/` edits / commit |

## Terminology (L-003-TERM.v1 + L-003J)

| Term | Role | Claim class |
|---|---|---|
| `JOINT_OUTCOME_STATE` / `Y_joint` | Primary measured object `(scanner_outcome, oracle_outcome)` | ontology lock (framing) |
| `scanner_outcome` | Component of Y_joint | measured label |
| `oracle_outcome` | Component of Y_joint | measured label |
| Named state_id (e.g. `JOINT_STATE_SL_TP`) | Population membership | observed state (not error) |
| `LABEL_MATCH` / `LABEL_MISMATCH` | Terminal label equality helpers | measured equality only |
| `EARLY_STOP_CANDIDATE` | SAFE_ALIAS â†’ `JOINT_STATE_SL_TP` | research alias only |
| `scanner_exit_precedes_oracle_tp` (aliases: scanner_exit_before_oracle_tp, seb) | `exit_ordering_relation` / path-timing inequality | OBSERVED association (not causality) |

## Prior chain (pointers)

| Finding | Role |
|---|---|
| L-003 / L-003B | Homonym; Y_scanner â‰  Y_oracle |
| L-003Câ€“E | Mismatch population + path geometry + T_MAE proxy |
| L-003F | Joint state machine + JOINT_STATE_SL_TP population |
| L-003G | Entry-time predictability of JOINT **falsified** |
| L-003Hâ€“I | Trail/exit associations; baseline inversion; causality **not** demonstrated |
| L-003-TERM | Terminology parity audit |
| **L-003J (this)** | Ontology lock: joint state primary |
| L-003K | Formula freeze: Y_scanner / Y_oracle / Y_joint |
| L-003L | Omega_joint freeze + four layers + MeasurementObject registry |

## Explicit non-promotions

- No `src/` edits
- No analytics registry / schema column promotion
- No EARLY_STOP / JOINT registry promotion
- No new measurements
- No attribution unlock (`ATTRIBUTION_BLOCKER_IDENTITY` + `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` remain)
- No trail-causality claim
- No commit / git add
- L-003 remains **NOT frozen**

## Cross-links

- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`
- Terminology: `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md`
- Lineage semantics: `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md`
- **L-003K (equations):** `docs/governance/ANALYTICS_JOINT_OUTCOME_FORMULAS_L003K.md` — formula freeze companion (Y_scanner, Y_oracle, Y_joint).
- **L-003L (Omega_joint + MeasurementObjects):** `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md` — state-space freeze + four-layer freeze + MeasurementObject identity registry (run_id `l003l_joint_state_space_measurement_objects_20260907_200006`).

## L-003M noun-parity pointer (docs only — 2026-09-07)

- **finding / version:** `L-003M.v1` · **status:** `NOUN_PARITY_LOCKED` · **run_id:** `l003m_noun_parity_20260907_201028`
- Canonical StateIDs are coordinate-only `STATE_*` (`STATE_SL_TP` etc.); L-003F / pre-L-003M names (`JOINT_STATE_SL_TP`, `EARLY_STOP_CANDIDATE`, …) = **research aliases only**.
- Prefer `MATCH_RELATION` (LABEL_MATCH/MISMATCH = terminal-label equality); never `CORRECTNESS_RELATION`.
- Prefer `scanner_terminal_label` / `oracle_terminal_label` when MeasurementObject not named; Process-vs-Variable rewrite: `Y_* emitted by <process>(...)`.
- Measured path noun: **path geometry descriptors** `{time_to_peak, MFE, T_MAE, exit-order inequality}`.
- Artifact: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` + `docs/governance/analytics_noun_parity_l003m-2026-09-07.json`.
- No end-to-end rewrite of this file; no src/schema/measurement/commit.
