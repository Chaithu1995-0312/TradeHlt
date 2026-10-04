# UI Archaeology Report

> Read-only investigation of the complete human-facing UI layer.
> **Date:** 2026-06-12
> **Scope:** All UI artifacts discovered in the repository — no assumptions, no redesign.

---

## Executive Summary

The repository contains **4 distinct UI systems** plus **1 empty UI package** and **1 archived legacy file**:

| # | System | Type | Location | Status |
|---|--------|------|----------|--------|
| 1 | **CRT Web Control Plane** (embedded) | Inline HTML+CSS+JS in server.py | `src/control_plane/server.py` lines 136–953 | Active |
| 2 | **CRT Trading Dashboard** (embedded) | Inline HTML+CSS+JS in server.py | `src/control_plane/server.py` lines 956–1546 | Active |
| 3 | **CRT Web Control Plane** (React kit) | React 18 SPA via Babel + JSX | `ui_kits/control_plane/` (16 files) | Active |
| 4 | **CRT Operations Dashboard** (React kit) | React 18 SPA via Babel + JSX | `ui_kits/crt_dashboard/` (22 files) | Active |
| 5 | **src/ui/** | Empty Python package | `src/ui/__init__.py` | Dead |
| 6 | **dashboard_ARCHIVED** | Legacy Python dashboard | `archive/ui_legacy/dashboard_ARCHIVED_2026_05_02.py` | Archived |

---

## 1. CRT Web Control Plane (embedded in server.py)

- **File:** `src/control_plane/server.py` lines 136–953
- **Method:** `ControlPlaneAPI.ui_html()` returns a complete HTML document as a Python string
- **Framework:** None (vanilla HTML + CSS + JavaScript)
- **Styles:** Dark theme with CSS custom properties (`--bg:#0f1724`, `--panel:#122033`, `--accent:#0ea5a3`)
- **External deps:** None (no CDN scripts)
- **Port:** 8787 (default)

### Pages/Views (3):
1. **Run Launcher & History** (default view) — Command launcher with form builder, run history table
2. **Monitoring Dashboard** — Toggleable view showing latest per-command monitor fields
3. **Run Inspector** — Selected run detail: metadata, stdout/stderr, artifacts, monitors

### Interactive Features:
- Command category/command selectors → dynamic form generation from `args_schema`
- File pickers populated from server glob endpoints
- Run/stop buttons with real-time polling (2s for monitors, 2s for runs)
- Search/filter run history
- Guided tour system (13 steps across 5 workflow stages)
- Playbook/workflow checklist with mark-complete toggles
- Report modal with Excel download + Groq LLM analysis buttons

### API Endpoints consumed (all in server.py):
- `/commands` — command catalog
- `/runs` — list runs
- `/runs/{id}` — run detail
- `/runs/{id}/logs` — stdout/stderr
- `/runs/{id}/artifacts` — artifact list
- `/runs/{id}/monitors` — live monitor fields
- `/monitors/dashboard` — aggregated dashboard
- `/monitors/history/{id}` — monitor history
- `/files?glob=...` — file picker options
- `/runs/{id}/report/excel` — download XLSX
- `/runs/{id}/report/llm` — Groq analysis

### Tour System (embedded JS):
- **`TOUR_STEPS` array** (13 steps) defined at line 330 of server.py
- Steps: Pipeline Overview → Prepare Data → Build Dataset → Tune Parameters → Validate Config → Promote Config → Governance → Capture Baseline → Backtest v2 → BitNet Gate → Unified Replay → Go Live → Trading Dashboard
- LocalStorage persistence for tour progress (`tutorial_progress`, `tutorial_seen`, `tutorial_dismissed_version`)

---

## 2. CRT Trading Dashboard (embedded in server.py)

- **File:** `src/control_plane/server.py` lines 956–1546
- **Method:** `ControlPlaneAPI.trading_dashboard_html()` returns a complete HTML document
- **Framework:** Vanilla HTML + CSS + JavaScript + Chart.js (CDN)
- **External deps:** `https://cdn.jsdelivr.net/npm/chart.js`
- **Route:** `/dashboard`

### Pages/Tabs (5):
1. **Status** — Active config, model, kill switch, trades 24h, 4 model versions (Gaussian/Zone Gate/RR Miner/TradeNet)
2. **Models** — Gaussian model registry table with promote buttons
3. **Opportunities** — Win rate by session chart (Chart.js bar), paginated opportunity records
4. **Trades** — Equity curve chart (Chart.js line), paginated trade journal
5. **Backtests** — Phase-5 calibration history table

### API Endpoints consumed:
- `/api/status` — runtime status
- `/api/model_versions` — 4-model version info
- `/api/models` — Gaussian registry
- `/api/instruments` — available instruments
- `/api/opportunities` — paginated opportunities
- `/api/opportunity_stats` — win rate aggregations
- `/api/trades` — paginated trades
- `/api/equity_curve` — cumulative PnL points
- `/api/backtest_history` — p5 calibration history
- `/api/promote_model` — POST: set active model

---

## 3. CRT Web Control Plane (React UI Kit)

- **Location:** `ui_kits/control_plane/`
- **Entry:** `index.html` → loads React 18 from unpkg CDN + Babel standalone + Mermaid
- **Framework:** React 18 (UMD via CDN) + Babel standalone for JSX transpilation
- **External deps:** React 18.3.1, React DOM 18.3.1, Babel 7.29.0, Mermaid 10
- **Routing:** In-app state switching (no URL router)
- **State management:** React useState/useEffect, local mock API subscription

### Component Inventory (16 files):

| File | Component(s) | Purpose |
|------|--------------|---------|
| `App.jsx` | `App` | Root — 4 views: runs, dashboard, workflow, agent |
| `Header.jsx` | `Header` | Top bar with nav buttons |
| `PlaybookPanel.jsx` | `PlaybookPanel` | Workflow checklist with stage groups |
| `LauncherPanel.jsx` | `LauncherPanel` | Command selector, form builder, run history |
| `InspectorPanel.jsx` | `InspectorPanel` | Run detail: metadata, logs, artifacts, monitors |
| `DashboardView.jsx` | `DashboardView` | Monitoring dashboard grid |
| `WorkflowPanel.jsx` | `WorkflowPanel` | Mermaid-based workflow diagram |
| `AgentPanel.jsx` | `AgentPanel` | Agent findings/audit logs |
| `Tour.jsx` | `Tour` | Guided tour system |
| `Primitives.jsx` | Shared UI primitives | Form inputs, buttons, tables, modals, status badges |
| `ComboBox.jsx` | `ComboBox` | Autocomplete/searchable dropdown |
| `FileUploader.jsx` | `FileUploader` | File selection widget |
| `Sparkline.jsx` | `Sparkline` | Inline sparkline chart |
| `format.js` | Format utilities | Date/number formatting |
| `realApi.js` | API client | Real HTTP fetch wrapper for backend endpoints |
| `mockApi.js` | Mock API | Fake data for development/testing |

### Views (4):
1. **runs** — Playbook + Launcher + Inspector (3-panel grid)
2. **dashboard** — DashboardView (monitoring grid)
3. **workflow** — WorkflowPanel (Mermaid diagram)
4. **agent** — AgentPanel (findings/audit logs)

### API Endpoints consumed (via realApi.js):
Same as embedded Control Plane (see section 1)

---

## 4. CRT Operations Dashboard (React UI Kit)

- **Location:** `ui_kits/crt_dashboard/`
- **Entry:** `index.html` → loads React 18 + Babel standalone + custom CSS
- **Framework:** React 18 (UMD via CDN) + Babel standalone + custom `styles.css`
- **External deps:** React 18, React DOM 18, Babel, Google Fonts (Inter)
- **Routing:** In-app tab switching (`activePage` state in `CrtDashboard`)
- **State management:** React useState in `CrtDashboard` (centralized store), 30s auto-refresh

### Component Inventory (22 files):
- `app.jsx` — Root `CrtDashboard` component, centralized state, 9-page router
- `data.js` — Static scaffold globals (`window.MODELS`, `window.ALERTS`, `window.SESSION_EQUITY`, etc.)
- `realData.js` — Legacy mount trigger (being phased out — Phase 6)
- `apiClient.js` — Centralized fetch surface (`window.ApiClient`)
- `charts.jsx` — Mini chart components (LineChart, VerticalBars, Heatmap, DonutChart, Scatter)
- `shared.jsx` — Shared components (TopBar, SidebarNew, KPIStrip, Modal, etc.)
- `styles.css` — Complete dark-theme stylesheet
- `page0_executive.jsx` — Executive Overview (default landing)
- `page1_runtime.jsx` — Runtime Dashboard
- `page2_research.jsx` — Research
- `page3_models.jsx` — Models
- `page4_trades.jsx` — Trades
- `page5_backtests.jsx` — Backtests
- `page6_system.jsx` — System
- `page7_intelligence.jsx` — Intelligence
- `page8_replay.jsx` — Replay Lab

### Pages (9):
1. **Executive** — KPIs (PnL, Win Rate, Profit Factor, Avg RR, Expectancy), PnL chart, Session Equity charts, Win Rate by Session, Opportunity Density heatmap, Alerts, Status strip
2. **Runtime** — Live runtime metrics
3. **Research** — Research analytics
4. **Models** — 4-model registry tables (Gaussian, Zone Gate, RR, TradeNet) with promote actions
5. **Trades** — Trade journal, equity curve
6. **Backtests** — Calibration history
7. **System** — System health
8. **Intelligence** — LLM-driven intelligence
9. **Replay Lab** — Replay analysis

### API Endpoints consumed (via apiClient.js):
Same set as the embedded Trading Dashboard + `/api/zone_gate_models`, `/api/rr_models`, `/api/tradenet_models`, `/api/scan_jobs`, `/api/opportunity_analytics`

---

## 5. src/ui/ — Empty Python Package

- **Location:** `src/ui/__init__.py`
- **Content:** Only `__init__.py` — no modules, no classes, no components
- **Status:** Dead — never populated

---

## 6. Archived Legacy Dashboard

- **Location:** `archive/ui_legacy/dashboard_ARCHIVED_2026_05_02.py`
- **Status:** Archived (date-stamped 2026-05-02)
- **Content:** Presumed Python-based dashboard (not analyzed — archived)

---

## 7. Server Routing Architecture

Defined in `src/control_plane/server.py` class `Handler` (inner class at line 1566):

### Root route:
- `GET /` → **redirects** to `/ui_kits/control_plane/` (line 1782–1788)

### Control Plane API routes:
- `GET /commands` → command catalog JSON
- `GET /runs?q=...` → run list JSON
- `GET /runs/{id}` → run detail JSON
- `GET /runs/{id}/logs` → stdout/stderr JSON
- `GET /runs/{id}/artifacts` → artifacts JSON
- `GET /runs/{id}/monitors` → live monitor fields JSON
- `GET /runs/{id}/report/excel` → XLSX download
- `POST /runs/{id}/report/llm` → Groq analysis JSON
- `POST /runs/{id}/context/report` → Claude analysis JSON
- `GET /monitors/dashboard` → aggregated dashboard JSON
- `GET /monitors/history/{id}` → monitor history JSON
- `GET /files?glob=...` → file glob results JSON
- `POST /commands/{id}/runs` → create run JSON
- `POST /runs/{id}/stop` → stop run JSON
- `POST /api/agent/synthesize` → agent findings synthesis JSON

### Trading Dashboard API routes:
- `GET /dashboard` → HTML page (trading dashboard)
- `GET /api/status` → runtime status JSON
- `GET /api/model_versions` → 4-model versions JSON
- `GET /api/models` → Gaussian registry JSON
- `GET /api/zone_gate_models` → Zone Gate registry JSON
- `GET /api/rr_models` → RR registry JSON
- `GET /api/tradenet_models` → TradeNet registry JSON
- `GET /api/instruments` → instrument list JSON
- `GET /api/opportunities` → paginated opportunities JSON
- `GET /api/opportunity_stats` → win rate stats JSON
- `GET /api/opportunity_analytics` → scatter + time-series JSON
- `GET /api/scan_jobs` → scanner run list JSON
- `GET /api/trades` → paginated trades JSON
- `GET /api/equity_curve` → equity curve JSON
- `GET /api/backtest_history` → p5 calibration history JSON
- `POST /api/promote_model` → set active model JSON
- `POST /api/promote_zone_gate` → promote zone gate JSON
- `POST /api/promote_rr` → promote RR model JSON
- `POST /api/promote_tradenet` → promote TradeNet JSON
- `POST /api/explain_model` → Groq model explanation JSON

### Agent panel routes:
- `GET /api/agent/findings` → JSONL tail of agent_findings.jsonl
- `GET /api/agent/audit` → JSONL tail of agent_audit.jsonl
- `GET /api/agent/llm_requests` → JSONL tail of agent_llm_requests.jsonl

### Static file serving:
- `GET /ui_kits/*` → static file serving for React UI kits (lines 1751–1780)
  - MIME map includes: .html, .js, .jsx, .css, .json, .png, .jpg, .svg, .md
  - Directory → serves index.html
  - `.js`/`.jsx` files get `Cache-Control: no-store`

### Catalog endpoint:
- `GET /catalog` → JSON catalog of data files, production configs, instruments

---

## 8. Backend Data Sources

Sourced by `dashboard_api.py` (`TradingDashboardAPI`) — stateless, read-only, file-based:

### Files read:
- `configs/production/ACTIVE_VERSION` — active config version label
- `models/gaussian_registry.json` — Gaussian model registry
- `models/zone_gate_registry.json` — Zone Gate registry
- `models/rr_registry.json` — RR model registry
- `models/tradenet_registry.json` — TradeNet registry
- `models/zone_registry.json` — fallback zone data
- `models/rr_dataset.json` — fallback RR data
- `models/rr_model.json` — fallback RR model
- `logs/kill_switch_state.json` — kill switch state
- `results/run_*/{instrument}_trades.csv` — trade journals
- `logs/{instrument}/{run_dir}/opportunities.jsonl` — opportunity logs
- `logs/opportunities_{instrument}.jsonl` — legacy flat opportunity logs
- `results/p5_calibration_*.json` — backtest calibration history
- `configs/production/{version}.json` — production configs (for instruments list)

---

## 9. Key Architectural Observations

1. **Dual UI delivery**: The server serves both inline embedded HTML (legacy compatibility) and serves React UI kits from disk at `/ui_kits/`. The root route `/` redirects to `/ui_kits/control_plane/` — the React version is the primary UI.

2. **Two incomplete React apps**: `ui_kits/control_plane/` and `ui_kits/crt_dashboard/` are separate React SPAs with overlapping but not identical functionality. Neither is a complete replacement for the other.

3. **Mock API**: `ui_kits/control_plane/mockApi.js` provides fake data for development — the app can run without a backend.

4. **No build step**: Both React apps use Babel standalone for in-browser JSX transpilation. There is no build/compile step, no Vite, no Webpack, no npm bundling.

5. **Shared backend, two frontends**: Both React apps and both embedded UIs ultimately call the same backend routes defined in `server.py`, though the React kits also call additional endpoints.

6. **src/ui/ is empty**: The `src/ui/` package exists but has never been populated — it appears to be a placeholder for a future unified UI.

7. **30-second polling**: The CRT Operations Dashboard refreshes status/trades/equity every 30 seconds. The Control Plane polls runs every 2 seconds and dashboard every 2 seconds.