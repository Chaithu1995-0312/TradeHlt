# L-003 Package Freeze

**Status:** `L003_PACKAGE_FROZEN`  
**version:** `L-003-FREEZE.v1`  
**run_id:** `l003_package_freeze_20260907_201945`  
**Date (UTC):** `2026-09-07T20:19:45.454186Z`  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  

Machine-readable: `docs/governance/analytics_l003_package_freeze-2026-09-07.json`.

## Freeze declaration

Stop L-003 doctrine / noun / ontology work. The L-003 package is **frozen**.

| Gate | Rule |
|---|---|
| Further L-003 doctrine / noun / ontology edits | **PROHIBITED** except errata |
| New research | Opens under **JOINT_STATE_EXPLAINABILITY** (`docs/research/JOINT_STATE_EXPLAINABILITY.md`) |
| Edge / attribution | **Still blocked** (historical IDENTITY + OUTCOME_SEMANTICS); research reframed away from "which outcome is correct" |
| This pass | Docs only — no `src/`, no analytics schema/lineage column edits, no new empirical measurements, no commit/add |

## Final ontology patches closed in this freeze (three leaks)

### Leak 1 — OutcomeLabel ≠ MeasurementObject

- `OutcomeLabel` ∈ {SL_HIT, TP_HIT, TIMEOUT} — **value domain only**
- MeasurementObjects `Y_scanner` / `Y_oracle` emit OutcomeLabels via different functions `f_scanner(path)`, `f_oracle(path)`
- Therefore `SL_HIT` under `Y_scanner` and `SL_HIT` under `Y_oracle` are **not** automatically the same event
- Updated: `MEASUREMENT_OBJECT_REGISTRY` + L-003K formulas note

### Leak 2 — JointStateCoordinate ≠ JointStatePopulation

- `JointStateCoordinate` = `s ∈ Ω_joint` (e.g. `STATE_SL_TP`)
- `JointStatePopulation` = `{ x : Y_joint(x) = s }`
- Forbid prose equating "JOINT" with a population without set notation
- Updated: L-003L / L-003M

### Leak 3 — exit ordering name

- Canonical observation name: `scanner_exit_precedes_oracle_tp`
- Formula: `scanner_exit_bar < oracle_tp_bar` (or oracle exit bar when TP)
- Alias / deprecated: `scanner_exit_before_oracle_tp`, `trail_exit_before_oracle_tp`, `seb` — do **not** encode cause in the name
- Prefer relation class: `exit_ordering_relation`
- Updated: L-003H / L-003I noun notes + L-003M rewrite rules

## Pin + run_id chain (B→M highlights)

| Finding | run_id (highlight) | Role |
|---|---|---|
| L-003 / L-003B | outcome / population comparison | Homonym; `Y_scanner ≠ Y_oracle` |
| L-003C–E | disagreement / path mechanics / adverse timing | Path geometry associates with joint membership |
| L-003F | joint states | Joint state census; names later aliased under L-003M |
| L-003G | joint-state entry predictability | **Strongest empirical:** entry-time AUC≈0.516 → entry-time predictability **falsified**; path-defined not entry-defined |
| L-003H–I | trail exit transitions / baseline inversion | Exit-ordering associates; trail not sufficient |
| L-003J | `l003j_joint_outcome_state_ontology_20260907_194325` | Ontology lock framing: `JOINT_OUTCOME_STATE` / `Y_joint` primary |
| L-003K | `l003k_joint_outcome_formulas_20260907_195221` | Formula freeze |
| L-003L | `l003l_joint_state_space_measurement_objects_20260907_200006` | `Ω_joint` + MeasurementObject registry |
| L-003M | `l003m_noun_parity_20260907_201028` | Noun / vocabulary parity |
| **FREEZE (this)** | `l003_package_freeze_20260907_201945` | Package freeze + three leak closures |

## Strongest empirical (frozen)

- **L-003G:** LOIO mean AUC ≈ **0.516** on available anatomy entry fields → **entry-time predictability falsified**
- Population remains **path-defined**, not entry-defined (on available fields)

## Strongest identity (frozen)

- `Y_scanner ≠ Y_oracle` (HOMONYM)
- MeasurementObjects registered: `Y_scanner`, `Y_oracle`, `Y_joint` (`REGISTERED_IDENTITY`)
- OutcomeLabels are shared value-domain tokens only; events are emitter-indexed

## Attribution / edge stance (unchanged)

- **No edge** claimed by this freeze
- Attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS as historically noted)
- Research reframed: observe / explain `Y_joint` populations — **not** "which outcome is correct"

## Successor episode

- `docs/research/JOINT_STATE_EXPLAINABILITY.md` — status `EPISODE_OPEN` (no measurements in this pass)

## Explicit non-promotions

- No `src/` edits
- No analytics schema / lineage column edits
- No new empirical measurements this pass
- No commit / git add
- No edge unlock / no attribution unlock
- No further L-003 doctrine/noun/ontology work except errata
