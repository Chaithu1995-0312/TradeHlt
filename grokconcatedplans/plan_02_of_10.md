# Concatenated session plans — part 2 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `bitnet-is-the-active-adaptive-ritchie.md` (16247 bytes)
2. `claude-architecture-migration-eager-wreath.md` (17693 bytes)
3. `claude-go-thrugh-docs-twinkling-finch.md` (7681 bytes)
4. `claude-you-have-full-fuzzy-bonbon.md` (56015 bytes)
5. `context-current-tradenet-is-jazzy-lemur.md` (16187 bytes)
6. `crt-127-0-0-1-get-runs-q-cheeky-blum.md` (4423 bytes)
7. `crt-engine-20260509-005424-is-empty-chec-parsed-yeti.md` (6238 bytes)


================================================================================
SOURCE_FILE: docs/plans/bitnet-is-the-active-adaptive-ritchie.md
SOURCE_BYTES: 16247
PART: 2/10 FILE 1/7
================================================================================

> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# BitNet Adaptive Threshold

> **Status: FROZEN (2026-06-03) — per the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (BitNet V2 adaptive threshold = FROZEN; evidence F-004).** The BitNet v1 gate is live at the hardcoded `0.55` (`crt_engine_v2.py:1800`); the adaptive infrastructure is unused. Retained for replay, **not** active work. Reopen only when enough `bitnet_score_at_entry` outcomes accrue to fit per-instrument/per-regime thresholds **and** the adaptive threshold beats the static gate on net rr — plus a SESSION LOG entry per `CLAUDE.md §6.2`.

## Context

`BitNetRunner` uses a hardcoded `0.5` threshold at `src/bitnet/bitnet_runner.py:130`. No per-instrument adaptation, no config key, no learning from outcomes. Additionally, `bitnet_score_at_entry` is not persisted on `TradeRecord` — verified against `src/runtime/backtest_v2.py:200` and the actual CSV header at `results/portfolio_raw/EURUSD/run_20260511_011915_EURUSD/EURUSD_trades.csv` (70 columns, zero `bitnet_*`).

This patch has three sequential parts:
1. Wire `bitnet_score_at_entry` onto `TradeRecord` so closed trades carry the score that led to their approval.
2. Replace the hardcoded threshold with a per-instrument per-regime lookup, sourced from a managed JSON file.
3. Build a threshold adapter that fits against the accumulated labelled history and writes calibrated thresholds back.

**Dependency order — do not skip steps.** Steps 1 and 2 can ship together. Step 3 requires N closed trades with `bitnet_score_at_entry` populated — run at least one full backtest after Steps 1+2 before implementing Step 3.

---

## Step 1 — Wire `bitnet_score_at_entry` onto TradeRecord

**Files:** `src/runtime/backtest_v2.py`, `src/runtime/live_engine_hook.py`

**`src/runtime/backtest_v2.py:200` — add two fields to `TradeRecord` dataclass:**

```python
bitnet_score_at_entry:    float = 0.0   # BitNet confidence score at approval time
bitnet_decision_at_entry: str   = ""    # "ACCEPT" | "REJECT" | "" (not evaluated)
```

Both fields default to safe values — old records without them load cleanly via the existing `from_dict` filtering pattern.

**Populate at approval time** — find the site in `BacktestRunner` where `BitNetRunner.predict()` is called (or `bitnet_score()` helper at `src/config_layer/crt_engine_v2.py:1030,1096`). At that call site, capture the result dict and write both fields into the `TradeRecord` before it is appended to the trade list:

```python
bitnet_result = bitnet_runner.predict(features)
trade.bitnet_score_at_entry    = bitnet_result.get("score", 0.0)
trade.bitnet_decision_at_entry = bitnet_result.get("decision", "")
```

**Confirm the CSV export** includes both new columns — `BacktestRunner` writes `TradeRecord` fields to CSV. The two new fields should appear automatically if the CSV writer uses `dataclasses.asdict()`. Verify the column appears in `*_trades.csv` after the first post-patch backtest run.

**Live path:** `src/runtime/live_engine_hook.py` — same pattern. At the point where the live engine calls BitNet for an approval decision, attach both fields to the alert payload (same shape as the `features` snapshot wiring from Fix 4).

---

## Step 2 — Replace hardcoded threshold with per-instrument per-regime lookup

**Files:** `src/bitnet/bitnet_runner.py`, `src/bitnet/bitnet_thresholds.json` (new), both prod configs

**`src/bitnet/bitnet_runner.py` — extend constructor and threshold lookup:**

Constructor currently takes only `model_path`. Extend:

```python
def __init__(
    self,
    model_path: str | Path,
    *,
    instrument: str = "UNKNOWN",
    config:     dict | None = None,
):
    # ... existing model load ...
    self._instrument  = instrument
    self._config      = config or {}
    self._thresholds  = self._load_thresholds()
```

Add `_load_thresholds()`:

```python
def _load_thresholds(self) -> dict:
    """Load per-instrument per-regime thresholds from bitnet_thresholds.json.
    Falls back to hardcoded 0.5 per instrument if file absent or parse fails."""
    path = Path(self._config.get(
        "bitnet_thresholds_path",
        "src/bitnet/bitnet_thresholds.json"
    ))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "BITNET_THRESHOLD_LOAD_FAILED", "WARNING", "bitnet_runner",
            {"path": str(path), "error": str(exc),
             "fallback": "hardcoded 0.5 for all instruments"}
        )
        return {}
```

Add `_threshold_for(regime)`:

```python
def _threshold_for(self, regime: str = "UNKNOWN") -> float:
    """Per-instrument per-regime threshold with fallback chain:
       instrument+regime → instrument+UNKNOWN → global → 0.5"""
    inst_block = self._thresholds.get(self._instrument, {})
    # Try exact regime match
    val = inst_block.get(regime.upper())
    if val is not None:
        return float(val)
    # Try instrument-level default
    val = inst_block.get("DEFAULT")
    if val is not None:
        return float(val)
    # Global default
    val = self._thresholds.get("__default__")
    if val is not None:
        return float(val)
    # Hardcoded floor — never silent
    return 0.5
```

**Replace `src/bitnet/bitnet_runner.py:130`:**

```python
# Before:
decision = "ACCEPT" if score > 0.5 else "REJECT"

# After:
regime    = features.get("_regime", "UNKNOWN")   # injected by caller if available
threshold = self._threshold_for(regime)
decision  = "ACCEPT" if score > threshold else "REJECT"
```

Note: `features.get("_regime")` — the `_` prefix marks it as metadata, not a canonical feature. It is not in `CANONICAL_FEATURES` and is stripped before the feature vector is assembled. The caller injects it alongside the feature dict. If absent, fallback is `"UNKNOWN"` → uses the instrument-level DEFAULT threshold.

**`src/bitnet/bitnet_thresholds.json` — initial file:**

```json
{
    "__default__": 0.5,
    "__schema_version__": "bitnet_thresholds_v1",
    "__note__": "Per-instrument per-regime acceptance thresholds. Managed by BitNetThresholdAdapter.",
    "ETHUSDT": {
        "DEFAULT":  0.5,
        "TRENDING": 0.5,
        "RANGING":  0.5,
        "UNKNOWN":  0.5
    },
    "EURUSD": {
        "DEFAULT":  0.5,
        "TRENDING": 0.5,
        "RANGING":  0.5,
        "UNKNOWN":  0.5
    }
}
```

All values start at `0.5` — identical to current hardcoded behaviour. Zero behavioural change until the adapter calibrates them. This is deliberate.

**Add to both prod configs under `bitnet` section:**

```json
"bitnet": {
    "bitnet_thresholds_path": "src/bitnet/bitnet_thresholds.json"
}
```

Re-hash both configs after editing (`python scripts/maintenance/_compute_hash.py`).

---

## Step 3 — Threshold adapter (run AFTER Step 1 produces labelled data)

**New file: `src/bitnet/bitnet_threshold_adapter.py`**

The adapter reads closed trade records where `bitnet_score_at_entry` is populated, fits a calibrated threshold per instrument per regime, and writes updated values back to `bitnet_thresholds.json`.

**Core logic:**

```python
def calibrate(
    self,
    instrument: str,
    regime: str,
    records: list[dict],
    *,
    target_precision: float = 0.60,   # min fraction of ACCEPTs that reach TP1
    min_samples: int = 50,
) -> tuple[float, dict]:
    """
    Find the threshold T such that:
      precision(score > T) >= target_precision
    where precision = fraction of trades with bitnet_score > T that reached TP1.

    Returns (threshold, diagnostics_dict).
    Falls back to 0.5 if insufficient samples.
    """
```

Algorithm — threshold sweep:

```python
candidates = np.arange(0.30, 0.85, 0.02)   # sweep 0.30 → 0.84 in steps of 0.02
best_threshold = 0.5
best_precision = 0.0

for t in candidates:
    approved = [r for r in records
                if r.get("bitnet_score_at_entry", 0.0) > t]
    if len(approved) < min_samples:
        continue
    tp1_hits = sum(
        1 for r in approved
        if str(r.get("exit_reason", "")).upper() in ("TP1", "TP2", "SL-BE")
    )
    precision = tp1_hits / len(approved)
    # Take the lowest threshold that meets the precision target
    # (maximizes trade count while maintaining quality floor)
    if precision >= target_precision and t < best_threshold:
        best_threshold = t
        best_precision = precision

return best_threshold, {
    "instrument": instrument,
    "regime": regime,
    "n_records": len(records),
    "n_approved_at_threshold": len([
        r for r in records
        if r.get("bitnet_score_at_entry", 0.0) > best_threshold
    ]),
    "precision_at_threshold": best_precision,
    "target_precision": target_precision,
}
```

**Writer — updates `bitnet_thresholds.json` atomically:**

```python
def write_threshold(
    self,
    instrument: str,
    regime: str,
    threshold: float,
    diagnostics: dict,
) -> None:
    thresholds = self._load()
    thresholds.setdefault(instrument, {})
    thresholds[instrument][regime.upper()] = round(threshold, 4)
    # Emit before write so audit trail exists even if write fails
    from src.utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "BITNET_THRESHOLD_UPDATED", "INFO", "bitnet_threshold_adapter",
        {"instrument": instrument, "regime": regime,
         "new_threshold": threshold, **diagnostics}
    )
    self._save_atomic(thresholds)
```

**CLI entry point** — `scripts/training/calibrate_bitnet_thresholds.py`:

```bash
python scripts/training/calibrate_bitnet_thresholds.py \
    --instrument ETHUSDT \
    --regime TRENDING \
    --trades-csv results/portfolio_raw/ETHUSDT/run_*/ETHUSDT_trades.csv \
    --target-precision 0.60 \
    --min-samples 50
```

**Wire into `auto_train_from_opportunities.py`** — after `_maybe_promote()`, add an optional `_calibrate_bitnet_thresholds(instrument)` call gated by `--calibrate-bitnet` flag. Same pattern as `--refresh-zones`.

---

## What does NOT change

- `BitNetRunner.predict()` return shape — `{"score", "decision", "error"}` unchanged
- All existing callers of `BitNetRunner` — `instrument=` is kw-only with default `"UNKNOWN"`, existing construction sites keep working
- `CANONICAL_FEATURES` — `_regime` is never added to the canonical list
- `src/bitnet/model_contract.py` — threshold file is separate from model envelope, no contract change
- The `0.5` floor — it is always the last fallback, never removed

---

## Critical files

- `src/bitnet/bitnet_runner.py:130` — hardcoded threshold to replace
- `src/runtime/backtest_v2.py:200` — `TradeRecord` dataclass (add two fields)
- `src/runtime/live_engine_hook.py` — live path approval site (mirror the wiring)
- `src/config_layer/crt_engine_v2.py:1030,1096` — existing `bitnet_score()` call sites for reference
- `src/runtime/backtest_bitnet.py:244-247,336,356-357` — reference impl of BitNet-gated decision flow
- `src/utils/integrity_events.py` — `emit_integrity_event()` for `BITNET_THRESHOLD_LOAD_FAILED` and `BITNET_THRESHOLD_UPDATED`
- `configs/production/v1_multi_2026_03.json`, `configs/production/v2_multi_2026_04 - deepdeektry.json` — add `bitnet.bitnet_thresholds_path`, re-hash
- `src/bitnet/bitnet_thresholds.json` — new file, initial all-0.5 values
- `src/bitnet/bitnet_threshold_adapter.py` — new file (Step 3)
- `scripts/training/calibrate_bitnet_thresholds.py` — new CLI entry (Step 3)

---

## Verification

```bash
# Step 1 — confirm bitnet_score_at_entry appears in CSV after backtest
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 2000
python -c "
import pandas as pd, glob
f = sorted(glob.glob('results/portfolio_raw/ETHUSDT/**/*_trades.csv', recursive=True))[-1]
df = pd.read_csv(f)
assert 'bitnet_score_at_entry' in df.columns, f'missing column. cols: {list(df.columns)}'
print('PASS — bitnet_score_at_entry present,', len(df), 'trades')
print(df[['bitnet_score_at_entry','bitnet_decision_at_entry','exit_reason']].head())
"

# Step 2 — confirm threshold lookup works and fallback chain fires
python -c "
from src.bitnet.bitnet_runner import BitNetRunner
runner = BitNetRunner('models/bitnet_export.json', instrument='ETHUSDT')
t_trend = runner._threshold_for('TRENDING')
t_unk   = runner._threshold_for('UNKNOWN')
t_fake  = runner._threshold_for('NONEXISTENT')
print(f'TRENDING={t_trend} UNKNOWN={t_unk} NONEXISTENT={t_fake}')
assert t_fake == 0.5, 'fallback chain broken'
print('PASS')
"

# Step 3 — calibrator produces valid threshold from synthetic records
python -c "
import random
from src.bitnet.bitnet_threshold_adapter import BitNetThresholdAdapter
records = []
for _ in range(200):
    score = random.uniform(0.3, 0.9)
    exit_reason = 'TP1' if score > 0.55 and random.random() > 0.3 else 'SL'
    records.append({'bitnet_score_at_entry': score, 'exit_reason': exit_reason})
adapter = BitNetThresholdAdapter()
threshold, diag = adapter.calibrate('ETHUSDT', 'TRENDING', records,
                                     target_precision=0.60, min_samples=20)
print(f'Calibrated threshold: {threshold:.4f}')
print(f'Diagnostics: {diag}')
assert 0.30 <= threshold <= 0.85
print('PASS')
"

# Step 4 — confirm integrity event emitted on threshold update
python -c "
import json, pathlib
from src.bitnet.bitnet_threshold_adapter import BitNetThresholdAdapter
adapter = BitNetThresholdAdapter()
adapter.write_threshold('ETHUSDT', 'TRENDING', 0.62, {'n_records': 200})
events = [json.loads(l) for l in
          pathlib.Path('logs/integrity_events.jsonl').read_text().splitlines()[-10:]]
kinds  = [e.get('event') for e in events]
assert 'BITNET_THRESHOLD_UPDATED' in kinds, kinds
print('PASS — event fired:', [e for e in events if e.get('event') == 'BITNET_THRESHOLD_UPDATED'][-1])
"
```

---

## Success criteria

- `bitnet_score_at_entry` and `bitnet_decision_at_entry` appear in `*_trades.csv` after first post-patch backtest
- Threshold lookup follows fallback chain: regime → DEFAULT → `__default__` → 0.5
- All existing construction sites work unchanged (kw-only `instrument=` with UNKNOWN default)
- Calibrator produces threshold in [0.30, 0.85] from synthetic labelled records
- `BITNET_THRESHOLD_UPDATED` integrity event fires on every threshold write
- Zero behavioural change until calibration runs (all thresholds start at 0.5)

---

## Sequencing

Ship Steps 1 and 2 together. Run one full backtest to accumulate labelled data. Then implement and verify Step 3 against real scores.

---

## Hotfix — UnicodeDecodeError on Windows when loading production config

### Context
My earlier config-rewrite script used `json.dump(..., ensure_ascii=False)`, which converted any pre-existing Unicode escape sequences (`\uXXXX`) in the JSON into actual UTF-8 bytes. `production_config.py` opens config files with `with open(path)` — no explicit encoding — so Python falls back to the Windows system codec (cp1252). cp1252 cannot decode the UTF-8 byte `0x9d` at position 1983, causing a `UnicodeDecodeError` at runtime.

### Root cause
Three `with open(...)` calls in `src/config_layer/production_config.py` lack `encoding='utf-8'`:
- Line 183 — `get_prod_metadata()` → reads full registry dict
- Line 223 — `load_prod_config_from_registry()` → the specific line in the traceback
- Line 326 — `get_prod_section()` → reads a named section

Line 362 already has `encoding="utf-8"` (correctly fixed in an earlier pass).

### Fix
Add `encoding="utf-8"` to the three bare `with open(registry_path)` calls.

```python
# Line 183:
with open(registry_path, encoding="utf-8") as f:

# Line 223:
with open(registry_path, encoding="utf-8") as f:

# Line 326:
with open(registry_path, encoding="utf-8") as f:
```

### Files
- `src/config_layer/production_config.py` — lines 183, 223, 326 (3 surgical edits)

### Verification
```bash
python src/runtime/backtest_v2.py --csv data/ETHUSDT_M15.csv --instrument ETHUSDT --output results/
# Should load config cleanly — no UnicodeDecodeError
```


================================================================================
SOURCE_FILE: docs/plans/claude-architecture-migration-eager-wreath.md
SOURCE_BYTES: 17693
PART: 2/10 FILE 2/7
================================================================================

# Architecture Migration — Event-Driven, LLM-Context-Economy Governance

> Created: 2026-05-28 · Updated: 2026-05-29 · Milestone: Trd-M0

## Context

Migrate Tradelatest toward an event-driven, replay-governed, explainable,
advisory-LLM, microservice-compatible architecture — **MAP before changing**.
Profitability is *not* the objective. Priority order: replay correctness >
explainability > telemetry continuity > advisory-AI > (structure validity ≠
execution validity).

Three exploration findings anchor the work:
1. **Migration is already underway.** `src/events/event_fabric.py` defines a canonical
   envelope (`event_id`, monotonic `generation`, `event_type`, `instrument`, `source`,
   ISO ts, `schema_hash`, `parent_event_id`, `payload`) with declared invariants. A
   `CognitiveBus`, `ReplayDriftGovernor`, and telemetry emitters already emit 5
   enveloped types. **Consolidate on this fabric — never fork it.**
2. **Decision spine is already microservice-clean** (config injected, structured dict
   returns): `EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 →
   UltronRiskGate`. The coupling lives in the *orchestration* layer.
3. **LLM authority is already isolated** — no LLM on the replay hot path; fusion LLM is
   an uncertainty-zone tie-breaker; agent has path-guard + `y/N` confirm; promotion
   requires an `APPROVE` ValidationReport.

## North Star — Why these docs exist (LLM context economy)

The end state is an **LLM-event-microservices** architecture. Microservices beat "one
LLM holding all context" for one reason: **context economy**. Separating the system
into services — each with documented **ins / internal flow / outs** — lets a future
LLM load only the *one service* it's working on, never the whole codebase. Therefore:

- **Every doc is a self-contained, loadable context unit** (ins → flow → outs),
  readable without loading the code.
- `service-boundary-map.md` + the per-service human-language docs are the *primary*
  LLM context units.
- Telemetry is **curated into per-episode "LLM logs"** so context does not grow
  unbounded as logs accumulate — the LLM reads compact causal narratives, not the raw
  firehose.
- **Every application flow is captured/documented** so the LLM always has a map.

This north star ranks above refactor speed.

## The Five Governance Questions (gate for every recommendation)

1. Does replay remain deterministic?
2. Does telemetry remain comparable across runs?
3. Can this state be audited later?
4. Can an LLM reason about this event?
5. Is execution authority still isolated?

Encoded as a pre-merge checklist header in `assistant_project.md`.

## Decisions (confirmed)

- **Scope this pass:** six documents + **Trd-M1** (telemetry normalization, including the
  per-episode LLM log) + **Workstream A** (plan persistence). Trd-M2–Trd-M5 are roadmap only.
- **New-doc location:** `docs/architecture/`; `assistant_project.md` stays at repo root
  (existing canonical doctrine + SESSION LOG ritual, CLAUDE.md §6).
- **Per-service human-language docs:** `docs/architecture/services/<svc>.md` — one per
  service. Template defined now; individual files authored **on demand ("on ask")**.
- **LLM log:** a **per-episode SUMMARY** record — the full enveloped event stream rolled
  up into one record per CRT episode. Full firehose telemetry retained separately for
  audit.
- **First code seam:** telemetry normalization (Trd-M1).

## Workstream A — Persist session plans to `docs/implementation_plan/` (do first)

**Why:** Plan-mode files write to the *global* `~/.claude/plans/` (this plan lives at
`C:\Users\Hi\.claude\plans\claude-architecture-migration-eager-wreath.md`), shared
across projects and easy to lose. User wants every session's plan version-controlled.

- **A1 — Capture now.** Create `docs/implementation_plan/` and copy this plan into it.
- **A2 — Automate via `PostToolUse` hook (built with the `update-config` skill, which
  is authoritative for exact schema).** Fires on the `Write` tool; copies the file into
  `docs/implementation_plan/` only when (a) `file_path` is under `~/.claude/plans/` and
  (b) the hook `cwd`/`CLAUDE_PROJECT_DIR` is `D:\Tradelatest` (guard against other
  projects' plans). Notes: `ExitPlanMode` is *not* a hook event; `Write` passes
  `file_path` in `tool_input`; Windows runs PowerShell — use an `args` array + a stdin
  wrapper that reads the hook JSON, checks `cwd`, then `Copy-Item`. Place in
  **project** settings (`D:\Tradelatest\.claude\settings.json`).
- **A3 — Verify:** writing a throwaway plan lands in `docs/implementation_plan/`;
  writing a file *outside* the plans dir does not trigger a copy.

## Deliverables — Six Documents (in `docs/architecture/`, except assistant_project.md)

Authored from exploration evidence with concrete `file:line` citations. Each is a
standalone LLM context unit.

1. **`codebase-state-map.md`** — package tree + one-line role per module; decision-spine
   trace (class/method/file:line); hidden-coupling inventory (Tier 1–3 blockers:
   module-level config loads `llm_inference_client.py:82`/`config_validator.py:78`/all
   `strategies/S01–S10`; engine↔`core.model_registry` `ml_gaussian_engine.py:53`;
   upward governance→runtime `portfolio_validation.py:28`,`config_validator.py:146`;
   `live_engine_hook.py:85–96` singletons; hardcoded paths `ultron_risk_gate.py:44`).
   Per layer: behavior · hidden coupling · replay risk · missing telemetry · event
   boundary · microservice seam.
2. **`event-taxonomy.md`** — the 9 `EventType` members (`event_fabric.py:56–65`, which
   are emitted vs declared-only); 7 `CRTState` transitions (`crt_engine_v2.py:52–60`) +
   legal-transition graph; **enveloped vs non-enveloped split** (non-enveloped:
   `fusion_trades.jsonl` `trade_logger.py:121/153/178`, `sweep_trace.jsonl`,
   `integrity_events.jsonl`); full JSONL inventory; CRT lifecycle + **episode boundary**
   definition (feeds the LLM log); Mermaid state diagram.
3. **`service-boundary-map.md`** (keystone for context economy) — candidate services
   (Feature/Ingestion, Scoring, Decision Spine, Execution/Risk, Governance, Replay,
   Telemetry/Bus, LLM Advisory, Agent/Control-Plane). **Per service: inputs, internal
   flow, outputs (the LLM-loadable contract)**, current crossings, blockers, effort
   tier. Dependency-direction doctrine (governance/analytics must not import
   `runtime.backtest_v2` — invert via abstract interface). Mermaid dependency map.
4. **`replay-governance.md`** — comparability contract (same CSV + `BacktestConfig`
   incl. `slippage_seed` + `PROD_VERSION`); determinism guarantees (seeded slippage
   `backtest_v2.py:379`, timestamp-keyed feature lookup `:1620–1621`, `.shift(1)` lag);
   replay-risk register (`FeaturePipeline` `center=True` `feature_pipeline.py:341`
   live-unsafe; `datetime.now()` metadata-only; `schema_hash` passive/audit-only); no
   lookahead, deterministic seeds, env timestamps excluded from comparison.
5. **`llm-governance-layer.md`** — isolation evidence (fusion tie-breaker, fail-open
   neutral, agent path-guard `executor.py:27–31`, promotion `APPROVE`
   `promotion_manager.py:138–145`); doctrine (advisory, never execution authority);
   hardening (`GOVERNANCE_MODE` flag, decision-path assertions, `CIRCUIT_OPEN`
   monitoring-only); LLM advisory-call event contract (every call emits an enveloped,
   replayable, comparable event).
6. **`assistant_project.md`** (root, append) — doctrine header: the five governance
   questions as a pre-merge checklist, the priority ordering, "consolidate on
   `event_fabric`," and the migration-sequencing index. Preserves the SESSION LOG ritual.

## Deliverable — Per-service human-language docs (template + one exemplar)

`docs/architecture/services/<svc>.md`, one per service, written in plain English so an
LLM (or human) can load a single service's context without the code. **Template:**
Purpose (1 line) · Inputs (data + contracts) · Internal flow (happy path + key
branches, prose) · Outputs (data + contracts) · Events emitted · Replay notes ·
Upstream/downstream services. This pass: define the template + write **one exemplar**
(the Decision Spine) to validate it. Remaining services authored on demand.

## Migration Sequencing (surgical, reversible)

- **Trd-M0** ✅ COMPLETE — Map & doctrine (the six docs + service-doc template/exemplar). No behavior change.
- **Trd-M1** ✅ COMPLETE (2026-05-29) — Telemetry normalization + **per-episode LLM log**.
- **Trd-M2** ✅ COMPLETE (2026-05-29) — Event extraction (emit `CRTState` transitions + declared-silent EventTypes).
- **Trd-M3** ✅ COMPLETE (2026-06-01) — Orchestration de-coupling: `live_engine_hook`
  singletons → injectable `LiveEngineContext`; `config_validator` module-level config load
  deferred to a lazy cached `_gates()` accessor (+ PEP 562 `__getattr__` for back-compat).
- **Trd-M4** ✅ COMPLETE (2026-06-01) — Dependency inversion: `core/backtest_port.py`
  (`BacktestPort`/`BacktestResult`/`BacktestFactory` Protocols); `portfolio_validation` +
  `config_validator` build the runner via the injectable factory (no module-level
  governance→runtime import); monkey-patch of `BacktestRunner.run` removed.
- **Trd-M5** ✅ COMPLETE (2026-06-01) — LLM-layer hardening: `GOVERNANCE_MODE`
  (`core/governance_mode.py`, strict/advisory), decision-path isolation assertions
  (fusion `evaluate()` + `UltronRiskGate.evaluate()`), `LLM_ADVISORY` enveloped advisory
  event. **Follow-up:** the LLM-client import-time config deferral was spun out (fragile
  cross-module refactor touching default-arg snapshots in already-fragile connectivity-test
  modules) — see plan `trd-m0-m5-tender-bentley.md §5.2b`.
- **Trd-M6** 🅿️ PARKED — Scenario-Aware Decisioning (first *capability* milestone; Trd-M0–Trd-M5 are
  all infrastructure and add no new decision capability). Definition + entry gate below.

Each step is scored pass/fail against the five governance questions.

## Trd-M6 🅿️ PARKED (decided 2026-06-01) — Scenario-Aware Decisioning

> Two-track context: this is **Trd-M6** (trading track), distinct from **Gov-M6** (governance track).
> See [`docs/architecture/roadmap.md`](../architecture/roadmap.md). Trd-M0–Trd-M5 make the
> "should we trade?" engine clean/replayable but add **zero new capability**; Trd-M6 is the
> first milestone that adds engine capability.

**What it is (reframed from "Scenario Intelligence"):** make every accepted signal
*forward-conditional* — it carries a small **enumerated, deterministic** scenario set
(continuation · sweep-trap · invalidation) with explicit invalidation/confirmation
conditions, **consumed at two boundaries that already exist**: `UltronRiskGate`
(probability-weighted sizing) and the in-trade management surface (dynamic invalidation
exit, replacing the static bracket + breakeven rule at `runtime/backtest_v2.py:2059-2094`).
The orphaned `src/regime/market_state_cluster_engine.py` (already emits
`BREAKOUT_CONTINUATION` / `RANGE_TRAP` / `VOLATILE_REVERSAL` / `trap_probability` /
`compression_score`, currently unwired) becomes the scenario-*prior* input rather than
dead code.

**Explicitly NOT Trd-M6:** a learned probabilistic path-tree / Monte-Carlo over futures with
expected-RR-per-scenario. Deferred to Trd-M7 — it collides with the #1 priority (`replay
correctness`) and the doctrine (LLM is a tie-breaker, **not** a hot-path dependency;
no-lookahead in replay). The deterministic enumerable set respects all three; a learned
distribution does not.

**Why the real gap is a consumer, not a forecaster:** scenario-flavored signal already
exists unconsumed (the orphaned regime engine proves it). A richer distribution layered
on a static-bracket engine produces *inert telemetry*, not edge. Trd-M6 builds the consumer.

**Doctrinal constraints (the five governance questions):** deterministic replay
(cluster/rule-based scoring, byte-identical across runs); no-lookahead (scenarios scored
only from candles ≤ now; invalidation is a forward *rule* evaluated as candles arrive);
LLM stays advisory; **ship measure-only first** (additive scenario telemetry, no gating)
per the proven Phase-6 ROI pattern, then connect a consumer, then gate.

**Entry gate — BOTH must hold before Trd-M6 leaves "parked":**
1. **Infra:** trading-track Trd-M3, Trd-M4, Trd-M5 complete (the foundation Trd-M6 consumes). *Today only
   Trd-M0/Trd-M1/Trd-M2 are done.*
2. **Empirical floor:** the throughput/validation gap is closed — Phase 5a (threshold
   sweep) + Phase 6c (session-config sweep) land, and the engine clears a
   minimum-trade-count + stable-PF floor (exact threshold = operator's call; proposed: a
   sweep configuration producing a materially larger, still-profitable trade sample than
   today's 15 — MEMORY `project_phase6_roi_baseline.md` / `project_phase6b_funnel_diagnosis.md`).

## Trd-M1 ✅ COMPLETE (2026-05-29) — Telemetry Normalization + LLM Episode Log

**Goal:** bring trade-domain JSONL onto the canonical envelope **and** add a curated
per-episode LLM log — without changing any decision, replay, or profitability behavior.

**Part 1 — Envelope the trade writers.**
- Targets: `trade_logger.py` (`_write :190`, records `:120/:152/:177`) and
  `sweep_trace_logger.py`.
- **Documented exception:** `integrity_events.py` *intentionally* avoids `event_fabric`
  (docstring `:16–18`) so it stays importable from `scripts/`; its `{ts,event,severity,
  source,payload}` shape is already auditable. Recorded as a deliberate exception in
  `event-taxonomy.md` — **not migrated**.
- Approach: add an additive `EventType` (e.g. `TRADE_LIFECYCLE`) or reuse
  `DECISION_SNAPSHOT` (decide in `event-taxonomy.md`); **grep consumers** of
  `fusion_trades*.jsonl` first → default to **dual-write** (legacy flat file untouched +
  new enveloped stream) unless grep proves in-place wrap is safe; wrap legacy record as
  `make_event_envelope(..., payload=<record>)`.

**Part 2 — Per-episode LLM log (`logs/llm_episodes.jsonl`).**
- A **deterministic, read-only projection**: a per-episode aggregator rolls up all
  enveloped events within one CRT lifecycle episode (`RANGE → … → RESOLUTION` or
  `EXPIRED`, boundary reuses `EpisodeMarker`/`CRTState` `crt_engine_v2.py:52–60,:150`)
  into **one summary record**, flushed at episode close.
- Summary payload: `episode_id`, `instrument`, `state_path` (the transition sequence),
  entry/exit (candle ts + prices), `decision` + `reason`, key features at decision,
  outcome (`rr`, `win`), drift severity, governance flags, and **`child_event_ids`**
  linking back to the full firehose for audit drill-down.
- It **never influences a decision** (execution authority isolated). Uses **candle
  timestamps**, not wall-clock, so episodes are replay-comparable.

**Replay/comparability guardrails (load-bearing):**
- ENTRY/EXIT keep using candle time (`opened_at`/`closed_at`); never wall-clock.
- Envelope `event_id` / `generation` / wall-clock `timestamp` are **NOT replay-
  comparable** — comparison keys on `payload` + candle ts. `generation` may interleave
  with threaded `CognitiveBus`; never use for cross-run correlation.
- The episode summarizer must be deterministic: same CSV + seed → byte-identical
  `llm_episodes.jsonl` payloads.

## Rollback Strategy

- Docs (Trd-M0): `git revert`.
- Trd-M1: additive. Part 1 dual-writes (legacy file untouched) until an explicit cutover;
  Part 2 writes a brand-new log only. No telemetry field removed without a documented
  superseding field (continuity rule). Hook (A2) is removable by deleting the
  settings.json entry.

## Telemetry Contracts

- Every cross-component event uses `make_event_envelope()` (fabric invariant #1).
- `schema_hash` on every event; offline audit vs current `FEATURE_ORDER_HASH`.
- **LLM episode log:** exactly one record per closed episode; fixed payload schema;
  `child_event_ids` resolve to real firehose events; replay-comparable on candle ts.
- No field removed without a superseding field; renames documented old→new in
  `event-taxonomy.md`.

## Verification

**Docs (Trd-M0):** every `file:line` resolves (spot-check); enveloped/non-enveloped
inventory matches actual writers; Mermaid parses; service-doc exemplar matches code.

**Trd-M1 (determinism is the acceptance gate):**
- Baseline run on fixed CSV + `slippage_seed`; snapshot `{instrument}_trades.csv` +
  `{instrument}_summary.json`.
- Apply Trd-M1, re-run identical CSV + seed → trade ledger + summary **byte-identical**.
- New enveloped trade events carry every legacy payload field (dual-write: legacy file
  unchanged). `llm_episodes.jsonl` **byte-identical across two identical runs**; each
  episode's `child_event_ids` resolve to real firehose events.
- Run `pytest` per `docs/reference/testing.md`.
- Append SESSION LOG ENTRY to `assistant_project.md`.

**Workstream A:** hook fires for plans-dir writes only, and only in this project's cwd.

## Out of Scope (this pass)

- Trd-M2–Trd-M5 not executed; per-service human docs beyond the one exemplar are on-demand.
- No config edits/rehash/promotion; no profitability tuning; no blind rewrites; no new
  parallel event system; `integrity_events.py` untouched.
- Trd-M1 must not alter any decision, gate, or replay behavior — logging/projection only.


================================================================================
SOURCE_FILE: docs/plans/claude-go-thrugh-docs-twinkling-finch.md
SOURCE_BYTES: 7681
PART: 2/10 FILE 3/7
================================================================================

# Plan: Reconcile the v1/v2 config-lineage divergence (governance trust)

> Created: 2026-06-02 · Updated: 2026-06-02 · Milestone: Production-governance integrity (backlog P1)
> Approach: **Option A — canonicalize the running config as governed (behavior-preserving).**

## Context — why this change

Production runs an **ungoverned config with stale validation evidence**, and the promotion
machinery is primed to silently overwrite it with a *different* lineage on the next promote.
All claims below were verified read-only against the live code/configs (2026-06-02):

1. **Ungoverned active.** `ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry` (hand-named,
   spaces in filename). `configs/promotion_log.jsonl` has **0 entries** for it — the last
   *governed* promotion was the clean `v2_multi_2026_04` (config_id `..._candidate_1`).
2. **Stale validation evidence.** The file's actual `params` are
   `retest_depth_max=0.8 / retest_atr_depth_fraction=0.5 / body_ratio_min=0.3 /
   atr_multiplier_min=0.6 / expansion_atr_min_distance=0.3`, but its `validation_summary`
   describes `v2_multi_2026_04_candidate_1` (`final_score=0.5966`, `total_trades=36`) — the
   *earlier* governed promotion with different params. `validation_summary` carries **no
   params fingerprint** → nothing to compare against.
3. **Hash gap hides the desync.** `_verify_config_hash` hashes `params` against the stored
   hash only ([production_config.py:89-108](src/config_layer/production_config.py));
   `validation_summary` is outside the hash, and `get_prod_section` never verifies it at all.
4. **Merge-base foot-gun.** `_load_full_base_config`
   ([promotion_manager.py:440-493](src/governance/promotion_manager.py)) prefers
   `v1_multi_2026_03` (which carries all 6 rich sections); `_write_to_registry`
   ([:545-581](src/governance/promotion_manager.py)) merges new params onto that base **and
   flips `ACTIVE_VERSION`**. The active config has `engine_runner` but **none** of
   `strategy_orchestrator / cognitive_layer / replay_memory / tradenet_meta /
   market_state_cluster / drift_governance` (verified: v1 has all 6, active has 0). → the
   next governed promotion would re-add those sections + change params lineage + flip live in
   one un-asked-for step.
5. **Active silently disables subsystems.** `get_prod_section` **raises** on an absent section
   ([:366-371](src/config_layer/production_config.py)); the 6 missing sections mean those
   subsystems are off/defaulted in production today.

**Outcome wanted:** make the *currently-running* behavior governed and auditable, and remove
the lineage foot-gun — without changing trading behavior or invalidating the recent
ROI/session/OOS baselines (all measured on the deepdeektry params + lean sections).

## Approach — Option A (recommended), not B

- **A (this plan):** keep deepdeektry's params + lean sections, but make them *governed* —
  fresh validation matching the actual params, clean version name, `PROMOTED` log entry.
  Behavior-neutral. Fold in the already-APPROVE'd BNBUSDT/SOLUSDT session overrides (the
  staged `v3_multi_2026_06.json` work) so there is **one** clean governed config.
- **B (rejected here):** adopt v1's rich-section lineage as canonical — that re-enables
  orchestrator/cognitive/replay/etc., which is a *capability* change that alters behavior and
  invalidates current baselines. That re-enablement is the separate "unconsumed intelligence"
  thread; do it deliberately + validated, later — not folded into a governance fix.

## Steps

1. **Canonicalize → governed `v3_multi_2026_06` (behavior-preserving).**
   - Take the running params (+ BNB/SOL `allowed_sessions_overrides`, already validated
     APPROVE) and run `ConfigValidator.validate` across the production instrument set
     (session-override-aware path, already shipped).
   - Write a **fresh `validation_summary` that matches the actual params** (carry a params
     fingerprint — see Step 3), a clean filename (no spaces), and a `PROMOTED`
     `promotion_log.jsonl` entry.
   - **Regression guard (before any flip):** per-instrument backtest metrics of governed `v3`
     must match current deepdeektry behavior (trades/PF/DD within noise) — proves no silent
     change. Reuse the staged `results/validation/v3_multi_2026_06_report.json` evidence.
   - *Flipping `ACTIVE_VERSION` stays the operator's action* (consistent with the prior
     "validated-ready" boundary) — see Out of scope.

2. **Fix the merge-base foot-gun** — `_load_full_base_config` should prefer the **current
   ACTIVE governed config** as merge base (fall back to `v1_multi_2026_03` only if the active
   is sparse/missing `engine_runner`), and **log which base it used**. Future promotions then
   build on what is actually running, not a stale hardcoded v1.
   - File: [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py)
     `_load_full_base_config` (`:440-493`) + the `_BASE_VERSION_FALLBACK` constant.

3. **Two governance guard tests** (`tests/`) — must **fail on current deepdeektry** and
   **pass on reconciled v3** (proves they catch the bug class):
   - **validation-freshness:** fail if `validation_summary` does not correspond to `params`
     (embed + compare a params fingerprint; reuse `_compute_params_hash`).
   - **governed-active:** assert `ACTIVE_VERSION`'s config has a matching `PROMOTED` entry in
     `promotion_log.jsonl`.

4. **Naming hygiene** — `ACTIVE_VERSION` must be a clean version key (no spaces / ad-hoc
   suffixes like `" - deepdeektry"`). Document the rule near the pointer loader
   (`get_active_version`, [production_config.py:60-82](src/config_layer/production_config.py)).

5. **Flag, do NOT silently do:** re-adding the 6 rich engine sections is a separate,
   deliberate, validated capability decision — track it against the evidence map, not here.

## Critical files
- [`src/config_layer/production_config.py`](src/config_layer/production_config.py) —
  `_verify_config_hash` (hash gap), `get_prod_section` (raises on missing),
  `get_active_version`/`PROD_VERSION`, `load_prod_config_from_registry`.
- [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py) —
  `_load_full_base_config` (base preference), `_write_to_registry` (merge + ACTIVE flip),
  `_build_registry_entry`, `_log_event`.
- `configs/production/ACTIVE_VERSION`, `configs/promotion_log.jsonl`, the two
  `v2_multi_2026_04*.json`, `v1_multi_2026_03.json`, staged `v3_multi_2026_06.json`.
- New: `tests/test_governance_integrity_guards.py` (the two guards).

## Verification
- **Behavior-neutrality:** governed `v3` per-instrument backtest metrics ≈ current deepdeektry
  (diff trades/PF/DD within noise) before any flip.
- **Governance integrity:** `PromotionManager.load_version("v3_multi_2026_06")` passes;
  `validation_summary` params-fingerprint == `params`; new `PROMOTED` entry present.
- **Guards prove the bug class:** the two new tests FAIL on current deepdeektry (stale summary
  + ungoverned active) and PASS on reconciled v3.
- **No regressions:** full `pytest -q` green; `_load_full_base_config` base-selection is logged
  and picks the active governed config.
- **Self-doc:** SESSION LOG (§6) appended; touched topic docs synced (§6.1) —
  `config-validation.md`, `promotion-governance.md`.

## Out of scope
- **Flipping `ACTIVE_VERSION`** — operator action (governance gate), done after the
  behavior-neutrality + guard evidence is in hand.
- **Re-enabling the 6 rich engine sections** — separate validated capability decision.
- Drift→action, zone-expectancy weighting, Probability Surface, Trd-M6 — later priorities.


================================================================================
SOURCE_FILE: docs/plans/claude-you-have-full-fuzzy-bonbon.md
SOURCE_BYTES: 56015
PART: 2/10 FILE 4/7
================================================================================

> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# CANONICAL EXECUTION COGNITION GRAPH — Tradelatest

## VERIFICATION METADATA
```
Git SHA:        e05f3846cf9c9e384a88e4f3bc08a4e470df23fe
Branch:         patch
Generated:      2026-05-20
Python:         3.14.3
ACTIVE_VERSION: "v2_multi_2026_04 - deepdeektry"  ← ANOMALY: spaces in name
Production Dir: configs/production/
Methodology:    Source-only. Every claim maps to file + line. NOT VERIFIED IN SOURCE used when unproven.
```

---

# 1. CANONICAL SYSTEM REALITY

## What this repository ACTUALLY is today

A **file-backed, Python ≥3.10 quantitative trading platform** with no database, no message broker, no cloud dependencies. All state is JSON files on disk.

### Production Runtime — CANONICAL
**Path:** CSV → `EngineRunner.run()` → `FusionEngine` → `DecisionEngine` → `UltronRiskGate` → trade decision

**Files:**
- `src/core/engine_runner.py` — orchestrates all 4 scoring engines (CANONICAL, LIVE_PRODUCTION)
- `src/core/fusion_engine.py` — weighted score fusion (CANONICAL)
- `src/core/decision_engine.py` — final EXECUTE/REJECT authority (CANONICAL)
- `src/config_layer/execution_planner.py` — entry/SL/TP derivation (CANONICAL)
- `src/core/ultron_risk_gate.py` — position-level risk gate (CANONICAL)

**Active production config:** `configs/production/v2_multi_2026_04 - deepdeektry.json`
**Active version pointer:** `configs/production/ACTIVE_VERSION` → `"v2_multi_2026_04 - deepdeektry"`

> ⚠️ ANOMALY: The ACTIVE_VERSION string contains spaces and a dash. Expected format: `v2_multi_2026_04`. This may cause path resolution issues on some OS/filesystem combinations if the string is used directly in file paths.

### Replay Runtime — CANONICAL (backtest_v2)
**File:** `src/runtime/backtest_v2.py` — `BacktestRunner` (CANONICAL)
**Duplicate paths (EXPERIMENTAL/PARTIALLY_CONNECTED):**
- `src/runtime/backtest_bitnet.py` — BitNet gate mode evaluation (EXPERIMENTAL)
- `src/runtime/unified_replay_harness.py` — Layer A + Layer B parallel run (EXPERIMENTAL)
- `src/governance/strategy_backtest.py` — per-strategy backtester, different schema (PARTIALLY_CONNECTED)

### Governance Runtime — GOVERNANCE_CRITICAL
- `src/governance/orchestrator.py` — GovernanceOrchestrator (GOVERNANCE_CRITICAL)
- `src/governance/shadow_promotion_gate.py` — ShadowPromotionGate (GOVERNANCE_CRITICAL)
- `src/governance/promotion_manager.py` — three promotion paths (GOVERNANCE_CRITICAL)
- `src/governance/reflection_buffer_advanced.py` — data → prompt pipeline (GOVERNANCE_CRITICAL)
- `src/governance/bitnet_governance_executor.py` — MetaGovernorExecutor (GOVERNANCE_CRITICAL)

### ML Runtime — PARTIALLY_CONNECTED
- `src/bitnet/bitnet_inference.py` — BitNetModel, inference from JSON weights (VALIDATION_CRITICAL)
- `src/features/feature_pipeline.py` — FeaturePipeline, 38 canonical features (CANONICAL)
- `models/gaussian_registry.json` — active: ETHUSDT v5 model, 35-feature schema (PARTIALLY_CONNECTED: schema v2 ≠ pipeline v3)
- `models/rr_registry.json` — active: ETHUSDT v5 (PARTIALLY_CONNECTED)
- `models/tradenet_registry.json` — active: ETHUSDT v5 .pth (PARTIALLY_CONNECTED)
- `models/zone_gate_registry.json` — active: ETHUSDT 202605_v1 (PARTIALLY_CONNECTED)
- `models/bitnet/bitnet_registry.json` — empty `{}` (DISCONNECTED — no trained model registered)
- `scripts/training/train_bitnet.py` — writes to `models/bitnet/` (PARTIALLY_CONNECTED after Phase 4 fix)

### Validation Runtime — VALIDATION_CRITICAL
- `src/config_layer/config_validator.py` — ConfigValidator (VALIDATION_CRITICAL)

### Control-Plane Runtime — LIVE_PRODUCTION
- `src/control_plane/server.py` — HTTP server localhost:8787 (LIVE_PRODUCTION)
- `src/control_plane/registry.py` — 47 CommandSpec entries (LIVE_PRODUCTION)
- `src/control_plane/jobs.py` — JobManager, subprocess.Popen execution (LIVE_PRODUCTION)

### Agent Runtime — EXPERIMENTAL
- `src/agent/plan_compiler.py` — 21 deterministic intents (EXPERIMENTAL)
- `src/agent/intent_router.py` — regex + LLM routing (EXPERIMENTAL)
- `src/agent/tool_registry.py` — tool handler registration (EXPERIMENTAL)

### Archived / Dead — DO NOT USE
- `archive/inout_legacy/ARCHIVED_2026_05_02/runner.py` — DEAD_CODE
- `archive/dead_code/` — DEAD_CODE
- Registry entry `live.inout_runner` → `inout.runner` — BROKEN (module not found)

---

# 2. CANONICAL EXECUTION GRAPH

## Path A: Control Plane → Subprocess (UI-triggered)

```
Browser → localhost:8787
→ ControlPlaneAPI (server.py)
→ JobManager.create_run(command_id, user_args) (jobs.py:200)
→ build_command_line(spec, merged_args) (jobs.py:1016)
    Registry defaults merged with user_args
    DRIFT RISK: registry defaults ≠ argparse defaults (--instruments, --instrument)
→ subprocess.Popen([sys.executable, script, ...args]) (jobs.py:325)
    shell=False — no direct shell injection
    No input validation on merged args values
→ Script runs as child process
→ Stdout/stderr streamed to logs/control_plane/runs/{run_id}.json
```

## Path B: Backtest (canonical replay)

```
CLI: python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv
→ main() (backtest_v2.py:1942)
→ argparse.parse_args() — no choices constraint on --instrument
→ BacktestConfig.from_prod_config(instrument) (backtest_v2.py:140)
    Loads configs/production/{ACTIVE_VERSION}.json
    Hash verification on params (SHA-256)
→ CandleLoader(csv_path, instrument).stream() — yields Candle objects
→ BacktestRunner.__init__(cfg, csv_path)
    Phase 1: FeaturePipeline(raw_df).run() → feature_vectors (N×38 float32)
             RAISES RuntimeError on failure (Phase 2 fix applied)
    Phase 2: FeatureMonitor(window_size=500) — logs ERROR if init fails
    Phase 3: get_prod_section("execution_planner") — RAISES if missing
    Phase 4: BACKTEST_ENGINE_GATE env var — EngineRunner wired only if "1"
→ BacktestRunner.run(candle_stream, total_candles, output_dir)
    Per-candle loop:
        warmup skip (candle_idx < warmup_candles)
        HTF init after seed candles
        Gap detection (GapDetector) → state reset if gap found
        engine.process_candle(candle, htf_id) → CRT state machine advance
        On TRADE_OPENED:
            feature lookup from feature_ts_to_idx
            Phase-5 scorer gate (CRTGaussianScorer or CRTCalibratedScorer)
            Reject if p_win < 0.35
            FeatureMonitor drift check
            Optional EngineRunner gate (BACKTEST_ENGINE_GATE=1)
        On TRADE_CLOSED: journal.on_trade_closed() → PnL computation
→ BacktestMetrics collected
→ ReportWriter.write():
    results/{instrument}/{instrument}_trades.csv
    results/{instrument}/{instrument}_summary.csv
    results/{instrument}/{instrument}_metrics.json
```

## Path C: EngineRunner (live scoring pipeline)

```
Signal candidate → EngineRunner.run(input_dict) (engine_runner.py:493)

Step 1: TrapValidatorEngine.compute(merged_input)
        score ≤ 0.0 → hard reject ("adapter_rejected")

Step 2: ALL 4 engines run unconditionally
    Zone Gate:   run_zone_gate_engine(features, model_fn, threshold)
                 BitNetZoneGate wrapper — loads from zone_registry_path
    CRT:         crt_compute(crt_config, candle_context)
    Gaussian:    HeuristicGaussianEngine.compute() or MLGaussianEngine.compute()
                 Selected by GAUSSIAN_IMPL env var OR config["gaussian_impl"]
    RR:          RREngine.compute(input_data)
    Optional:    RRFusionLayer.score_dict() if rr_fusion_enabled=true
    Optional:    strategy_consensus_score from context

Step 3: Completeness check
        EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}
        missing = EXPECTED_ENGINES - engine_results.keys()
        If ANY missing → reject("incomplete_engine_execution:{sorted(missing)}")

Step 4: FusionEngine.compute(engine_results)
        Weights: crt=0.30, gaussian=0.25, zone_gate=0.25, rr=0.20
        Dead engine detection (mean=0, var=0 over 1000 samples) → exclude from fusion
        Conflict detection: direction signals (+1, -1) — policy: conservative or majority
        final_score = weighted sum of clamped engine scores

Step 5: Fusion threshold gate
        final_score < fusion_min_score → reject("low_fusion_score")

Step 6: RegimeGovernor.evaluate() or _regime_governor_legacy()
        Trend/range/neutral regime detection
        Breakout + trap engine scores
        UltronRiskGate enabled (live) or disabled (training/backtest)
        not gate_result["allow"] → reject

Step 7: DecisionEngine.evaluate(score, p_win, zone_gate, fusion, config)
        SOLE authority for "execute" or "reject"
        Adaptive thresholds injected from acceptance_controller

Step 8: collector.log(full decision record)
        Appends to collector JSONL audit file

Step 9: acceptance_controller.update_metrics()
        convergence_controller.record_outcome()

Step 10: CognitiveBus.emit() — fire-and-forget, never raises

→ Returns decision_result dict from DecisionEngine
```

## Path D: Governance Orchestration (production config mutation)

```
CLI: python src/governance/orchestrator.py --collector-log ... --trades-csv ... --baseline-pnl ...
OR: governance_mode.py governance.run_loop tool (write=True, confirms required)

→ GovernanceOrchestrator.__init__():
    MetaGovernorExecutor(bitnet_bin, model_path, audit_log_path)
    ShadowPromotionGate(active_config_path)

→ GovernanceOrchestrator.run():
    Step 1: ReflectionBuffer.load_and_merge(collector_log, trades_csv) → DataFrame
    Step 2: reflection.generate_prompt_payload(df) → WRITES logs/meta_prompt.txt
    Step 3: executor.run_inference(prompt_path=logs/meta_prompt.txt)
            executor.extract_and_validate_config(raw_output) → patch dict
            executor.log_governance_event() → APPENDS logs/governance_audit.jsonl
    Step 4: shadow_gate.stage_candidate(patch) → WRITES configs/production/candidate.json
            shadow_gate.execute_shadow_test() → subprocess backtest
            shadow_gate.promote_if_superior(baseline_pnl, shadow_pnl, n_trades):
                Gate 1: n_trades ≥ min_shadow_trades
                Gate 2: shadow_pnl > baseline_pnl
                If BOTH pass:
                    shutil.copy(candidate_path, active_config_path)  ← NON-ATOMIC
                    candidate_path.unlink()
                    → active production config IS NOW MUTATED
                    → NO rollback path if crash occurs mid-copy
```

## Path E: Promotion (PromotionManager — canonical path)

```
CLI: python src/governance/promotion_manager.py promote --checkpoint ... --data-dir ...

→ promote_from_tuner_checkpoint(checkpoint_path, version, csv_paths):
    Load checkpoint JSON
    Filter valid results (score > -999.0)
    For each top config:
        ConfigValidator.validate(params, csv_paths) → ValidationReport
        If APPROVE:
            _execute_promotion(report, version, notes)
                _build_registry_entry() → registry dict with config_hash (SHA-256)
                _write_to_registry(entry, version):
                    Archive existing: shutil.copy2(out_path, archive_path)  ← non-atomic
                    Write new: open(out_path, "w") + json.dump()  ← NON-ATOMIC overwrite
                    Write pointer: ACTIVE_VERSION.write_text(version)  ← separate write
                    _log_event() → APPENDS configs/promotion_log.jsonl
→ Returns {"status": "PROMOTED", ...}

ATOMICITY GAP: Three separate writes. Crash between config write and ACTIVE_VERSION update
leaves system in version mismatch state.
```

## Path F: Agent REPL (AI-assisted execution)

```
CLI: python src/agent/cli.py
→ AgentCore REPL loop
→ User input → IntentRouter.classify(user_input, conversation)
    Step 1: regex_classify() against intent_patterns.json (deterministic)
    Step 2: If confidence < 0.6: llm_classify() via llm_chat() (stochastic)
    Step 3: Unknown → {"intent_key": "ask_user"}
→ PlanCompiler.build(intent_key) → Plan (from PLAN_REGISTRY lookup — deterministic)
→ Executor.execute(plan):
    Per ToolStep:
        If tool.write=True → confirm gate (y/N prompt)
        path_guard check
        handler(args)
→ Returns structured result
```

---

# 3. STATE OWNERSHIP GRAPH

## Active Production Config

| Property | Value |
|---|---|
| **Owner** | `PromotionManager._write_to_registry()` (canonical), `ShadowPromotionGate.promote_if_superior()` (governance path) |
| **Location** | `configs/production/{ACTIVE_VERSION}.json` |
| **Pointer** | `configs/production/ACTIVE_VERSION` (plain text file) |
| **Mutation locations** | `promotion_manager.py:_write_to_registry()` + `shadow_promotion_gate.py:235` |
| **Atomicity** | NOT atomic — two separate writes (config + pointer) |
| **Rollback** | Manual only — archive files preserved as `{version}_archived_{ts}.json` |
| **Concurrency risk** | HIGH — no locking; two concurrent governance runs can corrupt |
| **Crash consistency** | Config written but pointer stale = silent version mismatch |
| **Corruption risk** | CRITICAL — mid-write crash leaves truncated JSON |

## Governance Audit Log

| Property | Value |
|---|---|
| **Owner** | `bitnet_governance_executor.py` — `log_governance_event()` |
| **Location** | `logs/governance_audit.jsonl` |
| **Access pattern** | Append-only |
| **Rollback** | Not applicable (audit) |
| **Concurrency risk** | Low (single orchestrator instance assumed) |
| **Corruption risk** | LOW — append-only JSONL; partial line at crash is ignorable |

## Promotion Log

| Property | Value |
|---|---|
| **Owner** | `promotion_manager.py` — `_log_event()` |
| **Location** | `configs/promotion_log.jsonl` |
| **Access pattern** | Append-only |
| **Atomicity** | Single line write — effectively atomic |
| **Rollback** | Not applicable (audit) |
| **Corruption risk** | LOW — written AFTER config; crash before = silent promotion (no log entry) |

## Model Registries (4 active)

| Property | Value |
|---|---|
| **Owner** | Training scripts (`train_pipeline.py`, `model_registry.py`) |
| **Location** | `models/{gaussian,rr,tradenet,zone_gate}_registry.json` |
| **Active model selection** | `"active": true` flag in registry JSON |
| **Mutation** | Only via promotion path (model_registry.py GOV-3 atomic promotion) |
| **Fallback if active model file missing** | `FileNotFoundError` raised — NO silent fallback (verified in bitnet_inference.py) |
| **Schema mismatch** | All active models use 35-feature v2.0 schema; pipeline produces 38-feature v3.0 — requires truncation at inference |

## Feature Cache (per BacktestRunner)

| Property | Value |
|---|---|
| **Owner** | `BacktestRunner.__init__()` |
| **Location** | In-memory: `self.feature_vectors` (N×38 float32 numpy array), `self.feature_ts_to_idx` dict |
| **Lifecycle** | Created at BacktestRunner init, destroyed when object GC'd |
| **Concurrency risk** | None — per-instance, not shared |
| **Failure mode** | `RuntimeError` if FeaturePipeline fails (fail-fast, Phase 2 fix) |

## CRT Engine State (per candle)

| Property | Value |
|---|---|
| **Owner** | `CRTEngine` — maintains `EngineState` dataclass |
| **Mutable fields** | `current_state`, `atr`, `sweep_event`, `displacement_candle`, `retest_candle`, `active_trade`, `risk_score`, `event_log` |
| **Reset trigger** | Gap detection, session boundary, explicit reset |
| **Persistence** | In-memory only — not serialized between runs |
| **Determinism** | Deterministic given same candle sequence |

## Collector JSONL (runtime decisions)

| Property | Value |
|---|---|
| **Owner** | `collector.py` — `Collector.log()` |
| **Location** | `logs/{instrument}_fusion.jsonl` (approximate) |
| **Access pattern** | Append-only per run |
| **Consumer** | `ReflectionBuffer.load_and_merge()` for governance |
| **Corruption risk** | LOW — append-only |

---

# 4. METHOD-LEVEL EXECUTION COGNITION

## GovernanceOrchestrator.run()

| Field | Value |
|---|---|
| **File** | `src/governance/orchestrator.py` |
| **Class** | `GovernanceOrchestrator` |
| **Method** | `run()` lines 92–218 |
| **Human Purpose** | Drive reflection → LLM inference → shadow test → conditional production config promotion |
| **Architectural Role** | The ONLY autonomous production config mutation path outside of PromotionManager |
| **Invocation Sources** | `src/agent/modes/governance_mode.py:governance.run_loop` (write=True), CLI `main()` line 254 |
| **Runtime Flow** | ReflectionBuffer.load_and_merge → generate_prompt_payload → MetaGovernorExecutor.run_inference → ShadowPromotionGate.promote_if_superior |
| **State Mutations** | WRITES: `logs/meta_prompt.txt`, `logs/governance_audit.jsonl`, `configs/production/candidate.json`; CONDITIONALLY: `configs/production/{ACTIVE_VERSION}.json` |
| **Failure Modes** | Crash between steps leaves stale artifacts; mid-copy crash corrupts active config |
| **Fallback Behavior** | Returns `{"patch": None, "promoted": False, "reason": ...}` on reflection failure |
| **Determinism** | NONDETERMINISTIC — MetaGovernorExecutor uses BitNet/LLM; shadow PnL depends on data at call time |
| **Trust Classification** | GOVERNANCE_CRITICAL |
| **Security Risks** | `active_config_path` default is constructor parameter — path traversal if caller-controlled |
| **Important Findings** | NOT atomic. Concurrent calls can corrupt active config. No locking. |

## EngineRunner.run()

| Field | Value |
|---|---|
| **File** | `src/core/engine_runner.py` |
| **Class** | `EngineRunner` |
| **Method** | `run(input_dict)` lines 493–921 |
| **Human Purpose** | Score a trade candidate through all 4 engines and return final EXECUTE/REJECT decision |
| **Architectural Role** | Single authoritative scoring pipeline for both live and backtest paths |
| **Invocation Sources** | `live_engine_hook.py`, `BacktestRunner.run()` (when BACKTEST_ENGINE_GATE=1), agent copilot tools |
| **Downstream Calls** | TrapValidatorEngine → ZoneGate → CRTEngine → GaussianEngine → RREngine → FusionEngine → RegimeGovernor → DecisionEngine → Collector → acceptance/convergence controllers → CognitiveBus |
| **State Mutations** | Collector append, acceptance_controller metrics, convergence_controller outcomes |
| **Failure Modes** | ZoneGate exception → neutral 0.5 (SILENT FALLBACK). RRFusion exception → base RR score (SILENT). CognitiveBus exception → pass (intentional). |
| **Determinism** | PARTIALLY DETERMINISTIC — core pipeline deterministic; GaussianEngine depends on GAUSSIAN_IMPL env var; dead-engine exclusion depends on historical window |
| **Trust Classification** | CANONICAL, LIVE_PRODUCTION |
| **Important Findings** | ZoneGate and RRFusion silent fallbacks can produce neutral scores masking real failures. |

## ShadowPromotionGate.promote_if_superior()

| Field | Value |
|---|---|
| **File** | `src/governance/shadow_promotion_gate.py` |
| **Class** | `ShadowPromotionGate` |
| **Method** | `promote_if_superior(baseline_pnl, shadow_pnl, n_shadow_trades)` lines 186–246 |
| **Human Purpose** | Promote candidate config to production only if shadow backtest outperforms baseline |
| **Architectural Role** | Final gate before autonomous production config mutation |
| **State Mutations** | `shutil.copy(candidate_path, active_config_path)` — directly overwrites live production config |
| **Atomicity** | NOT atomic. `shutil.copy()` on Windows: open → truncate → write in chunks. Crash mid-copy = corrupted active config. |
| **Rollback Capability** | NONE — no backup taken before overwrite; archive only exists via PromotionManager path |
| **Concurrency Risk** | CRITICAL — no file locking; two parallel governance runs can both promote, second overwriting first |
| **Determinism** | NONDETERMINISTIC — depends on shadow backtest PnL and baseline_pnl at call time |
| **Trust Classification** | GOVERNANCE_CRITICAL, DANGEROUS (atomicity) |

## PromotionManager._write_to_registry()

| Field | Value |
|---|---|
| **File** | `src/governance/promotion_manager.py` |
| **Class** | `PromotionManager` |
| **Method** | `_write_to_registry(entry, version)` lines 494–605 |
| **Human Purpose** | Persist a validated config version to the production registry |
| **State Mutations** | (1) Archive: `shutil.copy2(out_path, archive_path)`, (2) Write: `open(out_path, "w") + json.dump()`, (3) Pointer: `ACTIVE_VERSION.write_text(version)`, (4) Log: `_log_event()` append to `promotion_log.jsonl` |
| **Crash Scenarios** | Config written but pointer stale → version mismatch silent. Config write half-done → corrupt JSON. |
| **SHA-256 Verification** | `_compute_config_hash(params)` — SHA-256 of `json.dumps(params, sort_keys=True)`. Stored in registry entry AND verified at load via `load_version()`. |
| **Determinism** | PARTIALLY DETERMINISTIC — SHA-256 is deterministic; timestamp fields are nondeterministic |
| **Trust Classification** | GOVERNANCE_CRITICAL |

## ConfigValidator.validate()

| Field | Value |
|---|---|
| **File** | `src/config_layer/config_validator.py` |
| **Class** | `ConfigValidator` |
| **Method** | `validate(params, csv_paths, config_id, use_llm, warmup_candles)` lines 310–421 |
| **Human Purpose** | Determine if a parameter set meets quality gates across all instruments |
| **Fail-Fast** | Missing CSV → hard REJECT. Instrument backtest exception → hard REJECT. (Phase 5 fix applied) |
| **Hard Gates** | min_trades_per_instrument, max_drawdown_pct, min_fitness_score |
| **Soft Gates** | win_rate, expectancy_rr, trade_count_target, score_std_dev |
| **Fitness Formula** | `0.5×expectancy_norm + 0.2×winrate + 0.2×count_norm + 0.1×dd_norm` |
| **Determinism** | DETERMINISTIC given same params + same CSV data |
| **Trust Classification** | VALIDATION_CRITICAL |

## FusionEngine.compute()

| Field | Value |
|---|---|
| **File** | `src/core/fusion_engine.py` |
| **Method** | `compute(engine_results)` lines 256–450 |
| **Completeness Gate** | `expected = ("crt","gaussian","zone_gate","rr")`. Missing → returns `{"final_score": 0.0, "reason": "missing_engine_outputs"}` |
| **Weights** | crt=0.30, gaussian=0.25, zone_gate=0.25, rr=0.20 (from config) |
| **Dead Engine Detection** | mean=0.0 AND var=0.0 over 1000-sample window → engine excluded from weighted average |
| **Conflict Policy** | "conservative" (reject on direction conflict) or "majority" (winner decides) |
| **Silent Fallback** | `fusion.evaluate()` raises → fall back to `compute()` path (SILENT degradation) |
| **Determinism** | DETERMINISTIC for same inputs; dead-engine exclusion depends on historical window |
| **Trust Classification** | CANONICAL |

## FeaturePipeline.run()

| Field | Value |
|---|---|
| **File** | `src/features/feature_pipeline.py` |
| **Method** | `run()` lines 736–802 |
| **Input** | DataFrame with columns: timestamp, open, high, low, close (volume optional, defaults 0.0) |
| **Output** | `(enriched_df, vectors)` — enriched_df is NaN-clean, vectors is (N, 38) float32 numpy array |
| **Feature Schema** | 38 features: 35 from v2.0 + 3 new v3.0 (`liquidity_distance`, `liquidity_pressure_score`, `volume_spike`) |
| **Lookahead Bias** | `center=True` rolling windows in live mode — acknowledged in code (lines 39–40) |
| **NaN Handling** | `finalize()` drops all rows with NaN — requires ≥200 bars history (ma_200 warmup) |
| **Determinism** | DETERMINISTIC — no random operations |
| **Schema Mismatch** | Active models use 35-feature v2.0. Pipeline produces 38. Slicing to 35 must occur at inference. |
| **Trust Classification** | CANONICAL |

---

# 5. TRUST CLASSIFICATION SYSTEM

| Component | File | Classification | Reason |
|---|---|---|---|
| EngineRunner | `src/core/engine_runner.py` | **CANONICAL, LIVE_PRODUCTION** | Single authoritative scoring path |
| FusionEngine | `src/core/fusion_engine.py` | **CANONICAL** | Sole fusion authority |
| DecisionEngine | `src/core/decision_engine.py` | **CANONICAL** | Sole EXECUTE/REJECT authority |
| BacktestRunner | `src/runtime/backtest_v2.py` | **CANONICAL** | Authoritative replay engine |
| FeaturePipeline | `src/features/feature_pipeline.py` | **CANONICAL** | Authoritative feature source |
| ConfigValidator | `src/config_layer/config_validator.py` | **VALIDATION_CRITICAL** | Mandatory pre-promotion gate |
| PromotionManager | `src/governance/promotion_manager.py` | **GOVERNANCE_CRITICAL** | Canonical promotion path |
| GovernanceOrchestrator | `src/governance/orchestrator.py` | **GOVERNANCE_CRITICAL** | Autonomous production mutator |
| ShadowPromotionGate | `src/governance/shadow_promotion_gate.py` | **GOVERNANCE_CRITICAL, DANGEROUS** | Atomicity risk on production write |
| ReflectionBuffer | `src/governance/reflection_buffer_advanced.py` | **GOVERNANCE_CRITICAL** | Governance data source |
| production_config.py | `src/config_layer/production_config.py` | **CANONICAL** | Single config authority |
| CRT Engine v2 | `src/config_layer/crt_engine_v2.py` | **CANONICAL** | Core signal state machine |
| UltronRiskGate | `src/core/ultron_risk_gate.py` | **LIVE_PRODUCTION** | Live position gate only |
| ExecutionPlannerV1_2 | `src/config_layer/execution_planner.py` | **CANONICAL** | Entry/SL/TP authority |
| BitNetModel | `src/bitnet/bitnet_inference.py` | **VALIDATION_CRITICAL** | Gate scoring (verified fail-fast) |
| BitNet Training | `scripts/training/train_bitnet.py` | **PARTIALLY_CONNECTED** | Writes to registry but inference path still manual |
| backtest_bitnet.py | `src/runtime/backtest_bitnet.py` | **EXPERIMENTAL** | Non-canonical metrics schema |
| unified_replay_harness.py | `src/runtime/unified_replay_harness.py` | **EXPERIMENTAL** | Composite of two schemas |
| strategy_backtest.py | `src/governance/strategy_backtest.py` | **PARTIALLY_CONNECTED** | Different schema, not in main pipeline |
| Agent system | `src/agent/` | **EXPERIMENTAL** | Not production-deployed |
| IntentRouter | `src/agent/intent_router.py` | **EXPERIMENTAL** | LLM fallback is nondeterministic |
| llm_research/policy_builder.py | `src/llm_research/policy_builder.py` | **DANGEROUS** | eval() on feature expressions (see §11) |
| `live.inout_runner` registry entry | `src/control_plane/registry.py:442` | **BROKEN** | Module not found (archived) |
| `archive/` | `archive/` | **DEAD_CODE** | No live imports confirmed |
| `archive/inout_legacy/` | `archive/inout_legacy/` | **LEGACY** | Runner awaiting restore decision |

---

# 6. DETERMINISM AUDIT

## BacktestRunner — DETERMINISTIC (with caveats)

- **Candle loop:** Reads from CSV sequentially. No time.now() in trading path. ✓ Deterministic
- **Slippage:** `SlippageModel(seed)` — seeded RNG via `random.Random(seed)`. If seed=0 → NOT seeded → nondeterministic slippage
- **Feature pipeline:** Pure numpy/pandas operations. ✓ Deterministic
- **Phase-5 scorer:** Gaussian parameters from config. ✓ Deterministic
- **EngineRunner gate:** `BACKTEST_ENGINE_GATE` env var — behavior changes based on environment. Partially nondeterministic

## EngineRunner — PARTIALLY DETERMINISTIC

- **GAUSSIAN_IMPL env var** (`engine_runner.py:275`): If set at runtime, switches engine implementation → same input can produce different scores
- **Dead-engine exclusion:** Depends on 1000-sample rolling window — window state not serialized → nondeterministic across restarts
- **RegimeGovernor:** Quota-based rejection in live mode — depends on daily trade count state
- **CognitiveBus:** Fire-and-forget async — timing nondeterministic (does not affect decision)

## Governance Orchestration — NONDETERMINISTIC

- **MetaGovernorExecutor.run_inference():** BitNet/LLM inference — inherently nondeterministic
- **Shadow backtest PnL:** Depends on data at call time — deterministic per dataset, nondeterministic across calls
- **promote_if_superior:** Comparison is deterministic given PnL values, but PnL values are nondeterministic

## IntentRouter — PARTIALLY DETERMINISTIC

- **Regex path:** Deterministic ✓
- **LLM path:** `llm_chat()` at temperature=0.0 — theoretically deterministic but LLM inference can vary

## PlanCompiler — DETERMINISTIC

- Pure Python dict lookup. No randomness. ✓ Fully deterministic

## Environment Variable Nondeterminism Sources

| Variable | Default | File | Effect |
|---|---|---|---|
| `GAUSSIAN_IMPL` | config value (→ "heuristic") | `engine_runner.py:275` | Switches ML vs heuristic Gaussian |
| `BACKTEST_ENGINE_GATE` | "0" | `backtest_v2.py:1398` | Enables/disables EngineRunner in backtest |
| `BACKTEST_BYPASS_ZONE_INVALID` | "1" | `backtest_v2.py` (referenced) | Bypass zone gate invalid rejection |

---

# 7. REPLAY TRUTH AUDIT

## Canonical Replay Engine

**`src/runtime/backtest_v2.py` — BacktestRunner** is the canonical replay engine.

- Produces: `BacktestMetrics` → `to_dict()` schema
- Used by: `ConfigValidator._run_instrument()`, direct CLI, auto_tuner_multi
- Output schema: `{approved_trades, rejected_trades, wins, losses, tp1_hits, tp2_hits, total_pnl_rr_raw, total_pnl_rr_net, max_drawdown_rr, max_drawdown_pct, win_rate, avg_rr_net}`

## Duplicate Replay Systems

| System | File | Schema | Authority |
|---|---|---|---|
| **BacktestRunner** | `backtest_v2.py` | `BacktestMetrics.to_dict()` | **CANONICAL** |
| **backtest_bitnet** | `backtest_bitnet.py` | `list[dict]` with `{decision, reason, bitnet_decision, ...}` | EXPERIMENTAL |
| **unified_replay_harness** | `unified_replay_harness.py` | Composite of both above | EXPERIMENTAL |
| **ConfigValidator** | `config_validator.py` | `{score, trades, win_rate, expectancy_rr, max_drawdown, total_pnl_rr}` | VALIDATION_CRITICAL (internal schema) |
| **StrategyBacktester** | `strategy_backtest.py` | `StrategyMetrics` with `{trade_count, win_count, profit_factor, expectancy_inr, ...}` | PARTIALLY_CONNECTED |

## Schema Divergence

- `ConfigValidator` consumes a custom 6-field dict derived from `BacktestMetrics`. If `BacktestMetrics` schema evolves (new fields, renamed fields), the validator's extraction logic must be updated manually — no shared serializer.
- `StrategyMetrics` uses `expectancy_inr` (India Rupees) — incompatible currency unit with `BacktestMetrics` which uses RR multiples.
- `backtest_bitnet.py` produces per-row records, not aggregate metrics — incomparable with BacktestRunner aggregate output.

## Authoritative Truth Map

| Metric | Authoritative Source |
|---|---|
| Trade P&L (replay) | `BacktestRunner` → `TradeJournal.on_trade_closed()` |
| Config fitness score | `ConfigValidator._fitness_score()` |
| Governance decision | `MetaGovernorExecutor.extract_and_validate_config()` |
| Feature vectors | `FeaturePipeline.run()` |
| Model inference | Per-model registry entry → respective loader |

---

# 8. GOVERNANCE TRANSACTION MODEL

## Promotion via PromotionManager (canonical path)

```
Transaction: promote_from_tuner_checkpoint() or promote_from_report()
Steps:
  1. Validate report (ConfigValidator.validate())           — NO file write
  2. _execute_promotion():
     a. _build_registry_entry()                            — NO file write
     b. shutil.copy2(out_path, archive_path)               — WRITE: archive
     c. open(out_path, "w"); json.dump(payload, f)         — WRITE: new config   ← NON-ATOMIC
     d. ACTIVE_VERSION.write_text(version)                  — WRITE: pointer     ← SEPARATE WRITE
     e. _log_event() → promotion_log.jsonl.append()        — WRITE: audit log
```

**Atomicity:** NONE — five separate I/O operations
**Rollback:** Archive file exists (step b) but no automatic restore
**Checksum:** SHA-256 computed and stored in registry entry; verified at load
**Concurrent mutation risk:** HIGH — no file locking

**Crash consistency scenarios:**

| Crash after | System state | Recovery |
|---|---|---|
| Step a | Nothing written. No corruption. | Re-run promotion. |
| Step b | Archive created; config unchanged. | Delete orphan archive; re-run. |
| Step c (partial write) | Config JSON corrupted. ACTIVE_VERSION unchanged. | Manual: restore archive; re-run. |
| Step c (complete) | New config written. ACTIVE_VERSION points to old. | `ACTIVE_VERSION.write_text(version)` manually. |
| Step d | Config + pointer updated. Audit log missing. | Safe operationally; governance blind. |
| Step e | No impact — audit only. | Accept missing log entry. |

## Promotion via ShadowPromotionGate (autonomous path)

```
Transaction: ShadowPromotionGate.promote_if_superior()
  1. stage_candidate(patch) → writes candidate.json   — WRITE: candidate (safe)
  2. execute_shadow_test()  → subprocess backtest      — WRITE: shadow_trades.csv
  3. promote_if_superior():
     a. shutil.copy(candidate_path, active_config_path)  ← NON-ATOMIC overwrite
     b. candidate_path.unlink()                           ← SEPARATE DELETE
     c. Returns {"promoted": True/False}
```

**NO rollback.** `shutil.copy()` on Windows opens destination, truncates, writes in chunks. Mid-crash = truncated active config. No temp-file-then-rename pattern. No archive taken before overwrite.

**Tamper risk:** `candidate.json` is written to a fixed path (`configs/production/candidate.json`). Between `stage_candidate()` and `promote_if_superior()`, any process with file access can modify the candidate. The shadow test runs on the staged candidate — a modified candidate passes the performance gate but installs the tampered config.

## SHA-256 Integrity

**Computed:** `hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()`
**Stored:** In registry entry under `config_hash`
**Verified:** At `load_version()` → raises `RuntimeError` if mismatch
**NOT verified:** If `config_hash` field is absent → `warnings.warn()` only, proceeds (fail-open gap)

---

# 9. FALLBACK CORRUPTION GRAPH

## Chain 1: ZoneGate Silent Neutral → Governance Contamination

```
ZoneGate.compute() raises exception (model file missing, corrupt weights)
→ engine_runner.py:546: returns 0.5 (NEUTRAL — SILENT)
→ FusionEngine.compute(): uses 0.5 as zone_gate score
→ final_score = 0.30×crt + 0.25×gaussian + 0.25×0.5 + 0.20×rr
   [effectively: missing gate receives neutral credit]
→ BacktestRunner: trade OPENS (score above threshold)
→ BacktestMetrics: trade counted as valid
→ ConfigValidator.validate(): score includes ghost trades
→ ValidationReport.decision = "APPROVE" [contaminated]
→ PromotionManager: config promoted to production
→ LIVE SYSTEM: runs with ZoneGate still broken, still neutral
```

## Chain 2: FeatureMonitor Silent Disable → Drift Undetected

```
FeatureMonitor.__init__() raises (missing import, bad config)
→ backtest_v2.py: logs ERROR, sets _monitor=None, _monitor_available=False (Phase 2 fix)
→ Drift detection DISABLED for entire backtest run
→ BacktestMetrics: no drift events recorded
→ ValidationReport: distribution["feature_drift"] absent or zero
→ Governance: approves config as if market conditions are stable
→ Live system: deployed to drifting market without drift guard active
```

*(Note: Phase 2 fix changed this from silent to ERROR-level log, but drift detection still disabled)*

## Chain 3: crt_gaussian_scorer.py Silent Defaults → Wrong Thresholds

```
production_config: "gaussian_scorer" section missing or malformed
→ crt_gaussian_scorer.py:36-55: .get() with hardcoded defaults:
    RETEST_MU = 0.237, RETEST_S2 = 0.040, SIGMOID_X0 = 0.50
→ Gaussian scorer runs with hardcoded parameters, not production-tuned values
→ Phase-5 gate: p_win computed with wrong thresholds
→ BacktestRunner: trade open/close decisions contaminated
→ Metrics: artificially high or low win rate depending on defaults vs actuals
→ ConfigValidator: fitness score based on wrong decisions
→ Governance: approves config based on incorrect fitness measurement
```

## Chain 4: Config Dump Swallow → No Audit Trail

```
_full_reg["engine_runner"] raises KeyError (section missing from config)
→ backtest_v2.py config dump: KeyError raised inside try/except
→ log.warning("Config dump skipped: ...")
→ Backtest continues with NO config snapshot written
→ Results directory: metrics + trades exist, but no config record
→ Governance review: cannot verify which config produced which results
→ Auditability: broken — results are orphaned from their config version
```

*(Note: Phase 2-E fix changed .get(key,{}) to [key] — KeyError now propagates. But the outer try/except still catches and logs warning. Config dump failure is still non-fatal by design.)*

## Chain 5: LLM Circuit Open → Invisible Gate Bypass

```
LLM endpoint down for > _FAIL_COUNT_DISABLE requests
→ llm_scorer.py:CIRCUIT_OPEN = True  (Phase 6 fix)
→ llm_score_safe() returns 1.0 for all subsequent calls
→ Fusion: LLM gate contributes neutral 1.0 to all scores
→ Trades that would have been filtered by LLM pass through
→ BacktestMetrics: inflated win count (gate disabled)
→ CIRCUIT_OPEN flag available for caller inspection (Phase 6 fix)
→ If callers don't check CIRCUIT_OPEN: governance contamination continues silently
```

---

# 10. PERFORMANCE / HOT PATH AUDIT

## Per-Candle Hot Loop (BacktestRunner.run())

| Operation | Frequency | Cost | Classification |
|---|---|---|---|
| feature_ts_to_idx lookup | Every TRADE_OPENED candle | O(1) dict lookup | Acceptable |
| FeaturePipeline.run() | Once per BacktestRunner init | O(N×38) batch | Acceptable |
| get_prod_section() | Called at init (Phase 3 fix — now once) | JSON file read + parse | Acceptable |
| CandleLoader.stream() | Per candle | CSV row yield | Acceptable |
| engine.process_candle() | Per candle | CRT state machine | Acceptable |
| CRTGaussianScorer.compute() | Per TRADE_OPENED | Gaussian PDF eval | Acceptable |
| journal.on_trade_closed() | Per TRADE_CLOSED | Arithmetic only | Acceptable |

## Production Config Loading

**`get_prod_section(section)`** (lines 298–334 in `production_config.py`):
- Each call re-reads `configs/production/{version}.json` from disk
- ~10ms per 50KB file — negligible for 1-per-backtest
- **If called per candle** (in live mode): ~10ms × candle_rate = potentially concerning
- NOT VERIFIED whether live_engine_hook.py caches this or calls per-signal

## Model Weight Loading

**BitNetModel:** Loaded once per `__init__()`. Weights cached in `self.model` dict.
**Per-prediction:** Forward pass is O(layers × features) — microseconds per call.
**Other models (Gaussian, RR, TradeNet):** Loading pattern NOT VERIFIED IN SOURCE for hot-path caching.

## O(N²) Risks

- `_aggregate_metrics()`: sum over instruments only — O(N instruments), not O(N²). Acceptable.
- `FusionEngine.compute()`: sum over 4 engines — O(1) effectively. Acceptable.
- `CRTEngine.event_log`: List appended per event. If event_log grows unbounded in long backtests → O(N) memory. **CONCERNING** for multi-year backtests.

## Repeated Deserialization

- `get_prod_section()` reads and parses JSON on every call — NOT VERIFIED as cached in live mode
- Model registry files read once at startup — NOT VERIFIED IN SOURCE

---

# 11. SECURITY SURFACE AUDIT

## CRITICAL: eval() on Feature Expressions

**File:** `src/llm_research/policy_builder.py`
**Lines:** 91 and 131
```python
# Line 91
expr = self._confidence_formula
for k, v in features.items():
    expr = expr.replace(k, str(float(v)))
return max(0.0, min(1.0, float(eval(expr))))  # noqa: S307

# Line 131
expr = condition.replace(" AND ", " and ").replace(" OR ", " or ")
for k in sorted(features.keys(), key=len, reverse=True):
    v = features.get(k, 0)
    expr = expr.replace(k, str(float(v)))
return bool(eval(expr))  # noqa: S307
```

**Attack vector:** If `features` dict keys or values can be influenced by external input (e.g., from model outputs, CSV data, or LLM responses), the string replacement can escape the float() conversion. A crafted feature name or value could inject arbitrary Python code.

**Severity:** CRITICAL if policy_builder receives untrusted feature data.
**Mitigation required:** Replace `eval()` with `ast.literal_eval()` + restricted evaluation or a purpose-built expression parser.

## HIGH: subprocess.Popen() with User-Controlled Args

**File:** `src/control_plane/jobs.py:325`
```python
proc = subprocess.Popen(record.command_line, cwd=str(self._repo_root), ...)
```
`command_line` is built by `build_command_line(spec, merged_args)` where `merged_args` comes from HTTP request body.

**Mitigation:** `shell=False` prevents shell injection. Args are passed as list — OS-level arg separation. BUT: if arg values contain path traversal (`../../etc/passwd`), the called script receives the malicious path.

**Validation gap:** No sanitization of arg values against allowed patterns before command construction.

## MEDIUM: Non-Atomic Config Overwrite

**File:** `src/governance/shadow_promotion_gate.py:235` and `src/governance/promotion_manager.py:556`

Both use direct `open(..., "w")` or `shutil.copy()` — not atomic. A concurrent read during write can return partial JSON, crashing the reader.

**Fix pattern:**
```python
tmp = target.with_suffix(".tmp")
shutil.copy(source, tmp)
os.replace(tmp, target)  # atomic on POSIX; on Windows: atomic if same filesystem
```

## MEDIUM: Candidate Config Tamper Window

Between `stage_candidate()` writing `configs/production/candidate.json` and `promote_if_superior()` reading it, any process with filesystem access can modify the candidate. The shadow test result proves the original candidate's performance, but the modified candidate is promoted.

## LOW: Config Version Path Traversal

**File:** `src/config_layer/production_config.py`
Version string from `ACTIVE_VERSION` file is used to construct `configs/production/{version}.json` path. If ACTIVE_VERSION contains `../`, path traversal occurs.

**Current value:** `v2_multi_2026_04 - deepdeektry` — contains spaces, which is itself anomalous but not path-traversal.

**Mitigation required:** Validate version string matches `[a-zA-Z0-9_-]+` before path construction.

## LOW: JSON Model Poisoning

Model weight files loaded via `json.load()` — safe against code execution (JSON is data-only). BUT: if malformed float values (NaN, Inf) are in weights, they propagate through forward pass, eventually producing NaN gate scores that fall back to neutral.

---

# 12. REPOSITORY-WIDE FAIL-FAST AUDIT

## Confirmed Silent Fallbacks (source-verified)

| # | File | Function | Pattern | Current Behavior | Corruption Risk |
|---|---|---|---|---|---|
| 1 | `engine_runner.py:546` | ZoneGate.check() | `except: return 0.5` | ZoneGate exception → neutral score | HIGH: trades approved with broken gate |
| 2 | `engine_runner.py:619` | RRFusion | `except: use base RR` | RRFusion exception → base score | MEDIUM: RR score less accurate |
| 3 | `engine_runner.py:918` | CognitiveBus | `except: pass` | Async bus emit failure ignored | LOW: intentional (fire-and-forget) |
| 4 | `fusion_engine.py:680` | fusion.evaluate() | `except: fallback to compute()` | Shadow evaluate failure → silent downgrade | MEDIUM: governance scoring diverges |
| 5 | `crt_gaussian_scorer.py:36-55` | Module init | `.get(key, hardcoded)` | Missing config section → hardcoded Gaussian params | HIGH: wrong thresholds in governance |
| 6 | `production_config.py:239` | hash check | `warnings.warn` + proceed | Missing config_hash → no integrity verification | HIGH: tampered config accepted silently |
| 7 | `control_plane/jobs.py:102` | load monitor specs | `except: specs={}` | Monitor config load failure → empty dict | LOW: monitoring broken, startup continues |
| 8 | `control_plane/jobs.py:152` | `_load_existing()` | `except: continue` | Corrupted run files skipped silently | LOW: audit trail incomplete |
| 9 | `crt_engine_v2.py:753` | feature extraction | `.get("disp_str", 0.0)` | Key "disp_str" → should be "disp_strength" | HIGH: wrong feature used in CRT scoring |
| 10 | `feature_pipeline.py:459` | ema_spread | `np.where(atr>0, ..., np.nan)` | NaN when ATR=0 — intentional (finalize drops) | NONE: correct pattern |

## Required Fail-Fast Corrections

**#1 (ZoneGate neutral):** `engine_runner.py:546` — replace `return 0.5` with `raise`. If ZoneGate is mandatory (in EXPECTED_ENGINES), its failure must halt the pipeline.

**#5 (crt_gaussian_scorer):** `crt_gaussian_scorer.py:36-55` — replace `.get(key, default)` with `_require(key)` pattern that raises `KeyError` if section/key missing.

**#6 (hash check):** `production_config.py:239` — replace `warnings.warn` + proceed with `RuntimeError` if `config_hash` field absent.

**#9 (key name):** `crt_engine_v2.py:753` — fix `"disp_str"` → `"disp_strength"`. Verify against actual feature dict keys at runtime.

---

# 13. ENFORCEMENT PLAN

## CI/CD Checks — Required

### AST-based Banned Pattern Scanner

**Target:** Block these patterns from entering `src/governance/`, `src/config_layer/`, `src/core/`, `src/runtime/`

```python
# Banned patterns (AST scan):
BANNED_PATTERNS = [
    "except Exception: pass",                    # bare swallow
    "except Exception:\n    return None",         # sentinel return
    "except Exception:\n    return 1.0",          # neutral fallback
    "except Exception:\n    return {}",           # empty dict fallback
    "eval(",                                      # eval anywhere
    ".get(key, {}) in governance path",           # config section defaults
    "warnings.warn followed by proceed",          # fail-open after warn
]
```

### Registry Validator

**CI check:** Before merge, verify all `CommandSpec.script` targets exist:
```python
for cmd in REGISTRY:
    assert Path(REPO_ROOT / cmd.script).exists(), f"Dead registry entry: {cmd.id}"
```

### Schema Consistency Check

**CI check:** Active model registry entries must declare feature count. Feature count must match `len(CANONICAL_FEATURES)` OR must be explicitly marked as v2.0 with truncation flag.

### Determinism Check

**CI check:** Backtest with seed=42 run twice — outputs must be byte-identical (for seeded slippage path).

### Governance Atomicity Check

**CI check:** Promotion paths must use `os.replace()` not `open("w")` for config writes. AST scan for `open(path, "w")` in `promotion_manager.py` and `shadow_promotion_gate.py`.

### Duplicate Schema Detector

**CI check:** Detect metric keys defined in more than one place with different types or scales. Flag `expectancy_inr` vs `expectancy_rr` cross-system.

## Enforcement Doctrine

```
CI FAILS on:
  - except Exception without re-raise in src/governance/, src/config_layer/, src/core/
  - warning+continue in promotion or validation code
  - registry target file missing at commit time
  - eval() in any file under src/
  - direct open(path, "w") for production config writes
  - .get() with fallback default for required config sections
```

---

# 14. CANONICAL PRODUCTION TRUTH

## What IS the true production path?

### Runtime: CANONICAL
`EngineRunner.run()` in `src/core/engine_runner.py` — the single scoring authority for both live and backtest.

### Metrics: CANONICAL
`BacktestMetrics.to_dict()` from `src/runtime/backtest_v2.py` — authoritative replay truth. All governance decisions must trace to this schema.

### Validator: CANONICAL
`ConfigValidator.validate()` in `src/config_layer/config_validator.py` — the mandatory pre-promotion gate. Any config not passing this is not production-valid.

### Config: CANONICAL
`configs/production/v2_multi_2026_04 - deepdeektry.json` — current active config per `ACTIVE_VERSION` file.

> ⚠️ ANOMALY: The ACTIVE_VERSION value `"v2_multi_2026_04 - deepdeektry"` contains spaces and a dash. The corresponding filename `v2_multi_2026_04 - deepdeektry.json` exists and is a valid JSON file. The name deviation from convention (`v2_multi_2026_04`) may indicate an experimental branch config promoted to ACTIVE unexpectedly. This should be verified with the operator.

### Promotion Path: CANONICAL
`PromotionManager.promote_from_tuner_checkpoint()` — the safe path. Requires `csv_paths` (verified). Always calls `ConfigValidator.validate()`.

**NOT canonical for CLI use:** `promote_from_report()` via CLI is now fixed (Phase 3) to require `--data-dir` and re-validate.

**NOT canonical:** `promote_direct()` — explicitly bypasses validation.

### Replay Engine: CANONICAL
`BacktestRunner` in `src/runtime/backtest_v2.py`.

**NOT canonical:** `backtest_bitnet.py`, `unified_replay_harness.py`, `strategy_backtest.py`.

### Models: CANONICAL (active)
- **Gaussian:** `v5_auto_2026_06_eth` — ETHUSDT, 35-feature v2.0 — `models/ETHUSDT/20260519_113806/gaussian_v5_auto_2026_06_eth.json`
- **RR:** `v5_auto_2026_06_eth2_ethusdt` — ETHUSDT, 35-feature — `models/ETHUSDT/20260519_134711/rr_model_v5_auto_2026_06_eth2.json`
- **TradeNet:** `v5_auto_2026_06_eth` — ETHUSDT, 35-feature — `.pth` (PyTorch)
- **Zone Gate:** `202605_v1_ethusdt` — ETHUSDT, 8 clusters — `models/ETHUSDT/20260519_113806/zone_registry_ETHUSDT_202605_v1.json`
- **BitNet:** NOT VERIFIED IN SOURCE — no registered model in `bitnet_registry.json`

### Conflicts: EXPLICITLY IDENTIFIED

| Conflict | Location | Risk |
|---|---|---|
| Feature schema v2 (35) vs v3 (38) | All active models vs FeaturePipeline | CRITICAL: inference uses wrong feature count |
| ACTIVE_VERSION name with spaces | `configs/production/ACTIVE_VERSION` | HIGH: path construction anomaly |
| 5 replay schemas with no shared serializer | Multiple runtime files | MEDIUM: governance can use wrong metrics |
| ShadowPromotionGate writes active config without atomicity | `shadow_promotion_gate.py:235` | CRITICAL: production mutation risk |

---

# 15. EXECUTION LINEAGE GRAPH

```
[CSV DATA]
    │
    ▼
FeaturePipeline.run() ─────────────────────── 38 features (v3.0)
    │                                              │
    │                          ┌─────────── MODEL INFERENCE
    │                          │         (sliced to 35 for v2.0 models)
    │                          │
    ▼                          ▼
CandleLoader.stream()    [Model Registries]
    │                    gaussian, rr, tradenet, zone_gate
    │
    ▼
BacktestRunner.__init__()
    │  feature_vectors cached
    │  FeatureMonitor initialized
    │  Phase 3/4 config loaded (execution_planner, feature_monitor)
    │
    ▼
BacktestRunner.run() ─── per-candle loop ─────────────────────────
    │                                                              │
    │                                                             CRT state machine
    │                                                             (crt_engine_v2.py)
    │
    On TRADE_OPENED:
    ├── feature lookup (feature_ts_to_idx O(1))
    ├── CRTGaussianScorer.compute() → p_win
    │   ├── LINEAGE BREAK: params from .get() with defaults (chain 3)
    ├── FeatureMonitor.update() → drift check
    └── Optional: EngineRunner.run() (BACKTEST_ENGINE_GATE=1)
    │
    ▼
BacktestMetrics.to_dict()
    │
    ├─────────────────────────────────────────────────────────────
    │                                                             │
    ▼                                                             ▼
ReportWriter output                              ConfigValidator._run_instrument()
{instrument}_trades.csv                          Custom extraction dict
{instrument}_metrics.json                        {score, trades, win_rate, ...}
    │                                                             │
    │                          ┌──────────────────────────────────┘
    │                          ▼
    │               _aggregate_metrics() → final_score
    │               _run_quality_gates() → APPROVE/REJECT
    │                          │
    │               ValidationReport
    │                          │
    │               PromotionManager._execute_promotion()
    │                          │
    │               ┌──────────┴──────────┐
    │               ▼                     ▼
    │        shutil.copy2()        open(out_path,"w")
    │        (archive)             (new config)  ← NON-ATOMIC
    │                                     │
    │                              ACTIVE_VERSION update ← SEPARATE WRITE
    │                                     │
    │                              promotion_log.jsonl append
    │                                     │
    │                    [NEW PRODUCTION CONFIG ACTIVE]
    │                                     │
    ▼                                     ▼
[REPLAY CONTINUES]              [FUTURE BACKTESTS USE NEW CONFIG]
    │
    LINEAGE BREAK: if config changes between replay runs,
    prior results cannot be compared (config version in _trades.csv
    is the only link — requires manual verification)
```

## Lineage Breaks (Verified)

| Break | Location | Impact |
|---|---|---|
| Feature v2/v3 mismatch | All active models | Inference uses wrong feature count |
| crt_gaussian_scorer hardcoded defaults | `crt_gaussian_scorer.py:36-55` | Wrong p_win threshold in validation runs |
| config_hash absent → proceed | `production_config.py:239` | Tampered config accepted without integrity check |
| BitNet model unregistered | `models/bitnet/bitnet_registry.json` | BitNet gate cannot be loaded for scoring |
| ShadowGate no archive before overwrite | `shadow_promotion_gate.py:235` | Prior config lost if promotion crashes mid-copy |
| 5 replay schemas | Multiple files | Cross-schema metric comparison impossible |

---

## APPENDIX: Source File Inventory (verified)

```
src/core/          17 files — engine_runner.py (CANONICAL), fusion_engine.py, decision_engine.py,
                              ultron_risk_gate.py, regime_governor.py, collector.py, model_registry.py, ...

src/config_layer/  13 files — production_config.py (CANONICAL), config_validator.py, crt_engine_v2.py,
                               crt_gaussian_scorer.py, execution_planner.py, llm_scorer.py, llm_inference_client.py, ...

src/governance/    10 files — orchestrator.py (GOVERNANCE_CRITICAL), promotion_manager.py,
                               shadow_promotion_gate.py (DANGEROUS), reflection_buffer_advanced.py,
                               bitnet_governance_executor.py, strategy_backtest.py, ...

src/features/       8 files — feature_pipeline.py (CANONICAL), feature_monitor.py, feature_schema.py, ...

src/runtime/        7 files — backtest_v2.py (CANONICAL), backtest_bitnet.py (EXPERIMENTAL),
                               unified_replay_harness.py (EXPERIMENTAL), live_engine_hook.py, ...

src/bitnet/         8 files — bitnet_inference.py (VALIDATION_CRITICAL), bitnet_runner.py, ...

src/agent/         12 files — plan_compiler.py, intent_router.py, tool_registry.py, executor.py, ...

src/control_plane/  9 files — registry.py (47 CommandSpecs), server.py, jobs.py, dashboard_api.py, ...

src/inout/          2 files — alphavantage_candle_fetcher.py, hummingbot_candle_fetcher.py
                              (NO runner.py — archived)

src/llm_research/   — policy_builder.py (DANGEROUS: eval())
```

---

*This document is source-grounded. Every claim maps to a verified file and line number. "NOT VERIFIED IN SOURCE" is used when source code does not prove a claim.*


================================================================================
SOURCE_FILE: docs/plans/context-current-tradenet-is-jazzy-lemur.md
SOURCE_BYTES: 16187
PART: 2/10 FILE 5/7
================================================================================

> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# TradeNet v2 — 3-Head Survival Classifier

> **Status: KILLED (2026-06-03) — superseded by the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (TradeNet V2 = KILLED; evidence F-001, F-005).** Retained for replay, **not** active work. Reopen only if the Phase-0 economic-edge gate clears **and** wiring TradeNet v1 into the fusion slot earns measured weight (weight-0.0 A/B lift) — and a SESSION LOG entry is filed per `CLAUDE.md §6.2`.

## Context

The current TradeNet is a single-sigmoid binary win/loss classifier. A trade that hits TP1 then gets stopped at breakeven is labeled "LOSS" — same as a trade that never reached 1R. The binary label conflates three distinct survival outcomes and gives the fusion engine a coarse signal.

This patch replaces the output head with three independent sigmoid heads (`p_tp1`, `p_tp2`, `p_survives_be`) on the existing 38-dim canonical feature vector, packages weights in a JSON envelope (mirroring the BitNet `model_contract` pattern), and registers per instrument under an `__active__` map (mirroring the Gaussian versioning pattern that just landed). The composite TradeNet score consumed by `FusionEngine.neural` becomes `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be`.

### Premise corrections vs. the original brief (locked-in)

- **v1 is already 38-dim, not 6-dim.** Input layer unchanged. No "6-feature bottleneck" — that was a misread.
- **Strategy one-hot flags dropped from this patch.** `active_strategies` is not emitted upstream; deferring to a follow-up.
- **`SL-BE` is not an exit_reason in the codebase** ([src/runtime/backtest_v2.py:803](src/runtime/backtest_v2.py)). `survives_be` is synthesized from the `mfe` field in `opportunities_*.jsonl` (confirmed key, value in price units): `survives_be = 1 iff mfe >= 1R` where `1R = abs(entry - sl)`.
- **v1 stores `.pth` PyTorch state_dicts, not JSON envelopes** ([src/training/trainer.py:589-609](src/training/trainer.py)). Legacy bridge handles `.pth` loading explicitly.
- **`min_samples = 500`** (reuses `training_trigger.min_new_samples`), counted on closed records only (exit_reason ∉ {"OPEN", ""}).
- **No `fusion_engine.py` change required.** The composite is computed inside the inference class; the wrapper at [src/training/trainer.py:803-841](src/training/trainer.py) still returns a single float through `FusionEngine.neural`. This is contrary to the brief's "one formula change" — but the brief's goal is achieved without touching fusion_engine.

## Files modified / created

### New
- **`src/training/trade_net_v2.py`** — pure-numpy `TradeNetV2` inference class. JSON envelope loader, 3-head forward pass, MFE-based composite. Legacy `.pth` bridge with `TRADENET_LEGACY_LOAD` integrity event (CRITICAL). Returns `None` when no model for instrument, emits `TRADENET_MISSING` (CRITICAL).
- **`scripts/training/train_trade_net_v2.py`** — PyTorch training script. Reads via existing `TradeDataset.from_opportunities()` ([scripts/training/phase5_calibration.py:382-460](scripts/training/phase5_calibration.py)). Extracts 3-label tensor. Trains 38→32→16→[3 heads] with 3 independent BCE terms. Exports JSON envelope. Registers + promotes via per-instrument registry. `--shadow` skips promotion.

### Modified
- **`src/core/model_registry.py`** — extend the `TradeNetRegistry` portion (already has `register_tradenet` at line 1278). Add `__active__` map migration (mirror Gaussian, lines [350-380](src/core/model_registry.py)). Replace single-active `promote(version)` with `promote(version, *, instrument=None, force=False, max_regression=0.01) -> (bool, str)`. Convenience wrappers at [1285-1298](src/core/model_registry.py) updated. `_default` bucket fallback for entries without instrument tag.
- **`src/training/trainer.py:803-841`** — `make_neural_fn` updated to detect v2 envelope vs. v1 `.pth` and route appropriately. For v2: instantiate `TradeNetV2`, call `predict(features)`, return `tradenet_score` (the composite). For v1: unchanged path. The wrapper signature stays `Callable[[dict], float]`, preserving the FusionEngine contract.
- **`models/tradenet_registry.json`** — schema-extended with `__active__` map; existing per-version entries (with `active: bool`) remain valid via legacy fallback scan.

### Unchanged (verified)
- `src/core/fusion_engine.py` — no change. The `evaluate()` path at [lines 583-606](src/core/fusion_engine.py) already handles `n_score=None` by renormalizing to gaussian-only. The `compute()` 4-engine path doesn't consume TradeNet directly.
- `src/runtime/backtest_v2.py` `TradeRecord` — no change.
- BitNet `model_contract.py` — referenced as the envelope pattern but not imported (mirror, don't depend).
- `configs/production/v1_multi_2026_03.json` — `training_trigger.min_new_samples = 500` reused; no new key.

## Architecture

### v2 net topology (PyTorch, training side)
```
Input         : 38-dim canonical feature vector (no strategy flags in this patch)
Shared trunk  : Linear(38, 32) → ReLU → Dropout(0.2) → Linear(32, 16) → ReLU
Heads (×3)    : Linear(16, 1) → Sigmoid     (one each for p_tp1, p_tp2, p_survives_be)
Loss          : sum of 3 BCELoss(reduction='none') terms, each with per-head class-balanced
                pos_weight = n_neg / n_pos (matches v1 imbalance handling pattern at trainer.py:651-661)
```

### JSON envelope schema (mirroring BitNet `model_contract.py`)
```json
{
  "schema_version":     "tradenet_v2",
  "feature_dim":        38,
  "feature_order_hash": "<sha256[:16] of CANONICAL_FEATURES list>",
  "feature_names":      [...38 names...],
  "trunk": [
    {"type": "linear", "in": 38, "out": 32, "weight": [[...]], "bias": [...]},
    {"type": "relu"},
    {"type": "linear", "in": 32, "out": 16, "weight": [[...]], "bias": [...]},
    {"type": "relu"}
  ],
  "heads": {
    "p_tp1":         {"weight": [[...]], "bias": [...]},
    "p_tp2":         {"weight": [[...]], "bias": [...]},
    "p_survives_be": {"weight": [[...]], "bias": [...]}
  },
  "scaler": {"mean": [...38...], "std": [...38...]},
  "metadata": {
    "instrument": "ETHUSDT",
    "trained_at": "2026-05-21T...Z",
    "n_samples_closed": 1234,
    "n_samples_total": 1500,
    "epochs": 100,
    "class_balance": {"p_tp1": [n_neg, n_pos], "p_tp2": [...], "p_survives_be": [...]},
    "metrics": {"auc_p_tp1": 0.71, "auc_p_tp2": 0.68, "auc_p_survives_be": 0.65}
  }
}
```

### Label extraction (revised vs. brief — `SL-BE` does not exist)
Per record (from `TradeDataset` or `opportunities_*.jsonl`):
```python
exit_reason = rec.get("outcome") or rec.get("exit_reason") or ""
mfe         = float(rec.get("mfe", 0.0))
entry, sl   = float(rec["entry"]), float(rec["sl"])
one_r       = abs(entry - sl)

reaches_tp1   = 1 if exit_reason in ("TP1", "TP2", "TP1_HIT", "TP2_HIT") else 0
reaches_tp2   = 1 if exit_reason in ("TP2", "TP2_HIT") else 0
survives_be   = 1 if (one_r > 0 and mfe >= one_r) else 0   # MFE proxy

# Missing-MFE fallback: emit TRADENET_SURVIVES_BE_UNRESOLVED (INFO), label as 0.
if "mfe" not in rec:
    emit_integrity_event("TRADENET_SURVIVES_BE_UNRESOLVED", "INFO",
                         "trade_net_v2", {"trade_id": rec.get("trade_id")})
```

Note: with MFE-rule, TP1 outcomes will typically have `survives_be=1` (since TP1 is at ≥1R), which differs from the brief's table — but the brief's table was rooted in non-existent SL-BE semantics. The MFE rule is the defensible derivable label.

### Composite score (inside `TradeNetV2.predict`)
```python
def predict(self, features: dict) -> dict:
    vec    = extract_feature_vector(features)              # 38-dim
    vec    = (vec - self.mean) / self.std                  # numpy scaler
    h      = relu(vec @ W1 + b1)                           # 38→32
    h      = relu(h @ W2 + b2)                             # 32→16 (no dropout at inference)
    p_tp1  = sigmoid(h @ W_tp1 + b_tp1)
    p_tp2  = sigmoid(h @ W_tp2 + b_tp2)
    p_be   = sigmoid(h @ W_be  + b_be)
    score  = 0.4*p_tp1 + 0.4*p_tp2 + 0.2*p_be
    return {"tradenet_score": float(score),
            "p_tp1": float(p_tp1), "p_tp2": float(p_tp2),
            "p_survives_be": float(p_be),
            "schema_version": "tradenet_v2"}
```

### Per-instrument registry (mirror Gaussian exactly)
- `models/tradenet_registry.json` gains an `__active__: {INSTRUMENT: version}` meta key on first migration ([model_registry.py:350-380](src/core/model_registry.py) is the Gaussian template — copy structurally).
- `TradeNetRegistry.promote(version, *, instrument=None, force=False, max_regression=0.01) -> (bool, str)`:
  - In-process `threading.RLock`; cross-process `.lock` file via `O_CREAT|O_EXCL`.
  - Resolves instrument from explicit arg → entry's `instrument` field → `_default`.
  - Reads current active from `__active__[instrument]`; falls back to entry-level `active=true` scan with matching `instrument` for pre-migration registries.
  - Deactivates current for THIS instrument only; activates new; updates `__active__[instrument]`.
  - Atomic write via `.tmp` + `os.replace`.
  - GOV-3 single-active-per-instrument guard.
  - Regression guard: blocks if `new_auc_p_tp1 < cur_auc_p_tp1 - max_regression` unless `force=True` (TradeNet uses AUC of `p_tp1` as the primary metric — mirroring Gaussian's `corr_expected_rr` role).

### Legacy `.pth` bridge
`TradeNetV2.__init__(model_path: str | Path, instrument: Optional[str] = None)`:
1. Resolves model path from registry (`__active__[instrument]` → entry → `model_file`).
2. If extension is `.pth` OR loaded JSON lacks `schema_version == "tradenet_v2"`:
   - Emit `TRADENET_LEGACY_LOAD` at **CRITICAL** severity (per user direction: creates operator pressure).
   - Lazy-import torch, load state_dict, build v1 model (38→32→16→1).
   - `predict()` returns `{"tradenet_score": float, "p_tp1": None, "p_tp2": None, "p_survives_be": None, "schema_version": "legacy_v1"}`.
3. If no model for instrument at all (no entry, no `_default`):
   - Emit `TRADENET_MISSING` at **CRITICAL**.
   - `predict()` returns `None`. Existing fusion logic at [fusion_engine.py:599-606](src/core/fusion_engine.py) already handles None by falling back to gaussian-only.

### Training script — minimum-sample gate
```python
closed = [r for r in dataset.trades if r.get("exit_reason", r.get("outcome", "")) not in ("OPEN", "")]
if len(closed) < int(config["training"]["training_trigger"]["min_new_samples"]):  # = 500
    emit_integrity_event("TRADENET_INSUFFICIENT_DATA", "WARNING", "train_trade_net_v2",
                         {"instrument": args.instrument, "n_closed": len(closed), "floor": 500})
    sys.exit(0)
```

### `--shadow` mode (optional, deferrable)
- After training + registering, do NOT promote.
- Iterate the next session's `opportunities_*.jsonl` writes (or replay a recent slice), call v1 + v2 in parallel, append per-trade `{ts, instrument, trade_id, v1_score, v2_composite, v2_p_tp1, v2_p_tp2, v2_p_survives_be, outcome}` to `logs/tradenet_shadow.jsonl` (new file; format mirrors `logs/opportunities_*.jsonl`).
- Compute Spearman rank correlation `p_tp1` vs. `reaches_tp1` across the slice; promote only if correlation > 0 and not worse than v1's `tradenet_score` vs. `outcome` correlation.

## Reuse map (functions/utilities to lean on)

| Existing | Location | Used for |
| --- | --- | --- |
| `extract_feature_vector` | [src/features/dataset_builder.py:38-98](src/features/dataset_builder.py) | Both training-time matrix build and inference-time vector extraction |
| `CANONICAL_FEATURES`, `CANONICAL_FEATURE_DIM` | [src/features/feature_schema.py:46-67](src/features/feature_schema.py) | Feature order canonicalization + envelope hash |
| `StandardScaler` | [src/training/trainer.py](src/training/trainer.py) (existing class with `from_dict` / `to_dict`) | Scaler serialization compatibility with v1 |
| `register_tradenet` | [src/core/model_registry.py:1278](src/core/model_registry.py) | Already accepts `instrument=`; reuse as-is |
| `TradeDataset.from_opportunities` | [scripts/training/phase5_calibration.py:382-460](scripts/training/phase5_calibration.py) | Primary data source (carries `mfe`) |
| `emit_integrity_event` | [src/utils/integrity_events.py:50-96](src/utils/integrity_events.py) | All integrity events (`TRADENET_LEGACY_LOAD`, `TRADENET_MISSING`, `TRADENET_SURVIVES_BE_UNRESOLVED`, `TRADENET_INSUFFICIENT_DATA`) |
| Gaussian promotion mechanics | [src/core/model_registry.py:463-619](src/core/model_registry.py) | Structural template for `TradeNetRegistry.promote` |
| `BitNet build_envelope` shape | [src/bitnet/model_contract.py:59-90](src/bitnet/model_contract.py) | Envelope-shape mirror (do not import) |

## Verification

### Unit-level (the brief's commands, corrected for the locked-in decisions)
```bash
# 1 — label extraction correctness (MFE-based, not exit_reason-only)
python -c "
from scripts.training.train_trade_net_v2 import extract_labels
cases = [
    {'exit_reason': 'TP2', 'mfe': 100.0, 'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=100 → be=1
    {'exit_reason': 'TP1', 'mfe': 2.0,   'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=2   → be=1
    {'exit_reason': 'SL',  'mfe': 0.3,   'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=0.3 → be=0
    {'exit_reason': 'SL',  'mfe': 1.5,   'entry': 100.0, 'sl': 99.0},      # mfe>1R reaches BE → be=1
    {'exit_reason': 'TIMEOUT', 'mfe': 0.5, 'entry': 100.0, 'sl': 99.0},
]
labels = extract_labels(cases)
assert labels[0].tolist() == [1, 1, 1]   # TP2
assert labels[1].tolist() == [1, 0, 1]   # TP1 + mfe>=1R
assert labels[2].tolist() == [0, 0, 0]   # SL without reaching 1R
assert labels[3].tolist() == [0, 0, 1]   # SL but reached 1R first
assert labels[4].tolist() == [0, 0, 0]   # TIMEOUT short of 1R
print('PASS')
"

# 2 — input matrix shape correct (38, not 43)
python -c "
from scripts.training.train_trade_net_v2 import build_input_matrix, INPUT_DIM
recs = [{'features': {k: 0.0 for k in __import__('features.feature_schema').feature_schema.CANONICAL_FEATURES}} ] * 10
X = build_input_matrix(recs)
assert X.shape == (10, 38), X.shape
print('PASS', X.shape)
"

# 3 — legacy .pth bridge loads, emits CRITICAL event, returns single-score result
python -c "
from src.training.trade_net_v2 import TradeNetV2
m = TradeNetV2('models/<existing v1 .pth path>', instrument='ETHUSDT')
out = m.predict({k: 0.0 for k in __import__('features.feature_schema').feature_schema.CANONICAL_FEATURES})
assert out['schema_version'] == 'legacy_v1'
assert out['p_tp1'] is None and out['p_tp2'] is None and out['p_survives_be'] is None
assert 0.0 <= out['tradenet_score'] <= 1.0
print('PASS')
"

# 4 — per-instrument isolation: promoting ETHUSDT does not deactivate EURUSD
python -c "
from src.core.model_registry import TradeNetRegistry
r = TradeNetRegistry()
# register fake v_eth + v_eur; promote each independently; assert __active__ entries don't collide
"

# 5 — short backtest with v1 still active, confirm no regression on ETHUSDT
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 500
```

### Integration
- Run `python -m pytest tests/test_gaussian_update_pipeline.py -q` as the template — write equivalent `tests/test_tradenet_v2_pipeline.py`: registration, promotion blocking on regression, GOV-3 single-active guard per instrument, atomic write under concurrent processes.
- After v2 promotion for one instrument, confirm `FusionEngine.evaluate()` continues to return non-None `neural` score and that the composite is in `[0, 1]`.

### Promotion sequence
```
ETHUSDT:  train → (optional --shadow) → promote
EURUSD:   train → (optional --shadow) → promote
XAUUSD:   train → (optional --shadow) → promote
```
Per-instrument independence is provided by the `__active__` map; failed promotion on one instrument does not affect others.

### Rollback
`promote_tradenet(prior_version, instrument=INSTR, force=True)` — same as Gaussian rollback. Prior versions remain in the registry; no archive needed (versioned-never-overwrite pattern, matches RR / ZoneGate).


================================================================================
SOURCE_FILE: docs/plans/crt-127-0-0-1-get-runs-q-cheeky-blum.md
SOURCE_BYTES: 4423
PART: 2/10 FILE 6/7
================================================================================

> Created: 2026-05-19 · Updated: 2026-05-19 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Configurable UI Poll Interval (default 3 min)

## Context
The control plane UI polls `/runs?q=` and `/monitors/dashboard` every **2 seconds** via a hardcoded `setInterval` in `realApi.js`. The `monitors()` method also fires an uncached fetch on every render. Both behaviours generate excessive server log noise. The user wants the interval configurable (single place to change) and defaulted to **3 minutes (180 000 ms)**. Following project convention, all tunables live in the production config — the server surfaces the value to the frontend at startup via the existing `/commands` response.

---

## Files to change

| File | Change |
|---|---|
| `configs/production/v1_multi_2026_03.json` | Add `"control_plane"` section with `"ui_poll_interval_ms": 180000` |
| `src/control_plane/server.py` | Include `poll_interval_ms` in `commands_payload()` response |
| `ui_kits/control_plane/realApi.js` | Read interval from server, use for `setInterval`; add TTL debounce to `monitors()` |

---

## Step-by-step

### 1. `configs/production/v1_multi_2026_03.json`
Add a new top-level section after `"alphavantage_data"`:
```json
"control_plane": {
  "ui_poll_interval_ms": 180000
}
```
Then re-hash: `python scripts/maintenance/_compute_hash.py`

### 2. `src/control_plane/server.py` — `ControlPlaneAPI.commands_payload()`
Load the section and append `poll_interval_ms` to the response so the frontend gets it on the very first call (startup).

```python
# in commands_payload(), before the return:
try:
    from src.config_layer.config_loader import get_prod_section
    cp_cfg = get_prod_section("control_plane")
    poll_ms = int(cp_cfg.get("ui_poll_interval_ms", 180_000))
except Exception:
    poll_ms = 180_000

return {
    "commands": commands,
    "categories": categories,
    "workflow_stages": list(workflow_stage_order()),
    "poll_interval_ms": poll_ms,
}
```

### 3. `ui_kits/control_plane/realApi.js`

**a) Hold the interval until `/commands` resolves, then start polling:**

Replace lines 56-58:
```js
// Before: hardcoded 2-second poll started immediately
// After: interval driven by server config, started after /commands resolves

let _pollIntervalMs = 180_000;  // fallback until server responds
let _pollTimer = null;

function _startPolling(intervalMs) {
  if (_pollTimer) clearInterval(_pollTimer);
  _pollIntervalMs = intervalMs;
  _pollTimer = setInterval(
    () => Promise.all([_fetchRuns(), _fetchDashboard()]).catch(() => {}),
    _pollIntervalMs
  );
}

// Startup: fetch everything, then start timer with server-provided interval
Promise.all([_fetchCommands(), _fetchRuns(), _fetchDashboard(), _fetchCatalog()])
  .then(() => {
    const cmd = _cache;   // _fetchCommands already stored poll_interval_ms in _cache
    _startPolling(_cache.poll_interval_ms || 180_000);
  })
  .catch(() => { _startPolling(180_000); });
```

Store `poll_interval_ms` in `_cache` inside `_fetchCommands()`:
```js
async function _fetchCommands() {
  try {
    const d = await fetch(BASE + "/commands").then(r => r.json());
    _cache.commands        = d.commands        || [];
    _cache.categories      = d.categories      || [];
    _cache.workflow_stages = d.workflow_stages || [];
    _cache.poll_interval_ms = d.poll_interval_ms || 180_000;  // ← add
    _notify();
  } catch (e) { console.warn("[realApi] fetchCommands failed:", e.message); }
}
```

**b) Debounce `monitors()` with a per-run TTL:**
```js
let _monsTtl = {};  // run_id -> last-fetch epoch ms

monitors(runId) {
  const now = Date.now();
  const stale = !_monsTtl[runId] || (now - _monsTtl[runId]) >= _pollIntervalMs;
  if (stale) {
    _monsTtl[runId] = now;
    fetch(BASE + `/runs/${runId}/monitors`).then(r => r.json()).then(d => {
      _monsCache[runId] = d; _notify();
    }).catch(() => {});
  }
  return _monsCache[runId] || { fields: [] };
},
```

---

## Verification
1. Start server: `python src/control_plane/server.py`
2. Open browser console on the control plane UI — confirm `[realApi] fetchCommands` fires once at startup and `setInterval` uses 180 000 ms
3. Watch server logs for 5 minutes — should see at most 2 poll cycles (one at startup + one at 3 min), not a flood of 2-second calls
4. Re-hash after config change: `python scripts/maintenance/_compute_hash.py`


================================================================================
SOURCE_FILE: docs/plans/crt-engine-20260509-005424-is-empty-chec-parsed-yeti.md
SOURCE_BYTES: 6238
PART: 2/10 FILE 7/7
================================================================================

> Created: 2026-05-09 · Updated: 2026-05-09 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# CRT Engine Log Empty — Root Cause & Fix Plan

## Context

Running `python src/runtime/backtest_v2.py --instrument ETHUSDT --csv data/hummingbot/ETHUSDT_1h.csv` produced `logs/crt_engine_20260509_005424.log` with only 1 line (blank). The user wants to know why.

There are **two independent causes** — one architectural, one config/data mismatch.

---

## Cause 1 — Architectural: Wrong log for backtest path (the direct answer)

**File:** `src/engines/crt_engine.py` lines 14–19

```python
_handler = logging.FileHandler(get_log_path("crt_engine"))   # ← file created at import
_log.addHandler(_handler)
...
def compute(trade_id, features, context):
    ...
    _log.info(json.dumps(...))   # ← only write point
```

The `crt_engine_*.log` is written **only** when `compute()` is called. `compute()` is only invoked by `engine_runner.py` (live/scoring mode). `backtest_v2.py` never calls `engine_runner.py` — it calls `CRTEngine` from `crt_engine_v2.py` directly (the state machine). The file is created at module-import time (when `crt_engine.py` is transitively imported), then never written to.

**Conclusion:** An empty `crt_engine_*.log` is expected in every backtest run. It is not a bug in the log; it is the wrong log to check for backtest diagnostics. The correct logs are:
- `logs/trade_system_20260509_005424.log` — FeaturePipeline, drift, feature health
- `logs/backtest_debug.log` — candle-by-candle state machine trace

---

## Cause 2 — Zero trades: Timeframe × Config mismatch

Active config: `v2_multi_2026_04` — validated **only on EURUSD** M15 data (`validation_summary.instruments: ["EURUSD"]`). Running it against ETHUSDT 1h exposes three compounding problems:

### 2a. HTF window too narrow for 1h data

```
backtest section: htf_candles_per_range = 4
```

On M15 (designed use): 4 candles = 1h HTF — correct.  
On 1h (actual use): 4 candles = 4h HTF — still functional, but every HTF boundary fires every **4 bars**, and the state machine needs RANGE → SWEEP → DISPLACEMENT → EXPANSION before the next boundary (EXPANSION + RETEST are protected from HTF resets; DISPLACEMENT is not).

**Evidence from `should_reset` (`crt_engine_v2.py:1324–1327`):**
```python
if current_htf_id != state.active_range.htf_candle_id:
    if state.current_state in [CRTState.EXPANSION, CRTState.RETEST]:
        return False, ""  # protected
    return True, f"HTF changed: ..."   # DISPLACEMENT → RESET here
```

With a 4-candle window, DISPLACEMENT is frequently blown away before EXPANSION can form.

### 2b. Feature drift on ETHUSDT 1h

From `trade_system_20260509_005424.log`:
```
FeatureMonitor: 258/3548 rows flagged as drift (Z > 2.5 on retest_depth/body_ratio/disp_strength)
FeatureHealth retest_depth | zero_rate=92.22%
```

`retest_depth` is 0 for 92% of candles — the FeaturePipeline's retest feature rarely fires on 1h ETHUSDT data because the state machine was parameterised for M15 EUR volatility.

### 2c. ATR-based gates tuned for M15 EURUSD

```json
"atr_min_displacement": 1.2,     // body must be 1.2× ATR
"expansion_atr_min_distance": 0.3,
"confirmation_body_min": 0.6,
"soft_conf_max_candles": 3       // only 3 hours to confirm on 1h data
```

These thresholds were optimised against EURUSD M15. On 1h ETHUSDT, ATR is ~12× larger in absolute price but structurally similar in percentage terms — so they don't hard-block, but the combination with 2a and 2b means the full 5-stage pipeline never completes.

---

## Proposed Fixes

### Fix A — Quick smoke-test: widen the HTF window

Pass `--htf 16` on the command line. On 1h data, 16 candles = 16h HTF — equivalent to the M15 config's 1h HTF conceptually. No code change required.

```
python src/runtime/backtest_v2.py \
  --instrument ETHUSDT \
  --csv data/hummingbot/ETHUSDT_1h.csv \
  --htf 16
```

`BacktestConfig.from_prod_config` picks this up at `backtest_v2.py:1799`:
```python
if args.htf is not None: cfg.htf_candles_per_range = args.htf
```

### Fix B — Resample to M15 (canonical path)

The system is architected for M15. ETHUSDT 1h data should be resampled to M15 before running the standard backtest. Avoids all parameter-tuning drift.

```
python scripts/data/resample_ohlcv.py \
  --input data/hummingbot/ETHUSDT_1h.csv \
  --output data/hummingbot/ETHUSDT_M15.csv \
  --from 1h --to 15m
```
(If `resample_ohlcv.py` does not exist it needs to be created; no code change to the engine itself.)

### Fix C — Add ETHUSDT to validation instruments and re-tune (medium-term)

To properly support 1h ETHUSDT:
1. Add `"ETHUSDT"` to `configs/production/v2_multi_2026_04.json → validation_summary.instruments`
2. Add a `per_instrument.ETHUSDT` config section with adjusted `atr_min_displacement`, `soft_conf_max_candles`, `htf_candles_per_range`
3. Run `python src/governance/promotion_manager.py promote ...` against ETHUSDT data
4. Re-hash: `python scripts/maintenance/_compute_hash.py`

This is the correct long-term path per `CLAUDE.md §3.1`.

---

## Critical Files

| File | Role |
|---|---|
| `src/engines/crt_engine.py:14–19` | Log file created on import; `compute()` never called from backtest |
| `src/runtime/backtest_v2.py:1344,1432` | Uses `CRTEngine` directly, not `engine_runner` |
| `src/config_layer/crt_engine_v2.py:1324–1327` | HTF reset logic; DISPLACEMENT not protected |
| `configs/production/v2_multi_2026_04.json:303` | `htf_candles_per_range: 4` |
| `logs/trade_system_20260509_005424.log` | Actual diagnostic log (drift warning, feature health) |

---

## Verification

1. **Confirm Cause 1**: `grep -c "" logs/crt_engine_20260509_005424.log` → 1 (blank). Correct; expected.
2. **Test Fix A**: Run with `--htf 16`; check `logs/backtest_debug.log` for `TRADE_OPENED` events.
3. **Confirm Cause 2**: Run with `--htf 16` and check if trade count becomes non-zero. If still zero after HTF fix, the issue is parameter thresholds (Fix C needed).
4. **Check events file**: `results/run_*_ETHUSDT/*_events.jsonl` shows state machine transitions — look for `DISPLACEMENT_CONFIRMED` followed immediately by `RESET` (confirms 2a).
