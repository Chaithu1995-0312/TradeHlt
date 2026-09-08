# L-003L — Freeze Ic_joint + four-layer ontology + MeasurementObject registry promotion

> **PACKAGE FREEZE (L-003-FREEZE.v1):** status **L003_PACKAGE_FROZEN** — further L-003 doctrine/noun/ontology edits **PROHIBITED** except errata. New research -> `docs/research/JOINT_STATE_EXPLAINABILITY.md`. run_id `l003_package_freeze_20260907_201945`. Pin `d7c25f6e55616261b8b229b000875abd3bd315eb`.

**Status:** `STATE_SPACE_FROZEN + MEASUREMENT_OBJECTS_REGISTERED` · package **`L003_PACKAGE_FROZEN`**  
**version:** `L-003L.v1`  
**Date (UTC):** `2026-09-07T20:00:06Z`  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003l_joint_state_space_measurement_objects_20260907_200006`

Machine-readable: `docs/governance/analytics_joint_state_space_l003l-2026-09-07.json`.  
Impact: `docs/governance/analytics_joint_state_space_l003l_impact-2026-09-07.json`.  
MeasurementObject registry: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md` + `docs/governance/measurement_object_registry.json`.

**Companions:** L-003J (ontology lock framing) · L-003K (formula freeze) · L-003F (empirical state census; names reused as aliases) · **L-003M (noun parity: coordinate-only STATE_* canonical IDs)**.

> **L-003M noun-parity pointer:** Canonical StateIDs are now coordinate-only `STATE_*` (see map below). L-003F interpretive names are **research aliases only** (same discipline as `EARLY_STOP_CANDIDATE`). See `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` / run_id `l003m_noun_parity_20260907_201028`.

## Banner / discipline

Docs/governance only. Closes three architecture gaps after L-003K:

1. Freeze **Ic_joint** (canonical joint-state space) exactly once.
2. Separate **four layers** (ExitProcess / MeasurementProcess / ObservedVariable / Population).
3. Promote **MeasurementObjects** (`Y_scanner`, `Y_oracle`, `Y_joint`) as **registered identities** — ontology correction, **not** an edge claim.

Complementary to TradeImpl Observation / Evidence / Finding / Policy (not rival).

## Gap 1 — Freeze Ic_joint

Define exactly once:

```
Ic_joint ⊆ {SL_HIT, TP_HIT, TIMEOUT} × {SL_HIT, TP_HIT, TIMEOUT}
StateID := f(Y_scanner, Y_oracle)
```

**Cardinality:** |Ic_joint| = 9 (full product). All pairs remain members even if some had zero mass in L-003F.

**Reminder:** StateIDs are **coordinates in joint-state space**, not transitions, errors, or disagreements. Canonical IDs are **coordinate-only** (`STATE_*`); mechanism-tinged names are aliases only (L-003M).

### Canonical StateID map (L-003M coordinate IDs; L-003F names = aliases)

| Canonical StateID | (Y_scanner, Y_oracle) | Research aliases | L-003F mass note |
|---|---|---|---|
| STATE_SL_SL | (SL_HIT, SL_HIT) | BOTH_SL | observed |
| STATE_TP_TP | (TP_HIT, TP_HIT) | BOTH_TP | observed |
| STATE_TO_TO | (TIMEOUT, TIMEOUT) | BOTH_TIMEOUT | observed |
| STATE_SL_TP | (SL_HIT, TP_HIT) | JOINT_STATE_SL_TP, EARLY_STOP_CANDIDATE | observed |
| STATE_TP_SL | (TP_HIT, SL_HIT) | FALSE_TP_CANDIDATE | observed; **alias = L-003F label only / not causal** |
| STATE_TO_TP | (TIMEOUT, TP_HIT) | LATE_REALIZATION | **zero-mass in L-003F; remains in Ic** |
| STATE_TO_SL | (TIMEOUT, SL_HIT) | LATE_FAILURE | **zero-mass in L-003F; remains in Ic** |
| STATE_TP_TO | (TP_HIT, TIMEOUT) | SCANNER_TP_ORACLE_TIMEOUT | **zero-mass in L-003F; remains in Ic** |
| STATE_SL_TO | (SL_HIT, TIMEOUT) | SCANNER_SL_ORACLE_TIMEOUT | observed |

Zero-mass states that remain in Ic: `STATE_TO_TP` (alias LATE_REALIZATION), `STATE_TO_SL` (alias LATE_FAILURE), `STATE_TP_TO` (alias SCANNER_TP_ORACLE_TIMEOUT).

Alias lock:

- `EARLY_STOP_CANDIDATE` = research alias for `STATE_SL_TP` (also aliased as `JOINT_STATE_SL_TP`) **only** (SAFE_ALIAS).
- Machine keys in L-003F map may retain `EARLY_STOP_CANDIDATE` / L-003F names for reproducibility; canonical coordinate id is `STATE_SL_TP`.
- All L-003F interpretive StateIDs above are **aliases**, not rival coordinates.

## Gap 2 — Four layers (frozen)

Complementary ontology nodes (not rival to TradeImpl Observation/Evidence/Finding/Policy):

| Layer | Definition | Examples | Anti-slide |
|---|---|---|---|
| **ExitProcess** | Algorithmic procedure | trailing `_simulate`; `intrabar_fixed` walk | Never write ExitProcess as MeasurementObject |
| **MeasurementProcess** | ExitProcess applied to a Population/unit (call site + params) | `_simulate(..., trail_mult=0.5)`; `forward_walk(..., exit_model="intrabar_fixed")` | Never conflate call-site with the Y it emits |
| **ObservedVariable** / MeasurementObject | Research variable identity | `Y_scanner`, `Y_oracle`, `Y_joint` | Never write as if `forward_walk` **IS** `Y_oracle` |
| **Population** | Set of units | anatomy opportunity rows across BNB/BTC/ETH/SOL | Never write Population as a variable |

### Explicit anti-slide rules

1. Never write as if `forward_walk` **IS** `Y_oracle` (emitter path ≠ ObservedVariable). Prefer: "`Y_oracle` emitted by `forward_walk(...)`" (L-003M rewrite rule).
2. Never write Population as variable.
6. Never equate bare "JOINT" / a StateID with a population without set notation: `JointStatePopulation = { x : Y_joint(x) = s }` where `s` is a `JointStateCoordinate`.
3. Never write ExitProcess as MeasurementObject.
4. Columns (`art_outcome`, `outcome`) are **projections**, not the MeasurementObject.
5. When MeasurementObject not named, prefer `scanner_terminal_label` / `oracle_terminal_label` over bare "outcome" (L-003M).


## Freeze errata — JointStateCoordinate ≠ JointStatePopulation (L-003-FREEZE.v1)

| Noun | Definition |
|---|---|
| `JointStateCoordinate` | `s ∈ Ω_joint` (e.g. `STATE_SL_TP`) |
| `JointStatePopulation` | `{ x : Y_joint(x) = s }` |

**Forbid** prose that equates bare "JOINT" / a StateID with a population unless the set notation is present. Coordinates are points in `Ω_joint`; populations are sets of units.

Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## Gap 3 — MeasurementObject registry (identity promotion, not edge)

First-class registry for research variables discovered by L-003:

- Human: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md`
- Machine: `docs/governance/measurement_object_registry.json`

Registered (minimum):

| object_id | status | edge? | attribution-eligible? |
|---|---|---|---|
| Y_scanner | REGISTERED_IDENTITY | no | no |
| Y_oracle | REGISTERED_IDENTITY | no | no |
| Y_joint | REGISTERED_IDENTITY | no | no |

**Why promote:** identity discovery (`Y_scanner ≠ Y_oracle`) is an **ontology correction of what is measured** — not an edge claim. Analytics `evidence_class` / outcome schema columns remain **unpromoted**. Affirmed by L-003M: MeasurementObject registry remains the correct promotion class (identity before edge).

## Explicit non-promotions

- No `src/` edits
- No analytics schema / lineage registry **column** edits
- No new empirical measurements
- No commit / git add
- No edge claims
- No attribution unlock (`ATTRIBUTION_BLOCKER_IDENTITY` + `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` remain)
- No EARLY_STOP-as-fact; no trail causality upgrade
- L-003 package status: **L003_PACKAGE_FROZEN** (see `ANALYTICS_L003_PACKAGE_FREEZE.md`); doctrine edits closed — research reframed to JOINT_STATE_EXPLAINABILITY
- TradeImpl Observation/Evidence/Finding/Policy hierarchy unchanged (complementary, not replaced)

## Prior chain

| Finding | Role |
|---|---|
| L-003 / L-003B | Homonym; Y_scanner ≠ Y_oracle |
| L-003F | Joint state census + names (now aliases under L-003M) |
| L-003J | Ontology lock: JOINT_OUTCOME_STATE primary (framing) |
| L-003K | Formula freeze: Y_scanner / Y_oracle / Y_joint equations |
| **L-003L (this)** | Ic_joint freeze + four-layer freeze + MeasurementObject identity registry |
| L-003M | Noun parity: STATE_* coordinates + MATCH_RELATION + terminal_label vocab |

## Cross-links

- L-003M: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md`
- L-003K: `docs/governance/ANALYTICS_JOINT_OUTCOME_FORMULAS_L003K.md`
- L-003J: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`
- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`
- Registry: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md`
