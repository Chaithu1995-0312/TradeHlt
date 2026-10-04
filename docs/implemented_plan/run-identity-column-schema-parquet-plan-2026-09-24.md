# Plan: Run identity → artifact column schema → Parquet system of record

> **STATUS: PARKED 2026-09-24** — not approved, nothing implemented, no repo files edited this session.
> **Resume with:** "Implement Phase A of the parked run-identity plan" (this file). Re-run the Working
> Tree Preflight (CLAUDE.md §1.5) first — the tree is dirty and other sessions write to it.
> **Decided by user:** code list = auto-from-imports + curated critical subset; new sibling module
> (leave `stack_version.py` untouched); Parquet = system of record (staged, flip gated).
> **Still needs approval before Phase A:** new `run_identity` section in the ACTIVE config
> `v2_htfcrt_2026_08.json` (§6.2 gate). **Before Phase C3:** CLAUDE.md storage-rule change + pyarrow
> becoming a required dependency.
> **Facts re-verify before building (found this session, may have moved):** `config_hash` = `params`
> only; `configs/stack_epoch_log.jsonl` absent; `stack_version` callers = `baseline_capture.py` +
> `tests/test_stack_version.py`; manifest writer `backtest_v2.py:4207-4252`; newest run folder
> `results/run_20260923_072728_XAUUSD__…_7de09f62` (corpus sha256 `4d73f5ce…aba56`, 47,275 rows).
> **Unwritten session-log entries:** this session's SESSION LOG blocks were NOT appended to
> `assistant_project.md` (plan mode blocked edits) — append them on resume.

## Context

Every backtest run folder (e.g. `results/run_20260923_072728_XAUUSD__…_7de09f62/`) must be
attributable to the exact **config, YAML, code and data** that produced it, so that a PnL change
can be traced to the value/file that caused it. Today it cannot:

- `config_hash` covers only the `params` block (`_compute_params_hash`); ~50 other config
  sections are invisible — a non-`params` edit that moves PnL leaves `config_hash`,
  `config_version` and the folder suffix unchanged (F-089 pattern).
- Code identity = `git rev-parse HEAD` + `tree_dirty` bool (`backtest_v2.py:2704-2730`), layer-trace
  only; the tree is permanently dirty (ongoing validation, concurrent sessions) so HEAD is a false pin.
- `src/config_layer/stack_version.py` already computes content-hash identity (`behavior_hash` /
  `provenance_hash`) but covers only the config file (whole-file, churns on `notes`), ontology frozen
  slice, feature schema ids, `candle_math.py`/`derived_math.py`, and executing model checkpoints.
  It omits `market_crt_states.yaml`, the engine/backtest/pipeline code, the corpus, and per-section
  identity. Callers: `baseline_capture.py`, `tests/test_stack_version.py` only. Its epoch ledger
  `configs/stack_epoch_log.jsonl` has never been written (file absent).
- `trades.csv` (declared analysis + training surface) has no per-column unit/dtype/role declaration
  (F-061 scale mix, float-serialized ordinals, dead `cached_session`, legacy `cached_*` aliases).

User decisions (2026-09-24): code list = **auto from imports + curated critical subset**; identity
logic in a **new sibling module** (stack_version untouched); **Parquet becomes system of record**.

Order: **A (run identity) → B (column schema) → C (Parquet SoR, staged)**. Phase A is the first
implementation turn; B and C are separate authorized turns.

## Phase A — `src/config_layer/run_identity.py` (new, sibling of stack_version)

Pure, read-only, `authority: NONE`. Builds one `run_identity` block:

| Component | Content |
|---|---|
| `stack` | `compute_stack_version()` result reused verbatim (`behavior_hash`, `provenance_hash`) — never re-derived |
| `config_sections` | sha256 of canonical JSON (sort_keys) per top-level section of the active config; `behavior_sections_hash` over all except a declared exclusion set (`notes`, `_comment_*`, `created_at`, `promoted_at`, `config_hash`) |
| `yaml` | sha256 per file of `configs/formulas/*.yaml` (globbed, so `market_crt_states.yaml` is covered) + `active_models.yaml` |
| `code_manifest` | `{relpath: sha256}` for every `sys.modules` entry whose `__file__` is under `src/`; `code_hash` = sha over the sorted map |
| `critical_modules` | curated list (config section `run_identity.critical_modules`, strict `_require`, non-`params` ⇒ hash-neutral); reports `critical_missing` (listed but not imported = list drift) and `critical_changed` flags |
| `dataset` | corpus path, rows, sha256 |
| `git` | HEAD sha, `tree_dirty`, and imported files that differ from HEAD — information only, never identity |
| `run_identity_hash` | sha over (`behavior_sections_hash`, `yaml`, `code_hash`, `stack.behavior_hash`, dataset sha256) |

**Concurrent-edit guard:** capture `code_manifest` twice — after engine construction (run start) and at
manifest write (run end). Any file hash that differs ⇒ `identity_status = CODE_CHANGED_DURING_RUN`
(recorded, run not failed; follows the existing best-effort manifest discipline at
`backtest_v2.py:4207-4252`).

**Wiring:** in `backtest_v2.py` manifest block (~line 4216) add `"run_identity": {...}` and bump
`"schema": "run_manifest_v3"` (additive; v2 keys unchanged). Start-snapshot taken where
`_build_layer_trace_emitter` is called (~line 3030).

**Diff tool:** `scripts/governance/run_identity_diff.py <run_dir_a> <run_dir_b>` → lists differing
config sections, YAML files, code files, dataset. SITS-register the script (census → seed → matrix).

**Governance same turn:** classify against `change_contracts.json` + BUILD_IMPACT_MANIFEST;
register `run_manifest_v3` in `docs/governance/schema_version_registry.json`
(`SCHEMA_EVOLUTION_CONTRACT.md` read first); document block in `docs/reference/schemas.md §9`;
topic doc update; SESSION LOG.

## Phase B — artifact column schema (separate turn)

Descriptive-first YAML registry per artifact, e.g. `configs/schemas/artifacts/trades.v1.yaml`: per
column `dtype` (logical), `unit`/basis (`price`, `close_relative`, `R`, `ordinal`…), `role`
(`id` · `feature_at_entry` · `outcome` · `basis` · `provenance` · `diagnostic` · `deprecated_alias`),
`fm_id` / `alias_of` (lineage points at ontology, never restates formulas), `known_issue`
(e.g. `cached_session: dead_constant`). Floor: declared columns == produced header of a real run.
`role` is the leakage guard for training (outcome columns never features). Covers trades.csv first,
then events / telemetry / summary / corpus.

## Phase C — Parquet as system of record (staged, separate turns)

- **C1 dual-write:** backtest writes `trades.parquet`, `events.parquet`, `crt_telemetry.parquet`
  alongside existing files; explicit typed pyarrow schema from Phase B (no inference — fixes `3.0`
  ordinals); `run_id` + `run_identity_hash` as columns; full `run_identity` + schema id in file
  key-value metadata. Layer trace → per-run partition
  (`results/layer_trace/XAUUSD/run_id=lt_…/part.parquet`) with the 15 repeated identity keys moved to
  metadata — structurally ends cross-run collisions. Reuse `utils/parquet_store.py` round-trip
  (lossless, null-vs-absent) verification approach.
- **C2 certification:** N runs where Parquet round-trips equal to legacy files; census and migrate
  readers of `trades.csv` / `events.jsonl`.
- **C3 flip (user-gated):** pyarrow becomes a required dependency for backtest (today an optional
  extra behind an import guard — convention change); update CLAUDE.md storage wording and the
  `parquet_store.py` docstring ("JSONL stays SoR"); decide legacy-file retirement.

## Critical files

- New: `src/config_layer/run_identity.py`, `scripts/governance/run_identity_diff.py`, `tests/test_run_identity.py`
- Edit: `src/runtime/backtest_v2.py` (manifest block ~4216, start snapshot ~3030), active config
  `configs/production/v2_htfcrt_2026_08.json` (new `run_identity` section — edit to active config
  needs explicit user approval per §6.2 gate)
- Reuse: `stack_version.compute_stack_version`, `stack_version._sha256_file/_sha256_json` pattern,
  `production_config.get_full_config_dict`, `bar_structure_snapshot.corpus_sha256`,
  `utils/run_manifest.py`, `utils/parquet_store.py`

## Verification

1. Preflight: `git status --porcelain`; `venv/Scripts/python.exe -c "import sys; print(sys.prefix)"`;
   baseline `python scripts/maintenance/check_governance_invariants.py --all` failure count BEFORE edits.
2. `pytest tests/test_run_identity.py tests/test_stack_version.py -v`: section hashes deterministic; a
   `notes` edit moves provenance but not `behavior_sections_hash`; code manifest contains
   `config_layer/crt_engine_v2.py`; critical-list drift reported; mid-run file change ⇒ `CODE_CHANGED_DURING_RUN`.
3. `venv/Scripts/python.exe src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv --output results`
   (echo path + 47,275 rows): manifest carries `run_identity`, `schema: run_manifest_v3`; `trades.csv`
   byte-identical to `run_20260923_072728` (identity recording is decision-neutral).
4. Run twice → `run_identity_diff.py` reports no differences; run against a shadow config copy with
   one non-`params` value changed → diff names exactly that section.
5. Green floor re-run: no new failures vs baseline; `construction_protocol.py validate-completion <manifest>`.
