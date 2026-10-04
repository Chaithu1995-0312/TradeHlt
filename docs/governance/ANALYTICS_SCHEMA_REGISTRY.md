# Analytics Schema Registry (DuckDB runtime columns)

**Status:** design-only, **provisional** governance inventory (symbol table).  
**Date:** 2026-09-06 (IST)  
**Scope:** Runtime analytics columns exposed (or projectable) through Trace → Parquet → DuckDB for the six `FAMILY_GLOBS` families. **Not** Context / ODP / PolicyOpinion design schemas. No new Parquet families, no YAML, no `src/` changes.

**Doctrine pointer:** Classification and the SAFE_ALIAS five-question gate are normative in  
`docs/design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md` §5 (rev 2.1 vocabulary doctrine).  
This registry is the **symbol-table inventory** of existing columns — provisional, **not** a frozen Alias Register.

**Phase 4 Lineage companion:** [`ANALYTICS_LINEAGE_REGISTRY.md`](./ANALYTICS_LINEAGE_REGISTRY.md) (descriptive origin columns; joins on field_name+family; 1:1 with this inventory). Lineage answers origin before attribution (Phase 5). Analytics never becomes authority.


### SAFE_ALIAS five-question gate (must all be true)

1. Same owner?  
2. Same population?  
3. Same cardinality?  
4. Same measurement meaning?  
5. Same decision rights?

Only then: **SAFE_ALIAS**. Else **HOMONYM** or **PROHIBITED_ALIAS**.

### Classification tokens used here

| Token | Meaning |
|-------|---------|
| **EXACT_MATCH** | Canonical physical name for this concept in this family / owner |
| **SAFE_ALIAS** | Different physical name, same concept — mapping allowed only if gate passes (usually needs producer-explicit) |
| **HOMONYM** | Same token / near-token, different concept or population — do not collapse |
| **PROHIBITED_ALIAS** | Mapping would erase ownership or D2 population identity |
| **NEW** | Used sparingly; prefer real exposed columns. Design-only absences live under **Tripwires / non-columns** |

### Recomputable doctrine (`recomputable`)

Column meaning for research ownership — **not** a Market Ontology claim:

| Value | Meaning |
|-------|---------|
| **true** | Regenerable from current owners + inputs (engine state, resolver `ontology_state`, DE decision/score, Ultron size, structure predicates from bars/config, feature bags, path metrics from bars+trade params, etc.). Research meaning: *what the owner would compute given the same inputs*. |
| **false** | Historical artifact / provenance / run identity that is **not** recomputed as a fact: `run_id`, hashes, corpus pins, `schema_version`, `emitted_by` / `producer_id`, emission timestamps, positional join indices (`bar_index`, `candle_index`), event discriminants, frozen outcome / training labels whose research meaning is *what was recorded that run*. |

**Consistency rule:** when unsure, prefer **false** for provenance / pins / ids, and **true** for owner-computed values. Labels that are *outputs of a past run* stay **false** even if a pipeline could be re-run.

**Examples:** `engine_state_after` (CRTEngine) → true; `ontology_state` (Resolver) → true; DE `decision` / scores → true; Ultron `final_position_size` → true; Planner `execution_id` → false; Trace `emitted_at` / `emitted_by` → false.

**Open question (restated):** Can every DuckDB-exposed column be traced to **exactly one owner** and **exactly one population**?

---

## 1. Ownership stack (keep separable)

| Layer | Role | Analytics examples (existing) |
|-------|------|-------------------------------|
| **Identity** | What population / stratum is discussed | `run_id`, `instrument`, `timeframe`, `corpus_sha256`, `bar_index`, partition keys `engine_state_after` / `crt_state_after` / `kind` / `event` |
| **Measurement** | How observations are stored and queried | `ontology_state`, structure atoms, path metrics, feature bags, episode metrics |
| **Decision** | How live opinions / accept-reject are applied | Telemetry `score*`, `accepted`, `reject_reason` / `rejection_reason`, `intent`; label `decision_ts` (timestamp of label decision — **not** DE `decision`) |

Design Identity fields such as Context `state_producer` / bare `state` are **not** columns in this registry (see Tripwires).

**Family discovery:** `scripts/analysis/query_trace.py` → `FAMILY_GLOBS`  
(`crt_construction`, `crt_telemetry`, `events`, `opportunities`, `clean_labels`, `bar_structure`).

---

## 2. Per-family registries

Evidence bases: live JSONL under `logs/` / `results/`, emitters `src/runtime/crt_construction_trace.py` / `bar_structure_snapshot.py`, vocabulary audit inventories, `docs/reference/schemas.md` §9.17, parquet manifests where present.

For huge families (`crt_telemetry` kinds, `clean_labels` / `opportunities` feature blobs): **key/canonical** columns listed thoroughly; kind-specific nested bags omitted unless they collide with identity/decision vocabulary. Always included when present: `state*`, `*confidence*`, `producer*`, `emitted_by`, `score*`, `decision*`, `approve`, `execute`, `reject*`.

### 2.1 `crt_construction` (join spine)

**Owner:** emitter `runtime.crt_construction_trace` (`src/runtime/crt_construction_trace.py`, `TRACE_OBSERVATION_JOIN`).  
**Population:** dual-construction bar observations (engine + resolver spines on same `bar_index`).  
**Partition (Parquet):** `engine_state_after`.  
**Sample evidence:** `logs/dual_construction_v2_envelope_safe/XAUUSD_crt_construction.jsonl` (34 top-level keys).

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| schema_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Trace record schema version string |
| run_id | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Run identity for join / lineage |
| instrument | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Instrument geography (join key; cross-family HOMONYM if co-projected without family qualifier) |
| timeframe | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Timeframe geography |
| corpus_path | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Source corpus path used for the run |
| corpus_sha256 | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Corpus content pin |
| config_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Config version label |
| config_hash | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Config content hash |
| ontology_source | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Ontology YAML path (e.g. market_crt_states) |
| ontology_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Ontology version integer |
| bar_index | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Bar index in corpus / engine walk |
| timestamp | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Bar timestamp (ISO); cross-family HOMONYM risk |
| emitted_by | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Literal `runtime.crt_construction_trace` |
| phase | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Emission phase (e.g. WARMUP / live) |
| engine_state_before | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Engine CRT state entering the bar |
| engine_state_after | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Engine CRT state after bar; **partition key**; engine population |
| engine_action | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Engine action taken this bar |
| engine_reason | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Engine reason / reject text |
| engine_gates | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Gate snapshot object/dict for the bar |
| ontology_state | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver final label for the bar (**resolver population**, not engine) |
| agree | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Whether engine and resolver labels agree |
| divergence_pair | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Pair recording engine vs resolver divergence |
| agree_scope | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Scope / mode of agreement check |
| engine.crt_state | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Nested/flat engine CRT state mirror (same population as `engine_state_after`) |
| engine.transitions | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Engine transition payload for the bar |
| engine.live_context | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Nested live context bag (cached sweep/session etc.); nested keys omitted unless collision |
| resolver.feature_vector | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver feature vector payload |
| resolver.l2_map | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver L2 map payload |
| resolver.predicate_affinity | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver predicate affinity payload |
| resolver.continuous_passed | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Continuous predicate pass flags |
| resolver.projected_site | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver projected site |
| resolver.supply_ok | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver supply OK flag |
| resolver.missing_when | crt_construction_trace | crt_construction | EXACT_MATCH | true | true|Resolver missing-when diagnostics |
| producer_id | crt_construction_trace | crt_construction | EXACT_MATCH | false | false|Envelope / provenance id string (sample always `resolver_engine_v1`). **Not** D2 `state_producer` — see PROHIBITED tripwire |

**Row count (this inventory):** 34.

**Population note:** `engine_state_after` and `ontology_state` are **two populations** on one row (engine vs resolver). One owner (emitter), two state populations — D2 requires an explicit producer to treat either as Context `state`.

---

### 2.2 `crt_telemetry`

**Owner:** CRT runtime telemetry writers (run `*_crt_telemetry.jsonl` under `results/` / scratch roots).  
**Population:** kind-discriminated CRT telemetry events (not the construction join spine).  
**Partition / discriminant:** `kind`.  
**Sample evidence:** multi-run census under `results/*/*_crt_telemetry.jsonl` (kinds observed: `RESET_ATTRIBUTED`, `CANDIDATE_LIFECYCLE`, `EXPANSION_RETRACE_CHECK`, `DECISION_DISTANCE`, `TRANSITION_COUNTER`, `RETEST_REPLAY`).

Kind-specific nested bags omitted unless identity/decision collision. Columns below are key/canonical + all `state*` / `score*` / `decision*` / `reject*` / `intent` seen.

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| kind | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Row discriminant / partition |
| candidate_id | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Candidate identity across lifecycle / distance / reset rows |
| candle_index | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Candle index for the telemetry event |
| timestamp | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Timestamp when present (e.g. `RETEST_REPLAY`); cross-family HOMONYM |
| from_state | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Prior CRT state (`RESET_ATTRIBUTED`); HOMONYM vs events `state_from` |
| to_state | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Next CRT state (`RESET_ATTRIBUTED`); HOMONYM vs events `state_to` |
| state_age_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Age of current state in candles at reset attribution |
| entered_states | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|States entered during candidate lifecycle |
| state_entry_counts | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Aggregate state entry counts (`TRANSITION_COUNTER`) |
| reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Attribution / transition reason text |
| htf_window_position | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|HTF window position at event |
| would_expand | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Whether expansion would have occurred |
| would_expand_score | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Score used in would-expand check; HOMONYM vs other `score*` |
| would_expand_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Threshold paired with `would_expand_score` |
| first_seen_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|First candle index candidate seen |
| first_seen_ts | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|First-seen timestamp |
| last_seen_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Last candle index candidate seen |
| age_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Candidate age in candles |
| max_score_seen | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Max score observed in lifecycle; HOMONYM vs other `score*` |
| score_at_approval | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Score at approval moment (lifecycle); approve-adjacent — not Policy `approve` |
| death_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Why candidate died |
| shadow_used | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Whether shadow path was used |
| shadow_context | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Shadow context payload (bag; details omitted) |
| shadow_displacement_br | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Shadow displacement metric |
| score_actual | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Actual score at decision-distance check |
| score_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Threshold compared to `score_actual` |
| decision_distance | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Distance metric between score and threshold (`DECISION_DISTANCE`) |
| accepted | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Whether candidate/retest was accepted |
| rejection_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Rejection reason (`DECISION_DISTANCE`) |
| soft_conf_candle_num | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Soft-confirmation candle number |
| score | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Bare score on `RETEST_REPLAY` — **HOMONYM** with other score columns if treated as one global field |
| intent | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Planner/retest intent string; near Policy `intent_stance` but different role → HOMONYM if bare-joined |
| reject_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Reject reason on `RETEST_REPLAY` (name variant of `rejection_reason`) |
| direction | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Trade/retest direction when present |
| entry | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Entry price on retest replay |
| atr | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|ATR at retest replay |
| disp_high | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Displacement high |
| disp_low | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Displacement low |
| sl_atr_buffer | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|SL ATR buffer |
| tp1_mult | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|TP1 multiple |
| tp2_mult | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|TP2 multiple |
| episode_start_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Expansion/retrace episode start |
| episode_end_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Expansion/retrace episode end |
| duration_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Episode duration |
| max_retrace_depth_abs | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Max retrace depth |
| ceiling_at_max | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Ceiling at max retrace |
| time_to_max_retrace_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Time to max retrace |
| qualified | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Episode qualification flag |
| outcome | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|Episode outcome label |
| expansion_dwell_stats | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Dwell stats bag (`TRANSITION_COUNTER`) |
| ended_by | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | false|What ended the episode (when present) |
| freshness_ratio | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Freshness ratio (when present) |
| age_hours_actual | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Actual age hours (when present) |
| age_hours_estimated | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Estimated age hours (when present) |
| age_pct_of_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Age as % of threshold (when present) |
| candidate_age_at_entry | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | true|Candidate age at entry (when present) |

**Absent in this family (do not invent):** bare `confidence`, `approve`, `execute`, `decision` (DE enum), `emitted_by`, `producer_id`, `state_producer`.

**Row count (this inventory):** 56 key/canonical (+ note: additional kind-only metrics may exist; omitted unless collision).

---

### 2.3 `events`

**Owner:** Engine/runtime event JSONL (`*_events.jsonl`).  
**Population:** discrete CRT/runtime events.  
**Partition default:** `event`.  
**Sample evidence:** `logs/dual_construction_v2/scratch_roots/.../XAUUSD_events.jsonl` (keys stable; event values include `RESET`, `STATE_TRANSITION`, `SWEEP`, `BEGIN_SOFT_CONF`, `FILTER_REJECTED`).

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| event | runtime events writer | events | EXACT_MATCH | false | false|Event type discriminant / partition |
| timestamp | runtime events writer | events | EXACT_MATCH | false | false|Event timestamp; cross-family HOMONYM |
| candle_index | runtime events writer | events | EXACT_MATCH | false | false|Candle index of event |
| state_from | runtime events writer | events | EXACT_MATCH | true | true|Prior state for transition/reset; HOMONYM vs telemetry `from_state` |
| state_to | runtime events writer | events | EXACT_MATCH | true | true|Next state; HOMONYM vs telemetry `to_state` |
| direction | runtime events writer | events | EXACT_MATCH | true | true|Direction associated with event |
| price | runtime events writer | events | EXACT_MATCH | true | true|Price at event |
| reason | runtime events writer | events | EXACT_MATCH | true | true|Reason text |
| metadata | runtime events writer | events | EXACT_MATCH | false | false|Nested metadata bag (omitted detail) |

**Row count (this inventory):** 9.

---

### 2.4 `opportunities`

**Owner:** Opportunity / phase-1 logging paths.  
**Population:** opportunity rows (run_header rows skipped on project).  
**Sample evidence:** `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl` (+ `.parquet` / manifest).

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| timestamp | opportunities logger | opportunities | EXACT_MATCH | false | false|Opportunity timestamp; cross-family HOMONYM |
| instrument | opportunities logger | opportunities | EXACT_MATCH | false | false|Instrument; cross-family join geography |
| direction | opportunities logger | opportunities | EXACT_MATCH | true | true|Long/short (or equiv.) direction |
| entry | opportunities logger | opportunities | EXACT_MATCH | true | true|Entry price |
| sl | opportunities logger | opportunities | EXACT_MATCH | true | true|Stop loss |
| tp | opportunities logger | opportunities | EXACT_MATCH | true | true|Take profit |
| outcome | opportunities logger | opportunities | EXACT_MATCH | false | false|Realized outcome label |
| rr_achieved | opportunities logger | opportunities | EXACT_MATCH | true | true|Realized R multiple |
| duration_candles | opportunities logger | opportunities | EXACT_MATCH | true | true|Holding duration in candles |
| mfe | opportunities logger | opportunities | EXACT_MATCH | true | true|Max favorable excursion |
| mae | opportunities logger | opportunities | EXACT_MATCH | true | true|Max adverse excursion |
| features | opportunities logger | opportunities | EXACT_MATCH | true | true|Nested feature bag (flattened on Parquet); **kind-specific / nested feature names omitted** unless identity/decision collision (`momentum_score` lives inside bag — HOMONYM vs telemetry `score*` if promoted bare) |

**Row count (this inventory):** 12 top-level (feature children omitted per huge-family rule).

---

### 2.5 `clean_labels`

**Owner:** Clean-label pipeline under `results/clean_labels/`.  
**Population:** labeled decision units (`unit_id`) for research / training.  
**Sample evidence:** `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl` + parquet manifest.

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| unit_id | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Stable labeled-unit identity |
| instrument | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Instrument geography |
| decision_ts | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Timestamp of the **label decision unit** — HOMONYM vs DE `decision` / Policy decision verbs if bare token `decision` is assumed |
| entry_index | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Entry bar index |
| side | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Trade side |
| entry | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Entry price |
| sl | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Stop loss |
| tp1 | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Take-profit 1 |
| tp2 | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Take-profit 2 (nullable / policy-driven) |
| tp2_policy | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Policy id governing TP2 |
| tp2_stretch_r | clean_labels builder | clean_labels | EXACT_MATCH | true | true|TP2 stretch in R |
| tp1_reward_mult | clean_labels builder | clean_labels | EXACT_MATCH | true | true|TP1 reward multiple |
| risk_distance | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Risk distance entry→SL |
| features | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Nested/flattened feature bag (38 children in sample); nested omitted unless collision |
| feature_vector | clean_labels builder | clean_labels | EXACT_MATCH | true | true|Dense vector aligned to feature order |
| y_tp1 | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Label: hit TP1 |
| y_tp2 | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Label: hit TP2 |
| y_survives_be | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Label: survives breakeven |
| y_R_net | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Net R label |
| y_mfe_r | clean_labels builder | clean_labels | EXACT_MATCH | false | false|MFE in R |
| y_mae_r_heat | clean_labels builder | clean_labels | EXACT_MATCH | false | false|MAE heat in R |
| y_holding_bars | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Holding bars |
| y_time_to_mfe | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Bars to MFE |
| y_time_to_1r | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Bars to 1R |
| y_expired_timeout | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Timeout expiry flag |
| y_reached_0_5r | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Reached 0.5R |
| y_reached_1r_horizon | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Reached 1R in horizon |
| y_reached_2r_horizon | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Reached 2R in horizon |
| path_mfe_r | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Path MFE in R |
| path_mae_r_heat | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Path MAE heat |
| path_outcome | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Path outcome enum/string |
| path_time_to_tp | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Path time to TP |
| path_time_to_failure | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Path time to failure |
| diagnostics | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Nested diagnostics bag |
| provenance | clean_labels builder | clean_labels | EXACT_MATCH | false | false|Nested provenance bag (protocol/hash/pit/exit_model/…) |

**Collision watch inside `features` (not promoted as registry rows):** `momentum_score`, `break_of_structure`, `liquidity_sweep`, `session`, `trend_bias` — HOMONYM vs bar_structure / telemetry / opportunities if selected as bare SQL columns without family prefix.

**Legacy naming (GT-1):** `tp2_surrogate_r` (observed only in the earliest `results/clean_labels/BNBUSDT/20260721T221711Z/` corpus, value `2.0`) is the **legacy name of canonical `tp2_stretch_r`** (current builder emits `tp2_stretch_r = TP2_ATR_MULT`). They are mutually exclusive names of the same concept across corpus protocol versions — treat as a near-HOMONYM / alias, **not** a distinct row.

**Absent:** bare `confidence`, `approve`, `execute`, `reject`, `producer_id`, `emitted_by`, `state*`.

**Row count (this inventory):** 35.

---

### 2.6 `bar_structure`

**Owner:** emitter `runtime.bar_structure_snapshot` (`src/runtime/bar_structure_snapshot.py`).  
**Population:** per-bar structure + engine CRT snapshot (engine stratum).  
**Partition (Parquet):** `crt_state_after` (see `logs/bar_structure/`).  
**Sample evidence:** `logs/dual_construction_v2_envelope_safe/XAUUSD_bar_structure.jsonl`.

| field_name | owner | family | classification | recomputable | canonical_definition |
|------------|-------|--------|----------------|--------------|----------------------|
| schema_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Snapshot schema version |
| run_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Run identity |
| instrument | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Instrument geography |
| timeframe | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Timeframe geography |
| corpus_path | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Corpus path |
| corpus_sha256 | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Corpus pin |
| config_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Config version |
| config_hash | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Config hash |
| feature_schema_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Feature schema version |
| feature_schema_hash | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Feature schema hash |
| bar_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Bar index |
| engine_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Engine candle index (nullable in warmup) |
| timestamp | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Bar timestamp |
| timestamp_basis | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Timestamp basis declaration |
| htf_candle_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|HTF candle id when known |
| emitted_by | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Literal `runtime.bar_structure_snapshot` |
| phase | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Emission phase |
| open | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|OHLC open |
| high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|OHLC high |
| low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|OHLC low |
| close | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|OHLC close |
| volume | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Volume |
| atr_abs | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Absolute ATR |
| crt_state_before | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Engine CRT state before bar |
| crt_state_after | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Engine CRT state after bar; **partition key**; SAFE_ALIAS to construction `engine_state_after` **only** with producer=engine explicit |
| crt_state_changed | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Whether CRT state changed this bar |
| crt_action | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|CRT action |
| crt_reject_reason | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|CRT reject reason |
| crt_direction | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|CRT direction |
| crt_range_h_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Range high reference |
| crt_range_l_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Range low reference |
| crt_range_size | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Range size |
| crt_range_session | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Session tag for range; not proven ≡ Context `session_id` |
| crt_range_htf_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|HTF id for range |
| crt_sweep_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Sweep price |
| crt_sweep_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Sweep candle index |
| crt_sweep_double_confirmed | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Double-sweep confirmation flag |
| crt_displacement_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Displacement candle index |
| crt_retest_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Retest candle index |
| crt_pending_displacement_ttl | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Pending displacement TTL |
| crt_htf_remaining_candles | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Remaining HTF candles |
| crt_evaluating_soft_conf | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Soft-conf evaluation flag |
| crt_trade_open | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Whether CRT trade is open |
| parent_timeframe | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Parent TF id |
| parent_enabled | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Parent feed enabled |
| parent_crt_state | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent CRT state (parent population — HOMONYM vs child `crt_state_after` if collapsed) |
| parent_bias | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent bias |
| parent_range_h_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent range high |
| parent_range_l_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent range low |
| parent_closed_this_bar | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent closed this bar |
| parent_last_close_ts | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Parent last close timestamp |
| htf_state | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|HTF state label; HOMONYM vs other `*state*` |
| htf_range_ratio | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|HTF range ratio |
| objective_status | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Objective status |
| objective_direction | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Objective direction |
| objective_target | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Objective target |
| objective_invalidate_at | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Objective invalidation level/time |
| htf_thresholds | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|HTF thresholds payload |
| objective_gate_enabled | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Objective gate enabled |
| objective_gate_mode | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Objective gate mode |
| smc_window_len | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|SMC window length |
| smc_max_window | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|SMC max window |
| smc_swing_window | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|SMC swing window |
| fvg_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG presence |
| fvg_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG bullish polarity |
| fvg_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG high |
| fvg_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG low |
| fvg_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG mid |
| fvg_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG formed index |
| fvg_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG age |
| fvg_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG width in ATR |
| fvg_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Price inside FVG |
| fvg_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to FVG |
| fvg_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|FVG window truncated |
| order_block_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block presence |
| order_block_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block bullish polarity |
| order_block_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block high |
| order_block_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block low |
| order_block_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block mid |
| order_block_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block formed index |
| order_block_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block age |
| order_block_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block width in ATR |
| order_block_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Price inside Order block |
| order_block_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to Order block |
| order_block_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Order block window truncated |
| breaker_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker presence |
| breaker_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker bullish polarity |
| breaker_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker high |
| breaker_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker low |
| breaker_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker mid |
| breaker_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker formed index |
| breaker_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker age |
| breaker_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker width in ATR |
| breaker_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Price inside Breaker |
| breaker_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to Breaker |
| breaker_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Breaker window truncated |
| mitigation_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation presence |
| mitigation_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation bullish polarity |
| mitigation_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation high |
| mitigation_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation low |
| mitigation_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation mid |
| mitigation_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation formed index |
| mitigation_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation age |
| mitigation_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation width in ATR |
| mitigation_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Price inside Mitigation |
| mitigation_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to Mitigation |
| mitigation_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Mitigation window truncated |
| pdh_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Prior day high present |
| pdh_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|PDH price |
| pdh_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to PDH |
| pdl_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Prior day low present |
| pdl_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|PDL price |
| pdl_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to PDL |
| pdh_pdl_day_ts | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | false|Day timestamp for PDH/PDL |
| eqh_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|EQH present |
| eqh_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to EQH |
| eql_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|EQL present |
| eql_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Distance to EQL |
| choch_value | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|CHoCH numeric/value (not boolean `choch_present`) |
| choch_basis | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|CHoCH basis |
| break_of_structure | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|BOS as float/metric — HOMONYM vs clean_labels/opportunities feature `break_of_structure` if co-selected bare |
| trend_bias | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | true|Trend bias; HOMONYM vs feature-bag `trend_bias` |

**Row count (this inventory):** 122.

#### bar_structure: identity vs annotation hints (D3-light)

Descriptive only — **not** Market Ontology v2.

| Hint | Columns (examples) | `recomputable` stance |
|------|--------------------|------------------------|
| **Observational / run identity** | `bar_index`, `engine_candle_index`, `timestamp`, `timestamp_basis`, `htf_candle_id`, `run_id`, corpus/config/schema pins, `emitted_by`, `phase`, `pdh_pdl_day_ts` | **false** |
| **Config / gate pins** | `parent_timeframe`, `parent_enabled`, `smc_window_*`, `objective_gate_*` | **false** |
| **Market observation (from corpus)** | `open`/`high`/`low`/`close`/`volume`/`atr_abs` | **true** (snapshot owner regenerates from bars) |
| **Engine / parent / HTF / objective state** | `crt_*`, `parent_crt_state`, `parent_bias`, `parent_range_*`, `htf_state`, `objective_*` (status/direction/target) | **true** |
| **Derived structure annotations** | `fvg_*`, `order_block_*`, `breaker_*`, `mitigation_*`, `pdh_*`/`pdl_*` (except day_ts), `eqh_*`/`eql_*`, `choch_*`, `break_of_structure`, `trend_bias` | **true** (structure predicates from bars/config) |

Formation indices (`*_formed_at_index`) are treated as **annotation** (true), not as run join keys like `bar_index` (false).

---

## 3. Cross-family HOMONYM / PROHIBITED tripwires

| Token / pair | Families | Classification | Rule |
|--------------|----------|----------------|------|
| bare `state` | *(none as column)* | **PROHIBITED_ALIAS** as global synonym | Must not silently mean `engine_state_after` **or** `ontology_state` **or** `crt_state_after` |
| `engine_state_after` ↔ `crt_state_after` | crt_construction ↔ bar_structure | **SAFE_ALIAS** only if producer=engine explicit + gate | Same engine population; different physical names |
| `engine_state_after` / `crt_state_after` ↔ `ontology_state` | crt_construction | **HOMONYM** (two populations) | Engine vs resolver labels on same row |
| `parent_crt_state` ↔ `crt_state_after` | bar_structure | **HOMONYM** if collapsed | Parent vs child TF populations |
| `htf_state` ↔ any CRT state column | bar_structure vs construction/events/telemetry | **HOMONYM** | HTF stratum ≠ execution CRT state |
| `from_state`/`to_state` ↔ `state_from`/`state_to` | crt_telemetry ↔ events | **HOMONYM** (naming) | Similar transition idea; different owners/schemas — qualify in joins |
| `producer_id` ↔ `state_producer` | crt_construction vs design Identity | **PROHIBITED_ALIAS** | Envelope id ≠ D2 producer enum (`engine`\|`resolver`) |
| bare `confidence` | *(not an analytics column today)*; DE float vs future ODP enum | **HOMONYM / PROHIBITED** same-name semantics | Prefer future names `decision_confidence` / `odp_confidence` — never bare `confidence` in co-projected stores |
| `score` / `score_actual` / `would_expand_score` / `max_score_seen` / `score_at_approval` / feature `momentum_score` | crt_telemetry (+ feature bags) | **HOMONYM** if treated as one field | Keep kind- and owner-qualified |
| `decision_distance` vs `decision_ts` vs DE `decision` | telemetry / clean_labels / DE | **HOMONYM** on stem `decision*` | Different rights: metric vs label timestamp vs execute/reject verb |
| `reject_reason` ↔ `rejection_reason` ↔ `crt_reject_reason` | telemetry / bar_structure | **HOMONYM** (near-names) | Do not UNION without owner qualification |
| `intent` (telemetry) ↔ Policy `intent_stance` | crt_telemetry vs Policy design | **HOMONYM** | Different decision rights |
| `instrument` / `timestamp` / `direction` | many families | Join geography **EXACT_MATCH** within a pinned run; **HOMONYM** across unrelated populations if co-projected blindly | Always carry `run_id` / family |

---

## 4. Explicit rules (normative-adjacent)

1. **No global `state` alias.** Inability to query bare `state` without `state_producer` (design) is a **feature**. Future projections: `state_producer`+`state`, or distinct `context_state_engine` / `context_state_resolver`.
2. **Preferred future confidence names:** `decision_confidence` (DE float belief) and `odp_confidence` (ODP categorical sample strength). Bare `confidence` is forbidden in shared DuckDB namespaces.
3. **`producer_id` ≠ `state_producer`.** Queries on `producer_id` do **not** satisfy D2 population identity.
4. **SAFE_ALIAS** across `engine_state_after` ↔ `crt_state_after` requires the five-question gate **and** explicit engine producer.
5. This registry inventories **existing** columns only. Design fields that are not columns belong in §5 Tripwires — researchers must not invent them as DuckDB columns.

---

## 5. Tripwires / non-columns (do not invent as analytics columns)

| Name | Why listed | Notes |
|------|------------|-------|
| bare `state` | Design Context identity; **not** a Trace column | PROHIBITED as silent synonym |
| `state_producer` | Required Context identity (`engine`\|`resolver`); **absent** from Trace | NEW when introduced under this exact name; never alias from `producer_id` |
| `variant_id` | Context identity; **absent** | NEW if persisted |
| `htf_bucket` | Context selector; **absent** as that name | Do not invent from `htf_state` / ratios |
| `choch_present` | Design boolean; analytics has `choch_value` | Type rule required before SAFE_ALIAS |
| `liquidity_sweep_direction` | Design enum; analytics has float `liquidity_sweep` in feature bags | Not a Trace column under this name |
| `session_id` | Design location id; analytics has `crt_range_session` / feature `session` | Not proven identity-equivalent |
| ODP `confidence` enum | Design measurement; **not** Trace | Collides with DE float `confidence` |
| DE `decision` / `execute` / `reject` / `approve` / float `confidence` | Live DecisionEngine module terms | Mostly **not** Trace family columns; must not be projected as Policy native fields; if ever co-located, use fully-qualified names |

---

## 6. Open question — answer from this inventory

**Can every DuckDB-exposed column be traced to exactly one owner and one population?**

| Claim | Verdict |
|-------|---------|
| One **owner** (emitter / writer) per column **within a family** | **Mostly yes** for listed key columns — each row above names a single owner |
| One **population** per column **across the analytics namespace** | **No — not yet** |

### Columns / stems that fail “exactly one population” (or one unambiguous namespace meaning)

1. **CRT state cluster:** `engine_state_after`, `engine.crt_state`, `crt_state_after`, `ontology_state`, `parent_crt_state`, `htf_state`, events `state_from`/`state_to`, telemetry `from_state`/`to_state` — multiple populations (engine / resolver / parent / HTF / event-transition / telemetry-transition).  
2. **`producer_id`:** one owner, but **identity-misleading** relative to D2 `state_producer` (tripwire).  
3. **`score*` cluster:** multiple kind-local scores under one family name stem.  
4. **`decision*` stem:** `decision_distance` (telemetry metric) vs `decision_ts` (label time) vs future/live DE `decision`.  
5. **Shared geography names** (`instrument`, `timestamp`, `direction`) — one meaning only inside a pinned run+family; ambiguous if naively UNION ALL’d.  
6. **Structure/feature overlaps** when feature bags flatten beside `bar_structure` (`break_of_structure`, `trend_bias`, …).

**Therefore:** the Trace layer can answer joins for **measurement**, but cannot yet host Context/ODP identity without aliases or translation — consistent with `ANALYTICS_VOCABULARY_ALIGNMENT.md` (“partial, leaning no”).

---

## 7. Inventory counts (this revision)

| Family | Rows | recomputable=true | recomputable=false |
|--------|------|-------------------|--------------------|
| crt_construction | 34 | 18 | 16 |
| crt_telemetry | 56 | 47 | 9 |
| events | 9 | 5 | 4 |
| opportunities | 12 | 9 | 3 |
| clean_labels | 35 | 10 | 25 |
| bar_structure | 122 | 97 | 25 |
| **Total listed** | **268** | **186** | **82** |

Every registry data row carries `recomputable` (`true`\|`false`). Column order: `field_name | owner | family | classification | recomputable | canonical_definition`.

Evidence refreshed 2026-09-06 from live JSONL/manifests + emitters + `FAMILY_GLOBS`. Provisional — update when emitters add columns; do not treat as frozen aliases.
