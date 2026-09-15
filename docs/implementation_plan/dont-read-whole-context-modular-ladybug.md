# Trade Chart tab — TradingView-style run chart in the CRT dashboard

## Context

`ui_kits/crt_dashboard/page4_trades.jsx` has four sub-tabs (Trade Explorer / Trade Trace /
Rejections / Session Analysis). None of them shows price. A run selected in the TopBar
dropdown is currently only readable as tables and KPI tiles — there is no way to look at
the bars the engine actually traded, or to see *where* in the price structure a CRT state
was held.

Nearly all the machinery already exists and is unused by the dashboard:

- `src/charts/chart_series.py` — governed corpus load (`CandleLoader`), the M15→H1/H4/D1/W1
  ladder (delegated to `research.resample` / `features.calendar_periods`), causal state
  downsampling, the frozen 9-state colour tokens, `crt_aliasing`, `build_legend`,
  `build_config_pin`.
- `src/charts/crt_overlay.py` — per-bar CRT track from a run's `events.jsonl`, joined **by
  timestamp** and fail-closed (three prior wrong answers are documented in its docstring).
- Every run dir (`results/run_<ts>_<INSTR>/`) already carries `<INSTR>_events.jsonl` and
  `<INSTR>_trades.csv`; `runs_payload` already reports `has_events`.
- `data_ingestion.dataset_integrity.validate_dataset` is the L3 OHLC gate.

So the work is: one read-only JSON endpoint, one precompute CLI for the resolver track, and
one React panel. Outcome: selecting a run in the TopBar and opening **Trade Chart** shows
that run's bars with its CRT states, its trades, its events, and the integrity verdict for
the corpus underneath — pan/zoom/crosshair like TradingView.

Authority: descriptive/UI only. No config change, hash-neutral, no economic claim, no G001
(CLAUDE.md §6.5).

## Design (approved mock)

Toolbar (run id · integrity badge · state-source badge · timeframe segmented control ·
overlay toggles) → chart (candles, gap bands, trade entry/exit markers with SL/TP1/TP2
price lines, CRT event pins) → engine state ribbon → resolver state ribbon with mismatch
hatching and agreement % → volume strip → legend + provenance footer (clock basis F-066,
corpus sha, aliasing note).

## Backend

### 1. `src/charts/crt_overlay.py` — extract one function (refactor, no behaviour change)

`resolve_states()` today always runs the spine. Add:

```python
def track_from_events(events_path: Path, base_ts: Sequence[datetime]) -> CRTTrack
```

holding the existing `_parse_state_events` → `_bar_positions` → `_forward_fill` →
`index_shift_diagnostic` body, and make `resolve_states()` call it after
`run_spine_for_states`. The dashboard reads a *run's* events, so it must never trigger a
spine re-run.

### 2. `src/charts/chart_api.py` (new, pure) — `chart_payload(...)`

```python
chart_payload(instrument, run_id, timeframe="M15", limit=1500,
              start=None, end=None, include=("crt","trades","events","gaps"))
```

Steps, each failing **closed and visibly** (the F-079/F-083/F-085 silent-gap class):

1. Resolve the run with `dashboard_api._resolve_run`. Unknown/foreign run → `{"ok": false,
   "error": ...}`.
2. Corpus binding: `data/mt5/<INSTR>_M15.csv`. The run summary does **not** record its
   corpus path, so binding is by convention and then *verified* — if any event timestamp is
   absent from the base series, `_bar_positions` already raises and the track becomes
   `UNAVAILABLE:corpus_mismatch`. Bars still render; colour does not.
3. Integrity: `validate_dataset(path, instrument=..., write_report=False,
   raise_on_fail=False)` → `{decision, missing_candles, gaps[]}`. `raise_on_fail=False` so a
   REJECT is *reported*, not thrown. Cache by `(path, st_mtime, st_size)` — it is an O(n)
   pass over 47k rows.
4. Bars: `load_base_candles` (module-level LRU keyed on path+mtime, one corpus resident) →
   `to_timeframe(base, timeframe)`.
5. Engine track: `track_from_events(run.events_path, base_ts)` → `downsample_states(...)`.
6. Resolver track: read the cache (below) if present, else
   `{"source": "UNAVAILABLE:not_cached"}`. Never computed in-request.
7. Trades: rows of `<INSTR>_trades.csv` overlapping the window → `direction, opened_at,
   closed_at, entry_fill, sl, tp1, tp2, exit_fill, exit_reason, pnl_rr_net, trade_id`.
8. Event pins: `SWEEP`/`DISPLACEMENT`/`RETEST`/`EXECUTION`/`RESET` rows from the same
   `events.jsonl`, windowed, with `direction`, `price`, `reason`.
9. Legend/provenance: `build_legend` + `build_config_pin` (carries `crt_aliasing`,
   `session_timestamp_basis`, `active_version`, `corpus_sha256`).

Windowing: default the **last** `limit` bars of the timeframe; `start`/`end` (ISO) override;
`limit` clamped to 5000 — same shape as the existing `per_page` clamps.

### 3. Route — `src/control_plane/server.py`

Add `if path == "/api/chart_series":` beside `/api/executive` (~line 1726), reading
`instrument`, `run_id`, `timeframe`, `limit`, `from`, `to` from `query` with the same
defensive `int()` pattern used by `/api/trades`.

### 4. Resolver track precompute — `src/charts/resolver_overlay.py` + CLI

Library builds the per-bar resolver states over a corpus by reusing the existing chain from
`scripts/research/run_crt_state_on_mt5_xauusd.py`: `FeaturePipeline` →
`features.resolver_supply.build_resolver_supply` → `crt_state_resolver.build_htf_id_timeline`
→ `CRTStateResolver.resolve` per bar. Writes

```
results/charts/_resolver_cache/<INSTR>__<corpus_sha8>__<variant>/{states.csv, meta.json}
```

`states.csv` = `timestamp,state`; `meta.json` records corpus sha256, row count, resolver
`variant_id`, `enabled_links`, `waived_when_features`, ontology/schema hashes. The endpoint
serves the cache only when `meta.corpus_sha256` matches the corpus it just loaded —
otherwise `UNAVAILABLE:stale_cache`.

Known trap (recorded in memory): `FeaturePipeline.run()` drops warmup rows and resets the
index — align by **timestamp**, pad the head with `UNAVAILABLE`, never by position.

Thin CLI wrapper `scripts/analysis/build_resolver_overlay.py` (§3.3 — argparse + call +
print only). It is a new runnable script, so SITS registration is required the same turn
(§3.1b): `script_census.py --write-stubs` → `seed_script_registry.py` →
`generate_script_matrix.py`.

Label discipline: the engine track and the resolver track are **different constructions**,
not two measurements of one thing (F-069: 88.16% agreement, EXPANSION recall 10.77%,
structurally config-unreachable). The UI shows them as two ribbons with an agreement figure
and never merges or reconciles them.

## Frontend

### 5. Vendor lightweight-charts

Drop the standalone UMD build into `ui_kits/crt_dashboard/vendor/` (react/babel are already
vendored there; the dashboard loads no CDN JS). Add `<script src="vendor/lightweight-charts.standalone.production.js">`
in `index.html` **before** the `text/babel` files. Add `vendor/README.md` recording exact
version + sha256 + source URL. One network fetch at install time; offline afterwards.

Verify the API shape against the version actually vendored before writing the component —
v5 replaced `chart.addCandlestickSeries(...)` with `chart.addSeries(CandlestickSeries, ...)`.
Pin one version and code to it.

### 6. `ui_kits/crt_dashboard/page4_trade_chart.jsx` (new) → `window.TradeChartPanel`

Props: `selectedInstrument`, `selectedRun`, `runs`. Self-fetching (the pattern
`page3_models.jsx` already uses for `explainModel`) so a 47k-bar corpus is never pulled on
the app-wide instrument reload in `app.jsx`.

- `React.useEffect` on `[selectedInstrument, selectedRun, timeframe]` → `fetchChartSeries`,
  with an `ignore` flag to drop stale responses.
- Chart: `createChart(ref, {...})` themed from `styles.css` colours; candlestick series;
  per-bar `color`/`borderColor`/`wickColor` from the CRT state when the ribbon toggle is on;
  `setMarkers` for trade entry/exit + event pins; `createPriceLine` for SL/TP1/TP2 of the
  hovered/selected trade.
- Ribbons and gap bands are **not** native primitives: render them on absolutely-positioned
  canvases overlaying the chart, mapping bar time → x with
  `chart.timeScale().timeToCoordinate()` and redrawing on
  `subscribeVisibleLogicalRangeChange` + `ResizeObserver`. Dispose the chart and unsubscribe
  in the effect cleanup.
- States: empty run → "select a run" placeholder; `ok:false` → the error string; integrity
  `REJECT` → red badge and bars still drawn (reporting, not hiding).

### 7. Wiring — surgical edits only

- `page4_trades.jsx`: append `"Trade Chart"` to `TABS`, add `TradeChart:"Trade Chart"` to
  `SUB_TO_TAB`, add one render block `{activeTab === "Trade Chart" && <TradeChartPanel .../>}`.
  The page needs `selectedRun`/`runs` — both already exist in `runtimeProps`; add them to the
  `TradesPage` signature.
- `shared.jsx`: add `{ id:"TradeChart", label:"Trade Chart", icon:"📈" }` after the
  `SessionAnalysis` sidebar sub-item (line ~221).
- `apiClient.js`: `fetchChartSeries(instrument, run_id, timeframe, limit, from, to)`.
- `index.html`: two `<script>` lines (vendor lib + the new jsx).

## Tests

- `tests/charts/test_track_from_events.py` — the refactor is behaviour-preserving:
  `track_from_events` on the cached run under
  `results/charts/_crt_cache/XAUUSD__v2_htfcrt_2026_08/` gives states identical to
  `resolve_states` for the same corpus.
- `tests/control_plane/test_chart_series_payload.py` — unknown run → `ok:false`; `limit`
  clamped and window is the *tail*; timeframe aggregation changes bar count but keeps
  `len(bars) == len(crt_state)`; a corpus whose timestamps don't contain the run's events →
  `crt_state_source` starts with `UNAVAILABLE`, bars still returned; missing resolver cache →
  `UNAVAILABLE:not_cached`; integrity `decision` present in the payload.
- No governed-path behaviour changes, so the gate is the standard floor, not a new one.

## Verification

```bash
venv/Scripts/python.exe -c "import sys; print(sys.prefix)"
```

```bash
venv/Scripts/python.exe -m pytest tests/charts tests/control_plane -q
```

```bash
venv/Scripts/python.exe scripts/analysis/build_resolver_overlay.py --instrument XAUUSD
```

```bash
venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'src');from charts.chart_api import chart_payload;import json;d=chart_payload('XAUUSD','run_20260812_113506_XAUUSD','H4',limit=200);print(json.dumps({k:(len(v) if isinstance(v,list) else v) for k,v in d.items() if k!='legend'},default=str)[:900])"
```

Then start the control plane, open `http://localhost:8787/ui_kits/crt_dashboard/index.html`,
select XAUUSD + `run_20260812_113506_XAUUSD`, open Trades → Trade Chart, and check with the
in-app browser: candles render, pan/zoom/crosshair work, the ribbon changes colour at the
event timestamps in `XAUUSD_events.jsonl`, the single trade's entry/exit markers land on
`2024-11-12T15:30`/`15:45`, weekend gaps are shaded, and switching M15→H4→D1 keeps ribbon and
bars aligned (D1 should surface the `crt_aliasing` warning).

```bash
venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

Capture the pre-existing failure count on this branch **before** editing, so a known red is
not read as a regression.

## Governance close-out

SESSION LOG entry in `assistant_project.md` (§6). SITS registration for the new script. No
finding flips; no `params` edit, so no rehash. If any doc cites a moved symbol, sync the
citation the same turn (§6.3).
