# UI design plan — codebase closure + run_id tracing (2026-09-14)

> Builds **on existing UI kits** (`ui_kits/control_plane`, `ui_kits/crt_dashboard`) + control-plane APIs.
> Goal: user can get **full closure** on (a) codebase intent/wiring and (b) run outputs, always keyed by **run_id**.
> Does **not** introduce a new SPA stack (no Vite/Next). Stay on React-via-Babel kits + stdlib server.

## 0. Current kit reality (baseline)

| Kit | Entry | Role today | run_id strength |
|-----|-------|------------|-----------------|
| `ui_kits/control_plane/` | `App.jsx` views: `runs`, `dashboard`, `workflow`, `explore`, `agent` | Launcher, history, inspector, playbook, workflow, agent | **Strong** — native `/runs/{id}` |
| `ui_kits/crt_dashboard/` | `app.jsx` pages: Executive, Runtime, Research, Models, Trades, Backtests, System, Intelligence, Replay, **Knowledge** | Ops / research / models chrome | **Partial** — some mappers carry `run_id`; many KPIs still scaffold |
| Embedded HTML in `server.py` | `/` redirects to React CP; `/dashboard` legacy trading HTML | Legacy parallel | Same backend APIs |

Companion docs already: `docs/UI_LLM_NAVIGATION.md`, `docs/UI_DESIGN_GAP_FROM_LIVE.md`, `docs/analysis/UI_ROUTE_MAP.md`.

## 1. Product principle: one Closure key = `run_id`

Every user-visible artifact of a launched job should answer:

1. **What ran?** `command_id`, args, config/version fingerprints  
2. **What came out?** artifacts, monitors, logs, excel/llm reports  
3. **What code/docs explain it?** semantic names + file paths + (optional) knowledge hits  
4. **How do I reopen it?** URL `/ui_kits/control_plane/?run={run_id}` (deep-link — to implement) and/or dashboard “Trace this run”

Persist path (already): `results/{instrument}/{instrument}_{short8}.json` with full hex `run_id` inside.

## 2. Information architecture (recommended — dual kit, one chrome contract)

**Do not merge kits in v1.** Close the dual-shell gap with a shared **RunChip** + deep links.

### Shell A — Control Plane (source of truth for runs)
Enhance existing panels:
- **Runs / Launcher** — already create_run  
- **Inspector** — promote to **Closure Inspector**:
  - Tabs: Overview | Logs | Artifacts | Monitors | Reports | **Code links** | **Knowledge**
  - Overview always shows full `run_id` + short8 + copy button + open-on-disk path
- **Workflow / Agent** — when a step produces a run, stamp `run_id` into the step card

### Shell B — CRT Dashboard (consume run_id, don’t fork job store)
- Add persistent **Run context bar** (below TopBar): selected `run_id` / “Follow latest” / clear  
- Pages that claim live data must show either:
  - bound `run_id`, or  
  - explicit `UNBOUND / SCAFFOLD` badge (System, Intelligence, Replay today)
- **Knowledge** (`page9`) — query results should cite artifact paths + optional `run_id` filter when evidence is run-scoped
- **Trades → Trace** — join journal rows → originating `run_id` when lineage exists; else show gap

### Shared primitive (new small modules in both kits)
- `RunChip.jsx` / `runContext.js` — format, copy, deep-link helper  
- Prefer extending `Primitives.jsx` + `shared.jsx` rather than new design system

## 3. Closure surfaces (what “full closure” means in UI)

| Closure kind | Where | Data source | Acceptance |
|--------------|-------|-------------|------------|
| Run closure | CP Inspector | `/runs/{id}`, logs, artifacts, monitors, report APIs | Can reconstruct command+outputs from UI alone |
| Code closure | CP Inspector “Code links” + Explore | `CODEBASE_SEMANTIC_NAMES.jsonl`, `UI_LLM_NAVIGATION.jsonl`, optional `/catalog` | Click → path; LLM nav graph stays authoritative |
| Output closure | Artifacts list + Excel/LLM report | existing report_api / context_report | Download + inline summary |
| Knowledge closure | Dashboard Knowledge + CP tab | retrieval APIs (verify live routes) | Answer shows evidence class + paths; link to run when present |
| Trace closure | Dashboard Trade Trace / Research | events/jsonl under results; run state JSON | Given run_id, open candle/event slice |

## 4. Phased delivery

### Phase U0 — Doc/contract freeze (no UI code)
- Confirm dual-kit strategy (ask user).  
- Freeze run_id as sole job key in `UI_LLM_NAVIGATION` (add Closure nodes).  
- Refresh route map line numbers only if verified.

### Phase U1 — Control Plane Closure Inspector
- Deep link `?run=`  
- Copy full/short id  
- Artifacts open-in-explorer (optional OS) via existing path fields  
- “Code links” panel: map `command_id` → script path from registry/commands payload

### Phase U2 — Dashboard Run context bar
- Bind selected run across pages  
- Scaffold pages must show UNBOUND badge  
- Knowledge + Trades Trace consume binding

### Phase U3 — End-to-end trace demo
- One golden path: launch known research/backtest command → Inspector closure → Dashboard Trace with same run_id  
- Screenshot pack under `docs/ui_mocks/closure_runid/`

### Phase U4 — (Optional) Unify chrome
- Only if user chooses: shared TopBar wrapper hosting both kits’ routes. Defer; high risk.

## 5. Non-goals
- New frontend build toolchain  
- Replacing embedded HTML immediately (can stay redirected)  
- Inventing live metrics for System/Intelligence/Replay without backend  
- Silent architecture.md rewrites (tracked in companion audit)

## 6. Open decisions (ask before implement)
1. Dual-kit + RunChip (recommended) vs forced single shell now  
2. Whether Knowledge is in Phase U2 critical path  
3. Whether research probes CLIs should appear as first-class Launcher commands (registry) for one-click closure demos  
