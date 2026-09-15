# Codebase Navigation (LLM Jump Map)

Purpose: first-open map for coding LLMs working in this repo. Use it to locate runtime entry points, packages, configs, tests, docs, and governance surfaces without scanning the whole tree. Prefer the linked paths below over inventing structure; sibling indexes are listed under [Related maps](#related-maps).

Branch context when written: `feature/trace-parquet-duckdb-query`. Remote: `https://github.com/Chaithu1995-0312/TradeHlt.git`.

---

## Start here

| Need | Jump to |
|------|---------|
| Package / CLI metadata | [`../pyproject.toml`](../pyproject.toml) · [`../README.md`](../README.md) |
| Agent / LLM operating notes | [`../CLAUDE.md`](../CLAUDE.md) · [`../AGENTS.md`](../AGENTS.md) · [`../GROK.md`](../GROK.md) · [`../HANDOFF.md`](../HANDOFF.md) |
| Active production config pin | [`../configs/production/ACTIVE_VERSION`](../configs/production/ACTIVE_VERSION) → currently `v2_htfcrt_2026_08` · [`../configs/production/v2_htfcrt_2026_08.json`](../configs/production/v2_htfcrt_2026_08.json) |
| Active model registry | [`../active_models.yaml`](../active_models.yaml) · [`../models/README.md`](../models/README.md) |
| Live / rail runtime | [`../src/runtime/live_rail_orchestrator.py`](../src/runtime/live_rail_orchestrator.py) · [`../scripts/live/run_live_rail.py`](../scripts/live/run_live_rail.py) · [`../src/engines/live_engine.py`](../src/engines/live_engine.py) |
| Core decision / fusion loop | [`../src/core/engine_runner.py`](../src/core/engine_runner.py) · [`../src/core/decision_engine.py`](../src/core/decision_engine.py) · [`../src/core/fusion_engine.py`](../src/core/fusion_engine.py) |
| CRT / feature spine | [`../src/features/feature_pipeline.py`](../src/features/feature_pipeline.py) · [`../src/features/crt_state_resolver.py`](../src/features/crt_state_resolver.py) · [`../src/engines/crt_engine.py`](../src/engines/crt_engine.py) |
| Tests entry | [`../tests/conftest.py`](../tests/conftest.py) · [`../docs/reference/testing.md`](reference/testing.md) |
| Research docs & readiness | [`research/`](research/) · [`research-readiness/`](research-readiness/) · [`../src/research/`](../src/research/) |
| Governance / semantic OS | [`governance/`](governance/) · [`../src/governance/semantic_os.py`](../src/governance/semantic_os.py) · [`../RESOLUTION_REGISTRY.md`](../RESOLUTION_REGISTRY.md) |
| Parquet / DuckDB helpers | [`../src/utils/parquet_store.py`](../src/utils/parquet_store.py) · [`../src/utils/duckdb_query.py`](../src/utils/duckdb_query.py) · [`../tests/test_duckdb_query.py`](../tests/test_duckdb_query.py) · [`../tests/test_parquet_store.py`](../tests/test_parquet_store.py) · [`../.grok/PARQUET_BOT_BRIEF.md`](../.grok/PARQUET_BOT_BRIEF.md) |

---

## Top-level tree (meaningful source)

Source / control surfaces (open these):

```text
Tradelatest/
├── src/                 # Python packages (production + research code)
├── scripts/             # Runnable CLIs / jobs by domain
├── tests/               # Pytest suite + fixtures
├── docs/                # Architecture, governance, research, ops docs
├── configs/             # Production / research / formula YAML+JSON
├── models/              # Serialized model artifacts + registries
├── tools/               # Adjunct tooling (tv_forensic, oss_lab, cpp)
├── research/            # Hypothesis packages (H-G001-*)
├── .grok/               # Grok working indexes / HOW maps
├── .github/             # CI / workflows
├── hooks/               # Git / process hooks
├── runtime/             # Thin runtime host (e.g. exec_telemetry)
├── multi_llm/           # Multi-LLM workspace (top-level)
├── mt5_analytics/       # MT5 analytics package surface
├── oss_lab/             # OSS lab experiments
├── manual_tools/        # Manual operator tools
├── agent-tools/         # Agent tool bundles
├── context/             # Context packs
├── flow_context/        # Flow-context layer assets
├── flow_graphs/         # Graph artifacts
├── bundles/             # Packaged bundles
├── archive/             # Archived material (not primary source)
├── pyproject.toml
├── active_models.yaml
├── CLAUDE.md / AGENTS.md / GROK.md / README.md / HANDOFF.md
└── RESOLUTION_REGISTRY.md / MASTER_ARCHITECTURE_REFERENCE.md / CODEBASE_WIRING_QUICKREF.md
```

Data / runtime artifacts (not primary source — usually large or generated; skip unless debugging runs):

| Path | Role |
|------|------|
| `data/` | Market / corpus data blobs |
| `logs/` | Run logs |
| `results/` | Experiment / backtest outputs |
| `reports/` | Generated reports |
| `.venv/` · `venv/` | Local Python envs |
| `.pytest_cache/` · `__pycache__/` | Caches |
| `exec_telemetry/` · `terminals/` · `xauusd_backtest_run/` · `_l003_scratch/` | Telemetry / scratch / run workspaces |
| `copiedSrcFiles/` · `ChatGpt  workflow/` · `grokconcated*` · package dirs like `H-SECONDLOW-002_*` | Working copies / packages — treat as secondary |

---

## `src/` packages

| Package | Purpose | Key files / dirs |
|---------|---------|------------------|
| [`../src/core/`](../src/core/) | Decision, fusion, feature store, Ultron risk, model registry | [`engine_runner.py`](../src/core/engine_runner.py) · [`decision_engine.py`](../src/core/decision_engine.py) · [`fusion_engine.py`](../src/core/fusion_engine.py) · [`feature_store.py`](../src/core/feature_store.py) · [`model_registry.py`](../src/core/model_registry.py) · [`ultron_risk_gate.py`](../src/core/ultron_risk_gate.py) |
| [`../src/engines/`](../src/engines/) | Scoring / CRT / RR / zone / TradeNet engines | [`crt_engine.py`](../src/engines/crt_engine.py) · [`live_engine.py`](../src/engines/live_engine.py) · [`rr_engine.py`](../src/engines/rr_engine.py) · [`gaussian_engine.py`](../src/engines/gaussian_engine.py) · [`zone_gate_engine.py`](../src/engines/zone_gate_engine.py) · [`tradenet_meta_engine.py`](../src/engines/tradenet_meta_engine.py) |
| [`../src/features/`](../src/features/) | Feature pipeline, CRT state, formula registries, SMC | [`feature_pipeline.py`](../src/features/feature_pipeline.py) · [`crt_state_resolver.py`](../src/features/crt_state_resolver.py) · [`crt_feature_builder.py`](../src/features/crt_feature_builder.py) · [`formula_registry.py`](../src/features/formula_registry.py) · [`registry/`](../src/features/registry/) · [`smc/`](../src/features/smc/) |
| [`../src/config_layer/`](../src/config_layer/) | Production config loaders, CRT config, model path resolution | [`production_config.py`](../src/config_layer/production_config.py) · [`production_bundle.py`](../src/config_layer/production_bundle.py) · [`model_resolver.py`](../src/config_layer/model_resolver.py) · [`crt_engine_v2.py`](../src/config_layer/crt_engine_v2.py) · [`state_contract.py`](../src/config_layer/state_contract.py) · [`rr/`](../src/config_layer/rr/) |
| [`../src/runtime/`](../src/runtime/) | Backtest / live rail / CRT traces / unified replay | [`live_rail_orchestrator.py`](../src/runtime/live_rail_orchestrator.py) · [`live_rail_feeder.py`](../src/runtime/live_rail_feeder.py) · [`backtest_v2.py`](../src/runtime/backtest_v2.py) · [`unified_replay_harness.py`](../src/runtime/unified_replay_harness.py) · [`crt_baseline_trace.py`](../src/runtime/crt_baseline_trace.py) |
| [`../src/live/`](../src/live/) | MT5 / Telegram / order bridges | [`mt5_bridge.py`](../src/live/mt5_bridge.py) · [`order_manager.py`](../src/live/order_manager.py) · [`telegram_bridge.py`](../src/live/telegram_bridge.py) |
| [`../src/inout/`](../src/inout/) | Market data fetchers + live rail adapters | [`mt5_candle_fetcher.py`](../src/inout/mt5_candle_fetcher.py) · [`live_rail/`](../src/inout/live_rail/) · [`live_rail/binance_ws_adapter.py`](../src/inout/live_rail/binance_ws_adapter.py) · [`live_rail/bar_builder.py`](../src/inout/live_rail/bar_builder.py) |
| [`../src/execution/`](../src/execution/) | Execution loop / intents / alerts | [`loop.py`](../src/execution/loop.py) · [`execution_intent_v1_0.py`](../src/execution/execution_intent_v1_0.py) · [`alert_manager.py`](../src/execution/alert_manager.py) |
| [`../src/strategies/`](../src/strategies/) | Strategy registry + S01–S10 wrappers | [`strategy_registry.py`](../src/strategies/strategy_registry.py) · [`strategy_orchestrator.py`](../src/strategies/strategy_orchestrator.py) · [`s01_crt_wrapper.py`](../src/strategies/s01_crt_wrapper.py) · [`base_strategy.py`](../src/strategies/base_strategy.py) |
| [`../src/governance/`](../src/governance/) | Semantic OS, registries, promotion, provenance | [`semantic_os.py`](../src/governance/semantic_os.py) · [`script_registry.py`](../src/governance/script_registry.py) · [`hypothesis_registry.py`](../src/governance/hypothesis_registry.py) · [`promotion_manager.py`](../src/governance/promotion_manager.py) · [`orchestrator.py`](../src/governance/orchestrator.py) |
| [`../src/research/`](../src/research/) | Research runners + family packages (sujan_crt, episodes, …) | [`runner.py`](../src/research/runner.py) · [`registry.py`](../src/research/registry.py) · [`cli.py`](../src/research/cli.py) · [`sujan_crt/`](../src/research/sujan_crt/) · [`episodes/`](../src/research/episodes/) · [`zone_mapping/`](../src/research/zone_mapping/) · [`model_runners/`](../src/research/model_runners/) |
| [`../src/data_ingestion/`](../src/data_ingestion/) | OHLCV schema, corpus gate, dataset registry | [`ohlcv_schema.py`](../src/data_ingestion/ohlcv_schema.py) · [`dataset_registry.py`](../src/data_ingestion/dataset_registry.py) · [`corpus_gate.py`](../src/data_ingestion/corpus_gate.py) · [`historical_fetcher.py`](../src/data_ingestion/historical_fetcher.py) |
| [`../src/control_plane/`](../src/control_plane/) | Jobs, monitors, dashboard / report APIs | [`server.py`](../src/control_plane/server.py) · [`jobs.py`](../src/control_plane/jobs.py) · [`registry.py`](../src/control_plane/registry.py) · [`dashboard_api.py`](../src/control_plane/dashboard_api.py) |
| [`../src/msip/`](../src/msip/) | MSIP shadow market-state interpretation | [`shadow_emitter.py`](../src/msip/shadow_emitter.py) · [`market_state_vector.py`](../src/msip/market_state_vector.py) · [`isolation.py`](../src/msip/isolation.py) |
| [`../src/bitnet/`](../src/bitnet/) | BitNet training / inference / registry | [`bitnet_runner.py`](../src/bitnet/bitnet_runner.py) · [`bitnet_inference.py`](../src/bitnet/bitnet_inference.py) · [`bitnet_registry.py`](../src/bitnet/bitnet_registry.py) · [`composition.py`](../src/bitnet/composition.py) |
| [`../src/training/`](../src/training/) | Train pipelines / TradeNet v2 | [`train_pipeline.py`](../src/training/train_pipeline.py) · [`trainer.py`](../src/training/trainer.py) · [`trade_net_v2.py`](../src/training/trade_net_v2.py) · [`evaluator.py`](../src/training/evaluator.py) |
| [`../src/portfolio/`](../src/portfolio/) | Allocation / correlation / exposure | [`allocator.py`](../src/portfolio/allocator.py) · [`correlation_engine.py`](../src/portfolio/correlation_engine.py) · [`exposure_tracker.py`](../src/portfolio/exposure_tracker.py) |
| [`../src/regime/`](../src/regime/) | Regime classification / routing | [`regime_classifier.py`](../src/regime/regime_classifier.py) · [`config_router.py`](../src/regime/config_router.py) |
| [`../src/replay/`](../src/replay/) | Replay memory / timing | [`replay_memory_engine.py`](../src/replay/replay_memory_engine.py) · [`timing_advisor.py`](../src/replay/timing_advisor.py) |
| [`../src/agent/`](../src/agent/) | In-repo agent core / tools / intent | [`agent_core.py`](../src/agent/agent_core.py) · [`intent_router.py`](../src/agent/intent_router.py) · [`tool_registry.py`](../src/agent/tool_registry.py) · [`executor.py`](../src/agent/executor.py) · [`modes/`](../src/agent/modes/) |
| [`../src/utils/`](../src/utils/) | Shared stores, logging, DuckDB | [`parquet_store.py`](../src/utils/parquet_store.py) · [`duckdb_query.py`](../src/utils/duckdb_query.py) · [`logging_config.py`](../src/utils/logging_config.py) · [`run_manifest.py`](../src/utils/run_manifest.py) |
| Other packages | Supporting domains | [`../src/analytics/`](../src/analytics/) · [`../src/charts/`](../src/charts/) · [`../src/cognitive/`](../src/cognitive/) · [`../src/events/`](../src/events/) · [`../src/expansion/`](../src/expansion/) · [`../src/feedback/`](../src/feedback/) · [`../src/identity/`](../src/identity/) · [`../src/interpreters/`](../src/interpreters/) · [`../src/journal/`](../src/journal/) · [`../src/llm_research/`](../src/llm_research/) · [`../src/monitoring/`](../src/monitoring/) · [`../src/multi_llm/`](../src/multi_llm/) · [`../src/retrieval/`](../src/retrieval/) · [`../src/scanner/`](../src/scanner/) · [`../src/search/`](../src/search/) · [`../src/structure/`](../src/structure/) · [`../src/uat/`](../src/uat/) · [`../src/ui/`](../src/ui/) · [`../src/validation_access/`](../src/validation_access/) |

---

## `scripts/`

| Area | Purpose | Entry examples |
|------|---------|----------------|
| [`../scripts/live/`](../scripts/live/) | Live rail runner | [`run_live_rail.py`](../scripts/live/run_live_rail.py) |
| [`../scripts/governance/`](../scripts/governance/) | Registries, provenance, feature DAG certs, promotion | [`query_registry.py`](../scripts/governance/query_registry.py) · [`promote_v2.py`](../scripts/governance/promote_v2.py) · [`seed_semantic_os.py`](../scripts/governance/seed_semantic_os.py) · [`feature_dag_certify.py`](../scripts/governance/feature_dag_certify.py) · [`construction_protocol.py`](../scripts/governance/construction_protocol.py) |
| [`../scripts/research/`](../scripts/research/) | Research / CRT / zone / BitNet job scripts | [`build_episodes.py`](../scripts/research/build_episodes.py) · [`build_trace_corpus.py`](../scripts/research/build_trace_corpus.py) · [`crt_parity_sweep.py`](../scripts/research/crt_parity_sweep.py) · [`analyze_trace_corpus.py`](../scripts/research/analyze_trace_corpus.py) |
| [`../scripts/backtest/`](../scripts/backtest/) | Backtest drivers | (dir) |
| [`../scripts/data/`](../scripts/data/) | Data build / ingest helpers | (dir) |
| [`../scripts/evaluation/`](../scripts/evaluation/) | Eval jobs | (dir) |
| [`../scripts/training/`](../scripts/training/) | Training jobs | (dir) |
| [`../scripts/control_plane/`](../scripts/control_plane/) | Control-plane CLIs | (dir) |
| [`../scripts/multi_llm/`](../scripts/multi_llm/) | Multi-LLM scripts | (dir) |
| [`../scripts/analysis/`](../scripts/analysis/) · [`metrics/`](../scripts/metrics/) · [`export/`](../scripts/export/) · [`maintenance/`](../scripts/maintenance/) · [`probes/`](../scripts/probes/) · [`portfolio/`](../scripts/portfolio/) · [`context/`](../scripts/context/) · [`misc/`](../scripts/misc/) | Supporting domains | — |
| Root scripts | Doc / registry / validation helpers | [`../scripts/validate_integration.py`](../scripts/validate_integration.py) · [`../scripts/export_model_registry.py`](../scripts/export_model_registry.py) · [`../scripts/rag_index.py`](../scripts/rag_index.py) · [`../scripts/update_config_hash.py`](../scripts/update_config_hash.py) |

---

## `tests/`

| Area | Purpose |
|------|---------|
| [`../tests/conftest.py`](../tests/conftest.py) | Shared fixtures |
| Root `test_*.py` | Large flat suite covering CRT, features, governance, engines, DuckDB, configs, BitNet, MSIP, zones, … |
| [`../tests/features/`](../tests/features/) · [`engines/`](../tests/engines/) · [`governance/`](../tests/governance/) · [`research/`](../tests/research/) · [`runtime/`](../tests/runtime/) · [`execution/`](../tests/execution/) · [`replay/`](../tests/replay/) · [`regime/`](../tests/regime/) · [`config_layer/`](../tests/config_layer/) · [`data_ingestion/`](../tests/data_ingestion/) · [`inout/`](../tests/inout/) | Package-aligned suites |
| [`../tests/fixtures/`](../tests/fixtures/) · [`golden/`](../tests/golden/) · [`harness/`](../tests/harness/) · [`helpers/`](../tests/helpers/) | Fixtures / golden / harness |
| Notable branch-relevant tests | [`../tests/test_duckdb_query.py`](../tests/test_duckdb_query.py) · [`../tests/test_parquet_store.py`](../tests/test_parquet_store.py) · [`../tests/test_query_trace.py`](../tests/test_query_trace.py) |

Docs: [`reference/testing.md`](reference/testing.md).

---

## `docs/`

| Area | Purpose | Start |
|------|---------|-------|
| This file | LLM jump map | [`CODEBASE_NAVIGATION.md`](CODEBASE_NAVIGATION.md) |
| Root docs | Intent / strategies / history | [`readme.md`](readme.md) · [`knowledge-map.md`](knowledge-map.md) · [`intent_to_code_map.md`](intent_to_code_map.md) · [`STRATEGIES.md`](STRATEGIES.md) · [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) · [`behavior_contracts.md`](behavior_contracts.md) |
| [`architecture/`](architecture/) | Architecture & wiring maps | [`code-map.md`](architecture/code-map.md) · [`codebase-wiring-guide.md`](architecture/codebase-wiring-guide.md) · [`three-layer-codebase-atlas.md`](architecture/three-layer-codebase-atlas.md) · [`signal-flow.md`](architecture/signal-flow.md) · [`entry-exit-map.md`](architecture/entry-exit-map.md) |
| [`governance/`](governance/) | Contracts, registries, CRT/MSIP/feature authority | [`SEMANTIC_OS_CONTRACT.md`](governance/SEMANTIC_OS_CONTRACT.md) · [`PHYSICAL_STORAGE_ARCHITECTURE.md`](governance/PHYSICAL_STORAGE_ARCHITECTURE.md) · [`MEASUREMENT_CONTRACT.md`](governance/MEASUREMENT_CONTRACT.md) · [`CORPUS_AUTHORITY.md`](governance/CORPUS_AUTHORITY.md) · [`GITIGNORE_SCHEMA.md`](governance/GITIGNORE_SCHEMA.md) |
| [`reference/`](reference/) | Config / CLI / testing / governance refs | [`config-reference.md`](reference/config-reference.md) · [`script-matrix.md`](reference/script-matrix.md) · [`cli-matrix.md`](reference/cli-matrix.md) · [`testing.md`](reference/testing.md) · [`governance.md`](reference/governance.md) |
| [`operations/`](operations/) | Current ops state | [`CURRENT_STATE.md`](operations/CURRENT_STATE.md) · [`TRUST_TIER_INDEX.md`](operations/TRUST_TIER_INDEX.md) · [`DEPENDENCY_GRAPH.md`](operations/DEPENDENCY_GRAPH.md) |
| [`research/`](research/) · [`research-readiness/`](research-readiness/) | Research reports & readiness packs | dirs |
| [`design/`](design/) · [`plans/`](plans/) · [`implementation_plan/`](implementation_plan/) · [`control_plane/`](control_plane/) · [`handover/`](handover/) · [`intent/`](intent/) · [`topics/`](topics/) · [`book/`](book/) · [`memory/`](memory/) · [`analysis/`](analysis/) | Design / plans / handover / topics | dirs |

---

## `configs/` · `models/` · governance · research · tools

### Configs

| Path | Purpose |
|------|---------|
| [`../configs/production/`](../configs/production/) | Pinned production stacks (`ACTIVE_VERSION`, `v2_htfcrt_2026_08.json`, `v4_*`, …) |
| [`../configs/research/`](../configs/research/) | Research configs + `experiments/`, `measurement_contracts/`, `provenance/` |
| [`../configs/control_plane/`](../configs/control_plane/) | e.g. [`monitors.json`](../configs/control_plane/monitors.json) |
| [`../configs/formulas/`](../configs/formulas/) · [`market_reality/`](../configs/market_reality/) · [`data_provenance/`](../configs/data_provenance/) · [`experimental/`](../configs/experimental/) | Formula / market / provenance / experimental configs |
| [`../configs/promotion_log.jsonl`](../configs/promotion_log.jsonl) | Promotion log |

### Models

| Path | Purpose |
|------|---------|
| [`../models/README.md`](../models/README.md) | Local model occupancy rules |
| Registries | [`../models/zone_registry.json`](../models/zone_registry.json) · [`../models/rr_registry.json`](../models/rr_registry.json) · [`../models/tradenet_registry.json`](../models/tradenet_registry.json) · [`../models/gaussian_registry.json`](../models/gaussian_registry.json) · [`../models/zone_gate_registry.json`](../models/zone_gate_registry.json) |
| Per-symbol dirs | [`../models/XAUUSD/`](../models/XAUUSD/) · `BTCUSDT/` · `ETHUSDT/` · `EURUSD/` · `BNBUSDT/` · `SOLUSDT/` · [`bitnet/`](../models/bitnet/) · [`replay/`](../models/replay/) |
| Root registry (tracked intent) | [`../active_models.yaml`](../active_models.yaml) |

### Top-level research & tools

| Path | Purpose |
|------|---------|
| [`../research/`](../research/) | Hypothesis packages (`H-G001-001`, `H-G001-001b`) |
| [`../tools/tv_forensic/`](../tools/tv_forensic/) | TradingView forensic probes / shots |
| [`../tools/oss_lab/`](../tools/oss_lab/) | OSS lab / codebase-memory tooling |
| [`../tools/cpp/`](../tools/cpp/) | C++ adjunct tools |
| [`../tools/btcusdt_crt_v3_replay.py`](../tools/btcusdt_crt_v3_replay.py) | BTCUSDT CRT v3 replay helper |
| [`../.grok/`](../.grok/) | HOW index, infra notes, parquet brief | [`HOW_INDEX.md`](../.grok/HOW_INDEX.md) · [`INFRA.md`](../.grok/INFRA.md) · [`PARQUET_BOT_BRIEF.md`](../.grok/PARQUET_BOT_BRIEF.md) · [`GOAL.md`](../.grok/GOAL.md) |

---

## Cross-links (related areas)

```text
Live path
  scripts/live/run_live_rail.py
    → src/runtime/live_rail_orchestrator.py
    → src/inout/live_rail/*  +  src/live/mt5_bridge.py
    → src/engines/live_engine.py
    → src/core/engine_runner.py  ↔  configs/production/ACTIVE_VERSION
    → tests/runtime/  +  tests/test_*live* / test_execution_loop.py

CRT / feature spine
  configs/production/v*_*.json  +  configs/formulas/
    ↔ src/config_layer/production_config.py / crt_engine_v2.py
    ↔ src/features/feature_pipeline.py / crt_state_resolver.py
    ↔ src/engines/crt_engine.py
    ↔ docs/governance/*crt*  +  tests/test_crt_* / tests/features/

Research loop
  configs/research/*  +  docs/research-readiness/*
    ↔ src/research/runner.py + family packages
    ↔ scripts/research/*
    ↔ tests/research/
    ↔ models/* registries (read-only artifacts)

Governance / promotion
  src/governance/*  ↔  scripts/governance/*
    ↔ docs/governance/*  ↔  RESOLUTION_REGISTRY.md
    ↔ configs/promotion_log.jsonl  ↔  tests/governance/

Storage / query (this branch theme)
  src/utils/parquet_store.py  ↔  src/utils/duckdb_query.py
    ↔ tests/test_parquet_store.py  ↔  tests/test_duckdb_query.py
    ↔ .grok/PARQUET_BOT_BRIEF.md  ↔  docs/governance/PHYSICAL_STORAGE_ARCHITECTURE.md
```

| From | Also open |
|------|-----------|
| Changing production behavior | `configs/production/` + `src/config_layer/` + matching `tests/test_crt_config_*` / `test_config_*` |
| Changing live rail | `src/runtime/live_rail_*` + `src/inout/live_rail/` + `scripts/live/` + `tests/inout/` / `tests/runtime/` |
| Changing strategies | `src/strategies/` + `docs/STRATEGIES.md` + `tests/test_strategy_*` |
| Changing models on disk | `models/README.md` + `active_models.yaml` + `src/core/model_registry.py` / `src/config_layer/model_resolver.py` |
| Changing semantic / script registries | `src/governance/semantic_os.py` + `scripts/governance/seed_*.py` + `docs/governance/SEMANTIC_OS_CONTRACT.md` |

---

## Related maps

Do **not** overwrite these; this file is a complementary filesystem jump map:

| Sibling map | Role |
|-------------|------|
| [`../CLAUDE.md`](../CLAUDE.md) · [`../AGENTS.md`](../AGENTS.md) · [`../GROK.md`](../GROK.md) | Agent operating instructions |
| [`../.grok/HOW_INDEX.md`](../.grok/HOW_INDEX.md) | Grok HOW / workflow index |
| [`knowledge-map.md`](knowledge-map.md) · [`intent_to_code_map.md`](intent_to_code_map.md) | Intent / knowledge navigation |
| [`architecture/code-map.md`](architecture/code-map.md) · [`architecture/codebase-state-map.md`](architecture/codebase-state-map.md) · [`architecture/three-layer-codebase-atlas.md`](architecture/three-layer-codebase-atlas.md) · [`architecture/codebase-wiring-guide.md`](architecture/codebase-wiring-guide.md) | Architecture / wiring atlases |
| [`../CODEBASE_WIRING_QUICKREF.md`](../CODEBASE_WIRING_QUICKREF.md) · [`../MASTER_ARCHITECTURE_REFERENCE.md`](../MASTER_ARCHITECTURE_REFERENCE.md) | Root wiring / architecture refs |
| [`../RESOLUTION_REGISTRY.md`](../RESOLUTION_REGISTRY.md) | Resolution registry |

---

*Generated as a navigation layer for coding LLMs. Links are relative to `docs/`. Prefer verifying paths on disk before large refactors.*
