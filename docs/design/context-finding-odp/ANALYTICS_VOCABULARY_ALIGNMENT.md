# Analytics Vocabulary Alignment Audit

**Status:** design-only, **provisional** (successor to D2: D2 = what population; this = what name).
**Governance symbol table:** `docs/governance/ANALYTICS_SCHEMA_REGISTRY.md` (provisional inventory of existing DuckDB analytics columns; not a frozen Alias Register).
**Phase 4 Lineage registry:** `docs/governance/ANALYTICS_LINEAGE_REGISTRY.md` (descriptive origin for each registry field; companion join on field_name+family; not attribution).

**Alias Register:** NOT normative yet — vocabulary doctrine only; do not freeze aliases into code or schemas.  
**Date:** 2026-09-06  
**Scope:** Naming alignment only. No code changes, no new Parquet/DuckDB families/views, no new YAML schemas, no runtime ownership changes.  
**One question:** If Context, ODP, and PolicyOpinion were persisted tomorrow, could they be queried through the existing Trace → Parquet → DuckDB layer without inventing aliases, duplicate columns, or translation logic?

**Answer: partial (leaning no).** Several Context identity selectors already circulate under *different* canonical analytics names (`engine_state_after`, `parent_crt_state`, `objective_status`, …). Several required Context identity fields (`state_producer`, `variant_id`, `htf_bucket`, `choch_present`, `liquidity_sweep_direction`, …) have **no** existing column. ODP `confidence` / Policy decision-adjacent names collide with live DecisionEngine vocabulary. Direct same-name DuckDB joins are therefore not possible without aliases or translation.

Evidence bases (read, not modified):
- `scripts/analysis/query_trace.py` `FAMILY_GLOBS`
- `scripts/maintenance/jsonl_to_parquet.py` `FAMILY_DEFAULTS`
- `src/runtime/crt_construction_trace.py` (emitted fields; sample LIVE row)
- `docs/reference/schemas.md` §9.17
- Sample JSONL: `logs/dual_construction_v2_envelope_safe/XAUUSD_crt_construction.jsonl`, sibling `XAUUSD_bar_structure.jsonl`, plus family samples under `logs/` / `results/`
- Design: `schemas/context.schema.yaml`, `schemas/odp.schema.yaml`, `POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md`

---

## 0. Layer separation (must remain separable)

| Layer | Purpose | Examples |
|-------|---------|----------|
| **Identity** | What population is being discussed | `state_producer`, `variant_id`, `state`, structure selectors |
| **Measurement** | How observations are stored and queried | `engine_state_after`, `ontology_state`, Parquet columns |
| **Decision** | How opinions are applied | `participation_stance`, `risk_stance`, `ABSTAIN` |

The findings below are valuable because they expose where these layers still leak into each other.

## 1. Current Analytics Vocabulary

Inventory of families registered in `FAMILY_GLOBS` / `FAMILY_DEFAULTS` today. Column lists are **key/canonical fields** (not exhaustive for huge families); `crt_construction` is listed thoroughly as the join spine. Real sample columns preferred over guesses.

| Family | Columns (key/canonical names) | Owner |
|--------|-------------------------------|-------|
| **crt_construction** | **Identity:** `schema_version`, `run_id`, `instrument`, `timeframe`, `corpus_path`, `corpus_sha256`, `config_version`, `config_hash`, `ontology_source`, `ontology_version`, `bar_index`, `timestamp`, `emitted_by`, `phase`. **Engine spine:** `engine_state_before`, `engine_state_after`, `engine_action`, `engine_reason`, `engine_gates`, `engine.crt_state`, `engine.transitions`, `engine.live_context` (nested: `cached_double_sweep`, `cached_session`, …). **Resolver spine:** `ontology_state`, `agree`, `divergence_pair`, `agree_scope`, `resolver.feature_vector`, `resolver.l2_map`, `resolver.predicate_affinity`, `resolver.continuous_passed`, `resolver.projected_site`, `resolver.supply_ok`, `resolver.missing_when`, `producer_id` (literal `resolver_engine_v1`). Partition key: `engine_state_after`. | Emitter `src/runtime/crt_construction_trace.py` (`TRACE_OBSERVATION_JOIN`); Parquet via `jsonl_to_parquet.py`; query via `query_trace.py` / DuckDB `open_views`. JSONL SoR; §9.17 notes measured columns TBD / no production `enabled:true` yet — research samples exist. |
| **crt_telemetry** | Partition/discriminant: `kind`. Kind-specific keys include: `TRANSITION_COUNTER` → `state_entry_counts`, `expansion_dwell_stats`; `DECISION_DISTANCE` → `score_actual`, `score_threshold`, `decision_distance`, `accepted`, `rejection_reason`; `CANDIDATE_LIFECYCLE` → `score_at_approval`, `max_score_seen`; `RETEST_REPLAY` → `score`, `intent`, `reject_reason`; `RESET_ATTRIBUTED` → `from_state`, `to_state`, `would_expand_score`; `EXPANSION_RETRACE_CHECK` → episode/retrace metrics. | CRT runtime telemetry writers (run results); family default partition `kind`. |
| **events** | Canonical: `event`, `timestamp`, `candle_index`, `state_from`, `state_to`, `direction`, `price`, `reason`, `metadata`. Event values observed: `RESET`, `STATE_TRANSITION`, `SWEEP`, `BEGIN_SOFT_CONF`, `FILTER_REJECTED`, …. Partition default: `event`. | Engine/runtime event JSONL (`*_events.jsonl`). |
| **opportunities** | `timestamp`, `instrument`, `direction`, `entry`, `sl`, `tp`, `outcome`, `rr_achieved`, `duration_candles`, `mfe`, `mae`, `features` (+ run_header rows skipped on project). | Opportunity / phase-1 logging paths. |
| **clean_labels** | `unit_id`, `instrument`, `decision_ts`, `entry_index`, `side`, `entry`, `sl`, `tp1`, `tp2`, …, `features`/`feature_vector`, label `y_*`, path metrics, `diagnostics`, `provenance`. | Clean-label pipeline under `results/clean_labels/`. |
| **bar_structure** | **Join/id:** `run_id`, `instrument`, `timeframe`, `bar_index`, `timestamp`, `phase`, hashes/versions. **Engine CRT:** `crt_state_before`, `crt_state_after`, `crt_action`, `crt_direction`, range/sweep/retest fields. **L1/L2:** `parent_crt_state`, `parent_bias`, `htf_state`, `htf_range_ratio`, `objective_status`, `objective_direction`, `objective_target`, …. **L4 atoms (booleans/floats):** `breaker_present`, `order_block_present`, `fvg_present`, `mitigation_present`, `choch_value`, `choch_basis`, `break_of_structure` (float), distances, PDH/PDL/EQH/EQL, `crt_range_session`, …. Partition key: `crt_state_after`. | Emitter `src/runtime/bar_structure_snapshot.py`; Parquet partitions present under `logs/bar_structure/`. |

### Canonical names already in circulation (analytics layer)

These names are the ones DuckDB/`query_trace` already group and join on today:

- **Execution CRT state (engine):** `engine_state_after` (crt_construction partition + default report), also `engine.crt_state`; bar_structure twin: `crt_state_after`.
- **Resolver label:** `ontology_state` (not named `state`).
- **Parent CRT:** `parent_crt_state` (bar_structure).
- **Objective / HTF:** `objective_status`, `objective_direction`, `htf_state`.
- **Structure presence (flat):** `breaker_present`, `order_block_present`.
- **Geography:** `instrument`, `timeframe`; session-ish: `crt_range_session` / feature `session` — **not** `session_id` / `htf_bucket`.
- **Producer-ish (not D2 producer):** `producer_id` = envelope id string, always `resolver_engine_v1` in sample — **not** Context `state_producer`.
- **DecisionEngine-adjacent (telemetry / DE module):** `score`, `p_win`, `confidence` (float), `decision` ∈ {`execute`,…}, `reject_stage`, `approve`-adjacent (`score_at_approval`).

No family today is named `context`, `odp`, or `policy_opinion`. No `crt_construction` Parquet projection was found on disk at audit time (JSONL samples exist); bar_structure Parquet partitions do exist.

---

## 2. Projected Context Vocabulary

Map from `context.schema.yaml` (esp. `identity_selector_fields`) → existing analytics columns. Nested Context paths are shown as schema field names.

| Context Field | Existing Column? | Alias Needed? |
|---------------|------------------|---------------|
| `state_producer` | **none / NEW** (no `state_producer` column; dual spines exist as parallel columns, not a producer enum). Closest non-equivalent: `producer_id` | **Yes** — and must **not** alias to `producer_id` (different meaning) |
| `variant_id` | **none / NEW** | **Yes** (new column) |
| `state` | **No exact name.** Closest: `engine_state_after` / `engine.crt_state` (engine); `ontology_state` (resolver); `crt_state_after` (bar_structure) | **Yes** — collision class: bare `state` vs `engine_state_after` |
| `parent_crt` | Near: `parent_crt_state` (bar_structure) | **Yes** (`parent_crt` ≠ `parent_crt_state`) |
| `objective.status` | Near: `objective_status` | **Yes** (nested vs flat) |
| `objective.direction` | Near: `objective_direction` | **Yes** |
| `objective.htf_state` | Near: `htf_state` | **Yes** (path vs flat; same token `htf_state` at leaf) |
| `structure.breaker_present` | **Yes** leaf: `breaker_present` (bar_structure) | Path flatten only; leaf CANONICAL |
| `structure.order_block_present` | **Yes** leaf: `order_block_present` | Path flatten only; leaf CANONICAL |
| `structure.double_sweep` | **Partial / fragmented:** `engine.live_context.cached_double_sweep`; `resolver.l2_map.double_sweep` / feature float; `crt_sweep_double_confirmed` — no single top-level boolean `double_sweep` on bar_structure sample | **Yes** (pick one spine or NEW) |
| `structure.liquidity_sweep_direction` | **none / NEW** (have `liquidity_sweep` float / `sweep_detected`, not signed direction enum) | **Yes** |
| `structure.break_of_structure_present` | Near: `break_of_structure` (float 0/1), not `*_present` boolean name | **Yes** |
| `structure.choch_present` | Near: `choch_value` (float) + `choch_basis`; **not** `choch_present` | **Yes** |
| `transition.from_state` | Near: `engine_state_before` / events `state_from` | **Yes** |
| `transition.to_state` | Near: `engine_state_after` / events `state_to` | **Yes** (and overlaps state spine) |
| `transition.edge_id` | **none / NEW** | **Yes** |
| `location.instrument` | **Yes:** `instrument` | No (leaf CANONICAL) |
| `location.timeframe` | **Yes:** `timeframe` | No (leaf CANONICAL) |
| `location.htf_bucket` | **none / NEW** (have `htf_state`, `htf_range_ratio`, distances — no `lower_third|middle_third|upper_third` column) | **Yes** |
| `location.session_id` | **none / NEW** (near: `crt_range_session`, feature `session`) | **Yes** |
| Non-identity (ref): `location.htf_percentile`, `distance_to_boundary_atr` | **none / NEW** as those names (distances exist under other names) | N/A for identity; still NEW if persisted as Context measurement |
| Non-identity: `mechanism`, `mechanism_confidence`, `resolver_state` | **none** as Context fields; resolver label exists as `ontology_state` | Do not alias `resolver_state`→`ontology_state` without doctrine note |

### Collision highlights

- **`state` vs `engine_state_after`:** Context requires a field literally named `state`; analytics canonical engine stratum is `engine_state_after` (also `crt_state_after` on bar_structure). Persisting Context.`state` beside Trace would duplicate meaning under a new name unless Trace columns are renamed (out of scope) or Context adopts the analytics name.
- **`state_producer`:** Required identity; absent from Trace. Dual columns do not encode the enum.
- **`variant_id`:** Absent; resolver populations cannot be keyed in DuckDB today.
- **`htf_bucket`:** Absent; cannot select Context location bucket without NEW column or derived translation.
- **`producer_id` trap:** Existing column name looks “producer-like” but is envelope id, not D2 `state_producer`.

---

## 3. Projected ODP Vocabulary

From `odp.schema.yaml` vs existing analytics names.

| ODP Field | Existing Column? | Alias Needed? |
|-----------|------------------|---------------|
| `id` (`ODP-*`) | **none / NEW** (no `odp_id` / `id` ODP family) | **Yes** (new); suggest distinct physical name `odp_id` if co-located with other `id`s |
| `finding_id` | **none / NEW** in Trace families | **Yes** |
| `contract_ref` | **none / NEW** | **Yes** |
| `condition` (Context object) | **none** as nested object column; selectors must map per §2 | **Yes** (compose from Trace columns + NEW fields) |
| `lookahead_bars` | **none / NEW** as ODP field (holding-bar labels exist under other names in clean_labels) | **Yes** |
| `outcome_metric` | **none / NEW** | **Yes** |
| `quantiles` (`p5`…`p95`) | **none / NEW** as ODP quantile object (MFE/MAE etc. are different metrics) | **Yes** |
| `n` | **none** as ODP sample-size column (ad-hoc SQL `count(*) as n` only) | **Yes** if persisted; avoid colliding with query aliases |
| `confidence` (enum: survivor\|confirmed\|provisional\|thin\|none) | **Name collision:** DecisionEngine output field `confidence` is a **float** (from `p_win`); not the ODP enum. No ODP confidence column exists. | **Yes** — same token, different type/meaning → PROHIBITED to reuse bare `confidence` without qualifier |
| `measurement_period`, `corpus_pin` | Near: `corpus_sha256` / run identity — not same names | **Yes** |
| `mechanism` / `mechanism_confidence` | **none** in Trace as those names | **Yes** if stored; excluded from identity |
| Identity selectors inside `condition` | Same gaps as §2 | Same as §2 |

ODP does **not** currently fit an existing `FAMILY_GLOBS` family; vocabulary question is still: can its fields share names with the Trace spine without translation? **No** for `contract_ref`, `quantiles`, sample `confidence`, and Context.`state` binding.

---

## 4. Projected Policy Vocabulary

From `POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md` vs DecisionEngine / analytics terms.

| PolicyOpinion Field | Existing DE / analytics term? | Collision? |
|---------------------|-------------------------------|------------|
| `participation_stance` | **No** DE twin | Clean (chosen stance) |
| `risk_stance` | **No** DE twin | Clean |
| `intent_stance` | Near Planner `intent` / telemetry `intent` — different role | Low if kept `*_stance` suffix |
| `on_odp_fallback` | **NEW** | None with DE |
| `contract_ref`, `odp_ref`, `context_selector` | **NEW** at Policy layer | Share names with ODP/Context by design |
| `size_hint_mult`, `risk_percent_override` | Map to Ultron sockets; not Trace columns | OK as Policy-only |
| `measured_fields: {}` | Must stay empty | — |

### DecisionEngine terms that Policy must **not** reuse as native fields

Observed in `src/core/decision_engine.py` / telemetry:

| DE / live term | Policy stance (contract) |
|----------------|--------------------------|
| `decision` / `execute` / `reject` | Forbidden on PolicyOpinion; owners emit these |
| `approve` / Ultron approve path | Forbidden |
| `confidence` (float) | Forbidden as Policy/ODP overload without rename |
| `score` / `p_win` / `normalized_score` | Forbidden; adapters must not write these as measured |
| `reject_stage` | Owner-only |

Contract already channels Policy through `participation_stance` / `risk_stance` / `intent_stance` — **good separation**. Residual risk is **shared DuckDB column namespace** if Policy rows are projected beside DE/telemetry using bare `confidence` / `score` / `decision`.

---

## 5. Vocabulary classification doctrine

Reusable review tool for future Parquet families, DuckDB views, Context projections, ODP tables, and PolicyOpinion adapters. **Not a frozen Alias Register.**

| Status | Meaning |
|--------|---------|
| **EXACT_MATCH** | Same concept, same owner — same physical name may be used |
| **SAFE_ALIAS** | Different name, same concept — mapping allowed if owner-preserving and producer-explicit |
| **HOMONYM** | Same name, different concept — must not be treated as one field; require fully-qualified names when co-queried |
| **PROHIBITED_ALIAS** | Mapping destroys identity or ownership (e.g. erases D2 producer distinction) |


### SAFE_ALIAS gate (analytics-family drift)

For every field that crosses JSONL emitter -> Parquet projection -> DuckDB view -> Context/ODP research query, ask all five:

1. Same owner?
2. Same population?
3. Same cardinality?
4. Same measurement meaning?
5. Same decision rights?

Only if **all five** are true may a field reach **SAFE_ALIAS**.
Everything else remains **HOMONYM** or **PROHIBITED_ALIAS**.

This is the next failure mode to watch: not Context/ODP schema drift (largely closed by D2), but analytics-family drift across the measurement spine.

### Normative-adjacent governance rules (vocabulary, not implementation)

1. **No safe global alias for Context `state`.** Mapping `state` to `engine_state_after` erases D2 in one direction; mapping to `ontology_state` erases it in the other. Bare `state` as a silent synonym is **PROHIBITED_ALIAS**. Inability to query a bare `state` without `state_producer` is a **feature**, not a defect. Future analytics projections must keep producer explicit: either `state_producer` + `state`, or distinct columns such as `context_state_engine` / `context_state_resolver`.

2. **PROHIBITED_ALIAS: `state_producer` <-> `producer_id`.** `producer_id` is Trace provenance (envelope id). `state_producer` is population identity (`engine` | `resolver`). Different ontologies. A DuckDB query on `producer_id` does **not** satisfy D2.

3. **HOMONYM / FORBIDDEN SAME-NAME SEMANTICS: ODP `confidence` vs DecisionEngine `confidence`.** Categorical sample strength is not float belief. When both appear in one query or co-projected store, require fully-qualified names: `odp_confidence`, `decision_confidence` — never bare `confidence`.

## 6. Alias Register (provisional — not normative)

Explicit pairs for review only. Classifications use section 5 doctrine. Do **not** treat this table as a schema contract.

| Design / proposed name | Analytics / live name | Classification |
|------------------------|----------------------|----------------|
| Context `state` (engine stratum) | `engine_state_after` / `engine.crt_state` | SAFE_ALIAS only when `state_producer=engine` is explicit |
| Context `state` with bar_structure | `crt_state_after` | SAFE_ALIAS (family-local), producer must remain engine |
| Context `state` (resolver stratum) | `ontology_state` | SAFE_ALIAS only when `state_producer=resolver` is explicit |
| bare `state` as global synonym for any of the above | — | **PROHIBITED_ALIAS** (erases D2) |
| `state_producer` | *(none today)* | NEW identity field; EXACT_MATCH when introduced under this name |
| `state_producer` <-> `producer_id` | Trace envelope id | **PROHIBITED_ALIAS** (governance tripwire) |
| `variant_id` | *(none)* | NEW identity field |
| `parent_crt` | `parent_crt_state` | SAFE_ALIAS |
| `objective.status` / `.direction` / `.htf_state` | `objective_status` / `objective_direction` / `htf_state` | SAFE_ALIAS (nesting shape differs) |
| `structure.breaker_present` / `order_block_present` | same leaf names | EXACT_MATCH |
| `structure.choch_present` / `break_of_structure_present` | `choch_value` / `break_of_structure` | SAFE_ALIAS at best (boolean vs float — not equivalent without a rule) |
| `structure.double_sweep` | fragmented cached/resolver/crt_* names | SAFE_ALIAS only after one CANONICAL is chosen; silent equate PROHIBITED |
| `structure.liquidity_sweep_direction` | *(none)* / float `liquidity_sweep` | NEW or SAFE_ALIAS after type rule; float is not signed direction enum |
| `location.htf_bucket` | *(none)* | NEW |
| `location.session_id` | `crt_range_session` / `session` | SAFE_ALIAS only if proven identity-equivalent (today: not) |
| `location.instrument` / `timeframe` | same | EXACT_MATCH |
| `transition.from_state` / `to_state` | `engine_state_before/after`, `state_from/to` | SAFE_ALIAS (producer-scoped) |
| ODP `confidence` (enum) <-> DE `confidence` (float) | bare `confidence` | **HOMONYM** — FORBIDDEN SAME-NAME; use `odp_confidence` / `decision_confidence` |
| Policy `*_stance` <-> DE `execute`/`approve`/`reject`/`score` | — | **PROHIBITED_ALIAS** (collapse destroys Decision vs Policy layer) |
| `contract_ref` | *(none)* | NEW |

## 7. Drift Findings (classified)

Actual naming / ownership drifts only. IDs `A-###`. Classified into section 5 buckets. No implementation prescriptions.

| ID | Finding | Classification |
|----|---------|----------------|
| **A-001** | **Ownership, not naming.** Context identity field `state` does not exist in analytics; three live measurement names (`engine_state_after`, `crt_state_after`, `ontology_state`) and zero bare `state`. No safe **global** alias — any single mapping erases D2. Bare-state unqueryability without producer is intentional. | **PROHIBITED_ALIAS** (global `state` <-> any one column); SAFE_ALIAS only when producer-qualified |
| **A-002** | Required Context `state_producer` is absent from Trace/Parquet. Dual construction encodes both answers as parallel columns, not as a producer enum. | NEW / identity gap (blocks EXACT_MATCH join today) |
| **A-003** | `producer_id` exists on crt_construction but means resolver-envelope provenance (`resolver_engine_v1`), not population `state_producer`. Six-month DuckDB trap: `SELECT producer_id` does not satisfy D2. | **PROHIBITED_ALIAS** (`state_producer` <-> `producer_id`); also **HOMONYM** on token proximity |
| **A-004** | Required-when-resolver `variant_id` is absent from all inventoried families. | NEW / identity gap |
| **A-005** | Design `parent_crt` vs analytics `parent_crt_state` — same graph, different token. | SAFE_ALIAS |
| **A-006** | Design nested `objective.*` vs flat `objective_status` / `objective_direction` / `htf_state`. | SAFE_ALIAS |
| **A-007** | Design `location.htf_bucket` enum absent; analytics has `htf_state` and continuous HTF ratios/distances only. | NEW (do not silently alias to continuous HTF) |
| **A-008** | Design `structure.choch_present` / `break_of_structure_present` vs analytics `choch_value` / `break_of_structure` floats — name and type drift. | SAFE_ALIAS at best after booleanization rule; else NEW |
| **A-009** | Design `structure.liquidity_sweep_direction` absent; nearest `liquidity_sweep` / `sweep_detected` are not the signed identity selector. | NEW (near-names are not SAFE_ALIAS) |
| **A-010** | `double_sweep` identity fragmented across `cached_double_sweep`, resolver `double_sweep`, and `crt_sweep_double_confirmed`. | SAFE_ALIAS only after CANONICAL pick; silent multi-map **PROHIBITED_ALIAS** |
| **A-011** | ODP `confidence` (categorical sample strength) shares bare token `confidence` with DecisionEngine float `confidence` — type and authority collision if co-projected. | **HOMONYM** / FORBIDDEN SAME-NAME SEMANTICS -> `odp_confidence` / `decision_confidence` |
| **A-012** | ODP `contract_ref`, `quantiles`, sample `n`, and `ODP-*` id have no Trace/Parquet CANONICAL columns today. | NEW |
| **A-013** | Policy stance channel names are clean vs DE, but DE verbs (`execute`/`reject`/`score`/`approve`/`confidence`) remain live in telemetry/DE output — Policy persistence that reuses those tokens would reintroduce the collision stances were designed to avoid. | **PROHIBITED_ALIAS** (stance <-> DE verb collapse); stance names themselves EXACT_MATCH-clean |
| **A-014** | `location.session_id` absent; near-names `crt_range_session` / numeric `session` are not the same identity selector. | NEW (near-names not SAFE_ALIAS today) |
| **A-015** | Family registry (`FAMILY_GLOBS` / `FAMILY_DEFAULTS`) has no Context/ODP/PolicyOpinion family — persistence would be a new family *or* Trace column overload; either path surfaces the alias set above. | Naming observation only (no classification of a field pair) |

### Classification summary

| Bucket | Findings |
|--------|----------|
| EXACT_MATCH (clean today) | leaf `instrument`, `timeframe`, `breaker_present`, `order_block_present`; Policy `*_stance` channel names (vs DE) |
| SAFE_ALIAS | A-005, A-006; producer-qualified state twins under A-001; A-008 only after type rule |
| HOMONYM | A-011 (`confidence`); A-003 proximity trap |
| PROHIBITED_ALIAS | A-001 global bare `state`; A-003 `state_producer`<->`producer_id`; A-010 silent multi-map; A-013 stance<->DE verb |
| NEW / absent | A-002, A-004, A-007, A-009, A-012, A-014 |

## 8. Closing (one question)

**Partial / no:** not without aliases, duplicate columns, or translation logic — and several of those aliases would be **PROHIBITED** because they destroy Identity/Measurement/Decision separation.

Enough leaf names already match that *some* Context selectors could be queried today, but the D2 identity key does **not** line up with Trace CANONICAL vocabulary as spelled. The DuckDB layer did not create that problem; it exposed a missing governed vocabulary boundary between identity fields, measurement fields, and decision fields — before runtime code depended on it.

**Do not freeze section 6 as normative.** The normative artifact is the **classification doctrine** (section 5 + SAFE_ALIAS gate); the alias table is merely today's inventory. Use section 5 when any future Context / ODP / Policy persistence or analytics-family projection is proposed.

---

*End of design-only audit (rev 2.1 — SAFE_ALIAS five-question gate; Alias Register remains non-normative). Uncommitted.*
