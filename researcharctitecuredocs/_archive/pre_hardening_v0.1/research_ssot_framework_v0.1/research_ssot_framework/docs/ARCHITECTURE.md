# Architecture and invariants

## Canonical authority

`manifest.json` is the SSOT for approved intent definitions and analysis-node contracts. The script inventory is a generated observation of source files, not the SSOT for what a script means.

## Intent resolution

An intent maps to one or more root nodes. The planner recursively resolves dependencies and creates a deterministic topological order. It does not invent new nodes at runtime. A future LLM intent resolver may propose a manifest patch, but approval and validation must happen before execution.

## Node contract

- `node_id`: stable identity
- `purpose`: declared question or computation
- `operation`: allowlisted operation category
- `inputs` / `outputs`: named contract fields
- `depends_on`: directed dependency edges
- `reuse_policy`: conditions for evidence reuse
- `required`: whether absence blocks final assembly

## Evidence reuse

Reuse requires exact compatible identities and measurement contracts. At minimum, future artifact identity must include dataset SHA, code SHA, config SHA, schema/version, operation version, parameters, and input artifact hashes. A matching filename is not sufficient.

## Final output

One final report is assembled from node statuses and validated evidence. It must show completed, reused, failed, blocked, and skipped nodes; evidence provenance; contract versions; and unresolved limitations. The MVP only emits the plan/report scaffold and never claims that measurements ran.

## Invariants

1. Planning is not execution.
2. Static intent inference is not runtime verification.
3. Unknown required inputs fail closed.
4. Distinct state producers cannot be pooled without an explicit bridge contract.
5. No script deletion or production mutation.
6. Final conclusions cannot exceed the evidence supplied by their dependency nodes.
