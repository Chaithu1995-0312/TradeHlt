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
- **M3 — manual multi-LLM hook (optional).** `pack_story --flow` bounds a transfer pack to one flow.
- **M4 — automated merge engine (deferred).**

This subsystem is context plumbing only — it **grants no new authority** (CLAUDE.md §6.5 / §13.8).
