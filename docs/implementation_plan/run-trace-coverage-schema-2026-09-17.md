# Run / Trace coverage schema — technical implementation design

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Status** | DESIGN ONLY — no code, config, or schema file changed by this document |
| **Task class** | `OBSERVATION_ONLY` (every phase below writes provenance beside decisions, never into them) |
| **ACTIVE_VERSION** | `v2_htfcrt_2026_08` |
| **Builds on** | [`LIVE_CHART_STATE_MONITOR_ARCHITECTURE_2026-09-16.md`](../architecture/LIVE_CHART_STATE_MONITOR_ARCHITECTURE_2026-09-16.md) (Grok, high-level) · [`using-trace-id-i-need-elegant-seahorse.md`](using-trace-id-i-need-elegant-seahorse.md) (lookup tool) · [`CANONICAL_LAYER_IDENTITY_CONTRACT.md`](../governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md) (L0–L5 identity) · `src/runtime/layer_trace.py` (span emitter) |
| **Authority** | Information only (§6.5). Grants no production, economic, or promotion authority. |

---

## 0. Problem in one paragraph

Grok's architecture freezes the join keys (`run_id` + `(instrument, bar_ts)` + `cost_model_id` +
`constructor_id`, §4.1) but not **which module writes which key, in which clock, on which asset**.
Without that, "everything about one run" and "everything about one bar" cannot be answered by
machine, and a missing row looks the same as a row that was never supposed to exist (F-079 class).
This design turns `run_id` and `trace_id` into a **coverage spine**: every asset any module builds
gets a registry row saying how (or whether) it joins to a run and to a bar, and every run gets a
manifest measuring how much of its own output it can account for.

---

## 1. Measured facts this design rests on (read-only, 2026-09-17)

### 1.1 One backtest run already carries four IDs

Measured on the run behind `results/run_20260916_225925_XAUUSD/`:

| ID value | Minted by | Clock | Where it is recorded |
|---|---|---|---|
| `20260916_225215` | `utils.logging_config.RUN_ID` (`logging_config.py:45`, `datetime.now()` at import) | naive **local** | `layer_trace.preexisting_run_ids`, `logs/run_{RUN_ID}/…` path |
| `run_20260916_225925_XAUUSD` | `ReportWriter.__init__` fallback (`backtest_v2.py:1762`, `datetime.now()`) + instrument suffix | naive **local** | results **folder name** only |
| `run_20260916_172925` | content mint passed to `ReportWriter.write(run_id=…)` (`backtest_v2.py:1771`) | UTC | `summary.run_id`, every `events.jsonl` row, `trades.csv` |
| `lt_20260916_172925_XAUUSD` | `layer_trace.mint_run_id` (`layer_trace.py:156`, UTC) | UTC | every `XAUUSD_layer_trace.jsonl` row |

Plus, outside a backtest:

| ID family | Minted by | Shape | Link to a backtest run today |
|---|---|---|---|
| Control-plane job | `control_plane/jobs.py:225` `uuid.uuid4().hex` | 32 hex | **glob match only** (`_discover_artifacts`), no recorded id |
| Dashboard run | `control_plane/dashboard_api.py:837` `d.name` | folder `YYYYMMDD_HHMMSS` | folder name |
| Chart API run | `charts/chart_api.py` | folder name `run_…_INSTR` | folder name (Grok's bind JSON already notes `api_run_id ≠ content_run_id`) |
| Paper live rail | `scripts/live/run_live_rail.py:110` | a directory path, **no id** | none |

### 1.2 Bar keys differ per output (confirmed by the lookup plan, reused here)

`layer_trace.bar_idx` = raw CSV row · `bar_structure.bar_index` = row · `features._pos` = row ·
`trades.candle_idx` = row + 1 · `events.candle_index` = engine counter (row − 62 on this corpus, not a
rule). **Only `bar_ts` is shared.** Every artifact writes it naive ISO, broker server clock (F-066).

### 1.3 What `layer_trace` actually contains

`results/layer_trace/XAUUSD_layer_trace.jsonl` today holds **four runs appended into one file**:

| run_id | rows |
|---|---|
| `lt_20260916_172925_XAUUSD` | 94,400 |
| `lt_20260916_181031_XAUUSD` | 15,847 |
| `lt_20260916_175055_XAUUSD` | 5,847 |
| `lt_20260916_180603_XAUUSD` | 847 |

All four: `tree_dirty=true`, `code_sha=1890785`, `corpus_sha256=4d73f5ce…` (the file on disk is now
`493747c8…`, content-equal but not byte-equal — see the 2026-09-17 SESSION LOG).

Rows by layer across the file: L0 4 · L1 4 (1 PASS, 3 NOT_REACHED) · **L2 0** · L3 58,463 ·
L4 58,463 · **L5 0 · L6 0** · L7 4 (`NOT_REACHED`) · L8 3 · **L9 0**.

- **L2 and L9 have no emit site** anywhere in `backtest_v2.py`.
- **L5/L6 emit only inside the EngineRunner veto branch** (`backtest_v2.py:~3316`), i.e. only when
  the engine gate is ON and a trade-open bar is rejected. On a gate-OFF run (`_fresh_stamp_backtest.py`
  defaults `BACKTEST_ENGINE_GATE=0`) they are silently absent, not `NOT_REACHED`.

### 1.4 Live rail audit rows cannot be joined at all

`results/live_rail_crt_sidecar_8k_20260916/audit.jsonl` rows are exactly
`{kind, decision, reason, ts}` — writer `runtime/live_rail_orchestrator.py:291`.
`ts` is **wall-clock processing time** (`2026-09-16T18:10:28.949507+00:00`), not the bar's open time;
there is **no `run_id`, no `instrument`, no `bar_ts`**. The side-car CRT events beside it do carry
`run_id=run_20260916_181031` — so within one paper run folder, the CRT half joins and the rail half
does not.

### 1.5 Two naming collisions the schema must survive

- **`trace_id` is a homonym.** `layer_trace` uses `{run_id}:{instrument}:{bar_ts}`;
  `interpreters/contract.py:93` uses `{NAME}-v{version}-{YYYYMMDD-HHMMSS}` for an interpreter reading;
  `research/opportunity_bands.py:134` carries a `source_trace_id` of its own.
- **`L0…L5` is a homonym.** The identity contract's L-layers are *objects*
  (`L0` OHLC … `L4` geometry, `L5` outcome — `identity/tokens.py`). `layer_trace`'s L-layers are *walk
  steps* (`L0` corpus admission … `L7` execution, `L8` ledger, `L9` measurement). `L4` means
  "parent-CRT/HTF step" in one and "trade geometry" in the other.

### 1.6 Scale of "all modules"

- `src/`: 629 `.py` files across 40 packages; **129 of them write files** (`write_text`, `open(...'w')`,
  `to_csv`, `to_parquet`, `json.dump`). Top writers: `research` 34 · `governance` 17 · `utils` 14 ·
  `runtime` 9 · `agent` 8 · `config_layer` 7.
- `scripts/`: 472 registered scripts in `data/script_registry.jsonl` (SITS).
- `data/framework_registry.jsonl`: 41 framework nodes.

---

## 2. Design rules (non-negotiable, each traced to a finding)

1. **Record, never derive, identity links.** Two IDs are linked only when some artifact wrote both
   strings (`preexisting_run_ids`, a manifest, a bind JSON). Never by clock arithmetic (F-101), never
   by folder proximity alone (proximity is recorded as `link=colocated`, a weaker grade).
2. **Never convert clocks inside the schema.** Every time field carries a `clock_basis`
   (`utc` · `broker_local` · `naive_local` · `wall_utc`). Converting is a reader step (F-066).
3. **Absence is a row.** Every expected-but-absent span, asset, or key is written with a status
   (`NOT_REACHED` · `NOT_EMITTED` · `UNJOINABLE`), never left missing (F-079).
4. **Namespace every overloaded word.** IDs carry `id_kind`; layers carry `layer_ns`. No renames of
   existing fields (a review never renames, §6.8) — the namespace lives beside them.
5. **Do not collapse the existing IDs.** They stay as recorded aliases; unifying the mint is a separate
   authorized `src/` change (already out of scope in the lookup plan).
6. **Coverage grants information only.** A run at 100% coverage is *traceable*, not correct or
   profitable (§6.5).

---

## 3. Identity model

### 3.1 Hierarchy

```
job_id        control-plane invocation            uuid4 hex            (0..1 per run)
  └─ run_id   one instrument pass on one rail     canonical: lt_YYYYMMDD_HHMMSS_{INSTR}, UTC
       ├─ aliases[]   every other id this run minted, recorded with source + clock_basis
       ├─ asset_id    one output file              sha256 of bytes at close
       └─ trace_id    one bar of this run          {run_id}:{instrument}:{bar_ts}   (bar_ts broker_local)
            └─ span_id  one walk layer on that bar {trace_id}:{layer}
```

- **Canonical `run_id` = the existing `layer_trace.mint_run_id` format.** It is already UTC, already
  instrument-scoped, already written on every span. Adopting it adds no fifth scheme.
- **Run-scoped rows** keep the existing sentinel `trace_id = {run_id}:RUN_SCOPED`, `bar_idx = -1`.

### 3.2 Closed vocabulary `id_kind`

| `id_kind` | Meaning | Example |
|---|---|---|
| `job` | control-plane job | `3f9c…` (32 hex) |
| `run_canonical` | `layer_trace` mint | `lt_20260916_172925_XAUUSD` |
| `run_content` | `ReportWriter.write(run_id=…)` content mint | `run_20260916_172925` |
| `run_folder` | results folder name | `run_20260916_225925_XAUUSD` |
| `run_logging` | `utils.logging_config.RUN_ID` | `20260916_225215` |
| `run_dashboard` | dashboard folder id | `20260916_225925` |
| `bar_trace` | `layer_trace` trace id | `lt_…:XAUUSD:2024-11-12T15:30:00` |
| `interpreter_reading` | `interpreters.contract` trace id | `PNF-v1-20241112-153000` |
| `source_trace` | research sidecar pointer | `opportunity_bands.source_trace_id` |

`bar_trace` and `interpreter_reading` never compare equal, even if a string happens to match.

### 3.3 Alias record

```json
{
  "id": "run_20260916_172925",
  "id_kind": "run_content",
  "clock_basis": "utc",
  "mint_site": "runtime.backtest_v2.ReportWriter.write",
  "link": "recorded",
  "evidence": "results/run_20260916_225925_XAUUSD/XAUUSD_summary.json#run_id"
}
```

`link ∈ {recorded, colocated}` — `recorded` when an artifact wrote both ids; `colocated` when only
folder membership connects them.

---

## 4. Layer namespaces and crosswalk

Every span/asset row carries `layer_ns ∈ {walk, identity}` next to `layer`.

| `walk` layer (layer_trace) | Walk module (as emitted) | Plane | Nearest `identity` object | Emitted today |
|---|---|---|---|---|
| L0 | `data_ingestion.ohlcv_schema+dataset_integrity+corpus_gate` | observation | L0 OHLC | yes (run-scoped) |
| L1 | `features.feature_pipeline` | observation | L1 Feature values | yes (run-scoped) |
| L2 | — | observation | L2 Feature states | **no emit site** |
| L3 | `config_layer.crt_engine_v2` | observation | L3_OCCUPANCY / L3_EVENT, `track_id=execution_tf` | yes, per bar |
| L4 | `runtime.parent_crt_feed+config_layer.htf_state` | observation | L3_OCCUPANCY, `track_id=parent_tf` (**not** identity L4) | yes, per bar |
| L5 | `core.engine_runner.EngineRunner` | evidence | — (no identity object) | gate-ON veto branch only |
| L6 | `core.fusion_engine+core.decision_engine` | evidence | — | gate-ON veto branch only |
| L7 | `config_layer.execution_planner+core.ultron_risk_gate` | execution | — | `NOT_REACHED` once (backtest) |
| L8 | `config_layer.crt_engine_v2.Trade` | observation | L4 Geometry (entry/sl) → L5 Outcome at close | trade birth only |
| L9 | — | measurement | MC-* / MPA provenance, outside L0–L5 | **no emit site** |

Crosswalk rows marked "nearest" are a navigation aid, not an equality claim; equality stays governed
by the identity contract's primary keys.

---

## 5. Schemas

Three schemas. **A is new, B is new, C is the existing span record, unchanged.**

### 5.A `run_manifest_v1` — one per run, written at run close

Purpose: the run's own coverage proof. Location: beside the run's outputs,
`{run_output_dir}/{instrument}_run_manifest.json`.

```json
{
  "schema_id": "run_manifest_v1",
  "run_id": "lt_20260916_172925_XAUUSD",
  "job_id": null,
  "rail": "backtest",
  "instrument": "XAUUSD",
  "timeframe": "M15",
  "aliases": [ { "...": "§3.3 alias records" } ],
  "identity": {
    "active_version": "v2_htfcrt_2026_08",
    "config_hash": "7de09f62…",
    "schema_hash": "d40e7c7d…",
    "dataset_id": "XAUUSD_MT5_PHASE1_20260521",
    "corpus_path": "data/mt5/XAUUSD_M15.csv",
    "corpus_sha256": "4d73f5ce…",
    "code_sha": "1890785…",
    "tree_dirty": true,
    "engine_gate": "OFF",
    "cost_model_id": "backtest_g1g2_v2",
    "constructor_id": "engine"
  },
  "window": {
    "bar_ts_first": "2024-05-22T20:30:00",
    "bar_ts_last": "2026-05-21T23:45:00",
    "clock_basis": "broker_local",
    "bars": 47197,
    "started_utc": "…",
    "closed_utc": "…"
  },
  "assets": [
    {
      "family": "events",
      "path": "results/run_20260916_225925_XAUUSD/XAUUSD_events.jsonl",
      "asset_id": "sha256:…",
      "rows": 7112,
      "run_key": { "field": "run_id", "value": "run_20260916_172925", "id_kind": "run_content" },
      "bar_key": { "field": "timestamp", "basis": "bar_open_ts", "clock_basis": "broker_local" },
      "bar_ts_min": "…", "bar_ts_max": "…",
      "join_status": "JOINABLE_RECORDED"
    }
  ],
  "spans": {
    "L0": { "status": "PASS", "rows": 1 },
    "L2": { "status": "NOT_EMITTED", "rows": 0, "reason": "no emit site (design gap G-RT-03)" },
    "L5": { "status": "NOT_REACHED", "rows": 0, "reason": "engine_gate=OFF" },
    "L7": { "status": "NOT_REACHED", "rows": 1, "reason": "backtest rail never imports planner/Ultron" }
  },
  "coverage": { "...": "§6 metrics" }
}
```

`engine_gate` is written here because the gate mode is otherwise only WARNed (F-058 residue); it is
the field that turns silent L5/L6 absence into a named `NOT_REACHED`.

### 5.B `asset_coverage_v1` — one row per (module, asset family), repo-wide registry

Purpose: the static map of every asset any module can build and how it joins. Follows the repo's
PRIMARY → GENERATED pattern (§2 of CLAUDE.md): a hand-maintained seed script
`scripts/governance/seed_asset_coverage.py` → generated `data/asset_coverage.jsonl`, guarded by
`tests/test_asset_coverage.py`. Never hand-edit the generated file.

| Field | Type | Vocabulary / rule |
|---|---|---|
| `id` | str | `RTC-NNN`, stable |
| `module` | str | dotted path, must import-resolve |
| `writer_symbol` | str | function/method that writes; must exist (AST-checked) |
| `package` | str | first segment of `module` |
| `rail` | enum | `backtest` · `paper_live` · `live` · `research` · `training` · `governance` · `control_plane` · `ui` · `agent` |
| `family` | str | reuse `jsonl_to_parquet.FAMILY_DEFAULTS` / `query_trace.FAMILY_GLOBS` names where they exist |
| `path_pattern` | str | glob, repo-relative |
| `format` | enum | `jsonl` · `csv` · `parquet` · `json` · `md` · `html` · `png` · `log` |
| `grain` | enum | `job` · `run` · `bar` · `bar_layer` · `event` · `trade` · `episode` · `aggregate` · `static` |
| `run_key` | obj\|null | `{field, id_kind, clock_basis}` |
| `bar_key` | obj\|null | `{field, basis, clock_basis}`; `basis ∈ bar_open_ts · csv_row · csv_row_plus_1 · engine_counter · wall_clock · none` |
| `trace_key` | obj\|null | `{field}` if written, or `{derive: "run_id+instrument+bar_ts"}` |
| `layer_ns` / `layers` | enum / list | §4 |
| `join_status` | enum | `JOINABLE_RECORDED` · `JOINABLE_DERIVED` · `RUN_ONLY` · `UNJOINABLE` · `NOT_EMITTED` |
| `gaps` | list | `NO_RUN_ID` · `NO_BAR_TS` · `WALL_CLOCK_NOT_BAR_TS` · `MULTI_RUN_FILE` · `LOCAL_CLOCK_ID` · `INDEX_OFFSET` · `HOMONYM` · `NO_EMIT_SITE` · `SILENT_CONDITIONAL` |
| `findings` | list | F-ids, must exist in `docs/current-findings.md` |
| `evidence` | list | `{path, line, symbol}`; path must be **git-tracked** (Findings Mandate rule) |
| `last_validated` | date | |

Seed rows from the measurements in §1 (first eight; the census fills the rest):

| id | module · writer | family | grain | run_key | bar_key | join_status | gaps |
|---|---|---|---|---|---|---|---|
| RTC-001 | `runtime.layer_trace.LayerTraceEmitter._write` | `layer_trace` | bar_layer | `run_id` / run_canonical / utc | `bar_ts` / bar_open_ts / broker_local | JOINABLE_RECORDED | `MULTI_RUN_FILE`, `NO_EMIT_SITE`(L2,L9), `SILENT_CONDITIONAL`(L5,L6) |
| RTC-002 | `runtime.backtest_v2.ReportWriter._write_events` | `events` | event | `run_id` / run_content / utc | `timestamp` / bar_open_ts / broker_local | JOINABLE_DERIVED | `INDEX_OFFSET` (`candle_index`) |
| RTC-003 | `runtime.backtest_v2.ReportWriter._write_trades` | `trades` | trade | `run_id` / run_content / utc | `opened_at`,`closed_at` / bar_open_ts / broker_local | JOINABLE_DERIVED | `INDEX_OFFSET` (`candle_idx`=row+1) |
| RTC-004 | `runtime.backtest_v2.ReportWriter._write_summary` | `summary` | run | `run_id` / run_content / utc | — | RUN_ONLY | — |
| RTC-005 | `runtime.backtest_v2.ReportWriter.__init__` | results folder | run | folder name / run_folder / naive_local | — | RUN_ONLY | `LOCAL_CLOCK_ID` |
| RTC-006 | `runtime.live_rail_orchestrator` (audit writer, `:291`) | `rail_audit` | event | **none** | `ts` / wall_clock / wall_utc | UNJOINABLE | `NO_RUN_ID`, `NO_BAR_TS`, `WALL_CLOCK_NOT_BAR_TS` |
| RTC-007 | `control_plane.jobs.JobManager.create_run` | job state JSON | job | `run_id` / job / — | — | RUN_ONLY | link to backtest run by glob only |
| RTC-008 | `interpreters.contract` reading | interpreter reading | bar | — | `observation_time` | JOINABLE_DERIVED | `HOMONYM` (`trace_id`) |

---

### 5.C `layer_trace` span record — existing `TRACE_SCHEMA_VERSION = "1.0.0"`, unchanged

Already carries the full identity block on every row plus `trace_id`, `span_id`, `bar_idx`, `bar_ts`,
`plane`, `layer`, `module`, `status`, `input_hash`, `output_hash`, `artifact_path`, `note`. This design
**does not change it**. Two additive fields are proposed for a governed `1.1.0` (§8, P3), not now:
`layer_ns` (constant `"walk"`) and `clock_basis` (constant `"broker_local"` for `bar_ts`).

---

## 6. Coverage metrics (what "coverage" means, precisely)

All computed per run from 5.A, never inferred from folder contents.

| Metric | Numerator | Denominator | Notes |
|---|---|---|---|
| `asset_run_coverage` | assets whose rows carry a recorded `run_id` | assets produced by the run | RUN_ONLY assets count as covered for this metric |
| `asset_bar_coverage` | bar-grain assets with a `bar_open_ts` key | bar-grain assets produced | `wall_clock` keys do **not** count |
| `span_bar_coverage[L]` | distinct `trace_id` with a span at layer `L` | bars in `window` | reported per layer; `NOT_REACHED`/`NOT_EMITTED` layers print their status, not 0% |
| `module_path_coverage` | walk modules with ≥1 span | modules reachable on this rail | denominator from the AST reachability census `scripts/analysis/layer_trace/h4_rail_reachability.py` (F-103), not hand-listed |
| `alias_link_grade` | aliases with `link=recorded` | all aliases | a run with only `colocated` links is traceable but weakly |

Repo-wide (from 5.B): `writer_modules_registered / writer_modules_found` — denominator = the AST
census of file-writing modules (129 in `src/` today), so an unregistered new writer lowers the number
instead of disappearing.

---

## 7. Gap ledger (measured, ordered by what blocks the spine)

| ID | Gap | Evidence | Fix (design) | Behaviour risk |
|---|---|---|---|---|
| G-RT-01 | Live rail audit has no `run_id` / `instrument` / `bar_ts`; `ts` is wall clock | §1.4, `live_rail_orchestrator.py:291` | add `run_id`, `instrument`, `bar_ts` (broker_local), keep `ts` renamed in meaning to `processed_at_utc` **by documentation only** — no field rename | append-only fields on an audit row; no decision reads it |
| G-RT-02 | Four runs appended into one `layer_trace` file | §1.3, path = `{output_dir}/{instrument}{suffix}` | config-gated path template `{output_dir}/{run_id}/{instrument}{suffix}`; default = current path (byte-identical) | path only; query tool already refuses mixed `run_id` |
| G-RT-03 | L2 and L9 have no emit site | §1.3 | emit run-scoped `NOT_EMITTED` rows for L2/L9 at run start; real L2 spans only after the FeatureStates producer is identified (memory: FeatureStates are ephemeral) | observation-only rows |
| G-RT-04 | L5/L6 silently absent when engine gate OFF | §1.3, `backtest_v2.py:~3316` | at run start, if gate OFF → `emit_not_reached_once(L5)` and `(L6)` with `reason=engine_gate=OFF`; record `engine_gate` in 5.A | observation-only rows |
| G-RT-05 | Run IDs not cross-recorded (folder ↔ content ↔ canonical ↔ logging) | §1.1 | 5.A `aliases[]` written by the same code that already fills `preexisting_run_ids`; add `run_content` and `run_folder` to it | observation-only file |
| G-RT-06 | Control-plane job ↔ backtest run linked by glob only | `jobs.py:363` `_discover_artifacts` | pass `job_id` to the child via env `TRADELATEST_JOB_ID`; child writes it into 5.A | env read only, no decision use |
| G-RT-07 | `trace_id` and `L0…L5` homonyms | §1.5 | `id_kind` + `layer_ns` in 5.A/5.B; no renames | none |
| G-RT-08 | Traces point at `corpus_sha256=4d73f5ce`; file on disk is now `493747c8` | §1.3 | 5.A records both `corpus_sha256_at_run` and, on read, a `corpus_now` check → `CORPUS_DRIFTED` status in the query tool | read-side only |
| G-RT-09 | Every measured run is `tree_dirty=true` | §1.3 | manifest surfaces it as a coverage caveat; no gate (recording, not blocking) | none |
| G-RT-10 | Grok's `live_chart_bind_v1` / `live_alert_v1` name `run_id` without `id_kind` | `docs/schemas/*.json` | v2 of both schemas: `run_id` → object `{id, id_kind}` and `join_keys` gains `trace_id`; v1 stays readable | schema docs only |

---

## 8. Implementation phases

Each phase is one change-set with its own impact manifest
(`docs/governance/build_manifests/CH-*.impact.json`, classified against `change_contracts.json`),
a SESSION LOG entry, and the green-floor delta reported against a baseline captured first.

### P0 — Census + registry seed (read-only; no `src/` change)
- New `scripts/analysis/asset_writer_census.py`: AST scan of `src/` + `scripts/` for file-writing
  calls → `{module, writer_symbol, call, path_literal_or_expr}`. Deterministic, sorted output.
- New `scripts/governance/seed_asset_coverage.py`: hand-curated rows (starting with RTC-001…008) →
  `data/asset_coverage.jsonl`.
- New `tests/test_asset_coverage.py`: every row's module imports, `writer_symbol` exists, enums are
  closed, `findings` exist, `evidence` paths are git-tracked; **ratchet**: registered writers ≥ last
  pinned count, and every census writer is either registered or on an explicit, shrink-only
  `UNREGISTERED_WRITERS` pin.
- SITS registration of both new scripts in the same turn (the floor fails otherwise).
- Exit: registry covers the backtest + paper rail writers fully; the rest pinned.

### P1 — Run manifest writer (`src/runtime/`, observation-only)
- New `src/runtime/run_manifest.py` (copy `docs/reference/example-service.py` structure):
  `RunManifestWriter.from_prod_config`, strict `_require` config section `run_manifest`
  (`enabled`, `schema_version`, `filename_suffix`) — top-level section ⇒ hash-neutral.
- Wire in `backtest_v2.py` at the point that already builds `LayerTraceEmitter` (`:2349`) and closes
  it; fill `aliases` from the same values that populate `preexisting_run_ids`, plus `run_content`
  and `run_folder`; `assets[]` from `ReportWriter.write`'s returned `paths` dict (sha256 + rows).
- G-RT-04 and G-RT-03 `NOT_REACHED` / `NOT_EMITTED` rows land here.
- **Parity gate (owed, blocking):** XAUUSD backtest manifest-ON vs OFF → `trades.csv` and
  `events.jsonl` byte-identical after removing `run_id`; rejection set identical. Same harness shape as
  `scripts/analysis/v3_config_parity.py`.
- Tests: `tests/test_run_manifest.py` — alias link grades, `NOT_REACHED` when gate OFF, asset sha and
  row counts, missing config key fails fast, disabled = no file.

### P2 — Live rail keys (G-RT-01, G-RT-06)
- `live_rail_orchestrator.py` audit rows gain `run_id`, `instrument`, `bar_ts`; paper runs mint a
  canonical `run_id` with `mint_run_id` and write a 5.A manifest with `rail=paper_live`.
- `jobs.py` passes `TRADELATEST_JOB_ID`; manifest records it.
- Tests: audit row keys present; `bar_ts` equals the closed bar that triggered the decision, not
  processing time; job id round-trips.
- Behaviour check: paper run order/NO_ORDER sequence identical before/after (keys excluded).

### P3 — `layer_trace` 1.1.0 (G-RT-02, §5.C additive fields)
- Config-gated per-run path template; default preserves today's path byte-for-byte.
- Add `layer_ns`, `clock_basis`; bump `TRACE_SCHEMA_VERSION` → governed edit (the module refuses
  mismatched config versions already).

### P4 — Consumers read the registry, not hand lists
- `query_trace.py` (the lookup plan) resolves runs through 5.A manifests first, falling back to its
  A2 scan; `FAMILY_GLOBS` checked against `data/asset_coverage.jsonl` by a test (drift = red).
- `--run-id` card prints §6 coverage metrics; `--trace-id` prints per-section `join_status` from 5.B.

### P5 — Link into Grok's surfaces
- `live_chart_bind_v2` / `live_alert_v2` (G-RT-10) with `{id, id_kind}` and `trace_id` in `join_keys`.
- `ui_kits/live_monitor/state.json` shows `run_id` (canonical), `alias_link_grade`,
  `span_bar_coverage[L3]`, and `UNJOINABLE` badges for rail audit until P2 lands.

---

## 9. Link map to Grok's architecture (what this design fills in)

| Grok section | Grok says | This design adds |
|---|---|---|
| §3 L1 "run_id mint rules (F-101)" | names the need | §3 hierarchy, `id_kind` vocabulary, alias record |
| §4.1 Keys | `run_id`, `(instrument, bar_ts)`, `cost_model_id`, `constructor_id` | per-module key fields + clock basis (5.B), recorded in 5.A `identity` |
| §4.3 acceptance 1 "bound run_id in both shells" | requirement | 5.A is the object both shells bind to |
| §4.3 acceptance 3 "or explicitly UNBOUND" | requirement | `join_status=UNJOINABLE` + gap codes, from data not UI |
| §7 G-LC-01 rail ↛ process_candle | gap | G-RT-01: even the rail's own audit can't join; fix keys first |
| §8 run-before-walk | rule | every phase ends in a measured coverage number or a parity result |
| §10 enrichment `run_id (content mint, F-101-aware)` | wish | resolved: canonical = `lt_…`, content mint kept as alias |

And to the lookup plan (`using-trace-id-…`): A2 `resolve_run` becomes "read the manifest if present";
A3/A3b print §6 metrics; A4 prints 5.B `join_status` per section.

---

## 10. Verification

1. Preflight: `git status --porcelain` (concurrent sessions); interpreter = `D:\Tradelatest\venv`;
   echo corpus path + row count + sha256 before any run.
2. Baseline: `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` —
   record failed/passed before the phase (2026-09-17 on `grokbotchanges`: 13 failed / 11 errors /
   555 passed, 11 errors from the corpus-hash drift).
3. P0: `pytest tests/test_asset_coverage.py`; census count printed and pinned.
4. P1: manifest ON/OFF parity on XAUUSD (byte-identical ledger/events minus `run_id`); open the
   manifest for `run_20260916_225925_XAUUSD`-equivalent run and confirm:
   aliases include `20260916_…` (logging), `run_…_XAUUSD` (folder), `run_…` (content), `lt_…` (canonical);
   `spans.L5.status == NOT_REACHED` with `reason=engine_gate=OFF`; `spans.L2.status == NOT_EMITTED`.
5. P2: paper rail smoke → every audit row has `run_id` and `bar_ts`; `bar_ts` values ⊆ corpus
   timestamps.
6. Floor delta after each phase: no new failures vs step 2.

## 11. Out of scope

- Collapsing the mint into one `run_id` at source (behaviour change to `ReportWriter`/logging; separate
  authorization).
- Any change to decisions, config `params`, `ACTIVE_VERSION`, promotion, or G001.
- Fixing the corpus-hash drift itself (data admission decision, tracked separately).
- The `capture_tv.py` automation-evasion edit (excluded by user decision 2026-09-17).
