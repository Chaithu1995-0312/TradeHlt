# Research SSOT Framework — Architecture contract v0.1

## Scope and authority

This is a **standalone experiment**. The manifest is the SSOT for approved intents, external input declarations, node contracts, dependency edges, producer identity, and required claims. It is not yet a thin wrapper over existing repository registries. The planner is plan-only and does not execute arbitrary scripts.

## Invariants

1. **Planning is not execution.** The planner only emits a dependency plan. Runtime statuses may be attached only from explicit execution results supplied to `apply_execution_results`.
2. **Static intent is not runtime truth.** Inventory docstrings/imports/path hints are heuristic observations, not verified behavior or script contracts.
3. **Input closure fails closed.** Every input is either a declared `external_inputs` ID or a `node_id.output` emitted by a transitive ancestor. Unknown inputs produce `INPUT_UNRESOLVED`; outputs from non-ancestors produce `HIDDEN_DEPENDENCY`. External inputs with `ref: UNRESOLVED` block their consumer.
4. **State producers cannot be silently pooled.** Producer identity is exactly `kind@config_ref`. `config_ref` must point to an external input of kind `config`; if that config is `UNRESOLVED` the node is `BLOCKED`. Producer identities propagate through outputs. Two or more producer identities entering a node require `operation: compare` or `operation: bridge`; bridges require an external contract. Every way to lose a producer is closed:
   - `PRODUCER_DROPPED` — a node with any state input may never emit `state_producer: "none"` (strict; pooling happens only through a bridge).
   - `PRODUCER_RELABELED` — a node with state inputs may not declare an explicit producer its inputs do not carry (bridges excepted).
   - `STATE_PRODUCER_UNDECLARED` — `artifact_resolve` nodes, and any output with no state inputs to inherit from, must declare `none` or `{kind, config_ref}`.
   - Dataset externals may declare `state_producer`; an undeclared dataset is `unknown@<id>`, a distinct producer that cannot pool with any other.
   - Comparison taint propagates: any output descended from a compare output stays diagnostic until a bridge, and `COMPARISON_REUSED_AS_POPULATION` fires when a `measurement` consumes it, however many hops later.
5. **No script deletion or production mutation.** This experiment does not modify existing scripts or production config and does not auto-merge analysis implementations.
6. **Conclusions cannot exceed evidence.** `required_claims` maps claim IDs to output refs in the intent closure. A claim is `SUPPORTED` only if every mapped output belongs to a `COMPLETED` or `REUSED` node. All other states leave the claim `UNSUPPORTED`. A status string is not evidence: see *Execution results*.

## Schema 1.1

- `external_inputs`: array of `{id, kind, ref}`; `kind ∈ {contract, identity, dataset, config}`. Dataset externals may add `state_producer` (`none` or `{kind, config_ref}`).
- `nodes`: each node has `node_id`, `purpose`, closed-enum `operation`, `inputs`, `outputs`, `depends_on`, closed-enum `reuse_policy`, and boolean `required`.
- `outputs` may be strings or `{name, state_producer}` objects. Producer specs may be `none`, `inherit`, or `{kind, config_ref}`.
- `intents.required_claims`: `{claim_id: ["node_id.output", ...]}`.
- Supported operations: `contract_check`, `artifact_resolve`, `measurement`, `compare`, `bridge`, `evidence_assembly`.
- Supported reuse policies: `NEVER_REUSE_FINAL_REPORT_WITHOUT_REVALIDATION`, `REUSE_ONLY_EXACT_IDENTITY`, `REUSE_IF_CONTRACT_AND_HASH_MATCH`, `NEVER_REUSE`.

## Status model

Node statuses: `PLANNED`, `BLOCKED`, `BLOCKED_UPSTREAM`, `COMPLETED`, `REUSED`, `FAILED`, `SKIPPED`. A failed node stays `FAILED` whether or not it is required; only its dependents become `SKIPPED` (a failure is never relabelled as an intentional skip). A claim remains unsupported if any required evidence output is missing, blocked, failed, skipped, or merely planned.

Report status is derived (one function, used by both plan and apply), in precedence order:

1. `BLOCKED` — any node `BLOCKED` / `BLOCKED_UPSTREAM` (the cause is upstream, not execution).
2. `INCOMPLETE` — any required node `FAILED` / `SKIPPED`, or every node has a result but some claim is `UNSUPPORTED`.
3. `PARTIAL` — some nodes have results, others are still `PLANNED`.
4. `COMPLETE` — every node has a result and every claim is `SUPPORTED`; otherwise `PLANNED_NOT_EXECUTED`.

## Execution results

`apply_execution_results(plan, results, base_dir)` (CLI: `apply --plan --results --base-dir --out`) attaches results produced elsewhere; it never executes anything.

- `COMPLETED` / `REUSED` must carry `artifacts: [{path, sha256}]` and `run_identity_ref`. Each artifact is re-hashed at apply time (relative paths resolve against `base_dir`); a missing file or a hash mismatch is rejected. A stated hash is never trusted.
- `REUSED` must also name `reused_identity`. It is recorded, not yet checked (no artifact cache exists).
- A result for a node id not in the plan is rejected, as is a `COMPLETED`/`REUSED` result for a node that cannot have run (blocked, or an upstream dependency unavailable).

## Inventory identity

`generated_at_utc` and the machine-local `repository_root` are excluded from `content_sha256`, so the same tree has the same identity across runs and clones. Default scan roots (`scripts/analysis`, `scripts/research`, `src/research`) live in one constant shared by the library and the CLI. `open()` mode detection and path detection remain static heuristics, not proof of runtime writes.

## Evidence reuse and later connectivity

A future adapter registry must require explicit allowlisting and exact compatible artifact identities, including dataset SHA, code SHA, config SHA, schema/version, operation version, parameters, and input artifact hashes. Filename similarity alone is insufficient. The next agreed phase is a **read-only overlap map** against existing script registry/SITS, `MEASUREMENT_CONTRACT`/`MC-*`, `research_family_registry`, Corpus SSOT F-119, and MPA v1. No `ref` binding should be guessed before that review.
