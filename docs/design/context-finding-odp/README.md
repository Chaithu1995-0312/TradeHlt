# Context / Finding / ODP / MeasurementContract / ExecutionPolicy â€” design draft

**Status:** design-only **v0.3**. No runtime wiring. No `src/` changes.

Path: `D:\Tradelatest\docs\design\context-finding-odp\`

## Final design chain

```
Hypothesis
  â†’ Measurement Contract     (how / on whom)
  â†’ ODP                      (measurement)
  â†’ Finding                  (knowledge)
  â†’ Execution Policy         (policy â€” opinions)
  â†’ Live Decision            (runtime consumers)
```

Layers kept independent:

| Layer | Artifact |
|-------|----------|
| Identity | Context L1â€“L3 (+ CRT identity owners) |
| Observation | Context L4 + joins |
| Measurement | MeasurementContract + ODP |
| Knowledge | Finding Registry |
| Policy | ExecutionPolicy |

## Selector doctrine (v0.3)

**Context fields are admissible selectors. Context fields are not mandatory selectors.**

`null` means â€œnot conditionedâ€ and is normal. Sparse Contexts first; add selectors only after they survive measurement (`n` / holdout). Cardinality explosion is a first-class failure mode â€” do not fill gaps with synthetic averages.

## ExecutionPolicy rules (v0.3)

- May **read** Context / Finding / ODP (ODP only under matching `contract_ref`)
- May **not write** any of them
- Holds decision thresholds, participation, sizing, risk, conflict resolution
- `measured_fields: {}` required empty
- No silent quantileâ†’size formulas; any mapping needs an explicit POLICY rule id
- Runtime engine wins by default (`policy_vs_runtime_engine: runtime_engine_wins`)

## Schemas

- `schemas/observation_hierarchy.schema.yaml`
- `schemas/context.schema.yaml`
- `schemas/measurement_contract.schema.yaml`
- `schemas/finding_registry.schema.yaml`
- `schemas/odp.schema.yaml`
- `schemas/execution_policy.schema.yaml`

## Examples

- `examples/mc_odp_ctx_example.yaml`
- `examples/f_example_sweep_breaker_ob.yaml`
- `examples/odp_example_001.yaml`
- `examples/odp_fallback.yaml`
- `examples/policy_example_read_odp.yaml`


## v0.4 / defect resolutions (2026-09-06)

See `docs/DESIGN_DEFECTS_D1_D2_D3_L4.md`.

- **D2:** `Context.state_producer` required (`engine`|`resolver`) â€” identity defect if omitted
- **D1:** Policyâ†’DecisionEngine threshold mutation superseded by Socket Adapter Matrix v1.1 (ABSTAIN only)
- **D3:** `mechanism*` excluded from Context identity
- **L4:** boolean structure presence = intentional v1 cardinality reduction; polarity optional later


## v0.5 (2026-09-06)

- **D2 gate:** ODP population key = `contract_ref + identity_selectors` (includes `state_producer`, `variant_id` when resolver)
- **D1 OPEN:** belief vs preference â€” Policy may or may not retune DecisionEngine thresholds; v1.1 ABSTAIN-only is provisional
- **D3:** continuous floats (`htf_percentile`, `distance_to_boundary_atr`) out of identity; `htf_bucket` stays

- Vocabulary alignment (design-only, 2026-09-06): `ANALYTICS_VOCABULARY_ALIGNMENT.md` — Trace/Parquet/DuckDB name audit vs Context/ODP/PolicyOpinion.
- Analytics schema registry (governance symbol table, 2026-09-06): `docs/governance/ANALYTICS_SCHEMA_REGISTRY.md` — DuckDB runtime column inventory (not frozen aliases).
- Analytics lineage registry (Phase 4 descriptive origin, 2026-09-06): `docs/governance/ANALYTICS_LINEAGE_REGISTRY.md` — companion to schema registry (field_name+family); not attribution / not authority.
