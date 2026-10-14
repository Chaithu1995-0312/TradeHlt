# Research SSOT Framework — hardened standalone experiment v0.1

A stdlib-only, plan-only intent → dependency DAG → evidence report prototype. This remains a **standalone experiment**; it does not connect to or mutate repository registries and does not execute arbitrary scripts.

## Hardened contract (manifest schema 1.1)

- `external_inputs` declares every input that does not come from a node output. Inputs with `ref: UNRESOLVED` block the consuming node; downstream nodes become `BLOCKED_UPSTREAM`.
- Node inputs must resolve to an external input or a `node_id.output` from a transitive dependency ancestor. Hidden dependencies and unknown inputs are errors.
- `intent.required_claims` maps each claim ID to one or more `node_id.output` references in the intent closure. A claim is `SUPPORTED` only when every mapped output comes from a `COMPLETED` or `REUSED` node.
- State producer identity is `kind@config_ref`; `config_ref` must name an external input of kind `config` (an `UNRESOLVED` config blocks the node). Producer identity always propagates: a node with state inputs can neither emit `none` nor relabel to a producer its inputs don't carry, and sources must declare their producer. Undeclared dataset externals are an `unknown` producer.
- Combining multiple producer identities is rejected unless the operation is `compare` or `bridge`. A bridge requires a declared external contract. Compare outputs stay diagnostic through any number of hops and cannot be measured as a state population.
- Operations and reuse policies are closed enums. A failed node stays `FAILED`; its dependents become `SKIPPED`. Report status is `BLOCKED` > `INCOMPLETE` > `PARTIAL` > `COMPLETE` / `PLANNED_NOT_EXECUTED`.
- The planner does not execute nodes. `apply_execution_results` (CLI `apply`) accepts results from elsewhere: `COMPLETED`/`REUSED` must carry `artifacts [{path, sha256}]` + `run_identity_ref`, and every artifact is re-hashed on apply.
- Inventory scans `scripts/analysis`, `scripts/research`, `src/research` by default (library and CLI share one constant), detects literal `open(..., mode="w/a/x/+")` as a likely write, and emits `content_sha256` excluding `generated_at_utc` and the machine-local root.

## Commands

From this directory:

```bash
PYTHONPATH=src python -m unittest -v
PYTHONPATH=src python -m research_ssot.cli validate --manifest examples/manifest.json
PYTHONPATH=src python -m research_ssot.cli plan --manifest examples/manifest.json --intent crt_expiry_diagnosis --out /tmp/plan.json
PYTHONPATH=src python -m research_ssot.cli apply --plan /tmp/plan.json --results results.json --base-dir <artifact dir> --out /tmp/plan_applied.json
PYTHONPATH=src python -m research_ssot.cli report --plan /tmp/plan.json --out /tmp/final_report.md
```

The example intentionally remains blocked because three required contracts are unresolved. Its claims must therefore remain unsupported. Example placeholder identities are illustrative, not verified repository identities.

## Safety boundary

Planning is not execution. No scripts are invoked by this prototype. No existing scripts are deleted, modified, or automatically consolidated. Production configuration and research promotion remain outside its authority.
