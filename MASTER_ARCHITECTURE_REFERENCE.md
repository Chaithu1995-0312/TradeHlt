# MASTER ARCHITECTURE REFERENCE

> **Consolidated reference document combining all existing authoritative documentation into a single navigable source.**  
> This document stitches together existing docs with provenance markers. It is NOT a summary or rewrite — it is an assembly of existing documentation for distribution to other LLMs.

---

## TABLE OF CONTENTS

1. [System Overview](#1-system-overview)
2. [Three Authority Architecture](#2-three-authority-architecture)
3. [market_ontology.yaml](#3-market_ontologyyard)
4. [active_models.yaml](#4-active_modelsyaml)
5. [Runtime Pipeline](#5-runtime-pipeline)
6. [Feature Lineage](#6-feature-lineage)
7. [Consumer Mapping](#7-consumer-mapping)
8. [Governance](#8-governance)
9. [Current Findings](#9-current-findings)
10. [Appendix](#10-appendix)

---

# 1. SYSTEM OVERVIEW

---

## Source: `docs/reference/architecture.md`

### 1.1 Tech Stack

| Layer              | Library / Tool                     | Version / Source                                                      |
| ------------------ | ---------------------------------- | --------------------------------------------------------------------- |
| Language           | Python                             | `>=3.10` (pinned in `pyproject.toml`)                                 |
| Build backend      | setuptools                         | `>=68` (legacy backend)                                               |
| Packaging          | `pyproject.toml` only              | No `requirements.txt`, no `setup.py`                                  |
| Data / numerics    | pandas, numpy, scipy               | imported across `src/features`, `src/runtime`, `src/engines`          |
| ML / training      | scikit-learn, torch (PyTorch)      | `src/training/trainer.py`, `src/engines/ml_gaussian_engine.py`        |
| Local LLM          | llama-cpp-python (GGUF)            | Consumed via `src/config_layer/llm_inference_client.py` → local HTTP server |
| BitNet inference   | `src/bitnet/bitnet_inference.py`   | GGUF model at `models/bitnet_b1_58_70b.gguf`                          |
| Fallback LLM       | Groq API                           | Key in `.env` → `GROQ_API_KEY`                                        |
| HTTP control plane | `http.server.ThreadingHTTPServer`  | `src/control_plane/server.py` (stdlib only — no FastAPI)              |
| Tests              | pytest                             | `pyproject.toml` → `testpaths = ["tests"]`, `pythonpath = ["src","scripts"]` |
| Persistence        | JSON files + JSONL append-only logs | `configs/production/*.json`, `configs/promotion_log.jsonl`, `logs/*.jsonl` |
| Cache / Queue      | None                               | In-memory only (`core/feature_store.py`)                              |
| Auth               | None                               | Control plane is localhost-only (`http://localhost:8787`)             |
| Market data        | CSV files                          | `data/*_M15.csv` (OHLCV, 15-min bars)                                 |

**No database, no message broker, no container runtime.** Everything is a flat-file service.

### 1.2 Directory Structure

```
D:\Tradelatest/
├── src/                          # Production Python package (setuptools package root)
│   ├── agent/                    # AI automation agent — NL→intent→deterministic plan→tool exec
│   ├── bitnet/                   # BitNet GGUF inference + zone validation
│   ├── config_layer/             # Config loaders, builders, validators, decision rules (CRT, llm_inference_client, execution_planner)
│   │   └── rr/                   # Risk-reward fusion layer (dataset builder, RR model fusion)
│   ├── control_plane/            # Stdlib HTTP server + HTML UI for command execution
│   ├── core/                     # Decision kernel: EngineRunner, FusionEngine, DecisionEngine, UltronRiskGate, Collector
│   ├── engines/                  # 4 scoring engines + trap-validation gating engine
│   ├── expansion/                # Deterministic parameter-expansion explorer (bounded mutation)
│   ├── features/                 # 38-dim canonical feature schema, pipeline, drift monitor
│   ├── governance/               # PromotionManager, shadow testing, portfolio validation, meta-governor
│   ├── inout/                    # Live trading executor (state machine, scanner, executor stub)
│   ├── llm_research/             # LLM-offline research pipeline (pattern extraction → policy builder → forward test)
│   ├── runtime/                  # Execution harnesses: backtest_v2, live_engine_hook, baseline_capture
│   ├── training/                 # Model training orchestrators
│   └── utils/                    # Logging, console-safe printing, trade logging, schema migration
│
├── scripts/                      # CLI entry points (not importable as `src.*`)
│   ├── analysis/                 # Config diffing, schema audit, CLI matrix docs, pyan graph gen
│   ├── backtest/                 # Manual backtest harness, debug runners
│   ├── control_plane/            # HTTP server launcher (run_server.py)
│   ├── data/                     # OHLCV prep, M15 unification, RR dataset, feature-vector generation
│   ├── export/                   # Model export + BitNet regeneration
│   ├── maintenance/              # Config hashing, BOM fixes
│   ├── misc/                     # Historical data, replay validators, parity checks
│   └── training/                 # auto_tuner, auto_tuner_multi, train_pipeline, phase5_calibration
│
├── configs/
│   ├── production/               # Versioned production configs
│   ├── formulas/                 # market_ontology.yaml (WHAT layer)
│   └── promotion_log.jsonl       # Append-only immutable promotion audit trail
│
├── data/                         # Market data CSVs (OHLCV, M15 bars)
├── models/                       # BitNet GGUF, zone registry, RR model artifacts
├── results/                      # Runtime artifacts: baseline manifests, tuner checkpoints, validation reports
├── logs/                         # JSONL audit logs
├── docs/                         # Handover docs, CLI matrix, architecture diagram HTML
│
├── CLAUDE.md                     # Master agent context + session-log mandate
├── active_models.yaml            # WHO layer (model metadata, state contracts)
├── README.md                     # Project overview
└── assistant_project.md          # Append-only session log
```

### 1.3 Core Data Flow

```
OHLCV CSV (or live feed)
  │
  ▼
FeaturePipeline          src/features/feature_pipeline.py
  • Streams candles, emits 38-dim canonical feature vector (CANONICAL_FEATURES)
  • Writes into FeatureStore (in-memory, per-instrument window)
  │
  ▼
FeatureMonitor           src/features/feature_monitor.py
  • Online Z-score drift detection (window=500)
  • HARD drift Z>3.0 → WARNING log; SOFT Z>2.5 → DEBUG
  │
  ▼
EngineRunner.run()       src/core/engine_runner.py
  ├── TrapValidatorEngine (adapter)        — hard reject if score ≤ 0.0
  ├── CRT engine           (compute)
  ├── Gaussian engine      (heuristic OR ml, per config)
  ├── ZoneGate engine      (run_zone_gate_engine)
  └── RR engine            (RREngine)
  • Completeness gate: ALL 4 engines must emit a score, else hard reject
  │
  ▼
FusionEngine.evaluate()   src/core/fusion_engine.py
  • Weighted combination (weight_crt / weight_gaussian / weight_zone_gate / weight_rr)
  • ScoreNormalizer (min-max rolling), EngineHealthTracker
  • LLM tie-breaker fires ONLY when Gaussian ∈ [0.45, 0.65]
  │
  ▼
DecisionEngine            src/core/decision_engine.py
  • fusion_min_score threshold → ACCEPT / REJECT
  │
  ▼
ExecutionPlannerV1_2      src/config_layer/execution_planner.py
  • Derives {entry, sl, tp, rr_ratio, position_size_hint, ttl_seconds} from intent
  • Intent-specific multipliers: BREAKOUT / PULLBACK / REVERSAL / LIQ_SWEEP
  │
  ▼
UltronRiskGate            src/core/ultron_risk_gate.py
  • TTL expiry, RR floor, daily trade limit, kill switch (daily loss),
    portfolio exposure, SL distance checks
  • Returns GateResult{approved, final_position_size, rejection_reason}
  │
  ▼
Execution
  ├── Backtest: BacktestRunner logs trade in equity curve
  └── Live: inout/executor dispatches order + state_machine transitions
  │
  ▼
Collector                 src/core/collector.py
  • Structured JSON audit of every decision path (ACCEPT and REJECT)
```

---

## Source: `docs/architecture/signal-flow.md`

### 1.4 Production Spine (10 Steps)

#### Step 1 — DATA INGEST

- **Module:**      `src/runtime/backtest_v2.py` (backtest) / `src/inout/scanner.py` (live)
- **Entry point:** `CandleLoader.stream()`
- **Reads from:**  raw OHLCV M15 CSV in `data/<INSTRUMENT>.csv`, or live tick adapter
- **Emits:**       `Candle` dataclass
- **Validates:**   L1 duplicate-header reject + L2 duplicate/out-of-order timestamp + Phase-1 column / Phase-2 value checks
- **Failure mode:** fail-fast on missing/empty CSV, malformed timestamps, lookahead

#### Step 2 — FEATURE PIPELINE

- **Module:**      `src/features/feature_pipeline.py`
- **Entry point:** `FeaturePipeline.run()` → `(enriched_df, vectors)`
- **Reads from:**  `CANONICAL_FEATURES` (38-dim) + `FEATURE_SCHEMA` hash baseline from `results/baseline/`
- **Emits:**       38-dim feature vectors (indices 0–4 = raw OHLCV)
- **Failure mode:** fail-fast on schema-hash mismatch

#### Step 3 — SCORING ENGINES

- **Module:**      `src/core/engine_runner.py`
- **Entry point:** `EngineRunner.run(...)` → invokes each engine in `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}`
- **Reads from:**  `engine_runner` config section + per-engine sections; model artifacts from `models/`
- **Emits:**       per-engine `score ∈ [0,1]` map
- **Failure mode:** optional-import for BitNet/llama; fail-fast if any of the four expected engines is missing

#### Step 4 — FUSION & DECISION

- **Module:**      `src/core/fusion_engine.py` + `src/core/decision_engine.py`
- **Entry point:** `FusionEngine.evaluate(scores)` → `DecisionEngine.decide(...)`
- **Reads from:**  `fusion_engine` (weights, normalizer), `decision_engine` (threshold)
- **Emits:**       `DecisionResult` ∈ {GO / PASS / REJECT} with `RejectReason` enum
- **Failure mode:** fail-fast on weight-sum drift; fail-open on `llm_inference_client` timeout

#### Step 5 — EXECUTION PLANNER

- **Module:**      `src/config_layer/execution_planner.py`
- **Entry point:** `ExecutionPlannerV1_2.plan(decision)` (only when Step 4 = GO)
- **Reads from:**  `execution_planner` section
- **Emits:**       `ExecutionPlan` (entry / SL / TP / RR / TTL)
- **Failure mode:** fail-fast on `reject_unknown_intent: true`

#### Step 6 — ULTRON RISK GATE

- **Module:**      `src/core/ultron_risk_gate.py`
- **Entry point:** `UltronRiskGate.evaluate(plan, portfolio_state)`
- **Reads from:**  `ultron_risk_gate` section
- **Emits:**       `GateResult` (APPROVE / REJECT)
- **Failure mode:** fail-fast — last deterministic capital check

#### Step 7 — EXECUTION

- **Module:**      `src/execution/` (broker stub) / `src/inout/executor.py` (live)
- **Entry point:** order dispatcher
- **Reads from:**  approved `GateResult` + `ExecutionPlan`
- **Emits:**       `TRADE_OPENED` JSONL line
- **Failure mode:** fail-fast on broker-API error

### 1.5 Async Feeders (off-spine)

#### Governance Kitchen

```
AutoTuner (scripts/training/auto_tuner_multi.py)
  → ConfigValidator.validate()  (src/config_layer/config_validator.py)
  → PromotionManager.promote_from_tuner_checkpoint()
  → configs/production/{ACTIVE_VERSION}.json + configs/promotion_log.jsonl
```

#### Training Kitchen

```
Raw trades  (logs/trades_*.jsonl)
  → DatasetValidator  (src/features/dataset_validator.py)
  → Trainer  (src/training/trainer.py)
  → ModelRegistry  (src/core/model_registry.py)
  → models/{zone_registry.json, rr_model.json, ...}
```

#### AI Agent

```
NL command
  → IntentRouter  (src/agent/intent_router.py)
  → PlanCompiler  (src/agent/plan_compiler.py)
  → Executor      (src/agent/executor.py)
```

#### INOUT (parallel strategy)

INOUT is a separate strategy that joins only at Step 6 (UltronRiskGate).

---

# 2. THREE AUTHORITY ARCHITECTURE

---

## Source: `docs/governance/config_authority_matrix.md`

### 2.1 Three Authority Doctrine

| Layer | Role | Canonical home | Runtime load? |
|---|---|---|---|
| **WHO** | Which model uses which feature / why; dual-track truth | `active_models.yaml` (repo root) | **Partial** — `state_contracts` load + `valid_transitions` drive SM instance graph |
| **HOW** | Thresholds, weights, switches, paths | `configs/production/{ACTIVE_VERSION}.json` | Yes |
| **WHAT** | Mathematical meaning of a quantity (FM-*) | `configs/formulas/market_ontology.yaml` | Indirect (registry dispatch; never `eval`'d) |

**Consolidation rule:** numbers → HOW · formulas → WHAT · narrative/reachability → WHO · version pointers → existing manifests

### 2.2 Authority Sources Inventory

| # | File | Exists | Role class |
|---|---|---|---|
| S1 | `configs/formulas/market_ontology.yaml` | YES | WHAT (descriptive) + formula bind |
| S2 | `active_models.yaml` | YES | WHO (descriptive; not runtime) |
| S3 | `configs/production/v2_multi_2026_04.json` | YES | HOW (active production) |
| S4 | `configs/production/ACTIVE_VERSION` | YES | Tier-0 pointer → `v2_multi_2026_04` |
| S5 | `configs/promotion_log.jsonl` | YES | Governance history (append-only) |

### 2.3 Authority Mapping

```
ACTIVE_VERSION (S4)
    │  get_active_version()  [production_config.py]
    ▼
v2_multi_2026_04.json (S3)  ── HOW ── thresholds / weights / flags / paths
    │  (Every consumer module calls get_prod_section())
    ▼
[Step 3–6 modules read config at runtime]
    ├── engine_runner (weights, zone threshold)
    ├── fusion_engine (per-engine weights)
    ├── decision_engine (score thresholds)
    ├── execution_planner (SL/TP multipliers)
    └── ultron_risk_gate (position sizing, daily limits)
```

---

## Source: `docs/governance/WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md` (referenced)

The three authorities define an executable boundary:

- **WHAT (market_ontology.yaml)** → Feature formulas → FM-ids (FM-001...FM-046) → Feature Registry
- **WHO (active_models.yaml)** → State contracts → FM requirements per state → CRT validation
- **HOW (production/*.json)** → Config thresholds → Module consumers → Runtime gates

---

# 3. MARKET_ONTOLOGY.YAML

---

## Source: `configs/formulas/market_ontology.yaml`

[Full YAML content from above — includes all primitives, compositions, derived metrics, rolling indicators, and migration candidates]

### 3.1 Schema v1.3

- **Authority**: user_approved (WHAT layer; grants no promotion authority)
- **Version**: 1.3 (2026-07-12): bottom-up cert program — rolling_indicators section (FM-040..046 first-class windowed identities)
- **Canonical features**: 38-dimensional vector (OHLCV + 33 derived features)

### 3.2 Layer Separation

- **Primitives** (FM-001...FM-005): Mathematical identities over OHLC (immutable)
- **Feature Compositions** (FM-010...FM-013): Trading interpretations (ratios, tunable)
- **Derived Metrics** (FM-020...FM-031): Deterministic normalized quantities (ATR/price-relative)
- **Rolling Indicators** (FM-040...FM-046): Windowed indicators (ATR, RSI, EMA, swing publication)

### 3.3 Key Features Referenced in Active_Models

| FM-id | Name | Used by | Notes |
|---|---|---|---|
| FM-002 | candle_range | SWEEP, EXPANSION | high - low |
| FM-010 | body_ratio | SWEEP, RETEST, BitNet | body_size / candle_range [0,1] |
| FM-020 | disp_strength | CRT scoring | body_size / (atr * close), clipped [0,3] |
| FM-027 | displacement_retrace | RETEST (CH-002) | Cross-candle retrace ratio |
| FM-028 | displacement_atr_ratio | EXPANSION (CH-002) | candle_range / atr |
| FM-040 | true_range | ATR base | max(H-L, \|H-PC\|, \|L-PC\|) |
| FM-041 | atr | All engines | SMA(14) of true_range / close |
| FM-043 | ema_fast | Gaussian, regime | close.ewm(span=9) |
| FM-044 | ema_slow | Gaussian, regime | close.ewm(span=21) |

---

# 4. ACTIVE_MODELS.YAML

---

## Source: `active_models.yaml` (root)

### 4.1 Schema v2.1

- **Canonical layers**: [intent, runtime, evidence, status]
- **Three truth layers**: intent (architectural), runtime (executing), evidence (research), status (rollup)
- **Machine-readable sources**: Registry for findings, hypotheses, framework entries

### 4.2 CRT Engine (Active)

**9-State State Machine:**

```
RANGE → [SWEEP, SHADOW_PENDING]
SHADOW_PENDING → [SWEEP, RANGE]
SWEEP → [DISPLACEMENT, EXPANSION, RANGE]
DISPLACEMENT → [EXPANSION, RANGE]
EXPANSION → [RETEST, EXPIRED, RANGE]
EXPIRED → [RANGE]
RETEST → [EXECUTION, RANGE]
EXECUTION → [RESOLUTION]
RESOLUTION → [RANGE]
```

**Phase-1 State Contracts (FM requirements per state):**

| State | Required FM | Config Keys | Eligible Models |
|---|---|---|---|
| RANGE | [] | atr_period, atr_buffer_multiplier, ema_fast, ema_slow, ... | [] |
| SWEEP | [FM-002, FM-010] | atr_min_displacement, body_ratio_min, atr_multiplier_min, ... | [] |
| EXPANSION | [FM-010, FM-028] | retest_depth_max, retest_atr_depth_fraction, ... | [] |
| RETEST | [FM-010, FM-027, FM-028] | conf_alpha, conf_beta, conf_weights, ... | [bitnet] |
| EXECUTION | [] | exit_model | [] |

**Detection Rules:**

- **Range**: Pure geometric (H/L reference over HTF window)
- **Sweep**: Boundary breach with rejection (candle.high > range.h_ref AND close < range.h_ref)
- **Displacement**: Multi-gate (body_ratio >= 0.70, atr_min_displacement, wick gates)
- **Expansion**: Single candle extension (close > disp.close + threshold)
- **Retest**: Adaptive depth ceiling (depth < max ceiling)
- **Expired**: TTL guard (age > max_candles OR age > max_hours)

**Cached Features at RETEST:**

- FM-027 displacement_retrace (CH-002)
- FM-010 body_ratio
- FM-028 displacement_atr_ratio (CH-002)
- retest_index
- session
- double_sweep

### 4.3 Gaussian Engine (Active — Heuristic)

**Runtime**: HeuristicGaussianEngine (3-feature momentum vote)  
**Features**: [ema_fast, ema_slow, momentum_score]  
**Target**: directional_momentum_score

**Trained Model** (experimental, unwired):
- Version: v4_mirrored (38-dim Naive Bayes)
- Status: experimental
- Correlation: 0.2066 (on test set)
- Evidence: [CURRENT_STATE.md, phase5_calibration.py]

### 4.4 BitNet Engine (Inactive)

**Status**: inactive (use_bitnet=false in production config)  
**Features**: [body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep]  
**Threshold**: 0.55 (hard-reject gate when enabled)  
**Evidence**: F-004

### 4.5 ZoneGate and RR Engines

(See Lineage section for detailed audits)

---

# 5. RUNTIME PIPELINE

---

## Source: `docs/architecture/signal-flow.md` (Complete)

[Full 10-step spine, feeders, cross-reference matrix, swim-lane diagram included above]

### 5.1 Cross-Reference Matrix

| Step | Module | Config section | Schema anchor | Write authority |
| ---- | ------- | -------------- | ------------- | -------------- |
| 1 | `src/runtime/backtest_v2.py` | `backtest`, `feature_monitor` | `Candle` | dev (no governance) |
| 2 | `src/features/feature_pipeline.py` | (schema-driven) | `CANONICAL_FEATURES` | dev + baseline rehash |
| 3 | `src/core/engine_runner.py` | `engine_runner`, `crt_engine`, `gaussian_scorer`, `rr_model` | `CRTState` | governance only (config) |
| 4 | `src/core/fusion_engine.py` + `decision_engine.py` | `fusion_engine`, `decision_engine`, `llama_gate` | `DecisionResult` | governance only (config) |
| 5 | `src/config_layer/execution_planner.py` | `execution_planner` | `ExecutionPlan` | governance only |
| 6 | `src/core/ultron_risk_gate.py` | `ultron_risk_gate`, `portfolio` | `GateResult` | governance only |
| 7 | `src/execution/`, `src/inout/executor.py` | (broker adapter) | JSONL `TRADE_OPENED` | dev |

---

# 6. FEATURE LINEAGE

---

## Source: `docs/topics/model-intent-and-feature-ownership.md`

### 6.1 Feature × Model Ownership Matrix

**Legend:**
- **REQ·A** required by intent
- **SPEC·A** intentionally excluded (keep specialized)
- **ALL·A** consumed via full-vector contract
- **CAND·B** expansion candidate, value evidence-pending

| # | Feature | CRT | Gaussian | RR | BitNet | Regime/Dual |
|---|---------|-----|----------|----|---------|----|
| 0 | open | SPEC·A | CAND·B | SPEC·A | CAND·B | CAND·B |
| 1 | high | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 2 | low | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 3 | close | REQ·A* | CAND·B | REQ·A | CAND·B | CAND·B |
| 6 | double_sweep | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 10 | trend_bias | SPEC·A | CAND·B | SPEC·A | CAND·B | REQ·A |
| 12 | momentum_score | SPEC·A | REQ·A | SPEC·A | CAND·B | REQ·A |
| 13 | atr | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 28 | body_ratio | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 32 | disp_strength | REQ·A | CAND·B | SPEC·A | REQ·A | REQ·A |
| 33 | retest_depth | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |
| 34 | candles_since_retest | REQ·A | CAND·B | SPEC·A | REQ·A | CAND·B |

### 6.2 Model Intent & Purpose

| Model | Purpose | Features it OWNS | Why it ignores the rest |
|-------|---------|------------------|------------------------|
| **CRT** | Structural state machine | body_ratio, disp_strength, retest_depth, atr, candles_since_retest, sweep_detected | Self-contained; uses internal EMA/ATR |
| **Gaussian** | Directional-momentum Gaussian | ema_fast, ema_slow, momentum_score | Designed as narrow momentum vote |
| **RR** | Candle-polarity index | close, high, low | Structural filter, not predictor |
| **ZoneGate** | Full-vector pattern similarity | ALL 38 (per-zone learned masking) | Per-zone learned, not designed |
| **BitNet** | 6-feature hard-reject | body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep | Deliberately compact gate |

---

# 7. CONSUMER MAPPING

---

## Source: `docs/governance/` (Lineage audits)

### 7.1 Engine Lineage Audits

#### BitNet Lineage (F-004)

- **Status**: AUDITED
- **File**: `src/bitnet/bitnet_inference.py:317`
- **State**: INERT + conditional skew; `use_bitnet=false` on active patch
- **Features**: [body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep]
- **Threshold**: 0.55 (hard-reject, when enabled)
- **Evidence**: Comprehensive lineage audit

#### Gaussian Lineage

- **Status**: AUDITED
- **State**: Live heuristic (3-feature) active; 38-dim trained model experimental/unwired
- **Features**: [ema_fast, ema_slow, momentum_score]
- **Evidence**: Dual-track heuristic/ML observational audit; no retrain/promote authority

#### RR Lineage (F-038, F-044)

- **Status**: AUDITED
- **Issues**:
  - F-038: RR-fusion was GAUSSIAN DUPLICATE in gate-ON fusion (disabled in active config)
  - F-044: RR-fusion confidence gate is mis-specified for dimensionality (d_sq-based gate over rank-27 Mahalanobis)
- **State**: Base RREngine active; rr_fusion disabled (`enabled:false`)
- **Evidence**: Three contracts (polarity / rr_fusion inert / F-048 mismatch)

#### ZoneGate Lineage (F-036, F-041)

- **Status**: AUDITED
- **Findings**:
  - F-036: ZoneGate tunable knobs (top_k/cluster_min_n) are config-TUNABLE but INERT (ΔG001≡0)
  - F-041: Runtime score via `models/zone_registry.json` parity with manifest verified
- **State**: Active geometric HARD gate; no marginal value
- **Evidence**: Active geometric HARD gate + no marginal value; PIT_UNCLEAN economic

#### TradeNet Lineage (F-005)

- **Status**: AUDITED
- **State**: INERT / UNWIRED fusion neural slot (architectural intent, not wired)
- **Evidence**: Code exists, never called in EXPECTED_ENGINES

---

# 8. GOVERNANCE

---

## Source: `docs/reference/governance.md` and `docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`

### 8.1 Promotion Workflow

```
AutoTuner → ValidationReport (hard + soft gates) → ConfigValidator.validate()
  ↓ (if APPROVE)
PromotionManager.promote_from_checkpoint()
  ├─ SHA-256 hash of new config
  ├─ Archive prior: configs/production/{old_version}_archived_{ts}.json
  ├─ Write: configs/production/{new_version}.json
  └─ Append: configs/promotion_log.jsonl (one immutable line)
```

### 8.2 Write Authority

| Component | Authority | Approval Path |
|-----------|-----------|---------------|
| `params` (CRT thresholds) | Governance only | PromotionManager + ConfigValidator |
| `engine_runner` (weights, flags) | Governance only | Config Authority |
| `fusion_engine` (per-engine weights) | Governance only | Config Authority |
| `decision_engine` (thresholds) | Governance only | Config Authority |
| `execution_planner` (SL/TP multipliers) | Governance only | Governance only |
| `ultron_risk_gate` (position sizing) | Governance only | Governance only |
| feature pipeline | dev + baseline rehash | Promotion on baseline change |
| CRT state machine | Research (frozen) | RFC only to change |

### 8.3 Hard + Soft Gates

**Hard gates** (must pass to promote):
- min_trades_per_instrument: 10
- max_drawdown_pct: 35%
- min_score_threshold: 0.15

**Soft gates** (warnings, may proceed):
- min_win_rate < 35%
- min_expectancy < -0.5R
- max_score_std_dev threshold

---

# 9. CURRENT FINDINGS

---

## Source: `docs/current-findings.md`

[Key subset of findings relevant to architecture and authority]

### 9.1 Architecture Findings

| F-id | Type | Conclusion | Confidence |
|------|------|-------------|------------|
| F-004 | ARCH | BitNet is a hard-reject gate WHEN `use_bitnet` enabled; but `use_bitnet:false` on active `v2_multi_2026_04`, so INERT | Certain |
| F-005 | ARCH | TradeNet v2 is BUILT but unwired — fusion neural slot is a permanent stub | Certain |
| F-006 | GOV | `config_integrity` is a REAL check but ORPHANED — it gates nothing at runtime | Certain |
| F-016 | GOV | On `patch`, active config is `v2_multi_2026_04` (pre-TP3); v4 applies only to TP3 code line | Certain |
| F-018 | GOV | Active config (patch) lags HEAD code: required sections absent + knobs hardcoded → data-gate runs on defaults | Certain |
| F-022 | GOV | `opportunities.jsonl` is a DETECTION STREAM, not trade ledger — outcome/rr only 36.8% self-consistent | Certain |
| F-036 | ECON | ZoneGate runtime knobs are config-TUNABLE but INERT — ΔG001≡0 (byte-identical entries) | Likely |
| F-037 | ARCH | Research spine is CRT-only by design — 4-engine fusion gate is OFF in backtests (`.env` BACKTEST_ENGINE_GATE=0) | Certain |
| F-038 | ARCH | RR was a GAUSSIAN DUPLICATE in gate-ON fusion — fix=retrain OR disable (`enabled:false` on active patch) | Certain |
| F-041 | GOV | ZoneGate runtime parity checked and reconciled (F-041A); honest labels show NO_EDGE (F-041B) | Certain |
| F-044 | ARCH | RR confidence gate is MIS-SPECIFIED for rank-27 Mahalanobis (100% in-sample bypass); fix pending | Certain |
| F-047 | ARCH | Feature lineage built; market ontology now AUTHORITATIVE source for feature math (registry-backed) | Certain |
| F-050 | ARCH | CRT cached_features now emit FM-027/FM-028 via derived_math (rename CH-002) | Certain |
| F-051 | ARCH | Centered-swing production binding is non-PIT; leaks future bars, contaminates 10/38 canonical dims | Likely |

### 9.2 Consumer & Dependency Findings

| F-id | Finding | Impact |
|------|---------|--------|
| F-039 | L3 dataset-integrity runs at only 2 call sites; rest use L1/L2 only (no L3) | L3 adds confidence, not validity |
| F-041A | ZoneGate version manifest parity reconciled (F-041A RESOLVED 2026-07-05) | Runtime↔label assignment parity 0.414 |
| F-041B | Honest zone labels show NO_EDGE (0/8 zones clear E>0 OOS) | Binding constraint = entry-info null |

---

# 10. APPENDIX

---

## Source: `docs/reference/schemas.md`

### 10.1 Canonical Dataclasses

```python
@dataclass
class Candle:
    timestamp: datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float = 0.0
    index:     int   = 0

@dataclass
class Trade:
    entry:     float
    exit:      float
    sl:        float
    tp:        float
    direction: "Direction"
    rr_ratio:  float

@dataclass
class DecisionResult:
    decision: str  # GO / PASS / REJECT
    reason: RejectReason
    confidence: float
    fusion_score: float

@dataclass
class ExecutionPlan:
    entry: float
    sl: float
    tp: float
    rr_ratio: float
    ttl_seconds: int
    position_size: float

@dataclass
class GateResult:
    approved: bool
    final_position_size: float
    rejection_reason: str
```

### 10.2 Key Design Patterns

| Pattern | Instances |
|---------|-----------|
| **Registry** | `PLAN_REGISTRY` (agent), `TOOL_REGISTRY`, `FORMULA_REGISTRY`, `CommandSpec` registry |
| **Factory** | `BacktestConfig.from_prod_config()`, `CRTConfig` builders |
| **Facade** | `EngineRunner` hides adapter → 4 engines → fusion → decision |
| **Gate chain** | Adapter → Completeness → Fusion → Decision → UltronRiskGate |
| **State machine** | CRT (RANGE → ...→ RESOLUTION); INOUT lifecycle |
| **Append-only log** | `promotion_log.jsonl`, `agent_audit.jsonl`, `expansion_trace.jsonl` |

### 10.3 External Integrations

| Integration | Purpose | Touch point | Failure mode |
|-------------|---------|------------|--------------|
| **Local llama.cpp server** | LLM tie-breaker + agent intent | `llm_inference_client.py` | Circuit breaker: returns neutral 1.0 after fail_count_disable retries |
| **Groq API** | Fallback LLM | `.env` → `GROQ_API_KEY` | Soft-fail via circuit breaker |
| **BitNet GGUF** | Zone scoring + agent | `bitnet_inference.py` → `models/bitnet_b1_58_70b.gguf` | Optional import guard |
| **CSV market data** | Historical replay | `data/*_M15.csv` | Hard fail if missing |

---

## Document Provenance

This master reference was assembled from the following authoritative sources:

1. `docs/reference/architecture.md` — Tech stack, directory structure, core flow
2. `docs/architecture/signal-flow.md` — 10-step spine, feeders, cross-ref matrix
3. `docs/governance/config_authority_matrix.md` — WHO/HOW/WHAT doctrine + sources
4. `docs/governance/WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.md` — Authority boundaries
5. `active_models.yaml` — CRT state contracts, FM requirements, model metadata
6. `configs/formulas/market_ontology.yaml` — Feature definitions, formulas, lineage
7. `docs/topics/model-intent-and-feature-ownership.md` — Feature × model ownership
8. `docs/governance/*_lineage_audit.md` — Engine audits (bitnet, gaussian, rr, zonegate, tradenet)
9. `docs/current-findings.md` — Findings index (subset)
10. `docs/reference/schemas.md` — Canonical dataclasses, patterns

---

**Last Updated**: 2026-07-17  
**Schema Version**: v2.1 (active_models.yaml), v1.3 (market_ontology.yaml)  
**Active Config**: v2_multi_2026_04  
**Document Type**: Consolidated reference (no new analysis)
