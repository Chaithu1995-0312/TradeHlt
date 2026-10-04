# UI design gaps from live crt_dashboard (2026-09-09)

Clicked every TopBar tab on `http://127.0.0.1:8787/ui_kits/crt_dashboard/` via Playwright. Screenshots: `docs/ui_mocks/live_tabs/01_executive.png` … `08_replay_lab.png`. Text extract: `docs/ui_mocks/live_tabs/tab_report.json`.

## Live chrome (every tab)

- TopBar tabs: Executive · Runtime · Trades · Models · Backtests · System · Intelligence · Replay Lab
- Instrument select + model badge (`CRT v6_2026_05_eur (Live)`) + alert bell (4)
- **Left sidebar IA is richer than TopBar** — groups OVERVIEW / RUNTIME / RESEARCH / MODELS / TRADES / BACKTESTS / SYSTEM with many sub-routes (Feature Explorer, Lineage Graph, Trade Trace, Monte Carlo, …). Several marked **NEW**.
- `Research` page exists in `app.jsx` but is **not** a TopBar tab (only sidebar RESEARCH children).

## Per-tab (what we saw)

| Live tab | Page file | What is on screen | Live vs scaffold (evidence) |
|----------|-----------|-------------------|-----------------------------|
| Executive | page0_executive.jsx | KPIs (+356.42 R hardcoded smell), session equity, opportunity heatmap, 4 alerts, active model | Partial — classic scaffold PnL; alerts look demo |
| Runtime | page1_runtime.jsx | Signal pipeline strip, kill switch SAFE, fusion scores, live signal card, event stream, equity | Partial/live mix — status API used; pipeline chrome dense |
| Trades | page4_trades.jsx | KPIs, sub-tabs Explorer/Trace/Rejections/Session, journal table | Partial — journal empty-ish in excerpt; KPIs echo Executive |
| Models | page3_models.jsx | Gaussian/Zone/RR/TradeNet + Lineage/Drift/Shadow/Promotions; real registry rows + Promote/Explain | Registry live; lineage/drift/shadow still aspirational tabs |
| Backtests | page5_backtests.jsx | Backtest Lab + Walk-Forward / Stress / Monte Carlo | History may live; rich lab tabs often "—" |
| System | page6_system.jsx | Feeds 12/12, jobs, integrity 100%, quick links | **Static scaffold** (survey + identical perfect metrics) |
| Intelligence | page7_intelligence.jsx | Causal graph, sequential patterns, state machine | **Prototype / inventable** |
| Replay Lab | page8_replay.jsx | Candle 15/30 synthetic replay controls | **Synthetic** (N_CANDLES demo) |

## MISSING_IN_DESIGN (live UI we under-specified)

1. **8 TopBar tabs vs our 6 views** — we merged Executive+Runtime → Ops Overview; dropped System/Intelligence/Replay as first-class; never mirrored TopBar 1:1 for LLM nav.
2. **Sidebar mega-menu** — RESEARCH (Feature/Cluster/Seq/Regime/Opportunity), MODELS (Lineage/Drift/Shadow/Promotions), TRADES (Trace/Rejections/Session), BACKTESTS (WF/Stress/MC), SYSTEM (Infra/DQ/Logs/Settings). Design mocks showed flat 6 cards only.
3. **Alert bell + Alerts sub-nav under Runtime** — design put Alerts only inside Trades; live surfaces alerts globally.
4. **Research as first-class domain** — live has full RESEARCH sidebar; our IA buried it under "Research & Backtests".
5. **Sub-route depth on Models/Trades/Backtests** — Promote/Explain exist; Trace/Rejections/Lineage/Drift/Shadow need explicit nodes in `UI_LLM_NAVIGATION`.
6. **Marketing chrome** — "Intelligence. Traceability. Edge." brand tag — design said strip; live still has it.
7. **Dual shell gap** — live dashboard has no Runs/Launcher/Inspector/Workflow/Agent (those live in `ui_kits/control_plane/`). Design assumed one shell; LLM nav must keep both kits as siblings until unified.

## MISSING_IN_LIVE (design we proposed that dashboard lacks)

1. **Runs / Launcher / Inspector / Playbook** — only on control_plane kit (`/ui_kits/control_plane/`), not dashboard TopBar.
2. **Pipeline & Agent** — Workflow Mermaid + Agent findings panel not in crt_dashboard tabs.
3. **Telegram/alert outcome pairing panel** — design Trades&Alerts mock; live has alert list + journal but not explicit alert↔fill outcome join UI.
4. **Unified kill-switch always-on chrome** — Runtime has kill switch; not equally prominent on every tab chrome (model badge yes).
5. **Fail-closed empty states** — Executive still shows +356.42 style pulse numbers (design forbid silent hardcoded PnL).
6. **Replay bound to `UnifiedReplayHarness` + `src/charts`** — live Replay is 30 synthetic candles.
7. **Coding-LLM link graph on screen** — no in-UI affordance; only docs (`UI_LLM_NAVIGATION.md`).

## Recommended view_id mapping (for LLM nav)

| live_tab / sidebar | design view_id | kit entry | primary semantic targets |
|--------------------|----------------|-----------|--------------------------|
| Executive + Runtime | ops_overview | page0 + page1 | ControlPlaneDashboardApi, LiveDecisionTelegramAlertEngine |
| Trades (+ Alerts sidebar) | trades_alerts | page4 | ExecutionAlertManager, TelegramAlertTransportBridge |
| Models (+ Promote…) | models | page3 | ActiveModelRegistry, promote APIs |
| Backtests + RESEARCH sidebar | research | page2 + page5 | BacktestMetricsRecomputeOracle, opportunities APIs |
| System | system_health (NEW — was deferred) | page6 | jobs/feeds — mostly scaffold |
| Intelligence | intelligence (NEW — mark inventable) | page7 | no authoritative backend yet |
| Replay Lab | replay (NEW — bind later) | page8 | UnifiedReplayHarness, ChartsApi |
| (control_plane) Runs | runs | App.jsx / Launcher | ControlPlaneHttpServer, JobManager |
| (control_plane) Workflow/Explore/Agent | pipeline_agent | Workflow/Explorer/Agent panels | Agent findings APIs |

## Traversal protocol addendum

1. Start at this gap doc or `docs/UI_LLM_NAVIGATION.md`.
2. If user is on **dashboard** URL → use live_tab ids above.
3. If user needs **run/launch** → switch kit to `ui_kits/control_plane/` (not a TopBar tab).
4. Resolve semantic_name → `docs/CODEBASE_SEMANTIC_NAMES.jsonl` → `src/…`.
5. Treat System / Intelligence / Replay / Lineage / Drift / Shadow as **scaffold** until APIs prove otherwise.

## Assets

- Live shots: `docs/ui_mocks/live_tabs/*.png`
- Prior design mocks: generated ui-mock-01…06 (chat assets; not yet copied into repo)
