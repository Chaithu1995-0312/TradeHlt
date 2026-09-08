# L-003M — Noun / vocabulary parity sweep

> **PACKAGE FREEZE (L-003-FREEZE.v1):** status **L003_PACKAGE_FROZEN** — further L-003 doctrine/noun/ontology edits **PROHIBITED** except errata. New research -> `docs/research/JOINT_STATE_EXPLAINABILITY.md`. run_id `l003_package_freeze_20260907_201945`. Pin `d7c25f6e55616261b8b229b000875abd3bd315eb`.

**Status:** `NOUN_PARITY_LOCKED` · package **`L003_PACKAGE_FROZEN`**  
**version:** `L-003M.v1`  
**Date (UTC):** `2026-09-07T20:10:28Z`  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**run_id:** `l003m_noun_parity_20260907_201028`

Machine-readable: `docs/governance/analytics_noun_parity_l003m-2026-09-07.json`.  
Impact: `docs/governance/analytics_noun_parity_l003m_impact-2026-09-07.json`.

**Companions:** L-003L (Ic_joint + MeasurementObject registry) · L-003K (formula freeze) · L-003J (ontology lock) · L-003-TERM (terminology parity audit).

## Banner / discipline

Docs/governance only. User scorecard: **equations clean; remaining debt is nouns that smuggle explanations.**

This pass freezes noun / vocabulary parity so canonical IDs stay **coordinate-only** / **identity-only**, and mechanism-tinged names stay **research aliases only** (same discipline as `EARLY_STOP_CANDIDATE`).

Does **NOT**: rewrite historical L-003B–I docs end-to-end; edit `src/`; edit analytics schema / lineage columns; add measurements; commit; claim edge / attribution.

## Scorecard response

| Debt class | Locked response |
|---|---|
| State names that smuggle mechanism | Canonical `STATE_*` = coordinate-only; old L-003F names = aliases |
| CORRECTNESS_RELATION framing | Prefer `MATCH_RELATION` (component equality); never oracle-right / scanner-wrong |
| Bare "outcome" overload | Prefer `scanner_terminal_label` / `oracle_terminal_label` unless MeasurementObject named |
| Process collapsed into Variable | Mechanical rewrite: "Y_* emitted by <process>(...)" |
| Path mechanics as measured noun | Canonical measured noun = **path geometry descriptors** |
| Identity promotion class | Affirm: MeasurementObject registry remains correct promotion class (identity before edge) |

## 1. State naming discipline — freeze map

Canonical **StateID** must be **coordinate-only**. Mechanism-tinged / interpretive names = **research aliases ONLY**.

```
STATE_SL_SL       = (SL_HIT, SL_HIT)     aliases: BOTH_SL
STATE_TP_TP       = (TP_HIT, TP_HIT)     aliases: BOTH_TP
STATE_TO_TO       = (TIMEOUT, TIMEOUT)   aliases: BOTH_TIMEOUT
STATE_SL_TP       = (SL_HIT, TP_HIT)     aliases: JOINT_STATE_SL_TP, EARLY_STOP_CANDIDATE
STATE_TP_SL       = (TP_HIT, SL_HIT)     aliases: FALSE_TP_CANDIDATE
STATE_TO_TP       = (TIMEOUT, TP_HIT)    aliases: LATE_REALIZATION
STATE_TO_SL       = (TIMEOUT, SL_HIT)    aliases: LATE_FAILURE
STATE_TP_TO       = (TP_HIT, TIMEOUT)    aliases: SCANNER_TP_ORACLE_TIMEOUT
STATE_SL_TO       = (SL_HIT, TIMEOUT)    aliases: SCANNER_SL_ORACLE_TIMEOUT
```

| Canonical StateID | (Y_scanner, Y_oracle) | Research aliases (not causal / not ontology facts) |
|---|---|---|
| `STATE_SL_SL` | (SL_HIT, SL_HIT) | `BOTH_SL` |
| `STATE_TP_TP` | (TP_HIT, TP_HIT) | `BOTH_TP` |
| `STATE_TO_TO` | (TIMEOUT, TIMEOUT) | `BOTH_TIMEOUT` |
| `STATE_SL_TP` | (SL_HIT, TP_HIT) | `JOINT_STATE_SL_TP`, `EARLY_STOP_CANDIDATE` |
| `STATE_TP_SL` | (TP_HIT, SL_HIT) | `FALSE_TP_CANDIDATE` |
| `STATE_TO_TP` | (TIMEOUT, TP_HIT) | `LATE_REALIZATION` |
| `STATE_TO_SL` | (TIMEOUT, SL_HIT) | `LATE_FAILURE` |
| `STATE_TP_TO` | (TP_HIT, TIMEOUT) | `SCANNER_TP_ORACLE_TIMEOUT` |
| `STATE_SL_TO` | (SL_HIT, TIMEOUT) | `SCANNER_SL_ORACLE_TIMEOUT` |

**Alias discipline (same as EARLY_STOP_CANDIDATE):**

- Machine keys / prior run_ids / L-003F–L historical prose may retain alias names for reproducibility.
- New prose prefers `STATE_*` coordinates.
- Alias ≠ observation that the named mechanism occurred.

Authoritative update sites: `ANALYTICS_JOINT_STATE_SPACE_L003L.md` + companion JSON (canonical + aliases listed). Historical L-003B–I: **pointer / alias table only** — no end-to-end rewrite.


## Freeze errata — JointStateCoordinate ≠ JointStatePopulation (L-003-FREEZE.v1)

| Noun | Definition |
|---|---|
| `JointStateCoordinate` | `s ∈ Ω_joint` (e.g. `STATE_SL_TP`) |
| `JointStatePopulation` | `{ x : Y_joint(x) = s }` |

**Forbid** prose that equates bare "JOINT" / a StateID with a population unless the set notation is present. Coordinates are points in `Ω_joint`; populations are sets of units.

Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## 2. MATCH_RELATION not CORRECTNESS_RELATION

```
LABEL_MATCH    := 1[Y_scanner == Y_oracle]   # terminal-label equality only
LABEL_MISMATCH := 1[Y_scanner != Y_oracle]
```

| Preferred framing | Forbidden framing |
|---|---|
| `MATCH_RELATION` — components equal / unequal as emitted labels | `CORRECTNESS_RELATION` — oracle right / scanner wrong |
| Terminal-label equality helpers | Semantic agreement, process agreement, "error" |

LABEL_MATCH/MISMATCH remain equality-only helpers (L-003J/K/TERM). Research questions prefer **state membership** (`STATE_*`) over who-is-right.

## 3. "outcome" overload — terminal_label vocabulary

When MeasurementObject is **not** named in prose, prefer:

| Preferred noun | Meaning |
|---|---|
| `scanner_terminal_label` | emitted value of `Y_scanner` ∈ {SL_HIT, TP_HIT, TIMEOUT} |
| `oracle_terminal_label` | emitted value of `Y_oracle` ∈ {SL_HIT, TP_HIT, TIMEOUT} |

Reserve bare **"outcome"** only when MeasurementObject is explicit (`Y_scanner` / `Y_oracle`), e.g. "outcome of `Y_scanner`" or formula text that already binds the RV.

Historical synonyms retained for reproducibility: `scanner_outcome`, `oracle_outcome`, columns `art_outcome` / `outcome` (projections, not objects).

Updated in: `MEASUREMENT_OBJECT_REGISTRY.md` + JSON; L-003K/L notes (pointers).

## 4. Process vs Variable — mechanical rewrite rule

**Forbidden collapse (do not write):**

- "forward_walk outcome"
- "forward_walk says"
- "forward_walk predicts"
- "scanner says" / "_simulate outcome" / "_simulate predicts" (same collapse)

**Required form:**

- `Y_oracle` emitted by `forward_walk(...)`
- `Y_scanner` emitted by `opportunity_scanner._simulate(...)`

| Layer | Noun |
|---|---|
| ExitProcess / MeasurementProcess | `forward_walk`, `_simulate` |
| ObservedVariable / MeasurementObject | `Y_oracle`, `Y_scanner` |
| Emitted terminal label | `oracle_terminal_label`, `scanner_terminal_label` |

## 5. Path mechanics → path geometry descriptors

Canonical **measured** noun:

**path geometry descriptors** = `{time_to_peak, MFE, T_MAE, exit_ordering_relation / scanner_exit_precedes_oracle_tp}`

| Role | Terms |
|---|---|
| Measured set (canonical) | path geometry descriptors |
| Hypothesis aliases only | path mechanics; stopped early; trail interaction |

Do not smuggle "path mechanics / stopped early / trail interaction" as if they were the measured object.

## 6. Affirm identity promotion

MeasurementObject registry (`Y_scanner`, `Y_oracle`, `Y_joint` as `REGISTERED_IDENTITY`) remains the **correct promotion class**: **identity before edge**.

- Affirms L-003L Gap 3.
- Does **not** unlock attribution, edge claims, or analytics schema columns.


## 7. Exit-ordering noun discipline (L-003-FREEZE.v1)

Relation class: **`exit_ordering_relation`**.

| Role | Term |
|---|---|
| Canonical observation | `scanner_exit_precedes_oracle_tp` |
| Formula | `scanner_exit_bar < oracle_tp_bar` |
| Alias / deprecated | `scanner_exit_before_oracle_tp`, `trail_exit_before_oracle_tp`, `seb` |

Rewrite rule: prefer cause-free ordering names; never smuggle "trail caused early exit" into the observation noun. Historical L-003H/I keys may retain aliases.

Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## Mechanical rewrite checklist (future docs)

1. State name = coordinate (`STATE_*`)? Or mechanism alias without alias mark?
2. Equality = `MATCH_RELATION` / LABEL_* only? Or slipped into correctness / error?
3. Bare "outcome" bound to named MeasurementObject? Else use `*_terminal_label`.
4. Process verb attached to process, not to Y_*? ("emitted by", never "forward_walk says")
5. Path language = geometry descriptors vs hypothesis aliases?
6. Any promotion claiming edge / attribution? Forbidden without new evidence.
7. Exit-order noun = `scanner_exit_precedes_oracle_tp` / class `exit_ordering_relation`? Or cause-smuggling alias without alias mark?

## Explicit non-promotions

- No `src/` edits
- No analytics schema / lineage registry **column** edits
- No new empirical measurements
- No commit / git add
- No edge claims / no attribution unlock
- No EARLY_STOP-as-fact; no trail causality upgrade
- No end-to-end rewrite of historical L-003B–I docs
- L-003 package status: **L003_PACKAGE_FROZEN** (see `ANALYTICS_L003_PACKAGE_FREEZE.md`); doctrine edits closed — research reframed to JOINT_STATE_EXPLAINABILITY
- `ATTRIBUTION_BLOCKER_IDENTITY` + `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` remain

## Prior chain

| Finding | Role |
|---|---|
| L-003-TERM | LABEL_MATCH vocabulary; path geometry preference |
| L-003J | JOINT_OUTCOME_STATE primary framing |
| L-003K | Formula freeze (equations clean) |
| L-003L | Ic_joint + four layers + MeasurementObject identity registry |
| **L-003M (this)** | Noun / vocabulary parity lock (coordinate StateIDs + rewrite rules) |

## Files touched

| File | Change |
|---|---|
| `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md` | **new** (this file) |
| `docs/governance/analytics_noun_parity_l003m-2026-09-07.json` | **new** |
| `docs/governance/analytics_noun_parity_l003m_impact-2026-09-07.json` | **new** (optional impact) |
| `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md` | canonical `STATE_*` + aliases |
| `docs/governance/analytics_joint_state_space_l003l-2026-09-07.json` | same |
| `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md` | terminal_label vocabulary |
| `docs/governance/measurement_object_registry.json` | same |
| `docs/governance/ANALYTICS_JOINT_OUTCOME_FORMULAS_L003K.md` | L-003M pointer |
| `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md` | L-003M pointer |
| `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md` | L-003M pointer |
| `docs/governance/analytics_l003_terminology_parity_audit-2026-09-07.json` | L-003M pointer |

## Cross-links

- L-003L: `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md`
- Registry: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md`
- L-003K: `docs/governance/ANALYTICS_JOINT_OUTCOME_FORMULAS_L003K.md`
- L-003J: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`
- TERM audit: `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md`
