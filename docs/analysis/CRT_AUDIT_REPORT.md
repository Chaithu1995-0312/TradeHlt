# CRT Engine Audit Report
**Date:** 2026-07-26
**Scope:** Source-based audit of all CRT-related implementations

---

## Architecture Overview

There are **three distinct CRT subsystems** in the codebase:

| Layer | File | Role | Execution Authority |
|---|---|---|---|
| **Production Engine** | `src/config_layer/crt_engine_v2.py` (3,315 lines) | Live trading state machine | **Primary** |
| **Shadow Resolver** | `src/features/crt_state_resolver.py` (1,141 lines) | Market-reality validation layer | Research only |
| **Scoring Adapter** | `src/engines/crt_engine.py` → `scoring_engine.py` | Strategy wrapper path | Secondary |

---

## 1. Interface Verification

### 1A. Production Engine (`crt_engine_v2.py`)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `CRTEngine.process_candle(candle, htf_id, session)` | `Candle` + HTF window id + session string | Engine action dict (state, trade, score, events) | ✅ |
| `StateMachine.try_range_to_sweep(state, sweep, ev_logger)` | `EngineState` + `SweepEvent` | `bool`: transition success | ✅ |
| `StateMachine.try_sweep_to_displacement(state, candle, ev_logger)` | `EngineState` + `Candle` | `bool`: 4-gate guard pass | ✅ |
| `StateMachine.try_displacement_to_expansion(state, candle, ev_logger)` | `EngineState` + `Candle` | `bool`: directional + ATR guard pass | ✅ |
| `StateMachine.try_expansion_to_retest(state, candle, atr, ev_logger)` | `EngineState` + `Candle` + ATR | `bool`: adaptive depth ceiling pass | ✅ |
| `StateMachine.try_retest_to_execution(state, candle, ev_logger)` | `EngineState` | `bool` | ✅ |
| `UltronRiskEngine.compute_score(state)` | `EngineState` | `RiskScore` (4-component + decay) | ✅ |
| `UltronRiskEngine.approve_with_soft_conf(state, conf_candle)` | `EngineState` + confirm candle | `(bool, RejectReason, float fusion_score)` | ✅ |
| `ExecutionEngine.build_trade(state, risk_engine)` | `EngineState` + optional `UltronRiskEngine` | `Optional[Trade]` | ✅ |

### 1B. Scoring Adapter (`scoring_engine.py`)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `compute_scores(body_ratio, move, atr, retest_depth, ...)` | 8 feature scalars + weights | `dict{sweep, breakout, retest, time, final}` | ✅ |
| `ScoringEngine.compute(features)` | Feature dict | `dict{score, p_win, components}` | ✅ |
| `ScoringEngine.score(features, gaussian_score, sub_scores)` | Features + gaussian score + sub-scores | `dict{final_score, gaussian, neural, llm, decision, reason, override}` | ✅ |

### 1C. Shadow Resolver (`crt_state_resolver.py`)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `CRTStateResolver.resolve(features, timestamp, htf_id, force_reset)` | 39-dim vector or dict + state metadata | `str` (state name from config) | ✅ |
| `CRTStateResolver.resolve_batch(vectors, timestamps, htf_ids)` | Lists of above | `list[str]` states | ✅ |

**Finding 1 (PARTIAL):** The `CRTStateResolver` explicitly notes it cannot reproduce EXECUTION or RESOLUTION states because the pipeline feature vector lacks a risk-score column. This is documented (`market_crt_states.yaml` comment) but means the shadow resolver's state distribution will always show EXECUTION=RESOLUTION=0 regardless of actual engine behavior.

---

## 2. Internal Algorithm Verification

### 2A. State Machine Transitions

**RANGE → SWEEP:**
```
RangeDetector.detect_sweep(candle, active_range, prev_sweep):
  1. swept_high = candle.high > range.h_ref AND candle.close < range.h_ref
  2. swept_low  = candle.low  < range.l_ref AND candle.close > range.l_ref
  3. double_confirmed = prev_sweep exists AND direction != prev direction
```
✅ Verdict: MATCH — correct range-boundary sweep detection.

**SWEEP → DISPLACEMENT** (4 sequential gates):
```
try_sweep_to_displacement:
  Gate 1: abs(close-open) >= atr_min_displacement * atr_abs      (1.2 × ATR)
  Gate 2: sweep age <= max_sweep_age_candles                      (20 candles)
  Gate 3: body_ratio >= body_ratio_min                            (0.70)
  Gate 4: wick_size >= atr_multiplier_min * atr_abs               (1.5 × ATR)
```
✅ Verdict: MATCH — all 4 gates match the documented architecture. Gate order matches `crt_engine_v2.py` header docstring exactly.

**DISPLACEMENT → EXPANSION:**
```
try_displacement_to_expansion:
  Gate 1: displacement_candle exists in memory
  Gate 2: directional bar (LONG → bullish close, SHORT → bearish close)
  Gate 3: close extends beyond displacement_close in direction
  Gate 4: abs(close - disp_close) >= expansion_atr_min_distance * atr_abs (0.2 × ATR)
```
✅ Verdict: MATCH — 4-gate guard with [PATCH 3] ATR-distance strengthening confirmed.

**EXPANSION → RETEST** (adaptive ceiling):
```
try_expansion_to_retest:
  Gate 1: active_range is not None
  Gate 2: depth_abs >= retest_min_depth_atr_fraction * atr       (0.10 × ATR floor)
  Gate 3: depth_abs <= max(static_ceiling, atr_ceiling)
           static_ceiling  = retest_depth_max × range.size        (0.25 × range)
           atr_ceiling     = retest_atr_depth_fraction × atr      (0.50 × ATR)
  Gate 4: displacement_atr_ratio <= max_displacement_strength     (2.0 — overextension guard)
```
✅ Verdict: MATCH — [PATCH 5] adaptive ceiling and [PATCH 7] displacement strength guard both confirmed.

**RETEST → EXECUTION** (soft confirmation):
```
try_retest_to_execution: (pure transition — risk is separate)

UltronRiskEngine.approve_with_soft_conf:
  1. Hard gates: news_active? spread_pct > max_spread_pct?
  2. Base score G = RiskScore.final (4-component weighted + decay)
  3. BitNet validation (if enabled)
  4. Confirmation score C = compute_soft_confirmation (4-component blend + weak-link penalty)
  5. Fusion score S = G^α × C^β                                  (α=0.70, β=0.30)
  6. S >= 0.75 → Tier 1 full risk
  7. S >= 0.30 → Tier 2 half risk
  8. else → REJECTED
```
✅ Verdict: MATCH — geometric fusion formula matches docstring.

### 2B. Scoring Formula Verification

**UltronRiskEngine (engine path):**
```
RiskScore.final = (0.35·sweep + 0.25·breakout + 0.20·retest + 0.20·time) × decay_factor
```
Where:
- `sweep_score`: 0.6 base + 0.4 double_sweep_bonus − proximity_penalty (capped [0,1])
- `breakout_score`: 0.5·body_ratio + 0.5·min(wick_size/ATR / 3.0, 1.0)
- `retest_score`: 1.0 − depth_abs / adaptive_ceiling (capped to [0,1])
- `time_score`: 1.0 during overlap, 0.8 single session, 0.0 closed
- `decay_factor`: exp(−λ × candles_since_retest), λ=0.05

✅ Verdict: MATCH — formula matches documented architecture.

**ScoringEngine path (compute_scores):**
```
final = w_sweep·s_sweep + w_breakout·s_breakout + w_retest·s_retest + w_time·s_time
```
Where:
- `s_sweep`: 0.0 if no sweep, 0.7 single, 1.0 double
- `s_breakout`: 0.5·min(body_ratio,1.0) + 0.5·min(disp_strength_atr_rescale/2.0, 1.0)
- `s_retest`: exp(−(retest_depth−0.5)²/0.04) — Gaussian centred at 0.5
- `s_time`: exp(−λ·max(0, candles_since_retest))

⚠ **Finding 2 (PARTIAL — DRIFT WARNING):** The **engine's** retest_score uses linear decay from 1.0 as depth approaches the adaptive ceiling. The **scoring engine's** s_retest uses a Gaussian centered at depth=0.5. These produce materially different scores for the same input values:

| retest_depth | Engine score (linear) | ScoringEngine score (Gaussian) |
|---|---|---|
| 0.0 | 1.0 | exp(−0.25/0.04) ≈ 0.0019 |
| 0.5 | ~0.5 (from 1.0 - 0.5/ceiling) | exp(0/0.04) = 1.0 |
| 1.0 | ~0.0 | exp(−0.25/0.04) ≈ 0.0019 |

The scoring engine considers retest_depth=0.0 (price at boundary, tight retest) as **near-zero confidence**, while the engine considers it **maximum confidence**. This is a **semantic inversion** — not merely a different scaling.

**Finding 2a (PARTIAL):** The two scoring paths (`compute_scores` in `scoring_engine.py` vs `UltronRiskEngine.compute_score` in `crt_engine_v2.py`) are structurally similar (4-component weighted sum + time decay) but use **different formulas** for each sub-score. The adapter layer (`crt_engine.py`) routes to `compute_scores`, not to the engine's `UltronRiskEngine`. This means the strategy wrapper path produces scores that do not match the engine's risk assessment.

### 2C. Shadow Resolver Predicate Fidelity

The resolver uses `market_crt_states.yaml` predicates evaluated against feature states from `FeatureStateEncoder`. Key observed divergences vs engine behavior:

| State | Resolver Gate | Engine Gate | Verdict |
|---|---|---|---|
| **SWEEP** | `liquidity_sweep: [SellSideSweep, BuySideSweep]` + `break_of_structure: [NoBreak]` + `displacement_flag: [NoDisplacement]` | `detect_sweep()`: price beyond HTF range ref + closes back inside | **PARTIAL** — Detector geometry differs (pipeline last-swing vs engine HTF-range) |
| **DISPLACEMENT** | `displacement_flag: [Displacement]` + continuous gates (4-way ATR check) | `try_sweep_to_displacement()`: same 4 gates | **MATCH** — Continuous gates faithfully mirror engine |
| **EXPANSION** | `displacement_flag: [Displacement]` + funnel + ATR extension gate | `try_displacement_to_expansion()` | **MATCH** — Gate structure identical |
| **RETEST** | `retest_flag: [RetestActive]` + `sweep_detected: [SweepDetected]` + `break_of_structure: [NoBreak]` + depth ≤ 0.08 | `try_expansion_to_retest()`: adaptive ceiling + displacement strength guard | **PARTIAL** — Resolver uses hardcoded depth_max=0.08 vs engine's adaptive ceiling; lacks displacement_strength gate |

**Finding 3 (PARTIAL):** The resolver's retest gate depth_max=0.08 is a **hard threshold**, while the engine uses an adaptive ceiling `max(0.25·range_size, 0.50·ATR)`. These produce different filter outcomes:
- Low-volatility market: engine ceiling < 0.08 → engine is stricter
- High-volatility market: engine ceiling > 0.08 → engine is looser

---

## 3. Causality Check

### 3A. Temporal Ordering

| Check | Source | Status |
|---|---|---|
| ATR computed from past candles only | `RangeDetector.compute_atr()`: `trs[-period:]` on past range | ✅ No look-ahead |
| Sweep detection uses current candle vs pre-established HTF range | `detect_sweep()`: compares to `active_range` formed from prior HTF buffer | ✅ |
| Candle.index is monotonic | `process_candle()` increments `current_candle_index` | ✅ |
| Event ordering preserved in event_log | Appended sequentially in EngineEvent | ✅ |
| Cached features at RETEST use current candle's close + displacement candle's stored prices | `state.cached_features` written in `try_expansion_to_retest` | ✅ |
| Trade built at EXECUTION uses retest_candle.close which is already known | `build_trade()` uses state.retest_candle.close | ✅ |

### 3B. Potential Leakage Concerns

| Concern | Analysis | Status |
|---|---|---|
| `feature_pipeline` might emit multi-candle aggregates (HH/LL) that peek forward | Not CRT's responsibility, but the `retest_flag` FM-061 uses rolling lookback (within sample, no future) | ✅ (pipeline question, not CRT) |
| `cached_features` survives state reset? | `reset_to_range()` sets `state.cached_features = None` — but the Trade object holds its own copy | ✅ Trade stores immutable snapshot |
| Shadow memory survives HTF reset but has TTL expiry | `pending_displacement_ttl` decrements per candle | ✅ |
| BitNet scoring uses cached features, not raw OHLCV | `bitnet_score()` receives pre-computed features, no future data | ✅ |

✅ **Verdict: No causal leakage detected.** All state transitions consume only past or current-candle data.

---

## 4. Semantic Ownership

| Claimed Responsibility | Code Evidence | Status |
|---|---|---|
| **CRT scores market state structure** (sweep → displacement → expansion → retest trajectory) | `StateMachine` transitions + `RiskScore` components reference only market geometry | ✅ |
| **CRT should NOT predict profitability** | `RiskScore.final` is a state-quality assessment (sweep conviction, breakout strength, retest depth, time decay). No PnL prediction model embedded. | ✅ |
| **CRT should NOT classify market regime** (trending/ranging/pullback) | Trend classification is in `sweep_taxonomy.py` / `feature_pipeline`. Engine references `direction` (LONG/SHORT) but does not classify regime. | ✅ |
| **CRT should NOT redefine OHLCV** | Uses `Candle` geometry (open/high/low/close) + ATR only. No raw price reinterpretation. FM formulas preserve registered identities. | ✅ |
| **CRT should NOT estimate TP probability** | `ExecutionEngine.build_trade()` computes TP levels from ATR-based risk distance, not from probability estimation. | ✅ |
| **Shadow resolver should not replace engine** | Docstring explicitly states it is a MARKET REALITY layer, not execution authority. | ✅ |
| **Shadow resolver should not produce EXECUTION without score** | Gate fail-closes on missing score feature — documented limitation. | ✅ |

✅ **Verdict: Semantic ownership is correct.** Each component stays within its documented responsibility.

---

## 5. Drift Detection — Intended vs Actual

### Component-by-Component Classification

| Component | Intended Architecture | Actual Implementation | Verdict |
|---|---|---|---|
| **RangeDetector** | Detect HTF range + compute ATR + detect sweeps | Performs all three roles correctly | **MATCH** |
| **StateMachine** | 9-state FSM with legal transition graph | 9 states, 9 guard functions, config-loaded transition graph from WHO bundle | **MATCH** |
| **UltronRiskEngine** | 4-component weighted score + soft-confirmation fusion | 4-component score + adaptive ceiling + weak-link penalty + geometric fusion (G^α × C^β) | **MATCH** |
| **ExecutionEngine** | Build trade with SL anchored to displacement candle + TP at R-multiples | SL anchored to displacement extreme + ATR buffer; TP as R-multiples per intent type | **MATCH** |
| **ResetLogic** | HTF + retrace + extension resets; protect active setups | HTF change, 50% retrace, 1.618 extension; protects EXPANSION/RETEST and open trades | **MATCH** |
| **Shadow memory** (Phase 1) | Pending displacement survives one HTF reset with TTL | `pending_displacement_candle` stored on reset, TTL=4 candles, collapses via SHADOW_PENDING→EXPANSION | **MATCH** |
| **ScoringEngine.compute_scores** | 4-component CRT scoring | Uses Gaussian retest score (different from engine's linear retest) | **DRIFT** (see Finding 2) |
| **ScoringEngine.ScoringEngine** class | Multi-modal scoring gate | Deterministic / neural / LLM modes — overengineered for current use, but structurally correct | **PARTIAL** (unused complexity) |
| **CRTStateResolver** | Config-driven market-reality shadow | Faithfully mirrors engine funnel for SWEEP→DISPLACEMENT→EXPANSION; RETEST gate diverges | **PARTIAL** (see Finding 3) |
| **s01_crt_wrapper** | Adapter wrapping crt_engine.compute | Correct adapter pattern; signal direction from feature flags (trend_bias + BoS/sweep) | **MATCH** |

---

## 6. Detailed Findings

### Finding 1 — Shadow Resolver Cannot Reproduce EXECUTION/RESOLUTION
- **Severity:** Informational
- **Impact:** Research state counts will always show 0 for EXECUTION/RESOLUTION
- **Recommendation:** Document this limitation in all reports that compare resolver vs engine distributions. Consider adding a synthetic score column to the enriched corpus for resolver parity experiments.

### Finding 2 — Scoring Formula Divergence Between Paths
- **Severity:** MEDIUM
- **Impact:** The strategy wrapper path (`s01_crt_wrapper` → `crt_engine.compute` → `compute_scores`) produces scores that differ materially from the engine's `UltronRiskEngine`. The retest score is semantically inverted (Gaussian centred at 0.5 vs linear from 1.0).
- **Location:** `src/engines/scoring_engine.py:48` vs `src/config_layer/crt_engine_v2.py:1797-1812`
- **Recommendation:** Either (a) unify the scoring formula, or (b) document explicitly that the two paths produce different scores and which path is authoritative for which use case.

### Finding 3 — Resolver RETEST Gate Uses Hard Threshold
- **Severity:** LOW
- **Impact:** The shadow resolver's RETEST occupancy may diverge from engine in high/low volatility regimes.
- **Location:** `src/features/crt_state_resolver.py:674` uses `retest_depth_max: 0.08` from config; engine at `crt_engine_v2.py:1460-1462` uses adaptive ceiling.
- **Recommendation:** Either (a) replicate the adaptive ceiling formula in the resolver, or (b) document that the resolver uses a simplified static threshold and quantify the divergence.

### Finding 4 (Minor) — DUAL `approve` methods in UltronRiskEngine
- **Severity:** LOW
- **Impact:** `UltronRiskEngine` has TWO approval methods: `approve()` (line 2016) and `approve_with_soft_conf()` (line 1930). The `approve()` method has dead code (commented-out `rs = self.compute_score(state)` on line 2031 before the uncommented version on line 2034) and uses BitNet differently (caches to `state.bitnet_main_score` vs direct call in `approve_with_soft_conf`).
- **Recommendation:** Consolidate to one approval path. The `approve_with_soft_conf` appears to be the intended modern path.

---

## 7. Summary

| Category | Status |
|---|---|
| **Interface** | ✅ All inputs/outputs verified |
| **Internal Algorithm** | 2 PARTIAL findings (scoring formula divergence, resolver gate) |
| **Causality** | ✅ No future leakage detected |
| **Semantic Ownership** | ✅ All components within responsibility boundaries |
| **Drift Classification** | 2 MATCH, 2 PARTIAL, 1 DRIFT (see below) |

### Drift Classifications

| Component | Classification |
|---|---|
| `crt_engine_v2.py` (RangeDetector + StateMachine + UltronRiskEngine + ExecutionEngine) | **MATCH** |
| `features/crt_state_resolver.py` | **PARTIAL** — RETEST gate simplified, cannot reproduce EXECUTION/RESOLUTION |
| `engines/scoring_engine.py` | **DRIFT** — Retest score formula semantically inverted vs engine |
| `engines/crt_engine.py` (wrapper) | **MATCH** — Correct delegation |
| `strategies/s01_crt_wrapper.py` | **MATCH** — Correct adapter pattern |

### Key Recommendation

The most actionable finding is **Finding 2**: the two scoring paths (engine vs adapter) use different retest formulas. If these paths are ever compared or fused, the scores will be inconsistent. Unify or explicitly document the divergence.