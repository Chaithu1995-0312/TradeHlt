> Created: 2026-05-18 · Updated: 2026-05-18 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Fix Dynamic Catalog Loading in React UI (ComboBox "0 options")

## Context

`LauncherPanel.jsx` reads `window.CATALOG` for ComboBox options (`csv`, `instrument`, `config`, `version` fields). In the old embedded HTML (`GET /`), each select was populated by direct JS calls like `loadInstruments()` fetching `/api/instruments` — no `CATALOG` needed. In the React UI kit, only `mockApi.js` sets `window.CATALOG` (hardcoded dev values), but `mockApi.js` is **not loaded** in `index.html`. So `realApi.js` never sets `window.CATALOG`, leaving it `{}` → "0 options" on every ComboBox.

## Fix — 2 files

### 1. `src/control_plane/server.py` — add `GET /catalog` route

In the `do_GET` handler, just before the `/files` route (around line 1635), add:

```python
if path == "/catalog":
    _data_dir   = REPO_ROOT / "data"
    _cfg_dir    = REPO_ROOT / "configs" / "production"
    data_csv    = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in _data_dir.glob("*.csv") if p.is_file()
    )
    data_all    = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in _data_dir.glob("**/*") if p.is_file()
    )
    prod_configs = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in _cfg_dir.glob("*.json")
        if p.is_file() and "_archived_" not in p.name
    )
    prod_versions = [Path(c).stem for c in prod_configs]
    instruments   = dash_api.instruments_payload()["instruments"]
    self._send_json(HTTPStatus.OK, {
        "data_csv":      data_csv,
        "data_all":      data_all,
        "instruments":   instruments,
        "prod_configs":  prod_configs,
        "prod_versions": prod_versions,
    })
    return
```

`Path` is already imported at the top of `server.py`. `dash_api` is in scope via the closure (`create_handler` parameter). `REPO_ROOT` is already a module-level constant.

### 2. `ui_kits/control_plane/realApi.js` — fetch catalog on startup

Add one fetch function and call it in the startup `Promise.all`:

```javascript
async function _fetchCatalog() {
  try {
    const d = await fetch(BASE + "/catalog").then(r => r.json());
    window.CATALOG = d;
    _notify();
  } catch (e) { console.warn("[realApi] fetchCatalog failed:", e.message); }
}
```

Change the startup line (currently line 49):
```javascript
// BEFORE
Promise.all([_fetchCommands(), _fetchRuns(), _fetchDashboard()]).catch(() => {});

// AFTER
Promise.all([_fetchCommands(), _fetchRuns(), _fetchDashboard(), _fetchCatalog()]).catch(() => {});
```

## Verification

1. Restart server: `python src/control_plane/server.py`
2. Open `http://127.0.0.1:8787/` (redirects to React UI)
3. Select any command with a `csv`, `instrument`, `config`, or `version` field
4. ComboBox should show actual files from `data/` and `configs/production/`
5. Check browser console — no `fetchCatalog failed` warning
6. Verify `curl http://localhost:8787/catalog` returns the four arrays

---

# Consolidate Duplicate Control Plane UIs

## Context

`http://127.0.0.1:8787/` serves the **old monolithic HTML** baked into `server.py` as a Python string (`api.ui_html()`). It is the original, single-file vanilla JS UI and has not kept pace with new features (no playbook, no sparklines, no 🧠 Context button, no file uploader).

`http://127.0.0.1:8787/ui_kits/control_plane/` serves `ui_kits/control_plane/index.html` as a static file — the **new React UI kit** that is the actively maintained version and receives all feature work.

They coexist because the React UI was never wired as the default. The `index.html` uses relative script paths (`realApi.js`, `App.jsx`, etc.) so it can only work when served under `/ui_kits/control_plane/`, not at `/` directly. The fix is a simple **redirect**: `GET /` → `302 /ui_kits/control_plane/`.

## Change (one line)

**File:** `src/control_plane/server.py` — line where `path == "/"` is handled (around line 1665):

```python
# BEFORE
if path == "/":
    self._send_html(HTTPStatus.OK, api.ui_html())
    return

# AFTER
if path == "/":
    self.send_response(HTTPStatus.FOUND)          # 302
    self.send_header("Location", "/ui_kits/control_plane/")
    self.send_header("Content-Length", "0")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    return
```

The `ui_html()` method on `ControlPlaneAPI` is **kept intact** — no deletion, minimal diff.

## Verification

1. Restart server: `python src/control_plane/server.py`
2. Open `http://127.0.0.1:8787/` — browser should redirect to `http://127.0.0.1:8787/ui_kits/control_plane/` and show the React UI
3. Confirm all features work: Command Launcher, Run History (📋 🧠 buttons), Run Inspector
4. Confirm `http://127.0.0.1:8787/ui_kits/control_plane/` still works directly (no regression)

---

# Context Report — 🧠 Implementation Plan

## Context

The Control Plane's existing `[📋 Report]` (in the old embedded HTML) covers raw logs + artifacts. The user wants a second, smarter button — **🧠 Context Report** — that extracts only the code that actually ran, sends it to Claude alongside run metadata, and returns structured operational intelligence: root cause, architecture analysis, artifact analysis, and recommended next actions. This is an **Operational Intelligence Engine**, not a chatbot.

---

## Architecture Overview

```
Run History row  →  🧠 button  →  POST /runs/{id}/context/report
                                       ↓
                               code_context_extractor.py
                                   (AST extraction from command script + traceback refs)
                                       ↓
                               context_report.py
                                   (build packet → call Claude API)
                                       ↓
                               ContextModal in React UI
                                   (5-section structured display)
```

---

## Files to Create

### 1. `src/control_plane/code_context_extractor.py`

Stateless module. No `src.*` imports (follows `report_api.py` pattern).

**`extract_code_context(command_line: list[str], stdout: str, stderr: str, repo_root: Path) → list[dict]`**

Steps:
1. Parse `command_line` to find the main Python script path (e.g., `scripts/training/phase5_calibration.py`).
2. AST-parse that file → extract all top-level `def` and `class` blocks as `{file, symbol, code, start_line, end_line}`.
3. Scan `stdout + stderr` for `File "..."` traceback patterns → collect additional referenced files.
4. AST-parse those files → extract only the functions/classes whose line ranges contain a traceback-referenced line.
5. Deduplicate and cap at 8 symbols total (largest first by line count, then traceback refs take priority).
6. Return list: `[{file, symbol, kind, code, start_line}]`

Fallback: if script path not found in `command_line` or AST parse fails, return `[]` (fail-open).

### 2. `src/control_plane/context_report.py`

Follows `RunReportAPI` pattern exactly — stateless class, no `src.*` imports, optional-import guard for `anthropic`.

**`class ContextReportAPI`**

```python
def context_analysis(
    self,
    run: dict,
    logs: dict,
    artifacts: list[dict],
    code_context: list[dict],
) -> dict:  # {"ok": True, "sections": {...}, "model": str} | {"ok": False, "error": str}
```

**Prompt structure** (token budget ~4 500 tokens → use `claude-haiku-4-5-20251001`):
```
SYSTEM: You are an operational intelligence engine for a quantitative trading system.
        Analyze execution context and return structured JSON only.

USER:
=== RUN METADATA ===
command: ...  status: ...  duration: ...  exit_code: ...  args: ...

=== STDOUT TAIL (last 3 000 chars) ===
...

=== STDERR TAIL (last 1 500 chars) ===
...

=== ARTIFACTS ===
path | exists | size
...

=== EXECUTED CODE CONTEXT ===
[file: scripts/training/phase5_calibration.py | symbol: train_model]
```python
def train_model(): ...
```
...

TASK: Return valid JSON with exactly these keys:
  root_cause, architecture_notes, artifact_analysis, recommendations (list of strings)
  Keep each value concise. No preamble.
```

**API call**: Uses `anthropic.Anthropic()` SDK with `ANTHROPIC_API_KEY` from `.env`. Model: `claude-haiku-4-5-20251001`. Max tokens: 1 024. Temperature: 0.1.

Returns:
```json
{
  "ok": true,
  "sections": {
    "root_cause": "...",
    "architecture_notes": "...",
    "artifact_analysis": "...",
    "recommendations": ["...", "..."]
  },
  "model": "claude-haiku-4-5-20251001",
  "code_context_count": 3
}
```

---

## Files to Modify

### 3. `src/control_plane/server.py`

Add two routes after the existing `report/llm` routes:

```
POST /runs/{run_id}/context/report
```

Handler flow:
1. Load run record → read stdout/stderr from log paths → load artifact list.
2. Call `code_context_extractor.extract_code_context(run["command_line"], stdout, stderr, _REPO_ROOT)`.
3. Call `ContextReportAPI().context_analysis(run, logs, artifacts, code_context)`.
4. Return JSON response.

Instantiate `ContextReportAPI` once in `ControlPlaneServer.__init__` alongside `RunReportAPI`.

### 4. `ui_kits/control_plane/LauncherPanel.jsx`

Add `Actions` column to Run History table. Each row gets two icon buttons:

```jsx
<td style={tdAct}>
  <span title="Report" style={iconBtn} onClick={e => { e.stopPropagation(); onReport(r.run_id); }}>📋</span>
  <span title="Context Report" style={iconBtn} onClick={e => { e.stopPropagation(); onContext(r.run_id); }}>🧠</span>
</td>
```

Props added: `onReport(run_id)`, `onContext(run_id)`.

### 5. `ui_kits/control_plane/InspectorPanel.jsx`

Add an "Actions" row after `RunSummary` (before Resolved Command):

```jsx
<div style={{ display: "flex", gap: 8, margin: "10px 0" }}>
  <Button onClick={() => onReport(run.run_id)}>📋 Report</Button>
  <Button onClick={() => onContext(run.run_id)} style={{ background: "#1a2e4a" }}>🧠 Context</Button>
</div>
```

Props added: `onReport`, `onContext`.

Add new `ContextModal` component at bottom of file:

```jsx
function ContextModal({ runId, onClose }) { ... }
```

Sections rendered:
- **Execution Summary** — from existing run data (status, duration, command)
- **Root Cause** — `sections.root_cause`
- **Architecture Notes** — `sections.architecture_notes`
- **Artifact Analysis** — `sections.artifact_analysis`
- **Recommendations** — `sections.recommendations` (ordered list)
- **Code Context** — collapsible: file path + symbol + code block for each extracted symbol

Loading state: spinner with "Analyzing execution context…"
Error state: red error box with `error` message.

Modal uses same pattern as `page3_models.jsx` CompareModal:
- Fixed position, centered, `z-index: 301`
- Dark backdrop overlay `rgba(0,0,0,0.55)` at `z-index: 300`
- Max height: `85vh`, scrollable body
- Header: `🧠 Context Report — {run_id.slice(0,8)}`

### 6. `ui_kits/control_plane/realApi.js`

Add one method:

```javascript
async contextReport(run_id) {
  const d = await fetch(BASE + `/runs/${run_id}/context/report`, { method: "POST" }).then(r => r.json());
  return d;
},
```

### 7. `ui_kits/control_plane/App.jsx`

Add state + handlers:
```javascript
const [contextRunId, setContextRunId] = useState(null);
const [contextData, setContextData] = useState(null);
const [contextLoading, setContextLoading] = useState(false);

async function handleContext(run_id) {
  setContextRunId(run_id);
  setContextData(null);
  setContextLoading(true);
  const d = await mockApi.contextReport(run_id);
  setContextData(d);
  setContextLoading(false);
}
```

Pass `onContext={handleContext}` to `LauncherPanel` and `InspectorPanel`.
Render `<ContextModal>` when `contextRunId != null`.

---

## Verification

1. Start control plane: `python src/control_plane/server.py`
2. Run any command from the Launcher (e.g., a training or validation command)
3. In Run History, click `🧠` button on a completed run row
4. Modal should appear with spinner → then 5 sections populated by Claude
5. Verify code context shows ≥1 extracted symbol from the command's script
6. Test on a failed run: root_cause section should identify the error
7. Test with `ANTHROPIC_API_KEY` missing: modal shows `{"ok": false, "error": "ANTHROPIC_API_KEY not set..."}`
8. Check `server.py` route responds correctly: `curl -X POST http://localhost:8787/runs/{id}/context/report`

---

## Non-Goals (Phase 2 — not in scope now)

- coverage.py subprocess wrapping (deferred — heuristic extraction covers 80% of value)
- Historical run comparison / recurring failure detection
- Streaming Claude response (single-shot for now)
- Caching context reports to disk
