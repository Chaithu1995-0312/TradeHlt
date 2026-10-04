# Codebase Wiring — Quick Reference

**Generated**: 2026-07-17 | **Modules**: 351 | **Dependencies**: 696 | **Packages**: 36

## Artifacts Regenerated

✓ `graph.dot` — Module-level import graph (AST-derived, 351 nodes, 696 edges)
✓ `analysis_results.json` — Structured dependency data
✓ `analysis_summary.txt` — Human-readable summary report
✓ `codebase_explorer.html` — Interactive browser-based explorer
✓ `scripts/analysis/graph_query.py` — CLI query tool
✓ `scripts/analysis/codebase_wiring_analysis.py` — Analysis engine
✓ `scripts/analysis/gen_html_explorer.py` — HTML generator
✓ `docs/architecture/codebase-wiring-guide.md` — Comprehensive guide
✓ `flow_graphs/*.dot` — 7 domain-scoped flow graphs (all perfect isolation)

---

## Quick Commands

### Explore via CLI
```bash
# Show a module's dependencies
python scripts/analysis/graph_query.py --module core.engine_runner

# Show what depends on this
python scripts/analysis/graph_query.py --downstream config_layer.production_config

# Find a path between two modules
python scripts/analysis/graph_query.py --path runtime.backtest_v2 engines.crt_engine

# Show all modules in a package
python graph_query.py --package core

# Show a flow's modules
python graph_query.py --flow runtime

# Detect cycles
python graph_query.py --cycles

# Stats
python graph_query.py --stats
```

### Explore via Browser
Open `codebase_explorer.html` in any web browser (fully self-contained, no server needed).

### Visualize the Graph
```bash
# Requires Graphviz (dot command)
dot -Tsvg graph.dot -o graph.svg
dot -Tpng graph.dot -o graph.png
```

---

## Key Findings

### Critical Bottlenecks (High In-Degree)
| Module | Consumers |
|--------|-----------|
| `config_layer.production_config` | 54 |
| `utils.logging_config` | 36 |
| `features.feature_schema` | 35 |

**Implication**: Changes to these modules affect 54+ downstream consumers.

### Hot-Path Orchestrators (High Out-Degree)
| Module | Dependencies |
|--------|--------------|
| `runtime.backtest_v2` | 24 |
| `core.engine_runner` | 20 |
| `runtime.live_engine_hook` | 19 |

**Implication**: Keep these thin; they're orchestrators, not logic containers.

### Circular Dependencies
Found 5 cycles (all in governance/config tiers, not hot path):
- `config_layer.llm_*` cycle (3 modules)
- `config_layer.crt_engine_v2 ↔ state_contract` cycle (2 modules)
- `training.trainer ↔ trade_net_v2` cycle (2 modules)

**Assessment**: Minor; acceptable by design.

### Flow Isolation
All 7 flows achieve **perfect isolation** (zero boundary dependencies):
- agent, control_plane, governance, research, runtime, telemetry, training

**Implication**: Flows can be independently deployed/tested.

---

## Critical Paths (Data Flow)

### Path 1: Configuration Authority
```
configs/production/*.json
  → config_layer.production_config
  → core.engine_runner
  → 4 engines + gates
```

### Path 2: Feature Pipeline
```
OHLCV candles
  → features.feature_pipeline
  → features.feature_schema (38-dim)
  → core.engine_runner
  → 4 engines
```

### Path 3: Scoring → Decision
```
4 engines
  → core.fusion_engine
  → core.decision_engine
  → core.acceptance_controller
  → core.ultron_risk_gate
```

### Path 4: Decision → Execution
```
core.ultron_risk_gate
  → runtime.live_engine_hook
  → execution.execution_intent_v1_0
  → journal.trade_logger
```

---

## Package Breakdown (Top 10)

| Package | Modules | Role |
|---------|---------|------|
| research | 77 | Experimental programs, analysis |
| config_layer | 22 | Config, validation, CRT state machine |
| core | 20 | Engine runner, fusion, decision, gates |
| features | 20 | Feature pipeline, schema, registry |
| agent | 19 | LLM integration, tool planning |
| utils | 18 | Logging, events, helpers |
| strategies | 16 | Strategy orchestration, runners |
| governance | 14 | Promotion, validation, audit |
| engines | 12 | Individual scorers (CRT, Gaussian, RR, ZoneGate) |
| control_plane | 11 | HTTP API, dashboard, registry |

---

## How to Modify the Codebase Safely

### Adding a New Module
1. Choose the right package (see `docs/reference/conventions.md`).
2. Import only from the same package or core/features.
3. Avoid importing from higher tiers (experimental/tooling).
4. Run `python scripts/analysis/gen_code_map.py` to verify.

### Changing a Bottleneck Module (e.g., `config_layer.production_config`)
1. Audit consumers: `python graph_query.py --downstream config_layer.production_config`
2. Plan backward compatibility (all 54 consumers must keep working).
3. Test against all consuming modules.
4. Use feature flags if migrating incrementally.

### Isolating Experimental Code
1. Keep it in `src/research/` or `src/agent/` (not in core).
2. Use the flow-scoped imports (see `flow_context/research.json`).
3. Test in isolation before integration.

### Detecting Unintended Coupling
1. Run: `python graph_query.py --module <module>`
2. Look for surprising imports (transitive paths you didn't expect).
3. Use explicit imports, avoid star imports (`from x import *`).

---

## Regenerating the Artifacts

All dependency analysis is deterministic (exact same input → exact same output):

```bash
# Regenerate module-level graph
python scripts/analysis/gen_code_map.py

# Regenerate flow-scoped subgraphs
python scripts/analysis/gen_flow_graphs.py

# Regenerate analysis & summary reports
python scripts/analysis/codebase_wiring_analysis.py

# Regenerate interactive explorer
python scripts/analysis/gen_html_explorer.py

# All at once
python scripts/analysis/gen_code_map.py && \
  python scripts/analysis/gen_flow_graphs.py && \
  python scripts/analysis/codebase_wiring_analysis.py && \
  python scripts/analysis/gen_html_explorer.py
```

**Note**: Function-level call graph (`gen_pyan.py`) hits Windows path limits with 1000+ files. Use module-level graph instead.

---

## File Locations

| Artifact | Path | Type |
|----------|------|------|
| Graph | `graph.dot` | Graphviz (ASCII) |
| Flow graphs | `flow_graphs/*.dot` | Graphviz (7 files) |
| Analysis JSON | `analysis_results.json` | JSON |
| Analysis Report | `analysis_summary.txt` | Text |
| Interactive Explorer | `codebase_explorer.html` | HTML (self-contained) |
| CLI Tool | `scripts/analysis/graph_query.py` | Python script |
| Analysis Engine | `scripts/analysis/codebase_wiring_analysis.py` | Python script |
| HTML Generator | `scripts/analysis/gen_html_explorer.py` | Python script |
| Code Map Generator | `scripts/analysis/gen_code_map.py` | Python script |
| Flow Slicer | `scripts/analysis/gen_flow_graphs.py` | Python script |
| Guide | `docs/architecture/codebase-wiring-guide.md` | Markdown |

---

## Next Steps

1. **Explore the graph**: Open `codebase_explorer.html` in a browser.
2. **Query the CLI**: Run `python graph_query.py --help`.
3. **Read the guide**: Open `docs/architecture/codebase-wiring-guide.md`.
4. **Check critical paths**: Understand how config / features / scoring flow through the system.
5. **Audit bottlenecks**: Use `graph_query.py --downstream <module>` to understand blast radius of changes.
