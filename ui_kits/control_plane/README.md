# Control Plane UI Kit

High-fidelity React/JSX recreation of Tradelatest's **CRT Web Control Plane** (`http://localhost:8787`), faithfully reproducing the inline-HTML SPA in `src/control_plane/server.py`.

## What's recreated
- Header strap with Dashboard / Help buttons
- Three-column layout: Playbook / Launcher / Inspector
- Run History table with click-to-inspect rows
- Run Inspector with monitored fields, stdout/stderr, artifacts
- Monitoring Dashboard view (toggle from header)
- Help Tour overlay
- Status pills, dashed-border helper boxes, workflow chips

## What's stubbed
- Real backend calls — replaced by an in-memory `mockApi` that mimics the JSON shapes of the original `/commands /runs /commands/:id/runs /runs/:id/logs` endpoints.
- Auto-poll (the original re-fetches every 2s); the mock simulates a single run lifecycle from queued → running → succeeded.

## Components
- `App.jsx` — top-level layout + view switching (runs ↔ dashboard)
- `Header.jsx` — page header
- `PlaybookPanel.jsx` — workflow stages with completion chips
- `LauncherPanel.jsx` — category/command select, dynamic args, CLI preview, history table
- `InspectorPanel.jsx` — run meta, monitored fields, stdout/stderr, artifacts
- `DashboardView.jsx` — monitoring grid of dash cards
- `Tour.jsx` — multi-step tour overlay
- `Primitives.jsx` — `<Panel>`, `<StatusPill>`, `<Chip>`, `<Helper>`, `<Pre>`
- `mockApi.js` — fake backend matching the real payload shapes

Open `index.html` to view.
