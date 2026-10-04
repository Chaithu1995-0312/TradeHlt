# DC-ADMIN-HISTRUN-COVERAGE-01 - Historical Run: date range from corpus OHLCV coverage

- Status: DESIGN ONLY (no code/config/dashboard changes made)
- Revision: r2 2026-09-25 01:56 IST - user decisions folded in (section 1A); sections 3, 4, 6, 7, 9, 10, 11 updated to match.
- Date: 2026-09-25 (IST)
- Scope: `ui_kits/crt_dashboard/page10_admin.jsx` (Historical Run page, design-only shell already added) + one new read-only backend endpoint on the 127.0.0.1:8787 control-plane server.
- Investigation: read-only on D:\Tradelatest. All numbers below were measured on 2026-09-25 with `.venv\Scripts\python.exe` (pandas, time column only; parquet via row-group statistics).

---

## 1. Goal

The From/To date pickers on the Historical Run page must be bounded by the OHLCV data we actually hold for each selected instrument (the "corpus"), not by today's date or a hard-coded range. The coverage must come from the same authority chain the backtest loader uses, fail closed when coverage cannot be established, and never silently fall back to placeholder dates or a placeholder instrument list.

---

## 1A. USER DECISIONS (2026-09-25 01:56 IST)

| # | Decision | Where it lands |
|---|---|---|
| D1 | A coin whose file for the selected timeframe has no reviewed clock-registry timezone is **GREYED OUT** (disabled, not selectable) with the reason "no reviewed timezone". This mirrors `CandleLoader` -> `clock_registry.require_reviewed_clock()` refusal (no record / sha mismatch / `user_reviewed=false`). | 4, 6.1, 7 |
| D2 | **Timeframe selector with BOTH M15 and M5.** Coverage, runnable status and TZ status are computed per (instrument, timeframe). Switching timeframe recomputes every row's state and the calendar bounds (and drops selections that become disabled). | 4, 6.1, 6.4 |
| D3 | **Default date range = full INTERSECTION** of the selected coins' coverage (no 90-day default). Union stays opt-in with a warning. | 6.2, 6.3, 6.5 |
| D4 | The 5 instruments with no data (ADAUSDT, EURGBP, NZDUSD, USDCAD, USDCHF) are greyed out too, in a **visually distinct** state. Two disabled states: `no_data` and `tz_unreviewed`. **Precedence: `no_data` wins** if both apply. Page shows a small legend. | 4, 6.1, 6.7 |
| D5 | **Excel EXCLUDED** as a coverage/data source - **CONFIRMED** 2026-09-28 01:12 IST (originally interpreted from "Excel for now yes"). | 3, 9 |

> **Note (2026-09-28 01:12 IST, design only, not implemented):** M15 for non-XAUUSD instruments will come from **M5-derived datasets** per DC-RESEARCH-LAB-01 UD-10 (`multi_llm/design_cards/DC-RESEARCH-LAB-01_ARCHITECTURE.md`): a derived M15 is its own dataset, identified by source M5 hash + resampling code hash + declared params (bar-boundary anchor, timezone, partial-bar rule), and never mixed with raw/vendor M15. A coverage endpoint would report derived M15 as **distinct from raw** M15 (separate source kind), not merged into it.

### 1A.1 Per-coin runnable table (read-only check, 2026-09-25 ~02:00 IST)

Method: for each of the 17 names returned by `/api/instruments`, resolved the family file (`data/mt5/{SYM}_{TF}.csv` for FX/XAU, `data/binance/{SYM}_{TF}.csv` for USDT), read the `timestamp` column (pandas), looked up `configs/data_provenance/ohlcv_clock_registry.json` and re-hashed each reviewed file to confirm the record's `sha256` still matches (all matched) and `user_reviewed=true`.

| Instrument | M15 state | M15 coverage (rows) | M15 clock | M5 state | M5 coverage (rows) | M5 clock |
|---|---|---|---|---|---|---|
| ADAUSDT | `no_data` | - | - | `no_data` | - | - |
| AUDUSD | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (49,722) | empty | **runnable** | 2025-10-06 00:00 -> 2026-07-02 05:25 (55,037) | MT5_SERVER_NY_DST |
| BNBUSDT | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (70,080) | empty | **runnable** | 2024-05-22 00:00 -> 2026-05-21 23:55 (210,240) | UTC |
| BTCUSDT | `tz_unreviewed` | same as BNBUSDT (70,080) | empty | **runnable** | same as BNBUSDT (210,240) | UTC |
| DOGEUSDT | `tz_unreviewed` | same (70,080) | empty | **runnable** | same (210,240) | UTC |
| ETHUSDT | `tz_unreviewed` | same (70,080) | empty | **runnable** | same (210,240) | UTC |
| EURCAD | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (49,715) | empty | **runnable** | 2025-10-06 00:00 -> 2026-07-02 05:25 (54,993) | MT5_SERVER_NY_DST |
| EURGBP | `no_data` | - | - | `no_data` | - | - |
| EURUSD | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (49,721) | empty | **runnable** | 2025-10-06 00:00 -> 2026-07-02 05:20 (55,017) | MT5_SERVER_NY_DST |
| GBPUSD | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (49,716) | empty | **runnable** | 2025-10-06 00:00 -> 2026-07-02 05:25 (54,999) | MT5_SERVER_NY_DST |
| NZDUSD | `no_data` | - | - | `no_data` | - | - |
| SOLUSDT | `tz_unreviewed` | same as BNBUSDT (70,080) | empty | **runnable** | same (210,240) | UTC |
| USDCAD | `no_data` | - | - | `no_data` | - | - |
| USDCHF | `no_data` | - | - | `no_data` | - | - |
| USDJPY | `tz_unreviewed` | 2024-05-22 00:00 -> 2026-05-21 23:45 (49,716) | empty | **runnable** | 2025-10-06 00:00 -> 2026-07-02 05:25 (55,000) | MT5_SERVER_NY_DST |
| XAUUSD | **runnable** | 2024-05-22 01:00 -> 2026-05-21 23:45 (47,275) | MT5_SERVER_NY_DST | **see note X** | 2025-10-06 01:00 -> 2026-07-02 05:25 (52,198) | MT5_SERVER_NY_DST |
| XRPUSDT | `tz_unreviewed` | same as BNBUSDT (70,080) | empty | **runnable** | same (210,240) | UTC |

Totals: **M15** = 1 runnable (XAUUSD), 11 `tz_unreviewed`, 5 `no_data`. **M5** = 11 runnable (12 if note X is resolved as runnable), 0 `tz_unreviewed`, 5 `no_data`.

Consequences worth seeing up front:
- On M5, MT5 coins cover **2025-10-06 -> 2026-07-02** and Binance coins cover **2024-05-22 -> 2026-05-21**. The default intersection for any MT5 + Binance M5 mix is therefore **2025-10-06 -> 2026-05-21**.
- MT5 M5 last day (2026-07-02, ends 05:20/05:25) is a **partial day** (`last_day_complete=false`).
- M5 reviews were recorded by `reviewed_by='Grok'` (2026-09-15, `user_reviewed=true`), so the gate passes. Recorded as fact, not re-judged here.

**Note X - XAUUSD M5 (new finding, needs confirmation):** the clock is reviewed, but `data/mt5/XAUUSD_M5.csv` is listed in `forensic_paths` of the bound Dataset Identity record `XAUUSD_MT5_PHASE1_20260521`, and `dataset_registry._is_forensic_request()` also rejects native `_M5` tokens for a bound symbol. `CandleLoader` -> `admit_csv_path()` would therefore **refuse it (FORENSIC / NOT_ADMITTED)**. Design: treat as **`no_data`** (no *admissible* corpus; `no_data` has precedence) with reason text "forensic only - not an admitted corpus". See open question Q3.

### 1A.2 Disabled-state styling (real variables from `ui_kits/crt_dashboard/styles.css` `:root`)

Variables available: `--bad` #ef4444, `--bad-2` #f87171, `--warn` #facc15, `--muted` #7f8da6, `--muted-2` #95a3bd, `--line` #1e2a44, `--panel-3` #182542. There is no `--warn-2` and no existing `.tag.warn`, so the amber tint uses the rgba form of `--warn`, the same way existing `.tag.short` uses `rgba(239,68,68,0.15)` for `--bad`.

| State | Row text | Row accent (left border 2px) | Tag | Tag colours | Checkbox |
|---|---|---|---|---|---|
| runnable | `var(--text)` (selected) / `var(--muted-2)` | none | clock badge, `.tag.normal` | existing | enabled |
| `no_data` | `var(--muted)`, opacity 0.5, symbol struck-through | `var(--bad-2)` | `NO DATA` | `color: var(--bad-2)`, `background: rgba(239,68,68,0.12)` | disabled, `cursor: not-allowed` |
| `tz_unreviewed` | `var(--muted)`, opacity 0.6 (coverage dates still shown) | `var(--warn)` | `NO REVIEWED TZ` | `color: var(--warn)`, `background: rgba(250,204,21,0.12)` | disabled, `cursor: not-allowed` |

Implementation note (later): either inline styles, or a small clearly-commented `hr-` block appended to styles.css (`.hr-row.no-data`, `.hr-row.tz-unreviewed`, `.hr-tag.no-data`, `.hr-tag.tz-unreviewed`, `.hr-legend`) that uses only the variables above.

## 2. Findings (what exists today)

### 2.1 Where OHLCV lives

| Location | Family | Format | Naming | TFs present | Notes |
|---|---|---|---|---|---|
| `data/mt5/` | MT5 (FX + XAUUSD) | CSV | `{SYMBOL}_{TF}.csv` | M5, M15, H1, H4 | AUDUSD, EURCAD, EURUSD, GBPUSD, USDJPY, XAUUSD. `corpus_store._default_csv_path()` and `chart_api._corpus_path()` both point here. |
| `data/mt5/XAUUSD_M15.parquet` + `.parquet.manifest.json` | corpus_store read-cache | Parquet | `<csv>.parquet` | M15 | ONLY instrument with a Parquet sidecar. Manifest built 2026-09-24T19:35:12Z (= 2026-09-25 01:05 IST). |
| `data/binance/` | Binance (crypto) | CSV | `{SYMBOL}_{TF}.csv` | M5, M15, H1, H4 | BNB/BTC/DOGE/ETH/SOL/XRP USDT. |
| `data/` (root) | "AUTHORITATIVE_CANONICAL" per census | CSV | `{SYMBOL}_M15.csv` | M15 | Byte-duplicates of mt5/binance M15 for everything except `data/XAUUSD_M15.csv`, which has DRIFTED (now a 1-month window, see 2.3). |
| `data/resampled/` | DERIVED (H1/H4 from M15) | CSV | `{SYMBOL}_{TF}.csv` | H1, H4 | Crypto only. Derived, not a corpus. |
| `data/yfinance/` | yfinance | CSV/XLSX | mixed | M15 | LOW-confidence provider (no verify gate) per census. FX files there only ~2.3k rows. |
| `data/*_1year.xlsx`, `data/*_2year.xlsx`, `data/XAUUSD_M15_2026*.xlsx`, `data/yfinance/*.xlsx` | legacy exports | XLSX | ad-hoc | M15 | Columns are `timestamp,open,high,low,close,volume`, but they are subsets/exports. Example: `data/XAUUSD_M15_1year.xlsx` starts **2026-04-17 04:00**, not a year back. All listed with EMPTY timezone and `reviewed_by=None` in the clock registry. **Excel is NOT the authority. Do not read it for coverage.** |
| `data/mt5/_rejected/`, `data/_rejected/`, `data/_archive_5wk/` | quarantined / archived | CSV | | | Never a coverage source (census RULE-QUARANTINE / RULE-ARCHIVE). |
| `data/perp/` | funding/basis series | CSV | | | Not OHLCV (census RULE-NON-OHLCV). |

Column schema (all canonical CSVs + xlsx + parquet): `timestamp,open,high,low,close,volume`. Timestamps are **naive** (no offset). Parquet schema: `symbol:string, timestamp:timestamp[us], open..volume:double`.

### 2.2 Measured coverage (canonical files, 2026-09-25)

| File | Rows | first_ts | last_ts | modal step | gaps > step |
|---|---|---|---|---|---|
| data/mt5/XAUUSD_M15.csv | 47,275 | 2024-05-22 01:00 | 2026-05-21 23:45 | 900 s | 516 |
| data/mt5/XAUUSD_M15.parquet (row-group stats) | 47,275 | 2024-05-22 01:00 | 2026-05-21 23:45 | - | - |
| data/mt5/EURUSD_M15.csv | 49,721 | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 109 |
| data/mt5/AUDUSD_M15.csv | 49,722 | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 109 |
| data/mt5/EURCAD_M15.csv | 49,715 | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 110 |
| data/mt5/GBPUSD_M15.csv | 49,716 | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 110 |
| data/mt5/USDJPY_M15.csv | 49,716 | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 110 |
| data/binance/{BNB,BTC,DOGE,ETH,SOL,XRP}USDT_M15.csv | 70,080 each | 2024-05-22 00:00 | 2026-05-21 23:45 | 900 s | 0 |
| data/binance/BTCUSDT_M5.csv | 210,240 | 2024-05-22 00:00 | 2026-05-21 23:55 | 300 s | 0 |
| data/binance/BTCUSDT_H1.csv / _H4.csv | 17,520 / 4,380 | 2024-05-22 00:00 | 2026-05-21 23:00 / 20:00 | | 0 |
| data/mt5/AUDUSD_M5.csv | 55,037 | **2025-10-06 00:00** | **2026-07-02 05:25** | 300 s | 45 |
| data/XAUUSD_M15.csv (root) | 2,116 | 2026-07-07 01:00 | 2026-08-06 23:45 | 900 s | 22 |

Scan cost: 0.03 to 0.66 s per file (time column only), about 5 s cold for the whole universe. Parquet stats read is effectively free.

Takeaways:
- Every canonical M15 corpus today ends **2026-05-21 23:45**. Today is 2026-09-25, so "Last 30d from today" would return an EMPTY range. Presets must be anchored to coverage end, not to today.
- M5 coverage differs from M15 for the same instrument (AUDUSD M5 is 2025-10-06 to 2026-07-02). Coverage is per (instrument, timeframe).
- FX gaps (~109) are weekends (census: largest EURUSD gap 173,700 s = 48.25 h). XAUUSD has 516 (daily session break + weekends). Crypto has none.

### 2.3 Existing manifests / registries (authority candidates)

1. **Dataset Identity registry**: `docs/governance/dataset_identity_registry.json` -> records under `docs/governance/datasets/*.json`. Loaded by `src/data_ingestion/dataset_registry.py::load_bound_datasets()`, verified by `resolve_canonical()`. Only **XAUUSD** is bound:
   - `XAUUSD_MT5_PHASE1_20260521`: `canonical_artifact` = data/mt5/XAUUSD_M15.csv, sha256 4d73f5ce..., rows 47,275, start 2024-05-22T01:00:00, end 2026-05-21T23:45:00, clock_basis broker_local, `legacy_rewrite_target: true`. This matches the measured file exactly. H1/H4/D1/W1/MN1 are *projections* (ParentCandleBuilder) of M15. Native `data/mt5/XAUUSD_H1.csv`, `_H4.csv`, `_M5.csv` and `data/XAUUSD_M15.csv` are listed as **forensic_paths** (not a corpus).
   - `XAUUSD_MT5_TVWINDOW_20260706_20260807`: data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv, 2,300 rows, 2026-07-06T01:00 to 2026-08-07T23:45, decision_status UNRESOLVED.
   - Unbound instruments use `unbound_load_policy: path_passthrough` (no recorded coverage).
2. **corpus_store Parquet manifest**: `data/mt5/XAUUSD_M15.parquet.manifest.json` (rows 47,275, source {path, size, mtime_ns, sha256}, dataset_id, admission_decision WARN). Freshness via `src/data_ingestion/corpus_store.py::status()` (FRESH/STALE/ABSENT/UNAVAILABLE by size+mtime_ns, optional sha256). No first/last ts in the manifest, but the Parquet `timestamp` column has row-group min/max statistics (verified: 2024-05-22 01:00 / 2026-05-21 23:45).
3. **OHLCV census fingerprint manifest**: `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json` (generated by `scripts/analysis/ohlcv_census.py`, 224 artifacts). Per artifact: `physical_path, size_bytes, sha256, instrument, timeframe, authority_class (AUTHORITATIVE_RAW / AUTHORITATIVE_CANONICAL / DERIVED / QUARANTINED / ARCHIVED / EXCLUDED), rows, first_timestamp, last_timestamp, timezone, modal_delta_seconds, gap_events_gt_modal, largest_gap_seconds, duplicate_timestamps, ...`. It matched every measured file EXCEPT `data/XAUUSD_M15.csv` (census: 50,169 rows to 2026-07-06; disk now: 2,116 rows, size mismatch). **So the census is usable only when size (and sha256) still match the file on disk.**
4. **Clock registry**: `configs/data_provenance/ohlcv_clock_registry.json` (220 records; `src/data_ingestion/clock_registry.py::lookup()`). Reviewed clocks: data/mt5/XAUUSD_M15.csv = `MT5_SERVER_NY_DST`; all `data/mt5/*_M5.csv` = MT5_SERVER_NY_DST; all `data/binance/*_M5.csv` = UTC. **All other M15 corpora (EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD, all binance M15) have EMPTY timezone / reviewed_by=None.** `CandleLoader.__init__` (`src/runtime/backtest_v2.py:896`) calls `require_reviewed_clock(...)`, so a backtest on those corpora would fail closed today. Coverage must expose this.
5. `data/asset_coverage.jsonl` is NOT data coverage (it is a runtime artifact writer catalog, RTC-001..008). Not relevant.
6. `data/corpus.duckdb` exists (274 KB) but is not referenced by the loaders below. OPEN: purpose unknown, not used.

### 2.4 How the dashboard gets `instruments`

- `ui_kits/crt_dashboard/apiClient.js` `fetchInstruments()` -> `GET /api/instruments`.
- Server: `src/control_plane/server.py` (stdlib HTTP, `scripts/control_plane/run_server.py --port 8787`), `do_GET` at line ~1651, route at line ~1679 -> `dash_api.instruments_payload()`.
- `src/control_plane/dashboard_api.py::instruments_payload()` (line ~1235) = active production config pairs/allowed_symbols/market_router keys UNION `_instruments_from_disk()` (results/run_*_<SYM>, logs/<SYM>/, data/*_M15.*) UNION `KNOWN_INSTRUMENTS`.
- Live response today: 17 instruments. **5 have NO OHLCV corpus on disk**: ADAUSDT, EURGBP, NZDUSD, USDCAD, USDCHF (only `_rejected/ADAUSD_*` exists). The instrument list is a union of "known names", not "data we have". The coverage endpoint must be what decides whether an instrument is selectable.
- **No existing endpoint exposes data coverage.** Closest: `GET /api/chart_series` -> `src/charts/chart_api.py::chart_payload()`, which loads `data/mt5/{instrument}_M15.csv` (hard-coded, so crypto charts have no corpus) with a `(path, mtime_ns, size)` cache (`_cache_key`, `_load_base_cached`) and runs `dataset_integrity.validate_dataset` (`_integrity_cached`). `/catalog` lists raw data files only (no coverage).

### 2.5 Loaders a coverage endpoint must reuse (not reimplement)

| Need | Reuse |
|---|---|
| Which file is canonical for (instrument, TF); legacy rewrite; forensic rejection | `data_ingestion.dataset_registry.admit_csv_path()`, `load_bound_datasets()`, `resolve_canonical()` |
| Bound-record coverage (start/end/rows/sha) | Dataset Identity record `canonical_artifact` / `timeframes[TF]` |
| Parquet cache freshness + fingerprint | `data_ingestion.corpus_store.status()`, `_fingerprint()`, `_manifest_path()`, `parquet_available()` |
| Time-column parse (same parser validation used) | `data_ingestion.dataset_integrity._stream_candles()` (reused by corpus_store.build for that reason); header aliases via `data_ingestion.ohlcv_schema.resolve_ohlcv_headers()` / `resolve_ohlcv_column_indices()`, `parse_ohlcv_timestamp()` |
| Gap analysis (session-aware) | `data_ingestion.dataset_integrity._analyze_gaps()` / `validate_dataset()` (already cached by chart_api) |
| Admission / plausibility verdict | `data_ingestion.corpus_gate.admit_corpus()` (`CorpusAdmission`) |
| Clock status | `data_ingestion.clock_registry.lookup()` (+ `require_reviewed_clock` semantics) |
| Cache key convention | `charts.chart_api._cache_key()` -> `(path, mtime_ns, size)` |
| Census fallback | `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json` (read-only JSON) |

---

## 3. Authority order for coverage (per instrument, timeframe)

Resolve the canonical path first (step 0), then take coverage from the first source that is VALID for that exact file:

0. **Resolve path**: bound dataset -> `resolve_canonical(dataset_id)`; else `admit_csv_path(requested, instrument)` on the family default (`data/mt5/{SYM}_{TF}.csv` for MT5 symbols, `data/binance/{SYM}_{TF}.csv` for USDT symbols; see open question Q1). Forensic / `_rejected` / `_archive` / derived-suffix paths are never eligible.
1. **Dataset Identity record** (bound datasets): `canonical_artifact.start/end/rows/sha256`. Valid only if the file's sha256 matches (as `resolve_canonical` already enforces). Today: XAUUSD M15 only. (Its M5 file is a forensic path of that record -> not admissible, see Note X.)
2. **corpus_store Parquet sidecar**: `status(...) == FRESH` -> rows from `ParquetFile.metadata.num_rows`, first/last from `timestamp` row-group min/max statistics (no data read). STALE/ABSENT -> skip (never serve stale). Today: XAUUSD M15 only.
3. **Census fingerprint manifest** entry for the same `physical_path`, only if `size_bytes` == current size AND (when computed) `sha256` matches. Gives first/last/rows/gaps for free. Today: valid for all canonical mt5/binance files. Invalid for `data/XAUUSD_M15.csv` (drifted).
4. **File scan**: stream the time column via the reused parser; compute first/last/rows/modal step/gap count. Cache by `(path, mtime_ns, size)`.
5. **Excel**: EXCLUDED (user decision D5, CONFIRMED 2026-09-28 01:12 IST). The xlsx files are subsets/exports with unreviewed clocks and are never read for coverage.

Every response states which step answered (`coverage_source`), so the UI can show the provenance and an auditor can reproduce it.

---

## 4. Proposed endpoint (read-only)

`GET /api/corpus/coverage?instrument=<SYM>&timeframe=<M15|M5>`

- `instrument` optional: omitted = every instrument from `instruments_payload()`, so the page gets list + states + coverage in one call and names without data come back as `no_data`.
- `timeframe` **required by the UI** (selector, D2), server default `M15`. Allowed: `M15`, `M5`. Anything else -> HTTP 400 `{error: "UNSUPPORTED_TIMEFRAME"}`. Every field below is per (instrument, timeframe); the page refetches (or reads its per-TF cache) on every timeframe switch.
- Placement: new `coverage_payload()` in a new `src/control_plane/coverage_api.py` (or a method on the dashboard API object), routed in `server.py` `do_GET` next to `/api/instruments`. Client: `ApiClient.fetchCorpusCoverage(timeframe, instrument?)` in `apiClient.js`. GET only, no side effects: it must NOT call `corpus_store.build()` / `ensure_fresh()` and must not write reports (`write_report=False`).

### 4.1 State derivation (per instrument, timeframe) - evaluated in this order, first hit wins

1. `no_data` - no family file; OR file unreadable / no time column / zero parseable rows; OR the only file is forensic / quarantined / not admitted (`admit_csv_path` would raise, e.g. XAUUSD M5, Note X). **Precedence over `tz_unreviewed`** (D4).
2. `tz_unreviewed` - file present and admissible, but `clock_registry.lookup(path)` has no record, `user_reviewed=false`, empty `timezone`, or recorded `sha256` != current file sha (STALE review). Same checks as `require_reviewed_clock()`, evaluated without raising.
3. `runnable` - otherwise.

`selectable = (state == "runnable")`. `reasons[]` keeps the detailed code(s); `state` is what the UI styles.

### 4.2 Response

```json
{
  "generated_at": "2026-09-25T02:00:00+05:30",
  "timeframe": "M5",
  "counts": { "runnable": 11, "tz_unreviewed": 0, "no_data": 6 },
  "items": [
    {
      "instrument": "AUDUSD", "timeframe": "M5",
      "state": "runnable", "selectable": true, "reasons": [],
      "source_path": "data/mt5/AUDUSD_M5.csv", "format": "csv",
      "coverage_source": "census_manifest",
      "first_ts": "2025-10-06T00:00:00", "last_ts": "2026-07-02T05:25:00",
      "first_date": "2025-10-06", "last_date": "2026-07-02", "last_day_complete": false,
      "row_count": 55037, "bar_seconds": 300,
      "clock": { "timezone": "MT5_SERVER_NY_DST", "user_reviewed": true, "reviewed_by": "Grok", "sha_match": true },
      "gaps_summary": { "gap_events": 45, "largest_gap_seconds": null },
      "fingerprint": { "size": 3103556, "mtime_ns": "...", "sha256": "6856a2d5..." }
    },
    {
      "instrument": "EURUSD", "timeframe": "M15",
      "state": "tz_unreviewed", "selectable": false,
      "reasons": ["CLOCK_UNREVIEWED"], "reason_text": "no reviewed timezone",
      "source_path": "data/mt5/EURUSD_M15.csv", "format": "csv",
      "coverage_source": "census_manifest",
      "first_ts": "2024-05-22T00:00:00", "last_ts": "2026-05-21T23:45:00",
      "row_count": 49721, "bar_seconds": 900,
      "clock": { "timezone": null, "user_reviewed": false, "reviewed_by": null, "sha_match": true }
    },
    {
      "instrument": "XAUUSD", "timeframe": "M5",
      "state": "no_data", "selectable": false,
      "reasons": ["FORENSIC_ONLY"], "reason_text": "forensic only - not an admitted corpus",
      "source_path": "data/mt5/XAUUSD_M5.csv",
      "first_ts": null, "last_ts": null, "row_count": null
    },
    {
      "instrument": "NZDUSD", "timeframe": "M5",
      "state": "no_data", "selectable": false,
      "reasons": ["NO_FILE"], "reason_text": "no M5 data on disk",
      "source_path": null, "first_ts": null, "last_ts": null, "row_count": null
    }
  ]
}
```

- For `tz_unreviewed`, coverage fields ARE returned (informational, shown greyed). For `no_data` they are null.
- `reasons[]` codes: `NO_FILE, UNREADABLE, NO_TIME_COLUMN, UNPARSEABLE_TS, EMPTY, FORENSIC_ONLY, QUARANTINED, ADMISSION_REJECT, AUTHORITY_MISMATCH` (-> `no_data`); `CLOCK_NO_RECORD, CLOCK_UNREVIEWED, CLOCK_STALE_SHA` (-> `tz_unreviewed`).
- Endpoint-level failure (exception, timeout) -> HTTP 5xx `{error}`; the UI treats it as "whole page disabled" (section 7).

Optional later (not v1): `POST /api/corpus/coverage/refresh`; `?gaps=1` for top-N gap detail.

## 5. Caching and fingerprint

- In-process dict keyed `(abs_path, mtime_ns, size)` (same convention as `chart_api._cache_key`), bounded (e.g. 64 entries, FIFO like `_CACHE_MAX_ENTRIES`).
- sha256 computed lazily (only when needed to validate a Dataset Identity record or census entry) and cached under the same key. Never recompute while mtime+size are unchanged.
- Cache invalidates automatically when a file is rewritten (mtime/size change). A census entry whose size no longer matches is ignored for that file (falls through to scan) and the item carries `coverage_source: "file_scan"` plus reason note `CENSUS_STALE` (informational).
- Response carries `fingerprint` so the eventual Run request can include it (`coins[i].fingerprint`) and the backend can refuse a run if the corpus changed between page load and Run.
- Cold full-universe cost measured about 5 s. Warm is dict lookups. Acceptable. The page shows a loading state per row.

---

## 6. UI behaviour (page10_admin.jsx)

### 6.1 Instrument list
- Source = `/api/corpus/coverage?timeframe=<selected TF>` items. No placeholder list; the design-only `HR_PLACEHOLDER_INSTRUMENTS` fallback in the current page is removed when this is wired. If the call fails: a single error row ("Coverage unavailable: <error>. Historical Run disabled."), no rows selectable, Run disabled.
- Row content: symbol, `first_date -> last_date`, row count, source badge (`identity` / `parquet` / `census` / `scan`), clock badge (`MT5 NY-DST` / `UTC`).
- Row state styling per section 1A.2:
  - `runnable`: normal, selectable.
  - `tz_unreviewed` (D1): greyed, amber accent `var(--warn)`, tag `NO REVIEWED TZ`, coverage dates still visible, checkbox disabled, tooltip = `reason_text`.
  - `no_data` (D4): greyed and struck-through, red accent `var(--bad-2)`, tag `NO DATA`, no dates, checkbox disabled, tooltip = `reason_text` (e.g. "no M15 data on disk", "forensic only - not an admitted corpus").
  - Precedence `no_data` > `tz_unreviewed` is decided server-side (4.1); the UI only renders `state`.
- Ordering: runnable first, then `tz_unreviewed`, then `no_data` (alphabetical within each group), so selectable coins are at the top.
- Header counter: `N selected / R runnable of T` for the current timeframe.
- "Select all" selects only `runnable` rows (respecting the filter).

### 6.2 Date pickers
- No dates until at least one runnable coin is selected: both inputs empty and disabled.
- On selection change: **default = the full intersection window** (D3): `From = max(first_date_i)`, `To = min(last_date_i)`. `min`/`max` attributes are set to the same bounds on both inputs.
- If the user has edited dates and the selection changes, re-clamp the edited dates into the new window. If they no longer fit, reset to the full intersection and show a one-line notice.
- Typed or pasted dates outside [min, max] are rejected inline. Run is disabled while invalid.

### 6.3 Multi-coin rule
- **Default: intersection** (D3). If empty (min > max): "Selected instruments have no overlapping coverage on <TF>", Run disabled.
- **Union: opt-in toggle** with a warning chip "Union: some instruments lack data for part of this range". Bounds = `min(first_date_i) .. max(last_date_i)`. Summary lists each coin's clipped effective range. Request carries `range_mode: "union"`.
- Example (today's data): M15 has only XAUUSD runnable -> 2024-05-22 -> 2026-05-21. M5 MT5 + Binance mix -> intersection **2025-10-06 -> 2026-05-21**. M5 MT5-only -> 2025-10-06 -> 2026-07-02 (last day partial). M5 Binance-only -> 2024-05-22 -> 2026-05-21.

### 6.4 Timeframe selector (D2)
- Segmented control `M15 | M5` (existing `.tabs`/`.tab` or `.btn.ghost`/`.btn.outline` pattern) above the instrument list, default `M15`.
- On switch:
  1. Fetch or reuse per-TF coverage.
  2. Recompute every row's state.
  3. **Drop selected coins that are not runnable on the new TF**, with a notice ("Removed on M5: XAUUSD (forensic only)").
  4. Recompute the intersection and reset dates to it.
- Under each coin, a subtle hint shows its state on the *other* TF when it differs (e.g. EURUSD on M15: "runnable on M5"), so the user can discover that switching TF unlocks coins.
- Coverage genuinely differs per TF (AUDUSD M15 2024-05-22 -> 2026-05-21 vs M5 2025-10-06 -> 2026-07-02); the calendar always reflects the selected TF.
- Timeframe goes into the run request.

### 6.5 Presets
- Anchored to the current window's **max** (corpus end), not today. `Full` (= default intersection, selected on load), `Last 1y`, `Last 90d`, `Last 30d`. Each is clamped to `min` and labelled when clamped. A preset is disabled if the window is shorter than it would need. No preset is auto-applied except `Full`.

### 6.6 Run summary (still design-only until wired)
`coins=[...], timeframe, from, to, range_mode, per-coin {state, first_ts, last_ts, clock.timezone, fingerprint}`, plus a warning if any selected coin has `last_day_complete=false` or selected coins mix clocks (MT5 NY-DST + UTC).

### 6.7 Legend (D4)
A single line under the instrument list (small, `.muted`, 10-11px):
`[green-dot] runnable   [amber tag] NO REVIEWED TZ - data present, clock not reviewed (backtest loader would refuse)   [red tag] NO DATA - no admissible file for this timeframe`
using exactly the colours in 1A.2.

## 7. Fail-closed rules

| Condition | State / result |
|---|---|
| No family file for (instrument, TF) | `no_data` (`NO_FILE`), greyed red, no dates |
| File unreadable / parse exception | `no_data` (`UNREADABLE`) |
| Time column not resolvable via ohlcv_schema aliases | `no_data` (`NO_TIME_COLUMN`) |
| Zero rows / all timestamps unparseable | `no_data` (`EMPTY` / `UNPARSEABLE_TS`) |
| Only forensic / `_rejected` / derived / non-admitted file (e.g. XAUUSD M5) | `no_data` (`FORENSIC_ONLY` / `QUARANTINED` / `ADMISSION_REJECT`) |
| Bound record sha256 != file sha256 | `no_data` (`AUTHORITY_MISMATCH`), matches `resolve_canonical` |
| Clock record missing / `user_reviewed=false` / empty tz | `tz_unreviewed` (`CLOCK_NO_RECORD` / `CLOCK_UNREVIEWED`), greyed amber, dates shown, not selectable (D1) |
| Clock record sha != file sha (review stale) | `tz_unreviewed` (`CLOCK_STALE_SHA`) |
| Both a no_data and a tz cause | `no_data` (precedence, D4) |
| Parquet sidecar STALE | skip to the next coverage source (never serve stale stats); informational note |
| Coverage endpoint error / timeout | whole page: no rows selectable, no dates, Run disabled, error banner. **No fallback to placeholder list or default dates.** |
| Intersection empty | Run disabled, message |
| Selected coin becomes non-runnable after a TF switch | removed from selection with a notice |

## 8. Edge cases

- **Time zones.** Corpus timestamps are naive and in the corpus clock: XAUUSD and MT5 = `MT5_SERVER_NY_DST` (broker-local), Binance M5 = UTC, Binance/MT5 M15 other than XAUUSD = unreviewed (census says "UTC is an ASSUMPTION"). Recommendation: the date pickers operate in **corpus-clock dates** (what the loader slices on), labelled e.g. "dates in broker time (MT5 NY-DST)". Show an IST conversion only as a tooltip on first/last ts (e.g. 2026-05-21 23:45 MT5 server time is around 2026-05-22 02:15 IST in summer). Mixed-clock multi-select (MT5 + Binance) must show a warning that "the same date" means different instants. See open question Q2.
- **Range semantics.** `from` = first bar with ts >= from 00:00, `to` = inclusive calendar day, sent to the backend as exclusive `to+1d 00:00`. This matches `corpus_store.read(start, end)` half-open `[start, end)`.
- **Partial first/last day.** XAUUSD starts 01:00 (session open) and that is not flagged. `last_day_complete` = last bar == last expected slot of the day for that market (FX/XAU 23:45, crypto 23:45). Example of a partial day: AUDUSD M5 ends 2026-07-02 05:25, flagged "last day partial".
- **Gaps.** Show `gap_events` and `largest_gap` per coin. Weekends and XAU daily breaks are expected. Distinguishing them from real holes needs `dataset_integrity` session-aware analysis (`_analyze_gaps` with market type). A selected range that lands entirely inside a gap (e.g. a weekend-only range) must be rejected ("0 bars in range").
- **Drifted duplicates.** `data/XAUUSD_M15.csv` (root) is now a 1-month file while the census recorded 2 years, and the Dataset Identity record lists it as forensic. Coverage must come from the resolved canonical path, never from a same-named file elsewhere.
- **Instruments with only rejected data** (ADAUSD under `_rejected`, requested as ADAUSDT): `NO_CORPUS` (no symbol aliasing ADAUSD <-> ADAUSDT in v1).
- **Corpus refreshed while the page is open.** The Run request carries fingerprints, so the backend re-checks and refuses on mismatch.

---

## 9. Open questions (for the user)

Answered on 2026-09-25 01:56 IST and moved to section 1A: tz-unreviewed handling (D1), timeframes (D2), default range (D3), no-data instruments (D4), Excel (D5, CONFIRMED 2026-09-28 01:12 IST).

Remaining:
1. **Crypto canonical root**: for USDT symbols, is the backtest corpus `data/binance/{SYM}_{TF}.csv` (assumed in this card; M5 exists only there) or root `data/{SYM}_M15.csv` (byte-identical for M15 today; census calls root "AUTHORITATIVE_CANONICAL", config `dataset_integrity.canonical_data_roots=['data']`)? `corpus_store._default_csv_path` only knows `data/mt5/`.
2. **Calendar clock**: pick dates in corpus clock (recommended; MT5 = MT5_SERVER_NY_DST, Binance M5 = UTC) or IST? Mixed-clock selections (MT5 + Binance) mean "the same date" is a different instant per coin.
3. **XAUUSD dataset choice / XAUUSD M5**: two bound datasets exist (PHASE1 2024-05-22 -> 2026-05-21; TVWINDOW 2026-07-06 -> 2026-08-07, UNRESOLVED). Offer only PHASE1 (the `legacy_rewrite_target`), or let the user pick? And confirm XAUUSD M5 stays `no_data` (forensic per the PHASE1 record, Note X) rather than being admitted.
4. **Excel (D5)**: CONFIRMED 2026-09-28 01:12 IST - Excel excluded (resolved; kept here for numbering).

## 10. OPEN (not found / not verified)

- `data/corpus.duckdb`: purpose and whether it holds coverage. Not referenced by the loaders inspected.
- Job runner: whether a Historical Run backend exists to consume the request (`src/control_plane/jobs.py::create_run` exists, not inspected).
- Binance M15 timezone: M15 files have no clock record (-> `tz_unreviewed` on M15). Binance M5 are declared UTC (reviewed_by Grok, "UTC epoch by API contract"). Whether M15 should get the same declaration is a registry action, out of scope here.
- Session-aware gap classification output shape of `dataset_integrity._analyze_gaps` (not read in detail). `largest_gap_seconds` for XAUUSD and the M5 files was not measured.
- Whether M5 runs are actually supported end-to-end by the backtest engine (the loader gates pass; strategy/config support for M5 not checked).

## 11. Implementation checklist (when approved; not done)

1. `coverage_api.py`: `coverage_payload(instrument=None, timeframe="M15")` for `M15|M5`, implementing section 3 authority order, 4.1 state derivation (reuse `dataset_registry.admit_csv_path`, `clock_registry.lookup` + sha check), cache from section 5.
2. `server.py` do_GET route `/api/corpus/coverage` (400 on unsupported TF).
3. `apiClient.js` `fetchCorpusCoverage(timeframe, instrument?)`.
4. `page10_admin.jsx`: M15/M5 selector; coverage-driven list with `runnable` / `tz_unreviewed` / `no_data` styling and legend (1A.2, 6.7); intersection default; union toggle; anchored presets; TF-switch re-evaluation; fail-closed states (section 7). Remove `HR_PLACEHOLDER_INSTRUMENTS`.
5. Optional `hr-` CSS block in styles.css using only `--bad-2`, `--warn`, `--muted`, `--line` (+ rgba tints of `--bad` / `--warn`).
6. Tests: fixtures for each row of section 7, both TFs; the per-coin table in 1A.1 as a golden snapshot (as of 2026-09-25); precedence case (no file + no clock -> `no_data`); XAUUSD M5 forensic case; TF switch dropping selections.
