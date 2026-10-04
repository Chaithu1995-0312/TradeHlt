# RRPatternMiner — Implementation Intent Audit (code-grounded)

**Date:** 2026-07-28  
**Authority:** architecture / research — no promote  
**Active config:** `configs/production/v2_multi_2026_04.json`  

---

## 0. Naming fact (confirmed from code)

There is **no class named `RRPatternMiner`**.

The subsystem lives in:

| Symbol | Kind | File |
|---|---|---|
| module docstring “Feature -> RR Pattern Miner trainer and pure-Python inference” | module | `src/config_layer/rr/rr_pattern_miner.py` |
| `RRPatternTrainer` | offline trainer | same file `:172` |
| `NanoInferenceEngine` | pure-Python inference | same file `:385` |
| `FeatureDimensionError` | exception | same file `:26` |
| `train_and_save` | convenience | same file `:528` |
| `RRFusionLayer` | runtime wrapper | `src/config_layer/rr/rr_fusion.py` |
| `RREngine` | **different** live fusion slot | `src/engines/rr_engine.py` (candle polarity — not Pattern Miner) |

CLI trainer: `scripts/training/train_rr_model.py` imports `RRPatternTrainer`.  
Dataset builder: `src/config_layer/rr/rr_dataset_builder.py`.

**In the rest of this audit, “RRPatternMiner” means the `rr_pattern_miner.py` subsystem (`RRPatternTrainer` + `NanoInferenceEngine`), not `RREngine`.**

---

## 1. Design intent

### 1.1 Market question (from code + config semantics)

**What the implementation actually answers:**

Given a **feature vector** of width equal to the trained model’s `n_features`, and given contemporaneous **Gaussian scores** (`gaussian_score`, `gaussian_p_win`):

1. How far is this feature vector from the **training distribution** (Mahalanobis \(d^2\))?
2. If “close enough” (confidence gate does **not** bypass): what **Ridge-regressed expected RR** and **GaussianNB P(win)** does the model predict?
3. What **blended final score** results from  
   \(0.5 \cdot \text{gaussian} + 0.3 \cdot \text{ml\_score} + 0.2 \cdot \text{confidence}\)  
   (`rr_model.score_weights` in production JSON)?

**Source:** `NanoInferenceEngine.predict` (`rr_pattern_miner.py:437–525`).

The **historical design name** (“pattern miner”) and Fusion philosophy (“is reward-risk economically viable?”) suggest similarity retrieval over past trades. **That algorithm is not implemented.** There is no neighbour search over a trade store at inference time.

### 1.2 Why it exists instead of another ML model

**Confirmed from code structure:**

- Offline training needs sklearn (`Ridge`, `LedoitWolf`, custom GNB params) → `RRPatternTrainer.train` (`:184–288`).
- Online path is **pure Python**, no sklearn/numpy at `predict` time → `NanoInferenceEngine` (`:385–525`).
- Designed as an **enhancement layer on top of the Gaussian score**, not a replacement of CRT / full TradeNet:
  - takes `gaussian_score` / `gaussian_p_win` as inputs;
  - can **bypass entirely** to Gaussian (`status: bypassed_low_confidence`);
  - can **cap** final_score to Gaussian when Gaussian is below threshold (`status: capped_by_threshold`).

**Architectural inference (not a code comment asserting “why vs TradeNet”):** multi-head TradeNet (`trade_net_v2`) is a separate capital-quality surface; RR Pattern Miner is a ridge+GNB+Mahalanobis stack specialized for RR/win labels and Gaussian fusion.

---

## 2. Runtime entry points

### 2.1 Source files

| Path | Role |
|---|---|
| `src/config_layer/rr/rr_pattern_miner.py` | Train + infer core |
| `src/config_layer/rr/rr_fusion.py` | Production wrapper around `NanoInferenceEngine` |
| `src/config_layer/rr/rr_dataset_builder.py` | Build/save/load training matrix |
| `scripts/training/train_rr_model.py` | CLI train + registry |
| `scripts/data/build_rr_dataset.py` | CLI dataset build |
| `src/core/engine_runner.py` | Constructs `RRFusionLayer` if enabled; applies after `RREngine` |
| `src/engines/live_engine.py:914` | Imports `get_fusion_layer` (secondary live path) |
| `models/rr_model.json` | Trained state_dict (currently 38-dim, quarantined vs schema 4.0) |
| `models/rr_dataset.json` / versioned datasets | Training corpus files |
| `models/rr_registry.json` | Version registry (via `core.model_registry`) |

### 2.2 Main classes / functions

```text
RRPatternTrainer.__init__(ridge_alpha, gnb_var_smoothing)
RRPatternTrainer.train(X, y_rr, y_win) -> state dict
RRPatternTrainer.save(path)
RRPatternTrainer.loocv_report(X, y_rr, y_win)

NanoInferenceEngine.__init__(state_dict)
NanoInferenceEngine.load(path) -> engine
NanoInferenceEngine.predict(features, gaussian_score, gaussian_p_win, threshold) -> dict

train_and_save(X, y_rr, y_win, path, ridge_alpha)

RRFusionLayer.__init__(model_path, threshold, enabled)
RRFusionLayer.score(trade, threshold) -> dict   # full canonical features
RRFusionLayer.score_dict(depth, body, disp, gaussian_*, sessions, hour, threshold)
```

### 2.3 Call graph into RRPatternMiner (Decision / Fusion)

**Confirmed: DecisionEngine and FusionEngine do NOT import or call `rr_pattern_miner` or `NanoInferenceEngine`.**

Actual path when `engine_runner.rr_fusion.enabled=true` **and** model loads:

```text
EngineRunner.__init__
  ├─ self.rr = RREngine(config)                    # candle polarity — separate
  └─ if engine_runner.rr_fusion.enabled:
       self.rr_fusion = RRFusionLayer(model_path, threshold, enabled=True)
         └─ NanoInferenceEngine.load(path)         # rr_pattern_miner

EngineRunner.run(...)
  ├─ gaussian_result = self.gaussian.compute(...)
  ├─ rr_result = self.rr.compute(...)              # polarity
  ├─ if self.rr_fusion and self.rr_fusion.is_loaded:
  │    if full_feature_vector:
  │      rr_fusion_result = self.rr_fusion.score(full_feature_dict, threshold)
  │        └─ build_feature_vector → NanoInferenceEngine.predict(...)
  │    else:
  │      rr_fusion_result = self.rr_fusion.score_dict(depth, body, disp, ...)
  │        └─ (often sparse vector of zeros except 3 features)
  │    rr_result["score"] = rr_fusion_result["final_score"]
  │    rr_result["rr_fusion"] = rr_fusion_result
  └─ engine_results = {crt, gaussian, zone_gate, rr}
       └─ FusionEngine.compute(engine_results)
            └─ uses rr_result["score"] only as a float weight_rr term
```

**Active config:** `engine_runner.rr_fusion.enabled: false`  
→ `EngineRunner` never constructs a loaded fusion layer that mutates RR; base `RREngine.compute` score enters fusion.

**Active artifact:** `models/rr_model.json` has `n_features: 38`  
→ Even if `enabled:true`, `RRFusionLayer._try_load` refuses load (`model_n != CANONICAL_FEATURE_DIM` 39) → `is_loaded=False` → passthrough.

```text
DecisionEngine.evaluate  ──X──  no reference to NanoInference / RRPatternTrainer
FusionEngine.compute     ──X──  no reference; only consumes engine_results["rr"]["score"]
```

---

## 3. Input contract

### 3.1 `NanoInferenceEngine.predict` inputs

| Parameter | Type | Meaning |
|---|---|---|
| `features` | `List[float]` length == `len(self.W)` | Scaled later inside predict; must match trained width |
| `gaussian_score` | float | Live Gaussian engine score (used in blend / bypass / cap) |
| `gaussian_p_win` | float | Passed through on bypass as `probability_of_win` |
| `threshold` | float default 0.5 | Cap rule: if gaussian &lt; threshold and final &gt; gaussian → clamp to gaussian |

**Source:** `rr_pattern_miner.py:437–443`.

### 3.2 Feature vector / schema

| Stage | Width | Authority |
|---|---|---|
| Trainer `N_FEATURES` | `CANONICAL_FEATURE_DIM` (**39** at import time) | `rr_pattern_miner.py:17–24` |
| On-disk `models/rr_model.json` | **38** (`feature_schema: canonical_38`) | artifact |
| Live spine feed | `build_feature_vector` → **39** | `feature_schema.py` |
| Load gate | refuse if `n_features != CANONICAL_FEATURE_DIM` | `rr_fusion.py:84–109` |

Optional train-time mask: `zero_indices` (e.g. price indices `[0,1,2,3,4,7,8,16,17,26,27]`) applied again at predict (`:458–465`).

### 3.3 Candidate trade fields (RRFusionLayer.score)

From trade dict or object (`rr_fusion.py:127–139, 141–188`):

- Nested `features` dict **or** top-level keys for all `CANONICAL_FEATURES`
- `gaussian_score`, `gaussian_p_win` (defaults 0.0 / 0.5 via `_get`)
- Drift check uses `retest_depth`, `body_ratio`, `disp_strength` vs `rr_model.drift_threshold`

`score_dict` path (`:207+`): builds mostly-zero canonical dict, sets only depth/body/disp — known starvation path when `full_feature_vector=false`.

### 3.4 Required configuration (import-time)

Module import calls `get_prod_section("rr_model")` and **requires** keys (`rr_pattern_miner.py:42–56`):

- `min_samples`, `model_path`, `mahal_clip`, `confidence_bypass_threshold`, `score_weights.{gaussian,ml,confidence}`

Optional nested: `confidence_gate` (defaults via `.get` to `legacy_scalar` etc. — see §9).

Trainer also reads `ridge_alpha`, `gnb_var_smoothing` from `_RR_CFG` with `.get` defaults 10.0 / 1e-9 (`:177–178`).

`rr_fusion` reads `rr_model.drift_threshold` at import (`rr_fusion.py:36`).

---

## 4. Historical corpus

### 4.1 What is searched at inference?

**Nothing is searched.**  
Inference does **not** open a trade DB, FAISS index, or neighbour list.  
The only artifact loaded is the **parameter JSON** (`models/rr_model.json` by default): Ridge weights, GNB parameters, Mahalanobis location/precision, scalers.

### 4.2 Training corpus (files)

| Artifact | Role |
|---|---|
| `models/rr_dataset.json` (config `rr_model.dataset_path`) | Default dataset path |
| `models/rr_dataset_*.json` / `models/{instrument}/{run}/rr_dataset.json` | Versioned / run-scoped |
| `models/rr_registry.json` | Active dataset/model pointers via `get_active_rr_entry` |

**Build path:**

```text
trades (+ optional OHLCV df)
  → rr_dataset_builder.build_dataset
       FeaturePipeline → extract_features (CANONICAL order)
       extract_target(trade) → y_rr, y_win
  → validate_dataset_integrity
  → save_dataset → JSON
```

**Train path:**

```text
load_dataset / legacy-38 load
  → optional zero price indices
  → RRPatternTrainer.train
  → trainer.save → models/rr_model_{version}.json
  → register_rr_model / optional promote → models/rr_model.json
```

CLI: `scripts/data/build_rr_dataset.py`, `scripts/training/train_rr_model.py`.

### 4.3 How updated

- Rebuild dataset from trade streams / opportunities via builders.  
- Retrain via `train_rr_model.py` → new versioned file + registry.  
- Promote copies/activates path used by `engine_runner.rr_fusion.model_path`.  
**No online incremental update of neighbours** (there is no neighbour store).

### 4.4 Schema of stored records

**Dataset JSON** (`save_dataset`, `rr_dataset_builder.py:330–348`):

```json
{
  "n_samples": int,
  "n_features": int,
  "feature_names": [...],
  "schema_hash": "...",
  "X": [[float, ...], ...],
  "y_rr": [float, ...],
  "y_win": [0|1, ...]
}
```

**Model JSON** (from `RRPatternTrainer.state` + optional fields from train_rr_model / quarantine):

```json
{
  "ridge_w": [n],
  "ridge_b": float,
  "gnb_C": [[n],[n]],
  "gnb_V": [[n],[n]],
  "gnb_mu": [[n],[n]],
  "conf_mu": [n],
  "conf_P": [[n][n]],
  "scale_mu": [n],
  "scale_sigma": [n],
  "n_features": int,
  "n_train": int,
  "ridge_alpha": float,
  "feature_schema": "canonical_N",
  "zero_indices": [int, ...],
  "training_distribution": { optional percentiles of d_sq },
  "schema_version" / quarantine fields (on current rr_model.json)
}
```

**Labels** (`extract_target`, `:126–207`):  
- `y_rr`: `rr_achieved` → `pnl_rr_net` → computed entry/sl/tp  
- `y_win`: outcome string / win field / sign of rr  

(F-022 risk: stream `rr_achieved` may be contaminated relative to honest forward walk.)

---

## 5. “Similarity engine”

### 5.1 Exact algorithm (confirmed)

| Component | Algorithm | Not |
|---|---|---|
| Distribution fit | Ledoit–Wolf covariance on **scaled** train matrix; precision `conf_P` | KNN, FAISS, cosine to stored trades |
| Distance | Mahalanobis \(d^2 = \delta^\top P \delta\) | Euclidean over neighbours |
| Regression | Ridge (`sklearn.linear_model.Ridge`) on scaled X → y_rr | Neighbour mean RR |
| Classification | Diagonal Gaussian NB (log-likelihood form stored as C, V, μ) for win/loss | Softmax over K neighbours |
| Confidence | \(\exp(-0.5 \cdot \min(d^2, \text{mahal\_clip}))\) | Retrieval count / agreement |

**There is no Top-K retrieval. There is no historical trade ID returned.**

### 5.2 Distance metric

- Mahalanobis with precision matrix from LedoitWolf (`train` `:245–254`).  
- Fallback: diagonal precision from variance (`:251–254`).  
- Clip: `d_sq = min(d_sq, mahal_clip)` with `mahal_clip=500` from config before confidence (`predict` `:480–482`).  
- Gate may use **unclipped** `d_sq_raw` for dof-aware modes (`:150–160`, `:480`).

### 5.3 Feature weighting

- **Ridge coefficients** `W` = learned weights on standardized features.  
- **zero_indices**: hard zero of selected dimensions at train and predict.  
- **score_weights**: blend weights among gaussian / ml / confidence, not per-feature.

### 5.4 Normalization

- Train: per-feature mean/std on X; std 0 → 1 (`train` `:212–215`).  
- Predict: same `scale_mu` / `scale_sigma` (`:466–468`).

### 5.5 Thresholds

| Name | Config key / code | Role |
|---|---|---|
| Confidence bypass | `confidence_bypass_threshold` (0.3) | legacy: if conf &lt; thr → return Gaussian |
| Gate mode | `confidence_gate.mode` | legacy_scalar / chi2_tail / dof_scaled / percentile |
| Mahalanobis clip | `mahal_clip` (500) | clip d_sq for exp confidence |
| Drift | `drift_threshold` (1.5) | RRFusionLayer: depth/body/disp &gt; thr → Gaussian passthrough |
| Cap threshold | `engine_runner.rr_fusion.threshold` (0.5) | if gaussian &lt; thr and final &gt; gaussian → clamp |
| RR score clamp | hard-coded `RR_SCORE_MIN=-3`, `RR_SCORE_MAX=5` | clamps expected_rr |

### 5.6 Top-K / filtering

- **Top-K:** none.  
- **Filtering:** confidence bypass; drift bypass; dim mismatch passthrough; disabled/not loaded passthrough.

---

## 6. Evidence aggregation

### 6.1 Neighbours

**N/A — no neighbours retrieved.**

### 6.2 How quantities are (or are not) computed

| Quantity | Implemented? | How |
|---|---|---|
| **expected_rr** | Yes | Ridge: \(\sum_i W_i X_i + b\), clamped to [-3, 5] |
| **probability_of_win** | Yes | Softmax of class log-likelihoods from stored GNB params (win vs loss) |
| **confidence** | Yes | \(\exp(-0.5 \cdot d^2_{\text{clipped}})\) |
| **ml_score** | Yes | \(\sigma(\text{expected\_rr}/3)\) |
| **final_score** | Yes | weighted blend of gaussian, ml_score, confidence |
| **MFE / MAE** | **No** | not in predict output or trainer |
| **Expectancy** | **No** as field | only via expected_rr as a proxy regression target |
| **TP probabilities** | **No** TP1/TP2 | only binary win GNB |
| **Duration / holding** | **No** | |
| **Sample size at inference** | **No** | `n_train` only in artifact metadata, not returned by predict |
| **Neighbour agreement** | **No** | |

LOOCV offline (`loocv_report`): rr_corr, brier_score, calibration buckets — **training diagnostics**, not runtime outputs.

---

## 7. Output contract

### 7.1 `NanoInferenceEngine.predict` return dict

| Field | Meaning (code) |
|---|---|
| `final_score` | Blended score, or pure `gaussian_score` on bypass/cap |
| `expected_rr` | Ridge prediction (0.0 on bypass) |
| `probability_of_win` | GNB p(win) or passthrough `gaussian_p_win` on bypass |
| `confidence` | Mahalanobis-based exp(-0.5 d_sq) |
| `status` | `success` \| `bypassed_low_confidence` \| `capped_by_threshold` |

Passthrough from `RRFusionLayer` adds statuses: `disabled`, `model_not_loaded`, `drift_detected`, `feature_dimension_mismatch`, `inference_error` with `confidence: 0.0`, `expected_rr: 0.0`.

### 7.2 Downstream consumption

| Consumer | Fields used |
|---|---|
| `EngineRunner.run` (when fusion loaded) | **`final_score` only** → overwrites `rr_result["score"]`; full dict stored under `rr_result["rr_fusion"]` |
| `FusionEngine.compute` | **`engine_results["rr"]["score"]`** (polarity or fused final_score) — does **not** read expected_rr / confidence / status |
| `DecisionEngine` | Does not read RRPatternMiner fields; may use fusion final_score / gaussian as p_win |
| UltronRiskGate | Economic RR from planner — **not** Pattern Miner expected_rr |

---

## 8. Consumer trace

### 8.1 Where Fusion “reads” RRPatternMiner

**It does not, by name.**  
Fusion only sees a single float in the `rr` engine slot after EngineRunner optionally replaces it.

```text
NanoInferenceEngine.predict
  → RRFusionLayer.score / score_dict
    → EngineRunner: rr_result["score"] = final_score
    → engine_results["rr"]
      → FusionEngine.compute → weight_rr * score
```

### 8.2 What affects the final decision (when enabled and loaded)

1. Confidence gate / drift / dim → may force `final_score = gaussian_score`.  
2. Else blend + optional cap by Gaussian threshold.  
3. That float participates in fusion average with weight_rr (0.2).  
4. Fusion score → DecisionEngine thresholds.

### 8.3 Currently ignored (even when enabled)

- `expected_rr` (not used by Decision/Ultron for sizing)  
- `probability_of_win` from GNB (except as passthrough field; Decision’s p_win typically from Gaussian)  
- `confidence` except as blend ingredient / gate input  
- `status` (logging only unless callers inspect `rr_fusion` meta)  
- Entire module when `rr_fusion.enabled=false` (**active**)  
- Entire module when model width ≠ 39 (**active artifact is 38**)

---

## 9. Configuration ownership

### 9.1 Production JSON — `rr_model` section

From `v2_multi_2026_04.json` (confirmed):

| Key | Value | Used by |
|---|---|---|
| `ridge_alpha` | 10.0 | RRPatternTrainer |
| `gnb_var_smoothing` | 1e-9 | RRPatternTrainer |
| `drift_threshold` | 1.5 | RRFusionLayer |
| `mahal_clip` | 500.0 | NanoInferenceEngine.predict |
| `confidence_bypass_threshold` | 0.3 | legacy confidence gate |
| `min_samples` | 20 | train min n |
| `dataset_min_samples` | 20 | dataset builder related |
| `score_weights.gaussian/ml/confidence` | 0.5 / 0.3 / 0.2 | final_score blend |
| `model_path` | models/rr_model.json | DEFAULT_MODEL_PATH |
| `dataset_path` | models/rr_dataset.json | tooling |
| `confidence_gate.mode` | legacy_scalar | `_confidence_bypass` |
| `confidence_gate.p_threshold` | 0.01 | chi2_tail |
| `confidence_gate.dof_scaled_max` | 3.0 | dof_scaled |

### 9.2 Production JSON — `engine_runner.rr_fusion`

| Key | Value | Role |
|---|---|---|
| `enabled` | **false** | Master switch — Pattern Miner off on spine |
| `model_path` | models/rr_model.json | Load path |
| `threshold` | 0.5 | Cap threshold in predict |
| `full_feature_vector` | false | score vs score_dict path |

### 9.3 Hard-coded in code

| Constant | Location | Value |
|---|---|---|
| `RR_SCORE_MIN` / `RR_SCORE_MAX` | rr_pattern_miner.py:46–47 | -3.0 / 5.0 |
| ml_score formula | predict:511 | sigmoid(expected_rr / 3.0) |
| GNB classes | train:225 | {0,1} loss/win |
| LedoitWolf fallback | train:251–254 | diagonal precision |
| Price zero indices list | train_rr_model.py:50 | [0,1,2,3,4,7,8,16,17,26,27] (only if CLI flag) |
| `N_FEATURES` at train time | CANONICAL_FEATURE_DIM | live schema width |

### 9.4 Soft defaults still present (code)

- `confidence_gate` missing → `{}` then mode `legacy_scalar` (`:77–78`)  
- `ridge_alpha` / `gnb_var_smoothing` via `_RR_CFG.get(..., default)` on trainer  
- RRFusionLayer `_get` defaults for gaussian fields  
These are **code facts**, not production-JSON guarantees.

---

## 10. Intent validation chain

```text
Intent (name): “mine RR patterns from history for economic viability”
        │
        ▼
Market hypothesis (implemented): feature vector near train dist + ridge RR + NB win
        improves on Gaussian score when confidence high
        │
        ▼
Ontology evidence: full (or zero-masked) canonical feature vector at entry
        labels y_rr, y_win from trade outcomes
        │
        ▼
“Similarity”: Mahalanobis to training cloud (NOT trade KNN)
        │
        ▼
Historical evidence: frozen parameters from training JSON
        (not live neighbour outcomes)
        │
        ▼
Aggregation: ridge + GNB + confidence blend with Gaussian
        │
        ▼
Output: final_score, expected_rr, probability_of_win, confidence, status
        │
        ▼
Fusion consumer: ONLY final_score → rr slot → weight_rr
        │
        ▼
Active patch: ENABLED=false and/or model 38≠39 → chain broken; RREngine polarity used instead
```

---

## 11. Semantic gaps (design vs implementation vs usage)

| Topic | Original / implied design | Implementation | Downstream usage (active) |
|---|---|---|---|
| Name “Pattern Miner” | Retrieve similar historical setups | Parametric model; no retrieval | N/A on spine |
| Economic RR | Predict viable RR | Ridge on labels (F-022 contamination risk) | Ultron uses planner RR, not this |
| Similarity | KNN/FAISS over trades | Mahalanobis to train mean | Unused when disabled |
| Confidence | Retrieval support | exp(-0.5 d²); F-044: legacy gate → ~100% bypass | N/A when disabled |
| Fusion RR slot | Pattern Miner score | **RREngine candle polarity** when fusion off | Fusion weight_rr = polarity |
| Decision p_win | Could use probability_of_win | Uses Gaussian kernel as p_win | GNB p_win ignored |
| Live dim | Match train | Artifact 38 vs live 39 → load refuse | Dead even if enabled without retrain |

---

## 12. Authority matrix

| Claim | Authority |
|---|---|
| No class `RRPatternMiner`; trainer + NanoInferenceEngine in `rr_pattern_miner.py` | **Code** |
| No KNN/FAISS/cosine neighbour search | **Code** |
| Mahalanobis + Ridge + GNB + Gaussian blend | **Code** |
| Call path EngineRunner → RRFusionLayer → NanoInferenceEngine | **Code** |
| DecisionEngine / FusionEngine do not import rr_pattern_miner | **Code** |
| Only `final_score` mutates fusion `rr` score | **Code** |
| `rr_fusion.enabled: false` on active config | **Configuration** |
| Model `n_features: 38`, live dim 39, load refuse | **Code + artifact** |
| F-038 / F-044 mechanism (bypass / gate mis-scale) | **Code + findings** (aligned) |
| Why “instead of TradeNet” product rationale | **Architectural inference** |
| Intent as true economic RR gate | **Not implemented** as Ultron/Decision consumer |
| MFE/MAE/duration/Top-K aggregation | **Not implemented** |
| Online corpus update / DB search | **Not implemented** |

---

## Appendix A — predict arithmetic (verbatim structure)

```text
features[i] zeroed if i in zero_indices
X[i] = (features[i] - scale_mu[i]) / scale_sigma[i]
delta = X - conf_mu
d_sq = delta^T conf_P delta
d_sq_raw = d_sq
d_sq = min(d_sq, mahal_clip)
confidence = clip(exp(-0.5 * d_sq), 0, 1)
if confidence_bypass(d_sq_raw, dof, confidence):
    return {final_score: gaussian_score, expected_rr: 0, probability_of_win: gaussian_p_win,
            confidence, status: bypassed_low_confidence}
expected_rr = clip(W·X + b, -3, 5)
p_win = softmax GNB(win vs loss)
ml_score = sigmoid(expected_rr / 3)
final_score = 0.5*gaussian + 0.3*ml_score + 0.2*confidence
if gaussian < threshold and final_score > gaussian:
    final_score = gaussian; status = capped_by_threshold
else status = success
```

## Appendix B — train arithmetic (verbatim structure)

```text
require n >= min_samples, X.shape[1] == N_FEATURES (live CANONICAL_FEATURE_DIM)
scale_mu, scale_std; Xs = (X - mu) / std
Ridge(alpha).fit(Xs, y_rr) → ridge_w, ridge_b
For class in {0,1}: GNB prior, mu, var → C, V, mu lists
LedoitWolf.fit(Xs) → conf_mu, conf_P (or diagonal fallback)
optional training_distribution d_sq percentiles
save JSON state_dict
```

---

**End of audit.**  
Primary source files: `src/config_layer/rr/rr_pattern_miner.py`, `rr_fusion.py`, `rr_dataset_builder.py`, `src/core/engine_runner.py`, `configs/production/v2_multi_2026_04.json`, `models/rr_model.json`.
