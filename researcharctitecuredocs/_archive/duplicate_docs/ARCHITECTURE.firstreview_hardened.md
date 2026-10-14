# Research SSOT Framework — Architecture contract v0.1

## Scope and authority

This is a **standalone experiment**. The manifest is the SSOT for approved intents, external input declarations, node contracts, dependency edges, producer identity, and required claims. It is not yet a thin wrapper over existing repository registries. The planner is plan-only and does not execute arbitrary scripts.

## Invariants

1. **Planning is not execution.** The planner only emits a dependency plan. Runtime statuses may be attached only from explicit execution results supplied to `apply_execution_results`.
2. **Static intent is not runtime truth.** Inventory docstrings/imports/path hints are heuristic observations, not verified behavior or script contracts.
3. **Input closure fails closed.** Every input is either a declared `external_inputs` ID or a `node_id.output` emitted by a transitive ancestor. Unknown inputs produce `INPUT_UNRESOLVED`; outputs from non-ancestors produce `HIDDEN_DEPENDENCY`. External inputs with `ref: UNRESOLVED` block their consumer.
4. **State producers cannot be silently pooled.** Producer identity is exactly `kind@config_ref`. `config_ref` must point to an external input of kind `config`. Producer identities propagate through outputs. Two or more producer identities entering a node require `operation: compare` or `operation: bridge`; bridges require an external contract. Compare outputs are diagnostic and cannot be fed into a `measurement` as a state population.
5. **No script deletion or production mutation.** This experiment does not modify existing scripts or production config and does not auto-merge analysis implementations.
6. **Conclusions cannot exceed evidence.** `required_claims` maps claim IDs to output refs in the intent closure. A claim is `SUPPORTED` only if every mapped output belongs to a `COMPLETED` or `REUSED` node. All other states leave the claim `UNSUPPORTED`.

## Schema 1.1

- `external_inputs`: array of `{id, kind, ref}`; `kind ∈ {contract, identity, dataset, config}`.
- `nodes`: each node has `node_id`, `purpose`, closed-enum `operation`, `inputs`, `outputs`, `depends_on`, closed-enum `reuse_policy`, and boolean `required`.
- `outputs` may be strings or `{name, state_producer}` objects. Producer specs may be `none`, `inherit`, or `{kind, config_ref}`.
- `intents.required_claims`: `{claim_id: ["node_id.output", ...]}`.
- Supported operations: `contract_check`, `artifact_resolve`, `measurement`, `compare`, `bridge`, `evidence_assembly`.
- Supported reuse policies: `NEVER_REUSE_FINAL_REPORT_WITHOUT_REVALIDATION`, `REUSE_ONLY_EXACT_IDENTITY`, `REUSE_IF_CONTRACT_AND_HASH_MATCH`, `NEVER_REUSE`.

## Status model

Node statuses: `PLANNED`, `BLOCKED`, `BLOCKED_UPSTREAM`, `COMPLETED`, `REUSED`, `FAILED`, `SKIPPED`. Report status is derived: `PLANNED_NOT_EXECUTED`, `BLOCKED`, `INCOMPLETE`, or `COMPLETE`. A required failure makes the report `INCOMPLETE`; a non-required failure is `SKIPPED` and skips its dependents. A claim remains unsupported if any required evidence output is missing, blocked, failed, skipped, or merely planned.

## Inventory identity

`generated_at_utc` is volatile and excluded from `content_sha256`. Inventory content identity covers the other inventory fields, including script SHA-256s, scan roots, counts, and limitations. `open()` mode detection and path detection remain static heuristics, not proof of runtime writes.

## Evidence reuse and later connectivity

A future adapter registry must require explicit allowlisting and exact compatible artifact identities, including dataset SHA, code SHA, config SHA, schema/version, operation version, parameters, and input artifact hashes. Filename similarity alone is insufficient. The next agreed phase is a **read-only overlap map** against existing script registry/SITS, `MEASUREMENT_CONTRACT`/`MC-*`, `research_family_registry`, Corpus SSOT F-119, and MPA v1. No `ref` binding should be guessed before that review.
