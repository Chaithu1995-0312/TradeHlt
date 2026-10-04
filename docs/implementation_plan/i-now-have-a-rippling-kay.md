# Finish run-scoped Executive Overview (ui_kits → dashboard_api)

## Context

A prior session (DeepSeek-driven, ran out of tokens mid-edit) implemented a run-scoped
Executive Overview: an instrument + **run** pair selects a single `results/run_<ts>_<INSTR>/`
backtest run, and every Executive KPI/chart is computed from that one run instead of the
previous mix of hard-coded literals, latest-run data, and `window.*` mocks from `data.js`.

Two problems motivated it:
1. **XAUUSD never appeared in the instrument dropdown** — `instruments_payload()` unioned only
   the active config's `data_ingestion.pairs` and `inout.scanner.allowed_symbols`; the active
   config (`v2_htfcrt_2026_08`) lists neither XAUUSD, despite 11 XAUUSD backtest runs on disk.
2. **No run selection existed** — every endpoint silently read "the latest" run.

The work stopped mid-edit. This plan finishes it.

### Verified state (measured this session, not assumed)

**Backend — complete and working.** Smoke-tested against real disk data:
- `instruments_payload()` now returns 17 instruments, **XAUUSD included**.
- `runs_payload("XAUUSD")` returns **11 runs**, newest first, each with a metrics preview.
- `executive_payload("XAUUSD", "run_20260812_113506_XAUUSD")` returns `ok:true` with real
  KPIs, cumulative PnL series, session buckets, and a `monthly_pnl`-derived density grid.
- `RunContext` / `_resolve_run` / `_iter_run_dirs` / `_instruments_from_disk` all present and
  correct; `_session_bucket_ui` correctly maps the ordinal-float form (`"3.0"` → `overlap`)
  that trade CSVs actually carry.
- `/api/runs` and `/api/executive` are wired in `server.py`; `run_id` added to `/api/trades`
  and `/api/equity_curve`.
- The `from utils.run_linkage import resolve_artifacts` import **does** resolve under the
  server's `sys.path` (the editable install exposes `utils` as top-level) — verified, not a defect.

**UI — two hard defects remain.** `index.html` transpiles JSX in-browser via Babel, so an
undefined symbol is a render-time `ReferenceError`:
- `runLabel(...)` is **called** at `page0_executive.jsx:36` and `:168` but **never defined
  anywhere** → the entire Executive page crashes on render. Hard blocker.
- `SessionEquityChart({ height = 120 })` (`page0_executive.jsx:184`) **ignores** the `se` prop
  passed at `:125` and still reads `window.SESSION_EQUITY` → the "Equity by Session" chart
  silently renders `data.js` mock data instead of the selected run's.

Everything else on the UI side landed correctly: run dropdown in `shared.jsx`, Executive-only
tab gating in `app.jsx` + `shared.jsx`, the gating placeholder, KPI wiring, `Heatmap` row shape
(`{year, cells[12]}`) matches the backend exactly, and the alerts card shows "yet to integrate".

**Baseline (pre-existing, unrelated — do not fix here).** `construction_protocol.py check`
is **RED** with exactly 2 failures, both feature-math/geometry census freshness:
`tests/test_feature_math_lint.py::test_universe_reconciliation_with_census` and
`tests/test_geometry_census.py::test_adjudication_closed_against_fresh_census`
(2 failed / 135 passed, 5:12). Neither touches `src/control_plane/` or `ui_kits/`. Per
CLAUDE.md §1.5 the correct move on a pre-existing red is to **report** it, not fix it.

### Confirmed scope decisions
- **Executive only.** `/api/status` and `/api/opportunity_stats` stay un-scoped — verified
  `status_payload` reads `ACTIVE_VERSION` + `models/<INSTR>/` + kill switch (no run dimension
  exists) and `opportunity_stats_payload` reads the `logs/<INSTR>/` opportunity stream (a
  different artifact family, and per F-022 a detection stream, not a trade ledger).
- **Enrich the run dropdown label** using the metrics `/api/runs` already returns.

---

## Changes

### 1. `ui_kits/crt_dashboard/page0_executive.jsx` — fix the two blocking defects

**(a) Define `runLabel`.** Add a module-scope helper above `ExecutivePage` that turns a
`run_id` (`run_20260812_113506_XAUUSD`) into a readable timestamp (`2026-08-12 11:35`), and
falls back to the raw id for any name that does not parse. Both existing call sites
(`:36`, `:168`) then resolve.

**(b) Make `SessionEquityChart` consume its prop.** Change the signature to
`function SessionEquityChart({ se, height = 120 })` and replace the body's first line
(`const se = window.SESSION_EQUITY || …`) with a prop-based default
(`se || { asian:[], london:[], ny:[], overlap:[] }`). This is the last `window.*` mock read on
this page. Leave `data.js` in place — `page4_trades.jsx` and `page5_backtests.jsx` still use
`SESSION_PNL` / `MONTHLY_RETURNS` and are out of scope.

**(c) Guard `profit_factor` display.** The backend returns `0.0` when a run has no winning
trades (verified: the latest XAUUSD run is a single loser). Render `0.00` as-is but confirm
`toFixed` is never called on `null` — the existing `!= null` guards already cover this; verify
rather than change.

### 2. `ui_kits/crt_dashboard/shared.jsx` — enrich the run `<option>` label

The `<option>` at the run `<select>` currently prints `r.run_id` verbatim. Build a label from
fields `runs_payload` already returns: parsed timestamp + `metrics.approved_trades` +
`metrics.total_pnl_rr_net`, e.g. `2026-08-12 11:35 · 1 trade · -0.04R`. Keep `value={r.run_id}`
unchanged so the id contract with the backend is untouched, and fall back to the bare `run_id`
when `metrics` is `null` (runs with no summary JSON).

### 3. `src/utils/run_linkage.py` — remove a wasted full-tree traversal

`_parquet_layers()` calls `rglob("*.parquet")` on **every** subdirectory of `logs/` and costs
**1.12s of the 1.76s** total `/api/executive` latency (measured). Its only consumer then checks
`if result["run_id"] in layer.name` — a match that cannot realistically fire, since run ids are
`run_<ts>_<INSTR>` and the layer dirs are names like `bar_structure` / `dual_construction_*`.

Fix: invert the order — iterate `LOGS_DIR.iterdir()`, test the cheap **name** predicate first,
and only confirm parquet presence (via a bounded `glob`, not a recursive `rglob`) for
directories that actually match. Behaviour is unchanged; the traversal cost disappears.

### 4. `src/control_plane/dashboard_api.py` — remove dead code

`_find_latest_run_summary` (`:101`) was added during the unfinished work and has **zero call
sites** (verified by grep). Delete it. Keep `_find_latest_trades_csv` — still used at `:253`.

### 5. `tests/test_dashboard_run_scope.py` — new test floor

No existing test covers `dashboard_api` (`tests/test_control_plane_api.py` is 102 lines and
references none of these payloads). Add a focused floor, following the assertion/invariant
style in `docs/reference/testing.md`:
- `instruments_payload()` includes an instrument that has runs on disk but is absent from the
  active config's `pairs`/`allowed_symbols` (the XAUUSD regression).
- `_resolve_run(inst, None)` returns the newest run; `_resolve_run(inst, "<real id>")` returns
  that exact run; a **foreign** run id returns `None` (the fail-closed cross-instrument guard).
- `executive_payload` returns `ok:false` for an unknown `run_id`, and for a real run the KPI
  arithmetic is self-consistent (`expectancy_rr * n_trades ≈ total_pnl_rr_net`).
- `_session_bucket_ui` maps the ordinal-float form (`"3.0"` → `"overlap"`), the name form, and
  returns `None` for empty/unknown — this is the mapping real trade CSVs depend on.

Tests must skip cleanly when no run fixture exists on disk, so the floor is portable to a fresh
clone (`results/` is not tracked).

### 6. Governance

- No class in `docs/governance/change_contracts.json` covers a read-only dashboard/UI change
  (verified: the 18 classes are all feature/formula/model/config/runtime/script/identity
  surfaces). This change touches no feature identity, formula, model, production config,
  runtime decision path, or script registry. Record that classification result explicitly
  rather than forcing a false class.
- `hooks/commit-msg` requires a **same-day `SESSION LOG ENTRY` in `assistant_project.md`** for
  any commit touching `src/**` — mandatory here regardless, per CLAUDE.md §6.
- No `params`-block config edit ⇒ no `_compute_hash.py` rehash needed.

---

## Verification

1. **Backend unit smoke** (must pass before touching the UI):
   ```bash
   venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'src'); from control_plane.dashboard_api import TradingDashboardAPI as A; a=A(); print('XAUUSD' in a.instruments_payload()['instruments'], a.runs_payload('XAUUSD')['total'], a.executive_payload('XAUUSD')['ok'])"
   ```
   Expect `True 11 True`.
2. **New floor:** `venv/Scripts/python.exe -m pytest tests/test_dashboard_run_scope.py -v`
3. **Perf regression:** time `/api/executive` before/after the `run_linkage` fix — expect the
   ~1.1s `_parquet_layers` cost to vanish while `linkage.logs.dir` still resolves to
   `logs/XAUUSD/xauusd_phase1_20260723` (`method: "named"`), i.e. identical output, less work.
4. **End-to-end in the browser** — start the control plane, open `localhost:8787`, then:
   - Executive tab is **disabled** (top bar + sidebar) until a run is chosen.
   - **XAUUSD** is present in the instrument dropdown; selecting it populates 11 enriched run
     labels.
   - Selecting a run enables Executive; KPIs, PnL-over-time, session charts, and the density
     heatmap all render with no console `ReferenceError`.
   - Switching instrument clears the run and re-disables the tab.
   - **Expect sparse charts for XAUUSD and do not treat that as a bug:** measured, the latest
     run has exactly **1 trade**, and all 10 XAUUSD trades across all 11 runs carry
     `session = 3.0` (OVERLAP) — so the Asian/London/NY series are legitimately empty. Use a
     crypto instrument with a denser run to exercise the multi-series path.
5. **Governance floor:** re-run `venv/Scripts/python.exe scripts/governance/construction_protocol.py check`
   (~5 min) and confirm it still shows **exactly the same 2 pre-existing failures** —
   `test_universe_reconciliation_with_census` and `test_adjudication_closed_against_fresh_census` —
   and no new ones. Report that baseline; do not attempt to fix it here.
6. **Session log:** append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (§6/§7.4).
