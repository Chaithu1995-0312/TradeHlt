# Semantic OS v2 — Slice 1 handoff brief (for the coding LLMs)

**Branch:** `semanticos_impl` · **Spec:** [`docs/governance/SEMANTIC_OS_V2_MEANING_PLANE.md`](../governance/SEMANTIC_OS_V2_MEANING_PLANE.md)
**Authored by:** Claude (design + registries) · **Implemented by:** Grok / DeepSeek · **Reviewed by:** Claude against the concept contracts

## 0. Read first — the rules

1. Implement **only** from the spec, `configs/formulas/concept_contracts.yaml`, the REP shards in
   `configs/formulas/representation_registry/`, and `configs/formulas/terminal_reason_map.yaml`.
   Never infer meaning from a variable name.
2. **Do not edit any existing module's behaviour.** Existing code is called where the contract names
   it as the authority (`structure.predicates`, `features.causal_structure`, `features.smc.*`,
   `config_layer.m15_structural_range`, `config_layer.htf_state`, `config_layer.crt_identity_schema`).
   Copying their logic instead of calling it is a defect (I-8).
3. **Do not fix divergences.** They are listed in each contract's `divergences`. Report any new one;
   do not change engine, pipeline or config behaviour.
4. **Do not invent ids or names** (concept ids, FM ids, F-ids, SPP ids beyond §4 below). Ask.
5. **Never bind a representation or consumer to a PROPOSED concept** (GP-07, MKT-Z06, MKT-E03,
   MKT-C02; values `FILLED`, `once_per_level`).
6. **Never delete** code, data or rules — mark DEPRECATED. No `git add -A` (concurrent sessions);
   stage explicit paths. No shell heredocs to write files.
7. Acceptance is **contract compliance** (tests below). Existing code is NOT a parity oracle (user
   decision O-1).
8. Return each deliverable with: files changed, test output, and any new divergence found.

## 1. Draft skeleton (optional starting point)

Claude left an **uncommitted, untested** draft in the working tree of `semanticos_impl`:
`src/semantics/{__init__,types,identity,geometry}.py`, `src/semantics/market/{__init__,levels,conditions,events}.py`.
You may adopt, rewrite or discard it. If you keep any of it, you own its tests.
Known draft issues: the module docstrings name SPP-005…009 before they exist (§4).

## 2. Package to build — `src/semantics/`

| Module | Implements | Must call (do not copy) |
|---|---|---|
| `types.py` | Layer, Kind, ContractStatus, Evidence, Side, Bias, LevelStatus, ZoneStatus, TerminalAuthority, TerminalClass, `Bar` protocol | — |
| `identity.py` | SemanticIdentity, `parameterization_id(concept_id, params, identity_bearing)`, RepresentationIdentity, InstanceKey, `instance_id` (no producer in instance identity) | `config_layer.crt_identity_schema.derive_constructor_id` |
| `geometry.py` | GP-01…GP-06 exactly as the §4 table of the spec (UPPER/LOWER) | GP-04 `structure.predicates.swept_high/low`; GP-05 `features.smc._geometry.is_mitigated`; GP-06 `structure.predicates.directional_impulse` |
| `market/levels.py` | MKT-L01 constructors: `swing_pivot(k)` (available_at = pivot + k), range edges, `prior_day` (declared clock), `equal_cluster`; MKT-L02 retracement / extension / equilibrium / candle_extreme with `anchor` | `features.causal_structure.causal_structure_series`, `features.smc._geometry.collect_causal_swings`, `features.smc.levels._nearest_equal_cluster`, `config_layer.m15_structural_range` |
| `market/zones.py` | MKT-Z01…Z05 typed zones; lifecycle ACTIVE → TOUCHED → BROKEN / FLIPPED; explicit `present` flag (I-7); `available_at` (FVG = close of bar i+1) | `features.smc.fvg._find_fvg_events`, `features.smc.order_block._find_break_events` / `_origin_candle`, `features.smc.breaker.find_active_breaker`, `features.smc.mitigation.find_active_mitigation_block` |
| `market/events.py` | MKT-E01 sweep (GP-04, strict, `founding` param, `implied_bias`); MKT-E02 structure_break = onset of a MKT-C01 change; MKT-E06/E07; MKT-E08 level_pierce; MKT-E10 retrace_breach; MKT-E11 extension_reach; MKT-E12 clock_rollover | — |
| `market/conditions.py` | MKT-C01 structural_position (UNDEFINED when no confirmed swing — never 0); MKT-C04 two_sided_sweep{k, W}; MKT-C07 break_against_momentum | `features.causal_structure.causal_structure_series`; `features.smc.choch.change_of_character` |
| `market/episodes.py` | MKT-P01 projection over a run-scoped `events.jsonl`: episodes (instance key = run_id + first non-AWAITING stage bar), stages with dwell, `Termination{authority, class, reason_code, legacy_reason}` via `terminal_reason_map.yaml` (longest match wins; unmatched = error); EXECUTION/RESOLUTION on a separate position track; series flags `policy_shaped` / `observation_shaped` / `producer_shaped` | — (reads the file; never re-runs or edits the engine) |
| `registry.py` | Loader + validator for the three registries (§3) | YAML/path style of `src/governance/semantic_os.py` |

Every value object carries its `concept_id`, `parameterization_id` and `available_at`. Absence is
`None` or `present=False`, never a sentinel.

## 3. Validator (`src/semantics/registry.py`) — required checks

| # | Check | Invariant |
|---|---|---|
| V-1 | Concept ids unique; required fields present for every record | — |
| V-2 | ACCEPTED: `authority.evidence` ⊆ {REPO, USER_DECISION}, non-empty, and every `authority.sources` path is **git-tracked** (`git ls-files`) | ACCEPTED definition |
| V-3 | Every `inputs` id exists and its layer rank ≤ the record's layer rank | I-12 |
| V-4 | Every parameter has `identity_bearing` | I-17 |
| V-5 | Kind MEASUREMENT → `units.unit` and `units.normalization_basis` present | I-4 |
| V-6 | Every REP record's `concept_id` exists; no REP points at a PROPOSED concept | I-18 |
| V-7 | A REP parameter value outside the contract `domain` is allowed only if listed in `legacy_values` AND the REP carries `divergence_ref` | I-2 |
| V-8 | REP identity tuples (concept, parameterization, producer, encoding, schema_version) unique across shards | identity |
| V-9 | `feature_pipeline.yaml`: every `CANONICAL_FEATURES` slot appears exactly once (representations ∪ raw_observations ∪ unmapped), and `slot` indices match | coverage |
| V-10 | `crt_engine.yaml` covers every `CRTState` member; `parent_crt.yaml` covers every `HTFState` and `ObjectiveStatus` member | coverage |
| V-11 | `unmapped` lists are shrink-only: pin today's lists in the test; a new entry fails | ratchet |
| V-12 | AST scan: every string literal / f-string leading literal passed as the reason argument of `reset_to_range(...)` in `src/config_layer/crt_engine_v2.py` and `src/runtime/backtest_v2.py`, and every reason string returned by `ResetLogic.should_reset`, matches a `terminal_reason_map.yaml` entry. Variables passed through (e.g. `reset_reason`, `gap_reason`) are traced to their literal source or listed explicitly | I-3 |

## 4. Founding profiles to add (meaning fixed here; you do the mechanics)

Add to `configs/formulas/structure_profiles.yaml` and update `tests/test_structural_profiles.py`
(`_SEED_IDS`, the four-founding test, the status test) in the same change:

| id | key | founding.name | founding.object | status | evidence |
|---|---|---|---|---|---|
| SPP-005 | swing_pivot | Confirmed swing pivot (k-delayed, FC1-A) | `src/features/causal_structure.py` | registered | F-051, FM-057 |
| SPP-006 | prior_day | Previous broker-day high/low (declared clock, F-066) | `src/features/smc/levels.py` | registered | F-076, F-066 |
| SPP-007 | equal_cluster | Equal highs/lows within tolerance·ATR | `src/features/smc/levels.py` | registered | F-076 |
| SPP-008 | mother_range | Frozen t=0 mother range (SEM-026) | locate the authority before writing; else `UNKNOWN` | research | F-090 |
| SPP-009 | htf_range_resolver | Resolver HTF range sweep reference | `src/features/crt_state_resolver.py` | research | F-069 |

`founding.identity`, `walk`, `predicates`, `threshold_refs` must be declared ontology ids/names or
`UNKNOWN` (the validator rejects invented ids). Verify every path with `git ls-files`.

## 5. Tests — `tests/semantics/` (+ registry floors in `tests/governance/`)

| File | Must prove |
|---|---|
| `tests/semantics/test_geometry.py` | Equality table: `high == L` not PIERCE; `close == L` not BEYOND, is REACH, not GP-04; zero-range bar; gap bar; LOWER mirrors |
| `tests/semantics/test_identity.py` | W=5 vs W=10 → different `parameterization_id`; change of a non-identity setting → same id; producer changes REP id, not instance id; missing identity-bearing param raises |
| `tests/semantics/test_events_conditions.py` | I-1: structure_break fires once per onset while structural_position persists (property over generated paths); sweep strict tie; no sweep against a level whose `available_at` is in the future |
| `tests/semantics/test_availability.py` | I-6 prefix invariance: values at bar t unchanged when future bars are appended (levels, conditions, events, zones) |
| `tests/semantics/test_absence.py` | I-7: no zone vs price exactly on the zone edge are distinguishable; no swing yet → UNDEFINED, not INSIDE |
| `tests/semantics/test_episode_projection.py` | Synthetic event rows → stages, dwell, terminal authority; unknown reason raises; longest-match rule; EXECUTION on the position track |
| `tests/governance/test_concept_contracts.py` | V-1…V-5 + mutation cases (PROPOSED with a REP; higher-layer input; untracked source) |
| `tests/governance/test_representation_registry.py` | V-6…V-11 + mutation cases |
| `tests/governance/test_terminal_reason_map.py` | V-12 + mutation case (delete an entry → fails) |
| optional, marker `measurement` | Project `results/xau_full_trace/run_20260930_163142*/XAUUSD_events.jsonl`; expect 0 unmapped and MARKET/EXPIRED 2,467 · FAILED 166 · SPENT 109 · OBSERVATION 121 · DECISION 20 · EXECUTION 4 |

## 6. Floor wiring

In `scripts/maintenance/check_governance_invariants.py`: add `src/semantics/`,
`configs/formulas/concept_contracts.yaml`, `configs/formulas/representation_registry/`,
`configs/formulas/terminal_reason_map.yaml` to `GOVERNED_PREFIXES`, and `tests/semantics/` to
`GREEN_FLOOR`. Run the floor under `venv/Scripts/python.exe` (the hook's bare Python 3.14 lacks
`jsonschema`); 7 reds pre-exist on this branch (schema-version census, model-path literals ×3,
script-registry grandfather ×2, corpus-read lint) — report, do not fix.

## 7. Out of scope

Trading / Decision-Execution layers · grounding extension · L3 v2.0.0 · ontology scope v2 · any
change to engine, pipeline, live rail or production config.

## 8. Done means

All §5 tests green under the venv; no new green-floor reds; `git diff --stat` shows no change to any
pre-existing `src/` module except the §6 path lists; each new divergence reported with file:line.
