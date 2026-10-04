# Physical Storage Architecture

```text
CANONICAL_LAYER_IDENTITY_CONTRACT.md
v1.0.0
CH-canonical-layer-identity

STORAGE_PRESERVATION_CONTRACT.md
v1.0.0
CH-storage-preservation-contract
```

| Field | Value |
|---|---|
| Phase 3 | **CLOSED** (user-accepted 2026-08-23) |
| Admissibility | **PASS** |
| Freeze status | **FROZEN v1.0.0** |
| Status token | `PHYSICAL_STORAGE_STATUS = CLOSED` |
| Date | 2026-08-23 |
| Change | `CH-physical-storage-architecture` (spec) · `CH-physical-storage-architecture-assess` (assessment) · `CH-occupancy-series-identity` (2026-09-05 names series lineage; occupancy PK unchanged) |
| Lane | semantic certification (physical preservation of frozen identity) |
| Authority | Governance / architecture only. No G001. No writers, readers, or migrations this turn. |

`PHYSICAL_STORAGE_STATUS = CLOSED`

This document answers the Phase 3 question and no other:

> **What physical architecture can satisfy both frozen contracts without violating identity preservation?**

It does **not** reopen `LAYER_IDENTITY_STATUS = CLOSED` or `STORAGE_PRESERVATION_STATUS = CLOSED`.  
It does **not** implement Phase 4 (writers / readers) or Phase 5 (replay / query).

`RECOMPUTE != RECOVER` is load-bearing. “We can rebuild it from OHLC” is not an architecture.

---

## 0. Admissibility table (gate — before any layout)

Required by preservation contract §3. A design that cannot put YES in every row is `PRESERVATION_REJECTED`. Proof sketches name the physical kind that carries the frozen PK, not a recompute path.

| Question | Required | This design | How (proof sketch) |
|---|---|---|---|
| Recover exact L0? | YES | **YES** | Identity record embeds `(instrument, timeframe, bar_open_ts, corpus_sha256)`. Payload bytes live in a content-addressed object. Load recomputes SHA-256 of those bytes and compares to stored `corpus_sha256`. Mismatch or missing hash ⇒ `UNIDENTIFIED`. Same timestamp, different hash ⇒ two objects. |
| Recover exact L1? | YES | **YES** | Vector record embeds full L0 PK + `schema_version` + `FEATURE_ORDER_HASH` + `feature_dim` + ordered values. Ordered names live in a declaration snapshot whose hash **is** `FEATURE_ORDER_HASH`. Load hashes the stored names (not HEAD `CANONICAL_FEATURES`), checks `len(values) == feature_dim`. 48 values without those three fields cannot appear. |
| Recover exact L2? | YES | **YES** | State record embeds full L0 PK + `fm_id` + `ontology_states_hash` + token. The `states:` block at encode time is a declaration snapshot. Load hashes that snapshot, compares to stored `ontology_states_hash`. HEAD ontology is not consulted. Re-derive with current encoder ⇒ different object. |
| Recover exact L3? | YES | **YES** | **Occupancy** is a first-class record (not folded from events): L0 PK + `producer_id` + `topology_id` + `track_id` + state-at-close. **Events** are a first-class series: occupancy PK + `state_from` + `state_to` + `event_kind`. One series, two `event_kind` values. Topology map is a declaration snapshot. Load of an event series that contains `STATE_TRANSITION` and zero `RESET` ⇒ `IDENTITY_INCOMPLETE`. Occupancy is not recovered by folding. `engine` and `resolver` cannot share a record. |
| Recover exact L4? | YES | **YES** | Geometry record embeds full L0 PK + `direction` + `entry_px` + `sl_px` (8 dp) + `geometry_kind` + `geometry_schema` + TP payload. `single_tp` and `dual_tp_partial` are different records even when entry/SL match. Trajectory is not on this record. Surrogate `trade_id` is not the PK. |
| Recover exact L5? | YES | **YES** | Outcome record embeds full L4 PK (not a trade-id alias) + `walk_kernel` + `cost_model_id` + `fill_model_id` + `y_R_gross`. Different fill model ⇒ different record. Detection `outcome` cannot be stored under `geometry_kind=engine_trade`. |

**All six YES.** User-assessed 2026-08-23: no identity-preservation violation. User-accepted 2026-08-23: Phase 3 **CLOSED**. `Admissibility: PASS`.

Technology names appear only after this table, as required by preservation contract §3.3.

---

## 1. Architectural constraints that are already law

These are not new identity rules. They constrain physical shape.

| Constraint | Source | Physical consequence |
|---|---|---|
| File-backed; no database, no broker, no cloud | `goal.md` §3 invariant 7 | Records and objects are files. No DBMS is the system of record |
| Equality is the frozen PK, not a path | identity contract | A locator (path, UUID, row number) may exist; Identity Check **ignores** it for equality |
| Missing PK ⇒ `UNIDENTIFIED`, never inferred | preservation §1.2 | Load does not fill gaps from path, neighbour, or HEAD |
| Hash fields validated on load | preservation §1.5 | The **bytes that were hashed** must be stored (or content-addressed). Otherwise validation would use HEAD — forbidden |
| `RECOMPUTE != RECOVER` | identity §3.2 · `goal.md` §3.8 | Child layers are stored, not rebuilt from parents at load |
| Untracked is not repository-identity | identity §3.4.4 · preservation §5.6 | A **tracked binding** must name every content hash the clone needs to resolve |
| JSONL is the existing record grain; columnar projection is not authority | census / `parquet_store` doctrine | Identity records are a record stream. A projection may exist later; it is not this architecture’s authority |
| Corpus authority: logical name → exact bytes | [`CORPUS_AUTHORITY.md`](CORPUS_AUTHORITY.md) R3 binding | L0 binding is that chain, not a filename |

---

## 2. The architecture (three object classes)

One store, three classes. They are different preservation problems. Collapsing them is an identity violation.

| Class | Name | What it is | What it is not |
|---|---|---|---|
| **A** | Declaration | The bytes an identity hash is over | An L1 vector, an occupancy, a git pointer |
| **B** | Identity record | One frozen object (L0–L5), PK as fields | The declaration it hashes; the git binding |
| **C** | Binding | Tracked name of hashes so a blob belongs to repository identity | Storage existence; the object itself |

```text
Class A  hash survives AND bytes survive
Class B  the object is stored, not reconstructed
Class C  blob exists AND blob is bound
```

`AUDITED != CLOSED` is the same shape as `exists != identified`. Class C is that distinction made physical.

### 2.1 Class A — Declaration snapshot

Content-addressed bytes of something the identity hashes:

| Snapshot kind | Hashed as | Why it must exist as bytes |
|---|---|---|
| OHLCV corpus | `corpus_sha256` | L0 load-time validation |
| Feature name order | `FEATURE_ORDER_HASH` | L1 load must not use HEAD `CANONICAL_FEATURES` |
| Ontology `states:` block for one `fm_id` | `ontology_states_hash` | L2 load must not recode with live ontology |
| `VALID_TRANSITIONS` map | `topology_id` | L3 occupancy/event must not adopt HEAD topology |

Address = SHA-256 of the exact snapshot bytes. The snapshot is immutable. A changed declaration is a new snapshot and a new identity family, not an edit.

### 2.2 Class B — Identity record

One record per frozen object. The record **embeds the full primary key as fields**. It also names the content hashes of any snapshots / payloads it binds.

It does **not** use a surrogate as identity. A physical locator may sit beside the PK for disk placement; equality does not see it.

Parent identity is **copied**, not pointed at by path. An L1 record contains the four L0 PK fields, not `corpus_file = data/XAUUSD_M15.csv`.

Records are **append-only**. PK reuse is forbidden (identity contract §3.2). A correction is a new record with a new identity, or an archive pointer. Never overwrite.

### 2.3 Class C — Tracked binding

A git-tracked ledger that names:

```text
identity PK
  → content hashes of snapshots and payloads
  → authority status (if any)
```

This is what makes an untracked blob **identifiable** from a clean clone. The bytes need not live in git. The **hash** must. A blob whose hash is not in a tracked binding is not repository-identity (preservation §5.6).

This is G-05 closed as architecture: logical `(instrument, timeframe)` is not L0; the binding to `corpus_sha256` is.

---

## 3. Identity Check (architectural role, not a writer)

Load is this function. Phase 4 will implement it. Phase 3 requires it to exist as a role, because a layout without a check is the envelope-`schema_hash` failure.

```text
binding + identity record + named snapshots/payloads
        ↓
1. Presence of every PK field (well-typed)
2. Closed-vocabulary membership
3. Recompute hash of bound bytes; compare to stored hash
4. L3 event series: STATE_TRANSITION present ∧ RESET absent ⇒ IDENTITY_INCOMPLETE
5. Child requires parent PK present on the same record (copied, not inferred)
6. No HEAD substitution
        ↓
PRESERVED  or  UNIDENTIFIED / IDENTITY_MISMATCH / IDENTITY_INCOMPLETE
```

A failed check **does not emit** an identified object. Silent skip is `PRESERVATION_REJECTED` (preservation §6).

There is no “read features and if hashes missing, run the pipeline.” That path is recompute.

---

## 4. Per-layer physical records

Field lists are the preservation contract’s persist tables, placed on identity records. Layout of directories is in §6; it does not change these fields.

### 4.1 L0

**Record fields:** `instrument`, `timeframe`, `bar_open_ts`, `corpus_sha256`, `open`, `high`, `low`, `close`, `volume`.

**Snapshot:** corpus bytes at `corpus_sha256`.

**Check:** SHA-256(corpus bytes) == `corpus_sha256`.

Same `bar_open_ts`, different `corpus_sha256` ⇒ two records. A filename is not stored as identity.

### 4.2 L1

**Record fields:** L0 PK (four fields) + `schema_version` + `FEATURE_ORDER_HASH` + `feature_dim` + ordered values.

**Snapshot:** ordered feature-name list whose hash is `FEATURE_ORDER_HASH`.

**Check:** hash(stored names) == `FEATURE_ORDER_HASH`; `len(values) == feature_dim`; `feature_dim` matches the family of `schema_version`.

Archive families (v2.0/35, v3.0/38, v4.0/39) are separate records with their own `schema_version` and their own name-list snapshot. They are never padded onto 48 at load.

Optional slot records add `fm_id` + `vector_index`; they do not replace the vector record.

### 4.3 L2

**Record fields:** L0 PK + `fm_id` + `ontology_states_hash` + state token.

**Snapshot:** the `states:` block for that `fm_id` at encode time.

**Check:** hash(snapshot) == `ontology_states_hash`. Live `market_ontology.yaml` is not an input to load.

### 4.4 L3

Two record kinds. Occupancy is not an event fold.

**Occupancy record:** L0 PK + `producer_id` + `topology_id` + `track_id` + state-at-close. Lineage may include `run_id`, `config_hash`, `constructor_id` (not PK).

**Event record:** occupancy PK + `state_from` + `state_to` + `event_kind` (`STATE_TRANSITION` \| `RESET`).

**Snapshot:** `VALID_TRANSITIONS` map at `topology_id`.

**Check (occupancy):** PK present; `producer_id` / `track_id` in closed set; topology hash matches snapshot; state legal on that track.

**Check (event series):** group by `occupancy_series_identity` `(producer_id, topology_id, track_id, corpus_sha256, run_id)` — identity contract §7.4.1. If the group contains `STATE_TRANSITION` and contains zero `RESET` ⇒ `IDENTITY_INCOMPLETE`. There is **no** second, transitions-only authority series. `constructor_id` and `config_hash` are reproducibility lineage of that series, not grouping keys for the RESET-completeness check (two configs of one recipe are two series via `run_id` / `config_hash` lineage, not via a PK rewrite).

`producer_id=engine` and `producer_id=resolver` are separate records. `execution_tf` and `parent_tf` are separate records.

### 4.5 L4

**Record fields:** L0 PK + `direction` + `entry_px` + `sl_px` + `geometry_kind` + `geometry_schema` + TP payload declared by that schema.

**Check:** closed vocabularies; 8 dp on price PK fields; `sl_px` present; `geometry_kind=detection_stream` cannot be loaded as `engine_trade`.

Trajectory (partial / trail / BE / time-stop) is **absent** from this record. If a later phase stores it, it hangs off L5 walk-kernel lineage, not here.

### 4.6 L5

**Record fields:** full L4 PK (all L4 fields copied) + `walk_kernel` + `cost_model_id` + `fill_model_id` + `y_R_gross` (+ net only if cost id ≠ `none_gross`).

**Check:** L4 PK complete (not `trade_id`); three basis tokens present and closed; `CONTAMINATED` detection fields cannot bind to `engine_trade`.

Same L4, different `fill_model_id` ⇒ two records.

---

## 5. Joins (physical, not inferred)

A join is field equality of copied PKs after both sides pass Identity Check.

```text
L0 record
  └─ L1 record     (copies L0 PK)
       └─ L2 record  (copies L0 PK + fm_id)
  └─ L3 occupancy  (copies L0 PK + producer + topology + track)
       └─ L3 event   (copies occupancy PK)
  └─ L4 record     (copies L0 PK + geometry tokens)
       └─ L5 record  (copies L4 PK + walk/cost/fill)
```

Forbidden physical joins: path equality, timestamp-only equality, surrogate-id equality, “the CSV in this folder,” HEAD schema to archive values.

Cross-`corpus_sha256` join remains `UNJOINABLE` (no coincidence table exists).

---

## 6. Reference file layout

This is a **reference** for Phase 4, not an invitation to invent a second identity. Kinds map to paths so implementers do not have to guess. Relocating files does not change identity; hashes do.

```text
# tracked — bindings and declaration snapshots small enough to version
docs/governance/identity_bindings/     # or a later governed path; TRACKED
  corpora.jsonl                        # (instrument, timeframe) → corpus_sha256 + clock_basis + status
  snapshots.jsonl                      # snapshot_kind → sha256
  record_manifests.jsonl               # layer → sha256 of identity-record files

# content-addressed payloads — MAY be gitignored if named in the tracked binding
objects/<sha256>                       # corpus bytes, name lists, states blocks, topology maps
records/<layer>/<sha256>.jsonl         # identity records; file hash named in record_manifests
```

Git occupancy of those paths is classified by [`GITIGNORE_SCHEMA.md`](GITIGNORE_SCHEMA.md)
(`CH-gitignore-schema-v1`): Class C = TRACKED_BINDING; `objects/` / `records/` /
`identity_store/` = LOCAL_IDENTITY. Dataset Identity under `docs/governance/datasets/`
is the standing L0 binding until the JSONL ledgers above are written. Committing
`data/` / `logs/` / `results/` / new `models/` files is a schema violation, not a
shortcut to preservation.

JSONL is the identity-record encoding because this repository already treats JSONL as the system of record. A later columnar file is a **projection** of these records. It cannot be the authority (preservation contract §3.2: reconstruction is recompute; census: Parquet is a sidecar).

Partitioning, compression, and engine choice (if any) are **not** identity. They are allowed in Phase 4 only if Identity Check still sees the same fields. They are out of scope for claiming this architecture admissible.

---

## 7. What this architecture refuses

| Temptation | Why it fails the gate |
|---|---|
| Path-keyed CSV as L0 | No `corpus_sha256`; G-05 | 
| Feature store that materializes L1/L2 on read from L0 | `RECOMPUTE != RECOVER`; L1/L2 admissibility = NO |
| Single `crt_state` column | Missing `producer_id` / `track_id`; engine = resolver collapse |
| Global transitions log without RESET | `IDENTITY_INCOMPLETE` |
| Occupancy recovered only by folding events | Fold is reconstruction; occupancy must be stored |
| `trade_id` / `CRT-NNNN` as L4 PK | Identity omits SL, corpus, geometry_schema (F-088 class) |
| 48 floats without name-list snapshot | Cannot validate `FEATURE_ORDER_HASH` without HEAD |
| Ontology file on HEAD as L2 declaration | Recode, not recover |
| Database as system of record | `goal.md` invariant 7 |
| Treating today’s `data/` / `logs/` / `results/` as already this store | Untracked; not `PRESERVED` until bound |
| Promote `opportunities.jsonl` outcome to L5 of `engine_trade` | `CONTAMINATED`; identity redefinition |

---

## 8. Phase 4 boundary (explicit)

Phase 3 is **CLOSED**. Phase 4 answers:

```text
Can Phase 4 writers and readers
implement Identity Check exactly as specified
without introducing recompute paths?
```

**Yes, as specified:** `src/identity/` (`CH-identity-store-phase4`).

- `identity.check.identity_check` is the only load
- `identity.store.IdentityStore.write` emits Class A then B then C; refuses PK reuse; will not fill hashes from HEAD
- `identity.store.IdentityStore.read` loads snapshots from bindings only
- Occupancy is stored; event series completeness is a separate check and does not fold occupancy
- AST floor: `check.py` / `store.py` do not import feature_pipeline, feature_states, feature_schema, crt_engine, crt_state_resolver, or state_identity

A writer that emits Class B without Class A, a reader that fills a missing hash from HEAD, or a load that folds events into occupancy, still fails this question. The floor in `tests/test_identity_store.py` is written so those paths fail the test.

Phase 4 **built**:

Phase 4 **may not**:

- add a PK component
- drop RESET from the event series
- default a missing hash
- run `FeaturePipeline` / `FeatureStateEncoder` / `CRTEngine` as a substitute for load
- migrate 38/39-dim records onto 48
- declare today’s gitignored files `PRESERVED` without writing tracked bindings

Phase 5 (replay / query) may only read objects that Identity Check marked `PRESERVED`.

**Phase 5 built:** `identity.query.IdentityQuery` (`CH-identity-query-phase5`).

- `preserved(layer)` emits only Identity Check `PRESERVED` payloads
- `at_l0` joins children by copied L0 PK after L0 itself is PRESERVED
- occupancy comes from `L3_OCCUPANCY` records; incomplete event series is annotated, not folded
- `outcomes_for_geometry` joins L5 on the full L4 PK (not `trade_id`)
- AST floor includes `query.py` against the same recompute-producer ban

---

## 9. What this freeze is, and is not

| This freeze does | This freeze does not |
|---|---|
| Name a file-backed architecture that can put YES on all six admissibility rows | Open a store, write a record, or choose Parquet/DuckDB as authority |
| Require declaration snapshots so hashes validate without HEAD | Repair `logs/crt_transitions.jsonl` |
| Store occupancy and events as separate L3 kinds | Fold occupancy from events |
| Keep JSONL as identity-record encoding | Make JSONL sacred beyond “system of record in this repo” |
| Point Phase 4 at Identity Check as the only load | Implement Identity Check |

**Classification (§6.8):** Phase 3 **CLOSED**. Admissibility **PASS**. Identity and preservation remain CLOSED and unreopened. Phase 4 Identity Check is implemented at `src/identity/` and is **not** a live decision path.

---

## 10. Authority footer

- **Grants:** Phase 3 architecture CLOSED / FROZEN v1.0.0, user-accepted 2026-08-23. Phase 4 Identity Check + file-backed writers/readers at `src/identity/`, fail-closed, no recompute producers on the load path.
- **Does not grant:** live-spine wiring, G001, promotion, migrations of existing `data/`/`logs/`/`results/`, or a Semantic OS id.
- **Does not reopen:** identity or preservation closures.
- **Does not claim:** any existing gitignored file is this store.

No F-id registered.
