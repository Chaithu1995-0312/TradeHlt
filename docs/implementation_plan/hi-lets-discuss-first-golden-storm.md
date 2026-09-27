# Parquet-backed windowed backtest (XAUUSD M15, one month) — design + DeepSeek prompt

## Context
The user wants a one-month XAUUSD backtest that reads candles through the governed Parquet layer
(not a raw CSV read), for a chosen config version, with a metrics summary plus detailed trade/event
logs. Today `backtest_v2.py` can only (a) read the whole CSV and (b) run `ACTIVE_VERSION`. User
decisions: **full history before the window** (so window trades match a full run exactly), and
**two stages** (admitted month first, newer Aug–Sep data as a follow-up).

## Verified facts (checked at source this session)
- `backtest_v2.py` CLI args at `src/runtime/backtest_v2.py:4677-4692`: **no** `--start/--end/--version`.
  `--config` does NOT switch configs — it only relabels `PROD_VERSION` to `CUSTOM:...` after the
  CRT config was already loaded from `ACTIVE_VERSION` (`:4709`, `:4754-4761`). Misleading flag.
- Version is fixed at import: `PROD_VERSION = get_active_version()` (`src/config_layer/production_config.py:82`).
  Existing precedent for running another version: `src/charts/crt_overlay.py:230-249` swaps
  `production_config.PROD_VERSION` and `backtest_v2.PROD_VERSION`, then restores.
- Parquet layer = `src/data_ingestion/corpus_store.py` (`build` / `ensure_fresh` / `read`). Per its
  docstring and FROZEN `docs/governance/CORPUS_AUTHORITY.md`, the **admitted CSV stays the sole
  identity anchor**; Parquet is a disposable cache re-verified against the CSV sha256 on every
  read (STALE ⇒ raises). So "don't read CSV" means "don't parse the CSV ad hoc" — the CSV bytes
  remain the truth the Parquet is checked against.
- Precedent consumer: `src/research/runner.py:145-195` (`HypothesisRunner._load_candles`) —
  windowed `corpus_store.read(...)`, `in_window` flags, provenance dict recorded. Mirror it.
- Enforcement already exists: `scripts/analysis/corpus_read_lint.py` (shrink-only ratchet on
  ungated corpus reads, allowlist `docs/governance/corpus_read_allowlist.json`).
- Admitted XAUUSD dataset: `XAUUSD_MT5_PHASE1_20260521`, `data/mt5/XAUUSD_M15.csv`, 47,275 rows,
  **2024-05-22 01:00 → 2026-05-21 23:45** (`docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json`).
  Parquet cache exists (`data/mt5/XAUUSD_M15.parquet` + manifest, built 2026-09-24, sha matches).
- `data/mt5/XAUUSD_M15_20260817_20260917.csv` is **unregistered** and referenced by no code.
  There is a **gap 2026-05-21 → 2026-08-17** between it and the admitted corpus.
- `BacktestRunner.run(candle_source, total_candles, output_dir)` (`:2948`) accepts any Candle
  iterator — clean seam. BUT `BacktestRunner.__init__` separately does `pd.read_csv(self.csv_path)`
  to build features (`:2464-2512`), and `self.csv_path` feeds provenance/hash/range in ~9 places
  (`:2663, 2735, 2766, 2852, 2899, 3084, 3140, 4243, 4292`).
- Outputs already produced per run: `{instr}_summary.json` (`:2118`), `{instr}_trades.csv`
  (`:2152`), `{instr}_events.jsonl` (`:2162`), `crt_telemetry.jsonl`. Metrics via
  `MetricsEngine.compute(journal, capital, ...)` (`:1705-1717`).

## Design (Stage 1 — admitted month 2026-04-21 → 2026-05-21)
1. **New CLI flags, all additive; defaults byte-identical to today:**
   `--source {csv,parquet}` (default `csv`), `--window-start`, `--window-end` (ISO; only valid with
   `--source parquet`), `--version` (default = `ACTIVE_VERSION`).
2. **Parquet read:** `corpus_store.read(instrument, "M15", start=None, end=None, strict=True)` —
   full history (user's choice). Fail closed on ABSENT/STALE with a message to run
   `corpus_store.build`. Never silently fall back to CSV.
3. **Features from the same bytes:** add optional `ohlcv_frame: pd.DataFrame | None` to
   `BacktestRunner.__init__`; when given, use it instead of `pd.read_csv(self.csv_path)` at
   `:2469`. Build the frame from `CorpusRead.candles` (timestamp/open/high/low/close/volume).
   Keep `csv_path = CorpusRead.csv_path` (the admitted CSV) so all provenance/hash sites keep
   pointing at the identity anchor — correct per CORPUS_AUTHORITY.
4. **Window report (post-filter, no engine change):** after the full replay, select closed trades
   whose **entry timestamp** ∈ [window_start, window_end]; rebuild a `TradeJournal` + fresh
   `CapitalCurve` from them and reuse `MetricsEngine.compute` (no re-derived metric math). Write
   `{instr}_window_summary.json`, `{instr}_window_trades.csv`, `{instr}_window_events.jsonl`
   (events filtered by bar timestamp) next to the untouched full-run files. Summary records
   `window`, `resolved first/last bar`, `dataset_id`, `csv_sha256`, `parquet_path`,
   `config_version`, and counts excluded (opened before window / closed after).
5. **Version selection:** follow the `crt_overlay.py:230-249` swap pattern, but first grep every
   `from ... import PROD_VERSION` / `get_prod_section` / `get_prod_config` consumer and prove the
   requested version reaches all of them (module-level copies will NOT see a swap). Fail closed if
   `configs/production/<version>.json` is missing. Record resolved version in the summary; the
   run must refuse to start if the summary would show a different version than requested.
6. **Governance:** classify against `docs/governance/change_contracts.json` + build manifest;
   `corpus_read_lint.py` must stay green (no new ungated read); SESSION LOG entry (commit hook,
   `src/**` touched); fix the misleading `--config` help text or leave it and note it (ask user).

## Stage 2 (follow-up, separate task — do NOT bundle)
Admit the Aug–Sep month. Open issue first: CORPUS_AUTHORITY says "one admitted artifact", and
there is a 3-month gap, so "full history before window" is impossible until May 21→Aug 17 is
fetched too. Needs: fetch gap via existing strict MT5 fetch, new dataset identity record +
clock review (`configs/data_provenance/ohlcv_clock_registry.json`), then `corpus_store.build`.
Design this with the user before implementing.

## Prompt for DeepSeek (Stage 1) — paste as-is
```
ROLE: Implementer for the Tradelatest repo (Python 3.12, venv at venv\Scripts\python.exe).
GOAL: Add a Parquet-backed, windowed, version-selectable mode to src/runtime/backtest_v2.py so
this runs:
  venv\Scripts\python.exe src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv
    --instrument XAUUSD --source parquet --window-start 2026-04-21T00:00:00
    --window-end 2026-05-21T23:45:00 --version <VERSION> --output results/xauusd_1m
HARD CONSTRAINTS:
- Default behaviour (no new flags) must be byte-identical: same trades.csv/summary.json on the
  full XAUUSD corpus before vs after your change. Prove it with a diff.
- Candles come from data_ingestion.corpus_store.read(instrument, "M15", strict=True) with
  start=None (full history). Never pd.read_csv the corpus on the parquet path. Fail closed on
  CorpusStoreError; never fall back to CSV.
- Mirror src/research/runner.py:145-195 (HypothesisRunner._load_candles) for the read + provenance.
- BacktestRunner.__init__ reads the CSV for features at backtest_v2.py:2469. Add an optional
  ohlcv_frame kwarg; when set, use it there instead of pd.read_csv. Build it from
  CorpusRead.candles. Keep csv_path = CorpusRead.csv_path so provenance sites (:2663 :2735 :2766
  :2852 :2899 :3084 :3140 :4243 :4292) still hash the admitted file.
- Window report = post-filter only. Do NOT gate entries in the engine. Trades whose entry
  timestamp is inside the window -> new TradeJournal + CapitalCurve -> reuse
  MetricsEngine.compute (backtest_v2.py:1705). Write {instr}_window_summary.json,
  {instr}_window_trades.csv, {instr}_window_events.jsonl beside the normal outputs. Summary must
  include window, resolved first/last bar, dataset_id, csv_sha256, parquet_path, config_version,
  excluded_opened_before_window, excluded_open_at_end.
- --version: default = configs/production/ACTIVE_VERSION. Use the swap pattern in
  src/charts/crt_overlay.py:230-249, BUT first grep for every `import PROD_VERSION`,
  get_prod_section, get_prod_config consumer reachable from backtest_v2 and show the requested
  version reaches each one. Fail closed if configs/production/<version>.json is missing.
- No new formula math, no magic numbers (CLAUDE.md §6.5), no edits to active configs.
- scripts/analysis/corpus_read_lint.py must pass.
TESTS (tests/test_backtest_parquet_window.py): default path unchanged; parquet path candles ==
CandleLoader candles (ts+OHLCV) on the full corpus; STALE cache raises; window filter counts
correct on a synthetic journal; --version with a missing file raises; resolved version recorded.
OUTPUT: unified diff + new test file + the byte-identity diff evidence. If anything is unclear,
write "# UNKNOWN:" instead of guessing.
```

## Verification (after DeepSeek's diff comes back — Claude runs this)
1. Preflight: `git status --porcelain` (concurrent sessions), interpreter = `D:\Tradelatest\venv`.
2. Byte-identity: default CSV run before/after on full XAUUSD → identical trades.csv/summary.json.
3. `venv\Scripts\python.exe -m pytest tests/test_backtest_parquet_window.py tests/test_corpus_store.py -v`.
4. `venv\Scripts\python.exe scripts/analysis/corpus_read_lint.py` and
   `scripts/maintenance/check_governance_invariants.py --all` (compare to pre-change red count).
5. Run the target command in the background; check window_summary shows 2026-04-21→05-21,
   dataset_id `XAUUSD_MT5_PHASE1_20260521`, requested version; spot-check that window trades
   equal the full-run trades with entry dates in that month.
