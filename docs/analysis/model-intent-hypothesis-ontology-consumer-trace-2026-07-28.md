# Model Intent → Hypothesis → Ontology → Implementation → Output → Consumer

**Date:** 2026-07-28  
**Branch-scoped runtime:** `ACTIVE_VERSION=v2_multi_2026_04`  
**Authority:** architecture / research documentation only — no promote, no ΔG001  
**Sources:** `active_models.yaml`, engine sources, `feature_schema.py`, fusion/decision paths, offline runners  

**Spine philosophy (intent, not proven edge):** each live engine answers a different question about the same OHLCV bar; fusion composes scores; DecisionEngine / Planner / Ultron consume further downstream. Evidence: entry-information nulls (F-019…) mean these remain *hypotheses*, not validated economic authorities.

```text
OHLCV → FeaturePipeline (39 CANONICAL) ─┬→ crt_score / gaussian / zone / rr  → FusionEngine.compute
                                        ├→ (optional offline) gaussian_ml / tradenet / envelope / rr_trained
CRTEngine FSM (candles) ────────────────┴→ TRADE_OPENED path; BitNet only if use_bitnet
```

---

## 1. CRT — structure (two surfaces)

### 1A. Fusion CRT scorer (`crt` engine slot)

| Layer | Content |
|---|---|
| **Design intent** | Answer: *“Is the market structure valid?”* as a **rule score** over pipeline morphology at the fusion stage — not prediction. |
| **Market hypothesis** | Institutional liquidity events leave readable candle structure: sweep → displacement → retest quality can be scored from contemporaneous features; high structure-rule score ↔ better setup. |
| **Ontology evidence** | `body_ratio`, `disp_strength` (as `move`), `atr` (FM-029 rescale), `retest_depth`, `sweep_detected`, `double_sweep`, `candles_since_retest`. Weights: `crt_engine.score_component_weights` (sweep, breakout, retest, time). |
| **Implementation path** | `EngineRunner` → `engines.crt_engine.compute` → `scoring_engine.compute_scores`: sub-scores sweep / breakout / retest / time → weighted sum `s_final`. Retest uses **Gaussian peak at depth 0.5** (≠ Ultron linear depth). |
| **Output semantics** | `structure_rule_score` ∈ [0,1] (`output_semantic`). **Not** a CRT state enum; **not** economic RR. |
| **Consumer contract** | Fusion slot `crt` · weight **0.4**. `FusionEngine.compute` averages with other engines → `final_score` / `normalized_score` → DecisionEngine score / p_win path. |

### 1B. CRT state machine (`CRTEngine`)

| Layer | Content |
|---|---|
| **Design intent** | Detect institutional trajectory **RANGE → SWEEP → … → EXECUTION → RESOLUTION** (9 states) from raw OHLCV. |
| **Market hypothesis** | Edge (if any) is in **process selection** after completed structure, not in static feature→outcome maps (F-002 intent; falsified extensions in F-019…). |
| **Ontology evidence** | Raw OHLCV + range refs; at RETEST emits cached geometry (`body_ratio`, FM-027/028 aliases, etc.) — not full 39-dim fusion vector. |
| **Implementation path** | `crt_engine_v2.CRTEngine.process_candle` · RangeDetector → StateMachine → UltronRiskEngine → ExecutionEngine. |
| **Output semantics** | `state`, `action` (e.g. `TRADE_OPENED`), trade geometry — **event stream**, not a fusion float. |
| **Consumer contract** | Backtest / live CRT spine opens trades; BitNet may gate **approve**; does **not** fill `engine_results["crt"]` (that is 1A). |

---

## 2. Gaussian (live heuristic)

| Layer | Content |
|---|---|
| **Design intent** | *“Is this historically profitable?”* — designed as probability-of-success match over CRT-labelled states. |
| **Market hypothesis** | EMA alignment + momentum composite that sits near a historical “good” locus is more likely to succeed. |
| **Ontology evidence** | **Only** `ema_fast`, `ema_slow`, `momentum_score` (FM EMA / momentum lineage). Full 39-dict required by assert, rest ignored. |
| **Implementation path** | `HeuristicGaussianEngine.compute`: \(x=((ema_f-ema_s)/ema_s + \tanh(m))/2\), \(score=\exp(-(x-\mu)^2/(2\sigma^2))\). Registry rarely supplies μ/σ → defaults 0/1 (F-060). **Symmetric** about 0. |
| **Output semantics** | `ema_momentum_kernel_score` — kernel similarity to flat/zero composite, **not** calibrated p(win). |
| **Consumer contract** | Fusion slot `gaussian` · weight **0.2**. EngineRunner also feeds Gaussian score into DecisionEngine as **p_win** (semantic stretch). Active: `gaussian_impl=heuristic`. |

### 2B. Gaussian ML (offline / config-gated)

| Layer | Content |
|---|---|
| **Design intent** | Same design question with a **trained** NB over full (or resolved) feature vector. |
| **Market hypothesis** | Full morphology + context distinguishes historically winning vs losing CRT-like setups. |
| **Ontology evidence** | Artifact `feature_schema_resolved` (XAU NB: **39** live names). |
| **Implementation path** | Offline: `gaussian_ml` runner → `load_gaussian_model` → name-anchored extract → scale → `predict_expected_rr` → logistic score. **Does not read** `gaussian_impl`. Production ML only if `gaussian_impl=ml`. |
| **Output semantics** | Pseudo-probability from expected_rr logistic; research/offline unless config selects ML. |
| **Consumer contract** | Offline only by default; spine remains heuristic unless config switched + promoted. |

---

## 3. ZoneGate

| Layer | Content |
|---|---|
| **Design intent** | *“Is this feature-space neighbourhood historically good?”* |
| **Market hypothesis** | Some regions of feature space cluster past successes; near-neighbour similarity to those zones is quality. |
| **Ontology evidence** | Full **canonical vector** (39 names; zone registry feature_order). Per-zone mask zeros price-level dims; **uniform** weights (not learned). |
| **Implementation path** | `score_zone_cluster` → `BitNetZoneGate.check` → top-k cluster score → pass vs `zone_cluster_threshold`. Mode `hard` on active config. |
| **Output semantics** | `neighbourhood_quality_score` ∈ [0,1] + `passed` / `best_zone_id`. Geometric; labels unread at runtime. |
| **Consumer contract** | Fusion slot `zone_gate` · weight **0.2**. DecisionEngine can reject `zone_gate_invalid` if not valid (and engine not “dead”). **F-036:** ΔG001≡0 non-pivotal on gate-ON fusion. |

---

## 4. RR (live polarity) and RR-trained (off-spine)

### 4A. Live RREngine

| Layer | Content |
|---|---|
| **Design intent** | *“Is reward-risk economically viable?”* (historical name). |
| **Market hypothesis** | Directionally **committed** candles (close at extreme) support CRT-style entries better than dojis. |
| **Ontology evidence** | `high`, `low`, `close` only (primitive OHLC). |
| **Implementation path** | `polarity = max((high-close)/range, (close-low)/range)` → domain {0} ∪ [0.5, 1]. |
| **Output semantics** | `candle_structure_quality` / candle polarity — **not** forward economic RR (that is Ultron after planner). |
| **Consumer contract** | Fusion slot `rr` · weight **0.2**. DecisionEngine no longer gates economic RR (F-048). |

### 4B. rr_trained (NanoInference / rr_model.json)

| Layer | Content |
|---|---|
| **Design intent** | Learned expected RR / win from multi-feature patterns (rr_fusion era). |
| **Market hypothesis** | Morphology predicts forward R; Mahalanobis confidence gates use of prediction. |
| **Ontology evidence** | 38-dim schema-v3 map from live 39 (macd_hist_z→macd_hist, candle_range→wick_size). |
| **Implementation path** | Offline `rr_trained`; production `rr_fusion.enabled=false` (F-038/F-044). |
| **Output semantics** | Raw expected_rr / p_win / confidence — gate mis-scaled historically. |
| **Consumer contract** | **Not** on spine; offline observe only. |

---

## 5. BitNet

| Layer | Content |
|---|---|
| **Design intent** | *“Is this market state acceptable?”* Hard reject if confidence &lt; threshold (0.55). |
| **Market hypothesis** | A compact 6-feature state embedding separates acceptable vs toxic RETEST/approval states. |
| **Ontology evidence** | Legacy6: `body_ratio`, `retest_depth`, `disp_strength`, `atr`, `candles_since_retest`, `double_sweep` (+ FM-027/028 aliases when present). |
| **Implementation path** | `bitnet_score` / composition → confidence. Wired only inside `UltronRiskEngine.approve*` when `use_bitnet=true`. |
| **Output semantics** | `state_acceptability_score` ∈ [0,1]. Veto can reset CRT FSM (F-055). |
| **Consumer contract** | **Not** a fusion engine_key. Active: `use_bitnet=false` → **inert**. Offline runner observes without enabling. |

---

## 6. TradeNet

| Layer | Content |
|---|---|
| **Design intent** | *“What is the capital quality of this setup?”* — milestone survival probabilities. |
| **Market hypothesis** | Canonical morphology predicts p(TP1), p(TP2), p(survive 1R BE). |
| **Ontology evidence** | Full live **39** vector (post-retrain XAU envelope); older ETH active pointer 35-dim / unwired. |
| **Implementation path** | MLP 39→32→16 → 3 sigmoids; composite 0.4/0.4/0.2. Would inject as `FusionEngine.neural_fn` on **evaluate()** path only. |
| **Output semantics** | `capital_quality_score` / heads — **not** continuous envelope bounds (Envelope’s job). |
| **Consumer contract** | **UNWIRED (F-005)**; no neural_fn on EngineRunner. Offline with `--artifact`. No TN_QUAL → no authority. |

---

## 7. EnvelopeNet

| Layer | Content |
|---|---|
| **Design intent** | *“What price–time operating envelope does this trade live in after entry?”* Boundaries, not win/lose. |
| **Market hypothesis** | Post-entry path has predictable MFE/MAE heat / holding / time-to-MFE from entry features. |
| **Ontology evidence** | **38-dim** LEGACY names (drop `macd_hist_raw`); clean-label protocol TN_ENV_CLEAN_L2. |
| **Implementation path** | Offline HistGradientBoosting heads; XAU bundle `results/envelope_offline/XAUUSD/…`. Point estimates only (no quantiles → bands not constructible per design). |
| **Output semantics** | `post_entry_envelope_bounds` as point heads: `mfe_r`, `mae_r_heat`, `holding_bars`, `time_to_mfe`. |
| **Consumer contract** | **No spine class**; weight-0 shadow design. Offline runner only. |

---

## 8. Fusion compose (not a “model”, but the consumer hub)

| Layer | Content |
|---|---|
| **Design intent** | Combine independent hypotheses into one actionable score. |
| **Market hypothesis** | Orthogonal signals improve selection when weighted. |
| **Ontology evidence** | Indirect — consumes four engine scores only. |
| **Implementation path** | `FusionEngine.compute`: weights crt 0.4 / gaussian 0.2 / zone 0.2 / rr 0.2 + normalizer. `evaluate()` (Gaussian→Neural→LLM) **unused** (`fusion_use_evaluate=false`). |
| **Output semantics** | `final_score`, `normalized_score`, per-engine breakdown. |
| **Consumer contract** | → DecisionEngine (score / p_win / zone validity) → ExecutionPlanner → UltronRiskGate (true **economic** min RR). |

---

## 9. Intentionally non-models (blocked on offline scoreboard)

| Id | Intent | Why not a score model here |
|---|---|---|
| **LLM gate** | Uncertainty arbiter in evaluate() band | No `llm_fn` injected; evaluate path dead |
| **Strategies S1–S10** | Sidecar consensus | Not on live spine |
| **EngineRunner** | Orchestrator | Use backtest, not single-model isolate |

---

## 10. Cross-model consumer map (active patch)

```text
                    ┌─ CRT FSM ──(use_bitnet?)──► UltronRiskEngine.approve
OHLCV ──► features ─┤
                    └─ EngineRunner ──► crt_score ×0.4
                                      gaussian ×0.2  ──► Fusion.compute ──► DecisionEngine
                                      zone_gate ×0.2                         │
                                      rr ×0.2                                ▼
                                                                   ExecutionPlanner
                                                                         │
                                                                         ▼
                                                                  UltronRiskGate (min_rr)

Offline only: gaussian_ml, tradenet, envelope, rr_trained, bitnet(observe)
```

| Consumer | What it believes the number means | What it actually is (often) |
|---|---|---|
| Fusion weights | Additive evidence of “good setup” | Four heterogeneous [0,1] scores |
| DecisionEngine `p_win` | Probability of win | Often **Gaussian kernel score** |
| DecisionEngine zone | Zone validity | Geometric neighbourhood, non-pivotal (F-036) |
| Ultron `min_rr` | Economic reward:risk | Planner SL/TP — **not** RREngine polarity |
| BitNet (if on) | Acceptability | 6-feat gate; can reset FSM |

---

## 11. Ontology ownership (short)

| Feature family | Primary intent owner | Also consumed by |
|---|---|---|
| OHLC extremes | RR polarity | CRT geometry, pipeline |
| body_ratio / disp / retest / sweep | CRT structure + BitNet | Zone full vector |
| ema_fast/slow, momentum | Gaussian heuristic | Zone full vector |
| Full 39 vector | ZoneGate, TradeNet, gaussian_ml | — |
| Legacy 38 (no macd_hist_raw) | Envelope | clean_labels |
| Legacy6 | BitNet | CRT cache aliases |

Full lineage: `active_models.yaml` `feature_lineage` + `docs/topics/model-intent-and-feature-ownership.md`.

---

## 12. Authority footer

- **Intent ≠ edge.** Philosophy block cites F-019…F-040 nulls.  
- **Tunability ≠ authority** (§6.5).  
- Offline runs grant **no** production wire-up.  
- Trace is descriptive; code + ACTIVE_VERSION win on conflict.
