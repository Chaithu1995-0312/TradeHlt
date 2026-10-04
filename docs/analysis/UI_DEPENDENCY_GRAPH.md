# UI Dependency Graph

> Canonical architecture of the existing UI layer — no redesign, only existing relationships.
> **Unknowns remain UNKNOWN.**

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     USER (Browser)                             │
│                                                                │
│  ┌─────────────────────┐  ┌───────────────────────────────┐    │
│  │  /ui_kits/          │  │  /ui_kits/crt_dashboard/     │    │
│  │  control_plane/     │  │  (React 18 Dashboard)         │    │
│  │  (React 18 SPA)     │  │                               │    │
│  │                     │  │  Pages: 9 (Executive → Replay)│    │
│  │  Views: 4           │  │  State: CrtDashboard (central)│    │
│  │  State: App (central)│  │  Poll: 30s                  │    │
│  │  Poll: 2s           │  │                               │    │
│  └────────┬────────────┘  └────────┬──────────────────────┘    │
│           │                        │                           │
│  ┌────────┴────────────┐  ┌────────┴──────────────────────┐    │
│  │  GET / (redirect)   │  │  GET /dashboard               │    │
│  │  Embedded CP HTML   │  │  Embedded Trading Dashboard   │    │
│  │  (vanilla JS)       │  │  (vanilla JS + Chart.js)      │    │
│  └────────┬────────────┘  └────────┬──────────────────────┘    │
│           │                        │                           │
└───────────┼────────────────────────┼───────────────────────────┘
            │                        │
            ▼                        ▼
┌────────────────────────────────────────────────────────────────┐
│              ControlPlaneServer (127.0.0.1:8787)               │
│              src/control_plane/server.py                       │
│                                                                │
│  ┌─────────────────────────────────────────────────────┐       │
│  │             do_GET / do_POST Router                 │       │
│  │                                                     │       │
│  │  / → redirect to /ui_kits/control_plane/             │       │
│  │  /dashboard → trading_dashboard_html()              │       │
│  │  /ui_kits/* → static file serve                     │       │
│  │  /commands, /runs/* → ControlPlaneAPI               │       │
│  │  /api/status, /api/models/* → TradingDashboardAPI    │       │
│  │  /api/agent/* → inline JSONL tail                   │       │
│  └───────────┬──────────────────────────────┬──────────┘       │
│              │                              │                  │
└──────────────┼──────────────────────────────┼──────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    ControlPlaneAPI           │  │    TradingDashboardAPI        │
│    src/control_plane/        │  │    src/control_plane/         │
│    server.py (line 54)       │  │    dashboard_api.py (line 82) │
│                              │  │                              │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │Command catalog + runs  │  │  │  │Status, models,         │  │
│  │Monitor snapshots       │  │  │  │opportunities, trades,  │  │
│  │File globbing           │  │  │  │equity curve, backtests │  │
│  └───────────┬────────────┘  │  │  └───────────┬────────────┘  │
└──────────────┼───────────────┘  └──────────────┼───────────────┘
               │                                 │
               ▼                                 ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    JobManager                │  │    RunReportAPI              │
│    src/control_plane/        │  │    src/control_plane/        │
│    jobs.py (line 79)         │  │    report_api.py (line 52)   │
│                              │  │                              │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │Subprocess queue        │  │  │  │Excel XLSX generation   │  │
│  │Run execution + logging │  │  │  │Groq LLM analysis       │  │
│  │Monitor extraction      │  │  │  └────────────────────────┘  │
│  └────────────────────────┘  │  │                              │
└──────────────────────────────┘  │  ┌────────────────────────┐  │
                                  │  │ContextReportAPI        │  │
                                  │  │src/control_plane/      │  │
                                  │  │context_report.py (154)│  │
                                  │  │Claude analysis          │  │
                                  │  └────────────────────────┘  │
                                  └──────────────────────────────┘

```

---

## 2. Data Flow: User → UI → API → Backend

```
User
  │
  ├──►  Browser loads /ui_kits/control_plane/index.html
  │      │
  │      ├──► React App mounts
  │      │      │
  │      │      ├──► fetches GET /commands          ← ControlPlaneAPI.commands_payload()
  │      │      │                                      │
  │      │      │                                      └── core_command_specs() [registry.py]
  │      │      │
  │      │      ├──► fetches GET /runs              ← ControlPlaneAPI.runs_payload()
  │      │      │                                      │
  │      │      │                                      └── JobManager.list_runs()
  │      │      │                                             │
  │      │      │                                             └── reads results/{inst}/*.json
  │      │      │
  │      │      ├──► user clicks Run Command
  │      │      │      │
  │      │      │      └──► POST /commands/{id}/runs  ← ControlPlaneAPI.create_run_payload()
  │      │      │                                         │
  │      │      │                                         └── JobManager.create_run()
  │      │      │                                                │
  │      │      │                                                ├── writes log files
  │      │      │                                                ├── spawns subprocess
  │      │      │                                                └── persists state JSON
  │      │      │
  │      │      └──► polls GET /runs/{id}/monitors    ← JobManager.live_monitors()
  │      │                                                 │
  │      │                                                 └── reads disk/memory fields
  │      │
  ├──►  Browser loads /ui_kits/crt_dashboard/index.html
  │      │
  │      ├──► CrtDashboard mounts
  │      │      │
  │      │      ├──► fetches GET /api/status          ← TradingDashboardAPI.status_payload()
  │      │      │                                      │
  │      │      │                                      ├── reads ACTIVE_VERSION file
  │      │      │                                      ├── reads models/{inst}/ dirs
  │      │      │                                      ├── reads kill_switch_state.json
  │      │      │                                      └── reads *_trades.csv for 24h count
  │      │      │
  │      │      ├──► fetches GET /api/models          ← TradingDashboardAPI.models_payload()
  │      │      │                                      │
  │      │      │                                      └── reads gaussian_registry.json
  │      │      │
  │      │      ├──► fetches GET /api/trades          ← TradingDashboardAPI.trades_payload()
  │      │      │                                      │
  │      │      │                                      └── reads *_trades.csv
  │      │      │
  │      │      └──► polls every 30s: status, trades, equity
  │      │
  ├──►  Browser loads GET / (redirects to React CP)
  │
  └──►  Browser loads GET /dashboard (embedded trading dashboard)
```

---

## 3. Component Dependency Tree (React Control Plane)

```
App.jsx
  ├── Header.jsx
  ├── PlaybookPanel.jsx
  ├── LauncherPanel.jsx
  │     ├── Primitives.jsx (form inputs, buttons, tables, modals)
  │     ├── ComboBox.jsx
  │     └── FileUploader.jsx
  ├── InspectorPanel.jsx
  │     ├── Primitives.jsx
  │     └── Sparkline.jsx
  ├── DashboardView.jsx
  │     └── Primitives.jsx
  ├── WorkflowPanel.jsx
  ├── AgentPanel.jsx
  ├── Tour.jsx
  └── (ContextModal — inline)
```

**Shared utilities:**
- `format.js` — date/number formatting (used by panels)
- `realApi.js` — HTTP fetch wrapper (used by panels)
- `mockApi.js` — fake data provider (dev only, used by App.jsx)

---

## 4. Component Dependency Tree (React Operations Dashboard)

```
app.jsx (CrtDashboard)
  ├── TopBar (shared.jsx)
  │     └── uses: selectedInstrument, status props
  ├── SidebarNew (shared.jsx)
  │     └── uses: activePage, activeSub props
  └── Content Area
        ├── ExecutivePage (page0_executive.jsx)
        │     ├── LineChart (charts.jsx)
        │     ├── SessionEquityChart (inline SVG)
        │     ├── VerticalBars (charts.jsx)
        │     ├── Heatmap (charts.jsx)
        │     └── uses: status, equity, oppStats props
        ├── RuntimePage (page1_runtime.jsx)
        ├── ResearchPage (page2_research.jsx)
        │     └── uses: opportunityAnalytics props
        ├── ModelsPage (page3_models.jsx)
        │     └── uses: models, zoneModels, rrModels, tradenetModels
        ├── TradesPage (page4_trades.jsx)
        │     └── uses: trades, equity props
        ├── BacktestsPage (page5_backtests.jsx)
        │     └── uses: backtestHistory props
        ├── SystemPage (page6_system.jsx)
        │     └── uses: scanJobs props
        ├── IntelligencePage (page7_intelligence.jsx)
        └── ReplayPage (page8_replay.jsx)
```

**Shared utilities:**
- `apiClient.js` — centralized fetch surface (`window.ApiClient`)
- `data.js` — static scaffold globals (`window.MODELS`, `window.ALERTS`, etc.)
- `styles.css` — complete stylesheet
- `charts.jsx` — 5 chart components (LineChart, VerticalBars, Heatmap, DonutChart, Scatter)

---

## 5. Backend Python Class Dependencies

```
ControlPlaneServer (server.py:1989)
  ├── ControlPlaneAPI (server.py:54)
  │     └── JobManager (jobs.py:79)
  │           ├── registry.py (core_command_specs, command_map, merge_command_args)
  │           │     └── cp_types.py (CommandSpec, ArgSpec, RunRecord)
  │           └── monitors.py (load_monitor_specs, extract_fields, MonitorFieldSpec)
  ├── TradingDashboardAPI (dashboard_api.py:82)
  │     └── (reads files directly — no src.* imports)
  ├── RunReportAPI (report_api.py:52)
  │     └── (stdlib-only + openpyxl + urllib.request)
  └── ContextReportAPI (context_report.py:154)
        └── (stdlib-only + anthropic)
```

---

## 6. File System Data Dependencies

```
ControlPlaneServer reads/writes:
  ├── logs/control_plane/runs/{id}.json        — legacy run states
  ├── results/{instrument}/{inst}_{id}.json     — new run states
  ├── logs/{instrument}/{inst}_{id}.stdout      — stdout logs
  ├── logs/{instrument}/{inst}_{id}.stderr      — stderr logs
  ├── logs/{instrument}/{inst}_{id}.log         — combined logs
  ├── logs/control_plane/monitor_history/*.jsonl — monitor history
  ├── logs/control_plane/requests.log          — request log
  └── logs/control_plane/polling.log           — polling log

TradingDashboardAPI reads:
  ├── configs/production/ACTIVE_VERSION         — active config version
  ├── models/gaussian_registry.json             — Gaussian model registry
  ├── models/zone_gate_registry.json            — Zone Gate registry
  ├── models/zone_registry.json                 — fallback zone data
  ├── models/rr_registry.json                   — RR model registry
  ├── models/rr_dataset.json                    — fallback RR data
  ├── models/rr_model.json                      — fallback RR model
  ├── models/tradenet_registry.json             — TradeNet registry
  ├── models/{instrument}/{run_dir}/gaussian_*  — per-instrument models
  ├── logs/kill_switch_state.json               — kill switch
  ├── results/run_*/{inst}_trades.csv           — trade CSVs
  ├── logs/{inst}/{run_dir}/opportunities.jsonl — opportunity logs
  ├── logs/opportunities_{inst}.jsonl           — legacy opportunity logs
  └── results/p5_calibration_*.json             — calibration history
```

---

## 7. Request → Response Flow

```
Browser                      ControlPlaneServer           File System
  │                                │                         │
  │  GET /commands                 │                         │
  │ ──────────────────────────►    │                         │
  │                                ├── core_command_specs()  │
  │                                │       │                 │
  │                                │       └─── reads ──────►│ registry.py (hardcoded specs)
  │                                │                         │
  │  ◄──────────── JSON ───────────│                         │
  │                                │                         │
  │  POST /commands/x/runs         │                         │
  │ ──────────────────────────►    │                         │
  │                                ├── create_run()          │
  │                                │       │                 │
  │                                │       ├── spawns ──────► subprocess
  │                                │       ├── writes ──────► stdout/stderr files
  │                                │       └── persists ────► state JSON
  │                                │                         │
  │  ◄──────── JSON ───────────────│                         │
  │                                │                         │
  │  GET /api/status               │                         │
  │ ──────────────────────────►    │                         │
  │                                ├── status_payload()      │
  │                                │       │                 │
  │                                │       ├── reads ───────► ACTIVE_VERSION
  │                                │       ├── reads ───────► models/{inst}/
  │                                │       ├── reads ───────► kill_switch_state.json
  │                                │       └── reads ───────► *_trades.csv
  │                                │                         │
  │  ◄──────── JSON ───────────────│                         │
```

---

## 8. Human Experience Graph

```
User (operator/trader)
  │
  ├──► CRT Web Control Plane (port 8787)
  │      │
  │      ├──► Playbook Panel
  │      │      └──► Workflow Stages (Data Prep → Live Runner)
  │      │
  │      ├──► Launcher Panel
  │      │      ├──► Command Selector (category → command)
  │      │      ├──► Form Builder (dynamic from args_schema)
  │      │      ├──► Run Preview (CLI command preview)
  │      │      └──► Run History (searchable table)
  │      │
  │      ├──► Inspector Panel
  │      │      ├──► Run Metadata
  │      │      ├──► Monitor Fields (live poll)
  │      │      ├──► Stdout / Stderr
  │      │      └──► Artifacts
  │      │
  │      ├──► Dashboard View
  │      │      └──► Per-Command Monitor Cards
  │      │
  │      ├──► Workflow View (Mermaid diagram)
  │      ├──► Agent Panel (findings/audit logs)
  │      └──► Guided Tour (13 steps)
  │
  └──► CRT Operations Dashboard (port 8787/dashboard)
         │
         ├──► Executive Page (KPIs, charts, alerts)
         ├──► Runtime Page (live metrics)
         ├──► Research Page (analytics)
         ├──► Models Page (4 registries + promote)
         ├──► Trades Page (journal + equity)
         ├──► Backtests Page (calibration history)
         ├──► System Page (health)
         ├──► Intelligence Page (LLM insights)
         └──► Replay Lab (replay analysis)
```

---

## 9. Job System Flow

```
User clicks "Run Command"
       │
       ▼
POST /commands/{id}/runs  {args: {...}}
       │
       ▼
JobManager.create_run()
       │
       ├── 1. Merge user args with spec defaults
       ├── 2. Build CLI command line
       ├── 3. Create run_id (UUID hex)
       ├── 4. Create instrument-aware log directories
       ├── 5. Persist RunRecord to results/{inst}/{inst}_{id}.json
       ├── 6. Spawn subprocess.Popen with tee to stdout/stderr/combined
       ├── 7. Pump stdout & stderr to files (separate threads)
       ├── 8. Wait for process exit
       ├── 9. Set status (succeeded/failed/stopped)
       ├──10. Discover artifacts via glob + args
       ├──11. Extract monitor snapshot from specs
       ├──12. Append to monitor_history JSONL
       └──13. Persist final RunRecord
              │
              ▼
       UI polls GET /runs/{id}/monitors
       UI polls GET /runs/{id}/logs
       UI polls GET /runs/{id}/artifacts