# Plan: Generate Pyan Dot File & Understand Codebase Wiring

## Context

The Tradelatest codebase uses a three-tier dependency visualization system:
1. **graph.dot** (module-level imports via AST): ~515 edges, structural
2. **pyan_call_flow.dot** (function/class calls via pyan3): tens of thousands of edges, runtime
3. **flow_graphs/*.dot** (domain-scoped slices): 7 flows (agent, runtime, governance, research, training, control_plane, telemetry)

Current status:
- All generation scripts exist (`gen_code_map.py`, `gen_pyan.py`, `gen_flow_graphs.py`)
- graph.dot exists and is up-to-date
- pyan_call_flow.dot exists but may be stale (last run unclear)
- flow_graphs/*.dot all exist
- flow_context/*.json manifests all exist (7 flows defined)

## Goals

1. **Regenerate all artifacts** to ensure they reflect the current codebase
2. **Analyze the wiring** to understand:
   - Module-level dependency structure
   - Critical paths and bottlenecks
   - Per-domain flow isolation
3. **Provide interactive exploration tools** to query the graph

## Implementation Plan

### Phase 1: Regenerate Core Artifacts (read-only, inspection only)
- [ ] **gen_code_map.py** → regenerate graph.dot (modules + imports via AST)
- [ ] **gen_pyan.py** → regenerate pyan_call_flow.dot (function/class calls via pyan3)
- [ ] **gen_flow_graphs.py** → regenerate all flow_graphs/*.dot slices

Success criteria:
- All three artifact types regenerated without errors
- Byte-identical check (deterministic generation confirmed)
- graph.dot validates against pyan for consistency

### Phase 2: Analyze Module-Level Structure
- [ ] Load graph.dot and extract statistics:
  - Node count per package
  - Edge count (dependencies between packages)
  - Cyclic dependency detection
  - Depth from entry points (runtime, governance, training, agent)
  - Betweenness centrality (critical intermediate modules)

- [ ] Per-flow analysis (flow_graphs/*.dot):
  - Module count per flow
  - Internal edges (within-flow dependencies)
  - Boundary edges (imports from outside flow)
  - Flow isolation score (low boundary edges = good)

Success criteria:
- Generate a structured report (`codebase_wiring_analysis.json`)
- Identify 3-5 critical paths and junction points
- Flag any circular dependencies

### Phase 3: Analyze Call-Graph Structure (pyan_call_flow.dot)
- [ ] Sample the pyan call graph (too large to fully analyze):
  - Total node/edge count
  - Top 10 most-called functions
  - Longest call chains (depth)
  - Hot spots (high in-degree)

Success criteria:
- Generate a summary (`call_graph_hotspots.txt`)
- Identify which modules are "hub" functions

### Phase 4: Interactive Exploration Tools
- [ ] **Graph query script** (read-only):
  - `--module <name>` → show all dependencies of a module
  - `--flow <name>` → show the flow's induced subgraph
  - `--path <from> <to>` → find shortest import path
  - `--downstream <module>` → modules that depend on this

- [ ] **Visualization preparation**:
  - Convert graph.dot to a Graphviz PNG/SVG for visual inspection
  - Generate a per-flow visual (7 small PNGs for each flow)

### Phase 5: Document & Summarize
- [ ] Create `docs/architecture/codebase-wiring-guide.md`:
  - Module hierarchy diagram (text-based ASCII tree)
  - Per-package role summary (from graph.dot clusters)
  - Critical dependencies (high fan-in/fan-out modules)
  - Per-flow topology (module count, boundary structure)
  - How to navigate: using graph.dot, query tools, flow_graphs

- [ ] Update `docs/reference/architecture.md` §3 with wiring section reference

## Critical Files to Touch

### Generation Scripts (read-only, just run them)
- `scripts/analysis/gen_code_map.py` — AST module parser
- `scripts/analysis/gen_pyan.py` — pyan3 call-graph runner
- `scripts/analysis/gen_flow_graphs.py` — flow-scoped slicer

### Artifacts (regenerated, never hand-edited)
- `graph.dot` — module import graph (Graphviz format)
- `pyan_call_flow.dot` — function call graph (Graphviz format)
- `flow_graphs/*.dot` — 7 domain slices

### Flow Manifests (hand-authored, stable)
- `flow_context/*.json` — 7 flow definitions (agent, runtime, governance, research, training, control_plane, telemetry)

### New Analysis Tools (to create)
- `scripts/analysis/codebase_wiring_analysis.py` — Phase 2 analysis
- `scripts/analysis/graph_query.py` — Phase 4 interactive tool

### Documentation (to update)
- `docs/architecture/codebase-wiring-guide.md` — new, comprehensive guide
- `docs/reference/architecture.md` — link to wiring guide

## Verification

✅ All generation scripts can run without errors
✅ Artifacts are deterministic (byte-identical on re-run)
✅ graph.dot nodes match pyan modules (no drift)
✅ flow_graphs/*.dot all validate against graph.dot
✅ No circular dependencies detected
✅ Query tools work against graph.dot and pyan_call_flow.dot

## Open Questions for User

1. **Visualization preference**: Would you like PNG/SVG renders of the graphs, or Graphviz interactive HTML, or both?
2. **Query tool interface**: Preference for CLI script (`python graph_query.py --module x`) or a simple REPL?
3. **Documentation depth**: Comprehensive (~50 pages) or executive summary (~5 pages)?
4. **Focus areas**: Any specific packages/flows you'd like deep-dive analysis on?

## Next Step

→ User approval, then execute Phase 1 (regenerate artifacts).
