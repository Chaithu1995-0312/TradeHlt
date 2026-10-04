# Tradelatest — Deep Codebase Analysis
**Session Date:** 2026-04-28  
**Scope:** Full codebase reachability map, fusion→decision spine, Ultron disambiguation, 4 scoring engine internals, EngineRunner.run() 8-step wiring.

---

## 1. Coverage Map — 4 Entry-Point Workflows

The 4 primary entry-point workflows and what they **call** (execution reachability, not code walkthrough):

| Workflow | Entry Script | Direct Orchestrator |
|---|---|---|
| Backtest | `scripts/training/backtest_v2.py` | `BacktestRunner._run_single()` → `EngineRunner.run()` per candle |
| BitNet Backtest | `scripts/training/backtest_bitnet.py` | Same via `BacktestRunner` |
| Unified Replay | `src/runtime/unified_replay_harness.py` | Same via `BacktestRunner` |
| Auto Tuner | `scripts/training/auto_tuner_multi.py` | Same via `BacktestRunner` |

**Key clarification:** "Not covered" in earlier sessions meant *internals not walked through*, not *unreachable*. All 4 workflows call `EngineRunner.run()` — the oven they call is the same; what was unread was inside the oven.

---

## 2. Transitive Reachability — 34 Reachable vs 59+ Isolated

### 2.1 Reachable from all 4 workflows (34 src modules)

```
Entry → BacktestRunner → EngineRunner.run()
  ├── engines/adapter_engine.py       (TrapValidatorEngine — Step 1 gate)
  ├── engines/crt_engine.py           → scoring_engine.py (Step 2)
  ├── engines/heuristic_gaussian_engine.py / ml_gaussian_engine.py (Step 2)
  ├── engines/zone_gate_engine.py     → features/feature_schema.py (Step 2)
  ├── engines/rr_engine.py            (Step 2)
  ├── core/fusion_engine.py           → convergence_controller.py (Step 4)
  ├── core/decision_engine.py         → acceptance_controller.py (Step 7)
  ├── core/ultron_gate.py             (Step 6 — regime filter)
  ├── core/collector.py               (Step 8 — structured log)
  ├── core/signal_audit.py            (Step audit)
  ├── config_layer/crt_engine_v2.py   (CRT state machine — backtest loop)
  ├── config_layer/production_config.py
  ├── config_layer/config_builder.py
  ├── config_layer/llm_inference_client.py  (optional LLM tie-breaker)
  ├── features/feature_pipeline.py    (optional import guard)
  ├── features/feature_schema.py
  ├── features/feature_monitor.py     (drift detection on TRADE_OPENED)
  ├── bitnet/bitnet_inference.py
  ├── bitnet/bitnet_runner.py
  ├── config_layer/rr/rr_fusion.py    (optionally behind rr_fusion.enabled flag)
  ├── config_layer/rr/rr_pattern_miner.py (optionally reachable)
  └── utils/* (logging_config, console_safe, zone_schema_migrator, …)
```

### 2.2 Isolated — 8 Separate "Kitchens"

Each kitchen has its own independent entry-point chain; none is reachable from the 4 backtest workflows above.

| Kitchen | Entry Points | Key Files |
|---|---|---|
| **Training / Governance** | `scripts/training/train_pipeline.py`, `model_registry.py` | `training/trainer.py`, `training/evaluator.py`, `config_layer/config_validator.py` |
| **Governance Pipeline** | `promotion_manager.py`, `shadow_promotion_gate.py` | `governance/orchestrator.py`, `governance/meta_governor_executor.py`, `governance/reflection_buffer_advanced.py` |
| **Agent System** | `agent/cli.py` | `agent/agent_core.py`, `agent/intent_router.py`, `agent/plan_compiler.py`, `agent/tool_registry.py`, `agent/executor.py`, `agent/modes/*` |
| **INOUT / Execution Loop** | `inout/controller.py` | `inout/executor.py`, `inout/state_machine.py`, `inout/scanner.py`, `inout/db.py`, `inout/config.py` |
| **Control Plane** | `scripts/control_plane/run_server.py` | `control_plane/types.py`, `control_plane/monitors.py` |
| **Portfolio** | _(no confirmed launcher)_ | `portfolio/allocator.py`, `portfolio/exposure_tracker.py`, `portfolio/capital_policy.py`, `portfolio/correlation_engine.py` |
| **New Packages (discovered during scan)** | _(no launchers found)_ | `src/search/`, `src/journal/`, `src/ui/`, `src/analytics/`, `src/feedback/`, `src/scanner/`, `src/regime/`, `src/llm_research/`, `src/expansion/` |
| **True Orphans (zero importers, no `__main__`)** | — | `core/feature_store.py`, `core/ultron_risk_gate_wrapper.py`, `bitnet/zone_validator.py`, `bitnet/stability_checker.py`, `bitnet/forward_tester.py`, `bitnet/_smoke_test.py` |

---

## 3. Ultron Naming Disambiguation (3 Separate Objects)

> **Critical:** The config key `ultron_gate_enabled` sounds like it controls `UltronRiskGate` (capital gate) but it controls `UltronGovernor` (regime signal filter). This was the primary source of confusion.

| Object | File | Role | Caller | Config Key |
|---|---|---|---|---|
| `UltronGovernor` (alias: `RegimeGovernor`) | `src/core/ultron_gate.py` | **Regime signal-quality filter.** Soft penalty + per-regime percentile gate (rolling 100-score window) + daily quota cap (3/day). | `EngineRunner.run()` Step 6 — *inside* the pipeline | `engine_runner.ultron_gate_enabled` |
| `UltronRiskGate` | `src/core/ultron_risk_gate.py` | **Capital protection gate.** 7-check waterfall: TTL → RR floor → daily limit → kill switch → exposure cap → SL distance → position sizing. | `live_engine_hook.py` — *after* `EngineRunner.run()` + `ExecutionPlannerV1_2.plan()` | `ultron_risk_gate.*` section |
| `UltronRiskGateWrapper` | `src/core/ultron_risk_gate_wrapper.py` | **Thin pre-scaler.** Applies regime_factor to `risk_percent` before delegating to `UltronRiskGate`. SR-1: always calls real gate, has no reject path of its own. | Not wired in production (true orphan as of this session) | — |

### 3.1 Changes Applied to Resolve Confusion

**`ultron_gate.py`** — added 18-line disambiguation docstring at module top; added alias at bottom:
```python
# Preferred alias — use RegimeGovernor in new code for clarity.
# UltronGovernor kept for backward compatibility (tests/test_ultron_gate.py line 391 asserts
# `assert "UltronGovernor" in s` against the report() string — cannot rename).
RegimeGovernor = UltronGovernor
```

**`engine_runner.py`** — updated import + inline comments:
```python
# RegimeGovernor (alias for UltronGovernor) = Step-6 signal-quality filter.
# NOT the capital-protection gate — see core/ultron_risk_gate.py for that.
from core.ultron_gate import UltronGovernor, RegimeGovernor  # noqa: F401

# ultron_gate_enabled controls THIS governor, NOT UltronRiskGate (capital gate).
self._ultron_gov = UltronGovernor()  # alias: RegimeGovernor

def ultron_governor(regime, dual_results, cfg):
    # LEGACY free-function version of RegimeGovernor (UltronGovernor).
    # Used by EngineRunner when ultron_gate_enabled=false (backtest/training).
    # No percentile gate, no daily quota. Prefer UltronGovernor class for live.
```

**`ultron_risk_gate.py`** — disambiguation note added at docstring top:
```
⚠️  NAMING NOTE — NOT the same as UltronGovernor (ultron_gate.py).
  UltronRiskGate  = CAPITAL PROTECTION (this file).
  UltronGovernor  = REGIME SIGNAL FILTER (ultron_gate.py).
```

---

## 4. EngineRunner.run() — Complete 8-Step Pipeline

```
input_data + context
        │
        ▼
Step 1: TrapValidatorEngine.compute(merged)
        score ≤ 0.0 → REJECT (adapter_rejected / data_integrity_failed / missing_fields / 
                               invalid_session / low_atr / non_positive_atr)
        │ score = 1.0
        ▼
Step 2: Run ALL 4 engines unconditionally
        ├── crt_compute(trade_id, features, context)         → {"score": float}
        ├── gaussian.compute(input_data)                     → {"score": float}
        ├── run_zone_gate_engine(zonegate_input, model_fn)   → {"score", "passed", "vector", "valid"}
        │   └── [if zone_mode="soft"] _compute_soft_zone_score() overrides score only
        └── rr.compute(input_data)                           → {"score", "rr_ratio"}
            └── [if rr_fusion.enabled] RRFusionLayer.score_dict() adjusts rr score
        │
        ▼
Step 3: Completeness check
        EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}
        missing = EXPECTED_ENGINES - engine_results.keys()
        if missing → REJECT (incomplete_engine_execution)
        │
        ▼
Step 4: FusionEngine.compute(engine_results)
        Weighted aggregation: CRT×0.30 + Gaussian×0.25 + ZoneGate×0.25 + RR×0.20
        + ConvergenceController stability penalty (zone_gate**4 dampening → sigmoid)
        + ScoreNormalizer rolling min-max window=1000 (fixes Gaussian compression)
        + EngineHealthTracker (dead engine exclusion)
        [optional shadow] FusionEngine.evaluate() — 3-layer Gaussian→Neural→LLM path
        │
        ▼
Step 5: Fusion baseline gate
        final_score < fusion_min_score (0.25 default) → REJECT (low_fusion_score)
        │
        ▼
Step 6: Dual-engine regime gate
        detect_regime(features) → "trend" | "range" | "neutral"
          trend:   ema_spread ≥ 0.15 AND momentum ≥ 0.30
          range:   volatility_ratio ≤ 0.80
          neutral: everything else
        breakout_engine(features) → {score, direction, reason}
        trap_engine(features)     → {score, direction, reason}
        
        IF ultron_gate_enabled=True (live):
          UltronGovernor.evaluate(regime, dual_results, dual_cfg, candle_date)
          → soft penalty + percentile gate (rolling 100) + daily quota (3/day)
        ELSE (backtest/training):
          ultron_governor() free-function
          → simple score+direction check; low-confidence neutrals rejected
        
        not gate_result.allow → REJECT (ultron_gate:reason)
        │
        ▼
Step 7: DecisionEngine.evaluate(score, p_win, zone_gate, fusion, config)
        DynamicThreshold: 85th percentile of rolling 1000 scores, [0.45, 0.65], fallback 0.55
        5-condition waterfall → "execute" | "reject"
        Adaptive thresholds injected from AcceptanceController.get_thresholds()
          (integral control α=0.01, targeting 5-15% accept rate)
        decision_result["regime"] = regime
        decision_result["selected_engine"] = selected_engine (breakout|trap)
        │
        ▼
Step 8: Collector.log(full record)
        AcceptanceController.update_metrics() + adjust_thresholds() (per-bar)
        
        Return: decision_result dict
```

---

## 5. The 4 Scoring Engines — Internals

### 5.1 Engine 1: CRT (Candle Recognition Theory)

**Files:** `src/engines/crt_engine.py` → delegates to `src/engines/scoring_engine.py::compute_scores()`

**Inputs:** `body_ratio`, `disp_strength`, `atr`, `retest_depth`, `candles_since_retest`, `sweep_detected`, `double_sweep`

**Formula (all components bounded [0,1]):**
```
s_sweep    = 0.0 (no sweep) | 0.7 (single sweep) | 1.0 (double sweep)

s_breakout = 0.5 × min(body_ratio, 1.0)
           + 0.5 × min(disp_strength / 2.0, 1.0)

s_retest   = exp( -((retest_depth - 0.5)² / 0.04) )
             └── Gaussian bell peak at retest_depth=0.5

s_time     = exp( -0.05 × max(0, candles_since_retest) )
             └── Exponential decay; lambda_decay=0.05

s_final    = 0.35×s_sweep + 0.25×s_breakout + 0.20×s_retest + 0.20×s_time
```

**Output:** `{"score": float, "sweep": float, "breakout": float, "retest": float, "time": float, "final": float}`

**Architecture note:** `crt_engine.py` is a thin logging wrapper. Real logic lives in `scoring_engine.py::compute_scores()`. The `ScoringEngine` class in `scoring_engine.py` is a **different, older 3-layer object** (Gaussian+Neural+LLM) — it is **not** called by `EngineRunner`. EngineRunner calls the module-level `crt_compute()` function only.

---

### 5.2 Engine 2: Gaussian (HeuristicGaussianEngine)

**Files:** `src/engines/heuristic_gaussian_engine.py`  
(Note: `gaussian_engine.py` is a pure backward-compat shim — `GaussianEngine = HeuristicGaussianEngine`)

**Selection:** `GAUSSIAN_IMPL` env var or config `gaussian_impl` key → `"heuristic"` (default) or `"ml"` (MLGaussianEngine, 32-dim GaussianNB)

**Inputs:** Only 3 of the 35-dim canonical features used:
- `ema_fast`, `ema_slow`, `momentum_score`

**Formula:**
```
ema_diff      = (ema_fast - ema_slow) / ema_slow
momentum_norm = tanh(momentum_score)
x             = (ema_diff + momentum_norm) / 2.0

score         = exp( -((x - μ)² / (2σ²)) )
                └── Pure Gaussian kernel (NOT Gaussian Naive Bayes)
```

**mu / sigma resolution priority:**
1. Config override keys `gaussian_mu` / `gaussian_sigma`
2. `GaussianRegistry.load()` → reads `models/gaussian_registry.json` (active version with fallback to `_FALLBACK_PRIORITY = ["v1", "import_fix_v1"]`)
3. Defaults: `mu=0.0`, `sigma=1.0`

**Output:** `{"score": float, "reason": str, "meta": {"mu": float, "sigma": float, "x": float}}`

**Failure modes:**
- `ema_slow = 0` → `RuntimeError` (fail-fast — no score=0 silent fallback)
- `ema_fast == ema_slow AND momentum == 0` → returns `score=0.5, reason="neutral_synthetic_condition"` (sentinel for synthetic/test data)
- Registry load fails → falls back to config/defaults with a WARNING log

**Key insight:** This is a distance-from-ideal scorer, not a classifier. A score of 1.0 means `x == μ` (EMA/momentum perfectly aligned with the trained ideal). Score drops as conditions diverge. The "compression" problem (~0.33–0.55 range) is fixed by `ScoreNormalizer` rolling min-max in FusionEngine.

---

### 5.3 Engine 3: ZoneGate (BitNet Zone Gate)

**File:** `src/engines/zone_gate_engine.py`

**Inputs:** Full `CANONICAL_FEATURE_ORDER` (35-dim vector from `features/feature_schema.py`)

**Two scoring modes (config `zone_mode`):**

| Mode | Score Source |
|---|---|
| `"hard"` (default) | `model_fn(vector)` via BitNet zone gate → `compute_weighted_cluster_score(top_scores)` |
| `"soft"` | `Z = 0.5×exp(-distance) + 0.3×freshness + 0.2×strength` — analytic formula, no model |

**BitNet scoring path (hard mode):**
```
_zone_model_fn(vector):
    result = self._zone_gate.check(vector)          # BitNet nearest-neighbour lookup
    top_scores = result.get("top_scores")
    if len(top_scores) >= 2:
        return compute_weighted_cluster_score(top_scores)
    return result.get("score", 0.5)                 # fallback to single score

compute_weighted_cluster_score(similarity_scores):
    valid = [clamp(s, 0, 1) for s in scores if isfinite(s)]
    if len(valid) < 2:  return max(valid)           # single-neighbour fallback
    if max-min > 0.15:  return 0.0                  # REJECT unstable cluster
    total = sum(valid)
    return sum( (s/total) * s for s in valid )      # self-weighted average
```

**Three-tier error policy:**
| Failure | Policy | Returns |
|---|---|---|
| Missing canonical keys | Fail-**closed** | `score=0.0, passed=False, valid=False` |
| Zone registry error | Fail-**open** (neutral) | `score=0.5, passed=True, valid=True` |
| Vector extraction / scoring error | Fail-**closed** | `score=0.0, passed=False, valid=False` |

**execution_mode="force_pass":** always returns `passed=True` but records `real_passed` in the result and still logs the real decision. Used for bypass in testing/forced scenarios.

**Output from `run_zone_gate_engine()`:**
```python
{"score": float, "passed": bool, "vector": list, "valid": bool}
# force_pass adds: "force_pass_override": True, "real_passed": bool
```

**EngineRunner wraps zone output:**
```python
zone_result = {
    "engine": "zone_gate",
    "score": float(zone_raw.get("score", 0.0)),
    "direction": 1 if zone_raw.get("passed") else 0,   # direction derived from pass/fail
    "meta": zone_raw,
}
```

**Session-level counters** (module-global, reset on process restart):
- `_ZONE_COUNTERS`: `total_pass`, `total_block`, `block_reason_dist`
- Access via `get_zone_gate_counters()` / reset via `reset_zone_gate_counters()`

---

### 5.4 Engine 4: RREngine (Risk-Reward)

**File:** `src/engines/rr_engine.py`

**Inputs:** `close`, `high`, `low`, `atr`  
(Note: `atr` is accepted for future extensions but **not used** in ratio calculation)

**Formula:**
```
# Bull scenario (long): risk is downside, reward is upside
bull_stop   = close - low       # risk distance
bull_target = high - close      # reward distance
bull_rr     = bull_target / bull_stop  (if bull_stop > 0 else 0.0)

# Bear scenario (short): risk is upside, reward is downside
bear_stop   = high - close
bear_target = close - low
bear_rr     = bear_target / bear_stop  (if bear_stop > 0 else 0.0)

rr_ratio = max(bull_rr, bear_rr)   # best scenario wins

# Score normalization:
if rr_ratio >= min_rr (default 1.5):
    score = min(1.0, rr_ratio / (min_rr * 2))
    # score = 0.5 at exactly rr=1.5; asymptotically → 1.0
else:
    score = 0.0
```

**Sanity check:** `high >= close >= low` required; violation → `score=0.0, reason="invalid_price_structure:..."`

**Output:** `{"score": float, "rr_ratio": float, "reason": str}`

**FIX NOTE (important for understanding test data):** Previous implementation always returned `rr=2.0` (used ATR multiples: `stop=atr*1.5, target=atr*3.0`). Current version uses real price-level distances. Any baseline data generated with the old engine will have constant `rr=2.0`.

---

### 5.5 Pre-Engine Gate: TrapValidatorEngine (Adapter)

**File:** `src/engines/adapter_engine.py`

**Role:** Step 1 gating — validates structural preconditions before any engine runs.

**Required fields (CANONICAL_REQUIRED):** `close`, `high`, `low`, `open`, `volume`, `atr`, `ema_fast`, `ema_slow`, `session`

**5-gate sequence (first failure returns immediately):**
```
Gate 0: _data_integrity == "real"           → rejects synthetic/mock data
Gate 1: All 9 CANONICAL_REQUIRED present    → rejects incomplete feature dicts
Gate 2: atr > 0                             → rejects non-positive ATR
Gate 3: atr >= min_atr (default 0.0005)     → rejects low-volatility bars
Gate 4: session in allowed_sessions         → rejects out-of-window sessions
        supports both int (0=ASIA,1=LONDON,2=NEWYORK) and string ("asia","london","new_york")
```

**Output:** `{"score": 1.0, "reason": "pass"}` OR `{"score": 0.0, "reason": "<gate_code>"}`

---

## 6. FusionEngine — Scoring Layer Deep-Dive

**File:** `src/core/fusion_engine.py`

### 6.1 Two Paths

| Path | Method | Trigger | Description |
|---|---|---|---|
| **compute()** | `FusionEngine.compute(engine_results)` | Always (main path) | Weighted aggregation of 4 engine scores + ConvergenceController penalty |
| **evaluate()** | `FusionEngine.evaluate(features, signal, candle_idx)` | `fusion_use_evaluate=True` OR `fusion_compare_evaluate=True` | 3-layer Gaussian→Neural→LLM pipeline |

### 6.2 compute() — Weighted Aggregation

Default `FusionConfig` weights:
```
weight_crt      = 0.30 (→ 0.40 in ENGINE_RUNNER_DEFAULTS)
weight_gaussian = 0.25 (→ 0.30)
weight_zone_gate= 0.25 (→ 0.20)
weight_rr       = 0.20 (→ 0.10)
```

**Completeness tiers:**
```
tier_full    = 0.75   (all 4 engines: full score)
tier_half    = 0.60   (3 engines: multiply by 0.60)
tier_quarter = 0.50   (2 engines: multiply by 0.50)
< 2 engines  → fusion_rejected=True, missing_engines populated
```

**Supporting classes:**
- **`ScoreNormalizer`**: Rolling min-max, window=1000. Fixes HeuristicGaussianEngine score compression (~0.33–0.55 → [0,1]).
- **`EngineHealthTracker`**: Detects dead engines (mean≈0, var≈0 over rolling window). Dead engines excluded from weighted fusion.
- **`ConvergenceController`**: Applied post-fusion. Pipeline:
  - zone_gate score\*\*4 dampening
  - sigmoid calibration: `1 / (1 + exp(-8 × (s - 0.6)))`
  - variance penalty: `final *= (1 - sigmoid(var))`
  - adaptive threshold ±0.02 step, targeting 10–30% accept rate

### 6.3 evaluate() — 3-Layer Pipeline (controlled by feature flag)

```
Layer 1: Gaussian (GaussianAdapter wrapping HeuristicGaussianEngine)
Layer 2: Neural (optional, behind neural_weight config)
Layer 3: LLM (llm_gate.llm_score_safe(), only when score near threshold OR models disagree)
         Trigger: |gaussian - threshold| ≤ llm_trigger_margin=0.05 OR |gaussian - neural| > 0.25
         LLM band: [llm_lower_band=0.45, llm_upper_band=0.65]
         Final: 0.6×gaussian + 0.3×neural + 0.1×llm
```

**Production flag:** `fusion_use_evaluate=False` (backtest), `fusion_compare_evaluate=True` (shadow logging — runs evaluate() but uses compute() score; compare delta in `evaluate_shadow` key).

---

## 7. DecisionEngine — Final Authority

**File:** `src/core/decision_engine.py`

**Role:** Sole emitter of "execute" or "reject". EngineRunner NEVER bypasses or overrides this.

**DynamicThreshold:** 85th percentile of rolling 1000 scores, clamped [0.45, 0.65], fallback 0.55 (used when `< _MIN_HISTORY` samples).

**5-condition waterfall:**
1. `score < dynamic_threshold` → REJECT "low_score"
2. `p_win < min_probability` → REJECT "low_probability"
3. `zone_gate.valid == False` → REJECT "zone_gate_rejected"  
4. `fusion.rr < min_rr_ratio` → REJECT "low_rr"
5. `fusion.weak_component > max_weak_component` → REJECT "weak_setup"
6. All pass → "execute"

**Adaptive injection:** `AcceptanceController.get_thresholds()` injects `score_threshold`, `engine_threshold`, `fusion_threshold` into config each bar. Integral control: `θ_new = clamp(θ_old + α × (accept_rate - target_mid), 0.50, 0.95)`.

---

## 8. Live Trading Extension (post-EngineRunner)

**File:** `src/runtime/live_engine_hook.py`  
Class: `HookedLiveEngine(LiveEngine)`

**Full call sequence:**
```
super().process(candle)
    └── _load_engine_config()     (fail-fast — _require() pattern)
    └── EngineRunner(engine_config).run(engine_input, context)
        └── [if decision == "execute"]
            └── ExecutionPlannerV1_2(exec_planner_cfg).plan(engine_result, features, context)
                └── [if plan.decision == "execute"]
                    └── UltronRiskGate(ultron_cfg).evaluate(trade_plan, portfolio_state)
                        └── [if risk_result.decision == "approve"]
                            └── send_to_broker(trade_plan, risk_result["final_position_size"])
```

**Additional features in `live_engine_hook.py`:**
- `_DailyResetTracker` (GAP-006): resets `trades_today` + `daily_loss_pct` at date boundary
- `FeatureMonitor` drift detection: HARD drift (Z>3.0) → WARNING; soft (Z>2.5) → DEBUG
- `UltronRiskGateWrapper` is available but **not wired** into this live hook (true orphan)

---

## 9. UltronGovernor (RegimeGovernor) — Regime Filter Detail

**File:** `src/core/ultron_gate.py`

**Three-layer soft filter:**

```
Layer 1: Soft penalty (regime + direction)
    REGIME_PENALTY:  trend=0.00, range=0.15, neutral=0.15
    DIRECTION_PENALTY: +0.10 if selected_engine.direction == 0 (no clear bias)
    adj_score = clamp(raw_score - (base_pen + dir_pen), 0, 1)

Layer 2: Per-regime percentile gate (rolling 100-score window)
    REGIME_ACCEPT_PERCENTILE: trend=0.75 (top 25%), range=0.90 (top 10%), neutral=0.92 (top 8%)
    Warmup (< WINDOW_MIN_SAMPLES=10): flat FALLBACK_THRESHOLD=0.45
    passes_gate = adj_score >= sorted(window)[min(int(pct*n), n-1)]
    Fail → REJECT "ultron_penalty"

Layer 3: Daily quota cap
    MAX_TRADES_PER_BATCH = 3 per trading day
    Resets at date boundary (candle_date != current_date)
    Fail → REJECT "ultron_quota"
```

**backtest/training path:** `ultron_gate_enabled=False` → uses legacy free-function `ultron_governor()` which has no percentile gate and no daily quota. Still applies regime-based selection and low-confidence neutral rejection (`b_score < neutral_min AND t_score < neutral_min`).

**`report()` string includes "UltronGovernor"** — tests assert this string; this is why it cannot be renamed (alias strategy used instead).

---

## 10. UltronRiskGate — Capital Protection Detail

**File:** `src/core/ultron_risk_gate.py`

**7-check waterfall (first failure → immediate REJECT):**

| # | Check | Reject Reason |
|---|---|---|
| 1 | `now > expires_at` | `expired_signal` / `malformed_expires_at` |
| 2 | `rr_ratio < min_rr_ratio (1.5)` | `rr_too_low` |
| 3 | `trades_today >= max_trades_per_day (10)` | `daily_limit` |
| 4 | `daily_loss_pct >= max_daily_loss_pct (3.0%)` | `kill_switch` |
| 5 | `open_risk + allowed_risk > max_portfolio_risk_pct (5.0%)` | `over_exposure` |
| 6 | `abs(entry - stop_loss) == 0` | `invalid_sl_distance` |
| 7 | `final_size <= 0` | `position_size_zero` |

**Position sizing formula (Check 7):**
```
allowed_risk   = min(risk_percent, max_risk_per_trade_pct)   # cap per-trade risk
risk_usd       = account_balance × (allowed_risk / 100)
max_size       = risk_usd / abs(entry - stop_loss)
final_size     = min(position_size_hint, max_size) if hint else max_size
final_size     = round(final_size, 6)
```

**DEFAULT_CONFIG:**
```json
{
  "max_risk_per_trade_pct": 1.0,
  "max_portfolio_risk_pct": 5.0,
  "max_trades_per_day":     10,
  "max_daily_loss_pct":     3.0,
  "min_rr_ratio":           1.5,
  "disabled":               false
}
```

**Critical caller responsibility:** Ultron does NOT update `portfolio_state` in-place. Caller must persist `result["portfolio_state"]["total_risk"]` and `result["portfolio_state"]["open_positions"]` between calls.

---

## 11. AcceptanceController Detail

**File:** `src/core/acceptance_controller.py`

**Integral control rule (per-bar via `adjust_thresholds()`):**
```
accept_rate = sum(accepted_flags) / len(accepted_flags)   # rolling window=200
target_mid  = (target_low + target_high) / 2 = (0.05 + 0.15) / 2 = 0.10
error       = accept_rate - target_mid
θ_new       = clamp(θ_old + α × error, 0.50, 0.95)       # α=0.01
```

**Threshold computation (when history ≥ 10):**
```
engine_threshold = clamp( mean(engine_scores) + k_sigma × std(engine_scores) )  k_sigma=1.0
fusion_threshold = clamp( percentile(fusion_scores, 85) )
score_threshold  = θ (integral-controlled value)
```

**Injected into DecisionEngine config each bar** via `EngineRunner._acceptance.get_thresholds()` merged into `effective_config`.

---

## 12. ConvergenceController Detail

**File:** `src/core/convergence_controller.py`

**Applied inside FusionEngine.compute() to the weighted fusion score.**

Constants:
```python
_WARMUP_BARS    = 10      # no-op until this many bars seen
_THRESH_MIN     = 0.30
_THRESH_MAX     = 0.90
_THRESH_STEP    = 0.02    # adaptive threshold ±0.02 per bar
_ACCEPT_RATE_HIGH = 0.30  # above this → raise threshold (fewer signals)
_ACCEPT_RATE_LOW  = 0.10  # below this → lower threshold (more signals)
_SIG_K = 8.0              # sigmoid sharpness
_SIG_T = 0.6              # sigmoid inflection point
```

**Pipeline applied to score:**
1. `zone_gate_score ** 4` dampening (very harsh on weak zone scores)
2. sigmoid calibration: `1 / (1 + exp(-8 × (score - 0.6)))`
3. variance penalty: `final *= (1 - sigmoid(variance))`
4. adaptive threshold ±0.02 per bar targeting 10–30% accept rate

---

## 13. Dual Engine Functions (Regime Detection)

**Both defined in `engine_runner.py` as module-level functions:**

### `detect_regime(features, cfg) → "trend" | "range" | "neutral"`
```
trend_strength = abs(ema_spread)
momentum       = abs(momentum_score)
volatility     = volatility_ratio

if trend_strength >= 0.15 AND momentum >= 0.30:  return "trend"
if volatility <= 0.80:                            return "range"
return "neutral"
```

### `breakout_engine(features, cfg) → dict`
```
score     = min(1.0, (abs(ema_spread) + abs(momentum_score)) / 2.0)
direction = sign(trend_bias);  direction=0 if score < breakout_min_score=0.30
reason    = "trend_follow" | "weak_breakout"
```

### `trap_engine(features, cfg) → dict`
```
if sweep_detected <= 0: return score=0.0, reason="no_sweep"
score     = min(1.0, disp_strength)
direction = -sign(trend_bias)   # counter-trend
direction=0 if score < trap_min_score=0.32
reason    = "liquidity_trap" | "weak_trap"
```

---

## 14. Key Architectural Observations & Gotchas

1. **CRT is a double-wrapper**: `crt_engine.py::compute()` → `scoring_engine.py::compute_scores()`. The `ScoringEngine` class in the same file is an **older standalone 3-layer scorer** not called by EngineRunner. Don't confuse them.

2. **`ScoringEngine.compute()` has a `print` statement** (line 137): `print(f"[SCORE] {score:.4f} p_win={p_win:.4f}")` — debug noise left in the class body. Not called by EngineRunner so not critical, but should be cleaned.

3. **Gaussian engine naming chain**: `gaussian_engine.py` (shim) → `heuristic_gaussian_engine.py` (real). `MLGaussianEngine` in `ml_gaussian_engine.py` is the ML alternative, selectable via `GAUSSIAN_IMPL=ml`.

4. **ZoneGate is the BitNet engine**: The BitNet model is not a standalone engine entry — it's invoked inside `zone_gate_engine.py` via `get_zone_gate(zone_registry_path)` singleton → `zone_gate.check(vector)`.

5. **RR engine was broken**: Previous version always returned `rr=2.0` (ATR multiples). Fixed to use real `high/low/close` price levels. Any historical test data with constant `rr=2.0` was generated with the broken version.

6. **`ultron_gate_enabled=False` in production JSON**: Backtest/training path uses legacy free-function with no quota or percentile filtering. Live path uses full `UltronGovernor` class.

7. **`fusion_compare_evaluate=True`** (production): runs the 3-layer evaluate() path as shadow and stores delta in `evaluate_shadow` key. `fusion_use_evaluate=False` (backtest) — compute() result is authoritative.

8. **Position sizing is FINAL at UltronRiskGate**: `ExecutionPlannerV1_2` produces a `position_size_hint`; UltronRiskGate caps it with its own risk-based calculation. Never use the hint directly.

9. **`UltronRiskGateWrapper` is an orphan**: Not wired into `live_engine_hook.py` or any other production caller. The regime pre-scaling it provides is unavailable in production as of this analysis.

10. **`AcceptanceController` warm-up**: Returns config defaults (no adaptation) until `_MIN_HISTORY=10` samples are collected. First 10 bars of any session use static thresholds.

---

## 15. Files Modified in This Session

| File | Change |
|---|---|
| `src/core/ultron_gate.py` | Added 18-line disambiguation docstring + `RegimeGovernor = UltronGovernor` alias |
| `src/core/engine_runner.py` | Updated import line to include `RegimeGovernor`; added inline disambiguation comments on config key and free function |
| `src/core/ultron_risk_gate.py` | Added naming disambiguation note to module docstring |

---

## 16. Pending Investigation Items

1. **True orphan verification**: Confirm `core/feature_store.py` is dead code (no importers, no `__main__`). Confirm `ultron_risk_gate_wrapper.py` intent — was it meant to be wired into `live_engine_hook.py`?

2. **New packages (discovered)**: `src/search/`, `src/journal/`, `src/ui/`, `src/analytics/`, `src/feedback/` — found via grep of script imports but no launchers found. Purpose unclear. Imports like `from journal.trade_logger import TradeLogger` suggest an active journal system.

3. **`execution/loop.py`**: Listed as possibly isolated. Confirm no launchers exist.

4. **Scoring engine `ScoringEngine.compute()` print**: Line 137 in `scoring_engine.py` has a bare `print()` — confirm not called from any live path, then remove.

5. **`RREngine` old-version data**: Audit whether any existing backtests or training data was generated with the broken constant `rr=2.0` version. If so, those datasets need to be regenerated.

6. **`UltronRiskGateWrapper` wiring decision**: Either wire it into `live_engine_hook.py` (replacing the direct `UltronRiskGate` call) or document it as intentionally unused and move it to `tools/` or delete it.

7. **Oven internals still unread**: inout/ layer (execution loop), agent/ system internals (plan_compiler, executor), governance pipeline (orchestrator, shadow_promotion_gate).

---

📝 SESSION LOG ENTRY  
Date: 2026-04-28  
Topic: Full oven internals analysis — 4 scoring engines + EngineRunner 8-step wiring + Ultron disambiguation + reachability map  
Decision/Output: |  
  Completed full read of all engine internals:  
  - crt_engine.py → scoring_engine.py::compute_scores() formula documented  
  - heuristic_gaussian_engine.py — Gaussian kernel (NOT NB), EMA/momentum 3-feature scorer  
  - zone_gate_engine.py — BitNet cluster scoring, 3-tier error policy  
  - rr_engine.py — real price-level RR (FIX: was constant 2.0 before)  
  - adapter_engine.py — TrapValidatorEngine 5-gate sequence  
  - engine_runner.py — complete 8-step run() wiring read end-to-end  
  All findings compiled to docs/SESSION_ANALYSIS_2026_04_28.md (this file).  
Open Questions: See §16 Pending Investigation Items above.  
Next Step: User to direct — options are (a) walk inout/ kitchen, (b) walk agent/ kitchen,  
  (c) investigate true orphans, (d) confirm RR data integrity, (e) wire UltronRiskGateWrapper.  
