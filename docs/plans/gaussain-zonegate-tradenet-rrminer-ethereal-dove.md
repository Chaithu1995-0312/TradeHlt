> Created: 2026-05-19 · Updated: 2026-05-19 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Feature Explorer Audit + Model Registry Tree & Groq Explain

> **Added 2026-05-19 (supersedes earlier Research page plan — that work is DONE)**

---

## Part D — Instrument-scoped Model Groups (TopBar coin filter drives registry view)

### Problem

The Models page shows ALL instruments' run groups simultaneously even when a specific coin is selected in the TopBar. When ETHUSDT is selected, EURUSD runs still appear as group headers — noise the user doesn't want.

### Root cause

`groupModels(list)` in `page3_models.jsx` receives the full unfiltered model list. `selectedInstrument` is already a prop on `ModelsPage` but is not applied when building groups.

### Fix — 1 helper + 4 call-site changes in `page3_models.jsx`

**Add `filterByInstrument()` helper** (insert after `groupModels()` definition, ~line 93):

```js
// Keep models that match selectedInstrument, OR have no instrument tag (legacy)
function filterByInstrument(list) {
  if (!selectedInstrument) return list;
  return list.filter(m => !m.instrument || m.instrument === selectedInstrument);
}
```

**Update 4 `groupModels()` call sites:**

| Before | After |
|--------|-------|
| `groupModels(gaussianModels)` | `groupModels(filterByInstrument(gaussianModels))` |
| `groupModels(zoneGateModels)` | `groupModels(filterByInstrument(zoneGateModels))` |
| `groupModels(rrMinerModels)`  | `groupModels(filterByInstrument(rrMinerModels))`  |
| `groupModels(tradenetMdls)`   | `groupModels(filterByInstrument(tradenetMdls))`   |

### Behaviour after fix

| TopBar | Groups shown |
|--------|-------------|
| ETHUSDT | ETHUSDT runs + Legacy |
| EURUSD  | EURUSD runs + Legacy |

`activeEntry` (footer) and `activeModels` (Compare) are computed from the full unfiltered list and remain unchanged — only the tree-view rendering is scoped.

### File modified

`ui_kits/crt_dashboard/page3_models.jsx` only — no backend changes needed.

### Verification

1. Hard-refresh → Models → Gaussian Models tab
2. TopBar = ETHUSDT → only ETHUSDT run groups visible
3. Switch to EURUSD → only EURUSD run groups visible
4. Legacy group (instrument: null) visible in all cases

---

## Part A — Research/Feature Explorer Audit Fixes

### Findings from log + code audit

| # | Issue | Severity | File | Line |
|---|-------|----------|------|------|
| A1 | `setLiveOutcomes` called but never defined → crashes on "← All Jobs" click | CRITICAL | `page2_research.jsx` | 59 |
| A2 | "Win Rate (TP)" label is wrong — metric is actually `rr_achieved > 0` rate (67.34%), NOT TP hit rate (4.5%). Contradicts the donut chart TP count right next to it | MEDIUM | `page2_research.jsx` | 76, `buildKpis` |
| A3 | Dead `selectedJob` row-click state — claims to switch donut to per-job data but props are all instrument-driven now; donut title still says "📋 {selectedJob.id}" which misleads users | LOW | `page2_research.jsx` | 84–89 |

**Root cause of A2 (confirmed by log sampling):**
- Backend `win = rr > 0` (RR-based win, not outcome-based)
- Frontend averages `(wl.long + wl.short) / 2 = 67.34%`
- TP_HIT count from `outcome_distribution` = 447 = 4.5% — different concept entirely
- A trailing-stop record can have `outcome=SL_HIT` yet `rr_achieved=+0.762` — so wins ≫ TP_HITs

### Fixes

**A1 — Remove undefined `setLiveOutcomes`:**
`page2_research.jsx` line 59: change
```js
onClick={() => { setSelectedJob(null); setLiveOutcomes(null); }}
```
to:
```js
onClick={() => setSelectedJob(null)}
```

**A2 — Rename KPI label and add TP rate:**
In `buildKpis()`: rename `winRateTP` → still kept as key; change display label from `"Win Rate (TP)"` to `"Win Rate (RR>0)"`.
Add a second derivable KPI: `tpHitRate = ((tp/total)*100).toFixed(2)+"%"` — display in the `Kpi` strip replacing the currently `"—"` Profit Factor slot (which has no backend data).

Updated KPI strip layout (5 slots):
1. Total Opportunities
2. Win Rate (RR > 0)  ← renamed from "Win Rate (TP)"
3. TP Hit Rate        ← new, replaces "Profit Factor" stub
4. Avg RR
5. Timeout Rate

**A3 — Remove misleading per-job donut header:**
`page2_research.jsx` lines 84–89: remove the `selectedJob &&` conditional span that shows `"📋 {selectedJob.id} · {selectedJob.inst}"` as donut title — instrument-level donut doesn't change by job click.

---

## Part B — Model Registry: Tree/Collapsible View by Opportunity Run

### Context

Screenshots show flat tables (Gaussian, Zone Gate, RR Miner, TradeNet). The user wants rows grouped by which opportunity scanner run produced the training data.

**Confirmed data link:** Registry entries contain `run_id` (YYYYMMDD_HHMMSS) and `instrument` fields that exactly match `logs/{instrument}/{run_id}/` scanner output directories. Zone Gate models lack `run_id` → fall into "Legacy" bucket.

### Step B1 — Enrich API payloads with `run_id` + `instrument`

**File:** `src/control_plane/dashboard_api.py`

The 4 `*_payload()` methods currently omit `run_id` and `instrument` from mapped output. Add them to the mapping in each method:

**`models_payload()`** (Gaussian):
```python
# Add to the existing dict:
"run_id":     m.get("run_id"),
"instrument": m.get("instrument"),
```

**`zone_gate_models_payload()`**, **`rr_models_payload()`**, **`tradenet_models_payload()`**: same additions — `run_id` and `instrument` fields from registry.

### Step B2 — Frontend: collapsible group rows in each model tab

**File:** `ui_kits/crt_dashboard/page3_models.jsx`

**Approach:** Keep the 4-tab structure. Inside each tab, group `activeModels` array by `(instrument || "—") + "/" + (run_id || "legacy")`. Render a collapsible group header row before each group's model rows.

**State to add:**
```js
const [collapsedGroups, setCollapsedGroups] = React.useState({});
function toggleGroup(key) {
  setCollapsedGroups(prev => ({ ...prev, [key]: !prev[key] }));
}
```

**Grouping logic (inside the tab render, replacing direct `activeModels.map`):**
```js
// Group models by (instrument, run_id)
const groups = {};
activeModels.forEach(m => {
  const key = (m.instrument || "—") + "/" + (m.run_id || "legacy");
  if (!groups[key]) groups[key] = { instrument: m.instrument || "—", run_id: m.run_id || null, models: [] };
  groups[key].models.push(m);
});
const sortedGroupKeys = Object.keys(groups).sort((a, b) => {
  // run_id groups before legacy; newest run first
  if (a.includes("/legacy")) return 1;
  if (b.includes("/legacy")) return -1;
  return b.localeCompare(a);
});
```

**Group header row (rendered before each group's model rows):**
```jsx
<tr className="model-group-header" onClick={() => toggleGroup(key)}>
  <td colSpan={NUM_COLS} style={{ padding:"8px 12px", background:"var(--panel-2)",
      borderLeft:"3px solid var(--accent)", cursor:"pointer", fontSize:12 }}>
    <span style={{ marginRight:8 }}>{collapsedGroups[key] ? "▶" : "▼"}</span>
    <span style={{ color:"var(--accent)", fontWeight:600 }}>
      {g.instrument}
    </span>
    {g.run_id ? (
      <span className="muted" style={{ marginLeft:8 }}>
        · Run {g.run_id} · Scan {g.run_id.slice(0,4)}-{g.run_id.slice(4,6)}-{g.run_id.slice(6,8)} {g.run_id.slice(9,11)}:{g.run_id.slice(11,13)}
      </span>
    ) : (
      <span className="muted" style={{ marginLeft:8 }}>· Legacy (no run link)</span>
    )}
    <span className="muted" style={{ marginLeft:8 }}>· {g.models.length} model{g.models.length > 1 ? "s" : ""}</span>
  </td>
</tr>
{!collapsedGroups[key] && g.models.map(m => /* existing model row JSX */)}
```

**CSS to add in `styles.css`:**
```css
.model-group-header:hover { background: var(--panel-3) !important; }
```

**`app.jsx`** — pass `run_id` and `instrument` already available in registry payloads through the existing runtimeProps. No new state needed; the 4 model state arrays already flow through.

---

## Part C — Groq "Explain Results" Button in Action Column

### Context

`src/agent/groq_client.py` has `GroqClient.chat(prompt, system, max_tokens)` — already used by the agent system. Config lives in prod config `agent.groq`. `report_api.py` shows the correct pattern for a new HTTP endpoint with LLM analysis.

### Step C1 — Backend: `explain_model_payload()`

**File:** `src/control_plane/dashboard_api.py`

Add after the existing promote methods:

```python
def explain_model_payload(self, model_type: str, version: str) -> dict[str, Any]:
    """Call GroqClient to generate human-readable explanation of model training results."""
    from src.agent.groq_client import GroqClient  # local import — optional dep

    # Registry map
    REGISTRIES = {
        "gaussian":   MODELS_DIR / "gaussian_registry.json",
        "zone_gate":  MODELS_DIR / "zone_gate_registry.json",
        "rr":         MODELS_DIR / "rr_registry.json",
        "tradenet":   MODELS_DIR / "tradenet_registry.json",
    }
    reg_path = REGISTRIES.get(model_type)
    if not reg_path or not reg_path.exists():
        return {"ok": False, "error": f"Unknown model type: {model_type}"}

    try:
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}

    entry = registry.get(version)
    if not entry:
        return {"ok": False, "error": f"Version not found: {version}"}

    metrics = entry.get("metrics") or {}
    # Build a concise context string
    ctx_lines = [
        f"Model type: {model_type}",
        f"Version: {version}",
        f"Trained at: {entry.get('trained_at', '—')[:10]}",
        f"Active: {entry.get('active', False)}",
        f"Instrument: {entry.get('instrument', 'multi')}",
        f"Run ID: {entry.get('run_id', 'n/a')}",
    ]
    for k, v in metrics.items():
        ctx_lines.append(f"{k}: {v}")
    if entry.get("n_zones"):
        ctx_lines.append(f"n_zones: {entry['n_zones']}")
    if entry.get("n_samples"):
        ctx_lines.append(f"n_samples: {entry['n_samples']}")

    context = "\n".join(ctx_lines)
    prompt = (
        f"You are an expert quant analyst reviewing a trading model.\n\n"
        f"Model stats:\n{context}\n\n"
        f"In 3–5 bullet points, explain in plain English:\n"
        f"1. How good is this model (corr, calibration, accuracy)?\n"
        f"2. Is the training dataset large enough to trust?\n"
        f"3. Any red flags or concerns?\n"
        f"4. Is it ready for live trading?\n"
        f"Be concise, specific, and use non-technical language where possible."
    )

    try:
        client = GroqClient()
        explanation = client.chat(prompt, max_tokens=512)
        return {"ok": True, "explanation": explanation, "version": version, "model_type": model_type}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### Step C2 — Backend: New route in `server.py`

After the `/api/opportunity_analytics` route (line ~1673):

```python
if path == "/api/explain_model" and method == "POST":
    try:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        model_type = body.get("model_type", "")
        version    = body.get("version", "")
        self._send_json(HTTPStatus.OK, dash_api.explain_model_payload(model_type, version))
    except Exception as e:
        self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})
    return
```

### Step C3 — `apiClient.js`: add fetch wrapper

```js
explainModel: function (model_type, version) {
  return fetch(BASE + "/api/explain_model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_type: model_type, version: version }),
  }).then(function (r) { return r.json(); });
},
```

### Step C4 — `page3_models.jsx`: Explain button + result modal

**State to add:**
```js
const [explainResult, setExplainResult] = React.useState(null);  // {version, model_type, explanation, ok, error}
const [explainLoading, setExplainLoading] = React.useState(false);
```

**`openExplain(modelType, ver)` function:**
```js
function openExplain(modelType, ver) {
  setExplainResult(null);
  setExplainLoading(true);
  window.ApiClient.explainModel(modelType, ver)
    .then(d => { setExplainResult(d); setExplainLoading(false); })
    .catch(e => { setExplainResult({ ok: false, error: String(e) }); setExplainLoading(false); });
}
```

**TAB_CFG `getEp` mapping** (existing pattern): use current `modelType` value from the active tab config: `"gaussian"`, `"zone_gate"`, `"rr"`, `"tradenet"`.

**Explain button in Action `<td>` (added alongside existing View/Promote):**
```jsx
<button className="btn-sm outline"
  style={{ fontSize:10, padding:"2px 8px", borderLeft:"none" }}
  onClick={() => openExplain(cfg.type, m.ver)}
  title="Explain with AI">
  🤖 Explain
</button>
```

**ExplainModal component:**
```jsx
{(explainLoading || explainResult) && (
  <div className="modal-overlay" onClick={() => setExplainResult(null)}>
    <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth:580 }}>
      <div className="modal-header">
        <span>🤖 AI Analysis — {explainResult?.version || "..."}</span>
        <span className="modal-close" onClick={() => setExplainResult(null)}>✕</span>
      </div>
      <div style={{ padding:"16px 20px", fontSize:13, lineHeight:1.7 }}>
        {explainLoading && <div className="muted">Asking Groq (llama-3.1-70b)…</div>}
        {explainResult && !explainResult.ok && (
          <div style={{ color:"var(--bad)" }}>Error: {explainResult.error}</div>
        )}
        {explainResult && explainResult.ok && (
          <div style={{ whiteSpace:"pre-wrap", color:"var(--text)" }}>
            {explainResult.explanation}
          </div>
        )}
      </div>
    </div>
  </div>
)}
```

**`TAB_CFG` type field** — ensure each tab config has a `type` field matching the registry key:
```js
"Gaussian Models":  { ..., type: "gaussian" },
"Zone Gate Models": { ..., type: "zone_gate" },
"RR Miner Models":  { ..., type: "rr" },
"TradeNet Models":  { ..., type: "tradenet" },
```

---

## Files Modified

| File | Change |
|------|--------|
| `ui_kits/crt_dashboard/page2_research.jsx` | A1: remove `setLiveOutcomes`, A2: rename KPI label + add TP Hit Rate KPI, A3: remove per-job donut header |
| `src/control_plane/dashboard_api.py` | B1: add `run_id`+`instrument` to 4 model payloads, C1: add `explain_model_payload()` |
| `src/control_plane/server.py` | C2: add `POST /api/explain_model` route |
| `ui_kits/crt_dashboard/apiClient.js` | C3: add `explainModel()` |
| `ui_kits/crt_dashboard/page3_models.jsx` | B2: collapsible group rows, C4: Explain button + ExplainModal |
| `ui_kits/crt_dashboard/styles.css` | B2: `.model-group-header` hover style |

---

## Verification

```bash
# A1 fix — no JS crash on All Jobs click
# A2 fix — KPI strip shows "Win Rate (RR>0)" + "TP Hit Rate" 
# B1 — curl shows run_id in models API
curl "localhost:8787/api/models" | python -c "import sys,json; m=json.load(sys.stdin)['models'][0]; print(m.get('run_id'), m.get('instrument'))"

# B2 — Models page shows collapsible group headers per run
# C — Groq explain button
curl -X POST "localhost:8787/api/explain_model" \
  -H "Content-Type: application/json" \
  -d '{"model_type":"gaussian","version":"v5_auto_2026_06_eth"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok'), d.get('explanation','')[:200])"
```

---

# Opportunity Data — Backend-Live Research Page

## Problem Statement

Research page shows empty/zero KPIs for most instruments because:

1. **Path gap (CRITICAL):** `opportunity_stats_payload()` reads `logs/opportunities_{instrument}.jsonl` (flat root-level), but `OpportunityScanner` writes to `logs/{instrument}/{run_id}/opportunities.jsonl` (nested). Only `BTCUSDT` has a stale flat file; EURUSD/ETHUSDT files exist at the wrong path.
2. **Missing `avg_rr`:** Not computed or returned by `opportunity_stats_payload()` but expected by the KPI strip.
3. **Three window globals still mocked:** `window.SCAN_JOBS`, `window.STACKED_OUTCOMES`, `window.SCATTER_POINTS` — no backend APIs exist yet.

## Root-Cause Map

```
OpportunityScanner writes → logs/{instrument}/{run_id}/opportunities.jsonl  (EXISTS 116 MB)
dashboard_api.py reads   → logs/opportunities_{instrument}.jsonl            (MISSING except BTCUSDT)
```

Real files confirmed:
- `logs/EURUSD/20260519_002117/opportunities.jsonl` (116.81 MB)
- `logs/ETHUSDT/20260519_113806/opportunities.jsonl` (116.91 MB)

## Architecture Target (Research Page)

```
Backend (opportunity files)
    ↓
/api/opportunity_stats?instrument=X     → KPI strip + donut chart
/api/opportunity_analytics?instrument=X → stacked bar + scatter chart
/api/scan_jobs?instrument=X             → recent scan jobs table
    ↓
ApiClient.js → app.jsx state → ResearchPage props (zero window.* reads)
```

---

## Implementation Steps

### Step 1 — `dashboard_api.py`: Add `_find_opportunity_file()` helper

Insert before `opportunity_stats_payload` (around line 606):

```python
def _find_opportunity_file(self, instrument: str) -> "Path | None":
    """Resolve the latest opportunities JSONL for instrument.
    Priority:
      1. logs/{instrument}/{latest_run_dir}/opportunities.jsonl  (scanner output)
      2. logs/opportunities_{instrument}.jsonl                   (legacy flat file)
    """
    run_dir = LOGS_DIR / instrument
    if run_dir.is_dir():
        runs = sorted(
            (d for d in run_dir.iterdir() if d.is_dir()),
            key=lambda d: d.name, reverse=True,
        )
        for run in runs:
            candidate = run / "opportunities.jsonl"
            if candidate.exists():
                return candidate
    flat = LOGS_DIR / f"opportunities_{instrument}.jsonl"
    return flat if flat.exists() else None
```

---

### Step 2 — `dashboard_api.py`: Update `opportunity_stats_payload()` (lines 608–680)

Two changes:
- **Path:** Replace `path = LOGS_DIR / f"opportunities_{instrument}.jsonl"` + `if not path.exists()` guard with `path = self._find_opportunity_file(instrument)` / `if path is None: return empty`
- **avg_rr:** Accumulate `rr_sum` and `rr_count` inside the loop; add to return dict

```python
# Inside the loop (after rr = float(...)):
rr_sum   += rr
rr_count += 1

# Return dict — add:
"avg_rr": round(rr_sum / rr_count, 4) if rr_count else None,
```

---

### Step 3 — `dashboard_api.py`: Update `opportunities_payload()` (line 543)

Replace `path = LOGS_DIR / f"opportunities_{instrument}.jsonl"` and its `if not path.exists()` guard with the same `_find_opportunity_file` pattern as Step 2.

---

### Step 4 — `dashboard_api.py`: Add `scan_jobs_payload()`

```python
def scan_jobs_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
    """List completed scanner runs for an instrument (latest 20)."""
    run_dir = LOGS_DIR / instrument
    if not run_dir.is_dir():
        return {"jobs": []}
    jobs: list[dict] = []
    for d in sorted(run_dir.iterdir(), key=lambda d: d.name, reverse=True):
        if not d.is_dir():
            continue
        opp_file = d / "opportunities.jsonl"
        if not opp_file.exists():
            continue
        run_id   = d.name
        job_time = run_id
        rec_est  = _estimate_line_count(opp_file)
        try:
            with open(opp_file, "r", encoding="utf-8", errors="replace") as f:
                hdr = json.loads(f.readline().strip())
            if hdr.get("type") == "run_header":
                job_time = hdr.get("started_at", run_id)[:16].replace("T", " ")
        except Exception:
            pass
        jobs.append({
            "id": f"SCAN-{run_id}", "inst": instrument,
            "time": job_time, "rec": f"{max(0, rec_est - 1):,}", "status": "Completed",
        })
    return {"jobs": jobs[:20]}
```

---

### Step 5 — `dashboard_api.py`: Add `opportunity_analytics_payload()`

Stride-samples up to 2,000 records uniformly across file (avoids reading all 116 MB). Produces:
- **`scatter_points`** (300 pts): x = `rsi_14`, y = `rr_achieved` mapped to 0–100, color by outcome
- **`outcomes_over_time`**: bucketed by quarter, sorted chronologically

```python
def opportunity_analytics_payload(self, instrument: str = "EURUSD") -> dict[str, Any]:
    path = self._find_opportunity_file(instrument)
    empty = {"scatter_points": [], "outcomes_over_time": []}
    if path is None:
        return empty

    total_lines = _estimate_line_count(path)
    stride      = max(1, total_lines // 2_000)
    OUTCOME_COLOR = {"TP_HIT": "#22c55e", "SL_HIT": "#ef4444", "TIMEOUT": "#facc15"}
    scatter: list[dict] = []
    buckets: dict[str, dict] = {}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, raw_line in enumerate(f):
                if i % stride != 0:
                    continue
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    rec = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "run_header":
                    continue

                outcome = rec.get("outcome", "UNKNOWN")
                feats   = rec.get("features") or {}
                rr      = float(rec.get("rr_achieved", 0) or 0)

                rsi = float(feats.get("rsi_14", 50) or 50)
                y   = min(100.0, max(0.0, (rr + 1) * 50.0))
                scatter.append({
                    "x": round(rsi, 1), "y": round(y, 1),
                    "color": OUTCOME_COLOR.get(outcome, "#7f8da6"),
                })

                ts = rec.get("timestamp", "")
                if ts and len(ts) >= 7:
                    try:
                        yr, mo = int(ts[:4]), int(ts[5:7])
                        key = f"{yr}-Q{(mo - 1) // 3 + 1}"
                        if key not in buckets:
                            buckets[key] = {"tp": 0, "sl": 0, "to": 0}
                        if outcome == "TP_HIT":
                            buckets[key]["tp"] += 1
                        elif outcome == "SL_HIT":
                            buckets[key]["sl"] += 1
                        elif outcome == "TIMEOUT":
                            buckets[key]["to"] += 1
                    except ValueError:
                        pass
    except Exception:
        return empty

    return {
        "scatter_points":     scatter[:300],
        "outcomes_over_time": [{"period": k, **v} for k, v in sorted(buckets.items())],
    }
```

---

### Step 6 — `server.py`: Add 2 routes

After the `/api/opportunity_stats` block (~line 1663):

```python
if path == "/api/scan_jobs":
    instrument = query.get("instrument", ["EURUSD"])[0]
    self._send_json(HTTPStatus.OK, dash_api.scan_jobs_payload(instrument))
    return

if path == "/api/opportunity_analytics":
    instrument = query.get("instrument", ["EURUSD"])[0]
    self._send_json(HTTPStatus.OK, dash_api.opportunity_analytics_payload(instrument))
    return
```

---

### Step 7 — `apiClient.js`: Add 2 fetch wrappers

```js
fetchScanJobs:             (ins) => fetch(`/api/scan_jobs?instrument=${encodeURIComponent(ins)}`).then(r => r.json()),
fetchOpportunityAnalytics: (ins) => fetch(`/api/opportunity_analytics?instrument=${encodeURIComponent(ins)}`).then(r => r.json()),
```

---

### Step 8 — `app.jsx`: State + fetch + props

Add state:
```js
const [scanJobs,             setScanJobs]             = React.useState([]);
const [opportunityAnalytics, setOpportunityAnalytics] = React.useState(null);
```

Add to `Promise.allSettled` calls in instrument-change useEffect:
```js
window.ApiClient.fetchScanJobs(selectedInstrument),
window.ApiClient.fetchOpportunityAnalytics(selectedInstrument),
```

Handle results (destructure `sjR, oaR` from `allSettled`):
```js
if (sjR.status === "fulfilled") setScanJobs(sjR.value.jobs || []);
if (oaR.status === "fulfilled") setOpportunityAnalytics(oaR.value);
```

Add to `runtimeProps`: `scanJobs`, `opportunityAnalytics`

---

### Step 9 — `page2_research.jsx`: Replace 3 window.* reads with props

- Signature: `ResearchPage({ oppStats, selectedInstrument, scanJobs, opportunityAnalytics })`
- `window.SCAN_JOBS || []` → `scanJobs || []`
- `window.STACKED_OUTCOMES || []` → `(opportunityAnalytics?.outcomes_over_time) || []`
- `window.SCATTER_POINTS || []` → `(opportunityAnalytics?.scatter_points) || []`
- `StackedBarChart` xLabels: replace 9 hardcoded labels with `(opportunityAnalytics?.outcomes_over_time || []).map(b => b.period)` so axis labels match real quarterly data
- `StackedBarChart` data shape: API returns `{period, tp, sl, to}` — chart already reads `{tp, sl, to}` ✓ (no mapping change needed)

---

## Files Modified

| File | Change |
|------|--------|
| `src/control_plane/dashboard_api.py` | +`_find_opportunity_file`, update `opportunity_stats_payload` + `opportunities_payload`, +`scan_jobs_payload`, +`opportunity_analytics_payload` |
| `src/control_plane/server.py` | +2 routes: `/api/scan_jobs`, `/api/opportunity_analytics` |
| `ui_kits/crt_dashboard/apiClient.js` | +`fetchScanJobs`, +`fetchOpportunityAnalytics` |
| `ui_kits/crt_dashboard/app.jsx` | +2 state, +2 fetch calls, +2 runtimeProps |
| `ui_kits/crt_dashboard/page2_research.jsx` | Accept `scanJobs`, `opportunityAnalytics` props; remove 3 `window.*` globals |

## Verification

```bash
curl "localhost:8787/api/opportunity_stats?instrument=ETHUSDT"
# → total_sampled > 0, avg_rr present, outcome_distribution populated

curl "localhost:8787/api/scan_jobs?instrument=ETHUSDT"
# → {"jobs": [{"id":"SCAN-20260519_113806","inst":"ETHUSDT","time":"...","rec":"...","status":"Completed"},...]}

curl "localhost:8787/api/opportunity_analytics?instrument=ETHUSDT"
# → {"scatter_points":[300 items],"outcomes_over_time":[quarterly buckets]}
```

Dashboard: hard-refresh → Research page shows real KPIs, real scan job table, real bar/scatter charts.
Instrument switch EURUSD → all Research data reloads from EURUSD opportunity file.

---

# Backend-Authoritative Cognitive Runtime — Master Implementation Plan

## Architectural Target

```
Live Market
    ↓
Runtime Backend (canonical truth)
    ↓
ApiClient.js (centralized fetch)
    ↓
app.jsx React state (single store)
    ↓
Pure UI page components (props only)
```

Forbidden pattern eliminated:
```
Backend → window globals → stale frontend snapshots
```

---

## PHASED IMPLEMENTATION

---

## Phase 0 — CDN Removal & Safety Net
**Goal:** Dashboard loads reliably with no external dependency.

### Files
| File | Change |
|------|--------|
| `ui_kits/crt_dashboard/vendor/` | Create dir; download react 18.3.1 + react-dom 18.3.1 + babel 7.29.0 |
| `ui_kits/crt_dashboard/index.html` | Replace 3 CDN script tags with `vendor/*.js`; add mount-failure safety net |

### PowerShell commands
```powershell
New-Item -ItemType Directory -Force "D:\Tradelatest\ui_kits\crt_dashboard\vendor"
Invoke-WebRequest "https://unpkg.com/react@18.3.1/umd/react.development.js"         -OutFile "D:\Tradelatest\ui_kits\crt_dashboard\vendor\react.development.js"
Invoke-WebRequest "https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" -OutFile "D:\Tradelatest\ui_kits\crt_dashboard\vendor\react-dom.development.js"
Invoke-WebRequest "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"         -OutFile "D:\Tradelatest\ui_kits\crt_dashboard\vendor\babel.min.js"
```

**Verification:** Hard-refresh — dark background, full dashboard, Network tab shows `vendor/*.js` from localhost.

---

## Phase 1 — Backend: Instrument Discovery from Prod Config
**Goal:** `/api/instruments` reads from active production config, not log-file disk scan.

### Files
| File | Change |
|------|--------|
| `src/control_plane/dashboard_api.py` | Rewrite `instruments_payload()` — load active prod config via `get_prod_section()`, union `data_ingestion.pairs` + `inout.scanner.allowed_symbols`, deduplicate, return sorted list |

### Logic sketch
```python
def instruments_payload(self):
    pairs = get_prod_section("data_ingestion").get("pairs", [])
    syms  = get_prod_section("inout").get("scanner", {}).get("allowed_symbols", [])
    merged = sorted(set(pairs) | set(syms))
    return {"instruments": merged or ["EURUSD"]}
```

**Verification:** `curl localhost:8787/api/instruments` returns all configured pairs from prod config.

---

## Phase 2 — Backend: Per-Instrument Status API
**Goal:** `/api/status?instrument=BTCUSDT` returns instrument-specific model version + trades.

### Files
| File | Change |
|------|--------|
| `src/control_plane/dashboard_api.py` | Update `status_payload(instrument="EURUSD")` — scan `models/{instrument}/` for latest run dir, extract version from `gaussian_*.json` filename; pass `instrument` to `_find_latest_trades_csv` |
| `src/control_plane/server.py` | `/api/status` handler: extract `instrument` from query params, pass to `status_payload(instrument)` |

### Model version lookup (dir-scan, no registry parsing)
```python
models_dir = REPO_ROOT / "models" / instrument
if models_dir.is_dir():
    runs = sorted(d.name for d in models_dir.iterdir() if d.is_dir())
    if runs:
        latest = models_dir / runs[-1]
        g_files = list(latest.glob("gaussian_*.json"))
        version = g_files[0].stem.replace("gaussian_", "") if g_files else "—"
    else:
        version = "—"
else:
    version = "—"
```

### Response shape
```json
{
  "instrument": "BTCUSDT",
  "active_model_version": "v5_auto_2026_06_eth",
  "active_model_corr": 0.72,
  "kill_switch": { "tripped": false },
  "trades_last_24h": 14,
  "latest_run": "20260519_113806"
}
```

**Verification:** `curl "localhost:8787/api/status?instrument=ETHUSDT"` → `v5_auto_2026_06_eth`; `?instrument=EURUSD` → `v6_2026_05_eur`.

---

## Phase 3 — ApiClient.js (Centralized Fetch Layer)
**Goal:** Single JS file owns all fetch logic. No raw `fetch()` calls elsewhere.

### New file: `ui_kits/crt_dashboard/apiClient.js`
Plain `<script>` (not Babel), sets `window.ApiClient`:
```js
window.ApiClient = {
  fetchInstruments:     ()    => fetch("/api/instruments").then(r => r.json()),
  fetchStatus:          (ins) => fetch(`/api/status?instrument=${ins}`).then(r => r.json()),
  fetchTrades:          (ins) => fetch(`/api/trades?instrument=${ins}&per_page=50`).then(r => r.json()),
  fetchEquityCurve:     (ins) => fetch(`/api/equity_curve?instrument=${ins}`).then(r => r.json()),
  fetchOpportunityStats:(ins) => fetch(`/api/opportunity_stats?instrument=${ins}`).then(r => r.json()),
  fetchModels:          ()    => fetch("/api/models").then(r => r.json()),
  fetchZoneGateModels:  ()    => fetch("/api/zone_gate_models").then(r => r.json()),
  fetchRRModels:        ()    => fetch("/api/rr_models").then(r => r.json()),
  fetchTradeNetModels:  ()    => fetch("/api/tradenet_models").then(r => r.json()),
  fetchBacktestHistory: ()    => fetch("/api/backtest_history").then(r => r.json()),
};
```

Load order in `index.html`: after `data.js`, before all Babel scripts.

---

## Phase 4 — app.jsx Becomes the Runtime Store
**Goal:** All runtime state lives in one React component. Pages are pure projections.

### State variables added to `CrtDashboard`
```
selectedInstrument   string      (seed from localStorage "crt_instrument" → default "EURUSD")
instruments          string[]    (/api/instruments)
instrumentLoading    bool        (true during instrument-switch fetch cycle)
status               object|null (/api/status)
trades               object[]    (/api/trades)
equity               number[]    (/api/equity_curve)
oppStats             object|null (/api/opportunity_stats)
models               object[]    (/api/models)
zoneModels           object[]    (/api/zone_gate_models)
rrModels             object[]    (/api/rr_models)
tradenetModels       object[]    (/api/tradenet_models)
backtestHistory      object[]    (/api/backtest_history)
```

### useEffect hooks
```
useEffect([], [])                → fetch instruments list once on mount
useEffect([selectedInstrument])  → full reload on instrument change:
    instrumentLoading = true
    parallel fetch all 5 instrument-aware endpoints
    all settled → update state, instrumentLoading = false
    save to localStorage
30s setInterval (cleanup on instrument change) → refresh status + trades + equity only
```

### Props passed to TopBar
`instruments`, `selectedInstrument`, `instrumentLoading`, `onInstrumentChange`

### Props passed to every page
`selectedInstrument`, `instruments`, `instrumentLoading`, `status`, `trades`, `equity`, `oppStats`, `models`, `zoneModels`, `rrModels`, `tradenetModels`, `backtestHistory`

### Remove from app.jsx
- `window._REAL_DATA_LOADING` check
- `realData.js` reliance (realData.js gutted in Phase 6)

---

## Phase 5 — TopBar Instrument Selector
**Goal:** Dropdown left of "CRT v5 (Live)" — disabled + spinner while loading; persisted.

### `shared.jsx` — TopBar changes
- New props: `instruments`, `selectedInstrument`, `instrumentLoading`, `onInstrumentChange`
- Render: `<select>` populated from `instruments` array; `disabled={instrumentLoading}`
- Spinner: inline CSS spinner shown when `instrumentLoading === true`
- Status pill: `CRT ${status?.active_model_version || "—"} (Live)` — dynamic from props
- `onInstrumentChange`: selector `onChange` → calls prop + `localStorage.setItem("crt_instrument", inst)`

---

## Phase 6 — Gut `data.js` Globals + `realData.js`
**Goal:** No window globals for runtime cognition.

### `data.js`
Remove `window.*` assignments for all runtime-backed data:
`RT_KPIS`, `TRADE_JOURNAL`, `EQ_TRADES`, `MODELS`, `ZONE_GATE_MODELS`, `RR_MODELS`, `TRADENET_MODELS`, `RESEARCH_KPIS`, `OUTCOMES_SEGMENTS`, `TRADE_KPIS`, `EQ_RUNTIME`, `EQ_BACKTEST`, `BT_HISTORY`, `BT_KPIS`

**Keep** (no backend equivalent yet): `FEATURE_DRIFT`, `LINEAGE_NODES`, `SHADOW_COMPARE`, `PROMOTION_HISTORY`, `REGIME_PERF`, `TRADE_TRACE`, `SEQ_PATTERNS` — mark with `// TODO: replace with /api/{endpoint}`

### `realData.js`
Gut entirely — remove all fetch/mount orchestration.
Reduce to: `window._REAL_DATA_LOADING = false;` or delete and remove from `index.html`.

---

## Phase 7 — Per-Page Prop Wiring
**Goal:** Pages read from props only. Zero `window.*` reads for runtime data.

| Page | Props consumed | Globals to remove |
|------|---------------|------------------|
| `page0_executive.jsx` | `status`, `equity`, `oppStats`, `selectedInstrument` | `RT_KPIS`, `EQ_TRADES`, `SESSION_PNL`, `EXEC_KPIS` |
| `page1_runtime.jsx` | `status`, `equity`, `trades`, `selectedInstrument` | `RT_KPIS`, `EQ_RUNTIME`, `RT_TRADES`, `SIGNAL_PIPELINE` |
| `page2_research.jsx` | `oppStats`, `selectedInstrument` | `RESEARCH_KPIS`, `OUTCOMES_SEGMENTS`; drop `job.inst` competing fetch |
| `page3_models.jsx` | `models`, `zoneModels`, `rrModels`, `tradenetModels`, `selectedInstrument` | `MODELS`, `ZONE_GATE_MODELS`, `RR_MODELS`, `TRADENET_MODELS` |
| `page4_trades.jsx` | `trades`, `selectedInstrument` | `TRADE_JOURNAL`, `TRADE_KPIS`, `EQ_TRADES` |
| `page5_backtests.jsx` | `backtestHistory`, `selectedInstrument` | `BT_HISTORY`, `BT_KPIS`, `EQ_BACKTEST` |
| `page6_system.jsx` | `selectedInstrument` | No runtime globals removed — add "Global data" note |
| `page7_intelligence.jsx` | `selectedInstrument` | No runtime globals removed — add instrument badge |
| `page8_replay.jsx` | `selectedInstrument` | No runtime globals removed — add instrument badge |

**Rule for pages without instrument-aware endpoints (System, Intelligence, Replay):**
Show instrument name in header; label existing data with muted `"Global data · not instrument-filtered"`.

---

## Phase 8 — View Modal Verification (already implemented)
- Verify `ViewModal` in `page3_models.jsx` uses `window.ApiClient` (Phase 3) instead of inline `fetch()`
- Confirm modal displays feature schema, metrics, raw registry JSON from actual backend data
- Wire `openView` in page3_models.jsx to call `window.ApiClient.fetchModels()` (or the matching model-type fetch)

---

## Phase 9 — 30s Refresh Loop Migration
**Goal:** Replace `realData.js` `setTimeout` chain with React `setInterval` in `app.jsx`.

```js
React.useEffect(() => {
  const id = setInterval(async () => {
    const [s, t, e] = await Promise.allSettled([
      ApiClient.fetchStatus(selectedInstrument),
      ApiClient.fetchTrades(selectedInstrument),
      ApiClient.fetchEquityCurve(selectedInstrument),
    ]);
    if (s.status === "fulfilled") setStatus(s.value);
    if (t.status === "fulfilled") setTrades(/* map */);
    if (e.status === "fulfilled") setEquity(/* map */);
  }, 30000);
  return () => clearInterval(id);  // restart on instrument change
}, [selectedInstrument]);
```

---

## CRITICAL FILES SUMMARY

### Backend
| File | Phases | Est. lines |
|------|--------|-----------|
| `src/control_plane/dashboard_api.py` | 1, 2 | ~40 lines |
| `src/control_plane/server.py` | 2 | ~3 lines |

### Frontend — New Files
| File | Phase |
|------|-------|
| `ui_kits/crt_dashboard/vendor/` (3 files) | 0 |
| `ui_kits/crt_dashboard/apiClient.js` | 3 |

### Frontend — Modified Files
| File | Phases |
|------|--------|
| `ui_kits/crt_dashboard/index.html` | 0, 3 |
| `ui_kits/crt_dashboard/data.js` | 6 |
| `ui_kits/crt_dashboard/realData.js` | 6 (gutted) |
| `ui_kits/crt_dashboard/app.jsx` | 4 (major rewrite) |
| `ui_kits/crt_dashboard/shared.jsx` | 5 |
| `ui_kits/crt_dashboard/page0_executive.jsx` | 7 |
| `ui_kits/crt_dashboard/page1_runtime.jsx` | 7 |
| `ui_kits/crt_dashboard/page2_research.jsx` | 7 |
| `ui_kits/crt_dashboard/page3_models.jsx` | 7, 8 |
| `ui_kits/crt_dashboard/page4_trades.jsx` | 7 |
| `ui_kits/crt_dashboard/page5_backtests.jsx` | 7 |
| `ui_kits/crt_dashboard/page6_system.jsx` | 7 |
| `ui_kits/crt_dashboard/page7_intelligence.jsx` | 7 |
| `ui_kits/crt_dashboard/page8_replay.jsx` | 7 |

---

## EXECUTION ORDER

```
Phase 0  → vendor + index.html           [dashboard loads reliably — unblocks all]
Phase 1  → /api/instruments prod config  [real instrument list]
Phase 2  → /api/status per-instrument    [status pill shows real per-coin model]
Phase 3  → apiClient.js                  [fetch surface ready]
Phase 4  → app.jsx runtime store         [state layer complete]
Phase 5  → TopBar selector               [instrument switching works end-to-end]
Phase 6  → remove globals / realData     [cleanup after Phase 4 stable]
Phase 7  → per-page prop wiring          [final global elimination across all pages]
Phase 8  → View modal verification       [already done — confirm ApiClient wiring]
Phase 9  → 30s refresh migration         [run after Phase 4 confirmed stable]
```

---

## HARD CONSTRAINTS

| Rule | Detail |
|------|--------|
| No new `window.*` for runtime data | All new state → `React.useState` in `app.jsx` |
| No hardcoded instruments | Always from `/api/instruments` → prod config |
| No hardcoded model versions | Always from `/api/status?instrument=` → dir-scan |
| Pages are pure projections | All data arrives as props; no `fetch()` in leaf pages |
| `ApiClient.js` is the only fetch surface | No raw `fetch()` calls outside `apiClient.js` |
| localStorage key | `"crt_instrument"` |
| Instrument selector disabled during load | `instrumentLoading === true` → `<select disabled>` + spinner |
