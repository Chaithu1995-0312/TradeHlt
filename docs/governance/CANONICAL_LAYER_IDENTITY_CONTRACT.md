# Canonical Layer Identity Contract

| Field | Value |
|---|---|
| Status | **FROZEN v1.0.0** |
| Phase 1 | **CLOSED** (user-accepted 2026-08-23) |
| Status token | `LAYER_IDENTITY_STATUS = CLOSED` |
| Date | 2026-08-23 |
| Change | `CH-canonical-layer-identity` (spec) · `CH-canonical-layer-identity-accept` (acceptance) · `CH-occupancy-series-identity` (2026-09-05 additive lineage; PK unchanged) |
| Lane | semantic certification |
| Predecessor | [`docs/analysis/feature_state_lineage_census.md`](../analysis/feature_state_lineage_census.md) (point-in-time census of what exists today) |
| Authority | Governance / identity only. No G001. No production authority. No Semantic OS id allocated this turn. |

`LAYER_IDENTITY_STATUS = CLOSED`

> **Phase 1 is CLOSED.** This document is FROZEN v1.0.0.
> It defines **equality**, not storage.
> Phase 2 (preservation rules) is [`STORAGE_PRESERVATION_CONTRACT.md`](STORAGE_PRESERVATION_CONTRACT.md) v1.0.0 · **CLOSED** (user-accepted 2026-08-23).
> Phase 3 physical architecture is [`PHYSICAL_STORAGE_ARCHITECTURE.md`](PHYSICAL_STORAGE_ARCHITECTURE.md) v1.0.0 · **CLOSED**. Phase 4 Identity Check: `src/identity/` (not live spine).

---

## 0. What this freeze is, and is not

This contract answers one question:

> For each of the six semantic layers, what **is** a thing — such that two records are the same object, or are not?

It does **not** answer how to store, write, read, migrate, or reconstruct those things. Those are later phases. A later writer that emits a record without the keys frozen here is a contract violation, not a design choice.

| This freeze does | This freeze does not |
|---|---|
| Name the six objects | Allocate storage |
| Freeze primary keys | Specify files, tables, or formats |
| Freeze lineage keys | Specify writers or readers |
| Freeze immutability | Rewrite today's artifacts |
| Freeze schema-versioning | Migrate 38/39-dim corpora onto 48 |
| Freeze archive rules | Grant G001, promotion, or CRT CLOSED |
| Bind keys to existing authorities | Invent FM-ids, CT-ids, SEM-ids, or F-ids |

**Classification (§6.8):** identity equality is `CLOSED` for the six named layers. Persistence remains the census gap (`TEST / CONTRACT GAP` there). `AUDITED != CLOSED`. `LINEAGE CLOSED != ECONOMICALLY VALIDATED`. `RECOMPUTE != RECOVER`. Identity CLOSED does not close CRT, measurement-contract admissibility, or any store.

---

## 1. Why identity before storage

The census (2026-08-23) established that the six-layer chain is **observability-incomplete**: Feature States are ephemeral, CRT occupancy survives only in gitignored run directories, the global CRT stream is fold-incomplete, geometry trajectory is never stored, and no artifact is tracked. That is a persistence gap.

A persistence gap is not an invitation to invent keys at write time. Historical failure class (F-022, F-046, F-056, F-079, F-083, F-085, F-088): a kernel whose name implied one object silently walked another, and nothing compared the two. Identity that is defined *as the writer is written* will be defined by the writer's convenience.

So the order is:

```
identity frozen  →  then storage may be designed  →  then writers may emit  →  then readers may join
```

Never the reverse.

---

## 2. The six objects

Layer numbers match the census. They are **join order**, not storage order, and not a claim that L(n+1) is computed from L(n).

| Layer | Object | What it is | What it is not |
|---|---|---|---|
| L0 | **OHLC** | One bar's six-field market fact from one exact corpus | A file path; a row index; a TradingView print of "the same" bar |
| L1 | **Feature Values** | The canonical numeric vector at that bar under one schema | A column name; a formula under a colliding name; a 38/39-dim archive treated as current |
| L2 | **Feature States** | The ontology-declared interpretation of a value at that bar | A CRT state; a decision input; a magnitude cut invented at encode time |
| L3 | **CRT States** | Occupancy of one named producer on one named track at that bar | Feature-state derived; HTFState; ObjectiveStatus; the resolver when the question is the engine |
| L4 | **Geometry** | The entry/SL/TP levels of one trade object, frozen at open | A trail/BE/partial trajectory; a planner thought that was never written; a detection `sl`/`tp` |
| L5 | **Outcome** | Realized R (and related path stats) of one geometry under one walk+cost+fill basis | A detection-stream `outcome` (F-022); a recompute under a different kernel |

HTFState, ObjectiveStatus, IntentState, RejectReason, and trade-intent labels (`liq_sweep` / `pullback` / `breakout` / `reversal`) are **out of this contract**. They have their own identities. Mixing them into L3 is a register collapse (F-077, F-078).

---

## 3. Common identity grammar

Every object has four key sets. Names are closed.

| Set | Role |
|---|---|
| **Primary key** | Equality. Two records with the same PK **are** the same object. Two records that differ on any PK component **are not**, even if they look similar. |
| **Lineage keys** | Provenance required to *join* or *re-identify*. Missing lineage ⇒ `UNJOINABLE`, never inferred. Lineage does not change equality. |
| **Payload** | The values the object carries. Payload mutation under the same PK is forbidden (see immutability). |
| **Not-keys** | Things that exist in today's artifacts and **must not** be treated as identity. |

### 3.1 Encoding (identity form, not storage)

When a later phase serializes an identity, it serializes the **tuple**, not a path.

- Field order is the order written in each object's PK table.
- `instrument` is the corpus-native symbol (`XAUUSD`, `BNBUSDT`), case-sensitive as stored.
- `timeframe` is a closed token: `M15` · `H1` · `H4` · `D1` · `W1` · `MN1` (calendar-true parent frames use the same tokens as `ParentCandleBuilder` rules).
- `bar_open_ts` is the bar **open** timestamp at second precision, `YYYY-MM-DDTHH:MM:SS`, as stored in the corpus. It is **not** timezone-converted at identity time. Clock meaning lives on the corpus (F-066).
- `corpus_sha256` is SHA-256 of the **exact bytes** of the physical OHLCV artifact.
- Numeric prices in a PK are rounded to **8 decimal places** (matches `clean_labels.builder._unit_id` and `episodes.schema.episode_id`).
- `direction` in a PK is `long` \| `short` (lowercase). Engine `Direction.LONG` / `Direction.SHORT` map to these; `NONE` is not a geometry or outcome identity.

New identity hashes, if a later phase needs a single-token id, **SHALL** be SHA-256 hex of the canonical tuple encoding. Existing hashes stay lineage stamps and keep their native algorithm:

| Existing stamp | Algorithm | Role after this freeze |
|---|---|---|
| `corpus_sha256` | SHA-256 | L0 lineage **and** PK component |
| `FEATURE_ORDER_HASH` | SHA-256[:16] of ordered names | L1 PK component |
| `SCHEMA_HASH` | MD5 of concatenated names | L1 lineage only (legacy) |
| `clean_labels` `_unit_id` / `episode_id` | SHA-1[:16] | L4 lineage alias, not the canonical PK |
| `CRTEngine.generate_trade_id` | MD5[:16] of instrument\|ts\|direction\|entry@5dp | L4 lineage alias for engine trades; **not** canonical (omits SL, omits corpus) |

A later phase **SHALL NOT** "fix" those existing hashes in place. That would re-identify historical records.

### 3.2 Common immutability

#### Repository invariant — `RECOMPUTE != RECOVER` (user-accepted 2026-08-23)

> **I can rebuild it does not imply I recovered the historical object.**

This is design law, not a storage hint. It is also invariant 8 in [`docs/architecture/goal.md`](../architecture/goal.md) §3.

Regenerating L1 from L0 with today's pipeline produces *today's* vector, not the historical identity (F-046, F-050, F-061, F-063, F-066, F-072). Recovery requires the historical PK, including schema and formula identity. The same rule applies at every layer: a fold of HEAD's CRT engine is not the occupancy series of a past run; a `multi_tp_walk` of an old entry is not the `forward_walk` outcome.

1. **PK reuse is forbidden.** A PK that has been bound to a payload is never bound to a different payload.
2. **In-place rewrite is forbidden.** A correction is a new identity, or an archive of the old plus a successor pointer. Never a silent overwrite.
3. **`RECOMPUTE != RECOVER`.** See the invariant above. This bullet is the operational form of that law.
4. **Absence is not identity.** A missing PK component ⇒ the record is `UNIDENTIFIED` for that layer. It is not filled from a path, a neighbouring row, or current `CANONICAL_FEATURES`.
5. **Alias ≠ identity.** `wick_size` is not `candle_range`. `macd_hist` is not `macd_hist_raw`. Decode-only aliases (`SCHEMA_V3_ALIASES`) never appear in a PK.
6. **Producer mismatch ≠ same object.** Engine CRT occupancy and resolver CRT occupancy at the same bar are two objects (F-069). Coincidence may be measured; equality may not be assumed.

### 3.3 Common schema versioning

| Rule | Meaning |
|---|---|
| **Self-declare or unidentified** | A persisted record that does not name its schema version is `UNIDENTIFIED`. Counting keys to infer dimension is forbidden (the `opportunities.jsonl` failure). |
| **Major** | Any change that alters a PK component, a closed vocabulary, or the meaning of an existing field. New major = new object family. Old family remains an archive. |
| **Minor** | Additive optional lineage fields that do not change equality. |
| **No silent coexistence** | The active family and an archive family are never joined as if current. Join across majors is `UNJOINABLE` unless a declared coincidence table exists (none exists today; this freeze does not create one). |
| **Decode-only aliases** | Permitted solely to *read* an archive. Never emitted. Never used as a PK component. |

Active feature-schema family (user decision 2026-08-23, census §0): **v5.0, dimension 48**. That decision is identity policy, not a storage claim.

### 3.4 Common archive rules

1. **Archives keep their identity forever.** A 38-dim vector remains a 38-dim vector identity. It is never "upgraded" onto 48 by padding, slicing, or renaming.
2. **An archive must self-declare** `schema_version` (and, for L1, `canonical_dim` + `FEATURE_ORDER_HASH` of *that* family). A non-self-declaring blob is not an archive; it is `UNIDENTIFIED`.
3. **Path is not identity.** Moving a file does not change the object. Replacing bytes under the same path **does** change the object (`corpus_sha256` moves; G-05 CONTRADICTED is the historical failure).
4. **Untracked is not repository-identity.** `data/`, `logs/`, `results/`, `models/` are gitignored. Until a tracked provenance record names `corpus_sha256` / content hash, a clean clone cannot resolve the identity. This freeze does not create that provenance store.
5. **Supersession is pointer, not deletion.** `SUPERSEDED` / `ARCHIVED` / `CONTAMINATED` are statuses on an identity that continues to exist (F-022 streams stay F-022; they do not become ledgers).
6. **No migration in this phase.** Byte-identical preservation of archives is the only legal relationship between families until a later authorized change defines a coincidence table.

### 3.5 Closed status tokens (any layer)

| Token | Meaning |
|---|---|
| `IDENTIFIED` | All PK components present and well-typed |
| `UNIDENTIFIED` | At least one PK component missing or illegal |
| `UNJOINABLE` | Identified, but a requested join is missing a required lineage key or crosses a forbidden boundary |
| `ARCHIVED` | Identified under a non-active schema family |
| `CONTAMINATED` | Identified, but declared not authoritative for the claim class (e.g. F-022 detection `outcome`) |

---

## 4. L0 — OHLC

**Authorities (meaning, not storage):**
[`ohlcv_schema.py`](../../src/data_ingestion/ohlcv_schema.py) `REQUIRED_OHLCV_COLUMNS` ·
[`ohlcv-output-contract-2026-07-10.json`](ohlcv-output-contract-2026-07-10.json) G-01…G-04 PROVEN, **G-05 CONTRADICTED** ·
[`CORPUS_AUTHORITY.md`](CORPUS_AUTHORITY.md) · F-066 (clock) · F-080 (engine vs TradingView at the daily-open bar).

### 4.1 Primary key

| Component | Type | Rule |
|---|---|---|
| `instrument` | symbol | Corpus-native |
| `timeframe` | token | Closed set in §3.1 |
| `bar_open_ts` | second-precision open | Unique and strictly increasing **within** one corpus (G-02) |
| `corpus_sha256` | SHA-256 of exact bytes | Required. Logical (instrument, timeframe) alone is **not** identity — G-05 is CONTRADICTED |

Logical bar `(instrument, timeframe, bar_open_ts)` is what a trader means by "the 01:00 M15 bar." It is **not** sufficient. Engine corpus and OANDA/TradingView can disagree at the daily-open slot (F-080); those prints are different L0 objects because they are different bytes.

### 4.2 Lineage keys

| Key | Why |
|---|---|
| `source_family` | `mt5` · `binance` · `yfinance` · other declared family. Volume and clock semantics are family-scoped. |
| `clock_basis` | `broker_local` (default, F-066) · `utc_corrected`. Lives on the **corpus**, not the bar. |
| `clock_provenance_record` | Human-reviewed timezone declaration (`ClockProvenanceError` if absent on file-backed reads). |
| `bar_index` | 0-based ordinal **inside this corpus only**. Join aid, never a cross-corpus key. |
| `corpus_authority_status` | `APPROVED` · `REJECTED` · `QUARANTINED` · `UNRESOLVED` · `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` ([`CORPUS_AUTHORITY.md`](CORPUS_AUTHORITY.md)) |

### 4.3 Payload (immutable)

`open`, `high`, `low`, `close`, `volume` — the six mandatory fields. Header aliases (`Open`→`open`, `tick_volume`→`volume`) are normalization **before** identity, not identity components.

### 4.4 Not-keys

- File path (`data/XAUUSD_M15.csv` vs `data/mt5/XAUUSD_M15.csv` — G-05 counterexample).
- `Candle.index` / backtest `candle_idx` / research `_pos`. These disagree across producers (1-based vs 0-based).
- A timezone-converted timestamp treated as a different bar of the same corpus.
- A TradingView screenshot mark (evidence of structure, not an L0 identity).

### 4.5 Immutability

OHLC values bound to a PK never change. Correcting a clock label is a **corpus** event: new `corpus_sha256` and/or new `clock_basis`, which is a new L0 family, not an edit of the old bars.

### 4.6 Schema versioning

Handoff contract id `OHLCV-OUTPUT-CONTRACT-v1`. The six-field presence/integrity/timestamp-uniqueness guarantees (G-01…G-04) are identity preconditions: a row that fails them is not an L0 object.

G-05 remains CONTRADICTED in the runtime. This freeze **does not remediate G-05**. It makes the missing component (`corpus_sha256`) part of the PK so a later writer cannot omit it.

### 4.7 Archive

A superseded corpus is a different `corpus_sha256`. The old hash remains a valid PK forever. `UNRESOLVED` corpora cannot be bound as authoritative (corpus-authority doctrine); they can still be *identified* if the four PK components are known.

---

## 5. L1 — Feature Values

**Authorities:**
[`feature_schema.py`](../../src/features/feature_schema.py) `CANONICAL_FEATURES` / `CANONICAL_FEATURE_DIM=48` / `FEATURE_ORDER_HASH` ·
ontology `configs/formulas/market_ontology.yaml` (meaning, §6.6) ·
CT-001 / CN-001 · F-046 · F-047 · F-051 · F-061 · F-062 · F-063 · F-076.

### 5.1 Primary key

The **vector** identity (one per bar per schema family):

| Component | Type | Rule |
|---|---|---|
| L0 PK | four-tuple | The bar the vector is about |
| `schema_version` | token | Active family: `5.0`. Archives: `2.0` / `3.0` / `4.0` |
| `FEATURE_ORDER_HASH` | SHA-256[:16] of **that family's** ordered names | Detects silent reorder even when `len()` matches |

A **slot** identity (one feature inside the vector):

| Component | Type | Rule |
|---|---|---|
| L1 vector PK | as above | |
| `fm_id` | `FM-*` | Ontology identity. A slot with no `fm_id` is `UNIDENTIFIED` |
| `vector_index` | int | Index in **that** `schema_version`'s order. Not portable across majors |

`SCHEMA_HASH` (MD5 of concatenated names) is lineage only. It is not a PK component. `FEATURE_ORDER_HASH` is.

### 5.2 Lineage keys

| Key | Why |
|---|---|
| `formula_hash` / ontology formula identity | Same name, different math, is a different slot (F-046, F-050) |
| `normalization_basis` | `atr_relative` (active default) · `atr_absolute` arm (F-061). Changes meaning of FM-022/023 descendants |
| `session_timestamp_basis` | `broker_local` · `utc_corrected` (F-066). Changes `session` / `hour_of_day` |
| `feature_pipeline` period keys | `rsi_period`, `atr_period`, EMA spans, MACD periods — behavioral, config-owned |
| `pit_status` | e.g. `PIT_UNCLEAN_CENTERED_SWINGS` (F-051). Contaminates identity of swing-descended slots; does not dissolve the PK |
| `producer` | `FeaturePipeline` is the canonical producer. Other builders are different identities if they emit a vector |

### 5.3 Payload

The ordered numeric vector of `canonical_dim` floats. Active `canonical_dim = 48`. Warmup-dropped rows are not L1 objects (there is no bar-aligned vector).

### 5.4 Not-keys

- Column name without `fm_id` (the `wick_size` / `body_ratio` class).
- Current `CANONICAL_FEATURES` applied to an undated archive (the `opportunities.jsonl` class).
- Pipeline intermediates not in `CANONICAL_FEATURES`.
- `candidate_features` on an episode (explicitly excluded from `content_hash()`; versioned interpretation, not L1).

### 5.5 Immutability

A vector bound to `(L0, schema_version, FEATURE_ORDER_HASH)` never changes. A formula correction under the same slot name is a **new** `fm_id` or a new `schema_version`, not an edit. Recompute from L0 with HEAD code is a new identity unless every lineage key matches the original.

### 5.6 Schema versioning

| Family | Dim | Status |
|---|---|---|
| v5.0 | 48 | **ACTIVE** (sole current surface) |
| v4.0 | 39 | ARCHIVE (`SCHEMA_V4_FEATURE_DIM`) |
| v3.0 | 38 | ARCHIVE (`SCHEMA_V3_FEATURE_DIM`); `SCHEMA_V3_ALIASES` decode-only |
| v2.0 | 35 | ARCHIVE (`SCHEMA_V2_FEATURE_DIM`) |

Slice/truncate of a longer vector onto a shorter model is a **consumer compatibility** act, not an identity act. The stored vector keeps its own family.

### 5.7 Archive

38-dim and 39-dim corpora attest to what was measured then. They **cannot** be joined to the active 48-dim surface as current. A 39-dim corpus that does not self-declare its schema is `UNIDENTIFIED`, not an honorary v4.0.

---

## 6. L2 — Feature States

**Authorities:**
[`feature_states.py`](../../src/features/feature_states.py) `FeatureStateEncoder` · ontology `states:` blocks · census §4 (19 families: 13 vector-bound, 6 not). Module docstring: *NOT on the decision path. Shadow-only.*

### 6.1 Primary key

| Component | Type | Rule |
|---|---|---|
| L0 PK | four-tuple | The bar being interpreted |
| `fm_id` | `FM-*` | The identity whose `states:` block is applied |
| `ontology_states_hash` | SHA-256 of that entry's `states:` block | A changed declaration is a new interpreter, not a recode of the old states |

The state **token** (`Bullish`, `SellSideSweep`, `X_UNMAPPED(...)`, …) is **payload**, not PK. The object is "the interpretation of this feature at this bar under this declaration."

Families **not** bound to a canonical slot (`rsi_state`, `displacement_flag`, `retest_flag`, and the three magnitude bands) still use `fm_id` as PK. Vector index is lineage, not required.

### 6.2 Lineage keys

| Key | Why |
|---|---|
| L1 vector PK | The value being interpreted. Missing L1 ⇒ `UNJOINABLE` (state without a value) |
| `vector_index` | Present iff the family is vector-bound |
| `band_edges` / magnitude-window identity | Magnitude bands (`atr_magnitude`, `body_commitment`, `momentum_magnitude`) depend on a trailing window; window change ⇒ new `ontology_states_hash` or explicit window lineage |
| `encoder_id` | `FeatureStateEncoder` is the only legal producer. Another mapping is a different object |

### 6.3 Payload

The declared state name, or a marker:

- `X_UNMAPPED(<value>)` — finite value outside the declared domain
- `X_NON_FINITE(<value>)` — NaN / inf

Markers are **legal payload**. They are not identity failures. They mean declaration and reality disagreed.

### 6.4 Not-keys

- A CRTState name used as a feature state (register collapse).
- A numeric cut invented in the encoder (the encoder owns no cuts).
- `volume_spike` as a CRT `when:` predicate (F-065: declared, not consumed). Declaration is identity; consumption is not.

### 6.5 Immutability

An (L0, fm_id, ontology_states_hash) occupancy never changes. Tightening a band is a new hash, therefore a new object family. Historical occupancies stay.

### 6.6 Schema versioning

L2 versions with the ontology entry it interprets, not with `CANONICAL_FEATURES`. A v5.0 vector may be interpreted by a later ontology; that pair is a new L2 family. Continuous features with empty `states:` have **no L2 object** (35 of 48 active slots today). Absence of a state is not a state called `None`.

### 6.7 Archive

The single `bar_matrix.csv` `state__*` build (XAUUSD M15, 2026-08-20) is an untracked snapshot, not a repository identity, until a tracked provenance record exists. This freeze does not promote it.

---

## 7. L3 — CRT States

**Authorities:**
[`state_identity.py`](../../src/config_layer/state_identity.py) `CRTState` (12 members) / `VALID_TRANSITIONS` / `EXECUTION_TIMEFRAME_STATES` / `PARENT_TIMEFRAME_STATES` ·
[`crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) `_transition` ·
[`crt_state_resolver.py`](../../src/features/crt_state_resolver.py) ·
F-069 (engine ≠ resolver) · F-074 (directional displacement) · F-075 / F-077 / F-078 (parent track and HTFState are other objects).

### 7.1 Two objects, not one

| Object | What it identifies |
|---|---|
| **Occupancy** | The producer's state **at bar close** on one track |
| **Transition event** | One legal (or RESET) edge that moved occupancy |

A setup / cycle (RANGE→…→RESOLUTION) is a **derived grouping** of occupancies, not a primary object of this freeze. No canonical `setup_id` is allocated here. Engine `Trade.id` is L4 lineage, not L3.

### 7.2 Occupancy primary key

| Component | Type | Closed vocabulary |
|---|---|---|
| L0 PK | four-tuple | The bar |
| `producer_id` | token | `engine` = `CRTEngine._transition` · `resolver` = `CRTStateResolver` |
| `topology_id` | identity of `VALID_TRANSITIONS` | The 12-state map as of CH-htfcrt-parent-candle-smc-v1. A changed legal-edge set is a new topology |
| `track_id` | token | `execution_tf` (9 states) · `parent_tf` (RANGE_C1 / MANIPULATION_C2 / DISTRIBUTION_C3) |

**Forbidden equalities (hard):**

- `producer_id=engine` occupancy ≠ `producer_id=resolver` occupancy at the same bar (F-069: 88.16% agreement, structurally unreachable EXECUTION on the resolver). Coincidence is a measurement, not identity.
- `track_id=execution_tf` ≠ `track_id=parent_tf`. The sub-graphs are disjoint. No occupancy PK may mix them.
- `HTFState.DISTRIBUTION` ≠ `CRTState.DISTRIBUTION_C3` (F-077). HTFState is not in this PK.

The state enum member (`RANGE`, `SWEEP`, …) is **payload**.

### 7.3 Transition-event primary key

| Component | Type | Rule |
|---|---|---|
| Occupancy PK (the bar of the event) | as above | |
| `state_from` | `CRTState` name \| `RESET` sentinel | |
| `state_to` | `CRTState` name | |
| `event_kind` | token | `STATE_TRANSITION` · `RESET` |

`RESET` is a first-class `event_kind`. A stream that drops RESET (global `logs/crt_transitions.jsonl`) is **not** an L3 occupancy series. Folding it as if complete is a contract violation (census §5.2 / §11 Q4).

Multiple events on one bar are distinct by (`state_from`, `state_to`, `event_kind`). Occupancy payload is the **terminal** `state_to` at bar close.

### 7.4 Lineage keys

| Key | Why |
|---|---|
| `config_version` / `config_hash` | CRTConfig changes legal gates; same PK with different config is a different *run*, joined via lineage, not collapsed |
| `run_id` | Required to attribute a stream. Today's global CRT log has none — that log is `UNIDENTIFIED` as L3 |
| `instrument` on the event | Required. Hardcoded `instrument=""` is `UNIDENTIFIED` |
| `parent_state` (bias input) | Lineage of an *execution_tf* occupancy when the parent-CRT gate is armed; not a PK component (F-075, F-089) |
| `directional_displacement_contract` | F-074 in force or not. Unsigned vs directional DISPLACEMENT are different topologies, not a retune |
| `constructor_id` | Recipe family: sha256 of `{construction, invocation}` (`crt_identity_schema.derive_constructor_id`). Pointers, not file contents. Lineage of a **series**, never a bar-occupancy PK component. Declared on `constructors.<C>.parameterization` in [`configs/formulas/crt_state_identity.yaml`](../../configs/formulas/crt_state_identity.yaml). Not yet stamped on occupancy records |

### 7.4.1 Occupancy series identity (additive, `CH-occupancy-series-identity`, 2026-09-05)

A **series** is the stream of occupancies and events produced by one construction of one producer on one corpus on one track. It is not a bar. It is not State Identity (Tier-1 names in `crt_state_identity.yaml`). Naming it does **not** change §7.2.

`occupancy_series_identity` (equality of two occupancy *streams*):

```text
producer_id
+ topology_id
+ track_id
+ corpus_sha256
+ run_id
```

This is the grouping already used by the physical-storage event-series check (`PHYSICAL_STORAGE_ARCHITECTURE.md` §4.4). A series that contains `STATE_TRANSITION` and zero `RESET` is `IDENTITY_INCOMPLETE` (§7.3).

**Reproducibility lineage** (required to recreate the series, not to equal two bar occupancies):

| Key | Level | Answers |
|---|---|---|
| `constructor_id` | recipe family | Which transformation machinery. Engine `965168941ce1e903…` (`supply_set=ohlcv_candle_stream`, `htf_source=internal_htf_builder`, `injection=none`). Resolver `61ef9dfe48ed4efb…` (`canonical_v5_plus_nonvector`, `phase_locked_timeline`, `injection=none`). The hash is over **pointers**, not JSON contents: HEAD `v2_multi_2026_04` and working-tree `v2_htfcrt_2026_08` may share an engine `constructor_id` |
| `config_hash` / `config_version` | settings | Which CRTConfig / promoted JSON was loaded. Distinct from `constructor_id` |
| invocation tokens | named recipe fields | `supply_set`, `htf_source`, `injection` — already inside `constructor_id`; named so a reader need not reverse the hash |

Three levels, not synonyms:

```text
Level 1  constructor_id     recipe family (pointers + invocation)
Level 2  config_hash        settings actually loaded
Level 3  corpus_sha256      observations that entered the machine
```

`run_id` attributes one execution of that triple. Without it the series is `UNIDENTIFIED` (today's global `logs/crt_transitions.jsonl`).

**Forbidden equalities (hard), in addition to §7.2:**

- `constructor_id` is not a bar occupancy PK component. Same recipe on two corpora is two series.
- `producer_id` is not optional because `constructor_id` is present. Two recipes can share a producer (`supply_set` split: 17,563 RANGE bars). Two producers cannot share occupancy (F-069).
- Omitting `track_id` or `topology_id` from the series identity collapses `execution_tf` into `parent_tf`, or unsigned into directional DISPLACEMENT.
- BC-1 corpus identity (`corpus_sha256` / Dataset Identity) is **L0**. This tuple is **L3 series**. Closing BC-1 does not identify an occupancy series; an occupancy series that omits `corpus_sha256` is not identified.
- `injection ≠ none` (`engine_state_to` / `engine_reset`) is a different constructor family, not "resolver with extras." Unnamed until registered under `constructors:`.

Word collision: identity YAML **parameterization** = `{construction, invocation}` (Level 1, hashed into `constructor_id`). **Settings** = `config_hash` / promoted version (Level 2). Do not use "parameterization" for both.

### 7.5 Payload

Occupancy: one `CRTState` member legal on that `track_id`.

Transition: `state_from`, `state_to`, `event_kind`, plus optional reason/metadata that do **not** enter the PK.

### 7.6 Not-keys

- Feature-state conjunctions (`SellSideSweep` ∧ `Displacement`). L2 does not produce L3 in this repository (census §8: L2→L3 edge is MISSING; the engine reads OHLC).
- `crt_state_resolved` column used as engine occupancy.
- Global `crt_transitions.jsonl` folded without RESET.
- `SHADOW_PENDING` / `EXPIRED` treated as illegal. They are legal members of `execution_tf`.
- `constructor_id` used as a bar occupancy PK, or as a substitute for `producer_id` / `track_id` / `topology_id`.
- `occupancy_series_identity` treated as a seventh layer or as State Identity.

### 7.7 Immutability

An occupancy PK binds to one payload at bar close. A later engine revision that would have labelled the bar differently is a new (`producer_id`, `topology_id`) family. Historical occupancies do not move.

Fail-open emits (conditional `if ev_logger and candle`) mean **a missing event is not evidence of no transition**. Absence ⇒ `UNIDENTIFIED` occupancy for that bar, not `RANGE` by default.

### 7.8 Schema versioning

| Topology | Members | Track |
|---|---|---|
| 9-state execution (pre-parent) | RANGE…RESOLUTION + SHADOW_PENDING + EXPIRED | `execution_tf` |
| 12-state (current) | 9 + RANGE_C1 + MANIPULATION_C2 + DISTRIBUTION_C3 | two disjoint tracks |

A 9-state occupancy series is an archive family. It does not grow three members in place.

### 7.9 Archive

Run-scoped `{INST}_events.jsonl` that is fold-complete (STATE_TRANSITION **and** RESET) may identify occupancies **for that run** iff `run_id`, `instrument`, and `corpus_sha256` are present. Today's global stream cannot. This freeze does not repair the stream.

---

## 8. L4 — Geometry

**Authorities:**
[`crt_engine_v2.py`](../../src/config_layer/crt_engine_v2.py) `Trade` ·
[`execution_planner.py`](../../src/config_layer/execution_planner.py) `ExecutionPlannerV1_2` ·
[`episodes/schema.py`](../../src/research/episodes/schema.py) `EntrySnapshot` / `episode_id` / `entry_geometry_hash` ·
[`clean_labels/builder.py`](../../src/research/clean_labels/builder.py) `_unit_id` ·
SEM-012 (visual CRT) · SEM-017 (`multi_tp_walk`) · F-072 (ATR units) · F-088 (production object ≠ `forward_walk` object).

### 8.1 Primary key

| Component | Type | Rule |
|---|---|---|
| L0 PK | four-tuple | The **entry** bar |
| `direction` | `long` \| `short` | |
| `entry_px` | price, 8 dp | |
| `sl_px` | price, 8 dp | Required. Geometry without a stop is not an L4 object (`EntrySnapshot` invariant) |
| `geometry_kind` | token | Closed: see §8.2 |
| `geometry_schema` | token | Closed: see §8.6 |

`tp_px` / `tp1_px` / `tp2_px` are **payload** (a structural hypothesis may have `tp=None`). Changing TP under the same entry/SL is a different payload bound to a new `geometry_schema` if the schema requires those fields, not a silent edit.

Existing aliases (lineage only, not PK):

- `_unit_id` = SHA-1[:16] of `instrument|ts|direction|entry|sl`
- `episode_id` = same plus `|population`
- `generate_trade_id` = MD5[:16] of `instrument|ts|direction|entry@5dp` (**omits SL and corpus** — insufficient as canonical PK)

### 8.2 Closed `geometry_kind`

| Token | Producer | Notes |
|---|---|---|
| `engine_trade` | `CRTEngine` `Trade` | Production object: entry, sl, tp1, tp2 |
| `planner_v1_2` | `ExecutionPlannerV1_2` | Planned levels. Today: never persisted. Still a distinct kind |
| `oracle_every_bar` | oracle labeler | Synthetic both-directions geometry at every bar (F-086 population) |
| `episode_entry` | `OpportunityEpisode.entry` | One TP; `population` is additional lineage |
| `visual_crt_sem012` | SEM-012 | Pool-founded; Arm A/B are outcome kernels, not geometry kinds |
| `detection_stream` | `opportunities.jsonl` sl/tp | **Not authoritative** for claims about trades (F-022). May be identified; may not be joined as `engine_trade` |

### 8.3 Lineage keys

| Key | Why |
|---|---|
| `population` | `episode_id` includes it so detection vs spine at the same bar do not collide |
| `atr_identity` | FM-041 close-relative vs FM-074 absolute (F-072). Levels derived from the wrong ATR are a different geometry |
| `planner_config` | `default_sl_atr_mult`, TP multipliers, TTL |
| L3 occupancy PK | Optional lineage when the geometry is engine-founded. Oracle every-bar geometry has none |
| `displacement_origin` | SEM-021: open of the founding displacement candle, captured at build time |
| `stop_policy` / `trail_fraction` | Identity of the *trajectory*, not of the entry geometry (F-088). Lineage of L5, not L4 PK |

### 8.4 Payload

Frozen-at-open levels: `entry_px`, `sl_px`, and the TP fields the `geometry_schema` declares.

**Trajectory is not payload of L4.** Partial fill, stop-to-half-TP1, trail, breakeven, and time-stop are a path under a policy. They belong to L5's walk kernel (SEM-017). Recording only endpoints and calling them the production geometry is the F-088 silent-gap.

### 8.5 Not-keys

- `Trade.id` / `CRT-NNNN` counters (run-local).
- `partial_tp_breakeven_enabled` as if it named breakeven (it does not; F-088 naming trap retained).
- Planner output that was never written (census: planned geometry is fully ephemeral). Unwritten ≠ identified.
- Detection `sl`/`tp` used as engine geometry.

### 8.6 Schema versioning (`geometry_schema`)

| Token | Fields | Status |
|---|---|---|
| `single_tp` | entry, sl, one tp | Archive relative to production; this is what `forward_walk` walks |
| `dual_tp_partial` | entry, sl, tp1, tp2, partial fraction | Production object (SEM-017) |
| `structural_no_tp` | entry, sl, tp=None | Legal for hypothesis episodes |

A `single_tp` geometry and a `dual_tp_partial` geometry at the same entry/SL are **different objects**. They may share an L0 bar; they do not share L4 identity.

### 8.7 Archive

Oracle labels (`labels.csv`) identify `oracle_every_bar` + `dual_tp_partial` (or whatever schema the labeler declared) under their own L0. They are not `engine_trade`. Engine `{INST}_trades.csv` identifies `engine_trade` iff the PK components are recoverable; `config_version` on that file is lineage, not PK.

---

## 9. L5 — Outcome

**Authorities:**
`forward_walk` · `multi_tp_walk` (SEM-017) · backtest ledger ·
[`MEASUREMENT_CONTRACT.md`](MEASUREMENT_CONTRACT.md) · SEM-015 cost · SEM-016 adverse fill ·
F-022 · F-081 · F-082 · F-083 · F-084 · F-088.

### 9.1 Primary key

| Component | Type | Rule |
|---|---|---|
| L4 PK | as §8.1 | The geometry being walked |
| `walk_kernel` | token | Closed: see §9.2 |
| `cost_model_id` | token | Closed: see §9.2 |
| `fill_model_id` | token | Closed: see §9.2 |

An outcome without a geometry is not an L5 object. An outcome with a geometry but a different walk or cost is a **different** L5 object (F-082 / F-088: the same entry set under a different basis is not a re-measure of the same outcome).

`measurement_contract_id` (`MC-*`) is **lineage**, not PK. A sealed contract binds a claim to a basis; the outcome identity is the basis itself. Two claims may share an L5 object; they must not share an L5 object across contracts that differ on walk/cost/fill.

### 9.2 Closed vocabularies

**`walk_kernel`**

| Token | Object walked | Notes |
|---|---|---|
| `forward_walk_intrabar_fixed` | `single_tp` | Historical default of research programs |
| `multi_tp_walk` | `dual_tp_partial` | Production-shaped (SEM-017); stop-policy params are additional lineage |
| `backtest_ledger` | `engine_trade` as the engine actually closed it | The live/backtest closer, not a research kernel |
| `detection_stream` | not a walk | **CONTAMINATED** for economic claims (F-022). Identifiable as a stream field; not an L5 of `engine_trade` |

**`cost_model_id`**

| Token | Notes |
|---|---|
| `flat_12bps` | Historical research default; ~11× too punitive on XAUUSD (F-082) |
| `sem015_component_xauusd` | Measured broker cost, metals/XAUUSD only |
| `none_gross` | Gross-only; must be named, never implied |

**`fill_model_id`**

| Token | Notes |
|---|---|
| `touch_exact` | Stop fills at the stop (historical `forward_walk` booked −1.000R exactly) |
| `sem016_adverse` | Adverse stop fill (F-082) |
| `engine_intrabar` | Backtest `_intrabar_trigger_price` (SL-first tie-break; F-088) |

### 9.3 Lineage keys

| Key | Why |
|---|---|
| `measurement_contract_id` | Claim binding. Absence ⇒ economic claims inadmissible (MEASUREMENT_CONTRACT) |
| `stop_policy` / `trail_fraction` / `horizon` | Path under `multi_tp_walk` |
| `split_id` / OOS partition | Same outcome object, different sample; split is not PK |
| `label_authority` | `clean_labels` provenance field |
| `y_unit` | `R_gross` · `R_net` · `win` — payload interpretation; mixing them is a claim error, not a PK change |

### 9.4 Payload

At minimum: `y_R_gross`. Net requires a named `cost_model_id` ≠ `none_gross`. Path stats (`mfe`, `mae`, `duration`, `exit_reason`) are payload extensions; they do not change equality.

### 9.5 Not-keys

- `opportunities.jsonl` `outcome` / `rr_achieved` (F-022, F-041B, F-045).
- A p-value, IC, or win-rate without an L4 PK.
- Re-derived y under a different kernel presented as the original y.
- `n` (count) as if it identified the object.

### 9.6 Immutability

An (L4, walk, cost, fill) outcome never changes. A cost-model correction (F-082) produces a **new** L5 identity. F-081's REJECT remains a valid statement about `flat_12bps` + `touch_exact`; F-084 is a different object under `sem015` + `sem016`. That is refinement, not rewrite.

### 9.7 Schema versioning

L5 versions with the walk kernel and the measurement-contract schema (`measurement_contract.schema.json` v1.0.0). Additive metric fields are minor. Changing what "R" means (gross vs net, SL-first vs TP-first) is major.

### 9.8 Archive

F-022 streams stay `CONTAMINATED` archives of a detection field. They are never promoted to `walk_kernel=backtest_ledger`. Clean-label / oracle / engine ledgers remain distinct families even when they share an L0 bar.

---

## 10. Cross-layer join rules

Joins are allowed only along declared lineage. There is no implicit "same timestamp ⇒ same object."

```
L0 OHLC
  └─ L1 Feature Values     requires L0 PK + schema family
       └─ L2 Feature States  requires L0 PK + fm_id + states hash
                             (L1 lineage required to prove the value existed)
  └─ L3 CRT occupancy      requires L0 PK + producer + topology + track
                             (does NOT require L2 — that edge does not exist in this repo)
       └─ L4 Geometry        may cite L3 occupancy as lineage; oracle geometry does not
            └─ L5 Outcome    requires L4 PK + walk + cost + fill
```

**Hard bans**

1. Join L1 v5.0 to L1 v3.0/v4.0 as current.
2. Join L3 `engine` to L3 `resolver` as equal.
3. Join L3 `execution_tf` to L3 `parent_tf` as one machine.
4. Join L4 `detection_stream` to L4 `engine_trade` as the same geometry.
5. Join L5 `forward_walk_intrabar_fixed` to L5 `multi_tp_walk` as the same outcome.
6. Join any layer across `corpus_sha256` without an explicit coincidence table (none exists).
7. Infer a missing PK from a file path, a row index, or HEAD `CANONICAL_FEATURES`.

**Reconstruct vs recover.** A later phase may *recompute* L1/L2 from L0. That produces a new identity unless every lineage key of the original is present and matched. Recompute cannot close a revalidation of a historical finding by itself (census Q2).

---

## 11. What today's artifacts are, under this freeze

This is a reading of the census through the new keys. It does not change any file.

| Layer | Typical today's record | Status under this freeze |
|---|---|---|
| L0 CSV | path + row, sometimes a `corpus_sha256` in one manifest | `UNIDENTIFIED` unless the four PK components are known |
| L1 `feature_snapshots.jsonl` | 48-dim, `instrument=""`, envelope `schema_hash` only | `UNIDENTIFIED` (no instrument, no corpus, no run) |
| L1 `clean_labels.jsonl` | self-declares `feature_dim: 38` | `ARCHIVED` (v3.0 family) if L0 PK recoverable; else `UNIDENTIFIED` |
| L1 `opportunities.jsonl` | 39-dim, no schema stamp | `UNIDENTIFIED` |
| L2 `bar_matrix.csv` `state__*` | one XAUUSD build, untracked | untracked snapshot; not repository-identity |
| L3 run `{INST}_events.jsonl` | fold-complete for that run | identifiable **for that run** iff instrument + corpus + producer named |
| L3 `logs/crt_transitions.jsonl` | no RESET, `instrument=""` | `UNIDENTIFIED`; not an occupancy series |
| L4 `{INST}_trades.csv` | engine levels | `engine_trade` candidate; SL/corpus must be present to identify |
| L4 planner | never written | no object |
| L5 opportunities `outcome` | detection field | `CONTAMINATED`; not L5 of `engine_trade` |
| L5 oracle `labels.csv` | every-bar geometry + walk | identifiable as `oracle_every_bar` + declared walk/cost/fill |

---

## 12. Freeze, amendment, and the Phase 2 gate

### 12.1 Freeze

This document is **FROZEN v1.0.0**. Phase 1 is **CLOSED**. User-accepted 2026-08-23.

`LAYER_IDENTITY_STATUS = CLOSED`

The six PKs, the closed vocabularies, the immutability rules (including `RECOMPUTE != RECOVER`), the schema-versioning rules, and the archive rules are the identity of the layers. Equality is frozen. Storage is not started.

### 12.2 Amendment

- Refine **in place** only by additive lineage keys or by tightening a prohibition.
- First additive lineage amendment: `CH-occupancy-series-identity` (2026-09-05) names `occupancy_series_identity` (§7.4.1) and adds `constructor_id` as a series lineage key (§7.4). Bar occupancy PK (§7.2) is unchanged. `LAYER_IDENTITY_STATUS` stays `CLOSED`. FROZEN marker stays **v1.0.0**.
- A PK change, a new closed-vocabulary member that alters equality, or a merge of two objects that this freeze keeps distinct, is a **new major** (`v2.0.0`) under a new change id.
- Never delete a rule. Mark it `SUPERSEDED` and point at the successor (CLAUDE.md §6.2 rule 4).
- Do not allocate Semantic OS ids, FM-ids, or F-ids as a side effect of amendment unless that change's class authorizes it.

### 12.3 Phase 2 gate (answered) / Phase 3 gate

Phase 1 is **CLOSED**. The Phase 2 question — *How does storage preserve the frozen identity?* — is answered and **CLOSED** by:

[`STORAGE_PRESERVATION_CONTRACT.md`](STORAGE_PRESERVATION_CONTRACT.md) **v1.0.0** · `CH-storage-preservation-contract` (user-accepted 2026-08-23; `STORAGE_PRESERVATION_STATUS = CLOSED`)

That document is subordinate to this freeze. It does not redefine any PK.

Phase 3 (physical storage design) **SHALL NOT** drift into Parquet layout, writers, readers, migrations, or replay engines until the proposal, in its first paragraph, cites:

```text
CANONICAL_LAYER_IDENTITY_CONTRACT.md
v1.0.0
CH-canonical-layer-identity

STORAGE_PRESERVATION_CONTRACT.md
v1.0.0
CH-storage-preservation-contract
```

and is all-YES on the preservation contract’s six-layer admissibility table.

A proposal that redefines a PK, invents a key not in this document, omits a PK component, drops RESET, or treats “I can rebuild it” as recovery (`RECOMPUTE != RECOVER`) is rejected at classification.

Until that citation exists, the following remain **forbidden**:

- storage schemas, files, tables, Parquet layouts, "semantic stores," "replay stores"
- writers, readers, indexes, joins-as-code
- migrations, backfills, archive-to-active coercions
- replay engines whose purpose is to persist or serve these objects
- code in `src/`, `scripts/`, `tests/` whose purpose is to persist or serve these objects
- treating any existing JSONL/CSV as if it already carried these PKs

### 12.4 Non-goals retained

- No G001, no promotion, no `ACTIVE_VERSION` change.
- No CRT recertification, no SEM-011 graduation.
- No remediation of G-05, of the fold-incomplete CRT stream, or of untracked artifacts.
- No claim that freezing identity makes historical findings revalidatable. It makes it *possible to say* whether a future record is the same object.

---

## 13. Worked equalities (normative examples)

These are the intended tests of the freeze. They are not implemented.

1. Same XAUUSD M15 01:00 bar, engine CSV vs TradingView CSV, different `corpus_sha256` → **two L0 objects** (F-080).
2. Same L0 bar, 48-dim v5.0 vector vs 38-dim v3.0 vector → **two L1 objects**; `UNJOINABLE` as current.
3. Same L0 bar, `wick_size` archive name vs `candle_range` v4+ name → alias decode may recover the slot; the archive family remains v3.0.
4. Same L0 bar, engine `DISPLACEMENT` vs resolver `DISPLACEMENT` → **two L3 occupancies**.
5. Same L0 bar, `execution_tf.RANGE` vs `parent_tf.RANGE_C1` → **two L3 occupancies**.
6. Same entry/SL, `geometry_schema=single_tp` vs `dual_tp_partial` → **two L4 objects**.
7. Same L4, `flat_12bps` vs `sem015_component_xauusd` → **two L5 objects** (F-081 vs F-084).
8. `opportunities.jsonl` `outcome` vs engine ledger PnL at the same timestamp → **not the same L5** (F-022).
9. Re-running `FeaturePipeline` on the same L0 with HEAD code after F-061 → **new L1** unless `normalization_basis` and formula identity match the original.
10. Same `producer_id=resolver`, same corpus, different `supply_set` → **two occupancy series** (17,563 RANGE-bar split). `producer_id` alone does not identify the series.
11. Same `constructor_id=96516894…`, different `config_hash` (HEAD `v2_multi_2026_04` vs working-tree `v2_htfcrt_2026_08`) → **same recipe family, two series** if both run. Recipe ≠ run.
12. Same L0 bar, engine `EXPANSION` vs resolver `EXPANSION` → still **two bar occupancies** (§13.4). Joining them as one series because both say EXPANSION is a contract violation.

---

## 14. Authority footer

- **Grants:** a frozen identity vocabulary for six layers. Phase 1 CLOSED / FROZEN v1.0.0, user-accepted 2026-08-23. `RECOMPUTE != RECOVER` is a repository invariant.
- **Does not grant:** storage, writers, readers, migrations, replay engines, production authority, economic claims, CRT CLOSED, or a Semantic OS contract id.
- **Does not resolve:** G-05 (logical corpus ≠ physical bytes — now a PK component, not a remediating writer), F-069 (engine ≠ resolver), F-088 (walk kernel ≠ production object) — it **names** them as identity splits so they cannot be silently collapsed later.
- **Predecessor census** remains the authority for *what exists on disk today*. This contract is the authority for *what a thing is*.
- **Phase 2** is CLOSED: [`STORAGE_PRESERVATION_CONTRACT.md`](STORAGE_PRESERVATION_CONTRACT.md) v1.0.0, user-accepted 2026-08-23. Preservation of this freeze, never a second definition of equality.
- **Phase 3** is CLOSED: [`PHYSICAL_STORAGE_ARCHITECTURE.md`](PHYSICAL_STORAGE_ARCHITECTURE.md) v1.0.0. Phase 4 Identity Check is `src/identity/` (not live spine).

No F-id registered. A freeze is design law (`goal.md` §3), not a market conclusion.
