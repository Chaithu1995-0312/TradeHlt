# UI LLM Navigation — TradeHlt / Tradelatest

> Machine- and human-readable **UI ↔ code link graph** for coding LLMs.
> **Do not** treat this as product UI source. Kits under `ui_kits/` are the UI surfaces; backends live under `src/`.
> Mockup ids (`ui-mock-01` … `ui-mock-06`) are **labels only** — do not regenerate mockup images from this doc.

Companion machine graph: [`UI_LLM_NAVIGATION.jsonl`](UI_LLM_NAVIGATION.jsonl) (one node or edge per line).

---

## Purpose

How a coding LLM should traverse **UI ↔ code** without guessing:

1. Start here (`docs/UI_LLM_NAVIGATION.md`) or the JSONL graph.
2. Pick a unified-shell `view_id`.
3. Open the listed kit entry file(s) and component tree (relative paths are real and verified).
4. Resolve each `semantic_name` in [`CODEBASE_SEMANTIC_NAMES.jsonl`](CODEBASE_SEMANTIC_NAMES.jsonl) → open the `path` field.
5. Confirm HTTP contracts in [`analysis/UI_ROUTE_MAP.md`](analysis/UI_ROUTE_MAP.md); component inventory in [`analysis/UI_COMPONENT_MAP.md`](analysis/UI_COMPONENT_MAP.md).
6. Open matching tests under `tests/test_control_plane_*.py` (and live/alert tests when the bind target is runtime).

**Unified shell IA (target product framing):** six views that stitch two kits — `ui_kits/control_plane/` (Runs + Pipeline/Agent) and `ui_kits/crt_dashboard/` (Ops / Trades / Models / Research). Kit view ids today differ (`runs|dashboard|workflow|explore|agent` vs page tabs `Executive|Runtime|…`); this map uses the **unified** ids below.

**Mockup id convention (design labels, not files):**

| mockup | view_id |
|--------|---------|
| ui-mock-01 | ops_overview |
| ui-mock-02 | runs |
| ui-mock-03 | trades_alerts |
| ui-mock-04 | models |
| ui-mock-05 | research |
| ui-mock-06 | pipeline_agent |

**Research-lane extension (2026-09-14):** `sealed_contracts` — Sealed-Contract Kit UX (`research.mc_kit` / F-086…F-097). Design-only today; not a crt_dashboard TopBar tab yet. Design: [`research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md`](research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md).

---

## Route table

| view_id | label | kit path(s) | entry component | mockup id | primary semantic_names | primary APIs / backends |
|---------|-------|-------------|-----------------|-----------|------------------------|-------------------------|
| `runs` | Runs / Launcher | `ui_kits/control_plane/` | `ui_kits/control_plane/App.jsx` (`view==="runs"`) | ui-mock-02 | `ControlPlaneHttpServer`, `ControlPlaneCommandSpecRegistryCatalog`, `ControlPlaneJobManager`, `ControlPlaneControlPlaneDashboardMonitor`, `RunReportAPIExcelGeneration`, `ContextReportAPIClaudePowered` | `GET /commands`, `GET /runs`, `GET /runs/{id}`, `…/logs|artifacts|monitors`, `POST /commands/{id}/runs`, `POST …/stop`, `GET …/report/excel`, `POST …/report/llm`, `POST …/context/report` via `:8787` |
| `ops_overview` | Ops Overview | `ui_kits/crt_dashboard/` | `ui_kits/crt_dashboard/app.jsx` → `ExecutivePage` + `RuntimePage` | ui-mock-01 | `ControlPlaneDashboardApi`, `ControlPlaneHttpServer`, `HealthCheckerLightweightStdlib` | `GET /api/status`, `GET /api/instruments`, `GET /api/equity_curve`, `GET /api/opportunity_stats`, `GET /api/trades` (30s poll) |
| `trades_alerts` | Trades & Alerts | `ui_kits/crt_dashboard/` (+ alert semantics in runtime/exec) | `page4_trades.jsx` (+ Runtime `Alerts` sub-nav; Executive alert strip) | ui-mock-03 | `ControlPlaneDashboardApi`, `LiveDecisionTelegramAlertEngine`, `TelegramAlertTransportBridge`, `ExecutionAlertManager` | `GET /api/trades`, `GET /api/equity_curve`, `GET /api/opportunities*`; alert send path is engine/bridge (not a dedicated UI POST yet) |
| `models` | Models | `ui_kits/crt_dashboard/` | `page3_models.jsx` | ui-mock-04 | `ControlPlaneDashboardApi`, `ActiveModelRegistry` | `GET /api/models`, `/api/zone_gate_models`, `/api/rr_models`, `/api/tradenet_models`, `POST /api/promote_*`, `POST /api/explain_model` |
| `research` | Research | `ui_kits/crt_dashboard/` | `page2_research.jsx` + `page5_backtests.jsx` (+ Intelligence/Replay Lab tabs) | ui-mock-05 | `ControlPlaneDashboardApi`, `ReplayMemoryEngine`, `BacktestMetricsRecomputeOracle` | `GET /api/opportunity_analytics`, `GET /api/scan_jobs`, `GET /api/backtest_history`, `GET /api/opportunities` |
| `pipeline_agent` | Pipeline & Agent | `ui_kits/control_plane/` | `App.jsx` views `workflow` \| `explore` \| `agent` | ui-mock-06 | `ControlPlaneCommandSpecRegistryCatalog`, `ControlPlaneFlowResolutionArchitecturalGraph`, `ControlPlaneASTBasedExtractionContext`, `AgentPostRunFindingsGroqLlama`, `InRepoAgentCore`, `AgentGrokAgenticAIInteractiveREPL` | Workflow/Explore: registry + flow context; Agent: `GET /api/agent/findings|audit|llm_requests`, `POST /api/agent/synthesize` |

Static kit URLs (server): `/ui_kits/control_plane/`, `/ui_kits/crt_dashboard/` (see `UI_ROUTE_MAP.md`). Root `/` → control plane kit.

---

## Per-view sections

### 1. `runs` — Runs / Launcher (ui-mock-02)

**Screen purpose:** Launch control-plane commands, track runs, inspect monitors/artifacts/logs, follow the playbook checklist.

**Component tree (relative links):**

- [`ui_kits/control_plane/App.jsx`](../ui_kits/control_plane/App.jsx) — root state + view router
  - [`Header.jsx`](../ui_kits/control_plane/Header.jsx) — Runs / Dashboard / Workflow / Explore / Agent
  - [`PlaybookPanel.jsx`](../ui_kits/control_plane/PlaybookPanel.jsx)
  - [`LauncherPanel.jsx`](../ui_kits/control_plane/LauncherPanel.jsx) — uses [`ComboBox.jsx`](../ui_kits/control_plane/ComboBox.jsx), [`FileUploader.jsx`](../ui_kits/control_plane/FileUploader.jsx)
  - [`InspectorPanel.jsx`](../ui_kits/control_plane/InspectorPanel.jsx) — uses [`Sparkline.jsx`](../ui_kits/control_plane/Sparkline.jsx)
  - [`Tour.jsx`](../ui_kits/control_plane/Tour.jsx), [`Primitives.jsx`](../ui_kits/control_plane/Primitives.jsx)
- Data adapters: [`realApi.js`](../ui_kits/control_plane/realApi.js) (**live**, loaded by `index.html`), [`mockApi.js`](../ui_kits/control_plane/mockApi.js) (**dev-only scaffold**)

**Outbound links (explicit):**

- Header → `dashboard` (CP monitoring grid — related to ops, not the crt kit)
- Header → `workflow` / `explore` / `agent` → unified `pipeline_agent`
- Inspector / Launcher report → Excel/LLM report endpoints
- Product IA: nav edge to `ops_overview`, `pipeline_agent`

**Bind targets (catalog):**

| path | semantic_name |
|------|---------------|
| `src/control_plane/server.py` | `ControlPlaneHttpServer` |
| `src/control_plane/registry.py` | `ControlPlaneCommandSpecRegistryCatalog` |
| `src/control_plane/jobs.py` | `ControlPlaneJobManager` |
| `src/control_plane/monitors.py` | `ControlPlaneControlPlaneDashboardMonitor` |
| `src/control_plane/report_api.py` | `RunReportAPIExcelGeneration` |
| `src/control_plane/context_report.py` | `ContextReportAPIClaudePowered` |
| `configs/control_plane/monitors.json` | `ControlPlaneConfigMonitorsJson` |

**Scaffold vs live:** **Live** when served behind `:8787` with `realApi.js`. `App.jsx` still names `mockApi` globally; production `index.html` loads `realApi.js` which exposes the same `mockApi` symbol. Survey: `mockApi.js` = DEV-ONLY (`UI_DRIFT_REPORT.md`).

**Tests:** `tests/test_control_plane_api.py` (`TestTestsControlPlaneApi`), `tests/test_control_plane_jobs.py`, `tests/test_control_plane_registry.py`, `tests/test_control_plane_tutorial.py`.

---

### 2. `ops_overview` — Ops Overview (ui-mock-01)

**Screen purpose:** Executive pulse + live runtime health (instrument-scoped status, equity, kill-switch, opportunity stats).

**Component tree:**

- [`ui_kits/crt_dashboard/app.jsx`](../ui_kits/crt_dashboard/app.jsx) — `CrtDashboard` store + poll
  - [`shared.jsx`](../ui_kits/crt_dashboard/shared.jsx) — `TopBar`, `SidebarNew`, `Kpi`, …
  - [`page0_executive.jsx`](../ui_kits/crt_dashboard/page0_executive.jsx) — `ExecutivePage`
  - [`page1_runtime.jsx`](../ui_kits/crt_dashboard/page1_runtime.jsx) — `RuntimePage` (kill-switch KPI)
  - [`charts.jsx`](../ui_kits/crt_dashboard/charts.jsx)
- Fetch surface: [`apiClient.js`](../ui_kits/crt_dashboard/apiClient.js); scaffold globals: [`data.js`](../ui_kits/crt_dashboard/data.js)

**Outbound links:** TopBar/Sidebar → Models, Trades, Research/Backtests, System, Intelligence, Replay Lab; product edges to `trades_alerts`, `models`, `research`, and back to `runs` / control plane.

**Bind targets:**

| path | semantic_name |
|------|---------------|
| `src/control_plane/dashboard_api.py` | `ControlPlaneDashboardApi` |
| `src/control_plane/server.py` | `ControlPlaneHttpServer` |
| `src/monitoring/health_checker.py` | `HealthCheckerLightweightStdlib` |

**Scaffold vs live:** **Hybrid.** Status / instruments / equity / trades / opp stats load live via `ApiClient` (30s refresh). Executive alert list and some KPI deltas still read `window.ALERTS` / hard-coded fallbacks from `data.js` (**scaffold**). `realData.js` = phased-out legacy mount.

---

### 3. `trades_alerts` — Trades & Alerts (ui-mock-03)

**Screen purpose:** Trade journal + equity; surface alert/telegram semantics for human-in-the-loop live decisions.

**Component tree:**

- [`page4_trades.jsx`](../ui_kits/crt_dashboard/page4_trades.jsx) — `TradesPage`
- Runtime sidebar sub-item `Alerts` (mapped in `SidebarNew` / `SIDEBAR_PAGE_MAP` → Runtime page)
- Executive alert strip in [`page0_executive.jsx`](../ui_kits/crt_dashboard/page0_executive.jsx) (`window.ALERTS`)
- Shared chrome: [`shared.jsx`](../ui_kits/crt_dashboard/shared.jsx), charts in [`charts.jsx`](../ui_kits/crt_dashboard/charts.jsx)

**Outbound links:** → `ops_overview` (status), → `models` (attribution), → `research` (opportunity analytics), → `runs` for replay/backtest jobs.

**Bind targets:**

| path | semantic_name |
|------|---------------|
| `src/control_plane/dashboard_api.py` | `ControlPlaneDashboardApi` |
| `src/engines/live_engine.py` | `LiveDecisionTelegramAlertEngine` |
| `src/live/telegram_bridge.py` | `TelegramAlertTransportBridge` |
| `src/execution/alert_manager.py` | `ExecutionAlertManager` |

**Scaffold vs live:** Trade table / equity **live** (`/api/trades`, `/api/equity_curve`). On-screen alert feed largely **scaffold** (`window.ALERTS`); Telegram send path is **live backend** outside the React kit. Rejection rows in trades page include scaffold examples (e.g. “Kill Switch Active”).

**Tests:** `tests/test_live_integration.py` (`TestTelegramBridge`, …), `tests/test_execution_loop.py` (alert send).

---

### 4. `models` — Models (ui-mock-04)

**Screen purpose:** Four model registries (Gaussian, Zone Gate, RR Miner, TradeNet) with promote + explain actions.

**Component tree:**

- [`page3_models.jsx`](../ui_kits/crt_dashboard/page3_models.jsx) — `ModelsPage` (+ compare modal)
- Store props from [`app.jsx`](../ui_kits/crt_dashboard/app.jsx) (`models`, `zoneModels`, `rrModels`, `tradenetModels`, setters)
- Sidebar Promotions / Lineage / Drift / ShadowCompare map back to Models page

**Outbound links:** → `research` (backtests / calibration), → `ops_overview` (active model pill), → `pipeline_agent` (promotion.manager / training commands).

**Bind targets:**

| path | semantic_name |
|------|---------------|
| `src/control_plane/dashboard_api.py` | `ControlPlaneDashboardApi` |
| `src/core/model_registry.py` | `ActiveModelRegistry` |

**Scaffold vs live:** Registry lists + promote/explain **live** (`POST /api/promote_model|promote_zone_gate|promote_rr|promote_tradenet`, `POST /api/explain_model`). Some lineage/timeline chrome may still mix scaffold copy.

**Tests:** `tests/test_gaussian_update_pipeline.py` (promote paths), registry-related control-plane tests.

---

### 5. `research` — Research (ui-mock-05)

**Screen purpose:** Feature / opportunity research surfaces plus backtest calibration history; adjacent Intelligence + Replay Lab tabs.

**Component tree:**

- [`page2_research.jsx`](../ui_kits/crt_dashboard/page2_research.jsx) — `ResearchPage`
- [`page5_backtests.jsx`](../ui_kits/crt_dashboard/page5_backtests.jsx) — `BacktestsPage`
- Related tabs: [`page7_intelligence.jsx`](../ui_kits/crt_dashboard/page7_intelligence.jsx), [`page8_replay.jsx`](../ui_kits/crt_dashboard/page8_replay.jsx)
- Charts: [`charts.jsx`](../ui_kits/crt_dashboard/charts.jsx)

**Outbound links:** → `models` (promote after calibration), → `runs` / `pipeline_agent` (launch backtest/replay commands), → `trades_alerts`.

**Bind targets:**

| path | semantic_name |
|------|---------------|
| `src/control_plane/dashboard_api.py` | `ControlPlaneDashboardApi` |
| `src/replay/replay_memory_engine.py` | `ReplayMemoryEngine` |
| `src/analytics/metrics_oracle.py` | `BacktestMetricsRecomputeOracle` |

**Scaffold vs live:** `backtest_history`, `opportunity_analytics`, `scan_jobs` **live** via app store. Many Research sidebar sub-navs (Clusters, Regime Map, …) are **IA scaffold** (map onto Research/Intelligence pages; limited dedicated pages).

**Outbound (2026-09-14):** Research sidebar / IA → **`sealed_contracts`** (Sealed-Contract Kit lane: Registry, Step-0 parity gate, Spec+detector composer, Primitives map). Design doc only until `ui_kits` implements the sub-nav; coding LLM should resolve design → planned `src/research/mc_kit/*` → existing drivers `src/research/mother_range/driver.py`, `src/research/sujan_crt/driver.py`, `src/research/evidence/*.py`.


**Tests:** `tests/test_unified_replay_harness.py`, `tests/test_workflow_dag_coverage.py` (replay/backtest stage).

---


### 5b. `sealed_contracts` — Sealed Contracts / MC Kit (design 2026-09-14)

**Screen purpose:** Operate the sealed-contract research lane (`research.mc_kit`): registry of MC contracts (F-086…F-097 frontier), Step-0 byte-identity baseline gate on reviewed `XAUUSD_M15`, Spec+detector composer with **8 explicit difference parameters**, and kit primitives map. **No economic authority** (`economic_claims_allowed=false`).

**Status:** DESIGN ONLY — UX doc exists; no dedicated jsx page yet. Place under crt_dashboard **Research** sub-nav; optional Control Plane Launcher/Inspector for Step-0 jobs.

**Design / component tree (links):**

- [`docs/research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md`](research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md) — four screens IA + UX rules
- Kit chrome reuse: [`page2_research.jsx`](../ui_kits/crt_dashboard/page2_research.jsx), [`page5_backtests.jsx`](../ui_kits/crt_dashboard/page5_backtests.jsx), [`shared.jsx`](../ui_kits/crt_dashboard/shared.jsx)
- Optional jobs: [`ui_kits/control_plane/LauncherPanel.jsx`](../ui_kits/control_plane/LauncherPanel.jsx), [`InspectorPanel.jsx`](../ui_kits/control_plane/InspectorPanel.jsx)

**Screens (design ids):** `registry` | `step0` | `composer` | `primitives`

**Outbound links (explicit):**

- ← `research` (parent Research IA)
- → `runs` / `pipeline_agent` (optional Step-0 / migrate command jobs)
- → planned `src/research/mc_kit/` modules: `bars`, `trade`, `stats`, `splits`, `controls`, `gate`, `artifacts`, `spec`
- → existing drivers (pre-migration): `src/research/mother_range/driver.py`, `src/research/sujan_crt/driver.py`, `src/research/evidence/{asymmetry_contract,magnitude_prior,rnet_overlay,mother_range_prior,visual_crt_prior}.py`
- → readiness artifacts: `docs/research-readiness/` (Step-0 byte-compare targets)

**Bind targets (planned + reuse; resolve semantic_name in catalog when present):**

| path | role |
|------|------|
| `docs/research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md` | UX source of truth |
| `src/research/mc_kit/` (planned) | sealed-contract primitives |
| `src/research/mother_range/driver.py` | trade-contract exemplar |
| `src/research/sujan_crt/driver.py` | trade-contract exemplar |
| `src/research/evidence/*.py` | prior-contract exemplars |
| `src/research/measurement/forward_walk.py` | walk + AdverseFill reuse |
| `src/research/costs.py` | ComponentCostModel / planned `xau_measured_cost_model()` |
| `docs/research-readiness/*` | committed artifact baselines |

**Scaffold vs live:** UI **design-only**. Backend kit **not built**. Step-0 / migrate / composer are planned flows. Difference chips (gross|net, zero_risk, volume, sha, split, verdict vocab, finalize_run, JSON opts) must stay explicit — never silent unify.

**Tests (when kit lands):** planned `tests/research/test_mc_kit.py`; existing prior/mother_range/sujan tests remain parity floor.

### 6. `pipeline_agent` — Pipeline & Agent (ui-mock-06)

**Screen purpose:** Mermaid workflow DAG, code/flow explorer, and agent findings/audit/synthesize driver UI.

**Component tree:**

- [`App.jsx`](../ui_kits/control_plane/App.jsx) when `view` ∈ {`workflow`,`explore`,`agent`}
  - [`WorkflowPanel.jsx`](../ui_kits/control_plane/WorkflowPanel.jsx) — node → command id; can open Explore flow
  - [`ExplorerPanel.jsx`](../ui_kits/control_plane/ExplorerPanel.jsx) — flows / modules / docs+code context
  - [`AgentPanel.jsx`](../ui_kits/control_plane/AgentPanel.jsx) — findings / audit / LLM request tails + synthesize
- Shared: [`Header.jsx`](../ui_kits/control_plane/Header.jsx), [`Primitives.jsx`](../ui_kits/control_plane/Primitives.jsx), [`realApi.js`](../ui_kits/control_plane/realApi.js)

**Outbound links:** Workflow node → command context / run; Workflow “Research|AI Agent|Telemetry” → Explore flow; Explore → back to Runs for execution; Agent → findings over past runs (`runs`).

**Bind targets:**

| path | semantic_name |
|------|---------------|
| `src/control_plane/registry.py` | `ControlPlaneCommandSpecRegistryCatalog` |
| `src/control_plane/dot_graph_context.py` | `ControlPlaneFlowResolutionArchitecturalGraph` |
| `src/control_plane/code_context_extractor.py` | `ControlPlaneASTBasedExtractionContext` |
| `src/agent/findings_synthesizer.py` | `AgentPostRunFindingsGroqLlama` |
| `src/agent/agent_core.py` | `InRepoAgentCore` |
| `src/agent/cli.py` | `AgentGrokAgenticAIInteractiveREPL` |
| `src/control_plane/server.py` | `ControlPlaneHttpServer` |

**Scaffold vs live:** Workflow diagram is **static Mermaid** wired to real command ids (live catalog). Explore/Agent panels **live** against server agent + flow endpoints when `realApi.js` is active.

---

## Global chrome

Shared controls that span crt_dashboard pages (and should remain consistent in any unified shell):

| Control | Files | Semantics / backends | Notes |
|---------|-------|----------------------|-------|
| **Instrument selector** | `ui_kits/crt_dashboard/shared.jsx` (`TopBar`), state in `app.jsx` | `ControlPlaneDashboardApi` ← `GET /api/instruments`; persists `localStorage.crt_instrument` | Live list; defaults EURUSD |
| **Kill-switch** | Displayed on `page1_runtime.jsx` from `status.kill_switch`; state file cited in archaeology as `logs/kill_switch_state.json` via `TradingDashboardAPI.status_payload()` | `ControlPlaneDashboardApi` (+ Ultron/live-rail kill semantics in tests) | **Live read** from `/api/status`; not a TopBar toggle today |
| **Active model pill** | `TopBar` in `shared.jsx` (`status.active_model_version`) | `ControlPlaneDashboardApi`, `ActiveModelRegistry` | Live per instrument |
| **CP header stage strip** | `ui_kits/control_plane/Header.jsx` | Stages mirror `ControlPlaneCommandSpecRegistryCatalog` / `WORKFLOW_STAGE_ORDER` | Chrome for pipeline awareness |

Control-plane kit has **no** instrument/kill-switch chrome; trading ops chrome lives in crt_dashboard `TopBar` / Runtime KPIs.

---

## Traversal protocol for coding LLMs

1. Open **`docs/UI_LLM_NAVIGATION.md`** (this file) or stream **`docs/UI_LLM_NAVIGATION.jsonl`**.
2. Choose a **`view_id`** from the route table (or follow a `rel:"nav"` edge).
3. Open the **kit entry** path (`entry` / `renders` edges) and walk the component tree links.
4. For each bind target, take **`semantic_name`** → grep/filter [`docs/CODEBASE_SEMANTIC_NAMES.jsonl`](CODEBASE_SEMANTIC_NAMES.jsonl) → open catalog `path`.
5. Confirm HTTP method/route in [`docs/analysis/UI_ROUTE_MAP.md`](analysis/UI_ROUTE_MAP.md); component purpose in [`docs/analysis/UI_COMPONENT_MAP.md`](analysis/UI_COMPONENT_MAP.md).
6. Open **tests** named in the per-view section (prefer `tests/test_control_plane_*.py`, live/alert/promote tests as applicable).
7. Respect **scaffold vs live**: prefer `realApi.js` / `apiClient.js` paths for production behavior; treat `data.js` / `mockApi.js` / hard-coded KPI fallbacks as non-authoritative UI fixtures.
8. Do **not** regenerate mockup images; use `mockup` ids only as cross-references to existing design artifacts.

---

## Related maps


- [`research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md`](research/ui/MC_KIT_SEALED_CONTRACT_UIUX.md) — Sealed-Contract Kit UI/UX (`view_id=sealed_contracts`)

| Doc | Role |
|-----|------|
| [`CODEBASE_NAVIGATION.md`](CODEBASE_NAVIGATION.md) | Repo atlas; points at `src/control_plane/`, `src/ui/` (empty/dead), scripts |
| [`CODEBASE_SEMANTIC_NAMES.jsonl`](CODEBASE_SEMANTIC_NAMES.jsonl) / [`.md`](CODEBASE_SEMANTIC_NAMES.md) | Canonical `semantic_name` ↔ `path` catalog |
| [`analysis/UI_ROUTE_MAP.md`](analysis/UI_ROUTE_MAP.md) | HTTP routes for CP + trading dashboard + agent |
| [`analysis/UI_COMPONENT_MAP.md`](analysis/UI_COMPONENT_MAP.md) | Component inventory (embedded + React kits) |
| [`analysis/UI_ARCHAEOLOGY.md`](analysis/UI_ARCHAEOLOGY.md) | Discovery narrative |
| [`analysis/UI_DRIFT_REPORT.md`](analysis/UI_DRIFT_REPORT.md) | Duplicates, scaffold vs live, dead `src/ui/` |
| [`analysis/UI_DEPENDENCY_GRAPH.md`](analysis/UI_DEPENDENCY_GRAPH.md) | UI ↔ files/APIs graph |
| [`analysis/UI_EVIDENCE_INDEX.md`](analysis/UI_EVIDENCE_INDEX.md) | Evidence pointers (e.g. kill_switch_state.json) |

---

## Sample traversal (`runs`)

1. `view_id=runs` → mockup `ui-mock-02`.
2. Open `ui_kits/control_plane/App.jsx` → branch `view === "runs"` renders Playbook + Launcher + Inspector.
3. Open `ui_kits/control_plane/LauncherPanel.jsx` → `onRun` → `mockApi.createRun` (provided by `realApi.js`).
4. Resolve `ControlPlaneHttpServer` in `CODEBASE_SEMANTIC_NAMES.jsonl` → `src/control_plane/server.py`.
5. Resolve `ControlPlaneCommandSpecRegistryCatalog` → `src/control_plane/registry.py`; `ControlPlaneJobManager` → `src/control_plane/jobs.py`.
6. Match routes in `UI_ROUTE_MAP.md`: `POST /commands/{command_id}/runs`, `GET /runs/{run_id}/monitors`, …
7. Run/read `tests/test_control_plane_api.py` (`test_api_run_lifecycle_and_artifacts`, `test_ui_route_returns_html`).

## Live dashboard tab map (2026-09-09)

Clicked TopBar on `/ui_kits/crt_dashboard/`. Gap analysis: [UI_DESIGN_GAP_FROM_LIVE.md](UI_DESIGN_GAP_FROM_LIVE.md). Shots: [ui_mocks/live_tabs/](ui_mocks/live_tabs/).

| live_tab | page file | design view_id | status |
|----------|-----------|----------------|--------|
| Executive | page0_executive.jsx | ops_overview | partial / scaffold KPIs |
| Runtime | page1_runtime.jsx | ops_overview | partial live |
| Trades | page4_trades.jsx | trades_alerts | partial |
| Models | page3_models.jsx | models | registry live; lineage/drift/shadow scaffold |
| Backtests | page5_backtests.jsx | research | partial |
| System | page6_system.jsx | system_health (new) | scaffold |
| Intelligence | page7_intelligence.jsx | intelligence (new) | inventable |
| Replay Lab | page8_replay.jsx | replay (new) | synthetic |
| *(sidebar RESEARCH only)* | page2_research.jsx | research | not in TopBar |
| *(design) Sealed Contracts* | — (Research sub-nav; no jsx yet) | sealed_contracts | design-only 2026-09-14 |
| *(other kit)* Runs… | control_plane/* | runs / pipeline_agent | not on dashboard TopBar |
