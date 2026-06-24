# UI Component Map

> Complete inventory of all UI components across all systems.
> **Source:** Read-only investigation of all UI artifacts.

---

## 1. Components Table

### Embedded Control Plane (in `src/control_plane/server.py` — `ControlPlaneAPI.ui_html()`)

| Name | Path | Type | Purpose | Active? | Evidence |
|------|------|------|---------|---------|----------|
| Header | server.py:213-220 | HTML `<header>` | Top bar with title, workflow stage indicator, Dashboard/Help buttons | Yes | `server.py` line 213 |
| Playbook Panel | server.py:222-228 | HTML `<section>` | Workflow checklist and command navigation | Yes | `server.py` line 222 |
| Launcher Panel | server.py:229-258 | HTML `<section>` | Command category/command selectors, form builder, run/stop, preview | Yes | `server.py` line 229 |
| Run History | server.py:248-258 | HTML table | Searchable run history table | Yes | `server.py` line 248 |
| Inspector Panel | server.py:259-276 | HTML `<section>` | Run metadata, monitored fields, stdout/stderr, artifacts | Yes | `server.py` line 259 |
| Run Report Modal | server.py:303-315 | HTML modal | Report download (Excel) + LLM analysis | Yes | `server.py` line 303 |
| Tour Card | server.py:290-301 | HTML overlay | 13-step guided tour overlay | Yes | `server.py` line 289 |
| Dashboard Grid | server.py:279-287 | HTML dashboard | Monitoring dashboard with auto-refresh | Yes | `server.py` line 279 |

### Embedded Trading Dashboard (in `server.py` — `ControlPlaneAPI.trading_dashboard_html()`)

| Name | Path | Type | Purpose | Active? | Evidence |
|------|------|------|---------|---------|----------|
| Status Header | server.py:1023-1026 | HTML `<header>` | Title + back link to Control Plane | Yes | `server.py` line 1023 |
| Tab Navigation | server.py:1028-1034 | HTML `<nav>` | 5-tab navigation (Status, Models, Opportunities, Trades, Backtests) | Yes | `server.py` line 1028 |
| Status Stats | server.py:1039-1045 | HTML stat cards | Active config, model, kill switch, trades 24h | Yes | `server.py` line 1039 |
| Model Versions Grid | server.py:1051-1072 | HTML 4-column grid | Gaussian, Zone Gate, RR Miner, TradeNet version info | Yes | `server.py` line 1051 |
| Models Table | server.py:1090-1103 | HTML table | Gaussian model registry with promote buttons | Yes | `server.py` line 1090 |
| Opportunities Panel | server.py:1106-1142 | HTML tab | Win rate bar chart + paginated opportunity table | Yes | `server.py` line 1106 |
| Trades Panel | server.py:1145-1172 | HTML tab | Equity curve line chart + paginated trade journal | Yes | `server.py` line 1145 |
| Backtests Panel | server.py:1175-1188 | HTML tab | Phase-5 calibration history | Yes | `server.py` line 1175 |

### React Control Plane (`ui_kits/control_plane/`)

| Component | File | Type | Purpose | Active? | Evidence |
|-----------|------|------|---------|---------|----------|
| App | `App.jsx` | React function component | Root — state manager + 4-view router | Yes | `App.jsx` line 1 |
| Header | `Header.jsx` | React function component | Top bar | Yes | `index.html` script src |
| PlaybookPanel | `PlaybookPanel.jsx` | React function component | Workflow checklist | Yes | `index.html` script src |
| LauncherPanel | `LauncherPanel.jsx` | React function component | Command selector + form + run | Yes | `index.html` script src |
| InspectorPanel | `InspectorPanel.jsx` | React function component | Run detail view | Yes | `index.html` script src |
| DashboardView | `DashboardView.jsx` | React function component | Monitoring dashboard | Yes | `index.html` script src |
| WorkflowPanel | `WorkflowPanel.jsx` | React function component | Mermaid workflow diagram | Yes | `index.html` script src |
| AgentPanel | `AgentPanel.jsx` | React function component | Agent findings/audit | Yes | `index.html` script src |
| Tour | `Tour.jsx` | React function component | Guided tour step-by-step | Yes | `index.html` script src |
| Primitives | `Primitives.jsx` | React function components | Shared: inputs, buttons, tables, modals, status badges | Yes | `index.html` script src |
| ComboBox | `ComboBox.jsx` | React function component | Autocomplete dropdown | Yes | `index.html` script src |
| FileUploader | `FileUploader.jsx` | React function component | File selection widget | Yes | `index.html` script src |
| Sparkline | `Sparkline.jsx` | React function component | Inline sparkline chart | Yes | `index.html` script src |

### React Operations Dashboard (`ui_kits/crt_dashboard/`)

| Component | File | Type | Purpose | Active? | Evidence |
|-----------|------|------|---------|---------|----------|
| CrtDashboard | `app.jsx` | React function component | Root store + 9-page router + 30s poll | Yes | `app.jsx` line 5 |
| TopBar | `shared.jsx` | React function component | Top navigation bar | Yes | `shared.jsx` |
| SidebarNew | `shared.jsx` | React function component | Vertical sidebar navigation | Yes | `shared.jsx` |
| ExecutivePage | `page0_executive.jsx` | React function component | KPIs, charts, alerts, status | Yes | `page0_executive.jsx` line 3 |
| RuntimePage | `page1_runtime.jsx` | React function component | Runtime metrics | Yes | `index.html` script src |
| ResearchPage | `page2_research.jsx` | React function component | Research analytics | Yes | `index.html` script src |
| ModelsPage | `page3_models.jsx` | React function component | 4-model registries with promote | Yes | `index.html` script src |
| TradesPage | `page4_trades.jsx` | React function component | Trade journal + equity | Yes | `index.html` script src |
| BacktestsPage | `page5_backtests.jsx` | React function component | Calibration history | Yes | `index.html` script src |
| SystemPage | `page6_system.jsx` | React function component | System health | Yes | `index.html` script src |
| IntelligencePage | `page7_intelligence.jsx` | React function component | LLM-driven intelligence | Yes | `index.html` script src |
| ReplayPage | `page8_replay.jsx` | React function component | Replay analysis | Yes | `index.html` script src |
| LineChart | `charts.jsx` | React function component | SVG line chart | Yes | `charts.jsx` |
| VerticalBars | `charts.jsx` | React function component | SVG bar chart | Yes | `charts.jsx` |
| Heatmap | `charts.jsx` | React function component | SVG heatmap | Yes | `charts.jsx` |
| DonutChart | `charts.jsx` | React function component | SVG donut | Yes | `charts.jsx` |
| Scatter | `charts.jsx` | React function component | SVG scatter plot | Yes | `charts.jsx` |
| SessionEquityChart | `page0_executive.jsx` | React function component | 4-series multi-line SVG | Yes | `page0_executive.jsx` line 164 |

---

## 2. Non-Component Supporting Files

| File | Location | Purpose |
|------|----------|---------|
| `realApi.js` | `ui_kits/control_plane/` | HTTP fetch wrapper for backend endpoints |
| `mockApi.js` | `ui_kits/control_plane/` | Fake data provider for development |
| `format.js` | `ui_kits/control_plane/` | Date/number formatting utilities |
| `apiClient.js` | `ui_kits/crt_dashboard/` | Centralized fetch surface (window.ApiClient) |
| `data.js` | `ui_kits/crt_dashboard/` | Static scaffold globals for development |
| `realData.js` | `ui_kits/crt_dashboard/` | Legacy mount trigger (Phase 6 deprecation) |
| `styles.css` | `ui_kits/crt_dashboard/` | Complete dark-theme stylesheet |

---

## 3. Backend API Providers (Python classes serving UI data)

| Class | File | Purpose | Active? | Evidence |
|-------|------|---------|---------|----------|
| `ControlPlaneAPI` | `src/control_plane/server.py` | Command/runs/monitors/files payload providers | Yes | `server.py` line 54 |
| `TradingDashboardAPI` | `src/control_plane/dashboard_api.py` | Status, models, opportunities, trades, equity, backtest payloads | Yes | `dashboard_api.py` line 82 |
| `RunReportAPI` | `src/control_plane/report_api.py` | Excel generation + Groq LLM analysis | Yes | `report_api.py` line 52 |
| `ContextReportAPI` | `src/control_plane/context_report.py` | Claude-powered operational intelligence | Yes | `context_report.py` line 154 |
| `JobManager` | `src/control_plane/jobs.py` | Run queue, subprocess execution, monitor snapshots | Yes | `jobs.py` line 79 |