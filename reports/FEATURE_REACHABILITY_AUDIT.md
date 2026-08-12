# Feature Reachability Audit

**Generated:** 2026-06-26  
**Scope:** All 38 CANONICAL_FEATURES + intermediates  
**Method:** Static code analysis of the full decision chain (EngineRunner.run() lines 565-1084)  

---

## Decision Chain (Evidence)

The production decision path is **EngineRunner.run()** at `src/core/engine_runner.py:565`. Every feature must pass through these gates to affect a trade decision:

```
Feature → Engine Score → Fusion → Regime Gate → DecisionEngine → TRADE/REJECT
                              ↑           ↑
                      [optional: Belief Gate] [optional: FeatureMonitor HARD drift veto]
```

### Layer 0: FeatureMonitor Drift Veto (runs AFTER adapter, during candle processing)
**File:** `backtest_v2.py:2060-2097`  
**Reads:** `retest_depth`, `body_ratio`, `disp_strength`  
**Can veto:** YES — HARD drift (Z>3.0) pauses trading for `_drift_cooldown` candles  

### Layer 1: Adapter Gate
**File:** `engine_runner.py:569-589`  
**Reads:** `merged` (input_data + context)  
**Consumes features via:** `TrapValidatorEngine.compute()`

### Layer 2: Engine Scoring
**File:** `engine_runner.py:593-732`  
Four engines run in parallel, each consuming different feature subsets:

| Engine | File | Features Read | Impact on Score |
|--------|------|---------------|-----------------|
| CRT | `crt_engine.py:17-46` | body_ratio, disp_strength, atr, retest_depth, candles_since_retest, sweep_detected, double_sweep | DIRECT |
| Gaussian | `heuristic_gaussian_engine.py:306-308` | ema_fast, ema_slow, momentum_score | DIRECT |
| Zone Gate | `zone_gate_engine.py:170-191` | ALL 38 via _extract_vector() | INDIRECT (via model_fn) |
| RR | `rr_engine.py:45-49` | close, high, low | DIRECT |

### Layer 3: Fusion
**File:** `engine_runner.py:782` → `fusion_engine.py:294`  
**Consumes:** 4 engine SCORES (crt, gaussian, zone_gate, rr)  
**Also consumes (regime detection):** `detect_regime(input_data, dual_cfg)` at `engine_runner.py:770`  
**Regime detection reads:** ema_spread, momentum_score, volatility_ratio  

### Layer 4: Fusion Threshold
**File:** `engine_runner.py:827-845`  
**Reads:** `fusion_result["final_score"]` — which is a weighted blend of engine scores  
**Threshold:** `fusion_min_score` from config (~0.25)  

### Layer 5: Dual-Engine Regime Gate
**File:** `engine_runner.py:882-934`  
**Reads:** `breakout_engine(input_data)`, `trap_engine(input_data)`  
**Breakout reads:** trend_bias, momentum_score, ema_spread  
**Trap reads:** sweep_detected, disp_strength, trend_bias  

### Layer 6: DecisionEngine
**File:** `engine_runner.py:966-972` → `decision_engine.py:108-162`  
**Reads:** fusion_score, p_win (from gaussian), zone_gate validity, rr_ratio, weak_component  
**Thresholds:** dynamic percentile-based (clamped 0.45-0.65), p_win ≥ threshold, rr_ratio ≥ threshold  

### Summary: Features that ACTUALLY Reach Decisions

Only features consumed DIRECTLY by engine compute methods or regime detection can alter scores. Features consumed only by the ZoneGate model_fn are opaque — their reachability is INDETERMINATE without model introspection.

---

## Per-Feature Reachability Matrix

### Features 0-4: Raw OHLCV

**Feature: open** (index 0)
- **Generated?** YES
- **Read directly?** NO — no engine reads `open` from canonical dict
- **Consumed by model?** YES — ZoneGate model_fn receives all 38 dims
- **Can change engine score?** NO
- **Can change fusion output?** NO (unless ZoneGate score changes → fusion changes)
- **Can change trade decision?** INDETERMINATE (depends on ZoneGate model weights)
- **Classification:** ACTIVE_VIA_MODEL (zone_gate only)

**Feature: high** (index 1)
- **Generated?** YES
- **Read directly?** YES — RREngine reads `high` (line 48)
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (RR engine score)
- **Can change fusion output?** YES (RR weight = 0.20 in fusion)
- **Can change trade decision?** YES (if RR score change crosses decision thresholds)
- **Classification:** ACTIVE

**Feature: low** (index 2)
- **Generated?** YES
- **Read directly?** YES — RREngine reads `low` (line 49)
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (RR engine score)
- **Can change fusion output?** YES (RR weight = 0.20)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: close** (index 3)
- **Generated?** YES
- **Read directly?** YES — RREngine reads `close` (line 47)
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (RR engine score)
- **Can change fusion output?** YES (RR weight = 0.20)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: volume** (index 4)
- **Generated?** YES
- **Read directly?** NO — no engine reads `volume` from canonical dict
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (only used as intermediate for volume_ratio in FeaturePipeline)
- **Can change fusion output?** INDETERMINATE (ZoneGate only)
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 5-6: Volume

**Feature: volume_ratio** (index 5)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: double_sweep** (index 6)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:28`, `bitnet_score()` line 329, `ScoringEngine.compute_scores()` line 28, `ExecutionEngine._derive_trade_intent()` line 1883
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT scoring — weight 0.35 in ultron)
- **Can change fusion output?** YES (CRT weight = 0.4 in fusion)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

### Features 7-9: EMA

**Feature: ema_fast** (index 7)
- **Generated?** YES
- **Read directly?** YES — `HeuristicGaussianEngine.compute()` line 306
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (Gaussian score)
- **Can change fusion output?** YES (Gaussian weight = 0.3 in fusion)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: ema_slow** (index 8)
- **Generated?** YES
- **Read directly?** YES — `HeuristicGaussianEngine.compute()` line 307
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (Gaussian score)
- **Can change fusion output?** YES (Gaussian weight = 0.3)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: ema_spread** (index 9)
- **Generated?** YES
- **Read directly?** YES — `detect_regime()` line 145, `breakout_engine()` line 162
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (not an engine input)
- **Can change fusion output?** YES (regime → fusion weights vary, e.g. CRT=0.38 in TRENDING vs 0.18 in RANGING)
- **Can change trade decision?** YES (regime affects both fusion weights and gate pass/fail)
- **Classification:** ACTIVE

### Features 10-11: Trend

**Feature: trend_bias** (index 10)
- **Generated?** YES
- **Read directly?** YES — `breakout_engine()` line 160, `trap_engine()` line 186
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (not an engine input)
- **Can change fusion output?** YES (affects regime gate pass/fail → decision)
- **Can change trade decision?** YES (regime gate can block trades)
- **Classification:** ACTIVE

**Feature: trend_strength** (index 11)
- **Generated?** YES (computed, z-scored)
- **Read directly?** NO — not read by any engine or detection function
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE (ZoneGate only)
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Feature 12: Momentum

**Feature: momentum_score** (index 12)
- **Generated?** YES
- **Read directly?** YES — `HeuristicGaussianEngine.compute()` line 308, `detect_regime()` line 146, `breakout_engine()` line 161, `_derive_trade_intent()` line 1887, `trap_engine()` (indirect via disp)
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (Gaussian score — weight 0.3 in fusion)
- **Can change fusion output?** YES (Gaussian + regime effects)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

### Features 13-14: Volatility

**Feature: atr** (index 13)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:23`, `bitnet_score()` line 327, `ScoringEngine.compute_scores()` line 22, `ExecutionEngine.build_trade()` line 1906, `UltronRiskEngine.approve()` line 1792, backtest_v2.py multiple places
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT, BitNet — multiple paths)
- **Can change fusion output?** YES (CRT weight = 0.4)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: volatility_ratio** (index 14)
- **Generated?** YES
- **Read directly?** YES — `detect_regime()` line 147
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (not an engine input)
- **Can change fusion output?** YES (regime → fusion weights)
- **Can change trade decision?** YES (regime gate can block)
- **Classification:** ACTIVE

### Feature 15: RSI

**Feature: rsi_14** (index 15)
- **Generated?** YES
- **Read directly?** NO — not read by any engine or detection function
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 16-18: MACD

**Feature: macd_line** (index 16)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: macd_signal** (index 17)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: macd_hist** (index 18)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 19-21: Structure

**Feature: sweep_detected** (index 19)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:27-28`, `trap_engine()` line 184, `ExecutionEngine._derive_trade_intent()` line 1883
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT scoring — sweep component weight 0.35 in ultron)
- **Can change fusion output?** YES (CRT + trap gate)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

**Feature: liquidity_sweep** (index 20)
- **Generated?** YES
- **Read directly?** indIRECTLY — used as intermediate for `double_sweep` in FeaturePipeline (line 584-591)
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (direct), YES (via double_sweep derivation)
- **Can change fusion output?** YES (via double_sweep → CRT score)
- **Can change trade decision?** YES (indirectly)
- **Classification:** ACTIVE_VIA_MODEL (direct), ACTIVE (indirect via double_sweep)

**Feature: break_of_structure** (index 21)
- **Generated?** YES
- **Read directly?** NO — no engine reads this field
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 22-25: Swings

**Feature: swing_high** (index 22)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: swing_low** (index 23)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: higher_high** (index 24)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: lower_low** (index 25)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 26-28: Candle Geometry

**Feature: body_size** (index 26)
- **Generated?** YES
- **Read directly?** NO — `body_ratio` is derived from this, but `body_size` itself is not read
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (only affects body_ratio which IS read)
- **Can change fusion output?** INDETERMINATE (ZoneGate only)
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: wick_size** (index 27)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (body_ratio uses it, but wick_size itself is not read)
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

**Feature: body_ratio** (index 28)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:22`, `bitnet_score()` line 324, `ScoringEngine.compute_scores()` line 40, `ScoringEngine.compute()` line 128, `ExecutionEngine._derive_trade_intent()` line 1890, `FeatureMonitor.detect_drift()` line 2065
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT, BitNet, ScoringEngine — 3 separate paths)
- **Can change fusion output?** YES (CRT weight = 0.4, BitNet can veto via UltronRiskEngine)
- **Can change trade decision?** YES (also can trigger HARD drift veto)
- **Classification:** ACTIVE

### Feature 29: Volatility Regime

**Feature: volatility_regime** (index 29)
- **Generated?** YES
- **Read directly?** YES — per F-029 measurement hook, s05_grid.py reads this
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (not directly)
- **Can change fusion output?** INDETERMINATE (ZoneGate) + ACTIVE (decision-reachable per s05_grid.py)
- **Can change trade decision?** YES (per F-029 documentation, blocks LONG in TRENDING regime)
- **Classification:** ACTIVE (decision-reachable per documentation)

### Features 30-31: Temporal

**Feature: session** (index 30)
- **Generated?** YES
- **Read directly?** PARTIAL — CRTEngine uses session gating (`allowed_sessions`) but from engine state, not canonical feature. Backtest_v2.py uses `self._session()` from CRT config, not the canonical value.
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO (via canonical dict), YES (via CRT engine state — separate path)
- **Can change fusion output?** INDETERMINATE (canonical), YES (CRT engine sessions gate trades directly)
- **Can change trade decision?** YES (session filtering in CRT engine is a hard gate)
- **Classification:** ACTIVE (but via CRT engine state, not canonical feature path)

**Feature: hour_of_day** (index 31)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL

### Features 32-34: CRT Context (CORE)

**Feature: disp_strength** (index 32)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:23`, `bitnet_score()` line 326, `ScoringEngine.compute_scores()` line 31, `trap_engine()` line 185, `ExecutionEngine._derive_trade_intent()` line 1891, `FeatureMonitor.detect_drift()` line 2065
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT, BitNet, trap — 3 paths)
- **Can change fusion output?** YES (CRT weight = 0.4, trap affects regime gate)
- **Can change trade decision?** YES (also HARD drift veto)
- **Classification:** ACTIVE

**Feature: retest_depth** (index 33)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:24`, `bitnet_score()` line 325, `ScoringEngine.compute_scores()` line 22, `ScoringEngine.compute()` line 129, `ExecutionEngine._derive_trade_intent()` line 1888, `FeatureMonitor.detect_drift()` line 2065
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT, BitNet, ScoringEngine — 3 paths)
- **Can change fusion output?** YES (CRT weight = 0.4)
- **Can change trade decision?** YES (also HARD drift veto)
- **Classification:** ACTIVE

**Feature: candles_since_retest** (index 34)
- **Generated?** YES
- **Read directly?** YES — `crt_engine.py:25`, `bitnet_score()` line 328, `ScoringEngine.compute_scores()` line 22, `UltronRiskEngine.approve()` line 1793, `ExecutionEngine._derive_trade_intent()` line 1886
- **Consumed by model?** YES — ZoneGate
- **Can change engine score?** YES (CRT, BitNet — time decay in scoring)
- **Can change fusion output?** YES (CRT weight = 0.4)
- **Can change trade decision?** YES
- **Classification:** ACTIVE

### Features 35-37: v3.0 Additions

**Feature: liquidity_distance** (index 35, v3.0)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate (only)
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL (v3.0)

**Feature: liquidity_pressure_score** (index 36, v3.0)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate (only)
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL (v3.0)

**Feature: volume_spike** (index 37, v3.0)
- **Generated?** YES
- **Read directly?** NO
- **Consumed by model?** YES — ZoneGate (only)
- **Can change engine score?** NO
- **Can change fusion output?** INDETERMINATE
- **Can change trade decision?** INDETERMINATE
- **Classification:** ACTIVE_VIA_MODEL (v3.0)

---

## ZoneGate Analysis

### All 38 Dimensions Matter?

**Determination: UNKNOWN without model introspection.**

The `_zone_model_fn` (`engine_runner.py:612-624`) creates a `BitNetZoneGate` instance and calls `.check(vector)` with the full 38-dim vector. Internally, the zone registry's centroid comparison may use:
- All 38 dimensions (cosine similarity on full vector)
- A subset (feature selection at training time)
- Dimensionally reduced representation (PCA, autoencoder, etc.)

The `_extract_vector()` function (`zone_gate_engine.py:170-191`) REQUIRES all 38 canonical keys. It does NOT perform feature selection.

**Feature importance extraction:** To determine which dimensions matter:
1. Open the zone registry JSON (`models/zone_registry.json`) — if centroids have 38 dims, all are used
2. If centroids have < 38 dims, the model was trained on a previous schema version
3. Weight analysis: if the registry stores per-feature weights, importance can be ranked
4. Ablation: zero each dimension and measure score change

**Ablation test design:**
```python
# Pseudocode for zone_gate ablation
zone_gate = load_zone_gate(registry_path)
baseline = zone_gate.check(full_vector)["score"]
for i in range(38):
    ablated = list(full_vector)
    ablated[i] = 0.0  # or mean, or constant
    result = zone_gate.check(ablated)
    delta = baseline - result["score"]
    # If delta ≈ 0, feature i is irrelevant to zone gate output
```

### Weights Can Be Extracted

If the zone registry stores centroids with per-feature components, the weight of each feature can be extracted by examining centroid coordinates. Each centroid's dimension `i` value represents how strongly feature `i` defines that zone.

---

## Final Reachability Summary

### 1. Feature Reachability Matrix

| Index | Feature | Reachable? | Path to Decision | Classification |
|-------|---------|-----------|------------------|----------------|
| 0 | open | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 1 | high | YES | RREngine → Fusion → Decision | ACTIVE |
| 2 | low | YES | RREngine → Fusion → Decision | ACTIVE |
| 3 | close | YES | RREngine → Fusion → Decision | ACTIVE |
| 4 | volume | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 5 | volume_ratio | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 6 | double_sweep | YES | CRT/ScoringEngine → Fusion → Decision | ACTIVE |
| 7 | ema_fast | YES | Gaussian → Fusion → Decision | ACTIVE |
| 8 | ema_slow | YES | Gaussian → Fusion → Decision | ACTIVE |
| 9 | ema_spread | YES | Regime detection → Fusion weights/Gate | ACTIVE |
| 10 | trend_bias | YES | Breakout/trap → Regime Gate | ACTIVE |
| 11 | trend_strength | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 12 | momentum_score | YES | Gaussian + Regime + Intent → Fusion/Gate | ACTIVE |
| 13 | atr | YES | CRT/BitNet/ScoringEngine → Fusion → Decision | ACTIVE |
| 14 | volatility_ratio | YES | Regime detection → Fusion weights/Gate | ACTIVE |
| 15 | rsi_14 | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 16 | macd_line | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 17 | macd_signal | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 18 | macd_hist | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 19 | sweep_detected | YES | CRT/Trap → Fusion/Gate | ACTIVE |
| 20 | liquidity_sweep | YES (indirect) | Via double_sweep | ACTIVE_VIA_MODEL |
| 21 | break_of_structure | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 22 | swing_high | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 23 | swing_low | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 24 | higher_high | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 25 | lower_low | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 26 | body_size | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 27 | wick_size | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 28 | body_ratio | YES | CRT/BitNet/ScoringEngine/Monitor → Fusion/Veto | ACTIVE |
| 29 | volatility_regime | YES | s05_grid.py per F-029 | ACTIVE |
| 30 | session | YES | CRT engine gating (separate path) | ACTIVE |
| 31 | hour_of_day | INDETERMINATE | ZoneGate only | ACTIVE_VIA_MODEL |
| 32 | disp_strength | YES | CRT/BitNet/Trap/Monitor → Fusion/Veto | ACTIVE |
| 33 | retest_depth | YES | CRT/BitNet/ScoringEngine/Monitor → Fusion/Veto | ACTIVE |
| 34 | candles_since_retest | YES | CRT/BitNet → Fusion | ACTIVE |
| 35 | liquidity_distance | INDETERMINATE | ZoneGate only (v3.0) | ACTIVE_VIA_MODEL |
| 36 | liquidity_pressure_score | INDETERMINATE | ZoneGate only (v3.0) | ACTIVE_VIA_MODEL |
| 37 | volume_spike | INDETERMINATE | ZoneGate only (v3.0) | ACTIVE_VIA_MODEL |

### 2. True Active Feature Count

| Classification | Count | Features |
|---------------|-------|----------|
| ACTIVE (can change decisions) | **16** | high, low, close, double_sweep, ema_fast, ema_slow, ema_spread, trend_bias, momentum_score, atr, volatility_ratio, sweep_detected, body_ratio, volatility_regime, session, disp_strength, retest_depth, candles_since_retest |
| ACTIVE_VIA_MODEL (ZoneGate only, indeterminate) | **20** | open, volume, volume_ratio, rsi_14, macd_line, macd_signal, macd_hist, break_of_structure, swing_high, swing_low, higher_high, lower_low, body_size, wick_size, liquidity_sweep, trend_strength, hour_of_day, liquidity_distance, liquidity_pressure_score, volume_spike |

### 3. Dead Compute Cost

Features computed by FeaturePipeline that are NOT in CANONICAL_FEATURES (never reach any consumer):

| Intermediate | Compute Cost | Dropped By |
|-------------|-------------|------------|
| prev_close | O(N) trivial | finalize() |
| delta_close | O(N) trivial | finalize() |
| candle_body | O(N) trivial | finalize() |
| upper_wick | O(N) trivial | finalize() |
| lower_wick | O(N) trivial | finalize() |
| direction | O(N) trivial | finalize() |
| volume_ma20 | O(N) rolling window | finalize() |
| ma_20, ma_50, ma_200 | O(N) rolling window | finalize() |
| rsi_state | O(N) trivial | finalize() |
| true_range | O(N) — used for ATR | consumed by atr_14_raw |
| atr_14_raw | O(N) rolling window | consumed by atr |
| bb_upper, bb_lower | O(N) rolling window + std | finalize() |
| bb_width, bb_position | O(N) trivial | finalize() |
| price_vs_ma20, price_vs_ma50 | O(N) trivial | finalize() |
| ma_slope_20 | O(N) trivial | finalize() |
| range_size | O(N) rolling window | finalize() |
| price_position | O(N) trivial | finalize() |
| last_swing_high/low_price | O(N) trivial | finalize() |
| displacement_flag | O(N) trivial | finalize() |
| retest_flag | O(N) rolling window | finalize() |

**Estimated dead compute proportion:** ~25 intermediate columns vs 38 canonical → ~40% of pipeline compute discarded by finalize().

### 4. Feature Importance Ranking (by reachability depth)

```
TIER 1 — DIRECT DECISION REACHABLE (can alter trade decision via multiple paths)
  body_ratio, disp_strength, retest_depth  ← also trigger HARD DRIFT VETO
  atr, candles_since_retest, double_sweep, sweep_detected
  ema_fast, ema_slow, momentum_score

TIER 2 — REGIME REACHABLE (can alter decision via regime classification)
  ema_spread, trend_bias, volatility_ratio

TIER 3 — ENGINE REACHABLE (can alter engine scores, thus fusion)
  high, low, close  (RR engine → 0.20 fusion weight)

TIER 4 — MODEL REACHABLE (can only affect ZoneGate, weight = 0.20-0.25 in fusion)
  All 20 ACTIVE_VIA_MODEL features

TIER 5 — INFRASTRUCTURE (read by CRT engine via state, not canonical features)
  session (CRT engine gating)
```

### 5. Recommended Feature Pruning Plan

#### IMMEDIATE REMOVAL (dead compute, no reachability path)
1. `rsi_state` — computed in FeaturePipeline, dropped by finalize()
2. `bb_upper`, `bb_lower`, `bb_width`, `bb_position` — computed, never canonical
3. `price_vs_ma20`, `price_vs_ma50`, `ma_slope_20` — z-scored intermediate
4. `upper_wick`, `lower_wick`, `candle_body`, `delta_close`, `prev_close` — debugging intermediates
5. `direction` — not consumed anywhere
6. `price_position` — not canonical
7. `range_size` — not canonical
8. `displacement_flag`, `retest_flag` — intermediate for canonical features, not themselves needed

#### ZONEGATE ABLATION REQUIRED (indeterminate)
For the **20 ACTIVE_VIA_MODEL features**, their decision reachability depends entirely on the ZoneGate model weights. Run the ablation experiment script to determine which of these actually matter:

- open, volume, volume_ratio, rsi_14, macd_line, macd_signal, macd_hist, break_of_structure, swing_high, swing_low, higher_high, lower_low, body_size, wick_size, trend_strength, hour_of_day, liquidity_distance, liquidity_pressure_score, volume_spike

If ablation shows these contribute zero score change when set to constant → **remove from CANONICAL_FEATURES**.

#### VALIDATE (suspicious architecture)
1. **FeaturePipeline ema_fast (9) vs CRTEngine ema_fast (2):** Different periods. The canonical ema_fast(9) feeds GaussianEngine for fusion. The CRTEngine's ema_fast(2) feeds soft confirmation. Any path that mixes these would produce wrong scores. **Verify they never cross.**

2. **FeaturePipeline ATR vs CRTEngine ATR:** Both period 14 but implementation differs (pandas vs manual rolling). Verify byte-identical output on same data.

3. **session in canonical features (int8) vs CRT engine state gating:** The canonical `session` is int8 (0/1/2). CRT engine reads `allowed_sessions` from config. These are independent paths. ZoneGate receives the int8 session — if the model was trained on a different encoding, mixing is wrong.

---

## Ablation Experiment Script

The following script performs feature-level ablation on the entire 38-dim canonical vector.

```python
#!/usr/bin/env python3
"""
run_feature_ablation.py
=======================
Feature ablation experiment for ZoneGate model.

For each canonical feature index (0-37):
  1. Load the baseline CPI/OHLCV dataset
  2. Run FeaturePipeline → get full 38-dim vectors
  3. For each vector, set feature[i] = 0.0
  4. Run through ZoneGate model_fn
  5. Compare with baseline score
  6. If delta == 0 for all rows → feature is DEAD_OR_DECORATIVE
  7. If delta > epsilon → feature is ACTIVE

Usage:
    python scripts/research/run_feature_ablation.py --csv data/EURUSD_M15.csv
"""

import sys, os, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from collections import defaultdict

from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from utils.logging_config import get_flow_logger
from engines.live_engine import get_zone_gate

logger = get_flow_logger("FEATURE_ABLATION")

ABLATION_VALUE = 0.0       # Value to set for ablated features
EPSILON = 0.001            # Minimum score delta to consider a feature "active"
ZONE_REGISTRY_PATH = "models/zone_registry.json"
ZONE_MIN_SAMPLES = 50
ZONE_TOP_K = 3


def load_zone_gate_model():
    """Load the same ZoneGate used by EngineRunner."""
    return get_zone_gate(
        ZONE_REGISTRY_PATH,
        min_samples=ZONE_MIN_SAMPLES,
        top_n=ZONE_TOP_K,
    )


def run_ablation(csv_path: str) -> dict:
    """Run full ablation experiment."""
    # Load and pipeline
    raw_df = pd.read_csv(csv_path)
    pipeline = FeaturePipeline(raw_df)
    enriched_df, vectors = pipeline.run()
    
    logger.info("Loaded %d rows, %d features", len(enriched_df), vectors.shape[1])
    assert vectors.shape[1] == len(CANONICAL_FEATURES), (
        f"Vector dim {vectors.shape[1]} != canonical {len(CANONICAL_FEATURES)}"
    )
    
    # Load zone gate model
    zone_gate = load_zone_gate_model()
    
    # Compute baseline scores
    baseline_scores = []
    for vector in vectors:
        result = zone_gate.check(vector.tolist())
        baseline_scores.append(float(result.get("score", 0.5)))
    baseline_mean = np.mean(baseline_scores)
    logger.info("Baseline zone gate: mean=%.4f std=%.4f", baseline_mean, np.std(baseline_scores))
    
    # Ablate each feature
    results = {}
    for i, feat_name in enumerate(CANONICAL_FEATURES):
        ablated_scores = []
        for vector in vectors:
            vec_abl = vector.copy()
            vec_abl[i] = ABLATION_VALUE
            result = zone_gate.check(vec_abl.tolist())
            ablated_scores.append(float(result.get("score", 0.5)))
        
        delta_mean = np.mean(ablated_scores) - baseline_mean
        delta_abs_mean = np.mean(np.abs(np.array(ablated_scores) - np.array(baseline_scores)))
        max_delta = np.max(np.abs(np.array(ablated_scores) - np.array(baseline_scores)))
        
        is_active = delta_abs_mean > EPSILON
        
        results[feat_name] = {
            "index": i,
            "baseline_mean": round(baseline_mean, 4),
            "ablated_mean": round(np.mean(ablated_scores), 4),
            "delta_mean": round(delta_mean, 4),
            "delta_abs_mean": round(delta_abs_mean, 4),
            "max_delta": round(max_delta, 4),
            "std_ablated": round(np.std(ablated_scores), 4),
            "active": is_active,
        }
        
        status = "ACTIVE" if is_active else "DEAD_OR_DECORATIVE"
        logger.info(
            "  [%s] feat[%2d] %-25s mean=%.4f Δ=%.6f |Δ|=%.4f max|Δ|=%.4f",
            status, i, feat_name,
            np.mean(ablated_scores), delta_mean, delta_abs_mean, max_delta,
        )
    
    # Summary
    active_count = sum(1 for r in results.values() if r["active"])
    dead_count = len(results) - active_count
    
    summary = {
        "total_features": len(CANONICAL_FEATURES),
        "active_features": active_count,
        "dead_or_decorative": dead_count,
        "baseline_mean": round(baseline_mean, 4),
        "ablation_value": ABLATION_VALUE,
        "epsilon": EPSILON,
        "active_feature_names": [k for k, v in results.items() if v["active"]],
        "dead_feature_names": [k for k, v in results.items() if not v["active"]],
        "per_feature": results,
    }
    
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Feature ablation experiment for ZoneGate model"
    )
    ap.add_argument("--csv", required=True, help="Path to OHLCV CSV file")
    ap.add_argument("--output", default="reports/feature_ablation_results.json",
                    help="Output JSON path")
    args = ap.parse_args()
    
    results = run_ablation(args.csv)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n=== Ablation Complete ===")
    print(f"Total:     {results['total_features']}")
    print(f"Active:    {results['active_features']}")
    print(f"Dead:      {results['dead_or_decorative']}")
    print(f"\nDead features: {results['dead_feature_names']}")
    print(f"\nResults written to: {output_path}")
```

---

*End of Feature Reachability Audit Report*