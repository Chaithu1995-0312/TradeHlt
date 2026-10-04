# OSS Integration Governance Lifecycle

```text
DISCOVERED
  → ASSESSED
  → APPROVED_FOR_LAB
  → BENCHMARKED
  → CERTIFIED
  → APPROVED_FOR_INTEGRATION
  → PROMOTED
```

Terminal / holding states (may apply at any step):

| State | Meaning |
|---|---|
| `REJECTED` | Explicit no — do not use |
| `DEFERRED` | Parked; not rejected, not approved |
| `RESEARCH_ONLY` | Evidence generation only; never production |
| `ADAPTER_ONLY` | Isolated adapter permitted; no spine wiring |
| `REFERENCE_ONLY` | Docs / papers only; no code dependency |

## Hard rules

1. **Never silently promote** an OSS dependency into production paths.
2. Default trust ceiling for external OSS: **T3**. **T4 production authority is forbidden** without an independent architecture decision + certification.
3. OSS must never silently become authoritative over:
   - market ontology
   - canonical feature identity
   - CRT semantics / state / context / shape
   - Fusion / Decision
   - Ultron capital authority
   - governance closure
   - production configuration
4. Every lifecycle transition is an append-only decision with `decision_reason` + provenance.
5. Construction protocol still applies for any production-touching change (`DOCUMENTATION_ONLY` for pure docs; broader classes when wiring).

## Intake pipeline (mandatory)

```text
DISCOVER → CAPABILITY MATCH → LICENSE → SECURITY/SUPPLY-CHAIN →
MAINTENANCE → ARCHITECTURAL BOUNDARY → ADAPTER DESIGN → VERSION PIN →
ISOLATED INTEGRATION → PARITY/CERTIFICATION → BENCHMARK → EVIDENCE →
GOVERNANCE DECISION
```

Forbidden:

```text
pip install → import throughout repository → assume equivalence
```

## Research evidence rule

Every OSS result must carry: `experiment_id`, `hypothesis`, `dataset`, `engine`,
`version`, `configuration`, `run artifact`, `raw outputs`, `normalized outputs`,
`metric definitions`, `limitations`, `reproducibility status`.

```text
Research result ≠ production finding ≠ production authority
```
