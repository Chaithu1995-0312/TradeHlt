# TradeNet Audit Report
**Date:** 2026-07-26
**Scope:** Source-based audit of all TradeNet-related implementations
**Precedent:** CRT_AUDIT_REPORT.md, GAUSSIAN_AUDIT_REPORT.md, ZONEGATE_AUDIT_REPORT.md (same methodology)

---

## Architecture Overview

TradeNet is the **neural** engine in the FusionEngine's 3-layer evaluate() stack (Gaussian → Neural → LLM). It answers the question "what is the probability that this trade will succeed, defined as reaching TP1, TP2, or at minimum surviving to breakeven?"

There are **two generations** of TradeNet implementation:

| Layer | File | Role | Execution Authority |
|---|---|---|---|
| **v2 inference (numpy)** | `src/training/trade_net_v2.py` (450 lines) | 3-head survival classifier, pure-numpy forward pass, legacy `.pth` bridge | **PRIMARY** — code complete |
| **v2 training (PyTorch)** | `scripts/training/train_trade_net_v2.py` (569 lines) | PyTorch training, envelope export, registry promotion | **PRIMARY** — code complete |
| **TradeNetRegistry** | `src/core/model_registry.py` TradeNetRegistry class (:1114-1331) + module-level fns (:1459-1498) | Per-instrument active pointer, register/promote/rollback, regression guard | **PRIMARY** — code complete |
| **v1 legacy (.pth)** | `src/training/trainer.py` (various) | Single-sigmoid binary win/loss classifier | **LEGACY** — no `.pth` on disk |
| **FusionEngine neural slot** | `src/core/fusion_engine.py:587-610` | `neural` callable slot in evaluate() | **UNWIRED** — F-005 |

**Critical architectural finding:** TradeNet v2 is **code complete but UNWIRED (F-005)**. The FusionEngine's `evaluate()` method has a `self.neural` callable slot (lines 588-610) with `neural_weight=0.4` in FusionConfig. However, the production path via `EngineRunner` uses `FusionEngine.compute()` — a SEPARATE method that aggregates 4 engines (CRT/Gaussian/ZoneGate/RR) WITHOUT a TradeNet/neural slot. TradeNet only enters the pipeline through `evaluate()`, which is the multi-layer scoring path, not the production engine-runner path.

---

## 1. Input Contract Verification

### 1A. v2 Inference Path

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `TradeNetV2.predict(features)` | 38-dim canonical feature dict | `{"tradenet_score": float [0,1], "p_tp1": float, "p_tp2": float, "p_survives_be": float, "schema_version": str}` | ✅ |
| `make_neural_fn_v2(instrument)` | Instrument string | `Callable[[dict], float]` (composite via closure) | ✅ |
| Registry resolution | `TradeNetRegistry.__active__[instrument]` | `model_file` path → JSON envelope or `.pth` | ✅ |

**Key observations:**
- The input is the **38-dim legacy canonical vector** (explicitly excludes `macd_hist_raw`). The training script strips `macd_hist_raw` at line 187 via `MACD_HIST_RAW_IDX`.
- Feature extraction uses `extract_feature_vector()` from `dataset_builder.py` — name-anchored via CANONICAL_FEATURES list.
- The v2 envelope embeds `feature_names` and `feature_order_hash` for schema alignment.
- No CRT-specific state, no OHLCV raw prices, no strategy one-hot flags (deferred from v2 spec).

### 1B. Inputs consumed vs not consumed

| Consumed | Not Consumed |
|---|---|
| 38 canonical features (excluding macd_hist_raw) | CRT state (RANGE/SWEEP/DISPLACEMENT/...) |
| StandardScaler (mean/std from training) | Gaussian score or RR estimate |
| Registry `__active__` pointer per instrument | Strategy flags (one-hot, deferred) |
| JSON envelope weights (numpy) or .pth state_dict | Zone gate score or cluster info |
| | Raw OHLCV prices |
| | Feature order beyond 38-legacy set |

**Verdict: Input contract is correct.** TradeNet consumes the 38-dim legacy vector with proper exclusion of macd_hist_raw. The envelope includes `feature_order_hash` for integrity verification. No unintended feature consumption.

---

## 2. Probability Model — What TradeNet Estimates

### 2A. The 3-Head Architecture

```
Input: 38-dim canonical feature vector
    ↓
Trunk: Linear(38, 32) → ReLU → Dropout(0.2) → Linear(32, 16) → ReLU
    ↓
Heads (3 independent sigmoids):
    p_tp1         = P(trade reaches TP1 target)
    p_tp2         = P(trade reaches TP2 target)
    p_survives_be = P(trade reaches ≥1R MFE, breakeven-survival proxy)
    ↓
Composite = 0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be
```

| Property | Value | Assessment |
|---|---|---|
| Output type | 3 independent Bernoulli via sigmoid | ⚠️ NOT a categorical softmax — heads are independent |
| Composite formula | `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be` | Hand-specified, not learned |
| Calibration | None — raw sigmoid outputs | ⚠️ No Platt scaling, isotonic regression, or temperature scaling |
| Label source | Exit reason (TP1/TP2/SL) + MFE field | ⚠️ relabeled from original binary labels |

**Finding 1 (INFORMATIONAL):** The three sigmoid heads are NOT constrained to sum to 1.0. A trade could simultaneously have p_tp2=0.9 and p_survives_be=0.1 (reaches TP2 but not breakeven? — a logical contradiction). The heads are trained independently with separate BCE losses and separate `pos_weight` class-balance terms. The composite is a hand-specified weighted average, not a probability mixture.

### 2B. Label Construction

```python
reaches_tp1   = 1 if exit_reason in ("TP1", "TP2", "TP1_HIT", "TP2_HIT") else 0
reaches_tp2   = 1 if exit_reason in ("TP2", "TP2_HIT") else 0
survives_be   = 1 if (one_r > 0 and mfe >= one_r) else 0   # MFE proxy
```

| Label | Source | Notes |
|---|---|---|
| reaches_tp1 | exit_reason string | Covers backtest and opportunity-scanner variants |
| reaches_tp2 | exit_reason string | Subset of TP1 outcomes |
| survives_be | MFE field (price units) | MFE >= 1R where 1R = abs(entry - sl) |
| survives_be (fallback) | 0 when mfe field missing | Emits TRADENET_SURVIVES_BE_UNRESOLVED (INFO) |

**Finding 2 (INFORMATIONAL):** The `survives_be` label uses MFE as a proxy — if the trade's maximum favorable excursion reached 1R, it's labeled as having "survived to breakeven." This is a defensible derivable label but differs from a true SL-BE outcome (which the `tradenet.txt` spec notes does not exist as an exit_reason in the codebase). TP1-hit trades will typically have survives_be=1 (since TP1 >= 1R by design), creating label correlation between heads.

### 2C. Training Loss

```python
loss = weighted_bce(p_tp1, y[:,0], pos_weight[0])
     + weighted_bce(p_tp2, y[:,1], pos_weight[1])
     + weighted_bce(p_be,   y[:,2], pos_weight[2])
```

**Finding 3 (INFORMATIONAL):** The per-head `pos_weight` is computed as `max(1.0, n_neg / n_pos)`. This means:
- For very rare events (TP2), the positive class is heavily upweighted
- For common events (non-TP2), weight stays at 1.0
- The three BCE terms are sum-combined without per-head scaling — each head contributes equally to the gradient regardless of its pos_weight

---

## 3. Output Contract Verification

### Current Outputs

| Method | Output | Status |
|---|---|---|
| `TradeNetV2.predict()` | `{"tradenet_score": float, "p_tp1": float, "p_tp2": float, "p_survives_be": float, "schema_version": str}` | ✅ |
| `make_neural_fn_v2()` | `Callable[[dict], float]` returning composite score | ✅ |
| Legacy `.pth` bridge | `{"tradenet_score": float, "p_tp1": None, "p_tp2": None, "p_survives_be": None, "schema_version": "legacy_v1"}` | ✅ |
| Missing model | `None` (FusionEngine renormalizes) | ✅ |

### How FusionEngine Consumes It

TradeNet enters FusionEngine through the **`evaluate()` path only**, not `compute()`:

| Path | Uses TradeNet? | Production Active? |
|---|---|---|
| `FusionEngine.evaluate()` (3-layer: Gaussian → Neural → LLM) | ✅ Yes, via `self.neural` callable | ❌ Not used by EngineRunner |
| `FusionEngine.compute()` (4-engine: CRT/Gaussian/ZoneGate/RR) | ❌ No TradeNet slot | ✅ Production path via EngineRunner |

**Finding 4 (CRITICAL — F-005 UNWIRED):** TradeNet is architecturally complete but **not connected to the production pipeline**. The `EngineRunner` calls `FusionEngine.compute()`, which aggregates CRT/Gaussian/ZoneGate/RR without a neural/TradeNet slot. The `evaluate()` method — which DOES have a neural slot with `neural_weight=0.4` — is NOT called by EngineRunner. The registry explicitly documents this: "TradeNet is UNWIRED (F-005)."

The `make_neural_fn_v2()` wrapper exists and returns a correct `Callable[[dict], float]`, but nothing in the production path instantiates or injects it.

---

## 4. Ownership Boundaries

| Boundary | Code Evidence | Status |
|---|---|---|
| TradeNet should **not** classify market structure | CRT owns StateMachine; TradeNet consumes only canonical features | ✅ |
| TradeNet should **not** estimate profit magnitude | Produces hit probabilities (p_tp1/p_tp2/p_be), not RR values | ✅ |
| TradeNet should **not** produce trade decisions | Composite enters FusionEngine as neural weight; DecisionEngine applies threshold | ✅ |
| TradeNet should **not** redefine OHLCV | Uses canonical features only; no raw price reinterpretation | ✅ |
| TradeNet should **not** duplicate Gaussian's role | Gaussian scores feature "normality"; TradeNet scores trade outcome probability | ✅ |
| TradeNet should **not** know about CRT state names | No import from crt_engine_v2.py or state_identity.py | ✅ |
| TradeNet should **not** modify FusionEngine compute() | The spec explicitly says "no fusion_engine.py change required" — and indeed none was made | ✅ |

**Verdict: Ownership boundaries are correct.** TradeNet stays strictly within its documented role as a trade-outcome probability estimator. Its connection to FusionEngine is through the `evaluate()` neural slot, which is architecturally correct but currently unwired.

---

## 5. Causal Correctness

| Check | Evidence | Status |
|---|---|---|
| Temporal accumulation | Stateless per-call computation — `TradeNetV2.predict()` scores each vector independently | ✅ |
| Future data in features | Consumes pipeline features at current bar | ✅ |
| Lookahead in model loading | Registry loaded at init (static artifact); envelope weights are fixed | ✅ |
| Online retraining | None — model is static | ✅ |
| Feature extraction | Name-anchored via `extract_feature_vector()` | ✅ |
| Label construction | Uses historical outcomes + MFE from opportunity records | ✅ |
| Missing-MFE fallback | Labels survives_be=0 with integrity event | ✅ |

**Verdict: No causal leakage detected.** All scoring consumes current-bar features. The model is a static artifact trained on historical outcomes. Feature extraction is name-anchored.

---

## 6. Production Authority — Implementation Identification

### Implementation Inventory

| Component | Status |
|---|---|
| `src/training/trade_net_v2.py` (TradeNetV2 class + make_neural_fn_v2) | **AUTHORITATIVE** — v2 inference |
| `scripts/training/train_trade_net_v2.py` (training + envelope export) | **AUTHORITATIVE** — v2 training |
| `src/core/model_registry.py` TradeNetRegistry + module-level fns | **AUTHORITATIVE** — registry |
| `src/core/fusion_engine.py` neural slot (:587-610) | **DORMANT** — exists but unwired |
| `src/training/trainer.py` `_build_model()` / `make_neural_fn()` | **LEGACY** — v1 `.pth` path |

### Registry State (from `models/tradenet_registry.json`)

| Version | Instrument | Type | Active? | Metrics |
|---|---|---|---|---|
| `v5_tradenet_2026_05_eur` | (none) | v1 `.pth` | ❌ | accuracy=0.710, composite=0.443 |
| `v6_2026_05_btc` | (none) | v1 `.pth` | ❌ | accuracy=0.710, composite=0.443 |
| `v6_2026_05_eur` | EURUSD | v1 `.pth` | ❌ | accuracy=0.698, composite=0.496 |
| `v5_auto_2026_06_eth` | ETHUSDT | v1 `.pth` | ✅ **ACTIVE** | accuracy=0.625, composite=0.458 |
| `v2_xauusd_20260723T084643` | XAUUSD | v2 JSON envelope | ❌ | auc_p_tp1=0.500 (random), pos_rate_p_tp1=0.0 (zero TP1 hits), auc_p_survives_be=0.644 |

**Finding 5 (CRITICAL — F-005 continuation):** The production registry state reveals:
1. The only **active** model is `v5_auto_2026_06_eth` for ETHUSDT — a **legacy v1 `.pth` file that does not exist on disk** (registry note confirms ".pth is absent from the repo").
2. The only **v2 envelope** ever trained (`v2_xauusd_20260723T084643`) has **degenerate metrics**: `auc_p_tp1=0.5` (random), `pos_rate_p_tp1=0.0` (zero TP1 events in training data). It was trained but NOT promoted (`active: false`).
3. The registry contains the critical note: "TradeNet is UNWIRED (F-005) and its .pth is absent from the repo; wire-up is gated behind TN_QUAL_V1."

### Production Wire-Up Status

| Check | Status |
|---|---|
| v2 inference code exists | ✅ `trade_net_v2.py` complete |
| v2 training code exists | ✅ `train_trade_net_v2.py` complete |
| Registry functions exist | ✅ TradeNetRegistry + module-level wrappers |
| Any model file on disk? | ❌ v1 `.pth` files absent; v2 XAUUSD envelope has degenerate metrics |
| FusionEngine neural slot wired? | ❌ `evaluate()` exists with neural slot but NOT used by EngineRunner |
| v2 envelope promoted for any instrument? | ❌ Only XAUUSD v2 trained — `active: false` |

**Finding 6 (AUTHORITATIVE):** TradeNet is **code-complete but operationally inert**. The entire pipeline — inference class, training script, registry, promotion guards — is built and tested. However:
- No trained model with non-degenerate metrics exists in the registry
- The production wire-up (connecting `make_neural_fn_v2` to `FusionEngine.evaluate()` neural slot in `EngineRunner`) has NOT been performed
- The registry documents the gate: `TN_QUAL_V1` must be satisfied before wire-up

---

## 7. Detailed Findings

### Finding 1 (INFORMATIONAL) — Independent Heads, Not a Categorical Distribution
- **Severity:** INFORMATIONAL
- **Location:** `trade_net_v2.py:357-361`, `train_trade_net_v2.py:288-294`
- **Impact:** The three sigmoid heads are independent — they do NOT sum to 1.0. The composite is a hand-specified weighted average (0.4/0.4/0.2), not a learned ensemble. A trade could logically have p_tp2 > p_tp1 (higher probability of reaching TP2 than TP1) if the network assigns it so.
- **Recommendation:** Document that the heads are independent Bernoulli, not a categorical or hierarchical distribution. For production use, consider whether a hierarchical structure (p_tp2 <= p_tp1 as a constraint) would better reflect the sequential nature of TP targets.

### Finding 2 (INFORMATIONAL) — Survives-BE Label Correlation
- **Severity:** LOW
- **Location:** `train_trade_net_v2.py:145-167`
- **Impact:** TP1-hit trades typically have `survives_be=1` since TP1 ≥ 1R by design. This creates label correlation between `reaches_tp1` and `survives_be`. The independent BCE losses will partially learn redundant signals for these two heads.
- **Recommendation:** Consider whether the survives_be label should use a different threshold (e.g., MFE >= 0.5R) to reduce correlation, or accept the correlation as architecturally inherent (breakeven survival IS a prerequisite for TP1).

### Finding 3 (INFORMATIONAL) — Equal Head Weighting in Loss
- **Severity:** LOW
- **Location:** `train_trade_net_v2.py:290-296`
- **Impact:** The three BCE losses are summed directly — each head contributes equally to the gradient regardless of class balance or pos_weight. For extreme imbalance (e.g., p_tp2 with <1% positive rate), the pos_weight upweights the positive class within that head, but the head's contribution to the total gradient is the same as p_tp1's.
- **Recommendation:** If one head consistently underperforms, consider per-head loss scaling or a learned weighting.

### Finding 4 (CRITICAL — F-005) — TradeNet Is UNWIRED in Production
- **Severity:** HIGH
- **Location:** Registry (`_schema_v4_note`), `fusion_engine.py`, `engine_runner.py`
- **Impact:** TradeNet has NO operational pipeline presence:
  - The `EngineRunner` calls `FusionEngine.compute()` (4 engines), NOT `evaluate()` (3 layers with neural slot).
  - The only "active" model in the registry is v1 `.pth` which does not exist on disk.
  - The only v2 envelope trained (XAUUSD) has `auc_p_tp1=0.5` (random) and was never promoted.
  - Wire-up is gated behind `TN_QUAL_V1` per registry annotation.
- **Recommendation:** Before wire-up: (a) train a v2 envelope with non-degenerate metrics (requires adequate TP1 hits in training data), (b) extend `EngineRunner` to instantiate `make_neural_fn_v2()` and inject it into `FusionEngine.evaluate()` or add a neural slot to `compute()`, (c) test that `FusionEngine.final_score` changes appropriately when neural is present.

### Finding 5 (CRITICAL) — v1 Active Model File Does Not Exist on Disk
- **Severity:** HIGH (for any legacy path attempt)
- **Location:** Registry `v5_auto_2026_06_eth` → `model_file: "models\\ETHUSDT\\20260519_113806\\tradenet_v5_auto_2026_06_eth.pth"`
- **Impact:** If any code path attempted to load the active TradeNet model for ETHUSDT, it would fail file-not-found. The `TradeNetV2._enter_missing_mode()` would emit `TRADENET_MISSING` (CRITICAL) and return None. FusionEngine handles None gracefully (renormalizes to Gaussian-only), so this is a silent degradation rather than a crash.
- **Recommendation:** Either (a) train and promote a real v2 envelope for ETHUSDT, or (b) mark the active pointer as absent to make the degradation explicit rather than relying on file-not-found fallback.

### Finding 6 (INFORMATIONAL) — v2 Envelope Has Degenerate Metrics
- **Severity:** MEDIUM (research finding)
- **Location:** Registry `v2_xauusd_20260723T084643`
- **Impact:** The only v2 envelope ever trained has `auc_p_tp1=0.5` (no better than random) because `pos_rate_p_tp1=0.0` — zero TP1 hits in the training data. The survive_BE head (`auc_p_survives_be=0.644`) shows moderate signal, but without TP1 or TP2 signal the composite score is unreliable.
- **Recommendation:** Investigate whether XAUUSD trades simply do not reach TP1 in the opportunity records, or whether the label construction is filtering them out. TradeNet may require instruments with sufficient TP1/TP2 outcomes to train effectively.

### Finding 7 (GHOST) — `_predict_legacy` Feature Truncation
- **Severity:** LOW
- **Location:** `trade_net_v2.py:376-408`
- **Impact:** The legacy v1 bridge silently truncates the feature vector if it exceeds the model's expected dimension (`vec = vec[:n]` at line 380). If v1 models were trained on a smaller feature set than the current 38-dim vector, truncation would produce incorrect inputs. Currently moot (no .pth files on disk), but a latent bug.
- **Recommendation:** If the legacy bridge is ever exercised, it should log a warning on truncation. Consider a strict dimension check that fails closed instead.

---

## 8. Summary

| Category | Status |
|---|---|
| **Input Contract** | ✅ 38-dim canonical feature vector (macd_hist_raw excluded). Name-anchored extraction. |
| **Probability Model** | ⚠️ 3 independent Bernoulli sigmoids (not a categorical distribution). No calibration layer. |
| **Output Contract** | ✅ Composite score `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be` + per-head probabilities. |
| **Ownership Boundaries** | ✅ All boundaries respected. No overlap with CRT, Gaussian, or RR domains. |
| **Causal Correctness** | ✅ No future leakage. Static artifact, name-anchored extraction. |
| **Production Authority** | ❌ **UNWIRED (F-005)** — code complete but no operational pipeline connection. |
| **Registry State** | ❌ Active model is v1 `.pth` (file absent). Only v2 envelope has degenerate metrics. |
| **Label Quality** | ⚠️ Survives_BE label correlates with TP1 labels. Zero TP1 hits in only v2 training run. |

### Answers to Central Questions

**What inputs does it consume?**
38-dim canonical feature vector (legacy 38-dim, excludes macd_hist_raw). No CRT state, no strategy flags, no OHLCV.

**What probability distribution does it estimate?**
Three independent Bernoulli distributions: P(reaches TP1), P(reaches TP2), P(survives to breakeven). NOT a categorical distribution — heads are independent sigmoids, not a softmax.

**How are probabilities calibrated?**
No explicit calibration. Raw sigmoid outputs from a 38→32→16→[3] MLP trained with weighted BCE. Per-head `pos_weight` handles class imbalance but provides no confidence calibration.

**Does it predict TP/SL, expected move, holding time, or something else?**
It predicts TP hit probabilities (TP1, TP2) and a breakeven-survival proxy (MFE ≥ 1R). It does NOT predict: SL hit probability, expected RR magnitude, expected move in price terms, or holding time.

**Is it the first model that directly contributes to Expected Net Profit, or is that deferred to RRPatternMiner/Fusion?**
**Deferred.** TradeNet produces a confidence-weighted probability blend. Expected Net Profit requires:
- Expected RR (from RRPatternMiner)
- TP hit probabilities (from TradeNet — if wired)
- Position sizing (from ExecutionEngine)

TradeNet is one component of ENP estimation but does NOT produce ENP directly.

### Drift Classifications

| Component | Classification |
|---|---|
| `trade_net_v2.py` (TradeNetV2 inference) | **MATCH** — v2 design spec implemented correctly |
| `train_trade_net_v2.py` (training script) | **MATCH** — v2 training, envelope export, registry registration |
| `model_registry.py` TradeNetRegistry | **MATCH** — per-instrument `__active__` map, register/promote/rollback |
| `fusion_engine.py` neural slot (:587-610) | **DORMANT** — evaluate() neural slot exists but not used by EngineRunner |
| `trainer.py` make_neural_fn / _build_model | **LEGACY** — v1 `.pth` path, superseded by v2 |
| Registry active model (v1 .pth) | **GHOST** — model file does not exist on disk |
| v2 XAUUSD envelope | **DEGENERATE** — auc_p_tp1=0.5 (random), never promoted |

### Key Recommendations

1. **Resolve F-005 (UNWIRED) before any operational use.** Train v2 envelopes with non-degenerate metrics (requires instruments with adequate TP1 hits). Wire `make_neural_fn_v2()` into the production `EngineRunner` — either by extending `FusionEngine.compute()` with a neural slot or switching to `evaluate()` path.

2. **Remove or relegate the ghost v1 `.pth` active pointer.** The ETHUSDT active model file does not exist. Either train and promote a v2 envelope, or clear the `__active__` map entry.

3. **Address label correlation.** The survives_be label (MFE ≥ 1R) is highly correlated with TP1 hits. Consider whether this head provides independent signal or whether a 2-head architecture (TP1 + TP2 only) would suffice.

4. **Document the independent-head semantics.** The three sigmoids are not a categorical distribution. Downstream consumers should not interpret them as such or expect them to sum to 1.0.

5. **No action needed on causal correctness or ownership boundaries** — both are clean.