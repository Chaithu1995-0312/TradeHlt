# Research SSOT Final Plan: crt_expiry_diagnosis

**Status:** `PLANNED_NOT_EXECUTED`  
**Execution policy:** `NO_ARBITRARY_SCRIPT_EXECUTION`

## Intent

Explain why CRT states expire, distinguishing clock/session resets from geometry and confirmation failures.

## Planned analysis tree

| Order | Node | Purpose | Operation | Depends on |
|---:|---|---|---|---|
| 1 | `resolve_run_identity` | Pin dataset, code, configuration, schema, timeframe, and state producer before analysis. | `contract_check` | — |
| 2 | `load_crt_transition_trace` | Locate or generate the canonical CRT transition trace for the pinned run. | `artifact_resolve` | `resolve_run_identity` |
| 3 | `measure_expiry_reasons` | Count expiry causes by state, reason, and eligible population without pooling distinct state producers. | `measurement` | `load_crt_transition_trace` |
| 4 | `measure_state_persistence` | Measure state duration and transition survival under a declared censoring rule. | `measurement` | `load_crt_transition_trace` |
| 5 | `assemble_crt_expiry_report` | Assemble validated measurements, provenance, disagreements, and unresolved gaps into one output. | `evidence_assembly` | `resolve_run_identity`, `measure_expiry_reasons`, `measure_state_persistence` |

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

This output is a deterministic plan, not a research finding. No script was executed by this MVP. Intent inferred from names/docstrings is not verified runtime behavior. Evidence validity, dataset compatibility, and metric contracts must be checked before any finding is admitted.
