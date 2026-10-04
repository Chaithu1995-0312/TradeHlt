# P-STRUCT-01 — CRT DISPLACEMENT evidence table

> **Status:** AUTHORIZED research node (2026-08-18). Evidence table, not a
> fingerprint taxonomy. No ontology node. No Semantic OS id. No new FM-id.
> No G001. No semantic promotion. Experiment 1 and P-VSTATE-02 are not
> amended. `CRT_OBJECT_RELATIONS` CLOSED is not a license to add CRT
> meaning here.
>
> Parent of this node: [`structure-dimension-inventory-displacement.md`](structure-dimension-inventory-displacement.md).
>
> Change: `CH-p-struct-01-narrow-node` · task class `OBSERVATION_ONLY`.

## Why this node exists

The inventory proved the proposed six-axis displacement fingerprint was
**over-specified relative to the current ontology**. Semantic layers
describe what the runtime already declares; they do not create market
meaning. This node records what is already observable inside the declared
CRT `DISPLACEMENT` population.

It is **not**:

```text
DISPLACEMENT = bullish + after_sweep + high_volume + against_ema + ...
```

## Population

CRT `STATE_TRANSITION` events with `state_to = DISPLACEMENT` only.

- Legal predecessor is derived from `VALID_TRANSITIONS`
  (`src/config_layer/state_identity.py:85`): only `SWEEP → DISPLACEMENT`.
- `RANGE → DISPLACEMENT` is not a legal edge. An input that contains it
  is `ILLEGAL_PREDECESSOR` (fail closed), never an `after_range` class.
- `SWEEP → EXPANSION` skips are counted in the rollup and are **not**
  rows. They are a different hop.
- Parent-CRT (`RANGE_C1` / `MANIPULATION_C2` / `DISTRIBUTION_C3`) and
  the nine SMC primitives from `v2_htfcrt_2026_08` are a **different
  construction**. They are not dimensions of this node.

## Evidence columns

| Column | Kind | Rule |
|---|---|---|
| `timestamp` | join key | Normalized event timestamp. Never `candle_index` across artifacts. |
| `engine_state` | grounded | Always `DISPLACEMENT`. |
| `direction` | grounded | `LONG` / `SHORT` / `null`. Joined from the companion `SWEEP` event at the predecessor sweep timestamp (F-074 / `crt.direction`). STATE_TRANSITION `direction` is often null — do not guess. |
| `direction_source` | grounded | `SWEEP_EVENT` or `UNJOINED`. |
| `predecessor_state` | grounded | `state_from` of this transition. |
| `after_sweep` | grounded | `predecessor_state == SWEEP`. Tautological if the file is legal. Not a class of displacement. |
| `age_since_sweep_bars` | derivable | `disp.candle_index - sweep_entry.candle_index` inside the **same** events file. |
| `age_since_sweep_class` | derivable | Always `UNKNOWN_N`. An explicit N has not been authorized. |
| `continuation_successor` | derivable | Next `STATE_TRANSITION` with `state_from=DISPLACEMENT`: `EXPANSION` / `RANGE` / `NONE`. |
| `continuation_age_bars` | derivable | Bar delta to `EXPANSION`, else `null`. |
| `continuation_age_class` | derivable | `UNKNOWN_N` if successor is `EXPANSION`, else `ABSENT`. |
| `volume_ratio` | observable only | FM-062 numeric, **only** if an official join file is supplied. Else `null`. |
| `volume_spike` | observable only | FM-063 raw value (pipeline int8 0/1), **only** if joined. Else `null`. Not `high_volume`. |
| `volume_join_status` | observable only | `NOT_JOINED` / `JOINED` / `MISSING_AT_TIMESTAMP`. |
| `volume_participation` | SEM-013 qualifier | Identity of FM-063 states: `NoSpike` / `VolumeSpike` / `UNJOINED`. Authorized CH-PSTRUCT-04. Not a CRTState. Not `high_volume`. |
| `crt_wire` | SEM-013 v2 annotation | `DISPLACEMENT:{NoSpike\|VolumeSpike}:ANNOTATION_ONLY` or `UNJOINED`. P-STRUCT-06. Not a subtype. |
| `crt_wire_gate` | SEM-013 v2 | Always `UNUSED`. |

`UNKNOWN_N` is data. It is not a missing value for the researcher to fill.

`volume_ratio = 1.73` is legal. `high_volume = true` is not — the
repository has not declared what `true` means for CRT displacement.

## How this table may become richer

Exactly two legal paths. There is no third.

1. **Authoritative join** of a quantity the ontology already declares
   (example: official FM-062/063 values on a supplied join file).
   The join fills an existing nullable column. It does not mint a
   class, a cut, or a new column name.
2. **Explicit ontology-contract change**, separately authorized, that
   adds or redefines a declared meaning. That is a new change id, not
   an edit of these counts.

Observed counts do **not** open either path. Modal age = 1 (73/399),
RESET-leave 257/399, or any other histogram cell is not a reason to
add a column, fill `UNKNOWN_N`, invent `high_volume`, or propose a
fingerprint. Interesting ≠ authorized.

## Named measurement (CH-PSTRUCT-05)

Not a new contract. Not a new column. A coincidence count of
**already-declared** columns:

- `direction × volume_participation`
- `volume_participation × continuation_successor`
- `direction × continuation_successor`

Cells are counts. `classes_minted: false`. `economic_claims_allowed:
false`. Ages stay `UNKNOWN_N`. This does not authorize N, EMA,
`after_range`, a CRT `when:` wire, or G001.

## Explicitly excluded

| Proposal | Treatment |
|---|---|
| `after_range` | FORBIDDEN / UNDEFINED. No CRT `RANGE → DISPLACEMENT` edge. |
| CRT high-volume classification | FORBIDDEN. FM-062/063 may be shown numerically. No cut. |
| `against_ema` / `with_ema` | UNDEFINED. Competing EMA pairs; no displacement rule. |
| `deep_retracement` | MIS-SCOPED. FM-027 is a later retest relationship. |
| Parent-CRT / SMC dimensions | Different architecture (`v2_htfcrt_2026_08`). Not this node. |
| Immediate / delayed continuation | Not a class. Age is a number; class stays `UNKNOWN_N`. |

Forbidden output keys (extractor fail-closed if any appear):
`after_range`, `high_volume`, `against_ema`, `with_ema`,
`deep_retracement`, `fingerprint`, `immediate`, `delayed`.

## What the LLM may do with a row

Allowed: “these long displacement events tend to occur one bar after a
sweep” — an interpretation of the table.

Forbidden: “one-bar-after-sweep is a defining displacement class.”
That would require a new contract.

## P-STRUCT-07 CLOSED — reviewer-resolved (CH-PSTRUCT-07)

The user is not required to pick HARD/SOFT, N, or an EMA pair.
§6.8: the reviewer carries the domain burden. Close:
`INTENTIONAL SEMANTIC SEPARATION`.

### 07A — should a gate consume SEM-013? **NO (`DO_NOT_CONSUME`)**

1. **Means today:** DISPLACEMENT is `SWEEP →` F-074 impulse
   (`try_sweep_to_displacement`: direction, body/ATR, `max_sweep_age_candles`).
   Volume is unused in every CRT `when:` (H8 / F-065). SEM-013 is
   `ANNOTATION_ONLY`, gate `UNUSED`.
2. **Should mean:** Displacement is *structure* (impulse away from the
   swept side). Volume is *testimony* (was participation unusual). Those
   are different questions. A hard consume on `when:` or
   `try_sweep_to_displacement` would make VolumeSpike part of being in
   DISPLACEMENT and would drop 132/399 existing events — a
   classification change P-STRUCT-06 forbade. A soft consume at this
   stage would mix RETEST-era confirmation into the impulse bar.
3. **Established:** F-074, `try_sweep_to_displacement`, H8, SEM-013 v2,
   P-STRUCT-06.
4. **Implementation:** does not violate that meaning. Unused is correct.
5. **Authorized change:** none. Do not consume.

### 07B — should an N define the temporal relation? **NO (`DO_NOT_DECLARE_CLASS_N`)**

The engine already has a temporal contract: `max_sweep_age_candles`
inside `try_sweep_to_displacement`. That is a *maximum legal age*, not
a class of displacement. A research `N=1` (modal on this file) would be
a subtype. `UNKNOWN_N` stays the class label. Ages stay numbers.

### 07C — should an EMA contract be introduced? **NO (`DO_NOT_INTRODUCE_EMA_ON_DISPLACEMENT`)**

Direction on DISPLACEMENT is F-074 vs the sweep, not vs an EMA. CRT
soft-confirm EMAs (spans 2/5) fire in the RETEST window. Pipeline
`ema_fast`/`ema_slow` (9/21) is a different pair (F-061). Inventing
`against_ema` here would pick a pair and a stage the ontology does not
attach to DISPLACEMENT. `against_ema` stays UNDEFINED as a displacement
dimension.

P-STRUCT-06 annotation is unchanged. No CRT edit. No G001.

## How to extract

```text
venv\Scripts\python.exe scripts/research/p_struct_01_displacement_evidence.py
    --events results/htf_objective_shadow/two_year/off/run_20260816_074305_XAUUSD/XAUUSD_events.jsonl
    --out-dir results/p_struct_01
```

`--volume-jsonl` is a pre-emitted official join file.

`--join-official-pipeline --csv data/mt5/XAUUSD_M15.csv` is the
authorized specific join (`CH-p-struct-01-official-volume-join`):
`FeaturePipeline.run()` emits FM-062/063; this script only copies
those numbers onto existing columns. It never computes volume / SMA
locally and never emits `high_volume`.

**Contract (CH-PSTRUCT-04 / SEM-013):** FM-063 `volume_spike` is authorized
as a non-state, non-economic `volume_participation` qualifier on CRT
DISPLACEMENT. Values are the official pipeline upper-tail states
`NoSpike` / `VolumeSpike` by identity. No new cut.

**CRT wire (CH-PSTRUCT-06 / SEM-013 v2):**
`CRT_WIRE=DISPLACEMENT:VolumeSpike:ANNOTATION_ONLY`, `gate=UNUSED`.
Research annotation on existing DISPLACEMENT events. Does not change
classification. Not a `when:` predicate, hard gate, or soft gate.

Floor: `tests/test_p_struct_01_displacement_evidence.py`.

## Observation (first extract)

Source: two-year XAUUSD events
`results/htf_objective_shadow/two_year/off/run_20260816_074305_XAUUSD/XAUUSD_events.jsonl`.
Volume join: official `FeaturePipeline.run()` on `data/mt5/XAUUSD_M15.csv`
(78-bar warmup dropped by `finalize`; all 399 displacement timestamps
were after warmup). Counts are observations, not classes, not a finding,
not G001. The join does not mint `high_volume`.

| Fact | Value |
|---|---|
| n | 399 |
| direction | SHORT 225 / LONG 174 (all joined from `SWEEP` events) |
| predecessor | SWEEP 399 / 399 (`after_sweep=true`) |
| age_since_sweep_bars | min 1, max 14; modal 1 (73 rows). Class = `UNKNOWN_N` for all 399 |
| continuation | EXPANSION 142 (class `UNKNOWN_N`); RANGE via RESET 257 (class `ABSENT`) |
| `SWEEP→EXPANSION` skips | 6, excluded from the table |
| FM-062 `volume_ratio` | JOINED 399/399; min 0.350 max 5.212 (numeric only) |
| FM-063 `volume_spike` | raw 0: 132 · raw 1: 267. Not `high_volume` |
| SEM-013 `volume_participation` | NoSpike 132 / VolumeSpike 267 (identity of FM-063). Not a CRT state. |
| P-STRUCT-06 `crt_wire` | DISPLACEMENT:VolumeSpike:ANNOTATION_ONLY 267 / DISPLACEMENT:NoSpike:ANNOTATION_ONLY 132 |
| `crt_wire_gate` | UNUSED 399 / 399 |
| CH-PSTRUCT-05 coincidence | See below. Counts only. |

An interpreter may say long and short displacements both occur, and
that one bar after the sweep is the most common numeric age on this
file. It may not say “one-bar-after-sweep is a defining displacement
class.” 257/399 left via RESET, not via the `DISPLACEMENT→EXPANSION`
edge — that is also a count, not a new class. Official volume numbers
are now on the row. SEM-013 names that official 0/1 as
`volume_participation` (`NoSpike`/`VolumeSpike`). That is still not
`high_volume`, not a CRT state, and not an economic result.

CH-PSTRUCT-05 coincidence (n=399; cells are counts, not classes):

| direction × participation | NoSpike | VolumeSpike |
|---|---:|---:|
| LONG | 57 | 117 |
| SHORT | 75 | 150 |

| participation × successor | EXPANSION | RANGE |
|---|---:|---:|
| NoSpike | 49 | 83 |
| VolumeSpike | 93 | 174 |

| direction × successor | EXPANSION | RANGE |
|---|---:|---:|
| LONG | 72 | 102 |
| SHORT | 70 | 155 |

Full rollup: `results/p_struct_01/rollup.json`.
Human copy: [`reports/p_struct_01_displacement_evidence.md`](../../reports/p_struct_01_displacement_evidence.md).
