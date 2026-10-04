# Codebase Wiring Guide

> **Last updated**: 2026-07-17
> **Artifact version**: analysis_results.json + graph.dot (regenerated)

## Overview

The Tradelatest trading system is composed of **351 modules** across **36 packages**, connected by **696 import dependencies**. This guide explains the module architecture, critical paths, and how to navigate the dependency graph.

### Key Statistics

- **Total modules**: 351
- **Total dependencies**: 696
- **Packages**: 36
- **Circular dependencies**: 5 (minor config-layer cycles)
- **Flow isolation**: Perfect (7 flows, 0 boundary deps each)

## Architecture Tiers

The codebase is organized in five tiers:

### Tier 0: Core Runtime Engine (Hot Path)
The spine: OHLCV → Features → Score → Fuse → Decide → Execute → Risk.

**Modules**: `core.engine_runner`, `core.decision_engine`, `core.fusion_engine`, `features.feature_pipeline`, `engines.crt_engine`

**Characteristics**:
- Lowest latency critical path
- Called on every candle
- Maximum coupling (high in-degree)
- Governed by config `production_config.json`

### Tier 1: Scoring Engines
Four independent engines feed the fusion layer.

**Modules**: `engines.crt_engine`, `engines.heuristic_gaussian_engine`, `engines.ml_gaussian_engine`, `engines.zone_gate_engine`, `engines.rr_engine`

**Pattern**: Each engine is autonomous (low coupling) but converges on `core.fusion_engine`.

### Tier 2: Infrastructure
Config, logging, utilities, data ingestion.

**Modules**: `config_layer.*`, `utils.*`, `data_ingestion.*`, `events.*`

**Bottlenecks**:
- `config_layer.production_config` (54 in-edges): The central config source
- `utils.logging_config` (36 in-edges): Every module logs
- `features.feature_schema` (35 in-edges): 38-dim canonical schema

### Tier 3: Features & Analysis
Feature engineering, training, analytics.

**Modules**: `features.*`, `training.*`, `analytics.*`, `strategies.*`

**Independence**: Mostly isolated from hot path (called periodically, not on every candle).

### Tier 4: Research & Tooling
Experimental code, analysis scripts, agent tools.

**Modules**: `research.*`, `agent.*`, `control_plane.*`, `governance.*`

**Volatility**: High; experimental code changes frequently without impacting production.

---

## Package Topology

### By Module Count (Top 10)

| Package | Modules | Role |
|---------|---------|------|
| **research** | 77 | Experimental pipeline, program evaluation, probes |
| **config_layer** | 22 | Config loading, validation, CRT engine, execution planner |
| **core** | 20 | Engine runner, decision engine, fusion, gates |
| **features** | 20 | Feature pipeline, schema, registry, candle math |
| **agent** | 19 | LLM integration, tool planning, governance modes |
| **utils** | 18 | Logging, integrity events, serialization, helpers |
| **strategies** | 16 | Strategy orchestration, results, base classes |
| **governance** | 14 | Promotion, validation, audit, policy |
| **engines** | 12 | Individual scorers (CRT, Gaussian, RR, ZoneGate) |
| **control_plane** | 11 | HTTP server, dashboard, registry, monitors |

---

## Critical Dependency Paths

### Path 1: Config → Runtime (Configuration Authority)
```
configs/production/*.json
  ↓
config_layer.production_config (54 consumers)
  ↓
core.engine_runner (orchestrator)
  ↓
config_layer.crt_engine_v2 (CRT state machine)
  ↓
engines.crt_engine (scoring)
```

**What**: Configuration flows from JSON files → `production_config` → orchestrators → engines.

**Why it matters**: A config error propagates to every engine. See `config_layer.config_validator` for validation gates.

**How to modify**: Edit `configs/production/v2_multi_2026_04.json`, then run `python scripts/maintenance/_compute_hash.py` before promotion.

---

### Path 2: Features → Scoring (Signal Pipeline)
```
data_ingestion.dataset_integrity
  ↓
features.feature_pipeline (38-dim builder)
  ↓
features.feature_schema (canonical 38-dim definition)
  ↓
core.engine_runner (feeds all engines)
  ↓
engines.crt_engine / engines.heuristic_gaussian_engine / engines.rr_engine / engines.zone_gate_engine
```

**What**: OHLCV candles → 38-dimensional feature vector → four independent scorers.

**Why it matters**: Feature changes affect every engine and backtest. The 38-dim schema is the contract.

**How to modify**: Add features to `features.feature_pipeline`, register in `features.feature_schema` (F-054 certification required).

---

### Path 3: Scores → Decision (Fusion & Acceptance)
```
engines.* (four scorers)
  ↓
core.fusion_engine (weighted average)
  ↓
core.decision_engine (applies thresholds)
  ↓
core.acceptance_controller (soft acceptance)
  ↓
core.ultron_risk_gate (hard risk check: SL/TP/RR)
```

**What**: Four engine scores fuse into a single accept/reject decision, gated by risk bounds.

**Why it matters**: The acceptance gates are the final filter before execution.

**How to modify**: Edit `config_layer.execution_planner` for SL/TP/RR logic; `core.ultron_risk_gate` for risk thresholds.

---

### Path 4: Decision → Execution (Trade Placement)
```
core.ultron_risk_gate.evaluate()
  ↓
runtime.live_engine_hook (live trade entry)
  ↓
execution.execution_intent_v1_0 (order spec)
  ↓
execution.alert_manager (entry/exit alerts)
  ↓
journal.trade_logger (PnL tracking)
```

**What**: Approved trades become execution orders and are logged for accounting.

**Why it matters**: The execution layer is where backtesting fiction meets live reality.

**How to modify**: Edit `runtime.live_engine_hook` for live-mode logic; `execution.execution_intent_v1_0` for order format.

---

## Circular Dependencies (Minor)

Five cycles detected, all in low-latency tiers (governance/config, not hot path):

### Cycle 1: LLM Inference
```
config_layer.llm_inference_client
  ↔ config_layer.llm_narrative
  ↔ config_layer.llm_scorer
```

**Impact**: None (LLM is a tie-breaker, disabled by default).

**Resolution**: Acceptable; these are utility functions that co-depend.

### Cycle 2: CRT State Contract
```
config_layer.crt_engine_v2
  ↔ config_layer.state_contract_loader
  ↔ config_layer.state_topology
```

**Impact**: None (state machine is stable).

**Resolution**: Acceptable; the state topology and contract are inextricably linked.

### Cycle 3: Training Loop
```
training.trainer
  ↔ training.trade_net_v2
```

**Impact**: None (training runs offline).

**Resolution**: Acceptable; a pair of tightly coupled model/trainer classes.

---

## Flow Isolation (Design)

Seven named flows divide the codebase by workload:

| Flow | Modules | Internal Edges | Boundary Edges | Isolation | Role |
|------|---------|----------------|----|-----------|------|
| **agent** | 17 | 20 | 0 | 1.00 | LLM integration, tool planning |
| **control_plane** | 17 | 19 | 0 | 1.00 | HTTP API, dashboard, monitoring |
| **governance** | 30 | 31 | 0 | 1.00 | Config validation, promotion, audit |
| **research** | 32 | 59 | 0 | 1.00 | Experimental programs, analysis |
| **runtime** | 45 | 58 | 0 | 1.00 | Live/backtest execution, hot path |
| **telemetry** | 36 | 35 | 0 | 1.00 | Metrics, logging, observability |
| **training** | 23 | 43 | 0 | 1.00 | Model building, calibration |

**Interpretation**: All flows are perfectly isolated (zero boundary edges). This is by design — each flow is independently deployable.

---

## Bottleneck Modules (Most Depended-On)

These modules are load-bearing; changes have wide blast radius:

| Module | In-Edges | Role |
|--------|----------|------|
| **config_layer.production_config** | 54 | Central config source |
| **utils.logging_config** | 36 | Universal logging setup |
| **features.feature_schema** | 35 | 38-dim canonical definition |
| **utils.integrity_events** | 18 | Event types |
| **research.contracts** | 18 | Interpreter contracts |

**Strategy**: Avoid breaking changes. Use strict versioning and compatibility layers.

---

## Exporter Modules (Most Dependent)

These modules are orchestrators; they know about many others:

| Module | Out-Edges | Role |
|--------|-----------|------|
| **runtime.backtest_v2** | 24 | Backtesting orchestrator |
| **core.engine_runner** | 20 | Hot-path orchestrator |
| **runtime.live_engine_hook** | 19 | Live-mode entry point |
| **strategies.strategy_orchestrator** | 16 | Strategy runner |
| **strategies** | 13 | Package aggregator |

**Strategy**: Keep these as thin orchestrators; avoid pushing business logic into them.

---

## How to Navigate

### Using `graph_query.py`

The CLI tool in `scripts/analysis/graph_query.py` lets you explore the graph interactively:

```bash
# Show all dependencies of a module
python graph_query.py --module core.engine_runner

# Show all modules that depend on this
python graph_query.py --downstream config_layer.production_config

# Find shortest path between two modules
python graph_query.py --path runtime.backtest_v2 engines.crt_engine

# Show all modules in a package
python graph_query.py --package core

# Show a flow's topology
python graph_query.py --flow runtime

# Find circular dependencies
python graph_query.py --cycles

# Overall statistics
python graph_query.py --stats
```

### Using `codebase_explorer.html`

Open `codebase_explorer.html` in a browser for an interactive explorer:

- **Search**: Find modules by name
- **Packages**: Browse by package
- **Bottlenecks**: See the most-depended-on modules
- **Details**: Click any module to see its dependencies and dependents

### Using `graph.dot` Directly

The Graphviz `graph.dot` file is the source of truth. Visualize it with:

```bash
# Convert to SVG (requires Graphviz)
dot -Tsvg graph.dot -o graph.svg

# Convert to PNG
dot -Tpng graph.dot -o graph.png

# View in graphviz-based viewers
```

---

## Common Tasks

### Adding a New Module

1. **Pick the right package**. See `CONVENTIONS.md` for placement rules.
2. **Declare dependencies strictly**. Use explicit imports, avoid circular refs.
3. **Register in config if needed**. See `config_layer.production_config` for wiring.
4. **Regenerate artifacts**: Run `python scripts/analysis/gen_code_map.py`.

### Refactoring a Bottleneck (e.g., `config_layer.production_config`)

1. **Audit current consumers**: `python graph_query.py --downstream config_layer.production_config`
2. **Plan compatibility layer**. New module must support all 54 consumer interfaces.
3. **Add feature-flag in config**. Gradual migration over several versions.
4. **Test exhaustively**. Blast radius is high.

### Isolating a New Experimental Module

1. **Place in `research/`** for experiments; `src/` for production.
2. **Limit imports to core + features**. Avoid importing other research modules (unless you coordinate).
3. **Coordinate with the research flow** (see `flow_context/research.json`).
4. **Test in isolation** before integration tests.

### Detecting Unintended Coupling

1. Run `python graph_query.py --module <module>`.
2. Look for surprising dependencies (imports you didn't write).
3. Likely sources: transitive imports, star imports (`from x import *`).
4. Fix by making imports explicit.

---

## Three-Layer Atlas (Master Reference)

**→ [See Three-Layer Codebase Atlas](three-layer-codebase-atlas.md) for the unified navigation map.**

This guide covers **Layer 1 (Static Topology)** in depth. The full atlas integrates:
- **Layer 1**: Module imports, bottlenecks, flow isolation (this guide)
- **Layer 2**: Runtime execution, authority entry points, latent code
- **Layer 3**: Governance & authority ownership, promotion workflow

Use the atlas when you need to understand a module across all three dimensions, or when tracing a change's impact through code → execution → authority.

---

## References

- **Dependency graph**: `graph.dot` (regenerated by `gen_code_map.py`)
- **Flow manifests**: `flow_context/*.json` (hand-authored)
- **Analysis data**: `analysis_results.json` (regenerated by `codebase_wiring_analysis.py`)
- **Query tool**: `scripts/analysis/graph_query.py`
- **Explorer**: `codebase_explorer.html` (generated by `gen_html_explorer.py`)

---

## Regenerating Artifacts

All dependency artifacts are deterministic and can be regenerated:

```bash
# Regenerate all
python scripts/analysis/gen_code_map.py
python scripts/analysis/gen_flow_graphs.py
python scripts/analysis/codebase_wiring_analysis.py
python scripts/analysis/gen_html_explorer.py
```

**Note**: `gen_pyan.py` (function-level call graph) requires `pyan3` and may hit Windows path-length limits on large codebases. The module-level `graph.dot` is preferred for LLM context and architecture reviews.
