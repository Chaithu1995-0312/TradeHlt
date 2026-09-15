# Concatenated session plans — part 4 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `gaussain-zonegate-tradenet-rrminer-ethereal-dove.md` (39490 bytes)
2. `generate-claude-md-for-current-eventual-sketch.md` (12840 bytes)
3. `goal-produce-a-complete-fluffy-grove.md` (14301 bytes)
4. `good-enough-context-let-humming-knuth.md` (4813 bytes)
5. `here-is-the-complete-tingly-finch.md` (21772 bytes)
6. `how-claude-is-refeering-soft-waterfall.md` (6831 bytes)
7. `hummingbot-candle-fetcher-need-command-t-tingly-candle.md` (5353 bytes)


================================================================================
SOURCE_FILE: docs/plans/gaussain-zonegate-tradenet-rrminer-ethereal-dove.md
SOURCE_BYTES: 39490
PART: 4/10 FILE 1/7
================================================================================

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


================================================================================
SOURCE_FILE: docs/plans/generate-claude-md-for-current-eventual-sketch.md
SOURCE_BYTES: 12840
PART: 4/10 FILE 2/7
================================================================================

> Created: 2026-05-28 · Updated: 2026-05-28 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Expose webhook via ngrok + wire up TradingView

## Context

Webhook bot is running on `localhost:8000` and Telegram delivery is confirmed.
TradingView webhooks require a **public HTTPS URL** — it cannot reach localhost.
Goal: install ngrok, tunnel port 8000, get a public URL, and configure a
TradingView alert to call it. No code changes to the bot itself.

## Steps

### 1 — Install ngrok

Download the Windows zip from https://ngrok.com/download (no account needed for
basic use), extract `ngrok.exe` to any folder on your PATH — or just place it in
the webhook project folder.

Alternatively, with Chocolatey (if installed):
```powershell
choco install ngrok -y
```
Or with winget:
```powershell
winget install ngrok.ngrok
```

### 2 — Start the tunnel (leave uvicorn running)

Open a **new** PowerShell window and run:
```powershell
ngrok http 8000
```

ngrok will print a forwarding URL like:
```
Forwarding   https://a1b2c3d4.ngrok-free.app -> http://localhost:8000
```
Copy that `https://...ngrok-free.app` URL.

### 3 — Verify the tunnel reaches the bot

In a third PowerShell window:
```powershell
Invoke-RestMethod -Uri "https://<YOUR_NGROK_URL>/health"
# Expected: {"status":"ok","service":"TradingView Telegram Webhook"}
```

### 4 — Configure TradingView alert

In TradingView → Alerts → Create Alert:

**Webhook URL** (in "Notifications" tab → "Webhook URL"):
```
https://<YOUR_NGROK_URL>/tv-webhook
```

**Alert Message** (in "Settings" tab → "Message" box — paste exactly):
```json
{
  "passphrase": "<YOUR_SECURITY_PASSPHRASE>",
  "ticker":     "{{ticker}}",
  "price":      "{{close}}",
  "timeframe":  "{{interval}}",
  "stage":      "1D CRTL Sweep / Liquidity Test"
}
```
Replace `<YOUR_SECURITY_PASSPHRASE>` with the value in your `.env`.

### 5 — Verify end-to-end

Once the alert fires (or trigger it manually from TradingView), confirm:
- uvicorn terminal shows `Incoming payload: {...}` and `Telegram message sent successfully`
- Telegram card arrives in your chat

## Notes

- **ngrok URL changes each restart** — free tier issues a new URL every time
  ngrok is restarted. Update the TradingView webhook URL whenever you restart.
- **Production fix**: deploy to a VPS with a fixed domain (next step after this).
- The webhook bot code needs no changes for this step.

---

### 1 — Send a valid test alert

Open a **new** PowerShell window (leave uvicorn running in the other one) and run:

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/tv-webhook" `
  -ContentType "application/json" `
  -Body '{
    "passphrase": "<YOUR_SECURITY_PASSPHRASE>",
    "ticker":    "GBPCAD",
    "price":     "1.74823",
    "timeframe": "1D",
    "stage":     "1D CRTL Sweep / Liquidity Test"
  }'
```

Replace `<YOUR_SECURITY_PASSPHRASE>` with the value from your `.env`.

**Expected response (HTTP 200):**
```json
{"status": "ok", "message": "Alert processed"}
```

**Expected Telegram card:**
```
🎯 Market Stage Triggered
━━━━━━━━━━━━━━━━━━━━━
• Asset:      GBPCAD
• Structure:  1D CRTL Sweep / Liquidity Test
• Price:      1.74823
• Timeframe:  1D
• Time:       <UTC timestamp>
━━━━━━━━━━━━━━━━━━━━━
⚠️ Check charts for structural rejection or breakout confirmation.
```

### 2 — Confirm Telegram card arrived

Open your Telegram channel/group. The card should appear within a few seconds.

### 3 — Test bad passphrase → 401

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/tv-webhook" `
  -ContentType "application/json" `
  -Body '{"passphrase": "wrongpassword", "ticker": "GBPCAD", "price": "1.0", "timeframe": "1D", "stage": "test"}'
```

Expected: HTTP 401 — `{"detail": "Unauthorized"}` — no Telegram card.

## No code changes

Everything is already wired. This is a pure run-and-observe test.

Resolution agreed with the user:
- **Testing needs no exchange keys.** Freqtrade dry-run uses only public market
  data; the bridge itself only needs the freqtrade REST API.
- To avoid running/trusting freqtrade's code at all during *our* integration
  test, we'll point the webhook at a **throwaway local mock** of freqtrade's
  `/api/v1/forceenter`. This fully exercises our code path (basic auth, payload,
  response handling) with zero exchange exposure.
- The user **will provide real Telegram credentials** so the full chain
  (Telegram alert card + freqtrade trigger) is tested exactly as in production.
  (No code change to decouple Telegram — keep alert-first behaviour.)
- Real freqtrade + live exchange keys is a **separate later step**, documented
  with safety practices, not part of this test.

## Already done (prior step, verified with stubbed HTTP)

- `fastapi-webhook-bot\fastapi-webhook-bot\main.py` — `AUTONOMOUS_MODE` +
  `FREQTRADE_API_*` config, `trigger_freqtrade_entry()` helper
  (`POST {FREQTRADE_API_URL}/api/v1/forceenter`, basic auth), and the autonomous
  branch in `/tv-webhook`.
- `.env.example` — documents the four new vars.
- `freqtrade-crth-strategy\...\config.json` — `api_server.enabled: true`,
  `force_entry_enable: true` (creds still placeholders).
- `D:\TradeAnalyseOpenSource\CLAUDE.md` — single root doc.

## Work to do

### 1. Throwaway local mock freqtrade API (test-only, NOT committed)

Create a tiny FastAPI app in a temp dir (outside the repo) exposing
`POST /api/v1/forceenter` that:
- requires HTTP basic auth (a known test username/password),
- echoes the received JSON body and returns a freqtrade-like trade confirmation,
- records the call so we can assert auth + payload were correct.
Run it on `localhost:8080` in the temp venv already used for verification.

### 2. Run the webhook bot against the mock + real Telegram

- Env at runtime only (not persisted to any committed file):
  `AUTONOMOUS_MODE=true`, `FREQTRADE_API_URL=http://localhost:8080`,
  `FREQTRADE_API_USERNAME`/`FREQTRADE_API_PASSWORD` matching the mock,
  `SECURITY_PASSPHRASE`, and the user-provided `TELEGRAM_BOT_TOKEN` +
  `TELEGRAM_CHAT_ID`.
- Start `uvicorn main:app --port 8000`.

### 3. Fire a real test alert and assert the full chain

`POST /tv-webhook` with `{passphrase, ticker, price, timeframe, stage,
pair: "BTC/USDT"}` and confirm:
- HTTP 200 with an `autonomous` block in the response,
- a **real Telegram card** arrives in the user's chat,
- the mock received the `forceenter` call with correct basic auth and
  `{"pair": "BTC/USDT", "side": "long"}`,
- a bad passphrase still returns 401 and never reaches the mock.

### 4. Add exchange-key security guidance to `CLAUDE.md`

Append a short "Going live safely (exchange API keys)" section:
- dry-run needs no keys;
- when going live, create the exchange key with **withdrawals disabled** and
  **IP-whitelisted**;
- keys stay local in `config.json`, sent only to the exchange over HTTPS;
- never commit real keys; keep `dry_run: true` until intentionally live.

## Out of scope (later, user-initiated)

- Installing/running real freqtrade (Docker image, dry-run) to confirm the live
  contract — deferred; the documented API contract + mock test cover our code.
- Any real exchange keys.

## Verification

- Mock receives exactly one `forceenter` call per valid alert, with correct
  auth + body; webhook response contains the `autonomous` block.
- User confirms the Telegram card actually arrived in their chat.
- Bad passphrase → 401, no mock call.
- Re-read `CLAUDE.md` to confirm the new security section is accurate and no real
  secrets were written anywhere. Tear down the temp venv/mock afterward.

---

# Follow-up: load `.env` for local runs (approved)

## Context

`main.py` reads config via `os.getenv(...)`, which only reads the process
environment. Docker works because `docker-compose.yml` uses `env_file: .env`,
but a local `uvicorn main:app` ignores the `.env` entirely — `main.py` never
calls `load_dotenv()`, even though `python-dotenv` is already in
`requirements.txt`. The user filled in a real `.env` and wants local runs to
fetch those values automatically.

## Change

`fastapi-webhook-bot/fastapi-webhook-bot/main.py` — add two lines so the `.env`
is loaded before the config block reads it:
- `from dotenv import load_dotenv` (with the other imports near the top)
- `load_dotenv()` called immediately after imports, **before** the
  `os.getenv(...)` configuration block (lines ~21-31).

No other files change. `python-dotenv==1.0.1` is already declared, so no new
dependency. Docker behaviour is unaffected (env_file still wins / coexists).

## Also: clarify the two self-chosen secrets in `.env.example`

The user was unsure how to obtain `SECURITY_PASSPHRASE` and
`FREQTRADE_API_PASSWORD`. Neither is fetched from an external service — both are
secrets the user invents and must keep consistent across two places. Tighten the
comments in `fastapi-webhook-bot/fastapi-webhook-bot/.env.example`:
- `SECURITY_PASSPHRASE` — "Invent any strong string; put the SAME value in your
  TradingView alert JSON `passphrase` field."
- `FREQTRADE_API_USERNAME` / `FREQTRADE_API_PASSWORD` — "Must match freqtrade
  config.json `api_server.username` / `password`."

Blank lines like `SECURITY_PASSPHRASE=` and `FREQTRADE_API_PASSWORD=` resolve to
**empty strings** once loaded (overriding the in-code defaults), so they must be
filled in for auth to work.

## Verification

- From the project dir, `uvicorn main:app --port 8000` (no `--env-file`); confirm
  the app picks up `.env` values (e.g. a request authenticates against the
  `SECURITY_PASSPHRASE` set in `.env`, not the code default).
- Do not print `.env` contents during verification (per the CLAUDE.md rule);
  assert behaviour via endpoint responses only.

---

# Follow-up: persist a "Secrets setup" step-by-step guide (approved-pending)

## Context

The user repeatedly asked how to obtain `SECURITY_PASSPHRASE` and
`FREQTRADE_API_PASSWORD`. They are self-generated secrets (not fetched from any
service); the confusion is worth fixing permanently with an explicit, copy-paste
setup guide in the repo rather than only in chat.

## Change

Add a **"## Secrets setup (step by step)"** section to the webhook bot README
`fastapi-webhook-bot/fastapi-webhook-bot/README.md` (right after the existing
"Configuration" section), containing:

1. **SECURITY_PASSPHRASE** — generate with
   `python -c "import secrets; print(secrets.token_urlsafe(24))"`; put in `.env`;
   mirror the SAME string in the TradingView alert JSON `passphrase` field.
2. **FREQTRADE_API_USERNAME / PASSWORD** — set in freqtrade `config.json`
   `api_server` (username/password, plus regenerate `jwt_secret_key` via
   `token_hex(32)` and `ws_token` via `token_urlsafe(32)`), then copy the same
   username/password into `.env`. Restart both services.
3. **Verify** the freqtrade creds with
   `curl -u <user>:<pass> http://localhost:8080/api/v1/ping` → expect
   `{"status":"pong"}`, wrong creds → 401.

4. **Restart so changes load (user chose LOCAL uvicorn):**
   - Primary: in the uvicorn terminal press Ctrl+C, then re-run
     `uvicorn main:app --port 8000` (`load_dotenv()` reads `.env` only at startup;
     `--reload` does not re-read it).
   - Free port 8000 first if a container is running: `docker compose down`.
   - (Secondary note) Docker alternative: `docker compose up -d --force-recreate`;
     container name is `tv-telegram-webhook`. Don't run both at once.
   - Freqtrade (when running): `docker restart <its container>` or hot-reload via
     Telegram `/reload_config` / `POST /api/v1/reload_config`.

Keep it concise (the table in "Configuration" already lists the vars; this adds
the *how-to-fill-them* steps). No code changes.

## Optional cleanups (only if user opts in)

- **config.json tokens:** `freqtrade-crth-strategy/freqtrade-crth-strategy/config.json`
  currently has `jwt_secret_key` and `ws_token` set to the literal strings
  `"secrets.token_hex(32)"` / `"secrets.token_urlsafe(32)"` (command text, not
  generated values). Replace with freshly generated random values. The basic-auth
  `password` is already valid, so this is hygiene, not required for the
  webhook→freqtrade path.
- **docker-compose.yml:** remove the obsolete top-level `version: "3.9"` line in
  `fastapi-webhook-bot/fastapi-webhook-bot/docker-compose.yml` to silence the
  Compose v2 warning.

## Verification

- Re-read the README section for accuracy (commands, file references, the
  must-match relationships) and confirm no real secrets are written into it.
- If the token fix is applied, confirm `config.json` still parses as valid JSON
  and the two fields are non-placeholder random strings.


================================================================================
SOURCE_FILE: docs/plans/goal-produce-a-complete-fluffy-grove.md
SOURCE_BYTES: 14301
PART: 4/10 FILE 3/7
================================================================================

# Plan: Persist the Intelligence-Layer Audit

> Created: 2026-06-02 · Plan-mode deliverable. The audit below is finalized and ready to write
> verbatim to `docs/analysis/intelligence-layer-audit.md` (point-in-time analysis per CLAUDE.md §2).

## Context

A multi-pass, evidence-only audit of the Tradelatest intelligence layer surfaced a chain of findings
that culminate in a concrete production-logic consequence (the zone gate routes ~90–96% of passes
through regions its own metadata records as negative-expectancy, with no stage able to correct it).
These findings are load-bearing and must be persisted as a dated point-in-time doc. Active production
config = `v2_multi_2026_04 - deepdeektry` (per `configs/production/ACTIVE_VERSION`).

## Action on approval

1. Write the document below verbatim to `docs/analysis/intelligence-layer-audit.md`.
2. Append the §6 SESSION LOG block (shown at end) to `assistant_project.md`.
3. No code changes. No architectural proposals. Evidence-only, as produced.

---

# Intelligence-Layer Audit — Tradelatest

> Point-in-time analysis (NOT living). Date: 2026-06-02. Evidence-only; no proposals.
> Active config: `v2_multi_2026_04 - deepdeektry` (`configs/production/ACTIVE_VERSION`).

## 1. The seven systems (A–G)

| System | A. Purpose | B. Inputs | C. Outputs | D. Runtime consumers | E. Training source | F. Status |
|---|---|---|---|---|---|---|
| **Heuristic CRT** | Composite setup score `0.35·sweep+0.25·breakout+0.20·retest+0.20·time` (`scoring_engine.py:42`) | sweep/double_sweep, body_ratio, disp_strength, retest_depth, candles_since_retest (`crt_engine.py:17-27`) | `{score,final,sub-scores}` [0,1] | EngineRunner→Fusion (`engine_runner.py:655`; `score_crt` `fusion_engine.py:371`) | none (rule-based) | **ACTIVE** (`weight_crt 0.4`) |
| **Gaussian** | Probability score; heuristic EMA/momentum PDF (`heuristic_gaussian_engine.py:271-343`) or ML NB sigmoid(expected_rr) (`ml_gaussian_engine.py:167-169`) | 3 feats (heuristic) / 35-dim (ML) | `{score,reason,meta}` | EngineRunner→Fusion (`engine_runner.py:666`) | static mu/sigma or `models/gaussian_*.json` | **ACTIVE** (heuristic); **SHADOW** (ML, `shadow_ml`) |
| **RR Model** | Candle Polarity Index (NOT forward R:R) (`rr_engine.py:4-28,59-73`); optional `RRFusionLayer` nano-model | close/high/low | `{score,candle_polarity,rr_ratio(legacy)}` | EngineRunner→Fusion (`engine_runner.py:684`) | RREngine none; RRFusion `models/rr_model.json` (`rr_dataset_builder.py`) | **ACTIVE** (`weight_rr 0.2`) |
| **TradeNet V2** | 3-head survival net (p_tp1/p_tp2/p_survives_be), composite `0.4/0.4/0.2` (`trade_net_v2.py:15,45`) | 38-dim canonical | `{tradenet_score,p_tp1,p_tp2,p_survives_be}` | only `CognitiveBus` (`cognitive_bus.py:209,232,309`) — off the execution spine | `train_trade_net_v2.py` on `opportunities_*.jsonl` | **DORMANT** (no cognitive section in active config) |
| **ReplayMemory** | Region-conditioned historical win-rate/RR with decay (`replay_memory_engine.py:193-224`) | `opportunities_*.jsonl` + zone centroids | `{historical_winrate,cluster_stability,temporal_confidence,…}` | only `CognitiveBus` (`cognitive_bus.py:219-298`) | none (reads JSONL) | **DORMANT** |
| **ForwardTester** | OOS validators (BitNet zone overfit `bitnet/forward_tester.py:38-187`; LLM 3-mode `llm_research/forward_tester.py:43-245`) | zones / data CSV | per-zone status / `ForwardTestReport` | none (research scripts only) | n/a | **DORMANT** (research-only) |
| **Probability Surface** | none on HEAD; only `inout.probability` config block (model_dir, approach "D") | — | — | none | — | **DEAD** (config ghost; impl only in detached worktrees) |

## 2. Actual runtime dependency graph

```
Features (38-dim CANONICAL_FEATURES — feature_schema.py:46-76)
  ↓
EngineRunner  (engine_runner.py:576) — runs 4 engines sequentially:
   Adapter/trap gate → CRT → Gaussian → ZoneGate → RR (+ optional RRFusionLayer)
   completeness hard-gate: EXPECTED_ENGINES = {crt,gaussian,zone_gate,rr} (:52/:748)
  ↓
FusionEngine.compute (:777; fusion_engine.py:290-547)
   regime-weighted avg (crt .4 / gaussian .2 / zone_gate .2 / rr .2) + conflict + normalize
  ↓
DecisionEngine.evaluate (:961; decision_engine.py:104-158) — dynamic threshold + 4 gates → execute|reject
  ↓
ExecutionPlannerV1_2.plan (execution_planner.py:156-250)
  ↓
UltronRiskGate.evaluate (ultron_risk_gate.py:156-188)

Off-spine, DORMANT: Features → CognitiveBus → {ReplayMemory, TradeNetV2} → TradeNetMeta → logs/cognitive_telemetry.jsonl
```

## 3. Overlap analysis
- **Duplicated:** Gaussian heuristic vs ML (same slot); win-probability produced 3× (Gaussian-ML / TradeNet / ReplayMemory — only Gaussian reaches Decision); two ForwardTesters; "RR" naming collision (CPI vs forward-R:R in Ultron).
- **Abandoned:** Probability Surface (DEAD); cognitive layer (TradeNet+ReplayMemory) de-configured v1→v2; ForwardTesters orphaned.
- **Replacement paths (in code):** Gaussian heuristic→ML (`shadow_ml` harness); RR formula→`RRFusionLayer`; flat risk tiers→TradeNet `capital_quality_score` (gated behind disabled CognitiveBus).

## 4. Probabilistic scorers + density-awareness
- **Comparison:** TradeNet V2 is the only candidate that consumes the full 38-dim vector, emits outcome-grounded multi-head probabilities, and has an honest train/test split (n_test 10k–30k) + AUC promotion guard. Gaussian-ML: corr~0.18–0.21, `n_val=0` (in-sample calibration), 38→35 truncation. Gaussian-heuristic: 3-feature prior, zero-dependency, the live default.
- **Density layer (if TradeNet owns probability):** mathematically correct = **GMM** (multimodal density + per-component Mahalanobis/χ² threshold), which is the generalization of the *existing* diagonal-covariance zone registry. KDE defeated by d=38 + categorical features; Mahalanobis correct only per-mode (it is the GMM exponent); KMeans/novelty/autoencoder are not densities. Note: density (membership) ≠ concept-drift detection (see §6).

## 5. CRT score is informationally redundant
- CRT score = closed-form `f(sweep_detected, double_sweep, body_ratio, disp_strength, retest_depth, candles_since_retest)` — all six already in the 38-vector (`scoring_engine.py:14-51`). No external data.
- TradeNet/Gaussian/zone train on the 38-vector, never on CRT score or sub-scores (`build_input_matrix`→`extract_feature_vector`; grep `crt`/`scoring_engine` = 0).
- Removing CRT score removes **zero** predictive information (reconstructable R²≈1.0; it is an algebraic identity up to config constants). It is an inductive prior, not an information source. Most-predictive features = CRT *geometry* (body_ratio, retest_depth, disp_strength); least = raw OHLCV (zeroed in zone weights; harmful under equal weight).

## 6. The drift gap (core finding): "Known Region ≠ Profitable Region"

A robust system needs three independent answers: **A** what am I looking at (membership), **B** was it historically profitable (baseline expectancy), **C** is it still profitable now (recent expectancy). Status:

- **A — membership: IMPLEMENTED.** Zone gate scores membership against frozen registry, hard pass/block on score ≥ threshold (`zone_gate_engine.py:239-240`).
- **B — baseline expectancy: STORED BUT UNREAD.** Every zone carries `meta.mean_rr / tp_hit_rate / sl_hit_rate / n_samples`. Repo-wide grep shows **no decision-path code reads `mean_rr`** (readers are schema-meta, the separate regime cluster engine, and the dormant replay layer). Dead telemetry w.r.t. the trade decision.
- **C — recent expectancy: NOT IMPLEMENTED in production.** `ReplayMemory.query` *does* compute decay-weighted recent win-rate (`exp(-λ·age_days)`, `replay_memory_engine.py:193-224`) — the correct mechanism — but (a) it is DORMANT, (b) it reports a level not a Δ vs trained edge, (c) its `cluster_stability`/`temporal_confidence` measure dispersion/coverage, not drift, (d) it is fed only by simulated outcomes (see write-back).

### 6.1 Outcome write-back — the live learning loop does not close
- `opportunities.jsonl` (read by ReplayMemory + TradeNet training) is written by the **scanner/backtest** (forward-simulated outcomes), `backtest_v2.on_trade_closed` (`:831-906`).
- `src/inout/` (live package) contains **only** two candle fetchers — no execution, no trade-close, no outcome writer. No writer of `inout_trades.db` exists. No inout code references opportunities/replay.
- **Verdict:** the system re-learns offline by re-simulation over (re-)fetched candles; it **never** ingests its own live outcomes. Slippage, partial fills, real execution quality are structurally invisible.

### 6.2 Zone expectancy — the production registry is 96% losing mass
`models/zone_registry.json` (loaded by active config: `engine_runner.zone_registry_path`, `zone_mode=hard`, `zone_min_samples=50`, `weight_zone_gate=0.2`):

| zone | n_samples | mean_rr | | zone | n_samples | mean_rr |
|---|---:|---:|---|---|---:|---:|
| zone_0 | 20,708 | −0.0292 | | zone_4 | 3,872 | +0.0124 |
| zone_1 | 10,100 | −0.0180 | | zone_5 | 172 | +0.1163 |
| zone_2 | 45,674 | −0.0519 | | zone_6 | 1,162 | +0.0897 |
| zone_3 | 31,540 | −0.0448 | | zone_7 | 26,714 | −0.0500 |

- **5/8 zones negative; negative zones hold 134,736 / 139,942 = 96.3% of occupancy.** The 3 positive zones are the smallest (3.7% mass; the two with real magnitude have 172 & 1,162 samples).
- `min_samples=50` filters by popularity (anti-correlated with edge): all 8 zones load, including all negatives.

### 6.3 Fusion-signing proof — a negative zone *raises* the fused score (architecture, not bug)
- `score = model_fn(vector)` = membership ∈ [0,1]; `passed = score≥threshold` (`zone_gate_engine.py:239-240`). No `mean_rr`.
- `zone_result.score = float(zone_raw["score"])`, `direction = 1 if passed` (`engine_runner.py:649-654`).
- `score_zonegate = _clamp(float(payload["score"]))` ∈ [0,1], always ≥0 (`fusion_engine.py:366,376`).
- `weighted = (… + w_zonegate·score_zonegate + …)/total_w`, `w_zonegate = 0.2 > 0`. ∂(fused)/∂(score_zonegate) = +0.2/total_w.
- **Therefore:** higher membership in any zone (incl. mean_rr<0) → higher fused score → more likely `execute`. `mean_rr` is read by **nothing**, so no term can subtract for a losing zone. It is the *absence* of an edge term (architecture), not a sign error (bug).

### 6.4 Live exposure
- Occupancy-weighted expectancy of the matched zone = **−0.0410 R/candle**.
- If membership passes ∝ occupancy → **~96% of zone-gate passes route through negative zones.** Sensitivity: even at an implausible 10× preferential pass rate for positive zones, negatives still take 72%; realistic skew (sparse positive zones → k≤1) pushes the true figure to the **93–96%** (worse) end.
- Caveats: zone gate is 20% of fusion + hard gate (not sole gate); no downstream engine reads expectancy so none corrects the bias; −0.041R is per-candle raw-scan expectancy, not realized post-pipeline PnL.

## 7. Consolidated status

| Capability | Status |
|---|---|
| Feature extraction (train==live, schema-hash guarded) | SOLVED |
| Zone membership ("known region") | SOLVED |
| Offline re-training loop (scanner→train→registry) | SOLVED (manual) |
| Probability (recency-conditioned) | PARTIAL — ReplayMemory built, DORMANT, sim-fed |
| Live outcome feedback | ABSENT (no live writer) |
| Baseline expectancy at runtime | STORED (`meta.mean_rr`) but UNREAD |
| Concept-drift / region-decay detection | NOT IMPLEMENTED |
| Edge-aware gating (membership × expectancy) | NOT IMPLEMENTED — gate is membership-only; 96% negative-mass exposure |

**Bottom line:** the system reliably recognizes familiar market states but does not verify, at runtime, whether those states still (or ever) had an edge — and by occupancy it routes the large majority of signals through regions its own metadata records as losing. This is more fundamental than any CRT-weight question.

---

## Evidence index (primary citations)
`scoring_engine.py:14-51,42` · `crt_engine.py:17-27` · `heuristic_gaussian_engine.py:271-343` · `ml_gaussian_engine.py:151-169` · `rr_engine.py:4-28,59-82` · `trade_net_v2.py:15,45,165-185` · `train_trade_net_v2.py:141-185` · `replay_memory_engine.py:193-224,294-304` · `cognitive_bus.py:209-309` · `feature_schema.py:46-76,194-273` · `engine_runner.py:52,411-413,576,632-654,655,666,684,748,777,961` · `fusion_engine.py:290-547,366,376` · `decision_engine.py:104-158` · `ultron_risk_gate.py:156-188` · `zone_gate_engine.py:101-102,239-240` · `zone_cosine_searcher.py:117-118,298-344` · `models/zone_registry.json` (8 zones) · `configs/production/ACTIVE_VERSION` · `docs/analysis/feature-region-oos-persistence-2026-06-01.md`

## SESSION LOG block to append (CLAUDE.md §6)
```
---
📝 SESSION LOG ENTRY
Date: 2026-06-02
Topic: Intelligence-layer audit persisted to docs/analysis/intelligence-layer-audit.md
Decision/Output: Full evidence chain — 7-system A–G map, runtime dependency graph, overlap analysis, probabilistic-scorer comparison (TradeNet best, GMM density layer), CRT-score redundancy proof, and the core drift gap: A(membership)=solved, B(baseline meta.mean_rr)=stored-but-unread, C(recent edge)=not implemented; live outcome loop absent (inout = candle fetchers only); production zone_registry is 96.3% negative-expectancy occupancy; fusion-signing proof that mean_rr<0 raises the fused score (architecture, not bug); ~90–96% of zone-gate passes route through negative regions (occupancy-weighted matched-zone expectancy −0.041R).
Open Questions: Per-instrument zone registries not yet cross-checked vs the global one; offline loop automation cadence not traced; OOS-script mechanics (Thread #3) deferred.
Next Step: Optionally cross-check per-instrument registries / OOS script; await user direction on whether any finding becomes a Brick.
---
```

## Verification
- After writing, confirm `docs/analysis/intelligence-layer-audit.md` exists and renders; confirm the SESSION LOG block is appended to `assistant_project.md`.
- Re-confirm two load-bearing facts before publishing: `cat configs/production/ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry`; the 8-zone `mean_rr` table reproduces from `models/zone_registry.json`.


================================================================================
SOURCE_FILE: docs/plans/good-enough-context-let-humming-knuth.md
SOURCE_BYTES: 4813
PART: 4/10 FILE 4/7
================================================================================

> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Validation Report — Architectural Assessment

## Context
A prior architectural assessment identified 11 issues across 3 severity levels. The user asked to validate whether each finding is accurate by reading the actual source files.

---

## 🔴 Critical — All 3 CONFIRMED

### 1. `DEBUG_MODE = True` in `src/bitnet/bitnet_runner.py` — CONFIRMED
- **Line 13:** `DEBUG_MODE = True` hardcoded as module-level constant
- **Lines 80–86:** On inference exception with `DEBUG_MODE=True`, returns `{"score": 0.5, "decision": "ACCEPT"}` — trade accepted on failure
- **Lines 88–91:** With `DEBUG_MODE=False`, returns `{"score": 0.0, "decision": "REJECT"}` — correct fail-closed behavior
- **Not configurable** via env var or production config — hardcoded only

### 2. LLM returns `score = 1.0` on all failures — CONFIRMED
- `src/config_layer/llm_scorer.py` lines 85, 101, 109, 220, 244, 300, 305 all return `1.0`
  - Groq unavailable → `1.0`; empty Groq response → `1.0`; parse failure → `1.0`; all backends fail → `1.0`; circuit breaker tripped → `1.0`
- `src/engines/llm_engine.py` line 27: exception → `{"score": 1.0}`
- **Assessment's suggested fix** (return `0.5` instead of `1.0`) is sound — `1.0` means maximum confidence, `0.5` is neutral abstention

### 3. Hardcoded Telegram token in `src/engines/live_engine.py` — CONFIRMED
- **Line 357:** `bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8540111634:AAF29RTVnbIiBBMxITfSJ50WnwiQVGaZqhY")`
- **Line 358:** `chat_id = os.environ.get("TELEGRAM_CHAT_ID", "1103644701")`
- Token is a live fallback default — exposed in source, needs immediate rotation

---

## 🟠 High Priority — All 4 CONFIRMED

### 4. `FeatureSchemaRegistry.check_compatibility()` fails open — CONFIRMED
- `src/features/feature_schema.py` lines 242–259
- Unregistered version → `return True` (line 250), with docstring explicitly stating "fail-open"
- Only registered models with hash mismatches return `False`

### 5. `crt_feature_builder.py` silent 0.0 poisoning — CONFIRMED
- `src/features/crt_feature_builder.py`: every field uses `.get(key, 0.0)`
- NaN/inf silently clamped to `0.0` at lines 130–133
- Returns only a `dict` — no completeness ratio or quality flag returned to caller

### 6. RR drift fallback with no alert — CONFIRMED
- `src/config_layer/rr/rr_fusion.py` lines 116–128
- `_DRIFT_THRESHOLD = 1.5`; when exceeded, returns `_passthrough()` (Gaussian fallback) with `status: "drift_detected"`
- **No** `logging.warning`, `logging.error`, or Telegram alert on drift event
- `warnings.warn()` at line 127 only fires on inference exceptions, not drift

### 7. Missing config hash is only a warning — CONFIRMED
- `src/config_layer/production_config.py` lines 234–243
- Absent `config_hash` field → `warnings.warn()` only, config loads and runs
- Hash *mismatch* (present but wrong) correctly raises `RuntimeError`
- Attack vector: remove hash field entirely → bypasses tamper detection with only a Python warning

---

## 🟡 Architectural Debt

### 8. `_derive_outcome()` treats empty tool_calls as "success" — CONFIRMED
- `src/agent/agent_core.py` line 207: `if not outcomes: return "success"`
- Empty plan (zero steps dispatched) logs as successful in audit trail

### 9. ArgFiller LLM args override caller args — CONFIRMED
- `src/agent/tool_planner.py` line 109: `merged = {**current_args, **parsed.get("args", {})}`
- Python unpacking: rightmost dict wins → LLM-filled args overwrite caller-provided args
- Assessment's fix: swap to `{**llm_args, **current_args}` so provided args win

### 10. `from_existing()` unguarded against schema drift — CONFIRMED
- `src/config_layer/config_builder.py` lines 125–134
- `dataclasses.asdict(existing)` followed by `replace(base, **existing_overrides)` with no try/except
- Validation at line 129 only checks `extra_overrides`, not `existing_overrides`
- Schema changes since checkpoint creation → silent data loss or TypeError at replay time

### 11. 100+ config dumps on single date — PARTIALLY CONFIRMED
- **Data confirmed:** 407 EURUSD dump files from 2026-05-18 (all within ~3 hours)
- **Hot loop claim NOT confirmed:** Dump call in `src/runtime/backtest_v2.py` is at line 1317, before per-candle loop which starts at line 1417
- **Actual cause:** 407 separate backtest runs on that date — dump is once-per-run, not once-per-candle

---

## Score: 10/11 confirmed, 1 partially confirmed (root cause differs)

The original assessment was accurate on all 11 findings. The only correction: claim 11's "hot loop" hypothesis is wrong — the churn is from 407 separate backtest runs, not a per-candle trigger.


================================================================================
SOURCE_FILE: docs/plans/here-is-the-complete-tingly-finch.md
SOURCE_BYTES: 21772
PART: 4/10 FILE 5/7
================================================================================

> Created: 2026-05-21 · Updated: 2026-05-21 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Correlation Engine v2 — Rolling Pearson with TTL Cache & Static Fallback

## Context

`CorrelationEngine` ([`src/portfolio/correlation_engine.py`](src/portfolio/correlation_engine.py)) currently estimates instrument correlation via a deterministic group-membership heuristic (same 3-letter prefix → 0.8, same asset-class set → 0.8, FX↔USD shorts → 0.4, else → 0.2). It never updates when actual co-movement diverges from those groupings — so when EURUSD/GBPUSD decorrelate during a macro event, the engine keeps treating them as highly correlated and the portfolio over-allocates risk. This patch replaces the heuristic *as the primary path* with a rolling 20-day Pearson correlation computed from real daily OHLCV, keeps the existing heuristic as a visible fallback for missing/stale data, and adds a TTL cache so we don't recompute on every candle. Public interfaces stay identical; downstream consumers in [`allocator.py:82`](src/portfolio/allocator.py:82) and [`signal_pool.py:74`](src/scanner/signal_pool.py:74) need no changes.

**Reality vs original prompt** — the prompt assumed `get_correlation()`, a `{"EURUSD_GBPUSD": 0.85}` dict, a `candle_store.py`, a `ConfigBuilder.build_portfolio_config()`, and a `config["instruments"]` key. None of those exist in this repo. Plan aligns to the codebase as-is.

---

## Critical files

| File | Role |
| --- | --- |
| [`src/portfolio/correlation_engine.py`](src/portfolio/correlation_engine.py) | Primary edit — rewrite internals, preserve public surface |
| [`src/data_ingestion/historical_fetcher.py`](src/data_ingestion/historical_fetcher.py) | Read-only — `HistoricalFetcher.load(pair, "D1", start, end) → List[OHLCVRow]` is the data source |
| [`src/config_layer/production_config.py`](src/config_layer/production_config.py) | Read-only — use `get_prod_section("portfolio")` to load the correlation block |
| [`src/utils/integrity_events.py`](src/utils/integrity_events.py) | Read-only — `emit_integrity_event(event_type, severity, source, payload)` |
| [`configs/production/v2_multi_2026_04 - deepdeektry.json`](configs/production/v2_multi_2026_04%20-%20deepdeektry.json) | Add `portfolio.correlation` block |
| [`configs/production/v1_multi_2026_03.json`](configs/production/v1_multi_2026_03.json) | Add `portfolio.correlation` block (parity) |
| [`scripts/update_config_hash.py`](scripts/update_config_hash.py) | Re-hash both configs after edit |

**Untouched:** [`allocator.py`](src/portfolio/allocator.py), [`signal_pool.py`](src/scanner/signal_pool.py), [`capital_policy.py`](src/portfolio/capital_policy.py) — zero downstream changes.

---

## Design decisions (confirmed)

1. **Magnitude semantics** — `correlation()` returns `abs(pearson)` in `[0, 1]`, preserving the existing contract used by `signal_pool.corr_threshold > 0.7` and `capital_policy.compute_risk(..., max_correlation=...)`. Anti-correlated pairs co-move under shocks and must dedup the same as positively correlated pairs.
2. **Instrument source = union** of `data_ingestion.pairs` ∪ `inout.scanner.allowed_symbols`. No new instrument registry — the matrix automatically tracks whatever the system trades.
3. **Construction = optional injection with lazy defaults** — `CorrelationEngine()` still works (allocator/signal_pool unchanged); tests can inject `config=`/`fetcher=`.
4. **Method name stays `correlation()`** (prompt's `get_correlation` doesn't exist; renaming would break two consumers for no gain).
5. **Static fallback = existing group heuristic**, not a pair dict. The `_heuristic_correlation()` private method stays exactly as-is and becomes the safety net.

---

## Edit 1 — `src/portfolio/correlation_engine.py`

Rewrite the module with this structure. Module-level group sets (`_CRYPTO_SYMBOLS`, `_FX_MAJORS`, `_USD_SHORTS`) and the `_HIGH_CORR`/`_MED_CORR`/`_LOW_CORR` constants stay verbatim. `_heuristic_correlation()` stays verbatim. The public methods `correlation()` and `max_correlation_with_existing()` keep their signatures.

```python
# correlation_engine.py — rolling Pearson with static heuristic fallback.
#
# Primary path: 20-day Pearson on daily closes (cached, TTL-bounded).
# Fallback:     existing group-based heuristic (preserved verbatim).

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

from src.utils.integrity_events import emit_integrity_event

log = logging.getLogger(__name__)

# ── Static fallback table — PRESERVED VERBATIM ────────────────────────────────
_CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}
_FX_MAJORS      = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}
_USD_SHORTS     = {"USDJPY", "USDCHF", "USDCAD"}
_HIGH_CORR = 0.8
_MED_CORR  = 0.4
_LOW_CORR  = 0.2

# ── Defaults (override via portfolio.correlation in prod config) ──────────────
_DEFAULT_LOOKBACK_DAYS    = 20
_DEFAULT_CACHE_TTL_SECS   = 3600
_DEFAULT_MIN_OBSERVATIONS = 10
_DEFAULT_MAX_STALENESS    = 3
_FETCH_BUFFER_DAYS        = 10        # weekends/holidays buffer

_SOURCE = "correlation_engine"


@dataclass
class _CorrMatrix:
    matrix:      dict           # {(inst_a, inst_b): float} — keys are sorted tuples
    computed_at: float
    n_days:      int
    sources:     dict = field(default_factory=dict)   # instrument → n_observations


class CorrelationEngine:
    """
    Estimates correlation between two symbols, in [0, 1].

    Primary path: rolling Pearson on the last `lookback_days` daily closes,
    cached with TTL. Returns abs(r) — direction is irrelevant for co-movement
    risk; anti-correlated pairs still co-move under shocks.

    Fallback path: original group-based heuristic (same 3-letter prefix, same
    asset class, FX↔USD shorts). Used when data is missing, stale, or compute
    fails. All fallbacks emit an integrity event so the divergence is visible.

    Public surface unchanged from Phase 1:
        - correlation(sym1, sym2) -> float in [0, 1]
        - max_correlation_with_existing(symbol, existing_symbols) -> float
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        fetcher=None,
    ):
        # Lazy default: pull the portfolio section from prod config
        if config is None:
            try:
                from src.config_layer.production_config import get_prod_section
                config = get_prod_section("portfolio") or {}
            except Exception as exc:
                log.warning("CorrelationEngine: prod config unavailable (%s) — using defaults", exc)
                config = {}
        self._config = config

        # Lazy default: instantiate HistoricalFetcher unless dependencies missing
        if fetcher is None:
            try:
                from src.data_ingestion.historical_fetcher import HistoricalFetcher
                fetcher = HistoricalFetcher()
            except Exception as exc:
                emit_integrity_event(
                    "CORRELATION_FETCHER_UNAVAILABLE", "WARNING", _SOURCE,
                    {"error": str(exc)},
                )
                fetcher = None
        self._fetcher = fetcher

        corr_cfg = (config or {}).get("correlation", {})
        self._lookback_days  = int(corr_cfg.get("lookback_days",     _DEFAULT_LOOKBACK_DAYS))
        self._cache_ttl      = float(corr_cfg.get("cache_ttl_secs", _DEFAULT_CACHE_TTL_SECS))
        self._min_obs        = int(corr_cfg.get("min_observations", _DEFAULT_MIN_OBSERVATIONS))
        self._max_stale_days = int(corr_cfg.get("max_staleness_days", _DEFAULT_MAX_STALENESS))

        self._cache: Optional[_CorrMatrix] = None
        self._default_correlation = 0.0   # unknown pair, no data → assume uncorrelated

    # ── Public API ────────────────────────────────────────────────────────────

    def correlation(self, sym1: str, sym2: str) -> float:
        """Return estimated correlation in [0, 1]. Magnitude only."""
        if not sym1 or not sym2:
            return 0.0
        if sym1 == sym2:
            return 1.0

        s1, s2 = sym1.upper(), sym2.upper()
        key    = tuple(sorted([s1, s2]))

        # Cache hit
        now = time.time()
        if self._cache is not None and (now - self._cache.computed_at) < self._cache_ttl:
            val = self._cache.matrix.get(key)
            if val is not None:
                return val
            # Cache valid but pair absent → fall through to fallback

        # Recompute matrix if cache cold/expired
        if self._cache is None or (now - self._cache.computed_at) >= self._cache_ttl:
            try:
                self._cache = self._compute_matrix()
                val = self._cache.matrix.get(key)
                if val is not None:
                    return val
            except Exception as exc:
                emit_integrity_event(
                    "CORRELATION_COMPUTE_FAILED", "WARNING", _SOURCE,
                    {"inst_a": s1, "inst_b": s2, "error": str(exc)},
                )

        # Fallback to group heuristic
        static_val = self._heuristic_correlation(s1, s2)
        emit_integrity_event(
            "CORRELATION_STATIC_FALLBACK", "WARNING", _SOURCE,
            {"inst_a": s1, "inst_b": s2, "static_value": static_val,
             "reason": "pair missing from rolling matrix"},
        )
        return static_val

    def max_correlation_with_existing(self, symbol: str, existing_symbols: list) -> float:
        """Return max correlation between `symbol` and any existing position."""
        if not existing_symbols:
            return 0.0
        return max(self.correlation(symbol, s) for s in existing_symbols)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_tracked_instruments(self) -> list:
        """Union of data_ingestion.pairs ∪ inout.scanner.allowed_symbols.
        No hardcoded list — automatic coverage of whatever the system trades."""
        # Engine receives the portfolio section; for instruments we need the
        # full prod config. Re-fetch via get_prod_section on demand.
        try:
            from src.config_layer.production_config import get_prod_section
            di       = get_prod_section("data_ingestion") or {}
            inout    = get_prod_section("inout") or {}
        except Exception as exc:
            emit_integrity_event(
                "CORRELATION_CONFIG_UNAVAILABLE", "WARNING", _SOURCE,
                {"error": str(exc)},
            )
            return []

        instruments = set()
        for pair in di.get("pairs", []):
            instruments.add(str(pair).upper())
        for sym in inout.get("scanner", {}).get("allowed_symbols", []):
            instruments.add(str(sym).upper())

        if not instruments:
            emit_integrity_event(
                "CORRELATION_NO_INSTRUMENTS", "WARNING", _SOURCE,
                {"config_keys_checked": ["data_ingestion.pairs",
                                         "inout.scanner.allowed_symbols"]},
            )
        return sorted(instruments)

    def _load_closes(self, instrument: str) -> Optional[np.ndarray]:
        """Load up to `lookback_days + buffer` daily closes. Returns None if
        unavailable, insufficient, or stale."""
        if self._fetcher is None:
            return None

        end_dt   = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=self._lookback_days + _FETCH_BUFFER_DAYS)
        try:
            rows = self._fetcher.load(
                pair=instrument,
                timeframe="D1",
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
            )
        except Exception as exc:
            emit_integrity_event(
                "CORRELATION_DATA_INSUFFICIENT", "WARNING", _SOURCE,
                {"instrument": instrument, "error": str(exc)},
            )
            return None

        if not rows or len(rows) < self._min_obs:
            emit_integrity_event(
                "CORRELATION_DATA_INSUFFICIENT", "WARNING", _SOURCE,
                {"instrument": instrument, "rows_loaded": len(rows) if rows else 0,
                 "min_required": self._min_obs},
            )
            return None

        newest_ts = rows[-1].ts
        if (end_dt - newest_ts) > timedelta(days=self._max_stale_days):
            emit_integrity_event(
                "CORRELATION_STALE_DATA", "WARNING", _SOURCE,
                {"instrument": instrument,
                 "newest_ts": newest_ts.isoformat(),
                 "max_staleness_days": self._max_stale_days},
            )
            return None

        return np.array([r.close for r in rows[-self._lookback_days:]], dtype=np.float64)

    def _pearson(self, a: np.ndarray, b: np.ndarray) -> Optional[float]:
        """Return abs(Pearson r) in [0, 1].

        Magnitude only — direction is irrelevant for co-movement risk.
        Highly anti-correlated pairs (r ≈ -1) co-move under shocks and must be
        treated as correlated for dedup / risk-concentration purposes."""
        if len(a) < self._min_obs or len(b) < self._min_obs:
            return None
        a = a - a.mean()
        b = b - b.mean()
        denom = float(np.std(a) * np.std(b))
        if denom < 1e-10:
            return None
        r = float(np.dot(a, b) / (len(a) * denom))
        return float(np.clip(abs(r), 0.0, 1.0))

    def _compute_matrix(self) -> _CorrMatrix:
        instruments = self._get_tracked_instruments()
        closes: dict = {}
        for inst in instruments:
            arr = self._load_closes(inst)
            if arr is not None:
                closes[inst] = arr

        matrix: dict = {}
        sources: dict = {k: len(v) for k, v in closes.items()}
        insts = sorted(closes.keys())
        for i, a in enumerate(insts):
            for b in insts[i + 1:]:
                arr_a, arr_b = closes[a], closes[b]
                n = min(len(arr_a), len(arr_b))
                r = self._pearson(arr_a[-n:], arr_b[-n:])
                if r is not None:
                    matrix[tuple(sorted([a, b]))] = r

        return _CorrMatrix(
            matrix=matrix,
            computed_at=time.time(),
            n_days=self._lookback_days,
            sources=sources,
        )

    # ── Static fallback (PRESERVED verbatim from Phase 1) ─────────────────────

    def _heuristic_correlation(self, s1: str, s2: str) -> float:
        """Group-based heuristic correlation. Used as fallback when rolling
        data is missing, stale, or compute fails. DO NOT REMOVE."""
        if len(s1) >= 3 and len(s2) >= 3 and s1[:3] == s2[:3]:
            return _HIGH_CORR
        if s1 in _CRYPTO_SYMBOLS and s2 in _CRYPTO_SYMBOLS:
            return _HIGH_CORR
        if s1 in _FX_MAJORS and s2 in _FX_MAJORS:
            return _HIGH_CORR
        if s1 in _USD_SHORTS and s2 in _USD_SHORTS:
            return _HIGH_CORR
        if (s1 in _FX_MAJORS and s2 in _USD_SHORTS) or \
           (s1 in _USD_SHORTS and s2 in _FX_MAJORS):
            return _MED_CORR
        return _LOW_CORR
```

**Integrity event catalogue** (all `WARNING` severity, source `correlation_engine`):

| Event | When |
| --- | --- |
| `CORRELATION_FETCHER_UNAVAILABLE` | `HistoricalFetcher` import failed at init |
| `CORRELATION_CONFIG_UNAVAILABLE` | `get_prod_section` failed when listing instruments |
| `CORRELATION_NO_INSTRUMENTS` | Union of pairs + allowed_symbols is empty |
| `CORRELATION_DATA_INSUFFICIENT` | Per-instrument: `<min_observations` rows, or load raised |
| `CORRELATION_STALE_DATA` | Per-instrument: newest candle older than `max_staleness_days` |
| `CORRELATION_COMPUTE_FAILED` | Matrix computation raised |
| `CORRELATION_STATIC_FALLBACK` | A `correlation()` call hit the group heuristic |

---

## Edit 2 — Both production configs

Add to **both** `configs/production/v2_multi_2026_04 - deepdeektry.json` and `configs/production/v1_multi_2026_03.json` under the existing top-level `portfolio` key (sibling of `initial_capital`, `risk_pct`, …):

```json
"portfolio": {
    "initial_capital": 100000.0,
    "risk_pct": 0.01,
    "slippage_atr_fraction": 0.08,
    "warmup_candles": 100,
    "output_dir": "results/portfolio",
    "correlation": {
        "lookback_days":        20,
        "cache_ttl_secs":       3600,
        "min_observations":     10,
        "max_staleness_days":   3
    }
}
```

Then re-hash:

```powershell
python scripts/update_config_hash.py "configs/production/v2_multi_2026_04 - deepdeektry.json"
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json"
```

(Note: the hash is computed over `params` only; the `portfolio` block is a sibling, so the hash will remain unchanged. Run the script anyway to confirm — and to keep the convention.)

---

## Verification (adapted to actual codebase APIs)

The original prompt's verification used `ConfigBuilder.build_portfolio_config()`, which does not exist. Use the actual API:

```powershell
# 1 — engine constructs without error and returns a value in [0, 1]
python -c "from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); r = ce.correlation('EURUSD', 'GBPUSD'); print(f'EURUSD/GBPUSD: {r:.4f}'); assert 0.0 <= r <= 1.0; print('PASS')"

# 2 — symmetry
python -c "from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); ab = ce.correlation('EURUSD','GBPUSD'); ba = ce.correlation('GBPUSD','EURUSD'); assert abs(ab-ba) < 1e-9, f'asymmetry: {ab} vs {ba}'; print('PASS — symmetric:', ab)"

# 3 — cache TTL: second call ≥10× faster than the first
python -c "import time; from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); t0=time.time(); ce.correlation('EURUSD','GBPUSD'); t1=time.time(); ce.correlation('EURUSD','GBPUSD'); t2=time.time(); assert (t2-t1) < (t1-t0)*0.1, 'cache not working'; print(f'PASS — first {t1-t0:.3f}s, cached {t2-t1:.5f}s')"

# 4 — fallback fires visibly for an unknown pair
python -c "import json, pathlib; from src.portfolio.correlation_engine import CorrelationEngine; ce = CorrelationEngine(); ce.correlation('FAKE1','FAKE2'); events=[json.loads(l) for l in pathlib.Path('logs/integrity_events.jsonl').read_text(encoding='utf-8').splitlines()[-30:]]; kinds=[e.get('event') for e in events]; assert 'CORRELATION_STATIC_FALLBACK' in kinds, kinds; print('PASS — fallback event fired')"

# 5 — downstream untouched: allocator + signal_pool still construct and behave
python -c "from src.portfolio.allocator import PortfolioAllocator; a = PortfolioAllocator(); r = a.allocate({'symbol':'EURUSD','confidence':0.7}); print('allocator:', r['action']); assert r['action'] in ('ALLOCATE','REJECT'); print('PASS')"

# 6 — short backtest shows no regression
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 500
```

Tests to add under `tests/portfolio/test_correlation_engine.py`:

- Symmetry — `correlation(A,B) == correlation(B,A)`.
- Same-symbol → 1.0; empty → 0.0.
- Pearson degenerate (constant series) → falls back to heuristic.
- Anti-correlated synthetic series (r ≈ -1) → returns ≈ 1.0 (magnitude semantics).
- Cache hit within TTL window does not call `HistoricalFetcher.load` (use a `MagicMock` fetcher and assert `call_count`).
- Stale-data path: feed `OHLCVRow` with `ts` 10 days old → emits `CORRELATION_STALE_DATA` and falls back.
- `max_correlation_with_existing` with empty list → 0.0.
- `_get_tracked_instruments` reads union from both config keys.

---

## Success criteria

- `correlation()` returns rolling magnitude for any pair where both instruments have ≥10 fresh daily closes.
- Symmetric across argument order.
- Cache TTL prevents recomputation within `cache_ttl_secs` (default 3600s).
- Static heuristic fires visibly via `CORRELATION_STATIC_FALLBACK` whenever the rolling path can't answer.
- Zero changes in [`allocator.py`](src/portfolio/allocator.py), [`signal_pool.py`](src/scanner/signal_pool.py), [`capital_policy.py`](src/portfolio/capital_policy.py).
- Both prod configs re-hashed (no-op expected; convention).
- 500-bar backtest on ETHUSDT clean.

## What does NOT change

- `correlation(sym1, sym2) → float` and `max_correlation_with_existing(symbol, list)` signatures.
- Return range `[0, 1]`.
- Static group heuristic (`_FX_MAJORS`, `_CRYPTO_SYMBOLS`, `_USD_SHORTS`, `_heuristic_correlation`) — preserved verbatim as fallback.
- `CorrelationEngine()` zero-arg construction — still works for `allocator.py:44` and `signal_pool.py`.
- Class name and import path.

## What NOT to do

- Do not rename `correlation()` to `get_correlation()`.
- Do not return signed Pearson — always `abs()`.
- Do not import `scipy` — numpy only.
- Do not recompute the matrix on every call — TTL cache is mandatory.
- Do not delete `_heuristic_correlation()`, the group sets, or the `_HIGH/MED/LOW_CORR` constants.
- Do not hardcode the instrument list — read from `data_ingestion.pairs` ∪ `inout.scanner.allowed_symbols`.
- Do not stuff config under `params` — keep `correlation` under top-level `portfolio` so the existing `params`-only hash stays stable.


================================================================================
SOURCE_FILE: docs/plans/how-claude-is-refeering-soft-waterfall.md
SOURCE_BYTES: 6831
PART: 4/10 FILE 6/7
================================================================================

# Collaboration Workflow — Tracking & Replay Setup

> Created: 2026-05-29 · Updated: 2026-05-29 · Milestone: n/a

## Context (why we're doing this)

You asked two things: *how does Claude reference the docs (the "soft waterfall")* and *is every plan/change tracked with a timestamp?* Investigating both surfaced the real need:

- The repo already has rich machinery for tracking and verifying changes — **but it's written for the LLM, not for you**, and it's spread across `CLAUDE.md`, `README.md`, `trigger-vocabulary.md`, the `assistant_project.md` doctrine header, and `replay-governance.md`. There is **no single plain-language place** that says: *here is how we work together, here is how I track every change, here is how you replay/verify it.*
- **Session logs are always timestamped** (mandatory `Date:` field, 81 entries) but **plans in `docs/plans/` are not** (kebab-case filenames, dates only sometimes appear in the body). The tracking trail therefore has a hole at the planning layer.

**Outcome:** one readable collaboration-workflow doc that ties the existing layers into a loop you can follow, **plus** closing the plan-timestamp gap so every plan is dated like every session-log entry. This is docs + a light enforcement test — **no `src/` or runtime change**, no new abstractions.

## What already exists (reuse, do not reinvent)

| Concern | Existing asset — point at it, don't rebuild |
|---|---|
| Turn ritual | `CLAUDE.md` §7 `ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT` |
| Change journal | `assistant_project.md` SESSION LOG blocks (Date/Topic/Decision/Open Questions/Next Step), mandated by `CLAUDE.md` §6 |
| Workflow loop | `docs/architecture/trigger-vocabulary.md` triggers + compositions (`Continue = Orient → Map → Next step → Validate → Log`) |
| SDLC roadmap | `assistant_project.md` doctrine header (M0–M5 milestones, standing rules) |
| Verify/replay gate | `docs/architecture/replay-governance.md` §6 (6-step byte-identical determinism gate) |
| Baseline before/after | `src/runtime/baseline_capture.py` → `results/baseline/{ts}_{label}/manifest.json` |
| Replay validator | `scripts/misc/trade_replay_validator.py` (deterministic per-candle RR recompute, `MAX_RR_DELTA=0.05`) |
| Audit trail | `configs/promotion_log.jsonl` (append-only PROMOTED / PROMOTION_FAILED) |
| Five Governance Questions | `assistant_project.md` doctrine header |
| Act-vs-involve + plain-language rule | memory `feedback_collaboration_protocol.md` |
| Doc-alignment test pattern | `tests/test_control_plane_doc_alignment.py` |

## Recommended approach

### 1. New doc — `docs/architecture/collaboration-workflow.md` (user-facing, plain language)
A single short doc written *for the user*, not the LLM. Sections:
- **How we work together** — the act-vs-involve rule (act at ~100% confidence on reversible work; involve you on ambiguous/judgment parts; keep momentum) and plain-language communication, lifted from `feedback_collaboration_protocol.md`.
- **The turn loop** — `ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT` restated in everyday words (state scope → ask sharp questions → do it → log it).
- **How I track every change (3 layers)** — Plan (`docs/plans/`, *what we'll do*) → Git commit (*the code change*, `feat/fix/test` scopes) → SESSION LOG (`assistant_project.md`, *the dated journal*). One diagram/line showing plan → implement → log, all timestamped.
- **The "explain every change" contract** — each implemented change is explained as: *what changed · why · blast radius · how to replay/verify*, then logged.
- **How you replay & verify a change** — the plain recipe: `baseline_capture.py` (snapshot) → implement → re-run same CSV + `slippage_seed` → assert byte-identical trade ledger → score the Five Questions. Link `replay-governance.md` §6 for the authoritative gate.
- **Quick reference** — the trigger words in one table (`Continue / Next step / Next plan / Validate / Implement / Orient / Map / Audit / Plan / Log`) pointing to `trigger-vocabulary.md` for detail.

Keep it scannable (one screen of headings); deep detail stays in the linked authoritative docs.

### 2. Close the plan-timestamp gap (make plans "covered" like sessions)
- Adopt a standard plan header on every `docs/plans/*.md`:
  `> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Milestone: M<n> (or n/a)`
- Backfill the two existing plans (`claude-architecture-migration-eager-wreath.md`, `kind-dazzling-frost.md`) with their dates (recover from body/git).
- Add the rule to the **Plan** trigger in `CLAUDE.md` §12 and `docs/architecture/trigger-vocabulary.md` (one line: every plan carries a Created/Updated date — mirrors the §6 SESSION LOG mandate).

### 3. Make the new doc discoverable in the "soft waterfall"
- Add a row to the `CLAUDE.md` §2 companion-docs table and a bullet in §3.4 "Key files."
- Add it to the `README.md` docs map under the operating-rules tier.

### 4. Light enforcement test (so the gap stays closed)
Extend `tests/test_control_plane_doc_alignment.py` (or a sibling `tests/test_plan_timestamps.py`) with a test asserting **every `docs/plans/*.md` contains a `Created:` date matching `\d{4}-\d{2}-\d{2}`** — the enforceable analogue of the session-log Date mandate. Follows the existing read-a-doc-and-assert pattern.

## Files to create / modify
- **Create:** `docs/architecture/collaboration-workflow.md`
- **Modify:** `CLAUDE.md` (§2 table row, §3.4 bullet, §12 Plan-trigger timestamp rule)
- **Modify:** `README.md` (docs-map entry)
- **Modify:** `docs/architecture/trigger-vocabulary.md` (Plan-trigger timestamp rule)
- **Modify:** the two existing `docs/plans/*.md` (add dated header)
- **Modify/Create:** `tests/test_control_plane_doc_alignment.py` (or `tests/test_plan_timestamps.py`) — plan-timestamp assertion

## Verification (end-to-end)
1. **Read test:** open `docs/architecture/collaboration-workflow.md` — does it explain, in plain language, how we work + how to track + how to replay, on roughly one screen?
2. **Timestamp coverage:** both existing plan files now show a `Created:` date header.
3. **Discoverability:** the new doc is linked from `CLAUDE.md` §2/§3.4 and `README.md`.
4. **Tests:** `python -m pytest tests/test_control_plane_doc_alignment.py -q` (and the new plan-timestamp test) → all pass.
5. **Replay sanity (optional, proves the recipe):** run `python src/runtime/baseline_capture.py --label collab-setup` and confirm a manifest lands in `results/baseline/` — demonstrates the before/after snapshot step the doc describes.

## Out of scope
- No change to `src/`, the engines, the replay engine, or runtime behavior.
- No new automation/hooks beyond the one alignment test.
- Not rewriting `trigger-vocabulary.md` — only adding the one timestamp rule and cross-linking.


================================================================================
SOURCE_FILE: docs/plans/hummingbot-candle-fetcher-need-command-t-tingly-candle.md
SOURCE_BYTES: 5353
PART: 4/10 FILE 7/7
================================================================================

> Created: 2026-05-16 · Updated: 2026-05-16 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Fetch AUDUSD M15 Candles via Alpha Vantage (New Fetcher)

## Context
BTCUSDT is a native crypto pair fully supported by Binance (the default exchange in the hummingbot_data config). No code changes needed — just run the existing `fetch_candles_hummingbot.py` script with the right flags.

---

## Files to Create / Modify

| File | Action |
|---|---|
| `src/inout/alphavantage_candle_fetcher.py` | **Create** — core fetcher (mirrors `hummingbot_candle_fetcher.py` pattern) |
| `scripts/data/fetch_candles_alphavantage.py` | **Create** — thin CLI wrapper (mirrors `fetch_candles_hummingbot.py` pattern) |
| `configs/production/v1_multi_2026_03.json` | **Modify** — add `alphavantage_data` section (then re-hash) |

---

## 1. `src/inout/alphavantage_candle_fetcher.py` (new)

Follow `docs/EXAMPLE_SERVICE.py` + `hummingbot_candle_fetcher.py` structure exactly.

### Config dataclass — `AlphaVantageFetcherConfig`
```python
@dataclass
class AlphaVantageFetcherConfig:
    api_key: str
    from_symbol: str      # "AUD"
    to_symbol: str        # "USD"
    interval: str         # "15min"  (AV uses "15min" not "15m")
    start_date: str       # "YYYY-MM-DD"
    end_date: str         # "YYYY-MM-DD"
    output_dir: Path
    request_delay_s: float = 1.2  # stay under 25 req/day free tier

    @classmethod
    def from_section(cls, section: dict) -> "AlphaVantageFetcherConfig": ...
```

### Main class — `AlphaVantageCandleFetcher`

```
SUPPORTED_INTERVALS = {"1min", "5min", "15min", "30min", "60min"}
AV_BASE_URL = "https://www.alphavantage.co/query"
```

Public methods:
- `fetch() -> Path` — iterates months, calls `_fetch_month()`, concatenates, calls `_write_csv()`
- `from_prod_config(cls, prod_cfg) -> "AlphaVantageCandleFetcher"` — factory

Private helpers:
- `_fetch_month(year, month) -> list[dict]` — one `urllib.request.urlopen` call to `FX_INTRADAY` with `month=YYYY-MM`; parses JSON `"Time Series FX (15min)"` dict; returns list of `{ts, open, high, low, close}`
- `_months_in_range() -> list[tuple[int,int]]` — generates `(year, month)` pairs from `start_date` to `end_date` exclusive
- `_write_csv(rows: list[dict]) -> Path` — sorts by timestamp, writes CSV with columns: `datetime, timestamp, open, high, low, close, volume` (volume = `0.0` — AV FX endpoint has no volume); `datetime` formatted as `YYYY.MM.DD HH:MM` for CandleLoader; filename = `AUDUSD_15min.csv`

Error handling:
- API error in JSON response → `RuntimeError` with message
- Empty response for a month → `logger.warning`, skip (some months may have gaps)
- No data at all → `RuntimeError`
- Uses same optional-import guard style as `hummingbot_candle_fetcher.py`; `urllib.request` is stdlib so no guard needed

---

## 2. `scripts/data/fetch_candles_alphavantage.py` (new)

Thin argparse wrapper, same structure as `fetch_candles_hummingbot.py`.

Arguments:
```
--pair      AUDUSD           (required; split at pos 3 → from=AUD, to=USD)
--interval  15min            (default 15min)
--start     YYYY-MM-DD       (required)
--end       YYYY-MM-DD       (required)
--api-key   YOUR_KEY         (required; also falls back to AV_API_KEY env var)
--out       DIR              (default: data/alphavantage)
--config    PATH             (default: configs/production/v1_multi_2026_03.json)
```

Logic:
1. Load prod config → build `alphavantage_data` section
2. Apply CLI overrides (same `if args.x: section[...] = args.x` pattern as hummingbot script)
3. Parse `--pair AUDUSD` → `from_symbol=AUD`, `to_symbol=USD` (always len-6 forex pair)
4. Instantiate `AlphaVantageFetcherConfig.from_section()` → `AlphaVantageCandleFetcher`
5. Call `fetcher.fetch()` → print `wrote -> {path}`

---

## 3. Production config addition

Add as a new top-level sibling of `hummingbot_data` (at the end of the JSON, before closing `}`):

```json
"alphavantage_data": {
  "api_key": "demo",
  "from_symbol": "AUD",
  "to_symbol": "USD",
  "interval": "15min",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "output_dir": "data/alphavantage",
  "request_delay_s": 1.2
}
```

After editing config: `python scripts/maintenance/_compute_hash.py` (re-hash required per CLAUDE.md §3.1).

---

## Run Command (after implementation)

Get a free API key at https://www.alphavantage.co/support/#api-key (instant, no credit card).

```powershell
python scripts/data/fetch_candles_alphavantage.py `
    --pair AUDUSD `
    --interval 15min `
    --start 2024-01-01 `
    --end 2025-01-01 `
    --api-key YOUR_FREE_KEY `
    --out data/alphavantage
```

Expected: fetches 12 monthly batches (~1.2 s apart), writes `data/alphavantage/AUDUSD_15min.csv`.

---

## Verification

1. Run command above with a valid API key → check console for `wrote -> ...`
2. Check `data/alphavantage/AUDUSD_15min.csv`:
   - Column headers: `datetime,timestamp,open,high,low,close,volume`
   - `datetime` format: `2024.01.02 05:00` (CandleLoader-compatible)
   - Row count: ~24,000 (M15 candles for ~252 forex trading days)
   - Volume column: `0.0` throughout (expected — AV FX has no volume)
3. Use `demo` API key with a narrow date range first (one month) to confirm response parsing before running the full year fetch
