# v3_unified_market_structure_2026_09 — Implementation Plan

**Change ID:** `CH-v3-unified-market-structure-v1`
**Posture:** register-only · observation-only · decision-neutral. `ACTIVE_VERSION` stays `v2_htfcrt_2026_08`.

---

## Context

The repo has spent F-019…F-096 falsifying directional edges one ontology at a time, and it now carries a rich structural vocabulary — 12 CRT states, a calendar-true parent-CRT track, HTFState/ObjectiveStatus, and 9 SMC primitives — that is **never observed together on the same bar**. The SMC detectors are the sharpest case: each one builds a full `Zone` object (`src/features/smc/_geometry.py:32`) and the `*_distance` wrapper immediately collapses it to one tanh scalar and throws the geometry away (`order_block.py:84-90`, `fvg.py:63-69`, `breaker.py:66-72`, `mitigation.py:59-65`). Zone edges, formation index, polarity and mitigation history are computed on every bar and discarded.

v3 adds a per-bar sidecar record that keeps all of it, logs it to parquet, and measures — under a sealed contract — whether any context family carries expectancy information beyond CRT state alone. Nothing reaches a decision until that evidence exists (§6.5 Authority Ladder; requirement 8 *is* that rule).

### The finding that reshaped requirement 7

`results/run_20260812_113506_XAUUSD/XAUUSD_summary.json` → **`total_setups: 1`** across 47,275 XAUUSD M15 bars. Attribution against CRT's own trade ledger is unmeasurable at n=1 (crypto majors pool to ~30, F-070). Per your decision, the baseline is the **every-bar, CRT-state-conditioned** population — the F-086 outcome-first inversion, ~94k primary units.

**Pre-registered limitation:** this measures incremental value on the every-bar population, **not** on production's executed trades. That sentence goes verbatim into the contract's `authority.note` and the finding.

### Decisions locked

| | |
|---|---|
| Record type name | **`BarStructureSnapshot`** (avoids collision with `MarketContext`/`MarketContextBuilder`, `src/features/market_context.py:156,223`) |
| Attribution baseline | Every-bar, CRT-state-conditioned |
| Walk kernel | `multi_tp_walk` (SEM-017) primary + `forward_walk(intrabar_fixed)` declared comparability arm |
| Activation | Register only; `ACTIVE_VERSION` unchanged |
| Spine contact | 3 emit sites in `backtest_v2.py` + one read-only `ParentCRTFeed` property |
| Instrument | XAUUSD M15, `data/mt5/XAUUSD_M15.csv` |

---

## Hard constraints

1. **Out-of-vector.** The snapshot adds **zero** canonical dimensions. `CANONICAL_FEATURES` stays a 48-tuple, `SCHEMA_HASH` stays `f52bf5d3f2ae6ddb75e8a35e9c323e07`, `FEATURE_ORDER_HASH` stays `160c96c52b198a16` (`src/features/feature_schema.py:88-125,212,223`). Adding dims breaks `tests/test_feature_layer_freeze.py`'s XAUUSD `vector_sha256` pin (:141-144) and re-stales all 6 model families (F-076). Written into SEM-035's `validation_rules` so it is enforced semantically, not remembered.
2. **`params` untouched.** `config_hash` covers `params` only (`production_config.py:89-92`). v3 carries the same 5 keys and the same hash `7de09f62…` as v2. Every new section is hash-neutral.
3. **JSONL is the system of record.** Parquet is a regenerable projection — `CC-PARQUET-PROJECTION` (`docs/governance/jsonl_claim_catalog.yaml:286`) forbids treating it as a second authority.
4. **Reuse, never re-derive.** SMC geometry comes from `features.smc`'s existing `find_active_*` functions verbatim. No new detection state machine, no local formula math (§6.6).

---

## Phase 1 — Config (`PRODUCTION_CONFIG_CHANGE`)

**File:** `configs/production/v3_unified_market_structure_2026_09.json` — byte-for-byte copy of `v2_htfcrt_2026_08.json` (46 top-level keys) with `version`/`config_id`/`created_at`/`promoted_at`/`notes` updated and **three** new sections appended.

- **`bar_structure_snapshot`** — `{enabled:false, schema_version:"1.0.0", authority:"OBSERVATION_ONLY", decision_neutral:true, emit_on_warmup_bars:true, output_dir, filename_suffix, families:{...11 flags}, smc:{max_window_source:"feature_pipeline.smc_max_window", swing_window_source:"feature_pipeline.swing_window", ...}}`. Default **off** — zero overhead unless a research run opts in.
- **`bar_structure_parquet`** — `{enabled:false, partition_by:"crt_state_after", compression:"zstd", verify_on_write:true}`.
- **`context_attribution`** — the promotion ledger: `{promoted_families: [], evidence_required:"MC-CTXATTR-XAUUSD-M15-V1", authority:"NONE"}`. An empty `promoted_families` is requirement 8 made mechanical.

**Registration, not promotion.** `promotion_manager._write_to_registry:498-610` deep-clones base `v1_multi_2026_03.json` and overlays only the 9 `_METADATA_KEYS:526-529` — running `promote_*` would **silently strip `parent_crt`, `feature_pipeline`, `backtest`**. That is why `v2_htfcrt_2026_08` was hand-written. v3 follows the same route: hand-write the config, hand-append **one `REGISTERED` line** to `configs/promotion_log.jsonl` (schema per `_log_event:629-635`). Not `PROMOTED` — `config_integrity.active_version_is_governed:66-76` is the only event-value consumer and only inspects the version named by `ACTIVE_VERSION`; writing `PROMOTED` for a never-activated version is a false governance record.

**Compatibility proof (requirement 9).** `scripts/analysis/v3_config_parity.py` runs the XAUUSD corpus under v2 then v3 and asserts byte-identical `XAUUSD_events.jsonl`, `trades.csv`, and summary. `PROD_VERSION` is import-frozen (`production_config.py:82`) so the harness must use **two serialized subprocesses** with a restore-on-exit guard on the `ACTIVE_VERSION` pointer. Artifact → `docs/research-readiness/market_context/parity/`.

---

## Phase 2 — `BarStructureSnapshot` (`RUNTIME_DECISION_PATH_CHANGE`, behaviour unchanged)

**Module:** `src/runtime/bar_structure_snapshot.py`. `SNAPSHOT_SCHEMA_VERSION = "1.0.0"`, mirroring `crt_baseline_trace.py:21`.

Flat record, ~118 keys, one JSON object per bar. **Key order is load-bearing** — `parquet_store._order_violation:620` checks it (a reordered flatten group scrambles vectors in `replay_memory_engine` with no error anywhere).

| Block | Fields | Source |
|---|---|---|
| Identity (16) | `schema_version, run_id, instrument, timeframe, corpus_path, corpus_sha256, config_version, config_hash, feature_schema_version, feature_schema_hash, bar_index, engine_candle_index, timestamp, timestamp_basis, htf_candle_id, emitted_by` | runner + `PROD_VERSION` |
| Bar (7) | OHLCV, `atr_abs` (**absolute price units**, `engine.state.atr_abs` — not close-relative FM-041), `spread_half` | candle + engine |
| CRT (18) | `crt_state_before/after/changed`, `crt_action`, `crt_direction`, range h/l/size/session/htf_id, sweep price/index/double, displacement & retest indices, pending TTL, htf position/remaining, `crt_trade_open` | reuse `crt_baseline_trace.snapshot_engine_state:196` accessor pattern verbatim |
| Parent CRT (7) | `parent_timeframe`, `parent_crt_state` ∈ {RANGE_C1,MANIPULATION_C2,DISTRIBUTION_C3}, `parent_bias`, range h/l refs, `parent_closed_this_bar`, `parent_last_close_ts` | `ParentCRTFeed` :81,:85,:89; all null when feed is `None` |
| HTF (3) | `htf_state` ∈ {UNKNOWN,EXPANSION,ACCUMULATION,DISTRIBUTION,REVERSAL}, `htf_range_ratio`, `htf_thresholds` | `.htf_state` :93 + **new** `ParentCRTFeed.last_range_ratio` property |
| Objective (6) | `objective_status/direction/target/invalidate_at` + `objective_gate_enabled`, `objective_gate_mode` | `.objective` :97 + config echo |
| SMC zones (4×11) | per family ∈ {fvg, order_block, breaker, mitigation}: `_present, _bullish, _high, _low, _mid, _formed_at_index, _age_bars, _width_atr, _inside, _distance, _window_truncated` | `find_active_fvg:40`, `find_active_order_block:55`, `find_active_breaker:25`, `find_active_mitigation_block:25` |
| Levels (10) | PDH/PDL + EQH/EQL: price, distance, swing index, cluster size, `_present` | `levels.pdh_pdl_distance:26`, `eqh_eql_distance:55` |
| CHoCH (4) | `choch_value`, `choch_basis`, `break_of_structure`, `trend_bias` | `choch.change_of_character:20`; **join** the pipeline columns rather than re-deriving |

**Null semantics, uniform:** `{f}_distance` is `0.0` and **never null** (matches `smc/__init__.py:1-16` — 0.0 means *no structure*, not *zero distance*). Every other zone field is null iff `{f}_present` is false. `{f}_window_truncated` disambiguates "no structure" from "`smc_max_window` cut it off" — without it, the ~100-bar boundary manufactures periodicity in every `_present` series and is a live source of spurious findings.

**Bit-identity guard:** `{f}_distance` must equal the existing 48-dim vector value exactly. A test asserts float equality against the `*_distance()` functions so the snapshot can never silently fork from the canonical feature.

### Emission

Three additive sites in `src/runtime/backtest_v2.py`, all behind `bar_structure_snapshot.enabled`:
1. `:2212-2213` — capture the currently-discarded `parent_feed.push()` return for `parent_closed_this_bar`.
2. Warmup branch `:2225-2229` — emit an identity+bar-only record so `bar_index` is a gapless `0..N-1` occupancy series.
3. **After `:2306`** — the main record. `result`, `candle`, `candle_idx`, `prev_state`/`curr_state`, `parent_feed`, `engine.state.atr_abs` are all in scope and nothing downstream reads anything set there. Precedent: `journal.observe_open_bar(candle)` :2251-2252.

**Decision neutrality is proven, not asserted:** emission happens *after* `process_candle` returns; the emitter takes read-only views; the ledger-parity test (Phase 6) is the proof.

**Perf.** `_find_break_events` re-runs `detect_causal_swings(bars[:i],k)` for every interior position on every bar (`order_block.py:46-51`), and order_block/breaker/mitigation each call it independently — **the identical scan runs 3× per bar**. Add a per-bar memo keyed on `(window_end_index, k)` shared across the three detectors. Pure caching, no math change; a test asserts memoized output is bit-identical to unmemoized.

**New:** `ParentCRTFeed.last_range_ratio` — pure read-only `@property` over already-stored fields. `classify_htf_state:96` computes the ratio and discards it; this surfaces it without private-attribute reads and touches no decision path.

---

## Phase 3 — Parquet

Reuse `src/utils/parquet_store.py` wholesale: `compact_jsonl:422` → `verify_projection:661` → `projection_status:113`. **pyarrow is optional** (`pyproject.toml:15-17`); every read path degrades to JSONL, so the emitter never hard-depends on it.

- Add `_market_context.jsonl` → `partition_by="crt_state_after"` to `FAMILY_DEFAULTS` (`scripts/maintenance/jsonl_to_parquet.py:43-48`). Partitioning by CRT state is deliberate: the attribution program reads per-stratum.
- Column list + arrow types + partition key are declared in the machine data contract (Phase 7), and `verify_on_write` runs `verify_projection` so a round-trip mismatch fails at write time.
- Claim-catalog framing: parquet carries `CC-PARQUET-PROJECTION` only — never a second authority.

---

## Phase 4 — Attribution program

**Contract:** `configs/research/measurement_contracts/instances/MC-CTXATTR-XAUUSD-M15-V1.json` · **Experiment:** `E-CTXATTR-XAUUSD-M15` · **Ontology:** SEM-035 (snapshot), SEM-036 (overlay) · **Code:** `src/research/evidence/context_attribution.py`, patterned directly on `rnet_overlay.py` (F-093).

Contract sealed and floor-green **before** the driver exists (the F-083 lesson). Profile `metals_mt5.v1.json` has two `REQUIRES_DECISION` terms the contract must explicitly resolve: `population.gap_policy`, and `features.session_timestamp_basis` → declare `broker_local`, cite F-066's measured 53.36% mislabel, and put session/hour-of-day **out of path**.

**Population.** Unit = (bar, direction). Primary arm n ≈ 47,157 × 2 = **94,314**. Reuse `research.oracle.labeler` rather than rebuilding — `PRIMARY_ARM = (disp_bar, production)` is already declared at `labeler.py:76-79`; the other three arms are **robustness, never gated**. Strata = `crt_state_after` from the snapshot, which is **engine**-authoritative, not the resolver (F-069/F-086 measured the gap: resolver RANGE 21,745 vs engine 35,159). Join snapshot ⟕ labels on `bar_index`, legal only within the same `run_id` + `corpus_sha256`; declare both grains in `src/research/evidence/catalog.py` `SURFACES` so the 1:2 fan-out is explicit and `IllegalJoinError` guards a wrong 1:1.

**Kernels.** Primary `multi_tp_walk:124` (`tie_break="production"`, `trail_fraction=0.5`, `runner_stop_pricing="ledger_blend"`, `timeout_pricing="mark_to_close"`, `max_forward=40`). Comparability `forward_walk(intrabar_fixed):80`. Both under the **same** `ComponentCostModel` (measured XAUUSD: half_spread 0.045, commission 0.040, entry/stop slippage 0.090, `status="MEASURED"`), `.provenance():326` written into metrics.

> Do **not** reuse `clean_labels.y_R_net` for the comparability arm — it bakes 12bps, which F-082 measured as ~11× punitive, confounding exit kernel with cost model. Re-run `forward_walk` fresh under SEM-015 so the kernel is the only difference.
>
> F-088's naming trap is **reproduced, not fixed**: `partial_tp_breakeven_enabled` does not do breakeven, and the effective tie-break is SL-first via `_intrabar_trigger_price`.

**Arms.** Baseline = `E[y | crt_state_after = s]` per stratum, no overlay. 22 pre-registered overlay arms = 11 families (parent_crt, htf, objective, fvg, order_block, breaker, mitigation, choch, eqh_eql, pdh_pdl, composite) × 2 directions. Each family's binary `agree_f(bar, side)` predicate is declared in `features.name_binding` **before any y is seen**.

**Metric.** Copy `rnet_overlay.overlay():61-98` exactly: `w = 1±k`, `k = OVERLAY_K = 0.5` frozen.
- **PRIMARY `delta_within_stratum`** — overlay computed inside each CRT stratum, aggregated stratum-size-weighted. Weights are mean-preserving within a stratum, so lift is orthogonal to CRT state *by construction*: a family cannot score by proxying for CRT state. This is what operationalizes "beyond CRT alone."
- **DIAGNOSTIC `delta_marginal`** — same overlay ignoring strata. `delta_marginal − delta_within_stratum` **is** the CRT-proxy component; making it visible is the point.

**Split.** Reuse the frozen calendar from `asymmetry_contract.py:22-27` (`HOLDOUT_START` 2025-12-24 19:15, idx 37820; `EMBARGO_BARS` 96; `HORIZON_BARS` 40) via `magnitude_prior.split_rows:89`, exactly as the other four evidence modules do. Spends no new holdout, keeps cross-contract comparability. **F-086's 236-bar stride holdout stays UNSPENT** — stated in `splits`.

**Controls, all three run:** `long_only_control:183` (**the binding control** — XAUUSD rose across the corpus, so zero is the wrong reference; F-086 saw positives collapse 65→8, 56→1, 2→0 against it), `random_entry_control:211`, and a new shuffled-context control (permute family `f` against `y` *within* each stratum — the exact null for `delta_within_stratum`).

**Multiplicity — a genuine problem, controlled four ways** (`metrics.multiplicity`, 22 primary tests):
1. **BH-FDR at q=0.10** over the 22. Not Bonferroni — effective independent n is **941 per direction** (F-086's measured block autocorrelation, +0.292 → +0.003 by lag 20), so Bonferroni would guarantee a vacuous null.
2. **Block-permutation null**, block=40 bars, 199 permutations (floor p=0.005 vs F-086's coarse 3). `tests/research/test_oracle_labeler.py` already floors block-vs-iid width.
3. **Train/holdout sign-match** (`rnet_overlay.verdict:101-108`) — the one genuinely OOS bit BH does not supply.
4. **Pass-count ceiling of 6/22.** More than that is reported as a suspected multiplicity artifact, not claimed.

**Success gate** (verbatim into `metrics.success_gate`): holdout agree-n ≥30 **and** disagree-n ≥30; train/holdout sign match on `delta_within_stratum`; BH-FDR survival at q=0.10; magnitude exceeds `long_only` and shuffled-context controls. **`E > 0` is deliberately not a clause** — base rate ≈ −0.29R (F-086), so beating the base means *losing less*, not earning. `INSUFFICIENT` is a registered outcome (F-096 precedent), never a dropped cell.

**A PROMOTE authorizes exactly one thing:** opening a separate, separately-authorized change program to wire that family into decision logic. It does **not** grant G001 authority, does not flip `economic_claims_allowed`, does not change `context_attribution.promoted_families`, and does not touch any config.

Close out with `run_close_out.finalize_run:77` (real mt00, honest `mt01.json` UNRUN) and `measurement_result_log.append_measurement_result:186`.

---

## Phase 5 — Governance (same turn as the code it describes)

- **Ontology** (`configs/formulas/market_ontology.yaml`): SEM-035 `bar_structure_snapshot` + SEM-036 `context_feature_attribution_overlay`, both into the existing **non-frozen** `execution_behaviours` section — `spec_schema.semantic_registry.sections` is a closed 12-entry list; do not extend it. Frozen runtime sections untouched. SEM-035 carries `not_equal_to` against `features.market_context.MarketContext`, the `crt_baseline_trace` bar record, `build_bar_matrix` rows, `logs/crt_transitions.jsonl`, and `CANONICAL_FEATURES`. SEM-036 carries the full `epistemic` block (`known_invariants` / `unknown_mechanism` / `candidate_hypotheses` / `resolution_metric` / `falsification_conditions`).
- **Claim catalog** (`docs/governance/jsonl_claim_catalog.yaml`): stream row `STR-BAR-STRUCTURE-SNAPSHOT` (L3, `IDENTIFIED`) + two classes — `CC-CTX-RUN-SCOPED-OBSERVATION` (**CAN**: "the engine's CRT state at this identified bar of this identified run was X") and `CC-CTX-NOT-DECISION` (**CANNOT**: "this context feature influenced a decision" / "is an edge"). The run+instrument+corpus identity and gapless bar coverage are precisely what `logs/crt_transitions.jsonl` lacks (`CC-L3-GLOBAL-UNIDENTIFIED`, :259). Regenerate via `python -m governance.jsonl_claim_catalog` — never hand-edit `data/jsonl_claim_catalog.jsonl`.
- **SITS**, same turn as the 3 new scripts: `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`. The hand-maintained `OVERLAYS` list (`seed_script_registry.py:28+`) **must** be extended or the PR-3 ratchet fails by design on `purpose == "GRANDFATHER_UNCLASSIFIED"`. All 22 required stub fields (`script_registry.py:59-82`).
- **Construction manifest** `docs/governance/build_manifests/CH-v3-unified-market-structure-v1.impact.json`, five change classes: `PRODUCTION_CONFIG_CHANGE`, `SEMANTIC_REGISTRY_CHANGE`, `JSONL_CLAIM_SURFACE_CHANGE`, `SCRIPT_LIFECYCLE_CHANGE`, `RUNTIME_DECISION_PATH_CHANGE` (declared even though behaviour is unchanged — declaring and proving neutrality is stronger than not declaring). `required_checks_ack` must cover the **union** of those five classes' `required_checks`. `production_behavior_changed: "NO"`; `affected_production_config: "v3… (REGISTERED, not activated)"`. No mandatory field may contain the literal `"UNKNOWN"` (`construction_protocol.py:107-109` BLOCKS).
- **Findings Mandate**: **F-097** in `docs/current-findings.md` + a row in the CLAUDE.md Repository Truths Index + a family row in `research_family_registry.json`; regenerate `data/findings.jsonl` via `export_findings.py`. Evidence paths must be **TRACKED** (`git ls-files`) — which is why raw snapshot JSONL under `logs/` can never be cited.

---

## Phase 6 — Tests

**New**
| test | asserts |
|---|---|
| `tests/test_v3_config_parity.py` | v2 vs v3 → byte-identical events/trades/summary; `params` and `config_hash` unchanged |
| `tests/test_bar_structure_snapshot_schema.py` | record validates against the machine contract; key order stable; null semantics (`_distance` 0.0-never-null; zone fields null iff `_present` false) |
| `tests/test_bar_structure_decision_neutrality.py` | **the requirement-4/5 proof** — emit ON vs OFF gives byte-identical ledger + event stream |
| `tests/test_bar_structure_smc_bit_identity.py` | `{f}_distance` equals the canonical 48-dim value exactly |
| `tests/test_smc_break_event_memo.py` | memoized `_find_break_events` is bit-identical to unmemoized |
| `tests/test_bar_structure_parquet_roundtrip.py` | `compact_jsonl` → `verify_projection` clean, including the reordered-flatten-group case |
| `tests/research/test_context_attribution_contract.py` | contract shape + `economic_claims_allowed:false` while mt00 UNRUN |
| `tests/research/test_context_attribution_overlay.py` | `delta_within_stratum` is mean-preserving within stratum; shuffled-context control nulls it |

**Must stay green** (do not regress): `test_feature_layer_freeze.py` (XAUUSD `vector_sha256`), `test_semantic_registry.py`, `test_jsonl_claim_catalog.py`, `test_jsonl_claim_grounding.py`, `test_script_registry.py`, `test_script_matrix_sync.py`, `test_construction_protocol.py`, `test_current_findings.py`, `test_measurement_result_log.py`, `test_parquet_store.py`, `test_config_reachability.py`.

Gate: `python scripts/maintenance/check_governance_invariants.py` (GREEN_FLOOR, grows monotonically — **never** replaced by the whole suite, which carries ~66 known F-018 reds).

---

## Phase 7 — Requirement-10 deliverables

| Deliverable | File |
|---|---|
| Migration plan | `docs/implementation_plan/v3-unified-market-structure-migration-2026-09.md` (phases, gates, rollback boundary, "what activation would additionally require" appendix) |
| Architecture diagram | mermaid, in the migration doc **and** `docs/architecture/bar-structure-snapshot-flow.md`; cross-linked from `docs/architecture/signal-flow.md`. Shows: candle → `parent_feed.push` → `process_candle` (decision path, unchanged) → **emit tap after :2306** → JSONL → parquet projection → attribution, with the decision path and the observation path visually separated |
| Data contract (human) | new section in `docs/reference/schemas.md` |
| Data contract (machine) | `docs/governance/bar_structure_snapshot_schema.json` — field table as JSON Schema; the artifact the schema test validates against |
| Parquet schema | same file, `parquet` block: columns, arrow types, `partition_by`, `FAMILY_DEFAULTS` entry, JSONL-is-authority statement |
| Test strategy | new section in `docs/reference/testing.md` |
| Object specs | `docs/research/bar_structure_snapshot_object.md` (SEM-035), `docs/research/context_attribution_object.md` (SEM-036) |
| MC contract | `configs/research/measurement_contracts/instances/MC-CTXATTR-XAUUSD-M15-V1.json` |
| Research readiness | `docs/research-readiness/context_attribution/mc_ctxattr_xauusd_m15_v1/{population_fingerprint,ledger.jsonl,split_manifest,metrics,report.md,mt00,mt01}` |
| Analysis write-up | `docs/analysis/context-attribution-holdout-2026-09-<dd>.md` |

---

## Sequencing & gates

| # | Phase | Independently verifiable when | Gate to advance |
|---|---|---|---|
| 1 | Config + registration | v3 loads via `get_prod_config`; parity harness byte-identical | parity green, `config_hash` unchanged |
| 2 | Snapshot module + emitter | schema test + neutrality test + SMC bit-identity green | **ledger byte-identical emit-ON vs OFF** |
| 3 | Parquet projection | round-trip + `verify_projection` clean on the full corpus | verify clean |
| 4 | Sealed contract | contract floor-green **before** the driver exists | `test_context_attribution_contract.py` green |
| 5 | Attribution run | metrics + report + mt00/mt01 written; result-log line appended | run executed, artifacts resolve |
| 6 | Governance + F-097 | GREEN_FLOOR green; `validate-completion` PASSes | `construction_protocol.py check` |
| 7 | Docs + diagram | citations resolve; `test_doc_citations.py` green | — |

Phases 1–3 are useful on their own (a governed, decision-neutral per-bar structure stream). Phase 4 seals before Phase 5 runs, per F-083.

---

## Verification (end to end)

```bash
python scripts/analysis/v3_config_parity.py --instrument XAUUSD
```

```bash
python scripts/research/emit_bar_structure_snapshots.py --config v3_unified_market_structure_2026_09 --instrument XAUUSD
```

```bash
python -m research.evidence.context_attribution --out docs/research-readiness/context_attribution/mc_ctxattr_xauusd_m15_v1
```

```bash
python scripts/governance/construction_protocol.py validate-completion docs/governance/build_manifests/CH-v3-unified-market-structure-v1.completion.json
```

```bash
python scripts/maintenance/check_governance_invariants.py --all
```

---

## Risks

- **R1 — power is genuinely thin.** Effective independent n is 941/direction, not 47,157. Across 22 tests, `INSUFFICIENT` is a likely and legitimate outcome (F-094/F-096 precedent). `kill_criteria` says so up front so the result is not quietly re-cut afterward.
- **R2 — `smc_max_window` boundary artifact.** A ~100-bar window manufactures periodicity in every `_present` series. Mitigated by `{f}_window_truncated`, a `forbidden_metric_substitutions` entry, and a `P({f}_present)` vs bar-age plot in the write-up.
- **R3 — duplication with `build_bar_matrix.py`.** It already emits 47,197 × 124 with parent/HTF state and the 48 features. The snapshot's genuine delta is exactly three things: **engine** CRT state (not the resolver), **Zone geometry** (which the tanh scalars discard), and **run-scoped identity**. Everything else is joined, not re-derived. If that delta ever shrinks to zero, extend `build_bar_matrix` instead.
- **R4 — `objective_gate.enabled` is `false`.** `ObjectiveStatus` is *observed*, never *acting*, in the current spine. The attribution program must not describe it as "a gate that exists"; the per-record `objective_gate_enabled` field is what makes that visible in the data rather than only in a docstring.
- **R5 — `context_attribution` has no reader**, so it would read `DEAD` under `test_config_reachability.py` if v3 is ever activated. Give it a reader in Phase 4.
- **R6 — four edits to `backtest_v2.py` is four chances to perturb.** The byte-identical ledger test is the only thing standing between this and a silent behaviour change; it is the gate for Phase 2 and must not be softened.
