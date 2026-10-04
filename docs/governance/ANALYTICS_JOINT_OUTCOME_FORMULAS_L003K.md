# L-003K — Formula freeze: `Y_scanner`, `Y_oracle`, `Y_joint`

> **PACKAGE FREEZE (L-003-FREEZE.v1):** status **L003_PACKAGE_FROZEN** — further L-003 doctrine/noun/ontology edits **PROHIBITED** except errata. New research -> `docs/research/JOINT_STATE_EXPLAINABILITY.md`. run_id `l003_package_freeze_20260907_201945`. Pin `d7c25f6e55616261b8b229b000875abd3bd315eb`.

**Status:** FORMULAS_FROZEN · package **L003_PACKAGE_FROZEN**  
**version:** `L-003K.v1`  
**Companion:** L-003J ontology lock — this is the **equation** companion (not another doctrine essay).  
**Date (UTC):** 2026-09-07T19:52:21.897045Z  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003k_joint_outcome_formulas_20260907_195221`

Machine-readable: `docs/governance/analytics_joint_outcome_formulas_l003k-2026-09-07.json`.  
Impact: `docs/governance/analytics_joint_outcome_formulas_l003k_impact-2026-09-07.json`.  
Ontology: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

## Frozen equations

```
Y_scanner := outcome emitted by opportunity_scanner._simulate
Y_oracle  := outcome emitted by research.measurement.forward_walk(exit_model="intrabar_fixed")
Y_joint   := (Y_scanner, Y_oracle)
```

## Emitter paths (repo-precise)

| Symbol | Emitter | Path / signature |
|---|---|---|
| `Y_scanner` | `opportunity_scanner._simulate` | `scripts/research/opportunity_scanner.py` `_simulate(..., trail_mult=0.5)` -> `dict["outcome"]` |
| `Y_oracle` | `forward_walk` | `src/research/measurement/forward_walk.py` `forward_walk(..., exit_model="intrabar_fixed")` -> `Outcome` |
| `Y_joint` | pair | `(Y_scanner, Y_oracle)` |

**Anatomy columns (artifact <-> formula):**

- `art_outcome` <-> `Y_scanner` (artifact / opportunities.jsonl scanner label)
- `outcome` <-> `Y_oracle` (anatomy oracle column)
- L-003H replay may **re-emit** both (`scanner_outcome_replay` + re-simulated oracle); identity xref still uses `art_outcome`

## Variable locks (not narrative)

1. **HOMONYM:** `Y_scanner != Y_oracle` as variables — distinct RVs. Label equality does **not** imply variable identity.
2. `scanner_outcome == oracle_outcome` means **terminal-label equality only**, **not** `Y_scanner = Y_oracle`.
3. `JOINT_STATE_SL_TP` is a **coordinate** in joint-state space `State(Y_scanner=SL, Y_oracle=TP)` — **not** an SL->TP transition, failure, disagreement, or error.
4. `EARLY_STOP_CANDIDATE` = research **alias** only (-> `JOINT_STATE_SL_TP`); not an observation that the detector stopped early.


## Freeze errata — OutcomeLabel ≠ MeasurementObject (L-003-FREEZE.v1)

- `OutcomeLabel` ∈ {SL_HIT, TP_HIT, TIMEOUT} is the **shared value domain only**.
- `Y_scanner` emits via `f_scanner(path)` (MeasurementProcess: `opportunity_scanner._simulate`).
- `Y_oracle` emits via `f_oracle(path)` (MeasurementProcess: `forward_walk(..., exit_model="intrabar_fixed")`).
- Therefore `SL_HIT` under `Y_scanner` and `SL_HIT` under `Y_oracle` are **not** automatically the same event (emitter-indexed events; label-token equality ≠ event identity).
- Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## Wording <-> formula parity

| Current wording | Formula actually measured | Better wording |
|---|---|---|
| LABEL_MATCH | `scanner_label == oracle_label` | Terminal-label equality |
| LABEL_MISMATCH | `scanner_label != oracle_label` | Terminal-label inequality |
| JOINT_STATE_SL_TP | `(scanner=SL, oracle=TP)` | Joint outcome state (coordinate) |
| `scanner_exit_precedes_oracle_tp` (alias: scanner_exit_before_oracle_tp / seb) | `scanner_exit_bar < oracle_tp_bar` | `exit_ordering_relation` (cause-free) |
| path geometry explains JOINT | association only | Path geometry associated with JOINT |
| trail interaction | not directly measured as cause | Trail-related pattern hypothesis |
| early adverse movement | `T_MAE` proxy | Early MAE timing proxy |

## Mechanical checks (future docs)

1. Does "agreement" actually mean `Y_scanner == Y_oracle` as **labels only**?
2. Does "prediction" mean `P(Y_joint | X)`?
3. Does "association" accidentally become "cause"?
4. Does a **state name** accidentally become a **process explanation**?

## Explicit non-promotions

- No `src/` edits; no registry columns; no new measurements; no commit/add
- No causal upgrade; no EARLY_STOP-as-fact; no attribution unlock
- L-003 package status: **L003_PACKAGE_FROZEN** (IDENTITY + OUTCOME_SEMANTICS blockers remain historically; no edge/attribution unlock)

## L-003L pointer

**L-003L (state space + MeasurementObjects):** `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md` — freezes Omega_joint (9 StateIDs), four-layer ontology (ExitProcess / MeasurementProcess / ObservedVariable / Population), and registers Y_scanner / Y_oracle / Y_joint as REGISTERED_IDENTITY (identity promotion, not edge). Machine: `docs/governance/analytics_joint_state_space_l003l-2026-09-07.json`; registry: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md`. run_id `l003l_joint_state_space_measurement_objects_20260907_200006`.

## L-003M noun-parity pointer (docs only — 2026-09-07)

- **finding / version:** `L-003M.v1` · **status:** `NOUN_PARITY_LOCKED` · **run_id:** `l003m_noun_parity_20260907_201028`
- Canonical StateIDs are coordinate-only `STATE_*` (`STATE_SL_TP` etc.); L-003F / pre-L-003M names (`JOINT_STATE_SL_TP`, `EARLY_STOP_CANDIDATE`, …) = **research aliases only**.
- Prefer `MATCH_RELATION` (LABEL_MATCH/MISMATCH = terminal-label equality); never `CORRECTNESS_RELATION`.
- Prefer `scanner_terminal_label` / `oracle_terminal_label` when MeasurementObject not named; Process-vs-Variable rewrite: `Y_* emitted by <process>(...)`.
- Measured path noun: **path geometry descriptors** `{time_to_peak, MFE, T_MAE, exit-order inequality}`.
- Artifact: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` + `docs/governance/analytics_noun_parity_l003m-2026-09-07.json`.
- No end-to-end rewrite of this file; no src/schema/measurement/commit.
