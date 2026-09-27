# Look up a whole run by `run_id`, and everything about one bar by `trace_id`

## Context

The user wants two ways into backtest results:

- **`--run-id X`**: everything that happened in one run, grouped by layer (L0–L9), plus events,
  telemetry and trades.
- **`--trace-id X`**: every recorded observation for one bar of one run, across all outputs, so
  they can dig into any single result.
- **`--run-id X --from TS --to TS`** (added 2026-09-17): the same run card, cut to a time
  range, so one session or one move on a chart can be read without the whole run (A3b).

Measured facts this plan rests on (2026-09-16, read-only):

- **One run's outputs are scattered.** `results/run_20260916_101942_XAUUSD/` (folder named in
  local time) holds trades/events/telemetry/summary whose `run_id` is `run_20260916_044942` (UTC).
  The config dump lives in `logs/config_dumps/`. `layer_trace` writes to its own
  `output_dir` (`results/layer_trace_h2/`) under a fourth ID, `lt_20260915_165314_XAUUSD`. It
  records `runtime.ReportWriter.run_id=run_20260915_222314`, and that folder exists — so aliases
  can be linked by exact recorded strings, never by time arithmetic.
- **Each output numbers bars differently.** Checked on three trades and 19 rejections against the
  raw XAUUSD CSV:

  | Output | Bar field | Relation to raw CSV row (0-based) |
  |---|---|---|
  | `layer_trace` | `bar_idx` | equal (source: `candle_idx - 1`) |
  | `bar_structure`, `crt_construction` | `bar_index` | equal by source (`bar_index=candle_idx - 1`); confirm in tests |
  | `bar_matrix` / `features.parquet` | `_pos` | equal |
  | `trades.csv` | `candle_idx` | row + 1 |
  | `events.jsonl` | `candle_index` | engine counter, row − 62 on this corpus (not a rule) |

  **The timestamp is the only key every output shares.** That is why
  `trace_id = {run_id}:{instrument}:{bar_ts}` (the format `layer_trace` already writes) is the
  right bar key.
- `query_trace.py` already has: family globs, fail-closed projection selection, `--run-dir`
  scoping, and `assert_view_lineage` (refuses mixed `run_id`/`corpus_sha256`). Reuse all of it.

User decisions: read-only query tool first (no backtest code change); keep
`run_id:instrument:bar_ts`; also plan switching `layer_trace` on in a shadow config.

Task class: Phase A `OBSERVATION_ONLY` tooling; Phase B `OBSERVATION_ONLY` + a new shadow config
(active config and `ACTIVE_VERSION` untouched).

## Phase A — `query_trace.py` lookups (read-only)

### A1. New families
- `scripts/maintenance/jsonl_to_parquet.py` `FAMILY_DEFAULTS`: add
  `"_layer_trace.jsonl": ("layer", None)` so a run's spans can be converted to Parquet,
  partitioned by layer.
- `scripts/analysis/query_trace.py` `FAMILY_GLOBS`: add `layer_trace`
  (`results/**/*_layer_trace.parquet`, `logs/**/…`) and `trades`
  (`results/**/*_trades.csv`, canonical CSV, not a projection → add to
  `_NON_PROJECTION_FAMILIES`, admissible if the file has a `run_id` column).
- `src/utils/duckdb_query.py` `open_views`: if the path ends in `.csv`, use
  `read_csv_auto(...)` instead of `read_parquet(...)`. Small additive branch; cover in
  `tests/test_duckdb_query.py`.

### A2. Run resolver: `resolve_run(run_id) -> RunBundle`
In `query_trace.py`, next to `discover_projections`:
- Scan the family globs plus `logs/config_dumps/*_config.json` and `results/**/_summary.json`.
  Read only the `run_id` that each artifact records: first JSONL line, distinct `run_id` on the
  Parquet/CSV view, the summary key, the config-dump key.
- **Aliases, by recorded evidence only:**
  (a) `layer_trace.preexisting_run_ids` values;
  (b) files in the same `run_*` folder whose recorded `run_id` differs from the folder name
  (e.g. folder `run_20260916_101942` ↔ content `run_20260916_044942`), marked
  `link=colocated`.
  Never convert clock bases (F-101).
- `RunBundle = {query_id, linked_ids[{id, source, link}], identity{…from layer_trace or config
  dump: active_version, config_hash, schema_hash, corpus_sha256, code_sha, tree_dirty},
  artifacts{family: path}}`.
- Zero matches → exit 1 `RUN NOT FOUND`. Two unlinked bundles for one ID → refuse
  (existing `AmbiguousRunError`).
- Then reuse `select_projections` + `open_views` + `assert_view_lineage`, scoped to the bundle's
  paths. Extend `assert_view_lineage` so the alias set counts as one run.

### A3. `--run-id X`: run card
Sections, each printed with its source path and row count:
1. **Identity**: the linked IDs and identity block.
2. **Layers**: `layer_trace` grouped by `layer, plane, module, status` with counts, plus
   `--layer L3` / `--status REJECT` filters that list the matching spans. Without a
   `layer_trace` artifact: `layers: NOT RECORDED (layer_trace disabled for this run)` — a
   distinct state, never an empty table (F-079 silent-gap class).
3. **Events** by `event`; **telemetry** by `kind`.
4. **Trades and rejections**, each with its ready-to-paste `trace_id`, built from `opened_at` /
   the event `timestamp`.

### A3b. `--from TS --to TS`: time range on the run card (added 2026-09-17)
Measured basis (read-only, 2026-09-17, `results/run_20260916_225925_XAUUSD` +
`results/layer_trace/XAUUSD_layer_trace.jsonl`): every artifact writes **naive ISO timestamps with
no zone** (`2024-11-12T15:30:00`) — `trades.opened_at/closed_at`, `events.timestamp`, the
`layer_trace` `trace_id` suffix. Those stamps are **broker server time**, not UTC (F-066).

**Flag contract**
- Both flags take the same naive ISO form the artifacts use. Accept `YYYY-MM-DD` as a
  shorthand for `T00:00:00` (`--from`) / `T23:45:00` (`--to`) on M15.
- **Clock basis is broker server time, and the card says so.** No zone conversion, no
  `--tz` flag (F-066/F-101: never do time arithmetic across clock bases). A value with a zone
  suffix (`Z`, `+03:00`) → `REFUSED (range must be broker-local naive; see F-066)`.
- **Inclusive on both ends, by bar open time.** A bar is in range when `from ≤ bar_open_ts ≤ to`.
- `--from` alone = from that bar to the end of the run; `--to` alone = from the start to that bar.
- `from > to` → exit 1 `REFUSED (empty range: from > to)`.
- **Mutually exclusive with `--trace-id`.** `--window N` already defines the bar-dossier
  neighbourhood in bars; two range definitions on one command would disagree at gaps.

**Resolving the range to rows (once, then reused by every section)**
- Read the run's corpus (A2 identity; refuse on `corpus_sha256` mismatch, same as A4). Map the
  range to `[row_from, row_to]` = first and last corpus rows whose timestamp is inside it.
- The card header prints: requested `from`/`to`, first and last bar actually in range, the row
  range, the bar count, and `clock=broker_local`.
- Range entirely outside the corpus span → `REFUSED (range outside corpus [first_ts, last_ts])`.
- Range inside the corpus span but with **no bars** (weekend, holiday, the 00:00–00:45 daily-open
  gap on the MT5 XAUUSD corpus, F-080) → `0 bars in range` in the header and every section prints
  `0 rows (range=…, no bars)` — a distinct state, never read as "nothing happened".

**Filter per section (same keys as A4, widened to a range)**

| Section | Range filter |
|---|---|
| Layers (`layer_trace`) | `bar_idx BETWEEN row_from AND row_to` (cross-check: `trace_id` suffix inside range) |
| Bar structure / CRT construction | `bar_index BETWEEN row_from AND row_to` |
| Events | `timestamp BETWEEN from AND to` |
| Telemetry with `timestamp` | `timestamp BETWEEN from AND to` |
| Telemetry with only `candle_index` | translate the range ends through the run's events (`candle_index ↔ timestamp`); if either end has no event anchor → `UNRESOLVED (no engine index anchor at range end)`; run-level aggregates (e.g. `TRANSITION_COUNTER`) → `NOT RANGEABLE (run aggregate)`, never silently shown as if in range |
| Episodes alive (`CANDIDATE_LIFECYCLE`) | overlap: `first_seen_idx ≤ i_to AND last_seen_idx ≥ i_from` in engine numbering; basis checked in A6, else `UNVERIFIED` |
| Trades | three counts printed separately: **opened in range**, **closed in range**, **open at any point in range** (`opened_at ≤ to AND closed_at ≥ from`); the listing uses "open at any point", each row flagged `opened_before` / `closes_after` when it crosses a boundary |
| Features (`bar_matrix_features`) | `timestamp BETWEEN from AND to`, same `corpus_sha256` + `schema_hash` gate as A4 |
| Research labels (`clean_labels`) | `timestamp BETWEEN from AND to`, labelled research cost world |

- Layer / event / telemetry counts in the card are **the range's counts**; the header also
  prints the whole-run totals beside them, so a range count is never mistaken for the run's.
- `--layer` / `--status` / `--section` / `--json` combine with the range unchanged.
- **Trades and rejections keep their ready-to-paste `trace_id`**, so a range read hands off
  directly to A4 for any single bar.

**Why a range and not a clock conversion.** The use case is "read this part of the run next to a
chart". Charts (TradingView) display UTC or a chosen zone; artifacts are broker-local. The tool
stays in the artifact's clock and prints the basis; converting a chart time to broker time is the
reader's step (measured offset, e.g. F-080's `+3h` in summer on OANDA↔MT5), not the tool's.

### A4. `--trace-id RUN:INSTR:TS`: bar dossier
- Parse with `split(":", 2)`, because the timestamp itself contains `:`. Resolve the run
  (A2). Convert the timestamp to a raw CSV row from the run's corpus, and refuse if the
  corpus `sha256` differs from `identity.corpus_sha256`.
- Pull each output with the key that works for it:

  | Section | Key used |
  |---|---|
  | Layers (`layer_trace`) | `trace_id` equality (also checks `bar_idx == row`) |
  | Bar structure / CRT construction | `bar_index == row` |
  | Events | `timestamp == ts` |
  | Telemetry with `timestamp` | `timestamp == ts` |
  | Telemetry with only `candle_index` | translate via the same run's events (`candle_index ↔ timestamp`); if no event exists at that bar → `UNRESOLVED (no engine index anchor)` |
  | Episodes alive (`CANDIDATE_LIFECYCLE`) | `first_seen_idx ≤ i ≤ last_seen_idx` in engine numbering; basis checked in A6 before shown, else `UNVERIFIED` |
  | Trades | `opened_at == ts` or `closed_at == ts` |
  | Features (`bar_matrix_features`) | `timestamp`, only if `corpus_sha256` **and** `schema_hash` match the run, otherwise `REFUSED` with both hashes |
  | Research labels (`clean_labels`) | `timestamp`, labelled research cost world (not comparable to `pnl_rr_net`) |

- Every section prints exactly one of: `N rows` · `0 rows (key=…)` · `NOT RECORDED` ·
  `REFUSED (reason)` · `UNRESOLVED` · `UNVERIFIED`.
- Options: `--window N` (±N bars, same keys), `--json` (dossier as JSON for LLM use),
  `--section layers,events,…`.
- **Forbidden joins stay refused:** never shows `events.state_to` next to
  `crt_state_resolved` as the same thing (F-069, `CC-L3-FORBIDDEN-JOIN`). They are printed as two
  labelled rows.

### A5. Docs and registration (same turn)
- Module docstring USAGE block. `docs/research/parquet_evidence_layer.md` and
  `docs/reference/schemas.md` get a short "run_id / trace_id lookup" section with the bar-number
  table above.
- `query_trace.py` is already registered in SITS; re-run
  `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`
  only if the census flags a change.
- Governance: change class expected `TRACE_OBSERVATION_JOIN` (confirm against
  `docs/governance/change_contracts.json`) → impact manifest
  `docs/governance/build_manifests/CH-run-trace-lookup.impact.json` → `validate-impact` before
  editing → `validate-completion` after. SESSION LOG in `assistant_project.md`.

### A6. Tests: `tests/test_query_trace.py` (extend)
Build small fixtures in `tmp_path`: a run folder with `trades.csv`/`events`/`telemetry`, a
`layer_trace` file listing preexisting IDs, and a 20-row corpus.
- `resolve_run` links folder ↔ content ↔ `layer_trace` IDs from recorded strings only; an
  unrelated run with a timestamp 5h30m away is **not** linked.
- The `trace_id` parse survives `:` inside the timestamp.
- Each bar-number mapping in the table (trades +1, `layer_trace` equal, events via timestamp).
- Section states: missing `layer_trace` → `NOT RECORDED`; feature schema mismatch → `REFUSED`;
  telemetry with no event anchor → `UNRESOLVED`.
- A corpus `sha256` mismatch refuses the dossier.
- `bar_structure.bar_index == layer_trace.bar_idx` on the same bar.
- **Time range (A3b):** both ends inclusive; `--from` only and `--to` only; date shorthand;
  `from > to` refuses; a zoned value (`Z`, `+03:00`) refuses; range outside the corpus refuses;
  a range with no bars (fixture gap) prints `0 bars in range` and `0 rows (range=…, no bars)` in
  every section; a trade opened before `--from` and closed inside is listed and flagged
  `opened_before`, and counted in "closed in range" but not "opened in range";
  `TRANSITION_COUNTER` prints `NOT RANGEABLE`; `--from` with `--trace-id` exits with a usage
  error; range counts and whole-run totals both appear and differ on the fixture.

## Phase B — switch `layer_trace` on in a shadow config (separate change, after A)

- New shadow config cloned from the active `v2_htfcrt_2026_08` with only a `layer_trace` section
  added (`enabled: true`, `output_dir` = results root, so the file lands next to that run's
  outputs). Top-level section → hash-neutral. `ACTIVE_VERSION` untouched, not promoted. Written
  by hand following the F-055 shadow pattern; **never** through `PromotionManager.promote_*`
  (memory: v1-base landmine).
- **The owed tracing on/off check:** XAUUSD backtest with the active config vs the shadow config
  → `trades.csv` and `events.jsonl` byte-identical after removing `run_id`; rejection set
  identical. Any difference = tracing is not observation-only → stop and report.
- Then `jsonl_to_parquet.py` on the new `layer_trace` file, and `query_trace.py --run-id` /
  `--trace-id CRT-0001's trace` end to end.
- Change class and impact manifest of its own (`CH-layer-trace-shadow-enable`).

## Out of scope (recorded, not done)
- Making the backtest mint one `run_id` and write `trace_id` onto events, telemetry and trades
  (fixes F-101 at the source; a later `src/` change).
- Cost stamp and intent-schema work: separate approved or pending changes. The dossier simply
  shows their columns once they exist.
- Any config promotion, `ACTIVE_VERSION` change, or G001 claim.

## Verification
1. Preflight: `git status --porcelain`; `venv/Scripts/python.exe -c "import sys;print(sys.prefix)"`.
2. `venv/Scripts/python.exe -m pytest -q tests/test_query_trace.py tests/test_duckdb_query.py tests/test_layer_trace.py tests/test_parquet_store.py`.
3. Real data, read-only:
   - `venv/Scripts/python.exe scripts/maintenance/jsonl_to_parquet.py` on
     `results/layer_trace_h2/XAUUSD_layer_trace.jsonl`, and on the events/telemetry of
     `results/run_20260915_222314_XAUUSD`;
   - `query_trace.py --run-id run_20260915_222314` → must link `lt_20260915_165314_XAUUSD`, show
     L0–L8 counts matching the measured 47,197 L4 / 47,178 L3 PASS / 19 L3 REJECT / 3 L5/L6/L8,
     and L7 `NOT_REACHED`;
   - `query_trace.py --trace-id lt_20260915_165314_XAUUSD:XAUUSD:2024-11-12T15:30:00` → L3/L4/L5/L6/L8
     spans, the TRADE_OPENED event, trade `CRT-0001` (`candle_idx` 11427), features row
     `_pos` 11426 or `REFUSED` with both schema hashes.
   - `query_trace.py --run-id run_20260916_044942` → layers `NOT RECORDED`, trades with trace_ids.
   - `query_trace.py --run-id run_20260915_222314 --from 2024-11-12T14:00:00 --to 2024-11-12T17:00:00`
     → header `clock=broker_local`, 13 bars in range; trades: `CRT-0001` opened and closed in
     range (15:30 → 15:45); range layer counts ≤ whole-run totals, both printed.
   - `query_trace.py --run-id run_20260915_222314 --from 2024-11-16 --to 2024-11-17` (a weekend)
     → `0 bars in range`, every section `0 rows (range=…, no bars)`.
4. `python scripts/maintenance/check_governance_invariants.py --all` — no new failures beyond the
   pre-existing baseline captured in step 1.
5. `construction_protocol.py validate-completion` on the manifest, then `check`.
