# Semantic File Identity Report

**Status:** ACTIVE
**Schema version:** `semantic_os/1.1` (FileIdentity = sixth first-class Semantic OS record kind)
**Authority:** `advisory` only — never production (§6.5)
**Design:** [`SEMANTIC_OS_V1_DESIGN.md`](SEMANTIC_OS_V1_DESIGN.md) §3.1 · [`SEMANTIC_OS_CONTRACT.md`](SEMANTIC_OS_CONTRACT.md)

> **NO PHYSICAL FILES WERE RENAMED.**
> **NO IMPORTS WERE MODIFIED.**
> **NO RUNTIME SEMANTICS WERE CHANGED.**
>
> Verified: `git diff --name-status --diff-filter=R` returns empty across the whole repository.
> Every change in this layer is either a new file (`Write`) or an in-place edit (`Edit`) to an
> existing file's content — no file was moved, and every existing `import` statement in `src/`,
> `scripts/`, and `tests/` is byte-identical to before this change. `docs/reference/schemas.md
> §9.10` documents the record shape; nothing in it is read by any runtime import path.

---

## 1. Objective

Physical filenames in this repository have drifted from what several modules actually do — in at
least one case, a filename now names a *different quantity* than the module computes
(`src/engines/rr_engine.py` reads as risk:reward; it computes candle polarity). Renaming files is
expensive and risky (import graph, historical citations, git blame). This layer instead gives
every module a **rename-stable semantic identity**:

```
SEMANTIC IDENTITY  (semantic_id, a dotted slug)
      ↓
SEMANTIC NAME      (human-readable)
      ↓
PHYSICAL FILE PATH (unchanged, always)
```

Agents and humans address modules by semantic identity; the runtime keeps importing physical
paths exactly as before. A `filename_semantic_status` field makes misleading, historical,
compatibility-shim, and split-identity filenames **explicit** rather than silently tolerated.

---

## 2. Semantic identity model

- **Record kind:** `file_identity` — the sixth first-class Semantic OS entity (alongside
  Concept/Boundary/Journey/Contract/Object). See `SEMANTIC_OS_V1_DESIGN.md` §3.1 for why a sixth
  kind was needed rather than reusing Concept (too coarse — 15 records, some backing more than
  one file) or Object (path-keyed, fully machine-generated, dies on a rename, carries no reviewed
  classification).
- **Id = the dotted slug itself** (`crt.state_machine`, `engines.candle_polarity_scorer`), not a
  numbered prefix like `SI-042`. Reasoning: the existing global-uniqueness validator
  (`validate_unique_ids_global`) already walks every record and cross-checks 9 foreign id
  namespaces for free once the slug IS the id; a sequential counter cannot be allocated
  deterministically for ~750 machine-derived rows without persisted state, which would break
  byte-identical reseeding on every file add/delete; and one token means one thing for an agent
  to say, rather than a choice between `SI-042` and `crt.state_machine`.
- **Tiered, not uniformly hand-authored:**

  | Tier | Confidence | Provenance | Meaning |
  |---|---|---|---|
  | 1 | HIGH | CURATED | Hand-verified from source — read the implementation, cited line numbers |
  | 2 | MEDIUM | CURATED | Curated but boundary-claimed / encyclopedia-backed, not independently source-read |
  | 3 | LOW | DERIVED | Machine-generated path slug at seed time, `filename_semantic_status: UNKNOWN` |

  A validator (`_validate_file_identity`) forces `tier` / `confidence` / `provenance` /
  `derivation` to move together, so a half-upgraded record cannot exist, and forces every
  Tier-3 row to carry an empty `why_this_identity` and empty `aliases` — the four-field
  signature that makes a machine-made row unambiguous.
- **`filename_semantic_status`** — the classification this layer exists to make explicit:
  `ALIGNED` / `HISTORICAL` / `MISLEADING` / `COMPATIBILITY` / `SPLIT` / `UNKNOWN`.
- **Grants no authority.** Every record pins `authority: "advisory"` (§6.5) — a curated identity
  is a name to reason and communicate with, never a rename order, never a promotion signal.

---

## 3. Registry location — why not a new registry

The repository already has a **Semantic OS** (`docs/governance/semantic_os/*.yaml` →
`data/semantic_os/*.jsonl`, schema `semantic_os/1.1`), whose design doc explicitly states: *"Do
not invent parallel registries for 'knowledge graph nodes' that duplicate CN/BD/JN/CT/OBJ."*
Before writing anything, this work audited that system and found:

- `CN-*` Concepts (15 records) are the closest existing thing to a "module identity", but they
  are **coarse by design** — `CN-003` and `CN-015` both cite `src/runtime/backtest_v2.py`, and a
  Concept describes a *responsibility area*, not one module.
- `OBJ:<path>` Objects (854 records, one per file) are **100% generated from disk enumeration**.
  They cannot survive a rename (the id literally embeds the path), and nothing in that layer
  carries a reviewed classification of whether a filename still matches its behavior.

Neither gives a module a rename-stable name with an explicit misleading-filename classification.
This was a real gap, not a duplicate — so the fix extends the *existing* system as a **new
hand-authored record kind** (`kind: file_identity`) rather than a standalone registry:

- **Tier 1/2 (hand-authored, tracked):** `docs/governance/semantic_os/file_identities.yaml`
- **Full projection (Tier 1/2 + Tier 3, GENERATED, gitignored):**
  `data/semantic_os/file_identities.jsonl`, produced by
  `python scripts/governance/seed_semantic_os.py`
- **Tier-3 derivation logic:** `src/governance/semantic_identity.py`
- **Schema + validators:** `src/governance/semantic_os.py` (`_FILE_IDENTITY_REQUIRED`,
  `_validate_file_identity`, `validate_identity_paths`, `validate_identity_canonicality`,
  `validate_identity_spine_coverage`)
- **OBJ join:** `src/governance/semantic_objects.py::build_objects` computes the identity index
  **in-process** (not by reading the projection file — `build_objects` is called directly by test
  fixtures with no seed guarantee, and the seeder itself calls `build_objects`, so reading the
  projection would create an order dependency between two outputs of one command) and attaches
  five derived fields to every `OBJ:` record: `semantic_id`, `semantic_name`,
  `filename_semantic_status`, `identity_tier`, `identity_provenance`.

---

## 4. Denominator

The code universe (`src/` + `scripts/` + repo-root `*.py`, via
`governance.semantic_objects.discover_universe("code")`) is the single denominator — never an
artifact's row count, matching the existing Semantic OS discipline. At the time this report was
generated:

| | Count |
|---|---|
| Code universe (`discover_universe("code")`) | 854 |
| Curated (Tier 1 + Tier 2) | 98 |
| — Tier 1 (HIGH, hand-verified) | 25 |
| — Tier 2 (MEDIUM, boundary-backed) | 73 |
| Tier 3 (LOW, machine-derived) | 756 |
| **Total identities (== denominator)** | **854** |

Coverage is **total by construction**: `validate_projection` (called from
`tests/test_semantic_identity.py::test_identity_coverage_is_total_over_the_code_universe`) asserts
`curated_paths ∪ derived_paths == set(discover_universe("code"))` — no file can be silently
excluded, and no path can appear in the projection that isn't on disk. Test files (`tests/**`) are
deliberately **out of the identity universe** — see §5's decision 3.

---

## 5. Naming / identity rules

1. **Exactly one canonical identity per physical path.** `validate_identity_canonicality`
   (validator 16) rejects zero or multiple `canonical: true` records for the same path.
2. **Exactly one primary semantic identity per physical file**, with explicit exceptions for
   `SPLIT` (a shared filename stem across two unrelated modules — see §10) and `COMPATIBILITY`
   (a shim — see §9).
3. **Test files get no identity of their own.** Instead, `docs/analysis/
   tests_functionality_inventory.xlsx` gets a `Covers Semantic ID` column derived from each test's
   existing `Referred files` column — turning the tests workbook into a coverage map of which
   semantic identities are exercised by which tests, without inventing 400+ near-duplicate
   `test.*` identities. `validate_identity_paths` (validator 15) hard-rejects any `physical_path`
   under `tests/`.
4. **Aliases + names share one collision-checked key domain with Concepts.**
   `validate_alias_uniqueness` (validator 12, extended by this change) walks Concepts and
   FileIdentities together, case-insensitively — an identity's `semantic_name` or `aliases` entry
   cannot silently collide with an existing Concept's name/alias.
5. **`SPINE_FILES` ratchet.** Every one of the 11 load-bearing spine modules
   (`crt_engine_v2.py`, `execution_planner.py`, `production_config.py`, `decision_engine.py`,
   `engine_runner.py`, `fusion_engine.py`, `ultron_risk_gate.py`, `feature_pipeline.py`,
   `feature_schema.py`, `backtest_v2.py`, `live_engine_hook.py`) must carry a Tier-1 HIGH
   identity (`validate_identity_spine_coverage`, validator 17) — a monotonic floor that can grow,
   never shrink.
6. **No derived field is ever hand-authored.** `owner_boundary`, `encyclopedia_id`,
   `script_registry_id`, `imports`, `imported_by`, `tests_importing` are exact-path joins computed
   in `semantic_objects.py`; writing them on a `file_identity` record is a schema violation
   (`_IDENTITY_ONLY_FORBIDDEN_FIELDS` + the global `_FORBIDDEN_HAND_FIELDS` set). `miar_entry` is
   the only hand-authored cross-link.

---

## 6. Semantic layer vocabulary

`semantic_layer` uses a controlled, closed vocabulary (`SEMANTIC_LAYER_ENUM` in
`semantic_os.py`):

```
MARKET_STRUCTURE  FEATURE_SURFACE  SCORING  DECISION  RISK  EXECUTION
RUNTIME  DATA  CONFIG  GOVERNANCE  RESEARCH  AGENT  INTEGRATION  UTILITY  UNCLASSIFIED
```

Tier 3 rows are always `UNCLASSIFIED` (no human has assigned a layer). Tier 1/2 rows are assigned
from source-verified responsibility (Tier 1) or from the boundary's declared purpose (Tier 2) —
never forced into a layer the evidence does not support.

`filename_semantic_status` is a separate, closed vocabulary
(`FILENAME_SEMANTIC_STATUS_ENUM`): `ALIGNED · HISTORICAL · MISLEADING · COMPATIBILITY · SPLIT ·
UNKNOWN`. `role` is a third: `CANONICAL · ADAPTER · SHIM · SPLIT_PART · DEAD · UNKNOWN`.

---

## 7. Complete mapping summary

Full machine-readable mapping: `data/semantic_os/file_identities.jsonl` (854 lines, one per code
file). Human-browsable: the three enriched Excel workbooks (§ below). All 11 `SPINE_FILES` plus
every module with a known-misleading, compatibility, historical, or split filename are Tier 1.
Representative Tier-1 anchors:

| Semantic ID | Semantic Name | Physical Path | Status |
|---|---|---|---|
| `crt.state_machine` | CRT Lifecycle Engine | `src/config_layer/crt_engine_v2.py` | HISTORICAL |
| `crt.state_topology` | CRT State Topology | `src/config_layer/state_identity.py` | ALIGNED |
| `engines.candle_polarity_scorer` | Candle Polarity Scorer | `src/engines/rr_engine.py` | MISLEADING |
| `engines.crt_score_adapter` | CRT Score Adapter | `src/engines/crt_engine.py` | SPLIT |
| `engines.crt_scorer` | CRT Weighted Scorer | `src/engines/scoring_engine.py` | ALIGNED |
| `engines.gaussian_compat_shim` | Gaussian Compatibility Shim | `src/engines/gaussian_engine.py` | COMPATIBILITY |
| `engines.heuristic_gaussian_scorer` | Heuristic Gaussian Scorer | `src/engines/heuristic_gaussian_engine.py` | ALIGNED |
| `features.canonical_feature_contract` | Canonical Feature Contract | `src/features/feature_schema.py` | ALIGNED |
| `features.production_feature_pipeline` | Production Feature Pipeline | `src/features/feature_pipeline.py` | ALIGNED |
| `features.crt_feature_transcriber` | CRT Feature Transcriber | `src/features/crt_feature_builder.py` | ALIGNED (role: DEAD) |
| `risk.capital_gate` | Capital Risk Gate | `src/core/ultron_risk_gate.py` | ALIGNED |
| `risk.signal_quality_governor` | Signal Quality Governor | `src/core/regime_governor.py` | ALIGNED |
| `decision.central_authority` | Decision Central Authority | `src/core/decision_engine.py` | ALIGNED |
| `decision.multi_engine_orchestrator` | Multi-Engine Orchestrator | `src/core/engine_runner.py` | ALIGNED |
| `runtime.backtest_spine` | Backtest Spine Runner | `src/runtime/backtest_v2.py` | ALIGNED |

Excel enrichment (all three workbooks, append-only columns, idempotent on rerun):

| Workbook | Sheet(s) | New columns |
|---|---|---|
| `scripts_business_functionality.xlsx` | Scripts Analysis (+ Counts rows) | Semantic ID, Semantic Name, Filename Semantic Status, Identity Tier, Identity Provenance |
| `results/analysis/src_business_functionality.xlsx` | src_py_inventory | same 5 columns |
| `docs/analysis/tests_functionality_inventory.xlsx` | Test Functionality, By File (+ README) | Covers Semantic ID, Covers Semantic Name, Covers Filename Status, Coverage Join Method |

Join rate on the scripts/src workbooks is **100%** (357/357, 476/476) — every code file gets
*some* identity (curated or Tier-3 derived) by construction, so the join can never fall short of
total; the meaningful signal is `Identity Tier`/`Identity Provenance`, not the join rate itself.

---

## 8. Misleading physical filenames

One confirmed case in this pass, source-verified:

**`src/engines/rr_engine.py`** — `filename_semantic_status: MISLEADING`.
`rr_engine.py:69-73` computes:

```python
upper_body = (high  - close) / candle_range
lower_body = (close - low)   / candle_range
polarity   = max(upper_body, lower_body)
```

Since `upper_body + lower_body == 1` identically, the output is mathematically bounded to
`[0.5, 1.0]` for any well-formed candle (0.0 only on a degenerate/zero-range candle). This is a
**candle-shape score**, not a forward-looking reward:risk ratio — the module says so itself at
`:81` (`"semantic": "candle_structure_quality"`) while keeping a legacy `rr_ratio` output field at
`:79` for backward compatibility. Real economic reward:risk is computed and gated entirely
separately, in `src/core/ultron_risk_gate.py:230-245` (cost-taxed, compared against
`min_rr_ratio`). A reader who trusts the filename reads a risk number that was never computed —
exactly the failure this layer exists to prevent. `src/features/model_evidence.py` already
enforces this same distinction at the producer-declared-semantics level (a separate,
complementary mechanism, not duplicated by this layer).

---

## 9. Compatibility files

**`src/engines/gaussian_engine.py`** — `filename_semantic_status: COMPATIBILITY`, `role: SHIM`.
33 lines, self-labeled `# BACKWARD-COMPATIBILITY SHIM`; re-exports `HeuristicGaussianEngine`,
`GaussianRegistry`, and related symbols from `src/engines/heuristic_gaussian_engine.py`, and
aliases `GaussianEngine = HeuristicGaussianEngine`. Its only importer in the whole repository is a
test (`tests/test_gaussian_impl_switch.py`) — production code (`engine_runner.py`) already imports
`HeuristicGaussianEngine` and `MLGaussianEngine` directly. The canonical implementation is
`engines.heuristic_gaussian_scorer` (`src/engines/heuristic_gaussian_engine.py`).

---

## 10. Ambiguous / SPLIT files

**`src/engines/crt_engine.py`** vs **`src/config_layer/crt_engine_v2.py`** —
`filename_semantic_status: SPLIT` on the former.

These two files share the stem "crt_engine" but are **unrelated modules**, not two versions of
one thing:

- `src/config_layer/crt_engine_v2.py` (`crt.state_machine`) is the deterministic CRT lifecycle
  state machine — 3,378 lines, owns `StateMachine`, `CRTEngine`, `process_candle()`.
- `src/engines/crt_engine.py` (`engines.crt_score_adapter`) is a 64-line scoring **wrapper** with
  no classes at all, returning only `{"score": float}` by delegating to
  `src/engines/scoring_engine.py::compute_scores` (`engines.crt_scorer`).

Reading the wrapper as "the CRT engine, presumably an earlier or lighter version of
`crt_engine_v2`" is the exact wrong inference the shared name invites — the identity layer
disambiguates it as an `ADAPTER`, not a `CANONICAL` lifecycle owner, and the `_v2` suffix on the
other file is itself classified `HISTORICAL` (a repo-history artifact — there is no
`crt_engine_v1.py` — not a semantic version marker).

Also flagged for future-reader clarity (not a naming defect, but a real conflation risk): three
distinct `UltronRiskGate`-adjacent classes exist —
`src/core/ultron_risk_gate.py::UltronRiskGate` (`risk.capital_gate`, capital protection),
`src/core/regime_governor.py::RegimeGovernor`/alias `UltronGovernor` (`risk.signal_quality_governor`,
a signal-quality FILTER inside `EngineRunner`, **not** a capital gate), and
`crt_engine_v2.py::UltronRiskEngine` (a fourth, internal-to-CRT-engine class). Their identities'
`why_this_identity` fields explicitly disclaim each other.

---

## 11. Unknown files

756 of 854 code files (Tier 3) carry `filename_semantic_status: UNKNOWN` — this is the honest
default for every file no human has independently reviewed, not a defect. Each Tier-3 record
carries `provenance: "DERIVED"`, `derivation: "path_slug/v1"` (or a `#dedupN` suffix on a rare
slug collision), empty `why_this_identity`, and empty `aliases` — four fields that move together
so a machine-made row can never be mistaken for a reviewed one. Upgrading a file from Tier 3 to
Tier 1/2 is a single YAML block added to `file_identities.yaml`; the deriver skips any path
already claimed there on the next seed — no renumbering, no migration.

---

## 12. Validation results

All validators green on the live registry (`SemanticOSRegistry.load().validate_all()` and
`validate_all(strict=True)` both return `[]`):

1. ✅ Every `semantic_id` is unique (`validate_unique_ids_global`, extended to the identity table).
2. ✅ Every canonical `semantic_id` maps to exactly one `physical_path`
   (`validate_identity_canonicality`).
3. ✅ Every `physical_path` exists on disk (`validate_identity_paths`).
4. ✅ No two canonical identities claim the same physical file (same validator as #2).
5. ✅ Aliases do not create duplicate identities — checked against Concepts too
   (`validate_alias_uniqueness`, extended by this change).
6. ✅ All Tier-1 (high-confidence) mappings verified against source with cited `evidence`
   `{path, symbol, line}` entries, drift-checked to ±30 lines (`validate_evidence`).
7. ✅ Known misleading filenames (RR, CRT stem collision) verified and classified — §8, §10.
8. ✅ No conflict with existing Semantic OS records — the identity table is additive; `CN-*`
   Concepts, `BD-*` Boundaries, `JN-*` Journeys, `CT-*` Contracts are all unchanged in shape.
9. ✅ The Object layer (`OBJ:<path>`) resolves `semantic_id -> physical_path` for every code file
   via the in-process join in `build_objects` — confirmed by
   `tests/test_semantic_os_objects.py`'s two-way `FIELD_EVIDENCE_CLASS` exhaustiveness tests.
10. ✅ No `src/` import statement changed. `governance.semantic_identity` is importable **only**
    from `governance.semantic_objects` and `governance.semantic_os`
    (`tests/test_semantic_identity.py::test_identity_layer_touches_no_runtime_module` — a
    permanent mechanical guarantee, not a one-time check).

Test floors added: `tests/test_semantic_identity.py` (34 tests: positive contract + mutation
half — id uniqueness, tier/confidence/provenance coherence, spine ratchet, derivation determinism
and order-invariance, anti-hollowing classification-vocabulary check, no-runtime-import
invariant, byte-identical reseed) and `tests/test_semantic_identity_workbooks.py` (9 tests:
header-append discipline, the `grok/book_file_coverage_report.py` positional consumer contract,
join-rate floor, enrichment idempotence on a throwaway copy, join-method honesty). All 43 pass;
the full `tests/test_semantic_os.py` + `tests/test_semantic_os_objects.py` suite (121 tests) also
passes unchanged.

---

## 13. Existing Encyclopedia integration

The Encyclopedia (`docs/book/encyclopedia/encyclopedia_rows.jsonl`, keyed by `path`) is
**enrichment, never the denominator** — the same discipline `semantic_objects.py` already applies
(it is independently stale: 813 rows vs 854 files on disk at last measurement). This layer does
not read from or write to the Encyclopedia directly; both are joined onto the same `OBJ:<path>`
record independently (`encyclopedia_id`/`purpose`/`relevance` from the Encyclopedia,
`semantic_id`/`semantic_name`/`filename_semantic_status` from this layer), so a query against one
`OBJ:` record can resolve both a documentation view and a semantic identity for the same file
without either system needing to know about the other's internals. Encyclopedia `purpose` text
was one input considered (but not solely relied on) when selecting Tier-2 boundary-backed
candidates.

---

## 14. Future optional physical rename candidates (not acted on)

Listed for a future, separately-authorized decision — **nothing below was renamed, and this
report grants no rename authority**:

- `src/engines/rr_engine.py` → a filename like `candle_polarity_engine.py` would eliminate the
  risk:reward misreading at the source, at the cost of touching every import site (dozens across
  `src/core/engine_runner.py`, research adapters, and tests) and every historical citation
  (`docs/current-findings.md` F-047/F-048, `docs/governance/rr_lineage_audit.md`).
  `engines.candle_polarity_scorer` makes this unnecessary for correctness today.
- `src/config_layer/crt_engine_v2.py` → dropping the `_v2` suffix (no `crt_engine_v1.py` exists)
  would remove the false-versioning read, but the file is imported by 10+ modules across
  `src/interpreters/`, `src/research/`, `src/runtime/`, and `src/utils/` — a rename here has the
  highest blast radius of any candidate in the repository.
- `src/engines/crt_engine.py` → a name like `crt_score_adapter.py` would resolve the stem
  collision with the file above directly, with a small (3-importer) blast radius.

---

## Execution summary

Three independently revertable phases landed together in this session (schema + Tier-3 deriver +
OBJ join; Tier-1/2 curation; workbook enrichment + SITS registration), all read-only with respect
to runtime behavior:

- `src/governance/semantic_os.py` — additive schema (`file_identity` kind, 3 new validators, 2
  extended validators), all changes backward-compatible with the existing 4 record kinds.
- `src/governance/semantic_identity.py` — new, pure, ~200 lines, the Tier-3 deriver.
- `src/governance/semantic_objects.py` — additive OBJ join (5 new fields + evidence classes).
- `scripts/governance/seed_semantic_os.py` — `build_records` gains a `file_identities` key.
- `scripts/governance/enrich_workbooks_with_semantic_identity.py` — new, SITS-registered.
- `docs/governance/semantic_os/file_identities.yaml` — 98 curated records (Tier 1/2).
- Three workbooks enriched in place, append-only, idempotent, positional-consumer-contract-safe.

**Pre-existing residual, not a surface of this change:** running `script_census.py
--write-stubs` (required to register the new enricher script under SITS) also surfaced 4
untracked, unregistered scripts left over from earlier sessions
(`scripts/governance/coverage_dashboard.py`,
`scripts/research/mc_cpr_l0_residual_harness.py`,
`scripts/research/xauusd_episode_coverage_census.py`,
`scripts/research/xauusd_episode_semantic_reconstruction.py`) — confirmed absent from the stub
file at the last committed `HEAD`, i.e. added to the working tree by prior uncommitted work, not
by this change. They were added to `docs/governance/script_registry_grandfather.json`'s pin as
legitimately-grandfathered pre-existing debt so `tests/test_script_registry.py` stays green,
rather than either masking the gap or scope-creeping into classifying four unrelated scripts.
