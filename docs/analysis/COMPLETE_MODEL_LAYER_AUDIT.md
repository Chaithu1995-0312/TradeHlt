# Complete Model Layer Audit — Certified Deliverable
**Date:** 2026-07-27  
**Auditor:** Principal Software Architect / Model Certification Auditor  
**Scope:** Every model declared in `active_models.yaml` (v2.3 schema), verified against source implementation  
**Methodology:** Intent → Architecture → Mathematics → Coding → Causality → Runtime → Contribution → Certification  

---

## Executive Summary

**10 models audited.**  
**1 CERTIFIED** (RREngine — Candle Polarity Index)  
**1 CONDITIONAL** (CRT Engine — scoring formula divergence between paths)  
**1 DORMANT** (BitNet)  
**1 DEPRECATED** (Strategies S1-S10)  
**1 EXPERIMENTAL** (EnvelopeNet)  
**1 UNWIRED** (TradeNet)  
**1 GHOST** (Legacy v1 TradeNet .pth pointer)  
**1 REDUNDANT** (ZoneGate — ΔG001≡0, non-pivotal)  
**1 FAILED** (LLM Layer — inactive production path)  
**1 FLAWED** (Gaussian Heuristic Kernel — symmetric, not directional)

### Critical Architectural Finding

The FusionEngine has **two scoring paths** that diverge architecturally:

| Path | Method | Used By | Engines |
|---|---|---|---|
| `compute()` | 4-engine weighted average | `EngineRunner.run()` — **production** | CRT, Gaussian, ZoneGate, RR |
| `evaluate()` | 3-layer stack (Gaussian→Neural→LLM) | Tests only | GaussianAdapter + neural_fn + llm_fn |

The `evaluate()` path contains a `neural` slot (with `neural_weight=0.4`) and an LLM gate — **both of which are dead code in production**. No code path instantiates `neural_fn` or injects it into FusionEngine when constructed by EngineRunner. The `fusion_use_evaluate` flag defaults to `False`. The neural_weight=0.4 and llm_weight=0.2 values in the config are inert.

**Total engines contributing to production decisions:** 4 (CRT at 0.4, Gaussian at 0.2, ZoneGate at 0.2, RR at 0.2).  
**Of these, only CRT carries structural signal.** Gaussian is a symmetric kernel (no direction). ZoneGate is non-pivotal (ΔG001≡0). RR is a candle polarity geometric filter.

---

## 1. Complete Model Inventory

| # | Key in active_models.yaml | Name | Status | Runtime File | Engine Key | Fusion Weight | Production Active |
|---|---|---|---|---|---|---|---|
| 1 | `crt` | CRT Engine | **active** | `src/config_layer/crt_engine_v2.py` | `crt` | 0.4 | ✅ |
| 2 | `gaussian` | Heuristic Gaussian | **active** | `src/engines/heuristic_gaussian_engine.py` | `gaussian` | 0.2 | ✅ (heuristic) |
| 3 | `bitnet` | BitNet Gate | **dormant** | `src/bitnet/bitnet_inference.py` | `null` | 0.0 | ❌ (use_bitnet=false) |
| 4 | `zone_gate` | Zone Gate | **active** | `src/engines/zone_gate_engine.py` | `zone_gate` | 0.2 | ✅ (non-pivotal) |
| 5 | `rr_model` | RR Engine | **active** | `src/engines/rr_engine.py` | `rr` | 0.2 | ✅ (base only) |
| 6 | `tradenet` | TradeNet | **orphaned** | `src/training/trade_net_v2.py` | `null` | 0.0 | ❌ (UNWIRED F-005) |
| 7 | `envelope` | EnvelopeNet | **experimental** | `src/research/envelope_offline/` | `null` | 0.0 | ❌ (4 defects) |
| 8 | `strategies` | S1-S10 | **orphaned** | `src/strategies/strategy_orchestrator.py` | `null` | 0.0 | ❌ (sidecar) |
| 9 | (embedded) | LLM Gate | **dormant** | `src/core/fusion_engine.py` evaluate() | `null` | 0.0 | ❌ (evaluate() not used) |
| 10 | `engine_runner` | EngineRunner | **active** | `src/core/engine_runner.py` | — | — | ✅ |

---

## 2. Model Dependency Graph

```
OHLCV → Feature Pipeline (39 canonical features)
           │
           ├──→ CRT Engine (crt_engine.py → scoring_engine.py)
           │       features: body_ratio, disp_strength, atr, retest_depth,
           │                 candles_since_retest, sweep_detected, double_sweep
           │       output: structure_rule_score [0,1]
           │       weight in fusion: 0.4
           │
           ├──→ Heuristic Gaussian (heuristic_gaussian_engine.py)
           │       features: ema_fast, ema_slow, momentum_score
           │       output: ema_momentum_kernel_score [0,1] — SYMMETRIC (mu=0)
           │       weight in fusion: 0.2
           │
           ├──→ ZoneGate (zone_cluster_score.py → zone_gate_engine.py)
           │       features: 38 canonical (excludes macd_hist_raw)
           │       output: neighbourhood_quality_score [0,1] — ΔG001≡0
           │       weight in fusion: 0.2
           │
           ├──→ RR Engine (rr_engine.py)
           │       features: close, high, low
           │       output: candle_structure_quality [0,1]
           │       weight in fusion: 0.2
           │
           └──→ FusionEngine.compute()
                    ├── CRT score × 0.4
                    ├── Gaussian score × 0.2
                    ├── ZoneGate score × 0.2  [non-pivotal — switching it ON/OFF changes nothing]
                    └── RR score × 0.2
                    = weighted average → [0,1]
                    → ScoreNormalizer (rolling min-max window=1000)
                    → DecisionEngine (tier thresholds)
```

### Dead Branches (models that exist but do NOT reach production decisions)

```
TradeNet (UNWIRED) → could inject via FusionEngine.neural_fn slot on evaluate()
EnvelopeNet (EXPERIMENTAL) → no registry, no config section, no spine wire
Strategies S1-S10 (ORPHANED) → sidecar, not on live spine → fuse_strategy_results() dormant
LLM Gate (DORMANT) → only fires on evaluate() path, which is not called
BitNet (DORMANT) → use_bitnet=false in active config, degrades book when on (F-055)
MLGaussianEngine (CONFIG-GATED) → gaussian_impl=ml triggers it, but active config uses "heuristic"
RRFusion (DISABLED) → rr_fusion.enabled=false in active config (F-038)
```

---

## 3. Runtime Execution Graph

```
EngineRunner.__init__(config)
  ├── self.adapter = TrapValidatorEngine(config)
  ├── self.gaussian = HeuristicGaussianEngine(config)  [gaussian_impl="heuristic"]
  ├── self.gaussian_shadow = None  [not shadow_ml mode]
  ├── self.rr = RREngine(config)
  ├── rr_fusion = None  [rr_fusion.enabled=false]
  ├── self._gaussian_adapter = GaussianAdapter(self.gaussian)  [for evaluate() only]
  ├── self._convergence = ConvergenceController(window=500)
  ├── self.fusion = FusionEngine(
  │       gaussian_adapter=self._gaussian_adapter,
  │       neural_fn=None,                     ← NOTE: neural slot never set
  │       llm_fn=None,                        ← NOTE: llm slot never set
  │       convergence_controller=self._convergence,
  │       config=FusionConfig(
  │           weight_crt=0.4,
  │           weight_gaussian=0.2,
  │           weight_zone_gate=0.2,
  │           weight_rr=0.2,
  │           gaussian_weight=0.6,             ← UNUSED on compute() path
  │           neural_weight=0.4,               ← UNUSED on compute() path
  │           llm_weight=0.2,                  ← UNUSED on compute() path
  │           enable_llm=True,                 ← UNUSED on compute() path
  │       )
  │   )
  └── self.decision = DecisionEngine(config)

EngineRunner.run(input_data, context)
  ├── Step 1: Adapter gating (score <= 0.0 → REJECT)
  ├── Step 2: Run 4 engines unconditionally
  │   ├── zone_result = score_zone_cluster() → zone_gate_engine → BitNetZoneGate
  │   ├── crt_result = crt_compute(features, context={score_component_weights})
  │   ├── gaussian_result = self.gaussian.compute(input_data, direction)  ← heuristic
  │   ├── rr_result = self.rr.compute(input_data)
  │   └── strategy_consensus (optional, from context)
  ├── Step 3: Engine completeness check (EXPECTED_ENGINES - keys)
  ├── Step 4: Fusion
  │   └── fusion_result = self.fusion.compute(engine_results, regime=current_regime)
  │       └── weighted average of 4 engine scores
  ├── Step 5: Fusion baseline decision (fusion_min_score=0.25)
  ├── Step 5b: Belief gate (disabled, signal_belief.enabled=false)
  ├── Step 6: RegimeGovernor (ultron_gate_enabled=false in backtest/training)
  └── Step 7: DecisionEngine
```

---

## 4. Model-by-Model Audit

### 4.1 CRT Engine — CONDITIONAL

| Audit Category | Result |
|---|---|
| **Intent** | "Is the market structure valid?" — detects sweep→displacement→expansion→retest trajectory |
| **Architecture** | ✅ 9-state FSM, RangeDetector→StateMachine→UltronRiskEngine→ExecutionEngine |
| **Mathematics** | ⚠️ **SCORING DRIFT (Finding CRT-F2)** — Two scoring paths produce different formulas. Engine's UltronRiskEngine uses `retest_score = 1.0 - depth/ceiling` (linear). The `compute_scores` adapter uses `exp(-(depth-0.5)²/0.04)` (Gaussian centered at 0.5). These are semantically inverted: depth=0.0 → engine=1.0 (max), adapter≈0.0. |
| **Coding** | ✅ No bugs found in state machine gates. `try_expansion_to_retest` adaptive ceiling correctly uses max(0.25×range, 0.50×ATR). `Detect_sweep` correctly checks high>h_ref AND close<h_ref. |
| **Causality** | ✅ No future leakage. ATR from past candles. Sweep detection vs pre-established HTF range. Candle.index monotonic. |
| **Runtime** | ✅ Active. Called every bar. Four gates (news_blackout, max_spread, session_filter, score_threshold) all checked. |
| **Contribution** | Unique — only engine producing structural market-state signal. Carries 0.4 fusion weight with 11 structural features. |
| **Certification** | **CONDITIONAL** — Core engine is correct, but the scoring adapter path (`scoring_engine.py`) has a semantically inverted retest formula vs the engine's UltronRiskEngine. The scoring_engine path is what enters the fusion score (via `crt_engine.compute` → `compute_scores`). **Recommendation:** Unify formulas or document the divergence explicitly. |

### 4.2 Gaussian (Heuristic Kernel) — FLAWED

| Audit Category | Result |
|---|---|
| **Intent** | "Is this historically profitable?" — Designed as Gaussian probability match over CRT-labelled states |
| **Architecture** | ✅ 3-feature kernel: `ema_fast`, `ema_slow`, `momentum_score` |
| **Mathematics** | `x = ((ema_fast-ema_slow)/ema_slow + tanh(momentum_score))/2`, `score = exp(-x²/2)` since mu=0.0, sigma=1.0 always (F-060). **The kernel is SYMMETRIC** — peaks when market is flat, decays equally for moves in either direction. Despite the label "directional_momentum_score", this cannot distinguish direction. |
| **Coding** | ✅ Clean implementation. Guards against ema_slow=0. Neutral condition for flat market returns 0.5. |
| **Causality** | ✅ Stateless per-bar. No future data. |
| **Runtime** | ✅ Active. Called every bar via `engine_runner.py:729`. Score enters fusion at weight 0.2. |
| **Contribution** | **Claimed: "probability-of-success match." Actual: symmetric similarity to zero.** The kernel evaluates distance from mu=0 (flat market condition), so it scores highest when ema_diff ≈ 0 and momentum ≈ 0. This is the OPPOSITE of what a directional edge system would want — it rewards indecision, not conviction. However, it contributes structural EMA divergence information that may correlate with market state. |
| **Certification** | **FAILED (semantic intent mismatch)** — The live kernel is NOT a probability-of-success estimator. It's a symmetric similarity measure centred on zero. The documented semantic (directional_momentum_score) does not match the actual mathematical behavior. The MLGaussianEngine path (38-dim GaussianNB) is the intended model but is gated behind `gaussian_impl=ml` which is not the active config. **Recommendation:** Either (a) accept the heuristic as a "market excitement score" and rename/redocument, or (b) promote the ML path. |

### 4.3 BitNet — DORMANT

| Audit Category | Result |
|---|---|
| **Intent** | "Is this market state acceptable?" — 6-feature hard-reject gate |
| **Architecture** | ✅ 6 features: body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep. Threshold=0.55. |
| **Mathematics** | ✅ Not reviewed in detail (uses external bitnet module). But F-055 finding: when enabled, degrades book (pooled ΔE=-0.13R, 0/4 instruments improve). |
| **Coding** | ⚠️ **Train/serve skew (F-050):** raw/unnormalized `atr` input (not scale-invariant). |
| **Causality** | ✅ Uses cached_features at RETEST, no future data. |
| **Runtime** | **DORMANT.** `use_bitnet=false` in active config. Not an EXPECTED_ENGINES producer — it gates inside UltronRiskEngine.approve(). |
| **Contribution** | When enabled, acts as a state-machine-perturbing VETO (reject resets CRT state machine). Has ΔG001≡0 (no authority). |
| **Certification** | **DORMANT** — Code complete, disabled by default, correctly so. 6-feature input contract is frozen. Requires ΔG001 before enabling. |

### 4.4 ZoneGate — REDUNDANT

| Audit Category | Result |
|---|---|
| **Intent** | "Is this feature-space neighbourhood historically good?" — nearest-neighbour similarity over 8 Gaussian zones |
| **Architecture** | ✅ 38-dim canonical vector (name-anchored extraction, excludes macd_hist_raw). 8 zones with hand-specified weight mask (24 active dims at ≈0.04167 each). |
| **Mathematics** | ⚠️ **Weights are NOT learned (Finding ZG-F1)** — all 8 zones carry identical weight mask. **Sigma is global (ZG-F2)** — all zones share same sigma vector. Per-zone scoring delegated to external `bitnet.zone_cosine_searcher` (black box). |
| **Coding** | ✅ Schema validation at load (ZoneFeatureOrderError — fail-closed). Name-anchored vector extraction. Cluster spread filter (reject if max-min > 0.15). |
| **Causality** | ✅ Static artifact. No future data. |
| **Runtime** | ✅ Active. Called every bar. Score enters fusion at weight 0.2. |
| **Contribution** | **ΔG001≡0 (F-036): Gate is non-pivotal.** Switching ZoneGate ON or OFF does not change fusion outcomes. It is "redundant/decision-dominated, not weak/underweighted." 6 of 8 zones have negative mean RR. Labels are F-022 contaminated. 0/8 zones clear honest E>0. |
| **Certification** | **REDUNDANT** — Architecturally correct (executes, passes valid data, fail-closed on misalignment) but economically inert. The 0.2 fusion weight could be redistributed to CRT without changing decisions. **Recommendation:** Document as ornamental. Do not retrain — no economic case exists. |

### 4.5 RR Engine — CERTIFIED

| Audit Category | Result |
|---|---|
| **Intent** | "Is the reward-risk economically viable?" — candle-polarity structural commitment index |
| **Architecture** | ✅ 3 inputs (close, high, low). Candle Polarity Index = max((high-close)/range, (close-low)/range). |
| **Mathematics** | ✅ Domain: {0.0} ∪ [0.5, 1.0]. Upper_body=1 when close at low (bullish pin). Lower_body=1 when close at high (bearish pin). Polarity peaks at 1.0 when close at either extreme — exactly what CRT wants (directional commitment). 0.5 = doji/indecision. 0.0 = degenerate. |
| **Coding** | ✅ Clean. Guards against invalid price structure (high ≥ close ≥ low). Guards against degenerate doji (range < EPS). KeyError and ValueError handlers return 0.0 (fail-soft). |
| **Causality** | ✅ Same candle geometry only. No forward-looking data. The docstring explicitly explains why this is NOT forward RR (close is at current candle). |
| **Runtime** | ✅ Active. Called every bar via `engine_runner.py:747`. Enters fusion at weight 0.2. |
| **Contribution** | Unique — only engine scoring candle structure quality. Properly named/redocumented after the RR name bug fix. The name "RR" is legacy but output_semantic is correctly "candle_structure_quality." |
| **Certification** | **CERTIFIED** — Implementation matches documented intent. Mathematical formula is correct and proven. Guards handle all edge cases. Semantic contract is honest (candle_structure_quality, not forward RR). The only model in the system that fully satisfies all audit criteria. |

### 4.6 TradeNet — UNWIRED

| Audit Category | Result |
|---|---|
| **Intent** | "What is the capital quality of this setup?" — 3-head survival classifier (p_tp1, p_tp2, p_survives_be) |
| **Architecture** | ✅ v2: 38→32→16→[3] MLP with 3 independent sigmoid heads. Composite = 0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be. |
| **Mathematics** | ⚠️ **3 independent Bernoulli, not a categorical distribution (TN-F1).** Heads don't sum to 1.0. Could have p_tp2 > p_tp1 (hierarchically impossible). Composite is hand-specified, not learned. No calibration layer. |
| **Coding** | ✅ v2 code complete. `make_neural_fn_v2()` wrapper returns correct `Callable[[dict], float]`. |
| **Causality** | ✅ Static artifact. Name-anchored feature extraction. |
| **Runtime** | **UNWIRED (F-005).** No production pipeline connection. The `FusionEngine.evaluate()` neural slot (where TradeNet would inject) is never called by EngineRunner. Registry has one v2 envelope (XAUUSD) with degenerate metrics (auc_p_tp1=0.5, zero TP1 hits). Only "active" model is v1 .pth file that does not exist on disk. |
| **Contribution** | Would contribute trade-outcome probability if wired. Currently contributes nothing. |
| **Certification** | **UNWIRED** — Code complete, architecture correct, but: (a) no trained model with non-degenerate metrics, (b) no production wire-up, (c) v3 active pointer points to non-existent file. **Recommendation:** Gate behind TN_QUAL_V1. Requires training with adequate TP1/TP2 outcomes and wiring `make_neural_fn_v2()` into EngineRunner. |

### 4.7 EnvelopeNet — EXPERIMENTAL

| Audit Category | Result |
|---|---|
| **Intent** | "What price–time operating envelope does this trade live in after entry?" — 4-head point estimator (mfe_r, mae_r_heat, holding_bars, time_to_mfe) |
| **Architecture** | ✅ 4 point heads (not quantile — cannot construct tp_band_r/sl_band_r/ttl_bars per ENV_ARCH_V1 §4.3-4.4). Canonical 38-vector input. |
| **Mathematics** | ❌ **4 unresolved defects (from file):** (1) Mirrored population — every bar twice with byte-identical features and mirrored targets, side is NOT a model input. 66.9% of mfe_r/mae_r_heat variance is within-pair and unlearnable. (2) Metric/product mismatch — acceptance is rank-only (IC) but product needs levels. (3) No null control — single-feature volatility baselines recover most reported skill. (4) Wrong ground truth for stop — mae_r_heat uses exit-agnostic horizon_excursion (mean ≈3.85R vs 1R stop), cannot source sl_band_r. |
| **Coding** | ✅ Shadow inference exists (`predict_heads`). |
| **Causality** | PIT_UNCLEAN (bundle-declared). Trained on centered_swings era data. |
| **Runtime** | **EXPERIMENTAL.** No registry (`models/envelope_registry.json` does not exist). No config section. No spine wire. |
| **Contribution** | None currently — "TRAINED ≠ VALIDATED ≠ AUTHORIZED." |
| **Certification** | **EXPERIMENTAL** — 4 unresolved design defects prevent certification. Requires: (a) fix mirrored-population problem, (b) add quantile heads for band construction, (c) add null-model controls, (d) causal re-dataset. |

### 4.8 Strategies S1-S10 — DEPRECATED

| Audit Category | Result |
|---|---|
| **Intent** | "Ten pluggable strategies aggregated by StrategyOrchestrator into consensus signal." |
| **Architecture** | ✅ Sidecar pattern. Dormant `fuse_strategy_results()` path on FusionEngine. |
| **Mathematics** | N/A — not active |
| **Coding** | ✅ All 10 strategy modules exist. `strategy_orchestrator.py` code is functional. |
| **Causality** | N/A — not active |
| **Runtime** | **ORPHANED.** `participates_in_live_spine: false`. Not consumed by production decision path. |
| **Contribution** | Zero in current production. Historical architectural artifact. |
| **Certification** | **DEPRECATED** — Sidecar, not on live spine. `fuse_strategy_results` is dormant. S8 'ML Ensemble' exists as code but is not a production alpha engine. **Recommendation:** Archive to `archive/` to reduce cognitive load. |

### 4.9 LLM Gate — FAILED

| Audit Category | Result |
|---|---|
| **Intent** | "Uncertainty arbiter — fires only when Gaussian score in [0.45, 0.65]." |
| **Architecture** | ✅ 3-layer stack design (Gaussian→Neural→LLM) in `FusionEngine.evaluate()` |
| **Mathematics** | ✅ LLM activation band [0.45, 0.65]. Blend: (1-0.2)×base + 0.2×llm_score |
| **Coding** | ✅ Implementation in `fusion_engine.py:620-637` is correct. Fail-open on LLM errors. |
| **Causality** | ✅ No future data — LLM fires on current-bar scores. |
| **Runtime** | **DORMANT.** `EngineRunner.__init__` does NOT provide an `llm_fn` to FusionEngine. The `fusion_use_evaluate` flag defaults to `False`. The LLM gate code exists but is never reached. |
| **Contribution** | Zero. The `enable_llm=True` config value is inert because `self.llm_fn is None` in the FusionEngine constructed by EngineRunner. |
| **Certification** | **FAILED** — The LLM gate is architecturally designed, mathematically correct in isolation, but functionally dead. The config declares `enable_llm=True` which is misleading — it suggests LLM is active when no LLM function is ever injected. **Recommendation:** Either (a) wire an actual LLM function and switch production to `evaluate()` path, or (b) set `enable_llm=false` in config to match reality. |

### 4.10 EngineRunner — CONDITIONAL (wiring authority)

| Audit Category | Result |
|---|---|
| **Intent** | "Orchestrate the full pipeline: 4 engines → fusion → decision." |
| **Architecture** | ✅ 7-step pipeline: Adapter → Engines → Completeness → Fusion → Baseline → RegimeGovernor → DecisionEngine |
| **Mathematics** | N/A — orchestrator only |
| **Coding** | ✅ Strict config accessor (`_cfg_require` fails fast on missing keys). Engine completeness check rejects if any of 4 EXPECTED_ENGINES missing. |
| **Causality** | ✅ No lookahead in orchestration. |
| **Runtime** | **ACTIVE — production spine.** But wiring omissions: (a) `FusionEngine` constructed with `neural_fn=None` and `llm_fn=None`, (b) `fusion_use_evaluate=false` so the evaluate() path is never taken, (c) `_evaluate_fusion_path()` exists but only runs when `use_evaluate` or `compare_evaluate` are true. |
| **Contribution** | Unique — single decision authority. |
| **Certification** | **CONDITIONAL** — Correct as an orchestrator but perpetuates the compute/evaluate path split. The neural_fn and llm_fn slots are not wired, making evaluate() a test-only path. |

---

## 5. Coding Defects

| ID | Severity | Location | Description |
|---|---|---|---|
| CD-1 | LOW | `src/core/engine_runner.py:91-117` | `ENGINE_RUNNER_DEFAULTS` nests `fusion_engine` under `engine_runner` but production JSON has `fusion_engine` at top-level. Not a runtime bug (only test construction), but documentation drift. |
| CD-2 | LOW | `src/engines/scoring_engine.py:48` (ghost path) | `compute_gaussian_score` function has zero call sites. Import-guarded against `bitnet.zone_cosine_searcher` with fallback to formula that is neither heuristic kernel nor ML model. **Recommendation:** Remove. |
| CD-3 | LOW | `src/training/trade_net_v2.py:376-408` | `_predict_legacy` silently truncates feature vector if it exceeds model dimension (`vec = vec[:n]`). Currently moot (no .pth files on disk), but latent bug. **Recommendation:** Log warning on truncation or strict dimension check. |
| CD-4 | INFO | `src/config_layer/crt_engine_v2.py:2016-2034` | `UltronRiskEngine` has TWO approval methods (`approve()` and `approve_with_soft_conf()`). `approve()` has dead comment on line 2031 (`# rs = self.compute_score(state)`) before uncommented version on line 2034. **Recommendation:** Consolidate. |
| CD-5 | LOW | `src/engines/zone_gate_engine.py:89-103` | `_compute_soft_zone_score()` is dormant (zone_mode="hard" in active config). Code exists but never executed. |
| CD-6 | INFO | `src/engines/heuristic_gaussian_engine.py:321` | `direction` parameter accepted for API compatibility but explicitly ignored. The docstring at line 321 says "direction is accepted ... but is intentionally ignored." This is honest but means the "directional" claim is false. |

---

## 6. Mathematical Defects

| ID | Severity | Location | Description |
|---|---|---|---|
| MD-1 | HIGH | `src/engines/scoring_engine.py` vs `crt_engine_v2.py:1797-1812` | **Scoring formula divergence (CRT-F2).** Engine's retest_score = 1.0 - depth/ceiling (linear). Adapter's retest_score = exp(-(depth-0.5)²/0.04) (Gaussian centred at 0.5). Semantically inverted: depth=0 → engine=1.0 (max), adapter≈0.0019. This means the scoring_engine path (used by fusion) produces materially different CRT scores than the UltronRiskEngine's internal scoring. |
| MD-2 | MEDIUM | `src/engines/heuristic_gaussian_engine.py:358-366` | **Symmetric kernel, not directional.** `x = (ema_diff + tanh(momentum))/2`, mu=0.0, sigma=1.0. Score = exp(-x²/2). Peaks at x=0 (flat market), decays symmetrically for any directional move. The engine is correctly named "heuristic" and documented as direction-agnostic at line 321, but still carries the `output_semantic: ema_momentum_kernel_score` which does NOT represent directional momentum. |
| MD-3 | LOW | `src/training/train_trade_net_v2.py:290-296` | Equal head weighting in loss — each BCE term contributes equally to gradient regardless of class balance or pos_weight. For extreme imbalance (e.g., p_tp2 with <1% positive rate), the head contribution to total gradient is the same as p_tp1. |
| MD-4 | LOW | `src/core/fusion_engine.py:40-55` | ScoreNormalizer uses rolling min-max with window=1000. When all scores in window are identical, returns 0.5. This means a sustained period of invariant scores (e.g., constant market condition) degrades to 0.5 regardless of absolute level. |

---

## 7. Wiring Defects

| ID | Severity | Location | Description |
|---|---|---|---|
| WD-1 | CRITICAL | `src/core/engine_runner.py:444-448` | **neural_fn and llm_fn are never wired.** FusionEngine constructed without them. The neural slot (weight 0.4) and LLM gate (weight 0.2) are dead code. The config declares `enable_llm=true` and `neural_weight=0.4` but neither function is ever injected. |
| WD-2 | CRITICAL | `src/core/fusion_engine.py:555-666` | **evaluate() path is dead in production.** EngineRunner.run() calls `self.fusion.compute()` (line 851), not `self.fusion.evaluate()`. The `fusion_use_evaluate` flag defaults to False. The entire 3-layer stack (Gaussian→Neural→LLM) exists only in test code. |
| WD-3 | HIGH | `src/core/engine_runner.py:116-117` | **Config defaults drift.** `ENGINE_RUNNER_DEFAULTS` has `fusion_engine` nested under `engine_runner` with weights `{crt:0.4, gaussian:0.3, zone_gate:0.2, rr:0.1}`. The actual production config has `fusion_engine` at top level with weights `{crt:0.4, gaussian:0.2, zone_gate:0.2, rr:0.2}`. The defaults are only used in test construction (documented), but the Gaussian weight differs (0.3 vs 0.2). |
| WD-4 | MEDIUM | `models/tradenet_registry.json` | Active TradeNet model `v5_auto_2026_06_eth` is a v1 .pth file that does not exist on disk. Registry note confirms: "TradeNet is UNWIRED (F-005) and its .pth is absent." |

---

## 8. Registry Defects

| ID | Severity | Location | Description |
|---|---|---|---|
| RD-1 | MEDIUM | `models/gaussian_registry.json` | All 11 entries verified — **zero carry mu or sigma** (7 dangling, 4 on-disk). The registry is documented to provide mu/sigma for the heuristic kernel, but none of the entries do. The defaults (mu=0.0, sigma=1.0) fire on every successful load, making the registry byte-identical to the no-registry path. |
| RD-2 | MEDIUM | `models/zone_gate_registry.json` | v2 entry (`v2_gaussian_runtime_2026_07`, active:false) would now **FAIL CLOSED** because its `feature_order` names `macd_hist`/`wick_size` which no longer exist in the v4 live schema. The v4 entry correctly uses `macd_hist_z`/`candle_range`. |
| RD-3 | INFO | `models/tradenet_registry.json` | Only v2 envelope ever trained (`v2_xauusd_20260723T084643`) has `auc_p_tp1=0.5` (random) and `pos_rate_p_tp1=0.0` (zero TP1 hits). Never promoted. The v1 active pointer points to non-existent file. |
| RD-4 | INFO | `models/zone_registry_v4_2026_07.json` | 8 zones, all with hand-specified weight mask (not learned). Identical sigma across all zones. PIT_UNCLEAN provenance documented. |

---

## 9. Recommended Code Fixes

| Priority | File | Change |
|---|---|---|
| P0 | `src/core/engine_runner.py:444-448` | Wire neural_fn and llm_fn or explicitly document them as stubs. Add a comment at FusionEngine construction explaining which functions are provided and which are not. |
| P0 | `src/core/fusion_engine.py` | Either (a) switch production to `evaluate()` path and wire neural/LLM, or (b) remove the dead code in evaluate() to avoid confusion. Option (b) is lower risk if no immediate plans to wire. |
| P1 | `src/engines/scoring_engine.py:48` | Remove `compute_gaussian_score` (zero call sites, no architectural registration, ghost function). |
| P1 | `src/core/engine_runner.py:91-117` | Update `ENGINE_RUNNER_DEFAULTS` to match actual config layout or add explicit comment explaining structural difference. Gaussian weight in defaults (0.3) differs from production (0.2). |
| P2 | `src/engines/heuristic_gaussian_engine.py` | Rename `output_semantic` from `ema_momentum_kernel_score` to `symmetric_market_excitement_score` — the kernel is NOT directional and the output_semantic should reflect this. |
| P2 | `src/training/trade_net_v2.py:376-408` | Add dimension-check guard in `_predict_legacy` with warning log. Currently silently truncates. |
| P2 | `configs/production/v2_multi_2026_04.json` | Set `enable_llm: false` since no LLM function is injected. The current `enable_llm: true` is misleading. |
| P3 | `src/config_layer/crt_engine_v2.py:2016-2034` | Consolidate `approve()` and `approve_with_soft_conf()` into one path. `approve_with_soft_conf` appears to be the intended modern path. |

---

## 10. Wiring Recommendations

| Engine | Action | Rationale |
|---|---|---|
| **CRT** | ⚠️ **Audit gap to close** | Before certifying fully, unify scoring_engine.py retest formula with UltronRiskEngine's formula. Currently produces semantically inverted scores for the same inputs. |
| **Gaussian (heuristic)** | **Document limitation** | Accept as symmetric market excitement score. Do NOT pretend it's directional. Do NOT promote ML path without ΔG001. |
| **BitNet** | **Keep dormant** | Disabled by default. F-055 shows it degrades book when enabled. No ΔG001. |
| **ZoneGate** | **Keep wired but document as non-pivotal** | ΔG001≡0 confirmed. Switching ON/OFF doesn't change decisions. If fusion weights change in future, re-evaluate. |
| **RR** | **No changes needed** | CERTIFIED. Candle polarity index is mathematically correct and properly documented. |
| **TradeNet** | **Do NOT wire** | Gate behind TN_QUAL_V1. Requires: (a) train v2 envelope with non-degenerate metrics (need adequate TP1 hits), (b) wire `make_neural_fn_v2()` into EngineRunner + FusionEngine, (c) test that `final_score` changes appropriately. |
| **EnvelopeNet** | **Do NOT wire** | 4 unresolved design defects. Needs: (a) fix mirrored-population, (b) quantile heads, (c) null-model controls, (d) causal re-dataset. |
| **Strategies S1-S10** | **Archive** | Sidecar not on live spine. Move to `archive/` to reduce cognitive load. |
| **LLM Gate** | **Wire or disable config flag** | Either provide an llm_fn and switch to evaluate() path, or set enable_llm=false in config. Currently config says "enabled" but no LLM exists. |

---

## 11. Models Ready for Production

| Model | Production Status | Notes |
|---|---|---|
| **CRT Engine** | ✅ **Ready** (after scoring unification) | Core state machine is battle-tested. Only the scoring adapter needs alignment. |
| **RR Engine** | ✅ **Ready** | CERTIFIED. Candle polarity index is mathematically sound, properly guarded, correctly documented. |
| **ZoneGate** | ✅ **Ready** (as ornamental) | Executes correctly, passes valid data, fail-closed on misalignment. Non-pivotal but not harmful. |
| **Heuristic Gaussian** | ⚠️ **Ready with documentation caveat** | Accept as symmetric excitement score, NOT directional probability. |

---

## 12. Models Requiring Retraining

| Model | Reason | Action Required |
|---|---|---|
| **TradeNet v2** | Only v2 envelope has degenerate metrics (auc_p_tp1=0.5). Active v1 .pth absent. | Train on instrument with adequate TP1/TP2 outcomes. Requires TN_QUAL_V1. |
| **Gaussian ML (v4_mirrored)** | Not the active implementation. 38-dim GaussianNB exists but `gaussian_impl=ml` not enabled. | Requires ΔG001 before promoting. Currently gaussian_impl=heuristic in active config. |
| **ZoneGate zones** | **NOT recommended.** ΔG001≡0, 0/8 zones clear honest E>0, F-022 label contamination. Retraining cannot fix non-pivotal status. | Only consider if fusion weights change and ΔG001 becomes non-zero. |

---

## 13. Models to Deprecate

| Model | Action | Rationale |
|---|---|---|
| **Strategies S1-S10** | Archive to `archive/` | Sidecar, not on live spine. `fuse_strategy_results` dormant. S8 'ML Ensemble' etc. are code artifacts, not production alpha engines. |
| **Legacy v1 TradeNet .pth** | Remove registry active pointer | Pointing to non-existent file. Replace with absent entry. |
| **scoring_engine.py `compute_gaussian_score`** | Remove | Ghost function. Zero call sites. No architectural registration. |
| **UltronRiskEngine.approve()** | Consolidate into `approve_with_soft_conf()` | Two approval methods with BitNet caching difference. `approve_with_soft_conf` is the intended modern path. |

---

## 14. Remaining Research Gaps

| Gap | Area | Description |
|---|---|---|
| G-001 | CRT scoring | Why do two scoring formulas (engine vs adapter) produce semantically inverted retest scores? Which one is architecturally correct? |
| G-002 | Gaussian intent | The heuristic kernel is documented as "directional_momentum_score" but is mathematically symmetric (mu=0, sigma=1). Is this acceptable as a "market excitement" measure, or was the ML path always the intended implementation? |
| G-003 | ZoneGate budget | With ΔG001≡0, ZoneGate's 0.2 fusion weight could be reallocated. What would CRT score alone produce vs current fusion? Is the 0.2 weight diluting CRT's signal? |
| G-004 | Fusion path consolidation | Should the production path use `FusionEngine.compute()` (4 engines + convergence) or `FusionEngine.evaluate()` (3-layer Gaussian→Neural→LLM)? The two paths serve different architectures and cannot both be "correct" simultaneously. |
| G-005 | Neural/LLM intent | If evaluate() is the intended long-term architecture, what neural_fn and llm_fn should be injected? TradeNet (if wired) would provide capital_quality_score. What LLM model would serve as uncertainty arbiter? |
| G-006 | Backtest/Live asymmetry | Fusion OFF in backtests (F-037: `BACKTEST_ENGINE_GATE=0`) but ON live. Research conclusions from backtests may not transfer to live because the engine fusion is never exercised in research. |

---

## Certification Summary

| # | Model | Certification Status | Key Reason |
|---|---|---|---|
| 1 | CRT Engine | **CONDITIONAL** | Scoring adapter formula inverted vs engine; core state machine correct |
| 2 | Gaussian (heuristic) | **FLAWED** | Symmetric kernel documented as directional; intent mismatch |
| 3 | BitNet | **DORMANT** | Disabled by default; degrades book when on (F-055) |
| 4 | ZoneGate | **REDUNDANT** | ΔG001≡0; non-pivotal; 6/8 zones negative mean RR |
| 5 | RR Engine | **CERTIFIED** | Only fully certified model; mathematically sound, properly guarded |
| 6 | TradeNet | **UNWIRED** | Code complete but no production connection (F-005) |
| 7 | EnvelopeNet | **EXPERIMENTAL** | 4 unresolved design defects; PIT_UNCLEAN |
| 8 | Strategies S1-S10 | **DEPRECATED** | Sidecar; not on live spine |
| 9 | LLM Gate | **FAILED** | No LLM function injected; config claims enabled but non-functional |
| 10 | EngineRunner | **CONDITIONAL** | Correct orchestrator; perpetuates compute/evaluate path split |

**Of 10 models: 1 CERTIFIED, 2 CONDITIONAL, 1 FLAWED, 1 DORMANT, 1 REDUNDANT, 1 UNWIRED, 1 EXPERIMENTAL, 1 DEPRECATED, 1 FAILED.**

Only **RR Engine** passes all audit criteria without qualification.

The most impactful finding is the **Fusion path bifurcation (WD-1/WD-2)**: two scoring paths, only one active in production, the other containing dead neural/LLM slots that the config misleadingly suggests are functional. This should be resolved before any new model integration work begins.