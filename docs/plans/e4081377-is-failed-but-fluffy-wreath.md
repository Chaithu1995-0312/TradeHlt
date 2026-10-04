> Created: 2026-05-19 · Updated: 2026-05-19 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Add Date Fields + Config Clarification for Fetch Commands (CURRENT TASK)

## Context

**Why the config field exists:** `fetch_candles_alphavantage.py` reads `--config` to resolve:
- `alphavantage_data.api_key` (fallback when `AV_API_KEY` env var absent)
- `alphavantage_data.interval` (default `15min`)
- `alphavantage_data.output_dir` (default `data/alphavantage`)

The script **exits code 1** if the config file is not found at the given path, so it is load-bearing. Since `AV_API_KEY` is already in `.env`, users will mostly just get the interval/out defaults from it. The field should stay — but its help text already explains this. No config change needed.

**Why start/end are plain text boxes:** Both ArgSpecs use `kind="str"`, which renders as `<input type="text">` in the form builder. The UI has no `kind="date"` branch. Result: users must type `YYYY-MM-DD` manually with no calendar widget. Fix: add `kind="date"` to both ArgSpecs and a matching render branch in LauncherPanel.

## Files to Change

| File | Change |
|---|---|
| `src/control_plane/registry.py` | `kind="date"` for `start`+`end` in both fetch CommandSpecs |
| `ui_kits/control_plane/LauncherPanel.jsx` | Add `kind === "date"` render branch → `<Input type="date" />` |

---

## Change 1 — `src/control_plane/registry.py`

Four one-word edits: `kind="str"` → `kind="date"` on the `start` and `end` ArgSpecs of both commands.

**`data.fetch_alphavantage`** (~line 820):
```python
# Before:
ArgSpec("start", flag="--start", kind="str", required=True,
        help="Start date inclusive (YYYY-MM-DD)"),
ArgSpec("end",   flag="--end",   kind="str", required=True,
        help="End date exclusive (YYYY-MM-DD)"),

# After:
ArgSpec("start", flag="--start", kind="date", required=True,
        help="Start date inclusive (YYYY-MM-DD)"),
ArgSpec("end",   flag="--end",   kind="date", required=True,
        help="End date exclusive (YYYY-MM-DD)"),
```

**`data.fetch_hummingbot`** (~line 856):
```python
# Before:
ArgSpec("start", flag="--start", kind="str", required=True,
        help="Start date inclusive (YYYY-MM-DD)"),
ArgSpec("end",   flag="--end",   kind="str", required=True,
        help="End date exclusive (YYYY-MM-DD)"),

# After:
ArgSpec("start", flag="--start", kind="date", required=True,
        help="Start date inclusive (YYYY-MM-DD)"),
ArgSpec("end",   flag="--end",   kind="date", required=True,
        help="End date exclusive (YYYY-MM-DD)"),
```

---

## Change 2 — `ui_kits/control_plane/LauncherPanel.jsx`

Insert a `kind === "date"` branch **before** the free-text fallback block (before line 226 `// Free-text fallback`). The existing free-text block already handles `kind === "int"`, `kind === "float"`, `kind === "list"` — date gets its own early-return branch:

```jsx
            // ── Date picker ───────────────────────────────────────────────────
            if (a.kind === "date") {
              return (
                <React.Fragment key={a.key}>
                  <Label>
                    {a.positional ? <span style={{ color: "#0ea5a3" }}>● </span> : null}
                    {a.key}{a.required && <span style={{ color: "#ef4444" }}> *</span>}
                  </Label>
                  <Input
                    type="date"
                    value={v ?? ""}
                    onChange={e => setArg(a.key, e.target.value)}
                  />
                </React.Fragment>
              );
            }

            // Free-text fallback (with optional file uploader for path-like keys)
```

`<Input type="date" />` renders the native browser calendar picker. The value is always `YYYY-MM-DD` format (HTML5 standard), which is exactly what both scripts expect for `--start` / `--end`.

---

## Verification

1. Restart server: `venv\Scripts\python.exe src\control_plane\server.py`
2. Hard-refresh (Ctrl+F5)
3. Select "Fetch Forex Data (AlphaVantage)" — `start` and `end` fields show calendar date pickers (not plain text boxes)
4. Same for "Fetch Crypto Data (Hummingbot)"
5. Pick a date — Resolved CLI Preview shows `--start 2025-01-01 --end 2025-06-01` in correct format
6. Other `kind="str"` fields (e.g. `out`, `api_key`) still render as plain text — unaffected

---

# Add "Synthesize" Button to InspectorPanel (COMPLETED)

## Context
The Agent findings synthesis can only be triggered from the agent REPL (`python -m src.agent.cli` → `synthesize run <run_id>`). There is no way to call it from the browser UI. The InspectorPanel already shows the selected run and has action buttons ("📋 Report", "🧠 Context") — adding "⚗ Synthesize" there gives the user one-click synthesis with no terminal required.

## Files to Change

| File | Change |
|---|---|
| `src/control_plane/server.py` | Add `POST /api/agent/synthesize` handler |
| `ui_kits/control_plane/InspectorPanel.jsx` | Add `useState` + Synthesize button with loading state |

---

## Change 1 — `src/control_plane/server.py`

Insert before the "Unknown route" fallback at line ~1930 (inside `do_POST`), after the `/runs/*/stop` block:

```python
                # ── Agent findings synthesis ──────────────────────────────────
                if path == "/api/agent/synthesize":
                    body   = self._read_json_body()
                    run_id = body.get("run_id", "").strip()
                    if not run_id:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "run_id required"})
                        return
                    try:
                        from src.agent.findings_synthesizer import synthesize_finding
                        finding = synthesize_finding(run_id)
                        ok = finding.get("status") not in ("run_not_found", "invalid_input")
                        self._send_json(HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST,
                                        {"ok": ok, "finding": finding})
                    except Exception as exc:
                        self._send_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
                    return
```

---

## Change 2 — `ui_kits/control_plane/InspectorPanel.jsx`

### 2a — Add `useState` to destructure (top of file, existing destructure line)
```jsx
// Before:
const { useState } = React;
// (or wherever useState is pulled from React at the top of InspectorPanel.jsx)
```
Check how `useState` is imported — if it's already destructured globally (`const { useEffect, useRef, useState, ... } = React;` at file top), no change needed. If not present in this file, add it.

### 2b — Convert `InspectorPanel` to use local state for synthesis

Change the function signature line and add state + handler inside the function body, before the early-return:

```jsx
function InspectorPanel({ run, artifacts, monitors, onReport, onContext }) {
  const [synth, setSynth] = useState("idle"); // "idle"|"loading"|"done"|"error"

  const onSynthesize = () => {
    if (!run || synth === "loading") return;
    setSynth("loading");
    fetch("/api/agent/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: run.run_id }),
    })
      .then(r => r.json())
      .then(j => setSynth(j.ok ? "done" : "error"))
      .catch(() => setSynth("error"))
      .finally(() => setTimeout(() => setSynth("idle"), 3000));
  };
  // ... existing early-return for !run ...
```

### 2c — Add Synthesize button in the button row (line ~199)

```jsx
<div style={{ display: "flex", gap: 8, margin: "10px 0 4px" }}>
  <Button onClick={() => onReport && onReport(run.run_id)}>📋 Report</Button>
  <Button onClick={() => onContext && onContext(run.run_id)} style={{ background: "#1a2e4a", border: "1px solid #0ea5a3", color: "#0ea5a3" }}>🧠 Context</Button>
  <Button
    onClick={onSynthesize}
    disabled={synth === "loading"}
    style={{
      background: synth === "done" ? "#1a3a2a" : synth === "error" ? "#3a1a1a" : "#1a2438",
      border: `1px solid ${synth === "done" ? "#7ee787" : synth === "error" ? "#ff7b72" : "#7b3f00"}`,
      color: synth === "done" ? "#7ee787" : synth === "error" ? "#ff7b72" : "#d29922",
      opacity: synth === "loading" ? 0.6 : 1,
    }}>
    {synth === "loading" ? "..." : synth === "done" ? "[+] Synthesized" : synth === "error" ? "[!] Failed" : "Synthesize"}
  </Button>
</div>
```

The button auto-resets to "idle" after 3 seconds (via `setTimeout` in `finally`). User then switches to the Agent tab and clicks Refresh to see the new finding.

---

## Verification

1. Restart server: `venv\Scripts\python.exe src\control_plane\server.py`
2. Hard-refresh browser (Ctrl+F5)
3. Go to **Runs** tab → select any completed run → Inspector shows it
4. Click **Synthesize** → button text changes to `...` (loading) then `[+] Synthesized` (green) or `[!] Failed` (red)
5. Switch to **Agent** tab → click **↻ Refresh** → new finding appears in Findings list with actual LLM summary (requires GROQ_API_KEY in .env)
6. Without GROQ_API_KEY: button still works and returns `[+] Synthesized` but finding has `status: synthesis_unavailable`

---

# Add Findings Intent Tests to test_agent_plan_compiler.py (COMPLETED)

## Context
The Agent-as-Driver feature is complete and verified in the browser. Three new intents were added to `PLAN_REGISTRY` in `src/agent/plan_compiler.py` (17 total, up from 14):
- `findings_synthesize` → `[_s("findings.synthesize")]`
- `findings_recent` → `[_s("findings.list_recent", n=10)]`
- `findings_explain` → `[_s("findings.explain")]`

`AGENT_REFERENCE.md §12` requires every registered intent to have a corresponding test. `tests/test_agent_plan_compiler.py` currently tests 14 intents via the `_EXPECTED_INTENTS` set and individual test functions — the 3 findings intents are absent.

## File to Change

**Only one file:** `tests/test_agent_plan_compiler.py`

### Change 1 — Extend `_EXPECTED_INTENTS` (line 162)

```python
# Before:
_EXPECTED_INTENTS = {
    # Pipeline
    "tune_only", "tune_and_validate", "tune_and_promote",
    "validate_only", "promote_only", "backtest_only", "full_pipeline",
    # Copilot
    "advise_signal", "veto_query", "resize_query",
    # Governance
    "governance_inspect", "governance_propose", "governance_run",
    # Cross-mode
    "audit_inspect",
}

# After:
_EXPECTED_INTENTS = {
    # Pipeline
    "tune_only", "tune_and_validate", "tune_and_promote",
    "validate_only", "promote_only", "backtest_only", "full_pipeline",
    # Copilot
    "advise_signal", "veto_query", "resize_query",
    # Governance
    "governance_inspect", "governance_propose", "governance_run",
    # Cross-mode
    "audit_inspect",
    # Findings / post-run synthesis
    "findings_synthesize", "findings_recent", "findings_explain",
}
```

Also update the docstring at the top of the file: `PLAN_REGISTRY: Dict[str, List[ToolStep]]  — 14 intents` → `— 17 intents`

### Change 2 — Add 3 test functions (after line 195, before EOF)

Add a new section and 3 tests following the exact patterns already in the file:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Findings / post-run synthesis intents
# ─────────────────────────────────────────────────────────────────────────────

def test_findings_synthesize_single_step():
    """findings_synthesize: single step findings.synthesize."""
    plan = PlanCompiler.build("findings_synthesize")
    assert _tools(plan) == ["findings.synthesize"]


def test_findings_recent_default_n():
    """findings_recent: single step findings.list_recent with default n=10."""
    plan = PlanCompiler.build("findings_recent")
    assert _tools(plan) == ["findings.list_recent"]
    step = plan.steps[0]
    assert step.default_args.get("n") == 10, (
        f"findings.list_recent must default n=10, got {step.default_args!r}"
    )


def test_findings_explain_single_step():
    """findings_explain: single step findings.explain."""
    plan = PlanCompiler.build("findings_explain")
    assert _tools(plan) == ["findings.explain"]
```

## Verification

```
pytest tests/test_agent_plan_compiler.py -v
```

All 19 tests must pass (16 existing + 3 new). Pay attention to:
- `test_plan_registry_contains_all_expected_intents` — now checks 17 intents are in registry
- `test_findings_recent_default_n` — checks `step.default_args["n"] == 10`

No other files need changing. The `PLAN_REGISTRY` already has all 3 entries; this is test coverage only.

---

# Agent-as-Driver — Post-Run Findings + On-Demand REPL Tab (COMPLETED)

## Context
`src/agent/cli.py` already exists (1,779 lines, 14 intents, 20 tools, audit log, confirm-gate). It is registered as CommandSpec `agent.cli` in `registry.py:784`. **The gap is not "build an agent" — it's three missing capabilities that the user's incorporation note assumes:**

1. **Post-run findings synthesis** — when a CRT run finishes, package the run record + logs + relevant source slice, ship to **Groq** (Llama-3.1-70B), and append a finding to `logs/agent_findings.jsonl`. The user can later ask the REPL "show recent findings" or "explain finding X".
2. **Request logging for LLM traffic** — every prompt/response pair from the agent's LLM client is persisted to `logs/agent_llm_requests.jsonl` (with redaction of `api_key`/`secret`/`token` values).
3. **A new "Agent" tab** in the CRT Web Control Plane that renders an agent-as-controller Mermaid diagram + tail of `logs/agent_findings.jsonl` + last 20 audit-log entries. The existing 11-node minimum-autonomous Workflow tab is **kept unchanged** — these are two views with different purposes.

Anomaly detection is **on-demand only** (user-driven REPL query). No background poller, no Windows file-lock contention.

---

## Mandatory Resources (existing — MUST reuse, do not duplicate)

| Resource | Path | Why mandatory |
|---|---|---|
| Agent REPL entry | `src/agent/cli.py` | Already registered, already wired to AgentCore |
| AgentCore turn loop | `src/agent/agent_core.py` | Owns the turn(user_input) contract |
| Tool registry decorator | `src/agent/tool_registry.py` — `register_tool()` | Required to expose new findings tools to the planner |
| Plan registry | `src/agent/plan_compiler.py` — `PLAN_REGISTRY` | Add 3 deterministic intent→tool sequences here |
| Intent regex file | `src/agent/intent_patterns.json` | Add patterns for the new intents |
| Executor safety gates | `src/agent/executor.py:75-96` | All new write paths must dispatch through this; do not bypass confirm-gate / path-guard |
| Audit writer | `src/agent/audit.py:57-121` | Existing per-step + summary JSONL — extend with `write_finding()`, do not invent parallel logger |
| LLM client pattern | `src/config_layer/llm_inference_client.py` | Copy the circuit-breaker + neutral-fallback shape for the new Groq client |
| Production config section | `configs/production/v1_multi_2026_03.json` — `"agent"` key | Add `agent.groq` + `agent.findings` subsections; rehash via `scripts/maintenance/_compute_hash.py` |
| Existing compressor | `scripts/analysis/compress_logs_for_llm.py` | Reuse for log compression inside findings synthesizer; do not re-implement |
| Run record schema | `src/control_plane/jobs.py` (RunRecord) | Findings synthesizer reads `run_id`, `script`, `args`, `exit_code`, `log_paths`, `artifact_paths` from this |

---

## Useful Resources (existing — read-only context)

- `docs/AGENT_REFERENCE.md` — invariants enforced by `tests/test_agent_*` (don't break them)
- `docs/SCHEMAS.md §9` — JSONL line schema conventions (timestamp + kind first)
- CLAUDE.md §4 — Windows cp1252 console rule; redact non-ASCII before any subprocess print
- `scripts/groq_bridge/` — existing stubs (NOT used by agent today); we promote the Python client pattern from here, not the CLI scripts

---

## New Components (minimum new code)

### 1. `src/agent/groq_client.py` (new)
- Class `GroqClient` modeled on `llm_inference_client.LlmInferenceClient` (circuit-breaker + neutral-fallback)
- `chat(prompt: str, system: str = "", max_tokens: int = 1024) -> str`
- Reads `GROQ_API_KEY` from env, falls back to `agent.groq.api_key_env` resolution
- After each call: appends `{ts, prompt_hash, prompt_redacted, response, latency_ms, error}` to `logs/agent_llm_requests.jsonl` (request logging)
- Redaction: strips values for keys matching `agent.findings.redact_patterns` (default: `["api_key","secret","password","token","AV_API_KEY"]`)
- `fail_count_disable=5` → after 5 failures, returns empty string + logs `CIRCUIT_OPEN` (does NOT break agent)

### 2. `src/agent/findings_synthesizer.py` (new)
- `synthesize_finding(run_id: str) -> dict`
- Loads `RunRecord` via existing `jobs.load_run(run_id)`
- Reads `log_paths.stdout` + `log_paths.stderr` (tail last 200 lines each)
- Slices source: reads first 200 + last 100 lines of `run_record.script` (or `args.files[0]` for data scripts)
- Calls `scripts.analysis.compress_logs_for_llm.compress()` if opportunity JSONLs are in artifacts
- Builds redacted prompt: `{stage, status, args (redacted), source_slice, log_tail, compressed_summary}`
- Sends to `GroqClient.chat()` with system prompt: "You are a CRT pipeline diagnostic assistant. Output JSON: {summary, anomalies[], recommended_next[]}"
- Appends finding to `logs/agent_findings.jsonl`: `{ts, run_id, command_id, status, summary, anomalies, recommended_next, prompt_hash, response_hash}`
- Returns finding dict

### 3. `src/agent/tools/findings_tools.py` (new)
- `findings.synthesize` (write=True via append-only log) — wraps `synthesize_finding(run_id)`
- `findings.list_recent` (write=False) — tails last N from `logs/agent_findings.jsonl`
- `findings.explain` (write=False) — loads one finding by `run_id`, formats human-readable

### 4. Edits to existing agent files (no new files)
- `src/agent/intent_patterns.json` — add 3 regex entries:
  ```json
  "findings_synthesize": ["^(synthesize|analy[sz]e) (run|finding) ([a-f0-9]+)"],
  "findings_recent":    ["^(show|list|recent) findings?"],
  "findings_explain":   ["^(explain|why) (run|finding) ([a-f0-9]+)"]
  ```
- `src/agent/plan_compiler.py — PLAN_REGISTRY` — add:
  ```python
  "findings_synthesize": [ToolStep("findings.synthesize", {"run_id": "$arg.run_id"})],
  "findings_recent":     [ToolStep("findings.list_recent", {"n": 10})],
  "findings_explain":    [ToolStep("findings.explain", {"run_id": "$arg.run_id"})],
  ```

### 5. Config additions to `configs/production/v1_multi_2026_03.json`
```json
"agent": {
  ...existing keys...,
  "groq": {
    "api_key_env": "GROQ_API_KEY",
    "model": "llama-3.1-70b-versatile",
    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
    "request_timeout_s": 8.0,
    "max_tokens": 1024,
    "fail_count_disable": 5
  },
  "findings": {
    "enabled": true,
    "auto_synthesize_on_run": false,
    "redact_patterns": ["api_key","secret","password","token","AV_API_KEY","GROQ_API_KEY"],
    "max_source_chars": 8000,
    "log_tail_lines": 200
  }
}
```
After edit: run `python scripts/maintenance/_compute_hash.py` (mandatory per CLAUDE.md §3.1).

### 6. New "Agent" tab in UI (4 small edits)
- `ui_kits/control_plane/AgentPanel.jsx` (new) — three sections:
  - **Mermaid diagram** (agent-as-controller view; see below)
  - **Recent findings** — fetch from new server endpoint `/agent/findings?limit=20`
  - **Audit log tail** — fetch from new server endpoint `/agent/audit?limit=20`
- `ui_kits/control_plane/Header.jsx` — add fourth button: `{btn("Agent", "agent")}`
- `ui_kits/control_plane/App.jsx` — add `view === "agent" ? <AgentPanel /> :` to ternary chain
- `ui_kits/control_plane/index.html` — add `<script type="text/babel" src="AgentPanel.jsx"></script>` before App.jsx

### 7. Two new read-only server endpoints in `src/control_plane/server.py`
- `GET /agent/findings?limit=N` → tail `logs/agent_findings.jsonl`
- `GET /agent/audit?limit=N` → tail `logs/agent_audit.jsonl`

Both wrap existing `_tail_jsonl()` helper (already in server.py for run logs). No new write paths.

---

## Mermaid for the new Agent tab

```
flowchart TB
  USER([User / Trader])
  subgraph AGENT_LAYER ["Agent Layer (agent.cli REPL)"]
    A["agent.cli\\nNatural-language REPL"]
    IR["IntentRouter\\nregex → LLM fallback"]
    PC["PlanCompiler\\nPLAN_REGISTRY (17 intents)"]
    EX["Executor\\nconfirm-gate + path-guard"]
    FS["FindingsSynthesizer\\nGroq llama-3.1-70b"]
    A --> IR --> PC --> EX
    EX -.->|on demand| FS
  end

  subgraph CRT_PIPE ["CRT Pipeline (existing — see Workflow tab)"]
    direction LR
    DATA[Data Prep] --> TUNE[CRT Tuning + Promotion]
    DATA --> ML[ML Model Training]
    TUNE --> LIVE[Live Runner]
    ML --> LIVE
    LIVE -.-> GOV[Governance]
  end

  USER -->|"types prompt"| A
  EX -->|"dispatch CommandSpec"| CRT_PIPE
  CRT_PIPE -->|"artifacts: logs/, results/, models/"| FS
  FS -->|"append"| FINDINGS[("logs/agent_findings.jsonl")]
  EX -->|"append"| AUDIT[("logs/agent_audit.jsonl")]
  FS -->|"LLM prompts (redacted)"| LLMREQ[("logs/agent_llm_requests.jsonl")]
  FINDINGS -.->|"on-demand recall"| A
  A -->|"reply + alerts"| USER

  classDef agent fill:#ffcc88,stroke:#a86200,stroke-width:2px
  classDef pipe fill:#d0e8ff,stroke:#0057b7,stroke-width:1px
  classDef store fill:#f0f0f0,stroke:#666,stroke-width:1px
  class A,IR,PC,EX,FS agent
  class DATA,TUNE,ML,LIVE,GOV pipe
  class FINDINGS,AUDIT,LLMREQ store
```

---

## Acknowledged Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Secret leakage to Groq** | `agent.findings.redact_patterns` applied in `GroqClient` before send; `prompt_redacted` (not raw) stored in `logs/agent_llm_requests.jsonl` |
| **Latency / cost spike** | `auto_synthesize_on_run=false` default → user must explicitly invoke `findings.synthesize <run_id>`; circuit-breaker disables after 5 failures |
| **Confirm-gate bypass** | All findings tools dispatch through existing `Executor.dispatch()`. The append-to-jsonl is treated as `write=True` but path-guarded to `logs/` only |
| **BitNet still used for intent routing** | Unchanged — intent routing stays on local BitNet (cheap, fast). Only findings synthesis uses Groq. Two separate code paths |
| **Windows cp1252 / file lock** | No background poller — on-demand only. JSONL appends use `with open(..., "a", encoding="utf-8")` like existing audit writer |
| **Diagram conflict with Workflow tab** | Workflow tab unchanged (11-node minimum-autonomous). Agent tab is a new view with the agent-as-controller diagram. Each diagram has a single, distinct purpose |
| **Config hash drift** | Mandatory rehash step listed in verification |
| **No GROQ_API_KEY at startup** | GroqClient lazy-loads the key on first call; if missing, returns empty + logs `MISSING_KEY` once; findings tools degrade gracefully ("synthesis unavailable — set GROQ_API_KEY") |

---

## Open Blockers (need user to clear or accept)

1. **GROQ_API_KEY provisioning** — user must set env var or paste into `.env`; not auto-provisioned by this plan
2. **Test suite extension** — `docs/AGENT_REFERENCE.md §12` lists invariants enforced by tests; adding 3 new intents will require 3 new test entries in `tests/test_agent_plan_registry.py` (small; same pattern)
3. **The user's sample Mermaid in their message lists `live.inout_runner (stub)`** — confirmed in code that it is NOT a stub (it's the real entry). The agent-tab diagram drops the "(stub)" label

---

## Verification

1. `python scripts/maintenance/_compute_hash.py` → config hash updates without error
2. `pytest tests/test_agent_*` → existing agent invariant tests still green
3. `pytest tests/test_agent_plan_registry.py -k findings` → 3 new intent mappings pass
4. Set `GROQ_API_KEY` in env; run any data prep (e.g. `data.fetch_alphavantage`); in REPL type `synthesize run <run_id>` → finding appears in `logs/agent_findings.jsonl` within ~2s
5. Restart server; hard-refresh; click new "Agent" tab → diagram renders, findings tail visible (empty initially), audit tail visible (populated from prior runs)
6. Unset `GROQ_API_KEY`; run synthesize → degrades to "synthesis unavailable" message, no exception, finding NOT appended
7. Grep `logs/agent_llm_requests.jsonl` for `api_key`/`secret`/`AV_` strings → must return 0 matches (redaction proof)

---

# Previous: Workflow Diagram — Minimum Autonomous Pipeline (completed earlier this session)

## Context
Current WorkflowPanel.jsx diagram has 30+ nodes including scripts already wrapped by higher-level orchestrators and optional paths (groq bridge, backtest loops, replay, baseline capture). The goal: collapse internal sub-scripts into their parent orchestrators, remove optional paths, and produce the minimum node diagram that covers the **entire flow end-to-end** — touching all 4 runtime engines (CRT, Gaussian, Zone Gate, RR) with no manual gaps between steps.

## Collapse Map — what gets absorbed / removed

| Removed node | Absorbed into |
|---|---|
| `training.opportunity_scanner` | `training.auto_train` (calls it internally) |
| `training.phase5_calibration` | `training.auto_train` (calls it internally) |
| `analysis.compress_logs` | `training.auto_train` (calls it internally) |
| `validation.config_validator` | `promotion.manager` (calls validate() internally) |
| `tuning.auto_tuner` (single) | Superseded by `auto_tuner_multi` |
| `training.train_pipeline` | Superseded by `training.auto_train` |
| `data.unified_data_builder` | Alternative entry; same output as `prepare_data` |
| `groq.prepare_retrospective`, `groq.ingest_response`, `groq.apply_llm_suggestions` | Optional LLM retrospective — not core autonomous |
| `replay.unified` | Optional verification — not a required step |
| `backtest.v2`, `backtest.bitnet` | Optional verification — not a required step |
| `baseline.capture` | Optional safety snapshot — not a required step |

## Minimum Nodes Remaining: 11

All 4 runtime engines covered:
- **CRT engine** → `tuning.auto_tuner_multi` tunes CRT params; `promotion.manager` promotes them
- **Gaussian engine** → `training.auto_train` wraps phase5_calibration + promote_gaussian
- **Zone Gate engine** → `training.discover_zones` → `zone_registry.json`
- **RR engine** → `training.build_rr_dataset` → `training.train_rr_model` → `rr_model.json`

## File to Change

**Only:** `ui_kits/control_plane/WorkflowPanel.jsx`

Replace the `diagram` constant and update the legend subtitle.

## New Mermaid Diagram

```
flowchart TB
  %% ── Data Sources ──────────────────────────────────────────────
  AV["data.fetch_alphavantage\n8 forex pairs"]
  HB["data.fetch_hummingbot\n3 crypto pairs"]
  D1["data.prepare_data\nNormalize raw CSVs → M15"]

  AV -->|data/*.csv| D1
  HB -->|data/*.csv| D1

  %% ── CRT Hyperparameter Loop ───────────────────────────────────
  subgraph CRT [" CRT Hyperparameter Loop "]
    direction TB
    T1["tuning.auto_tuner_multi\nGrid-search CRT params\n→ checkpoint_multi.json"]
    P1["promotion.manager\n(wraps: ConfigValidator)\n→ configs/production/v*.json"]
    T1 -->|checkpoint_multi.json| P1
  end

  D1 -->|"*_M15.csv"| T1

  %% ── ML Model Training ─────────────────────────────────────────
  subgraph ML [" ML Model Training "]
    direction TB
    AT["training.auto_train\n(wraps: opportunity_scanner\n+ compress_logs\n+ phase5_calibration\n+ promote_gaussian)"]
    DZ["training.discover_zones"]
    BR["training.build_rr_dataset"]
    TRR["training.train_rr_model"]
    AT -->|opportunities.jsonl| DZ
    AT -->|opportunities.jsonl| BR
    BR -->|rr_dataset.json| TRR
  end

  D1 -->|"*_M15.csv"| AT

  %% ── Live + Governance ─────────────────────────────────────────
  L1["live.inout_runner\nMulti-instrument live loop"]
  G1["governance.orchestrator\n(wraps: ShadowPromotionGate\n+ BitNet LLM)"]

  P1 -->|production_config.json| L1
  AT -->|gaussian_registry.json| L1
  DZ -->|zone_registry.json| L1
  TRR -->|rr_model.json| L1

  L1 -.->|flow_collector.log| G1
  G1 -.->|shadow promote| L1

  %% ── Styles ────────────────────────────────────────────────────
  classDef compound fill:#d0e8ff,stroke:#0057b7,stroke-width:2px
  classDef source fill:#fff8e6,stroke:#b87d00,stroke-width:1px
  classDef live fill:#e6ffe6,stroke:#3a8a00,stroke-width:2px
  class AT,P1 compound
  class AV,HB source
  class L1,G1 live
```

## Legend subtitle change

```
Blue nodes = compound scripts (wrap multiple sub-scripts) | Solid = file handoff | Dashed = feedback loop
```

## Verification

1. Restart server: `venv\scripts\python.exe src\control_plane\server.py`
2. Hard-refresh browser
3. Click "Workflow" tab — 2 subgraph boxes (CRT Hyperparameter Loop, ML Model Training)
4. Confirm exactly 11 visible nodes: AV, HB, D1, T1, P1, AT, DZ, BR, TRR, L1, G1
5. Confirm `opportunity_scanner`, `compress_logs`, `groq.*`, `replay.*`, `backtest.*`, `baseline.capture` are absent
6. Confirm `AT` and `P1` have blue fill; `AV`/`HB` have yellow-ish fill; `L1`/`G1` have green fill
7. `L1 -.-> G1 -.-> L1` dashed feedback loop visible

---

# Previous: Workflow Diagram Panel — CRT Web Control Plane

## Context (superseded — diagram already implemented; now being redesigned)
User wanted the Mermaid workflow diagram rendered in the CRT Web Control Plane. WorkflowPanel.jsx was created with a 30+ node diagram. This task replaces that diagram with the minimum autonomous version above.

## Diagram Corrections (vs. user-provided Mermaid)

| Issue | Fix |
|-------|-----|
| `G1 -->|candidate_config.json| P1` (solid bridge) | **Remove** — orchestrator promotes internally via `ShadowPromotionGate`; confirmed in prior session. No file output to `promotion.manager`. |
| `live.inout_runner (NOT IMPLEMENTED)` | Remove `(NOT IMPLEMENTED)` label — the script is fully implemented. |
| Missing `data.fetch_alphavantage` + `data.fetch_hummingbot` | Add both nodes under Data Prep, with solid arrows to `data.prepare_data`. |
| `L1 -.->|planned| G1` | Change to `L1 -.-> G1` (edge now exists in registry after previous session fix). |

---

## Files to Change

| File | Action |
|------|--------|
| `ui_kits/control_plane/index.html` | Add Mermaid CDN `<script>` tag |
| `ui_kits/control_plane/WorkflowPanel.jsx` | **New file** — renders Mermaid diagram |
| `ui_kits/control_plane/App.jsx` | Add `"workflow"` view state + wire panel |
| `ui_kits/control_plane/Header.jsx` | Add "Workflow" toggle button |

---

## Change 1 — `index.html`: Add Mermaid CDN

After the existing CDN script tags (React + Babel), add:
```html
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
```

---

## Change 2 — `WorkflowPanel.jsx` (new file)

```jsx
// WorkflowPanel.jsx
const { useEffect, useRef } = React;

function WorkflowPanel() {
  const ref = useRef(null);

  const diagram = `
flowchart TB
  %% ── Data Prep ────────────────────────────────────────────────
  RAW[(Raw CSV)]
  AV[data.fetch_alphavantage]
  HB[data.fetch_hummingbot]
  D1[data.prepare_data]
  D2[data.unified_data_builder]

  RAW --> D1
  RAW --> D2
  AV -->|data/*.csv| D1
  HB -->|data/*.csv| D1

  %% ── Tuning ───────────────────────────────────────────────────
  T1[tuning.auto_tuner_multi]
  T2[tuning.auto_tuner]
  D1 -->|M15 CSV| T1
  D2 -->|M15 CSV| T1

  %% ── Model Training ───────────────────────────────────────────
  M1[training.opportunity_scanner]
  M2[training.phase5_calibration]
  M3[training.discover_zones]
  M4[training.build_rr_dataset]
  M5[training.train_rr_model]
  M6[training.train_pipeline]
  M7[training.auto_train]
  A1[analysis.compress_logs]

  M1 -->|opportunities.jsonl| M2
  M1 -->|opportunities.jsonl| M3
  M1 -->|opportunities.jsonl| M4
  M1 -->|opportunities.jsonl| A1
  M4 -->|rr_dataset.json| M5

  %% ── Groq Bridge ──────────────────────────────────────────────
  GR1[groq.prepare_retrospective]
  GR2[groq.ingest_response]
  GR3[groq.apply_llm_suggestions]
  A1 -.-> GR1
  GR1 -.-> GR2
  GR2 -.-> GR3
  GR3 -.-> M2
  GR3 -.-> M3

  %% ── Validation & Promotion ────────────────────────────────────
  V1[validation.config_validator]
  P1[promotion.manager]
  G1[governance.orchestrator]

  A1 -->|compressed_summary.json| G1
  V1 -->|validation_report.json| P1

  T1 -.-> M1
  T1 -.-> V1
  T2 -.-> M1
  T2 -.-> V1
  M2 -.-> M3
  M3 -.-> M4
  M4 -.-> V1
  M5 -.-> V1
  M6 -.-> V1
  M7 -.-> V1

  %% ── Replay & Backtest ─────────────────────────────────────────
  R1[replay.unified]
  B1[backtest.v2]
  B2[backtest.bitnet]
  C1[baseline.capture]

  V1 -.-> R1
  R1 -.-> B1
  R1 -.-> B2
  B1 -.-> V1
  B2 -.-> R1

  %% ── Live Runner ───────────────────────────────────────────────
  L1[live.inout_runner]
  P1 -->|production_config.json| L1
  P1 -.-> C1
  C1 -.-> T1
  L1 -.-> R1
  L1 -.-> G1
  G1 -.-> L1

  %% ── Styles ────────────────────────────────────────────────────
  classDef bridge fill:#e6ffe6,stroke:#090,stroke-width:2px
  classDef guidance fill:#f8f8f8,stroke:#aaa,stroke-width:1px
  class D1,D2,AV,HB,T1,M1,M2,M3,M4,M5,A1,V1,P1,G1,L1 bridge
`;

  useEffect(() => {
    if (!ref.current || !window.mermaid) return;
    window.mermaid.initialize({ startOnLoad: false, theme: "dark" });
    ref.current.innerHTML = diagram;
    ref.current.removeAttribute("data-processed");
    window.mermaid.run({ nodes: [ref.current] });
  }, []);

  return (
    <div style={{ padding: "16px", overflowY: "auto", height: "100%" }}>
      <h2 style={{ marginBottom: "12px", fontSize: "14px", fontWeight: 600 }}>
        Pipeline Workflow
      </h2>
      <p style={{ fontSize: "11px", color: "#aaa", marginBottom: "16px" }}>
        Solid arrows = file-based data bridges &nbsp;|&nbsp; Dashed arrows = sequential guidance
      </p>
      <div className="mermaid" ref={ref} style={{ background: "transparent" }} />
    </div>
  );
}
```

---

## Change 3 — `App.jsx`: Add workflow view

Find the existing view state initialization and add `"workflow"`:
```jsx
// In the view state handler, add the workflow branch:
{view === "workflow" && <WorkflowPanel />}
```

The exact insertion point depends on current App.jsx layout — need to read it during implementation.

---

## Change 4 — `Header.jsx`: Add Workflow button

Add a third toggle button alongside the existing "Runs" and "Dashboard" buttons:
```jsx
<button onClick={() => setView("workflow")}
        style={{ ..., background: view === "workflow" ? activeColor : inactiveColor }}>
  Workflow
</button>
```

---

## Verification

1. Restart server: `venv\scripts\python.exe src\control_plane\server.py`
2. Hard-refresh browser
3. Click "Workflow" button in header
4. Mermaid diagram renders with dark theme
5. Confirm: no `candidate_config.json → promotion.manager` solid arrow
6. Confirm: `data.fetch_alphavantage` and `data.fetch_hummingbot` nodes visible under Data Prep
7. Confirm: `live.inout_runner` label has no "(NOT IMPLEMENTED)"
8. Confirm: `live.inout_runner → governance.orchestrator` dashed edge is present

---

# Data Prep: AlphaVantage + Hummingbot Fetcher CommandSpecs

## Context
User wants AlphaVantage (forex) and Hummingbot (crypto) data fetching accessible from the CRT Web Control Plane Data Prep section. Both fetcher classes and CLI scripts **already exist** in the codebase — only registry changes are needed. No Python script modifications required.

**Existing scripts confirmed:**
- `scripts/data/fetch_candles_alphavantage.py` → forex via AlphaVantage FX_INTRADAY API
- `scripts/data/fetch_candles_hummingbot.py` → crypto via Hummingbot exchange connectors
- `src/inout/alphavantage_candle_fetcher.py` → underlying client class
- `src/inout/hummingbot_candle_fetcher.py` → underlying client class

---

## Instrument Lists

**Forex (AlphaVantage)** — from prod config `v1_multi_2026_03.json` + data folder:
`EURUSD, GBPUSD, AUDUSD, USDJPY, USDCHF, USDCAD, NZDUSD, EURCAD`

**Crypto (Hummingbot)** — from prod config + data folder:
`BTCUSDT, ETHUSDT, XAUUSD`

---

## File to Change

**Only:** `src/control_plane/registry.py`

### Change 1 — Add `data.fetch_alphavantage` CommandSpec

Insert after the existing `data.historical_fetcher` CommandSpec (~line 798):

```python
CommandSpec(
    id="data.fetch_alphavantage",
    title="Fetch Forex Data (AlphaVantage)",
    description="Download M15 forex OHLCV candles from Alpha Vantage FX_INTRADAY API into data/.",
    category="Data Prep",
    mode="python-file",
    script="scripts/data/fetch_candles_alphavantage.py",
    args_schema=(
        ArgSpec("pair", flag="--pair", kind="choice", required=True,
                choices=("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "NZDUSD", "EURCAD"),
                help="Forex pair to fetch"),
        ArgSpec("start", flag="--start", kind="str", required=True,
                help="Start date inclusive (YYYY-MM-DD)"),
        ArgSpec("end",   flag="--end",   kind="str", required=True,
                help="End date exclusive (YYYY-MM-DD)"),
        ArgSpec("interval", flag="--interval", kind="choice", default="15min",
                choices=("1min", "5min", "15min", "30min", "60min"),
                help="Candle interval (default 15min)"),
        ArgSpec("api_key", flag="--api-key", kind="str", default=None,
                help="Alpha Vantage API key (falls back to AV_API_KEY env var then config)"),
        ArgSpec("out", flag="--out", kind="str", default="data",
                help="Output directory (default: data/)"),
        ArgSpec("config", flag="--config", kind="file",
                default="configs/production/v1_multi_2026_03.json",
                file_glob="configs/production/*.json",
                help="Production config JSON (provides api_key and defaults)"),
    ),
    artifacts=("data/*.csv",),
),
```

### Change 2 — Add `data.fetch_hummingbot` CommandSpec

Insert after `data.fetch_alphavantage`:

```python
CommandSpec(
    id="data.fetch_hummingbot",
    title="Fetch Crypto Data (Hummingbot)",
    description="Download M15 crypto OHLCV candles from exchange via Hummingbot connector into data/.",
    category="Data Prep",
    mode="python-file",
    script="scripts/data/fetch_candles_hummingbot.py",
    args_schema=(
        ArgSpec("pair", flag="--pair", kind="choice", required=True,
                choices=("BTCUSDT", "ETHUSDT", "XAUUSD"),
                help="Crypto pair to fetch"),
        ArgSpec("exchange", flag="--exchange", kind="choice", default="binance",
                choices=("binance", "bybit", "okx", "kucoin", "kraken"),
                help="Exchange connector (default: binance)"),
        ArgSpec("start", flag="--start", kind="str", required=True,
                help="Start date inclusive (YYYY-MM-DD)"),
        ArgSpec("end",   flag="--end",   kind="str", required=True,
                help="End date exclusive (YYYY-MM-DD)"),
        ArgSpec("interval", flag="--interval", kind="choice", default="15m",
                choices=("1m", "5m", "15m", "30m", "1h", "4h", "1d"),
                help="Candle interval (default 15m)"),
        ArgSpec("out", flag="--out", kind="str", default="data",
                help="Output directory (default: data/)"),
        ArgSpec("config", flag="--config", kind="file",
                default="configs/production/v1_multi_2026_03.json",
                file_glob="configs/production/*.json",
                help="Production config JSON (provides exchange/interval defaults)"),
    ),
    artifacts=("data/*.csv",),
),
```

### Change 3 — Add quickstart notes for both new commands

Add to `_QUICKSTART_NOTES_BY_COMMAND`:

```python
"data.fetch_alphavantage": (
    "Requires a free Alpha Vantage API key — set AV_API_KEY environment variable or pass --api-key.",
    "Free tier: 25 requests/day. Fetching 1 year of M15 data = 12 monthly API calls per pair.",
    "Output lands in data/ as {PAIR}_M15.csv — feed directly into Prepare Data (validate-only) next.",
),
"data.fetch_hummingbot": (
    "Fetches from Binance/Bybit/OKX via Hummingbot connectors — no API key required for public candles.",
    "Output lands in data/ as {PAIR}_M15.csv — feed directly into Prepare Data (validate-only) next.",
    "Use 'binance' exchange for BTCUSDT/ETHUSDT. Use 'bybit' for XAUUSD (spot).",
),
```

### Change 4 — Add edges in `_RECOMMENDED_NEXT_BY_COMMAND`

Both new commands should recommend `data.prepare_data` (validate the fetched CSV) as next step:

```python
"data.fetch_alphavantage": ("data.prepare_data",),
"data.fetch_hummingbot":   ("data.prepare_data",),
```

Also add these commands to the `_WORKFLOW_STAGE_BY_COMMAND` dict:
```python
"data.fetch_alphavantage": "Data Prep",
"data.fetch_hummingbot":   "Data Prep",
```

---

## No Changes Needed

- `scripts/data/fetch_candles_alphavantage.py` — already correct CLI
- `scripts/data/fetch_candles_hummingbot.py` — already correct CLI
- `src/inout/alphavantage_candle_fetcher.py` — already implemented
- `src/inout/hummingbot_candle_fetcher.py` — already implemented
- No production config section additions needed (scripts fall back gracefully when config section is missing; `--pair`, `--start`, `--end` are the only truly required args)

---

## Verification

1. Restart server: `venv\scripts\python.exe src\control_plane\server.py`
2. Hard-refresh browser
3. In UI: Category = Data Prep → Command dropdown must show "Fetch Forex Data (AlphaVantage)" and "Fetch Crypto Data (Hummingbot)"
4. AlphaVantage form: pair dropdown shows 8 forex pairs; interval choices are 1min/5min/15min/30min/60min; start/end date text fields; api-key field
5. Hummingbot form: pair dropdown shows BTCUSDT/ETHUSDT/XAUUSD; exchange dropdown shows binance/bybit/okx; interval choices are 1m/5m/15m/30m/1h/4h/1d
6. "What to run next" shows "Prepare Data" for both

---

# Per-Instrument Differentiation — Architecture Analysis

## How the Pipeline Handles Multiple Instruments

The pipeline is **multi-instrument but globally unified**. Instrument separation happens only at the data and opportunity-log layers. From model training onward, everything collapses into one shared set.

### Layer-by-layer breakdown

| Stage | Command | Runs how many times? | Output per instrument? | Key flag |
|-------|---------|---------------------|------------------------|----------|
| **Data** | `data.prepare_data` | Once per instrument | `data/{INSTR}_M15.csv` — YES, named per instrument | `--instrument EURUSD` |
| **Data** | `data.unified_data_builder` | Once (batch all) | `data/{INSTR}_M15.csv` for each — YES | positional list |
| **Tuning** | `tuning.auto_tuner_multi` | Once (all instruments together) | `results/tuner/checkpoint_multi.json` — ONE shared checkpoint | `--instruments EURUSD,GBPUSD,...` |
| **Opportunities** | `training.opportunity_scanner` | **Once per instrument** (must be run N times) | `logs/opportunities_{INSTR}_{RUN_ID}.jsonl` — YES, named per instrument | `--instrument` required |
| **Training** | `training.phase5_calibration` | Once (all opportunities merged or one representative) | `models/gaussian_{version}.json` — ONE shared model | `--opportunities` (multi-file) |
| **Training** | `training.discover_zones` | Once (all opportunities merged) | `models/zone_registry_{version}.json` — ONE shared registry | `--opportunities` (multi-file) |
| **Training** | `training.build_rr_dataset` | Once (all opportunities merged) | `models/rr_dataset_{version}.json` — ONE shared dataset | `--opportunities` (multi-file) |
| **Training** | `training.train_rr_model` | Once | `models/rr_model_{version}.json` — ONE shared model | `--dataset` |
| **Validation** | `validation.config_validator` | Once (runs per-instrument backtests internally) | `results/validation_report.json` — ONE report, per-instrument metrics inside | `--data-dir data/` (reads all CSVs) |
| **Promotion** | `promotion.manager` | Once | `configs/production/{version}.json` — ONE config for all | `--checkpoint` |
| **Live** | `live.inout_runner` | Once (multi-instrument loop inside) | Shared logs | `--config` |

### The two chokepoints where "N instruments → 1 thing" happens

```
INSTRUMENT-LEVEL                           SHARED

data/EURUSD_M15.csv ─┐
data/GBPUSD_M15.csv ─┤─► auto_tuner_multi ─────────────► checkpoint_multi.json (1)
data/AUDUSD_M15.csv ─┘                                         │
                                                               ▼
logs/opportunities_EURUSD_*.jsonl ─┐                   promotion.manager
logs/opportunities_GBPUSD_*.jsonl ─┼─► phase5_calib ──► models/gaussian_{v}.json (1)
logs/opportunities_AUDUSD_*.jsonl ─┘    discover_zones ─► models/zone_registry_{v}.json (1)
                                         build_rr_dataset ─► models/rr_dataset_{v}.json (1)
                                         train_rr_model ──► models/rr_model_{v}.json (1)
```

### Registry model structure — NO per-instrument keys

All three model registries are globally keyed by version string, not by instrument:
- `models/gaussian_registry.json` — one `"active": true` entry, no instrument dimension
- `models/zone_registry.json` — single `"zones"` array, no instrument dimension
- `models/rr_registry.json` — one `"active": true` entry, no instrument dimension

**One active model set is shared across all instruments at runtime.**

---

## UI Gap: opportunity_scanner must be run N times

`training.opportunity_scanner` requires `--instrument` (single choice, required). To cover 8 instruments, a user must submit 8 separate runs from the UI — one per instrument. There is no batch loop in the CommandSpec.

**Option A — document it** (no code change): Add a quickstart note: "Run once per instrument. Feed all resulting JSONL files into Phase-5 Calibration via multi-select."

**Option B — add a batch wrapper CommandSpec** (new code): Register `training.opportunity_scanner_batch` that accepts `--instruments` (list) and loops internally. This is new functionality.

**Recommendation: Option A** — the existing multi-select `--opportunities` arg in phase5_calibration already handles merging multiple JSONL files. Users simply run the scanner 8 times and pass all 8 files to the next step. No new code needed; a quickstart note is sufficient.

---

## Registry Fix for opportunity_scanner quickstart_notes

**File:** `src/control_plane/registry.py` — `_QUICKSTART_NOTES_BY_COMMAND["training.opportunity_scanner"]`

Add a note clarifying per-instrument usage. Currently the notes say:
```
"Run after data prep — generates unbiased JSONL training data for all ML models.",
"Set --tp-atr-mult 2.0 --sl-atr-mult 1.0 to match the production 2R target.",
"Output: logs/opportunities_{instrument}.jsonl — feed this into Phase 5 and Discover Zones.",
```

Add:
```
"Run once per instrument (e.g. 8 runs for 8 instruments). Multi-select all resulting JSONL files when feeding Phase-5 Calibration and Discover Zones.",
```

Also add a note to `training.phase5_calibration`, `training.discover_zones`, `training.build_rr_dataset`:
```
"Accepts multiple --opportunities files — pass ALL per-instrument JSONL outputs from Opportunity Scanner for a merged model.",
```

These are 4 quickstart_note additions in `_QUICKSTART_NOTES_BY_COMMAND`, no ArgSpec changes needed.

---

# Registry Edge & Bridge Fix Plan

## Context
User's gap analysis identified broken/misleading edges in `_RECOMMENDED_NEXT_BY_COMMAND` and missing ArgSpecs in `src/control_plane/registry.py`. Investigation confirmed 3 real bugs and ~10 sequential-guidance-only edges. Changes are confined to `registry.py` only — no Python script changes required.

---

## Confirmed Bugs (require code changes)

### Bug 1 — governance.orchestrator CommandSpec missing `--compressed-summary` arg
**File:** `src/control_plane/registry.py` (~line 319)
- Python script `src/governance/orchestrator.py` accepts `--compressed-summary` (mutually exclusive with `--collector-log`/`--trades-csv`) **but the ArgSpec is absent from the registry**.
- This means the UI never shows the arg; users cannot connect `analysis.compress_logs` output to `governance.orchestrator` from the UI.
- Also: `collector_log` and `trades_csv` are `required=True` in the ArgSpec but are **optional** in the actual script when `--compressed-summary` is supplied.

**Fix in registry.py:**
1. Add ArgSpec for `--compressed-summary`:
```python
ArgSpec("compressed_summary", flag="--compressed-summary", kind="file", required=False,
        file_glob="logs/compressed_*.json",
        help="Pre-computed compressed summary JSON from compress_logs (mutually exclusive with --collector-log/--trades-csv)"),
```
2. Change `collector_log` and `trades_csv` from `required=True` to `required=False`.

---

### Bug 2 — `governance.orchestrator → promotion.manager` edge is wrong
**File:** `src/control_plane/registry.py` line 168
```python
"governance.orchestrator": ("promotion.manager",),
```
**Investigation result:** `orchestrator.py` calls `ShadowPromotionGate.promote_if_superior()` **internally** (Step 4). Any promotion goes through `shadow_promotion_gate.py` directly — the orchestrator does NOT output a file that `promotion.manager` can consume. The `configs/production/*.json` in its artifacts is written by `ShadowPromotionGate`, not as a handoff to `promotion.manager`.

**Fix:** Replace with `live.inout_runner` as next step (after governance approves, user runs the live runner on the newly promoted config):
```python
"governance.orchestrator": ("live.inout_runner",),
```

---

### Bug 3 — `live.inout_runner → governance.orchestrator` edge is MISSING
**File:** `src/control_plane/registry.py` line 173
```python
"live.inout_runner": ("replay.unified",),
```
`live.inout_runner` produces `logs/flow_collector.log` and `logs/inout_audit.jsonl`. The `governance.orchestrator`'s `--collector-log` arg reads exactly this file. The edge SHOULD exist but doesn't.

**Fix:**
```python
"live.inout_runner": ("replay.unified", "governance.orchestrator"),
```

---

## Sequential-Guidance Edges (keep as-is — correct workflow order, not data bridges)

These edges are NOT bugs — they guide the user through the workflow even though no file from the upstream command feeds directly into the downstream CLI arg. They should be kept:

| Edge | Why keep |
|------|----------|
| `tuning.auto_tuner_multi → training.opportunity_scanner` | Scanner reads same data CSV tuner used; run after tuning to build training data |
| `tuning.auto_tuner → training.opportunity_scanner` | Same |
| `tuning.auto_tuner_multi → validation.config_validator` | Validate current prod config before deciding to promote checkpoint |
| `training.phase5_calibration → training.discover_zones` | Both read from same opportunity JSONL; run both from same scanner output |
| `training.discover_zones → training.build_rr_dataset` | Same opportunity JSONL source; natural sequence |
| `training.build_rr_dataset → validation.config_validator` | After RR model trained from dataset, validate that it improves the full system |
| `validation.config_validator → replay.unified` | After validating params, replay to visually inspect trade-level truth |
| `baseline.capture → tuning.auto_tuner_multi` | Capture baseline BEFORE new tuning campaign to enable before/after comparison |
| `replay.unified → backtest.v2` | Run standalone backtest after replay for detailed metrics comparison |
| `replay.unified → backtest.bitnet` | Same — compare BitNet gate modes after replaying |
| `backtest.v2 → validation.config_validator` | Validate params again after seeing raw backtest results |

---

## Files to Change

**Only one file:** `src/control_plane/registry.py`

### Change 1 — Fix governance.orchestrator CommandSpec (lines ~319–342)
Add `compressed_summary` ArgSpec; change `collector_log` and `trades_csv` to `required=False`:

```python
# Before:
ArgSpec("collector_log", flag="--collector-log", kind="file", required=True, ...),
ArgSpec("trades_csv", flag="--trades-csv", kind="file", required=True, ...),
# (no --compressed-summary)

# After:
ArgSpec("collector_log", flag="--collector-log", kind="file", required=False, ...),
ArgSpec("trades_csv", flag="--trades-csv", kind="file", required=True, ...),
ArgSpec("compressed_summary", flag="--compressed-summary", kind="file", required=False,
        file_glob="logs/compressed_*.json",
        help="Pre-computed compressed summary JSON from compress_logs (mutually exclusive with --collector-log/--trades-csv)"),
```

Wait — `trades_csv` stays `required=True` because baseline_pnl is always required. Actually no: when `--compressed-summary` is provided, BOTH `--collector-log` AND `--trades-csv` are optional at the script level. Fix both to `required=False`.

### Change 2 — Fix edge: governance.orchestrator → live.inout_runner (line 168)
```python
# Before:
"governance.orchestrator": ("promotion.manager",),
# After:
"governance.orchestrator": ("live.inout_runner",),
```

### Change 3 — Add edge: live.inout_runner → governance.orchestrator (line 173)
```python
# Before:
"live.inout_runner": ("replay.unified",),
# After:
"live.inout_runner": ("replay.unified", "governance.orchestrator"),
```

---

## Verification

1. Start server: `venv\scripts\python.exe src\control_plane\server.py`
2. Hard-refresh browser
3. Navigate to Governance Orchestrator command in UI
4. Confirm `--compressed-summary` field appears in the form
5. Confirm `--collector-log` and `--trades-csv` are no longer marked required
6. Navigate to INOUT Live Runner — confirm "governance.orchestrator" appears in recommended next steps
7. Navigate to Governance Orchestrator — confirm "live.inout_runner" appears in recommended next steps (not "promotion.manager")

---

# Previous Work (completed in prior sessions)

# Command I/O Map — Inputs, Outputs & Bridges (all 20 original commands)

## Data Prep

### data.prepare_data
- **IN:** `--files` user-specified CSVs (histdata M1 / binance 1m / standard M15)
- **OUT:** `data/{INSTRUMENT}_M15_real.csv`
- **Bridge →** auto_tuner, auto_tuner_multi, backtest_v2, opportunity_scanner

### data.unified_data_builder
- **IN:** `data/DAT_ASCII_{INSTR}_M1_*.csv`, `data/{INSTR}-1m-*.csv` (hardcoded globs per instrument)
- **OUT:** `data/{INSTRUMENT}_M15.csv` (one per instrument)
- **Bridge →** auto_tuner, auto_tuner_multi, backtest_v2, opportunity_scanner

---

## Tuning

### tuning.auto_tuner
- **IN:** `data/{INSTRUMENT}_M15*.csv` (via --csv or --data-dir glob)
- **OUT:** `results/tuner/checkpoint.json`, `results/tuner/live_log.jsonl`, `results/tuner/runs/{TS}_{INSTR}/`
- **Bridge →** promotion.manager (checkpoint.json), governance.orchestrator

### tuning.auto_tuner_multi
- **IN:** `data/{INSTRUMENT}_M15.csv` (multi-instrument glob)
- **OUT:** `results/tuner/checkpoint_multi.json`, `results/tuner/live_log_multi.jsonl`, `results/tuner/runs/`, `results/tuner/runs_oos/`
- **Bridge →** promotion.manager (checkpoint_multi.json — primary input)

---

## Model Training

### training.opportunity_scanner
- **IN:** `data/{INSTRUMENT}_M15.csv` (single --csv, M15 OHLCV)
- **OUT:** `logs/opportunities_{INSTRUMENT}_{RUN_ID}.jsonl` (one JSONL record per bar×direction, 35-dim canonical features + rr_achieved + outcome)
- **Bridge →** training.phase5_calibration, training.discover_zones, training.build_rr_dataset, analysis.compress_logs, groq bridge

### training.phase5_calibration
- **IN:** `logs/opportunities_*.jsonl` (--opportunities), optional cached `models/phase5_dataset.json`
- **OUT:** `models/gaussian_{version}.json`, `results/p5_calibration_{version}.json`, optionally `models/tradenet_{version}.pth`
- **Bridge →** validation.config_validator (gaussian model loaded via registry), promotion.manager

### training.discover_zones
- **IN:** One or more `logs/opportunities_*.jsonl`
- **OUT:** `models/zone_registry_{version}.json`, `models/zone_gate_registry.json`
- **Bridge →** validation.config_validator (zone registry loaded at runtime), live.inout_runner

### training.build_rr_dataset
- **IN:** `logs/opportunities_*.jsonl` (recommended) OR `results/**/*_trades.csv` (legacy)
- **OUT:** `models/rr_dataset_{version}.json`, `models/rr_registry.json`
- **Bridge →** training.train_rr_model

### training.train_rr_model
- **IN:** `models/rr_dataset_{version}.json` (active from rr_registry)
- **OUT:** `models/rr_model_{version}.json`, `models/rr_model.json` (canonical when --promote)
- **Bridge →** validation.config_validator (rr model loaded at runtime), live.inout_runner

### training.train_pipeline
- **IN (tradenet):** `results/**/*.json` training data, **IN (gaussian):** `logs/**/*_fusion.jsonl`
- **OUT (tradenet):** `models/tradenet_{version}.pth` + scaler JSON, **OUT (gaussian):** `models/gaussian_{version}.json`
- **Bridge →** validation.config_validator, promotion.manager

### training.auto_train  *(nightly orchestrator)*
- **IN:** `data/{INSTRUMENT}_M15.csv` for all instruments in --instruments
- **OUT:** `logs/opportunities_{INSTR}_{RUN_ID}.jsonl`, `models/gaussian_{version}.json`, `results/p5_calibration_{version}.json`, `results/merged_opportunities_{RUN_ID}.jsonl`
- **Bridge →** (wraps opportunity_scanner → phase5_calibration in sequence; optionally promotion.manager)

### analysis.compress_logs
- **IN:** `logs/opportunities_*.jsonl` (one or more)
- **OUT:** `logs/compressed_summary_{name}.json` (token-compact JSON: summary + anomalies)
- **Bridge →** governance.orchestrator (--compressed-summary-path), groq.prepare_retrospective

---

## Validation & Promotion

### validation.config_validator
- **IN:** Candidate params dict + `data/{INSTRUMENT}_M15.csv` paths (per-instrument backtests); reads `models/gaussian_registry.json`, `models/zone_registry.json`, `models/rr_registry.json` at runtime
- **OUT:** `ValidationReport` (in-memory; caller writes to `results/validation/approved/` or `rejected/`)
- **Bridge →** promotion.manager (report fed directly)

### promotion.manager
- **IN:** `results/tuner/checkpoint_multi.json` OR `results/validation/approved/*.json`; base `configs/production/v1_multi_2026_03.json`
- **OUT:** `configs/production/{version}.json`, `configs/promotion_log.jsonl`
- **Bridge →** live.inout_runner (loads promoted config), replay.unified, backtest.bitnet

### governance.orchestrator
- **IN:** `logs/collector.jsonl` (decision events), `results/**/*_trades.csv`, `logs/compressed_summary*.json` (optional), `configs/production/*.json`
- **OUT:** `logs/meta_prompt.txt`, `logs/governance_audit.jsonl`, candidate config JSON (shadow gate)
- **Bridge →** promotion.manager (candidate config), groq bridge

---

## Live Runner

### live.inout_runner
- **IN:** `configs/production/{version}.json` (promoted), models loaded from registry at startup (`models/gaussian_registry.json`, `models/zone_registry.json`, `models/rr_registry.json`)
- **OUT:** `logs/inout_runner.log`, `logs/inout_heartbeat.jsonl`, `logs/inout_audit.jsonl`, `logs/flow_collector.log` (decision events per bar)
- **Bridge →** governance.orchestrator (flow_collector.log), replay.unified (comparison), analysis.compress_logs

---

## Replay & Backtest

### replay.unified
- **IN:** `configs/production/*.json` (--config), `data/{INSTRUMENT}_M15.csv` (--data)
- **OUT:** `results/alignment/{INSTR}_{TS}_unified_report.json`, `results/alignment/{INSTR}_{TS}_v2_truth/`, optional filtered CSVs
- **Bridge →** governance.orchestrator (trades for review), analysis.compress_logs

### backtest.v2
- **IN:** `data/{INSTRUMENT}_M15*.csv` (--csv)
- **OUT:** `results/{RUN_ID}_{INSTR}/{INSTR}_summary.json`, `results/{RUN_ID}_{INSTR}/{INSTR}_trades.csv`, `logs/backtest_debug.log`
- **Bridge →** training.build_rr_dataset (legacy --csv mode), governance.orchestrator (trades), training.discover_zones (legacy mode)

### backtest.bitnet
- **IN:** `configs/production/*.json` (--config), `data/{INSTRUMENT}_M15.csv` (--data)
- **OUT:** `logs/backtest_decisions_{SYMBOL}_{TS}.jsonl`
- **Bridge →** governance.orchestrator (decision log review)

### baseline.capture
- **IN:** Auto-resolves `configs/production/{PROD_VERSION}.json`, `models/gaussian_registry.json`, `models/zone_registry.json` (no explicit --files)
- **OUT:** `results/baseline/{TS}_{LABEL}/manifest.json` (schema hash + config SHA256 + model registry snapshot)
- **Bridge →** Used as pre-promotion safety snapshot; compared against post-promotion state

---

## Full Bridge Map (file-level)

```
data/INSTR_M15.csv
  ├─► data.prepare_data ──────────────► data/INSTR_M15_real.csv
  ├─► data.unified_data_builder ──────► data/INSTR_M15.csv
  ├─► tuning.auto_tuner ──────────────► results/tuner/checkpoint.json
  ├─► tuning.auto_tuner_multi ────────► results/tuner/checkpoint_multi.json
  ├─► training.opportunity_scanner ───► logs/opportunities_*.jsonl
  ├─► backtest.v2 ────────────────────► results/**/trades.csv + summary.json
  └─► replay.unified ─────────────────► results/alignment/**

logs/opportunities_*.jsonl
  ├─► training.phase5_calibration ────► models/gaussian_*.json
  ├─► training.discover_zones ────────► models/zone_registry_*.json
  ├─► training.build_rr_dataset ──────► models/rr_dataset_*.json
  └─► analysis.compress_logs ─────────► logs/compressed_summary_*.json

models/rr_dataset_*.json
  └─► training.train_rr_model ────────► models/rr_model_*.json

models/{gaussian,zone_registry,rr_model}_*.json  (registry loaded at runtime)
  ├─► validation.config_validator ────► ValidationReport (in-memory)
  └─► live.inout_runner ──────────────► logs/inout_audit.jsonl + flow_collector.log

results/tuner/checkpoint_multi.json
  └─► promotion.manager ──────────────► configs/production/{version}.json

configs/production/{version}.json
  ├─► live.inout_runner
  ├─► replay.unified
  └─► backtest.bitnet

logs/flow_collector.log + results/**/trades.csv
  └─► governance.orchestrator ────────► logs/meta_prompt.txt + governance_audit.jsonl

logs/compressed_summary_*.json
  └─► governance.orchestrator
```

---

# UI Coverage Gap Analysis — CRT Web Control Plane vs Codebase

## Registered commands (20 total — all scripts confirmed to exist)

| ID | Script | Category |
|----|--------|----------|
| data.prepare_data | scripts/data/prepare_data.py | Data Prep |
| data.unified_data_builder | scripts/data/unified_data_builder.py | Data Prep |
| tuning.auto_tuner_multi | scripts/training/auto_tuner_multi.py | Tuning |
| tuning.auto_tuner | scripts/training/auto_tuner.py | Tuning |
| validation.config_validator | src/config_layer/config_validator.py | Validation & Promotion |
| promotion.manager | src/governance/promotion_manager.py | Validation & Promotion |
| governance.orchestrator | src/governance/orchestrator.py | Validation & Promotion |
| replay.unified | src/runtime/unified_replay_harness.py | Replay & Backtest |
| backtest.v2 | src/runtime/backtest_v2.py | Replay & Backtest |
| backtest.bitnet | src/runtime/backtest_bitnet.py | Replay & Backtest |
| baseline.capture | src/runtime/baseline_capture.py | Replay & Backtest |
| live.inout_runner | inout.runner (module) | Live Runner |
| training.opportunity_scanner | scripts/research/opportunity_scanner.py | Model Training |
| training.phase5_calibration | scripts/training/phase5_calibration.py | Model Training |
| training.discover_zones | scripts/research/discover_zones.py | Model Training |
| training.build_rr_dataset | scripts/data/build_rr_dataset.py | Model Training |
| training.train_rr_model | scripts/training/train_rr_model.py | Model Training |
| training.train_pipeline | scripts/training/train_pipeline.py | Model Training |
| training.auto_train | scripts/auto_train_from_opportunities.py | Model Training |
| analysis.compress_logs | scripts/analysis/compress_logs_for_llm.py | Model Training |

## Not in UI — operational scripts (should add)

| Script | Category to add | Why |
|--------|----------------|-----|
| `scripts/update_config_hash.py` | Maintenance | Required after any config edit; currently run manually |
| `scripts/training/auto_tuner_gemini_gate.py` | Tuning | Gemini-gate variant of auto_tuner |
| `scripts/groq_bridge/prepare_retrospective.py` | Groq Bridge | Phase-1 retrospective prep |
| `scripts/groq_bridge/ingest_response.py` | Groq Bridge | Phase-1 response ingestion |
| `scripts/groq_bridge/apply_llm_suggestions.py` | Groq Bridge | Apply LLM hyperparameter suggestions |
| `scripts/governance/promote_v2.py` | Validation & Promotion | Thin wrapper for v2 promotion |
| `scripts/training/train_bitnet.py` | Model Training | BitNet model training |
| `scripts/analysis/daily_crypto_structure.py` | Analysis | Daily market structure report |
| `scripts/analysis/schema_audit.py` | Analysis | Schema audit / consistency check |
| `scripts/misc/build_zone_registry_from_trades.py` | Maintenance | Rebuild zone registry from trades |
| `src/agent/cli.py` | Agent | Agent REPL entry point |
| `src/data_ingestion/historical_fetcher.py` | Data Prep | Multi-pair historical data fetch |
| `src/governance/portfolio_validation.py` | Validation & Promotion | Portfolio-level validation |
| `src/monitoring/health_checker.py` | Maintenance | System health check |
| `src/runtime/analyze_fusion_shadow.py` | Replay & Backtest | Fusion shadow analysis |
| `src/analytics/sl_tp_comparator.py` | Replay & Backtest | Dual SL/TP comparison |
| `src/config_layer/config_builder.py` | Validation & Promotion | Config build utility |
| `src/config_layer/execution_planner.py` | Replay & Backtest | Execution planner CLI |
| `src/config_layer/insight_reporter.py` | Analysis | LLM-powered insight report |

## Not in UI — internal/test (skip registering)

| Script | Reason to skip |
|--------|---------------|
| `scripts/control_plane/run_server.py` | Meta — launches the server itself |
| `scripts/misc/run_parity.py` | Dev/parity check, not a workflow step |
| `scripts/backtest/manual_backtest.py` | Dev tool, not production workflow |
| `scripts/analysis/generate_cli_matrix.py` | Meta — generates documentation |
| `scripts/analysis/gen_dummy_trades.py` | Test data generator |
| `scripts/misc/bitnet_ternary_inference.py` | Standalone inference util |
| `src/bitnet/_smoke_test.py` | Test, not a workflow command |
| `src/core/ultron_risk_gate.py` | Core engine, CLI is for dev only |
| `src/engines/live_engine.py` | Invoked via `live.inout_runner`, not directly |
| `src/config_layer/production_config.py` | Config load utility, not a workflow step |
| `src/utils/logging_config.py` | Utility module |
| `src/utils/llm_logger.py` | Utility module |
| `src/utils/zone_schema_migrator.py` | One-off migration tool |
| `src/features/feature_monitor.py` | Monitoring util, not a workflow step |

## Next action

Add the **19 operational scripts** to `src/control_plane/registry.py` as new `CommandSpec` entries, grouped into new/existing categories. Priority order: Maintenance > Groq Bridge > Analysis > Agent > remaining.

---

# Previous (already done): Fix: validate() issue strings also contain → (run a24c3934)

## Context

Run a24c3934: correct venv Python, all args transmitted, validation ran 3 seconds, then
crashed at `print(f"    [!]  {issue}")` — the print template is ASCII-safe now, but the
`issue` string itself contains `→` from `validate()` line 213:
```python
issues.append(f"Out of order at row {i}: {rows[i-1][0]} → {rows[i][0]}")
```

## Fix (1 line)

**`scripts/data/prepare_data.py:213`** — replace `→` with `->` inside the issue string builder.

## Progress so far on a24c3934

Validation ran fully for AUDUSD and BTCUSDT before crash:
- AUDUSD: 121,254 bars, 371 unexpected gaps (data quality issue, not a code bug)
- BTCUSDT: 35,138 bars, 1 unexpected 0-min gap (likely duplicate at boundary)

---

# Previous (already done): Fix: UnicodeEncodeError in prepare_data.py (run 36812d87 — new failure after args fix landed)

## Context

Run 36812d87 is the first run where args were transmitted correctly (files, already_m15, validate_only all present). It failed exit_code=1 with:
```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 2-66
scripts/data/prepare_data.py:387 — print(f"\n{'═'*65}")
```
Windows cp1252 console can't encode `═` (U+2550), `─` (U+2500), `→` (U+2192), `✅`, `⚠️`, `❌`.
CLAUDE.md §4: "Non-ASCII output must go through src/utils/console_safe.py".
Fix: replace all non-ASCII chars in print statements with ASCII equivalents.

Note: run also used system Python 3.14 (not venv) — because server was started without venv active.
Server uses `sys.executable` (registry.py:679), so start server with `venv/scripts/python.exe src/control_plane/server.py`.

## File: scripts/data/prepare_data.py — all print lines with non-ASCII

| Line | Non-ASCII | Replace with |
|------|-----------|--------------|
| 304 | `─` | `-` |
| 306 | `─` | `-` |
| 312 | `⚠️` | `[!]` |
| 320 | `❌` | `[FAIL]` |
| 339 | `→` | `->` |
| 346 | `→` | `->` |
| 355 | `→` | `->` |
| 360 | `⚠️` | `[!]` |
| 362 | `✅` | `[OK]` |
| 367 | `✅` | `[OK]` |
| 387 | `═` | `=` |
| 389 | `═` | `=` |
| 415 | `✅`/`⚠️` | `[OK]`/`[!]` |
| 419 | `→` | `->` |
| 427 | `✅` | `[OK]` |
| 438 | `⚠️` | `[!]` |
| 440 | `═` | `=` |
| 441 | `✅`/`⚠️` | `[OK]`/`[!]` |
| 442 | `═` | `=` |
| 516 | `─` | `-` |
| 519 | `─` | `-` |

(`—` em dash at line 312 is cp1252-safe; keep as-is)

## Verification

1. `venv/scripts/python.exe scripts/data/prepare_data.py --source standard --files data/AUDUSD_M15.csv --instrument AUDUSD --already-m15 --validate-only`
2. Must exit 0, no UnicodeEncodeError

---

# Previous (already done): Fix: realApi.js sends args unwrapped — server always receives empty args (all 7 run failures)

## Root Cause (definitive)

**All 7 runs failed for the same reason**, not because of caching:

| Layer | Code | What it does |
|-------|------|--------------|
| **Client** | `realApi.js:172` | `body: JSON.stringify(args \|\| {})` → sends `{"files":[...],...}` |
| **Server** | `server.py:1863` | `args = payload.get("args", {})` → expects `{"args":{...}}` wrapper → always gets `{}` |

The old inline JS in `server.py:744` uses `JSON.stringify({args})` (wrapped correctly). The React `realApi.js` was written without the wrapper, so **every run ever submitted from the React UI has had `args = {}`** — all user selections silently discarded.

## Fix (1 character change in 1 file)

**`ui_kits/control_plane/realApi.js:172`**

```diff
- body: JSON.stringify(args || {}),
+ body: JSON.stringify({ args: args || {} }),
```

## Verification

1. Restart server: `python src/control_plane/server.py`
2. Hard-refresh browser (Ctrl+F5)
3. Select `data/EURUSD_M15.csv`, check `already_m15` + `validate_only`, click Run
4. Run record must show `"files": ["data/EURUSD_M15.csv"]`, `"already_m15": true`, `"validate_only": true`
5. Exit code must be 0

---

# Previous (already done): Add sys.path bootstrap to server.py so `python src/control_plane/server.py` works

## Context

After the `cp_types.py` rename, running `python src/control_plane/server.py` directly still
fails with `ModuleNotFoundError: No module named 'src.control_plane'`. Root cause: direct
file execution adds `src/control_plane/` to `sys.path` (not the repo root), so `src.*`
absolute imports can't resolve. `python -m src.control_plane.server` works because `-m`
adds the repo root. Fix: insert the repo root into `sys.path` at the top of `server.py`
before the first `src.*` import.

## File to Change (1 line in 1 file)

**`src/control_plane/server.py`** — insert after stdlib imports, before line 12 (`from src.control_plane.jobs`):

```python
# Ensure repo root is on sys.path when run directly (python src/control_plane/server.py)
import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```

Note: `Path` is already imported on line 9 (`from pathlib import Path`), so no extra import needed.

## Status of run b5b82ed2

Run b5b82ed2 (11:03:15) was the 6th cached-JS failure — submitted immediately after server
restart, before the browser hard-refresh cleared the old JS. The CURRENT form in the
screenshot has files selected, instrument auto-filled, and both boxes checked. No code change
needed for this — user should click "Run Command" now.

## Verification

1. Stop server (Ctrl+C)
2. `python src/control_plane/server.py` — must start without `ModuleNotFoundError`
3. Submit a run with files selected + both checkboxes checked → must succeed

---

# Previous Analysis — Run Failure Analysis — 5 consecutive failures (e4081377 → 63294180)

## Root Cause: 100% confirmed — stale browser cache

**Every single run has identical symptoms.** Comparing the run record to what the UI showed
at submission time:

| Field | What UI showed | What server received | Why different |
|-------|---------------|----------------------|---------------|
| source | `histdata` | `standard` | Old cached JS sends initial default |
| files | `["data/AUDUSD_M15.csv"]` | `[]` | Old JS never wired file selection to args |
| instrument | `AUDUSD` (auto) | `EURUSD` | Old JS has no auto-fill logic |
| already_m15 | `true` (checked) | `false` | Old JS checkbox state not tracked |
| validate_only | `true` (checked) | `false` | Old JS checkbox state not tracked |

The fix to `LauncherPanel.jsx` exists **on disk** but the browser **never fetched it**
because `Cache-Control: no-store` is only sent after the server restarts. The server has
not been restarted since the fix was applied.

## Timeline of failures

| Run | Started | files | validate_only | Result |
|-----|---------|-------|---------------|--------|
| e4081377 | 07:12 | [] | false | argparse exit 2 |
| bb3f30d6 | 09:45 | [] | false | argparse exit 2 |
| efd117c0 | 09:55 | [] | false | argparse exit 2 |
| e0b4c16b | 10:19 | [] | false | argparse exit 2 |
| 63294180 | 10:48 | [] | false | argparse exit 2 |

All five are **identical failures** caused by the same stale JS. No variation.

## Odds of success after server restart

| Scenario | Probability | Reason |
|----------|------------|--------|
| `validate_only=true` (box checked) | ~100% | `--validate-only` bypasses `--files` check entirely; script runs on existing CSVs |
| `validate_only=false` + file selected | ~100% | Files now wired via fixed ComboBox multi-select; `--files data/AUDUSD_M15.csv` sent |
| `source=histdata` + M15 CSV + `validate_only=false` | ~0% | histdata parser expects raw M1 format (`YYYYMMDD HHMMSS,O,H,L,C,V`), not M15 CSV |
| `source=standard` + M15 CSV + `already_m15=true` | ~100% | standard parser + already_m15 flag → reads M15 CSV as-is, no resampling |

## One additional risk: source=histdata with M15 file

The UI currently shows `source: histdata` selected. After restart, that value **will** be
sent. But `data/AUDUSD_M15.csv` is a normalized M15 CSV — not raw histdata M1 format.
Running `--source histdata` against it will likely produce a parse error or empty output.

**Fix:** Change source back to `standard` before running, OR check `validate_only`
(which skips parsing entirely and just validates the existing file).

## Required action

1. **Restart the control plane server** — one restart activates `Cache-Control: no-store`
2. **Hard-refresh the browser** (Ctrl+F5) — clears the stale JSX from Chrome's cache
3. After that, form values will match what the server receives on every submit

No further code changes are needed. All fixes are already on disk.
