# RR Engine Lineage Audit

**Program:** Post-CH-002 model/training lineage (subsystem priority 3 — final of five)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Prerequisite:** `POST_CH002_BASELINE_DIFFERENTIAL = PASS` · CRT CLOSED  
**Authority:** observational — no retrain, no re-enable `rr_fusion`, no DecisionEngine rewire

> **GATE (2026-07-21):** Before a new **RR research epoch**, complete
> [`rr_production_readiness_checklist.md`](rr_production_readiness_checklist.md).
> Every item must be **RESOLVED** or **ACCEPTED**. The 12 Research-critical items follow a
> **four-layer graph** (Experiment freeze → Feature truth → Label generation → Research
> execution); epoch begin only when **all four layers** are complete.
> **L1 centerpiece:** signed
> [`rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json`](rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json)
> (`protocol_hash`); L2+ must `assert-signed` and embed the hash. Package currently
> `READY_FOR_SIGNATURE` (proposed fill; owner sign pending;
> `protocol_hash=521fc88f…`). GATE-R / epoch **NOT_AUTHORIZED**. This audit remains the
> lineage narrative; the checklist + L1 certificate are the **blocking inventory**.

---

## Verdict

```text
RR_LINEAGE_VERDICT = THREE_CONTRACTS
  A_LIVE_GEOMETRY     = ACTIVE ALIGNED (RREngine candle polarity ∈[0.5,1]; fusion score)
  B_TRAINED_FUSION    = INERT (rr_fusion.enabled=false; F-038 shipped)
                        + GATE_SKEW if re-enabled (F-044) + LABEL_RISK (F-045/F-022)
  C_DECISION_RR_GATE  = SEMANTIC_MISMATCH (F-048) — polarity vs rr_threshold=1.5
  D_ULTRON_TRUE_RR    = SEPARATE path (SL/TP-derived; min_rr_ratio) — not this engine
  CH002_IMPACT        = INERT for A; pipeline names for B (no force rebuild)
  REBUILD_REQUIRED    = NO for current production
  MARGINAL_OOS        = NO_AUTHORITY for trained model; geometry unmeasured as ΔG001 lever
```

---

## Three (plus one) contracts — never conflate

| ID | Name | Learning? | Active on spine? |
|---|---|---|---|
| **A** | `RREngine` — Candle Polarity Index | No (geometry) | **YES** — fusion weight `weight_rr` |
| **B** | `NanoInferenceEngine` + `RRFusionLayer` | Yes (Ridge + GNB + Mahalanobis) | **NO** — `rr_fusion.enabled=false` |
| **C** | `DecisionEngine` `fusion["rr"] < rr_threshold` | N/A (consumer) | Gate-ON path only; **structurally broken** vs A |
| **D** | `UltronRiskGate` Check 2 — true forward RR | N/A | Separate; uses trade `rr_ratio` from planner SL/TP |

`EXPECTED_ENGINES` includes `"rr"` → **A** always runs when EngineRunner runs.

---

## Lineage chain (11 slots) — dual fill where A/B differ

### 1. Training population

| Track | Population |
|---|---|
| **A** | None — pure OHLC geometry |
| **B** | Preferred: `scripts/data/build_rr_dataset.py --opportunities` JSONL (features already in record). Legacy: trades CSV + FeaturePipeline |
| Builder | `src/config_layer/rr/rr_dataset_builder.py` |
| Corpus scale | `models/rr_model.meta.json`: n=**49,000**, effective_dof=**27** |

### 2. Feature identities

| Track | Features |
|---|---|
| **A** | `close`, `high`, `low` only (`rr_engine.py:47-49`) |
| **B** | Full 38-dim `CANONICAL_FEATURES`; train/infer zero price indices `[0,1,2,3,4,7,8,16,17,26,27]` → **dof≈27** (`train_rr_model.py`, model `zero_indices`) |
| Pipeline names | `retest_depth` / `disp_strength` (FM-021/020) appear in B vectors |
| CRT FM-027/028 | **Not** used by A or B |

### 3. Target / label

| Track | Target |
|---|---|
| **A** | None |
| **B** | `extract_target`: `y_rr` from `rr_achieved` → `pnl_rr_net` → entry/sl/tp; `y_win` from outcome/win/rr>0 (`rr_dataset_builder.py:125-206`) |

**F-045:** kill-test **INDETERMINATE** — labels are F-022-contaminated stream; `y_rr` near-degenerate (win→+1.0). Apparent OOS discrimination (AUC 0.605) is **not** credible economic authority. Required before Keep/Retire: `forward_walk(intrabar_fixed)` re-label.

### 4. Dataset builder

| Path | Role |
|---|---|
| `scripts/data/build_rr_dataset.py` | Opportunities or trades → RR dataset JSON |
| `RRPatternTrainer` | Ridge expected_rr + GNB p_win + Ledoit-Wolf confidence covariance (`rr_pattern_miner.py`) |
| `scripts/training/train_rr_model.py` | Train → versioned model + `rr_registry.json` |
| Probe | `scripts/analysis/rr_confidence_probe.py`, `scripts/research/rr_shadow_value.py` (read-only) |

### 5. Artifact

| Path | Role | Active for live fusion? |
|---|---|---|
| `models/rr_model.json` | Canonical NanoInference state (sha `6ed92d26…cd66`) | Only if rr_fusion enabled |
| `models/rr_model.meta.json` | d_sq distribution provenance (F-044) | Docs/probe |
| `models/rr_model_202605_bnb_*.json` | Versioned BNB models | Registry |
| `models/rr_registry.json` | Version manifest; e.g. `202605_bnb_v2_bnbusdt` active → versioned file | Bookkeeping for B |

Config default model path: `engine_runner.rr_fusion.model_path` / `rr_model.model_path` = `models/rr_model.json`.

### 6. Loader

| Track | Loader |
|---|---|
| **A** | `RREngine(config)` in `EngineRunner.__init__` (`engine_runner.py:345`) — always |
| **B** | `RRFusionLayer` only if `rr_fusion.enabled` (`:354-373`); `NanoInferenceEngine.load(path)` |

With `enabled:false`: `self.rr_fusion = None`; `rr_result = self.rr.compute(input_data)` flows **unmutated** (F-038 Fix B; test `test_rr_fusion_disabled_is_base_rr_identity`).

### 7. Inference inputs

#### A — geometry

```text
input_data[close, high, low]
  → polarity = max( (h-c)/range, (c-l)/range )  ∈ (0.5, 1] mid→extreme
  → score = candle_polarity = rr_ratio (legacy field name)
  → semantic: candle_structure_quality  # NOT forward RR
```

#### B — trained (disabled)

```text
canonical 38-vector (or historically starved 2–3 keys via score_dict — F-038 Fix A)
  → zero_indices mask
  → scale → ridge expected_rr + GNB p_win
  → Mahalanobis d_sq → confidence = exp(-0.5 · d_sq)  # legacy_scalar mode
  → if confidence < confidence_bypass_threshold(0.3) → passthrough gaussian
```

**F-044:** gate mis-scaled for rank-27 form — **100% in-sample bypass** (min d_sq=4.30 > cut for conf≥0.3). Retrain alone cannot fix. Modes `chi2_tail` / `dof_scaled` / `percentile` exist; default **`legacy_scalar`**.

### 8. Output semantics

| Track | Output | Meaning |
|---|---|---|
| **A** | `score` / `rr_ratio` ∈[0,1] | Candle extreme-commitment quality |
| **B** (if on) | `final_score`, `expected_rr`, `probability_of_win`, `confidence` | Historically collapses to **gaussian** under legacy gate |
| **C** consumer | Treats `fusion["rr"]` as **true RR ratio ≥1.5** | **Mismatch** with A (F-048) |
| **D** Ultron | Trade `rr_ratio` from SL/TP | True economic RR floor (`min_rr_ratio=1.5`) |

### 9. Active config

| Key | Value |
|---|---|
| `engine_runner.rr_fusion.enabled` | **`false`** |
| `rr_fusion.model_path` | `models/rr_model.json` |
| `rr_fusion.full_feature_vector` | `false` (legacy score_dict path if ever enabled) |
| `rr_model.confidence_bypass_threshold` | `0.3` |
| `rr_model.drift_threshold` | `1.5` |
| `rr_model` confidence mode | `legacy_scalar` |
| `decision_engine.rr_threshold` | **`1.5`** |
| `ultron` / execution `min_rr_ratio` | `1.5` (true RR on trade plan) |
| `fusion_engine.weight_rr` | `0.2` (applies to **A** score in fusion average) |

### 10. Runtime consumption

```text
EngineRunner.run
  → rr_result = RREngine.compute(input_data)          # A always
  → if rr_fusion loaded: mutate rr_result             # B OFF → skip
  → engine_results["rr"] → FusionEngine.compute       # A score weight 0.2
  → DecisionEngine.evaluate(
        fusion={"rr": engine_results["rr"]["rr_ratio"], ...}   # C
    )
       if rr < 1.5 → reject "low_rr"
       # polarity ≤ 1.0 always → low_rr always when score path reaches here
```

**Backtest gate-ON:** EngineRunner is a **post-CRT veto**. F-048: `run()` can never return `execute` because polarity ≤1 < `rr_threshold` 1.5.  
**Observed BNB baseline:** 11 trades journaled — admits are CRT path with ER rejects only `invalid_session` (2); DecisionEngine `execute` is not the journal admitter in this harness (veto-only / fail-soft nuances — F-048 residual).

**True RR floor (D):** `UltronRiskGate` compares planner-derived `trade["rr_ratio"]` to `min_rr_ratio` — independent of RREngine.

**WIRING SHIPPED 2026-07-17 (contracts C/D, B unchanged):**
- **C (F-048 partial fix):** `engine_runner` marks fusion RR as `rr_semantic=candle_polarity`; `DecisionEngine` only enforces economic RR when `true_rr` is supplied or legacy `rr` without polarity semantic — polarity no longer forces permanent `low_rr`.
- **D:** `live_engine_hook` sets `trade_plan["rr_ratio"]` from SL/TP1 geometry (`|tp1−entry|/|entry−sl|`), plus `rr_ratio_tp2` audit field — no longer hardcoded `1.0`.
- **B:** remains `rr_fusion.enabled=false` (shadow/inert; no production authority).
- **Note:** intents with TP1 R-multiple &lt; `ultron_risk_gate.min_rr_ratio` (1.5) will now fail D honestly (e.g. default `tp1_atr_multiplier=1.0`, pullback 0.8).

**IF LIVE REJECTS SPIKE (post 2026-07-17 D-wiring):**
- Correct action = review `crt_engine.tp1_atr_multiplier*` vs `ultron_risk_gate.min_rr_ratio` under **config governance** (rehash/promote as required) — **not** a research/descriptive-pack change.
- Optional: open a **separate pre-registered** study on optimal R thresholds (new hypothesis cycle) — **not** derived from the XAUUSD descriptive pack / near-miss autopsy.
- Forbidden: re-enable `rr_fusion` (B), re-conflate polarity (A) with economic RR (D), or invent exits from descriptive near-miss stats without preregistration.

**H-RR-THRESHOLD-001 OPENED 2026-07-17 (user-explicit):**  
Pre-registration frozen at  
[`docs/research-readiness/h-rr-threshold-001-preregistration.md`](../research-readiness/h-rr-threshold-001-preregistration.md)  
(+ JSON twin). Status = design frozen, **not run**. Research-only; no auto config promote.

### 11. Marginal OOS value

| Claim | Status |
|---|---|
| A (polarity) improves expectancy | Unmeasured as isolated lever; fusion weight present |
| B (trained RR) | **INERT**; F-045 indeterminate; F-044 blocks re-enable |
| Re-enable rr_fusion | **NO_AUTHORITY** without dof-aware gate + clean labels + ΔG001 |
| Fix F-048 DecisionEngine | Intent adjudication open (bug vs dormant-live) — architecture program |

---

## CH-002 impact assessment

| Question | Answer |
|---|---|
| Does RREngine read FM-027/028? | **No** (OHLC only) |
| Does trained model use CRT emission keys? | **No** — pipeline vector |
| Live A score changed by CH-002? | **No** (baseline economic parity PASS) |
| Rebuild required now? | **NO** |
| Rebuild before re-enable B? | Gate fix + label re-derive first; retrain alone insufficient (F-044) |

---

## F-048 producer–consumer mismatch (detail)

| Producer (A) | Consumer (C) |
|---|---|
| `rr_ratio` = polarity ∈ **[0.5, 1.0]** | Requires `fusion["rr"] ≥ rr_threshold` **1.5** |
| Documented `semantic: candle_structure_quality` | Comment at engine_runner:955–957 still says “true RR ratio” |
| Intent tests inject `rr: 2.0` for execute | Real wire can never clear 1.5 |

**Ultron (D)** already owns true RR.  
**Status:** CANDIDATE / confirmed mismatch; not remediated in this audit; **not** a CH-002 issue; **do not** reopen CRT.

---

## Rebuild / re-enable matrix

| Action | Allowed now? | Condition |
|---|---|---|
| Retrain rr_model for CH-002 | **NO** | B inert; pipeline names OK |
| Re-enable `rr_fusion` | **NO** | F-044 gate + F-045 labels + ΔG001 |
| Switch confidence mode off legacy | Config research only | Still need enable + authority |
| Fix DecisionEngine to true RR | Separate design program | Intent adjudication first |
| Change RREngine formula | STRUCTURAL / high cost | Not lineage-driven |

---

## Known gaps / non-blockers

1. **Legacy field name `rr_ratio`** on polarity output — root of F-048 confusion.  
2. **engine_runner comment** still claims true RR for DecisionEngine wire.  
3. **`active_models.yaml` findings** list F-038; should also cite F-044/F-045/F-048 (doc hygiene).  
4. **Registry active BNB model** ≠ live fusion consumer while fusion disabled.  
5. **score_dict 3-feature starvation** still default if fusion re-enabled without `full_feature_vector:true` (F-038 Fix A).  
6. **Backtest gate-OFF** never exercises A/B/C (F-037).

---

## Key file map

| Role | Path |
|---|---|
| Live geometry | `src/engines/rr_engine.py` |
| Trained train/infer | `src/config_layer/rr/rr_pattern_miner.py` |
| Dataset / labels | `src/config_layer/rr/rr_dataset_builder.py` |
| Fusion layer | `src/config_layer/rr/rr_fusion.py` |
| Orchestration | `src/core/engine_runner.py` ~345–373, ~683–730, ~954–977 |
| Decision gate | `src/core/decision_engine.py:144-147` |
| True RR | `src/core/ultron_risk_gate.py` ~230–245 |
| Train CLI | `scripts/training/train_rr_model.py` |
| Build data | `scripts/data/build_rr_dataset.py` |
| Artifact | `models/rr_model.json` (+ meta, registry) |
| Findings | F-038, F-044, F-045, F-048 |
| Config | `v2_multi_2026_04.json` — `rr_fusion`, `rr_model`, `decision_engine.rr_threshold` |
| active_models | `active_models.yaml` → `rr_model:` |
| Tests | `tests/test_engine_runner_rr_fusion.py`, `tests/test_rr_fusion_full_vector.py` |

---

## Full program rollup (all five subsystems)

| Subsystem | Spine? | CH-002 | Rebuild now? | Dominant finding |
|---|---|---|---|---|
| Gaussian | YES (heuristic) | INERT | NO | Live ≠ trained ML |
| ZoneGate | YES (trained geometric) | INERT | NO | F-036 non-pivotal · F-041B no edge |
| **RR** | YES geometry / NO fusion | INERT | NO | F-038/044/045/048 multi-contract |
| BitNet | NO | SKEW if enable | NO (YES before enable) | F-004 · train≠serve math |
| TradeNet | NO | INERT | NO | F-005 unwired |

**No mass retrain justified by CH-002.**  
**StructuredOpportunity / MarketSnapshot** may now be designed from these verified interfaces — not before.

---

## Final return

```text
RR_ACTIVE_ON_PATCH       = RREngine geometry YES; rr_fusion NO
RR_LINEAGE_STATUS        = THREE_CONTRACTS (A ALIGNED / B INERT+SKEW / C MISMATCH)
REBUILD_REQUIRED_NOW     = NO
CH002_IMPACT             = INERT
NEW_FINDINGS             = none (F-038/044/045/048 already cover)
DO_NOT                   = retrain for rename; re-enable fusion; silent F-048 “fix”
PROGRAM_LINEAGE_STATUS   = COMPLETE (Gaussian, ZoneGate, RR, BitNet, TradeNet)
HIGHEST_LEVERAGE_NEXT    = optional model_lineage_rollup.md OR F-048 intent adjudication
                           OR OI-ER-001 — NOT CRT rediscovery, NOT mass retrain
```
