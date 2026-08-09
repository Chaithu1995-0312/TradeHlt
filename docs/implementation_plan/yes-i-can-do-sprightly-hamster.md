# Tradelatest Semantic OS v2 — Build 1 (L1 + L5 + L6)

## Context

The repo already has a Canonical Book (26 chapters), a Repository Encyclopedia (813 rows + JSONL twin),
a market ontology (54 `FM-*` nodes with full epistemic blocks), MIAR (17 model-intent entries), a Closure
& Authority Index (11 surfaces), and ~250 governance artifacts. What it does **not** have is a way to
*reason across them*. Today an agent can find `feature_pipeline.py`; it cannot answer "who owns ATR
normalization", "what guarantees no lookahead", or "what breaks if I change this."

Three concrete gaps, verified against source:

1. **No concept layer.** Nothing enumerates Market→Feature→State→Engine→Decision→Execution→Risk→
   Research→Governance as first-class nodes. The two closest — MIAR's 7 `stages` and the closure index's
   11 `surfaces` — use different, unreconciled vocabularies and answer different questions.
2. **No cross-surface query.** `scripts/governance/feature_surface_query.py` is exactly the right
   pattern (evidence-classed, fail-closed on ambiguity, freshness from embedded `generated_at`) but joins
   only the *feature* surface.
3. **Impact is declared, never computed.** `construction_protocol.py validate-completion` diffs a
   *human-written* manifest against `git status`. Nothing computes blast radius, even though every input
   exists: `graph.dot` (696 edges), `config-consumer-graph.generated.json` (763 nodes / 1,295 edges),
   `build_lineage_graph()`, `citation-map.generated.md`, findings `evidence_paths`.

**Outcome:** an advisory, queryable semantic layer that answers *why / who owns / what breaks* by
traversing relationships — built by **joining and computing** from existing authorities, never by
duplicating them.

### The rule that shapes everything

> Hand-author **only** what code cannot answer: why it exists, what invariant must never break, why this
> design, why alternatives were rejected, which finding justifies it.
> Imports, dependencies, callers, package, ownership, size, tests, reachability, runtime path — **generated**.

This is mechanically enforced (validator #14, `_FORBIDDEN_HAND_FIELDS`), not merely stated.

### Four entities

| Entity | Count | Source | Notes |
|---|---|---|---|
| **Concepts** `CN-###` | ~50 | HAND | Stable meaning. *References* MIAR/closure/ontology/book/findings; owns none of them. |
| **Boundaries** `BD-###` | ~40 | HAND | Architectural seams, **not files**. Owner + member globs + consumers + the invariant protected. Survives implementation churn. |
| **Journeys** `JN-###` | 4–8 | HAND | Ordered semantic paths across concepts. Machine twin of `signal-flow.md`. |
| **Objects** `OBJ:<path>` | 844 | **100% GENERATED** | Zero manual maintenance. Every field computed + evidence-classed. |

**Evidence is not a new registry** — it joins `data/findings.jsonl` (70), `data/hypothesis_registry.jsonl`
(18), `data/framework_registry.jsonl` (41), and pytest discovery.

### Decisions taken (do not re-litigate)

- **Granularity:** concept + boundary contracts hand-authored; ~844 objects fully generated.
- **Vocabulary:** new axis *above* MIAR and Closure, joined by validated FKs. Neither is edited.
- **Scope:** L1 + L5 + L6. L2/L3/L4 are projections of L1, not separate work.
- **Enforcement:** guard tests on GREEN_FLOOR; validation is **graph integrity**, not file presence.
- **Authority:** `authority: "advisory"` pinned on every record (§6.5). Grants **zero** production authority.
- **Untracked inputs:** targeted `git add` of the 6 artifacts (Phase 0).
- **Change class:** reuse `SCRIPT_LIFECYCLE_CHANGE` + `DOCUMENTATION_ONLY`; file the
  `GOVERNANCE_REGISTRY_ADDITION` gap as a follow-up.
- **Import graph:** add an AST import census for `scripts/` + `tests/` + root in build 1.

---

## Verified facts this plan rests on

| Claim | Verified |
|---|---|
| `graph.dot` is `src/`-only | 696 `->` edges, dotted module names, **0** `scripts`/`tests` nodes |
| Code universe on disk | 472 src + 351 scripts + 21 root = **844**; tests 411 (→ 1,255 with `--universe all`) |
| Encyclopedia denominator is stale | 813 rows vs 844 on disk — 38 src + 21 root missing, 0 tests |
| `module_attribution` ownership is empty | `owner_surface` = `UNATTRIBUTED` on **463/463**; `regime` populated (RESEARCH 180 / PLATFORM 90 / SUBSTRATE 56 / DECISION 55 / TERMINAL 51 / MODEL_LINEAGE 31) |
| 6 inputs untracked | `encyclopedia_rows.jsonl`, `module_attribution_stubs.jsonl`, `config-consumer-graph.generated.json`, `miar_registry.json`, `closure_authority_index.json`, `change_contracts.json` — all UNTRACKED, **not** ignored. `graph.dot` + `citation-map.generated.md` are TRACKED. |
| Citation map recall is low | 20 rows / 18 symbols, several stored as bare basenames → HEURISTIC only |

---

## File inventory

### Committed PRIMARY (hand-authored truth)

| Path | Role |
|---|---|
| `docs/governance/semantic_os/concepts.yaml` | ~50 Concept records |
| `docs/governance/semantic_os/boundaries.yaml` | ~40 Boundary records |
| `docs/governance/semantic_os/journeys.yaml` | 4–8 Journey records |
| `docs/governance/SEMANTIC_OS_CONTRACT.md` | Charter — mirrors `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md` |
| `docs/governance/build_manifests/CH-semantic-os-v2.{impact,completion}.json` | §3.3b entry/exit |

YAML (not JSONL) because prose fields need block scalars; precedent is `configs/formulas/market_ontology.yaml`.
Under `docs/` because `.gitignore` line 2 ignores `data`.

### Logic — `src/` (committed)

| Path | Role |
|---|---|
| `src/governance/semantic_os.py` | Enums, `_REQUIRED_FIELDS` per kind, `ValidationError`, `validate_record`, `SemanticOSRegistry`, `dump`, all 14 graph validators. **Mirrors `src/governance/framework_registry.py` shape exactly.** |
| `src/governance/semantic_objects.py` | `discover_universe()`, `ast_import_census()`, `build_objects()`, `ObjectIndex`, `FIELD_EVIDENCE_CLASS`, `coverage_report()` |
| `src/governance/semantic_query.py` | **L5.** `SemanticIndex`, `Answer`, `QUESTION_REGISTRY`, `AmbiguousAliasError` |
| `src/governance/semantic_impact.py` | **L6.** `blast_radius()`, `required_checks_for()`, `draft_impact_manifest()` |

PR-6 pattern (`src/governance/script_seed.py`): logic in `src/`, thin CLI in `scripts/`, so tests import
it without `spec_from_file_location`.

### Thin CLIs — `scripts/` (committed, **SITS-registered same turn**)

| Path | Role |
|---|---|
| `scripts/governance/seed_semantic_os.py` | Write path → `data/semantic_os/*.jsonl` via `SemanticOSRegistry.dump()`, pinned `_TS` |
| `scripts/governance/query_semantic_os.py` | Read path — L5 + L6 + `--validate` |

Two scripts only, to minimise SITS surface. Named `query_semantic_os.py` (not `semantic_os.py`) to avoid
shadowing `src/governance/semantic_os.py` under `pythonpath = ["src","scripts","."]`.

### Tests (committed)

`tests/test_semantic_os.py` · `test_semantic_os_objects.py` · `test_semantic_query.py` ·
`test_semantic_impact.py` — each with an autouse module-scoped reseed fixture copied from
`tests/test_framework_registry.py:30-36` (because `data/` is gitignored).

### Generated projection (gitignored, disposable)

`data/semantic_os/{concepts,boundaries,journeys,objects}.jsonl` + `index_meta.json`

### Modified

| Path | Change |
|---|---|
| `scripts/maintenance/check_governance_invariants.py:69` | +4 GREEN_FLOOR targets; +6 `GOVERNED_FILES` |
| `tests/test_governance_invariant_check.py` | pin the new GREEN_FLOOR members |
| `docs/reference/schemas.md` | new §9.10 Concept · §9.11 Boundary · §9.12 Journey · §9.13 Object, in the §9.9 TypedDict-literal style |
| `docs/governance/script_registry_stubs.jsonl` | regenerated |
| `scripts/governance/seed_script_registry.py` | 2 real `purpose` OVERLAYs (never `GRANDFATHER_UNCLASSIFIED`) |
| `docs/reference/script-matrix.md` | regenerated |
| `assistant_project.md` | SESSION LOG entry (§7.4) |

**Not touched:** no `src/` runtime path, no `configs/`, no `models/`, no `active_models.yaml`.
`PRODUCTION_BEHAVIOR_CHANGED = NO`.

### ID namespaces

`CN-###` · `BD-###` · `JN-###` · `JN-###.S##` (steps) · `OBJ:<posix-path>` (objects).

Two-letter + zero-padded matches every existing namespace (`FM-`, `SEM-`, `UNK-`, `RC-`, `IND-`, `MOD-`,
`SCR-`, `F-`, `H-`); none of CN/BD/JN collides. **Objects deliberately break the pattern** — a sequential
`OBJ-0001` needs a pinned allocation ledger (exactly why `module_attribution_stubs.jsonl` exists), which
reintroduces the maintenance the user's contract forbids. `OBJ:<path>` is stable by construction, is the
natural join key against every artifact (they all key on path), and follows the repo's own precedent in
`config-consumer-graph.generated.json` (`file:<path>`, `cfg:<section>.<key>`).

---

## Record schemas

Legend: **H** hand-authored (required in YAML) · **C** computed at seed (pinned) · **D** derived at query
time (**forbidden in the YAML source**).

### Concept `CN-###`

- **Identity (H):** `id`, `name`, `aliases`, `status` (ACTIVE|PROPOSED|SUPERSEDED|RETIRED),
  `supersedes`, `superseded_by`; `authority: "advisory"` (**C**, pinned literal).
- **Intent (H):** `why_it_exists`, `problem_it_solves`, `explicit_non_goals` (vocabulary borrowed from
  `miar_registry.entries[]`).
- **Authority — references only (H):** `miar_stage` (FK→7 stages), `miar_entry` (FK→entries[].id),
  `closure_surface_id` (FK→11 surfaces), `ontology_ids` (FK→`FM-*`/`SEM-*`/`UNK-*`/`RC-*`/`IND-*`),
  `owner_boundary` (FK→exactly one BD), `related_boundaries`, `canonical_source` (one repo path).
- **Contracts (H):** `invariants`, `preconditions`, `postconditions`,
  `assumptions[] {assumption, falsified_by: F-NNN|null, status: HOLDS|FALSIFIED|UNTESTED}`.
- **Behavior (H):** `behavior`, `failure_modes[] {mode, symptom, detection, finding}` — `mode` is the FK
  target for journey steps.
- **Reasoning (H):** `why_this_design`, `alternatives_rejected[] {alternative, why_rejected, evidence}`,
  `research_findings` (FK→F-NNN), `hypotheses` (FK→H-NNN), `framework_ids`.
- **LLM (H):** `summary_50` (≤320 chars, enforced), `summary_200` (≤1400), `retrieval_keywords`,
  `semantic_tags` (closed vocabulary in the charter).
- **Doc anchors (H):** `book_chapter` (must exist **and** be in `docs/book/README.md` TOC), `topic_doc`,
  `intent_chain`, `intent_domain_doc`, `related_concepts`, `orphan_justification`.
- **C:** `created`, `last_validated` (pinned `_TS`), `schema_version: "semantic_os/1"`.

**`_FORBIDDEN_HAND_FIELDS` (D — schema violation if present in YAML):** `objects`, `modules`,
`authoritative_modules`, `tests`, `config_keys`, `consumers`, `dependencies`, `imports`, `reachability`,
`book_status`, `citations`, `bytes`, `package`, `owner_surface`, `evidence_count`, `journey_steps`,
`entry_points`, `blast_radius`. *This list is the hand-author rule, mechanised.*

### Boundary `BD-###`

- **H:** `id`, `name` (e.g. "Feature Production"), `kind`
  (PRODUCTION|POLICY|AUTHORITY|TRANSPORT|STORAGE|OBSERVATION), `status`, `authority_layer` (WHAT|HOW|WHO —
  vocabulary from `WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json`).
- **H:** `owner` (one repo path), `owner_symbol` (validated with the ±30-line drift window),
  `members` (**globs** and/or explicit paths), `members_exclude`, `consumers` (BD-ids and/or paths).
- **H, required non-empty:** `invariant_protected`, `invariant_violation_symptom`.
- **H:** `contract {inputs, outputs, guarantees, non_guarantees, enforced_by_tests}`.
- **H:** `concepts` (FK→CN, bidirectionally enforced), `closure_surface_id`, `miar_stage`,
  `change_classes` (FK→`change_contracts.json` keys — **the root of L6's `required_checks`**),
  `evidence[] {path, symbol, line, type}`, `findings`, `why_this_boundary`.
- **D:** `members_resolved`, `member_count`, `import_fan_in/out`, `cross_boundary_imports`,
  `config_keys_read`, `test_files`, `uncovered_members`, `orphan_members`.

A boundary is **not a file list you maintain** — you maintain the glob and the invariant. Renaming a module
inside `src/features/` changes nothing; a glob matching zero files is a validation error. That is the
churn-survival property.

### Journey `JN-###`

- **H:** `id`, `name`, `kind` (RUNTIME|RESEARCH|GOVERNANCE|AGENT|CONFIG), `status`, `source_doc`
  (the prose ancestor), `trigger`, `terminal_outcomes`, `why_this_path`.
- **H `steps[]`:** `step_id` (`JN-001.S03`), `order` (1..N contiguous), `name`, `concept` (FK, required),
  `boundary` (FK, required — must be the concept's `owner_boundary` or in `related_boundaries`),
  `failure_mode` (**FK into that concept's own `failure_modes[].mode`**), `on_failure`
  (HALT|SKIP|DEGRADE|REJECT|FALLBACK), `next[]` (branches allowed), `evidence {path, anchor}`.
- **H `async_feeders[]`:** `{name, joins_at_step, kind}` — the 4 from `signal-flow.md` §2.
- **D:** `objects_traversed`, `config_keys_on_path`, `required_checks_union`, `invariants_on_path`.

`failure_mode` being an FK into the concept's declared modes is what stops journeys degenerating into
free-text narrative.

---

## The generated Object layer

**Universe = disk enumeration** (`--universe code` default = 844; `--universe all` adds tests = 1,255).
Artifacts are *enrichments*, never the denominator — denominator drift is precisely why
`test_module_attribution.py` enforces enumeration HARD. Every object carries
`present_in: ["encyclopedia","module_attribution","script_registry"]` plus a top-level `coverage_gaps`
block recording the measured 38 / 21 / 9 / 411 deltas.

| Field | Source | evidence_class |
|---|---|---|
| `id`, `path`, `kind` | disk `rglob`, POSIX-normalised | PROVEN |
| `bytes`, `sha256` | recomputed from disk (**not** read from encyclopedia — its `bytes` is a snapshot) | PROVEN |
| `package` | path → dotted, `src.` stripped (mirrors `gen_code_map._pkg`) | PROVEN |
| `classes`, `functions`, `has_main` | `ast.parse` top-level defs | PROVEN |
| `purpose` | encyclopedia `purpose`, else docstring line 1, + explicit `purpose_source` | TEXT_REFERENCE |
| `relevance`, `phase`, `group`, `book_status` | encyclopedia | HEURISTIC (curated classification) |
| `imports` / `consumers` | `graph.dot` fwd/rev edges (src/) **+ `ast_import_census()`** (scripts/tests/root) | PROVEN |
| `graph_reachable_from` | BFS from declared entry points | PROVEN — *reachability ≠ "runs in production"* |
| `owner_boundary` | `boundaries.yaml` glob resolution | PROVEN |
| `owner_surface` | `module_attribution.owner_surface` | **`UNATTRIBUTED` on 463/463 — emitted verbatim, never guessed** |
| `regime`, `reachability_declared` | module_attribution | HEURISTIC (stub notes say "regime is a package heuristic"; reachability all UNKNOWN) |
| `config_keys` | config-consumer-graph edges + per-key `verdict` from `config-reachability-report.json` | PROVEN iff `verdict == READ_AND_USED`, else HEURISTIC |
| `tests_importing` | AST import scan of `tests/**` | PROVEN |
| `test_text_references` | `\bbasename\b` regex over `tests/` | TEXT_REFERENCE — **never called coverage** |
| `doc_citations` | `citation-map.generated.md` | HEURISTIC (18 symbols, bare basenames, low recall) |
| `findings_evidence`, `framework_evidence` | exact path in `evidence_paths[]` / `evidence[].path` | PROVEN |
| `script_registry` block | 22 SITS keys verbatim | PROVEN |
| `entry_points` | `control_plane_id`/`agent_tool_id` + `control_plane/registry.py` + `agent/tool_registry.py` | PROVEN |
| `concepts`, `journey_steps` | FK walk via `owner_boundary` | PROVEN |

### Must be `null`, never guessed

1. **Call-level edges.** Everything is module-import-level. `pyan_call_flow.dot` (~64.8k edges, tracked)
   resolves by name heuristic with unpinned freshness → HEURISTIC at best, **excluded from build 1**.
2. **Dynamic imports.** `importlib`/`__import__` are invisible to both graphs → `dynamic_import_risk: true`
   on token presence only, class TEXT_REFERENCE.
3. **`owner_surface`.** 0/463 attributed. Real ownership comes from `owner_boundary` — this is the concrete
   gap the Boundary layer closes.
4. **Behavioural test coverage.** No `.coverage`/`coverage.xml` in the repo. Textual hits ≠ coverage; two
   separate fields, never merged.
5. **"Runs in production".** `relevance` (curated) / `reachability_declared` (UNKNOWN) / graph reachability
   (real, but reachability) stay **three separate fields**, never collapsed into one `is_live`.
6. **`purpose` for the 38 src + 21 root files absent from the encyclopedia** → docstring fallback with
   `purpose_source`, or `null`. Never synthesised.

### Determinism & freshness

Pinned `_TS`, all lists sorted, `json.dumps(sort_keys=True)`, records sorted by `id` → byte-identical
reruns (pattern: `test_script_matrix_sync.py`). A separate `inputs` block records per artifact
`{path, sha256, embedded_generated_at, exists, stale}`; freshness comes from the **embedded** timestamp
(`_latest_by_generated_at` discipline, `feature_surface_query.py:80`), never the filename. Caveat recorded,
not silently normalised: encyclopedia `generated_at` is a date string (`"2026-08-07"`) while the config
graph carries full ISO — not cross-comparable.

---

## L5 — Semantic Query Engine

```python
from governance.semantic_query import SemanticIndex, AmbiguousAliasError, Answer

idx = SemanticIndex.load()
idx.resolve("atr normalization")        # -> CN-/BD-/FM-id; raises AmbiguousAliasError
idx.get_concept("CN-012"); idx.get_boundary("BD-004")
idx.get_journey("JN-001"); idx.get_object("src/core/engine_runner.py")
idx.filter(miar_stage=..., closure=..., tag=..., search=...)
idx.answer("owner", target="FM-041")    # -> Answer
idx.summary(); idx.sources; idx.meta["stale_artifacts"]
```

```python
@dataclass(frozen=True)
class Answer:
    question: str; target: str
    verdict: str                 # ANSWERED | PARTIAL | UNANSWERABLE | AMBIGUOUS
    rows: list[dict]             # {claim, evidence_class, artifacts, detail}
    weakest_evidence_class: str  # PROVEN | HEURISTIC | TEXT_REFERENCE
    caveats: list[str]; unanswerable_reason: str | None
```

`QUESTION_REGISTRY` is a **closed slug vocabulary** — no NL parsing, mirroring §3.3's "Deterministic by
design — do not route planning through the LLM."

**Reusing `feature_surface_query.py`:** `scripts/governance/` has no `__init__.py`, so its docstring's
`from scripts.governance...` import does not actually work — `tests/test_feature_surface_query.py:14-19`
loads it via `importlib.util.spec_from_file_location`. Do the same; expose as
`idx.feature_surface: FeatureSurfaceIndex | None`; on failure set
`meta["feature_surface"] = "UNAVAILABLE: <reason>"` and degrade dependent answers.

### CLI (`scripts/governance/query_semantic_os.py`)

```
--summary  --concept ID|NAME|ALIAS  --boundary  --journey  --object PATH
--list {concepts|boundaries|journeys|objects}  --search TEXT
--stage MIAR_STAGE  --closure SURFACE_ID  --tag TAG  --field FIELD (repeatable)
--ask SLUG --target X            # the five question resolvers
--validate [--strict]            # graph integrity; exit 1 on error
--impact PATH|ID [--depth N]     # L6
--emit-impact-manifest PATH --change-id ID [--write]
--sources  --json
```

`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at import (cp1252 guard,
`feature_surface_query.py:43`).

### The five questions — honest answerability

| Ask | Join path | Verdict | Weakest class |
|---|---|---|---|
| `--ask guarantees --target no_lookahead` | tags/invariants → CN → BD `invariant_protected` + `contract.guarantees` + `enforced_by_tests` + `evidence[]` → members → `tests_importing`; cross-join `feature_surface_query` PIT classes for all 38 vector features + `docs/book/05-*.md` | **PARTIAL** — the declared enforcement set is provable; "nothing else can introduce lookahead" is **not provable by any artifact here** | TEXT_REFERENCE |
| `--ask owner --target "atr normalization"` | alias → ontology (`FM-041 atr` + ATR-normalised `derived_metrics`) → CN → BD `owner` + `owner_symbol` (drift-checked) + `authority_layer`; cross-check `fm_ownership_consumer_matrix.json` | **AMBIGUOUS by design** — 3 candidates (FM-041 kernel period; ATR-normalised derived metrics; the CRT-local recompute that `WHAT_HOW_WHO_...json` records as `DUPLICATED_AUTHORITY / MARKET_MATH_LEAK_INTO_WHO`, parity unproven). Fails closed rather than picking. `owner_surface` **cannot** answer this today — reported as a gap, not an answer | PROVEN per candidate |
| `--ask writers --target execution_geometry` | CN → BD "Execution Planning" → members → `graph.dot` reverse edges → config-consumer-graph `cfg:execution_planner.*` → `boundary.change_classes` → `required_checks` | **PARTIAL** — import edges + `READ_AND_USED` config keys PROVEN; call-level "this function mutates that field" **not available**. Mandatory caveat: *import edge ≠ mutation* | HEURISTIC |
| `--ask disproved --target CN-0NN` | CN `assumptions[].falsified_by` → `findings.jsonl` (`status`, `reversal`, `supersedes`) + `hypothesis_registry.jsonl` (`status: falsified`, `findings[]`) + framework registry | **ANSWERED** where declared (the registries already carry structured falsification, e.g. H-001 `falsified` → F-019/F-021/F-026); else keyword search over 70 findings + 18 hypotheses → PARTIAL | PROVEN / TEXT_REFERENCE |
| `--ask authoritative --target CN-0NN` | CN `canonical_source` → BD `owner` (+drift-verified symbol) → `evidence[]` → members → closure status → encyclopedia `relevance` → graph importers | **ANSWERED**, ranked: `owner` (exactly one) > drift-verified evidence > glob members (*membership ≠ authority*) > importers. Mandatory caveat quoted from the index: **"CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE"** — never infer authority from an upstream CLOSED surface | PROVEN |

---

## L6 — Impact engine

**Seed normalisation:** path → itself · `CN-id` → its boundary's members · `BD-id` → `members_resolved` ·
`JN-id` → union over step boundaries · `FM-*`/`SEM-*` → `feature_surface_query` row's
`PRODUCERS.write_sites` + `impl_refs` · `section.key` → config-graph consumers.

| Layer | Source | evidence_class |
|---|---|---|
| **imports** | `graph.dot` reverse-BFS (`--depth N`) **+ `ast_import_census()`** for scripts/tests/root | PROVEN |
| **config** | config-consumer-graph + `config-reachability-report.json`; seed → keys it reads → *co-consumers* | PROVEN iff `verdict == READ_AND_USED`, else HEURISTIC |
| **fm_lineage** | `features.registry.build_lineage_graph()` → descendants → affected `CANONICAL_FEATURES` → `SCHEMA_HASH` invalidation flag | PROVEN |
| **doc_citations** | `citation-map.generated.md`, exact path then basename | HEURISTIC — 18 symbols, low recall, stated as a caveat |
| **findings** | exact path in findings/framework/hypothesis `evidence` | PROVEN |
| **semantic** | boundary globs → concepts → journey steps → **`invariants_at_risk`** | PROVEN |
| **checks** | matched `boundary.change_classes` → `required_checks` ∪ static path→class fallback ∪ GREEN_FLOOR if a seed hits `GOVERNED_PREFIXES`/`GOVERNED_FILES` ∪ `tests_importing` | PROVEN |

**Static path→class fallback** for seeds no boundary claims: `configs/production/*` →
`PRODUCTION_CONFIG_CHANGE` · `configs/formulas/market_ontology.yaml` → `FEATURE_IDENTITY_CHANGE` ·
`src/features/**` → `FORMULA_CHANGE`+`DERIVED_METRIC_CHANGE` · `feature_schema.py` →
`DATASET_SCHEMA_CHANGE` · `active_models.yaml`/`models/**` → `ACTIVE_MODEL_CHANGE` · `src/core/**`,
`execution_planner.py` → `RUNTIME_DECISION_PATH_CHANGE` · `scripts/**` → `SCRIPT_LIFECYCLE_CHANGE` ·
docs-only → `DOCUMENTATION_ONLY`.

GREEN_FLOOR is **imported**, not copied — `spec_from_file_location`, exactly as
`tests/test_governance_invariant_check.py:13-16` does.

Output carries per-row `evidence_class` plus a top-level `weakest_evidence_class` so a reader cannot
over-trust the aggregate, and an `inputs` block with per-artifact sha256 / availability.

### Draft manifest emission

`--emit-impact-manifest <out> --change-id CH-x [--write]` (stdout unless `--write`). Fills the computed
fields of `_IMPACT_MANDATORY` (`construction_protocol.py:45`): `change_classes`, `affected_files`,
`affected_feature_ids`, `affected_models`, `affected_production_config`, `required_checks_ack` — plus
underscore-prefixed `_generated_by` / `_evidence_classes` / `_caveats` (safe: `validate_impact` only checks
mandatory-field presence and literal `"UNKNOWN"` values).

**Deliberate:** `objective` and `rollback_boundary` emit as drafts **and** the emitter writes
`"unknowns": [{"question": "objective not authored by a human", "blocking": true}]`, so the raw draft
**fails `validate-impact`** until a human writes the objective. Two tests pin this
(`test_emitted_draft_manifest_fails_validate_impact`, and passes once filled). The engine computes the
mechanical 80%; it can never fake the authored 20%.

---

## Graph integrity validation

All in `src/governance/semantic_os.py`, each returning `list[ValidationError]` (`component_id`, `kind`,
`detail`) mirroring `framework_registry.ValidationError`.

1. `validate_schema` — required fields per kind, enums, types, `authority == "advisory"` pinned, summary caps
2. `validate_unique_ids_global` — CN/BD/JN/step ids unique **and disjoint from** all 12 ontology sections,
   F-, H-, MOD-, SCR-, framework ids, MIAR entry ids, closure `surface_id`s, `change_classes` keys
3. `validate_no_orphan_concepts` — every CN referenced by ≥1 BD **and** ≥1 JN step, or carries a non-empty
   `orphan_justification`; every BD has ≥1 concept and ≥1 resolved member; every JN has ≥2 steps
4. `validate_no_cyclic_ownership` — DFS-colour CN→`owner_boundary`→BD→`concepts`→CN and BD→`consumers`→BD;
   self-consumption is an error
5. `validate_bidirectional_consistency` — `CN.owner_boundary == BD` ⟺ `CN ∈ BD.concepts`
6. `validate_fk_resolution` — miar stage/entry, closure surface, ontology ids, findings (**reusing**
   `framework_registry.valid_finding_ids()`), hypotheses, framework ids, change classes, `book_chapter`
   exists **and** is in the README TOC, `topic_doc`, `canonical_source`, CN cross-refs
7. `validate_boundary_members` — every glob resolves to ≥1 real file; explicit paths exist; **no file
   claimed by two boundaries**; reports `unclaimed_objects`
8. `validate_spine_coverage` — a pinned `SPINE_FILES` set (`engine_runner.py`, `feature_pipeline.py`,
   `crt_engine_v2.py`, `fusion_engine.py`, `decision_engine.py`, `execution_planner.py`,
   `ultron_risk_gate.py`, `backtest_v2.py` + the 7 signal-flow step modules) is 100% boundary-claimed;
   monotonic `_BOUNDARY_COVERAGE_FLOOR` ratchet mirroring `_ATTRIBUTED_FLOOR`
9. `validate_journey_dag` — `order` 1..N contiguous & unique; `next` targets in-journey; **acyclic**; every
   step reachable from order-1; **every edge strictly forward in `order`**; ≥1 terminal;
   `async_feeders[].joins_at_step` resolves
10. `validate_journey_step_fks` — step `concept`/`boundary` resolve; boundary ∈
    `{concept.owner_boundary} ∪ related_boundaries`; **`failure_mode` ∈ `concept.failure_modes[].mode`**
11. `validate_evidence` — **reuses** framework_registry's `_resolve` + ±30-line symbol-drift window
12. `validate_alias_uniqueness` — concept names + aliases form one key domain; collision = error
    (fail-closed); collision with an ontology alias = warning
13. `validate_referenced_objects_reachable` — every referenced path exists; every `src/` object appears in
    `graph.dot` (absence ⇒ `stale_graph` error)
14. `validate_no_derived_in_source` — `_FORBIDDEN_HAND_FIELDS` absent from the YAML

### Negative (mutation) tests — required by repo precedent

Using the `_mutate(deepcopy)` pattern from `tests/test_semantic_registry.py:76-79`. One test per violation
class, each asserting the **specific** message substring (not merely "errors non-empty"):

`test_orphan_concept_is_caught` · `test_cyclic_ownership_is_caught` · `test_self_consuming_boundary_is_caught` ·
`test_duplicate_id_with_frozen_fm_is_caught` (`FM-002`) · `..._with_finding_is_caught` (`F-001`) ·
`..._with_mod_is_caught` (`MOD-0001`) · `..._with_scr_is_caught` (`SCR-001`) ·
`test_duplicate_concept_id_is_caught` · `test_unknown_miar_stage_is_caught` ·
`test_unknown_closure_surface_is_caught` · `test_unknown_ontology_id_is_caught` (`FM-999`) ·
`test_unknown_finding_is_caught` (`F-999`) · `test_unknown_change_class_is_caught` ·
`test_missing_book_chapter_is_caught` · `test_book_chapter_not_in_toc_is_caught` ·
`test_boundary_glob_matching_nothing_is_caught` · `test_file_claimed_by_two_boundaries_is_caught` ·
`test_empty_invariant_protected_is_caught` · `test_owner_symbol_drift_is_caught` ·
`test_journey_cycle_is_caught` · `test_journey_order_gap_is_caught` · `test_journey_backward_edge_is_caught` ·
`test_unreachable_journey_step_is_caught` · `test_step_failure_mode_not_declared_is_caught` ·
`test_step_boundary_not_owned_by_concept_is_caught` · `test_async_feeder_dangling_step_is_caught` ·
`test_bidirectional_mismatch_is_caught` · `test_missing_required_field_is_caught` ·
`test_derived_field_in_hand_source_is_caught` · `test_authority_must_be_advisory` ·
`test_ambiguous_alias_is_caught` · `test_referenced_object_missing_from_disk_is_caught` ·
`test_src_object_missing_from_graph_dot_is_caught` · `test_spine_coverage_floor_cannot_regress` ·
`test_summary_50_over_cap_is_caught`

**Positive/contract:** `test_live_registry_is_clean` · `test_seed_is_byte_identical_on_rerun` ·
`test_every_concept_has_nonempty_why_it_exists` · `test_all_seven_miar_stages_have_a_concept` ·
`test_journey_jn001_covers_signal_flow_steps_1_to_7_and_4_feeders`.

**Object/query/impact suites** carry their own negatives: no PROVEN import deps where the source is
unavailable; `owner_surface` never fabricated; every emitted field has a `FIELD_EVIDENCE_CLASS` entry;
ambiguous alias raises; no `Answer` row claims PROVEN from a name-based source; emitted draft manifest
**fails** `validate_impact`; impact output deterministic for a fixed seed.

---

## Build sequence

Each phase leaves the repo green and is independently verifiable.

**Phase 0 — Construction Protocol entry + track the inputs.** *(approval gate)*
`git add` the 6 untracked artifacts — a **targeted 6-file add, never `git add -A`** (standing blocker:
836 untracked / 68 in `src/`; a partial commit breaks the build). Write
`docs/governance/build_manifests/CH-semantic-os-v2.impact.json` classified
`["SCRIPT_LIFECYCLE_CHANGE", "DOCUMENTATION_ONLY"]`; run `validate-impact`. File the
`GOVERNANCE_REGISTRY_ADDITION` change-class gap as a tracked follow-up.

**Phase 1 — schema + registry core, walking skeleton.**
`src/governance/semantic_os.py` + the 3 YAMLs with 2 concepts / 2 boundaries / 1 journey +
`scripts/governance/seed_semantic_os.py` (**SITS same turn**) + `tests/test_semantic_os.py` with the full
mutation suite. Verify: tests green, seed byte-identical, `--validate` exit 0. No GREEN_FLOOR change yet.

**Phase 2 — Object layer + AST import census.**
`src/governance/semantic_objects.py` (incl. `ast_import_census()` covering the 783 files `graph.dot`
misses) + `--objects` on the seed CLI + `tests/test_semantic_os_objects.py`. Verify 844 objects and that
`coverage_gaps` matches the measured 38/21/9/411 deltas. **Record** the encyclopedia/attribution staleness;
do **not** regenerate those artifacts in this build (separate governed change).

**Phase 3 — author the real semantics.** *(approval gate + user participation — the largest phase)*
~50 concepts, ~40 boundaries, 4–8 journeys. Seeded from: `docs/intent_graph.md` (12 Chains, each already
carrying Thought / Goal / Belief / Economic Meaning / Architecture Decision / Modules / Runtime Effect /
Alignment Status — a near one-to-one match for `why_it_exists` / `why_this_design` / `invariants`),
`docs/intent/` (7 domain files), `docs/intent_to_code_map.md` (intent→file:line → BD `evidence[]`),
`docs/book/README.md` Concept Index (~20 concepts with canonical chapters → `book_chapter`),
`docs/topics/` (26 → `topic_doc`), `miar_registry.json` (17 entries × 7 stages → `miar_stage`,
`explicit_non_goals`, `falsification`), `closure_authority_index.json` (11 surfaces),
`WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json` (→ `authority_layer` + several ready-made boundaries),
`signal-flow.md` Steps 1–7 + §2.1–2.4 + §3 matrix (→ JN-001).
Split **3a** mechanical extraction proposal (every field citing its source line) → user review → **3b**
commit. `why_this_design` / `alternatives_rejected` are historical facts; per §6.2 rule 3 and §6.6
"never fabricate", they must be user-confirmed, not invented.

**Phase 4 — L5 Semantic Query Engine.** `src/governance/semantic_query.py` +
`scripts/governance/query_semantic_os.py` (**SITS**) + `tests/test_semantic_query.py`.

**Phase 5 — L6 Impact Engine.** `src/governance/semantic_impact.py` + `--impact` /
`--emit-impact-manifest` on the existing CLI (no third script) + `tests/test_semantic_impact.py`.

**Phase 6 — enforcement + docs.** *(approval gate)*
GREEN_FLOOR additions + `test_governance_invariant_check.py` pins; `docs/reference/schemas.md`
§9.10–§9.13; `docs/governance/SEMANTIC_OS_CONTRACT.md`; SESSION LOG; `validate-completion` →
`CH-semantic-os-v2.completion.json`. Any `CLAUDE.md` edit is separately gated.

**Phase 7 — verification sweep.**

---

## Verification

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --validate
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --summary
```

The five questions:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask guarantees --target no_lookahead --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask owner --target "atr normalization" --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask writers --target execution_geometry --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask disproved --target CN-012 --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask authoritative --target CN-012 --json
```

L6:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --impact src/features/feature_pipeline.py --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --impact src/features/feature_pipeline.py --emit-impact-manifest docs/governance/build_manifests/CH-probe.impact.json --change-id CH-probe
```

Tests:

```bash
D:/Tradelatest/.venv/Scripts/python.exe -m pytest -q tests/test_semantic_os.py tests/test_semantic_os_objects.py tests/test_semantic_query.py tests/test_semantic_impact.py
```

SITS (same turn as any new `scripts/**/*.py`):

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl && D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_script_registry.py && D:/Tradelatest/.venv/Scripts/python.exe scripts/analysis/generate_script_matrix.py
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe -m pytest -q tests/test_script_registry.py tests/test_script_matrix_sync.py
```

Construction Protocol + green floor:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-semantic-os-v2.impact.json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/construction_protocol.py check
```

Determinism — run the seed twice and compare hashes:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects && sha256sum data/semantic_os/*.jsonl > /tmp/a.txt && D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects && sha256sum data/semantic_os/*.jsonl > /tmp/b.txt && diff /tmp/a.txt /tmp/b.txt && echo BYTE-IDENTICAL
```

---

## Known limits (stated, not hidden)

1. **Import edges are module-level, not call-level.** L6 answers "which modules could be affected", never
   "which function mutates which field."
2. **`citation-map.generated.md` has 18 symbols** with several bare basenames → doc-citation blast radius
   has low recall and is HEURISTIC.
3. **`owner_surface` is `UNATTRIBUTED` on 463/463 and `reachability` is `UNKNOWN` on all.** The Object
   layer will faithfully report 0% attribution. That will look alarming; it is the truth, and it is the
   gap the Boundary layer closes.
4. **The `~813` encyclopedia denominator is stale** (38 src + 21 root missing, 0 tests). Honest
   denominator is 844 code objects; the delta is recorded in `coverage_gaps`, not silently patched.
5. **No behavioural test coverage data exists** in the repo. `test_text_references` is textual and is never
   labelled coverage.
6. **Q1 (no-lookahead) can never return ANSWERED.** The enforcement set is provable; exhaustiveness is not.
7. **This layer is advisory (§6.5).** `authority: "advisory"` is pinned with a negative test. Boundary
   membership grants zero production authority; only demonstrated ΔG001 does.
