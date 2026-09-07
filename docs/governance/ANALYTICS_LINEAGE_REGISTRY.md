# Analytics Lineage Registry (descriptive)

**Status:** design-only, **provisional** (Phase 4 Lineage).  
**Date:** 2026-09-06 (IST)  
**Companion to:** [`ANALYTICS_SCHEMA_REGISTRY.md`](./ANALYTICS_SCHEMA_REGISTRY.md) (joins on `field_name` + `family`; owner carried for identity).  
**Coverage:** 268 rows — 1:1 with the schema registry.  
**Scope:** Descriptive origin lineage for existing DuckDB analytics columns. **Not** a new ontology, schema family, YAML Context/ODP/Policy, decision authority, or Market Ontology v2. No `src/` changes.

---

## Doctrine

- **Lineage answers origin before attribution.** Attribution (edge / causal edge labeling) is **Phase 5** and is **not** ready.
- **Analytics never becomes authority.** This registry does not grant decision rights, freeze aliases, or promote Trace→Parquet→DuckDB columns into Context / ODP / PolicyOpinion.
- **SAFE_ALIAS five-question gate still applies** (same owner, population, cardinality, measurement meaning, decision rights) — see vocabulary doctrine in `docs/design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md` §5 and the schema registry header.
- **Tripwires (do not collapse):**
  - no global state;
  - `producer_id` ≠ Context `state_producer`;
  - DecisionEngine `confidence` / telemetry decision vocabulary ≠ ODP `confidence` (`decision_confidence` vs `odp_confidence`).
- **UNKNOWN policy:** if a lineage cell is not evidenced from emitters / JSONL samples / `FAMILY_DEFAULTS` / `FAMILY_GLOBS`, it is marked **`UNKNOWN` explicitly** — never invented.
- **Evidence class (doctrine — see `docs/design/context-finding-odp/ANALYTICS_LINEAGE_SEMANTICS_DECISION.md` §4):** each row/family is classed `CORPUS_VERIFIED` / `CODE_VERIFIED` / `DECLARED_ONLY`. Only `CORPUS_VERIFIED` with resolved `produced_by` is eligible as attribution input. A row may be `CODE_VERIFIED` (reachable in emitter code) without being `CORPUS_VERIFIED` (observed on disk) — **implemented ≠ observed**.
- **Attribution eligibility (doctrine — decision sheet §5):** `opportunities.outcome` / `rr_achieved` are **NOT attribution-eligible** until an exit/oracle contract (L-003) makes them mean a realized trade. `opportunities.features` / `clean_labels.features` are parent-only; per-field producer unenumerated (GT-4).
- **`consumed_by`:** research tooling / diagnostics only unless a real decision consumer is evidenced. **Do not invent DecisionEngine consumers.**

### Column schema (this companion)

| Column | Role |
|--------|------|
| `field_name` | Identity key (with family) |
| `owner` | Identity / ownership from schema registry |
| `family` | Identity key (with field_name) |
| `classification` | Carry-forward from schema registry |
| `recomputable` | Carry-forward from schema registry |
| `source_jsonl_field` | Physical key as seen in JSONL (or UNKNOWN) |
| `source_jsonl_family` | Path/suffix pattern from `jsonl_to_parquet.FAMILY_DEFAULTS` |
| `parquet_column` | Usually same as field; note nested/dot-path when applicable |
| `duckdb_view` | Family view name from `query_trace.FAMILY_GLOBS` |
| `produced_by` | Emitter module / write site (evidence-based) |
| `consumed_by` | Research/diagnostics only unless evidenced otherwise |

**Why companion (not in-place):** adding six lineage columns to the existing six-column symbol table would make the primary registry unreadable; this file keeps 1:1 row identity and cross-links both ways.

### Evidence bases (read, not modified)

- `docs/governance/ANALYTICS_SCHEMA_REGISTRY.md` (268-row inventory)
- `docs/design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md`
- `scripts/analysis/query_trace.py` → `FAMILY_GLOBS`
- `scripts/maintenance/jsonl_to_parquet.py` → `FAMILY_DEFAULTS`
- Emitters: `src/runtime/crt_construction_trace.py`, `src/runtime/bar_structure_snapshot.py`, write sites in `src/runtime/backtest_v2.py`, `src/research/clean_labels/builder.py`
- Sample JSONL keys: dual_construction construction/bar_structure; multi-run `*_crt_telemetry.jsonl` kinds; events / opportunities / clean_labels samples under `logs/` / `results/`

---

## Summary (UNKNOWN rates)

- **Rows:** 268 (target 268)
- **Lineage-specific cells:** 1608 (6 cols × 268)
- **UNKNOWN lineage cells:** 12 (**0.7%**)
- **UNKNOWN by column:** `produced_by`=12
- **Families by UNKNOWN density (highest first):**
  - `opportunities`: 12 UNKNOWN / 72 lineage cells (16.7%)
  - `crt_construction`: 0 UNKNOWN / 204 lineage cells (0.0%)
  - `crt_telemetry`: 0 UNKNOWN / 336 lineage cells (0.0%)
  - `events`: 0 UNKNOWN / 54 lineage cells (0.0%)
  - `clean_labels`: 0 UNKNOWN / 210 lineage cells (0.0%)
  - `bar_structure`: 0 UNKNOWN / 732 lineage cells (0.0%)
- **produced_by vs owner conflicts:** none (generic owners such as `crt_telemetry writers` / `runtime events writer` / `opportunities logger` are umbrellas; specific module owners match emitters).
- **`opportunities.produced_by`:** all 12 rows are `UNKNOWN` at module granularity (multiple research/training references; no single emitter pinned).

---

## Family `crt_construction` (34 rows)

- **JSONL pattern:** `*_crt_construction.jsonl`
- **DuckDB view:** `crt_construction`
- **produced_by (family default):** `src/runtime/crt_construction_trace.py`

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| schema_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | schema_version | *_crt_construction.jsonl | schema_version | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| run_id | crt_construction_trace | crt_construction | EXACT_MATCH | false | run_id | *_crt_construction.jsonl | run_id | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| instrument | crt_construction_trace | crt_construction | EXACT_MATCH | false | instrument | *_crt_construction.jsonl | instrument | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| timeframe | crt_construction_trace | crt_construction | EXACT_MATCH | false | timeframe | *_crt_construction.jsonl | timeframe | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| corpus_path | crt_construction_trace | crt_construction | EXACT_MATCH | false | corpus_path | *_crt_construction.jsonl | corpus_path | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| corpus_sha256 | crt_construction_trace | crt_construction | EXACT_MATCH | false | corpus_sha256 | *_crt_construction.jsonl | corpus_sha256 | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| config_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | config_version | *_crt_construction.jsonl | config_version | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| config_hash | crt_construction_trace | crt_construction | EXACT_MATCH | false | config_hash | *_crt_construction.jsonl | config_hash | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| ontology_source | crt_construction_trace | crt_construction | EXACT_MATCH | false | ontology_source | *_crt_construction.jsonl | ontology_source | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| ontology_version | crt_construction_trace | crt_construction | EXACT_MATCH | false | ontology_version | *_crt_construction.jsonl | ontology_version | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| bar_index | crt_construction_trace | crt_construction | EXACT_MATCH | false | bar_index | *_crt_construction.jsonl | bar_index | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| timestamp | crt_construction_trace | crt_construction | EXACT_MATCH | false | timestamp | *_crt_construction.jsonl | timestamp | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| emitted_by | crt_construction_trace | crt_construction | EXACT_MATCH | false | emitted_by | *_crt_construction.jsonl | emitted_by | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| phase | crt_construction_trace | crt_construction | EXACT_MATCH | false | phase | *_crt_construction.jsonl | phase | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine_state_before | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine_state_before | *_crt_construction.jsonl | engine_state_before | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine_state_after | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine_state_after | *_crt_construction.jsonl | engine_state_after | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine_action | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine_action | *_crt_construction.jsonl | engine_action | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine_reason | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine_reason | *_crt_construction.jsonl | engine_reason | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine_gates | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine_gates | *_crt_construction.jsonl | engine_gates | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| ontology_state | crt_construction_trace | crt_construction | EXACT_MATCH | true | ontology_state | *_crt_construction.jsonl | ontology_state | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| agree | crt_construction_trace | crt_construction | EXACT_MATCH | true | agree | *_crt_construction.jsonl | agree | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| divergence_pair | crt_construction_trace | crt_construction | EXACT_MATCH | true | divergence_pair | *_crt_construction.jsonl | divergence_pair | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| agree_scope | crt_construction_trace | crt_construction | EXACT_MATCH | false | agree_scope | *_crt_construction.jsonl | agree_scope | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine.crt_state | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine.crt_state | *_crt_construction.jsonl | engine.crt_state [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine.transitions | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine.transitions | *_crt_construction.jsonl | engine.transitions [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| engine.live_context | crt_construction_trace | crt_construction | EXACT_MATCH | true | engine.live_context | *_crt_construction.jsonl | engine.live_context [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.feature_vector | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.feature_vector | *_crt_construction.jsonl | resolver.feature_vector [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.l2_map | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.l2_map | *_crt_construction.jsonl | resolver.l2_map [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.predicate_affinity | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.predicate_affinity | *_crt_construction.jsonl | resolver.predicate_affinity [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.continuous_passed | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.continuous_passed | *_crt_construction.jsonl | resolver.continuous_passed [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.projected_site | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.projected_site | *_crt_construction.jsonl | resolver.projected_site [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.supply_ok | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.supply_ok | *_crt_construction.jsonl | resolver.supply_ok [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| resolver.missing_when | crt_construction_trace | crt_construction | EXACT_MATCH | true | resolver.missing_when | *_crt_construction.jsonl | resolver.missing_when [nested/dot-path] | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |
| producer_id | crt_construction_trace | crt_construction | EXACT_MATCH | false | producer_id | *_crt_construction.jsonl | producer_id | crt_construction | src/runtime/crt_construction_trace.py | research/diagnostics only |

## Family `crt_telemetry` (56 rows)

- **JSONL pattern:** `*_crt_telemetry.jsonl`
- **DuckDB view:** `crt_telemetry`
- **produced_by (family default):** `src/runtime/backtest_v2.py`

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| kind | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | kind | *_crt_telemetry.jsonl | kind | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| candidate_id | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | candidate_id | *_crt_telemetry.jsonl | candidate_id | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| candle_index | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | candle_index | *_crt_telemetry.jsonl | candle_index | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| timestamp | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | timestamp | *_crt_telemetry.jsonl | timestamp | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| from_state | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | from_state | *_crt_telemetry.jsonl | from_state | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| to_state | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | to_state | *_crt_telemetry.jsonl | to_state | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| state_age_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | state_age_candles | *_crt_telemetry.jsonl | state_age_candles | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| entered_states | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | entered_states | *_crt_telemetry.jsonl | entered_states | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| state_entry_counts | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | state_entry_counts | *_crt_telemetry.jsonl | state_entry_counts | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | reason | *_crt_telemetry.jsonl | reason | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| htf_window_position | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | htf_window_position | *_crt_telemetry.jsonl | htf_window_position | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| would_expand | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | would_expand | *_crt_telemetry.jsonl | would_expand | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| would_expand_score | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | would_expand_score | *_crt_telemetry.jsonl | would_expand_score | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| would_expand_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | would_expand_threshold | *_crt_telemetry.jsonl | would_expand_threshold | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| first_seen_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | first_seen_idx | *_crt_telemetry.jsonl | first_seen_idx | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| first_seen_ts | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | first_seen_ts | *_crt_telemetry.jsonl | first_seen_ts | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| last_seen_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | last_seen_idx | *_crt_telemetry.jsonl | last_seen_idx | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| age_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | age_candles | *_crt_telemetry.jsonl | age_candles | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| max_score_seen | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | max_score_seen | *_crt_telemetry.jsonl | max_score_seen | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| score_at_approval | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | score_at_approval | *_crt_telemetry.jsonl | score_at_approval | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| death_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | death_reason | *_crt_telemetry.jsonl | death_reason | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| shadow_used | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | shadow_used | *_crt_telemetry.jsonl | shadow_used | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| shadow_context | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | shadow_context | *_crt_telemetry.jsonl | shadow_context | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| shadow_displacement_br | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | shadow_displacement_br | *_crt_telemetry.jsonl | shadow_displacement_br | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| score_actual | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | score_actual | *_crt_telemetry.jsonl | score_actual | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| score_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | score_threshold | *_crt_telemetry.jsonl | score_threshold | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| decision_distance | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | decision_distance | *_crt_telemetry.jsonl | decision_distance | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| accepted | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | accepted | *_crt_telemetry.jsonl | accepted | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| rejection_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | rejection_reason | *_crt_telemetry.jsonl | rejection_reason | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| soft_conf_candle_num | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | soft_conf_candle_num | *_crt_telemetry.jsonl | soft_conf_candle_num | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| score | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | score | *_crt_telemetry.jsonl | score | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| intent | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | intent | *_crt_telemetry.jsonl | intent | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| reject_reason | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | reject_reason | *_crt_telemetry.jsonl | reject_reason | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| direction | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | direction | *_crt_telemetry.jsonl | direction | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| entry | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | entry | *_crt_telemetry.jsonl | entry | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| atr | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | atr | *_crt_telemetry.jsonl | atr | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| disp_high | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | disp_high | *_crt_telemetry.jsonl | disp_high | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| disp_low | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | disp_low | *_crt_telemetry.jsonl | disp_low | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| sl_atr_buffer | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | sl_atr_buffer | *_crt_telemetry.jsonl | sl_atr_buffer | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| tp1_mult | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | tp1_mult | *_crt_telemetry.jsonl | tp1_mult | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| tp2_mult | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | tp2_mult | *_crt_telemetry.jsonl | tp2_mult | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| episode_start_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | episode_start_idx | *_crt_telemetry.jsonl | episode_start_idx | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| episode_end_idx | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | episode_end_idx | *_crt_telemetry.jsonl | episode_end_idx | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| duration_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | duration_candles | *_crt_telemetry.jsonl | duration_candles | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| max_retrace_depth_abs | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | max_retrace_depth_abs | *_crt_telemetry.jsonl | max_retrace_depth_abs | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| ceiling_at_max | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | ceiling_at_max | *_crt_telemetry.jsonl | ceiling_at_max | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| time_to_max_retrace_candles | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | time_to_max_retrace_candles | *_crt_telemetry.jsonl | time_to_max_retrace_candles | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| qualified | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | qualified | *_crt_telemetry.jsonl | qualified | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| outcome | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | outcome | *_crt_telemetry.jsonl | outcome | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| expansion_dwell_stats | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | expansion_dwell_stats | *_crt_telemetry.jsonl | expansion_dwell_stats | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| ended_by | crt_telemetry writers | crt_telemetry | EXACT_MATCH | false | ended_by | *_crt_telemetry.jsonl | ended_by | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| freshness_ratio | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | freshness_ratio | *_crt_telemetry.jsonl | freshness_ratio | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| age_hours_actual | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | age_hours_actual | *_crt_telemetry.jsonl | age_hours_actual | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| age_hours_estimated | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | age_hours_estimated | *_crt_telemetry.jsonl | age_hours_estimated | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| age_pct_of_threshold | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | age_pct_of_threshold | *_crt_telemetry.jsonl | age_pct_of_threshold | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |
| candidate_age_at_entry | crt_telemetry writers | crt_telemetry | EXACT_MATCH | true | candidate_age_at_entry | *_crt_telemetry.jsonl | candidate_age_at_entry | crt_telemetry | src/runtime/backtest_v2.py | research/diagnostics only |

## Family `events` (9 rows)

- **JSONL pattern:** `*_events.jsonl`
- **DuckDB view:** `events`
- **produced_by (family default):** `src/runtime/backtest_v2.py`

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| event | runtime events writer | events | EXACT_MATCH | false | event | *_events.jsonl | event | events | src/runtime/backtest_v2.py | research/diagnostics only |
| timestamp | runtime events writer | events | EXACT_MATCH | false | timestamp | *_events.jsonl | timestamp | events | src/runtime/backtest_v2.py | research/diagnostics only |
| candle_index | runtime events writer | events | EXACT_MATCH | false | candle_index | *_events.jsonl | candle_index | events | src/runtime/backtest_v2.py | research/diagnostics only |
| state_from | runtime events writer | events | EXACT_MATCH | true | state_from | *_events.jsonl | state_from | events | src/runtime/backtest_v2.py | research/diagnostics only |
| state_to | runtime events writer | events | EXACT_MATCH | true | state_to | *_events.jsonl | state_to | events | src/runtime/backtest_v2.py | research/diagnostics only |
| direction | runtime events writer | events | EXACT_MATCH | true | direction | *_events.jsonl | direction | events | src/runtime/backtest_v2.py | research/diagnostics only |
| price | runtime events writer | events | EXACT_MATCH | true | price | *_events.jsonl | price | events | src/runtime/backtest_v2.py | research/diagnostics only |
| reason | runtime events writer | events | EXACT_MATCH | true | reason | *_events.jsonl | reason | events | src/runtime/backtest_v2.py | research/diagnostics only |
| metadata | runtime events writer | events | EXACT_MATCH | false | metadata | *_events.jsonl | metadata | events | src/runtime/backtest_v2.py | research/diagnostics only |

## Family `opportunities` (12 rows)

- **JSONL pattern:** `opportunities.jsonl`
- **DuckDB view:** `opportunities`
- **produced_by (family default):** `UNKNOWN`

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| timestamp | opportunities logger | opportunities | EXACT_MATCH | false | timestamp | opportunities.jsonl | timestamp | opportunities | UNKNOWN | research/diagnostics only |
| instrument | opportunities logger | opportunities | EXACT_MATCH | false | instrument | opportunities.jsonl | instrument | opportunities | UNKNOWN | research/diagnostics only |
| direction | opportunities logger | opportunities | EXACT_MATCH | true | direction | opportunities.jsonl | direction | opportunities | UNKNOWN | research/diagnostics only |
| entry | opportunities logger | opportunities | EXACT_MATCH | true | entry | opportunities.jsonl | entry | opportunities | UNKNOWN | research/diagnostics only |
| sl | opportunities logger | opportunities | EXACT_MATCH | true | sl | opportunities.jsonl | sl | opportunities | UNKNOWN | research/diagnostics only |
| tp | opportunities logger | opportunities | EXACT_MATCH | true | tp | opportunities.jsonl | tp | opportunities | UNKNOWN | research/diagnostics only |
| outcome | opportunities logger | opportunities | EXACT_MATCH | false | outcome | opportunities.jsonl | outcome | opportunities | UNKNOWN | research/diagnostics only |
| rr_achieved | opportunities logger | opportunities | EXACT_MATCH | true | rr_achieved | opportunities.jsonl | rr_achieved | opportunities | UNKNOWN | research/diagnostics only |
| duration_candles | opportunities logger | opportunities | EXACT_MATCH | true | duration_candles | opportunities.jsonl | duration_candles | opportunities | UNKNOWN | research/diagnostics only |
| mfe | opportunities logger | opportunities | EXACT_MATCH | true | mfe | opportunities.jsonl | mfe | opportunities | UNKNOWN | research/diagnostics only |
| mae | opportunities logger | opportunities | EXACT_MATCH | true | mae | opportunities.jsonl | mae | opportunities | UNKNOWN | research/diagnostics only |
| features | opportunities logger | opportunities | EXACT_MATCH | true | features | opportunities.jsonl | features | opportunities | UNKNOWN | research/diagnostics only |

## Family `clean_labels` (35 rows)

- **JSONL pattern:** `clean_labels.jsonl`
- **DuckDB view:** `clean_labels`
- **produced_by (family default):** `src/research/clean_labels/builder.py`
- **Legacy naming (GT-1):** `tp2_surrogate_r` (earliest `results/clean_labels/BNBUSDT/20260721T221711Z/` corpus, value `2.0`) is the **legacy name of canonical `tp2_stretch_r`** (current builder emits `tp2_stretch_r = TP2_ATR_MULT`). Same concept across corpus protocol versions — near-HOMONYM / alias, **not** a distinct row.

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| unit_id | clean_labels builder | clean_labels | EXACT_MATCH | false | unit_id | clean_labels.jsonl | unit_id | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| instrument | clean_labels builder | clean_labels | EXACT_MATCH | false | instrument | clean_labels.jsonl | instrument | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| decision_ts | clean_labels builder | clean_labels | EXACT_MATCH | false | decision_ts | clean_labels.jsonl | decision_ts | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| entry_index | clean_labels builder | clean_labels | EXACT_MATCH | false | entry_index | clean_labels.jsonl | entry_index | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| side | clean_labels builder | clean_labels | EXACT_MATCH | true | side | clean_labels.jsonl | side | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| entry | clean_labels builder | clean_labels | EXACT_MATCH | true | entry | clean_labels.jsonl | entry | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| sl | clean_labels builder | clean_labels | EXACT_MATCH | true | sl | clean_labels.jsonl | sl | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| tp1 | clean_labels builder | clean_labels | EXACT_MATCH | true | tp1 | clean_labels.jsonl | tp1 | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| tp2 | clean_labels builder | clean_labels | EXACT_MATCH | true | tp2 | clean_labels.jsonl | tp2 | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| tp2_policy | clean_labels builder | clean_labels | EXACT_MATCH | false | tp2_policy | clean_labels.jsonl | tp2_policy | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| tp2_stretch_r | clean_labels builder | clean_labels | EXACT_MATCH | true | tp2_stretch_r | clean_labels.jsonl | tp2_stretch_r | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| tp1_reward_mult | clean_labels builder | clean_labels | EXACT_MATCH | true | tp1_reward_mult | clean_labels.jsonl | tp1_reward_mult | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| risk_distance | clean_labels builder | clean_labels | EXACT_MATCH | true | risk_distance | clean_labels.jsonl | risk_distance | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| features | clean_labels builder | clean_labels | EXACT_MATCH | true | features | clean_labels.jsonl | features | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| feature_vector | clean_labels builder | clean_labels | EXACT_MATCH | true | feature_vector | clean_labels.jsonl | feature_vector | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_tp1 | clean_labels builder | clean_labels | EXACT_MATCH | false | y_tp1 | clean_labels.jsonl | y_tp1 | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_tp2 | clean_labels builder | clean_labels | EXACT_MATCH | false | y_tp2 | clean_labels.jsonl | y_tp2 | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_survives_be | clean_labels builder | clean_labels | EXACT_MATCH | false | y_survives_be | clean_labels.jsonl | y_survives_be | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_R_net | clean_labels builder | clean_labels | EXACT_MATCH | false | y_R_net | clean_labels.jsonl | y_R_net | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_mfe_r | clean_labels builder | clean_labels | EXACT_MATCH | false | y_mfe_r | clean_labels.jsonl | y_mfe_r | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_mae_r_heat | clean_labels builder | clean_labels | EXACT_MATCH | false | y_mae_r_heat | clean_labels.jsonl | y_mae_r_heat | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_holding_bars | clean_labels builder | clean_labels | EXACT_MATCH | false | y_holding_bars | clean_labels.jsonl | y_holding_bars | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_time_to_mfe | clean_labels builder | clean_labels | EXACT_MATCH | false | y_time_to_mfe | clean_labels.jsonl | y_time_to_mfe | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_time_to_1r | clean_labels builder | clean_labels | EXACT_MATCH | false | y_time_to_1r | clean_labels.jsonl | y_time_to_1r | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_expired_timeout | clean_labels builder | clean_labels | EXACT_MATCH | false | y_expired_timeout | clean_labels.jsonl | y_expired_timeout | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_reached_0_5r | clean_labels builder | clean_labels | EXACT_MATCH | false | y_reached_0_5r | clean_labels.jsonl | y_reached_0_5r | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_reached_1r_horizon | clean_labels builder | clean_labels | EXACT_MATCH | false | y_reached_1r_horizon | clean_labels.jsonl | y_reached_1r_horizon | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| y_reached_2r_horizon | clean_labels builder | clean_labels | EXACT_MATCH | false | y_reached_2r_horizon | clean_labels.jsonl | y_reached_2r_horizon | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| path_mfe_r | clean_labels builder | clean_labels | EXACT_MATCH | false | path_mfe_r | clean_labels.jsonl | path_mfe_r | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| path_mae_r_heat | clean_labels builder | clean_labels | EXACT_MATCH | false | path_mae_r_heat | clean_labels.jsonl | path_mae_r_heat | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| path_outcome | clean_labels builder | clean_labels | EXACT_MATCH | false | path_outcome | clean_labels.jsonl | path_outcome | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| path_time_to_tp | clean_labels builder | clean_labels | EXACT_MATCH | false | path_time_to_tp | clean_labels.jsonl | path_time_to_tp | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| path_time_to_failure | clean_labels builder | clean_labels | EXACT_MATCH | false | path_time_to_failure | clean_labels.jsonl | path_time_to_failure | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| diagnostics | clean_labels builder | clean_labels | EXACT_MATCH | false | diagnostics | clean_labels.jsonl | diagnostics | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |
| provenance | clean_labels builder | clean_labels | EXACT_MATCH | false | provenance | clean_labels.jsonl | provenance | clean_labels | src/research/clean_labels/builder.py | research/diagnostics only |

## Family `bar_structure` (122 rows)

- **JSONL pattern:** `*_bar_structure.jsonl`
- **DuckDB view:** `bar_structure`
- **produced_by (family default):** `src/runtime/bar_structure_snapshot.py`

| field_name | owner | family | classification | recomputable | source_jsonl_field | source_jsonl_family | parquet_column | duckdb_view | produced_by | consumed_by |
|------------|-------|--------|----------------|--------------|-------------------|---------------------|----------------|-------------|-----------------------------|
| schema_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | schema_version | *_bar_structure.jsonl | schema_version | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| run_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | run_id | *_bar_structure.jsonl | run_id | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| instrument | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | instrument | *_bar_structure.jsonl | instrument | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| timeframe | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | timeframe | *_bar_structure.jsonl | timeframe | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| corpus_path | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | corpus_path | *_bar_structure.jsonl | corpus_path | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| corpus_sha256 | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | corpus_sha256 | *_bar_structure.jsonl | corpus_sha256 | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| config_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | config_version | *_bar_structure.jsonl | config_version | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| config_hash | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | config_hash | *_bar_structure.jsonl | config_hash | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| feature_schema_version | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | feature_schema_version | *_bar_structure.jsonl | feature_schema_version | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| feature_schema_hash | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | feature_schema_hash | *_bar_structure.jsonl | feature_schema_hash | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| bar_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | bar_index | *_bar_structure.jsonl | bar_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| engine_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | engine_candle_index | *_bar_structure.jsonl | engine_candle_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| timestamp | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | timestamp | *_bar_structure.jsonl | timestamp | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| timestamp_basis | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | timestamp_basis | *_bar_structure.jsonl | timestamp_basis | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| htf_candle_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | htf_candle_id | *_bar_structure.jsonl | htf_candle_id | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| emitted_by | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | emitted_by | *_bar_structure.jsonl | emitted_by | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| phase | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | phase | *_bar_structure.jsonl | phase | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| open | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | open | *_bar_structure.jsonl | open | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | high | *_bar_structure.jsonl | high | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | low | *_bar_structure.jsonl | low | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| close | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | close | *_bar_structure.jsonl | close | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| volume | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | volume | *_bar_structure.jsonl | volume | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| atr_abs | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | atr_abs | *_bar_structure.jsonl | atr_abs | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_state_before | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_state_before | *_bar_structure.jsonl | crt_state_before | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_state_after | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_state_after | *_bar_structure.jsonl | crt_state_after | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_state_changed | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_state_changed | *_bar_structure.jsonl | crt_state_changed | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_action | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_action | *_bar_structure.jsonl | crt_action | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_reject_reason | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_reject_reason | *_bar_structure.jsonl | crt_reject_reason | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_direction | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_direction | *_bar_structure.jsonl | crt_direction | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_range_h_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_range_h_ref | *_bar_structure.jsonl | crt_range_h_ref | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_range_l_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_range_l_ref | *_bar_structure.jsonl | crt_range_l_ref | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_range_size | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_range_size | *_bar_structure.jsonl | crt_range_size | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_range_session | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_range_session | *_bar_structure.jsonl | crt_range_session | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_range_htf_id | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_range_htf_id | *_bar_structure.jsonl | crt_range_htf_id | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_sweep_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_sweep_price | *_bar_structure.jsonl | crt_sweep_price | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_sweep_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_sweep_candle_index | *_bar_structure.jsonl | crt_sweep_candle_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_sweep_double_confirmed | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_sweep_double_confirmed | *_bar_structure.jsonl | crt_sweep_double_confirmed | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_displacement_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_displacement_candle_index | *_bar_structure.jsonl | crt_displacement_candle_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_retest_candle_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_retest_candle_index | *_bar_structure.jsonl | crt_retest_candle_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_pending_displacement_ttl | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_pending_displacement_ttl | *_bar_structure.jsonl | crt_pending_displacement_ttl | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_htf_remaining_candles | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_htf_remaining_candles | *_bar_structure.jsonl | crt_htf_remaining_candles | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_evaluating_soft_conf | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_evaluating_soft_conf | *_bar_structure.jsonl | crt_evaluating_soft_conf | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| crt_trade_open | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | crt_trade_open | *_bar_structure.jsonl | crt_trade_open | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_timeframe | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | parent_timeframe | *_bar_structure.jsonl | parent_timeframe | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_enabled | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | parent_enabled | *_bar_structure.jsonl | parent_enabled | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_crt_state | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_crt_state | *_bar_structure.jsonl | parent_crt_state | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_bias | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_bias | *_bar_structure.jsonl | parent_bias | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_range_h_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_range_h_ref | *_bar_structure.jsonl | parent_range_h_ref | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_range_l_ref | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_range_l_ref | *_bar_structure.jsonl | parent_range_l_ref | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_closed_this_bar | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_closed_this_bar | *_bar_structure.jsonl | parent_closed_this_bar | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| parent_last_close_ts | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | parent_last_close_ts | *_bar_structure.jsonl | parent_last_close_ts | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| htf_state | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | htf_state | *_bar_structure.jsonl | htf_state | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| htf_range_ratio | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | htf_range_ratio | *_bar_structure.jsonl | htf_range_ratio | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_status | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | objective_status | *_bar_structure.jsonl | objective_status | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_direction | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | objective_direction | *_bar_structure.jsonl | objective_direction | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_target | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | objective_target | *_bar_structure.jsonl | objective_target | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_invalidate_at | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | objective_invalidate_at | *_bar_structure.jsonl | objective_invalidate_at | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| htf_thresholds | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | htf_thresholds | *_bar_structure.jsonl | htf_thresholds | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_gate_enabled | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | objective_gate_enabled | *_bar_structure.jsonl | objective_gate_enabled | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| objective_gate_mode | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | objective_gate_mode | *_bar_structure.jsonl | objective_gate_mode | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| smc_window_len | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | smc_window_len | *_bar_structure.jsonl | smc_window_len | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| smc_max_window | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | smc_max_window | *_bar_structure.jsonl | smc_max_window | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| smc_swing_window | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | smc_swing_window | *_bar_structure.jsonl | smc_swing_window | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_present | *_bar_structure.jsonl | fvg_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_bullish | *_bar_structure.jsonl | fvg_bullish | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_high | *_bar_structure.jsonl | fvg_high | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_low | *_bar_structure.jsonl | fvg_low | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_mid | *_bar_structure.jsonl | fvg_mid | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_formed_at_index | *_bar_structure.jsonl | fvg_formed_at_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_age_bars | *_bar_structure.jsonl | fvg_age_bars | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_width_atr | *_bar_structure.jsonl | fvg_width_atr | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_inside | *_bar_structure.jsonl | fvg_inside | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_distance | *_bar_structure.jsonl | fvg_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| fvg_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | fvg_window_truncated | *_bar_structure.jsonl | fvg_window_truncated | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_present | *_bar_structure.jsonl | order_block_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_bullish | *_bar_structure.jsonl | order_block_bullish | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_high | *_bar_structure.jsonl | order_block_high | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_low | *_bar_structure.jsonl | order_block_low | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_mid | *_bar_structure.jsonl | order_block_mid | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_formed_at_index | *_bar_structure.jsonl | order_block_formed_at_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_age_bars | *_bar_structure.jsonl | order_block_age_bars | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_width_atr | *_bar_structure.jsonl | order_block_width_atr | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_inside | *_bar_structure.jsonl | order_block_inside | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_distance | *_bar_structure.jsonl | order_block_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| order_block_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | order_block_window_truncated | *_bar_structure.jsonl | order_block_window_truncated | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_present | *_bar_structure.jsonl | breaker_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_bullish | *_bar_structure.jsonl | breaker_bullish | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_high | *_bar_structure.jsonl | breaker_high | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_low | *_bar_structure.jsonl | breaker_low | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_mid | *_bar_structure.jsonl | breaker_mid | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_formed_at_index | *_bar_structure.jsonl | breaker_formed_at_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_age_bars | *_bar_structure.jsonl | breaker_age_bars | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_width_atr | *_bar_structure.jsonl | breaker_width_atr | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_inside | *_bar_structure.jsonl | breaker_inside | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_distance | *_bar_structure.jsonl | breaker_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| breaker_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | breaker_window_truncated | *_bar_structure.jsonl | breaker_window_truncated | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_present | *_bar_structure.jsonl | mitigation_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_bullish | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_bullish | *_bar_structure.jsonl | mitigation_bullish | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_high | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_high | *_bar_structure.jsonl | mitigation_high | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_low | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_low | *_bar_structure.jsonl | mitigation_low | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_mid | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_mid | *_bar_structure.jsonl | mitigation_mid | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_formed_at_index | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_formed_at_index | *_bar_structure.jsonl | mitigation_formed_at_index | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_age_bars | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_age_bars | *_bar_structure.jsonl | mitigation_age_bars | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_width_atr | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_width_atr | *_bar_structure.jsonl | mitigation_width_atr | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_inside | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_inside | *_bar_structure.jsonl | mitigation_inside | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_distance | *_bar_structure.jsonl | mitigation_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| mitigation_window_truncated | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | mitigation_window_truncated | *_bar_structure.jsonl | mitigation_window_truncated | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdh_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdh_present | *_bar_structure.jsonl | pdh_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdh_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdh_price | *_bar_structure.jsonl | pdh_price | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdh_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdh_distance | *_bar_structure.jsonl | pdh_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdl_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdl_present | *_bar_structure.jsonl | pdl_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdl_price | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdl_price | *_bar_structure.jsonl | pdl_price | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdl_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | pdl_distance | *_bar_structure.jsonl | pdl_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| pdh_pdl_day_ts | bar_structure_snapshot | bar_structure | EXACT_MATCH | false | pdh_pdl_day_ts | *_bar_structure.jsonl | pdh_pdl_day_ts | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| eqh_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | eqh_present | *_bar_structure.jsonl | eqh_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| eqh_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | eqh_distance | *_bar_structure.jsonl | eqh_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| eql_present | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | eql_present | *_bar_structure.jsonl | eql_present | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| eql_distance | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | eql_distance | *_bar_structure.jsonl | eql_distance | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| choch_value | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | choch_value | *_bar_structure.jsonl | choch_value | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| choch_basis | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | choch_basis | *_bar_structure.jsonl | choch_basis | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| break_of_structure | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | break_of_structure | *_bar_structure.jsonl | break_of_structure | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |
| trend_bias | bar_structure_snapshot | bar_structure | EXACT_MATCH | true | trend_bias | *_bar_structure.jsonl | trend_bias | bar_structure | src/runtime/bar_structure_snapshot.py | research/diagnostics only |

---

## Cross-links

- Schema symbol table: [`ANALYTICS_SCHEMA_REGISTRY.md`](./ANALYTICS_SCHEMA_REGISTRY.md)
- Vocabulary doctrine: [`../design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md`](../design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md)
- Design README: [`../design/context-finding-odp/README.md`](../design/context-finding-odp/README.md)

**Confirmation:** no `src/` changes; no Context/ODP/Policy YAML changes; no commit in this Phase 4 pass.
