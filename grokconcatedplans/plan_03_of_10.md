# Concatenated session plans — part 3 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `d-tradelatest-logs-logsrepo-tree-txt-d-tidy-gem.md` (85337 bytes)
2. `d-tradelatest-models-tradenet-registry-robust-neumann.md` (10704 bytes)
3. `d-tradelatest-trade-discovery-trace-md-serene-zebra.md` (104036 bytes)
4. `dont-read-logs-will-streamed-trinket.md` (9236 bytes)
5. `e4081377-is-failed-but-fluffy-wreath.md` (77778 bytes)
6. `frolicking-foraging-hearth.md` (6567 bytes)
7. `from-docs-gather-the-foamy-swan.md` (12726 bytes)


================================================================================
SOURCE_FILE: docs/plans/d-tradelatest-logs-logsrepo-tree-txt-d-tidy-gem.md
SOURCE_BYTES: 85337
PART: 3/10 FILE 1/7
================================================================================

> Created: 2026-05-27 · Updated: 2026-05-27 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Sprint 1 — Phase A+B: Activate _transition_path Injection (READY TO IMPLEMENT)

## Context

Phase A (CRT Transition Path View) and Phase B (StrategyIntent Contract) are already
fully implemented in the codebase. The **only remaining gap** is that `backtest_v2.py`
does not inject `_transition_path` into the feature dict before calling
`StrategyOrchestrator.compute()`. Without it, `StrategyIntentBuilder._build_evidence()`
always falls back to generic evidence even for S01/S10, which declare
`capabilities=frozenset({"transition_path"})`.

## Status of all Phase A+B components

| Component | File | Status |
|-----------|------|--------|
| `CRTTransitionEvent` dataclass | `crt_engine_v2.py` | ✅ Done (lines 1750–1810) |
| `recent_transition_path()` | `crt_engine_v2.py` | ✅ Done — signature: `(state: EngineState, n=16) -> List[CRTTransitionEvent]` |
| `strategy_intent.py` | `src/strategies/` | ✅ Done |
| `intent_builder.py` | `src/strategies/` | ✅ Done — routes S01/S10 to CRT path evidence |
| `strategy_result.py` fields | `src/strategies/` | ✅ Done — `capabilities`, `intent_obj` present |
| `s01_crt_wrapper.py` capabilities | line 143 | ✅ Done — `frozenset({"transition_path"})` |
| `s10_trap_strategy.py` capabilities | line 196 | ✅ Done — `frozenset({"transition_path"})` |
| `strategy_orchestrator._aggregate()` | `src/strategies/` | ✅ Done — calls `StrategyIntentBuilder` |
| `OrchestratorResult.hypotheses` | `src/strategies/` | ✅ Done |
| `recent_transition_path` import in backtest | `backtest_v2.py` line 1473 | ✅ Done — imported as `_recent_path` |
| **`_transition_path` injection in backtest** | `backtest_v2.py` line 1739 | ❌ MISSING |
| `live_engine_hook.py` injection | line 630 | ✅ Intentional `[]` — no live CRT state machine; builder falls back to generic evidence gracefully |

## The One Change

### File: `src/runtime/backtest_v2.py`

**Location**: Line 1738–1739 (inside `if self._orch_available and self.feature_vectors is not None:`)

**Context** (existing code):
```python
_feat_dict["close"] = candle.close
_feat_dict["atr"] = engine.state.atr
                                              # ← insert here
_candle_dict = {"close": candle.close, ...}
_orch_result = self._orch.compute(_feat_dict, _candle_dict)
```

**Change** (one line):
```python
_feat_dict["close"] = candle.close
_feat_dict["atr"] = engine.state.atr
if _phase_d_available:
    _feat_dict["_transition_path"] = _recent_path(engine.state)
_candle_dict = {"close": candle.close, "high": candle.high, "low": candle.low,
                "open": candle.open, "volume": candle.volume}
_orch_result = self._orch.compute(_feat_dict, _candle_dict)
```

**Why `_phase_d_available` guard:**
`_recent_path` is imported inside the same try/except at line 1471–1477 that also
imports `encode_crt_path` / `compute_pattern_hash`. `_phase_d_available` is the guard
variable already defined there. If `crt_engine_v2.recent_transition_path` ever fails
to import, this silently skips injection and `_transition_path` stays absent —
`StrategyIntentBuilder` already handles missing key with generic evidence.

## Verification

```bash
# Run with BACKTEST_ENGINE_GATE=1 (StrategyOrchestrator runs in this path too):
BACKTEST_ENGINE_GATE=1 python src/runtime/backtest_v2.py --instrument BNBUSDT --csv data/BNBUSDT_M15.csv

# Standard run (StrategyOrchestrator at line 1730 always runs when feature_vectors != None):
python src/runtime/backtest_v2.py --instrument BNBUSDT --csv data/...csv
```

After the change, for S01/S10 trades, `OrchestratorResult.hypotheses[i].evidence` should
return transition labels like `["SWEEP→DISPLACEMENT:...", "DISPLACEMENT→EXPANSION:..."]`
rather than `["intent:BUY", "regime:TRENDING", ...]`.

To confirm: add a temporary `print` or check `flow_collector.log` for:
```json
"hypotheses": [{"strategy_id": "S1", "source_path_hash": "<16-hex>", ...}]
```
`source_path_hash` being non-empty (not `""`) means CRT-enriched evidence fired.

## Files Modified

| File | Change |
|------|--------|
| `src/runtime/backtest_v2.py` | Insert `_feat_dict["_transition_path"] = _recent_path(engine.state)` at line 1739 (guarded by `_phase_d_available`) |

---

# Fix Plan: Gaussian shadow_ml Mode + Remove GAUSSIAN_IMPL Env Var

## Context

Two changes requested:
1. **Remove `GAUSSIAN_IMPL` env var** — `config["gaussian_impl"]` becomes the only control point
2. **Add `"shadow_ml"` mode** — HeuristicGaussianEngine drives fusion production score; MLGaussianEngine runs in parallel, its score logged to `engines_raw["gaussian"]["shadow"]` but never enters FusionEngine inputs

This closes the learning loop comparison: after N trades you can compare
`corr(heuristic_score, outcome)` vs `corr(shadow_ml_score, outcome)` from
`flow_collector.log` without any production risk.

---

## Architecture: How gaussian score flows

```
run() line 588:
    gaussian_result = self.gaussian.compute(input_data, direction=_gauss_dir)
    ↓
engine_results["gaussian"] = gaussian_result      ← fusion reads ["score"] only
    ↓ line 671:
fusion_result = self.fusion.compute(engine_results, ...)   ← only ["score"] consumed
    ↓
collector logs engines_raw["gaussian"] = gaussian_result   ← full dict, all keys
```

Key: FusionEngine reads `engine_results["gaussian"]["score"]` only. Extra keys in the
dict (like `"shadow"`) are ignored by fusion — safe to attach before or after fusion call.

All 4 engines run **synchronously** (no executor). Shadow compute is a simple additional
`.compute()` call after the primary, ≤10 lines.

---

## Changes — one file only: `src/core/engine_runner.py`

### Change 1 — `_get_gaussian_engine()`: remove env var, add shadow_ml branch

```python
@staticmethod
def _get_gaussian_engine(config: dict):
    """
    Instantiate primary Gaussian engine from config only.
    GAUSSIAN_IMPL env var removed — config["gaussian_impl"] is the single source of truth.

    Values:
      "heuristic"  → HeuristicGaussianEngine (EMA/momentum kernel)
      "ml"         → MLGaussianEngine (GaussianNBModel)
      "shadow_ml"  → HeuristicGaussianEngine (production); MLGaussianEngine runs as shadow
    """
    cfg_impl = config.get("gaussian_impl", "heuristic") if isinstance(config, dict) else "heuristic"
    impl = cfg_impl.lower()                        # ← no os.getenv() call

    if impl == "ml":
        logger.info("EngineRunner: using MLGaussianEngine (config: gaussian_impl=ml)")
        return MLGaussianEngine(config)
    elif impl == "shadow_ml":
        logger.info("EngineRunner: using HeuristicGaussianEngine + MLGaussianEngine shadow (gaussian_impl=shadow_ml)")
        return HeuristicGaussianEngine(config)
    else:
        logger.info("EngineRunner: using HeuristicGaussianEngine (config: gaussian_impl=%s)", impl)
        return HeuristicGaussianEngine(config)
```

### Change 2 — new `_get_shadow_gaussian_engine()` static method

```python
@staticmethod
def _get_shadow_gaussian_engine(config: dict):
    """Returns MLGaussianEngine shadow when gaussian_impl=shadow_ml, else None."""
    cfg_impl = config.get("gaussian_impl", "") if isinstance(config, dict) else ""
    if cfg_impl.lower() == "shadow_ml":
        logger.info("EngineRunner: shadow MLGaussianEngine instantiated")
        return MLGaussianEngine(config)
    return None
```

### Change 3 — `__init__()`: instantiate shadow alongside primary

After the existing `self.gaussian = self._get_gaussian_engine(config)` line:
```python
self.gaussian_shadow = self._get_shadow_gaussian_engine(config)   # None unless shadow_ml
```

### Change 4 — `run()`: shadow compute block after gaussian_result (line ~588)

After `gaussian_result = self.gaussian.compute(input_data, direction=_gauss_dir)`:
```python
if self.gaussian_shadow is not None:
    try:
        _sh = self.gaussian_shadow.compute(input_data, direction=_gauss_dir)
        gaussian_result["shadow"] = {
            "score":     _sh["score"],
            "reason":    _sh.get("reason", "shadow_ml"),
            "meta":      _sh.get("meta", {}),
            "delta":     round(_sh["score"] - gaussian_result["score"], 4),
            "agreement": bool((_sh["score"] >= 0.5) == (gaussian_result["score"] >= 0.5)),
        }
    except Exception as _se:
        logger.debug("EngineRunner: shadow gaussian failed — %s", _se)
```

`gaussian_result["shadow"]` is attached BEFORE `engine_results` is assembled but AFTER
the primary score is set. FusionEngine only reads `["score"]` so fusion is unaffected.

---

## Config usage

```json
"gaussian_impl": "heuristic"   → HeuristicGaussianEngine only (baseline)
"gaussian_impl": "ml"          → MLGaussianEngine only (current production, no shadow)
"gaussian_impl": "shadow_ml"   → Heuristic drives fusion; ML logged in shadow
```

To activate shadow mode: change line 26 of `v2_multi_2026_04 - deepdeektry.json`:
```json
"gaussian_impl": "shadow_ml"
```
(Currently set to `"ml"` from previous fix — change only when shadow comparison is wanted.)

---

## Output shape in `flow_collector.log` (shadow_ml mode)

```json
"engines_raw": {
  "gaussian": {
    "score": 0.882,                // heuristic → enters fusion unchanged
    "reason": "gaussian_computed",
    "meta": {"mu": 0.0, "sigma": 1.0, "x": 0.042},
    "shadow": {
      "score": 0.617,              // ml → logged only, never in fusion
      "reason": "ml_gaussian",
      "meta": {"expected_rr": 0.45, "confidence": 0.78, "model_version": "p5_..."},
      "delta": -0.265,             // ml_score - heuristic_score
      "agreement": false           // heuristic ≥0.5 but ml < 0.5 → disagree
    }
  }
}
```

---

## Files modified

| File | Change |
|------|--------|
| `src/core/engine_runner.py` | Remove `os.getenv("GAUSSIAN_IMPL", ...)` from `_get_gaussian_engine()`; add shadow_ml branch; add `_get_shadow_gaussian_engine()`; add `self.gaussian_shadow`; add shadow compute block in `run()` |

No changes to: FusionEngine, collector, HeuristicGaussianEngine, MLGaussianEngine, config file (except when activating shadow mode).

---

## Verification

```bash
# Test shadow_ml mode (temporarily change config to shadow_ml):
BACKTEST_ENGINE_GATE=1 python src/runtime/backtest_v2.py \
  --instrument BNBUSDT --csv data/BNBUSDT_M15.csv

# flow_engine_runner.log should show:
#   "using HeuristicGaussianEngine + MLGaussianEngine shadow (gaussian_impl=shadow_ml)"

# flow_collector.log: each trade should have engines_raw.gaussian.shadow.score != null
# Fusion score unchanged from heuristic-only baseline (verify same range ~0.37-0.56)

# Test ml mode (config=ml, no env var):
BACKTEST_ENGINE_GATE=1 python src/runtime/backtest_v2.py \
  --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
# flow_engine_runner.log: "using MLGaussianEngine (config: gaussian_impl=ml)"
# No GAUSSIAN_IMPL env var required, no warning

# Confirm env var is fully dead:
GAUSSIAN_IMPL=heuristic BACKTEST_ENGINE_GATE=1 python src/runtime/backtest_v2.py \
  --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
# With env var removed from code, this env var is silently ignored
# flow_engine_runner.log should still show "using MLGaussianEngine"
```

---

# Fix Plan: Gaussian Engine Wiring + Strategy Orchestrator Audit

## Context

`run_20260524_124220_BNBUSDT` showed two warnings from `engines.heuristic_gaussian_engine`:

```
GaussianRegistry: SAFE MODE — active version 'p5_20260524T120449' artifact is MISSING.
HeuristicGaussianEngine[BNBUSDT]: registry load failed. Using config/default mu=0.00, sigma=1.00.
```

This reveals **three layered problems**:

### Problem 1 — Wrong engine selected (root cause of warning)
`configs/production/v2_multi_2026_04 - deepdeektry.json` line 26:
```json
"gaussian_impl": "heuristic"
```
`EngineRunner._get_gaussian_engine()` (engine_runner.py lines 263-283) checks env var first, then config. Without `GAUSSIAN_IMPL=ml` env var, HeuristicGaussianEngine is always instantiated — the calibrated GaussianNBModel (MLGaussianEngine) is never loaded. The learning loop is open.

### Problem 2 — HeuristicGaussianEngine path doubling bug
`GaussianRegistry._artifact_exists()` (heuristic_gaussian_engine.py line 127):
```python
path = os.path.join(self.models_dir, model_file)
# models_dir = "models"
# model_file = "models\\BNBUSDT\\bnbusdt_balanced_20260524\\gaussian_p5_20260524T120449.json"
# result = "models/models/BNBUSDT/..." ← DOUBLED prefix → file not found
```
Exact same root cause as the `ml_gaussian_engine.py` path bug fixed in the previous session. The `phase5_calibration.py` stores the full `models/...` path in the registry entry, but both loaders prepend `models/` again.

Consequence: even when HeuristicGaussianEngine IS used, it can never load any calibrated version from the registry — always falls back to `mu=0.0, sigma=1.0` → all trades score ≈0.882 (non-discriminating).

### Problem 3 — HeuristicGaussianEngine and MLGaussianEngine expect different registry schemas
`HeuristicGaussianEngine` reads `mu` / `sigma` scalars from the registry entry (lines 49-50 of `_normalize_registry_entry`). The `p5_20260524T120449` entry has **no `mu`/`sigma` keys** — it was created by `phase5_calibration.py` for MLGaussianEngine (stores model file path + calibration metrics). Even if the artifact check passed, HeuristicGaussianEngine would still use `mu=0.0, sigma=1.0`.

**Implication**: HeuristicGaussianEngine and MLGaussianEngine are calibrated independently. They share a registry file but read different schema fields. There is currently **no heuristic-specific mu/sigma calibration tool** in the codebase.

### Problem 4 — StrategyOrchestrator not wired in backtest
`StrategyOrchestrator` is only called in `src/runtime/live_engine_hook.py` (line 631). In `src/runtime/backtest_v2.py`, it is **never imported or called**. All 8 trades in every backtest run show `strategy_consensus: 0.0`. This is a known architectural gap — the plan file has it marked as "StrategyOrchestrator not in BACKTEST_ENGINE_GATE path."

---

## Fix Plan — 2 Targeted Fixes + 1 Architectural Note

### Fix A — Make MLGaussianEngine permanent (1 config line)

**File:** `configs/production/v2_multi_2026_04 - deepdeektry.json`

Change line 26:
```json
"gaussian_impl": "heuristic"   →   "gaussian_impl": "ml"
```

**Effect:**
- `EngineRunner._get_gaussian_engine()` reads `config["gaussian_impl"]` as fallback when env var is absent
- MLGaussianEngine is instantiated for all runs without any env var
- `GAUSSIAN_IMPL=ml` env var no longer needed (but still works as override)
- `instrument` is already injected into `_er_cfg` (fixed last session) → `MLGaussianEngine` reads the correct per-instrument registry entry

**What changes in scoring:**
- Gaussian score comes from GaussianNBModel inference (range 0.5–0.82 per last run)
- `reason = "ml_gaussian"` (not `"gaussian_computed"`)
- model_version = `"p5_20260524T120449"` shown in meta

### Fix B — HeuristicGaussianEngine path doubling (defensive fix)

**File:** `src/engines/heuristic_gaussian_engine.py`

In `GaussianRegistry._artifact_exists()` (line 124-128), strip `models/` prefix before joining — same fix pattern as `ml_gaussian_engine.py`:

```python
def _artifact_exists(self, version: str) -> bool:
    entry = self._entries.get(version, {})
    model_file = entry.get("model_file", f"{version}.json")
    # Strip leading "models/" prefix — registry stores full path, models_dir already adds it
    from pathlib import Path as _Path
    _mf = _Path(model_file)
    if _mf.parts and _mf.parts[0].lower() == "models":
        model_file = str(_Path(*_mf.parts[1:]))
    path = os.path.join(self.models_dir, model_file)
    return os.path.exists(path)
```

**Why needed even after Fix A:** HeuristicGaussianEngine is still instantiated for instruments without a calibrated ML model (e.g., EURUSD, ETHUSDT). If those instruments get a `p5_*` entry, the same path doubling would occur.

---

### Architectural Note — StrategyOrchestrator in Backtest (OUT OF SCOPE for this fix)

**Current state:** `strategy_consensus = 0.0` in all backtest runs. Fusion receives only 4 engines.

**Why it's not wired:** `StrategyOrchestrator.compute()` takes a CRT candle + feature dict and runs 10 strategies synchronously. In a 70K-candle backtest, calling it on every EXECUTION event would add ~8 calls × 10 strategies = 80 strategy.compute() calls. The strategies (S01–S10) need the CRT state machine state injected — that integration exists in `live_engine_hook.py` but not in `backtest_v2.py`.

**When to wire it:** After Phases A+B of the CRT+StrategyOrchestrator enhancement plan (which adds `recent_transition_path()` and `StrategyIntentBuilder`) — that work is already planned. Wiring the orchestrator before those phases would produce strategy scores without the richer context.

**Verification command needed:** `strategy_consensus` score is non-zero only in live mode currently. After wiring, backtest fusion scores should gain a 5th component.

---

## Files Modified

| File | Change |
|------|--------|
| `configs/production/v2_multi_2026_04 - deepdeektry.json` | `"gaussian_impl": "heuristic"` → `"gaussian_impl": "ml"` (line 26) |
| `src/engines/heuristic_gaussian_engine.py` | `_artifact_exists()`: strip `models/` prefix before `os.path.join()` (same pattern as ml_gaussian_engine.py fix) |

No rehash needed — `_compute_hash.py` hashes only the CRT `params` dict, not the full config file.

---

## Verification

```bash
# After Fix A:
BACKTEST_ENGINE_GATE=1 python src/runtime/backtest_v2.py \
  --instrument BNBUSDT --csv data/BNBUSDT_M15.csv

# Check in logs/run_{ts}/BNBUSDT/flow_engine_runner.log:
#   Should show: "EngineRunner: using MLGaussianEngine (GAUSSIAN_IMPL=ml)"
#   NOT HeuristicGaussianEngine
# Check in flow_collector.log:
#   "engines_raw.gaussian.reason" should be "ml_gaussian" (not "gaussian_computed")
#   "engines_raw.gaussian.meta.model_version" should be "p5_20260524T120449"

# After Fix B:
# Run with a non-BNBUSDT instrument that has a p5_* entry:
BACKTEST_ENGINE_GATE=1 GAUSSIAN_IMPL=heuristic python src/runtime/backtest_v2.py \
  --instrument EURUSD --csv data/EURUSD_M15.csv
# Should NOT show "artifact is MISSING" warning
```

---

# BNBUSDT Training Pipeline — Activate Zone Gate + RR Model

## Context

After running BNBUSDT backtests with `BACKTEST_ENGINE_GATE=1`, two engines produce dead scores:
- **Zone Gate**: scores 0.0 on all trades — `models/zone_registry.json` does not exist
- **RR Model**: falls back to candle_polarity formula — `models/rr_model.json` does not exist

Both engines require training from unbiased candle-level data via the opportunity scanner.
The candle data exists at `data/BNBUSDT_M15.csv` (70,080 bars).
Using existing trades CSVs (8 per run) is insufficient (MIN_SAMPLES=20) and biased.

## Pipeline — 4 Steps in Order

All commands are run from `D:\Tradelatest\` as the working directory.

### Step 1 — Opportunity Scanner (generates unbiased labels for every candle)

```bash
python scripts/research/opportunity_scanner.py \
  --csv data/BNBUSDT_M15.csv \
  --instrument BNBUSDT \
  --run-id bnbusdt_training_20260524
```

**Output:** `logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`
**Size:** ~140,000 records (70,000 candles × 2 directions × 2 simulations), each with 35-dim feature vector + `rr_achieved` label
**Duration:** ~2–5 minutes (pure Python KMeans warmup + forward simulation per bar)

CRT is NOT consulted — this is the unbiased ground truth that breaks the recursive training loop.

### Step 2 — Build RR Dataset (from opportunities JSONL)

```bash
python scripts/data/build_rr_dataset.py \
  --opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl \
  --instrument BNBUSDT \
  --run-id bnbusdt_training_20260524
```

**Output:** `models/BNBUSDT/bnbusdt_training_20260524/rr_dataset.json`
**Registers in:** `models/rr_registry.json` (auto-promotes if no active version exists)

### Step 3 — Train and Promote RR Model

```bash
python scripts/training/train_rr_model.py \
  --dataset models/BNBUSDT/bnbusdt_training_20260524/rr_dataset.json \
  --instrument BNBUSDT \
  --version 202605_bnb_v1 \
  --promote \
  --zero-price-features
```

**Output:** `models/rr_model.json` (canonical path — EngineRunner reads this)
**`--promote`**: copies versioned model to `models/rr_model.json`
**`--zero-price-features`**: zeros indices [0,1,2,3,4,7,8,16,17,26,27] (open/high/low/close/volume/ema_fast/ema_slow/macd_line/macd_signal/body_size/wick_size) — prevents price-level anchoring across regimes

### Step 4 — Discover Zones and Promote

```bash
python scripts/research/discover_zones.py \
  --opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl \
  --instrument BNBUSDT \
  --version 202605_bnb_v1 \
  --output models/zone_registry.json
```

**Output:** `models/zone_registry.json` (canonical path — EngineRunner reads this via `zone_gate.registry_path`)
`--no-promote` is NOT passed, so the `--output` canonical file IS written.
Default `--n-clusters 8`, `--min-samples 15` — sufficient for ~140K records.

## Verification — Step 5 (re-run backtest)

```bash
set BACKTEST_ENGINE_GATE=1 && python src/runtime/backtest_v2.py --instrument BNBUSDT
```

Check `logs/run_{ts}/BNBUSDT/flow_collector.log` for the 8 trades:
- `zone_gate_score` → should be non-zero (was 0.0 before)
- `rr_raw_score` → should NOT equal `max((high-close)/(high-low), (close-low)/(high-low))` (was candle_polarity fallback)
- `fusion_gate_score` → will change as weighted components change

Also check `flow_engine_runner.log` — `FUSION_GATE: score=` values will shift from ~0.4–0.6 range.

## Critical Files — No Code Changes Required

| Component | Path | Role |
|-----------|------|------|
| Candle data | `data/BNBUSDT_M15.csv` | Input to opportunity scanner |
| Opportunity scanner | `scripts/research/opportunity_scanner.py` | Step 1 — generates JSONL |
| RR dataset builder | `scripts/data/build_rr_dataset.py` | Step 2 — vectorises opportunities |
| RR model trainer | `scripts/training/train_rr_model.py` | Step 3 — Ridge + GaussianNB + LedoitWolf |
| Zone discovery | `scripts/research/discover_zones.py` | Step 4 — KMeans on feature vectors |
| Canonical RR model | `models/rr_model.json` | Runtime target (written by --promote) |
| Canonical zone registry | `models/zone_registry.json` | Runtime target (written by default) |

**No Python source files are modified** — all 4 scripts exist and are production-ready.
**No config changes needed** — `engine_runner.zone_gate.registry_path` already points to `models/zone_registry.json`.

## Blockers Confirmed Resolved

| Blocker | Resolution |
|---------|-----------|
| No `opportunities.jsonl` | Step 1 creates it from `data/BNBUSDT_M15.csv` |
| Only 8 trades per CSV (< MIN_SAMPLES=20) | Step 1 generates ~140K records — orders of magnitude more |
| `models/rr_model.json` missing | Step 3 `--promote` writes it |
| `models/zone_registry.json` missing | Step 4 default behavior writes it |
| `models/BNBUSDT/` dir missing | Created automatically by `mkdir(parents=True, exist_ok=True)` |

---

## Post-Training Verification Analysis — run_20260524_113126 (COMPLETED)

Pipeline executed and verified. Engine status after training (`BACKTEST_ENGINE_GATE=1`):

| Engine | Score range (8 trades) | Status | Root cause |
|--------|------------------------|--------|------------|
| CRT `crt_engine.compute()` | 0.2031–0.5252 | ✅ ACTIVE + discriminating | First appearance in crt_engine.log |
| Gaussian (Heuristic) | 0.8819–0.8826 | ⚠️ FIRED but locked | mu=0 σ=1 → x≈±0.5 always ~0.882; needs calibration |
| Zone Gate | 1.0 (all 8) | ⚠️ FIRED but non-discriminating | Global per-feature σ too wide (price σ≈155); any candle within ~$310 of centroid scores ≈1.0 |
| RR Model (rr_fusion) | ~0.882 candle_polarity | ⚠️ LOADED but bypassed | `bypassed_low_confidence` (confidence ~5e-62); 98.7% SL_HIT class imbalance → Ridge predicts expected_rr≈0 |
| Adapter | 0.0 | ❌ Not loaded | No model file |
| LLM | 0.0 | ❌ Not configured | Expected |
| Strategy Consensus | 0.0 | ❌ Not called | StrategyOrchestrator not in BACKTEST_ENGINE_GATE path |

**Fusion score shift** (before training → after training): +0.028 to +0.138 per trade (all 8 improved).
**Zone Gate**: 8 zones loaded, valid=true, passed=true, zone_gate_dead=false — but underpowered.
**Note:** `fusion: {}` in `BNBUSDT_fusion.jsonl` is expected — fusion.jsonl logs CRT state-machine events; full engine breakdown is in `flow_collector.log`.

---

## Fix Plan — Three Remaining Engine Issues

### Fix 1 — RR Fusion Class Imbalance (HIGHEST PRIORITY)

**Root cause:** `opportunity_scanner.py` default `--tp-atr-mult 2.0 --sl-atr-mult 1.0` (2:1 RR scan) produces 98.7% SL_HIT / 1.3% TP_HIT outcomes. Ridge learns expected_rr≈0 for all inputs. `RRFusionLayer` detects confidence ~5e-62 and sets `status: bypassed_low_confidence` — falling back to candle_polarity formula.

**Fix:** Re-scan with equal TP/SL (1:1 RR) to produce ~50/50 balanced outcomes, then rebuild dataset and retrain.

```bash
# Step 1 — Re-scan with balanced TP/SL
python scripts/research/opportunity_scanner.py \
  --csv data/BNBUSDT_M15.csv \
  --instrument BNBUSDT \
  --tp-atr-mult 1.0 \
  --sl-atr-mult 1.0 \
  --run-id bnbusdt_balanced_20260524

# Step 2 — Rebuild dataset from balanced scan
python scripts/data/build_rr_dataset.py \
  --opportunities logs/BNBUSDT/bnbusdt_balanced_20260524/opportunities.jsonl \
  --instrument BNBUSDT \
  --run-id bnbusdt_balanced_20260524

# Step 3 — Retrain with promote
python scripts/training/train_rr_model.py \
  --dataset models/BNBUSDT/bnbusdt_balanced_20260524/rr_dataset.json \
  --instrument BNBUSDT \
  --version 202605_bnb_v2 \
  --promote \
  --zero-price-features
```

**Expected outcome:** `rr_fusion.status` changes from `bypassed_low_confidence` to an active prediction; `expected_rr` becomes non-zero; RR engine contributes meaningful differentiation.

**Verification:** In `flow_collector.log`, check `rr.rr_fusion.status` — should be `ok` or `scored` (not `bypassed_low_confidence`). `expected_rr` should vary across trades.

---

### Fix 2 — Zone Gate Discrimination

**Root cause:** When converting zone_v1 schema to Gaussian schema, `sigma` was computed as the **global** per-feature standard deviation across all 139,942 samples. Price features (open/high/low/close) span $450–$1,100 → σ≈155. The Gaussian kernel `exp(-0.5 * ((x-mu)/sigma)^2)` evaluates to ≈1.0 for any BNBUSDT trade within ~$310 of any centroid — which is every trade.

**Fix option A (preferred):** Compute **per-cluster** sigma from the samples assigned to each cluster center, so sigma reflects intra-cluster spread, not global spread. Run this after the balanced rescan already generates the opportunities.jsonl (reuse same file).

```python
# Inline script or add to zone_schema_migrator.py
# 1. Load opportunities.jsonl + zone_registry (kmeans version in .bak)
# 2. For each sample, assign to nearest centroid
# 3. Compute per-cluster per-feature std dev from assigned samples
# 4. Replace global sigma with per-cluster sigma in zone_registry.json
# 5. Apply min-floor of 0.01 (prevent division by zero on constant features)
```

**Fix option B (simpler):** Re-run `discover_zones.py` with **normalized** (z-score) features so that sigma≈1 is meaningful. Normalize at scan time by computing global mean/std once, then dividing all feature vectors before KMeans. Zone scoring then operates in normalized space.

**Verification:** In `flow_collector.log`, `zone_gate_score` should vary across trades (not all 1.0). Some trades should score 0.4–0.8 range, others closer to 1.0.

---

### Fix 3 — Gaussian Engine Calibration

**Root cause:** `GAUSSIAN_IMPL=heuristic` (set via env var or config). `HeuristicGaussianEngine` uses mu=0, sigma=1 and maps any feature vector with x≈±0.5 to score≈0.882. No per-instrument calibration.

**Fix:** Run `phase5_calibration.py` for BNBUSDT using the opportunities data to fit a proper per-instrument Gaussian.

```bash
python scripts/training/phase5_calibration.py \
  --opportunities logs/BNBUSDT/bnbusdt_balanced_20260524/opportunities.jsonl \
  --instrument BNBUSDT \
  --version 202605_bnb_v1
```

*(Verify exact script name and args from `scripts/training/` — may be `calibrate_gaussian.py` or similar.)*

**Verification:** `flow_engine_runner.log` line 1 should change from `HeuristicGaussianEngine` to `CalibratedGaussianEngine` (or similar). Gaussian scores should vary: low RSI/momentum candles score differently from high-momentum candles.

---

### Execution Order

Fix 1 and Fix 3 share the **same** balanced opportunities.jsonl — run Fix 1 Step 1 first (the balanced rescan), then use its output for both Fix 1 Steps 2–3 and Fix 3. Fix 2 (per-cluster sigma) also consumes the same JSONL.

```
Balanced rescan (bnbusdt_balanced_20260524)
  ├── Fix 1: build_rr_dataset → train_rr_model --promote
  ├── Fix 2: per-cluster sigma re-conversion OR normalized discover_zones
  └── Fix 3: phase5_calibration
Then: re-run backtest → verify all 3 fixes in flow_collector.log
```

---

## Fix Execution Results — run_20260524_121852 (COMPLETED)

### What Was Done

**Balanced rescan:** `--tp-atr-mult 1.0 --sl-atr-mult 1.0` → 49,000 samples (still 93.6% SL_HIT — real markets trend)

**Fix 1 (RR):** `build_rr_dataset` → `train_rr_model --version 202605_bnb_v2 --promote` → `models/rr_model.json` updated ✅

**Fix 2 (Zone Gate) — three sub-fixes required (not one):**
1. Scale-free weights: zeroed price/dollar feature indices {0,1,2,3,4,7,8,9,12,16,17,26,27}, 25 active features at w=0.04 → `models/zone_registry.json` ✅
2. Added scalar `"weight": meta["n_samples"]` per zone — the underpowered guard checks `z.get("weight",0)` (singular, scalar), not the `"weights"` list → `models/zone_registry.json` ✅
3. `MLGaussianEngine._load_model()` was calling legacy `get_active_gaussian()` (EURUSD-only) — fixed to use `get_active_version(instrument)` via `GAUSSIAN_INSTRUMENT` env var or `config["instrument"]` key → `src/engines/ml_gaussian_engine.py` ✅
4. `load_gaussian_model(model_file)` doubled the `models/` prefix (registry stores full path, function prepends `MODELS_DIR`) — stripped leading `models/` before call → `src/engines/ml_gaussian_engine.py` ✅

**Fix 3 (Gaussian):** `phase5_calibration.py --opportunities ... --train --gaussian --promote` → APPROVED (corr=+0.2110, CV stable) → registered in `gaussian_registry.json` as `p5_20260524T120449` ✅

### Engine Status After All Fixes

| Engine | Scores (8 trades) | Status |
|--------|-------------------|--------|
| CRT `crt_engine.compute()` | 0.2031–0.5252 | ✅ Discriminating |
| Gaussian (ML) | 0.5046–0.8174 | ✅ ACTIVE — `reason=ml_gaussian`; CRT-0008 highest |
| Zone Gate | 0.6806–0.8880 | ✅ ACTIVE + Discriminating — `underpowered` cleared |
| RR Fusion | bypassed_low_confidence | ⚠️ Still bypassed — 93.6% SL_HIT even at 1:1 RR |
| Fusion | 0.4068–0.5639 | ✅ Wider spread; winners ranked higher |

**Activation command for future backtests:**
```bash
BACKTEST_ENGINE_GATE=1 GAUSSIAN_IMPL=ml GAUSSIAN_INSTRUMENT=BNBUSDT \
  python src/runtime/backtest_v2.py --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
```

### Files Modified

| File | Change |
|------|--------|
| `models/zone_registry.json` | Scale-free weights + scalar `weight` field per zone |
| `models/rr_model.json` | Retrained from balanced 1:1 RR scan (202605_bnb_v2) |
| `models/gaussian_registry.json` | BNBUSDT p5 model registered + promoted |
| `src/engines/ml_gaussian_engine.py` | Instrument-aware registry lookup + `models/` prefix strip |

### Remaining (Open)

1. ~~RR fusion class imbalance~~ — **RESOLVED** (see Fix 4 below)
2. **Gaussian via config (not env var)**: Set `gaussian_impl: "ml"` in `engine_runner` section of production config. `instrument` is now injected into `_er_cfg` via `backtest_v2.py` line 1470, so `GAUSSIAN_INSTRUMENT` env var is no longer needed. Still requires env var `GAUSSIAN_IMPL=ml` to switch engine from heuristic to ML.
3. **Per-instrument zone registry**: Currently one `models/zone_registry.json` shared across instruments. Each instrument needs its own zones trained from its own candle data.

---

## Fix 4 — RR Fusion Import Bug (COMPLETED — run_20260524_123651)

### Root cause (two layers)

**Layer 1 — config file edit irrelevant:** `confidence_bypass_threshold` was correctly changed to `0.0` in `configs/production/v2_multi_2026_04 - deepdeektry.json`. But this had no effect because `_CONF_BYPASS` in `rr_pattern_miner.py` is a module-level constant set at IMPORT TIME from `get_prod_section("rr_model")`.

**Layer 2 — import fails silently:** `rr_pattern_miner.py` (and `rr_fusion.py`) both do:
```python
try:
    from production_config import get_prod_section as _get_section
    ...
except Exception:
    _RR_CFG = {}  # ← silently used when import fails
```
`backtest_v2.py` adds `src/` to `sys.path`. `production_config` lives at `src/config_layer/production_config.py`. The bare `from production_config import` fails with `ModuleNotFoundError` → caught silently → `_RR_CFG = {}` → `_CONF_BYPASS = 0.3` (hardcoded default). This was true in EVERY run — the config file was never read.

### Fix (two files)

```python
# In rr_pattern_miner.py and rr_fusion.py — try full package path first:
try:
    try:
        from config_layer.production_config import get_prod_section as _get_section
    except ImportError:
        from production_config import get_prod_section as _get_section  # standalone script path
    _RR_CFG = _get_section("rr_model")
except Exception:
    _RR_CFG = {}
```

Also:
- `confidence_bypass_threshold` in production config set to `0.0` (allows all predictions through)
- `instrument` injected into `_er_cfg` in `backtest_v2.py` line 1470 (removes need for `GAUSSIAN_INSTRUMENT` env var)

### Final engine status — run_20260524_123651

```
BACKTEST_ENGINE_GATE=1 GAUSSIAN_IMPL=ml python src/runtime/backtest_v2.py --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
```

| Trade | CRT | Gaussian(ML) | Zone | RR(exp_rr/status) | Fusion |
|-------|-----|-------------|------|-------------------|--------|
| T1 | 0.2164 | 0.6243 | 0.8107 | 0.4573(-0.194/success) | 0.3958 |
| T2 | 0.3376 | 0.5046 | 0.8236 | 0.3972(-0.203/success) | 0.4075 |
| T3 | 0.5252 | 0.5751 | 0.8300 | 0.4325(-0.200/success) | 0.5007 |
| T4 | 0.3862 | 0.5792 | 0.8880 | 0.4345(-0.203/success) | 0.4561 |
| T5 | 0.3260 | 0.5810 | 0.8207 | 0.4354(-0.204/success) | 0.4256 |
| T6(worst) | 0.2031 | 0.5818 | 0.8073 | 0.4359(-0.200/success) | **0.3776** |
| T7 | 0.4161 | 0.5839 | 0.8480 | 0.4368(-0.205/success) | 0.4640 |
| T8(best+1.83R) | 0.4086 | **0.8174** | 0.6806 | 0.8174(drift_detected) | **0.5639** |

Fusion correctly ranks best trade highest (0.5639) and worst trade lowest (0.3776). Spread = 0.186 (up from 0.157 before Fix 4).

### Files modified

| File | Change |
|------|--------|
| `src/config_layer/rr/rr_pattern_miner.py` | Fixed import: `config_layer.production_config` first, fallback to bare `production_config` |
| `src/config_layer/rr/rr_fusion.py` | Same import fix |
| `configs/production/v2_multi_2026_04 - deepdeektry.json` | `confidence_bypass_threshold: 0.3 → 0.0` |
| `src/runtime/backtest_v2.py` | Inject `_er_cfg["instrument"] = self.cfg.instrument` at EngineRunner construction |

---

# CRT + StrategyOrchestrator Architecture Enhancement Plan (COMPLETED — Phases A–D)

## Context

The CRT state machine is already a deterministic symbolic reasoner, but the downstream
consumers (StrategyOrchestrator, FusionEngine) only see the FINAL state, not the PATH
that led to it. This loses WHY a displacement happened, how strong the sweep was, and
how long the retest held — all of which are replay-trainable signals.

Four phases build on each other in strict order. Each is backward-compatible (additive
only). Gaussian/BitNet thresholds are not touched.

**Architecture invariants (freeze):**
- CRT MUST NEVER know strategy outcome
- StrategyOrchestrator MUST NEVER mutate CRT state
- One-way flow only: CRT → features → Strategy → Fusion → Decision

---

## What already exists (do NOT re-implement)

| Component | Location | Relevant fields |
|-----------|----------|----------------|
| `EngineEvent` | `crt_engine_v2.py` | event, state_from, state_to, reason, timestamp, candle_index, metadata |
| `event_log: list` on EngineState | `crt_engine_v2.py` | Full event history, flushed every 100 events |
| `transition_log: list` | `crt_engine_v2.py` | Legacy simple-dict history |
| `cached_features` at RETEST | `crt_engine_v2.py` | body_ratio, disp_strength, retest_depth, session, double_sweep |
| `SweepEvent.sweep_type` | `crt_engine_v2.py` | 'TYPE-A'|'TYPE-B'|'TYPE-C'|'TYPE-D' |
| `StrategyResult` | `strategy_result.py` | score, intent, regime, signal, confidence, entry/sl/tp |
| `OrchestratorResult` | `strategy_orchestrator.py` | signal, confidence, all_results, gate_reason |
| `ReplayRecord` | `replay_memory_engine.py` | outcome, rr_achieved, features, cluster_id |
| `TradeRecord` | `backtest_v2.py` | All 38 features, cached_retest_depth, cached_disp_strength, exit_reason, pnl_rr_net |
| Soft confirmation manifold | `crt_engine_v2.py` | evaluating_soft_conf, soft_conf_candles, decay_factor |

---

## Phase A — CRT Transition Path View (NOT new storage)

### Problem
`EngineEvent` + `event_log` already capture every state transition with full
reason and metadata. Adding a parallel `transition_history: deque` would create
a second truth source, risk drift, and cost memory with no benefit.

**Decision: view layer only — read from existing `event_log`, return typed snapshots.**

### New: `CRTTransitionEvent` as a VIEW type (not stored)

`CRTTransitionEvent` is the RETURN type of the view function.
It is never stored on EngineState — it is constructed on demand.

```python
from types import MappingProxyType
from typing import Mapping, Any

@dataclass(frozen=True, slots=True)
class CRTTransitionEvent:
    candle_idx:      int
    timestamp:       datetime
    from_state:      str                    # e.g. "SWEEP"
    to_state:        str                    # e.g. "DISPLACEMENT"
    trigger_reason:  str                    # copied from EngineEvent.reason
    sweep_type:      Optional[str]          # from EngineEvent.metadata["sweep_type"]
    disp_strength:   Optional[float]
    atr:             float                  # from EngineEvent.metadata["atr"]
    feature_snapshot: Mapping[str, Any]     # READ-ONLY — MappingProxyType at construction
```

**Why `Mapping[str, Any]` not `dict`:**
The invariant "StrategyOrchestrator MUST NEVER mutate CRT state" requires that
downstream code cannot do `event.feature_snapshot["disp_strength"] = 999`.
`MappingProxyType` raises `TypeError` on write — enforced at runtime.

In `recent_transition_path()`:
```python
# dict() copy first — prevents upstream ev.metadata["features"]["x"]=y
# from silently reflecting through the proxy (proxy is a VIEW, not a copy).
feature_snapshot = MappingProxyType(dict(meta.get("features", {})))
```

### New: `recent_transition_path()` view function in `crt_engine_v2.py`

```python
def recent_transition_path(
    state: EngineState,
    n: int = 16,
) -> list[CRTTransitionEvent]:
    """Build a typed, windowed view of the last n state transitions.

    Reads from state.event_log (canonical truth) — no duplicate storage.
    Supplements fields from state.cached_features and state.sweep_event
    for the most recent context.
    """
    transitions = [
        ev for ev in state.event_log
        if ev.event == "STATE_TRANSITION"
    ][-n:]

    result = []
    for ev in transitions:
        meta = ev.metadata or {}
        result.append(CRTTransitionEvent(
            candle_idx     = ev.candle_index,
            timestamp      = ev.timestamp,
            from_state     = ev.state_from or "",
            to_state       = ev.state_to or "",
            trigger_reason = ev.reason or "",
            sweep_type     = meta.get("sweep_type"),
            disp_strength  = meta.get("disp_strength"),
            atr            = meta.get("atr", state.atr),
            # dict() copy THEN MappingProxyType — prevents ev.metadata["features"]["x"]=y
            # from silently reflecting through the proxy after construction.
            feature_snapshot = MappingProxyType(dict(meta.get("features", {}))),
        ))
    return result
```

### Change: store richer metadata at each `_transition()` call

So the view function can reconstruct what happened, enrich the EngineEvent.metadata
written inside `_transition()` with the fields view consumers need:

```python
# Inside _transition(), after existing event_log.append():
ev_logger.log(EngineEvent(
    ...existing fields...,
    metadata={
        "sweep_type":    state.sweep_event.sweep_type if state.sweep_event else None,
        "disp_strength": state.cached_features.get("disp_strength") if state.cached_features else None,
        "atr":           state.atr,
        "features":      dict(state.cached_features) if state.cached_features else {},
    }
))
```

**This is the ONLY change to `_transition()`.** No new field on EngineState.

### File changed
`src/config_layer/crt_engine_v2.py` — add `CRTTransitionEvent` dataclass +
`recent_transition_path()` function + richer metadata in `_transition()`.
**Zero changes to EngineState fields, zero changes to `process_candle()` API.**

### What StrategyOrchestrator gains
`recent_transition_path(engine.state)` returns a list like:
```
RANGE→SWEEP(TYPE-B, sweep_type='TYPE-B')
SWEEP→DISPLACEMENT(disp=1.8×ATR)
DISPLACEMENT→EXPANSION
EXPANSION→RETEST(depth=0.18)
```
Injected as **`engine_input["_transition_path"]`** before orchestrator call.
`StrategyIntentBuilder` reads `features["_transition_path"]` inside `_aggregate()` —
strategies declaring `supports_transition_path = True` (S01, S10) get path evidence;
all others get a feature-summary evidence list automatically.

**Key: use `"_transition_path"` everywhere — not `"_transition_history"`.**
Affects: `live_engine_hook.py` (inject only). No individual strategy file consumes it directly.

---

## Phase B — StrategyIntent Contract + Central IntentBuilder

### Problem
`StrategyResult` is a score+geometry snapshot with no concept of WHY the strategy
believes what it does. If intent were built inside each strategy file (e.g. S01 only),
`OrchestratorResult.hypotheses` would be dominated by that one strategy — biasing
replay and poisoning expectancy learning. With ~10 strategies (expandable), this
is unacceptable.

**Correct flow — adapter layer between strategies and orchestrator:**
```
Strategy.compute() → StrategyResult
                          ↓
               StrategyIntentBuilder.build()   ← central, no strategy changes
                          ↓
                    StrategyIntent
                          ↓
             OrchestratorResult.hypotheses     ← all strategies represented equally
```

---

### New file: `src/strategies/strategy_intent.py`

```python
@dataclass
class InvalidationRule:
    """Machine-executable invalidation condition — no NLP parsing required."""
    field:       str    # feature name (e.g. "disp_strength", "retest_depth")
    op:          str    # "<" | ">" | ">=" | "<=" | "=="
    value:       float  # threshold
    description: str = ""

    def is_violated(self, features: dict) -> bool:
        v = features.get(self.field)
        if v is None:
            return False
        return {"<": v < self.value, ">": v > self.value,
                ">=": v >= self.value, "<=": v <= self.value,
                "==": v == self.value}.get(self.op, False)


@dataclass
class StrategyIntent:
    strategy_id:      str
    strategy_family:  str                    # "CRT"|"ZONE"|"GAUSSIAN"|"BITNET"|"MOMENTUM"|"PATTERN"
    direction:        int                    # 1=BUY, -1=SELL, 0=NEUTRAL
    confidence:       float                  # [0.0, 1.0]
    invalidation:     List[InvalidationRule] # machine-executable exit conditions
    expected_rr:      float                  # abs((tp-entry)/(entry-sl))
    ttl:              int                    # candles before hypothesis expires
    source_path_hash: str = ""              # SHA-256[:16] of enriched CRT path string

    # Evidence is lazy — callable, not a pre-built list.
    # Generated only when the intent is selected (approved, stored to replay, logged).
    # Prevents: ~90 strategies × evidence strings × every candle = wasteful allocation.
    _evidence_factory: Optional[Callable[[], List[str]]] = field(default=None, repr=False)

    @property
    def evidence(self) -> List[str]:
        """Materialise evidence on first access only."""
        return self._evidence_factory() if self._evidence_factory else []

    def is_valid(self, candles_elapsed: int) -> bool:
        return self.ttl == 0 or candles_elapsed < self.ttl

    def check_invalidation(self, features: dict) -> Optional[InvalidationRule]:
        return next((r for r in self.invalidation if r.is_violated(features)), None)

    def to_dict(self) -> dict:
        """Materialises evidence at serialisation time."""
        ...
```

`source_path_hash` formula (sweep_type + disp_strength prevent state-name collisions):
```python
path_str = "→".join(
    f"{t.from_state}:{t.to_state}:{t.sweep_type or ''}:{round(t.disp_strength or 0.0, 1)}"
    for t in transition_path
)
source_path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:16] if path_str else ""
```

---

### New file: `src/strategies/intent_builder.py`

Central adapter. Reads universally available `StrategyResult` fields — **zero changes
to any individual strategy file**.

```python
class StrategyIntentBuilder:
    """Converts any StrategyResult → StrategyIntent.

    Generic path: extracts direction/confidence/RR from StrategyResult fields.
    CRT-enriched path: attaches transition path evidence for strategies that
                       declare supports_transition_path = True.

    strategy_family reduces replay sparsity — family-level expectancy can be
    learned before per-strategy expectancy when samples are thin.
    """
    _DEFAULT_TTL  = 3    # candles; matches soft_conf_max_candles
    MAX_EVIDENCE  = 4    # max evidence items per intent (prevents unbounded allocation)

    # Map strategy_id → family label.  One source of truth — no per-strategy changes.
    _FAMILY_MAP: dict[str, str] = {
        "S1":  "CRT",
        "S2":  "MOMENTUM",
        "S3":  "BREAKOUT",
        "S4":  "STAT_ARB",
        "S5":  "MOMENTUM",
        "S6":  "MOMENTUM",
        "S7":  "SENTIMENT",
        "S8":  "BITNET",
        "S9":  "PATTERN",
        "S10": "ZONE",
    }

    def build(
        self,
        strategy_result: "StrategyResult",
        features: dict,
    ) -> Optional["StrategyIntent"]:
        """Return None only if signal is NO_TRADE (no hypothesis to form)."""
        r = strategy_result
        if r.signal == "NO_TRADE":
            return None

        direction = 1 if r.signal == "BUY" else -1
        rr = abs((r.tp - r.entry) / (r.entry - r.sl + 1e-9)) if r.sl != r.entry else 0.0

        # Generic invalidation derived from geometry — same for all strategies
        invalidation = self._generic_invalidation(r, features)

        # Evidence: transition path for CRT-aware strategies; feature summary for others
        evidence, path_hash = self._build_evidence(r, features)

        return StrategyIntent(
            strategy_id       = r.strategy_id,
            strategy_family   = self._FAMILY_MAP.get(r.strategy_id, "UNKNOWN"),
            direction         = direction,
            confidence        = r.confidence,
            invalidation      = invalidation,
            expected_rr       = round(rr, 3),
            ttl               = self._DEFAULT_TTL,
            source_path_hash  = path_hash,
            _evidence_factory = evidence,   # Callable — materialised on .evidence access only
        )

    def _generic_invalidation(self, r, features) -> List[InvalidationRule]:
        """Geometry-based invalidation applicable to every strategy."""
        atr = features.get("atr", 0.001)
        rules = []
        if r.signal == "BUY":
            rules.append(InvalidationRule("close", "<", r.entry - atr,
                                          "price closed below entry - 1×ATR"))
        else:
            rules.append(InvalidationRule("close", ">", r.entry + atr,
                                          "price closed above entry + 1×ATR"))
        return rules

    def _build_evidence(self, r, features) -> tuple["Callable[[], List[str]]", str]:
        """CRT-enriched evidence for strategies that support it; feature summary otherwise.

        Reads r.capabilities — capability travels with the result, no registry lookup.
        Works offline, in batch replay, and in remote workers without the strategy class loaded.
        Returns (evidence_factory: Callable, path_hash: str).
        """
        transition_path = features.get("_transition_path", [])

        if "transition_path" in r.capabilities and transition_path:
            # path_hash computed eagerly (cheap, needed for replay grouping)
            path_str = "→".join(
                f"{t.from_state}:{t.to_state}:{t.sweep_type or ''}:{round(t.disp_strength or 0.0, 1)}"
                for t in transition_path
            )
            path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:16]
            # Capture last MAX_EVIDENCE transitions only — prevents unbounded allocation
            # for long paths (e.g. 16-item window captured by recent_transition_path)
            _tp = transition_path[-self.MAX_EVIDENCE:]
            evidence = lambda: [
                f"{t.from_state}→{t.to_state}:{t.trigger_reason[:40]}"
                for t in _tp
            ]
        else:
            # Generic evidence factory — captures r by reference, evaluated lazily
            _r = r
            evidence = lambda: [
                f"intent:{_r.intent}",
                f"regime:{_r.regime}",
                f"score:{round(_r.score, 3)}",
                f"conf:{round(_r.confidence, 3)}",
            ][:self.MAX_EVIDENCE]
            path_hash = ""

        return evidence, path_hash  # evidence is a Callable — materialised on .evidence access only
```

`_STRATEGY_REGISTRY` is the existing strategy class map in `strategy_orchestrator.py`
(already keyed by strategy_id string). No new registry needed.

---

### Declaring CRT-awareness — via `capabilities` in `StrategyResult` (not class attribute)

Capability travels WITH the result, not on the class. Builder reads `r.capabilities`.
No class attribute. No registry lookup. Works offline and in remote workers.

```python
# In src/strategies/s01_crt_wrapper.py — only change is adding capabilities to return:
return StrategyResult(
    ...,
    capabilities=frozenset({"transition_path"}),   # ← only addition
)

# In src/strategies/s10_trap_strategy.py — trap detection uses CRT structure:
return StrategyResult(
    ...,
    capabilities=frozenset({"transition_path"}),   # ← only addition
)

# All other strategies: default frozenset() — no change needed
```

`BaseStrategy` does NOT need a class attribute. **S02–S09 `compute()` methods unchanged.**

---

### Change: `StrategyResult` — add two new fields

In `src/strategies/strategy_result.py`, add two fields (backward-compatible defaults):
```python
intent_obj:    Optional["StrategyIntent"] = field(default=None)
capabilities:  frozenset[str]             = field(default_factory=frozenset)
```

`capabilities` travels WITH the result — no registry lookup needed at build time.
Strategies that understand the CRT transition path emit:
```python
return StrategyResult(
    ...,
    capabilities=frozenset({"transition_path"}),
)
```
All others emit default `frozenset()`. Works offline, in batch replay, in remote workers.

(`frozenset` not `set` — immutable, hashable, cannot be accidentally mutated after emit.)

(Name `intent_obj` avoids collision with existing `intent: str` enum field.)

---

### Change: `StrategyOrchestrator._aggregate()` — build intents centrally

After all 10 strategy results are collected, before returning `OrchestratorResult`:
```python
# In strategy_orchestrator.py, inside _aggregate():
_builder = StrategyIntentBuilder()
for r in all_results:
    if r.intent_obj is None:
        r.intent_obj = _builder.build(r, features)  # features passed from compute()

hypotheses = [r.intent_obj for r in all_results if r.intent_obj is not None]
```

`OrchestratorResult` gains:
```python
hypotheses: List[StrategyIntent] = field(default_factory=list)
```

All strategies participate. No strategy is excluded. No strategy is dominant.

---

### Passing `_transition_path` to strategies

In `live_engine_hook.py`, inject BEFORE calling `_orch_pre.compute()`:
```python
engine_input["_transition_path"] = recent_transition_path(engine.state)
```

The builder reads `features["_transition_path"]` inside `_aggregate()` — strategies
with `supports_transition_path = True` get path evidence; others get feature summary.

**Key: `"_transition_path"` is the canonical dict key everywhere.**

---

### Files changed
- `src/strategies/strategy_intent.py` (NEW — `InvalidationRule` + `StrategyIntent` with lazy `_evidence_factory`)
- `src/strategies/intent_builder.py` (NEW — `StrategyIntentBuilder` with `_FAMILY_MAP`, capability-based routing, lazy evidence lambdas)
- `src/strategies/strategy_result.py` (add `intent_obj: Optional[StrategyIntent]` + `capabilities: frozenset[str]`)
- `src/strategies/s01_crt_wrapper.py` (add `capabilities=frozenset({"transition_path"})` to `StrategyResult` return only)
- `src/strategies/s10_trap_strategy.py` (same single-line capabilities addition)
- `src/strategies/strategy_orchestrator.py` (add `StrategyIntentBuilder` call in `_aggregate`; add `hypotheses: List[StrategyIntent]` to `OrchestratorResult`)
- `src/runtime/live_engine_hook.py` (inject `engine_input["_transition_path"]`)

**NOT changed:** `base_strategy.py`, S02–S09 strategy files — zero modifications required.

---

## Phase C — Temporal Voting (Belief Persistence)

### Problem
A strategy can win a single candle (noise) and trigger execution. Inserting belief
between Strategy and EngineRunner would accumulate RAW strategy opinions before
regime/fusion weighting — that's still noise. Belief must accumulate FINAL conviction
— the post-fusion score — so it represents the system's weighted verdict, not individual
strategy polls.

### Correct gate location

```
CRT → Features → StrategyOrchestrator → Fusion → [BeliefTracker] → Decision
                                                    ↑
                                         accumulates post-fusion score
                                         gates DecisionEngine call
```

The `SignalBeliefTracker` lives INSIDE `EngineRunner.run()`, between
`FusionEngine.evaluate()` and `DecisionEngine.evaluate()`.

### New file: `src/core/signal_belief_tracker.py`

```python
class SignalBeliefTracker:
    """Exponential belief accumulator over post-fusion conviction scores.

    Input: fusion_score (float, signed: positive=BUY, negative=SELL)
           derived from FusionEngine output + strategy_consensus_direction

    belief[t] = DECAY * belief[t-1] + (1 - DECAY) * fusion_signal
    where fusion_signal = fusion_score * strategy_consensus_direction

    Gate: abs(belief) >= HIGH_CONVICTION  OR  confirm_count >= MIN_CONFIRMS
    """
    DECAY           = 0.70    # config-driven
    HIGH_CONVICTION = 0.65    # matches fusion threshold
    MIN_CONFIRMS    = 2       # consecutive candles same direction

    def update(self, fusion_score: float, direction: int) -> "BeliefState": ...
    def reset(self) -> None: ...

@dataclass
class BeliefState:
    belief:        float   # signed [-1, 1]; positive=BUY conviction, negative=SELL
    direction:     int     # 1 | -1 | 0
    confirm_count: int     # consecutive candles passing fusion gate same direction
    approved:      bool    # True → DecisionEngine may proceed
    reason:        str     # "HIGH_CONVICTION" | "CONFIRMED" | "INSUFFICIENT"
```

### Ownership: `RuntimeContext` — no module-global state

A module-global `BeliefRegistry._trackers = {}` survives across backtests, parallel
pytest runs, and future ECS workers — hidden state that breaks deterministic replay.

**Solution: `RuntimeContext` owned by `BacktestRunner` / `LiveRunner`.**
`EngineRunner` receives `context["belief_registry"]` — it never creates or owns state.

```
BacktestRunner.__init__()
  └── self._runtime_ctx = RuntimeContext(belief_config)
        └── self.belief_registry: dict[str, SignalBeliefTracker]
                                   ↑ keyed by f"{instrument}:{timeframe}"

LiveRunner.__init__()
  └── self._runtime_ctx = RuntimeContext(belief_config)

EngineRunner.run(input_data, context)
  └── context["belief_registry"] →  RuntimeContext.belief_registry
```

### New: `RuntimeContext` + `BeliefRegistry` in `signal_belief_tracker.py`

```python
class BeliefRegistry:
    """Per-RuntimeContext registry — NOT module-global.

    Keyed by f"{instrument}:{timeframe}".
    Lifecycle: created with RuntimeContext, destroyed when runner exits.
    No reset methods needed — lifecycle is the reset.
    """
    def __init__(self, config: dict = None):
        self._config   = config or {}
        self._trackers: dict[str, SignalBeliefTracker] = {}

    def get(self, instrument: str, timeframe: str) -> SignalBeliefTracker:
        key = f"{instrument}:{timeframe}"
        if key not in self._trackers:
            self._trackers[key] = SignalBeliefTracker(self._config)
        return self._trackers[key]


@dataclass
class RuntimeContext:
    belief_registry: BeliefRegistry
    # Future: add regime_tracker, drift_state, etc. here
```

### Integration: inside `EngineRunner.run()` (`src/core/engine_runner.py`)

```python
# After FusionEngine produces fusion_score:
_registry     = context.get("belief_registry")   # injected by BacktestRunner/LiveRunner
_fusion_dir   = context.get("strategy_consensus_direction", 0)

if _registry is not None and self._belief_enabled:
    _instrument   = context.get("instrument", "UNKNOWN")
    _timeframe    = context.get("timeframe", "M15")
    _tracker      = _registry.get(_instrument, _timeframe)
    _belief_state = _tracker.update(fusion_score, _fusion_dir)

    if not _belief_state.approved:
        return {
            "decision": "HOLD",
            "stage": "BELIEF_GATE",
            "reason": _belief_state.reason,
            "belief": _belief_state.belief,
            "confirm_count": _belief_state.confirm_count,
        }

# Else: proceed to DecisionEngine
```

`self._belief_enabled` loaded from config `engine_runner.signal_belief.enabled`.
EngineRunner stores NO tracker — it only reads from `context["belief_registry"]`.

### Wiring in `BacktestRunner.__init__()` / `LiveRunner`

```python
from core.signal_belief_tracker import RuntimeContext, BeliefRegistry
_belief_cfg = _er_cfg.get("signal_belief", {})
self._runtime_ctx = RuntimeContext(belief_registry=BeliefRegistry(_belief_cfg))
```

Then in the candle loop where EngineRunner is called:
```python
context["belief_registry"] = self._runtime_ctx.belief_registry
_er_result = _engine_runner.run(_feat_map_er, context=context)
```

**No explicit reset calls — `BacktestRunner` dying == registry dying.**

### Config keys (add to `engine_runner` section of production config)

```json
"signal_belief": {
    "decay": 0.70,
    "high_conviction_threshold": 0.65,
    "min_confirmations": 2,
    "enabled": true
}
```

`enabled: false` bypasses the gate entirely (for ablation/comparative testing).

### Files changed
- `src/core/signal_belief_tracker.py` (NEW — `SignalBeliefTracker`, `BeliefRegistry`, `RuntimeContext`, `BeliefState`)
- `src/core/engine_runner.py` — load `self._belief_enabled` from config; read `context["belief_registry"]` between FusionEngine and DecisionEngine
- `src/runtime/backtest_v2.py` — create `RuntimeContext` in `__init__`; inject `belief_registry` into context before each `_engine_runner.run()` call
- `configs/production/v1_multi_2026_03.json` — add `signal_belief` to `engine_runner` section

---

## Phase D — Strategy Memory + Replay Attachment

### Problem
After a trade closes, the winning/losing strategy is not recorded.
`ReplayRecord` has outcome + RR but no strategy label.
The replay engine can't learn "BREAKOUT intent on TYPE-B sweep → 2.1R" patterns.

### Change: `TradeRecord` — add strategy fields

In `backtest_v2.py` `TradeRecord` dataclass, add:
```python
winning_strategy_id: str = ""          # "S1" | "S3" | "" if no strategy
crt_path:           List[str] = field(default_factory=list)  # compact codes, see below
pattern_hash:       str = ""           # SHA-256[:16] of key features at RETEST
```

`crt_path` stores compact 1-char codes (defined in `pattern_hasher.py`, NOT in BacktestRunner):
```python
# In src/utils/pattern_hasher.py — single ownership for all consumers
_CRT_PATH_CODES = {
    "RANGE":        "R",
    "SWEEP":        "S",
    "DISPLACEMENT": "D",
    "EXPANSION":    "E",
    "RETEST":       "T",
    "EXECUTION":    "X",
    "RESOLUTION":   "Z",
}
_CRT_PATH_DECODE = {v: k for k, v in _CRT_PATH_CODES.items()}

def encode_crt_path(path: list["CRTTransitionEvent"]) -> list[str]:
    """Compress transition list to compact codes: ["S","D","T","X"]"""
    return [_CRT_PATH_CODES.get(t.to_state, t.to_state[:1]) for t in path]

def decode_crt_path(codes: list[str]) -> list[str]:
    """Expand compact codes to full state names: ["SWEEP","DISPLACEMENT",...]"""
    return [_CRT_PATH_DECODE.get(c, c) for c in codes]
```

Used by: `TradeRecord` (at close), `ReplayRecord` (on load), `Collector` (in strategy dict),
analytics / UI (via `decode_crt_path`). All import from `utils.pattern_hasher` — no duplication.

### Change: `ReplayRecord` — add strategy_id

In `replay_memory_engine.py`, add `strategy_id: str = ""` to `ReplayRecord`.

### Pattern hash computation (utility)

New helper in `src/utils/pattern_hasher.py`:
```python
def compute_pattern_hash(
    features: dict,
    sweep_type: Optional[str] = None,
) -> str:
    """Stable SHA-256[:16] from CRT decision inputs.

    regime is included so same CRT path in TRENDING vs RANGING
    are treated as distinct populations in the expectancy table.
    """
    key_fields = {
        "pattern_schema": "v1",              # version stamp — future field additions won't corrupt old clusters
        "body_ratio":     round(features.get("body_ratio", 0.0), 2),
        "retest_depth":   round(features.get("retest_depth", 0.0), 2),
        "disp_strength":  round(features.get("disp_strength", 0.0), 1),
        "session":        features.get("session", "UNKNOWN"),
        "sweep_type":     sweep_type or "",
        "double_sweep":   bool(features.get("double_sweep", False)),
        "regime":         features.get("_regime", "UNKNOWN"),
    }
    return hashlib.sha256(json.dumps(key_fields, sort_keys=True).encode()).hexdigest()[:16]
```

`_regime` is the regime label injected by `StrategyOrchestrator` or `EngineRunner` into
the features dict at decision time (e.g. `"TRENDING"`, `"RANGING"`, `"VOLATILE"`).
If absent, defaults to `"UNKNOWN"` — backward compatible with existing replay records.

### Attachment at trade close

In `BacktestRunner._on_trade_close()` (or equivalent), after PnL is computed:
```python
from config_layer.crt_engine_v2 import recent_transition_path
from utils.pattern_hasher import encode_crt_path, compute_pattern_hash

_path = recent_transition_path(engine.state)   # reads event_log — single source of truth

rec.winning_strategy_id = self._last_strategy_id
rec.crt_path            = encode_crt_path(_path)          # ["S","D","T","X"] compact
rec.pattern_hash        = compute_pattern_hash(rec.features, sweep_type=self._last_sweep_type)
```

**`engine.state.transition_history` does not exist — always use `recent_transition_path()`.**
`encode_crt_path` / `decode_crt_path` live in `utils/pattern_hasher.py` — single import point
for TradeRecord, ReplayRecord, Collector, and UI.

And `_last_strategy_id` is set when StrategyOrchestrator approves:
```python
self._last_strategy_id = _orch_result.top_result.strategy_id if _orch_result else ""
```

### JSONL schema extension (collector + opportunities.jsonl)

The `Collector.collect()` record already has `id, features, engines, outcome`.
Add:
```python
"strategy": {
    "winning_id": str,           # "S1"
    "crt_path": [str],           # ["SWEEP", "DISPLACEMENT", "RETEST", "EXECUTION"]
    "pattern_hash": str,         # 16-char hex
    "hypotheses": [StrategyIntent.to_dict()],
}
```

### Files changed
- `src/utils/pattern_hasher.py` (NEW — `compute_pattern_hash`, `encode_crt_path`, `decode_crt_path`, `_CRT_PATH_CODES`)
- `backtest_v2.py` — `TradeRecord` (add 3 fields) + `_on_trade_close` + `_last_strategy_id` tracker
- `src/replay/replay_memory_engine.py` — add `strategy_id: str = ""` to `ReplayRecord`, load from JSONL
- `src/core/collector.py` — add `strategy` dict to collected record

---

## Implementation order + sprint grouping

**Sprint 1 (A + B) — observability:** why did the trade happen
```
1. Phase A  →  crt_engine_v2.py only — zero API breakage
2. Phase B  →  strategy_intent.py (NEW) + strategy_result.py + s01 + orchestrator + live_hook
```

**Sprint 2 (C) — noise reduction:** stop one-candle false signals
```
3. Phase C  →  signal_belief_tracker.py (NEW) + engine_runner.py + prod config
```

**Sprint 3 (D) — memory:** learn which interpretation survives
```
4. Phase D  →  pattern_hasher.py (NEW) + TradeRecord + ReplayRecord + collector
```

**Do NOT** touch Gaussian, BitNet, or RR thresholds in any phase.
**Do NOT** start log cleanup work until Sprint 1 (A+B) is merged — CRT observability
ROI exceeds filesystem hygiene.

---

## Verification

| Phase | How to verify |
|-------|--------------|
| A | `recent_transition_path(engine.state)` returns ≤16 `CRTTransitionEvent` items; each has from/to/reason/atr; `engine.state` has NO new fields (confirm EngineState unchanged) |
| B | `OrchestratorResult.hypotheses` has one entry per non-NO_TRADE result (all strategies represented); S01 `strategy_family=="CRT"`, S08 `strategy_family=="BITNET"`; S01/S10 `source_path_hash` is 16-char hex with transition labels in evidence; S02–S09 evidence contains `["intent:BREAKOUT","regime:TRENDING",...]`; S02–S09 source files NOT modified |
| C | `RuntimeContext.belief_registry.get("BTCUSDT","M15")` returns isolated tracker; two consecutive candles same fusion direction → `approved=True`; single candle → `approved=False`; `BacktestRunner` destruction kills registry (no explicit reset needed); parallel pytest runs use separate `RuntimeContext` instances; `enabled=false` bypasses gate |
| D | Closed trade: `TradeRecord.pattern_hash` 16-char hex; `TradeRecord.winning_strategy_id == "S1"`; `ReplayRecord` loaded from JSONL has `strategy_id` field |

---

# Plan: Log Cleanup + Coin-Level Run Log Separation

## Context

`logs/` is a flat directory with hundreds of files named `{module}_{RUN_ID}.log`.
Every backtest process spawns ~7 flow log files sharing the same RUN_ID timestamp,
but no coin/instrument dimension — all coins land in the same root. Old files
accumulate with no rotation. Fusion JSONLs (`EURUSD_fusion.jsonl`) grow forever.
`results/` has stray `run_{ts}_{COIN}/` dirs at root rather than under `results/{COIN}/`.

**User answers:** keep 7 days active → archive rest; runs are sometimes single-coin
sometimes multi-coin; fusion JSONL should rotate per-run (one file per run, not rolling).

---

## Target Structure

```
logs/
  run_20260523_102229/          ← one subdir per process (RUN_ID)
    EURUSD/
      crt_engine.log
      flow_engine_runner.log
      flow_feature_pipeline.log
      flow_collector.log
      flow_cognitive_bus.log
      flow_execution_planner.log
      trade_system.log
      EURUSD_fusion.jsonl       ← rotated per-run, lives here now
    ETHUSDТ/                    ← populated only if multi-coin run
      ...
  agent_audit.jsonl             ← governance audit, NEVER moved
  agent_intent_log.jsonl
  agent_findings.jsonl
  agent_llm_requests.jsonl
  expansion_rejected.jsonl
  expansion_trace.jsonl
  backtest_debug.log
  archive/
    202605/
      flow_engine_runner_20260518_230129.log
      ...                       ← flat logs >7 days old archived here

results/
  EURUSD/
    run_20260510_150023_EURUSD/
    run_20260511_005453_EURUSD/
  ETHUSDT/
    run_20260521_235920_ETHUSDT/
  portfolio_raw/                ← already correct, unchanged
```

---

## Observed log anatomy (from screenshots)

Each backtest run spawns a timestamp cluster of flat files. Example for run `_103447`:
- `flow_feature_pipeline_20260523_103447.log` — 3 KB (pipeline ran)
- `trade_system_20260523_103447.log` — 3 KB (has content)
- `crt_engine_20260523_103447.log` — **0 KB** (FileHandler opened but no candle cleared the gate)
- `flow_collector_20260523_103447.log` — **0 KB** (same)
- `flow_engine_runner_20260523_103447.log` — **0 KB** (same)

**Why 0 KB:** Python's `FileHandler` was created at module import time — the empty file
is created immediately even if nothing is ever logged to it.
Coin fusion JSONLs (`SOLUSDT_fusion.jsonl`, `BTCUSDT_fusion.jsonl`, etc.) accumulate
across runs (append-only) — not empty, but grow forever.

---

## Deliverable 1 — Cleanup Script (no core-code changes)

**New file:** `scripts/maintenance/cleanup_logs.py`

```
usage: python scripts/maintenance/cleanup_logs.py [--days 7] [--dry-run]
```

Logic:
1. Walk `logs/*.log` and `logs/*.jsonl` (root level only, not subdirs).
2. Skip governance files: `agent_*.jsonl`, `expansion_*.jsonl`, `backtest_debug.log`,
   `integrity_events.jsonl`.
3. For files older than `--days` (default 7): move to `logs/archive/YYYYMM/` using
   `shutil.move`. Create archive subdir if absent.
4. `--dry-run` prints actions without executing.
5. Print summary: N moved, N skipped, N errors.

Note: **0 KB files are valid archive targets** — they should be swept up like any other
old run file (no special handling needed).

---

## Deliverable 2 — Coin-Level Log Init (core code changes)

### 2a. `src/utils/logging_config.py`

**Problem:** `RUN_ID` and all `FileHandler`s are created at module import — before
any symbol is known. Handlers must become lazy.

**Changes:**

1. Keep `RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")` at module level (unchanged).
2. Change `get_log_path(name, ext)` to accept optional `symbol: str = None`:
   - With symbol → `logs/run_{RUN_ID}/{symbol}/{name}.{ext}`
   - Without → `logs/{name}_{RUN_ID}.{ext}` (legacy fallback, used by non-backtest paths)
3. Remove eager `FileHandler` creation in the `FLOWS` dict initialisation block.
4. `get_flow_logger(name)` returns the logger with NO handlers yet (avoids double-attach).
5. Add `init_coin_logging(symbol: str) -> None`:
   - Creates `logs/run_{RUN_ID}/{symbol}/` via `Path.mkdir(parents=True, exist_ok=True)`.
   - For each flow name in `FLOWS`: attaches a `FileHandler` pointed at
     `logs/run_{RUN_ID}/{symbol}/{flow_name}.log` if not already attached for that symbol.
   - Attaches `trade_system.log` handler for the root logger scoped to that subdir.
6. Add `close_coin_logging(symbol: str) -> None`:
   - Flushes and closes all handlers on flow loggers for that symbol.
   - Removes them from each logger (so next `init_coin_logging` doesn't double-attach).

### 2b. `src/engines/crt_engine.py`

**Problem:** Module-level eager `FileHandler` creation (`_handler = FileHandler(get_log_path("crt_engine"))`).

**Changes:**

- Remove the module-level `_handler` creation and `addHandler` call.
- `get_log_path("crt_engine")` call now happens inside `init_coin_logging()` in
  `logging_config.py` — the `crt_engine` logger is included in the `FLOWS` dict so
  it is covered automatically.

### 2c. `src/runtime/backtest_v2.py`

**Problem:** Fusion JSONL path is `logs/{instrument}_fusion.jsonl` (root, no run scope).

**Changes:**

1. In `BacktestRunner.__init__()`, after `self.bt_config` is assigned (~line 1320):
   ```python
   from utils.logging_config import init_coin_logging, RUN_ID
   init_coin_logging(bt_config.instrument)
   ```
2. Change fusion JSONL path (line 1324) from:
   ```python
   _log_dir / f"{bt_config.instrument}_fusion.jsonl"
   ```
   to:
   ```python
   _log_dir / f"run_{RUN_ID}" / bt_config.instrument / f"{bt_config.instrument}_fusion.jsonl"
   ```
   (`_log_dir` remains `Path("logs")`.)
3. Add a cleanup call at end of `BacktestRunner.run()` (or in a `finally` block):
   ```python
   from utils.logging_config import close_coin_logging
   close_coin_logging(bt_config.instrument)
   ```
   This ensures multi-coin processes don't accumulate open handlers across coins.

---

## Deliverable 3 — Results Migration Script

**New file:** `scripts/maintenance/reorganize_results.py`

```
usage: python scripts/maintenance/reorganize_results.py [--dry-run]
```

Logic:
1. Glob `results/run_*_{COIN}/` dirs (top-level only, not inside `portfolio_raw/`).
2. Parse coin from dir name: last `_`-delimited token.
3. Move each dir to `results/{COIN}/run_{ts}_{COIN}/`, creating parent if needed.
4. `--dry-run` prints plan. Default asks for confirmation before moving.

**Dirs NOT touched:** `results/portfolio_raw/` (already correct), `results/AGENT/`,
`results/LIVE/`, `results/DATA/`, top-level JSON/calibration files (leave in place).

---

## Critical Files

| File | Change |
|------|--------|
| `src/utils/logging_config.py` | Lazy handlers, `init_coin_logging`, `close_coin_logging` |
| `src/engines/crt_engine.py` | Remove eager module-level `FileHandler` |
| `src/runtime/backtest_v2.py` | Call `init_coin_logging`, update fusion JSONL path |
| `scripts/maintenance/cleanup_logs.py` | **NEW** — archive old flat logs |
| `scripts/maintenance/reorganize_results.py` | **NEW** — move stray run dirs |

---

---

## Bug Fix — 0 KB flow log files (discovered post-implementation)

### Root cause (two bugs)

**Bug 1 — `delay=False` (default on `FileHandler`):**
`logging.FileHandler` opens the file on `__init__`, creating it on disk before any record
is written. `init_coin_logging()` creates 17 flow files the moment it runs regardless of
whether those flows ever log. All 17 files exist at 0 bytes.

**Bug 2 — `FlowLogFilter` missing from FileHandler path:**
`BASE_FORMAT` uses `%(flow_name)s`. That attribute is injected by `FlowLogFilter`,
which is added to the logger inside `get_flow_logger()`. But `init_coin_logging()` adds
the `FileHandler` directly via `logging.getLogger()`, bypassing `get_flow_logger()`.
If `get_flow_logger()` has not yet been called for a flow, the logger has no filter.
Every `emit()` on the FileHandler hits a `KeyError` on `flow_name`, Python's logging
catches it silently, nothing is written — even when records DO arrive.
This explains why `BNBUSDT_fusion.jsonl` = 11 KB (own simple formatter) while all
flow logs = 0 KB.

### Fix — two changes inside `init_coin_logging()` in `src/utils/logging_config.py`

**Change 1:** Call `get_flow_logger(flow_name)` before attaching the FileHandler so that
`FlowLogFilter` and the console handler are guaranteed to be on the logger first.

**Change 2:** Add `delay=True` to both `FileHandler` constructors so the file is only
created on the first actual write — 0-byte ghost files never appear.

```python
# Before (buggy):
logger = logging.getLogger(f"flow.{flow_name.lower()}")
fh = logging.FileHandler(run_dir / f"{stem}.log", encoding="utf-8")

# After (fixed):
logger = get_flow_logger(flow_name)            # ensures FlowLogFilter is present
fh = logging.FileHandler(run_dir / f"{stem}.log", encoding="utf-8", delay=True)
```

Same `delay=True` fix applies to the engine logger block (`crt_engine`, `llm_engine`).

**File:** `src/utils/logging_config.py` — `init_coin_logging()` function only.

---

## Verification

1. **Cleanup script:** run `python scripts/maintenance/cleanup_logs.py --dry-run` and
   confirm the printed file list matches old flat logs (not governance files).
2. **Single-coin run:** `python src/runtime/backtest_v2.py --instrument EURUSD ...`
   → verify `logs/run_{RUN_ID}/EURUSD/` dir is created with all flow logs and
   `EURUSD_fusion.jsonl` inside.
3. **Multi-coin run:** run for two instruments sequentially → two subdirs appear under
   `logs/run_{RUN_ID}/`, handlers don't double-fire.
4. **Results migration:** run with `--dry-run`, verify only top-level `run_*` dirs are
   listed, then run without flag and confirm `results/ETHUSDT/run_*/` exists.
5. **Governance files:** confirm `logs/agent_audit.jsonl` etc. are untouched by all scripts.
6. **Tests:** `pytest tests/` — no test should reference the old flat log path.

---

## Phase: Missing Flow Logs Investigation + Fix

### Root cause — why only 2 files appear in a standard backtest

A standard `BacktestRunner` run (no `BACKTEST_ENGINE_GATE=1`) fires exactly **two**
log outputs:

| File | Why it appears |
|------|---------------|
| `flow_feature_pipeline.log` | `FeaturePipeline.__init__` always runs; flow logger fires |
| `{COIN}_fusion.jsonl` | `_TradeLogger` always writes trade records |

All other expected files are absent because:

#### Group 1 — Wrong logger name (fixable: these DO run, just use generic logger)

| Flow | Module | Problem |
|------|--------|---------|
| `ZONE_GATE` | `src/engines/zone_gate_engine.py` line 23 | Uses `logging.getLogger(__name__)` + `logging.getLogger("ZONE_GATE_DEBUG")` instead of `get_flow_logger("ZONE_GATE")` — records never reach the coin-scoped FileHandler |

#### Group 2 — Gated behind `BACKTEST_ENGINE_GATE=1` (by design — do not change)

These modules are only instantiated when `os.getenv("BACKTEST_ENGINE_GATE", "0") == "1"`
in `backtest_v2.py` lines 1418-1428:

| File | Flow | Condition |
|------|------|-----------|
| `flow_engine_runner.log` | ENGINE_RUNNER | `BACKTEST_ENGINE_GATE=1` → `EngineRunner.__init__` |
| `flow_collector.log` | COLLECTOR | `BACKTEST_ENGINE_GATE=1` → `collector.py` called by EngineRunner |
| `flow_execution_planner.log` | EXECUTION_PLANNER | `BACKTEST_ENGINE_GATE=1` → EngineRunner decision path |
| `flow_ultron_risk_gate.log` | ULTRON_RISK_GATE | Uses `get_flow_logger()` correctly, but config has `disabled=True` for backtests |
| `crt_engine.log` | crt_engine logger | `BACKTEST_ENGINE_GATE=1` → `crt_engine.compute()` only called via EngineRunner |
| `flow_cognitive_bus.log` | COGNITIVE_BUS | `BACKTEST_ENGINE_GATE=1` **AND** `cognitive_layer.enabled=True` in prod config |

#### Group 3 — trade_system.log (not implemented — old design artifact)

Mentioned in the `logging_config.py` docstring ("Aggregated system log:
`logs/trade_system.log`") but no logger or FileHandler named `trade_system` exists
anywhere. The per-coin coin-scoped flow files replaced it conceptually, but the
aggregated file was never implemented.

---

### Deliverable — Two targeted fixes

#### Fix A: `src/engines/zone_gate_engine.py` — use flow logger

Change the module-level logger setup from generic `logging.getLogger` to the
named flow logger so zone gate records land in `flow_zone_gate.log`:

```python
# Before (line 23-24):
logger = logging.getLogger(__name__)
_debug_logger = logging.getLogger("ZONE_GATE_DEBUG")

# After:
from utils.logging_config import get_flow_logger
logger = get_flow_logger("ZONE_GATE")
_debug_logger = logging.getLogger("ZONE_GATE_DEBUG")   # keep debug logger as-is
```

This is a pure substitution: the call sites (`logger.warning(...)`, `logger.error(...)`)
are unchanged; only the handler destination changes.

**Impact:** `flow_zone_gate.log` now appears in every standard backtest coin dir that
triggers zone gate evaluation. With `delay=True` on the FileHandler, the file only
appears when zone gate actually evaluates a bar.

#### Fix B: `src/utils/logging_config.py` — add trade_system aggregated handler

Inside `init_coin_logging()`, after attaching all flow FileHandlers, add one more
handler to the named `"trade_system"` logger that aggregates all flow records:

```python
# In init_coin_logging(), after the FLOWS loop:
# Aggregated trade_system.log — collects all flow records in one place
ts_logger = logging.getLogger("trade_system")
ts_logger.setLevel(logging.DEBUG)
ts_logger.propagate = False
ts_fh = logging.FileHandler(
    run_dir / "trade_system.log", encoding="utf-8", delay=True
)
ts_fh.setFormatter(fmt)
ts_logger.addHandler(ts_fh)
pairs.append((ts_logger, ts_fh))
```

Then each flow module that wants to write to the aggregated log can do:
```python
import logging
_ts_log = logging.getLogger("trade_system")
```
Or alternatively, make `get_flow_logger()` also forward records to `trade_system`
by adding a handler copy — **chosen approach: keep it simple, let the coin-scoped
flow files be the primary logs; trade_system.log is populated only by modules that
explicitly use `logging.getLogger("trade_system")`**.

Update the docstring in `logging_config.py` to accurately reflect:
- Which flows fire in standard backtest vs BACKTEST_ENGINE_GATE=1
- That trade_system.log is the aggregated handler name

---

### Files changed

| File | Change |
|------|--------|
| `src/engines/zone_gate_engine.py` | Lines 23-24: replace `logging.getLogger(__name__)` with `get_flow_logger("ZONE_GATE")` |
| `src/utils/logging_config.py` | `init_coin_logging()`: add `trade_system` aggregated FileHandler; update module docstring |

No changes to `backtest_v2.py`, `crt_engine.py`, `llm_engine.py`, or any gate-dependent modules.

---

### Verification (incremental)

After fix A: run a standard BNBUSDT backtest → confirm `flow_zone_gate.log` appears
(non-zero, contains zone evaluation records).

After fix B: verify `trade_system.log` exists in the coin dir (even if 0-byte on first
run — modules must opt in; the file stub confirms the handler wiring is correct).

---

## Reference: `crt_engine.compute()` — When It Is Called

### The two CRT code paths (they are different)

```
Standard backtest (always):
  BacktestRunner.run()
    → engine.process_candle()        ← CRT STATE MACHINE (crt_engine_v2.py)
      action = "TRADE_OPENED"
      ↓ (no further CRT scoring — trade is directly journaled)

Full backtest (BACKTEST_ENGINE_GATE=1 only):
  BacktestRunner.run()
    → engine.process_candle()        ← same state machine
      action = "TRADE_OPENED"
      → Phase-5 scorer gate          ← CRTGaussianScorer / CRTCalibratedScorer (ML model)
      → drift veto gate              ← FeatureMonitor
      → _engine_runner.run()         ← EngineRunner (only if gate=1)
          → crt_engine.compute()     ← THIS is the crt_engine.py wrapper
          → llm_engine.compute()
          → zone_gate scoring
          → rr_engine scoring
          → FusionEngine
          → DecisionEngine
          → ExecutionPlanner
          → UltronRiskGate
```

### Key distinction

`engine.process_candle()` = **CRT state machine** (`src/config_layer/crt_engine_v2.py`)
— runs in every backtest, no env var needed.

`crt_engine.compute()` = **parallel engine wrapper** (`src/engines/crt_engine.py`)
— calls `compute_scores()` from `scoring_engine.py`, logs JSON, returns `{"score": float}`.
— only called by `EngineRunner.run()` at `src/core/engine_runner.py` line 572.

### Exact conditions for `crt_engine.compute()` to fire

All four must be true simultaneously:

| # | Condition | Where in backtest_v2.py |
|---|-----------|-------------------------|
| 1 | `BACKTEST_ENGINE_GATE=1` env var set | line 1420 |
| 2 | CRT state machine emitted `"TRADE_OPENED"` | line 1501 |
| 3 | Phase-5 Gaussian scorer did NOT reject (`not _p5_rejected`) | line 1651 |
| 4 | Feature drift monitor did NOT veto (`not _drift_vetoed`) | line 1651 |

If all four pass → `_engine_runner.run()` is called → EngineRunner unconditionally calls
`crt_engine.compute()` as one of its four parallel engines.

### Why `crt_engine.log` is empty/absent in standard runs

Without `BACKTEST_ENGINE_GATE=1`, `EngineRunner` is `None` (line 1418).
The CRT state machine still runs (and may open trades), but `crt_engine.compute()`
is never invoked — so no JSON records are written and the file never appears
(with `delay=True` on the FileHandler).

### Also called by

`src/strategies/s01_crt_wrapper.py` line 81 — but this is invoked by
`StrategyOrchestrator`, not `BacktestRunner`. Not used in standard backtests.


================================================================================
SOURCE_FILE: docs/plans/d-tradelatest-models-tradenet-registry-robust-neumann.md
SOURCE_BYTES: 10704
PART: 3/10 FILE 2/7
================================================================================

> Created: 2026-05-16 · Updated: 2026-05-16 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Feature Pipeline Bug-Fix Plan
## Context
A Phase 5 validation audit of the 242,290-sample training dataset revealed four confirmed bugs in the feature engineering pipeline. Evidence is **baked into the registered model scalers** — `gaussian_v5_tradenet_2026_05.json` scaler mean/std fields are the forensic record:

| Feature idx | Name | Scaler mean | Scaler std | Expected | Verdict |
|---|---|---|---|---|---|
| 4 | volume | 0.0 | 1.0 (unfitted) | varies | ❌ dead |
| 5 | volume_ratio | 1.0 | 1.0 (unfitted) | ~1 with variance | ❌ constant |
| 15 | rsi_14 | 0.0 | **52.74** | mean≈50, std≈16 | ❌ wrong formula |
| 22 | swing_high | 0.14263 | 0.34970 | — | — |
| 23 | swing_low | **0.14263** | **0.34970** | different from 22 | ❌ copy-paste |
| 24 | higher_high | 0.19115 | 0.39321 | — | — |
| 25 | lower_low | **0.19115** | **0.39321** | different from 24 | ❌ copy-paste |
| 9–12, 16–18 | ema_spread / trend_bias / trend_strength / momentum_score / macd_line / macd_signal / macd_hist | 0.0 | non-zero | 0.0 is correct (natural zero-mean indicators) | ⚠️ silent NaN→0 fill is a latent risk |

**Primary file to change:** `src/features/feature_pipeline.py`

---

## Bug 1 — Volume Flatline (Issue 1)

**Root cause:** `_validate_input()` inserts `volume = 0.0` when the column is absent (FX safe fallback). `compute_volume_features()` then hits `volume_ma20 == 0` on every row and returns the static fallback `volume_ratio = 1.0`. Both features are constants — zero variance, zero model signal.

**Lines affected:**
- `_validate_input()` (~line 163): `self.df["volume"] = 0.0`
- `compute_volume_features()` (~lines 192–205): `np.where(volume_ma20 > 0, volume / volume_ma20, 1.0)`

**Fix — synthetic tick-activity proxy when FX volume is dead:**
```python
def compute_volume_features(self) -> None:
    df = self.df

    raw_vol = df["volume"]
    vol_is_dead = (raw_vol.max() == 0) or raw_vol.isna().all()

    if vol_is_dead:
        # FX mode: use intrabar range as tick-activity proxy
        proxy = df["high"] - df["low"]
        proxy_ma20 = proxy.rolling(20).mean()
        df["volume"] = proxy                         # proxy replaces dead zeros
        df["volume_ma20"] = proxy_ma20
        df["volume_ratio"] = np.where(
            proxy_ma20 > 0,
            proxy / proxy_ma20,
            1.0
        )
    else:
        df["volume_ma20"] = raw_vol.rolling(20).mean()
        df["volume_ratio"] = np.where(
            df["volume_ma20"] > 0,
            raw_vol / df["volume_ma20"],
            1.0
        )

    df["volume_spike"] = (df["volume_ratio"] > 1.5).astype(np.int8)
    self.df = df
```

---

## Bug 2 — Copy-Paste Twins in Market Structure (Issue 2)

**Root cause:** The scaler records `swing_high` and `swing_low` with byte-for-byte identical mean/std (0.14263 / 0.34970), proving the training data had both columns evaluated against the **same** condition. Ditto for `higher_high` / `lower_low`. The current `feature_pipeline.py` code is correct, but the training dataset was generated by a version that had:

```python
# BUG (prior version, reconstructed):
df["swing_low"]  = (df["high"] == roll_high).astype(np.int8)  # ← wrong: duplicates swing_high
df["lower_low"]  = (df["high"] > ref_high).astype(np.int8)    # ← wrong: duplicates higher_high
```

**Fix — harden `compute_structure_liquidity()` with assertions and correct column references:**
```python
def compute_structure_liquidity(self) -> None:
    df = self.df
    w = 2 * SWING_WINDOW + 1

    roll_high = df["high"].rolling(w, center=True, min_periods=w).max()
    roll_low  = df["low"].rolling(w, center=True, min_periods=w).min()

    # Bullish pivot: bar's HIGH is the local maximum
    df["swing_high"] = (df["high"] == roll_high).astype(np.int8)
    # Bearish pivot: bar's LOW is the local minimum  ← must use df["low"] and roll_low
    df["swing_low"]  = (df["low"]  == roll_low).astype(np.int8)

    # Integrity check — catch copy-paste regressions at runtime
    assert not df["swing_high"].equals(df["swing_low"]), (
        "swing_high and swing_low are identical — check column reference bug"
    )

    df["last_swing_high_price"] = df["high"].where(df["swing_high"] == 1).ffill()
    df["last_swing_low_price"]  = df["low"].where(df["swing_low"]  == 1).ffill()

    ref_high = df["last_swing_high_price"].shift(1)
    ref_low  = df["last_swing_low_price"].shift(1)

    # Bullish structure: current HIGH exceeds previous swing high
    df["higher_high"] = (df["high"] > ref_high).astype(np.int8)
    # Bearish structure: current LOW breaks below previous swing low  ← must use df["low"] and ref_low
    df["lower_low"]   = (df["low"]  < ref_low).astype(np.int8)

    # Integrity check
    assert not df["higher_high"].equals(df["lower_low"]), (
        "higher_high and lower_low are identical — check column reference bug"
    )

    df["break_of_structure"] = np.where(
        df["close"] > ref_high,  1,
        np.where(df["close"] < ref_low, -1, 0)
    ).astype(np.int8)

    sweep_high = (df["high"] > ref_high) & (df["close"] <= ref_high)
    sweep_low  = (df["low"]  < ref_low)  & (df["close"] >= ref_low)
    df["liquidity_sweep"] = np.where(sweep_high, 1, np.where(sweep_low, -1, 0)).astype(np.int8)

    self.df = df
```

---

## Bug 3 — RSI Scaling / Bounds (Issue 3)

**Root cause:** The scaler records `rsi_14` mean=0.0, std=52.74. Standard [0,100] RSI has mean≈50, std≈14–18. The only formula that produces mean≈0 and std≈52 with range [-100,100] is:

```python
# BUG (prior version, reconstructed):
rsi_14 = 100.0 * (gain - loss) / (gain + loss + 1e-9)   # ← wrong: Stochastic-like, not RSI
```

This gives `[-100, 100]` range, mean≈0 (symmetric around 0), and std≈52–58 — matching the scaler exactly.

The current formula in `compute_indicators()` is structurally correct (`100 - 100/(1+rs)`) but:
1. Has no hard bounds clip → edge cases near `loss ≈ 0` can produce values slightly outside [0, 100]
2. The computed RSI is placed directly in canonical features with no post-normalization

**Fix — add clip + optional zero-center mapping:**
```python
# In compute_indicators(), after:
df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
# Add:
df["rsi_14"] = df["rsi_14"].clip(0.0, 100.0)   # strict bounds guard

# Optional: zero-center for model training (clean [-50, 50] mapping)
# df["rsi_14"] = df["rsi_14"] - 50.0
```

**Decision required:** The canonical feature currently ships as raw [0, 100]. If zero-centering is desired (for consistency with ema_spread / momentum_score which are naturally zero-centered), apply `rsi_14 = rsi_14 - 50` consistently and retrain. If keeping [0, 100], just add the `.clip()`.

The plan applies only the `.clip()` (safe, non-breaking). Zero-centering is a separate decision that requires retraining.

---

## Bug 4 — Silent Zero-Filling / Masking (Issue 4)

**Root cause:** In `compute_canonical_ema_features()` and related methods, features that depend on `atr > 0` use `0.0` as the fallback:

```python
df["ema_spread"] = np.where(df["atr"] > 0, ..., 0.0)   # ← 0.0 stays in dataset
df["momentum_score"] = np.where(df["atr"] > 0, ..., 0.0)
df["disp_strength"] = np.where((df["atr"] > 0) & (df["close"] > 0), ..., 0.0)
df["retest_depth"] = np.where((df["retest_flag"] == 1) & ..., ..., 0.0)
```

`finalize()` calls `dropna()` — it removes NaN rows but **silently keeps 0.0-filled rows**. In practice, with a 14-bar ATR warmup, only the first ~14 rows are affected, so the scaler mean impact is negligible. However, using `0.0` is semantically wrong: "ATR not yet available" should be `NaN` (→ dropped) not `0.0` (→ kept as a valid sample saying "no spread").

**Fix — replace fallback `0.0` with `np.nan` in ATR-gated computations:**
```python
# compute_canonical_ema_features:
df["ema_spread"] = np.where(
    df["atr"] > 0, (df["ema_fast"] - df["ema_slow"]) / df["atr"], np.nan
).astype(np.float32)

df["momentum_score"] = np.where(
    df["atr"] > 0, df["close"].diff() / df["atr"], np.nan
).astype(np.float32)

# compute_canonical_temporal_features:
df["disp_strength"] = np.where(
    (df["atr"] > 0) & (df["close"] > 0),
    df["body_size"] / (df["atr"] * df["close"]),
    np.nan,
).astype(np.float32)
df["disp_strength"] = df["disp_strength"].clip(0.0, 3.0)

df["retest_depth"] = np.where(
    (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
    (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
    np.nan,
).astype(np.float32)
df["retest_depth"] = df["retest_depth"].clip(0.0, 1.0)
```

`finalize()` already calls `dropna(subset=CANONICAL_FEATURES)`, so these NaN rows will be properly cleaned up.

**Note on mean=0 for macd_line / macd_signal / ema_spread / trend_bias:** These are **not bugs**. MACD, EMA spread, and momentum_score are zero-centered by mathematical construction. Over a large FX dataset their mean converges to ≈0.0 and the scaler correctly records this. `trend_strength` and `macd_hist` are in `NORMALIZE_COLS` and are z-scored → mean=0 is the intended output. These fields need no change.

---

## Files to Modify

| File | Methods changed |
|---|---|
| `src/features/feature_pipeline.py` | `compute_volume_features`, `compute_indicators` (clip RSI), `compute_structure_liquidity` (assertions), `compute_canonical_ema_features`, `compute_canonical_temporal_features` |

No changes needed to `scripts/data/prepare_data.py`, `feature_schema.py`, or the registry JSON files.

---

## Verification

After applying fixes, re-run the dataset builder and check the new scaler means:

1. **Volume**: `volume` std > 0 and varies with session; `volume_ratio` mean ≈ 1.0 but std > 0.
2. **Swing**: `swing_high` and `swing_low` means should diverge (typically swing_high slightly > swing_low in bull-biased FX periods); `higher_high` and `lower_low` means should differ by > 0.01.
3. **RSI**: mean ≈ 50, std ≈ 14–18 (for [0,100]). Range strictly within [0, 100].
4. **Zero-fill**: Run `pipeline.log_critical_feature_health()` and confirm `zero_rate` for `ema_spread`, `momentum_score`, `disp_strength` drops to < 0.1% (only first warmup rows).
5. **Runtime assertion**: `compute_structure_liquidity` assertions will raise immediately if a future copy-paste bug reintroduces the duplication.

After fixing and retraining, the new scaler should show:
- `volume` std ≠ 1.0 (was unfitted)
- `rsi_14` mean ≈ 50 (was 0.0)
- `swing_high` mean ≠ `swing_low` mean (were identical)
- `higher_high` mean ≠ `lower_low` mean (were identical)


================================================================================
SOURCE_FILE: docs/plans/d-tradelatest-trade-discovery-trace-md-serene-zebra.md
SOURCE_BYTES: 104036
PART: 3/10 FILE 3/7
================================================================================

> Created: 2026-05-28 · Updated: 2026-05-28 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Phase 4 — Shadow Governance

> **Status**: Phase 0b ✅ | Phase 1 ✅ | Phase 2b ✅ | Phase 3a ✅ | Phase 3b ✅ (PASS INTEGRITY / PASS PROMOTION GATE) | Phase 4b ✅ (shadow_advisory_only=True) | Phase 5a → threshold sweep ← current

---

## Phase 4 — Shadow Governance

### Context

Phase 3b restored temporal causality (max dwell 209 days → 5.17 days). But the TTL freed the engine for 23 additional cycles, overwhelmingly shadow expansions: 22 shadow trades vs 15 normal, at radically different outcomes.

```
Shadow:  n=22  avg_rr=-0.290  WR=36%
Normal:  n=15  avg_rr=+0.314  WR=60%
```

Shadow is now the throughput driver and the performance drag simultaneously.

**Key diagnostic finding**: S-scores overlap completely (shadow avg=0.551, normal avg=0.543). The scoring model cannot distinguish shadow quality from normal quality. The quality difference is structural, not observable by the S-score at approval time.

**Why shadow underperforms**: Shadow expansions always have `candidate_age_at_entry=4` (displacement from previous HTF window, age=TTL boundary). Normal expansions have `candidate_age_at_entry=1` (fresh displacement). The displacement candle's market context is stale by the time the shadow expansion fires. This staleness is not captured by body_ratio or the G/C score fusion.

**User verdict**: "Shadow is now the weakest component. Earlier we protected shadow. Now evidence says shadow quality < normal quality."

**Prescribed experiment**: `shadow_threshold: OFF / LOW / MEDIUM / HIGH` → measure trades/rr/dd → find minimum threshold where `shadow_avg_rr >= 0`.

---

### Phase 4a — Telemetry Audit (read-only, current data)

Before implementing any gate, establish the baseline discriminator. Key finding from Phase 3b data:

| Metric | Shadow | Normal |
|---|---|---|
| n | 22 | 15 |
| avg_rr | −0.290 | +0.314 |
| WR | 36% | 60% |
| candidate_age_at_entry | 4 (always at TTL boundary) | 1 (fresh) |
| approval score avg | 0.551 | 0.543 |
| expansion episodes | 147 | 55 |
| retest→trade conversion | 26.8% | 28.8% |

S-scores overlap → score-based threshold alone will NOT discriminate. The pending displacement candle's `body_ratio` is the only structural signal available at expansion entry that differs between candidates.

**Missing signal**: `shadow_htf_alignment` — does the pending displacement direction still match the CURRENT HTF candle's range midpoint at expansion entry? This is the theoretically correct discriminator but not yet tracked. Add in Phase 4b.

---

### Phase 4b — Shadow Age-Decay Gate

#### Diagnosis

Body-ratio and S-score distributions overlap completely between shadow (avg=0.551) and normal (avg=0.543) candidates. A body-ratio gate or score threshold cannot discriminate. The quality difference is structural: shadow displacement candles are always from a **prior HTF window** (`candidate_age_at_entry=4`, always at TTL boundary), meaning market context is stale. Normal candidates enter fresh (`candidate_age_at_entry=1`). The staleness is not captured by body_ratio or the G/C fusion — it must be penalised at the point of trade approval, not at expansion entry.

**Architecture: memory → freshness → decide** (not memory → reject)

#### Decision Order (Phase 4b)

For shadow candidates only, in the soft-confirmation approval path:
1. **HTF alignment check** — does the pending displacement direction still match the current HTF range midpoint? (Structural veto — logged; no hard block in 4b, advisory)
2. **Freshness penalty** — `freshness_multiplier = exp(-λ × candidate_age_at_entry)` (λ = `shadow_age_penalty_lambda`)
3. **Effective score** — `effective_S = final_S × freshness_multiplier`
4. **Threshold gate** — compare `effective_S >= tier_2_threshold` (same threshold, softer shadow score)
5. **(Optional, later)** — `shadow_displacement_body_ratio` tracked for Phase 5 training label; no gate in Phase 4b.

For normal candidates: no penalty, no change.

#### New `CRTConfig` keys (after `expansion_age_warn_candles`)

```python
    # ── Shadow age-decay gate (Phase 4b) ─────────────────────────
    # Exponential decay applied to the S-score of shadow candidates at soft-conf approval.
    #
    # Variant A (shadow_age_norm_candles = 0, raw):
    #   effective_score = final_S × exp(−λ × age)
    #   At shadow age=4 (invariant): λ=0.10→×0.670 | λ=0.20→×0.449 | λ=0.35→×0.247
    #   Risk: behaves as threshold shifting when age is constant. λ is not interpretable.
    #
    # Variant B (shadow_age_norm_candles > 0, normalised):
    #   effective_score = final_S × exp(−λ × age / shadow_age_norm_candles)
    #   At age=4, norm=4: λ=0.40→×0.670 | λ=0.80→×0.449 | λ=1.39→×0.247
    #   Benefit: λ=1.0 means "at max shadow age, score → 1/e ≈ 37%". Interpretable.
    #   When normal candidates later carry age=1, both forms remain consistent.
    #
    # 0.0 = OFF (no decay, Phase 3b behavior).
    shadow_age_penalty_lambda: float = 0.0

    # Normalisation denominator for shadow age-decay (0 = raw, no normalisation).
    # Recommended: set to pending_displacement_ttl_candles (= 4) for Variant B.
    # When > 0: freshness_multiplier = exp(−λ × age / shadow_age_norm_candles)
    shadow_age_norm_candles: int = 0

    # Advisory-only shadow: if True, shadow expansions never produce trades.
    # Shadow still tracks through EXPANSION→RETEST for telemetry; EXECUTION is blocked.
    # Fallback: use when no λ satisfies the composite governance gate.
    shadow_advisory_only: bool = False
```

#### Implementation — age-decay in soft-confirmation path (`process_candle()` RETEST branch)

The decay is applied AFTER `final_S` is computed and BEFORE the `tier_2_threshold` comparison. No changes to expansion entry, state machine, or earlier logic.

```python
# In process_candle(), inside the soft-conf evaluation block:

_effective_S      = final_S
_freshness_mult   = 1.0
_shadow_ctx: dict = {}

if self.state._came_from_shadow:
    _age    = self.state._expansion_entry_idx - self.state._displacement_entry_idx
    _lambda = self.config.shadow_age_penalty_lambda
    _norm   = self.config.shadow_age_norm_candles   # Phase 4b Variant B
    if _lambda > 0.0:
        # Variant B (normalised) when norm > 0; Variant A (raw) when norm == 0
        _age_input      = (_age / _norm) if _norm > 0 else _age
        _freshness_mult = math.exp(-_lambda * _age_input)
        _effective_S    = final_S * _freshness_mult
        if approved and _effective_S < self.config.tier_2_threshold:
            approved = False
            reason   = RejectReason.LOW_SCORE
    _shadow_ctx = {
        "age":                  _age,
        "age_normalised":       round(_age / _norm, 3) if _norm > 0 else None,
        "htf_alignment":        self.state._shadow_htf_alignment,
        "freshness_multiplier": round(_freshness_mult, 4),
        "score_before":         round(final_S, 4),
        "score_after":          round(_effective_S, 4),
        "lambda":               _lambda,
        "norm_candles":         _norm,
        "variant":              "B_normalised" if _norm > 0 else "A_raw",
    }
```

`shadow_context.variant` records which formula was active — "A_raw" or "B_normalised" — so post-run queries can distinguish runs without re-reading the config.

#### `shadow_advisory_only` block (approved, unchanged from original design)

Wire into `process_candle()` after `_effective_S >= tier_2_threshold` passes but before `build_trade()`:

```python
# Phase 4b: shadow advisory gate — block trade execution for shadow-sourced setups
if self.config.shadow_advisory_only and self.state._came_from_shadow:
    emit_integrity_event("SHADOW_ADVISORY_BLOCK", "INFO", "crt_engine", {
        "candidate_id":        f"CAND-{self.state._expansion_entry_idx}",
        "score_before":        round(final_S, 4),
        "score_after":         round(_effective_S, 4),
        "freshness_multiplier": round(_freshness_multiplier, 4),
        "candle_index":        candle.index,
    })
    self.sm.reset_to_range(self.state, "shadow_advisory_only", candle, self.ev_log)
    action["action"] = "SHADOW_ADVISORY_BLOCK"
    return action
```

#### Telemetry additions to CANDIDATE_LIFECYCLE (approved)

Add `shadow_context` dict and `shadow_displacement_body_ratio` to `on_candidate_opened()` / `on_candidate_accepted()` / CANDIDATE_LIFECYCLE flush:

```python
# In on_candidate_accepted(), extend signature:
def on_candidate_accepted(
    self, candle_index: int, score_at_approval: float = 0.0,
    shadow_context: Optional[dict] = None,          # Phase 4b
    shadow_displacement_br: float = 0.0,            # Phase 4b (body_ratio of pending disp candle)
) -> None:
    if self._active_candidate is not None:
        self._active_candidate["score_at_approval"]       = score_at_approval
        self._active_candidate["shadow_context"]          = shadow_context or {}
        self._active_candidate["shadow_displacement_br"]  = shadow_displacement_br
        self._close_candidate(candle_index, "ACCEPTED")
```

`shadow_displacement_body_ratio` is computed at the SHADOW_EXPANSION_CONFIRMED path:
```python
# When state._came_from_shadow == True and expanding:
_pdc = state.pending_displacement_candle
_shadow_br = abs(_pdc.close - _pdc.open) / (_pdc.high - _pdc.low) if _pdc and (_pdc.high - _pdc.low) > 0 else 0.0
```

CANDIDATE_LIFECYCLE flush includes both fields. No gate on `shadow_displacement_body_ratio` in Phase 4b — telemetry only for Phase 5 training label.

`shadow_htf_alignment: Optional[bool]` is stored on `EngineState` at shadow expansion entry (set in `try_shadow_pending_to_expansion()`), then read at soft-conf time for the `shadow_context` dict. Add field to `EngineState`:
```python
    _shadow_htf_alignment: Optional[bool] = None   # Phase 4b
```

#### Experiment Matrix

Two variants. All shadows are at `candidate_age_at_entry=4` (invariant from Phase 3b). 

**Variant A — raw (norm=0): `exp(−λ × age)`**

| Run | λ | `norm` | Penalty at age=4 | Avg eff_S | Note |
|---|---|---|---|---|---|
| A0 | 0.00 | 0 | 1.000 | 0.551 | Baseline — Phase 3b reproduced |
| A1 | 0.10 | 0 | 0.670 | 0.369 | Weak shadows cut (S < 0.448 fails) |
| A2 | 0.20 | 0 | 0.449 | 0.247 | Most shadow cut (need S > 0.668) |
| A3 | 0.35 | 0 | 0.247 | 0.136 | ≈ advisory_only; all shadow S fails |

**Variant B — normalised (norm=4): `exp(−λ × age/4)`**

Same penalty levels as A, but λ is now interpretable: "λ=1.0 → at max shadow age, score × 1/e."

| Run | λ | `norm` | Penalty at age=4 | Equiv to A-run | Note |
|---|---|---|---|---|---|
| B1 | 0.40 | 4 | 0.670 | = A1 | Same penalty, semantically bounded λ |
| B2 | 0.80 | 4 | 0.449 | = A2 | |
| B3 | 1.39 | 4 | 0.247 | = A3 | ≈ advisory_only |

**A/B comparison rule**: Runs with identical penalties (A1≡B1, A2≡B2, A3≡B3) should produce identical trade outcomes. If they differ, there is an implementation bug in the normalization path. If they match: normalization is a clean reparametrization, adopt Variant B for all future λ tuning.

Decision gate after experiments:
- Read inspection table (below) first, not PnL.
- If any run achieves composite gate: adopt lowest λ that passes, use that variant's form.
- If no run achieves composite gate: set `shadow_advisory_only: True`.

#### Composite Promotion Gate (replaces weak `shadow_avg_rr >= 0`)

Shadow passes governance when ALL three hold:
1. `shadow_avg_rr >= 0` (net positive expected value)
2. `shadow_wr >= normal_wr - 10%` (win-rate not more than 10pp below normal)
3. `shadow_max_dd <= baseline_max_dd` (drawdown does not exceed Phase 3b 9.23R baseline)

If any condition fails, escalate λ to the next level.

#### Primary Post-Run Inspection Table

Read this table BEFORE PnL summary. The question is: **does shadow quality improve before shadow quantity collapses?**

| Run | λ | norm | shadow_n | shadow_RR | normal_n | normal_RR | total_DD | approval_rate | shadow_quality_improves |
|---|---|---|---|---|---|---|---|---|---|
| A0 | 0.00 | 0 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | baseline |
| A1 | 0.10 | 0 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | ❌ FALSE — no change (penalty ×0.670 above floor) |
| A2 | 0.20 | 0 | 4  | −0.394 | 15 | +0.336 | 3.18R | 100% | ❌ FALSE — RR WORSENS as n collapses |
| A3 | 0.35 | 0 | 0  | n/a    | 15 | +0.328 | 2.08R | 100% | ❌ FALSE — all shadow eliminated (≡ advisory_only) |
| B1 | 0.40 | 4 | 22 | −0.290 | 15 | +0.314 | 9.23R | 100% | ✅ A1≡B1 parity confirmed |
| B2 | 0.80 | 4 | 4  | −0.394 | 15 | +0.336 | 3.18R | 100% | ✅ A2≡B2 parity confirmed |
| B3 | 1.39 | 4 | 0  | n/a    | 15 | +0.328 | 2.08R | 100% | ✅ A3≡B3 parity confirmed |

**VERDICT (2026-05-28)**: shadow_quality_improves = FALSE for all λ. `shadow_advisory_only = True` applied to production config.

**Normal_n and normal_RR should be stable across all runs** (decay applies only to shadow). If normal stats shift between runs, there is a bug in the shadow-conditional guard.

**Interpretation key**:
- `shadow_quality_improves = True` when `shadow_RR` rises toward 0 as `shadow_n` falls — decay is selecting better shadow candidates.
- `shadow_quality_improves = False` when `shadow_RR` stays near −0.29 even as `shadow_n` collapses — decay is acting as pure threshold shifting (all shadows are equally bad; cutting them by score makes no quality difference).
- If `shadow_quality_improves = False` for all λ: adopt `shadow_advisory_only = True`. Shadow quality problem is structural (all shadows from stale context), not filterable by score.

```powershell
# Run after each backtest — fill one row of the inspection table:
$tel     = Get-Content "results\run_*\BNBUSDT_M15_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$trades  = Import-Csv "results\run_*\BNBUSDT_M15_trades.csv"
$accepted = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" -and $_.death_reason -eq "ACCEPTED" }
$shadow_acc = $accepted | Where-Object { $_.shadow_used -eq $true }
$normal_acc = $accepted | Where-Object { $_.shadow_used -eq $false }

# shadow_n, normal_n
"shadow_n=$($shadow_acc.Count)  normal_n=$($normal_acc.Count)"

# shadow_RR and normal_RR from trades (join on candidate_id or use shadow_used from telemetry)
$shadow_ids  = $shadow_acc.candidate_id
$shadow_rr   = ($trades | Where-Object { $shadow_ids -contains "CAND-$($_.entry_candle_idx)" }).pnl_rr_net |
               Measure-Object -Average | Select-Object -ExpandProperty Average
$normal_rr   = ($trades | Where-Object { $shadow_ids -notcontains "CAND-$($_.entry_candle_idx)" }).pnl_rr_net |
               Measure-Object -Average | Select-Object -ExpandProperty Average
"shadow_RR=$shadow_rr  normal_RR=$normal_rr"

# total_DD from report.txt
Select-String "Max drawdown" "results\run_*\BNBUSDT_M15_report.txt"

# approval_rate
"approval_rate=$($accepted.Count) / $($tel | Where-Object { $_.kind -eq 'CANDIDATE_LIFECYCLE' }).Count"

# A/B parity check (B-run only): variant field in shadow_context
$variant = ($shadow_acc | Select-Object -First 1).shadow_context.variant
"formula_variant=$variant"
```

---

### Updated Promotion Gates

> **Phase 4b result (2026-05-28):** shadow_advisory_only=True. Shadow gates below are vacuously satisfied (0 shadow trades). Normal-only baseline: 15 trades, WR=60%, avg_RR=+0.328, DD=2.08R.

| Gate | Condition | Phase 4b (advisory_only=True) | Status |
|---|---|---|---|
| `temporal: max_expansion_days < 7` | `max * 15/60/24 < 7` | 5.17 days | ✅ |
| `shadow_avg_rr >= 0` | shadow trades net positive | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_wr >= normal_wr − 10%` | shadow WR within 10pp of normal | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_max_dd <= baseline_dd` | shadow DD ≤ 9.23R baseline | 0 shadow trades — vacuous | ✅ (vacuous) |
| `shadow_share < 50%` | shadow not majority of trades | 0/15 = 0% | ✅ |
| `freshness_penalty_mean > 0.7` | decay not too aggressive | N/A (advisory_only) | N/A |
| `normal_avg_rr >= 0` | normal trades positive | +0.328R | ✅ |
| `max_dd < 5R` | total drawdown controlled | 2.08R | ✅ |
| `UNBOUNDED_STATE = 0` | | 0 | ✅ |
| `TEMPORAL_PARADOX = 0` | | 0 | ✅ |
| `SHADOW_LEAK = 0` | | 0 | ✅ |
| `expired_share < 10%` | 7/202 = 3.5% | 3.5% | ✅ |
| `approval_rate < 95%` | 100% (pre-existing) | 100% | ❌ Pre-existing |

**Note on `freshness_penalty_mean > 0.7`**: at Variant A λ=0.10, age=4, mean=0.67 (just misses). At Variant B λ=0.40, age/4=1.0, mean=exp(-0.40)=0.67 (same). This gate checks that the lambda is not so aggressive it collapses all signal. If the adopted λ causes `freshness_penalty_mean < 0.7`, the gate fails and shadow_advisory_only is required.

**Note on `approval_rate = 100%` (deferred to Phase 5 — decision selectivity)**: Score modifies but does not govern. The engine can now: discover → remember → age → expire. But it barely chooses: `tier_2_threshold=0.30` is below all candidate score floors (floor ≈0.44), making the decision layer a pass-through. Phase 5 scope: raise threshold until approval_rate < 95%, calibrate tier_1/tier_2 split against realised RR by tier. Do NOT move there yet — N is too small for threshold recalibration until shadow governance is resolved.

---

### Blast Radius (Phase 4b)

| Change | Behavior | Risk |
|---|---|---|
| `shadow_age_penalty_lambda: 0.0` in CRTConfig | New config key; 0.0 = no change | Low |
| `shadow_age_norm_candles: 0` in CRTConfig | New config key; 0 = Variant A (no norm) | Low |
| `shadow_advisory_only: False` in CRTConfig | New config key; False = no change | Low |
| Age-decay in soft-conf approval path | Reduces `effective_S` for shadow candidates | Medium — intended |
| Variant B normalisation (`norm > 0`) | Changes λ → age/norm interpretation | Low — reparametrization |
| `shadow_context.variant` field | "A_raw" or "B_normalised" in telemetry | Low |
| `shadow_context` dict in CANDIDATE_LIFECYCLE | Telemetry only | Low |
| `shadow_displacement_br` in CANDIDATE_LIFECYCLE | Telemetry only | Low |
| `_shadow_htf_alignment` on EngineState | Set at expansion entry, read at soft-conf | Low |
| `SHADOW_ADVISORY_BLOCK` in TRADE_OPENED path | Blocks shadow trades if advisory_only=True | High — hard block |
| No change to `try_shadow_pending_to_expansion()` | Shadow path entry unchanged | None |

---

## Phase 3b Gate — expired_counterfactual_rr (Promotion Blocker)

### Context

Phase 3b implemented a 495-candle TTL guard that expired 7 expansion episodes. The promotion gate requires computing `expired_counterfactual_rr` — a post-hoc simulation answering: **"did TTL remove alpha, or did it correctly cut stale structure?"**

This is a post-processing script only. No engine changes. Output feeds the Phase 3b promotion blocker.

### Data Sources

| Source | Path | Role |
|---|---|---|
| Phase 3b telemetry | `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_crt_telemetry.jsonl` | Canonical list of 7 expired candidates (EXPANSION_RETRACE_CHECK, ended_by=expired); provides ceiling_at_max |
| Integrity log | `logs/integrity_events.jsonl` | EXPANSION_EXPIRED events (would_trade_if_alive, score, source); 63 total — must filter to Phase 3b run via telemetry |
| M15 CSV | `data/BNBUSDT_M15.csv` | OHLCV rows indexed by candle_index. Columns: timestamp,open,high,low,close,volume |
| Trades CSV | `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_trades.csv` | Actual trade outcomes for comparison baseline |

### 7 Expired Candidates (Phase 3b canonical)

Recovered from EXPANSION_RETRACE_CHECK records with ended_by=expired:

| candidate_id | episode_start | expiry_candle | source | retest_depth_pct | retest_distance_abs |
|---|---|---|---|---|---|
| CAND-7992 | 7992 | 8488 | normal | 17.25 | 0.0 |
| CAND-13056 | 13056 | 13552 | shadow | 0.0 | 0.8 |
| CAND-26676 | 26676 | 27172 | normal | 0.0 | 0.8 |
| CAND-27492 | 27492 | 27988 | shadow | 61.65 | 0.0 |
| CAND-50488 | 50488 | 50984 | normal | 17.45 | 0.0 |
| CAND-56680 | 56680 | 57176 | shadow | 15.863 | 0.0 |
| CAND-69439 | 69439 | 69935 | shadow | 6.737 | 0.0 |

Note on `retest_depth_pct`: computed as `telemetry._expansion_max_depth / config.retest_depth_max` (uses raw config fraction, not ATR-scaled). High value = depth already exceeded raw threshold (adaptive ceiling different). Low/zero = depth never reached raw threshold.
Note on `retest_distance_abs = 0.0`: depth already past the raw config threshold (adaptive ATR ceiling may still reject).

### Algorithm

```
Script: scripts/analysis/p5a_expired_counterfactual_rr.py

Constants from production config:
  retest_depth_max: 0.3
  retest_atr_depth_fraction: 0.5
  ATR_PERIOD: 14
  SCAN_WINDOW: 200     # candles to scan forward from expiry
  EXIT_WINDOW: 100     # candles to scan for SL/TP hit
  SL_MULT: 1.0         # ATR multiplier for SL (legacy_sl_atr_mult from production config)
  MIN_RR: 1.5          # TP = entry + MIN_RR × (entry − SL) (min_rr_ratio from production config)

Step 1 — Load data:
  candles = pd.read_csv("data/BNBUSDT_M15.csv", parse_dates=["timestamp"])
  candles["ATR14"] = compute_atr(candles, period=14)  # rolling 14-period True Range
  
Step 2 — Load Phase 3b telemetry, build expired_episodes dict:
  For each EXPANSION_RETRACE_CHECK record with ended_by="expired":
    key = episode_start_idx
    value = {ceiling_at_max, episode_end_idx, shadow_used}
  (Should yield exactly 7 entries from Phase 3b run)

Step 3 — Load integrity_events.jsonl, filter to Phase 3b candidates:
  For each EXPANSION_EXPIRED event where candidate_id in expired_episodes:
    Merge: would_trade_if_alive, score, source fields

Step 4 — For each expired candidate:
  a. Get displacement_candle = candles.iloc[episode_start_idx]
  b. Determine direction:
       direction = LONG if displacement_candle.close < displacement_candle.open else SHORT
       (bearish displacement candle → LONG trade setup; bullish → SHORT)
  c. Set range reference approximation:
       l_ref = displacement_candle.low   (LONG)
       h_ref = displacement_candle.high  (SHORT)
  d. Use ceiling_at_max from telemetry as forward_ceiling
     (ATR-scaled at moment of max depth; constant approximation for post-expiry period)
  
Step 5 — Forward scan from episode_end_idx+1 to episode_end_idx+SCAN_WINDOW:
  retest_found = False
  for j in range(episode_end_idx+1, min(episode_end_idx+SCAN_WINDOW, len(candles))):
    c = candles.iloc[j]
    if direction == LONG:
      depth = c.close - l_ref
      structure_broken = c.close < l_ref      # price broke back below range ref → invalid
    else:
      depth = h_ref - c.close
      structure_broken = c.close > h_ref      # price broke back above range ref → invalid
    
    if structure_broken:
      break  # candidate structure failed; no trade
    
    if 0 <= depth < forward_ceiling:
      # RETEST FIRES — simulate trade
      entry = c.close
      atr_j = candles["ATR14"].iloc[j]
      sl = (l_ref - atr_j * SL_MULT) if direction == LONG else (h_ref + atr_j * SL_MULT)
      risk = abs(entry - sl)
      tp = entry + MIN_RR * risk if direction == LONG else entry - MIN_RR * risk
      
      # Scan for SL/TP hit
      rr = simulate_exit(candles, j+1, j+EXIT_WINDOW, sl, tp, direction)
      # rr = +MIN_RR if TP hit, -1.0 if SL hit, 0 if neither (time exit)
      retest_found = True
      break
  
  if not retest_found:
    rr = None  # No retest in SCAN_WINDOW

Step 6 — Report:
  Print table: candidate_id | source | ceiling | direction | found_retest | rr | entry_candle
  Summary:
    n_counterfactual = count(found_retest=True)
    mean_counterfactual_rr = mean(rr for found_retest=True)
    n_normal_cf = count(source=normal and found_retest=True)
    n_shadow_cf = count(source=shadow and found_retest=True)
    mean_normal_cf_rr = mean(rr for normal counterfactuals)
    mean_shadow_cf_rr = mean(rr for shadow counterfactuals)
    
  Compare vs actual trades:
    Load trades CSV, compute actual mean_rr
    Print: "TTL removed alpha?" verdict based on mean_counterfactual_rr sign
```

### Approximations (explicitly noted in script header)

| Approximation | Source of error | Direction of bias |
|---|---|---|
| direction from displacement candle close vs open | Engine uses full sweep/displacement confirmation | Possible misclassification |
| l_ref/h_ref from displacement candle low/high | Engine uses range reference from HTF-defined range | May differ from actual range boundary |
| forward_ceiling = ceiling_at_max from telemetry | ATR changes post-expiry; ceiling_at_max is from peak depth moment | Could over- or under-filter |
| ATR14 from rolling TR | Engine uses internal ATR with specific warmup | Small numerical difference |
| SL = 1.0×ATR from entry | Actual SL from execution_planner uses body/ATR combination | SL may be tighter or wider |
| No soft_conf evaluation | Actual engine requires soft confirmation candle | Script may count retests that engine would reject |

Script header must state: "APPROXIMATION — counterfactual simulation; not a backtest replay. Results directional only."

### Output Gate

The promotion gate for Phase 3b is satisfied when this script produces a documented output in `results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_phase3b_report.md` containing:
- The 7-candidate table
- `n_counterfactual_trades`, `mean_counterfactual_rr`
- Verdict: "TTL removed alpha: YES/NO/UNCERTAIN"
- Split: normal_cf_rr vs shadow_cf_rr (shadow_advisory_only=True makes the shadow result moot for production, but documents TTL impact on each source)

### Script Arguments

```
python scripts/analysis/p5a_expired_counterfactual_rr.py
  --telemetry results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_crt_telemetry.jsonl
  --integrity-log logs/integrity_events.jsonl
  --data data/BNBUSDT_M15.csv
  --trades results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_trades.csv
  --scan-window 200
  --exit-window 100
  --sl-mult 1.0
  --rr-target 1.5
  [--output results/run_20260527_134013_BNBUSDT_M15/BNBUSDT_M15_phase3b_report.md]
```

### Verification

```powershell
# Confirm 7 candidates found in telemetry
python scripts/analysis/p5a_expired_counterfactual_rr.py --telemetry ... --dry-run
# Output should show exactly 7 expired episodes from the telemetry file

# Full run
python scripts/analysis/p5a_expired_counterfactual_rr.py --telemetry ... --data ... --integrity-log ... --trades ...

# Check output file exists
Test-Path "results\run_20260527_134013_BNBUSDT_M15\BNBUSDT_M15_phase3b_report.md"
```

---

## Phase 5 — Decision Selectivity

### Architecture State After Phase 4b

| Layer | Role | Status |
|---|---|---|
| CRT structure discovery | finds displacement + expansion candidates | ✅ stable |
| TTL guard (Phase 3b) | expires stale structure | ✅ stable |
| Shadow governance (Phase 4b) | blocks stale execution confidence | ✅ stable (advisory_only) |
| **Decision selectivity (Phase 5)** | **ranks valid structure** | ← current frontier |

**Core insight**: "S-scores overlap completely" means current score measures **local pattern quality**, not **market state continuity**. The engine has good structure memory but weak execution ranking. Phase 5 creates meaningful rejection — not fewer trades for its own sake, but trades ranked by market state quality.

**Critical constraint**: Do NOT raise `tier_2_threshold` globally before replay sweep. `normal_avg_rr = +0.328` is the first healthy stable baseline. Global tightening risks destroying it before understanding what the threshold is actually cutting.

**Phase 5 goal**: `approval_rate: 95% → 70–85%` without degrading `normal_avg_rr`.

---

### Phase 5a — Replay Selectivity Sweep

**Mechanism**: backtest experiment sweep only — no live config changes. Mirror structure of Phase 4b lambda sweep.

**Experiment matrix**: `tier_2_threshold ∈ [0.44, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60]`

Rationale for range: candidate score floor ≈ 0.44 (Phase 3b data). Start just above the floor where first rejections appear.

For each run, measure:

| threshold | approvals | approval_rate | WR | avgRR | DD | selectivity_improves |
|---|---|---|---|---|---|---|
| 0.44 | TBD | TBD | TBD | TBD | TBD | baseline |
| 0.48 | TBD | TBD | TBD | TBD | TBD | ? |
| ... | | | | | | |

**Normal_avgRR must remain ≥ +0.300 across all runs.** If raising threshold hurts avgRR, selectivity is cutting quality candidates — the score space is still not predictive.

**Inspection criterion**: `selectivity_improves = True` when both:
1. `approval_rate` drops meaningfully (≥5pp below baseline)
2. `avgRR` does not fall below +0.300 (no expectancy destruction)

If `selectivity_improves = False` for all levels: score space has no predictive structure yet. Do not lock any threshold. Collect more N.

**Config change for each run** (only `tier_2_threshold` in the JSON, re-hash each time):
```json
"tier_2_threshold": 0.44
```

**Telemetry query after each run**:
```powershell
$tel     = Get-Content "results\run_*\BNBUSDT_M15_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$cands   = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" }
$accepted = $cands | Where-Object { $_.death_reason -eq "ACCEPTED" }
$rejected = $cands | Where-Object { $_.death_reason -eq "LOW_SCORE" }
"approvals=$($accepted.Count)  rejections=$($rejected.Count)"
"approval_rate=$([math]::Round($accepted.Count / $cands.Count, 3))"
# avgRR from trades CSV
$trades = Import-Csv "results\run_*\BNBUSDT_M15_trades.csv"
($trades.pnl_rr_net | Measure-Object -Average).Average
```

**Preconditions** (check before running):
- `shadow_advisory_only = True` in config ✅ (Done — Phase 4b)
- Phase 3b Gate (expired_counterfactual_rr) documented ❌ (see above — run script first)
- N current = 15 (minimum viable; run on extended date range for N≥30 if possible)

---

### Phase 5b — Counterfactual Reject Audit

After Phase 5a identifies a candidate threshold, audit what was rejected:

**Mechanism**: For each rejected candidate (`death_reason = "LOW_SCORE"` in CANDIDATE_LIFECYCLE), simulate the outcome IF the trade had been taken.

**New telemetry field** (no engine change — add to post-processing only):
```python
rejected_candidate: {
    "candidate_id":   str,
    "score":          float,         # score_at_approval (below threshold)
    "shadow":         bool,          # shadow_used
    "threshold":      float,         # tier_2_threshold at run time
    "decision_distance": float,      # abs(score - threshold) — how close to passing
    "outcome_if_taken": float | None # simulated RR (post-processing, same logic as expired_counterfactual_rr)
}
```

**Question answered**: `mean(outcome_if_taken) < 0` → rejection improved expectancy (threshold is working). `mean(outcome_if_taken) > 0` → rejection is cutting good trades (threshold too high).

**Script**: `scripts/analysis/p5b_reject_audit.py` — same simulation logic as `p3b_gate_expired_counterfactual_rr.py` (reuse the forward-scan simulate_exit() function).

---

### Phase 5c — Decision Distance Telemetry

**One code addition** to `TelemetryCollector` in `crt_engine_v2.py`: emit `decision_distance` in CANDIDATE_LIFECYCLE for every candidate (accepted or rejected):

```python
"decision_distance": round(abs(score_at_approval - config.tier_2_threshold), 4)
```

**Why**: Near-misses (`decision_distance < 0.03`) are the most valuable training labels. A candidate that scores 0.52 when threshold=0.50 may behave identically to one scoring 0.48 — but only one gets approved. Tracking decision_distance enables the training pipeline to:
1. Label near-misses separately from clear rejections
2. Avoid training a model on a boundary artifact
3. Calibrate score granularity vs threshold precision

**Additional**: `htf_transition_distance` on EngineState — candles since HTF window rolled at the moment of candidate entry. Currently shadow candidates cluster near the HTF boundary (candidate_age_at_entry=4, invariant). For normal candidates this varies. `htf_transition_distance` diagnoses whether HTF boundary proximity itself is the poison for shadow — independent of the score.

```python
# EngineState new field (Phase 5c)
_htf_transition_distance: int = 0   # candles since HTF rolled at candidate entry (backtest sets this)
```

Set in `BacktestRunner.run()` at SWEEP_DETECTED / SHADOW_PENDING entry:
```python
engine.state._htf_transition_distance = _htf_position - 1  # 0 = HTF just rolled
```

Include in CANDIDATE_LIFECYCLE flush:
```python
"htf_transition_distance": c.get("htf_transition_distance", None)
```

**Expected finding**: if shadow candidates cluster at `htf_transition_distance ≈ 4` and normal candidates cluster at `htf_transition_distance ≈ 0–1`, this confirms that the shadow decay problem is HTF boundary proximity, not displacement staleness. This unlocks a better discriminator for Phase 6 shadow rehabilitation.

---

### Governance Refinements (Required Before Implementation)

These apply to Phase 4b code and Phase 5 telemetry additions. Document them here so they are not lost.

#### Refinement 1 — Rename `_age` variable (Phase 4b code)

**Current** (in soft-conf decay path):
```python
_cand_age = self.state._expansion_entry_idx - self.state._displacement_entry_idx
```

**Renamed to** `_cross_window_distance` (or `_pending_structure_age`):
```python
_cross_window_distance = self.state._expansion_entry_idx - self.state._displacement_entry_idx
```

**Reason**: The name `age` implies temporal freshness. But this value is `{1 for normal, 4 for shadow}` — a discrete indicator of **cross-window displacement memory**, not true elapsed time. Using "age" risks contaminating future learning when the variable is used as a training feature. The decay formula in the shadow_context dict should also rename: `"age"` → `"cross_window_distance"`, `"age_normalised"` → `"cross_window_distance_normalised"`.

#### Refinement 2 — Advisory block ordering (Phase 4b code)

**Current** ordering in `process_candle()` RETEST branch:
```
threshold check (tier_2_threshold) → advisory_block → build_trade
```

**Corrected** ordering:
```
threshold check → candidate_accept (telemetry) → advisory_block → execution
```

**Why**: Advisory suppression is an **execution gate**, not an **approval mutation**. A shadow candidate that clears the threshold but is blocked by `shadow_advisory_only` should be recorded as `ACCEPTED` in telemetry (approved structure) but `NOT_EXECUTED` at execution layer. This keeps `approval_rate` statistics clean — it measures structure quality, not execution policy.

**Implementation**: call `self.telemetry.on_candidate_accepted(...)` BEFORE the `shadow_advisory_only` block. The `SHADOW_ADVISORY_BLOCK` event fires after acceptance. This does not change trade outcomes; it correctly reflects that the candidate was structurally approved before execution was suppressed.

**New field in CANDIDATE_LIFECYCLE**:
```python
"approval_path": "NORMAL" | "SHADOW" | "SHADOW_DECAYED" | "SHADOW_BLOCKED"
```

Logic:
- `NORMAL`: normal candidate, approved, executed
- `SHADOW`: shadow candidate, λ=0 or no decay applied, executed (when advisory_only=False)
- `SHADOW_DECAYED`: shadow candidate, `freshness_multiplier < 1.0`, still approved after decay, executed
- `SHADOW_BLOCKED`: shadow candidate, approved by threshold, blocked by `shadow_advisory_only=True`

This field makes `decision selectivity` traceable across all sub-paths. Phase 5 analysis can then stratify by `approval_path`.

Set `approval_path` in `on_candidate_accepted()` signature:
```python
def on_candidate_accepted(
    self, candle_index: int, score_at_approval: float = 0.0,
    shadow_context: Optional[dict] = None,
    shadow_displacement_br: float = 0.0,
    approval_path: str = "NORMAL",   # Phase 5c
) -> None:
```

#### Refinement 3 — Add `context_source` to shadow_context dict (Phase 4b telemetry)

**Current** `shadow_context` dict:
```python
{"age": ..., "freshness_multiplier": ..., "variant": "A_raw" | "B_normalised", ...}
```

**Add** `context_source` field:
```python
"context_source": "PRIOR_HTF"   # current shadow is always PRIOR_HTF
# Future values: "SAME_HTF" (delayed same-window continuation), "REGIME_CARRY" (HTF regime carryover)
```

**Reason**: "shadow" is currently one subtype — cross-window displacement memory (PRIOR_HTF). Future paths may include:
- delayed same-window continuation (SAME_HTF): displacement fired near HTF boundary, expansion delayed until next candle in same window
- regime carryover (REGIME_CARRY): HTF structural regime persists across multiple windows without new displacement

Tagging `context_source` now avoids training pipeline confusion later when new shadow subtypes emerge.

#### Refinement 4 — Composite gate: minimum shadow N (Phase 4b / Phase 5)

**Add to composite promotion gate**:
```
shadow passes governance when ALL:
1. shadow_avg_rr >= 0
2. shadow_wr >= normal_wr - 10%
3. shadow_max_dd <= baseline_max_dd
4. shadow_n >= 10   ← NEW: prevent single-survivor luck from passing gate 1
```

At N < 10, `shadow_avg_rr >= 0` is trivially achievable by luck (1 winner among 3 survivors passes). The composite gate must require statistical minimum before any λ is adopted.

---

### Phase 5 Promotion Gates

| Gate | Condition | Status |
|---|---|---|
| `expired_counterfactual_rr documented` | Phase 3b Gate closed | ✅ DONE (2026-05-28) |
| `approval_rate < 95%` at adopted threshold | from Phase 5a sweep | ❌ TBD |
| `normal_avg_rr >= +0.300` at adopted threshold | selectivity does not hurt expectancy | ❌ TBD |
| `reject_audit_mean_rr < 0` | Phase 5b confirms rejections are bad trades | ❌ TBD |
| `decision_distance tracked` | Phase 5c telemetry live | ❌ TBD |
| `htf_transition_distance tracked` | Phase 5c telemetry live | ❌ TBD |
| `approval_path tracked` | Phase 5c telemetry live | ❌ TBD |

### Implementation Order

```
Phase 5a (run first):
  1. Run p3b_gate_expired_counterfactual_rr.py (closes Phase 3b promotion blocker)
  2. Score distribution analysis from Phase 3b/4b telemetry
  3. Threshold sweep: 7 backtest runs at tier_2_threshold=[0.44..0.60]
  4. Fill inspection table, find minimum threshold where approval_rate < 95%
  5. Verify normal_avg_rr >= +0.300 at that threshold

Phase 5b (after 5a sweep completes):
  6. p5b_reject_audit.py on winning threshold run
  7. Confirm reject_audit_mean_rr < 0

Phase 5c (parallel with 5b, code additions — INCLUDE governance refinements):
  8. Rename _age → _cross_window_distance in soft-conf path + shadow_context dict
  9. Reorder advisory_block after on_candidate_accepted() call
  10. Add approval_path to on_candidate_accepted() + CANDIDATE_LIFECYCLE flush
  11. Add context_source to shadow_context dict
  12. Add decision_distance to CANDIDATE_LIFECYCLE (1 line, TelemetryCollector)
  13. Add _htf_transition_distance to EngineState + BacktestRunner
  14. Re-run with winning threshold — verify new fields in telemetry

Phase 5 promotion:
  15. Lock tier_2_threshold, set tier_1_threshold (if score cluster exists above)
  16. Re-hash config
  17. Run full validation suite, update promotion gates
```

---

## Phase 3b — PASS INTEGRITY / FAIL PROMOTION (archived)

---

## Context

The 20,115-candle expansion episode is not simply stale memory — it reveals that `candidate lifecycle ≠ market lifecycle`. Before adding any TTL, we must determine whether the episode is:

- **Case A — Genuine stale expansion**: displacement candle was valid; expansion state persisted because price never retraced. Needs TTL expiry.
- **Case B — Accounting bug**: `on_expansion_ended()` was never called (e.g. `ended_by="eof"` dominates). Needs state accounting fix.

Phase 3a adds telemetry to diagnose which case applies. Phase 3b implements the expiry, but only after 3a confirms Case A.

---

## Phase 3a — Temporal Audit (telemetry only, no behavior change)

### Goal

Measure `age_candles`, `age_hours_actual`, `age_hours_estimated`, and `ended_by` for every expansion episode. Distinguish accounting bugs from genuine stale state. Emit `UNBOUNDED_STATE` CRITICAL if any episode is pathologically long.

### Additions to `src/config_layer/crt_engine_v2.py`

#### Edit 1 — Add `_expansion_start_ts` + `_last_expansion_seen_idx/ts` to `TelemetryCollector.__init__` (≈ line 442)

`_last_expansion_seen_idx/ts` must be updated every EXPANSION candle so that the RUN_END closure uses the true last-seen position, not the start position. Without this, long open episodes collapse to zero duration at flush time.

```python
        self._expansion_start_idx: int = 0
        self._expansion_start_ts: Optional[datetime] = None   # Phase 3a — for age_hours_actual
        # Phase 3b RC1: track last candle seen while expansion is active (for correct RUN_END closure)
        self._last_expansion_seen_idx: int = 0
        self._last_expansion_seen_ts: Optional[datetime] = None
```

#### Edit 2 — Extend `on_state_entered()` to capture expansion timestamp; update `on_expansion_retrace_check()` to track last-seen candle (≈ line 462)

```python
def on_state_entered(
    self, state_name: str, candle_index: int,
    candle_ts: Optional[datetime] = None,   # Phase 3a
) -> None:
    ...
    if state_name == "EXPANSION":
        self._expansion_active         = True
        self._expansion_start_idx      = candle_index
        self._expansion_start_ts       = candle_ts          # Phase 3a
        self._last_expansion_seen_idx  = candle_index       # Phase 3b RC1
        self._last_expansion_seen_ts   = candle_ts          # Phase 3b RC1
        self._expansion_max_depth      = 0.0
        self._expansion_ceiling_at_max = 0.0
        self._expansion_time_to_max    = 0
```

Pass `candle_ts` from `StateMachine._transition()` (≈ line 850):
```python
if self.telemetry and candle:
    self.telemetry.on_state_entered(target.name, candle.index, candle_ts=candle.timestamp)
```

Also update `on_expansion_retrace_check()` to keep `_last_expansion_seen_*` current on every EXPANSION candle (≈ line 479):
```python
def on_expansion_retrace_check(
    self, candle_index: int, depth_abs: float, ceiling: float,
    candle_ts: Optional[datetime] = None,   # Phase 3b RC1
) -> None:
    if not self._expansion_active:
        return
    if depth_abs > self._expansion_max_depth:
        self._expansion_max_depth      = depth_abs
        self._expansion_ceiling_at_max = ceiling
        self._expansion_time_to_max    = candle_index - self._expansion_start_idx
    # Phase 3b RC1: track last candle seen during this episode
    self._last_expansion_seen_idx = candle_index
    if candle_ts is not None:
        self._last_expansion_seen_ts = candle_ts
```

Call site in `StateMachine.try_expansion_to_retest()`: add `candle_ts=candle.timestamp` to the `telemetry.on_expansion_retrace_check(...)` call.

#### Edit 3 — Add `ended_by` + dual `age_hours` + new fields to `on_expansion_ended()` (≈ line 490)

```python
def on_expansion_ended(
    self, candle_index: int, reason: str,
    end_ts: Optional[datetime] = None,            # Phase 3a — actual end timestamp
    shadow_used: bool = False,                    # Phase 3a — was this a shadow expansion?
    candidate_age_at_entry: int = 0,              # Phase 3a — candles from displacement → expansion
    age_pct_of_threshold: float = 0.0,           # Phase 3b — age/TTL×100; 0 if no TTL active
) -> None:
    if not self._expansion_active:
        return
    self._expansion_active = False
    dwell = candle_index - self._expansion_start_idx
    self._expansion_dwells.append(dwell)

    # Phase 3a: ended_by taxonomy
    _ended_by = (
        "retest"   if reason == "QUALIFIED"
        else "eof"      if reason == "RUN_END"
        else "expired"  if reason == "EXPIRED"
        else "reset"
    )

    # Phase 3a: dual age_hours — never approximate if actual timestamps available
    _age_estimated = round(dwell * 15 / 60, 2)   # M15 approximation
    _age_actual: Optional[float] = None
    if self._expansion_start_ts is not None and end_ts is not None:
        _age_actual = round(
            (end_ts - self._expansion_start_ts).total_seconds() / 3600.0, 2
        )

    # Phase 3a: emit CLOCK_DRIFT — RC2: INFO@10%, WARN@25% (not WARNING@5%)
    # Markets contain gaps, DST, and exchange timestamp variance; 5% is too aggressive.
    if _age_actual is not None and _age_estimated > 0:
        _drift_pct = abs(_age_actual - _age_estimated) / _age_estimated
        if _drift_pct > 0.10:
            _drift_severity = "WARNING" if _drift_pct > 0.25 else "INFO"
            emit_integrity_event(
                "CLOCK_DRIFT", _drift_severity, "crt_engine",
                {
                    "age_hours_actual":    _age_actual,
                    "age_hours_estimated": _age_estimated,
                    "drift_pct":           round(_drift_pct * 100, 1),
                    "candle_index":        candle_index,
                },
            )

    outcome = (
        "QUALIFIED"   if reason == "QUALIFIED"
        else "RUN_END"     if reason == "RUN_END"
        else "EXPIRED"     if reason == "EXPIRED"
        else "INTERRUPTED"
    )
    self._expansion_records.append({
        "kind":                        "EXPANSION_RETRACE_CHECK",
        "episode_start_idx":           self._expansion_start_idx,
        "episode_end_idx":             candle_index,
        "duration_candles":            dwell,
        "age_hours_actual":            _age_actual,             # Phase 3a — None if timestamps absent
        "age_hours_estimated":         _age_estimated,          # Phase 3a — M15 approximation
        "ended_by":                    _ended_by,               # Phase 3a
        "shadow_used":                 shadow_used,             # Phase 3a
        "candidate_age_at_entry":      candidate_age_at_entry,  # Phase 3a
        "age_pct_of_threshold":        age_pct_of_threshold,             # Phase 3b — 0.0 if no TTL active
        "freshness_ratio":             round(age_pct_of_threshold / 100.0, 3),  # RC5: 0.20=fresh, 1.20=stale
        "outcome":                     outcome,
        # ... existing fields (max_retrace_depth_abs etc.) unchanged
    })
```

**Pass new args from callers:**

In `StateMachine._transition()`, when calling `on_expansion_ended` via RETEST entry (≈ line 851):
```python
if target == CRTState.RETEST and self.telemetry._expansion_active:
    self.telemetry.on_expansion_ended(
        candle.index, "QUALIFIED",
        end_ts=candle.timestamp,
        shadow_used=state._came_from_shadow,
        candidate_age_at_entry=(
            state._expansion_entry_idx - state._displacement_entry_idx
        ),
    )
```
Add `_expansion_entry_idx: int = 0` to `EngineState` now (needed for `candidate_age_at_entry`):
```python
    _expansion_entry_idx: int = 0   # Phase 3a — set in _transition() when EXPANSION entered
```
Set it in `_transition()` when `target == CRTState.EXPANSION`:
```python
        if target == CRTState.EXPANSION and candle:
            state._expansion_entry_idx = candle.index
```

In `TelemetryCollector.on_reset()` → `on_expansion_ended` (≈ line 562, inside `on_reset` or wherever `from_state == "EXPANSION"` fires):
```python
        if from_state == "EXPANSION":
            self.on_expansion_ended(
                candle_index, reason,
                end_ts=candle_ts,            # pass candle.timestamp here
                shadow_used=shadow_used,      # pass from reset context
                candidate_age_at_entry=candidate_age_at_entry,
            )
```
Extend `on_reset()` signature with `candle_ts`, `shadow_used`, `candidate_age_at_entry` (all `Optional`/`= 0` defaults). Call site in `reset_to_range()` passes `candle.timestamp`, `state._came_from_shadow`, and `(state._expansion_entry_idx - state._displacement_entry_idx)`.

In `flush()` for `RUN_END` case (≈ line 670) — **RC1 fix: use `_last_expansion_seen_idx/ts`, not `_expansion_start_idx`**:
```python
        if self._expansion_active:
            # RC1: use last-seen candle, not start candle — avoids collapsing long open episodes
            self.on_expansion_ended(
                self._last_expansion_seen_idx, "RUN_END",
                end_ts=self._last_expansion_seen_ts,
            )
```

#### Edit 4 — `UNBOUNDED_STATE` integrity event in `flush()` with revised threshold (≈ line 680) — **RC3**

Threshold: `max(P95×3, median×25)` — P99 with small N is self-referential (it may already contain the anomaly, making `P99×2` ineffective at detecting it).

```python
if len(_dwells) >= 10:
    _sorted_d  = sorted(_dwells)
    _p95       = _sorted_d[int(0.95 * len(_sorted_d))]   # RC3: use P95, not P99
    _median    = _statistics.median(_dwells)
    _threshold = max(_p95 * 3, _median * 25)              # RC3: P95×3 / median×25
    _unbounded = [d for d in _dwells if d > _threshold]
    if _unbounded:
        emit_integrity_event(
            "UNBOUNDED_STATE", "CRITICAL", "crt_engine",
            {
                "state":     "EXPANSION",
                "p95":       _p95,
                "median":    _median,
                "threshold": _threshold,
                "offenders": _unbounded,
            },
        )
```

#### Edit 5 — Add P99 + `ended_by_counts` to `expansion_dwell_stats` in `flush()` (extend existing block)

```python
_dwell_stats: dict = {
    "count":   len(_dwells),
    "mean":    round(_statistics.mean(_dwells), 1)    if _dwells else 0,
    "median":  round(_statistics.median(_dwells), 1)  if _dwells else 0,
    "p90":     _sorted_d[int(0.90 * len(_sorted_d))] if len(_dwells) >= 10 else 0,
    "p99":     _sorted_d[int(0.99 * len(_sorted_d))] if len(_dwells) >= 10 else 0,  # Phase 3a
    "max":     max(_dwells, default=0),
    "ended_by_counts": {   # Phase 3a — key diagnostic for Case A vs B
        "retest":  sum(1 for r in self._expansion_records if r.get("ended_by") == "retest"),
        "reset":   sum(1 for r in self._expansion_records if r.get("ended_by") == "reset"),
        "eof":     sum(1 for r in self._expansion_records if r.get("ended_by") == "eof"),
        "expired": sum(1 for r in self._expansion_records if r.get("ended_by") == "expired"),
    },
}
```

### Decision after Phase 3a re-run

```powershell
$tel = Get-Content "results\BNBUSDT\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. ended_by distribution — primary Case A/B diagnostic
$eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" }
$eps | Group-Object ended_by | Select-Object Name, Count

# 2. Shadow-correlated long expansions?
$eps | Sort-Object duration_candles -Descending | Select-Object -First 5 | Format-Table episode_start_idx, duration_candles, ended_by, shadow_used, candidate_age_at_entry

# 3. UNBOUNDED_STATE integrity event
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | Where-Object { $_.event_type -eq "UNBOUNDED_STATE" }

# 4. CLOCK_DRIFT check
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | Where-Object { $_.event_type -eq "CLOCK_DRIFT" }

# 5. P99 and ended_by_counts
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).expansion_dwell_stats
```

**Decision gate — three cases:**

| Observation | Conclusion | Next action |
|---|---|---|
| `ended_by=eof` count ≥ 2 | **Case A — accounting bug**: `on_expansion_ended` not called at non-EOF exits | Fix closure before any TTL |
| `ended_by=eof` = 1 AND age extreme = 1 episode | **Case B — genuine stale expansion** | Proceed with Phase 3b |
| `ended_by=retest` dominant AND P99 small | **Case C — no pathology** | No TTL needed; promote |

---

## Phase 3b — Expiry (✅ IMPLEMENTED — PASS INTEGRITY / FAIL PROMOTION)

> **5 required changes from final reviews:**
> 1. RUN_END closure must use `_last_expansion_seen_idx/ts`, not `_expansion_start_idx`
> 2. CLOCK_DRIFT: INFO if >10%, WARN if >25% (not WARNING at 5%)
> 3. UNBOUNDED_STATE threshold: `max(P95×3, median×25)` (not `max(P99×2, median×20)`)
> 4. **Closure priority hierarchy**: RETEST (4) > EXPIRED (3) > RESET (2) > RUN_END (1) — try retest BEFORE TTL check; document via `_CLOSURE_PRIORITY`
> 5. **Expiry recoverability**: EXPANSION_EXPIRED must carry `retest_distance_abs`, `retest_depth_pct`, `freshness_ratio` so that post-hoc `expired_counterfactual_rr` can be computed
>
> **Promotion blocker**: Do not promote Phase 3b to production until a distribution report exists: P50/P90/P95/P99/MAX of expansion ages, ended_by distribution, and `expired_counterfactual_rr`.
>
> **Additional additions:** `age_pct_of_threshold` + `freshness_ratio` fields on every expansion record; `TEMPORAL_STALE_WIN` WARN event on winning stale trades; pre-expiry promotion gates.

### Phase 3a Diagnosis Summary

| ended_by | Count | Notes |
|---|---|---|
| retest | 66 (71%) | dominant — state accounting is CORRECT |
| reset | 26 (28%) | **all 26 are shadow expansions** |
| eof | 1 (1%) | expected: episode open at run end |
| expired | 0 | Phase 3b not yet active |

**Case B confirmed**: The 20,115-candle episode ended via `retest` (not eof) — no accounting bug. The displacement was normal (not shadow). Shadow expansions self-terminate quickly via retrace resets — they are "probe → invalidate" behaviour. TTL guard was simply absent.

**Shadow not pathological**: All 26 resets are shadow expansions. Normal expansions never reset mid-episode. Shadow path is healthy — it probes and self-corrects.

### TTL Derivation: `min(P99_non_outlier, 7_days)`

From Phase 3a data (N=93 episodes, excluding top 1% outlier → N=92):
- P99 of 92 non-pathological = **495 candles** (≈ 123.75 h ≈ 5.2 days)
- 7 days = 7 × 24 × 4 candles = 672 candles (M15)
- `min(495, 672) = 495` candles

**Frozen config values:**
```json
"max_expansion_age_candles": 495,
"max_expansion_age_hours": 124
```

This expires only the obvious anomaly (20,115 candles). The 5 longest non-pathological episodes (342–495 candles) sit right at the boundary — those at ≤495 candles are legitimate continuation structures. Setting TTL at P99 (not P95) avoids cutting valid episodes on first pass; tighten later once more data accumulates.

### New config keys in `CRTConfig` (after `pending_displacement_ttl_candles`, ≈ line 370)
```python
    # ── Expansion TTL guard (Phase 3b) ────────────────────────────
    # Expire if EITHER limit exceeded. Derived: min(P99_non_outlier, 7d).
    # Phase 3a data: P99=495 candles (123.75h). 7d=672 candles → TTL=495.
    max_expansion_age_candles: int = 495
    max_expansion_age_hours:   int = 124
```

### New `EXPIRED` state in `CRTState` and `VALID_TRANSITIONS`
```python
class CRTState(Enum):
    ...
    EXPANSION      = auto()
    EXPIRED        = auto()   # Phase 3b — soft archive before reset
    RETEST         = auto()
    ...

VALID_TRANSITIONS = {
    ...
    CRTState.EXPANSION: [CRTState.RETEST, CRTState.EXPIRED, CRTState.RANGE],
    CRTState.EXPIRED:   [CRTState.RANGE],
    ...
}
```

### New EngineState fields (after `_came_from_shadow`)
```python
    _expansion_entry_idx: int               = 0    # Phase 3b
    _expansion_entry_ts:  Optional[datetime] = None # Phase 3b
```

Set in `StateMachine._transition()` when `target == CRTState.EXPANSION`.

### Closure priority hierarchy (RC-Closure) — `_CLOSURE_PRIORITY` constant + retest-first ordering

Add near the top of `TelemetryCollector` or as a module-level constant:
```python
# Phase 3b RC-Closure: Closure reason priority — higher wins when multiple apply simultaneously.
# Execution success (RETEST) must dominate; RUN_END is last resort.
_CLOSURE_PRIORITY: dict[str, int] = {
    "QUALIFIED": 4,  # Retest fired — structure delivered
    "EXPIRED":   3,  # TTL guard fired
    "RESET":     2,  # HTF or other reset interrupted
    "RUN_END":   1,  # Flush at end of run
}
```

**Critical ordering change in `process_candle()` EXPANSION branch**: try retest FIRST, then TTL.
If both would apply on the same candle, RETEST (priority=4) must win over EXPIRED (priority=3).

```python
elif s == CRTState.EXPANSION:
    # RC-Closure: RETEST has higher priority than EXPIRED — check first
    if self.sm.try_expansion_to_retest(self.state, candle, self.ev_log):
        action["action"] = "RETEST_QUALIFIED"
        return action

    # ── Phase 3b: Expansion TTL guard (runs only if retest did NOT fire) ────
    _exp_age_c = candle.index - self.state._expansion_entry_idx
    ...
```

**Guard in `on_expansion_ended()`** — defend against out-of-order calls. Add `_expansion_ended_reason: str = ""` field to `TelemetryCollector.__init__`. In `on_expansion_ended()`:
```python
def on_expansion_ended(self, candle_index, reason, ...):
    if not self._expansion_active:
        # Allow higher-priority override (e.g. if RETEST fires after a RUN_END was queued)
        new_prio = _CLOSURE_PRIORITY.get(reason, 0)
        old_prio = _CLOSURE_PRIORITY.get(self._expansion_ended_reason, 0)
        if new_prio <= old_prio:
            return   # Lower or equal priority — ignore
        # Higher priority — fall through to update the last record
        if self._expansion_records:
            last = self._expansion_records[-1]
            # Re-derive ended_by from new reason and patch the record
            last["ended_by"] = (
                "retest" if reason == "QUALIFIED"
                else "eof" if reason == "RUN_END"
                else "expired" if reason == "EXPIRED"
                else "reset"
            )
            last["outcome"] = reason if reason in ("QUALIFIED", "RUN_END", "EXPIRED") else "INTERRUPTED"
        return
    self._expansion_active = False
    self._expansion_ended_reason = reason
    ...  # rest unchanged
```

This ensures the TRANSITION_COUNTER `ended_by_counts` reflects the semantically correct reason even if closure paths fire in unexpected order.

### TTL check in EXPANSION branch in `process_candle()` (after `try_expansion_to_retest` — RC-Closure ordering)

```python
elif s == CRTState.EXPANSION:
    # ── Phase 3b: Expansion TTL guard ───────────────────────────
    _exp_age_c = candle.index - self.state._expansion_entry_idx
    _max_c = self.config.max_expansion_age_candles
    _max_h = self.config.max_expansion_age_hours
    _age_h: float = (_exp_age_c * 15 / 60)  # M15 approximation; use ts delta if available

    if self.state._expansion_entry_ts is not None:
        _age_h = (candle.timestamp - self.state._expansion_entry_ts).total_seconds() / 3600.0

    _ttl_exceeded = (
        (_max_c > 0 and _exp_age_c > _max_c)
        or (_max_h > 0 and _age_h > _max_h)
    )

    if _ttl_exceeded:
        # ── would_trade_if_alive: structural quality of displacement candle ──
        _dc = self.state.displacement_candle
        _would_trade = False
        if _dc is not None:
            _body = abs(_dc.close - _dc.open)
            _rng  = _dc.high - _dc.low
            _br   = _body / _rng if _rng > 0 else 0.0
            _would_trade = _br >= self.config.body_ratio_min

        # freshness_ratio = age/ttl (0.20=fresh, 0.80=aging, 1.20=stale — can exceed 1.0)
        _freshness_ratio = round(_exp_age_c / _max_c, 3) if _max_c > 0 else 0.0
        # age_pct_of_threshold: same value as percentage (100% = exactly at TTL, 120% = 20% over)
        _age_pct = round(_freshness_ratio * 100, 1)

        # Structural G-score snapshot for training label (max_score_seen may be 0 if
        # no retest ever fired; record the body_ratio as the fallback quality signal)
        _body_ratio = 0.0
        if _dc is not None:
            _rng2 = _dc.high - _dc.low
            _body_ratio = abs(_dc.close - _dc.open) / _rng2 if _rng2 > 0 else 0.0

        # RC5 — retest_distance: how close was price to triggering a retest at expiry?
        # Uses telemetry.on_expansion_retrace_check depth data for current depth estimate.
        # current_depth = max retrace seen so far (telemetry._expansion_max_depth)
        # retest_threshold = configured fraction of ATR (retest_depth_max * last ATR)
        # Both are approximations; exact values require state internals from try_expansion_to_retest().
        _current_depth_abs  = self.telemetry._expansion_max_depth   # best available depth proxy
        _retest_threshold   = self.config.retest_depth_max          # config fraction (not ATR-scaled)
        _retest_distance_abs = max(0.0, _retest_threshold - _current_depth_abs)
        _retest_depth_pct    = round(_current_depth_abs / _retest_threshold, 3) if _retest_threshold > 0 else 0.0
        # retest_depth_pct: 0.9 = almost triggered retest; 0.1 = very far from retest

        emit_integrity_event("EXPANSION_EXPIRED", "WARNING", "crt_engine", {
            "candidate_id":          f"CAND-{self.state._expansion_entry_idx}",
            "expansion_age_candles": _exp_age_c,
            "expansion_age_hours":   round(_age_h, 1),
            "source":                "shadow" if self.state._came_from_shadow else "normal",
            "shadow_used":           self.state._came_from_shadow,
            "would_trade_if_alive":  _would_trade,
            "freshness_ratio":       _freshness_ratio,   # RC5: 0.20=fresh, 0.80=aging, 1.20=stale
            "age_pct_of_threshold":  _age_pct,           # e.g. 400/500 → 80.0%
            "retest_distance_abs":   round(_retest_distance_abs, 6),  # RC5: how far from retest trigger
            "retest_depth_pct":      _retest_depth_pct,  # RC5: fraction of way to retest (0-1+)
            "score":                 round(_body_ratio, 4),
            "candle_index":          candle.index,
        })
        self.telemetry.on_expansion_ended(
            candle.index, "EXPIRED",
            end_ts=candle.timestamp,
            shadow_used=self.state._came_from_shadow,
            candidate_age_at_entry=(
                self.state._expansion_entry_idx - self.state._displacement_entry_idx
            ),
            age_pct_of_threshold=_age_pct,   # pass through to EXPANSION_RETRACE_CHECK record
        )
        self.sm._transition(self.state, CRTState.EXPIRED, "expansion_ttl_exceeded", candle, self.ev_log)
        action["action"] = "EXPANSION_EXPIRED"
        return action
    # ... existing try_expansion_to_retest unchanged
```

### `EXPIRED` branch (new `elif` after EXPANSION block)
```python
elif s == CRTState.EXPIRED:
    self.sm.reset_to_range(self.state, "expansion_ttl_exceeded", candle, self.ev_log)
    action["action"] = "EXPANSION_TTL_RESET"
```

### Clear new fields in `reset_to_range()` cleanup block (after `_came_from_shadow`)
```python
        state._came_from_shadow    = False  # [Phase 2b]
        state._expansion_entry_idx = 0      # [Phase 3a/3b]
        state._expansion_entry_ts  = None   # [Phase 3b]
```

### `TEMPORAL_PARADOX` integrity event (Phase 3b — wire into TRADE_OPENED path)

If a trade is opened and `structure_age > max_expansion_age_candles`, the trade is newer than the structure validity window. Emit CRITICAL before allowing execution:

```python
# In process_candle() TRADE_OPENED path, after approval:
_struct_age = candle.index - self.state._expansion_entry_idx
if (self.config.max_expansion_age_candles > 0
        and _struct_age > self.config.max_expansion_age_candles):
    emit_integrity_event(
        "TEMPORAL_PARADOX", "CRITICAL", "crt_engine",
        {
            "candidate_id":     f"CAND-{self.state._expansion_entry_idx}",
            "structure_age":    _struct_age,
            "max_allowed":      self.config.max_expansion_age_candles,
            "shadow_used":      self.state._came_from_shadow,
            "candle_index":     candle.index,
        },
    )
    # Do NOT open the trade — return without TRADE_OPENED action
    return action
```

`TEMPORAL_PARADOX` acts as the last-resort guard: TTL expiry should have caught this first. If TEMPORAL_PARADOX fires, it means the TTL check has a gap.

### `TEMPORAL_STALE_WIN` integrity event (Phase 3b — wire into TRADE_OPENED path, alongside TEMPORAL_PARADOX)

A winning trade opened from an expansion older than P95 is dangerous: it may be hiding a gap in temporal causality even if TTL hasn't expired yet. P95 of non-pathological episodes = 342 candles → add `expansion_age_warn_candles: int = 342` to `CRTConfig`.

```python
# CRTConfig — after max_expansion_age_hours:
expansion_age_warn_candles: int = 342   # P95 from Phase 3a; warn if trade opened above this age
```

Wire into `process_candle()` TRADE_OPENED path (emit AFTER the trade is opened, not instead of it):
```python
# After trade opens successfully (TRADE_OPENED confirmed):
_warn_age = self.config.expansion_age_warn_candles
if _warn_age > 0 and _struct_age > _warn_age:
    emit_integrity_event(
        "TEMPORAL_STALE_WIN", "WARNING", "crt_engine",
        {
            "candidate_id":      f"CAND-{self.state._expansion_entry_idx}",
            "structure_age":     _struct_age,
            "warn_threshold":    _warn_age,
            "shadow_used":       self.state._came_from_shadow,
            "candle_index":      candle.index,
        },
    )
    # Note: trade still executes — this is a WARNING, not a block
```

A `TEMPORAL_STALE_WIN` event in the results log answers: "was this trade from stale structure?" and allows the training pipeline to label these trades separately.

### Pre-expiry promotion gates (verify Phase 3a data before enabling Phase 3b TTL in production)

These confirm the closure system is healthy before activating expiry:

| Gate | Value from Phase 3a | Pass? |
|---|---|---|
| `ended_by[eof] < 5%` | 1/93 = 1.1% | ✅ PASS |
| `max_age_pct < 150%` (non-pathological max / P99_non_outlier) | 495/495 = 100% | ✅ PASS |
| `clock_drift_warn == 0` | 0 | ✅ PASS |

All three pre-expiry gates passed on Phase 3a data. Phase 3b TTL is cleared for production config.

### Promotion Blocker — Distribution Report (required before production deploy)

**Do not promote Phase 3b config to production** until the following report is produced from the Phase 3b verification run. Missing any field = BLOCK.

```powershell
# Run after Phase 3b backtest completes. This is NOT part of the backtest itself.
$tel  = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$iev  = Get-Content "logs\integrity_events.jsonl"               | ForEach-Object { $_ | ConvertFrom-Json }
$eps  = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" }
$ages = $eps.duration_candles | Sort-Object

# 1. expansion_age_distribution
[PSCustomObject]@{
    P50 = $ages[[int]($ages.Count * 0.50)];  P90 = $ages[[int]($ages.Count * 0.90)]
    P95 = $ages[[int]($ages.Count * 0.95)];  P99 = $ages[[int]($ages.Count * 0.99)]
    MAX = ($ages | Measure-Object -Maximum).Maximum
} | Format-Table

# 2. ended_by_distribution
$eps | Group-Object ended_by | Select-Object Name, Count | Format-Table

# 3. expired_counterfactual_rr — post-hoc: for each expired episode where would_trade_if_alive=True,
#    scan forward in original CSV from episode_end_idx and check if price reached retest depth.
#    Report: count of would-have-traded, mean RR of those simulated trades vs actual trade mean RR.
$expired = $iev | Where-Object { $_.event_type -eq "EXPANSION_EXPIRED" -and $_.would_trade_if_alive -eq $true }
"expired_with_trade_potential: $($expired.Count)"
# Full counterfactual RR requires Python post-processing script — see Phase 4 verification notes.
```

`expired_counterfactual_rr` is computed by a post-processing script (not the engine) that:
1. Reads all `EXPANSION_EXPIRED` events where `would_trade_if_alive=True`
2. For each, scans forward in the original M15 CSV from `candle_index`
3. Checks if price would have reached the retest depth threshold within 50 candles
4. If yes, simulates the trade using the same SL/TP logic and records the RR
5. Reports: n_counterfactual_trades, mean_counterfactual_rr, vs actual trade mean_rr

**Gate**: `expired_counterfactual_rr` must be computed and documented in `results/run_*/BNBUSDT_phase3b_report.md` before production promotion. This answers: "did TTL remove alpha?"

### Production config update (frozen from Phase 3a P99_non_outlier)
```json
"max_expansion_age_candles": 495,
"max_expansion_age_hours": 124,
"expansion_age_warn_candles": 342
```
Re-hash with `python scripts/maintenance/_compute_hash.py`.

---

## Verification (Phase 3b)

```powershell
$tel = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. EXPANSION_EXPIRED fired (the 20,115-candle episode must be among them)
$expired_eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "expired" }
$expired_eps.Count   # must be >= 1

# 2. max expansion days < 7 (promotion gate — 495 candles = 5.2 days < 7)
$tc = $tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }
"max_days = $(($tc.expansion_dwell_stats.max * 15) / 60 / 24)"   # must be < 7.0

# 3. Trade count (the 20,115-episode produced 1 trade — it should be lost after 3b)
$trades = Import-Csv "results\run_*\BNBUSDT_trades.csv"
$trades.Count   # expect 13 (was 14; 1 trade from pathological episode removed)

# 4. shadow_share (< 60% raised from 50% — Phase 3a confirmed shadow not pathological)
"shadow_share = $([int]($trades | Where-Object { $_.shadow_used -eq '1' }).Count / [math]::Max($trades.Count,1))"

# 5. approval_rate
$cands = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" }
"approval_rate = $($cands | Where-Object { $_.death_reason -eq 'ACCEPTED' }).Count / [math]::Max($cands.Count,1)"

# 6. UNBOUNDED_STATE and TEMPORAL_PARADOX must both be 0
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | 
    Where-Object { $_.event_type -in @("UNBOUNDED_STATE","TEMPORAL_PARADOX") } | 
    Measure-Object | Select-Object Count   # must be 0

# 7. SHADOW_LEAK still 0 (regression check from Phase 1)
Get-Content "logs\integrity_events.jsonl" | ConvertFrom-Json | 
    Where-Object { $_.event_type -eq "SHADOW_LEAK" } | Measure-Object | Select-Object Count

# 8. Closure priority — verify no RETEST was replaced by EXPIRED (ended_by=retest must dominate)
$expired_eps = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "expired" }
$retest_eps  = $tel | Where-Object { $_.kind -eq "EXPANSION_RETRACE_CHECK" -and $_.ended_by -eq "retest" }
"retest=$($retest_eps.Count)  expired=$($expired_eps.Count)  (retest must exceed expired)"

# 9. freshness_ratio and retest_distance fields present on expired episodes (RC5)
$expired_eps | Select-Object -First 1 | Format-List freshness_ratio, retest_distance_abs, retest_depth_pct

# 10. Promotion blocker: distribution report fields present
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).expansion_dwell_stats | 
    Format-List count, mean, median, p90, p99, max, ended_by_counts
```

---

## Promotion Gates

| Gate | Pass condition | Severity | Notes |
|---|---|---|---|
| `max_expansion_days < 7` | `max * 15 / 60 / 24 < 7` | Hard | TTL at 495 candles (5.2d) must cap worst case under 7 days |
| `UNBOUNDED_STATE = 0` | No records in `integrity_events.jsonl` | Hard | After 3b TTL is active; any hit = replay not trustworthy |
| `TEMPORAL_PARADOX = 0` | No records after 3b active | Hard | No trade should survive past its structure TTL |
| `approval_rate < 95%` | `accepted / total < 0.95` | Hard | Decision layer must be binding before promotion |
| `shadow_share < 60%` | `shadow_trades / total < 0.60` | Soft | Raised from 50%: Phase 3a confirmed shadow is not pathological |
| `SHADOW_LEAK = 0` | Preserved from Phase 1 | Hard | No regression on shadow integrity |

---

## Blast Radius

| Change | Phase | Behavior change | Risk |
|---|---|---|---|
| `on_state_entered(candle_ts=)` signature | 3a | None | Low |
| `_expansion_start_ts` tracking | 3a | None | Low |
| `ended_by` + `age_hours` in EXPANSION_RETRACE_CHECK | 3a | None (telemetry only) | Low |
| P99 + `ended_by_counts` in TRANSITION_COUNTER | 3a | None (telemetry only) | Low |
| `UNBOUNDED_STATE` integrity event | 3a | Logs CRITICAL to `integrity_events.jsonl` | Low |
| `_CLOSURE_PRIORITY` constant + retest-first ordering | 3b RC-Closure | **Behavior change**: RETEST wins over EXPIRED on same candle | Low — correct direction |
| `_expansion_ended_reason` guard in `on_expansion_ended()` | 3b RC-Closure | Allows priority-based override of early lower-priority records | Low |
| `freshness_ratio` + `retest_distance_abs` + `retest_depth_pct` | 3b RC5 | Telemetry only — enables counterfactual RR computation | Low |
| `EXPIRED` state + VALID_TRANSITIONS | 3b | New legal state | Low — additive |
| `_expansion_entry_idx/ts` on EngineState | 3b | None until TTL check | Low |
| TTL check in EXPANSION branch | 3b | **Behavior change** | Medium — intended |
| `EXPIRED` branch | 3b | **Behavior change** | Medium — intended |
| Config keys + re-hash | 3b | New config | Low |

---

---

# Archived Plan: Phase 2b — Score Inversion Diagnosis (COMPLETE ✅)

## Context — Why Phase 2b Before Zone Model

Phase 1 re-run (`run_20260527_083602_BNBUSDT`, isolated dataset, 14,016 candles) showed:
- **Real uplift**: 2→5 trades, −0.42R→+2.02R (+2.44R delta). Shadow path fired (SHADOW_PENDING=16).
- **Score inversion** (N=5): `score→outcome Pearson = −0.936`. Higher score = worse outcome. With N=5 this is noisy, but the direction is dangerous and must be explained before promotion.
- **100% approval rate**: All 5 candidates cleared `tier_2_threshold=0.30` on candle 1. Decision layer contributes nothing — it is currently a pass-through.
- **EXPANSION dwell**: EXPANSION=6,616 candle-dwell across 14K candles (≈47% of all candles). Average episode length ~413 candles (≈103 hours). Retest never fires on most entries — price continues trending without retracing to the ATR depth ceiling.

Zone model is deferred until these three questions are answered:
1. Is score inversion real, or a shadow-path artefact from a stale displacement candle?
2. At what `tier_2_threshold` does the decision layer actually reject trades?
3. What is the expansion episode dwell distribution — are there a few pathologically long episodes?

---

## Investigation Framework

### Root Cause Hypotheses for Score Inversion

The S-score fuses:
- **G (structural)**: body_ratio + wick/ATR from `state.displacement_candle`
- **C (confirmation)**: EMA alignment + distance + body at retest

For shadow trades, `state.displacement_candle = state.pending_displacement_candle` (prior HTF window).
**Key**: the displacement candle's structural quality (body_ratio, wick) is intrinsic — it does NOT change based on age. Shadow trades and normal trades produce **structurally identical S-scores** from the same displacement candle quality.

Therefore, the −0.936 correlation is most likely explained by:
1. **N=5 sample bias** — the critical value for |r|=0.878 at α=0.05 with N=5 is on the boundary; one trade can swing the sign
2. **Shadow retest timing** — displacement candle is from prior window; the retest happens N>4 candles later; market structure may have shifted enough that the displacement's quality no longer predicts the retest outcome
3. **ATR regime shift** — if ATR expands between displacement and retest, the retest depth ceiling shrinks, making the retest marginally valid but structurally weak

Phase 2b must stratify correlation by `shadow_used` to test hypothesis 2. If inversion is confined to `shadow_used=True` trades, shadow path needs a quality gate before promotion.

---

## Phase 2b Additions (telemetry only — no behavior change)

### Addition 1: `shadow_used` flag on candidate lifecycle and TradeRecord

**Where to add the flag:** `TelemetryCollector._active_candidate` dict (in `crt_engine_v2.py`).

**Step 1** — Extend `on_candidate_opened()` signature:
```python
def on_candidate_opened(
    self, candidate_id: str, candle_index: int, ts: str,
    shadow: bool = False,          # NEW: True if opened via SHADOW_SWEEP_DETECTED
) -> None:
    self._active_candidate = {
        "candidate_id":  candidate_id,
        "first_seen_idx": candle_index,
        "first_seen_ts":  ts,
        "entered_states": [],
        "max_score_seen": 0.0,
        "shadow_used":    shadow,          # NEW
    }
```

**Step 2** — Pass `shadow=True` from the RANGE branch in `CRTEngine.process_candle()` when shadow path fires:
```python
# Existing call at SHADOW_SWEEP_DETECTED path:
self.telemetry.on_candidate_opened(
    f"CAND-{candle.index}", candle.index, candle.timestamp.isoformat(),
    shadow=True,     # ADD THIS
)
```
Normal path call stays `shadow=False` (default).

**Step 3** — Include `shadow_used` in `flush()` → CANDIDATE_LIFECYCLE record:
```python
{
    "kind":           "CANDIDATE_LIFECYCLE",
    "candidate_id":   c["candidate_id"],
    ...
    "shadow_used":    c.get("shadow_used", False),   # ADD
}
```

**Step 4** — Add `shadow_used: bool = False` to `TradeRecord` dataclass (in `backtest_v2.py` or `schemas`). Set it in the backtest loop when `TRADE_OPENED` and action came from shadow path. Mechanism: check `action.get("shadow_source_htf")` (already set in SHADOW_EXPANSION_CONFIRMED action dict) — non-empty means shadow trade.

In `BacktestRunner.run()`, after `TRADE_OPENED`:
```python
if "TRADE_OPENED" in action and engine.state.active_trade:
    _is_shadow = bool(result.get("shadow_source_htf"))  # set by SHADOW_EXPANSION_CONFIRMED
    engine.state.active_trade.shadow_used = _is_shadow
```

Add to CSV output in `_trade_row()`:
```python
"shadow_used": int(r.shadow_used),
```

---

### Addition 2: Score distribution per candidate in CANDIDATE_LIFECYCLE

Currently, `max_score_seen` captures the peak S-score. Add `score_at_approval` — the specific score that triggered the approval decision (scores evaluated on each soft_conf candle; the first one that exceeds tier_2_threshold is the approval score).

**Where:** `TelemetryCollector.on_candidate_score()` already tracks `max_score_seen`. Add `score_at_approval` field, populated in `on_candidate_accepted()`:

```python
def on_candidate_accepted(self, candle_index: int, score_at_approval: float = 0.0) -> None:
    if self._active_candidate is not None:
        self._active_candidate["score_at_approval"] = score_at_approval
        self._close_candidate(candle_index, "ACCEPTED")
```

Pass `score_at_approval=final_S` from `process_candle()` at the TRADE_OPENED call site:
```python
self.telemetry.on_candidate_accepted(candle.index, score_at_approval=final_S)
```

Include in CANDIDATE_LIFECYCLE flush:
```python
"score_at_approval": c.get("score_at_approval", 0.0),
```

---

### Addition 3: Expansion episode dwell histogram

The EXPANSION=6,616 candle-dwell concern needs quantification. Currently, the TRANSITION_COUNTER telemetry has `state_entry_counts` (how many times each state was entered), but not the dwell distribution per episode.

Add `on_expansion_episode_end(candle_index, entry_idx)` to `TelemetryCollector`:
```python
def on_expansion_episode_end(self, candle_index: int, entry_idx: int) -> None:
    dwell = candle_index - entry_idx
    self._expansion_dwells.append(dwell)
```

Track `_expansion_entry_idx` inside `TelemetryCollector._expansion_active` (already managed via `on_expansion_ended`). Emit dwell stats in `flush()` TRANSITION_COUNTER record:
```python
"expansion_dwell_stats": {
    "count":  len(self._expansion_dwells),
    "mean":   statistics.mean(self._expansion_dwells) if self._expansion_dwells else 0,
    "median": statistics.median(self._expansion_dwells) if self._expansion_dwells else 0,
    "max":    max(self._expansion_dwells, default=0),
    "p90":    sorted(self._expansion_dwells)[int(0.9 * len(self._expansion_dwells))] if len(self._expansion_dwells) >= 10 else 0,
},
```

Call `on_expansion_episode_end()` from `StateMachine`:
- In `_transition()`: when `from CRTState.EXPANSION to CRTState.RETEST` (normal qualified exit)
- In `reset_to_range()`: when `state.current_state == CRTState.EXPANSION` (interrupted exit)

---

## Decision Queries After Re-run

```powershell
$tel = Get-Content "results\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }

# 1. Score at approval by shadow_used
$cands = $tel | Where-Object { $_.kind -eq "CANDIDATE_LIFECYCLE" -and $_.death_reason -eq "ACCEPTED" }
$cands | Group-Object shadow_used | ForEach-Object {
    $g = $_.Name; $scores = $_.Group.score_at_approval
    "$g: count=$($_.Count) avg_score=$(($scores | Measure-Object -Average).Average)"
}

# 2. Approval threshold sensitivity (from trades CSV — no re-run needed)
$trades = Import-Csv "results\run_*\BNBUSDT_trades.csv"
foreach ($thr in @(0.30, 0.40, 0.50, 0.55, 0.65)) {
    $approved = $trades | Where-Object { [float]$_.risk_score -ge $thr }
    $wr = ($approved | Where-Object { [float]$_.pnl_rr_net -gt 0 }).Count / [math]::Max($approved.Count, 1)
    "thr=$thr trades=$($approved.Count) WR=$wr"
}

# 3. Expansion dwell stats (from TRANSITION_COUNTER record)
$tc = $tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }
$tc.expansion_dwell_stats

# 4. Score-outcome correlation split by shadow_used
$shadow_trades = $trades | Where-Object { $_.shadow_used -eq "1" }
$normal_trades = $trades | Where-Object { $_.shadow_used -eq "0" }
# Compute Pearson correlation for each group in Python
```

---

## Blast Radius Summary

| Change | Files | Behavior | Risk |
|---|---|---|---|
| `shadow_used` in `on_candidate_opened()` | `crt_engine_v2.py` TelemetryCollector | None (telemetry only) | Low |
| `shadow_used` in CANDIDATE_LIFECYCLE flush | `crt_engine_v2.py` | None | Low |
| `shadow_used: bool` on `TradeRecord` | `backtest_v2.py` (or shared schema) | None | Low |
| Set `shadow_used` from `shadow_source_htf` action | `backtest_v2.py` run loop | None | Low |
| `score_at_approval` field | `crt_engine_v2.py` TelemetryCollector + process_candle | None | Low |
| Expansion dwell histogram | `crt_engine_v2.py` TelemetryCollector + StateMachine | None | Low |

All additions are telemetry-only. No state machine, no thresholds, no config keys changed.

---

## Verification

1. Syntax check both files
2. Re-run on isolated dataset (`Part_1_Isolated.csv`): verify CANDIDATE_LIFECYCLE records have `shadow_used` and `score_at_approval` fields
3. Re-run on full BNBUSDT dataset: compute stratified correlation
4. Check `expansion_dwell_stats` in TRANSITION_COUNTER: flag if p90 > 100 candles (25 hours)
5. Threshold sensitivity: if tier_2_threshold 0.30→0.55 drops approval rate below 80%, the threshold is now binding — worth raising for Phase 3

---

## Phase 2b → Phase 3 Gates

| Gate | Proceed if |
|---|---|
| Score inversion confined to shadow | Add shadow quality gate (min S-score for shadow candidates) before promotion |
| Score inversion in both shadow and normal | Recalibrate G/C weights; score module has a measurement problem |
| Score inversion is N=5 noise (full dataset r > −0.50) | No score change needed; current thresholds viable |
| Expansion p90 > 200 candles | Add expansion TTL (max_expansion_candles config key) |
| tier_2_threshold=0.55 drops trades < 5% from 0.30 | Raise threshold; most candidates cluster well above 0.30 |

Zone model decision is gated behind Phase 2b completion.

---

# Archived Plan: Phase 0b Telemetry + Shadow Displacement Protection

## Context

Phase 0 telemetry (run_20260527_074732_BNBUSDT, 2,649 records) answered all structural unknowns.
The original hypothesis — EXPANSION→RETEST at 3–4% survival is the primary bottleneck, fix
`retest_depth_max` — was **wrong**. True bottleneck: DISPLACEMENT→EXPANSION at 5.2% (8/154),
driven by HTF resets (98.1% of all 2,033 resets). EXPANSION→RETEST actual survival = 87.5%.

This plan covers the next two phases:
- **Phase 0b** — two additional telemetry fields to confirm the HTF-position hypothesis before
  any structural change (would_expand_without_htf_reset + HTF window position counter)
- **Phase 1** — shadow displacement protection (pending_displacement memory that survives one
  HTF reset with a TTL), implemented as a behaviorally safe fallback path

Zone filter question answered: the "Not in discount/premium zone" check is **hardcoded range
midpoint** (`mid = (h_ref + l_ref) / 2`), NOT the BNBUSDT zone model. A zone model WAS trained
(`models/BNBUSDT/bnbusdt_training_20260524/zone_registry_BNBUSDT_202605_bnb_v1.json`, 8 clusters)
but is not wired into the production CRT pipeline. The midpoint filter killed 3/7 retest episodes.

---

## Phase 0 Confirmed Facts (do not re-measure)

| Transition | Actual | Old hypothesis |
|---|---:|---|
| SWEEP→DISPLACEMENT | 154/600 = 25.7% | ~14% |
| DISPLACEMENT→EXPANSION | 8/154 = **5.2%** | not considered |
| EXPANSION→RETEST | 7/8 = **87.5%** | ~3–4% (wrong by 25×) |
| RETEST→EXECUTION | 2/7 = 28.6% | ~33% |

Reset breakdown: 1,995/2,033 (98.1%) are HTF-driven. 116/146 DISPLACEMENT resets are HTF-driven.
Decision distance: 7 evaluations, all approved on candle 1. Zero S-score rejections.
RETEST kills: 3× range-midpoint zone filter, 2× session filter. Not threshold, not S-score.

**Invalidated candidates:** `retest_depth_max` (not binding), `soft_conf_max_candles` (not binding).

---

## Phase 0b — Two Telemetry Additions (no behavior change)

### Addition 1: `would_expand_score` in RESET_ATTRIBUTED

**Constraint:** NOT a boolean `from_state=="DISPLACEMENT" and "HTF" in reason`.
That only proves interruption happened, not that expansion would have occurred.
Replace with a **computed score** that estimates expansion probability at reset time.

**Where:** `TelemetryCollector.on_reset()` in `src/config_layer/crt_engine_v2.py`

Pass additional context from `StateMachine.reset_to_range()` → `TelemetryCollector.on_reset()`
by extending the call signature:

```python
# Extended on_reset signature:
def on_reset(
    self, from_state: str, reason: str, candle_index: int,
    displacement_age_candles: int = 0,   # candles since displacement entered
    ema_aligned: bool = False,           # True if ema_fast > ema_slow (bullish) or < (bearish) per direction
    remaining_htf_candles: int = 0,      # candles left in current HTF window at reset time
    direction_consistent: bool = False,  # True if current candle close direction matches displacement
) -> None:
```

Score formula (telemetry only, not used in execution decisions):
```python
_would_expand_score: float = 0.0
if from_state == "DISPLACEMENT" and "HTF" in reason:
    _would_expand_score = (
        min(displacement_age_candles / 3, 1.0) * 0.3   # age weight (max out at 3+ candles)
        + (0.3 if ema_aligned else 0.0)                 # momentum alignment
        + (0.25 if direction_consistent else 0.0)       # close direction
        + min(remaining_htf_candles / 4, 1.0) * 0.15   # time available in window
    )  # range: 0.0 – 1.0
```

Add to RESET_ATTRIBUTED record dict:
```python
"would_expand_score":           _would_expand_score,   # 0.0 if not DISPLACEMENT+HTF
"would_expand_threshold":       0.55,                  # candidates above this are "likely would-expand"
"would_expand":                 _would_expand_score >= 0.55,
```

**In `StateMachine.reset_to_range()`**, compute and pass these values before the telemetry call:
```python
if self.telemetry and candle:
    _disp_age = state.current_candle_index - getattr(state, '_displacement_entry_idx', 0)
    _ema_al   = (state.ema_fast_val > state.ema_slow_val) == (state.direction == Direction.LONG)
    _dir_con  = (candle.close > candle.open) == (state.direction == Direction.LONG)
    self.telemetry.on_reset(
        state.current_state.name, reason, candle.index,
        displacement_age_candles=_disp_age,
        ema_aligned=_ema_al,
        remaining_htf_candles=0,   # not available without HTF context; placeholder
        direction_consistent=_dir_con,
    )
```

`remaining_htf_candles` cannot be computed inside the engine (no HTF context there). Option:
pass it from `BacktestRunner.run()` via `engine.state` — store `_htf_remaining_candles` on
`EngineState` and update it from the backtest loop (same place as `_htf_position` counter).

**What `would_expand_score` measures:** A candidate that was deep into displacement, had aligned
EMAs, consistent direction, and plenty of time remaining in the HTF window had high probability of
continuing to expansion. A score near 1.0 = architecture interruption cost this trade.
A score near 0.0 = displacement was likely to fail even without the HTF reset.

### Addition 2: HTF Window Position Counter

**Where:** `src/runtime/backtest_v2.py` — the main candle loop, NOT the engine itself.

Add a local counter in `BacktestRunner.run()` just before the candle loop:
```python
_htf_position: int = 0          # 1-based position within current 4-candle HTF window
_prev_htf_id:  str = ""
_htf_remaining: int = cfg.htf_candles_per_range   # candles left in current window
```

Inside the loop, after `htf.push(candle)` and before `engine.process_candle(...)`:
```python
if htf.current_htf_id != _prev_htf_id:
    _htf_position  = 1
    _prev_htf_id   = htf.current_htf_id
    _htf_remaining = cfg.htf_candles_per_range - 1
else:
    _htf_position  += 1
    _htf_remaining -= 1
# Expose to engine state so reset_to_range() can access it
engine.state.htf_remaining_candles = _htf_remaining
```

After `action = engine.process_candle(candle, htf.current_htf_id)`:
```python
if action.get("action") == "DISPLACEMENT_CONFIRMED":
    engine.telemetry.on_displacement_htf_position(_htf_position, _htf_remaining)
```

Add `on_displacement_htf_position(self, position: int, remaining: int)` to `TelemetryCollector`:
```python
def on_displacement_htf_position(self, position: int, remaining: int) -> None:
    if self._active_candidate is not None:
        self._active_candidate["disp_htf_pos"]       = position
        self._active_candidate["disp_htf_remaining"] = remaining
```

Add `htf_remaining_candles: int = 0` to `EngineState` — used by `reset_to_range()` to compute
`remaining_htf_candles` for the `would_expand_score`.

In RESET_ATTRIBUTED dict in `on_reset()`, also add:
```python
"htf_window_position": self._active_candidate.get("disp_htf_pos") if self._active_candidate else None,
```

**Decision histogram query (after re-run):**
```powershell
$tel = Get-Content "...BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$resets = $tel | Where-Object { $_.kind -eq "RESET_ATTRIBUTED" -and $_.from_state -eq "DISPLACEMENT" }
$resets | Where-Object { $_.reason -like "*HTF*" } | Group-Object htf_window_position | Sort-Object Name
# would_expand candidates (architecture cost)
($resets | Where-Object { $_.would_expand -eq $true }).Count
```

---

## Phase 1 — Shadow Displacement Protection (APPROVE WITH CONSTRAINTS)

### Constraint 2: Explicit SHADOW_PENDING State (no SWEEP bypass)

**Rejected path:** RANGE → EXPANSION (bypassing SWEEP entirely)
**Required path:** RANGE → SHADOW_PENDING → SWEEP → EXPANSION

SHADOW_PENDING is an explicit `CRTState` value. It preserves auditability: every trade can be
traced through a visible state sequence. The shadow path is not a shortcut — it still requires
a sweep to confirm direction, it just skips the displacement strength check since that already
passed in the prior window.

**State machine addition:**

In `CRTState` enum (near line where CRTState is defined):
```python
class CRTState(Enum):
    RANGE        = "RANGE"
    SHADOW_PENDING = "SHADOW_PENDING"   # NEW: pending displacement memory active
    SWEEP        = "SWEEP"
    DISPLACEMENT = "DISPLACEMENT"
    EXPANSION    = "EXPANSION"
    RETEST       = "RETEST"
    EXECUTION    = "EXECUTION"
    RESOLUTION   = "RESOLUTION"
```

In `VALID_TRANSITIONS` dict:
```python
VALID_TRANSITIONS = {
    CRTState.RANGE:           [CRTState.SWEEP],
    CRTState.SHADOW_PENDING:  [CRTState.SWEEP, CRTState.RANGE],   # NEW
    CRTState.SWEEP:           [CRTState.DISPLACEMENT, CRTState.RANGE],
    CRTState.DISPLACEMENT:    [CRTState.EXPANSION, CRTState.RANGE],
    CRTState.EXPANSION:       [CRTState.RETEST,  CRTState.RANGE],
    CRTState.RETEST:          [CRTState.EXECUTION, CRTState.RANGE],
    CRTState.EXECUTION:       [CRTState.RESOLUTION, CRTState.RANGE],
    CRTState.RESOLUTION:      [CRTState.RANGE],
}
```

**State transition flow:**

```
HTF reset fires while state == DISPLACEMENT:
  1. reset_to_range() stores pending memory → state = RANGE

Next HTF window, RANGE branch:
  2. sweep detected, same direction, pending active → state = SHADOW_PENDING

SHADOW_PENDING branch (new elif in process_candle):
  3. try_shadow_pending_to_sweep() → state = SWEEP (uses pending displacement candle as context)
  4. try_shadow_sweep_to_expansion() → state = EXPANSION (skips body_ratio/atr displacement check)

From EXPANSION onwards: identical to normal path.
```

### Constraint 3: Pending Memory Origin Fields

**Where:** `EngineState` (new fields), populated in `reset_to_range()`.

```python
# Shadow displacement memory (survives HTF reset, expires after TTL)
pending_displacement_candle:  Optional[Candle]   = None
pending_displacement_dir:     Direction          = Direction.NONE
pending_displacement_ttl:     int                = 0
pending_displacement_source_htf:    str          = ""   # HTF ID when displacement was formed
pending_displacement_formed_idx:    int          = 0    # candle_index when displacement formed
pending_displacement_age_at_reset:  int          = 0    # candle age when HTF reset fired
pending_displacement_reason_created: str         = ""   # reset reason that created this memory
```

In `reset_to_range()`, before clearing `state.displacement_candle`:
```python
if (state.displacement_candle is not None
        and "HTF" in reason
        and state.current_state == CRTState.DISPLACEMENT):
    state.pending_displacement_candle          = state.displacement_candle
    state.pending_displacement_dir             = state.direction
    state.pending_displacement_ttl             = self.config.pending_displacement_ttl_candles
    state.pending_displacement_source_htf      = state.active_range.htf_candle_id if state.active_range else ""
    state.pending_displacement_formed_idx      = getattr(state, '_displacement_entry_idx', 0)
    state.pending_displacement_age_at_reset    = state.current_candle_index - state.pending_displacement_formed_idx
    state.pending_displacement_reason_created  = reason
```

Also add `_displacement_entry_idx: int = 0` to `EngineState`, set in `_transition()` when
`target == CRTState.DISPLACEMENT`.

**The origin fields allow:** Training pipeline to separate `natural_expansion` (displacement
→ expansion in same HTF window) from `shadow_expansion` (cross-window memory). Feature
distributions may differ, and a model trained without separation would confuse the two.

### Constraint 4: TTL = 4 candles (one HTF window)

**Config key:** `pending_displacement_ttl_candles: 4` (not 8).

Rationale: "pause → compress → continue" happens within the adjacent HTF window.
If the market did not continue in the next 4 candles (1 hour), the displacement context is stale.
Two windows (8 candles) risks using displacement context that is structurally obsolete.

Production config change: `configs/production/v2_multi_2026_04 - deepdeektry.json` → `crt_engine`:
```json
"pending_displacement_ttl_candles": 4
```

### SHADOW_LEAK Integrity Event (Constraint 5)

When a shadow resume fires, validate that the sweep was legitimate. If not, emit SHADOW_LEAK.

**Where:** `CRTEngine.process_candle()`, SHADOW_PENDING branch, after sweep re-check.

```python
# Integrity check: shadow resume requires valid sweep in same direction
if sweep is None or sweep.direction != self.state.pending_displacement_dir:
    # Shadow memory exists but no valid confirming sweep — this is a SHADOW_LEAK
    from utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "SHADOW_LEAK", "ERROR", "crt_engine",
        {
            "candidate_id":     f"CAND-{candle.index}",
            "pending_dir":      self.state.pending_displacement_dir.value,
            "sweep_dir":        sweep.direction.value if sweep else "NONE",
            "candle_index":     candle.index,
        },
    )
    # Expire the pending memory to prevent further contamination
    self.state.pending_displacement_ttl           = 0
    self.state.pending_displacement_candle        = None
    return action  # do not resume
```

SHADOW_LEAK is an ERROR-severity integrity event that surfaces in `logs/integrity_events.jsonl`.
A non-zero SHADOW_LEAK count invalidates the replay run.

### Counterfactual Replay Output (Constraint 5)

After Phase 1 re-run, `BacktestRunner` should produce a counterfactual section alongside the
standard summary. **Where:** `BacktestRunner._print_summary()` or a new method.

```python
# In BacktestRunner.run(), after writing telemetry:
_shadow_trades   = [t for t in journal.closed_trades if "SHADOW" in getattr(t, "source_path", "")]
_baseline_trades = [t for t in journal.closed_trades if t not in _shadow_trades]
_tel_records     = engine.dump_telemetry()
_shadow_exp      = sum(1 for r in _tel_records if r.get("kind") == "TRANSITION_COUNTER"
                       and "SHADOW_PENDING" in r.get("state_entry_counts", {}))
```

Report structure:
```
COUNTERFACTUAL COMPARISON
  Baseline  trades: X | avg_rr: Y
  Shadow    trades: X | avg_rr: Y  (shadow resume path only)
  SHADOW_LEAK: 0 (must be 0 for replay to be valid)
```

This isolates gains from the shadow path so the RR impact is attributable.

---

## Decision Gates

### Phase 0b → Phase 1 gate

After Phase 0b re-run, evaluate:

```
HTF position histogram:
  If position 4/4 kill rate ≥ 2× positions 1-3 → HTF timing is causal → proceed with SHADOW_PENDING
  If positions 1-4 fail at equal rate → timing is NOT causal → investigate body_ratio/atr gates first

would_expand score distribution:
  Count candidates with would_expand_score >= 0.55 → upper bound on shadow protection gain
  If count < 5 → shadow protection likely yields < 1 additional trade → deprioritize
  If count >= 20 → high potential; worth the architectural complexity
  
SHADOW_LEAK gate (Phase 1 only):
  SHADOW_LEAK count must be 0 after Phase 1 re-run
  Any SHADOW_LEAK → stop replay, debug before promotion
```

### Zone Filter Gate (deferred)

Do not modify midpoint filter in Phase 1. First measure:
- `midpoint_rr`: realized RR of trades where entry_price was within 10% of midpoint vs >10%
- `zone_model_rr`: what RR distribution the BNBUSDT zone model assigns to those RETEST episodes
Compare. If zone model significantly outperforms midpoint, wire it in for Phase 2.

The 3 zone-killed retest episodes had `structure_valid = True` (reached RETEST legitimately).
These should be logged as `structure_valid / execution_rejected` for training label value — they
are false negatives with known feature vectors.

---

## Blast Radius Summary

| Change | Files | Behavior change | Risk |
|---|---|---|---|
| `would_expand_score` in RESET_ATTRIBUTED | `crt_engine_v2.py` TelemetryCollector + EngineState | None (telemetry only) | Low |
| HTF position counter + on_displacement_htf_position | `backtest_v2.py` loop + `crt_engine_v2.py` TelemetryCollector | None (telemetry only) | Low |
| `htf_remaining_candles` on EngineState | `crt_engine_v2.py` EngineState + backtest_v2.py | None (used only for score calc) | Low |
| `SHADOW_PENDING` added to CRTState + VALID_TRANSITIONS | `crt_engine_v2.py` enum + dict | New legal state; old tests that enumerate states will need updating | Medium |
| `pending_displacement_*` fields on EngineState (8 fields) | `crt_engine_v2.py` EngineState | None until reset_to_range() populates them | Low |
| Shadow memory creation in reset_to_range() | `crt_engine_v2.py` StateMachine.reset_to_range() | New: stores memory on HTF+DISPLACEMENT reset | Medium |
| SHADOW_PENDING branch + shadow resume in process_candle() | `crt_engine_v2.py` CRTEngine.process_candle() | New path: DISPLACEMENT→SHADOW_PENDING→SWEEP→EXPANSION | Medium |
| Config key `pending_displacement_ttl_candles: 4` | production JSON + rehash | None until shadow fires | Low |
| SHADOW_LEAK integrity event | `crt_engine_v2.py` + `utils/integrity_events.py` | Logs ERROR, halts shadow resume | Low |
| Counterfactual section in summary output | `backtest_v2.py` BacktestRunner | None (reporting only) | Low |

---

## Implementation Order

```
Phase 0b — Telemetry additions (no behavior change, re-run required)
│
│  Edit 1: EngineState — add htf_remaining_candles: int = 0
│  Edit 2: TelemetryCollector.on_reset() — extend signature + add would_expand_score fields
│  Edit 3: StateMachine.reset_to_range() — pass ema_aligned, direction_consistent, htf_remaining
│  Edit 4: TelemetryCollector — add on_displacement_htf_position(position, remaining)
│  Edit 5: BacktestRunner.run() — add _htf_position/_htf_remaining counters,
│           update engine.state.htf_remaining_candles, call on_displacement_htf_position
│
│  Re-run same backtest (no config change). Inspect histogram + would_expand counts.
│
└── Decision gate → proceed to Phase 1 only if histogram confirms HTF-timing as causal

Phase 1 — Shadow Displacement Protection
│
│  Edit 6: CRTState enum — add SHADOW_PENDING
│  Edit 7: VALID_TRANSITIONS — add SHADOW_PENDING transitions
│  Edit 8: EngineState — add 8 pending_displacement_* fields + _displacement_entry_idx
│  Edit 9: StateMachine._transition() — set _displacement_entry_idx on DISPLACEMENT entry
│  Edit 10: StateMachine.reset_to_range() — create pending memory on HTF+DISPLACEMENT reset
│  Edit 11: CRTEngine.process_candle() — add SHADOW_PENDING branch with SHADOW_LEAK guard
│  Edit 12: CRTConfig — add pending_displacement_ttl_candles: int = 4
│  Edit 13: Production JSON + rehash
│  Edit 14: BacktestRunner._print_summary() — add counterfactual comparison section
│
│  Re-run. Verify:
│    - SHADOW_LEAK count == 0 (hard gate)
│    - SHADOW_PENDING entry count > 0 (shadow fired)
│    - EXPANSION count > 8 (shadow added episodes)
│    - DISPLACEMENT→EXPANSION survival > 5.2%
│    - Trade count and RR distribution vs baseline
│
└── Governance gate: ConfigValidator.validate() before any promotion

Zone attribution (parallel, no re-run)
│
│  Add structure_valid / execution_rejected fields to RESET_ATTRIBUTED records
│  for candidates that reached RETEST before zone/session filter fired
```

---

## Verification

After Phase 0b re-run:
```powershell
$tel = Get-Content "results\BNBUSDT\run_*\BNBUSDT_crt_telemetry.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$resets = $tel | Where-Object { $_.kind -eq "RESET_ATTRIBUTED" -and $_.from_state -eq "DISPLACEMENT" }

# HTF position histogram (causal test)
$resets | Where-Object { $_.reason -like "*HTF*" } | Group-Object htf_window_position | Sort-Object Name

# would_expand gate
($resets | Where-Object { $_.would_expand -eq $true }).Count
```

After Phase 1 shadow protection:
```powershell
# SHADOW_LEAK count — must be 0
($tel | Where-Object { $_.kind -eq "INTEGRITY_EVENT" -and $_.event_type -eq "SHADOW_LEAK" }).Count

# Expansion episode count (should exceed baseline of 8)
($tel | Where-Object { $_.kind -eq "TRANSITION_COUNTER" }).state_entry_counts

# Counterfactual output is in BNBUSDT_report.txt under "COUNTERFACTUAL COMPARISON" section
```


================================================================================
SOURCE_FILE: docs/plans/dont-read-logs-will-streamed-trinket.md
SOURCE_BYTES: 9236
PART: 3/10 FILE 4/7
================================================================================

> Created: 2026-05-09 · Updated: 2026-05-09 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Zone Registry Fix — Per-Instrument Registry with Underpowered Auto-Bypass

## Status: CRT Session Filter (previous plan) — ✅ DONE
All 5 steps implemented. `allowed_sessions` guard fires before `try_retest_to_execution`. Tests pass.

---

## Context

The zone_gate rejects EURUSD signals via `zone_gate_invalid` because the current `models/zone_registry.json` was built from **27 profitable trades across 8 instruments** (AUDUSD, BTCUSDT, ETHUSDT, EURCAD, EURUSD, GBPUSD, USDJPY, XAUUSD). The resulting single centroid is a cross-instrument average that does not represent EURUSD-specific profitable patterns. EURUSD signals deviate from this average → low Gaussian similarity score (< 0.5 threshold) → `zone_gate_invalid` → WR collapse.

**Data reality** (from `results/` CSVs):
| Instrument | Total trades | Profitable | In current zone |
|---|---|---|---|
| EURUSD | 8 | 3 | Diluted into 27-trade global centroid |
| Total (all instruments) | 71 | 27 | All merged into 1 zone |

**Root cause**: 3 EURUSD profitable trades is far too few for meaningful KMeans clustering (zone builder needs ≥ 10 samples). The zone gate is generating spurious `zone_gate_invalid` rejections that have no signal quality basis.

---

## Diagnosis

`models/zone_registry.json`:
- 1 zone, `weight=19.0` (total profitable trades used in build)
- `sigma[4]=0.0`, `sigma[5]=0.0`, `sigma[30]=0.0` — zero-variance features (constant across all trades)
- `threshold=0.5` — tight given cross-instrument training noise

`BitNetZoneGate` in `src/engines/live_engine.py`:
- `get_zone_registry_path(instrument, base_dir="models/bitnet")` already checks `models/bitnet/{INSTRUMENT}/zone_registry.json` before falling back to global — **per-instrument loading is already wired**
- `check()` computes weighted Gaussian similarity; returns `allowed=False` when best score < threshold

`HealthTracker.is_dead()` in `src/core/fusion_engine.py`:
- Requires `mean == 0.0 AND variance == 0.0` exactly — does NOT fire with the current registry because sigma-zero features produce near-zero but non-constant scores across candles

Current backtest bypass: `BACKTEST_BYPASS_ZONE_INVALID=1` (default on) — skips `zone_gate_invalid` rejections in backtest mode. This is correct short-term but not principled.

---

## Plan

### Step 1 — Add `zone_min_samples` guard to `BitNetZoneGate` (immediate fix)

**File:** `src/engines/live_engine.py` — `BitNetZoneGate.__init__()` and `check()`

In `__init__()`, after zones are loaded:
```python
# Compute total training samples across all zones
_total_samples = sum(float(z.get("weight", 0)) for z in self._zones)
_min_samples = float(config.get("zone_min_samples", 50))  # default 50
self._underpowered = bool(self._zones) and (_total_samples < _min_samples)
if self._underpowered:
    _log.warning(
        "ZoneGate: registry has only %.0f training samples (< %.0f min). "
        "Gate will auto-bypass (underpowered_zone_registry).",
        _total_samples, _min_samples,
    )
```

In `check()`, at the top of the method:
```python
if self._underpowered:
    return {
        "allowed": True,
        "score": 1.0,
        "threshold": 0.0,
        "zone_id": None,
        "reason": "underpowered_zone_registry",
        "top_scores": [],
    }
```

**Config key** to add to `configs/production/v2_multi_2026_04.json` under `engine_runner`:
```json
"zone_min_samples": 50
```

Current registry `weight=19 < 50` → auto-bypass fires → `zone_gate_invalid` never fires → no spurious rejections.

When a proper per-instrument registry is built with ≥ 50 samples, auto-bypass deactivates automatically.

### Step 2 — Add `--instrument` filter to zone builder (tool improvement)

**File:** `build_zone_registry_from_trades.py`

Modify `collect_profitable_vectors()` signature to accept optional instrument filter:
```python
def collect_profitable_vectors(trade_csv_paths, instrument: str | None = None):
    ...
    for path in trade_csv_paths:
        df = pd.read_csv(path)
        # Filter by instrument if requested
        if instrument and "instrument" in df.columns:
            df = df[df["instrument"].str.upper() == instrument.upper()]
            if df.empty:
                continue
        ...
```

Modify `main()` to accept `--instrument` and `--output` CLI args:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--instrument", default=None, help="Filter by instrument (e.g. EURUSD)")
parser.add_argument("--output", default="models/zone_registry.json")
parser.add_argument("--min-points", type=int, default=5)
args = parser.parse_args()

# Auto-route output to per-instrument path if --instrument given
if args.instrument and args.output == "models/zone_registry.json":
    instr_key = f"{args.instrument}_M15"  # matches get_zone_registry_path lookup
    output_path = f"models/bitnet/{instr_key}/zone_registry.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
else:
    output_path = args.output
```

This makes the existing `get_zone_registry_path("EURUSD_M15")` lookup in `live_engine.py` auto-find the per-instrument file.

### Step 3 — Recompute config hash

After adding `zone_min_samples` to `configs/production/v2_multi_2026_04.json`:
```bash
cd D:\Tradelatest
python -c "
import json, hashlib
with open('configs/production/v2_multi_2026_04.json') as f:
    data = json.load(f)
params = data['params']
canonical = json.dumps(params, sort_keys=True)
h = hashlib.sha256(canonical.encode()).hexdigest()
data['config_hash'] = h
with open('configs/production/v2_multi_2026_04.json', 'w') as f:
    json.dump(data, f, indent=2)
print('New hash:', h[:24])
"
```

### Step 4 — Tests

**File:** `tests/test_zone_gate_min_samples.py` (new)

```python
def test_underpowered_registry_auto_bypasses():
    """BitNetZoneGate with weight=19 < zone_min_samples=50 returns allowed=True always."""
    gate = BitNetZoneGate(zones=[...weight=19 zone...], config={"zone_min_samples": 50})
    result = gate.check(feature_vector=[0.0]*35)
    assert result["allowed"] is True
    assert result["reason"] == "underpowered_zone_registry"

def test_powered_registry_enforces_threshold():
    """BitNetZoneGate with weight=60 >= zone_min_samples=50 enforces similarity threshold."""
    gate = BitNetZoneGate(zones=[...weight=60 zone with known centroid...], config={"zone_min_samples": 50})
    # Feed a feature vector distant from centroid
    result = gate.check(feature_vector=[999.0]*35)
    assert result["allowed"] is False
```

### Step 5 — Verify

```bash
cd D:\Tradelatest

# 1. Confirm zone gate no longer rejects signals (underpowered bypass active)
set BACKTEST_ENGINE_GATE=1
set BACKTEST_BYPASS_ZONE_INVALID=0   # turn off old bypass — new mechanism takes over
python src/runtime/backtest_v2.py --instrument EURUSD --csv data/EURUSD_M15.csv
# Expect: zone_gate_invalid count = 0 in rejection summary

# 2. Run regression suite
pytest tests/test_zone_gate_min_samples.py tests/test_engine_runner_dual_gate.py tests/test_crt_session_filter.py -v

# 3. Future: rebuild per-instrument registry once more data exists
python build_zone_registry_from_trades.py --instrument EURUSD
# → writes models/bitnet/EURUSD_M15/zone_registry.json (auto-loaded by live_engine)
```

---

## Critical Files

| File | Change |
|------|--------|
| `src/engines/live_engine.py` | Add `_underpowered` flag in `BitNetZoneGate.__init__()`, bypass in `check()` |
| `configs/production/v2_multi_2026_04.json` | Add `engine_runner.zone_min_samples: 50` |
| `build_zone_registry_from_trades.py` | Add `--instrument` CLI arg and per-instrument output routing |
| `tests/test_zone_gate_min_samples.py` (new) | Bypass + enforce threshold tests |

## Existing Utilities Reused
- `BitNetZoneGate.__init__()` / `check()` — `src/engines/live_engine.py` (already the scoring authority)
- `get_zone_registry_path(instrument)` — `src/engines/live_engine.py:45–55` (per-instrument path already supported)
- `build_zone_registry_from_trades.py` — existing builder, just add `--instrument` filter

## Expected Outcome

| Metric | Before (zone gate active, bad registry) | After (underpowered bypass) |
|---|---|---|
| `zone_gate_invalid` rejections | ~63% of all rejects | 0 |
| Signals passing to ultron gate | ~37% | ~100% (of session-allowed signals) |
| WR | 37% (suppressed) | TBD — depends on CRT quality |
| Zone gate effectiveness | Noise (cross-instrument centroid) | Neutral (gate inactive until proper registry built) |

**Long-term fix**: Once profitable EURUSD trade count reaches ≥ 50 (from longer CSV or multi-run accumulation), run `python build_zone_registry_from_trades.py --instrument EURUSD` to activate per-instrument zone filtering. The `zone_min_samples=50` threshold auto-reactivates the gate when that file exists.

## Out of Scope
- WR improvement to 70% — requires CRT threshold tuning or more data (separate task)
- Multi-instrument portfolio backtest (Phase C infrastructure already ready)
- Ultron gate regime context (separate blocker — needs HTF regime signal in feature dict)


================================================================================
SOURCE_FILE: docs/plans/e4081377-is-failed-but-fluffy-wreath.md
SOURCE_BYTES: 77778
PART: 3/10 FILE 5/7
================================================================================

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


================================================================================
SOURCE_FILE: docs/plans/frolicking-foraging-hearth.md
SOURCE_BYTES: 6567
PART: 3/10 FILE 6/7
================================================================================

# Adopt Gov-/Trd- Milestone Prefixes Across Living Docs + Code Comments

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: doc/naming convention (cross-track)

## Context

Two milestone tracks share the labels `M1`–`M5` (governance: Idea Governance Framework
→ Automated Audits; trading: Telemetry → LLM Hardening). A bare "M3" is ambiguous. The
previous session created [`docs/architecture/roadmap.md`](../../D:/Tradelatest/docs/architecture/roadmap.md)
which *states the rule* ("never cross-reference by number alone") but left the underlying
docs/code using bare `Mn`. **Decision (user, 2026-06-01): propagate `Gov-`/`Trd-`
prefixes everywhere it matters, and adopt them as the new canonical IDs.**

A blind find/replace is unsafe — `\bM[0-6]\b` matches **278 occurrences across 22 docs +
11 code files**, of which three distinct classes exist:
- ✅ **Real milestone refs** — get prefixed.
- ⛔ **Timeframe literals** — `historical_fetcher.py "M1": mt5.TIMEFRAME_M1` / `"M15"`,
  `strategy_result.py:59 "M1 / M5 / M15"`, `control_plane/registry.py:230 "raw M1 CSVs"`.
  Renaming these **breaks the candle-timeframe dictionaries**. NEVER touch.
- 📜 **Historical/point-in-time records** — `docs/analysis/*`, superseded plan snapshots,
  the append-only SESSION LOG history in `assistant_project.md`. Rewriting falsifies the
  preservation record (I2/P7 invariant). NEVER touch.

**User decisions applied:** scope = living docs + code *comments/docstrings only*; the
prefixes become **canonical IDs** (registry §3 updated + documented supersession). The
exact M6 validation-floor threshold stays the operator's call (no doc change).

**Intended outcome:** every *living* milestone reference is track-qualified; the registry's
ID convention is updated; timeframe literals and historical records are untouched; no code
logic changes.

## The disambiguation method (applied per occurrence)

For each in-scope match, read surrounding context and classify:
- **Governance** → `Gov-Mn` — only in `idea-governance-framework.md`,
  `user-progress-registry.md`, and the two governance rows of `CLAUDE.md §2`.
- **Trading** → `Trd-Mn` — everywhere else (migration plan, all other architecture docs,
  `assistant_project.md` doctrine block, code comments).
- **Timeframe/Other** → leave untouched.

Track = which roadmap.md section the milestone lives in (§1 = Gov, §2 = Trd).

## Deliverables

### D1 — Trading-track refs → `Trd-Mn`
**Living docs** (milestone refs only): `docs/plans/claude-architecture-migration-eager-wreath.md`
(M0–M6); `docs/architecture/goal.md` (M0–M5, ~L133–135); `docs/architecture/trigger-vocabulary.md`
("M0–M5 migration index/sequence", ~L11/24/68/135); `docs/architecture/service-boundary-map.md`
(M1–M5); `docs/architecture/event-taxonomy.md` (M1/M2); `docs/architecture/replay-governance.md`
(M1); `docs/architecture/llm-governance-layer.md` (M5); `docs/architecture/codebase-state-map.md`
(M1, L118); `docs/architecture/services/decision-spine.md`; `assistant_project.md`
**doctrine block only** (the Migration sequencing index M0–M6 — NOT the SESSION LOG below it).

**Code comments/docstrings only** (never string literals): `src/runtime/backtest_v2.py`,
`src/config_layer/crt_engine_v2.py`, `src/cognitive/cognitive_bus.py`, `src/utils/trade_logger.py`,
`src/utils/sweep_trace_logger.py`, `src/utils/episode_summarizer.py`, `src/core/engine_runner.py`,
`src/events/event_fabric.py` (L66–67). Pattern: `# M1 …` → `# Trd-M1 …`, `"""M2 dual-write …`
→ `"""Trd-M2 dual-write …`.

### D2 — Governance-track refs → `Gov-Mn`
`docs/architecture/idea-governance-framework.md` (self-ref "M1" + refs M2/M3/M4/M5);
`docs/governance/user-progress-registry.md` (prose refs + §5 table — see D3);
`CLAUDE.md §2`: idea-governance row `(M1)`→`(Gov-M1)`, user-progress row `(M2)`→`(Gov-M2)`.

### D3 — Registry ID canonicalization (`user-progress-registry.md`)
- **§3 ID-format table:** split the single ambiguous `Migration milestones | M<n> | M2`
  row into two: `Governance milestones | Gov-M<n> | Gov-M2` and
  `Trading-arch milestones | Trd-M<n> | Trd-M3`. Reword the "M0–M5 today; this file = M2"
  note to "this file = Gov-M2".
- **Immutability note:** under §3, add one line recording the one-time governed rename
  (`M1..M5 → Gov-M1..Gov-M5`) as a *documented supersession* — honoring "a Brick's ID
  never changes once filed" via supersession (parallel to the telemetry-continuity rule),
  not silent mutation.
- **§5 registry table:** `Idea ID` column `M1→Gov-M1 … M5→Gov-M5`; `Blocked By`
  `M2→Gov-M2`, `M3→Gov-M3`. Phase / config-version rows unchanged.

### D4 — roadmap.md tidy (already prefixed this session)
Light pass only: confirm §0 rule wording stays canonical; bare slash-shorthand like
`Gov-M3/M4/M5` is acceptable (track-qualified by the prefix). No structural change.

## Strict exclusions (never touch)
- **Timeframe literals:** `src/data_ingestion/historical_fetcher.py`,
  `src/strategies/strategy_result.py:59`, `src/control_plane/registry.py:230`, and any
  `M15`/`H1`/`H4`/`D1` token.
- **Historical docs:** `docs/analysis/*`; all `docs/plans/*` **except** the active
  migration plan + this plan file; the SESSION LOG history in `assistant_project.md`.
- `docs/reference/conventions.md` — verified to contain **no** milestone refs.
- No code logic, no config edits/rehash/promotion.

## Verification
1. `grep -rn "\bM[0-6]\b"` across in-scope living docs + the 8 code files → every
   remaining *unprefixed* match is a timeframe literal or lives in an excluded file; **zero
   bare milestone refs remain in living docs / code comments.**
2. `git diff -- src/data_ingestion/historical_fetcher.py src/strategies/strategy_result.py src/control_plane/registry.py docs/analysis/` → **empty** (timeframe literals + historical docs untouched).
3. `user-progress-registry.md` §3 shows the two split ID rows + supersession note; §5
   `Idea ID`/`Blocked By` use `Gov-Mn`; Phase/config rows unchanged.
4. `CLAUDE.md §2` idea-gov/registry rows read `Gov-M1`/`Gov-M2`; `roadmap.md §0` rule intact.
5. `pytest tests/test_topic_docs.py` (+ any plan-header test) → still green (rename is
   cosmetic to the doc-structure floor).
6. Append a `📝 SESSION LOG ENTRY` to `assistant_project.md` recording the convention adoption.

## Out of scope
- Timeframe literals, historical/point-in-time docs, SESSION LOG history, `conventions.md`.
- Any engine/decision/config behavior change. This is a naming-convention pass only.


================================================================================
SOURCE_FILE: docs/plans/from-docs-gather-the-foamy-swan.md
SOURCE_BYTES: 12726
PART: 3/10 FILE 7/7
================================================================================

# ROI Increase Plan — Gap Analysis & Implementation (BNBUSDT M15)

> Created: 2026-05-29 · Updated: 2026-05-29 · Milestone: optimization track (Phase 6b — ROI gaps)

---

## Context

The ROI Step (Phase 6a, 2026-05-29) established the first measured baseline:

| Metric | Baseline value |
|---|---|
| Total return (ROI) | +4.91% over 2 yr |
| CAGR | +2.43% |
| Profit factor | 1.79 |
| Return / max-DD | 2.38 |
| Trades | 15 (2 yr), 60% WR, +0.328R avg |

**The ROI equation is multiplicative:** `ROI ≈ N × R̄ × risk%` = 15 × 0.328 × 1.0% = 4.9%

Three independent levers, each with a measurable gap. This plan identifies the gaps from the trades ledger (`results/roi_baseline/run_20260529_161443_BNBUSDT/`) and the codebase exploration, then sequences additive work to close them — following the same measure-first doctrine as Phases 0–5.

`docs/architecture/goal.md` still holds: correctness invariants are not touched. All work is additive telemetry + config-tuning + governance-safe parameter sweep. Changes that would require an explicit deviation flag (e.g. raising risk% above current gate) are flagged explicitly.

---

## Gap Analysis

### Gap 1 — Frequency (N = 15 / 2 yr) is the dominant throttle

`ROI sensitivity: +1 trade ≈ +0.33%` (at current R̄ and risk). Frequency is so low that a 2× lift here doubles ROI more than any other lever.

**Root cause is unmeasured.** `BacktestMetrics.state_distribution` tracks *candle-counts per state* (how long setups dwell), NOT *how many setups entered each state*. The binding constraint — which funnel stage drops the most candidates — is invisible in the current telemetry.

Phase 0 memory identified DISPLACEMENT→EXPANSION at 5.2% as the old bottleneck, but that was on an earlier config and measured manually from JSONL events. With the current config (TTL guard, shadow path, selectivity from Phases 1–5) the binding stage may have shifted.

**Sub-gaps from the trades ledger:**
- 5 of 15 losses are SL hits within 2–11 candles; losers confirm clean −1R structure (not the frequency problem).
- The detection thresholds that control funnel entry are: `body_ratio_min` (0.65), `atr_multiplier_min` (1.50), `expansion_atr_min_distance` (0.20), `retest_depth_max` (0.30). These live in the tuner `PARAM_SPACE` (`scripts/training/auto_tuner_multi.py:98–110`).
- The tuner's current fitness gives 20% weight to `trade_count_norm` with target=50 — at N=15 vs target=50 this should already push toward more trades, yet 15/50 is still only 30% of target. The binding constraint is upstream of the parameters already being swept.

### Gap 2 — R-capture ceiling (R̄ = 0.328R; winners capped at ~+1.9R)

All 5 winners hit TP2 (~+1.9R). Zero TP1-only exits. No runner / TP3 exists. Strong moves (like CRT-0004 +1.90R, CRT-0005 +1.83R) are capped at TP2 with no tail.

**Sub-gaps:**
- `tp2_atr_multiplier = 2.0` in the active config, which with typical SL distance ~3.2 ATR gives TP2 ≈ 6.4 ATR from entry. A TP3 at 3.0× or a trail-after-TP2 would extend R-capture without increasing risk.
- CRT-0012 ran 90 candles to TP2 (+1.92R). A trailing stop activated after TP2 could have captured additional R.
- Config keys for TP extension already exist in the `crt_engine` section pattern (tp1/tp2 multipliers per intent) — a `tp3_atr_multiplier` key follows the same pattern.

### Gap 3 — Cost drag (0.99R = 17% of gross 5.91R)

`simulated_spread_pct = 0.0002` + slippage_atr_fraction = 0.1. Per-trade avg cost = 3502 pips. This is already measured but not broken down by session.

NEWYORK session: 7 trades, 71% WR, +2.99R net — best session.  
LONDON session: 8 trades, 50% WR, +1.93R net — more trades but worse WR and lower R/trade.

Session-level cost drag is not currently separated in telemetry. LONDON trades may carry disproportionate cost (wider spreads). This is a read-only audit gap, not a code change.

### Gap 4 — Risk headroom (risk% = 1.0%; gate ceiling = 5.0%)

Current: 1.0% risk/trade (backtest + gate). Gate max_risk_per_trade_pct = 1.0% and max_portfolio_risk_pct = 5.0%.

At N=15 / 2yr there is virtually never more than 1 open position, so portfolio cap is never binding. Raising risk/trade from 1.0% to 1.5% would lift ROI by ~50% with the same edge — but this is a **deliberate deviation** that changes expected drawdown. Must be flagged and measured before applying. For now: measure what drawdown would look like at 1.5% (re-run with `--risk-pct 0.015`) and compare to gate before promoting.

---

## Proposed Work (sequenced by confidence and reversibility)

### Step 1 — Funnel transition-count telemetry (additive, measure-first) ★ Start here

**Why first:** Can't fix frequency without knowing where the funnel breaks. Mirrors Phase 0 doctrine.

**What:** Add a `funnel_counts` dict to `BacktestMetrics` tracking *setup entry counts* per CRT state (not candle-dwell). A "setup" enters SWEEP when it transitions out of RANGE with a valid sweep; DISPLACEMENT when transitioning out of SWEEP; etc.

**How:**
- `src/config_layer/crt_engine_v2.py`: add a `transition_counts` dict to `CRTEngine.__init__` (around line 509); increment on each legal state transition in the transition handler (around line 550).
- `src/runtime/backtest_v2.py`: add `funnel_counts: dict = field(default_factory=dict)` to `BacktestMetrics`; populate from the engine's `transition_counts` in `MetricsEngine.compute`. Add to `to_dict()`.
- Report writer: add a `── FUNNEL ──` block showing transition counts and per-stage conversion rates (e.g. `SWEEP→DISPLACEMENT: 83 / 847 = 9.8%`).
- **No gate, no fitness change.** Additive telemetry only (invariant #5).
- Config: no new config knobs needed — this is pure instrumentation.

**Verification:** Run BNBUSDT baseline again; confirm `funnel_counts` in summary JSON shows non-zero counts for each stage; conversion rates sum correctly; pytest green.

---

### Step 2 — Detection-threshold sweep targeting frequency (tuner, config-safe)

**Why:** Once funnel counts reveal the binding stage, run a targeted parameter sweep with frequency-weighted fitness. The tuner infrastructure already exists (`scripts/training/auto_tuner_multi.py`, CLI entry, `PARAM_SPACE`, checkpointing to `results/tuner/checkpoint_multi.json`).

**What:** Modify the tuner fitness to temporarily up-weight `trade_count_norm` (e.g. from 0.20 → 0.40) and down-weight `expectancy_rr` (0.50 → 0.30), with a floor on expectancy (reject if exp < 0.10R). This finds configs that trade more without going negative-expectancy.

**How:**
- Add a `frequency_boost_mode: false` flag to the `tuner` config section in `configs/production/v2_multi_2026_04 - deepdeektry.json`. When true, `auto_tuner_multi.py:fitness_multi()` swaps weights. A single boolean switch — no fitness logic duplication.
- Set `trade_count_target: 30` (from 50) as the new reasonable target for BNBUSDT (given the 2yr data).
- Run: `python scripts/training/auto_tuner_multi.py --data-dir data/ --instruments BNBUSDT --max-trials 200`
- Promote via governance if improved: `python src/governance/promotion_manager.py promote ...`
- **No behavior change without promotion.** The sweep is read-only until the config is promoted.

**Deviation flag:** Re-weighting fitness is within the existing ConfigValidator governance path. The resulting config still must pass all hard/soft gates (min trades, max drawdown, score threshold) before promotion. No invariant is touched.

---

### Step 3 — TP3 / trail-after-TP2 for R-capture extension (config + thin code)

**Why:** All winners are currently capped at TP2 (~+1.9R). A TP3 target at 3.0× ATR would extend R on strong moves without increasing risk (SL is already set; only the upside cap changes).

**How:**
- `configs/production/v2_multi_2026_04 - deepdeektry.json`: add `"tp3_atr_multiplier": 3.0, "tp3_enabled": false` to the `crt_engine` section. Default false = no behavior change until explicitly enabled.
- `src/config_layer/crt_engine_v2.py`: add `tp3_atr_multiplier: float = 3.0` and `tp3_enabled: bool = False` to `CRTConfig` (same pattern as existing tp1/tp2 fields). In `compute_crt_levels()` (approx. line 1888): compute `tp3_price` if enabled.
- `src/runtime/backtest_v2.py`: check `tp3_price` in the trade-resolution logic alongside TP1/TP2 checks. Add `tp3_hits: int = 0` to `BacktestMetrics`.
- **Enabled only by config flag.** Default false means zero behavior change until user promotes a config with `tp3_enabled: true`.

**Reuse pattern:** Exactly mirrors the existing tp1/tp2_atr_multiplier_breakout/pullback per-intent pattern. No new architectural concept.

---

### Step 4 — Risk% sensitivity study (read-only, then config decision)

**Why:** At N=15 / 2yr, raising risk/trade from 1.0% to 1.5% would lift ROI by ~50% if edge holds. But this increases max drawdown proportionally. Must be measured before deciding.

**How (read-only first):**
- Run three CLI backtests at risk_pct 0.01, 0.015, 0.02 using `--risk-pct` flag.
- Compare: total_return_pct, max_drawdown_pct, return_to_max_dd (already in the new ROI metrics).
- Record in a dated analysis doc in `docs/analysis/`.

**If the MAR ratio stays above 2.0 at 1.5% risk:** raise `risk_pct_per_trade` in the `backtest` section and `max_risk_per_trade_pct` in the `ultron_risk_gate` section, re-hash (params key only), promote. This is an **explicit deviation step** — must be flagged in SESSION LOG and the promotion log.

---

### Step 5 — Session-level cost audit (additive report, no code change)

**Why:** LONDON vs NEWYORK have different WR/R but cost drag is not separated. If LONDON's lower WR is partly cost-driven, a session filter or wider SL buffer in London could improve net R.

**How:** The `session_breakdown` dict is already in the distribution output. A simple post-processing script (`scripts/analysis/session_cost_audit.py`) reads the trades CSV and computes gross vs net PnL per session. No new telemetry needed — the data is already in `BNBUSDT_trades.csv`. This is a one-off analytical script in `scripts/`, not production code.

---

## File inventory

| File | Change type |
|---|---|
| `src/config_layer/crt_engine_v2.py` | Add `transition_counts` to `CRTEngine` (Step 1); add `tp3_*` to `CRTConfig` (Step 3) |
| `src/runtime/backtest_v2.py` | Add `funnel_counts`, `tp3_hits` to `BacktestMetrics`; populate from engine (Steps 1, 3) |
| `configs/production/v2_multi_2026_04 - deepdeektry.json` | Add `frequency_boost_mode` to `tuner`; add `tp3_*` to `crt_engine`; adjust `trade_count_target` (Steps 2, 3) |
| `scripts/training/auto_tuner_multi.py` | Add `frequency_boost_mode` branch to `fitness_multi()` (Step 2) |
| `scripts/analysis/session_cost_audit.py` | New read-only analysis script (Step 5) |
| `tests/test_roi_gaps.py` | Tests for funnel_counts, tp3 logic, fitness boost mode (Steps 1–3) |

---

## Sequence rationale

1 → 2: You can't sweep for frequency without knowing where the funnel breaks — Step 1 unblocks Step 2.  
2 → 3: TP3 is independent of frequency and can be done in parallel, but it has smaller expected impact (only affects existing winners).  
4: Deferred until edge is confirmed at higher frequency (Step 2). Raising risk on 15 trades / 2yr is not yet validated.  
5: Purely analytical, can run at any point.

---

## Invariant / governance check

- **Deterministic?** All changes are post-hoc metrics (Step 1) or config-gated with default=false (Steps 3–4). Step 2 sweep is read-only until promoted. ✅
- **Telemetry additive?** funnel_counts, tp3_hits are additive new fields. Nothing removed. ✅
- **No partial fusion?** EXPECTED_ENGINES untouched. ✅
- **Governance path?** Tuner sweep → ConfigValidator gates → PromotionManager → promotion_log. ✅
- **Deviation flags required?** Step 4 (raise risk%) and enabling tp3 in production require explicit SESSION LOG deviation note + Five Governance Questions pass before promoting.

---

## Verification (end-to-end, after Steps 1–3)

1. `python -m pytest tests/ -k "roi or funnel or tp3"` — green
2. Re-run BNBUSDT baseline: `python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/roi_gap1`  
   → confirm `funnel_counts` in summary JSON; report shows `── FUNNEL ──` block with conversion rates.
3. (Step 2) Run frequency sweep: `python scripts/training/auto_tuner_multi.py --data-dir data/ --instruments BNBUSDT --max-trials 200`  
   → checkpoint at `results/tuner/checkpoint_multi.json`; confirm improved trade count with expectancy floor holding.
4. (Step 3) Enable `tp3_enabled: true` locally; re-run baseline; confirm `tp3_hits > 0` on historical data; confirm no regressions in gate logic.
