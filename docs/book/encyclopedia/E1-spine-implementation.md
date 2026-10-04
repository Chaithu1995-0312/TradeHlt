# Encyclopedia E1 — Spine Implementation (Group A)

**Phase:** E1  
**Status:** DONE (file-level map; not line-by-line reverse engineering)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)

## Scope

Group A packages that implement or host the candle → order spine and its immediate I/O / control surfaces:

| Package | Files mapped | Architecture chapters |
|---|---:|---|
| `src/core/` | 20 | Ch.11–14, Ch.02 |
| `src/config_layer/` | 28 (incl. `rr/`) | Ch.06–08, Ch.13, Ch.16 |
| `src/engines/` | 13 | Ch.10 |
| `src/runtime/` | 10 | Ch.05, Ch.15, Ch.02 |
| `src/execution/` | 5 | Ch.15 |
| `src/live/` | 3 | Ch.15 |
| `src/inout/` | 4 | Ch.05, Ch.15 |
| `src/control_plane/` | 11 | Ch.22 |
| **Total** | **~94** | |

**Not in E1:** full `src/features/` registry depth (package oriented in Ch.06–07; file encyclopedia deferred to a follow-on spine-features pass if needed), `src/research/` (E2), governance (E3).

**Legend — Relevance**

| Tag | Meaning |
|---|---|
| LIVE | On or adjacent to production spine / promotion path |
| PARTIAL | Built + tested; wiring conditional or incomplete |
| SIDECAR | Optional / advisory / non-veto on default path |
| OBSERVE_ONLY | Telemetry or probes; must not change decisions |
| SHIM | Compatibility alias; prefer canonical module |
| INERT | Present but disabled / unwired on active config |

---

## 1. `src/core/` — Decision spine orchestration

**Package role:** Orchestrate scoring → fusion → decision → capital gate; hold shared types and optional controllers.

### Already in the architecture book (CITED)

| File | Classes | Purpose (short) | Chapter |
|---|---|---|---|
| `engine_runner.py` | `EngineRunner` | Orchestrates engines, fusion, decision path | Ch.02, Ch.10–12 |
| `fusion_engine.py` | `FusionEngine`, … | Multi-engine score fusion / completeness | Ch.11 |
| `decision_engine.py` | `DecisionEngine` | Semantic accept/reject (no economic RR) | Ch.12 |
| `ultron_risk_gate.py` | `UltronRiskGate` | Final capital / RR / exposure check | Ch.14 |

### Encyclopedia entries — omitted / supporting

### `src/core/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Package exports for the decision spine.
- **Relationships:** Imported by runtime, agents, tests.
- **Entry points:** Import surface only.
- **Chapter:** Ch.04 package map.

### `src/core/types.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Canonical TypedDict / contract types for the execution spine (`EngineContext`, engine results, etc.).
- **Relationships:** Consumed by EngineRunner, engines, tests that pin shapes.
- **Entry points:** Imported across `src/core`, `src/engines`, tests.
- **Chapter:** Complements `docs/reference/schemas.md`.

### `src/core/feature_store.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Canonical feature store — single source of truth for feature dictionaries used on the spine.
- **Relationships:** Fed by feature builders / pipeline; read by engines and gates.
- **Entry points:** EngineRunner / live hook paths; unit tests.
- **Chapter:** Ch.07 (vector) without naming this module.

### `src/core/gate_intelligence.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Pure signal gate used by `ExecutionPlanner` (intent / geometry-adjacent approval), not the capital gate.
- **Relationships:** Called from `execution_planner.py`; uses CRT-level geometry helpers (`compute_crt_levels` chain).
- **Entry points:** Planner path after Decision ACCEPT; tests under planner/gate.
- **Chapter:** Ch.13 (planner) — this file is the missing named helper.
- **Note:** ATR unit issues in CRT levels surface here via geometry (Ch.13 open defect).

### `src/core/model_registry.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Versioned model registry with promotion margin / GOV-style quality gates for model artifacts.
- **Relationships:** Training / promotion paths; loads model JSON under `models/`.
- **Entry points:** Training scripts, promotion flows; `tests` around registry.
- **Chapter:** Ch.16 (promotion) adjacent.

### `src/core/collector.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Append structured records to `logs/collector.jsonl` (telemetry for fusion shadow / analysis).
- **Relationships:** Written from EngineRunner / runtime; read by `runtime/analyze_fusion_shadow.py`.
- **Entry points:** Runtime with collector enabled; analysis scripts.
- **Chapter:** None (ops telemetry).

### `src/core/acceptance_controller.py`
- **Group:** A · **Relevance:** SIDECAR / PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Adaptive acceptance control — modulates accept rates / thresholds over time.
- **Relationships:** Optional layer near fusion/decision; config-driven when wired.
- **Entry points:** Config sections if present; focused tests.
- **Chapter:** None — not required to understand baseline spine.

### `src/core/convergence_controller.py`
- **Group:** A · **Relevance:** SIDECAR / PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Convergence layer for FusionEngine (stability of multi-engine agreement).
- **Relationships:** Fusion path when enabled.
- **Entry points:** Fusion config flags; tests.
- **Chapter:** Ch.11 optional depth.

### `src/core/dynamic_threshold.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Percentile-based adaptive thresholds (not fixed hardcodes).
- **Relationships:** Controllers / gates that need regime-aware cutoffs.
- **Entry points:** Config + unit tests.
- **Chapter:** None.

### `src/core/hierarchical_meta_fusion.py`
- **Group:** A · **Relevance:** SIDECAR / INERT-ish · **Book:** NOT_IN_BOOK
- **Purpose:** Multi-layer hierarchical meta-fusion for capital allocation quality scoring (HMF).
- **Relationships:** Sidecar to main fusion; findings class F-012 (sidecar-only consumers).
- **Entry points:** Explicit HMF callers / research; not default spine.
- **Chapter:** Ch.04 dormant/sidecar class.

### `src/core/regime_governor.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Regime-aware governor (`UltronGovernor` naming in module) — regime context for sizing/gates.
- **Relationships:** Adjacent to Ultron / risk; not a substitute for UltronRiskGate.
- **Entry points:** Config-gated integrations; tests.
- **Chapter:** Ch.14 adjacent.

### `src/core/signal_audit.py`
- **Group:** A · **Relevance:** OBSERVE_ONLY · **Book:** NOT_IN_BOOK
- **Purpose:** Per-bar signal audit + leak detection recorder.
- **Relationships:** Observes spine outputs; should not mutate decisions.
- **Entry points:** Audit-enabled runs; analysis.
- **Chapter:** None.

### `src/core/signal_belief_tracker.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Temporal belief accumulator that can gate DecisionEngine calls (multi-bar confidence).
- **Relationships:** Upstream of DecisionEngine when enabled.
- **Entry points:** Config + tests; may be inactive on default configs.
- **Chapter:** None.

### `src/core/governance_mode.py`
- **Group:** A · **Relevance:** LIVE (LLM layer) · **Book:** NOT_IN_BOOK
- **Purpose:** `GOVERNANCE_MODE` switch hardening for the LLM layer (Trd-M5) — when LLM is advisory vs restricted.
- **Relationships:** LLM client / agent governance; not a trade veto by itself.
- **Entry points:** Config / env governance mode; agent paths.
- **Chapter:** Ch.21 / Ch.16 adjacent.

### `src/core/backtest_port.py`
- **Group:** A · **Relevance:** LIVE (interface) · **Book:** NOT_IN_BOOK
- **Purpose:** Dependency-inversion port for backtest results (Trd-M4) — clean boundary between runtime and consumers.
- **Relationships:** Implemented/used by backtest harnesses and validators.
- **Entry points:** Backtest / config validator.
- **Chapter:** Ch.05 / Ch.16.

### `src/core/ultron_risk_gate_wrapper.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Wrapper around `UltronRiskGate` for alternate call shapes / integration adapters.
- **Relationships:** Prefer `ultron_risk_gate.py` as canonical; wrapper for callers needing a facade.
- **Entry points:** Live / strategy adapters; tests.
- **Chapter:** Ch.14.

---

## 2. `src/config_layer/` — Config, CRT, planner, models, LLM transport

**Package role:** Production config load, CRT state machine, execution planner, goal schema, model path resolution, RR offline stack, optional LLM transport.

### Already in the architecture book (CITED)

| File | Purpose | Chapter |
|---|---|---|
| `crt_engine_v2.py` | Full CRT state machine | Ch.08 |
| `execution_planner.py` | Intent classifier + gate | Ch.13 |
| `config_validator.py` | Pre-promotion validation | Ch.16 |
| `goal_schema.py` / `goal_validator.py` | Goal layer | Ch.01 |
| `state_identity.py` | CRTState / transitions seed | Ch.08 |
| `crt_gaussian_scorer.py` | CRT-side Gaussian scoring helper | Ch.10 adjacent |

### Encyclopedia entries

### `src/config_layer/production_config.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Load active production config; `get_active_version()` / `get_prod_config()` — **Tier-0 runtime truth** (`ACTIVE_VERSION`).
- **Relationships:** Nearly every production path; fail-fast if version missing.
- **Entry points:** Import from engines, backtest, promotion, CLI.
- **Chapter:** CLAUDE.md §4.0; Ch.16.

### `src/config_layer/config_builder.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Single source of truth for building `CRTConfig` (and override validation). Site of F-057 split-brain when programmatic path skips production JSON.
- **Relationships:** `market_router` profiles; BacktestRunner / CRT engine.
- **Entry points:** Backtest, tuner, tests; CLI path usually via production JSON.
- **Chapter:** Ch.13 (F-057), Ch.08.

### `src/config_layer/market_router.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Market-type CRT profiles (crypto/forex) and routing into ConfigBuilder defaults.
- **Relationships:** Feeds ConfigBuilder when production overrides absent.
- **Entry points:** ConfigBuilder; instrument onboarding.
- **Chapter:** Ch.13 F-057 mechanism.

### `src/config_layer/production_bundle.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Immutable executable production state as one object (bundle of config + identity members).
- **Relationships:** Promotion / runtime loaders that want a sealed snapshot.
- **Entry points:** Governance / production load paths.
- **Chapter:** Ch.16.

### `src/config_layer/stack_version.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Composite identity over WHAT / HOW / WHO / EXECUTION stack versions.
- **Relationships:** Bundle / promotion identity checks.
- **Entry points:** Governance tooling.
- **Chapter:** Ch.16 adjacent.

### `src/config_layer/model_paths.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** CODE layout authority for where model artifacts live on disk.
- **Relationships:** `model_resolver`, registries under `models/`.
- **Entry points:** Trainers, resolvers, EngineRunner model load.
- **Chapter:** Ch.10 / Ch.16.

### `src/config_layer/model_resolver.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Resolve model family → registry active entry → artifact path (+ identity parity).
- **Relationships:** Zone / RR / Gaussian / BitNet loaders.
- **Entry points:** Engine construction; tests for registry parity (e.g. zone manifest).
- **Chapter:** Ch.10, F-041 class.

### `src/config_layer/state_topology.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Immutable CRT state topology view (`VALID_TRANSITIONS` runtime topology).
- **Relationships:** Breaks import cycles vs full crt_engine_v2; used by tests and resolvers.
- **Entry points:** CRT tests (`test_crt_state_invariants`), topology consumers.
- **Chapter:** Ch.08.

### `src/config_layer/state_contract.py` / `state_contract_loader.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Typed immutable CRT state contract + loader for declarative/YAML-backed contract surfaces.
- **Relationships:** Semantic/state resolver pipelines; CRT governance.
- **Entry points:** Contract tests; semantic pipeline.
- **Chapter:** Ch.08 / Ch.06 adjacent.

### `src/config_layer/crt_config_provenance.py`
- **Group:** A · **Relevance:** OBSERVE_ONLY / LIVE-meta · **Book:** NOT_IN_BOOK
- **Purpose:** Track how a CRTConfig was constructed (construction mode) — observability for F-057 class bugs.
- **Relationships:** ConfigBuilder / BacktestRunner diagnostics.
- **Entry points:** Probes and governance checks.
- **Chapter:** Ch.13 F-057.

### `src/config_layer/crt_sweep_taxonomy.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Pure-function geometric classification of CRT sweeps (taxonomy helpers for engine/research).
- **Relationships:** CRT engine and research classifiers.
- **Entry points:** CRT tests; research scripts.
- **Chapter:** Ch.08 adjacent.

### `src/config_layer/llm_inference_client.py`
- **Group:** A · **Relevance:** SIDECAR (fail-open) · **Book:** NOT_IN_BOOK
- **Purpose:** LLM HTTP transport with timeout / failure disable; returns neutral scores after N failures.
- **Relationships:** Agent, optional gates; **not** hard dependency of trade path.
- **Entry points:** Agent, llama/LLM config sections.
- **Chapter:** CLAUDE.md constraints; Ch.21.

### `src/config_layer/llm_scorer.py` / `llm_narrative.py` / `insight_reporter.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Score computation, narrative generation, and insight reporting over LLM transport.
- **Relationships:** Optional engines (`llm_engine`), dashboards, reports.
- **Entry points:** Control-plane report APIs; optional engine path.
- **Chapter:** Ch.21 / Ch.22 adjacent.

### `src/config_layer/rr/rr_dataset_builder.py`
- **Group:** A · **Relevance:** RESEARCH / LIVE-train · **Book:** NOT_IN_BOOK
- **Purpose:** Build RR training datasets from features + outcomes (label path historically F-022-sensitive).
- **Relationships:** `rr_pattern_miner`, training scripts.
- **Entry points:** `scripts/training/*`, research.
- **Chapter:** Ch.10 RR lineage; F-022/F-045.

### `src/config_layer/rr/rr_pattern_miner.py`
- **Group:** A · **Relevance:** RESEARCH / ARTIFACT · **Book:** NOT_IN_BOOK
- **Purpose:** Train / pure-Python inference for RR pattern model (Mahalanobis-style confidence).
- **Relationships:** Produces `models/rr_model*.json`; F-044 gate mis-spec documented in findings.
- **Entry points:** Training scripts; offline probes.
- **Chapter:** Ch.10; F-044/F-038.

### `src/config_layer/rr/rr_fusion.py`
- **Group:** A · **Relevance:** INERT on active (disabled) · **Book:** NOT_IN_BOOK
- **Purpose:** Advisory RR fusion layer; **disabled** in active production config (`rr_fusion.enabled: false`) so base RREngine flows unmutated.
- **Relationships:** EngineRunner only constructs when enabled.
- **Entry points:** Config flag; regression tests for disabled identity.
- **Chapter:** Ch.10–11; F-038/F-044.

### `src/config_layer/rr/__init__.py`
- **Group:** A · **Relevance:** LIVE (package) · **Book:** NOT_IN_BOOK
- **Purpose:** RR subpackage marker / exports.
- **Chapter:** Ch.10.

### `src/config_layer/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Package docstring / exports for config layer.
- **Chapter:** Ch.04.

---

## 3. `src/engines/` — Scoring engines + gates

**Package role:** Four mandatory engines (CRT, Gaussian, Zone Gate, RR) plus optional validators and meta layers.

### Already CITED

`crt_engine.py`, `heuristic_gaussian_engine.py`, `ml_gaussian_engine.py`, `rr_engine.py`, `scoring_engine.py`, `zone_gate_engine.py` — see **Ch.10**.

### Encyclopedia entries — support / optional

### `src/engines/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Package exports for scoring engines.
- **Chapter:** Ch.10.

### `src/engines/gaussian_engine.py`
- **Group:** A · **Relevance:** SHIM · **Book:** DIR_ORIENTED
- **Purpose:** Backward-compatibility shim; canonical implementations are heuristic / ML Gaussian modules.
- **Relationships:** Prefer `heuristic_gaussian_engine.py` / `ml_gaussian_engine.py`.
- **Chapter:** Ch.10.

### `src/engines/live_engine.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Live trading decision helper + zone load path used by live hook (not the full HookedLiveEngine).
- **Relationships:** `live_engine_hook` subclasses / wraps live engine behaviors; zone registry load.
- **Entry points:** Live path; tests.
- **Chapter:** Ch.15.

### `src/engines/zone_cluster_score.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Pure zone cluster scoring shared by EngineRunner and historical zone tooling.
- **Relationships:** Zone gate / discover_zones pipelines.
- **Chapter:** Ch.10 Zone Gate.

### `src/engines/trap_validator_engine.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** DIR_ORIENTED
- **Purpose:** Data integrity / trap validation pre-gate (quality of setup, not fusion weight).
- **Relationships:** Optional pre-filter before or beside scoring.
- **Entry points:** Config when enabled; tests.
- **Chapter:** None dedicated.

### `src/engines/llm_engine.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** DIR_ORIENTED
- **Purpose:** Parallel engine wrapper around `llm_score_safe()` — advisory, fail-open class.
- **Relationships:** `llm_scorer` / inference client.
- **Chapter:** Ch.21 constraints (LLM not hot-path hard dep).

### `src/engines/tradenet_meta_engine.py`
- **Group:** A · **Relevance:** INERT / UNWIRED · **Book:** DIR_ORIENTED
- **Purpose:** TradeNet meta-cognition layer — fusion neural slot historically stubbed (F-005).
- **Relationships:** Not on active production path without TN qualification protocol.
- **Chapter:** Ch.10 / F-005; tradenet lineage audit.

---

## 4. `src/runtime/` — Backtest, live hook, baselines, probes

**Package role:** Run the spine over historical or live candles; capture baselines; optional observation tools.

### Already CITED

| File | Purpose | Chapter |
|---|---|---|
| `backtest_v2.py` | Candle-by-candle backtest harness | Ch.05, Ch.02 |
| `live_engine_hook.py` | `HookedLiveEngine.process` live tick entry | Ch.15 |

### Encyclopedia entries

### `src/runtime/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Package marker.
- **Chapter:** Ch.04.

### `src/runtime/baseline_capture.py`
- **Group:** A · **Relevance:** LIVE (governance hygiene) · **Book:** DIR_ORIENTED
- **Purpose:** Capture reproducible baseline manifest (schema hash, models, config SHA).
- **Relationships:** Pre-training / pre-migration hygiene.
- **Entry points:** `python src/runtime/baseline_capture.py --label …`
- **Chapter:** CLAUDE.md Phase 0; Ch.16.

### `src/runtime/unified_replay_harness.py`
- **Group:** A · **Relevance:** LIVE (research/ops) · **Book:** DIR_ORIENTED
- **Purpose:** Run execution-truth backtest (v2) and BitNet gate modes on same dataset; emit comparable artifacts.
- **Relationships:** Backtest + BitNet shadow configs.
- **Entry points:** Research / replay CLIs; determinism tests.
- **Chapter:** Ch.05; F-055 class.

### `src/runtime/backtest_bitnet.py`
- **Group:** A · **Relevance:** RESEARCH / SHADOW · **Book:** DIR_ORIENTED
- **Purpose:** Row-by-row backtest with BitNet as hard gatekeeper (shadow experiments).
- **Relationships:** BitNet package; shadow production configs.
- **Entry points:** Research scripts; F-055 shadow.
- **Chapter:** Ch.10 BitNet; F-004/F-055.

### `src/runtime/analyze_fusion_shadow.py`
- **Group:** A · **Relevance:** OBSERVE_ONLY · **Book:** DIR_ORIENTED
- **Purpose:** Analyze EngineRunner fusion shadow telemetry from collector logs.
- **Relationships:** `collector.py` JSONL.
- **Entry points:** Offline analysis CLI.
- **Chapter:** None.

### `src/runtime/crt_baseline_trace.py`
- **Group:** A · **Relevance:** OBSERVE_ONLY · **Book:** DIR_ORIENTED
- **Purpose:** Behavior-preserving CRT baseline observation / operand traces.
- **Relationships:** CRT engine diagnostics.
- **Entry points:** Forensic / baseline programs.
- **Chapter:** Ch.08 diagnostics.

### `src/runtime/crt_fail_reason_counters.py`
- **Group:** A · **Relevance:** OBSERVE_ONLY · **Book:** DIR_ORIENTED
- **Purpose:** Count CRT `try_*` fail reasons — observation only.
- **Relationships:** CRT funnel diagnostics.
- **Entry points:** Governance / CRT census tools.
- **Chapter:** Ch.08 / governance CRT artifacts.

### `src/runtime/exit_model_band.py`
- **Group:** A · **Relevance:** RESEARCH · **Book:** DIR_ORIENTED
- **Purpose:** Dual-bound exit-model reporting (trust-layer exit bands).
- **Relationships:** Research exit/cost studies (F-025 class).
- **Entry points:** Research scripts.
- **Chapter:** Ch.19 exit falsification.

---

## 5. `src/execution/` — Multi-signal execution loop (partial)

### Already CITED

`loop.py` — multi-signal execution loop; **built, tested, no live caller** (Ch.15).

### Encyclopedia entries

### `src/execution/__init__.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Package marker.
- **Chapter:** Ch.15.

### `src/execution/alert_manager.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Alerts for execution loop events (human-visible notifications).
- **Relationships:** `ExecutionLoop`; may bridge to Telegram later.
- **Entry points:** Loop when wired; tests.
- **Chapter:** Ch.15.

### `src/execution/override_handler.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Human/system overrides against automated execution decisions.
- **Relationships:** Execution loop; safety rail.
- **Entry points:** Loop when wired; tests.
- **Chapter:** Ch.15.

### `src/execution/execution_intent_v1_0.py`
- **Group:** A · **Relevance:** PARTIAL · **Book:** NOT_IN_BOOK
- **Purpose:** Human-in-the-loop execution intent state machine (v1.0 contract).
- **Relationships:** Distinct from CRT `ExecutionPlanner` intents; for loop-level intent lifecycle.
- **Entry points:** Execution loop / UAT; tests (`test_execution_*`).
- **Chapter:** Ch.15.

---

## 6. `src/live/` — Live broker / alert bridges

### `src/live/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Package marker for live bridges.
- **Chapter:** Ch.15.

### `src/live/mt5_bridge.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** MetaTrader 5 order execution bridge (IPC to terminal).
- **Relationships:** Live path after Ultron approve; requires MT5 running.
- **Entry points:** Live engine / operator setup.
- **Chapter:** Ch.15; external MT5.

### `src/live/telegram_bridge.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** DIR_ORIENTED
- **Purpose:** Telegram bot alerts for signals / status.
- **Relationships:** Live engine optional notifications (not capital authority).
- **Entry points:** Live config with bot token (secrets in `.env` — never commit).
- **Chapter:** Ch.15.

---

## 7. `src/inout/` — Market data I/O (not the archived strategy rail)

**Resolved in Ch.15:** fetchers only; archived parallel spine is `archive/inout_legacy/`.

### `src/inout/mt5_candle_fetcher.py`
- **Group:** A · **Relevance:** LIVE · **Book:** DIR_ORIENTED
- **Purpose:** Fetch M15 (etc.) OHLCV from MT5 → CSV for CandleLoader.
- **Entry points:** `scripts/data/fetch_candles_mt5.py`.
- **Chapter:** Ch.05, Ch.15.

### `src/inout/alphavantage_candle_fetcher.py`
- **Group:** A · **Relevance:** LIVE (data) · **Book:** DIR_ORIENTED
- **Purpose:** Alpha Vantage FX intraday → CSV (premium limits apply).
- **Chapter:** Ch.05.

### `src/inout/hummingbot_candle_fetcher.py`
- **Group:** A · **Relevance:** LIVE (data) · **Book:** DIR_ORIENTED
- **Purpose:** Exchange OHLCV via hummingbot-supported venues → CSV.
- **Chapter:** Ch.05.

### `src/inout/perp_funding_fetcher.py`
- **Group:** A · **Relevance:** RESEARCH / LIVE-data · **Book:** DIR_ORIENTED
- **Purpose:** Binance USDⓈ-M perpetual funding/basis inputs for carry research (Programs 6/6b).
- **Chapter:** Ch.19 P6; Ch.05.

---

## 8. `src/control_plane/` — Localhost command catalog + dashboard

### Already CITED

`registry.py` (`CommandSpec` catalog), `server.py` (stdlib HTTP localhost:8787) — **Ch.22**.

### Encyclopedia entries

### `src/control_plane/__init__.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Package exports for control plane.
- **Chapter:** Ch.22.

### `src/control_plane/cp_types.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** `ArgSpec`, `CommandSpec`, `RunRecord` dataclasses for the catalog and job history.
- **Relationships:** `registry.py`, `jobs.py`, `server.py`.
- **Chapter:** Ch.22; schemas.

### `src/control_plane/jobs.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** `JobManager` — queue and run control-plane commands as subprocesses.
- **Relationships:** Server API → subprocess argv from CommandSpec.
- **Entry points:** Dashboard “run command”; localhost only.
- **Chapter:** Ch.22.

### `src/control_plane/dashboard_api.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Read-only data API for the CRT trading dashboard UI.
- **Relationships:** Server routes; log/artifact readers.
- **Chapter:** Ch.22.

### `src/control_plane/monitors.py`
- **Group:** A · **Relevance:** LIVE · **Book:** NOT_IN_BOOK
- **Purpose:** Dashboard monitor specs (jsonl-tail / json / regex / file-stat sources).
- **Relationships:** Dashboard live panels.
- **Chapter:** Ch.22.

### `src/control_plane/report_api.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Run history reports (Excel) + optional LLM analysis.
- **Relationships:** Job history; LLM client.
- **Chapter:** Ch.22 adjacent.

### `src/control_plane/context_report.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** ContextReportAPI — architecture analyst pack for a run (LLM-assisted).
- **Relationships:** `code_context_extractor`, `dot_graph_context`.
- **Chapter:** Ch.22 / multi-LLM ops.

### `src/control_plane/code_context_extractor.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** AST-based code extraction for context reports.
- **Chapter:** Ch.22.

### `src/control_plane/dot_graph_context.py`
- **Group:** A · **Relevance:** SIDECAR · **Book:** NOT_IN_BOOK
- **Purpose:** Flow resolution + architectural graph context (`.dot`) for reports.
- **Relationships:** `graph.dot` / pyan outputs when present.
- **Chapter:** Ch.04 / Ch.22.

---

## E1 coverage rollup

| Package | Exact CITED (pre-E1 book) | E1 encyclopedia entries added | Residual risk |
|---|---:|---|---|
| core | 4 | 16 supporting modules mapped | Controllers may be config-off — verify before assuming LIVE |
| config_layer | 7 | 21 modules mapped | F-057 / rr_fusion disabled still apply |
| engines | 6 | 7 support modules mapped | TradeNet/LLM inert unless enabled |
| runtime | 2 | 8 modules mapped | Observation tools must stay OBSERVE_ONLY |
| execution | 1 | 4 modules mapped | Loop still unwired to live |
| live | 0 | 3 modules mapped | Secrets never in docs |
| inout | 0 | 4 fetchers mapped | ≠ archived strategy rail |
| control_plane | 2 | 9 modules mapped | localhost-only, no auth |

**E1 exit criterion (charter):** every Group A spine-package **`.py` file** has a purpose/relevance row above (or is a trivial empty `__init__` noted as package marker). **Met.**

**Not claimed:** full call-graph proof for every optional controller; economic authority for any sidecar.

---

## Next

- **E2** — `src/research/` + research scripts index (category + driver map, not 142 essays).
- Optional **E1b** — `src/features/` file encyclopedia (registry package depth) if spine feature math is the next editing focus.

---
**Related chapters:** [00](../00-quick-start.md) · [08](../08-crt-state-machine.md) · [10](../10-four-scoring-engines.md) · [11–15](../11-fusion.md) · [16](../16-config-first-and-promotion.md) · [22](../22-control-plane.md) · [24](../24-repository-encyclopedia.md)
