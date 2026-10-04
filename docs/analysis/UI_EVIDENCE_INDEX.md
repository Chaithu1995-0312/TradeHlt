# UI Evidence Index

> Complete citation index for every UI artifact discovered.
> Every statement in the companion reports traces to an exact file path + line/function/component.
> **Unknowns remain UNKNOWN — no assumptions.**

---

## 1. Source Files (Python — Backend)

| File | Key Classes/Functions | UI Role | Lines |
|------|----------------------|---------|-------|
| `src/control_plane/server.py` | `ControlPlaneAPI` (line 54), `ControlPlaneAPI.ui_html()` (line 135), `ControlPlaneAPI.trading_dashboard_html()` (line 955), `ControlPlaneServer` (line 1989), `Handler` (line 1566), `create_handler()` (line 1549), `run_server()` (line 2040) | HTTP server: routing, 2 embedded HTML UIs, static file serving | 2061 |
| `src/control_plane/dashboard_api.py` | `TradingDashboardAPI` (line 82): `status_payload()`, `models_payload()`, `model_versions_payload()`, `opportunities_payload()`, `opportunity_stats_payload()`, `trades_payload()`, `equity_curve_payload()`, `backtest_history_payload()`, `instruments_payload()`, `promote_model_payload()`, `explain_model_payload()`, `zone_gate_models_payload()`, `rr_models_payload()`, `tradenet_models_payload()` | Read-only data API for all dashboard endpoints | 1075 |
| `src/control_plane/jobs.py` | `JobManager` (line 79): `create_run()`, `stop_run()`, `list_runs()`, `get_run()`, `read_logs()`, `live_monitors()`, `dashboard_snapshot()`, `monitor_history()`, `snapshot()` | Run queue, subprocess execution, monitor extraction | 497 |
| `src/control_plane/registry.py` | `core_command_specs()` (line 197), `command_map()` (line 953), `merge_command_args()` (line 990), `build_command_line()` (line 1047), `command_spec_to_json()` (line 1127), `workflow_stage_order()` (line 968), `WORKFLOW_STAGE_ORDER` (line 20), `_KNOWN_INSTRUMENTS` (line 16), `_WORKFLOW_STAGE_BY_COMMAND` (line 29), `_QUICKSTART_NOTES_BY_COMMAND` (line 54), `_RECOMMENDED_NEXT_BY_COMMAND` (line 171) | CommandSpec catalog, workflow stages, arg merging | 1143 |
| `src/control_plane/report_api.py` | `RunReportAPI` (line 52): `excel_bytes()` (line 64), `llm_analysis()` (line 240), `_build_excel_context()` (line 153) | Excel XLSX generation + Groq-powered run analysis | 312 |
| `src/control_plane/context_report.py` | `ContextReportAPI` (line 154): `context_analysis()` (line 162), `_build_prompt()` (line 65) | Claude-powered operational intelligence | 244 |
| `src/control_plane/monitors.py` | `load_monitor_specs()`, `extract_fields()`, `default_monitors_path()`, `MonitorFieldSpec` | Monitor field spec parsing + extraction | (not fully read) |
| `src/control_plane/cp_types.py` | `CommandSpec` dataclass, `ArgSpec` dataclass, `RunRecord` dataclass | Shared type definitions | (not fully read) |
| `src/control_plane/code_context_extractor.py` | `extract_code_context()` | AST-based code extraction for context reports | (not fully read) |
| `src/ui/__init__.py` | (empty) | Dead package — no UI code | 1 |

---

## 2. Source Files (React — Frontend)

### ui_kits/control_plane/ (16 files)

| File | Component(s)/Functions | UI Role |
|------|----------------------|---------|
| `index.html` | HTML shell | Entry point — loads React 18 + Babel + Mermaid + all JSX files |
| `App.jsx` | `App` (line 1) | Root component: 4 views (runs, dashboard, workflow, agent), central state via useState |
| `Header.jsx` | `Header` | Top bar |
| `PlaybookPanel.jsx` | `PlaybookPanel` | Workflow checklist with stage groups |
| `LauncherPanel.jsx` | `LauncherPanel` | Command selector, dynamic form, run/stop, search history |
| `InspectorPanel.jsx` | `InspectorPanel` | Run detail: metadata, monitors, stdout/stderr, artifacts |
| `DashboardView.jsx` | `DashboardView` | Monitoring dashboard grid |
| `WorkflowPanel.jsx` | `WorkflowPanel` | Mermaid workflow diagram |
| `AgentPanel.jsx` | `AgentPanel` | Agent findings/audit log viewer |
| `Tour.jsx` | `Tour` | Guided tour overlay |
| `Primitives.jsx` | Shared: form inputs, buttons, tables, status badges, modals | Reusable UI primitives |
| `ComboBox.jsx` | `ComboBox` | Autocomplete/searchable dropdown |
| `FileUploader.jsx` | `FileUploader` | File selection widget |
| `Sparkline.jsx` | `Sparkline` | Inline sparkline SVG chart |
| `format.js` | Format utilities | Date/number formatting functions |
| `realApi.js` | API client | HTTP fetch wrapper for backend routes |
| `mockApi.js` | Mock API | Fake data provider for development (dev-only) |
| `README.md` | Documentation | Setup and usage notes |

### ui_kits/crt_dashboard/ (22 files)

| File | Component(s)/Functions | UI Role |
|------|----------------------|---------|
| `index.html` | HTML shell | Entry point — loads React 18 + Babel + styles + all .jsx pages |
| `app.jsx` | `CrtDashboard` (line 5) | Root store: centralized React state, 9-page router, 30s auto-refresh |
| `apiClient.js` | `window.ApiClient` | Centralized fetch surface (all dashboard API endpoints) |
| `data.js` | Static globals | `window.MODELS`, `window.ALERTS`, `window.SESSION_EQUITY`, etc. |
| `realData.js` | Legacy mount trigger | Being phased out (Phase 6) |
| `styles.css` | Complete stylesheet | Dark-theme CSS for entire dashboard |
| `charts.jsx` | `LineChart`, `VerticalBars`, `Heatmap`, `DonutChart`, `Scatter` | SVG chart components |
| `shared.jsx` | `TopBar`, `SidebarNew`, `KPIStrip`, `Modal` | Shared layout components |
| `page0_executive.jsx` | `ExecutivePage` (line 3), `SessionEquityChart` (line 164) | Executive overview — KPIs, charts, alerts, status |
| `page1_runtime.jsx` | `RuntimePage` | Live runtime metrics |
| `page2_research.jsx` | `ResearchPage` | Research analytics |
| `page3_models.jsx` | `ModelsPage` | 4-model registry tables with promote |
| `page4_trades.jsx` | `TradesPage` | Trade journal + equity curve |
| `page5_backtests.jsx` | `BacktestsPage` | Phase-5 calibration history |
| `page6_system.jsx` | `SystemPage` | System health |
| `page7_intelligence.jsx` | `IntelligencePage` | LLM-driven intelligence |
| `page8_replay.jsx` | `ReplayPage` | Replay analysis |

---

## 3. Test Files (UI-Relevant)

| File | Test Functions | What It Validates |
|------|---------------|-------------------|
| `tests/test_control_plane_api.py` | `test_api_run_lifecycle_and_artifacts()` (line 26), `test_ui_route_returns_html()` (line 81) | API lifecycle + embedded UI HTML returns correctly |
| `tests/test_control_plane_tutorial.py` | Tutorial tests | Guided tour system works |
| `tests/test_control_plane_jobs.py` | Job tests | JobManager subprocess execution |
| `tests/test_control_plane_registry.py` | Registry tests | CommandSpec registry integrity |
| `tests/test_control_plane_doc_alignment.py` | Doc alignment tests | Documentation alignment with control plane |

---

## 4. Documentation Files (UI-Relevant)

| File | Content |
|------|---------|
| `README.md` | Project overview — mentions 8787 port, control plane, dashboard |
| `CLAUDE.md` | Operating manual for LLM session management — references control plane |

---

## 5. Configuration Files (UI-Relevant)

| File | Content |
|------|---------|
| `configs/control_plane/monitors.json` | Monitor field specifications per command |
| `configs/control_plane/` | Directory containing monitor configs |

---

## 6. Archived UI Artifacts

| File | Original Purpose | Archived Date |
|------|-----------------|---------------|
| `archive/ui_legacy/dashboard_ARCHIVED_2026_05_02.py` | Python-based dashboard (pre-React) | 2026-05-02 |

---

## 7. Key Endpoints and Their Producers

### Page endpoints:
- `GET /` → redirect to `/ui_kits/control_plane/` — `Handler.do_GET` line 1782
- `GET /dashboard` → `api.trading_dashboard_html()` — `Handler.do_GET` line 1624
- `GET /ui_kits/*` → static file serve — `Handler.do_GET` line 1751

### Control Plane API:
- `GET /commands` → `api.commands_payload()` — line 1789
- `GET /runs` → `api.runs_payload(query)` — line 1796
- `GET /runs/{id}` → `api.run_payload(id)` — line 1839
- `GET /runs/{id}/logs` → `api.logs_payload(id)` — line 1816
- `GET /runs/{id}/artifacts` → `api.artifacts_payload(id)` — line 1820
- `GET /runs/{id}/monitors` → `api.monitors_payload(id)` — line 1824
- `GET /runs/{id}/report/excel` → `report_api.excel_bytes()` — line 1799
- `POST /runs/{id}/report/llm` → `report_api.llm_analysis()` — line 1899
- `POST /runs/{id}/context/report` → `context_api.context_analysis()` — line 1913
- `POST /commands/{id}/runs` → `api.create_run_payload()` — line 1939
- `POST /runs/{id}/stop` → `api.stop_payload()` — line 1947
- `GET /monitors/dashboard` → `api.dashboard_payload()` — line 1828
- `GET /monitors/history/{id}` → `api.monitor_history_payload()` — line 1831
- `GET /files` → `api.files_payload(glob)` — line 1792
- `GET /catalog` → inline JSON — line 1724

### Trading Dashboard API:
- `GET /api/status` → `dash_api.status_payload()` — line 1630
- `GET /api/model_versions` → `dash_api.model_versions_payload()` — line 1627
- `GET /api/models` → `dash_api.models_payload()` — line 1634
- `GET /api/zone_gate_models` → `dash_api.zone_gate_models_payload()` — line 1637
- `GET /api/rr_models` → `dash_api.rr_models_payload()` — line 1640
- `GET /api/tradenet_models` → `dash_api.tradenet_models_payload()` — line 1643
- `GET /api/instruments` → `dash_api.instruments_payload()` — line 1646
- `GET /api/opportunities` → `dash_api.opportunities_payload()` — line 1649
- `GET /api/opportunity_stats` → `dash_api.opportunity_stats_payload()` — line 1662
- `GET /api/opportunity_analytics` → `dash_api.opportunity_analytics_payload()` — line 1670
- `GET /api/scan_jobs` → `dash_api.scan_jobs_payload()` — line 1666
- `GET /api/trades` → `dash_api.trades_payload()` — line 1674
- `GET /api/equity_curve` → `dash_api.equity_curve_payload()` — line 1685
- `GET /api/backtest_history` → `dash_api.backtest_history_payload()` — line 1689
- `POST /api/promote_model` → `dash_api.promote_model_payload()` — line 1862
- `POST /api/promote_zone_gate` → `dash_api.promote_zone_gate_payload()` — line 1873
- `POST /api/promote_rr` → `dash_api.promote_rr_payload()` — line 1878
- `POST /api/promote_tradenet` → `dash_api.promote_tradenet_payload()` — line 1883
- `POST /api/explain_model` → `dash_api.explain_model_payload()` — line 1888

### Agent API:
- `GET /api/agent/findings` → inline JSONL tail — line 1693
- `GET /api/agent/audit` → inline JSONL tail — line 1703
- `GET /api/agent/llm_requests` → inline JSONL tail — line 1713
- `POST /api/agent/synthesize` → `agent.findings_synthesizer.synthesize_finding()` — line 1952

---

## 8. Data Files Consumed by UI Backend

| Path | Read By | Purpose |
|------|---------|---------|
| `configs/production/ACTIVE_VERSION` | `TradingDashboardAPI.status_payload()` (dashboard_api.py:101) | Active config version label |
| `models/gaussian_registry.json` | `TradingDashboardAPI.models_payload()` (dashboard_api.py:184) | Gaussian model registry |
| `models/zone_gate_registry.json` | `TradingDashboardAPI._zone_gate_version()` (dashboard_api.py:273) | Zone Gate registry |
| `models/zone_registry.json` | `TradingDashboardAPI._zone_gate_version()` (dashboard_api.py:295) | Fallback zone data |
| `models/rr_registry.json` | `TradingDashboardAPI._rr_model_version()` (dashboard_api.py:316) | RR model registry |
| `models/rr_dataset.json` | `TradingDashboardAPI._rr_model_version()` (dashboard_api.py:338) | Fallback RR dataset |
| `models/rr_model.json` | `TradingDashboardAPI._rr_model_version()` (dashboard_api.py:340) | Fallback RR model |
| `models/tradenet_registry.json` | `TradingDashboardAPI._tradenet_version()` (dashboard_api.py:362) | TradeNet registry |
| `models/{instrument}/{run_dir}/gaussian_*.json` | `TradingDashboardAPI.status_payload()` (dashboard_api.py:119) | Per-instrument active model |
| `logs/kill_switch_state.json` | `TradingDashboardAPI.status_payload()` (dashboard_api.py:137) | Kill switch state |
| `results/run_*/{instrument}_trades.csv` | `TradingDashboardAPI.trades_payload()` (dashboard_api.py:858) | Trade journal data |
| `logs/{instrument}/{run_dir}/opportunities.jsonl` | `TradingDashboardAPI._find_opportunity_file()` (dashboard_api.py:616) | Modern opportunity logs |
| `logs/opportunities_{instrument}.jsonl` | `TradingDashboardAPI._find_opportunity_file()` (dashboard_api.py:635) | Legacy opportunity logs |
| `results/p5_calibration_*.json` | `TradingDashboardAPI.backtest_history_payload()` (dashboard_api.py:938) | Calibration history |
| `configs/production/{version}.json` | `TradingDashboardAPI.instruments_payload()` (dashboard_api.py:982) | Production config (instruments list) |
| `logs/agent_findings.jsonl` | Inline in Handler.do_GET (server.py:1693) | Agent findings |
| `logs/agent_audit.jsonl` | Inline in Handler.do_GET (server.py:1703) | Agent audit log |
| `logs/agent_llm_requests.jsonl` | Inline in Handler.do_GET (server.py:1713) | Agent LLM requests |
| `.env` | `RunReportAPI.llm_analysis()` (report_api.py:254), `ContextReportAPI.context_analysis()` (context_report.py:176) | API keys (GROQ_API_KEY, ANTHROPIC_API_KEY) |

---

## 9. Embedded UI Key Code Sections

| Feature | Location | Lines |
|---------|----------|-------|
| Control Plane HTML template | `ControlPlaneAPI.ui_html()` | server.py:136-953 |
| Control Plane CSS | Inline `<style>` | server.py:142-210 |
| Trading Dashboard HTML template | `ControlPlaneAPI.trading_dashboard_html()` | server.py:956-1546 |
| Trading Dashboard CSS | Inline `<style>` | server.py:963-1020 |
| Tour steps array | `TOUR_STEPS` | server.py:330-357 |
| Session labels | `SESSION_LABELS` | server.py:1195 |
| Polling interval (runs) | `setInterval(refreshRuns, 2000)` | server.py:856 |
| Polling interval (monitors) | `setInterval(()=>refreshMonitors(runId), 2000)` | server.py:688 |
| Polling interval (dashboard) | `setInterval(refreshDashboard, 2000)` | server.py:839 |
| Dashboard status polling | `setInterval(loadStatus, 10000)` | server.py:1542 |
| Static file MIME map | Inline dict in Handler.do_GET | server.py:1752-1760 |
| CORS headers | `Handler.do_OPTIONS` | server.py:1849-1855 |

---

## 10. UI Kit In-Browser Rendering

Both React UI kits use UMD React + Babel standalone for in-browser JSX transpilation:

- **React 18.3.1 UMD:** `https://unpkg.com/react@18.3.1/umd/react.development.js`
- **React DOM 18.3.1 UMD:** `https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js`
- **Babel 7.29.0 standalone:** `https://unpkg.com/@babel/standalone@7.29.0/babel.min.js`
- **Mermaid 10 (CP only):** `https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`
- **Chart.js (embedded dashboard only):** `https://cdn.jsdelivr.net/npm/chart.js`
- **Google Fonts (dashboard only):** `Inter` via `https://fonts.googleapis.com`

No package.json, no Vite, no Webpack, no build step exists for any UI artifact.