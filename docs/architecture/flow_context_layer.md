# flow-context layer

> **Orientation page — NOT an authority.** The front door for the flow-scoped LLM context
> subsystem. It points at the parts; it does not describe the flows or duplicate any knowledge.
> Flow *content* lives in the existing Layer-1 docs ([`signal-flow.md`](signal-flow.md),
> [`service-boundary-map.md`](service-boundary-map.md), [`services/`](services)). The only
> hand-authored truth is `flow_context/*.json`.

## Why

The Control-Plane **Context** button feeds the run's executed code to an LLM, but the global import
graph (`graph.dot`, ~560 edges) is too coarse to feed whole. This layer slices it per *flow* so the
LLM sees its run's small dependency neighbourhood (~16–54 edges), not the whole codebase.

## The three layers (human judgment flows one way)

| Layer | Artifact | Authored or derived |
| --- | --- | --- |
| **L1 — human docs** | `signal-flow.md`, `service-boundary-map.md` (S1–S9), `services/*` | existing; **reused, never duplicated** |
| **L2 — flow graphs** | `flow_graphs/<flow>.dot` (induced subgraph + 1-hop dependency boundary) | **derived** by `scripts/analysis/gen_flow_graphs.py` |
| **L3 — manifests (SSOT)** | `flow_context/<flow>.json` (`flow`, `doc`, `entrypoint`, `modules`, `keywords`) | **hand-authored — the only human authority** |

Derivation: `flow_context` manifest ∩ AST import graph (`gen_code_map.build_graph()`) →
`flow_graphs/<flow>.dot`. The generator validates every listed module against the real graph, so a
manifest can never silently drift from the code. `tests/test_flow_manifests.py` enforces this and
byte-identical regeneration.

## Resolver + fallback chain

`src/control_plane/dot_graph_context.py` (stdlib, no `src.*` imports, fail-open) maps a run's
executed files to graph nodes and resolves a flow:

```
run → executed modules → resolve_flow (module overlap + entrypoint + keyword tiebreak)
   ├─ flow matched ........... source = "flow_slice"          (load flow_graphs/<flow>.dot)
   ├─ no flow match .......... source = "global_neighborhood" (1-hop slice of graph.dot)
   └─ nothing usable ......... { "available": false }          (Context report still works)
```

Neighbour keys are `depends_on` / `imported_by` — see the vocabulary rule below.

## Rules

- **Single authority.** Only `flow_context/*.json` is hand-maintained. `flow_graphs/*.dot`,
  `graph.dot`, and the generated docs are products — regenerate them, never hand-edit. A new
  manually-maintained artifact in this subsystem is a smell.
- **Import ≠ call.** `graph.dot` is an *import* graph: an edge `A -> B` means **"A depends on /
  imports B"**, never "A calls B" or "A runs before B." Vocabulary is `depends_on` / `imported_by` /
  `impact_radius` / `architectural_boundary`. Never infer runtime execution order from imports.
- **Fail-open + bounded.** Any missing artifact degrades gracefully; slices stay small by construction.

## Regenerate

```
python scripts/analysis/gen_code_map.py      # graph.dot + code-map / module-roles (AST)
python scripts/analysis/gen_flow_graphs.py   # flow_graphs/<flow>.dot from the manifests
python scripts/analysis/gen_flow_graphs.py --flow runtime   # print one slice, write nothing
```

## Milestones

- **M1 — infrastructure (done).** Manifests, generator, `flow_graphs/*`, resolver, drift tests, and
  additive server wiring. The LLM output is intentionally unchanged at M1.
- **M2 — architecture-analyst report (planned).** Swap the Context prompt to an architecture-analyst
  contract returning `executive_summary · architecture_notes · code_flow · impact_radius ·
  structural_observations`, fed by the flow slice; render the sections in the Context modal.
- **M2P — pluggable report provider (done).** The Context report answers the analyst prompt via a
  provider, resolved as env `CONTEXT_REPORT_PROVIDER` → prod config `context_report.provider` →
  default `export`. Values:
  - `export` (default, **$0**) — no LLM call; returns + saves the prompt
    (`logs/context_prompts/<run>.md`) to paste into Claude Code.
  - `local` / `groq` — the server injects an `llm_caller` over `llm_inference_client.llm_chat`
    (BitNet-local → Groq free-tier); the 5-key parse is shared with `api`.
  - `api` — metered Anthropic (`claude-haiku-4-5`); opt-in, needs `ANTHROPIC_API_KEY`.
- **M5 — Workflow-node Context (done).** Each `flow_context` manifest also carries `command_ids[]`
  (the Workflow-DAG nodes it owns). `resolve_flow_for_command` (command_ids → `script` fallback) +
  `build_flow_code_context` (synthesizes code context from a flow's modules, no run needed) feed
  `GET /workflow/nodes/<command_id>/context` → `{flow, doc, architecture (export-first), latest_run}`.
  Clicking a Workflow node opens a drawer (code/architecture + run details + flow doc). Unmapped nodes
  (`data.*`) fail open to run-only.
- **M6 — Flow/Module Explorer (done).** An "Explore" tab lists all flows + their modules start→end;
  selecting a flow or a module shows its **docs + code + input/output** (flow `inputs`/`outputs`, or a
  module's `depends_on`/`imported_by`) inline + a $0 Copy/Export bundle. Routes: `GET /flows` +
  `GET /flows/<flow>/context?module=<opt>`. Reuses `build_flow_code_context` / `extract_graph_context` /
  `module_neighbors` / `context_analysis`.
- **M7 — Workflow DAG completeness (done).** The Workflow-tab Mermaid is now faithful to
  `registry.WORKFLOW_STAGE_ORDER` (restored the eliminated **Replay & Backtest** stage + a
  `config_validator` node), shows orthogonal subsystems (Research / Agent / Telemetry → click into the
  Explore tab), and a coverage test (`test_workflow_dag_coverage.py`) fails if any pipeline stage is
  silently dropped. Added the **`telemetry`** flow manifest (S7), closing the long-open gap.
- **M3 — manual multi-LLM hook (optional).** `pack_story --flow` bounds a transfer pack to one flow.
- **M4 — automated merge engine (deferred).**

This subsystem is context plumbing only — it **grants no new authority** (CLAUDE.md §6.5 / §13.8).
