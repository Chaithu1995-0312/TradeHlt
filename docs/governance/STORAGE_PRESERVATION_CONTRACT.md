# Storage Preservation Contract

| Field | Value |
|---|---|
| Status | **FROZEN v1.0.0** |
| Phase 2 | **CLOSED** (user-accepted 2026-08-23) |
| Status token | `STORAGE_PRESERVATION_STATUS = CLOSED` |
| Date | 2026-08-23 |
| Change | `CH-storage-preservation-contract` (spec) · `CH-storage-preservation-accept` (acceptance) · `CH-occupancy-series-identity` (2026-09-05 series lineage named; occupancy PK unchanged) |
| Lane | semantic certification |
| Identity authority (mandatory citation) | [`CANONICAL_LAYER_IDENTITY_CONTRACT.md`](CANONICAL_LAYER_IDENTITY_CONTRACT.md) **v1.0.0** · `CH-canonical-layer-identity` |
| Predecessor | Lineage census (disk-truth) → identity contract (equality, CLOSED) |
| Authority | Governance / preservation only. No G001. No production authority. No Semantic OS id allocated this turn. |

This document answers the Phase 1 gate question and no other:

```text
CANONICAL_LAYER_IDENTITY_CONTRACT.md
v1.0.0
CH-canonical-layer-identity
```

> **How does storage preserve the frozen identity?**

**Storage is subordinate to identity. Storage may never redefine identity.**

`LAYER_IDENTITY_STATUS = CLOSED` remains. This contract does not reopen it. It does not choose a technology.

`STORAGE_PRESERVATION_STATUS = CLOSED`

Phase 1 answered *what makes an object the same object?*  
Phase 2 answered *what must be preserved so the same object can be recovered?*  
Without reopening identity.

---

## Sequence (this program)

```text
Phase 0  Lineage Census                         (disk-truth; analysis)
Phase 1  Identity Contract                      (FROZEN v1.0.0 / CLOSED)
Phase 2  Storage Preservation Contract          (FROZEN v1.0.0 / CLOSED)
Phase 3  Physical Storage Design                (CLOSED / FROZEN v1.0.0)
Phase 4  Writers / Readers (Identity Check)     (src/identity/; not live spine)
Phase 5  Replay & Query Layer                   (src/identity/query.py; PRESERVED-only)
```

The next legitimate design question is not “what should we store?” It is:

```text
What physical architecture can satisfy
both frozen contracts
without violating identity preservation?
```

---

## Explicitly excluded (Phase 3+)

These words name technologies and layouts. They are **not** preservation. They **SHALL NOT** appear as design choices in this contract, and a Phase 2 discussion that drifts into them is out of scope:

```text
Parquet
DuckDB
Writers
Readers
Migrations
Replay engines
Compression
Partitioning
File layout
```

A later physical design is admissible only if it cites **both** this file and the identity freeze, and proves the admissibility test in §3.

---

## 1. Identity Preservation Rules

### 1.1 The round-trip

For every frozen layer L0–L5:

```text
Store
  ↓
Load
  ↓
Identity Check
```

must satisfy:

```text
Loaded Object Identity
=
Stored Object Identity
```

Identity means the **primary key** frozen in the identity contract, not the payload resembling the original, not a recompute from a parent layer, and not a path or row index.

### 1.2 Fail-closed

If identity cannot be **proven** from what was stored:

```text
UNIDENTIFIED
```

must be returned.

**Never inferred.** Forbidden inferences include: filling a missing PK component from a file path, a neighbouring row, HEAD `CANONICAL_FEATURES`, current ontology `states:` blocks, or “the only corpus we have.”

### 1.3 Subordination

| Rule | Meaning |
|---|---|
| Identity is prior | A store that cannot emit the frozen PK is not a store of that object |
| Storage does not name | Closed vocabularies (`producer_id`, `geometry_kind`, `walk_kernel`, …) are owned by the identity contract. A store may only persist those tokens; it may not add, alias, or collapse them |
| Storage does not round | Price PK components stay at the identity contract’s 8 decimal places. A store that persists a different rounding has a different object |
| `RECOMPUTE != RECOVER` | Loading a parent layer and re-running current code is not recovery of the child. That is a new identity unless every child PK component was stored and matched |

### 1.4 What “persist” means here

**Persist** = the field is a first-class stored component of the object, bound at store time, available at load time without derivation.

It does **not** mean a column, a file, a table, or a codec. Those are Phase 3.

### 1.5 What “validated on load” means here

**Validated on load** = the Identity Check recomputes the identity-relevant hash or token from the bound payload and **compares** it to the stored value. Mismatch ⇒ `UNIDENTIFIED` (or `IDENTITY_MISMATCH` — §6). Absence ⇒ `UNIDENTIFIED`. A stored hash that is never checked is not preservation (the envelope-`schema_hash` class).

### 1.6 Preservation-status tokens

Identity-contract tokens still apply (`IDENTIFIED` · `UNIDENTIFIED` · `UNJOINABLE` · `ARCHIVED` · `CONTAMINATED`). This contract adds preservation-layer outcomes. They **map into** identity tokens; they do not replace them.

| Token | Meaning | Maps to |
|---|---|---|
| `PRESERVED` | Store→Load→Identity Check: loaded PK = stored PK | `IDENTIFIED` |
| `IDENTITY_INCOMPLETE` | Required identity event or field was not stored (e.g. RESET dropped) | `UNIDENTIFIED` — must not be folded as a complete object |
| `IDENTITY_MISMATCH` | Stored PK present but fails load-time validation (hash/bytes disagree) | `UNIDENTIFIED` |
| `PRESERVATION_REJECTED` | A proposed storage design fails §3 | not an object — the design is illegal |

---

## 2. Layer Preservation Requirements

Every layer’s frozen PK is copied verbatim from the identity contract. This section does not add PK components and does not remove any.

### 2.1 L0 — OHLC

**Frozen identity** ([identity contract](CANONICAL_LAYER_IDENTITY_CONTRACT.md) §4.1):

```text
(instrument, timeframe, bar_open_ts, corpus_sha256)
```

**Must persist**

| Field | Constraint |
|---|---|
| `instrument` | Corpus-native symbol |
| `timeframe` | Closed token |
| `bar_open_ts` | Bar open, second precision, as stored in the corpus |
| `corpus_sha256` | SHA-256 of the **exact bytes** of the physical OHLCV artifact |
| payload | `open`, `high`, `low`, `close`, `volume` |

**Must enforce**

- `corpus_sha256` is **immutable** once bound. A byte change is a new L0 object, never an edit.
- `corpus_sha256` is **validated on load** against the bytes being read.

**Rule**

```text
Same timestamp
Different corpus_sha256
=
Different L0 object
```

Logical `(instrument, timeframe, bar_open_ts)` alone is not preservable identity. A store that omits `corpus_sha256` cannot recover exact L0.

### 2.2 L1 — Feature Values

**Frozen identity** (identity contract §5.1):

```text
vector: (L0, schema_version, FEATURE_ORDER_HASH)
slot:   + (fm_id, vector_index)
```

**Must persist**

| Field | Constraint |
|---|---|
| L0 PK | All four L0 components, not a timestamp alias |
| `schema_version` | Family token (`5.0` active; `2.0` / `3.0` / `4.0` archive) |
| `FEATURE_ORDER_HASH` | SHA-256[:16] of **that family’s** ordered names |
| `feature_dim` | `canonical_dim` of that family (48 for v5.0). Stored so dimension is not counted from values |
| payload | The ordered vector of `feature_dim` floats |
| slot (if stored) | `fm_id` + `vector_index` |

**Must enforce**

- `FEATURE_ORDER_HASH` validated on load against the stored name order, not against HEAD `CANONICAL_FEATURES`.
- `feature_dim` must equal the length of the stored vector and the dim of `schema_version`. Disagreement ⇒ `IDENTITY_MISMATCH`.

**Rule**

```text
48 values
≠
48-value identity
```

Identity is:

```text
values
+
ordering
+
schema
```

A store that persists 48 numbers without `schema_version` and `FEATURE_ORDER_HASH` cannot recover exact L1.

### 2.3 L2 — Feature States

**Frozen identity** (identity contract §6.1):

```text
(L0, fm_id, ontology_states_hash)
```

**Must persist**

| Field | Constraint |
|---|---|
| L0 PK | All four L0 components |
| `fm_id` | Ontology identity of the family |
| `ontology_states_hash` | SHA-256 of that entry’s `states:` block at encode time |
| payload | The state token (including `X_UNMAPPED(...)` / `X_NON_FINITE(...)`) |

**Must enforce**

- `ontology_states_hash` validated on load against the declaration that is claimed to have produced the token. If the live ontology has moved, the stored hash **does not update**. Mismatch with a requested “current” declaration is not repairable by recoding.

**Rule**

```text
Re-derived states
≠
Recovered states
```

unless `ontology_states_hash` (and L0, `fm_id`) match.

`RECOMPUTE != RECOVER` applies directly: running `FeatureStateEncoder` on a recovered L1 with HEAD ontology is a new L2 object.

### 2.4 L3 — CRT States

**Frozen identity** (identity contract §7.2–§7.3):

```text
occupancy:
(L0, producer_id, topology_id, track_id)

event:
occupancy PK + (state_from, state_to, event_kind)
```

`event_kind` ∈ { `STATE_TRANSITION`, `RESET` }. `RESET` is first-class.

**Must persist**

| Field | Constraint |
|---|---|
| Occupancy PK | L0 + `producer_id` + `topology_id` + `track_id` |
| Occupancy payload | `CRTState` member legal on that `track_id` (state at bar close) |
| Every event | `state_from`, `state_to`, `event_kind` |
| Both event kinds | `STATE_TRANSITION` **and** `RESET` |
| Occupancy series identity | `producer_id` + `topology_id` + `track_id` + `corpus_sha256` + `run_id` (identity contract §7.4.1). A stream missing `run_id` is `UNIDENTIFIED` as a series |
| Series reproducibility lineage | `constructor_id` (recipe family) and `config_hash` / `config_version` (settings). Not PK. Not a substitute for `producer_id` |

**Must enforce**

- A stream that stores `STATE_TRANSITION` and drops `RESET` is **not** an L3 occupancy series.

**Rule**

```text
RESET cannot be dropped.
```

Any stream lacking RESET events:

```text
IDENTITY_INCOMPLETE
```

`IDENTITY_INCOMPLETE` maps to `UNIDENTIFIED`. Folding it as occupancy is a contract violation (the census `crt_transitions.jsonl` class). Absence of an event is not evidence of no transition (identity contract §7.7 fail-open rule).

`producer_id=engine` and `producer_id=resolver` remain two objects. A store that writes one column called `crt_state` without `producer_id` cannot recover exact L3.

### 2.5 L4 — Geometry

**Frozen identity** (identity contract §8.1):

```text
(L0, direction, entry_px, sl_px, geometry_kind, geometry_schema)
```

**Must persist**

| Field | Constraint |
|---|---|
| L0 PK | Entry bar, all four components |
| `direction` | `long` \| `short` |
| `entry_px`, `sl_px` | 8 decimal places; `sl_px` required |
| `geometry_kind` | Closed token (`engine_trade`, `planner_v1_2`, `oracle_every_bar`, `episode_entry`, `visual_crt_sem012`, `detection_stream`) |
| `geometry_schema` | Closed token (`single_tp`, `dual_tp_partial`, `structural_no_tp`) |
| payload | TP fields the schema declares (`tp` / `tp1` / `tp2`) |

**Must enforce**

- Trajectory (partial, trail, BE, time-stop) is **not** L4 payload. If stored, it is L5 walk-kernel lineage, not a substitute for `geometry_schema`.

**Rule**

```text
single_tp
≠
dual_tp_partial
```

even if `entry_px` and `sl_px` match.

A store that persists entry/SL and omits `geometry_kind` / `geometry_schema` cannot recover exact L4 (F-088 class).

### 2.6 L5 — Outcome

**Frozen identity** (identity contract §9.1):

```text
(L4, walk_kernel, cost_model_id, fill_model_id)
```

**Must persist**

| Field | Constraint |
|---|---|
| L4 PK | All L4 components, not a trade-id alias |
| `walk_kernel` | Closed token |
| `cost_model_id` | Closed token |
| `fill_model_id` | Closed token |
| payload | at minimum `y_R_gross`; net only if `cost_model_id` ≠ `none_gross` |

**Must enforce**

- Detection-stream `outcome` remains `CONTAMINATED`. Persisting it under an L5 PK of `engine_trade` is a redefinition of identity and is rejected.

**Rule**

```text
same trade
different fill model
=
different outcome object
```

The same holds for `walk_kernel` and `cost_model_id`. A store that persists R and omits the three basis tokens cannot recover exact L5.

---

## 3. Admissibility Criteria

A storage **design** (Phase 3) is admissible only if it can answer **yes** to every row. This is a proof obligation on the design, not a measurement of today’s files.

| Question | Required |
|---|---|
| Recover exact L0? | YES |
| Recover exact L1? | YES |
| Recover exact L2? | YES |
| Recover exact L3? | YES |
| Recover exact L4? | YES |
| Recover exact L5? | YES |

**Exact** means: Store→Load→Identity Check returns `PRESERVED` for that layer’s frozen PK, including hashes validated on load, RESET not dropped, and no inferred PK component.

Any NO:

```text
Storage Design = REJECTED
```

`PRESERVATION_REJECTED`.

### 3.1 What “can recover” does not mean

- Does not mean “we could recompute it from OHLC.”
- Does not mean “we have a CSV that looks like it.”
- Does not mean “dimension matches.”
- Does not mean “one instrument, one build, untracked” (census `bar_matrix` class).

### 3.2 All-six rule

This contract is the preservation bar for the **six-layer identity**. A design that preserves L0 and L5 and reconstructs the middle is **REJECTED**. Reconstruction is recompute.

A file that is not claiming to be this preservation store is out of scope — it is not admitted by failing quietly; it is simply not this object. The moment a design claims to store “the lineage,” §3 applies in full.

### 3.3 Citation required of Phase 3

A Phase 3 physical-storage proposal **SHALL**, in its first paragraph, cite:

```text
CANONICAL_LAYER_IDENTITY_CONTRACT.md
v1.0.0
CH-canonical-layer-identity

STORAGE_PRESERVATION_CONTRACT.md
v1.0.0
CH-storage-preservation-contract
```

and walk the §3 table with a yes/no and a proof sketch per layer. Technology names may appear only after that table is all YES.

---

## 4. Load-Time Validation Rules

Load is an Identity Check, not a decode.

### 4.1 Order of checks (any layer)

1. **Presence.** Every PK component of that layer is present and well-typed. Else `UNIDENTIFIED`.
2. **Closed vocabulary.** Tokens are members of the identity contract’s closed sets. Else `UNIDENTIFIED`.
3. **Hash/bytes validation.** Where the PK or a required persist field is a hash (`corpus_sha256`, `FEATURE_ORDER_HASH`, `ontology_states_hash`), recompute from the bound payload and compare. Else `IDENTITY_MISMATCH` → `UNIDENTIFIED`.
4. **Completeness of events (L3).** If `event_kind=STATE_TRANSITION` exists in the stored series and `event_kind=RESET` does not, `IDENTITY_INCOMPLETE` → `UNIDENTIFIED`.
5. **Parent identity.** Child load requires parent PK preserved (L1 requires L0, L5 requires L4, …). Missing parent ⇒ `UNJOINABLE` or `UNIDENTIFIED`, never a guessed join.
6. **No HEAD substitution.** Current schema, current ontology, current `VALID_TRANSITIONS` must not replace stored hashes.

### 4.2 Pass criterion

Only if 4.1(1–6) succeed:

```text
Loaded Object Identity = Stored Object Identity
→ PRESERVED
```

### 4.3 Forbidden load behaviors

| Behavior | Why forbidden |
|---|---|
| Pad/slice a vector to current dim | Redefines L1 family |
| Recode states with live `states:` | Redefines L2 |
| Fold transitions-only as occupancy | Drops RESET; L3 `IDENTITY_INCOMPLETE` |
| Treat detection `outcome` as ledger R | Redefines L5 (F-022) |
| Fill `corpus_sha256` from the path the operator pointed at | G-05 class; inferring identity |
| Silent skip of a failed check | Same class as F-056 / F-079 / F-083 / F-085 — skipped validation indistinguishable from absent |

### 4.4 Validate-on-load is not optional

A field that is persisted but not checked is not preserved. The identity contract already recorded envelope `schema_hash` as a passive drift detector no runtime path checks. This contract forbids that pattern for every required persist field in §2.

---

## 5. Archive Preservation Rules

Archives are first-class identities. Preservation of an archive is preservation of **its** PK, not promotion onto the active family.

1. **Keep the family.** A v3.0 / 38-dim vector stays a v3.0 / 38-dim identity. Never pad, slice, or rename onto v5.0 / 48 as if current (identity contract §3.4 / §5.6).
2. **Self-declare.** An archive that does not store `schema_version` (and for L1, `feature_dim` + `FEATURE_ORDER_HASH` of *that* family) is `UNIDENTIFIED`, not an honorary archive.
3. **No path identity.** Moving bytes does not change the object. Replacing bytes under the same name changes `corpus_sha256` and is a new L0.
4. **Supersession is a pointer.** `ARCHIVED` / `CONTAMINATED` / `SUPERSEDED` stay on the identity. F-022 streams stay `CONTAMINATED`; they are never stored as `walk_kernel=backtest_ledger`.
5. **No migration in this phase.** Byte-identical preservation is the only legal relationship between families until a later authorized change defines a coincidence table (identity contract §3.4.6). A coincidence table is not implied by this contract.
6. **Untracked is not preserved.** Gitignored `data/` / `logs/` / `results/` / `models/` have no repository identity until a tracked provenance record names the hashes. This contract does not create that record. It forbids a Phase 3 design from treating untracked files as already `PRESERVED`.

---

## 6. Identity Failure Modes

These are the ways a store fails preservation. They are closed enough to reject a design; they are not an implementation checklist.

| Mode | Typical cause | Required outcome |
|---|---|---|
| **Missing PK component** | Timestamp without `corpus_sha256`; 48 floats without `FEATURE_ORDER_HASH`; entry/SL without `geometry_schema` | `UNIDENTIFIED` |
| **Inferred PK** | Path, row index, HEAD schema, “only one corpus” | `UNIDENTIFIED` (inference is illegal, not a guess to confirm) |
| **Hash not checked** | Stored `corpus_sha256` / `FEATURE_ORDER_HASH` / `ontology_states_hash` never compared on load | not preserved; treat as `IDENTITY_MISMATCH` if a check is later added and fails, else the design is `PRESERVATION_REJECTED` |
| **Hash disagrees** | Bytes moved; order renamed; ontology `states:` edited | `IDENTITY_MISMATCH` → `UNIDENTIFIED` |
| **Dropped RESET** | Transitions-only CRT stream | `IDENTITY_INCOMPLETE` → `UNIDENTIFIED` |
| **Collapsed split** | `engine` vs `resolver`; `single_tp` vs `dual_tp_partial`; v5.0 vs v3.0; two fill models as one R | redefinition of identity → `PRESERVATION_REJECTED` if designed; `UNIDENTIFIED` if encountered |
| **Recompute presented as load** | Child rebuilt from parent with current code | `RECOMPUTE != RECOVER` — new object, not `PRESERVED` |
| **Contaminated promoted** | Detection `outcome` stored as L5 of `engine_trade` | `CONTAMINATED` remains; promotion is rejected |
| **Silent skip** | Failed check logged and the row still emitted as identified | `PRESERVATION_REJECTED` (F-079 class) |
| **Partial six-layer claim** | Design stores L0+L5, reconstructs L1–L4 | `Storage Design = REJECTED` |

---

## 7. What this freeze is, and is not

| This freeze does | This freeze does not |
|---|---|
| Answer *how storage preserves the frozen identity* | Choose a format, engine, or file tree |
| Require every frozen PK component to be persisted and checked | Allocate writers or readers |
| Make RESET first-class in any future store | Repair `logs/crt_transitions.jsonl` |
| Reject designs that recover by recompute | Grant G001, promotion, or CRT CLOSED |
| Keep archives as archives | Migrate 38/39-dim corpora onto 48 |

**Classification (§6.8):** preservation *rules* are `CLOSED` (user-accepted 2026-08-23). No store exists yet. `AUDITED != CLOSED`. `RECOMPUTE != RECOVER`. Identity CLOSED does not close a physical store. Preservation CLOSED does not close CRT, measurement-contract admissibility, or Phase 3.

---

## 8. Phase 3 gate (normative)

Phase 2 is **CLOSED**. Phase 3 (physical storage design) **SHALL NOT** begin with a technology. It begins with the §3 table and the question: *what physical architecture can satisfy both frozen contracts without violating identity preservation?*

Until a Phase 3 proposal cites both freezes (§3.3) and is all-YES on §3, the following remain **forbidden**:

- Parquet / DuckDB / any store engine
- writers, readers, indexes
- migrations, backfills
- replay engines
- compression, partitioning, file layout
- code in `src/`, `scripts/`, `tests/` whose purpose is to persist or serve these objects

A Phase 3 design that invents a key, omits a PK component, drops RESET, or treats rebuild as recovery is rejected at classification.

---

## 9. Authority footer

- **Grants:** a frozen preservation vocabulary subordinate to identity v1.0.0. Phase 2 CLOSED / FROZEN v1.0.0, user-accepted 2026-08-23. Store→Load→Identity Check. All-six admissibility. `IDENTITY_INCOMPLETE` for dropped RESET. Each layer is a preservation obligation, not a storage implementation.
- **Does not grant:** a store, a layout, writers, readers, migrations, replay, production authority, economic claims, or a Semantic OS contract id.
- **Does not reopen:** `LAYER_IDENTITY_STATUS = CLOSED`.
- **Additive lineage (2026-09-05, `CH-occupancy-series-identity`):** persist `occupancy_series_identity` and series reproducibility lineage (`constructor_id`, `config_hash`) as named in identity contract §7.4.1. Occupancy PK unchanged. FROZEN marker stays **v1.0.0**.
- **Does not resolve:** G-05 as a writer (it remains a PK that must be persisted and validated), the fold-incomplete CRT stream (it remains `IDENTITY_INCOMPLETE` if stored as-is), or untracked artifacts.
- **Phase 3** may only be designed as a physical architecture that satisfies **both** frozen contracts. “We can recompute it” is not an argument (`RECOMPUTE != RECOVER`).

No F-id registered. Preservation rules are design law, not a market conclusion.
