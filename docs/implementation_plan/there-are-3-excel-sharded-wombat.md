# Semantic File Identity Layer

## Context

Physical filenames in this repo have drifted from what the modules actually do, and some now
name a *different quantity* than they compute:

- `src/engines/rr_engine.py` reads as risk:reward but computes candle polarity.
  `rr_engine.py:69-73` sets `polarity = max((high-close)/range, (close-low)/range)`; the two
  terms sum to 1, so output is bounded `[0.5, 1.0]` (0.0 only on a degenerate candle). The
  module self-declares `"semantic": "candle_structure_quality"` at `:81` while keeping a legacy
  `rr_ratio` output field at `:79`. Real economic RR lives in `src/core/ultron_risk_gate.py:230-245`.
- `src/engines/gaussian_engine.py` is a 33-line back-compat shim re-exporting from
  `heuristic_gaussian_engine.py`; its only importer is a test.
- `src/config_layer/crt_engine_v2.py` (CRT lifecycle state machine) and `src/engines/crt_engine.py`
  (64-line scoring wrapper) share a stem but are unrelated modules, not versions of each other.

Renaming the files is expensive and risky. This change instead gives every module a **rename-stable
semantic identity** — `semantic_id` → `semantic_name` → `physical_path` — so humans and agents
address modules by meaning while the runtime keeps importing physical paths unchanged. Misleading
filenames get explicitly *classified* rather than silently tolerated.

**Intended outcome:** `"Candle Polarity Scorer"` → `engines.candle_polarity_scorer` →
`src/engines/rr_engine.py`, resolvable in both directions, with zero runtime impact.

### Why this extends the Semantic OS instead of adding a registry

The repo already has a Semantic OS (`docs/governance/semantic_os/*.yaml` → `data/semantic_os/*.jsonl`,
schema `semantic_os/1.1`, guarded by `tests/test_semantic_os.py` + `tests/test_semantic_os_objects.py`).
Its `SEMANTIC_OS_V1_DESIGN.md:137` forbids parallel registries. But its per-file layer (`OBJ:<path>`,
849 objects) is **path-derived and fully machine-generated** — it dies on a rename — and `CN-*`
concepts are coarse (15 records; `backtest_v2.py` backs both CN-003 and CN-015). A rename-stable
per-module identity genuinely does not exist yet, so this is a real gap filled *inside* the existing
system, not a competing one.

### Decisions already made

1. New hand-authored record kind inside the Semantic OS (not a standalone registry).
2. Tiered coverage over the whole code universe: Tier 1 curated/HIGH (~50-60 load-bearing),
   Tier 2 curated/MEDIUM, Tier 3 machine-derived/LOW.
3. Test files get **no** identity — the tests workbook gets a `Covers Semantic ID` column instead.
4. Workbooks are regenerated with their existing generators, *then* enriched.

### Verified constraints

- **All three workbooks are untracked.** `.gitignore:5` is a bare `results`; the other two were
  never added. Guard tests must `pytest.skip` when a workbook is absent.
- **`grok/book_file_coverage_report.py:128-154` reads workbooks positionally** (`row[0..2]` only).
  Appending columns is safe; inserting or reordering is not.
- **`SEMANTIC_OS_V1_DESIGN.md:117`** states "Only five first-class entity kinds", and `:95-111`
  already uses *Identity* for a different L0 concept (`identity_kind`, implemented in zero files).
  → name the new kind **`file_identity`**, and revise the design doc in the same change.
- **Projection is stale**: disk has 852 code files (475 src + 356 scripts + 21 root), projection
  says 849. Reseed before measuring any coverage floor.
- **`_FORBIDDEN_HAND_FIELDS`** (`semantic_os.py:152`) forbids hand-writing derived fields.
  `owner_boundary` / `encyclopedia_id` / `script_registry_id` are already computed as PROVEN joins
  in `semantic_objects.py:597,605,622` and must **not** be hand-authored on identity records.
- Across all 9 foreign id namespaces (1,078 ids), **zero** match a dotted lowercase slug — so the
  slug can safely be the record `id`, and existing global-uniqueness validation covers it for free.

---

## Design

### Record id = the dotted slug

`id: crt.state_machine`, not `SI-042`. Reasons: `validate_unique_ids_global()`
(`semantic_os.py:559`) already walks `self.records` and cross-checks `foreign_id_namespace()`, so
uniqueness + collision-proofing come with zero new code; ~790 Tier-3 rows cannot deterministically
allocate sequential numbers without a persisted counter (which would break byte-identical reseed on
any file add/delete); and one token means one thing for agents to say.

```python
_ID_RE["file_identity"] = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,4}$")
```

The **at least one dot** is load-bearing — it guarantees disjointness from single-token MIAR entry
ids like `crt`, `gaussian`.

### Required fields

```python
_FILE_IDENTITY_REQUIRED = (
    "id", "kind", "semantic_name", "physical_path", "status", "authority",
    "tier", "confidence", "provenance", "derivation",
    "canonical", "role", "semantic_layer",
    "filename_semantic_status", "filename_status_reason",
    "aliases", "concept_ids", "miar_entry",
    "summary_50", "why_this_identity", "evidence",
    "supersedes", "superseded_by",
)
```

New enums beside the existing ones at `semantic_os.py:78-92`:

| Enum | Values |
|---|---|
| `FILENAME_SEMANTIC_STATUS_ENUM` | `ALIGNED HISTORICAL MISLEADING COMPATIBILITY SPLIT UNKNOWN` |
| `IDENTITY_ROLE_ENUM` | `CANONICAL ADAPTER SHIM SPLIT_PART DEAD UNKNOWN` |
| `IDENTITY_TIER_ENUM` | `1 2 3` |
| `IDENTITY_CONFIDENCE_ENUM` | `HIGH MEDIUM LOW` |
| `IDENTITY_PROVENANCE_ENUM` | `CURATED DERIVED` |
| `SEMANTIC_LAYER_ENUM` | `MARKET_STRUCTURE FEATURE_SURFACE SCORING DECISION RISK EXECUTION RUNTIME DATA CONFIG GOVERNANCE RESEARCH AGENT INTEGRATION UTILITY UNCLASSIFIED` |

Field notes:
- `physical_path` — repo-relative POSIX, must exist, end `.py`, must **not** start `tests/`.
- `canonical: bool` — exactly one `true` per `physical_path`. Non-canonical rows exist only for
  genuine SPLIT cases.
- `derivation` — `null` for CURATED, `"path_slug/v1"` for DERIVED. This is what makes a machine row
  unambiguous.
- `miar_entry` — the **only** hand-authored cross-link. Everything else is derived (see constraints).
- `evidence` — reuses the existing `{path, symbol, line, type}` shape and the ±30-line drift check in
  `validate_evidence` (`semantic_os.py:980`). Bare symbols only (`StateMachine`, not
  `class StateMachine`) since the check is `symbol in line`.

### Worked example (Tier 1, MISLEADING)

```yaml
  - id: engines.candle_polarity_scorer
    kind: file_identity
    semantic_name: Candle Polarity Scorer
    physical_path: src/engines/rr_engine.py
    status: ACTIVE
    authority: advisory
    tier: 1
    confidence: HIGH
    provenance: CURATED
    derivation: null
    canonical: true
    role: CANONICAL
    semantic_layer: SCORING
    filename_semantic_status: MISLEADING
    filename_status_reason: >-
      "rr" reads as risk:reward, which this module does not compute. rr_engine.py:69-73 sets
      polarity = max((high-close)/range, (close-low)/range); the two terms sum to 1, so output is
      bounded [0.5, 1.0], and a zero-range candle returns 0.0. That is a candle-shape score, not a
      forward reward ratio. The module says so itself at :81 ("semantic":
      "candle_structure_quality"). Economic RR lives in src/core/ultron_risk_gate.py:230-245.
    aliases: [rr_engine, candle structure quality, rr_ratio]
    concept_ids: [CN-005]
    miar_entry: crt
    summary_50: >-
      Scores how close a candle's close sits to either extreme of its own range. Bounded
      [0.5, 1.0]. Not risk:reward.
    why_this_identity: >-
      The identity must state the quantity, because the filename states a different one and
      src/features/model_evidence.py already enforces producer-declared semantics against
      active_models.yaml. Renaming the file breaks the import graph; renaming the MEANING is free.
    evidence:
      - {path: src/engines/rr_engine.py, symbol: candle_polarity, line: 73, type: code}
      - {path: src/engines/rr_engine.py, symbol: rr_ratio, line: 79, type: code}
      - {path: src/core/ultron_risk_gate.py, symbol: rr_ratio, line: 230, type: code}
    supersedes: null
    superseded_by: null
```

### Tier-1 anchors (source-verified)

| semantic_id | physical_path | status | role |
|---|---|---|---|
| `crt.state_machine` | `src/config_layer/crt_engine_v2.py` | HISTORICAL | CANONICAL |
| `crt.state_topology` | `src/config_layer/state_identity.py` | ALIGNED | CANONICAL |
| `engines.candle_polarity_scorer` | `src/engines/rr_engine.py` | MISLEADING | CANONICAL |
| `engines.crt_score_adapter` | `src/engines/crt_engine.py` | SPLIT | ADAPTER |
| `engines.crt_scorer` | `src/engines/scoring_engine.py` | ALIGNED | CANONICAL |
| `engines.gaussian_compat_shim` | `src/engines/gaussian_engine.py` | COMPATIBILITY | SHIM |
| `engines.heuristic_gaussian_scorer` | `src/engines/heuristic_gaussian_engine.py` | ALIGNED | CANONICAL |
| `features.canonical_feature_contract` | `src/features/feature_schema.py` | ALIGNED | CANONICAL |
| `features.production_feature_pipeline` | `src/features/feature_pipeline.py` | ALIGNED | CANONICAL |
| `features.crt_feature_transcriber` | `src/features/crt_feature_builder.py` | ALIGNED | DEAD |
| `risk.capital_gate` | `src/core/ultron_risk_gate.py` | ALIGNED | CANONICAL |
| `risk.signal_quality_governor` | `src/core/regime_governor.py` | ALIGNED | CANONICAL |

`crt.state_machine` owns transition **enforcement** (`StateMachine._transition` at
`crt_engine_v2.py:980`); it *imports* `VALID_TRANSITIONS` from `state_identity.py:69`, which is why
the graph gets its own identity. `risk.capital_gate` and `risk.signal_quality_governor` must each
disclaim the other in `why_this_identity` — conflating them (plus `crt_engine_v2.py::UltronRiskEngine`)
is a live failure mode.

### Tier 3 is generated, not materialized

Only Tier 1 + Tier 2 live in the YAML (~60-150 reviewable records). Tier 3 is derived at seed time
from a pure function of the sorted path set. Rationale: a Tier-3 row asserts nothing a human decided,
so materializing ~790 of them into a hand-authored file is exactly the anti-pattern
`validate_no_derived_in_source` exists to prevent; deleted files would leave dangling paths;
and `git diff` on the YAML then shows only human decisions.

`derive_slug(rel_path)`: posix-normalize → strip `.py` and trailing `/__init__` → namespace segments
(`src/a/b/c` → `a.b.c`; `scripts/a/b` → `scripts.a.b`; `root.py` → `root.<name>`) → lowercase,
non-alphanumerics to `_`, collapse repeats, prefix `x_` if empty/leading-digit → ensure ≥1 dot →
elide to `first + last two` if >5 segments. Collisions: group by slug over the sorted path list,
append `__2`, `__3`… to all but the first, recorded in `derivation` as `path_slug/v1#dedup2` so it is
never silent. Curated paths are skipped before derivation, so a derived slug can never shadow a
curated one.

Tier-3 rows carry **empty `aliases`** deliberately — a derived basename alias would collide on every
duplicate filename (`__init__.py` alone gives ~50). Basename lookup is a query concern.

Auto-vs-curated is unambiguous on four fields that a validator forces to move together:
`provenance == "DERIVED"`, `tier == 3`, `derivation != null`, `why_this_identity == ""`.
**Upgrade path:** add the record to the YAML as CURATED; the deriver skips that path on the next
seed. One YAML block, no renumbering, no migration.

---

## Files to change

### 1. `src/governance/semantic_os.py` — all additive

| Location | Edit |
|---|---|
| `:78` `KIND_ENUM` | add `"file_identity"` |
| `:101` `_ID_RE` | add the `file_identity` slug regex |
| after `:92` | add the 6 enums above |
| after `:146` | add `_FILE_IDENTITY_REQUIRED` |
| `:152` `_FORBIDDEN_HAND_FIELDS` | add `encyclopedia_id`, `script_registry_id`, `semantic_id` |
| after `:177` | `_IDENTITY_TIER1_FLOOR = len(SPINE_FILES)` — monotonic ratchet |
| `:432` `__init__` | append keyword `file_identities: list[dict] \| None = None` (back-compatible: `tests/test_semantic_os.py:66` passes 4 positional args) |
| `:447` `load` | 5th `_load("file_identities.yaml", "file_identities")` |
| `:468` `records` | append sorted identities |
| `:477` `get` | add the 5th table (currently iterates 4 literally) |
| `:524` `summary` | add identity counts + `spine_identified` |
| new | `identity_by_path() -> dict[str, str]` — canonical rows only, deterministic |
| `:1161` `validate_record` | dispatch `file_identity` → `_validate_file_identity` |

New validators wired into `validate_all` (`:1110`) after `validate_alias_uniqueness`:

- `validate_identity_paths` — path exists on disk (reuse `_resolve_repo_path` at `:420`), is `.py`,
  is not under `tests/`.
- `validate_identity_canonicality` — exactly one `canonical: true` per `physical_path`.
- `validate_identity_spine_coverage` — every `SPINE_FILES` entry has a Tier-1 HIGH identity; mirrors
  `validate_spine_coverage` (`:856`) including the ratchet.

Extended (not new): **`validate_alias_uniqueness` (`:1025`)** currently walks only `self.concepts`.
It must walk concepts *and* identities into one `owner` dict, keying on `name`/`semantic_name` +
`aliases`, preserving the case-insensitive normalisation that `test_alias_collision_is_case_insensitive`
pins. This is what keeps `semantic_query`'s `AmbiguousAliasError` honest.
`validate_fk_resolution` (`:717`) gains a small identity block (`miar_entry`, `concept_ids`,
`superseded_by`).

`_validate_file_identity` asserts the enum memberships, the tier↔confidence↔provenance coherence
table (`1→HIGH/CURATED`, `2→MEDIUM/CURATED`, `3→LOW/DERIVED`), `derivation is None` iff CURATED,
that Tier-1 may not be `UNKNOWN`, that a non-`ALIGNED`/`UNKNOWN` status requires a non-empty
`filename_status_reason`, and **explicitly rejects** hand-authored `owner_boundary` /
`encyclopedia_id` / `script_registry_id` (needed because `owner_boundary` is legitimately in
`_CONCEPT_REQUIRED`, so the generic forbidden-field check will not catch it).

### 2. `src/governance/semantic_identity.py` — new, ~200 lines

Pure and dependency-light: `DERIVATION_VERSION`, `derive_slug`, `derive_semantic_name`,
`derive_tier3_identities(paths, curated)`, `resolve_identity_index(curated, derived) -> {path: record}`
(the single join point used by both OBJ and Excel), and `validate_projection(...)` for the
projection-level invariants the registry cannot see (curated↔derived slug collision, total coverage).

### 3. `scripts/governance/seed_semantic_os.py`

`build_records` (`:55`) gains a `"file_identities"` key = curated ∪ derived, sorted by id.
`main()` needs **no change** — it already iterates `records.items()` and calls
`SemanticOSRegistry.dump()` (`:112-113`), and `dump` (`:1130`) runs `validate_record` per row, so
derived rows get schema-validated for free and `index_meta.json` self-updates. Determinism holds:
`discover_universe` returns sorted, derivation sorts, `dump` sorts by id and key, `_TS` is pinned.

### 4. `src/governance/semantic_objects.py` — the OBJ join

In `build_objects()` (`:478`), after the registry block (`:499-529`), compute the identity index
**in-process** (not by reading `identities.jsonl`) — `build_objects` is called directly by
`tests/test_semantic_os_objects.py:41` with no seed guarantee, and the seeder itself calls
`build_objects`, so reading the projection would create an order dependency between two outputs of
one command.

Add five keys to the record literal (`:578-625`), always present, `None` for test objects:
`semantic_id`, `semantic_name`, `filename_semantic_status`, `identity_tier`, `identity_provenance`.

`FIELD_EVIDENCE_CLASS` (`:67-115`) additions — `tests/test_semantic_os_objects.py:97,105` enforces
two-way exhaustiveness, so each needs a justified class:

| Field | Class | Why |
|---|---|---|
| `semantic_id` | `HEURISTIC` | A field carries one class, and the honest class is the weakest across its sources. Tier 1/2 is human judgement (same shape as `relevance`/`group`, already HEURISTIC at `:82-85`); declaring it PROVEN would invite over-trust in exactly the way this layer exists to prevent. Consumers read `identity_provenance` to tell the cases apart. |
| `semantic_name` | `HEURISTIC` | Same; for derived rows it is title-cased path text owned by no artifact of record. |
| `filename_semantic_status` | `HEURISTIC` | Explicitly a classification; `UNKNOWN` for all Tier 3. |
| `identity_tier` | `PROVEN` | Read verbatim off the record that declares it — the same exact-key-join relationship that makes `encyclopedia_id` (`:87`) PROVEN. |
| `identity_provenance` | `PROVEN` | Records which build path produced the row; the build owns that fact exactly. |

Also extend the tuple in `test_curated_classifications_are_not_claimed_proven`
(`tests/test_semantic_os_objects.py:121`) with the three HEURISTIC fields, so a future contributor
cannot quietly promote the slug to PROVEN. And add an `"identity"` block to `coverage_report()`
(`:630`) publishing the tier/status gap rather than hiding it, per that function's established style.

### 5. `scripts/governance/enrich_workbooks_with_semantic_identity.py` — new

```
--workbook {scripts,src,tests,all}   default all
--projection data/semantic_os
--check                              dry run; exit 1 on floor breach
--min-join-rate 0.98
--json
```

Fails loudly if `identities.jsonl` is absent rather than degrading to an empty join — a workbook of
blank Semantic-ID cells reads as *coverage measured at zero* rather than *not measured*.

**Joins:**
- **Workbook 1** `scripts_business_functionality.xlsx` / `Scripts Analysis`: column A is relative to
  `scripts/`, not the repo root (the generator strips the prefix at
  `_scripts_functionality_export.py:304`). Re-prefix with the *same* expression
  `grok/book_file_coverage_report.py:149-153` uses, so the two consumers agree by construction.
  Append **D-H**: `Semantic ID`, `Semantic Name`, `Filename Semantic Status`, `Identity Tier`,
  `Identity Provenance`. On the `Counts` sheet append metric **rows** (join rate, unjoined, Tier-1
  count), gated on the label not already present.
- **Workbook 2** `results/analysis/src_business_functionality.xlsx` / `src_py_inventory`: column A
  verbatim after backslash normalisation. Same D-H headers.
- **Workbook 3** `docs/analysis/tests_functionality_inventory.xlsx` / both `Test Functionality` and
  `By File`: append **G-J** `Covers Semantic ID`, `Covers Semantic Name`, `Covers Filename Status`,
  `Coverage Join Method`. Column B is used only as a row key — deliberately **not** given an identity.

`Covers Semantic ID` derives from the `Referred files` column: split on `"; "`, drop non-`.py` and
`tests/`-prefixed tokens, look each up in `identity_by_path`, join hits with `"; "`. `Coverage Join
Method` records `IMPORT_PATH_EXACT` / `IMPORT_PATH_PARTIAL:<n>` / `UNRESOLVED:<n>` / `NONE`. That
distinction matters: `test_functionality_excel.py:190-193` emits a best-effort path even when the
module does not exist on disk, so a raw token is not proof of a real file — collapsing that into a
blank cell would silently overstate coverage.

**Idempotence:** look up each header in row 1 and reuse its column if present, else append at
`ws.max_column + 1`. Never `insert_cols`, never reorder, never touch A-C (A-F on wb 3). Re-running is
an in-place overwrite.

**Style preservation:** open with plain `load_workbook` (not `read_only`/`data_only`).
`copy.copy()` fill/font/alignment from `ws.cell(1,1)` onto new headers and from `ws.cell(i,1)` onto
each new data cell — this reproduces wb 1's `F2F2F2` banding and thin borders without re-deriving the
parity rule, and correctly reproduces wb 2's plain header. Set explicit widths for new columns and
**rewrite `ws.auto_filter.ref`** on all three (wb 1 hardcodes `A1:C{n}`, wb 3 `A1:F{n}`, wb 2 froze
`ws.dimensions` at generation) or the filter will cover fewer columns than exist. Leave `freeze_panes`
alone — `"A2"` is column-independent. Append at most two provenance lines to wb 3's `README` sheet.

### 6. Docs

- `docs/governance/SEMANTIC_OS_V1_DESIGN.md` — revise §2/§3: the "five first-class entity kinds"
  table (`:117`) becomes six, and reconcile the new `file_identity` record kind against the L0
  `identity_kind` enum (`:95-111`) so the two uses of the word do not contradict. Mark as a v1.2
  revision.
- `docs/governance/SEMANTIC_OS_CONTRACT.md` — add the kind to the entity table.
- `docs/reference/schemas.md` — add the record schema section.
- `docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md` — the report. **Tracked tier, not
  `reports/governance/`**: an attestation that "no files were renamed" is worthless if it cannot be
  read on a fresh clone, and only 4 files under `reports/` are tracked. Emit the disposable machine
  run-log to `reports/governance/semantic_file_identity_run.json` via `--json` and cite it from the
  tracked `.md`.

---

## Verification

### New: `tests/test_semantic_identity.py`

Positive: `validate_all()` and `validate_all(strict=True)` both clean; slug uniqueness + global
disjointness from `foreign_id_namespace()`; every id matches the regex *and* contains a dot (asserted
separately — the dot is what buys MIAR disjointness); every `physical_path` exists, is `.py`, not
under `tests/`; exactly one canonical per path; **total coverage** (`{physical_path} ==
set(discover_universe("code"))`); every `SPINE_FILES` entry Tier-1 HIGH + ratchet cannot regress;
tier/confidence/provenance coherence; derived rows unambiguous on all four fields; derivation
deterministic *and order-invariant* (run twice + once shuffled); `validate_projection() == []`;
`identities.jsonl` present in the seed output.

Two that prevent the layer from being hollow:
- `test_classification_vocabulary_is_not_decorative` — at least one curated record for each of
  `MISLEADING`, `COMPATIBILITY`, `HISTORICAL`, `SPLIT` (all four demonstrably exist), and
  `len(curated) >= 50`. Without it the layer passes by calling everything `ALIGNED`.
- `test_identity_layer_touches_no_runtime_module` — the set of `src/` files importing
  `governance.semantic_identity` is exactly `{semantic_objects.py, semantic_os.py}`. This is the
  permanent mechanical guarantee that the identity layer never becomes a runtime dependency.

Negative half, mirroring the existing `_clone` + `_assert_caught` pattern
(`tests/test_semantic_os.py:55-76`): id without a dot; id equal to a MIAR entry id (`crt`);
`physical_path` under `tests/`; path not on disk; two canonical on one path; zero canonical;
`tier: 1` with `confidence: LOW`; `tier: 1` with status `UNKNOWN`; `MISLEADING` with empty reason;
an identity alias equal to a **concept** name (proves the `validate_alias_uniqueness` extension
fires); hand-authored `owner_boundary`; hand-authored `imports`; a spine file dropped; evidence
drifted >±30 lines.

### New: `tests/test_semantic_identity_workbooks.py`

Every test `pytest.skip`s if its workbook is absent (all three are untracked). Asserts: new headers
present and A-C/A-F unchanged; **the positional consumer contract holds** — actually import and run
`grok/book_file_coverage_report.py`'s loaders and check `row[0..2]` still mean file/summary/referred;
join rate ≥ 98% on wb 1/2; enrichment idempotent (copy to `tmp_path`, run twice, compare
`max_column` and every cell — never mutate the real artifact from a test); wb 3 has **no** `Semantic
ID` header (pins decision 3); `Coverage Join Method` honest (sentinel → `NONE`; non-empty ids →
`IMPORT_PATH_*`).

### Must stay green

`tests/test_semantic_os.py` (esp. `test_live_registry_is_clean`,
`test_seed_runs_and_is_byte_identical_on_rerun`, `test_no_derived_field_is_hand_authored`,
`test_ambiguous_alias_is_caught`, `test_spine_coverage_floor_cannot_regress`,
`test_validate_record_rejects_unknown_kind` — confirm its fixture uses a genuinely unknown kind, not
`"identity"`), `tests/test_semantic_os_objects.py`, `tests/test_script_registry.py`,
`tests/test_script_matrix_sync.py`, `tests/test_miar_registry.py`, `tests/test_current_findings.py`,
`tests/test_doc_citations.py`, `tests/test_topic_docs.py`.

### End-to-end

```bash
python scripts/governance/seed_semantic_os.py --check && python scripts/governance/seed_semantic_os.py --objects && python -m pytest -q tests/test_semantic_os.py tests/test_semantic_os_objects.py tests/test_semantic_identity.py
```

Then confirm resolution works in both directions — `semantic_query` resolves
`"Candle Polarity Scorer"` → `engines.candle_polarity_scorer` → `src/engines/rr_engine.py`, and the
OBJ record for that path carries the matching `semantic_id`.

---

## Execution order

Three independently revertable commits. Nothing outside `src/governance/` is touched; no Python file
is renamed; no import statement is modified.

**Pre-flight (read-only):** `construction_protocol.py check`; baseline the two semantic test files;
`seed_semantic_os.py --check`. Then write
`docs/governance/build_manifests/CH-semantic-file-identity.impact.json` with
`change_classes: ["SCRIPT_LIFECYCLE_CHANGE", "DOCUMENTATION_ONLY"]` and `unknowns: []` (a blocking
unknown fails `validate-impact`). The pair matters: `DOCUMENTATION_ONLY` alone would trip the
`src/`-diff guard at `construction_protocol.py:159-162`, which fires only when that class is the
*sole* entry.

**Commit 1 — schema + code, empty registry.** Edits 1-4 above plus `file_identities.yaml` containing
only `file_identities: []`, plus `tests/test_semantic_identity.py`. After this every file already has
a Tier-3 identity and OBJ carries `semantic_id` — the layer is live and total before a single human
word is written. Tier-1 tests fail until commit 2, so either gate them behind the ratchet or land
commits 1+2 together.

**Commit 2 — curation.** The ~50-60 Tier-1 records (anchors above) plus Tier-2. Cap Tier 2 at the ~93
boundary-claimed paths plus hand-picked additions — pulling all 785 encyclopedia rows in would make
"MEDIUM confidence" mean "we pasted the encyclopedia". Update the three docs.

**Commit 3 — script + SITS + workbooks + report.** Add the enricher and its test, then register SITS
**the same turn** (`script_census.py --write-stubs` → overlay in `seed_script_registry.py` with
`purpose != GRANDFATHER_UNCLASSIFIED` → `seed_script_registry.py` → `generate_script_matrix.py`).
Then regenerate-then-enrich — regeneration overwrites each workbook wholesale, so it **must** come
first or the appended columns are destroyed:

```bash
python scripts/analysis/src_business_functionality_inventory.py && python _scripts_functionality_export.py && python scripts/analysis/test_functionality_excel.py && python scripts/governance/seed_semantic_os.py --objects && python scripts/governance/enrich_workbooks_with_semantic_identity.py --workbook all --check && python scripts/governance/enrich_workbooks_with_semantic_identity.py --workbook all
```

Finish with the full suite and `construction_protocol.py validate-completion`.

**Rollback:** `git revert`, then re-run the seeder and the three generators. `data/semantic_os/**` is
gitignored and the workbooks are untracked, so both regenerate from source.

---

## Out of scope

No Python file renamed, no import modified, no module API/formula/threshold/config/CRT-transition/
feature-calculation/execution change. `filename_semantic_status` is a *classification*, not a rename
authority — the report will list future rename candidates without acting on them. The layer is pinned
`authority: advisory` by `_stamp`, so it grants no promotion or production authority (§6.5).
