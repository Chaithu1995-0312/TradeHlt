# Trace → Parquet → DuckDB Query Layer Integration

## Context

The request is to integrate a "Trace / Parquet / DuckDB" analytics layer into the codebase.
Investigation (3 Explore agents + direct verification) established the real starting state:

- **The "Trace" is `CRTConstructionTrace`** ([src/runtime/crt_construction_trace.py](src/runtime/crt_construction_trace.py))
  — a per-bar, backtest-only, `enabled:false` observational sidecar that joins the CRT engine's
  state to the declarative ontology resolver's state and appends one JSONL row per bar to
  `logs/crt_construction/{instrument}_crt_construction.jsonl`. It was just tracked into git this
  session (commit `3948650`). It has **no Parquet projection today** — it isn't in
  `jsonl_to_parquet.py`'s `FAMILY_DEFAULTS`.
- **Parquet already has a governed layer**: [src/utils/parquet_store.py](src/utils/parquet_store.py)
  (JSONL stays system of record; Parquet is a regenerable, staleness-checked sidecar,
  `iter_records()` falls back to JSONL) + [scripts/maintenance/jsonl_to_parquet.py](scripts/maintenance/jsonl_to_parquet.py)
  CLI, covering 5 families today: `_crt_telemetry.jsonl`, `_events.jsonl`, `opportunities.jsonl`,
  `clean_labels.jsonl`, `_bar_structure.jsonl`.
- **DuckDB has exactly one precedent**: [scripts/analysis/query_decision_atlas.py](scripts/analysis/query_decision_atlas.py)
  (SCR-504) — connects and runs SQL directly over Parquet files via `read_parquet()` views,
  built ad hoc (its own `_rel()` helper, no shared module). `duckdb` is currently bundled only in
  the unrelated `mt5_analytics` pyproject extra.
- **Governance guardrail verified directly** (not just via the sub-agent's report):
  [docs/governance/STORAGE_PRESERVATION_CONTRACT.md](docs/governance/STORAGE_PRESERVATION_CONTRACT.md)
  and [docs/governance/PHYSICAL_STORAGE_ARCHITECTURE.md](docs/governance/PHYSICAL_STORAGE_ARCHITECTURE.md)
  forbid Parquet/DuckDB from ever becoming **authority** for the frozen L0–L5 canonical identity
  layer (`src/identity/`'s job) — but explicitly bless Parquet as a "sidecar" / "projection" over
  JSONL for everything else, which is exactly what `parquet_store.py` and
  `query_decision_atlas.py` already do. **This plan stays entirely in that lane**: read-only
  research tooling in `scripts/analysis/` + `src/utils/`, never touching `src/identity/`, never
  wired into any live/backtest decision path, never claiming authority over anything.

**User decisions (via AskUserQuestion):**
1. Cover `CRTConstructionTrace` **and** the 5 existing families with one shared, reusable DuckDB
   query layer — not a one-off script for the trace alone. This dedupes the boilerplate
   `duckdb.connect()` + `read_parquet()` pattern currently only living inside
   `query_decision_atlas.py`.
2. Add `duckdb` to the `parquet` pyproject extra so `pip install tradelatest[parquet]` gets both
   pyarrow (projection-build) and duckdb (query) in one step.

## Changes

### 1. `pyproject.toml`
Add `duckdb` to the `parquet` extra; update its comment to describe the two roles (build vs
query). Leave `mt5_analytics`'s own `duckdb` entry as-is (harmless duplication, different
subsystem).

### 2. `scripts/maintenance/jsonl_to_parquet.py`
Add a `FAMILY_DEFAULTS` entry for the trace:
```python
"_crt_construction.jsonl": ("engine_state_after", None),
```
Partition by `engine_state_after`, mirroring `_bar_structure.jsonl`'s existing rationale (research
reads this per CRT-state stratum) — cite the same reasoning in a comment. `--partition-by ''`
remains available at conversion time to override if that turns out wrong once real data exists.
Update the module docstring's family-defaults table with a one-line entry for the new family
(measured columns: none yet — first real conversion will confirm sparsity, note as "TBD, no
production run has `enabled:true` yet").

### 3. New: `src/utils/duckdb_query.py` (sibling of `parquet_store.py`, `jsonl_writer.py`)
Single shared helper, generalizing `query_decision_atlas.py`'s inline `_rel()`/view-registration
pattern so no future script reinvents it:
- `duckdb_available() -> bool` — same optional-import-guard shape as `parquet_available()`.
- `open_views(table_globs: dict[str, str], *, read_only=True) -> duckdb.DuckDBPyConnection` —
  for each `{name: glob_pattern}` pair, registers `create view {name} as select * from
  read_parquet('{glob_pattern}')`, transparently handling both a single `.parquet` file and a
  partitioned directory (`.../kind=*/*.parquet`) via the same glob.
- Raise `RuntimeError` pointing at `pip install tradelatest[parquet]` when duckdb is absent —
  same message convention as `parquet_store.compact_jsonl` (`parquet_store.py:441-445`).
- **AST-level constraint**: this module imports nothing from `feature_pipeline`, `crt_engine`,
  `feature_states`, or any recompute-capable module — it is pure I/O over already-built Parquet
  files, never a substitute for the source JSONL.

### 4. New: `scripts/analysis/query_trace.py`
The concrete deliverable. Generalizes `query_decision_atlas.py`'s CLI shape (`--sql` for ad-hoc
queries, default section prints when no `--sql` given) across all 6 families using
`duckdb_query.open_views`:
- A small `FAMILY_GLOBS` table (family name → glob under `logs/`/`results/`), reusing the same
  family keys as `jsonl_to_parquet.FAMILY_DEFAULTS` so the two modules describe one vocabulary.
- `--family {crt_construction,crt_telemetry,events,opportunities,clean_labels,bar_structure}`
  (repeatable) to select which views to register; default = all with an existing projection.
- `--list` — prints which families currently have a Parquet projection on disk and their row
  counts (skips silently, not an error, for families with none yet — e.g. `crt_construction`
  until the trace is first enabled and converted).
- `--sql "<query>"` for ad-hoc queries against the registered views, same UX as
  `query_decision_atlas.py`.
- Header comment marks it **READ-ONLY. DESCRIPTIVE ONLY.** — no p-value/verdict/economic claim,
  matching this repo's research-tooling convention.

### 5. Tests
- `tests/test_duckdb_query.py` — `open_views` over synthetic single-file and partitioned-directory
  parquet fixtures (tmp_path), missing-duckdb fail-open message, glob resolution correctness.
  Follow `tests/test_parquet_store.py`'s fixture style.
- Extend `tests/test_jsonl_to_parquet*` (or add if none exists — check first) to assert
  `resolve_family` returns the new `_crt_construction.jsonl` default.
- A real-reader-parity test building a projection over a tiny synthetic
  `crt_construction_trace`-shaped JSONL sample (using the schema in
  `docs/reference/schemas.md` §9.17 / the emitter's own field list) — per the standing lesson in
  memory ([[project-jsonl-parquet-projection]]): round-trip equality alone is not enough, a
  new family needs its real reader exercised both ways before being trusted.
- `tests/test_query_trace.py` (or extend the SITS/script tests) confirming `--list`/`--sql` run
  without error against a small fixture atlas.

### 6. SITS registration (§3.1 item 1b, non-optional for the new script)
1. `python scripts/analysis/script_census.py --write-stubs` to add
   `scripts/analysis/query_trace.py`.
2. Add its overlay row in `scripts/governance/seed_script_registry.py` — category `DIAGNOSTIC`,
   lifecycle `ACTIVE`, `implementation_status: LOGIC_IN_SCRIPT` (same classification as the
   `query_decision_atlas.py` precedent at that file's existing entry).
3. `python scripts/governance/generate_script_matrix.py` to regenerate the matrix.
4. `jsonl_to_parquet.py` needs no re-registration — only its `FAMILY_DEFAULTS` dict grows
   (additive, not a config/hash change).

### 7. Docs (Documentation Drift Protocol, §6.2/§6.3/§6.4)
- `docs/reference/schemas.md` §9.17 — add a short "Parquet projection" note under the
  `CRTConstructionTrace` schema entry: family suffix, partition key, how to build
  (`jsonl_to_parquet.py`) and query (`query_trace.py`).
- Check `docs/topics/crt-spine.md` (already references this trace at lines 11/49/70/93) — append
  one dated Discussion entry noting the projection+query capability now exists, rather than
  creating a new topic doc (§6.2 rule 1: existing-doc-first).
- **Do not** touch `active_models.yaml`'s `machine_readable_sources` table — this is a read-path
  query tool, not a new source of truth.
- **No F-id / finding registered** — pure tooling, no economic or statistical claim.

### 8. Construction Protocol (§3.3b)
Classify the change against `docs/governance/change_contracts.json` before implementing
(BUILD_IMPACT_MANIFEST), then `python scripts/governance/construction_protocol.py validate-completion <manifest>`
/ `check` after.

## Explicit non-goals (keep scope tight)

- Do **not** flip `crt_construction_trace.enabled` anywhere — stays the user's own toggle.
- Do **not** touch `src/identity/` or make any Parquet/DuckDB object "authority" for L0–L5 —
  the Storage Preservation freeze stays fully respected and unreopened.
- Do **not** migrate `query_decision_atlas.py` onto the new shared helper — it's already governed
  and registered; leave it as optional future cleanup, not part of this change.
- Do **not** wire DuckDB/Parquet into `engine_runner.py`, `backtest_v2.py`, or
  `live_engine_hook.py` — strictly read-only offline research tooling.

## Verification

1. `venv/Scripts/python.exe -m pytest tests/test_parquet_store.py tests/test_duckdb_query.py tests/test_query_trace.py -v`
2. `venv/Scripts/python.exe scripts/maintenance/jsonl_to_parquet.py --dry-run --glob "logs/crt_construction/*.jsonl"`
   (confirms family resolution; real conversion only meaningful once the trace has been enabled
   for at least one run)
3. `venv/Scripts/python.exe scripts/analysis/query_trace.py --list` — confirms all 6 families
   resolve and view registration works against whatever projections exist on disk.
4. `python scripts/maintenance/check_governance_invariants.py --all` (green floor).
5. `python scripts/governance/construction_protocol.py check`.
6. Per-response `📝 SESSION LOG ENTRY` in `assistant_project.md` (§6, unconditional).
