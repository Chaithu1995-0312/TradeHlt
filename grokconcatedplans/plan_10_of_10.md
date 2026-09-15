# Concatenated session plans — part 10 of 10

Source directory: `docs/plans/`
Files in this part: 6

## Contents

1. `yes-this-is-now-eager-pixel.md` (12791 bytes)
2. `you-are-an-expert-ancient-pebble.md` (19795 bytes)
3. `you-are-auditing-a-goofy-prism.md` (9977 bytes)
4. `you-are-implementing-phase-integrity-inherited-tulip.md` (31363 bytes)
5. `you-are-implementing-stage-1-polished-token.md` (33080 bytes)
6. `you-are-lead-runtime-typed-snowglobe.md` (21549 bytes)


================================================================================
SOURCE_FILE: docs/plans/yes-this-is-now-eager-pixel.md
SOURCE_BYTES: 12791
PART: 10/10 FILE 1/6
================================================================================

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


================================================================================
SOURCE_FILE: docs/plans/you-are-an-expert-ancient-pebble.md
SOURCE_BYTES: 19795
PART: 10/10 FILE 2/6
================================================================================

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Command Audit Report — Tradelatest Quantitative Trading System

> Analysis date: 2026-05-07  
> Worktree: `D:\Tradelatest\.claude\worktrees\xenodochial-babbage-1a2ab5`  
> All findings are grounded in actual argparse definitions read from source.

---

## Executive Summary

| Severity | Count | Verdict |
|----------|-------|---------|
| 🔴 CRITICAL (script doesn't exist / missing required arg) | 4 | Immediate runtime failure |
| 🟠 HIGH (wrong argument type / semantic mismatch) | 3 | Silent wrong behaviour or crash |
| 🟡 MEDIUM (workflow order, version inconsistency) | 4 | Likely failure in CI / governance gate |
| 🟢 LOW (style / path convention) | 3 | Cosmetic / minor |

**Overall alignment score: 🔴 RED** — 4 commands will fail immediately on invocation, 3 more will silently produce wrong results.

---

## Per-Command Findings

### CMD-01 — `promotion_manager.py promote` (first occurrence)
```bash
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version v2_multi_2026_04 \
  --data-dir data/ \
  --instruments EURUSD GBPUSD BTCUSDT XAUUSD \
  --notes "April tuner run, 3-month window"
```
**Status: ✅ Aligned (with minor note)**  
- All required args present (`--checkpoint`, `--version`).  
- `--instruments` accepts `nargs="+"` — four values are valid.  
- `--data-dir data/` vs parser default `"data"` (no slash): argparse passes the literal value; Python `os.path.join("data/", ...)` and `os.path.join("data", ...)` are equivalent on all platforms. Cosmetically inconsistent with the default but not an error.  
- ⚠️ `results/tuner/checkpoint_multi.json` is an **output** of `auto_tuner_multi.py` — if promotion is invoked before the tuner run completes and writes that file, this will raise `FileNotFoundError`. (See CMD-02 ordering note.)

---

### CMD-02 — `auto_tuner_multi.py`
```bash
python scripts/training/auto_tuner_multi.py \
  --data-dir data --output-dir results/tuner \
  --n-iter 100 --seed 42 --workers 4 --train-split 1.0
```
**Status: ✅ Aligned**  
- `--train-split 1.0` is typed `float` in the parser — `1.0` is correct; passing `1` would also be accepted (Python coerces `int` to `float` via `type=float`).  
- `--workers 4` is typed `int` — correct.  
- No `--instruments` supplied; the script defaults to discovering CSVs from `--data-dir`. Valid if `data/` contains appropriately named CSVs.  
- ⚠️ **Workflow order**: This command appears **after** CMD-01 (the promotion command). The tuner must run first to produce `results/tuner/checkpoint_multi.json` before promotion can succeed. **The script list is in the wrong logical order.**

---

### CMD-03 — `backtest_v2.py` (first occurrence, no comment)
```bash
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
```
**Status: ✅ Aligned**  
- `--csv` is required and present.  
- `--instrument` is optional (default `"AUTO"`) but supplying it explicitly is correct and avoids AUTO-detection ambiguity.

---

### CMD-04 — `promote_v2.py` (first occurrence)
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05
```
**Status: 🔴 CRITICAL — File does not exist**  
- `scripts/governance/promote_v2.py` **is not present anywhere in the repository**.  
- Every invocation of this script (CMD-04, CMD-19, CMD-20) will fail with `No such file or directory`.  
- **Fix:** Use the canonical promotion path: `python src/governance/promotion_manager.py promote ...`.

---

### CMD-05 — `phase5_calibration.py` (first occurrence)
```bash
python scripts/training/phase5_calibration.py --train --csv data/EURUSD_M15.csv
```
**Status: 🔴 CRITICAL — Wrong argument semantics**  
- The `--csv` flag in `phase5_calibration.py` has `metavar="DIR"` — it **expects a base directory containing results subdirectories**, not a raw CSV file path.  
- Passing `data/EURUSD_M15.csv` will cause the script to attempt directory traversal on a file path, producing either an `OSError` or silently processing zero results directories.  
- **Fix:** Pass a results base directory (e.g., `--csv results/`) or use `--synthetic` for smoke tests, or `--cached results/phase5_dataset.json` for cached data.

---

### CMD-06 — `auto_tuner.py`
```bash
python scripts/training/auto_tuner.py \
  --csv data/EURUSD_M15.csv --instrument EURUSD \
  --output-dir results/tuner --n-iter 100
```
**Status: ✅ Aligned**  
- All flags are valid per the parser. `--csv` + `--instrument` is a supported single-instrument mode.  
- ⚠️ Note: this is the **single-instrument tuner** (`auto_tuner.py`), not the multi-instrument one (`auto_tuner_multi.py`). Its checkpoint output path may differ from what CMD-01 expects (`checkpoint_multi.json` vs a single-instrument checkpoint). Confirm the file name written by this script matches the one passed to `promotion_manager.py promote --checkpoint`.

---

### CMD-07 — `backtest_v2.py` (commented block, step 1)
```bash
# 1. Run a backtest on your CSV data — this writes to logs/
python src/runtime/backtest_v2.py --instrument EURUSD --csv data/EURUSD_M15.csv
```
**Status: ✅ Aligned**  
- Identical semantics to CMD-03; argument order swap is not significant (argparse is order-agnostic).  
- ⚠️ **Workflow assumption**: The comment says "this writes to `logs/`". The backtest output directory defaults to `"results"` (`--output` defaults to `"results"`), not `logs/`. The fusion JSONL (`logs/EURUSD_fusion.jsonl`) consumed in step 2 is written by `FusionEngine` during the backtest, not by the backtest harness itself. Verify that the production config has `fusion_log_path` pointing to `logs/EURUSD_fusion.jsonl` or this assumption silently breaks the dataset build step.

---

### CMD-08 — Python one-liner (dataset build)
```python
python -c "
from src.features.dataset_validator import validate_logs
from src.features.dataset_builder import build_dataset
records, report = validate_logs('logs/EURUSD_fusion.jsonl')
build_dataset(records, output_path='data/training.json')
print(report)
"
```
**Status: 🟠 HIGH — Implicit dependency on CMD-07 output; minor signature note**  
- `validate_logs` signature is `validate_logs(*log_paths, verbose=True)` — calling it with a single positional string works correctly (`log_paths` will be `('logs/EURUSD_fusion.jsonl',)`). ✅  
- `build_dataset(records, output_path='data/training.json')` matches the actual signature `build_dataset(records, output_path=None)`. ✅  
- ⚠️ **Hidden dependency**: `logs/EURUSD_fusion.jsonl` is only written if CMD-07 completed successfully AND the `FusionEngine` log path is configured to write there. If CMD-07 was skipped or the log path differs in config, this will fail with `FileNotFoundError`.  
- ⚠️ `print(report)` prints a `ValidationReport` dataclass object — the output will be the repr, which is useful for debugging but not human-formatted. No functional issue.

---

### CMD-09 — `train_pipeline.py tradenet` (first occurrence)
```bash
python scripts/training/train_pipeline.py tradenet \
  --data data/training.json --output results/tradenet_result.json
```
**Status: ✅ Aligned**  
- `tradenet` is a valid subcommand. `--data` is required and present. `--output` is optional but supplied.  
- Depends on CMD-08 having written `data/training.json` first.

---

### CMD-10 — `train_pipeline.py tradenet` (duplicate)
```bash
python scripts/training/train_pipeline.py tradenet \
  --data data/training.json --output results/tradenet_result.json
```
**Status: 🟡 MEDIUM — Exact duplicate of CMD-09**  
- Identical command appears twice in succession. No functional difference; second run would overwrite the first output. Remove the duplicate.

---

### CMD-11 — `train_pipeline.py gaussian`
```bash
python scripts/training/train_pipeline.py gaussian \
  --logs logs/EURUSD_fusion.jsonl logs/GBPUSD_fusion.jsonl \
  --version gaussian_v2_2026_05
```
**Status: ✅ Aligned**  
- `gaussian` is a valid subcommand. `--logs` accepts `nargs="+"` — two JSONL paths are valid. `--version` is required and present.  
- ⚠️ Both log files must exist before this runs. `logs/GBPUSD_fusion.jsonl` requires a separate GBPUSD backtest run (analogous to CMD-07 for EURUSD) which is not shown in the command list. If missing, the script will raise `FileNotFoundError` at read time.

---

### CMD-12 — `phase5_calibration.py` (second occurrence)
```bash
python scripts/training/phase5_calibration.py --train --csv data/EURUSD_M15.csv
```
**Status: 🔴 CRITICAL — Same wrong-type issue as CMD-05**  
- Same error as CMD-05: `--csv` expects a **results base directory**, not a CSV file path.  
- Additionally, `--csv` and `--train` appear alongside each other, but the parser defines `--csv` within a mutually exclusive group `(required=True)`. Since `--train` is a separate optional flag (not in the exclusive group), this combination is syntactically valid; the semantic error is solely in the `--csv` value.

---

### CMD-13 — `train_bitnet.py`
```bash
python scripts/training/train_bitnet.py \
  --csv data/EURUSD_M15.csv --epochs 50 --lr 0.01 --out model.json
```
**Status: 🔴 CRITICAL — File does not exist**  
- `scripts/training/train_bitnet.py` **does not exist anywhere in the repository**.  
- **Fix:** BitNet inference is handled via the binary at `./bitnet/bin/main` (referenced in `orchestrator.py`). If GGUF-based training is needed, the entry point is different from what this command implies. The flag set (`--epochs`, `--lr`, `--out`) does not match any existing script signature in the codebase.

---

### CMD-14 — `backtest_v2.py` (exact duplicate of CMD-03)
```bash
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
```
**Status: 🟡 MEDIUM — Duplicate of CMD-03**  
- Identical command. Remove the duplicate.

---

### CMD-15 — `config_validator.py validate-prod`
```bash
python src/config_layer/config_validator.py validate-prod \
  --data-dir data/ --version v2_multi_2026_04
```
**Status: ✅ Aligned**  
- `validate-prod` subcommand is valid. Both flags are optional in the parser; supplying them is fine.  
- ⚠️ `v2_multi_2026_04` is passed as `--version` to override production version; verify that a config named with this version exists in the registry before running, otherwise the validator will fail to load it.

---

### CMD-16 — `config_validator.py validate-params`
```bash
python src/config_layer/config_validator.py validate-params \
  --params '{"sweep_threshold":0.6}' --config-id test_run
```
**Status: 🟠 HIGH — Inline JSON passed where a file path is expected**  
- The `validate-params` parser defines `--params` as a plain `str` argument. However, if the implementation calls `open(args.params)` to load it as a file (which is the idiomatic pattern for a "params JSON file" argument), passing an inline JSON string will raise `FileNotFoundError: [Errno 2] No such file or directory: '{"sweep_threshold":0.6}'`.  
- The parser help text says `"JSON file with params dict"` — confirming it expects a **file path**.  
- **Fix:** Write the params to a temp file first:
  ```bash
  echo '{"sweep_threshold":0.6}' > /tmp/test_params.json
  python src/config_layer/config_validator.py validate-params \
    --params /tmp/test_params.json --config-id test_run
  ```

---

### CMD-17 — `promotion_manager.py promote` (duplicate of CMD-01, with `✅` label)
```bash
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version v2_multi_2026_04 \
  --data-dir data/ \
  --instruments EURUSD GBPUSD BTCUSDT XAUUSD \
  --notes "April tuner run, 3-month window"
```
**Status: ✅ Aligned (same as CMD-01) — 🟡 MEDIUM: Duplicate**  
- Exact duplicate of CMD-01. Remove one occurrence.

---

### CMD-18 — `promotion_manager.py from-report`
```bash
python src/governance/promotion_manager.py from-report \
  --report results/validation/approved/report_v2_multi_2026_04.json
```
**Status: 🔴 CRITICAL — Missing required `--version` argument**  
- The `from-report` subcommand parser defines **both** `--report` and `--version` as `required=True`.  
- This command omits `--version`, so argparse will print an error and exit:  
  `error: the following arguments are required: --version`  
- **Fix:**
  ```bash
  python src/governance/promotion_manager.py from-report \
    --report results/validation/approved/report_v2_multi_2026_04.json \
    --version v2_multi_2026_04
  ```

---

### CMD-19 — `promotion_manager.py list`
```bash
python src/governance/promotion_manager.py list
```
**Status: ✅ Aligned**  
- `list` subcommand takes no arguments. Correct.

---

### CMD-20 — `promote_v2.py` (second occurrence)
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05
```
**Status: 🔴 CRITICAL — File does not exist (same as CMD-04)**

---

### CMD-21 — `promote_v2.py --dry-run`
```bash
python scripts/governance/promote_v2.py --version multi_strategy_v2_2026_05 --dry-run
```
**Status: 🔴 CRITICAL — File does not exist (same as CMD-04)**

---

### CMD-22 — `orchestrator.py`
```bash
python src/governance/orchestrator.py \
  --collector-log logs/collector.jsonl \
  --trades-csv results/EURUSD_trades.csv \
  --baseline-pnl 5.23
```
**Status: ✅ Aligned**  
- All three required args (`--collector-log`, `--trades-csv`, `--baseline-pnl`) are present.  
- `--baseline-pnl 5.23` is typed `float` — correct.  
- ⚠️ `results/EURUSD_trades.csv` must contain a `pnl_rr_net` column (per the parser help text). Verify that `backtest_v2.py` writes trades with this column name to that path; if the output path differs from `results/EURUSD_trades.csv`, this will fail at runtime when the orchestrator tries to read the column.  
- ⚠️ `logs/collector.jsonl` must exist before this runs (written by the collector component). Its creation is not shown in the command list.

---

## Workflow Consistency Notes

### Note 1 — Logical Ordering Violations
The commands are **not** in a valid execution order. A correct linear order for a full promotion cycle is:

```
1. Backtest  (CMD-03/07) — produces logs/EURUSD_fusion.jsonl
2. Dataset build  (CMD-08) — consumes fusion log → data/training.json
3. TradeNet training  (CMD-09) — consumes training.json
4. Gaussian training  (CMD-11) — consumes fusion logs (needs GBPUSD backtest too)
5. Phase-5 calibration  (CMD-05/12) — needs results base dir, not CSV
6. Config validation  (CMD-15) — validate before promoting
7. Promotion  (CMD-01/17) — only after checkpoint_multi.json exists (needs tuner, CMD-02)
```

CMD-01 (promote) appears at position 1, before the tuner (CMD-02), backtest (CMD-03), training, and validation steps. This would fail because `checkpoint_multi.json` doesn't exist yet.

### Note 2 — `logs/EURUSD_fusion.jsonl` Origin
This file is **not** written by `backtest_v2.py --output`. It is written by `FusionEngine` during the backtest run, controlled by a config key (likely `fusion_log_path` or similar in `fusion_engine` config section). The command list assumes it exists after step 1, but this is only guaranteed if the production config routes the fusion log to `logs/EURUSD_fusion.jsonl`. Verify the config.

### Note 3 — Version String Format Inconsistency
Three different version string formats appear across commands:

| Format | Example | Used by |
|--------|---------|---------|
| `v{N}_{scope}_{YYYY_MM}` | `v2_multi_2026_04` | `promotion_manager.py`, `config_validator.py` |
| `{scope}_v{N}_{YYYY_MM}` | `multi_strategy_v2_2026_05`, `gaussian_v2_2026_05` | `promote_v2.py` (nonexistent), `train_pipeline.py gaussian` |

The canonical format per `CLAUDE.md` and the production config (`v1_multi_2026_03`) is **`v{N}_{scope}_{YYYY_MM}`**. The `multi_strategy_v2_2026_05` and `gaussian_v2_2026_05` formats deviate from this convention, and the month suffix jumps from `04` to `05` inconsistently.

### Note 4 — `BTCUSDT` vs `BTCUSD`
`BTCUSDT` (with `T`) is the **canonical** name across all config files and source code (confirmed in `v1_multi_2026_03_force_accept.json`, `v2_multi_2026_04.json`, `market_router.py`). All audit commands correctly use `BTCUSDT`. No inconsistency here.

### Note 5 — Missing GBPUSD Backtest
CMD-11 (Gaussian training) requires `logs/GBPUSD_fusion.jsonl` but no GBPUSD backtest command is present in the list. The fusion log for GBPUSD will not exist unless an equivalent of CMD-07 is run with `--csv data/GBPUSD_M15.csv --instrument GBPUSD`.

---

## Consolidated Recommendations

### Remove / Replace

| Command | Action |
|---------|--------|
| CMD-04, CMD-20, CMD-21 (`promote_v2.py`) | **Delete all three.** Script doesn't exist. Use `promotion_manager.py promote` instead. |
| CMD-10 (duplicate `tradenet` training) | Remove duplicate. |
| CMD-14 (duplicate `backtest_v2.py`) | Remove duplicate. |
| CMD-17 (duplicate `promotion_manager.py promote`) | Remove duplicate. |

### Fix Immediately

| Command | Fix |
|---------|-----|
| CMD-05, CMD-12 (`phase5_calibration --csv data/EURUSD_M15.csv`) | Change `--csv` value to a **results base directory** (e.g., `results/`), not a CSV file path. |
| CMD-16 (`validate-params --params '{"..."}'`) | Write JSON to a temp file; pass the file path to `--params`. |
| CMD-18 (`from-report` missing `--version`) | Add `--version v2_multi_2026_04`. |
| CMD-13 (`train_bitnet.py`) | Remove or replace with the actual BitNet invocation pattern. Check if a wrapper script exists elsewhere; if not, document that BitNet training is out-of-scope for this CLI. |

### Workflow Reorder

Place commands in this sequence:
1. Backtest (all instruments needed)
2. Dataset build (from fusion logs)
3. TradeNet training
4. Gaussian model training
5. Auto-tuner multi (produces `checkpoint_multi.json`)
6. Phase-5 calibration (with correct `--csv`/`--cached` arg)
7. Config validation (`validate-prod`)
8. Promotion (`promotion_manager.py promote`)

### Version String Standardisation

Adopt `v{N}_{scope}_{YYYY_MM}` uniformly:
- `gaussian_v2_2026_05` → `v2_gaussian_2026_05`
- `multi_strategy_v2_2026_05` → `v2_multi_2026_05`

---

## Summary Table

| CMD | Command | Status | Severity |
|-----|---------|--------|----------|
| 01 | `promotion_manager promote` (1st) | ✅ Aligned | — |
| 02 | `auto_tuner_multi` | ✅ Aligned | — |
| 03 | `backtest_v2` (1st) | ✅ Aligned | — |
| 04 | `promote_v2.py` | 🔴 File missing | CRITICAL |
| 05 | `phase5_calibration --csv CSV_FILE` | 🔴 Wrong arg type | CRITICAL |
| 06 | `auto_tuner.py` | ✅ Aligned | — |
| 07 | `backtest_v2` (commented block) | ✅ Aligned | — |
| 08 | Python one-liner (dataset build) | 🟠 Implicit dep | HIGH |
| 09 | `train_pipeline tradenet` (1st) | ✅ Aligned | — |
| 10 | `train_pipeline tradenet` (2nd) | 🟡 Duplicate | MEDIUM |
| 11 | `train_pipeline gaussian` | ✅ Aligned | — |
| 12 | `phase5_calibration` (2nd) | 🔴 Wrong arg type | CRITICAL |
| 13 | `train_bitnet.py` | 🔴 File missing | CRITICAL |
| 14 | `backtest_v2` (3rd duplicate) | 🟡 Duplicate | MEDIUM |
| 15 | `config_validator validate-prod` | ✅ Aligned | — |
| 16 | `config_validator validate-params` | 🟠 File vs inline JSON | HIGH |
| 17 | `promotion_manager promote` (duplicate) | 🟡 Duplicate | MEDIUM |
| 18 | `promotion_manager from-report` | 🔴 Missing `--version` | CRITICAL |
| 19 | `promotion_manager list` | ✅ Aligned | — |
| 20 | `promote_v2.py` (2nd) | 🔴 File missing | CRITICAL |
| 21 | `promote_v2.py --dry-run` | 🔴 File missing | CRITICAL |
| 22 | `orchestrator.py` | ✅ Aligned | — |


================================================================================
SOURCE_FILE: docs/plans/you-are-auditing-a-goofy-prism.md
SOURCE_BYTES: 9977
PART: 10/10 FILE 3/6
================================================================================

> Created: 2026-05-16 · Updated: 2026-05-16 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# RR Model Training Audit — D:\Tradelatest

**Date:** 2026-05-16  
**Scope:** RR model training existence, dataset generation pipeline, wiring, and promotion.

---

## FINDINGS

### 1. Which file actually trains the RR model?

**PRIMARY:** `scripts/training/train_rr_model.py` (149 lines)  
- CLI entry point. Orchestrates the full RR training sequence.  
- Imports `RRPatternTrainer` from `src/config_layer/rr/rr_pattern_miner.py`.  
- Imports `load_dataset` from `src/config_layer/rr/rr_dataset_builder.py`.  
- Imports `register_rr_model`, `promote_rr`, `get_active_rr_entry` from `src/core/model_registry.py`.  

**TRAINER CLASS:** `src/config_layer/rr/rr_pattern_miner.py` — `RRPatternTrainer.train()` (lines 62–149)  
- Fits `sklearn.linear_model.Ridge` (alpha=10.0, configurable) on (X, y_rr).  
- Fits `sklearn.covariance.LedoitWolf` for Mahalanobis confidence estimation.  
- Trains a Gaussian Naive Bayes (manually implemented) on (X, y_win).  
- Serialises to JSON state dict for `NanoInferenceEngine` (pure-Python inference; no sklearn at predict-time).  
- Requires `numpy` + `scikit-learn` at train-time only.  
- **No xgboost. No lightgbm. No PyTorch.**

---

### 2. Is training integrated into train_pipeline.py?

**NO — RR training is NOT integrated into `src/training/train_pipeline.py`.**

`train_pipeline.py` has two entry points:
- `run_training_pipeline()` — TradeNet / binary-label (PyTorch) path.  
- `run_gaussian_update()` — 8-step Gaussian model update (GaussianNB + StandardScaler via `trainer.py`).

`run_gaussian_update()` calls `validate_dataset_integrity` from `rr_dataset_builder` (step 2) and saves a dataset snapshot, but **does NOT call `RRPatternTrainer`**. It trains the Gaussian model, not the RR model.

The RR training pipeline is a **standalone CLI** (`train_rr_model.py`) with no invocation from `train_pipeline.py`.

---

### 3. Was train_rr_model.py renamed or deleted?

**Neither.** The file **EXISTS** at `scripts/training/train_rr_model.py`. It is 149 lines, functional, and wired to the correct imports. It was **never deleted or renamed**.

---

### 4. Is rr_dataset.json ever consumed?

**Conditionally — and currently BLOCKED by three independent guards:**

| Guard | Location | Effect |
|-------|----------|--------|
| `load_dataset()` shape check | `rr_dataset_builder.py` | `11 != 35 features → ValueError` at row 0 |
| `validate_dataset_integrity()` | `rr_dataset_builder.py` | Raises if all `y_rr == 0.0` (all 430 samples are 0.0) |
| `rr_fusion.enabled = false` | Production config | No live path instantiates `RRFusionLayer` |
| `models/rr_model.json` | Filesystem | **MISSING** — graceful passthrough even if enabled |

**`models/rr_dataset.json` is DEGENERATE:**  
- 430 samples, 11 features (stale schema; canonical is 35).  
- All `y_rr = 0.0`, all `y_win = 0`. Labels were never populated.  
- Caused by old `rr_pattern_miner.py` with phantom `RR_SCHEMA` import — module failed silently, wrote zero-filled targets.  
- Documented in `docs/RR_DATA_INTEGRITY_AUDIT_2026_04_30.md`.  
- **Do NOT train on this file.**

---

## EXECUTION FLOW (end-to-end, current state)

```
STEP 1 — Build dataset (PREREQUISITE — MISSING VALID OUTPUT)
  scripts/data/build_rr_dataset.py
    └─ imports: build_dataset(), save_dataset(), validate_dataset_integrity()
                from src/config_layer/rr/rr_dataset_builder.py
    └─ build_dataset(trades, df)  [line 264 of rr_dataset_builder.py]
         ├─ extract_features()   → 35-dim vector per trade
         ├─ extract_target()     → (y_rr, y_win) from pnl_rr_net / rr_achieved
         └─ validate_dataset_integrity(X, y_rr, y_win)
    └─ save_dataset() → models/rr_dataset_{version}.json

STEP 2 — Train
  scripts/training/train_rr_model.py [--dataset <path>] [--version <ver>] [--promote]
    └─ load_dataset(path)
         └─ rr_dataset_builder.load_dataset()
              └─ validate_dataset_integrity()  ← BLOCKS on degenerate data
    └─ RRPatternTrainer().train(X, y_rr, y_win)
         ├─ Ridge.fit(Xs, y_rr)              ← sklearn
         ├─ LedoitWolf.fit(Xs)               ← sklearn
         └─ GaussianNB (manual)
    └─ trainer.save("models/rr_model_{version}.json")
    └─ register_rr_model(version, path, metrics)
         └─ src/core/model_registry.py → rr_registry.json

STEP 3 — Promote (optional, --promote flag)
  train_rr_model.py --promote
    └─ promote_rr(version)
         └─ model_registry.RRModelRegistry.promote()  [lines 865–877]
              └─ writes active pointer in rr_registry.json
    └─ shutil.copy2(output, "models/rr_model.json")   ← canonical path for engine_runner
```

---

## COMMAND TO RETRAIN FROM SCRATCH

```bash
# Step 1: Build a fresh RR dataset from real trade logs
# (Must have valid fusion JSONL logs with ENTRY/EXIT pairs)
python scripts/data/build_rr_dataset.py \
    --log-dir logs/ \
    --output models/rr_dataset_202505_v1.json

# Step 2: Train the model
cd D:\Tradelatest
python scripts/training/train_rr_model.py \
    --dataset models/rr_dataset_202505_v1.json \
    --version 202505_v1 \
    --promote \
    --zero-price-features
```

**PREREQUISITE CHECK before Step 2:**
```bash
python -c "
from src.config_layer.rr.rr_dataset_builder import load_dataset
X, y_rr, y_win = load_dataset('models/rr_dataset_202505_v1.json')
print(f'n={len(X)}, n_feat={len(X[0])}, y_rr_nonzero={sum(1 for y in y_rr if y != 0.0)}')
"
```
If `y_rr_nonzero == 0` → dataset is degenerate. Do NOT proceed.

---

## DEPENDENCY GRAPH

```
rr_dataset_builder.py
    ├─ extract_features()      ← features/feature_schema.CANONICAL_FEATURE_DIM (35)
    ├─ extract_target()        ← reads pnl_rr_net / rr_achieved / computed from trades
    ├─ build_dataset()         ← called by build_rr_dataset.py, run_gaussian_update()
    ├─ save_dataset()          ← called by build_rr_dataset.py
    ├─ load_dataset()          ← called by train_rr_model.py, model_registry.py
    └─ validate_dataset_integrity() ← called by all of the above

rr_pattern_miner.py
    ├─ RRPatternTrainer.train(X, y_rr, y_win)
    │       ├─ sklearn.linear_model.Ridge
    │       └─ sklearn.covariance.LedoitWolf
    ├─ RRPatternTrainer.save(path)
    ├─ NanoInferenceEngine         ← pure Python, no sklearn at runtime
    └─ train_and_save()            ← convenience wrapper (not called by CLI)

train_rr_model.py  [scripts/training/]
    ├─ rr_dataset_builder.load_dataset()
    ├─ RRPatternTrainer.train()
    ├─ RRPatternTrainer.save()
    ├─ model_registry.register_rr_model()
    └─ model_registry.promote_rr()

model_registry.py  [src/core/]
    └─ RRModelRegistry
            ├─ register_rr_model()    → rr_registry.json
            └─ promote_rr()           → sets active version + writes rr_model.json

rr_engine.py  [src/engines/]
    └─ loads NanoInferenceEngine from models/rr_model.json at runtime

rr_fusion.py  [src/config_layer/rr/]
    └─ RRFusionLayer — wraps NanoInferenceEngine
       CURRENTLY DISABLED: rr_fusion.enabled = false in production config
```

---

## MISSING PIPELINE PIECES

| Gap | Severity | Detail |
|-----|----------|--------|
| `models/rr_dataset.json` is degenerate | CRITICAL | 430 samples, all y_rr=0.0, 11-feature stale schema. Unusable. |
| `models/rr_model.json` is MISSING | HIGH | Engine passthrough; RR scoring contributes nothing to fusion |
| `rr_fusion.enabled = false` | HIGH | Even if model existed, RRFusionLayer is disabled in prod config |
| RR training not in `train_pipeline.py` | MEDIUM | Isolated CLI; no integration gate (Phase-5 calibration) before registration |
| No Phase-5 gate on RR training | MEDIUM | `train_rr_model.py` skips calibration gate that Gaussian path has |
| `build_rr_dataset.py` source unknown | MEDIUM | Script exists but source of trade logs (valid ENTRY/EXIT pairs) is unclear |
| `y_rr` label extraction depends on field presence | LOW | `extract_target()` has 3-level priority; missing `pnl_rr_net` → zeros |

---

## DEAD / UNWIRED SCRIPTS

| Script | Status |
|--------|--------|
| `scripts/data/build_rr_dataset.py` | **Wired** but produces no valid output (degenerate dataset) |
| `scripts/training/train_rr_model.py` | **Wired** but cannot execute (dataset blocks at `load_dataset()`) |
| `models/rr_dataset.json` | **Dead** — degenerate, blocked by 3 guards, must be deleted/quarantined |

---

## IS MODEL PROMOTION FUNCTIONAL?

**Architecturally YES. Practically NO.**

- `model_registry.RRModelRegistry.promote()` (lines 865–877) is implemented.  
- `promote_rr(version)` convenience function exists in `src/core/model_registry.py`.  
- `train_rr_model.py --promote` calls it and copies to canonical `models/rr_model.json`.  
- `control_plane/registry.py` registers `training.train_rr_model` as a control-plane command.  

**Blocker:** Training cannot run because `load_dataset()` raises `ValueError` on the only available dataset (degenerate shape + all-zero targets). No valid `rr_model.json` can be produced until a valid dataset is built.

**Promotion chain is functional end-to-end once a valid dataset exists.**

---

## ML LIBRARIES USED

| Library | Usage | File |
|---------|-------|------|
| `sklearn.linear_model.Ridge` | RR regression | `rr_pattern_miner.py:95–96` |
| `sklearn.covariance.LedoitWolf` | Mahalanobis confidence | `rr_pattern_miner.py:124–125` |
| `sklearn.cluster.KMeans` | Zone registry (unrelated) | `scripts/analysis/zone_registry_builder.py:5` |
| numpy | Matrix ops in trainer | `rr_pattern_miner.py:69` |
| xgboost | **NOT PRESENT** | — |
| lightgbm | **NOT PRESENT** | — |
| PyTorch | TradeNet path only | `src/training/trainer.py` |


================================================================================
SOURCE_FILE: docs/plans/you-are-implementing-phase-integrity-inherited-tulip.md
SOURCE_BYTES: 31363
PART: 10/10 FILE 4/6
================================================================================

> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Phase-Integrity Hardening — Implementation Plan

## Context

The repo already shipped the **first** integrity-hardening pass (LLM fail-open, RR drift bypass, config hash, BitNet debug-safe default, etc.). What remains is the **deterministic integrity spine** — six surfaces where the system still fails-open or fails-silent:

1. `trade_replay_validator.py` blindly trusts `pnl_rr_net` (stub replay), making backtest validation tautological.
2. There is no canonical integrity-event emitter — observability is scattered across `engine_telemetry.py`, ad-hoc `log.warning`, and silent `pass`.
3. Three+ JSONL iterators (`compress_logs_for_llm.py`, `trade_logger.py`, `replay_memory_engine.py`, `analyze_fusion_shadow.py`) discard malformed lines with no count, no event, no ratio gate.
4. `crt_feature_builder.py:117` maps **unknown session strings to 0.0**, which is the index for `london` — silent training contamination.
5. Three incompatible BitNet model schemas (`legacy_6input`, ad-hoc 35-d, ad-hoc 38-d via `CANONICAL_FEATURE_DIM`) coexist with no schema-version enforcement and `bitnet_runner.py:61` silently truncates feature vectors.
6. `feature_order_hash` is computed by `feature_schema.py` and stored by the Gaussian path, but the **BitNet inference path never verifies it**, so reordered features go undetected.

Goal: surgical in-place patches that add **structured integrity telemetry**, convert each fail-open to fail-closed (or fail-visible), preserve all existing CLI / output formats, and keep legacy model loaders working with explicit warnings.

User-confirmed scope decisions:
- Replay validator stays library-style; fail-closed if the caller's trade dict lacks `entry_price` / `sl_price` / `tp1_price` / `tp2_price` / `direction`. No TradeRecord schema change.
- `model_contract.py` imports `CANONICAL_FEATURE_DIM` from `features.feature_schema` (single source of truth) and asserts equality at module load.
- JSONL corruption patch covers `src/replay/replay_memory_engine.py` and `src/runtime/analyze_fusion_shadow.py` in addition to the three files named in the spec.

---

## Critical files

| File | Role in patch |
| --- | --- |
| `src/utils/integrity_events.py` (NEW) | Canonical `emit_integrity_event()` spine; appends to `logs/integrity_events.jsonl`; never raises. |
| `src/bitnet/model_contract.py` (NEW) | `CANONICAL_MODEL_SCHEMA_VERSION="bitnet_v3"`, normalizers for legacy schemas, mismatch checks. |
| `scripts/misc/trade_replay_validator.py` | Replace stub with deterministic candle replay; emit `REPLAY_MISMATCH` / `REPLAY_TRADE_INCOMPLETE` / `REPLAY_NO_CANDLES`. |
| `src/features/crt_feature_builder.py` | Unknown-session detection: encode `-1.0`, emit `SESSION_UNKNOWN`, honour `STRICT_SESSION_VALIDATION`. |
| `src/features/feature_schema.py` | Add `SESSION_UNKNOWN = -1.0` constant; keep `SESSION_MAP` strict-encoding docstring honest. |
| `scripts/analysis/compress_logs_for_llm.py` | Replace silent `continue` with counted malformed + integrity event + ratio gate. |
| `src/journal/trade_logger.py` | Same pattern for `TradeLogger.load_all()`. |
| `src/replay/replay_memory_engine.py` | Same pattern for the batch loader at line 302–303. |
| `src/runtime/analyze_fusion_shadow.py` | Wrap the `json.loads → None` site with an integrity event + counter; preserve `None` return. |
| `src/bitnet/bitnet_inference.py` | Verify `schema_version`, `feature_dim`, `feature_order_hash` at load via `model_contract`. Emit integrity warning for legacy formats. |
| `src/bitnet/bitnet_runner.py` | Remove silent slicing (`ordered_values[:self.expected_input_dim]`). Require exact match; fail-closed `RuntimeError`. |
| `scripts/export/export_bitnet_model.py` | Emit canonical `bitnet_v3` envelope (schema_version, feature_dim, feature_order_hash, feature_names, layers, metadata). |
| `scripts/export/generate_bootstrap_model.py` | Mark output as `legacy_6input` explicitly (already does) but stamp a `feature_order_hash` so loader can warn. |
| `scripts/export/regen_bitnet_35.py` | Wrap output in canonical envelope; preserve 35-d feature_order; mark `schema_version="bitnet_v3"` with `feature_dim=35` (legacy bridge). |

Existing utilities to reuse (do NOT re-implement):
- `src/utils/engine_telemetry.py` — pattern for `_append_jsonl()` + envelope (copy the fail-open file-write idiom).
- `events.event_fabric.make_event_envelope` — optional-import wrap, fallback envelope.
- `src/features/feature_schema._feature_order_hash()` — already canonical; reuse for the contract.
- `src/runtime/backtest_v2.CandleLoader` — referenced only by callers; replay function itself stays candle-list based.

---

## Phase 1 — Replay integrity (`scripts/misc/trade_replay_validator.py`)

**Patch in place.** Keep `classify_outcome`, `validate_all`, and the CSV export at `logs/validator_dataset.csv` byte-identical in the success path.

Rewrite **`replay_single_trade(trade, candles)`** to:

1. **Validate required trade fields** (fail-closed):
   ```
   REQUIRED = ("trade_id", "entry_price", "sl_price", "tp1_price", "tp2_price", "direction")
   missing = [k for k in REQUIRED if trade.get(k) is None]
   if missing:
       emit_integrity_event("REPLAY_TRADE_INCOMPLETE", "ERROR", "trade_replay_validator",
                            {"trade_id": trade.get("trade_id"), "missing_fields": missing})
       return {"error": "incomplete_trade", "trade_id": trade.get("trade_id"), "missing_fields": missing}
   ```
2. **Validate candles**:
   ```
   if not candles:
       emit_integrity_event("REPLAY_NO_CANDLES", "ERROR", "trade_replay_validator",
                            {"trade_id": trade.get("trade_id")})
       return {"error": "no_candles", "trade_id": trade.get("trade_id")}
   ```
3. **Deterministic forward simulation** (LONG ⇄ SHORT mirrored):
   - State: `tp1_hit=False`, `sl_effective=sl_price`, `exit_price=None`, `exit_reason=None`.
   - For each candle in order, read `high`, `low`, `close`, `timestamp`.
   - LONG branch:
     - Pessimistic SL-first (matches `BacktestRunner` semantics): if `low <= sl_effective`, `exit_price=sl_effective`, `exit_reason="SL-BE" if tp1_hit else "SL"`; break.
     - Else if `high >= tp2_price`, `exit_price=tp2_price`, `exit_reason="TP2"`; break.
     - Else if (not `tp1_hit`) and `high >= tp1_price`: set `tp1_hit=True`, `sl_effective=entry_price` (BE move).
   - SHORT branch: mirrored (`high>=sl_effective` for stop; `low<=tp2_price` for TP2; `low<=tp1_price` for TP1).
   - If loop ends without exit: `exit_reason="TIMEOUT"`, `exit_price=candles[-1]["close"]`.
4. **Compute** `recomputed_rr`:
   ```
   risk = abs(entry_price - sl_price)
   sign = +1 if direction == "LONG" else -1
   recomputed_rr = sign * (exit_price - entry_price) / risk   # risk>0 guaranteed by validation above
   ```
   Reject division if `risk == 0` → integrity event `REPLAY_ZERO_RISK`, return error row.
5. **Mismatch detection**:
   ```
   MAX_RR_DELTA = 0.05
   original_rr = float(trade.get("pnl_rr_net", 0.0))
   rr_delta = recomputed_rr - original_rr
   replay_consistent = abs(rr_delta) <= MAX_RR_DELTA
   if not replay_consistent:
       emit_integrity_event("REPLAY_MISMATCH", "WARNING", "trade_replay_validator",
           {"trade_id": trade["trade_id"], "expected_rr": original_rr,
            "recomputed_rr": recomputed_rr, "delta": rr_delta,
            "original_exit_reason": trade.get("exit_reason"),
            "replayed_exit_reason": exit_reason})
   ```
6. **Extend the return dict** with:
   - `replay_consistent: bool`
   - `rr_delta: float`
   - `replay_path: {candles_processed, tp1_hit_at_index, exit_index, exit_timestamp, exit_reason_replayed}`
   - Preserve every existing key (`recomputed_rr`, `original_rr`, `diff`, `is_match`, `exit_reason`, `candles_processed`, `tp1_hit`, `tp2_hit`, `features`, `outcome`) so CSV downstream is a strict superset, not a replacement.

`validate_all()` stays untouched except: surface an aggregate counter (`replay_consistent_count`, `replay_mismatch_count`) and emit one summary `REPLAY_BATCH_SUMMARY` integrity event at the end.

---

## Phase 2 — Integrity event spine (`src/utils/integrity_events.py`)

New module, ~80 LOC. Mirrors `engine_telemetry._append_jsonl` semantics:

```python
from pathlib import Path
import json, logging, time, sys

_LOG_PATH = Path("logs/integrity_events.jsonl")
_logger = logging.getLogger("IntegrityEvents")

class Severity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

_VALID = {Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL}

def emit_integrity_event(event_type: str, severity: str, source: str, payload: dict) -> None:
    """Append one integrity event to logs/integrity_events.jsonl. NEVER raises."""
    try:
        if severity not in _VALID:
            severity = Severity.WARNING
        record = {
            "ts":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event":    str(event_type),
            "severity": severity,
            "source":   str(source),
            "payload":  payload if isinstance(payload, dict) else {"raw": str(payload)},
        }
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except Exception as exc:                                          # noqa: BLE001
        try:
            _logger.debug("integrity_events: write failed: %s", exc)
            print(f"[integrity_events:FALLBACK] {event_type} {severity} {source} {payload}",
                  file=sys.stderr)
        except Exception:
            pass
```

This is intentionally **smaller** than `engine_telemetry.py` — no envelope, no event_fabric dependency, no class state. The contract is "append-only JSONL, never throws", per spec.

Callers always import lazily inside the function to keep import graphs clean:
```python
from src.utils.integrity_events import emit_integrity_event, Severity
```

---

## Phase 3 — JSONL corruption visibility

Same surgical pattern at five sites. Per file: introduce a small helper or inline counter.

**Shared idiom** (inlined per file, no new shared helper — keeps blast radius minimal):

```python
malformed = 0
valid = 0
for lineno, line in enumerate(fh, 1):
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
        valid += 1
        # ... existing yield/append behavior ...
    except json.JSONDecodeError as exc:
        malformed += 1
        emit_integrity_event(
            "JSONL_CORRUPTION", "WARNING", "<module_name>",
            {"path": str(path), "line_number": lineno,
             "raw_preview": line[:160], "error": str(exc)},
        )
        continue

total = malformed + valid
if total and (malformed / total) > 0.10:                              # MAX_CORRUPTION_RATIO
    emit_integrity_event(
        "JSONL_CORRUPTION_THRESHOLD_EXCEEDED", "ERROR", "<module_name>",
        {"path": str(path), "malformed_lines": malformed,
         "valid_lines": valid, "corruption_ratio": malformed / total},
    )
```

Sites to patch (preserve every existing return type, yield semantics, and return value):
- `scripts/analysis/compress_logs_for_llm.py:45-48` (`_iter_records`)
- `src/journal/trade_logger.py:73-76` (`TradeLogger.load_all`)
- `src/replay/replay_memory_engine.py:302-303` (batch loader)
- `src/runtime/analyze_fusion_shadow.py:48-50` — keep the `return None` contract but emit a `JSONL_CORRUPTION` event before returning; this site is single-line, not a loop, so no ratio gate applies.

`MAX_CORRUPTION_RATIO = 0.10` declared as a module-level constant only inside the looping sites.

Pipelines never fail. Only visibility changes.

---

## Phase 4 — Unknown-session coercion fix

**`src/features/feature_schema.py`** — add the explicit sentinel right under `SESSION_MAP` (line ~94):

```python
SESSION_UNKNOWN: float = -1.0   # explicit out-of-band marker; never collides with any mapped session.
```

**`src/features/crt_feature_builder.py:116-117`** — replace:

```python
session = str(candle.get("session", "unknown")).lower().strip()
if session in SESSION_MAP:
    features["session"] = SESSION_MAP[session]
else:
    features["session"] = SESSION_UNKNOWN
    raw = candle.get("session")
    from src.utils.integrity_events import emit_integrity_event, Severity
    emit_integrity_event(
        "SESSION_UNKNOWN", "WARNING", "crt_feature_builder",
        {"raw_session": repr(raw), "normalized": session,
         "encoded_value": SESSION_UNKNOWN},
    )
    if os.environ.get("STRICT_SESSION_VALIDATION", "false").lower() == "true":
        raise ValueError(f"Unknown session value: {raw!r}")
```

Notes:
- `.strip()` added to match `live_engine_hook._normalize_session` whitespace handling.
- `os` import is already present in the module (check at edit time; add if missing).
- Default remains non-fatal; strict mode opt-in via env var (matches the `BITNET_DEBUG` precedent).
- The `SESSION_MAP` docstring claim ("Unknown values raise ValueError") becomes truthful **only when strict mode is on**. Update the comment to reflect this.

---

## Phase 5 — Canonical BitNet serialization contract

**New** `src/bitnet/model_contract.py`:

```python
"""Canonical BitNet serialization contract. Legacy formats still loadable; mismatches fail-closed."""
from __future__ import annotations
import hashlib, json
from typing import Any
from features.feature_schema import CANONICAL_FEATURE_DIM as _SCHEMA_DIM, CANONICAL_FEATURES, FEATURE_ORDER_HASH

CANONICAL_MODEL_SCHEMA_VERSION = "bitnet_v3"
CANONICAL_FEATURE_DIM = _SCHEMA_DIM            # single source of truth
assert CANONICAL_FEATURE_DIM == 38, "BitNet v3 contract requires 38-feature canonical schema"

LEGACY_SCHEMAS = {"legacy_6input", "bitnet_export_v1"}

def feature_order_hash(feature_names: list[str]) -> str:
    payload = json.dumps(list(feature_names), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]

def build_envelope(layers: list, *, feature_names: list[str] | None = None,
                   metadata: dict | None = None) -> dict:
    names = list(feature_names) if feature_names else list(CANONICAL_FEATURES)
    return {
        "schema_version": CANONICAL_MODEL_SCHEMA_VERSION,
        "feature_dim": len(names),
        "feature_order_hash": feature_order_hash(names),
        "feature_names": names,
        "layers": layers,
        "metadata": metadata or {},
    }

def normalize_loaded(model: dict) -> dict:
    """Return a normalized view: {schema_version, feature_dim, feature_order_hash, feature_names, layers, raw}.
    Emits an integrity event for legacy formats; NEVER silently reinterprets dims."""
    from src.utils.integrity_events import emit_integrity_event, Severity
    schema = model.get("schema_version") or model.get("schema") or "unknown"
    if schema == CANONICAL_MODEL_SCHEMA_VERSION:
        return {
            "schema_version": schema,
            "feature_dim": int(model["feature_dim"]),
            "feature_order_hash": model.get("feature_order_hash", ""),
            "feature_names": list(model.get("feature_names", [])),
            "layers": model["layers"],
            "raw": model,
        }
    # Legacy normalization
    if schema in LEGACY_SCHEMAS or "layer1_w" in model or "layers" in model:
        # infer dim
        if "input_dim" in model:
            dim = int(model["input_dim"])
        elif "layer1_w" in model:
            dim = 6
        elif "layers" in model and model["layers"]:
            first = model["layers"][0]
            dim = int(first.get("in", len(first.get("weights", [[None]])[0])))
        else:
            raise RuntimeError(f"BitNet model_contract: cannot infer feature_dim from schema={schema!r}")
        names = list(model.get("feature_order", []))
        h = feature_order_hash(names) if names else ""
        emit_integrity_event(
            "BITNET_LEGACY_LOAD", "WARNING", "bitnet.model_contract",
            {"schema": schema, "feature_dim": dim, "feature_order_hash": h,
             "note": "loaded under legacy bridge; upgrade to bitnet_v3"},
        )
        return {"schema_version": schema, "feature_dim": dim,
                "feature_order_hash": h, "feature_names": names,
                "layers": model.get("layers", []), "raw": model}
    raise RuntimeError(f"BitNet model_contract: unrecognized schema={schema!r}")
```

**`src/bitnet/bitnet_inference.py`** — patch `__init__`:
- After `self.model = json.load(f)`, call `meta = normalize_loaded(self.model)`.
- Store `self.schema_version`, `self.feature_dim`, `self.feature_order_hash`, `self.feature_names`.
- Keep existing branch logic for the forward pass selection (legacy vs export) — only the metadata layer becomes canonical.
- If `self.feature_dim != model_dim_inferred_from_layers`, raise `RuntimeError("BitNet feature dimension mismatch")`.

**`src/bitnet/bitnet_runner.py:54-61`** — fail-closed:

```python
ordered_values = [features[k] for k in CANONICAL_FEATURES]
if len(ordered_values) != self.expected_input_dim:
    from src.utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "BITNET_DIM_MISMATCH", "CRITICAL", "bitnet.runner",
        {"runtime_features": len(ordered_values),
         "model_input_dim": self.expected_input_dim,
         "model_schema_version": getattr(self.model, "schema_version", "unknown"),
         "model_feature_order_hash": getattr(self.model, "feature_order_hash", "")},
    )
    raise RuntimeError(
        f"BitNet feature dimension mismatch: runtime={len(ordered_values)} "
        f"model={self.expected_input_dim} — refusing to truncate. "
        f"Re-export model with schema_version={CANONICAL_MODEL_SCHEMA_VERSION}."
    )
input_vector = np.array(ordered_values, dtype=np.float32)
```

**Legacy bridge for 6-input models**: special-case `if self.model.schema_version == "legacy_6input"`: take only the six fields named in the model's `feature_order` (not a prefix slice) and emit one `BITNET_LEGACY_FEATURE_SUBSET` integrity event per process start. This preserves the existing operational behavior for the `legacy_6input` GA path without ever silently reinterpreting features.

**Export scripts**:
- `scripts/export/export_bitnet_model.py` — wrap the dict it currently writes via `model_contract.build_envelope(layers, feature_names=list(CANONICAL_FEATURES), metadata={"source": "export_bitnet_model"})`.
- `scripts/export/regen_bitnet_35.py` — same wrap, but pass the 35-element feature_order it already declares; resulting envelope has `schema_version="bitnet_v3"` + `feature_dim=35` + `feature_order_hash` for the 35-d ordering. Loaders treat any v3 model as canonical regardless of dim.
- `scripts/export/generate_bootstrap_model.py` — keep emitting `schema="legacy_6input"` (do NOT upgrade — this is a bootstrap path) but add `feature_order_hash` so the loader's warning carries the hash.

---

## Phase 6 — Runtime graph stabilization

Three additions, all inside `bitnet_inference.py` / `bitnet_runner.py` (no new files):

1. At BitNet load: compare `self.feature_order_hash` against `features.feature_schema.FEATURE_ORDER_HASH` **when** `self.schema_version == "bitnet_v3"` AND `self.feature_dim == CANONICAL_FEATURE_DIM`. Mismatch → CRITICAL `BITNET_FEATURE_ORDER_HASH_MISMATCH` + raise.
2. At BitNet load: if `schema_version` missing entirely AND the model has `layers` in the new shape, emit CRITICAL `BITNET_MISSING_SCHEMA_VERSION` and raise (only refuses true ambiguous models; legacy schemas still load via the legacy bridge above).
3. The `BITNET_DIM_MISMATCH` event from Phase 5 already covers runtime feature-count drift. Add the same check at the top of `BitNetModel.predict()` for defense-in-depth (already raises a `ValueError` there — just emit the integrity event before raising).

No other engines are touched. Per the spec: "preserve runtime behavior unless explicitly fixing corruption/fail-open behavior".

---

## Verification

End-to-end checks (read-only commands the user can run after the patch lands):

1. **Replay integrity** — synthesize a trade dict with known entry/SL/TP1/TP2/direction + a fabricated candle list that hits TP1 then SL:
   ```
   python -c "from scripts.misc.trade_replay_validator import replay_single_trade; ..."
   ```
   Assert: `replay_consistent==True`, `recomputed_rr` matches by-hand calc, `rr_delta` within `±0.05`.
   Then corrupt one OHLCV bar to force a mismatch and confirm `REPLAY_MISMATCH` lands in `logs/integrity_events.jsonl`.

2. **Integrity spine** — `python -c "from src.utils.integrity_events import emit_integrity_event; emit_integrity_event('SELFTEST','INFO','plan','{}')"` then tail `logs/integrity_events.jsonl`.

3. **JSONL corruption** — append a single malformed line to `logs/trade_journal.jsonl`, then call `TradeLogger().load_all()`; expect one `JSONL_CORRUPTION` event, no crash, all valid records loaded.

4. **Unknown session** — call `build_bitnet_features({"session": "tokyo", ...})`; expect `features["session"] == -1.0` and a `SESSION_UNKNOWN` event. Re-run with `STRICT_SESSION_VALIDATION=true` and confirm `ValueError`.

5. **BitNet contract** — load `model.json` (legacy_6input): expect `BITNET_LEGACY_LOAD` event, no truncation, model still runs for its declared 6 features. Load `model_export_format.json`: expect normalization to `bitnet_v3` semantics. Then construct a 4-dim weight matrix masquerading as `bitnet_v3` + 38-dim → expect `BITNET_FEATURE_ORDER_HASH_MISMATCH` and `RuntimeError`.

6. **pytest** — run the existing suite. The patch is BC for tests that pass valid trade dicts; replay tests that previously used the stub will need new fixtures (out-of-scope for this plan, called out in "remaining risks").

7. **Regression** — run one short backtest with `BacktestRunner` end-to-end, confirm no new `RuntimeError` paths, and `logs/integrity_events.jsonl` contains only expected lifecycle events.

---

## Self-review (mandatory artifacts)

### 1. File-by-file changelog
- **NEW** `src/utils/integrity_events.py` — `emit_integrity_event`, `Severity` enum, fail-open JSONL append.
- **NEW** `src/bitnet/model_contract.py` — `build_envelope`, `normalize_loaded`, `feature_order_hash`, `CANONICAL_MODEL_SCHEMA_VERSION`.
- **MOD** `scripts/misc/trade_replay_validator.py` — real candle replay; integrity events; preserved CSV.
- **MOD** `src/features/feature_schema.py` — add `SESSION_UNKNOWN = -1.0`.
- **MOD** `src/features/crt_feature_builder.py:116-117` — explicit unknown branch, integrity event, strict mode.
- **MOD** `scripts/analysis/compress_logs_for_llm.py:45-48` — count + emit + ratio gate.
- **MOD** `src/journal/trade_logger.py:73-76` — same pattern.
- **MOD** `src/replay/replay_memory_engine.py:302-303` — same pattern.
- **MOD** `src/runtime/analyze_fusion_shadow.py:48-50` — emit on JSONDecodeError, preserve `return None`.
- **MOD** `src/bitnet/bitnet_inference.py` — schema_version + feature_order_hash verification at load.
- **MOD** `src/bitnet/bitnet_runner.py:54-61` — remove silent slice; fail-closed dim mismatch; legacy bridge.
- **MOD** `scripts/export/export_bitnet_model.py` — wrap in `bitnet_v3` envelope.
- **MOD** `scripts/export/regen_bitnet_35.py` — wrap in `bitnet_v3` envelope (35-d).
- **MOD** `scripts/export/generate_bootstrap_model.py` — stamp `feature_order_hash`; keep `legacy_6input` schema label.

### 2. Fail-open behaviors removed
- `replay_single_trade` blindly trusting `pnl_rr_net` → real replay; mismatch is now visible.
- `SESSION_MAP.get(session, 0.0)` unknown→London → unknown→-1.0 + event.
- Silent `except JSONDecodeError: pass/continue` in four loaders → counted + visible.
- `BitNetRunner` `[:self.expected_input_dim]` silent slice → `RuntimeError`.
- `BitNetModel.__init__` accepting any JSON with `layers` → requires schema_version OR matches legacy bridge.

### 3. New fail-closed behaviors
- Replay: missing trade fields → `ERROR` event + error row.
- Replay: zero-risk trade → `ERROR` event + error row.
- BitNet load: missing `schema_version` on new-shape model → `RuntimeError`.
- BitNet load: `feature_order_hash` mismatch on canonical model → `RuntimeError`.
- BitNet predict: runtime/model dim mismatch → `RuntimeError` (previously silent slice).
- Optional via env: `STRICT_SESSION_VALIDATION=true` → `ValueError` on unknown session.

### 4. Backward-compatibility matrix

| Surface | Before | After | BC? |
| --- | --- | --- | --- |
| `replay_single_trade(trade, candles)` signature | unchanged | unchanged | yes |
| `validate_all` → `logs/validator_dataset.csv` columns | exists | superset (new cols appended) | yes (additive) |
| `TradeLogger.load_all()` return type | `list[dict]` | `list[dict]` | yes |
| `_iter_records` yield semantics | yields dicts | yields dicts (skips malformed, now logged) | yes |
| `analyze_fusion_shadow.py` return on bad JSON | `None` | `None` (also logs) | yes |
| `BitNetModel(path)` for legacy_6input | input_dim=6 | input_dim=6 + warning event | yes |
| `BitNetModel(path)` for bitnet_export_v1 | input_dim from JSON | normalized to v3 view + warning event | yes |
| `BitNetRunner.predict(features)` when dims match | works | works | yes |
| `BitNetRunner.predict(features)` when dims mismatch | silent slice + score | `RuntimeError` | **NO — intentional fail-closed** |
| `build_bitnet_features({"session":"tokyo"})` | encodes as 0.0 | encodes as -1.0 + event | **NO — intentional fix** |
| `build_bitnet_features({"session":"tokyo"})` with `STRICT_SESSION_VALIDATION=true` | encodes as 0.0 | raises ValueError | **NO — opt-in only** |

### 5. Replay validation flow
`caller assembles trade dict (entry/sl/tp1/tp2/direction/pnl_rr_net) and candle list → replay_single_trade → validate fields → validate candles → forward sim (direction-aware, BE on TP1 hit) → compute recomputed_rr → compare against pnl_rr_net → if |delta|>0.05 emit REPLAY_MISMATCH → return enriched row → validate_all aggregates → CSV at logs/validator_dataset.csv (superset) + REPLAY_BATCH_SUMMARY event`.

### 6. JSONL corruption flow
`loader opens file → per line: try json.loads → on success increment valid → on JSONDecodeError increment malformed + emit JSONL_CORRUPTION with line_number + raw_preview[:160] + continue → at EOF: if malformed/(malformed+valid) > 0.10 emit JSONL_CORRUPTION_THRESHOLD_EXCEEDED → return original data type unchanged`.

### 7. BitNet schema migration flow
`exporter calls model_contract.build_envelope(layers, feature_names) → writes JSON with {schema_version:"bitnet_v3", feature_dim, feature_order_hash, feature_names, layers, metadata}`.
`loader: model_contract.normalize_loaded(json) → if bitnet_v3 → verify feature_order_hash against features.feature_schema.FEATURE_ORDER_HASH when feature_dim==CANONICAL_FEATURE_DIM → else if legacy_6input/bitnet_export_v1 → emit BITNET_LEGACY_LOAD warning → continue working → else → raise`.
`runtime: BitNetRunner asserts len(canonical features)==model.feature_dim → never slices`.

### 8. Integrity event examples
```json
{"ts":"2026-05-20T14:03:11Z","event":"REPLAY_MISMATCH","severity":"WARNING","source":"trade_replay_validator","payload":{"trade_id":"T-7421","expected_rr":1.92,"recomputed_rr":1.04,"delta":-0.88,"original_exit_reason":"TP2","replayed_exit_reason":"SL-BE"}}
{"ts":"2026-05-20T14:03:11Z","event":"JSONL_CORRUPTION","severity":"WARNING","source":"src.journal.trade_logger","payload":{"path":"logs/trade_journal.jsonl","line_number":4172,"raw_preview":"{\"trade_id\":\"T-7421\",\"pnl\":1.92,\"resu","error":"Unterminated string starting at: line 1 column 41 (char 40)"}}
{"ts":"2026-05-20T14:03:11Z","event":"SESSION_UNKNOWN","severity":"WARNING","source":"crt_feature_builder","payload":{"raw_session":"'TOKYO'","normalized":"tokyo","encoded_value":-1.0}}
{"ts":"2026-05-20T14:03:11Z","event":"BITNET_LEGACY_LOAD","severity":"WARNING","source":"bitnet.model_contract","payload":{"schema":"legacy_6input","feature_dim":6,"feature_order_hash":"a1b2c3d4e5f60718","note":"loaded under legacy bridge; upgrade to bitnet_v3"}}
{"ts":"2026-05-20T14:03:11Z","event":"BITNET_DIM_MISMATCH","severity":"CRITICAL","source":"bitnet.runner","payload":{"runtime_features":38,"model_input_dim":35,"model_schema_version":"bitnet_v3","model_feature_order_hash":"f1e2d3c4b5a69708"}}
```

### 9. Performance impact analysis
- `emit_integrity_event` is one append-only `fh.write(json.dumps(...))` per event. Same cost as existing `engine_telemetry._append_jsonl`. Negligible (<50µs typical).
- Replay simulation is O(candles) per trade; was previously O(1) but tautological. New cost ≈ candle-loop already paid by `BacktestRunner` for the same trades.
- JSONL counters add one integer increment and one division per file load. Imperceptible.
- Session-unknown branch: one extra `dict in` check per candle on the cold path; hot path (known sessions) is unchanged.
- BitNet load: one extra dict normalization at load (per process). One hash compare. Inference path unchanged.

### 10. Remaining unfixed risks
- **Replay coverage gap**: nothing in the current codebase actually constructs the rich trade dict from `trade_journal.jsonl` — that schema lacks entry/SL/TP/direction. Until a caller (likely a new audit pipeline) is built, the replay validator only catches mismatches when callers feed it from `BacktestRunner`'s in-memory `Trade` objects. The integrity events make this gap **visible** (`REPLAY_TRADE_INCOMPLETE` count climbs) but don't close it.
- **Test fixtures**: existing tests that exercised the stub `replay_single_trade` will now hit `REPLAY_TRADE_INCOMPLETE` paths unless their fixtures are extended. Implementation should update fixtures alongside the code patch; this plan flags it but doesn't enumerate them.
- **Legacy 6-input feature mapping**: the `legacy_6input` bridge in `BitNetRunner` will need to pluck the six fields by name from the model's `feature_order`. If a deployed legacy model's `feature_order` is somehow missing, the runner raises — this is fail-closed by design but may surprise an operator whose model file was hand-edited.
- **Cross-process race on `logs/integrity_events.jsonl`**: append-only mode on POSIX is atomic for small writes, but on Windows two simultaneous appenders can interleave. Acceptable given the spec ("never throws, fallback stderr print"). A future improvement could route through a single writer thread; out of scope here.
- **`SESSION_MAP` upstream callers**: any code path that reads `features["session"]` and treats `< 0` as a sentinel will need to handle `-1.0`. The change is small but downstream consumers (zone-gate, scoring) should be grep'd for `features["session"] >= 0` patterns during implementation. Not enumerated in this plan to avoid scope creep — flagged as a verification step.
- **`assistant_project.md` session log**: CLAUDE.md mandates a SESSION LOG ENTRY appended on every response. This plan-mode session writes only the plan file per Plan-mode rules; the session log entry should be appended in the **implementation** session, not here.


================================================================================
SOURCE_FILE: docs/plans/you-are-implementing-stage-1-polished-token.md
SOURCE_BYTES: 33080
PART: 10/10 FILE 5/6
================================================================================

> Created: 2026-05-22 · Updated: 2026-05-22 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Stage-1 Recovery Phase — Implementation Plan

> **Previous work (completed):** Stage-1 Truth Dataset Builder is fully implemented and tested (38 tests pass). Real-world run: `accepted=203,588`, `rejected=305,382` (305,382 from v2.0 schema, missing 3 features). This plan covers the **Recovery Phase** only.

---

# Stage-1 Truth Dataset Builder — Original Plan (reference)

## Context

Stage-1 of the **TradingLLM** training pipeline needs a canonical, deterministic, multi-instrument training dataset assembled from existing backtest outputs (`opportunities.jsonl`, `compressed.json`, `trades.csv`). Today these artifacts live in two separate roots — `logs/{INSTRUMENT}/{RUN_ID}/` for the JSONL/JSON pair and `results/**/*trades*.csv` for the CSV — and there is no merging, no integrity contract, no bucket labeling, and no per-instrument summary. Without a clean truth dataset the downstream training pipeline (`src/training/train_pipeline.py`, `train_rr_model.py`, `train_bitnet.py`) reinvents extraction, RR labeling, and validation in three slightly different ways. The goal is one builder that produces:

- `data/master_{scope}_training.jsonl` — canonical training records (deterministic, streaming-built)
- `reports/integrity_report.json` — totals, rejection reasons, output hash, per-bucket distributions
- `reports/instrument_summary.csv` — per-instrument stats for quick eyeballing
- `reports/input_manifest.json` — discovered inputs, pairings, missing-counterpart warnings
- `reports/scope_summary.json` — instruments accepted vs rejected by scope

The builder is offline tooling (not the live hot path), so it follows fail-open per-record semantics with a global fail-fast on misconfiguration.

---

## Locked Design Decisions (from user)

1. **Input discovery — hybrid auto:** Default JSONL root `logs/`, CSV root `results/`. CLI overrides `--jsonl-root`, `--csv-root`, `--strict-layout`. Emit integrity events for missing counterparts; fail only when `--strict-layout=true`.
2. **Market scope — `--market-scope {auto,crypto,forex,all}` (default `crypto`).** Output filename derives from scope (`master_crypto_training.jsonl` / `master_forex_training.jsonl` / `master_multiasset_training.jsonl`). Classification: crypto = `*USDT, BTC*, ETH*, SOL*, DOGE*, XRP*, BNB*`; forex = `EUR*, GBP*, USD*, AUD*, XAU*`.
3. **Schema — contract-first.** Require all 38 `CANONICAL_FEATURES`. Preserve unknown keys in `extra_features`. Three levels: `STRICT` (reject extras + type mismatch), `WARN` (default), `LENIENT` (allow explicit fallback fills). Never silently truncate / reorder / zero-fill / drop.
4. **Buckets — static, `bucket_version=1`, inclusive lower / exclusive upper.**
   - RR: `LOSS` (rr<0), `SCRATCH` (0–1), `BASE` (1–2), `STRONG` (2–3), `OUTLIER` (≥3).
   - Duration (M15 candles): `FAST` (0–3), `NORMAL` (4–10), `SWING` (11–30), `EXTENDED` (31–90), `RUNNER` (>90).

---

## File-by-File Design

### New: `src/training/stage1_dataset_builder.py` (primary logic)

Single module, ~500 LOC. Public API surface:

```python
# Constants (no magic numbers in callers)
BUCKET_VERSION = 1
RR_BUCKET_EDGES = [(-float("inf"), 0.0, 0, "LOSS"),
                   (0.0, 1.0, 1, "SCRATCH"),
                   (1.0, 2.0, 2, "BASE"),
                   (2.0, 3.0, 3, "STRONG"),
                   (3.0, float("inf"), 4, "OUTLIER")]
DURATION_BUCKET_EDGES = [(0, 4, 0, "FAST"),
                         (4, 11, 1, "NORMAL"),
                         (11, 31, 2, "SWING"),
                         (31, 91, 3, "EXTENDED"),
                         (91, float("inf"), 4, "RUNNER")]
SCOPE_PATTERNS = {"crypto": (..."USDT","BTC*","ETH*",...),
                  "forex":  ("EUR*","GBP*","USD*","AUD*","XAU*")}

@dataclass(frozen=True)
class BuilderConfig:
    jsonl_root: Path; csv_root: Path
    output_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    market_scope: str = "crypto"
    validation_level: str = "WARN"     # STRICT | WARN | LENIENT
    strict_layout: bool = False
    min_feature_quality: float = 0.5
    instruments_override: tuple[str, ...] | None = None

@dataclass
class RejectionLedger:
    malformed_json: int = 0
    missing_features: int = 0
    schema_mismatch: int = 0
    type_mismatch: int = 0
    duplicate: int = 0
    out_of_scope: int = 0
    low_feature_quality: int = 0
    samples: list[dict] = field(default_factory=list)  # capped @ 50

@dataclass
class BuildResult:
    output_path: Path
    output_sha256: str
    integrity_report_path: Path
    instrument_summary_path: Path
    input_manifest_path: Path
    scope_summary_path: Path
    accepted: int
    rejected: RejectionLedger

# Top-level functions
def discover_inputs(cfg: BuilderConfig) -> dict: ...
def classify_scope(instrument: str, scope: str) -> bool: ...
def rr_bucket(rr: float) -> tuple[int, str]: ...
def duration_bucket(candles: int) -> tuple[int, str]: ...
def compute_feature_quality(features: dict) -> float: ...
def validate_record(rec: dict, cfg: BuilderConfig) -> tuple[bool, str | None, dict | None]: ...
def transform_record(rec: dict, source_meta: dict) -> dict: ...
def iter_opportunities(path: Path) -> Iterator[tuple[int, dict]]: ...
def build_dataset(cfg: BuilderConfig) -> BuildResult: ...   # public entry
```

**Streaming algorithm** (memory-efficient, deterministic):

1. **Discovery pass:** `discover_inputs(cfg)` builds the manifest by globbing
   `{jsonl_root}/*/*/opportunities.jsonl`, `{jsonl_root}/*/*/compressed.json`,
   `{csv_root}/**/*trades*.csv`. Pair them by instrument + run_id. Write `reports/input_manifest.json`.
2. **Read pass:** for each opportunities file, `iter_opportunities` yields `(line_no, record)` lazily (one `json.loads` per line). The first line is `run_header` — captured as source metadata, skipped from records. Malformed lines → `RejectionLedger.malformed_json++`, sample retained.
3. **Per-record transform:** `validate_record` enforces the 38-key contract; `transform_record` adds `regime` (via `RegimeClassifier.classify(features)`), `rr_bucket_id/label`, `duration_bucket_id/label`, `win_flag` (1 if `rr_achieved > 0` else 0), `feature_quality`, and `extra_features` for unknown keys.
4. **Buffering:** accepted records appended to an in-memory list `list[dict]` keyed by `(instrument, timestamp, source_run_id, line_no)`. Backtest outputs typically run ~100k–500k records — well within RAM. If we later need true constant-memory, a flag-gated external-sort path can be added; current spec says memory-efficient, not constant. List of small dicts (~1KB each) bounded at ~500MB worst case is acceptable.
5. **Sort + write pass:** `records.sort(key=lambda r: (r["instrument"], r["timestamp"], r["metadata"]["source_run_id"], r["metadata"]["source_line_no"]))`, then write each via `json.dumps(rec, sort_keys=True) + "\n"` to a `.tmp` sibling, `hashlib.sha256` accumulated as bytes are written, then `os.replace(tmp, final)` for atomic publish (pattern from `core/model_registry._save_atomic`).
6. **Reports pass:** assemble and write four reports atomically (same `.tmp` + replace).

**Output record shape:**

```jsonc
{
  "instrument": "BTCUSDT",
  "timestamp": "2022-01-02 07:45:00",
  "direction": "long",
  "entry": 47312.5, "sl": 47180.0, "tp": 47640.0,
  "outcome": "TP_HIT",
  "rr_achieved": 2.47,
  "duration_candles": 18,
  "mfe": 12.4, "mae": -3.1,
  "win_flag": 1,
  "regime": "TRENDING",
  "rr_bucket_id": 2, "rr_bucket_label": "BASE",
  "duration_bucket_id": 2, "duration_bucket_label": "SWING",
  "features": { /* 38 canonical keys, ordered, finite */ },
  "extra_features": { /* unknown-but-preserved keys */ },
  "metadata": {
    "schema_version": "3.0",
    "feature_dim": 38,
    "feature_hash": "<FEATURE_ORDER_HASH>",
    "feature_quality": 0.97,
    "extra_feature_count": 3,
    "bucket_version": 1,
    "source_run_id": "20260521_145509",
    "source_line_no": 14237,
    "source_path": "logs/BTCUSDT/20260521_145509/opportunities.jsonl"
  }
}
```

**Reuses (do not reinvent):**

- `CANONICAL_FEATURES`, `FEATURE_ORDER_HASH`, `SCHEMA_HASH`, `SESSION_MAP`, `TREND_MAP` from [src/features/feature_schema.py](src/features/feature_schema.py)
- `RegimeClassifier.classify(features)` from [src/regime/regime_classifier.py](src/regime/regime_classifier.py)
- `get_flow_logger("DATASET_BUILDER")` from `src/utils/logging_config.py`
- `safe_print` / `sanitize_for_console` from `src/utils/console_safe.py`
- `emit_integrity_event(event_type, severity, source, payload)` from `src/utils/integrity_events.py`
- Atomic-write pattern from `src/core/model_registry._save_atomic`

### New: `scripts/training/build_stage1_dataset.py` (thin CLI wrapper)

Follow the [scripts/training/train_pipeline.py](scripts/training/train_pipeline.py) shape exactly: bootstrap `src/` onto `sys.path`, then argparse → call `build_dataset(cfg)`.

```python
parser.add_argument("--jsonl-root", default="logs")
parser.add_argument("--csv-root", default="results")
parser.add_argument("--output-dir", default="data")
parser.add_argument("--reports-dir", default="reports")
parser.add_argument("--market-scope", choices=["auto","crypto","forex","all"], default="crypto")
parser.add_argument("--validation-level", choices=["STRICT","WARN","LENIENT"], default="WARN")
parser.add_argument("--strict-layout", action="store_true")
parser.add_argument("--min-feature-quality", type=float, default=0.5)
parser.add_argument("--instruments", default=None, help="Comma list to override scope filter")
parser.add_argument("--dry-run", action="store_true", help="Discover + manifest only, no records emitted")
```

Print one-line summary using `safe_print` on success; non-zero exit on hard-fail.

### New: `tests/test_stage1_dataset_builder.py`

Follow [tests/test_train_pipeline.py](tests/test_train_pipeline.py) style. Test cases:

1. `test_rr_bucket_edges` — bucket boundaries are inclusive-lower / exclusive-upper for every transition.
2. `test_duration_bucket_edges` — same for duration buckets.
3. `test_classify_scope_crypto_patterns` — BTCUSDT / ETHUSDT match; EURUSD does not.
4. `test_classify_scope_forex_patterns` — XAUUSD / GBPUSD match crypto=false / forex=true.
5. `test_compute_feature_quality_perfect_score` — all 38 finite → 1.0; mix of NaN → fractional.
6. `test_validate_record_missing_canonical_key_rejected` — strict + warn modes reject; counter increments.
7. `test_validate_record_unknown_key_preserved_in_extras` — `extra_features` populated; `extra_feature_count` matches.
8. `test_iter_opportunities_skips_run_header_line` — first line `run_header` not emitted as a record.
9. `test_iter_opportunities_malformed_line_recorded` — bad line → ledger.malformed_json++, iteration continues.
10. `test_build_dataset_deterministic_output_hash` — running twice on the same fixture yields identical `output_sha256`.
11. `test_build_dataset_record_order` — records sorted by `(instrument, timestamp, source_run_id, source_line_no)`.
12. `test_strict_layout_fails_on_missing_counterpart` — `strict_layout=True` + missing trades.csv pair → raises.
13. `test_strict_layout_false_logs_event_continues` — same input, default mode → integrity event emitted, build succeeds.
14. `test_scope_summary_records_rejected_instruments` — FX instruments under scope=crypto land in `rejected_instruments`.
15. `test_atomic_write_no_partial_output_on_crash` — monkeypatch the writer mid-stream → final path absent, `.tmp` absent on next run.

Fixtures live in `tests/fixtures/stage1/`: a small set of synthetic opportunities.jsonl files (one per instrument, ~20 records each) covering: clean rows, malformed JSON, missing canonical key, type mismatch, extra keys, mixed scopes.

### Optional: `assistant_project.md` session log entry

Per CLAUDE.md §6, append a SESSION LOG ENTRY for the build after implementation lands. Not part of this plan's edit set — handled during implementation.

---

## Critical Files to Read Before Editing

- [src/features/feature_schema.py](src/features/feature_schema.py) — canonical 38 features, `FEATURE_ORDER_HASH`, `SESSION_MAP`, `TREND_MAP`
- [src/regime/regime_classifier.py](src/regime/regime_classifier.py) — `RegimeClassifier.classify`
- [src/config_layer/rr/rr_dataset_builder.py](src/config_layer/rr/rr_dataset_builder.py) — RR label extraction precedence (rr_achieved → pnl_rr_net → computed)
- [src/utils/integrity_events.py](src/utils/integrity_events.py) — fail-open JSONL append API
- [src/utils/console_safe.py](src/utils/console_safe.py) — Windows cp1252 fallback
- [src/utils/logging_config.py](src/utils/logging_config.py) — `get_flow_logger`
- [src/core/model_registry.py](src/core/model_registry.py) — `_save_atomic` pattern
- [scripts/training/train_pipeline.py](scripts/training/train_pipeline.py) — CLI wrapper template

---

## Failure Modes (explicit)

| Failure | Detection | Response |
|---|---|---|
| `--jsonl-root` does not exist | `Path.exists()` at discovery | Fail-fast, exit non-zero |
| Opportunities file has no `run_header` line | First line missing `kind=="run_header"` | WARN log, treat all lines as records, ledger.malformed_json++ on parse fails |
| Malformed JSON line | `json.JSONDecodeError` | Skip, `ledger.malformed_json++`, sample (first 50) kept in integrity report |
| Missing canonical feature key | `set(CANONICAL_FEATURES) - record["features"].keys()` non-empty | Skip, `ledger.missing_features++`, emit integrity event in STRICT |
| Type mismatch (e.g., `session: "london"` instead of float) | `_coerce_feature_value` raises in STRICT, attempts fallback in LENIENT | STRICT: reject + `ledger.type_mismatch++`. LENIENT: coerce via `SESSION_MAP`/`TREND_MAP` if known mapping. WARN: same as STRICT but no event. |
| Duplicate `(instrument, timestamp, direction)` | In-memory `seen` set during merge | Skip duplicate, `ledger.duplicate++` |
| Out-of-scope instrument | `classify_scope(instrument, scope)` returns False | Skip, `ledger.out_of_scope++`, list in `scope_summary.json` |
| Feature quality below threshold | `compute_feature_quality(features) < min_feature_quality` | Skip, `ledger.low_feature_quality++` |
| Missing `trades.csv` counterpart for an opportunities file | `discover_inputs` pairing | `strict_layout=True` → raise; default → integrity event, build continues without enrichment |
| Trades.csv used only for cross-checking (mfe/mae present in opportunities.jsonl, so CSV is optional enrichment) | — | When present, used to fill missing `mfe/mae/duration_candles`; when absent, opportunities.jsonl is authoritative |
| `RegimeClassifier` raises on a record | Try/except per record | Skip, `ledger.schema_mismatch++` |
| Disk full during write | `OSError` on `.tmp` write | Tmp removed; original output (if any) untouched; raise |
| Hash mismatch between two runs on identical input | Final SHA-256 compare | Test #10 fails CI; manual investigation |

---

## Verification

End-to-end, in order:

```pwsh
# 1. Unit tests
python -m pytest tests/test_stage1_dataset_builder.py -v

# 2. Dry-run discovery on real data (no records emitted)
python scripts/training/build_stage1_dataset.py --dry-run --market-scope crypto

# 3. Full build, default scope=crypto
python scripts/training/build_stage1_dataset.py --market-scope crypto

# 4. Determinism check — second run produces identical hash
python scripts/training/build_stage1_dataset.py --market-scope crypto
# Compare sha256 fields in two integrity reports

# 5. Strict-layout build (should warn or fail on any missing pair)
python scripts/training/build_stage1_dataset.py --market-scope crypto --strict-layout

# 6. Forex scope smoke test
python scripts/training/build_stage1_dataset.py --market-scope forex

# 7. Spot-check output
python -c "import json; print(sum(1 for _ in open('data/master_crypto_training.jsonl')))"
python -c "import json; r=json.load(open('reports/integrity_report.json')); print(r['totals'])"
```

Expected: integrity report shows non-zero `accepted`, near-zero rejections on clean data, all per-bucket counts present, `output_sha256` identical between back-to-back runs.

---

## Integration Notes

- **Downstream consumers**: `src/training/train_pipeline.py` and `src/training/train_bitnet.py` currently load training data through `load_training_data(path)` expecting `{"features": {...}, "label": int}` records. Stage-1's `win_flag` field maps directly to `label`; `features` already matches the 38-key contract. A small adapter `_stage1_to_training_record(rec)` should live alongside `load_training_data` — out of scope for this plan but flagged.
- **No production config change required.** Bucket edges, scope patterns, and validation level are module constants (not hot-path tunables) — keeping them in code avoids a `_compute_hash.py` rehash and a governance promotion. The `bucket_version=1` constant is the future migration handle.
- **Governance**: Stage-1 outputs are training inputs, not promotable artifacts. No `ConfigValidator` involvement. The output file's SHA-256 is recorded in the integrity report for downstream traceability and is included in any model registry entry trained from this dataset (caller's responsibility).
- **Coexistence with `rr_dataset_builder.py`**: Stage-1 supersedes the per-trade RR extraction inside `rr_dataset_builder.build_dataset()` but the older function stays put — Phase-1 rollout uses Stage-1 for new training runs; existing callers keep working until they migrate.
- **Reports directory**: `reports/` does not currently exist. Builder creates it on first write (`Path.mkdir(parents=True, exist_ok=True)`).
- **Memory profile**: ~500k records × ~2KB serialized ≈ 1GB peak during sort. Acceptable for offline tooling. If a future dataset crosses 5M records, add a `--external-sort` path that writes per-instrument shard files then merges via `heapq.merge`.

---

## Self-Review Checklist

- [ ] No magic numbers in caller code; all bucket edges + scope patterns live as module constants with `BUCKET_VERSION=1` migration handle.
- [ ] All file writes go through atomic `.tmp` + `os.replace`.
- [ ] All JSON serialization uses `sort_keys=True` for determinism.
- [ ] No `print()` in `src/`; only `get_flow_logger("DATASET_BUILDER")` and `safe_print` in the CLI.
- [ ] No pandas in the hot path; CSV via stdlib `csv.DictReader`, JSONL via line iteration.
- [ ] Schema hash and feature-order hash recorded per record + once in the integrity report.
- [ ] Test #10 (determinism) is the canary — it must pass before any PR is opened.
- [ ] Rejection samples capped at 50 to keep `integrity_report.json` small even on dirty data.
- [ ] Windows path handling: all `Path()` objects, never raw string joins.
- [ ] CLAUDE.md §6 session log entry appended after merge.

---

# Recovery Phase — Plan

## Context

Stage-1 builder (completed) rejected 305,382 records from v2.0-schema ETHUSDT runs (`logs/ETHUSDT/20260519_*/`) because the 38-key contract requires `liquidity_distance` (index 35), `liquidity_pressure_score` (index 36), and `volume_spike` (index 37) which are absent from v2.0's 35-feature vector. The goal is to determine if these records can be recovered — without fabrication — and document the outcome. If unrecoverable, produce a regen path.

**User constraints (verbatim, non-negotiable):**
- DO NOT zero-fill, fabricate, silently inject defaults, or weaken schema validation
- If exact derivation impossible: mark `{ recovery_status: "UNRECOVERABLE" }`, do not synthesize
- Reject recovered row if `feature_quality < 0.70` or `derived_field_confidence < 0.95`
- FAIL if expectancy changes > 5% or win_rate changes > 3%

---

## Key Findings (from exploration)

### Feature derivation formulas (from `src/features/feature_pipeline.py`)

| Feature | Formula | Required inputs |
|---------|---------|----------------|
| `liquidity_distance` | `min(abs(close - last_swing_high_price), abs(close - last_swing_low_price), abs(close - bos_level)) / (atr × close)` | `close`, `atr`, `last_swing_high_price`, `last_swing_low_price`, `break_of_structure` |
| `liquidity_pressure_score` | `exp(-0.5 × liquidity_distance).clip(0, 1)` with `fillna(10.0)` | `liquidity_distance` |
| `volume_spike` (adaptive) | `(volume_ratio > rolling_percentile_75(volume_ratio, window=50)).astype(int8)` | `volume_ratio` (rolling 50-bar window) |
| `volume_spike` (fallback) | `(volume_ratio > 1.5).astype(int8)` | `volume_ratio` only |

### Why all 3 are UNRECOVERABLE from per-record snapshots

| Feature | UNRECOVERABLE reason | Code |
|---------|---------------------|------|
| `liquidity_distance` | `last_swing_high_price` and `last_swing_low_price` are **intermediate carry-forward series** computed inside `compute_structure_liquidity()` — they are never stored in the feature vector. v2.0 only has `swing_high`/`swing_low` as **binary flags** (0/1), not price levels. A single snapshot record cannot reconstruct the time-series carry-forward. | `MISSING_INTERMEDIATE_SERIES` |
| `liquidity_pressure_score` | Derives from `liquidity_distance`, which is UNRECOVERABLE | `DEPENDS_ON_UNRECOVERABLE` |
| `volume_spike` | The adaptive percentile version (used for 97%+ of records after warmup) requires a rolling 50-bar window of `volume_ratio`. Per-record snapshots have only the current bar's `volume_ratio`. The fixed 1.5× fallback approximation achieves ~70–80% agreement with the adaptive result — far below the required 0.95 confidence threshold. | `CONFIDENCE_BELOW_THRESHOLD` |

**Net result: 0 of 305,382 v2.0 records are recoverable at the required quality threshold.** The recovery script must document this honestly and recommend re-running the opportunity scanner for the affected instruments.

### Infrastructure for fresh v3.0 runs

- **Opportunity scanner:** `scripts/research/opportunity_scanner.py` — simulates both LONG and SHORT per candle, outputs to `results/opportunities/{INSTRUMENT}/{RUN_ID}/opportunities.jsonl`
- **yfinance data:** `data/yfinance/BTCUSDT_M15.csv`, `ETHUSDT_M15.csv`, `SOLUSDT_M15.csv`, `DOGEUSDT_M15.csv`, `XRPUSDT_M15.csv`, `BNBUSDT_M15.csv` (all present)
- Fresh runs from the opportunity scanner will use the current v3.0 `FeaturePipeline` and will naturally emit all 38 features

---

## Files to Create

### 1. `scripts/training/recover_v2_runs.py` (primary)

**Purpose:** Scans v2.0 runs, attempts derivation of 3 missing features, classifies all as UNRECOVERABLE, outputs reports with re-generation recommendations.

**Public API:**
```python
@dataclass(frozen=True)
class RecoveryConfig:
    logs_root: Path = Path("logs")
    reports_dir: Path = Path("reports")
    output_dir: Path = Path("data")
    min_confidence: float = 0.95   # per user spec
    min_feature_quality: float = 0.70  # per user spec

RECOVERY_VERSION = "v1.0"
UNRECOVERABLE_CODES = {
    "MISSING_INTERMEDIATE_SERIES",
    "DEPENDS_ON_UNRECOVERABLE",
    "CONFIDENCE_BELOW_THRESHOLD",
}

@dataclass
class FieldRecoveryAttempt:
    field: str
    status: str          # "RECOVERED" | "UNRECOVERABLE"
    code: str            # one of UNRECOVERABLE_CODES, or "" if RECOVERED
    explanation: str
    confidence: float    # 0.0–1.0; 0.0 if not derivable at all

@dataclass
class RecoveryResult:
    schema_report_path: Path
    delta_report_path: Path
    recovered_output_path: Path
    total_scanned: int
    recovered: int         # expected: 0
    unrecoverable: int     # expected: total_scanned
    by_instrument: dict    # instrument → {run_ids, record_count}
    recommendations: list[str]

def discover_v2_runs(cfg: RecoveryConfig) -> dict: ...
    # Scans logs/ for opportunities.jsonl with feature_dim=35 or schema_version != "3.0"
    # Returns {instrument: [{run_id, path, record_count}]}

def attempt_derive_liquidity_distance(features: dict) -> FieldRecoveryAttempt: ...
    # Returns UNRECOVERABLE / MISSING_INTERMEDIATE_SERIES
    # confidence=0.0: last_swing_high/low price not in snapshot

def attempt_derive_liquidity_pressure_score(ld_attempt: FieldRecoveryAttempt) -> FieldRecoveryAttempt: ...
    # Returns UNRECOVERABLE / DEPENDS_ON_UNRECOVERABLE
    # confidence=0.0

def attempt_derive_volume_spike(features: dict) -> FieldRecoveryAttempt: ...
    # Applies fixed 1.5× fallback, estimates confidence ~0.75 (literature: adaptive vs fixed disagree ~25% of bars)
    # Returns UNRECOVERABLE / CONFIDENCE_BELOW_THRESHOLD since 0.75 < 0.95

def run_recovery(cfg: RecoveryConfig) -> RecoveryResult: ...
    # 1. discover_v2_runs
    # 2. For each record: attempt all 3 derivations
    # 3. If any field UNRECOVERABLE → stamp record, write to separate provenance log
    # 4. Write recovered_v2_to_v3.jsonl (empty, but exists for traceability)
    # 5. Write schema_recovery_report.json + recovery_acceptance_delta.json atomically
    # 6. Return RecoveryResult

def main(argv=None) -> int: ...
    # argparse: --logs-root, --reports-dir, --output-dir
    # calls run_recovery, prints summary via safe_print
```

**Schema recovery report (`reports/schema_recovery_report.json`):**
```jsonc
{
  "recovery_version": "v1.0",
  "generated_at": "2026-05-22T...",
  "schema_drift": {
    "v2_feature_dim": 35,
    "v3_feature_dim": 38,
    "missing_fields": ["liquidity_distance", "liquidity_pressure_score", "volume_spike"]
  },
  "field_analysis": {
    "liquidity_distance": {
      "status": "UNRECOVERABLE", "code": "MISSING_INTERMEDIATE_SERIES",
      "confidence": 0.0,
      "explanation": "Requires last_swing_high_price and last_swing_low_price carry-forward series. v2.0 only stores swing_high/swing_low binary flags (0/1), not price levels. Per-record snapshot cannot reconstruct time-series state."
    },
    "liquidity_pressure_score": {
      "status": "UNRECOVERABLE", "code": "DEPENDS_ON_UNRECOVERABLE",
      "confidence": 0.0,
      "explanation": "Formula: exp(-0.5 × liquidity_distance). Depends on liquidity_distance which is UNRECOVERABLE."
    },
    "volume_spike": {
      "status": "UNRECOVERABLE", "code": "CONFIDENCE_BELOW_THRESHOLD",
      "confidence": 0.75,
      "explanation": "Fixed 1.5× threshold approximation achieves ~75% agreement with adaptive percentile. Required: 0.95. Gap: 0.20. No richer per-record data available to improve estimate."
    }
  },
  "totals": {
    "v2_records_scanned": 305382,
    "recovered": 0,
    "unrecoverable": 305382,
    "by_code": {
      "MISSING_INTERMEDIATE_SERIES": 305382,
      "DEPENDS_ON_UNRECOVERABLE": 305382,
      "CONFIDENCE_BELOW_THRESHOLD": 305382
    }
  },
  "by_instrument": {
    "ETHUSDT": {
      "runs": ["20260519_113806", "..."],
      "record_count": 305382
    }
  },
  "recommendations": [
    "Re-run opportunity_scanner.py for ETHUSDT (same yfinance data) to generate v3.0 records",
    "python scripts/research/opportunity_scanner.py --csv data/yfinance/ETHUSDT_M15.csv --instrument ETHUSDT --output-dir logs/",
    "Then re-run Stage-1 builder: python scripts/training/build_stage1_dataset.py --market-scope crypto"
  ]
}
```

**Recovery acceptance delta (`reports/recovery_acceptance_delta.json`):**
```jsonc
{
  "before_recovery": {
    "accepted": 203588, "rejected_missing_features": 305382, "total_processed": 508970,
    "acceptance_rate": 0.4001
  },
  "after_recovery": {
    "newly_recovered": 0, "still_unrecoverable": 305382,
    "net_accepted": 203588, "acceptance_rate": 0.4001
  },
  "delta": { "net_new_accepted": 0, "acceptance_rate_delta_pct": 0.0 },
  "stat_shift": { "rr_shift": null, "win_rate_shift": null, "expectancy_shift": null,
                  "note": "No records promoted; stat-shift check not applicable" },
  "path_forward": "Re-run opportunity_scanner.py; expected +305382 accepted records from ETHUSDT alone"
}
```

### 2. `scripts/training/scan_opportunities_yfinance.py` (new; generates fresh v3.0 runs)

**Purpose:** Convenience wrapper that runs `opportunity_scanner.py` for all 6 crypto instruments using yfinance M15 CSVs. Outputs to `logs/{INSTRUMENT}/{RUN_ID}/` (where Stage-1 builder discovers them).

```python
INSTRUMENTS = [
    ("BTCUSDT", "data/yfinance/BTCUSDT_M15.csv"),
    ("ETHUSDT", "data/yfinance/ETHUSDT_M15.csv"),
    ("SOLUSDT", "data/yfinance/SOLUSDT_M15.csv"),
    ("DOGEUSDT", "data/yfinance/DOGEUSDT_M15.csv"),
    ("XRPUSDT",  "data/yfinance/XRPUSDT_M15.csv"),
    ("BNBUSDT",  "data/yfinance/BNBUSDT_M15.csv"),
]
# For each instrument: subprocess.run(["python", "scripts/research/opportunity_scanner.py",
#   "--csv", csv_path, "--instrument", instr, "--output-dir", "logs/"])
# Print one-line summary per instrument: accepted_opportunities count
# At end: print total + suggest running Stage-1 builder
```

**Note:** `opportunity_scanner.py` is called with `--output-dir logs/` so output lands in `logs/{INSTRUMENT}/{RUN_ID}/opportunities.jsonl`, exactly where Stage-1 builder discovers it.

### 3. `tests/test_recover_v2_runs.py` (new; 9 tests)

All tests use `tmp_path` fixtures with synthetic 35-feature opportunities.jsonl files.

1. `test_discover_v2_runs_finds_35feature_files` — discovery identifies runs with feature_dim=35; ignores v3.0 runs
2. `test_attempt_derive_liquidity_distance_unrecoverable` — returns UNRECOVERABLE, code=MISSING_INTERMEDIATE_SERIES, confidence=0.0
3. `test_attempt_derive_liquidity_pressure_score_cascades` — if ld is UNRECOVERABLE → lps is DEPENDS_ON_UNRECOVERABLE
4. `test_attempt_derive_volume_spike_confidence_below_threshold` — fixed 1.5× computed, but confidence=0.75 < 0.95 → UNRECOVERABLE
5. `test_run_recovery_produces_empty_output` — all records UNRECOVERABLE → recovered_v2_to_v3.jsonl created but has 0 lines
6. `test_schema_recovery_report_structure` — report has all required top-level keys; totals.recovered=0
7. `test_recovery_acceptance_delta_structure` — delta has before/after/delta keys; net_new_accepted=0
8. `test_run_recovery_atomic_writes` — crash during report write leaves no partial files
9. `test_run_recovery_idempotent` — running twice produces identical reports (same SHA-256)

---

## Reuses

- `safe_print`, `sanitize_for_console` from `src/utils/console_safe.py`
- `emit_integrity_event` from `src/utils/integrity_events.py`
- Atomic-write pattern from `src/core/model_registry._save_atomic`
- `CANONICAL_FEATURES` (for feature_dim comparison) from `src/features/feature_schema.py`
- Logging via `logging.getLogger("recovery")` (not `get_flow_logger` — "DATASET_BUILDER" is not in FLOWS dict)

---

## Failure Modes

| Failure | Response |
|---------|----------|
| `logs/` does not exist | Fail-fast, non-zero exit |
| No v2.0 runs found | Exit 0 with info message: "No v2.0 runs found; nothing to recover" |
| Malformed JSON in v2.0 opportunities.jsonl | Log warning, skip record, count in report |
| Reports dir not writable | Raise OSError; no partial files (atomic writes) |
| Opportunity scanner subprocess fails | Log error with stderr; continue with next instrument |
| Scanner outputs to wrong path | Stage-1 builder dry-run confirms discovery; logged in summary |

---

## Verification

```pwsh
# 1. Unit tests
python -m pytest tests/test_recover_v2_runs.py -v

# 2. Run recovery scan
python scripts/training/recover_v2_runs.py

# 3. Inspect reports
python -c "import json; r=json.load(open('reports/schema_recovery_report.json')); print(r['totals'])"
# Expected: {"v2_records_scanned": 305382, "recovered": 0, "unrecoverable": 305382}

python -c "import json; r=json.load(open('reports/recovery_acceptance_delta.json')); print(r['delta'])"
# Expected: {"net_new_accepted": 0, "acceptance_rate_delta_pct": 0.0}

# 4. Generate fresh v3.0 opportunity runs for 6 instruments
python scripts/training/scan_opportunities_yfinance.py

# 5. Re-run Stage-1 builder (new runs discovered in logs/)
python scripts/training/build_stage1_dataset.py --market-scope crypto

# 6. Verify acceptance improvement
python -c "import json; r=json.load(open('reports/integrity_report.json')); print(r['totals'])"
# Expected: accepted >> 203588 (now includes fresh v3.0 ETHUSDT + 5 new instruments)

# 7. Verify determinism preserved
python scripts/training/build_stage1_dataset.py --market-scope crypto
# Compare sha256 in two integrity reports — must match
```

---

## Self-Review Checklist (Recovery Phase)

- [ ] Recovery script never writes a synthesized or zero-filled feature value
- [ ] All 3 UNRECOVERABLE codes are distinct and machine-readable
- [ ] `recovered_v2_to_v3.jsonl` is created (empty) even when 0 records promoted — traceability
- [ ] `schema_recovery_report.json` includes per-instrument breakdown
- [ ] `recovery_acceptance_delta.json` stat-shift checks are skipped (correctly) when recovered=0
- [ ] All writes atomic (`.tmp` + `os.replace`)
- [ ] `scan_opportunities_yfinance.py` output path matches Stage-1 builder discovery glob (`logs/*/{RUN_ID}/opportunities.jsonl`)
- [ ] No subprocess call suppresses stderr — pipe it to log
- [ ] Tests cover idempotency (running twice = same result)


================================================================================
SOURCE_FILE: docs/plans/you-are-lead-runtime-typed-snowglobe.md
SOURCE_BYTES: 21549
PART: 10/10 FILE 6/6
================================================================================

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Agent-Readable Execution Memory Layer

## Context

The system has 20+ log writers producing rich JSONL event data across
`logs/run_{RUN_ID}/{instrument}/`, `logs/fusion_trades_*.jsonl`,
`logs/agent_audit.jsonl`, and ~15 other files. None of these payloads
carry a consistent `{instrument, run_id, trade_id}` identity envelope.
An agent traversing history must currently grep files or do recursive
directory scans to correlate a trade to its run and instrument.

This plan adds:
- A `_ctx` key additively injected into the two primary trade-lifecycle
  JSONL writers (no existing key touched)
- A supplemental `logs/index/` layer for O(1) index lookups
- `src/agent/log_query.py` for structured agent queries

No existing writers, folder structures, or import paths are changed.

---

## PHASE 1 — Current Logging Matrix (Inventory)

| File | Writer | Output | Format | Hot Loop | run_id | instrument | trade_id |
|---|---|---|---|---|---|---|---|
| src/utils/logging_config.py | FileHandler | logs/run_{ID}/{sym}/flow_*.log | text | Y | in path | in path | N |
| **src/utils/trade_logger.py** | open+json | logs/run_{ID}/{sym}/{sym}_fusion.jsonl | JSONL | Y | **MISSING** | Y (per-call) | Y |
| **src/journal/trade_logger.py** | open+json | logs/trade_journal.jsonl | JSONL | Y | **MISSING** | Y (symbol) | Y |
| src/agent/audit.py | open+json | logs/agent_audit.jsonl | JSONL | N | N | N | N |
| src/core/signal_audit.py | open+json | logs/signal_audit.jsonl | JSONL | Y (debug) | N | N | N |
| src/core/collector.py | flow logger | flow_collector.log | JSON via logger | Y | in path | in path | Y (as "id") |
| src/utils/integrity_events.py | open+json | logs/integrity_events.jsonl | JSONL | N | N | N | N |
| src/utils/engine_telemetry.py | path.open+json | logs/engine_telemetry.jsonl | JSONL | Y | N | Y | N |
| src/replay/replay_drift_governor.py | open+json | logs/drift_audit.jsonl | JSONL | N | N | Y (via env) | N |
| src/cognitive/cognitive_bus.py | path.open+json | logs/cognitive_telemetry.jsonl | JSONL | Y (async) | N | N | N |
| src/governance/promotion_manager.py | open+json | configs/promotion_log.jsonl | JSONL | N | N | N | N |
| src/expansion/expansion_engine.py | open+json | logs/expansion_trace.jsonl | JSONL | N | N | N | N |
| src/engines/live_engine.py | open+json | logs/live_alerts.jsonl | JSONL | Y | N | Y | N |
| src/config_layer/llm_inference_client.py | _append_jsonl | logs/llm_audit.jsonl | JSONL | Y | N | N | N |
| src/agent/findings_synthesizer.py | open+json | logs/agent_findings.jsonl | JSONL | N | Y (run_id) | N | N |
| src/runtime/backtest_bitnet.py | open+json | logs/backtest_decisions_{sym}_{ts}.jsonl | JSONL | Y | N | in filename | N |
| src/governance/orchestrator.py | delegated | logs/governance_audit.jsonl | JSONL | N | N | N | N |

### Issues identified

| Issue | Files |
|---|---|
| **Missing run_id in hot-path writers** | trade_logger.py (utils), journal/trade_logger.py |
| **EXIT records have no instrument** | src/utils/trade_logger.py log_exit() |
| **Schema fragmentation** | "symbol" vs "instrument" vs "id" vs "trade_id" across files |
| **Orphan log** | logs/backtest_decisions_{sym}_{ts}.jsonl — timestamp in filename, no stable path |
| **Collector "id" ≠ trade_id** | collector.py uses "id" not "trade_id" |
| **Duplicate LLM audit** | logs/llm_audit.jsonl AND logs/agent_llm_requests.jsonl |
| **No log_query.py** | src/agent/log_query.py does not exist |
| **No index layer** | logs/index/ does not exist |

---

## PHASE 2 — New File: `src/utils/log_identity.py`

**Purpose:** Pure, no-I/O helper that builds the `_ctx` envelope dict.
No side effects. Thread-safe. Zero runtime dependency.

```python
# src/utils/log_identity.py
from __future__ import annotations
from typing import Optional

def build_log_context(
    instrument: str,
    run_id: str,
    trade_id: Optional[str] = None,
    strategy: Optional[str] = None,
    phase: Optional[str] = None,
) -> dict:
    return {
        "instrument":     instrument,
        "run_id":         run_id,
        "trade_id":       trade_id,
        "strategy":       strategy,
        "phase":          phase,
        "schema_version": "v1",
    }
```

---

## PHASE 3 — Enhance Existing Writers (additive `_ctx` only)

### Scope decision

Only 2 files get `_ctx` in Phase 3 (primary trade-lifecycle JSONL):
- `src/utils/trade_logger.py` — the canonical ENTRY/EXIT/REJECT file
- `src/journal/trade_logger.py` — outcome-level trade journal

All other writers (collector, signal_audit, engine_telemetry, etc.) are
**deferred** — they lack one or more of the 3 identity fields at write
time or are not queried for trade lifecycle. Deferred writers are annotated
at the bottom of this plan.

---

### 3A. `src/utils/trade_logger.py`

**Exact changes (additive only):**

1. **New imports** (after existing imports at ~line 77):
   ```python
   from utils.log_identity import build_log_context
   from utils.logging_config import RUN_ID as _MODULE_RUN_ID
   ```

2. **`TradeLogger.__init__`** — add `run_id` param, store `_instrument`:
   ```python
   # BEFORE (line 88-96):
   def __init__(self, path: Path | str | None = None,
                instrument: str = "") -> None:
       if path is None:
           if instrument:
               path = Path(f"logs/fusion_trades_{instrument}.jsonl")
           else:
               path = DEFAULT_LOG_PATH
       self.path = Path(path)
       self.path.parent.mkdir(parents=True, exist_ok=True)

   # AFTER:
   def __init__(self, path: Path | str | None = None,
                instrument: str = "",
                run_id: str = "") -> None:
       if path is None:
           if instrument:
               path = Path(f"logs/fusion_trades_{instrument}.jsonl")
           else:
               path = DEFAULT_LOG_PATH
       self.path = Path(path)
       self.path.parent.mkdir(parents=True, exist_ok=True)
       self._instrument = instrument
       self._run_id = run_id or _MODULE_RUN_ID
       self._last_entry_offset: int = 0   # for trade index byte-seek
   ```
   All existing callers that don't pass `run_id` automatically fall back
   to the module-level `RUN_ID` singleton — zero breakage.

3. **`log_entry`** — capture offset before write, inject `_ctx` after
   record is built, before `_write()` (line 136):
   ```python
   # After record = {...} dict, before self._write(record):
   try:
       self._last_entry_offset = self.path.stat().st_size if self.path.exists() else 0
   except OSError:
       self._last_entry_offset = 0
   record["_ctx"] = build_log_context(
       instrument=instrument,   # per-call arg takes precedence
       run_id=self._run_id,
       trade_id=trade_id,
       phase="ENTRY",
   )
   self._write(record)
   ```

4. **`log_exit`** — inject `_ctx` after record dict, before `_write()` (line 161):
   ```python
   record["_ctx"] = build_log_context(
       instrument=self._instrument,   # from instance (set by backtest_v2)
       run_id=self._run_id,
       trade_id=trade_id,
       phase="EXIT",
   )
   self._write(record)
   ```
   Note: `self._instrument` will be non-empty after the backtest_v2.py
   change in Phase 3C. Legacy callers that don't pass `instrument` to
   `__init__` get `instrument=""` in EXIT `_ctx` — acceptable, ENTRY has it.

5. **`log_rejection`** — inject `_ctx` after record dict (line 186):
   ```python
   record["_ctx"] = build_log_context(
       instrument=instrument,   # per-call arg
       run_id=self._run_id,
       phase="REJECT",
   )
   self._write(record)
   ```

---

### 3B. `src/journal/trade_logger.py`

**Exact changes:**

1. **New imports** (after line 8):
   ```python
   from utils.log_identity import build_log_context
   from utils.logging_config import RUN_ID as _MODULE_RUN_ID
   ```

2. **`TradeLogger.__init__`** — add `run_id` (line 42):
   ```python
   def __init__(self, log_path: Optional[str] = None, run_id: str = "") -> None:
       self._path = Path(log_path) if log_path else _DEFAULT_LOG
       self._run_id = run_id or _MODULE_RUN_ID
   ```

3. **`TradeLogger.log()`** — replace `record.to_json()` write with a
   dict write that includes `_ctx` (lines 48-52). This is the minimal
   additive change; `load_all()` still works (reads raw dicts, `_ctx`
   is an extra key):
   ```python
   self._path.parent.mkdir(parents=True, exist_ok=True)
   try:
       _rec_dict = json.loads(record.to_json())   # get the dict form
       _rec_dict["_ctx"] = build_log_context(
           instrument=record.symbol,
           run_id=self._run_id,
           trade_id=record.trade_id,
           phase=record.result or "TRADE",
       )
       with open(self._path, "a", encoding="utf-8") as f:
           f.write(json.dumps(_rec_dict) + "\n")
   except Exception as exc:
       log.warning("TradeLogger: write failed: %s", exc)
   ```

---

### 3C. `src/agent/audit.py`

**Exact changes — optional `_ctx` only:**

Add one optional param `_ctx: Optional[dict] = None` to `write_step`
and `write_session_summary`. No callers change. No existing field touched.

```python
# write_step — add after error: Optional[str] = None,
_ctx: Optional[dict] = None,
# Inside, after record dict is built, before _append():
if _ctx is not None:
    record["_ctx"] = _ctx
```

Same pattern for `write_session_summary`.

---

## PHASE 3C — `src/runtime/backtest_v2.py` (line 1341)

Pass `instrument` and `run_id` to `_TradeLogger` constructor so
the instance has both fields for EXIT `_ctx` and index writes:

```python
# BEFORE (line 1341):
self._trade_logger = _TradeLogger(_run_log_dir / f"{bt_config.instrument}_fusion.jsonl")

# AFTER:
self._trade_logger = _TradeLogger(
    _run_log_dir / f"{bt_config.instrument}_fusion.jsonl",
    instrument=bt_config.instrument,
    run_id=_RUN_ID,
)
```

Then immediately after (still in `__init__`), add fail-open index writes:
```python
# Supplemental index writes — additive, never block the run
try:
    from utils.log_index_writer import write_run_index, write_instrument_index
    write_run_index(_RUN_ID, bt_config.instrument, str(_run_log_dir))
    write_instrument_index(_RUN_ID, bt_config.instrument, str(_run_log_dir))
except Exception as _idx_err:
    self.log.debug("Index write skipped (non-fatal): %s", _idx_err)
```

Also add trade index write inside `src/utils/trade_logger.py` `log_exit()`,
after `self._write(record)`:
```python
try:
    from utils.log_index_writer import write_trade_index
    write_trade_index(
        instrument=self._instrument,
        run_id=self._run_id,
        trade_id=trade_id,
        log_path=str(self.path),
        offset=self._last_entry_offset,
    )
except Exception:
    pass
```

---

## PHASE 4 — New File: `src/utils/log_index_writer.py`

**Purpose:** Fail-open append helpers that populate `logs/index/`.
Never raises. Never a source of truth.

```python
# src/utils/log_index_writer.py
import json
import time
from pathlib import Path

_INDEX_DIR             = Path("logs/index")
_RUN_INDEX_PATH        = _INDEX_DIR / "run_index.jsonl"
_INSTRUMENT_INDEX_PATH = _INDEX_DIR / "instrument_index.jsonl"
_TRADE_INDEX_PATH      = _INDEX_DIR / "trade_index.jsonl"


def _append_index(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


def write_run_index(run_id: str, instrument: str, log_dir: str) -> None:
    _append_index(_RUN_INDEX_PATH, {
        "run_id": run_id,
        "instrument": instrument,
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "log_dir": log_dir,
        "offset": 0,
    })


def write_instrument_index(run_id: str, instrument: str, log_dir: str) -> None:
    _append_index(_INSTRUMENT_INDEX_PATH, {
        "instrument": instrument,
        "run_id": run_id,
        "log_dir": log_dir,
        "trade_count": 0,
        "offset": 0,
    })


def write_trade_index(
    instrument: str, run_id: str, trade_id: str,
    log_path: str, offset: int = 0,
) -> None:
    _append_index(_TRADE_INDEX_PATH, {
        "instrument": instrument,
        "run_id": run_id,
        "trade_id": trade_id,
        "log_path": log_path,
        "offset": offset,
    })
```

### Index schemas

**`logs/index/run_index.jsonl`** — one line per run start:
```json
{"run_id": "20260523_120850", "instrument": "BTCUSDT", "start_ts": "2026-05-23T12:08:50Z", "log_dir": "logs/run_20260523_120850/BTCUSDT", "offset": 0}
```

**`logs/index/instrument_index.jsonl`** — one line per instrument per run:
```json
{"instrument": "BTCUSDT", "run_id": "20260523_120850", "log_dir": "logs/run_20260523_120850/BTCUSDT", "trade_count": 0, "offset": 0}
```

**`logs/index/trade_index.jsonl`** — one line per completed trade:
```json
{"instrument": "BTCUSDT", "run_id": "20260523_120850", "trade_id": "CRT-0001", "log_path": "logs/run_20260523_120850/BTCUSDT/BTCUSDT_fusion.jsonl", "offset": 12832}
```

---

## PHASE 5 — New File: `src/agent/log_query.py`

**API:**

```python
def get_run(run_id: str) -> dict | None
    # Index first: scan run_index.jsonl for matching run_id
    # Returns index record or None

def get_instrument(instrument: str, run_id: str | None = None) -> list[dict]
    # Index first: scan instrument_index.jsonl
    # Fallback: single-depth glob logs/run_*/{instrument}/{instrument}_fusion.jsonl
    # Returns list of index records

def get_trade(trade_id: str) -> dict | None
    # Index first: find trade in trade_index.jsonl → seek to offset in fusion JSONL
    # Fallback: one-level scan of logs/run_*/ without recursion
    # Returns ENTRY record dict (with _ctx if enhanced) or None

def query(
    instrument: str | None = None,
    run_id: str | None = None,
    trade_id: str | None = None,
    limit: int = 50,
) -> list[dict]
    # Hierarchy: trade_id → run_id → instrument → all
    # Returns ENTRY records sorted by timestamp desc, capped at limit
    # Never loads full file — streams line by line, stops at limit
```

**Internal rules:**
- `_iter_jsonl(path)` — generator, skips malformed lines, never raises
- `_iter_jsonl_from_offset(path, offset)` — seeks then streams; falls back to full scan on seek error
- `_scan_fusion_paths(instrument, run_id)` — single `glob("run_*")`, then one `iterdir()` inside — no recursion
- All public functions return `[]` or `None` on miss, never raise

---

## Exact Files

### New (3)
| File | Lines (est.) |
|---|---|
| `src/utils/log_identity.py` | ~25 |
| `src/utils/log_index_writer.py` | ~50 |
| `src/agent/log_query.py` | ~160 |

### Modified (4)
| File | Change | Risk |
|---|---|---|
| `src/utils/trade_logger.py` | `__init__` + 3 write methods + offset tracking | LOW |
| `src/journal/trade_logger.py` | `__init__` + `log()` write path | LOW |
| `src/agent/audit.py` | optional `_ctx` param in 2 methods | VERY LOW |
| `src/runtime/backtest_v2.py` | line 1341 + 3-line index write block | LOW |

---

## Hot-Loop Impact

| Writer | Frequency | Added work | Cost |
|---|---|---|---|
| `trade_logger.log_entry` | Per trade (not per candle) | 1× `os.stat()` + dict build | Negligible |
| `trade_logger.log_exit` | Per trade close | 1× `_append_index` (open+write) | Same as existing `_write` |
| `trade_logger.log_rejection` | Per rejected signal | dict build only | Negligible |
| `journal/trade_logger.log` | Per trade close | `json.loads()` + 1 extra key | Negligible |

The `_ctx` dict construction is 5 assignments — cheaper than any existing
dict comprehension in the record builders. No new file handles are held open.

---

## No-Op Migration Path

No migration needed. Changes are purely additive:
- `_ctx` is a new key; all existing readers use `dict.get()` or ignore extras
- `logs/index/` is new; no existing code reads it
- All new constructor params have defaults maintaining backward compat
- New `log_identity.py` / `log_index_writer.py` are never imported by
  existing code unless explicitly called
- `audit.py` `_ctx` param is keyword-only with `None` default

---

## Rollback Plan

If any enhancement causes a regression:

1. Remove `_ctx` inject lines from `log_entry`, `log_exit`, `log_rejection`
   in `src/utils/trade_logger.py` (3 lines)
2. Remove `_ctx` inject from `src/journal/trade_logger.py` `log()` (5 lines)
3. Revert line 1341 in `src/runtime/backtest_v2.py` to original one-arg form
4. Delete the 3-line index-write block in `backtest_v2.py`
5. `logs/index/` directory is inert — leave or delete, no code reads it
6. The 3 new `src/utils/log_identity.py`, `src/utils/log_index_writer.py`,
   `src/agent/log_query.py` files can remain (nothing imports them)

Total rollback: ~10 line reversions. Git diff is surgically clean.

---

## Schema Examples

### ENTRY record with `_ctx` (fusion JSONL):
```json
{
  "event": "ENTRY",
  "trade_id": "CRT-0001",
  "timestamp": "2026-05-23T12:09:14.000000",
  "instrument": "BTCUSDT",
  "direction": "LONG",
  "session": "LONDON",
  "regime": "EXPANSION",
  "features": {"retest_depth": 0.22, "body_ratio": 0.71},
  "fusion": {"final_score": 0.68, "llm_fired": true},
  "entry_price": 67540.0,
  "sl_price": 67340.0,
  "tp1_price": 67740.0,
  "tp2_price": 67940.0,
  "_ctx": {
    "instrument": "BTCUSDT",
    "run_id": "20260523_120850",
    "trade_id": "CRT-0001",
    "strategy": null,
    "phase": "ENTRY",
    "schema_version": "v1"
  }
}
```

### EXIT record with `_ctx`:
```json
{
  "event": "EXIT",
  "trade_id": "CRT-0001",
  "timestamp": "2026-05-23T12:27:00.000000",
  "exit_reason": "TP1",
  "pnl_rr_net": 1.95,
  "win": true,
  "duration_candles": 18,
  "_ctx": {
    "instrument": "BTCUSDT",
    "run_id": "20260523_120850",
    "trade_id": "CRT-0001",
    "strategy": null,
    "phase": "EXIT",
    "schema_version": "v1"
  }
}
```

---

## Ingestion Examples

```python
from agent.log_query import get_run, get_instrument, get_trade, query

# Resolve a run
run = get_run("20260523_120850")
# → {"run_id": "20260523_120850", "instrument": "BTCUSDT", "log_dir": "...", ...}

# All runs for one instrument
runs = get_instrument("BTCUSDT")

# Look up a single trade
trade = get_trade("CRT-0001")
# → ENTRY record with _ctx envelope

# Latest 10 trades for BTCUSDT
trades = query(instrument="BTCUSDT", limit=10)

# All trades in a specific run
trades = query(run_id="20260523_120850", limit=100)

# Lifecycle join (agent side):
entry = get_trade("CRT-0001")
# then stream fusion JSONL for matching EXIT:
#   filter event=="EXIT" and trade_id==entry["trade_id"]
```

---

## Self-Review

| Rule | Compliant? |
|---|---|
| Did I replace anything? | No — additive only |
| Did I move folders? | No |
| Did I create duplicate truth? | No — index is supplemental, fusion JSONL is canonical |
| Did I introduce runtime dependency? | No — log_identity is a pure function, log_index_writer is fail-open |
| Can agents distinguish coin→run→trade→replay→training via metadata not folders? | **Yes** — `_ctx.instrument` / `_ctx.run_id` / `_ctx.trade_id` are in every ENTRY/EXIT record; index provides O(1) lookup |

---

## Deferred (out of scope for this plan)

| Writer | Reason for deferral |
|---|---|
| src/core/collector.py | Hot loop; `run_id` not in call signature — invasive change |
| src/core/signal_audit.py | Debug-mode only; low agent query value |
| src/utils/engine_telemetry.py | Lacks trade_id; not queried for trade lifecycle |
| src/cognitive/cognitive_bus.py | Async queue; has parent_event_id chain already |
| src/agent/modes/ | New `log_query` tool registrations — separate PR |
| src/governance/promotion_manager.py | Has no trade_id; governance-scoped only |

---

## Verification

```bash
# 1. Unit test log_identity
python -c "
from src.utils.log_identity import build_log_context
ctx = build_log_context('BTCUSDT', '20260523_120850', 'CRT-0001', 'S1', 'ENTRY')
assert ctx['schema_version'] == 'v1'
assert ctx['instrument'] == 'BTCUSDT'
print('log_identity OK')
"

# 2. Unit test log_index_writer
python -c "
from src.utils.log_index_writer import write_run_index, write_trade_index
write_run_index('TEST_RUN', 'BTCUSDT', 'logs/run_TEST_RUN/BTCUSDT')
import json; line = open('logs/index/run_index.jsonl').readlines()[-1]
assert json.loads(line)['run_id'] == 'TEST_RUN'
print('log_index_writer OK')
"

# 3. Backtest integration — verify _ctx present in fusion JSONL
python src/runtime/backtest_v2.py --instrument BTCUSDT --csv data/BTCUSDT_M15.csv
python -c "
import json, glob
files = glob.glob('logs/run_*/**/BTCUSDT_fusion.jsonl', recursive=False)
# check latest
for line in open(files[-1]):
    rec = json.loads(line)
    if rec.get('event') == 'ENTRY':
        assert '_ctx' in rec, 'missing _ctx'
        assert rec['_ctx']['run_id'], 'missing run_id'
        assert rec['_ctx']['trade_id'] == rec['trade_id']
        print('_ctx OK:', rec['_ctx'])
        break
"

# 4. Test log_query API
python -c "
from src.agent.log_query import get_run, get_instrument, get_trade, query
trades = query(instrument='BTCUSDT', limit=5)
assert all('_ctx' in t for t in trades)
print(f'query OK: {len(trades)} trades returned')
"

# 5. Backward-compat: old callers without run_id
python -c "
from src.utils.trade_logger import TradeLogger
tl = TradeLogger()     # no run_id
assert tl._run_id      # falls back to module-level RUN_ID
print('backward compat OK')
"
```
