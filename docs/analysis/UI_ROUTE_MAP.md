# UI Route Map

> Complete route table for the Control Plane HTTP server (`src/control_plane/server.py`).
> **Server:** `ControlPlaneServer` on `127.0.0.1:8787`

---

## 1. Page Routes

| Route | Method | Response | Handler | Consumer |
|-------|--------|----------|---------|----------|
| `/` | GET | 302 Redirect → `/ui_kits/control_plane/` | `Handler.do_GET` (line 1782) | Browser |
| `/dashboard` | GET | HTML page (CRT Trading Dashboard) | `Handler.do_GET` (line 1624) → `api.trading_dashboard_html()` | Browser |
| `/ui_kits/control_plane/` | GET | Static HTML (React app entry) | `Handler.do_GET` (line 1763) → file serve | Browser |
| `/ui_kits/crt_dashboard/` | GET | Static HTML (React dashboard entry) | `Handler.do_GET` (line 1763) → file serve | Browser |

## 2. Control Plane API Routes

| Route | Method | Response | Handler | Consumer |
|-------|--------|----------|---------|----------|
| `/commands` | GET | JSON: commands list, categories, workflow_stages | `Handler.do_GET` (line 1789) → `api.commands_payload()` | React CP + embedded CP |
| `/runs?q={query}` | GET | JSON: filtered/paginated run list | `Handler.do_GET` (line 1796) → `api.runs_payload()` | React CP + embedded CP |
| `/runs/{run_id}` | GET | JSON: single run detail | `Handler.do_GET` (line 1839) → `api.run_payload()` | React CP + embedded CP |
| `/runs/{run_id}/logs` | GET | JSON: stdout/stderr strings | `Handler.do_GET` (line 1816) → `api.logs_payload()` | React CP + embedded CP |
| `/runs/{run_id}/artifacts` | GET | JSON: artifact list with path/exists/size | `Handler.do_GET` (line 1820) → `api.artifacts_payload()` | React CP + embedded CP |
| `/runs/{run_id}/monitors` | GET | JSON: live monitor field values | `Handler.do_GET` (line 1824) → `api.monitors_payload()` | React CP + embedded CP |
| `/runs/{run_id}/report/excel` | GET | Binary: .xlsx file download | `Handler.do_GET` (line 1799) → `report_api.excel_bytes()` | React CP + embedded CP |
| `/runs/{run_id}/report/llm` | POST | JSON: Groq analysis result | `Handler.do_POST` (line 1899) → `report_api.llm_analysis()` | React CP + embedded CP |
| `/runs/{run_id}/context/report` | POST | JSON: Claude analysis result | `Handler.do_POST` (line 1913) → `context_api.context_analysis()` | React CP |
| `/runs/{run_id}/stop` | POST | JSON: stopped run state | `Handler.do_POST` (line 1947) → `api.stop_payload()` | React CP + embedded CP |
| `/commands/{command_id}/runs` | POST | JSON: created run state | `Handler.do_POST` (line 1939) → `api.create_run_payload()` | React CP + embedded CP |
| `/monitors/dashboard` | GET | JSON: latest per-command monitor fields | `Handler.do_GET` (line 1828) → `api.dashboard_payload()` | React CP + embedded CP |
| `/monitors/history/{command_id}` | GET | JSON: monitor history entries | `Handler.do_GET` (line 1831) → `api.monitor_history_payload()` | React CP |
| `/files?glob={pattern}` | GET | JSON: file glob match list | `Handler.do_GET` (line 1792) → `api.files_payload()` | React CP + embedded CP |
| `/catalog` | GET | JSON: data CSV list, instruments, prod configs | `Handler.do_GET` (line 1724) → inline | React apps (window.CATALOG) |

## 3. Trading Dashboard API Routes

| Route | Method | Response | Handler | Consumer |
|-------|--------|----------|---------|----------|
| `/api/status` | GET | JSON: instrument runtime status | `Handler.do_GET` (line 1630) → `dash_api.status_payload()` | Embedded dashboard + React dashboard |
| `/api/model_versions` | GET | JSON: all 4 model version info | `Handler.do_GET` (line 1627) → `dash_api.model_versions_payload()` | Embedded dashboard + React dashboard |
| `/api/models` | GET | JSON: Gaussian registry list | `Handler.do_GET` (line 1634) → `dash_api.models_payload()` | Embedded dashboard + React dashboard |
| `/api/zone_gate_models` | GET | JSON: Zone Gate registry list | `Handler.do_GET` (line 1637) → `dash_api.zone_gate_models_payload()` | React dashboard |
| `/api/rr_models` | GET | JSON: RR model registry list | `Handler.do_GET` (line 1640) → `dash_api.rr_models_payload()` | React dashboard |
| `/api/tradenet_models` | GET | JSON: TradeNet registry list | `Handler.do_GET` (line 1643) → `dash_api.tradenet_models_payload()` | React dashboard |
| `/api/instruments` | GET | JSON: available instrument list | `Handler.do_GET` (line 1646) → `dash_api.instruments_payload()` | Embedded dashboard + React dashboard |
| `/api/opportunities` | GET | JSON: paginated opportunity records | `Handler.do_GET` (line 1649) → `dash_api.opportunities_payload()` | Embedded dashboard + React dashboard |
| `/api/opportunity_stats` | GET | JSON: win rate by direction/session | `Handler.do_GET` (line 1662) → `dash_api.opportunity_stats_payload()` | Embedded dashboard + React dashboard |
| `/api/opportunity_analytics` | GET | JSON: scatter + time-series chart data | `Handler.do_GET` (line 1670) → `dash_api.opportunity_analytics_payload()` | React dashboard |
| `/api/scan_jobs` | GET | JSON: scanner run list | `Handler.do_GET` (line 1666) → `dash_api.scan_jobs_payload()` | React dashboard |
| `/api/trades` | GET | JSON: paginated trade records | `Handler.do_GET` (line 1674) → `dash_api.trades_payload()` | Embedded dashboard + React dashboard |
| `/api/equity_curve` | GET | JSON: cumulative PnL curve points | `Handler.do_GET` (line 1685) → `dash_api.equity_curve_payload()` | Embedded dashboard + React dashboard |
| `/api/backtest_history` | GET | JSON: p5 calibration history | `Handler.do_GET` (line 1689) → `dash_api.backtest_history_payload()` | Embedded dashboard + React dashboard |
| `/api/promote_model` | POST | JSON: promote result | `Handler.do_POST` (line 1862) → `dash_api.promote_model_payload()` | Embedded dashboard + React dashboard |
| `/api/promote_zone_gate` | POST | JSON: promote result | `Handler.do_POST` (line 1873) → `dash_api.promote_zone_gate_payload()` | React dashboard |
| `/api/promote_rr` | POST | JSON: promote result | `Handler.do_POST` (line 1878) → `dash_api.promote_rr_payload()` | React dashboard |
| `/api/promote_tradenet` | POST | JSON: promote result | `Handler.do_POST` (line 1883) → `dash_api.promote_tradenet_payload()` | React dashboard |
| `/api/explain_model` | POST | JSON: Groq model explanation | `Handler.do_POST` (line 1888) → `dash_api.explain_model_payload()` | React dashboard |

## 4. Agent Panel Routes

| Route | Method | Response | Handler | Consumer |
|-------|--------|----------|---------|----------|
| `/api/agent/findings` | GET | JSON: tail of agent_findings.jsonl | `Handler.do_GET` (line 1693) → inline | React CP (AgentPanel) |
| `/api/agent/audit` | GET | JSON: tail of agent_audit.jsonl | `Handler.do_GET` (line 1703) → inline | React CP (AgentPanel) |
| `/api/agent/llm_requests` | GET | JSON: tail of agent_llm_requests.jsonl | `Handler.do_GET` (line 1713) → inline | React CP (AgentPanel) |
| `/api/agent/synthesize` | POST | JSON: agent findings synthesis | `Handler.do_POST` (line 1952) → `agent.findings_synthesizer.synthesize_finding()` | React CP |

## 5. Health Check Route (separate server)

| Route | Method | Response | Port | Source |
|-------|--------|----------|------|--------|
| (health endpoint) | GET | (not analyzed) | 8788 | `maintenance.health_checker` command via `src/monitoring/health_checker.py` |

---

## 6. Route Summary

| Category | Count |
|----------|-------|
| HTML Pages | 3 (`/`, `/dashboard`, `/ui_kits/*/index.html`) |
| Control Plane API (GET) | 9 |
| Control Plane API (POST) | 4 |
| Trading Dashboard API (GET) | 14 |
| Trading Dashboard API (POST) | 5 |
| Agent Panel (GET) | 3 |
| Agent Panel (POST) | 1 |
| Static file serving | Dynamic (`/ui_kits/{path}`) |
| **Total documented routes** | **39+** |