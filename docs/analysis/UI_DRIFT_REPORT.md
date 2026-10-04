# UI Drift Report

> Read-only detection of duplicate dashboards, dead pages, unused components, unreachable routes, orphan APIs, multiple truths, and inconsistent naming.
> **Unknowns remain UNKNOWN.**

---

## 1. Duplicate Dashboards

| Duplicate Group | Occurrences | Location | Evidence |
|----------------|------------|----------|----------|
| **CRT Web Control Plane** | 2 | `server.py` lines 136–953 (embedded) + `ui_kits/control_plane/` (React) | Both serve the same purpose: command launcher, run history, run inspector, monitoring dashboard, playbook, tour |
| **CRT Trading Dashboard** | 2 | `server.py` lines 956–1546 (embedded) + `ui_kits/crt_dashboard/` (React) | Both serve trading status, models, opportunities, trades, backtests |
| **Monitoring Dashboard** | 3 | Embedded CP (Dashboard view), React CP (DashboardView), React dashboard (multiple pages) | All three show monitoring/status data but with different visual layouts |

## 2. Dead Pages / Unreachable Routes

| Potential Dead Item | Location | Status | Evidence |
|--------------------|----------|--------|----------|
| `src/ui/__init__.py` | `src/ui/` | **DEAD** — package exists but is empty (no modules, no classes) | Contains only `__init__.py` with no code |
| `dashboard_ARCHIVED_2026_05_02.py` | `archive/ui_legacy/` | **ARCHIVED** — explicitly dated and moved to archive | Archived on 2026-05-02 |
| `App.jsx` view="workflow" | `ui_kits/control_plane/WorkflowPanel.jsx` | **QUESTIONABLE** — referenced in App.jsx but may not have active route in embedded version | No `/workflow` route exists in server.py; no workflow_stages route |
| `App.jsx` view="agent" | `ui_kits/control_plane/AgentPanel.jsx` | **ACTIVE** — routes exist | `/api/agent/*` routes confirmed in server.py |

## 3. Unused Components

| Component | Location | Status | Evidence |
|-----------|----------|--------|----------|
| `mockApi.js` | `ui_kits/control_plane/` | **DEV-ONLY** — provides fake data; not used in production | Referenced in `App.jsx` line 3: `useEffect(() => mockApi.subscribe(...)` — assumes mockApi is global |
| `realData.js` | `ui_kits/crt_dashboard/` | **BEING PHASED OUT** (Phase 6) | `index.html` comment: "legacy mount trigger — being phased out (Phase 6)" |

## 4. Multiple Truths / Data Duplication

| Concept | Truth Sources | Files | Risk |
|---------|--------------|-------|------|
| **Workflow stages** | `WORKFLOW_STAGE_ORDER` tuple in `registry.py` | `src/control_plane/registry.py` lines 20-27 | Single source — OK |
| **Command specs** | `core_command_specs()` function | `src/control_plane/registry.py` lines 197-939 | Single source — OK |
| **Instruments list** | `KNOWN_INSTRUMENTS` tuple (hardcoded) vs `instruments_payload()` (config-derived) | `registry.py` line 16 vs `dashboard_api.py` line 973 | **DUAL TRUTH** — hardcoded `_KNOWN_INSTRUMENTS` in registry.py may drift from config-derived list in dashboard_api.py |
| **Tour steps** | `TOUR_STEPS` array in embedded CP | `server.py` lines 330-357 | Single source in embedded — but React CP has its own `Tour.jsx` with potentially different steps — **UNKNOWN** |
| **Monitor field specs** | JSON file at `configs/control_plane/monitors.json` | Loaded by `load_monitor_specs()` in `monitors.py` | File-based — single source from disk |
| **Session labels** | `SESSION_LABELS` in both embedded dashboard + React dashboard | `server.py` line 1195 + `ui_kits/crt_dashboard/` pages | **DUPLICATED** — same mapping hardcoded in two places |

## 5. Unreachable Routes / Orphan APIs

| Route | Defined In | Consumer | Status |
|-------|-----------|----------|--------|
| `/api/zone_gate_models` | `server.py` line 1637 | React dashboard only | **OK** — dedicated consumer |
| `/api/rr_models` | `server.py` line 1640 | React dashboard only | **OK** — dedicated consumer |
| `/api/tradenet_models` | `server.py` line 1643 | React dashboard only | **OK** — dedicated consumer |
| `/api/opportunity_analytics` | `server.py` line 1670 | React dashboard only | **OK** — dedicated consumer |
| `/api/scan_jobs` | `server.py` line 1666 | React dashboard only | **OK** — dedicated consumer |
| `/api/promote_zone_gate` | `server.py` line 1873 | React dashboard only | **OK** — dedicated consumer |
| `/api/promote_rr` | `server.py` line 1878 | React dashboard only | **OK** — dedicated consumer |
| `/api/promote_tradenet` | `server.py` line 1883 | React dashboard only | **OK** — dedicated consumer |
| `/api/explain_model` | `server.py` line 1888 | React dashboard only | **OK** — dedicated consumer |
| `/api/agent/findings` | `server.py` line 1693 | React CP AgentPanel | **OK** — dedicated consumer |
| `/api/agent/audit` | `server.py` line 1703 | React CP AgentPanel | **OK** — dedicated consumer |
| `/api/agent/llm_requests` | `server.py` line 1713 | React CP AgentPanel | **OK** — dedicated consumer |
| `/api/agent/synthesize` | `server.py` line 1952 | React CP AgentPanel | **OK** — dedicated consumer |
| `/catalog` | `server.py` line 1724 | React apps (window.CATALOG) | **OK** — dedicated consumer |
| `/runs/{id}/context/report` | `server.py` line 1913 | React CP (ContextModal) | **OK** — referenced in App.jsx |

## 6. Inconsistent Naming

| Concept | Inconsistent Names | Locations |
|---------|-------------------|-----------|
| Zone Gate model registry file | `zone_gate_registry.json` vs `zone_registry.json` | `dashboard_api.py` uses both (primary vs fallback) |
| RR model files | `rr_model.json`, `rr_dataset.json`, `rr_registry.json` | Multiple paths in `dashboard_api.py` |
| TradeNet model files | `tradenet_registry.json` vs `tradenet_p5_*.pth` | `dashboard_api.py` primary vs fallback |
| UI directory name | `ui_kits` (on disk) vs `/ui_kits/` (URL route) | Consistent |
| Dashboard entry points | `/dashboard` (embedded) vs `/ui_kits/crt_dashboard/` (React) vs `DashboardView` (React CP) | 3 different paths to dashboard-like views |
| Session label storage | `SESSION_LABELS` object in embedded JS | `server.py` line 1195 — hardcoded in two consumers |

## 7. Framework/Stack Drift

| UI System | Framework | Rendering | Build Step | Network |
|-----------|-----------|-----------|------------|---------|
| Embedded Control Plane | Vanilla HTML/CSS/JS | Server-side HTML string | None | Polls every 2s |
| Embedded Trading Dashboard | Vanilla HTML/CSS/JS + Chart.js CDN | Server-side HTML string | None | Polls every 10s |
| React Control Plane | React 18 UMD + Babel standalone | Client-side (in-browser JSX transpile) | None | Polls every 2s |
| React Operations Dashboard | React 18 UMD + Babel standalone | Client-side (in-browser JSX transpile) | None | Polls every 30s |

**Observation:** All 4 systems share the same backend routes. The difference is purely in the front-end delivery mechanism. There is no build tool, no bundler, no package.json for any of them.

## 8. API Surface Drift Summary

| API Surface | Embedded CP | React CP | Embedded Dashboard | React Dashboard |
|-------------|-------------|-----------|-------------------|-----------------|
| `/commands` | ✅ | ✅ | ❌ | ❌ |
| `/runs/*` | ✅ | ✅ | ❌ | ❌ |
| `/monitors/*` | ✅ | ✅ | ❌ | ❌ |
| `/files` | ✅ | ✅ | ❌ | ❌ |
| `/api/status` | ❌ | ❌ | ✅ | ✅ |
| `/api/models` | ❌ | ❌ | ✅ | ✅ |
| `/api/opportunities` | ❌ | ❌ | ✅ | ✅ |
| `/api/trades` | ❌ | ❌ | ✅ | ✅ |
| `/api/backtest_history` | ❌ | ❌ | ✅ | ✅ |
| `/api/zone_gate_models` | ❌ | ❌ | ❌ | ✅ |
| `/api/agent/*` | ❌ | ✅ | ❌ | ❌ |

**Drift:** No single UI consumes all API endpoints. React CP and React Dashboard are separate apps that each consume a different subset of the total API surface.

## 9. Test Coverage Drift

| Test File | What It Tests | UI Relevance |
|-----------|--------------|-------------|
| `test_control_plane_api.py` | API lifecycle (create/run/stop/artifacts) + UI route returns HTML with "CRT Web Control Plane" | Confirms embedded UI renders |
| `test_control_plane_jobs.py` | JobManager subprocess execution | Backend only |
| `test_control_plane_registry.py` | CommandSpec registry | Backend only |
| `test_control_plane_tutorial.py` | Tour/tutorial system | Tests tutorial embedded UI |
| `test_control_plane_doc_alignment.py` | Doc alignment with control plane | Doc integrity only |

**Gap:** No tests exist for the React UI kits (`ui_kits/control_plane/`, `ui_kits/crt_dashboard/`). The React apps are untested.