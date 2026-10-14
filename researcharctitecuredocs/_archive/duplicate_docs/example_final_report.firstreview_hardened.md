# Research SSOT Final Report: crt_expiry_diagnosis

**Status:** `BLOCKED`  
**Execution policy:** `NO_ARBITRARY_SCRIPT_EXECUTION`

## Intent

Explain why CRT states expire, distinguishing clock/session resets from geometry and confirmation failures.

## Analysis tree

| Order | Node | Status | Purpose | Operation | Depends on |
|---:|---|---|---|---|---|
| 1 | `resolve_run_identity` | `PLANNED` | Pin dataset, code, configuration, schema, timeframe, and state producer before analysis. | `contract_check` | — |
| 2 | `load_crt_transition_trace` | `BLOCKED` | Locate or generate the canonical CRT transition trace for the pinned run. | `artifact_resolve` | `resolve_run_identity` |
| 3 | `measure_expiry_reasons` | `BLOCKED_UPSTREAM` | Count expiry causes by state, reason, and eligible population without pooling distinct state producers. | `measurement` | `load_crt_transition_trace` |
| 4 | `measure_state_persistence` | `BLOCKED_UPSTREAM` | Measure state duration and transition survival under a declared censoring rule. | `measurement` | `load_crt_transition_trace` |
| 5 | `assemble_crt_expiry_report` | `BLOCKED_UPSTREAM` | Assemble validated measurements, provenance, disagreements, and unresolved gaps into one output. | `evidence_assembly` | `resolve_run_identity`, `measure_expiry_reasons`, `measure_state_persistence` |

## Claims and evidence

| Claim | Status | Evidence | Missing / unverified |
|---|---|---|---|
| `state_producer_identity` | **UNSUPPORTED** | — | `resolve_run_identity.run_identity_record` (PLANNED) |
| `expiry_reason_counts` | **UNSUPPORTED** | — | `measure_expiry_reasons.expiry_reason_measurement` (BLOCKED_UPSTREAM) |
| `population_identity` | **UNSUPPORTED** | — | `measure_expiry_reasons.population_counts` (BLOCKED_UPSTREAM) |
| `measurement_contract` | **UNSUPPORTED** | — | `measure_expiry_reasons.expiry_reason_measurement` (BLOCKED_UPSTREAM), `measure_state_persistence.state_persistence_measurement` (BLOCKED_UPSTREAM) |

## Blocked reasons

- `load_crt_transition_trace`: External input unresolved: transition_trace_contract
- `measure_expiry_reasons`: Upstream dependency not available: load_crt_transition_trace (BLOCKED)
- `measure_state_persistence`: Upstream dependency not available: load_crt_transition_trace (BLOCKED)
- `assemble_crt_expiry_report`: Upstream dependency not available: measure_expiry_reasons (BLOCKED_UPSTREAM)
- `assemble_crt_expiry_report`: Upstream dependency not available: measure_state_persistence (BLOCKED_UPSTREAM)

### Unresolved external inputs

- `transition_trace_contract` (kind: `contract`)
- `expiry_reason_contract` (kind: `contract`)
- `persistence_contract` (kind: `contract`)

## Required evidence outputs

- `resolve_run_identity` → `run_identity_record`
- `load_crt_transition_trace` → `crt_transition_trace`
- `measure_expiry_reasons` → `expiry_reason_measurement`
- `measure_expiry_reasons` → `population_counts`
- `measure_state_persistence` → `state_persistence_measurement`
- `assemble_crt_expiry_report` → `final_report.md`
- `assemble_crt_expiry_report` → `run_record.json`

## Inventory snapshot

No script inventory was attached to this report.

## Interpretation and limits

A claim is SUPPORTED only when every mapped evidence output comes from a COMPLETED or REUSED node. PLANNED, BLOCKED, FAILED, or SKIPPED outputs do not support conclusions. This framework does not execute arbitrary scripts; execution results must come from explicitly registered adapters. Producer identity is kind + config reference. A compare output is diagnostic and cannot be reused as a state population.
