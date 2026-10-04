# Plan — Flow-scoped LLM context layer (M1 infra) + architecture-analyst report (M2)

## Context

The **Context** button ([InspectorPanel.jsx:216](ui_kits/control_plane/InspectorPanel.jsx:216)) sends a
run's executed source (`extract_code_context`) + logs to Claude, but the LLM has **no flow / architecture
awareness** — it can't situate the run in the pipeline or reason about impact radius. The only graph is the
global `graph.dot` (408 edges, AST-derived **import** graph, [gen_code_map.py](scripts/analysis/gen_code_map.py)) —
too coarse to feed whole, too undifferentiated for per-flow analysis.

**Goal:** an LLM-native **flow layer** where each run is analyzed against *its* flow's small graph (~20–60
edges) + executed code, producing an **architecture / impact-radius** analysis (not a bug hunt). Locked design:
- **Single human authority = `flow_context/<flow>.json`** (the only hand-maintained artifact). Everything
  else is **generated** — if another manually-maintained artifact appears, the architecture is degrading.
- **No new prose docs.** Manifests link the **existing** Layer-1 docs (§6.2 rule 1 *existing-doc-first*).
- **Edges are architectural, not runtime.** `graph.dot` is an *import* graph: `A -> B` = **"A `depends_on`
  / imports B"**, never "A calls B / executes before B." Vocabulary everywhere: `depends_on` · `imported_by`
  · `impact_radius` · `architectural_boundary`; never caller/callee/executes-before; **never infer execution
  order from imports.**
- **Two independent milestones**, not one feature: **M1 (infra) ships and is verified before M2 (report)**.

**Layer 1 already exists** — flows map onto the **S1–S9 service taxonomy**
([service-boundary-map.md](docs/architecture/service-boundary-map.md)) + [signal-flow.md](docs/architecture/signal-flow.md)
+ [services/](docs/architecture/services). Manifests *reference* these, never duplicate them.

## Architecture (3 layers; human judgment flows one way)

```
flow_context/<flow>.json   ← ONLY human authority (flow, doc-link, entrypoint, modules[], keywords[])  [L3]
        │  generator validates modules ⊆ graph.dot nodes, slices edges (AST-derived via build_graph())
        ▼
flow_graphs/<flow>.dot     ← DERIVED induced subgraph of graph.dot (~20–60 import edges)               [L2]
        │  Context button resolves run → flow → loads slice
        ▼
LLM analyst call (flow doc + .dot slice + manifest + executed code + logs + artifacts + meta)
        → 5-key architecture JSON                                                                  [consumer]
```
Human docs (signal-flow.md / service-boundary-map.md / services/*) are **Layer 1**, referenced by each
manifest's `doc` field — reused, never duplicated.

---

## M1 — Flow infrastructure (no prompt changes; ships independently)

### 1. Flow manifests (the only human-authored artifact) — new `flow_context/` (6 files)
One JSON per flow; `modules` use `graph.dot` node names. **Add a `keywords[]`** array (free, no new
artifact) so `pack_story.py` / future models can route by topic:
```json
{
  "flow": "runtime",
  "title": "Runtime / Signal Spine",
  "doc": "docs/architecture/signal-flow.md",
  "service_ids": ["S1","S2","S3","S4"],
  "entrypoint": "runtime.backtest_v2",
  "modules": ["features.feature_pipeline","core.engine_runner","core.fusion_engine",
              "core.decision_engine","config_layer.execution_planner","core.ultron_risk_gate"],
  "keywords": ["signal","fusion","decision_engine","ultron","execution"]
}
```
Initial set: `runtime` (signal-flow.md, S1–S4) · `governance` (S5 + replay-governance.md) · `training`
(S5/S6) · `agent` (S9) · `control_plane` (S9) · `research` (S6 + pipeline-linkage-spine-as-hypothesis.md).
`telemetry` (S7) **open** — add only if it earns a dedicated flow. **Membership = the only hand-judgment;**
cross-flow overlap (runtime/research/governance) is expected and acceptable.

### 2. Generator — new `scripts/analysis/gen_flow_graphs.py`
Stdlib-only, deterministic (mirrors [gen_code_map.py](scripts/analysis/gen_code_map.py); **reuse its
`build_graph()`** — one AST derivation, edges never hand-drawn). Per manifest:
- **validate** every `modules` entry ∈ `module_set` (else raise → drift caught at build time);
- emit `flow_graphs/<flow>.dot` = induced subgraph over the flow's modules + their 1-hop **dependency
  boundary** (boundary styled distinctly), same emit style as `emit_dot`; sort before emit (**byte-identical**);
- `--flow <name>` prints one slice to stdout (parity with gen_code_map's `--package`).

### 3. Drift test — new `tests/test_flow_manifests.py`
Mirror [tests/test_doc_citations.py](tests/test_doc_citations.py) / `test_current_findings.py`: every
`modules` entry resolves to a real `graph.dot` node; each `doc` path exists; `entrypoint` resolves;
`flow_graphs/<flow>.dot` regenerates **byte-identical**; valid JSON + required keys (incl. `keywords`). This
test is what makes "manifest = single authority" safe — it fails the instant a flow drifts from the code.

### 4. Flow resolver / graph context — new `src/control_plane/dot_graph_context.py`
Stdlib-only, no `src.*` imports, stateless — same contract as
[code_context_extractor.py](src/control_plane/code_context_extractor.py).
- `_file_to_module(file, repo_root)` — executed file → graph node (`src/core/engine_runner.py` →
  `core.engine_runner`; non-`src/` → None).
- `resolve_flow(code_context, repo_root)` — load `flow_context/*.json`, pick best overlap (entrypoint match
  first, then max module-set overlap; `keywords` available as a tiebreaker). Returns manifest or None.
- `extract_graph_context(code_context, repo_root)` — **public API**; neighbors labeled **`depends_on`**
  (outgoing imports) / **`imported_by`** (incoming / upstream consumers / `impact_radius`) — no caller/callee:
  - flow matched → load that `flow_graphs/<flow>.dot` slice → `source="flow_slice"` + `flow`/`title`/`doc`;
  - else → bounded 1-hop neighborhood from global `graph.dot` (caps `_MAX_GRAPH_NODES`/`_MAX_NEIGHBORS`,
    `source="global_neighborhood"`);
  - neither available → `{"available": False}` (**fail-open**).

### 5. Server wiring — `src/control_plane/server.py`
In the context route ([:1928](src/control_plane/server.py:1928)), after `extract_code_context(...)`:
`graph_ctx = extract_graph_context(code_ctx, _repo_root)` → pass into `context_api.context_analysis(...)`.
**M1 keeps the current report shape working** (graph_context accepted but prompt unchanged) — no behavior
change to the LLM output until M2.

**M1 Done = all of items 1–5 + the drift test green + byte-identical regeneration. No prompt/UI changes.**

---

## M2 — Architecture-analyst report (only after M1 is complete & verified)

### 6. New system prompt + 5-key output — `src/control_plane/context_report.py`
Swap `_SYSTEM_PROMPT` and the return schema for the flow-aware call to the **architecture-analyst** contract:
- **Role:** architecture analyst & code auditor — understand how components interact and how changes
  propagate. **Not** a debugger / style review / bug hunt. Inputs (authoritative): flow doc, `.dot` slice,
  manifest, executed source, logs, artifacts, metadata.
- **Embedded hard rule:** dependency edges are *architectural, not runtime*; never infer "A calls B" from
  `A -> B`; use depends_on / imported_by / upstream / downstream / impact_radius / architectural_boundary only.
- **Output = valid JSON only, exactly these 5 keys:**
  `executive_summary` · `architecture_notes` · `code_flow` · `impact_radius` · `structural_observations`
  - **`code_flow`** — architectural narration of how the executed modules fit the larger subsystem, from the
    flow slice + dependency edges (**architectural dependencies, not guaranteed runtime order**). Cover:
    modules depending on the current module → the current module → modules it depends on; subsystem
    boundaries, responsibilities, information movement, impact radius. Graph notation
    (`FeaturePipeline → EngineRunner → DecisionEngine → UltronRiskGate`). Only describe runtime sequencing
    when explicit evidence exists; **never infer execution order from imports**; no bug hunting, no fixes.
  - **`impact_radius`** — importing/imported modules + neighboring subsystems + likely propagation paths.
  - **`structural_observations`** (renamed from `observations` to fight bug-hunt drift) — *structural* findings
    only: orchestration hubs, fan-in, fan-out, coupling, boundary layers, isolated components. **Explicitly
    NOT** recommendations / improvements / suspected issues.
- `_build_prompt(...)` ([:65](src/control_plane/context_report.py:65)) renders `=== PIPELINE FLOW (<flow>) ===`
  with slice edges as `A depends on B` + the flow doc link. `context_analysis(...)`
  ([:162](src/control_plane/context_report.py:162)) takes `graph_context`; update the JSON-decode fallback
  ([:220](src/control_plane/context_report.py:220)) and success ([:239](src/control_plane/context_report.py:239))
  paths to the 5-key shape.
- **Supersession:** replaces the old root_cause/artifact_analysis/recommendations schema for the
  flow-analysis call. Keep the old path behind a flag only if a non-architecture report is still wanted
  (confirm at implementation).

### 7. Frontend — `ui_kits/control_plane/InspectorPanel.jsx`
In `ContextModal` ([:270](ui_kits/control_plane/InspectorPanel.jsx:270)) render the **5 analyst sections**
(`executive_summary`, `architecture_notes`, `code_flow`, `impact_radius`, `structural_observations`) reusing
`ctxSectionTitle`/`ctxBox`; show resolved flow name + doc link. `code_flow` in a monospace block (preserves
`→` arrows). Retire old section blocks (or same flag as item 6).

**M2 Done = items 6–7, the report returns the 5-key schema, UI renders it, no import edge described as a call.**

---

## M3 — Manual multi-LLM hook (optional)
Add `--flow <name>` to [pack_story.py](scripts/context/pack_story.py): bound a transfer pack to one flow's
manifest (incl. `keywords`) + doc + `.dot` slice → feeds the existing §13 hand-operated handoff (Claude
narration / Gemini completeness / DeepSeek planning / GPT synthesis). **No automated fan-out.** No new artifacts.

## M4 — Automated parallel-LLM merge engine — **deferred** (conflicts §13's hand-operated protocol).

---

## Critical files
- **New:** `flow_context/*.json` (M1) · `scripts/analysis/gen_flow_graphs.py` (M1) · `flow_graphs/*.dot`
  (generated, M1) · `src/control_plane/dot_graph_context.py` (M1) · `tests/test_flow_manifests.py` (M1).
- **Edit:** [context_report.py](src/control_plane/context_report.py) (M2) · [server.py](src/control_plane/server.py)
  (M1 wiring) · [InspectorPanel.jsx](ui_kits/control_plane/InspectorPanel.jsx) (M2) ·
  (M3) [pack_story.py](scripts/context/pack_story.py).
- **Reused:** [graph.dot](graph.dot) / [gen_code_map.py](scripts/analysis/gen_code_map.py) (`build_graph()`),
  S1–S9 docs, `extract_code_context`.

## Guardrails (§6.2 / §6.5)
- **Single authority:** only `flow_context/*.json` is hand-maintained; flow `.dot`, slices, contexts are
  generated. Any new manual artifact is a smell.
- **Import ≠ call:** all edge language architectural; enforced by the prompt rule + verification step.
- **Determinism / drift:** flow `.dot` from `build_graph()` (AST), byte-identical regen, drift test guards it.
- **Fail-open + bounded:** missing graph/flow → graceful degrade; slice + caps keep tokens small.
- **Additive / no new authority** (§6.5 / §13.8): context plumbing only — no gating, no automated cross-model calls.
- §6 SESSION LOG appended to `assistant_project.md` on implementation (deferred — plan mode is read-only).

## Verification
- **M1:** `python scripts/analysis/gen_code_map.py && python scripts/analysis/gen_flow_graphs.py` →
  `flow_graphs/*.dot` (~20–60 edges each); `python -m pytest tests/test_flow_manifests.py -v` green; rerun
  generator → byte-identical; Context button still returns the *current* report (no behavior change).
- **M2:** control plane (`python -m src.control_plane.server`, :8787) → open a **runtime** run → **🧠 Context**
  → 5-section report (`executive_summary · architecture_notes · code_flow · impact_radius ·
  structural_observations`) naming the `runtime` flow, `code_flow` narrating depends-on relationships in graph
  notation, linking `signal-flow.md`. Needs `ANTHROPIC_API_KEY`.
- **Fail-open:** no-flow-match → global neighborhood still renders; remove `flow_graphs/` → Context still works.
- **Language check:** report contains no "calls / executes before" claims about import edges, and
  `structural_observations` carries no recommendations / suspected issues.
