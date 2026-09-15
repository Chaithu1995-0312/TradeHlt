# ARCHITECTURE.md

> Technical architecture of the **Tradelatest** quantitative trading bot.
> Source of truth: `D:\Tradelatest`. Derived from live code inspection, not assumptions.

---

## 1. Tech Stack

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

---

## 2. Directory Structure

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
├── mt5_analytics/                # MT5-FIRST post-trade analytics — separate, READ-ONLY subsystem beside Tradelatest (imports src/)
│   ├── core/                     # mt5_adapter (read-only), shared_pipeline, rebuild, daemon, verify, coverage, checkpoint
│   ├── engines/                  # position_reconstructor (frozen kernel), features/, deal_characterizer
│   ├── providers/                # CandleProvider protocol (fixture / MT5)
│   ├── storage/ · schemas/ · registry/ · ui/   # partition writer + manifests, frozen v1.0 schemas, engine registry, Streamlit dashboard
│   └── MIGRATIONS.md             # artifact-affecting changes (UTC normalization, swap representation)
│
├── manual_tools/                 # EXECUTION utilities kept OUTSIDE the read-only analytics layer (demo-only trade_generator)
│
├── tests/                        # pytest suite (50+ files)
│   └── inout/                    # Live-executor subpackage tests
│
├── configs/
│   ├── production/               # Versioned production configs (active: v1_multi_2026_03.json)
│   ├── experimental/spec/        # BitNet / bitpacking design specs (.md)
│   └── promotion_log.jsonl       # Append-only immutable promotion audit trail
│
├── data/                         # Market data CSVs (OHLCV, M15 bars)
├── models/                       # BitNet GGUF, zone registry, RR model artifacts
├── results/                      # Runtime artifacts: baseline manifests, tuner checkpoints, validation reports
├── logs/                         # JSONL audit logs (agent_audit, intent_log, expansion_trace, expansion_rejected)
├── docs/                         # Handover docs, CLI matrix, architecture diagram HTML
│
├── pyproject.toml                # Build + pytest config (only dependency manifest)
├── .env                          # GROQ_API_KEY (fallback LLM)
├── CLAUDE.md                     # Master agent context + session-log mandate
├── AGENTS.md                     # High-level agent role definitions
├── README.md                     # Project overview
└── assistant_project.md          # Append-only session log (per CLAUDE.md mandate)
```

---

## 3. Core Data Flow

> For the per-candle linear walk (Steps 1–7) and the async kitchen feeders
> (Governance, Training, Agent, INOUT), see [`docs/SIGNAL_FLOW.md`](SIGNAL_FLOW.md).

### 3.1 Backtest / Live decision path

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

### 3.2 Governance / promotion path

```
auto_tuner_multi.py → checkpoint_multi.json
  │
  ▼
ConfigValidator.validate(params, csv_paths, config_id)
  • Per-instrument BacktestRunner over each CSV
  • Computes fitness from weighted metrics (fitness_weights)
  • HARD gates: min_trades_per_instrument, max_drawdown_pct, score_threshold
  • SOFT gates: min_win_rate, min_expectancy, max_score_std_dev
  • Returns ValidationReport{decision, metrics, per_instrument, hard_failures, warnings}
  │
  ▼ (only if decision == "APPROVE")
PromotionManager.promote_from_checkpoint()
  • SHA-256 hash of new config
  • Archives prior prod: configs/production/{old_version}_archived_{ts}.json
  • Writes configs/production/{new_version}.json
  • Appends one line to configs/promotion_log.jsonl
```

### 3.3 Agent path

```
User NL input (REPL)
  │
  ▼
IntentRouter            src/agent/intent_router.py   — 14 intents, LLM-classified
ArgFiller               src/agent/tool_planner.py
PlanCompiler            src/agent/plan_compiler.py   — deterministic PLAN_REGISTRY lookup (no LLM planning)
Executor                src/agent/executor.py        — confirm-gate + path-guard
  │
  ▼
Tool dispatch (17 tools in tool_registry) → audit.jsonl + intent_log.jsonl
```

---

## 4. Key Design Patterns

| Pattern          | Instances                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| **Registry**     | `PLAN_REGISTRY` (agent), `TOOL_REGISTRY` (agent), `model_registry.py` (governance), `CommandSpec` registry (control plane) |
| **Factory**      | `BacktestConfig.from_prod_config(cfg)`, `_params_to_crt_config(params)`                                 |
| **Strategy**     | Four interchangeable engines behind a uniform score contract (`{score, intent, regime}`)                |
| **Facade**       | `EngineRunner` hides adapter → 4 engines → fusion → decision behind one `.run()`                        |
| **Gate chain**   | Adapter gate → Engine completeness → Fusion threshold → Decision → UltronRiskGate                       |
| **State machine**| `CRTState` enum (RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION); `inout/state_machine.py` for live trade lifecycle |
| **Observer**     | `FeatureMonitor` subscribes to `TRADE_OPENED` events for drift Z-scoring                                |
| **Command**      | `CommandSpec` + `JobManager` (control plane) — commands are first-class objects, run in thread pool     |
| **Append-only log** (event-sourcing lite) | `promotion_log.jsonl`, `agent_audit.jsonl`, `expansion_trace.jsonl` — immutable audit trails |
| **Fail-open / fail-fast split** | Fail-**fast** on config load (`RuntimeError`); fail-**open** on external LLM (returns neutral 1.0 after `fail_count_disable` retries) |
| **Feature flag** | `fusion_use_evaluate` in production config gates the new `FusionEngine.evaluate()` path                 |

---

## 5. External Integrations

| Integration                  | Purpose                           | Touch point                                         | Failure mode                                             |
| ---------------------------- | --------------------------------- | --------------------------------------------------- | -------------------------------------------------------- |
| **Local llama.cpp server**   | LLM tie-breaker + agent intent    | `config_layer/llm_inference_client.py` — `server_url` from prod config | Circuit breaker: after `fail_count_disable` retries, returns neutral `1.0` |
| **Groq API**                 | Fallback LLM when local unavailable | `.env` → `GROQ_API_KEY`                           | Soft-fail via same circuit breaker                       |
| **BitNet GGUF (local file)** | Zone scoring + agent reasoning    | `src/bitnet/bitnet_inference.py` → `models/bitnet_b1_58_70b.gguf` | Optional import guard → `_MONITOR_AVAILABLE = False`     |
| **CSV market data**          | Historical replay                 | `data/*_M15.csv`                                    | Hard fail in `BacktestRunner` if missing                 |
| **Control plane HTTP UI**    | Manual command execution          | `http://localhost:8787` (stdlib `ThreadingHTTPServer`) | Localhost only — no external exposure                    |

No queues, no message brokers, no cloud storage, no external databases.

---

## 6. Environment Config Overview

### 6.1 `.env` keys

| Key              | Purpose                                                 | Required? |
| ---------------- | ------------------------------------------------------- | --------- |
| `GROQ_API_KEY`   | Fallback LLM access when local llama.cpp server is down | Optional (soft-fail if absent) |

### 6.2 Production config (`configs/production/v1_multi_2026_03.json`)

Single source of truth — **no magic numbers in Python code**. The JSON contains nine top-level sections, each consumed by a dedicated loader (`get_prod_section("<name>")`):

| Section             | Consumer                                                    | Purpose                                                            |
| ------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------ |
| `params`            | `config_builder.py` → `CRTConfig`                           | CRT-engine tunable parameters (body_ratio, retest_depth, ATR mults)|
| `engine_runner`     | `core/engine_runner.py`                                     | Model path, allowed sessions, zone thresholds, gaussian impl, fusion flags |
| `execution_planner` | `config_layer/execution_planner.py`                         | Intent-specific TP/SL/TTL/RR multipliers                           |
| `ultron_risk_gate`  | `core/ultron_risk_gate.py`                                  | Position sizing, daily limits, kill switch thresholds              |
| `fusion_engine`     | `core/fusion_engine.py`                                     | Per-engine weights (weight_crt / weight_gaussian / weight_zone_gate / weight_rr) |
| `decision_engine`   | `core/decision_engine.py`                                   | Score thresholds for ACCEPT / REJECT                               |
| `crt_engine`        | `config_layer/crt_engine_v2.py`                             | CRT state machine parameters                                       |
| `governance`        | `governance/shadow_promotion_gate.py`                       | Shadow testing config                                              |
| `llama_gate`        | `config_layer/llm_inference_client.py`                      | LLM server URL, timeouts, `fail_count_disable`, `request_timeout`  |
| `config_validator`  | `config_layer/config_validator.py`                          | Hard + soft gate thresholds, fitness weights, trade count target   |
| `agent`             | `src/agent/*`                                               | BitNet 3B config, REPL mode, `copilot_auto_narrate=false`          |

### 6.3 Config loading contract

```python
# Every consumer loads its slice the same way:
from config_layer.production_config import get_prod_section
cfg = get_prod_section("llama_gate")  # "llama_gate" is the JSON key; module is config_layer/llm_inference_client.py
value = _require_key(cfg, "server_url")  # raises KeyError if missing → RuntimeError
```

Missing or malformed config **fails fast at import time** — no lazy silent defaults.

---

## 7. Execution Entry Points

| Command                                                                                 | Purpose                         |
| --------------------------------------------------------------------------------------- | ------------------------------- |
| `python scripts/training/auto_tuner_multi.py`                                           | Multi-instrument hyperparam search |
| `python src/config_layer/config_validator.py validate-prod --data-dir data/`            | Re-validate active prod config  |
| `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_multi.json --version v2_... --data-dir data/` | Promote candidate |
| `python src/runtime/backtest_v2.py`                                                     | Candle-by-candle backtest       |
| `python src/runtime/baseline_capture.py --label phase0`                                 | Baseline manifest snapshot      |
| `python src/inout/runner.py`                                                            | Live trading executor           |
| `python scripts/control_plane/run_server.py`                                            | HTTP UI at `localhost:8787`     |
| `python -m src.agent.cli`                                                               | Agent REPL                      |
