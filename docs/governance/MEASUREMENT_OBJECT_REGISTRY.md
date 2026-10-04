# MeasurementObject Registry (research variables)

> **PACKAGE FREEZE (L-003-FREEZE.v1):** status **L003_PACKAGE_FROZEN** — further L-003 doctrine/noun/ontology edits **PROHIBITED** except errata. New research -> `docs/research/JOINT_STATE_EXPLAINABILITY.md`. run_id `l003_package_freeze_20260907_201945`. Pin `d7c25f6e55616261b8b229b000875abd3bd315eb`.

**Status:** MEASUREMENT_OBJECTS_REGISTERED (identity promotion) · package **L003_PACKAGE_FROZEN**  
**Authority finding:** L-003L (`L-003L.v1`); noun-parity companion **L-003M** (`L-003M.v1`)  
**run_id:** `l003l_joint_state_space_measurement_objects_20260907_200006`  
**Date (UTC):** `2026-09-07T20:00:06Z`  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`

Machine-readable: `docs/governance/measurement_object_registry.json`.  
Impact: `docs/governance/measurement_object_registry_impact-2026-09-07.json`.  
State-space freeze companion: `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md`.  
Noun parity: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` (run_id `l003m_noun_parity_20260907_201028`).

## Purpose

Register **first-class research MeasurementObjects** discovered by L-003 — ontology correction of **what is measured** (`Y_scanner ≠ Y_oracle`), **not** an edge claim and **not** attribution-eligible by itself.

Complementary to TradeImpl Observation / Evidence / Finding / Policy (not rival).

**Not in scope here:** analytics schema / lineage registry **column** promotion; `evidence_class` edits; outcome-column promotion.

**L-003M affirmation:** MeasurementObject registry remains the **correct promotion class** (identity before edge).

## Layer reminder (L-003L)

| Layer | Role |
|---|---|
| ExitProcess | algorithmic procedure |
| MeasurementProcess | ExitProcess @ Population (call site + params) |
| ObservedVariable / MeasurementObject | Y_* identities (this registry) |
| Population | set of units |

Anti-slide: never write `forward_walk` as if it **is** `Y_oracle`; never write Population as variable; never write ExitProcess as MeasurementObject. Columns are projections.

L-003M Process-vs-Variable rewrite: prefer "`Y_oracle` emitted by `forward_walk(...)`" / "`Y_scanner` emitted by `opportunity_scanner._simulate(...)`". Forbidden: "forward_walk outcome/says/predicts".

## Terminal-label vocabulary (L-003M)

When MeasurementObject is **not** named in prose, prefer:

| Noun | Meaning |
|---|---|
| `scanner_terminal_label` | emitted value of `Y_scanner` ∈ {SL_HIT, TP_HIT, TIMEOUT} |
| `oracle_terminal_label` | emitted value of `Y_oracle` ∈ {SL_HIT, TP_HIT, TIMEOUT} |

Reserve bare **"outcome"** only when MeasurementObject is explicit (`Y_scanner` / `Y_oracle`).

Historical synonyms retained for reproducibility: `scanner_outcome`, `oracle_outcome`; columns `art_outcome` / `outcome` remain projections.

MATCH_RELATION (not CORRECTNESS_RELATION):

```
LABEL_MATCH    := 1[Y_scanner == Y_oracle]   # terminal-label equality only
LABEL_MISMATCH := 1[Y_scanner != Y_oracle]
```


## OutcomeLabel vs MeasurementObject (L-003-FREEZE.v1)

| Noun | Role |
|---|---|
| `OutcomeLabel` | Value domain only: ∈ {SL_HIT, TP_HIT, TIMEOUT} |
| `MeasurementObject` | Research variable identity (`Y_scanner`, `Y_oracle`, `Y_joint`) |

Emission:

```
scanner_terminal_label := f_scanner(path)   # Y_scanner / opportunity_scanner._simulate
oracle_terminal_label  := f_oracle(path)    # Y_oracle  / forward_walk(exit_model="intrabar_fixed")
```

**Consequence:** `SL_HIT` under `Y_scanner` and `SL_HIT` under `Y_oracle` are **not** automatically the same event. Shared token ∈ OutcomeLabel does not collapse MeasurementObjects or event identity.

Freeze: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` (`l003_package_freeze_20260907_201945`).

## Entries

### Y_scanner

| Field | Value |
|---|---|
| object_id | `Y_scanner` |
| formula | `Y_scanner := outcome emitted by opportunity_scanner._simulate` (L-003K) |
| mathematical_type / formula_map | **`Omega -> OutcomeLabel`** · `Y_scanner : Omega -> OutcomeLabel` (ARCH-REVIEW.v1 errata) |
| emitter_path + params | `scripts/research/opportunity_scanner.py` `_simulate(..., trail_mult=0.5)` → `dict["outcome"]` |
| value_domain | `{SL_HIT, TP_HIT, TIMEOUT}` |
| emitted_label_noun | `scanner_terminal_label` (L-003M; prefer when object not named) |
| related_columns | `art_outcome` (projection / artifact — **not** the object) |
| population_default | anatomy opportunity rows across BNB/BTC/ETH/SOL |
| distinct_from | `Y_oracle` (HOMONYM); ExitProcess `_simulate`; column `art_outcome` |
| status | **REGISTERED_IDENTITY** |
| edge / attribution | **NOT** edge; **NOT** attribution-eligible by itself |

### Y_oracle

| Field | Value |
|---|---|
| object_id | `Y_oracle` |
| formula | `Y_oracle := outcome emitted by research.measurement.forward_walk(exit_model="intrabar_fixed")` (L-003K) |
| mathematical_type / formula_map | **`Omega -> OutcomeLabel`** · `Y_oracle : Omega -> OutcomeLabel` (ARCH-REVIEW.v1 errata) |
| emitter_path + params | `src/research/measurement/forward_walk.py` `forward_walk(..., exit_model="intrabar_fixed")` → `Outcome` |
| value_domain | `{SL_HIT, TP_HIT, TIMEOUT}` |
| emitted_label_noun | `oracle_terminal_label` (L-003M; prefer when object not named) |
| related_columns | `outcome` (projection / anatomy oracle column — **not** the object) |
| population_default | anatomy opportunity rows across BNB/BTC/ETH/SOL |
| distinct_from | `Y_scanner` (HOMONYM); ExitProcess `forward_walk` (**is not** Y_oracle); column `outcome` |
| status | **REGISTERED_IDENTITY** |
| edge / attribution | **NOT** edge; **NOT** attribution-eligible by itself |

### Y_joint

| Field | Value |
|---|---|
| object_id | `Y_joint` |
| formula | `Y_joint := (Y_scanner, Y_oracle)` (L-003K); alias `JOINT_OUTCOME_STATE` (L-003J) |
| mathematical_type / formula_map | **`Omega -> S`** with `S = L x L` · `Y_joint : Omega -> S` (ARCH-REVIEW.v1 errata) |
| emitter_path + params | pair composition of Y_scanner + Y_oracle emitters |
| value_domain | Ic_joint (9 StateIDs; canonical `STATE_*` per L-003M / L-003L) |
| related_columns | `art_outcome` + `outcome` are projections of components — **not** Y_joint |
| population_default | anatomy opportunity rows across BNB/BTC/ETH/SOL |
| distinct_from | LABEL_MATCH/MISMATCH helpers; named StateID membership predicates; EARLY_STOP_CANDIDATE alias |
| status | **REGISTERED_IDENTITY** |
| edge / attribution | **NOT** edge; **NOT** attribution-eligible by itself; **NOT** schema-column promotion |

## Explicit non-promotions

- No analytics `evidence_class` / outcome **schema column** promotion
- No lineage registry column edits
- No edge claims / no attribution unlock
- No `src/` edits / no new measurements / no commit
- L-003 finding package status: **L003_PACKAGE_FROZEN** (errata-only; new work -> JOINT_STATE_EXPLAINABILITY)

## Cross-links

- L-003M: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md`
- L-003L: `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md`
- L-003K formulas: `docs/governance/ANALYTICS_JOINT_OUTCOME_FORMULAS_L003K.md`
- L-003J ontology: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`


## Errata - mathematical maps (ARCH-REVIEW.v1)

**run_id:** `arch_review_falsify_pack_20260908_023341` · **version:** `ARCH-REVIEW.v1`

Producer refs alone are insufficient. Each Y_* now declares a mathematical type (domain->codomain). L-003 package remains FROZEN; this is registry errata only.

| object_id | mathematical_type | formula_map.notation |
|---|---|---|
| `Y_scanner` | `Omega -> OutcomeLabel` | `Y_scanner : Omega -> OutcomeLabel` |
| `Y_oracle` | `Omega -> OutcomeLabel` | `Y_oracle : Omega -> OutcomeLabel` |
| `Y_joint` | `Omega -> S` with `S = L x L` | `Y_joint : Omega -> S` |

Default domain population: `Omega_anatomy_opportunity` (see `docs/governance/POPULATION_REGISTRY.md`).

```text
L := OutcomeLabel = {SL_HIT, TP_HIT, TIMEOUT}
S := L x L
Y_joint(x) := (Y_scanner(x), Y_oracle(x))
```

