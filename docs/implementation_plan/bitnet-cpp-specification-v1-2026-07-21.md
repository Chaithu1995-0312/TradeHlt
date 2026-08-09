# BitNet.cpp Specification v1

**Status:** **RUNTIME FROZEN** — architecture + Python platform complete; bottleneck = **evidence** (not design)  
**Accepted (UTC):**  
- 2026-07-21 — Spec v1 / v1.1 (contracts A+B+C, hierarchy)  
- 2026-07-21 — Spec **v1.2** / **v1.2.1** (backbone family + versioned numeric defaults)  
- 2026-07-21 — Python reference runtime; architecture work stops  
- 2026-07-21 — **v1.2.3** phase transition: architecture → evidence; CONTRACT-C + model.bundle  
- 2026-07-21 — **v1.2.4** evidence stages R1–R6; model.bundle manifests  
- 2026-07-22 — R1 trainer shipped (reproducibility only)  
- 2026-07-22 — **v1.2.5** R1 non-claims; R2.5 before R3; Evaluation Report v1  
- 2026-07-22 — **v1.2.6** R2.5 kill-test gates; R3 three outcomes  
- 2026-07-22 — **R2.5 harness implemented** (`bitnet.r25_kill_test` + CLI); thresholds  
  `r25_thresholds_v1` pre-registered; PASS → earn R3 only  
**Date (UTC):** 2026-07-22  
**Revision:** **v1.2.6** (+ R2.5 harness shipped)  
**Branch scope:** `feature/truth-registry-v2` (and any descendant that inherits active `v2_multi_2026_04`)  
**Authority class:** architecture / governance only — grants **no** production enablement, retrain, wire-up, C++, or Phase 2b code authority  
**Prerequisite reads:**  
[`docs/governance/bitnet_lineage_audit.md`](../governance/bitnet_lineage_audit.md) ·  
[`docs/topics/bitnet-gate.md`](../topics/bitnet-gate.md) ·  
F-004 / F-050 / F-055 · §6.5 Authority Ladder  

---

## 0. Why this document exists

**Biggest risk (v1.0):** rewriting BitNet before freezing the contract → interface drift.  
**Biggest risk (v1.2):** *designing forever* without a backbone family → every impl invents structure.  
**Biggest risk (v1.2.1):** treating **numeric knobs** (H, L, N_res, budgets) as sacred laws →
either endless re-spec or false rigidity when a retrain needs a wider latent.

**Design is frozen.** Further work is implementation / training / evidence — not new architecture
layers — unless a product decision opens a **new architecture family**.

**Rule (non-negotiable):**

```text
CONTRACT FIRST (A + B + C)          ✅ v1.1
  → SURFACE INVENTORY               ✅
  → STABLE API HIERARCHY            ✅ v1.1
  → BACKBONE FAMILY (structural)    ✅ v1.2
  → NUMERIC DEFAULTS (versioned)    ✅ v1.2.1  ← not immutable laws
  → (optional) Python Protocols     Phase 2b — deferred
  → IMPLEMENTATION (any language)   Phase 3 — not yet
  → TRAINING                        Phase 4 — not yet
  → SHADOW EVAL                     Phase 5 — not yet
  → PRODUCTION PROMOTE              Phase 6 — evidence only
```

**Does not** change CONTRACT-A legacy composition; **does not** authorize C++ or Phase 2b.

### 0.1 Law tiers (v1.2.1 — binding)

| Tier | What | Change rule |
|---|---|---|
| **L0 — Contract law** | CONTRACT-A / B / C; pure inference; CRT façade `bitnet_score` semantics | Migration section + user authority |
| **L1 — Architecture law** | Hierarchy Encoder→Backbone→Heads→Adapter; BitLinear residual **family**; ternary+scale; post-act residual; single final latent; no backbone LayerNorm; heads not inside residual stages | New architecture family id (not a silent edit) |
| **L2 — Versioned defaults** | H, L, N_res, E, param/latency **guidance**, train hyper-recs, bias on/off default | Bump `defaults_profile` + declare values in artifact envelope; **self-describing load** |
| **L3 — Open product** | CRT 6 vs 38 cutover; STE vs PTQ; enable/ΔG001 | Product / Phase 5–6 |

**Rule:** L2 numbers in this document are the **current defaults profile**
(`defaults_profile = bitlinear_res_defaults_v1`). They are the recommended starting point and the
parity baseline for the first implementation — **not** constitutional invariants.  
An artifact that uses different H/L/N_res remains **in-family** if L1 holds and the envelope
declares the actual numerics.

---

## 1. Mission and scope

### 1.1 Mission (economic / product)

BitNet answers one question when used on the CRT spine:

> **"Is this market state acceptable enough to allow the opportunity to proceed?"**

It is an **optional hard-reject evidence producer** (veto only when enabled). It is:

| Is | Is not |
|---|---|
| A confidence / acceptability score | The trading engine |
| Optional evidence (config-gated) | A fusion vote among EXPECTED_ENGINES |
| Pure inference when scoring | A decision-maker with promotion authority |
| Distinct from TradeNet | A multi-outcome TP1/TP2/BE predictor |
| Distinct from Claude Coding Agent | Software that writes the repository |

### 1.2 Scope of this specification

| In scope | Out of scope |
|---|---|
| Freeze production inference contract (CONTRACT-A) | Enabling `use_bitnet` on active config |
| Freeze aspirational multi-head surface (CONTRACT-B) as non-prod | Training a new model / writing C++ |
| Freeze training contract (CONTRACT-C) | Wiring TradeNet / fusion neural_fn |
| Inventory all BitNet-named surfaces | ZoneGate / `BitNetZoneGate` geometric scoring |
| Design stable API hierarchy (Encoder→Backbone→Heads→Adapter) | LLM / BitNet-3B / GGUF (unrelated naming) |
| Test + governance promotion criteria | Any production behavior change |

### 1.3 Naming hygiene (do not conflate)

| Name in repo | Actual subsystem |
|---|---|
| **BitNet gate / `bitnet_score`** | 6-feature neural hard-reject (this spec) |
| **bitnet_v3 / export ternary** | Alternate model envelope + shallow ternary FF |
| **`tools/cpp/cpp_runner.cpp`** | C++ parity harness (not spine) |
| **BitNetZoneGate** | ZoneGate geometric registry scorer — **not** this model |
| **BitNet 3B / llama gate** | LLM tie-breaker path — **not** this model |
| **TradeNet v2** | 38-dim 3-head outcome model — **separate** (F-005) |

---

## 2. Three contracts (must stay separate)

```text
CONTRACT-A  Inference consumer (CRT gate)     — what callers require today
CONTRACT-B  Inference product (multi-head)    — aspirational capability surface
CONTRACT-C  Training                          — how weights may be produced
```

A and B describe **serve-time** shapes. C describes **train-time** discipline.  
**Train/serve identity** is the join of C → A/B: an artifact is only CRT-eligible if its
encoded train identities match the encoder identities declared for the serve path.

### CONTRACT-A — Production CRT gate (FROZEN baseline · ACCEPTED)

This is what the spine **actually** calls when `use_bitnet=true`.  
**Any modernization that claims CRT compatibility MUST satisfy CONTRACT-A or provide an explicit adapter that preserves A’s external semantics.**

| Field | Specification | Source of truth |
|---|---|---|
| **Function** | `bitnet_score(features: dict) -> float` | `src/bitnet/bitnet_inference.py:317-332` |
| **Input keys (hard)** | `body_ratio`, `retest_depth`, `disp_strength`, `atr`, `candles_since_retest`, `double_sweep` | same |
| **Input order** | Exactly the order above (positional list into legacy forward) | same |
| **Missing key** | **Fail-fast** (KeyError) — production behavior | same |
| **Output** | Scalar confidence **∈ [0, 1]** (sigmoid) | legacy `forward()` |
| **Threshold consumer** | `bn_score < config.bitnet_main_threshold` → reject | `crt_engine_v2.py:1970-1978` |
| **Default threshold** | `0.55` | `CRTConfig.bitnet_main_threshold` |
| **Enable flag** | `use_bitnet` (active production: **`false`**) | F-004; `v2_multi_2026_04` |
| **Reject reason** | `RejectReason.LOW_SCORE` | crt_engine_v2 |
| **Role** | Optional hard veto **before** soft-confirmation fusion; not a fusion engine | lineage audit |
| **Side effects of `bitnet_score` itself** | **None** — pure function over features + loaded model weights | required invariant |
| **Side effects of *call site*** | May log score; may set `state.bitnet_main_score`; may reject | crt_engine_v2 |

#### CONTRACT-A serve-time feature mapping (call-site adapter)

CRT cache does **not** store `retest_depth` / `disp_strength` under those names post-CH-002:

```text
CRT cached_features:
  body_ratio
  displacement_retrace     # FM-027
  displacement_atr_ratio   # FM-028
  + atr_abs as "atr"
  + candles_since_retest
  (+ double_sweep when present)

Call-site map (approve_with_soft_conf, crt_engine_v2.py:1971-1974):
  retest_depth  ← displacement_retrace   (FM-027)
  disp_strength ← displacement_atr_ratio (FM-028)

bitnet_score hard keys:
  body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep
```

#### CONTRACT-A train/serve skew (known defect — F-050)

| Legacy key | Train identity (`train_bitnet.py` / pipeline) | Serve identity (if enabled) |
|---|---|---|
| `retest_depth` | FM-021 pipeline geometry | FM-027 CRT displacement retrace |
| `disp_strength` | FM-020 pipeline geometry | FM-028 CRT displacement ATR ratio |
| `atr` | pipeline relative ATR (typically) | `state.atr_abs` (absolute price units) |

**Freeze implication:** CONTRACT-A freezes the *interface*, including the current (skewed) identity map, as the **behavior baseline**. Fixing identity is a **separate governed change** (new schema version + retrain + parity), not a silent rewrite.

#### CONTRACT-A behavioral role

```text
Evidence producer → optional veto
NOT decision authority
NOT fusion weight
NOT TradeNet
```

Active patch: path **skipped** (`use_bitnet:false`) → **INERT** (F-004).  
Shadow measurement of existing model: **no authority to enable** (F-055).

---

### CONTRACT-B — Aspirational BitNet.cpp multi-head (FROZEN as non-production · ACCEPTED)

This is the design discussed as “true BitNet.cpp,” **not** what the spine runs today.

```text
38 Canonical Features
        ↓
Feature Quantization / Normalization (declared, versioned)
        ↓
BitLinear Layers (1-bit / ternary weights)
        ↓
Residual Blocks
        ↓
Feature Interaction Learning
        ↓
Compact Latent Representation
        ↓
Output Heads
    ├── confidence          (must remain mappable to CONTRACT-A score if used as CRT gate)
    ├── win_probability     (optional research head)
    ├── expected_rr         (optional research head)
    └── embedding           (optional research / retrieval head)
```

| Field | Draft rule |
|---|---|
| **Input dim** | 38 = `CANONICAL_FEATURE_DIM` / `CANONICAL_FEATURES` order |
| **feature_order_hash** | Must match `features.feature_schema.FEATURE_ORDER_HASH` |
| **Normalization** | Must be serialized with the model (mean/std or declared quantizer); train ≡ serve |
| **Primary CRT-compatible output** | `confidence ∈ [0, 1]` with documented calibration |
| **Extra heads** | Allowed only if callers that expect a scalar still receive a stable primary score |
| **Spine role** | Still **evidence producer**; enable only via `use_bitnet` + promotion |
| **Status** | **NOT AUTHORIZED for production** until Phase 4 + §10 gates pass |

**Critical rule:** Implementing CONTRACT-B **must not** change CONTRACT-A call sites until an adapter proves:

```text
adapter(CONTRACT-B.predict(x38)).confidence  ≈  CONTRACT-A semantics
```

or an explicit **schema version bump** + config migration is approved (behavior change authorized).

---

### CONTRACT-C — Training Contract (FROZEN · ACCEPTED)

**Purpose:** freeze *how a model may be learned and exported* so that any future retrain
or BitNet.cpp rebuild cannot claim CRT compatibility without train≡serve identity and a
versioned label definition.

CONTRACT-C does **not** authorize a retrain. It only freezes the rules a retrain must obey.

#### C.1 Identity lock (closes F-050 class defects)

| Rule | Specification |
|---|---|
| **Feature names alone are insufficient** | Every train feature MUST carry a stable identity: `FM-id` and/or ontology formula id + version |
| **Train ≡ serve** | The encoder’s declared identity list for serve MUST equal the train identity list (order + FM-id). Mismatch → artifact is **not CRT-eligible** |
| **No silent aliasing** | Mapping CRT cache keys (e.g. FM-027 → legacy `retest_depth`) is an **Adapter** concern and MUST appear in metadata as an explicit map, never as “same string different math” |
| **ATR scale** | Train and serve MUST agree absolute vs close-relative for any feature named `atr` (today’s path is inconsistent — blocked for new CRT-eligible artifacts until fixed) |

#### C.2 Population

| Field | Specification |
|---|---|
| **Universe** | Explicit instrument list + timeframe (e.g. M15) |
| **Bar filter** | Versioned predicate (status-quo example: pipeline `retest_depth > 0.05` under **declared FM-id**) |
| **Warmup / horizon** | Declared integers (status quo: WARMUP=60, MAX_FWD=40) |
| **Direction scope** | Declared: bullish-only / bearish / both (status quo train: bullish-only) |
| **Leakage** | No future bars in features; PIT rules match feature-layer doctrine for any promoted feature |

#### C.3 Labels (versioned)

Every training run MUST stamp a `label_contract_id` and definition:

| Field | Specification |
|---|---|
| **label_contract_id** | Stable string, e.g. `BITNET_LABEL_ATR_RACE_BULL_V1` or `BITNET_LABEL_FW_INTRABAR_12BPS_V1` |
| **Definition** | Exact TP/SL/timeout/cost geometry in text + code reference |
| **Timeout policy** | Include / drop / soft-label (status quo: drop) |
| **Economic authority** | `DIAGNOSTIC_ONLY` \| `RESEARCH_CANDIDATE` \| `CRT_ELIGIBLE_CANDIDATE` |
| **Contamination gate** | Labels derived from F-022 opportunity `outcome`/`rr` without `forward_walk` re-derive are **not** `CRT_ELIGIBLE_CANDIDATE` |

**Status-quo label (must be declared if retained):**

```text
label_contract_id: BITNET_LABEL_ATR_RACE_BULL_V1
  win  = high reaches close + 2·ATR before low reaches close − 1·ATR within 40 bars
  loss = SL first
  timeout = dropped
  economic_authority: DIAGNOSTIC_ONLY  (not M4 journal expectancy)
```

For any claim of production enablement, prefer a governed label such as
`forward_walk(intrabar_fixed)` (+ declared cost) with `economic_authority` upgraded only
after shadow ΔG001 evidence (CONTRACT-A enable path still required).

#### C.4 Loss / objective

| Field | Specification |
|---|---|
| **Primary objective** | Declared (status quo: MSE on sigmoid confidence vs {0,1}) |
| **Multi-head** | If CONTRACT-B heads train, each head has its own loss term + weight; composite confidence definition is fixed *before* train |
| **Class balance** | Declared (none / pos_weight / resampling) |
| **Forbidden** | Optimizing directly against CRT trade count or post-hoc threshold search that leaks test instruments into train |

#### C.5 Splits and evaluation during train

| Field | Specification |
|---|---|
| **Split** | Time-ordered; no random shuffle across time |
| **Holdout** | At least one OOS window not used for early stopping cherry-pick without disclosure |
| **Metrics logged** | Per-split: n, pos rate, loss, optional AUC; **not** treated as ΔG001 |
| **ΔG001** | Only via spine shadow diagnostic after artifact export (Phase 4) — never from train loop |

#### C.6 Export envelope + model.bundle (join to A/B)

**R1 package rule (v1.2.4):** emit a **self-contained `model.bundle`** (directory/zip), not weights alone.
Minimum members: `envelope.json`, `metadata.json`, `feature_schema.json`, `label_contract.json`,
`metrics.json`, `training_manifest.json`, `evaluation_report.json` (may be stub at R1),
`sha256.txt` (+ `weights.bin` if not inlined). See §11 bundle layout.

Every exported artifact / envelope MUST include:

```text
schema_version
feature_dim
feature_names[]
feature_order_hash
train_feature_identities:  [{ name, fm_id, formula_id?, version }]
label_contract_id
label_definition_ref
economic_authority
train_population: { instruments, timeframe, bar_filter_id, direction_scope }
normalization: { type, params... }     # mean/std or quantizer — train≡serve
backbone_id / heads_id / encoder_id    # hierarchy component ids (§4)
adapter_maps: { crt_serve?: { from_key, to_key, from_fm, to_fm }[] }
artifact_sha256
created_at
trainer_git_commit?                    # optional but recommended
```

Loaders reject CRT-eligible use if `economic_authority` is only `DIAGNOSTIC_ONLY` and a
caller requests production gate load (research harness may still load for measurement).

#### C.7 Registry and promotion (training side)

| Rule | Specification |
|---|---|
| **Empty registry today** | `models/bitnet/bitnet_registry.json` is empty — no promote surface |
| **Future promote** | Requires non-empty registry entry + CONTRACT-C fields + hash |
| **Retrain ≠ enable** | Registering an artifact grants **no** `use_bitnet:true` |
| **Rollback** | Prior artifact + config snapshot restorable |

#### C.8 CONTRACT-C one-pager

```text
BITNET_CONTRACT_C_V1 (TRAINING)
  train_feature_identities == serve encoder identities (order + FM-id)
  no silent name aliasing (adapters declare maps)
  label_contract_id + economic_authority required on every artifact
  status-quo ATR-race label = DIAGNOSTIC_ONLY
  F-022 opportunity labels without re-derive ≠ CRT_ELIGIBLE_CANDIDATE
  time-ordered splits; train metrics ≠ ΔG001
  export carries encoder/backbone/heads ids + normalization
  retrain does not enable production
```

---

## 3. Surface inventory (Phase 1 deliverable)

### 3.1 Architecture diagram (authoritative for this branch)

```text
                         ┌─────────────────────────────────────┐
                         │  NAMING COLLISION (NOT BitNet model) │
                         │  BitNetZoneGate / ZoneGate registry  │
                         │  → fusion engine "zone_gate"         │
                         └─────────────────────────────────────┘

CANONICAL 38-dim FeaturePipeline ──────────────────────────────┐
        │                                                      │
        │ (research / export paths)                            │
        ▼                                                      │
  train_bitnet.py ──► model.json (legacy_6input, 6→16→8→1)     │
  export_bitnet_model.py ──► bitnet_v3 / export ternary JSON   │
  tools/cpp/cpp_runner.cpp ──► cpp_outputs.json (parity only)  │
        │                                                      │
        ▼                                                      │
  BitNetModel (bitnet_inference.py)                            │
    ├─ legacy forward(6) ◄── bitnet_score()  ◄── CRT CALL SITE │
    └─ predict(export/v3 vector) ◄── BitNetRunner (harness)    │
                                                               │
CRT spine (when use_bitnet=true):                              │
  RETEST cached_features (FM-027/028 + body_ratio)             │
        │                                                      │
        ▼                                                      │
  UltronRiskEngine.approve_with_soft_conf                      │
        │  map FM→legacy keys                                  │
        ▼                                                      │
  bitnet_score → [0,1]                                         │
        │                                                      │
        ├─ score < bitnet_main_threshold → REJECT LOW_SCORE    │
        └─ else → soft-confirmation fusion (G×C tiers)         │
                                                               │
ACTIVE CONFIG (v2_multi_2026_04): use_bitnet=false → SKIP ─────┘
```

### 3.2 Artifact table

| Surface | Path | Contract | Spine? |
|---|---|---|---|
| CRT score API | `src/bitnet/bitnet_inference.py` `bitnet_score` | **A** | Yes (gated) |
| Model class | `BitNetModel` same file | A + export/v3 | Indirect |
| Serialization | `src/bitnet/model_contract.py` (`bitnet_v3`, legacy bridges) | Envelope | Loader |
| Runner | `src/bitnet/bitnet_runner.py` | Fail-closed dim + thresholds | Harness / alternate |
| Thresholds JSON | `src/bitnet/bitnet_thresholds.json` | BitNetRunner only | No CRT path |
| Train | `scripts/training/train_bitnet.py` | 6 keys, ATR-race labels | No |
| Export | `scripts/export/export_bitnet_model.py`, `regen_bitnet_35.py`, `generate_bootstrap_model.py` | export/v3 | No |
| C++ parity | `tools/cpp/cpp_runner.cpp` (+ `json.hpp`) | 35-feat ternary experiment | **No** |
| Default artifact | cwd `model.json` (legacy_6input) | A | CRT default load |
| Export artifact | `results/model_export_format.json` | export path | `engine_runner.model_path` (not CRT score path) |
| Registry | `models/bitnet/bitnet_registry.json` | **empty** — no promote surface | No |
| Shadow config | `configs/production/v2_multi_bitnet_shadow_2026_07.json` | research only | Non-active |
| Shadow diagnostic | `scripts/research/bitnet_shadow_diagnostic.py` | F-055 | Read-only econ |
| Lineage audit | `docs/governance/bitnet_lineage_audit.md` | observational | — |
| Topic | `docs/topics/bitnet-gate.md` | living topic | — |
| Original multi-head BitNet.cpp source | **Not in repo as production subsystem** | B (aspirational) | — |

### 3.3 CRT call sites (CONTRACT-A consumers)

| Site | File | Notes |
|---|---|---|
| **Live path** | `UltronRiskEngine.approve_with_soft_conf` | Guarded by `use_bitnet`; maps FM-027/028 |
| **Dead path** | `UltronRiskEngine.approve` | BitNet block unguarded by `use_bitnet`; **no spine callers** (F-004) — do not resurrect without guard |
| Config | `CRTConfig.use_bitnet`, `bitnet_main_threshold` | Active: false / 0.55 |
| Persistence | `TradeRecord.bitnet_score_at_entry` / `bitnet_decision_at_entry` | When scored |

### 3.4 What is *not* on the inventory as BitNet.cpp

- No residual-block multi-head C++ engine integrated into EngineRunner or CRT.
- `cpp_runner.cpp` is a **parity tool** (normalize → binarize → 3 ternary layers → dump JSON).

---

## 4. Interface hierarchy design (Phase 2 · ACCEPTED design, no code)

**Principle:** separate *what the spine needs* (Adapter → CONTRACT-A) from *how features
are prepared* (Encoder), *how representation is learned* (Backbone), and *what is
predicted* (Heads). Internals may change; boundaries must not.

```text
                    ┌──────────────────────────────────────────┐
                    │         IBitNetModel (composition)       │
                    │   load() · predict() · metadata()        │
                    └──────────────────────────────────────────┘
                                         │
           ┌─────────────┬───────────────┼───────────────┬─────────────┐
           ▼             ▼               ▼               ▼             │
    IFeatureEncoder  IBackbone        IHeads        IAdapter           │
           │             │               │               │             │
           │             │               │               │             │
   FeatureBag/Tensor  EncodedTensor   Latent      HeadOutputs     Prediction
           │             │               │               │             │
           └─────────────┴───────────────┴───────────────┴─────────────┘

Pipeline (serve):

  raw features (dict | tensor)
        │
        ▼
  ┌─ Encoder ─────────────────────────────────────────────────────────┐
  │  select by declared identities · order · normalize/quantize       │
  │  fail-closed on missing/NaN/hash mismatch                         │
  │  out: EncodedTensor + EncodingMeta                                │
  └───────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─ Backbone ────────────────────────────────────────────────────────┐
  │  BitLinear / residual / latent (pure math)                        │
  │  out: Latent                                                      │
  └───────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─ Heads ───────────────────────────────────────────────────────────┐
  │  confidence (required for CRT path)                               │
  │  optional: win_p, expected_rr, embedding (CONTRACT-B)             │
  │  out: HeadOutputs                                                 │
  └───────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─ Adapter ─────────────────────────────────────────────────────────┐
  │  CrtGateAdapter → Prediction.confidence for CONTRACT-A            │
  │  ResearchAdapter → full heads                                     │
  │  IdentityAdapter → pass-through for harnesses                     │
  │  FORBIDDEN without product decision: FusionEngine weight adapter  │
  └───────────────────────────────────────────────────────────────────┘
        │
        ▼
  Prediction  (and bitnet_score façade ≡ .confidence)
```

### 4.1 Layer contracts

#### 4.1.1 `IFeatureEncoder`

| Concern | Rule |
|---|---|
| **In** | `FeatureBag` (name→value) and/or dense vector + declared order |
| **Out** | `EncodedTensor` (float buffer, length = encoder.dim) + `EncodingMeta` |
| **Must** | Enforce identity list, order, `feature_order_hash`, normalize/quantize from artifact |
| **Must not** | Run neural weights, open files after `load`, apply CRT reject logic |
| **Fail** | Missing required key/id, NaN, dim/hash mismatch → hard error |

```text
IFeatureEncoder
  id() -> string                    # e.g. enc_legacy6_v1 | enc_canonical38_v1
  identities() -> FeatureIdentity[] # name + fm_id + formula_id?
  dim() -> int
  feature_order_hash() -> string
  encode(FeatureBag | FeatureVector) -> EncodedTensor
  load_params(envelope.normalization / encoder section) -> Result
```

**Concrete encoder profiles (design ids):**

| encoder_id | dim | Use |
|---|---|---|
| `enc_legacy6_v1` | 6 | CONTRACT-A parity with current `bitnet_score` keys |
| `enc_canonical38_v1` | 38 | CONTRACT-B / bitnet_v3 |
| `enc_export_ternary_v1` | per artifact | Historical export/cpp parity harness |

#### 4.1.2 `IBackbone`

| Concern | Rule |
|---|---|
| **In** | `EncodedTensor` only |
| **Out** | `Latent` (fixed latent_dim declared in metadata) |
| **Must** | Pure, deterministic matmuls / BitLinear / residual |
| **Must not** | Know feature names, labels, CRT thresholds, or trading |

```text
IBackbone
  id() -> string                 # e.g. bb_legacy_mlp_6_16_8_v1 | bb_bitlinear_res_v1
  latent_dim() -> int
  forward(EncodedTensor) -> Latent
  load_weights(envelope.backbone) -> Result
```

**Concrete backbone profiles (design ids):**

| backbone_id | Notes |
|---|---|
| `bb_legacy_mlp_6_16_8_v1` | Current production math: Linear→clip→Linear→clip (pre-output) |
| `bb_export_ternary_ff_v1` | Existing ternary export / cpp_runner style |
| `bb_bitlinear_res_v1` | CONTRACT-B BitLinear residual **family** — L1 frozen §5.2; numerics = L2 defaults profile |

#### 4.1.3 `IHeads`

| Concern | Rule |
|---|---|
| **In** | `Latent` |
| **Out** | `HeadOutputs` |
| **Required head for CRT path** | `confidence ∈ [0, 1]` |
| **Optional heads** | Only if declared in envelope; research until product decision |

```text
IHeads
  id() -> string
  head_names() -> string[]
  forward(Latent) -> HeadOutputs
  load_weights(envelope.heads) -> Result

HeadOutputs:
  confidence: float            # required when CRT-bound
  win_probability?: float
  expected_rr?: float
  embedding?: bytes | float[]
  extras?: map<string, float>
```

| heads_id | Heads |
|---|---|
| `hd_confidence_sigmoid_v1` | confidence only (CONTRACT-A) |
| `hd_multi_conf_win_rr_emb_v1` | CONTRACT-B multi-head |

#### 4.1.4 `IAdapter`

| Concern | Rule |
|---|---|
| **In** | `HeadOutputs` + optional raw/CRT feature context |
| **Out** | Consumer-facing `Prediction` (or scalar for façade) |
| **Must** | Own **all** serve-time key remaps (FM-027/028 → legacy names) as declared maps |
| **Must not** | Recompute neural forward; change latent math |

```text
IAdapter
  id() -> string
  adapt(HeadOutputs, context?) -> Prediction
  serve_maps() -> AdapterMap[]   # empty if identities already match

Adapter profiles:
  ad_crt_gate_v1       → Prediction.confidence for CONTRACT-A / bitnet_score
  ad_research_full_v1  → full heads exposed
  ad_identity_v1       → pass-through for unit/parity harnesses
  ad_fusion_neural_v1  → FORBIDDEN until product + Authority Ladder (not BitNet’s job today)
```

**CRT serve map (status quo, belongs on adapter metadata, not inside backbone):**

```text
ad_crt_gate_v1 maps (when feeding enc_legacy6 from CRT cache):
  displacement_retrace   (FM-027) → retest_depth   (legacy train key name)
  displacement_atr_ratio (FM-028) → disp_strength  (legacy train key name)
  atr_abs                → atr
```

Note: this map is **declared aliasing of values into legacy key slots**. CONTRACT-C forbids
claiming FM-027 ≡ FM-021; the map is a compatibility adapter only. New CRT-eligible
artifacts should encode true identities in the encoder and shrink the adapter map to empty.

### 4.2 Composition root: `IBitNetModel`

```text
IBitNetModel
  load(path | bytes, options) -> Result
  predict(features) -> Prediction
  metadata() -> Metadata

  # accessors for tests / parity
  encoder() -> IFeatureEncoder
  backbone() -> IBackbone
  heads() -> IHeads
  adapter() -> IAdapter
```

#### Prediction (minimum)

```text
Prediction:
  confidence: float          # REQUIRED for CRT; ∈ [0, 1]
  schema_version: string
  feature_dim: int
  feature_order_hash: string # empty only for declared legacy_6input
  encoder_id, backbone_id, heads_id, adapter_id: string
  heads: map<string, float>  # optional (CONTRACT-B)
  embedding: optional blob
  diagnostics: optional map  # non-authoritative
```

#### Metadata (minimum)

```text
Metadata:
  schema_version
  feature_dim
  feature_names[]
  feature_order_hash
  encoder_id / backbone_id / heads_id / adapter_id
  train_feature_identities[]     # CONTRACT-C
  label_contract_id              # CONTRACT-C
  economic_authority             # CONTRACT-C
  train_label_definition
  artifact_sha256
  instrument_scope
  created_at
```

### 4.3 Python façade (preserve existing callers)

```text
bitnet_score(features: dict) -> float
  ≡  default_IBitNetModel.predict(features).confidence
  MUST remain the CRT call-site entry point until an explicit migration.

Default composition for current production behavior:
  enc_legacy6_v1 + bb_legacy_mlp_6_16_8_v1
  + hd_confidence_sigmoid_v1 + ad_crt_gate_v1
```

### 4.4 Wiring recipes (allowed combinations)

| Recipe | Encoder | Backbone | Heads | Adapter | Contract |
|---|---|---|---|---|---|
| **Prod CRT (current)** | `enc_legacy6_v1` | `bb_legacy_mlp_6_16_8_v1` | `hd_confidence_sigmoid_v1` | `ad_crt_gate_v1` | A |
| **Research 38 multi-head** | `enc_canonical38_v1` | `bb_bitlinear_res_v1` | `hd_multi_conf_win_rr_emb_v1` | `ad_research_full_v1` | B (+ C) |
| **CRT via 38 (future)** | `enc_canonical38_v1` | `bb_bitlinear_res_v1` | multi or conf-only | `ad_crt_gate_v1` | B→A adapter; needs enable gates |
| **C++ parity harness** | `enc_export_ternary_v1` | `bb_export_ternary_ff_v1` | conf/raw | `ad_identity_v1` | harness only |

Illegal combinations (examples):

- CRT adapter on artifact with `economic_authority=DIAGNOSTIC_ONLY` for production enable  
- Backbone that reads feature names  
- Adapter that mutates weights  
- Fusion adapter without separate product authorization  

### 4.5 C++ interface sketch (design only — **not** an implementation mandate)

```cpp
// Design sketch only. No C++ implementation is authorized by Spec v1 acceptance.

struct FeatureIdentity {
  std::string name;
  std::string fm_id;
};

struct EncodedTensor { std::vector<float> data; int dim; };
struct Latent        { std::vector<float> data; int dim; };

struct HeadOutputs {
  float confidence;
  // optional heads omitted in sketch
};

struct Prediction {
  float confidence;                 // [0, 1]
  std::string schema_version;
  std::string encoder_id, backbone_id, heads_id, adapter_id;
};

struct Metadata { /* §4.2 fields */ };

class IFeatureEncoder {
public:
  virtual EncodedTensor encode(/* FeatureBag or FeatureVector */) const = 0;
  virtual int dim() const = 0;
  virtual std::string id() const = 0;
  virtual ~IFeatureEncoder() = default;
};

class IBackbone {
public:
  virtual Latent forward(const EncodedTensor&) const = 0;
  virtual std::string id() const = 0;
  virtual ~IBackbone() = default;
};

class IHeads {
public:
  virtual HeadOutputs forward(const Latent&) const = 0;
  virtual std::string id() const = 0;
  virtual ~IHeads() = default;
};

class IAdapter {
public:
  virtual Prediction adapt(const HeadOutputs&) const = 0;
  virtual std::string id() const = 0;
  virtual ~IAdapter() = default;
};

class IBitNetModel {
public:
  virtual bool load(const std::string& path) = 0;
  virtual Prediction predict(/* features */) const = 0;
  virtual Metadata metadata() const = 0;
  virtual ~IBitNetModel() = default;
};
```

### 4.6 Invariants (all layers)

1. **Pure inference** after `load`: no I/O, no global mutation, no config writes in encode/forward/adapt.  
2. **Deterministic** given same weights + same encoded input (documented float tolerance).  
3. **Fail-closed dims / hash** — no silent slice.  
4. **No NaN in** at encoder boundary.  
5. **CRT scalar path** always exposes `confidence ∈ [0,1]` via adapter.  
6. **Evidence only** — no orders, sizing, or planner bypass.  
7. **Single responsibility** — Encoder≠Backbone≠Heads≠Adapter.  
8. **CONTRACT-C join** — CRT-eligible load requires train identities ≡ encoder identities.

### 4.7 What Phase 2 authorizes next (still not C++)

| Allowed after hierarchy acceptance | Still forbidden |
|---|---|
| Python ABC / Protocol stubs + tests of composition wiring | C++ BitNet.cpp rewrite |
| Refactor `bitnet_score` façade to call composition **byte-identical** | Changing reject set / enable flag |
| Document envelope fields for hierarchy ids | Production retrain without CONTRACT-C compliance |
| Parity harness alignment plan | Fusion wiring |

**Recommended next engineering step (optional):** Python Protocols for the four layers +
a `LegacyComposition` that preserves current `bitnet_score` outputs byte-identical —
still **no** C++.

---

## 5. Neural architecture

### 5.1 CONTRACT-A reference architecture (current, frozen as behavior baseline)

**backbone_id:** `bb_legacy_mlp_6_16_8_v1` (unchanged by v1.2)

```text
Input 6 → Linear 16 → clip[-1,1] → Linear 8 → clip[-1,1] → Linear 1 → sigmoid
~233 weights; JSON legacy_6input
```

v1.2 does **not** migrate CRT off this path.

---

### 5.2 CONTRACT-B backbone family — `bb_bitlinear_res_v1` (**design frozen · numerics = defaults**)

**Architecture family is FROZEN (L1).**  
**Numeric sizes and budgets are versioned defaults (L2)** — see §0.1 and §5.2.6.

Family id: `bb_bitlinear_res_v1`  
Current defaults profile: **`bitlinear_res_defaults_v1`** (Spec v1.2.1)

#### 5.2.1 Design goals

| Goal | Tier | Statement |
|---|---|---|
| Role | L1 | Shared trunk for CONTRACT-B multi-head; CRT only via adapter later |
| Hardware intent | L1 | CPU-first, no GPU requirement for the family |
| Determinism | L1 | Pure function after load |
| Fit | L1 | Ternary W + float scale family (export-spirit compatible) |
| Speed / memory | **L2** | Guidance under defaults profile — not constitutional hard-fail laws |

#### 5.2.2 Topology family (**L1 architecture law**)

Structural pattern (dimensions written symbolically; concrete numbers in §5.2.6):

```text
EncodedTensor x ∈ R^{D_in}     # D_in from encoder (canonical: 38)
        │
        ▼
  BitLinear_in : D_in → H      # projection (no residual; dim change)
  act = hardtanh / clip[-1, 1]
        │
        ▼  h0 ∈ R^{H}
  ResidualBlock × N_res        # same width H
        │   each block:
        │     u = BitLinear_1 (H → H)
        │     u = act(u)
        │     u = BitLinear_2 (H → H)
        │     u = act(u)
        │     h ← act(h + u)     # post-act residual; no LayerNorm
        ▼  h ∈ R^{H}
  BitLinear_lat : H → L
  act = hardtanh / clip[-1, 1]
        │
        ▼
  Latent z ∈ R^{L}             # SINGLE attachment point for all Heads
```

| Structural rule (L1) | Law |
|---|---|
| Stage order | project-in → residual stack → project-to-latent |
| Residual F | exactly **two** BitLinears with act after each, then residual add + act |
| Stage-wise heads | **Forbidden** in this family |
| Head attachment | **Final latent only** |
| Encoder coupling | `D_in` MUST equal encoder dim (canonical path: 38) |

#### 5.2.3 BitLinear + quantization (**L1**, with one L2 default)

| Item | Tier | Rule |
|---|---|---|
| Weight type | L1 | **Ternary** \(w \in \{-1, 0, +1\}\) |
| Scale | L1 | **Per-output-channel float32** |
| Matmul | L1 | \( y = (W_{ternary} \cdot x) \odot s + b \) |
| Activation storage | L1 | **float32** activations (weight-only quant in this family) |
| Bias present | **L2** | Default **true**; may be false if envelope declares `bias: false` |
| Packing | L3/impl | Bit-pack optional; logical ternary required |

Binary-only \(\{-1,+1\}\) without zero is **out of family** (legacy export recipe only).

#### 5.2.4 Activation & residual pattern (**L1**)

| Item | Law |
|---|---|
| Activation | Hardtanh / clip to \([-1, 1]\) after every BitLinear |
| Residual | Post-act: \(h \leftarrow \mathrm{act}(h + F(h))\) |
| Backbone norm | **No** LayerNorm / BatchNorm / RMSNorm in this family |
| Input norm | Encoder only (CONTRACT-C) |

Adding backbone LayerNorm is a **new architecture family**, not an L2 default tweak.

#### 5.2.5 Latent & head attachment (**L1** + L2 sizes)

| Item | Tier | Rule |
|---|---|---|
| Single latent vector | L1 | Yes — one \(z\) |
| Heads on final latent only | L1 | Yes |
| Confidence head form | L1 | `Linear_fp32(L → 1) → sigmoid` → \(c \in [0,1]\) |
| Optional heads form | L1 | float32 linears on \(z\) (not ternary) |
| Latent dim \(L\) | **L2** | Default 32 (profile) |
| Embedding dim \(E\) | **L2** | Default 0 (off); profile suggests 16 if enabled |
| Temperature | L2/Adapter | Default 1.0; not part of residual topology |

CRT threshold remains config `bitnet_main_threshold` (CONTRACT-A).

#### 5.2.6 Versioned defaults profile — `bitlinear_res_defaults_v1` (**L2**)

These values **instantiate** the family for the first implementation and as the documented
starting point. They are **not** immutable architectural laws. Changing them requires:

1. A new `defaults_profile` id (e.g. `bitlinear_res_defaults_v2`), **or** an artifact that
   simply declares different numerics under the same family id, and  
2. Envelope self-description (§5.2.9) so loaders never assume H=64.

| Parameter | Default (profile v1) | Notes |
|---|---|---|
| `D_in` | **38** | Locked to `enc_canonical38_v1` when using that encoder |
| `H` (hidden) | **64** | Width of residual stack |
| `L` (latent) | **32** | Head input size |
| `N_res` | **2** | Residual block count |
| BitLinear count | \(1 + 2 N_{res} + 1\) | **6** under default N_res |
| `bias` | **true** | Per BitLinear out-channel |
| `embedding_dim` | **0** (off) | Use 16 only if research enables emb head |
| Dropout in backbone | **0** | |

**Derived counts under defaults v1 (illustrative, not law):**

| Layer | Shape | Ternary elements |
|---|---|---|
| BitLinear_in | 64 × 38 | 2 432 |
| Res ×2 ×2 | 4 × (64 × 64) | 16 384 |
| BitLinear_lat | 32 × 64 | 2 048 |
| **Total** | | **20 864** |

**Guidance budgets (L2 — review targets, not automatic reject laws):**

| Guidance | Default v1 target |
|---|---|
| Ternary elements | ~21k; keep “small” (order 10⁴–10⁵) |
| Float params (scale+bias+heads) | order 10³ |
| Serialized working set | prefer ≤ 256 KiB; review if ≫ 1 MiB |
| Latency (38→latent, CPU) | prefer ≤ 50 µs typical; investigate if ≫ 1 ms |

Exceeding guidance → **engineering review + documented defaults_profile bump**, not an automatic
“unconstitutional” failure. Economic authority remains Phase 5–6 only.

**Train hyper-recommendations (L2, non-binding):**

| Hyperparameter | Default recommendation |
|---|---|
| Optimizer | AdamW |
| LR | 1e-3 (search allowed) |
| Weight decay | 1e-4 on float scale/head |
| STE vs PTQ | OPEN (L3); serve must be ternary |
| Epochs / batch | OPEN; CONTRACT-C logs them |

#### 5.2.7 Changing numerics (allowed path)

```text
OK (still bb_bitlinear_res_v1 family):
  H=128, L=64, N_res=3  IF envelope declares dims + defaults_profile
  and L1 pattern unchanged

NOT OK (new family required):
  add LayerNorm in backbone
  attach heads to intermediate residuals
  switch to FP16 dense Linear-only trunk without ternary
  binary-only weights without ternary zero
  put reject threshold inside backbone
```

Family id stays `bb_bitlinear_res_v1` while L1 holds. Optional: stamp
`backbone_variant: "H128_L64_N3"` for humans; **machine truth is envelope dims**.

#### 5.2.8 Serialization (self-describing — **required**)

Loaders MUST read numerics from the artifact, never hardcode defaults as sole truth.

```text
backbone:
  id: "bb_bitlinear_res_v1"              # L1 family
  defaults_profile: "bitlinear_res_defaults_v1"  # L2 profile used at train (or "custom")
  input_dim: <D_in>                      # REQUIRED actual
  hidden_dim: <H>                        # REQUIRED actual
  latent_dim: <L>                        # REQUIRED actual
  n_residual_blocks: <N_res>             # REQUIRED actual
  activation: "hardtanh_m1_p1"           # L1
  residual: "post_act_add"               # L1
  layernorm: false                       # L1
  quantization: "ternary_per_out_scale"  # L1
  bias: <bool>
  stages: [ ... shapes MUST match declared H/L/N_res ... ]
```

Heads remain a **sibling** envelope section. Head `in_features` MUST equal `latent_dim`.

Under **defaults v1**, stages are 38→64, four 64→64, 64→32 — but any declared consistent set is valid.

#### 5.2.9 Product / process still OPEN (L3)

| Item | Status |
|---|---|
| CRT long-term 6 vs 38 cutover | OPEN |
| STE vs PTQ | OPEN |
| Per-instrument vs global | OPEN |
| Enable / ΔG001 | OPEN |
| Phase 2b Python code | DEFERRED |

#### 5.2.10 One-pager

```text
FAMILY bb_bitlinear_res_v1 (L1 FROZEN)
  pattern: Din→H → Res×N_res@H → L=latent; heads on latent only
  Res: act(h+F), F=BL→act→BL→act; act=clip[-1,1]
  W ternary + float scale; no backbone LN

DEFAULTS bitlinear_res_defaults_v1 (L2 — not laws)
  Din=38, H=64, L=32, N_res=2, bias=true, emb=0
  guidance: ~21k ternary, ≤256KiB prefer, ≤50µs prefer

CHANGE NUMERICS: declare in envelope + profile id
CHANGE STRUCTURE: new architecture family
```

---

### 5.3 Explicit non-goals (still)

- Do not replace TradeNet’s 3-head TP/BE semantics inside BitNet.
- Do not put BitNet into `EXPECTED_ENGINES`.
- Do not enable by default.
- Do not treat design freeze as authorization to train or ship C++.
- Do not change CONTRACT-A legacy MLP without behavior-change approval.
- Do not re-open design workshops for H/L/N_res — bump L2 profile or declare custom dims.

---

## 6. Training pipeline

**Authoritative rules:** **CONTRACT-C (§2)**. This section is a pointer only.

| Topic | See |
|---|---|
| Identity lock / F-050 | C.1 |
| Population / labels / loss / splits | C.2–C.5 |
| Export envelope + registry | C.6–C.7 |
| Status-quo diagnostic label | C.3 `BITNET_LABEL_ATR_RACE_BULL_V1` |

Implementation of a new trainer remains **out of scope** until a separate task authorizes
retrain under CONTRACT-C. Hierarchy component ids (`encoder_id` / `backbone_id` / `heads_id`)
MUST be written into the export envelope at train time.

---

## 7. Serialization format

### 7.1 Accepted schemas (existing)

| schema | Dim | Notes |
|---|---|---|
| `legacy_6input` | 6 | CRT `bitnet_score` path today |
| `bitnet_export_v1` | varies | Legacy bridge + integrity event |
| `bitnet_v3` | 38 | Canonical envelope in `model_contract.py` |

### 7.2 Rules

- Loaders **never** silently reinterpret `feature_dim` (`model_contract.normalize_loaded`).
- New multi-head / BitNet.cpp weights MUST ship as a **versioned** envelope including the
  **self-describing** backbone fragment (§5.2.8) when family id is `bb_bitlinear_res_v1`.
- Loader MUST reject: missing dims, stage shapes ≠ declared H/L/N_res, `layernorm:true`,
  non-ternary quant for this family, or stage-wise head weights inside backbone (L1 violations).
- Loader MUST **not** reject merely because H/L/N_res ≠ defaults v1 (64/32/2) if L1 holds and
  dims are declared (L2 is not a hard gate).
- Artifact SHA-256 recorded in registry on any promote attempt.

---

## 8. Runtime API and CRT / Fusion integration

### 8.1 CRT integration (only path that matters for production risk)

```text
Feature cache at RETEST
  → (optional) CrtServeAdapter
  → IBitNetModel.predict
  → confidence
  → if use_bitnet and confidence < bitnet_main_threshold:
        REJECT LOW_SCORE
  → else continue soft confirmation
```

Config keys (behavioral, already present):

| Key | Section | Active value | Meaning |
|---|---|---|---|
| `use_bitnet` | crt_engine | **false** | Master enable |
| `bitnet_main_threshold` | crt_engine / params | **0.55** | Hard reject cutoff |

### 8.2 Fusion integration

**BitNet is not a fusion engine.**  
`EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}`.  
Do not add BitNet to fusion weights without a **new** product decision and Authority Ladder evidence.

### 8.3 Relation to TradeNet

| | BitNet | TradeNet |
|---|---|---|
| Question | State acceptable? | Outcome probabilities if entered? |
| Dim (intent) | 6 (A) / 38 (B aspirational) | 38 |
| Heads | 1 confidence (A) | p_tp1, p_tp2, p_survives_be |
| Spine | CRT veto socket | Fusion `neural_fn` socket (**unwired**) |
| Status | INERT (flag off) | UNWIRED (F-005) |

---

## 9. Test plan

### 9.1 Contract tests (required before any enable)

| ID | Test | Pass criterion |
|---|---|---|
| T-A1 | Hard keys present → score ∈ [0,1] | Always |
| T-A2 | Missing key → raises | Fail-fast preserved |
| T-A3 | Determinism | Same input → same score (atol e.g. 1e-6) |
| T-A4 | Threshold reject | score 0.54 / thr 0.55 → LOW_SCORE when enabled |
| T-A5 | `use_bitnet=false` | Zero BitNet calls / no reject from BitNet |
| T-A6 | Adapter map | FM-027/028 → legacy keys documented + unit-tested |
| T-B1 | 38-dim hash | feature_order_hash matches schema |
| T-B2 | Dim mismatch | fail-closed |
| T-H1 | Layer SR | Encoder does not load backbone weights; adapter does not matmul latent |
| T-H2 | Composition | Default recipe scores match legacy `bitnet_score` (byte-identical or atol) |
| T-H3 | Illegal combo | CRT production load rejects DIAGNOSTIC_ONLY economic_authority |
| T-CXX | C++/Python parity | Only after C++ exists: max abs error bound on same weights |
| T-P1 | Existing suite | `tests/test_bitnet_inference.py`, `tests/test_bitnet_parity.py` green |

### 9.2 CONTRACT-C / economic tests

| ID | Test | Pass criterion |
|---|---|---|
| T-C1 | label_contract_id present | Every export stamps id + economic_authority |
| T-C2 | Identity lock | train_feature_identities == encoder.identities (order + fm_id) |
| T-C3 | No silent alias | Serve maps listed in adapter metadata when keys remapped |
| T-E1 | Train/serve identity | Same FM-ids train and serve; no F-050 class skew for CRT-eligible |
| T-E2 | Shadow A/B | Book-level ΔG001 (or declared equivalent) on majors |
| T-E3 | Authority Ladder | Only **positive** measured benefit may justify enable |
| T-E4 | Prior | F-055 non-improving baseline — new model must beat OFF |

### 9.3 Non-tests (do not use as production gates)

- In-sample accuracy on ATR-race labels alone.
- “Looks like BitNet architecture” branding.
- Presence of C++ code without contract tests.

---

## 10. Governance and promotion criteria

### 10.1 Authority ladder (from CLAUDE.md §6.5)

```text
Information exists  ≠  Economic usefulness  ≠  Authority  ≠  Architecture justified
```

| Action | Minimum evidence |
|---|---|
| Keep dormant | Default (current) |
| Shadow-measure | Research config only; no ACTIVE_VERSION change |
| Retrain | **CONTRACT-C** complete export + identity lock + registry entry |
| Enable `use_bitnet` on active | CONTRACT-C `CRT_ELIGIBLE_CANDIDATE` + shadow ΔG001 positive + user approval (+ ValidationReport if config promote) |
| Replace CONTRACT-A with CONTRACT-B on CRT | Behavior-change authorization + `ad_crt_gate_v1` parity or versioned migration |
| Write C++ BitNet.cpp | Design frozen (**yes**) + explicit Phase-3 task still required |
| Change H/L/N_res (same family) | L2: declare dims + `defaults_profile` / custom — **allowed** |
| Change quant family / residual pattern / add LN | L1: **new architecture family** — not a silent edit |

### 10.2 Related findings (do not silently reverse)

| Id | Binding claim |
|---|---|
| F-004 | Gate real when enabled; **inert** on active (`use_bitnet:false`) |
| F-050 | Train/serve name collision post-CH-002 |
| F-055 | Enabling **existing** model did not improve majors book |

### 10.3 Completion gates for this program

| Phase | Exit criterion | Status |
|---|---|---|
| **0 Contract freeze** | A + B + C frozen; user accept | **DONE** |
| **1 Inventory** | §3 diagram + artifact table match code | **DONE** |
| **2 Interface hierarchy** | Encoder→Backbone→Heads→Adapter designed | **DONE** |
| **2★ Backbone family (v1.2)** | L1 structural family frozen | **DONE** |
| **2★★ Defaults tier (v1.2.1)** | Numerics = versioned defaults, not laws | **DONE** |
| **2b Optional Python Protocols** | Byte-identical façade / reference impl | **DEFERRED** (user: not yet) |
| **3 Implementation** (C++ or other) | Behind hierarchy + §5.2; explicit task | **Not authorized** |
| **4 Training** | CONTRACT-C + frozen backbone shapes | **Not authorized** |
| **5 Shadow evaluation** | ΔG001 / T-E* | Not started |
| **6 Production promote** | Evidence + user approval | Not started |

### 10.4 Explicit STOP conditions

- Any rewrite that changes CRT reject set without measured ΔG001.
- Enabling without train/serve identity fix when claiming new model quality.
- Conflating ZoneGate / TradeNet / LLM BitNet 3B with this gate.
- “Just ship BitNet.cpp” without CONTRACT-A / hierarchy preservation.
- Training without CONTRACT-C envelope fields or with silent FM aliasing.
- Putting neural logic in Adapter or reject logic in Backbone.

---

## 11. Recommended execution order (reaffirmed)

| Phase | Action | Code? | Status |
|---|---|---|---|
| **v1.1 / 0–2** | Contracts A+B+C + hierarchy | No | **DONE** |
| **v1.2** | Backbone **family** L1 freeze | No | **DONE** |
| **v1.2.1** | Numerics demoted to L2 versioned defaults | No | **DONE** |
| **2b** | Python interfaces / reference impl | Optional | **DEFERRED** |
| **3** | Implementation (C++ / Python / ONNX) | Yes | Not authorized |
| **4** | Training under CONTRACT-C + declared dims | Yes | Not authorized |
| **5** | Shadow evaluation (ΔG001) | Yes | Later |
| **6** | Production promote | Config + evidence | Only if earned |

### Phase transition (v1.2.3 — binding belief)

| Before | After |
|---|---|
| Bottleneck: **architecture uncertainty** | Bottleneck: **evidence uncertainty** |
| Work type: software design / contracts | Work type: **ML research** (labels, data, identity, eval) |
| Success metric: workable decomposition | Success metric: fair experiments + economic shadow |

```text
Problem definition     ✅ Mature
Architecture           ✅ Mature
Contracts A/B/C        ✅ Mature  (C is the research load-bearing piece)
Runtime platform       ✅ Mature  (not a validated model)
Training system        🟡 R1 next
Learned weights        ❌ Unknown
Economic value         ❌ Unknown
```

**Most valuable remaining artifact:** **CONTRACT-C** — without it, A vs B comparisons mix data/labels/norm/features and are meaningless. With it, experiments are comparable science, not trial-and-error.

**Current recommendation (conf 10/10):**

```text
Architecture / contracts / Python platform   ✅ STOP refining
Weights / learning                           ❌ only training answers
Legacy vs BitLinearRes offline               ❌ not started
Economic (shadow ΔG001)                      ❌ not started
C++ / optimize                               ⏸ after evidence only
```

Do **not** open architecture workshops. Do **not** jump to C++.  
Train **before** optimize. Labels/data/identity/eval methodology ≫ more design.

**Project nature (v1.2.4):**

```text
Before:  "Can we design a good BitNet?"
Now:     "Can a well-defined BitNet earn its place through evidence?"
```

BitNet is a **research program** hosted on a frozen platform — not an architecture project.

#### Evidence stages (governance — do not conflate)

A model may pass one stage and fail another. **Scientific validity ≠ economic validity ≠ operational readiness.**

| Stage | Question | Evidence required | Authority granted if pass |
|---|---|---|---|
| **R0** | Is the platform executable? | Composition tests, façade parity | Research runtime only |
| **R1** | Can we train **reproducibly**? | **CONTRACT-C** + complete `model.bundle` + reload | Auditable pipeline — **not** usefulness |
| **R2** | Can it **learn** (metrics)? | Holdout loss/AUC/calibration under same contract | Scientific interest only |
| **R2.5** | Can we **falsify** “learns something useful”? | Kill-test suite (§11 R2.5); shuffle/constant **must fail** | Only then earn R3 |
| **R3** | Better than **legacy**? | Strict offline A/B (same data/labels/split/metrics; backbone only) | Relative offline claim only |
| **R4** | Improve **trading**? | Shadow / book-level economics (ΔG001 class) | Economic research claim; still no enable |
| **R5** | **Production-worthy** ops? | Latency, memory, reliability | Operational readiness only |
| **R6** | **Enable** it? | Product + governance (§6.5, user, config) | `use_bitnet` / promote — only here |

#### What R1 proves vs does not (v1.2.5 — binding)

```text
R1 PROVES (engineering reproducibility):
  CSV → FeaturePipeline → Label contract → Train → Quantize
    → Bundle → Reload → Inference
  Same machinery for every future experiment.

R1 DOES NOT PROVE:
  labels are economically meaningful
  model learns useful representations
  BitLinearRes ≻ legacy MLP
  production should change
```

**Anti-pattern (highest risk now):** declaring success because R1 exists.

| Step | Action | Status |
|---|---|---|
| R0 | Python runtime platform | **DONE** |
| R1 | CONTRACT-C trainer + model.bundle | **DONE** (reproducibility only) |
| R2 | ML metrics under contract | Partial (bundle `metrics.json`); deepen as needed |
| **R2.5** | **Kill-test** (try to falsify learning) | **Harness shipped** — run on real data before R3 |
| R3 | Offline legacy vs BitLinearRes (backbone only) | Only if R2.5 **PASS** |
| R4 | Shadow / book-level economics | Only if R3 = **PROMOTE_TO_SHADOW** |
| R5 | Ops / C++ if needed | After R4 if earned |
| R6 | Production enable | Explicit product decision only |

**Anti-patterns:** green composition = quality; R1 bundle = useful model; confirmation bias after sunk cost; R2 metrics = edge; R3 offline = live P&amp;L; R5 latency = enable.

#### R2.5 — Kill-test (falsification before promotion)

**Design intent:** after heavy investment, guard **confirmation bias**.  
Question is not “find evidence it works” but:

> **Can we prove this model is *not* learning anything useful?**

If it **survives** the kill-tests, it **earns R3**. Otherwise investigate pipeline — do **not** R3.

| Test | Purpose | Pass criterion |
|---|---|---|
| Training convergence | Optimization reduces loss | Loss decreases and stabilizes; no NaN |
| Holdout &gt; random | Predictive signal exists | Better than pre-registered chance baseline |
| Calibration | Probabilities meaningful | Calibration error within pre-set bound |
| Prediction collapse | Not one-class constant | Healthy output distribution (std/entropy floor) |
| Seed stability | Reproducible training | Similar metrics across seeds (pre-set band) |
| Feature ablation | Key features matter | Sensible degradation when ablated |
| **Label shuffle (kill)** | “Learn” random labels? | **Must fail** (no real holdout skill on shuffled y) |
| **Constant-feature (kill)** | Invent signal from noise? | **Must fail** (no skill when features constant/noise) |

The **last two are load-bearing.** If the model still looks good under shuffled labels or constant features → leakage, eval bug, or broken pipeline (investigate; **R2.5 FAIL**).

Pre-register numeric thresholds **before** looking at results. Document in `evaluation_report.json` stage=`R2.5`.

```text
R2.5
   │
   ├── FAIL  →  investigate pipeline / labels / eval  (no R3)
   │
   └── PASS  →  R3 only
```

#### R3 — Strict offline comparison + binary economic-path gate

Both arms **must** share identical: feature pipeline/identities, `label_contract_id`, train/holdout split, metrics.  
**Only the backbone (exported weights) changes.**

```text
Legacy MLP
      │
      ▼
BitLinearRes
      │
      ▼
Difference significant?  (pre-registered test)
      │
 ┌────┴────┐
No        Yes
 │         │
STOP    (consider PROMOTE_TO_SHADOW
         only if also operationally acceptable to try R4)
```

No ambiguous “maybe continue because we invested.”

#### R3 conclusions — only three outcomes

At end of R3, **exactly one** of:

| Outcome | Meaning |
|---|---|
| **PROMOTE_TO_SHADOW** | Evidence supports R4 shadow (economic) evaluation |
| **RETRAIN_REVISE** | Pipeline OK (R2.5 passed); model needs improvement — not R4 yet |
| **STOP** | No measurable advantage over legacy — end BitLinearRes track on this contract |

Sunk-cost bias is not a fourth outcome.

#### Gate document after R3: `BitNet Evaluation Report v1`

Not code — this report is the sole R3→R4 authority artifact:

```text
BitNet Evaluation Report v1
  Legacy MLP  vs  BitLinearRes
  Same data / labels / metrics / split
  R2.5 kill-test summary (must be PASS)
  → Winner? By how much?
  → Statistically significant? (pre-registered)
  → Operational cost?
  → Recommendation: PROMOTE_TO_SHADOW | RETRAIN_REVISE | STOP
```

#### `model.bundle` (required from R1 onward)

Trainer MUST NOT emit “weights only.” Every run produces a **portable, reproducible, auditable package**:

```text
model.bundle/   (directory or zip; name may include version + instrument + ts)
├── envelope.json              # self-describing backbone + heads + encoder (serve load)
├── weights.bin                # optional packed weights; or inlined in envelope for small models
├── metadata.json              # population, defaults_profile, instrument_scope, created_at
├── feature_schema.json        # feature_names, order hash, train_feature_identities (FM-ids)
├── label_contract.json        # label_contract_id, definition, economic_authority, timeout policy
├── metrics.json               # R2-class ML metrics (NOT ΔG001; never enable authority)
├── training_manifest.json     # dataset fingerprint, optimizer, epochs, seed, preprocess + software versions
├── evaluation_report.json     # exact offline/shadow eval that justified advancing a stage (filled as stages run)
└── sha256.txt                 # hashes of the above files
```

| File | Minimum content |
|---|---|
| `training_manifest.json` | dataset fingerprint/hash, split policy, optimizer, LR schedule, epochs, batch, random seed, preprocessing versions, git commit / package versions, backbone defaults_profile |
| `evaluation_report.json` | stage id (R2/R3/R4…), protocol id, baselines compared, metrics table, data window, pass/fail vs pre-registered criteria, links to result paths |

Load path: `envelope.json` (+ weights) via composition loader; reject incomplete bundles (missing label_contract, feature identities, training_manifest, or sha).  
`evaluation_report.json` may be partial after R1 (train-only) and **must be updated** before claiming R3/R4 advancement.

---

## 12. Open questions (empirical / product — design closed)

1. **First train label:** `BITNET_LABEL_ATR_RACE_BULL_V1` (diagnostic) vs `forward_walk` CRT-eligible candidate?
2. **Population:** which instruments / window for first BitLinearRes train?
3. **Offline success metric** before shadow (not “loss only” — define before R3).
4. **CRT long-term:** stay on 6-feat legacy gate vs 38-dim family cutover (product).
5. STE vs PTQ for ternary (implementation detail at R1/R2).

H/L/N_res remain L2 defaults, not design blockers.

---

## 13. Document control

| Item | Value |
|---|---|
| Spec id | BITNET-CPP-SPEC-V1 |
| Revision | **v1.2.6** (R2.5 kill-test; R3 three outcomes only; anti-confirmation-bias) |
| Supersedes | soft “sanity check” framing of R2.5 |
| Does not supersede | F-004 / F-050 / F-055 / bitnet_lineage_audit |
| Implementation authority | **None** until explicit Phase 2b/3/4 task |
| Related plans | `make-bitnet-trained-as-abstract-shell.md` |

**Change policy:**  
- **L1** structure → new architecture family id.  
- **L2** numerics → new `defaults_profile` and/or declared envelope dims (self-describing).  
- **L0** contracts → dated migration section + authority.

---

## Appendix A — CONTRACT-A one-pager (copyable freeze)

```text
BITNET_CONTRACT_A_V1 (PRODUCTION CRT GATE)
  inputs:
    body_ratio, retest_depth, disp_strength,
    atr, candles_since_retest, double_sweep
  missing_key: fail-fast
  output: confidence in [0, 1]
  pure: yes (score function)
  consumer: UltronRiskEngine.approve_with_soft_conf when use_bitnet
  reject: confidence < bitnet_main_threshold (default 0.55) → LOW_SCORE
  active_enable: false on v2_multi_2026_04
  role: optional veto / evidence — not fusion, not planner, not TradeNet
  default_composition:
    enc_legacy6_v1 + bb_legacy_mlp_6_16_8_v1
    + hd_confidence_sigmoid_v1 + ad_crt_gate_v1
```

## Appendix B — CONTRACT-C one-pager

```text
BITNET_CONTRACT_C_V1 (TRAINING)  — see §2 C.8 full text
  train_feature_identities == serve encoder identities
  label_contract_id + economic_authority required
  ATR-race status quo = DIAGNOSTIC_ONLY
  retrain ≠ enable
```

## Appendix C — Hierarchy one-pager

```text
IFeatureEncoder  → EncodedTensor   (identities, normalize, fail-closed)
IBackbone        → Latent          (pure neural; no feature names)
IHeads           → HeadOutputs     (confidence required for CRT)
IAdapter         → Prediction      (serve maps; CRT façade)
IBitNetModel     = composition root (load / predict / metadata)
bitnet_score(f)  ≡ model.predict(f).confidence
```

## Appendix D — Backbone one-pager

```text
L1 FAMILY bb_bitlinear_res_v1 (FROZEN design)
  Din→H → Res×N_res@H → L latent; heads on latent only
  Res: act(h+F); F=BL→act→BL→act; act=clip[-1,1]
  ternary W + float scale; no backbone LN

L2 DEFAULTS bitlinear_res_defaults_v1 (not laws)
  Din=38 H=64 L=32 N_res=2 bias=true emb=0
  guidance ~21k ternary / prefer ≤256KiB / prefer ≤50µs
  retune via envelope dims + defaults_profile bump
```

## Appendix E — Phase checklist

- [x] Phase 0 contract freeze (A + B + C)
- [x] Phase 1 inventory
- [x] Phase 2 hierarchy design
- [x] **v1.2 backbone family** (L1)
- [x] **v1.2.1 numerics as versioned defaults** (L2)
- [x] **Design freeze** — stop architecture accretion
- [x] Phase 2b/3 **Python reference runtime** (2026-07-21)
- [x] **PARK architecture** (v1.2.4) — research program; evidence stages R1–R6 separated
- [x] **R1 trainer** (2026-07-22) — reproducibility only; not usefulness
- [x] **R2.5 kill-test harness** (2026-07-22): `src/bitnet/r25_kill_test.py`,
  CLI `scripts/research/bitnet_r25_kill_test.py`, thresholds `r25_thresholds_v1`,
  tests `tests/test_bitnet_r25_kill_test.py`. Label-shuffle + constant-feature kill tests.
  PASS = `PASS_EARN_R3` only (no enable).
- [ ] R2.5 run on governed CSV population (not only synthetic smoke)
- [ ] R3 offline → Evaluation Report v1 → PROMOTE_TO_SHADOW \| RETRAIN_REVISE \| STOP
- [ ] R4 shadow · R5 ops · R6 enable
