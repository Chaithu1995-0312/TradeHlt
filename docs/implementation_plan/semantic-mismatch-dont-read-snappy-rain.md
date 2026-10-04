# Semantic OS v2: slice 1 (foundation + market core) on branch `semanticos_impl`

## Context
Over several rounds of discussion we designed, reviewed and froze Ontology v2: a meaning plane for the
existing Semantic OS.

- **Chain:** geometry primitives → market → trading → decision/execution, with concept contracts,
  a representation (REP) registry, an identity contract, five terminal authorities and invariants I-1…I-19.
- **User decisions (2026-10-02):**
  - Do **not** use existing code as a parity or measurement oracle; several of its parts are broken.
  - Start fresh on a new branch, `semanticos_impl`, and **reuse existing implementation where its
    meaning matches the contract** (memory: reuse when semantics match; a re-implemented copy is the defect).
  - Commit the F-111 work first.
  - The first slice is foundation plus market core.
- **Acceptance is contract compliance:** property tests, boundary tables and registry floors.
- **Existing modules are called, never edited**, so production behaviour cannot change by construction.

### Decisions recorded as defaults (from the final review)
| Id | Decision |
|---|---|
| O-1 | Phase A/B parity requirement is **dropped** by the user. Acceptance is contract compliance only |
| O-2 | File name `concept_contracts.yaml`; the term is "concept contract" (Semantic OS `CT-*` keeps "contract") |
| O-3 | Concept contracts carry meaning authority (§6.6). No runtime authority |
| O-4 | TTL expiry → `terminal_authority = PRODUCER` |
| O-5 | Claude implements this slice |
| O-6 | L3 v2.0.0 and ontology scope v2 are separate change ids, both **deferred** (this slice touches neither L3 storage nor `market_ontology.yaml`) |

**Correction found while planning:** GP-07 IN_BAND is **PROPOSED**, not ACCEPTED.
- `src/structure/predicates.py:33` says SP-003 has no implementation ("definition DEFERRED on OQ7").
- The only band logic is the pipeline's internal `retest_flag` (`feature_pipeline.py:1025-1035`).

## Step 0: Commit F-111, then branch
1. On `grokbotchanges`, stage **explicit paths only**. Never `git add -A`; concurrent sessions are active.
   - Files: `CLAUDE.md`, `assistant_project.md`, `configs/production/v2_htfcrt_2026_08.json`,
     `docs/current-findings.md`, `docs/governance/research_family_registry.json`,
     `src/governance/multi_strategy_validator.py`, `docs/governance/config_unit_registry.json`,
     `tests/governance/test_config_semantic_invariants.py`,
     `docs/implementation_plan/semantic-mismatch-dont-read-snappy-rain.md`.
   - Leave alone: `.claude/settings.local.json`, `ic-003-shape-narratives.md`, other plan docs, logs,
     `report.json`, `scratch_run_logs/` (other sessions' work).
2. Commit message "F-111: declare config units, live risk 1%, drawdown 75k INR", with the Co-Authored-By line.
   The pre-commit hook runs the green floor; capture the failure baseline first. The same-day session log exists.
3. `git switch -c semanticos_impl`.

## Step 1: Architecture record (docs)
- **New file `docs/governance/SEMANTIC_OS_V2_MEANING_PLANE.md`:** the frozen spec from the final handoff.
  Planes, layers and types with must-not rules, the identity contract, the concept-contract template and
  ACCEPTED definition, REP sharding, terminal authority, I-1…I-19, the catalog, mapping dispositions,
  deferred governance (L3 v2.0.0, ontology scope v2), and the O-1…O-6 decisions.
- **Pointer section** in the existing `docs/governance/SEMANTIC_OS_CONTRACT.md` (existing-doc-first;
  the charter owns the Semantic OS).

## Step 2: Registries (`configs/formulas/`, all new)
- **`concept_contracts.yaml`.** One record per concept id, using the template (definition, layer, kind,
  identity, parameterization with `identity_bearing`, inputs, rule, units, availability, lifecycle,
  absence, representation, authority{status, evidence, sources[], lineage}, consumers, divergences, version).
  - Slice-1 records: GP-01…07 (GP-07 PROPOSED); MKT-L01, L02; Z01–Z05 (Z06 + FILLED PROPOSED);
    E01, E02, E06–E08, E10–E12 (E03 `choch` PROPOSED); C01, C03, C04, C07 (C02 PROPOSED); P01 + stages.
  - Divergences seeded from this session's evidence:
    - FM-058 inclusive tie (0.40%)
    - engine `double_confirmed` dead
    - `feature_pipeline.py:281` W comment
    - `expansion_min_range_ratio` inert
    - `tp*_atr_multiplier` actually means R
    - FM-083 uses EMA rather than structure
    - BOS re-fires on every bar beyond the level
- **`representation_registry/` shards:**
  - `feature_pipeline.yaml`: the structure, sweep and SMC slots of `CANONICAL_FEATURES`.
  - `crt_engine.yaml`: CRTState members, `SweepEvent`, events.jsonl RESET.
  - `parent_crt.yaml`: HTFState, ObjectiveStatus.
  - Unmapped canonical slots are listed in a **shrink-only ratchet**, not silently skipped.
- **`terminal_reason_map.yaml`.** Each legacy reset reason (literal or prefix) maps to
  `{terminal_authority, terminal_class, reason_code}`.
  - Covers the 18 `reset_to_range` sites (`crt_engine_v2.py`) and the `should_reset` reasons (`:2866-2923`).
  - Examples: HTF changed → MARKET/EXPIRED; 50% retrace → MARKET/FAILED; 1.618 → MARKET/SPENT;
    session gap → OBSERVATION; TTL / `Sweep expired` / `expansion_ttl_exceeded` → PRODUCER;
    `resolver_founding*` → PRODUCER; off-session, parent bias, soft-confirmation, low score,
    discount/premium → DECISION/FILTERED; post-resolution and `trade_build_rejected:*` → EXECUTION.
- **`structure_profiles.yaml` (additive):** five new founding profiles: `swing_pivot`, `prior_day`,
  `equal_cluster`, `mother_range`, `htf_range_resolver`.

## Step 3: Validator: `src/semantics/registry.py`
Loads and validates the registries. Reuses the YAML / repo-path patterns in
`src/governance/semantic_os.py` (`_resolve_repo_path`, the loader style).

| Check | Invariant |
|---|---|
| Unique concept ids; required fields by status | — |
| ACCEPTED `authority.sources` resolve to **git-tracked** paths (same rule as `test_findings_evidence_paths_resolve`) | — |
| `inputs` reference only the same or lower layer | I-12 |
| PROPOSED → 0 REPs and 0 consumers | I-18 |
| Every MEASUREMENT has units + normalisation basis | I-4 |
| Every parameter declares `identity_bearing` | I-17 |
| Every REP resolves to exactly one concept; REP identity tuples unique across shards | I-2 / identity |
| Every `reset_to_range` / `should_reset` reason literal in `crt_engine_v2.py` (AST scan) has a map entry | I-3 |

**Floor tests**, which ride the existing `tests/governance/` GREEN_FLOOR entry:
`tests/governance/test_concept_contracts.py`, `test_representation_registry.py`,
`test_terminal_reason_map.py`.

## Step 4: Runtime package `src/semantics/` (new; existing modules untouched)
| Module | Contents | Reuse (call, don't copy) |
|---|---|---|
| `identity.py` | `SemanticIdentity`, `parameterization_id()` (sha256 of canonical JSON of identity-bearing params), `InstanceKey`. Producer is part of REP identity only | Same canonicalisation as `crt_identity_schema.derive_constructor_id` (`src/config_layer/crt_identity_schema.py:451`) |
| `geometry.py` | GP-01 PIERCE (`>`), GP-02 BEYOND (`>`), GP-03 REACH (`>=`), GP-04 PIERCE_AND_REJECT, GP-05 OVERLAP (inclusive), GP-06 DIRECTIONAL_IMPULSE. Upper and lower variants. GP-07 not implemented (PROPOSED) | GP-04 = `structure.predicates.swept_high/low`; GP-06 = `predicates.directional_impulse`; GP-05 matches `features.smc._geometry.is_mitigated` |
| `market/levels.py` | Frozen `Level` (price, side, founding, timeframe, clock, formed_at, available_at, status). Constructors for `swing_pivot(k)`, `m15_structural_range`, `prior_day`, `equal_cluster`; `derived_level` (retracement, extension, candle_extreme, equilibrium) | `features.causal_structure.causal_structure_series` (swings, k-delay), `config_layer.m15_structural_range`, `features.smc.levels` |
| `market/zones.py` | Typed zones with lifecycle ACTIVE → TOUCHED → BROKEN → FLIPPED; explicit `present` (I-7) | `features.smc.fvg/_find_fvg_events`, `order_block._find_break_events`/`find_active_order_block`, `breaker`, `mitigation` |
| `market/events.py` | `sweep(level, bar)` (GP-04, strict, founding parameter); `structure_break` = **onset** of a `structural_position` change (`consumption=onset`; `once_per_level` PROPOSED, not built); `level_pierce`; `retrace_breach`; `extension_reach`; `clock_rollover` | — |
| `market/conditions.py` | `structural_position`; `two_sided_sweep{W}` (W identity-bearing); `momentum_bias`; `break_against_momentum` | `causal_structure` BOS; `features.smc.choch.change_of_character` |
| `market/episodes.py` | CRT episode **projection** over a run-scoped `events.jsonl` (STATE_TRANSITION + RESET). Produces `Episode` (instance key = run_id + sweep bar), stages with dwell, and `Termination{authority, class, reason_code, legacy_reason}` via `terminal_reason_map.yaml`. EXECUTION/RESOLUTION go to a separate position track. A `policy_shaped` / `observation_shaped` flag supports I-3a | Engine output as-is; no engine re-run, no engine edit |

**Common rules for every value object:**
- It carries `available_at` (I-6).
- Absence is `present=False` or `None`, never a sentinel (I-7).
- It records its concept id and `parameterization_id`.

**Floor wiring:**
- Add `src/semantics/` and the three new YAML paths to `GOVERNED_PREFIXES`.
- Add `tests/semantics/` to `GREEN_FLOOR` (`scripts/maintenance/check_governance_invariants.py:36,86`).

## Step 5: Tests (`tests/semantics/`, contract and property based)
- **`test_geometry.py`:** the equality and boundary table (`high==L`, `close==L`, zero-range bar, gap bar).
- **`test_identity.py`:**
  - W=5 vs W=10 → different `parameterization_id`.
  - A change to a non-identity setting → same id.
  - The producer changes the REP id, not the instance id.
- **`test_events_conditions.py` (I-1):**
  - `structure_break` fires only at onset.
  - `structural_position` persists.
  - Sweep tie is strict (close == L is not a sweep).
- **`test_availability.py` (I-6):** prefix invariance on synthetic series. A value at t is unchanged when
  future bars are appended.
- **`test_absence.py` (I-7):** no zone vs price exactly at the edge are distinguishable.
- **`test_episode_projection.py`:** synthetic event rows → stages, dwell, terminal authority. Unknown reason
  strings raise.
- **Optional real-corpus smoke**, marked `measurement` (skipped by default per the repo test policy):
  project the active-config trace (`results/xau_full_trace/...`) and check that every reason is mapped.

## Step 6: Repo obligations
- Construction Protocol:
  - Classify against `docs/governance/change_contracts.json`.
  - Write a BUILD_IMPACT_MANIFEST.
  - Run `scripts/governance/construction_protocol.py validate-completion <manifest>`.
- Session-log entries in `assistant_project.md`.
- No findings: no conclusion changes.
- Commit on `semanticos_impl` with explicit paths only.

## Out of scope (next slices)
- Trading layer: thesis, objective, invalidation, entry, stop, target, cost, outcome. Decision/Execution layer.
- Grounding `--kind CONCEPT / REPRESENTATION`.
- L3 v2.0.0 reopen; `market_ontology.yaml` scope v2.
- Any edit to existing engine, pipeline or config behaviour (Phase B alignment).

## Verification
1. `venv/Scripts/python.exe -m pytest tests/semantics tests/governance/test_concept_contracts.py tests/governance/test_representation_registry.py tests/governance/test_terminal_reason_map.py -v`
2. `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all`. No new reds against the
   baseline captured in step 0.
3. Mutation checks in a temp copy:
   - Give a PROPOSED concept a REP → I-18 fails.
   - Delete a reason-map entry → the AST coverage check fails.
   - Make an input reference a higher layer → I-12 fails.
4. Scratchpad demo: project the active-config XAUUSD trace into episodes and print the counts by
   terminal authority (expect MARKET/EXPIRED to dominate SWEEP exits, about 74%).
5. `git status` shows no edits to existing `src/` modules other than `check_governance_invariants.py` path lists.
