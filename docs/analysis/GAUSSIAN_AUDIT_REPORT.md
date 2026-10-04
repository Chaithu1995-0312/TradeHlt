# Gaussian Engine Audit Report
**Date:** 2026-07-26
**Scope:** Source-based audit of all Gaussian-related implementations
**Precedent:** CRT_AUDIT_REPORT.md (same methodology)

---

## Architecture Overview

There are **three distinct Gaussian scoring subsystems** in the codebase:

| Layer | File | Role | Execution Authority |
|---|---|---|---|
| **HeuristicGaussianEngine** | `src/engines/heuristic_gaussian_engine.py` (376 lines) | Production live spine (F-060) | **Primary** |
| **MLGaussianEngine** | `src/engines/ml_gaussian_engine.py` (260 lines) | ML-based GaussianNB scoring | Config-gated (`gaussian_impl=ml`) |
| **`compute_gaussian_score`** | `src/engines/scoring_engine.py:64-93` | Legacy per-feature Gaussian kernel | **GHOST** — dead code |

The backward-compat shim `src/engines/gaussian_engine.py` re-exports `HeuristicGaussianEngine` as `GaussianEngine` for existing imports.

---

## 1. Input Contract Verification

### 1A. HeuristicGaussianEngine (production default)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `compute(input_data, candle_idx, direction)` | `input_data` dict with **3 required keys**: `ema_fast`, `ema_slow`, `momentum_score` | `{"score": float [0,1], "reason": str, "meta": {mu, sigma, x}}` | ✅ |
| `__init__(config, instrument, preload_registry)` | Config dict + optional instrument override | Engine instance with lazy registry load | ✅ |

**Key observation:** The heuristic engine consumes only 3 of the 39 canonical features. It does **not** consume CRT-specific outputs (`retest_depth`, `disp_strength`, `sweep_detected`, `body_ratio`, etc.). This is by design (F-060) — the heuristic kernel is a simple EMA/momentum probability score, not a CRT state evaluator.

### 1B. MLGaussianEngine (config: `gaussian_impl=ml`)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `compute(input_data, candle_idx, direction)` | Full 39-dim canonical feature dict | `{"score": float [0,1], "reason": str, "meta": {expected_rr, confidence, model_version, ...}}` | ✅ |
| Name-anchored extraction | `input_data` dict + `_feature_schema_resolved` (trained name order) | `List[float]` — built by name, never by truncation | ✅ |

**Key observation:** The ML path uses the **full canonical vector** via `gaussian_schema_contract.extract_model_feature_vector()`. This is the P0 name-anchored contract (2026-07-22) — vectors are built in trained name order, never by ambient truncation of the 39-dim vector.

### 1C. `compute_gaussian_score` (scoring_engine.py — GHOST PATH)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `compute_gaussian_score(features, params)` | Raw feature list + params dict with per-feature mu/sigma/weights | `float` | **DEAD CODE** |

**Finding 1 (GHOST):** `compute_gaussian_score` in `scoring_engine.py:64-93` is a **third** Gaussian scoring function that:
1. Accepts raw feature indices (not canonical names)
2. Uses per-feature mu/sigma/weights from a params dict
3. Is import-guarded against `bitnet.zone_cosine_searcher` — tries to import an external implementation first
4. Falls back to a per-feature Gaussian formula that is neither the heuristic kernel nor the ML model
5. **Is never called anywhere in the codebase** (zero call sites found via `search_files`)

**Recommendation:** Remove or archive this dead code. It has no architectural registration and no consumers.

---

## 2. Statistical Model Verification

### 2A. HeuristicGaussianEngine — Kernel Formula

```
x = ((ema_fast - ema_slow) / ema_slow + tanh(momentum_score)) / 2.0
score = exp(-(x - mu)² / (2σ²))
```

| Property | Value | Assessment |
|---|---|---|
| Distribution | Fixed-radius Gaussian kernel centred at mu | Not a proper density estimate |
| mu source | (1) config override → (2) registry active entry → (3) default 0.0 | ✅ |
| sigma source | (1) config override → (2) registry active entry → (3) default 1.0 | ✅ |
| Online estimation | None — mu/sigma are static | ⚠️ No distribution adaptation |
| Likelihood output | Not produced | ⚠️ Gap vs task requirements |
| Novelty/familiarity | Not produced | ⚠️ Gap vs task requirements |
| Anomaly classification | Not produced | ⚠️ Gap vs task requirements |

**Finding 2 (INFORMATIONAL):** The heuristic kernel is a **fixed-radius similarity measure**, not a statistical density estimator. It evaluates distance from a single point (mu) scaled by bandwidth (sigma). This is adequate for its documented role (F-060: "simple EMA/momentum probability score") but does not meet the task's stated requirements for likelihood, novelty, familiarity, or anomaly classification.

### 2B. MLGaussianEngine — GaussianNB Model

| Property | Value | Assessment |
|---|---|---|
| Model type | GaussianNBModel + StandardScaler | ✅ Proper generative classifier |
| Training | Historical data via `load_gaussian_model()` | ✅ |
| Inference | `predict_expected_rr(scaled)` → sigmoid → score | ✅ |
| Class probabilities | Available via `probs` from `predict_expected_rr` | ⚠️ Not surfaced in output dict |
| Likelihood | Implicit in GaussianNB (P(features|class)) | ⚠️ Not exposed |
| Schema alignment | v3 aliases resolved at load; collapse detection | ✅ |

**Finding 3 (LOW):** The ML path computes class probabilities (`probs` at `ml_gaussian_engine.py:239`) but does not surface them in the output dict. The `expected_rr` and `confidence` values are exposed in `meta`, but log-likelihood under the model is not. If likelihood/novelty/familiarity are required, the ML path is the natural place to expose them.

### 2C. Registry mu/sigma — Actual Values

The `gaussian_registry.json` stores mu/sigma per entry via `_normalize_registry_entry()`. However, **F-060 established that no mu/sigma from this registry reaches the live score** when `gaussian_impl=heuristic` (the production default). The heuristic engine's `_ensure_registry()` only loads the registry when `_mu_override` is None, and even then the registry's mu/sigma are used only for the heuristic kernel — not for any ML inference.

| Instrument | Active Version | mu | sigma | Schema Version |
|---|---|---|---|---|
| ETHUSDT | `v5_auto_2026_06_eth` | 0.0 | 1.0 | v2.0 (35 dim) |
| BNBUSDT | `p5_20260524T120449` | 0.0 | 1.0 | v3.0 (38 dim) |
| XAUUSD | `xauusd_nb_20260722T194904Z` | 0.0 | 1.0 | v3.0 (39 dim, v4 names) |

**Finding 4 (INFORMATIONAL):** All active registry entries have mu=0.0, sigma=1.0 (defaults). No trained mu/sigma values are stored. This means the heuristic kernel always evaluates `exp(-x²/2)` — a standard normal kernel centred at zero. The registry serves primarily as a **model file pointer** for the ML path, not as a source of distribution parameters for the heuristic path.

---

## 3. Output Contract Verification

### Current Outputs

| Implementation | Output Keys | Likelihood? | Novelty? | Familiarity? | Anomaly? |
|---|---|---|---|---|---|
| HeuristicGaussianEngine | `score`, `reason`, `meta:{mu, sigma, x}` | ❌ | ❌ | ❌ | ❌ |
| MLGaussianEngine | `score`, `reason`, `meta:{expected_rr, confidence, model_version, ...}` | ❌ (implicit in NB) | ❌ | ❌ | ❌ |
| `compute_gaussian_score` (ghost) | `float` only | ❌ | ❌ | ❌ | ❌ |

**Finding 5 (GAP):** Neither implementation produces explicit likelihood, novelty, familiarity, or anomaly classification as documented in the task requirements. Both produce a scalar score in [0,1] that is consumed by FusionEngine as a confidence weight. The pipeline does not currently require these additional outputs — FusionEngine consumes only the `score` key. If these outputs are needed for a downstream consumer, the output contract must be extended.

---

## 4. Ownership Boundaries

| Boundary | Code Evidence | Status |
|---|---|---|
| Gaussian should **not** classify market structure | CRT owns StateMachine, RangeDetector, sweep_taxonomy.py | ✅ |
| Gaussian should **not** estimate profit | RR engine owns expected_rr; ExecutionEngine builds TP/SL | ✅ |
| Gaussian should **not** produce trade decisions | DecisionEngine applies threshold; FusionEngine aggregates | ✅ |
| Gaussian should only score feature probability | Both implementations produce [0,1] confidence scores | ✅ |
| Gaussian should **not** redefine OHLCV | Uses canonical features only; no raw price reinterpretation | ✅ |

**Verdict: Ownership boundaries are correct.** Each component stays within its documented responsibility.

---

## 5. Causal Correctness

| Check | HeuristicGaussianEngine | MLGaussianEngine | Status |
|---|---|---|---|
| Temporal accumulation | None — stateless per-bar computation | None — model loaded at init, static | ✅ |
| Future data in features | Consumes pipeline outputs at current bar | Consumes pipeline outputs at current bar | ✅ |
| Lookahead in model loading | N/A (no model) | Model loaded from static artifact | ✅ |
| Online retraining | None | None | ✅ |
| Feature extraction | By name from input dict | By name from input dict (name-anchored) | ✅ |

**Verdict: No causal leakage detected.** Both implementations consume only current-bar data. The ML model is a static artifact trained on historical data.

---

## 6. Implementation Drift — Intended vs Actual

### Component-by-Component Classification

| Component | Intended Architecture | Actual Implementation | Verdict |
|---|---|---|---|
| **HeuristicGaussianEngine** (F-060, live spine) | 3-feature EMA/momentum Gaussian kernel | ✅ `x = ((ema_fast-ema_slow)/ema_slow + tanh(momentum))/2` → `exp(-(x-mu)²/2σ²)` | **MATCH** |
| **MLGaussianEngine** (config: gaussian_impl=ml) | Full 39-dim GaussianNB with name-anchored contract | ✅ Name-anchored extraction, schema v3→v4 alias resolution, collapse detection | **MATCH** |
| **GaussianRegistry** | Per-instrument active pointer with safe-mode fallback | ✅ `__active__` map, artifact existence check, version fallback | **MATCH** |
| **GaussianAdapter** (fusion_engine.py) | Thin wrapper for uniform interface | ✅ Delegates to `scorer.compute()`, fallback 0.5 | **MATCH** |
| **Schema alignment** (gaussian_schema_contract) | Name-anchored extraction with v3 alias resolution | ✅ `macd_hist→macd_hist_z`, `wick_size→candle_range`; collapse detection | **MATCH** |
| **`compute_gaussian_score`** (scoring_engine.py) | Unknown — no architectural doc | 3rd scoring function with per-feature mu/sigma/weights; import-guarded; **zero call sites** | **GHOST** |
| **`CRTGaussianScorer`** (backtest_v2.py) | No-op scorer, replaced by Phase-5 | ✅ Returns None (no gate) | **MATCH** |
| **`CRTCalibratedScorer`** (backtest_v2.py) | Delegates to `core.model_registry.load_active_gaussian_scorer()` | ✅ Dynamic loader | **MATCH** |

### Production Config Authority

| Setting | Active Config (v2_multi_2026_04) | v4 Config (not active) |
|---|---|---|
| `gaussian_impl` | `"heuristic"` | `"ml"` |
| Fusion weight: gaussian | 0.20 | (not checked) |
| Fusion weight: crt | 0.40 | (not checked) |
| Fusion weight: zone_gate | 0.20 | (not checked) |
| Fusion weight: rr | 0.20 | (not checked) |

**Finding 6 (AUTHORITATIVE):** The **HeuristicGaussianEngine** is the production authority (F-060, `gaussian_impl=heuristic` in active config). The ML path is gated behind `gaussian_impl=ml` and remains disabled in production. The v4 config (`v4_multi_2026_06.json`) sets `gaussian_impl=ml` but is **not the active version** — the active pointer points to `v2_multi_2026_04`.

### Fusion Engine Config Location

**Finding 7 (MINOR):** The `fusion_engine` section is a **top-level key** in the production JSON, not nested under `engine_runner`. The `EngineRunner.__init__()` reads it via `_cfg_require(config, "fusion_engine", "engine_runner")` which works because the full config dict is passed. However, the `ENGINE_RUNNER_DEFAULTS` dict in `engine_runner.py:91-117` nests `fusion_engine` under `engine_runner` — this is a **structural inconsistency** between the defaults dict and the actual config layout. The defaults are only used in direct-construction tests (documented at line 108-112), so this is not a runtime bug, but it is a documentation drift.

---

## 7. Schema Alignment Verification

### v2.0 Schema (35 dim) — All legacy registry entries

```
saved: 35 features including macd_hist, wick_size
live:  39 features (v4.0)
resolved: 35 features (2 renames applied)
  macd_hist → macd_hist_z  (v3.0 emitted z-scored value)
  wick_size → candle_range  (pure rename, always was high-low)
missing: []  (all names resolved)
alignable: True
is_full_live: False  (subset of 39-dim)
is_strict_subset: True
```

### v3.0/v4.0 Schema (38/39 dim) — BNBUSDT and XAUUSD entries

```
saved: 38-39 features with macd_hist_raw, macd_hist_z, candle_range
live:  39 features (v4.0)
resolved: 39 features (no renames needed)
missing: []  (all names resolved)
alignable: True
is_full_live: True
```

**Verdict: Schema alignment is correct.** The `gaussian_schema_contract` module correctly resolves v2→v4 name changes. The `assert_model_schema_compatible()` function validates that resolved length matches `model.n_features`. The `extract_model_feature_vector()` function builds vectors in trained name order — never by ambient truncation.

---

## 8. Detailed Findings

### Finding 1 (GHOST) — `compute_gaussian_score` Dead Code
- **Severity:** LOW
- **Location:** `src/engines/scoring_engine.py:64-93`
- **Impact:** A third Gaussian scoring function exists with no callers. It is import-guarded against `bitnet.zone_cosine_searcher` (which exists and would be used if imported). The fallback path uses per-feature mu/sigma/weights from a params dict — a formula that is neither the heuristic kernel nor the ML model.
- **Recommendation:** Remove the dead code. If the `bitnet.zone_cosine_searcher` path is needed, it should be registered as a proper engine implementation.

### Finding 2 (INFORMATIONAL) — Heuristic Kernel Is Not a Density Estimator
- **Severity:** INFORMATIONAL
- **Location:** `src/engines/heuristic_gaussian_engine.py:358-366`
- **Impact:** The heuristic kernel evaluates `exp(-(x-mu)²/2σ²)` — a fixed-radius similarity measure, not a statistical density estimate. It does not produce likelihood, novelty, familiarity, or anomaly classification.
- **Recommendation:** Document that the heuristic kernel is a similarity measure, not a density estimator. If likelihood/novelty/familiarity are required, use the ML path or extend the output contract.

### Finding 3 (LOW) — ML Path Class Probabilities Not Surfaced
- **Severity:** LOW
- **Location:** `src/engines/ml_gaussian_engine.py:239`
- **Impact:** The ML path computes `probs` from `predict_expected_rr` but does not include them in the output dict. Log-likelihood under the GaussianNB model is accessible but not exposed.
- **Recommendation:** If downstream consumers need likelihood or class probabilities, surface `probs` in the output `meta` dict.

### Finding 4 (INFORMATIONAL) — Registry mu/sigma Are All Defaults
- **Severity:** INFORMATIONAL
- **Location:** `models/gaussian_registry.json`
- **Impact:** All active registry entries have mu=0.0, sigma=1.0 (defaults). No trained distribution parameters are stored. The registry serves primarily as a model file pointer for the ML path.
- **Recommendation:** If the heuristic kernel is to remain authoritative, consider whether trained mu/sigma values would improve scoring. Currently the kernel evaluates `exp(-x²/2)` for all instruments.

### Finding 5 (GAP) — Output Contract Lacks Likelihood/Novelty/Familiarity/Anomaly
- **Severity:** GAP (depends on requirements)
- **Impact:** Neither implementation produces the outputs listed in the task requirements (likelihood, novelty, familiarity, anomaly classification). The pipeline currently consumes only the `score` key.
- **Recommendation:** Determine whether these outputs are needed. If so, extend the output contract of the authoritative implementation (HeuristicGaussianEngine or MLGaussianEngine).

### Finding 6 (AUTHORITATIVE) — HeuristicGaussianEngine Is Production Authority
- **Severity:** INFORMATIONAL
- **Impact:** The active production config (`v2_multi_2026_04.json`) sets `gaussian_impl=heuristic`. The ML path is disabled in production. The v4 config (`v4_multi_2026_06.json`) sets `gaussian_impl=ml` but is not the active version.
- **Recommendation:** Document this authority explicitly. Any switch to `gaussian_impl=ml` requires a config promotion.

### Finding 7 (MINOR) — Fusion Engine Config Location Inconsistency
- **Severity:** LOW
- **Location:** `src/core/engine_runner.py:91-117` vs `configs/production/v2_multi_2026_04.json`
- **Impact:** The `ENGINE_RUNNER_DEFAULTS` dict nests `fusion_engine` under `engine_runner`, but the production JSON has `fusion_engine` as a top-level key. The defaults are only used in direct-construction tests (documented), so this is not a runtime bug.
- **Recommendation:** Update `ENGINE_RUNNER_DEFAULTS` to match the actual config layout, or add a comment explaining the structural difference.

---

## 9. Summary

| Category | Status |
|---|---|
| **Input Contract** | ✅ Heuristic: 3 features (ema_fast, ema_slow, momentum_score). ML: full 39-dim canonical vector. |
| **Statistical Model** | ⚠️ Heuristic: fixed-radius kernel (not density estimator). ML: proper GaussianNB. Neither produces likelihood/novelty/familiarity/anomaly. |
| **Output Contract** | ⚠️ Both produce scalar score [0,1] only. Likelihood/novelty/familiarity/anomaly not surfaced. |
| **Ownership Boundaries** | ✅ All boundaries respected. |
| **Causal Correctness** | ✅ No future leakage detected. |
| **Implementation Drift** | 6 MATCH, 1 GHOST (see below) |

### Drift Classifications

| Component | Classification |
|---|---|
| `heuristic_gaussian_engine.py` (HeuristicGaussianEngine) | **MATCH** |
| `ml_gaussian_engine.py` (MLGaussianEngine) | **MATCH** |
| `gaussian_schema_contract.py` (name-anchored contract) | **MATCH** |
| `GaussianRegistry` (registry loader) | **MATCH** |
| `GaussianAdapter` (fusion_engine.py) | **MATCH** |
| `CRTGaussianScorer` / `CRTCalibratedScorer` (backtest_v2.py) | **MATCH** |
| `compute_gaussian_score` (scoring_engine.py) | **GHOST** — dead code, no callers |

### Key Recommendations

1. **Remove ghost code:** `compute_gaussian_score` in `scoring_engine.py:64-93` has no callers and no architectural registration.
2. **Document kernel limitations:** The heuristic kernel is a similarity measure, not a density estimator. If likelihood/novelty/familiarity/anomaly are required, extend the ML path's output contract.
3. **Surface ML probabilities:** The ML path computes class probabilities but does not expose them. Add `probs` to the output `meta` dict if downstream consumers need them.
4. **Fix defaults inconsistency:** Update `ENGINE_RUNNER_DEFAULTS` in `engine_runner.py` to match the actual config layout (fusion_engine at top level, not nested under engine_runner).
5. **No action needed on schema alignment:** The name-anchored contract correctly resolves v2→v4 schema changes. All registry entries are alignable.