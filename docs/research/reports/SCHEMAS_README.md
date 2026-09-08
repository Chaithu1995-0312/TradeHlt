# Schemas for FALSIFY / Measurement architecture (ARCH-REVIEW.v1)

**run_id:** `arch_review_falsify_pack_20260908_023341`  
**version:** `ARCH-REVIEW.v1`  
**Pin:** `d7c25f6e55616261b8b229b000875abd3bd315eb`

These schemas make the FALSIFY Evidence Pack and registries machine-checkable. They do **not** reopen L-003 doctrine; they bind identities already frozen under L-003L/M + MOR.

## Files

| Schema | Purpose |
|---|---|
| `measurement_object.schema.json` | MeasurementObject identity: `object_id`, **`formula_map` (domain→codomain)**, producer, value_domain, projections, status |
| `joint_state_space.schema.json` | Freeze **L** (OutcomeLabel), **S=L×L**, StateID map, aliases, `Y_joint:Ω→S` |
| `population.schema.json` | Population registry entries: id, unit, membership_rule, instrument_scope |
| `falsify_record.schema.json` | One falsification/association record: H0, predictor, target, metric, result, scope, artifacts, non_claims |
| `registry_shape_references.json` | Keys mirrored from existing `measurement_object_registry.json` / L-003L / L-003M |

## How schemas bind to FALSIFY records

1. **`falsify_record.MeasurementObject`** SHOULD cite a `measurement_object.schema.json`-valid object (or `object_id` registered in MOR).
2. **`falsify_record.Population`** SHOULD cite a `population.schema.json`-valid `population_id` from Population Registry.
3. **Targets** that are joint coordinates (e.g. `STATE_SL_TP`) MUST be members of **S** in `joint_state_space.schema.json` / L-003L `Omega_joint`.
4. Mathematical maps are first-class:
   - `Y_scanner : Ω → L` (OutcomeLabel)
   - `Y_oracle  : Ω → L`
   - `Y_joint   : Ω → S` where `S = L × L`
5. Producer refs alone are insufficient; `formula_map.notation` must appear on Y_* registry entries.

## Companion human artifacts

- Report: `docs/research/reports/L003_JSE_ARCHITECTURE_REVIEW_AND_FALSIFY_EVIDENCE.md`
- Pack: `docs/research/reports/l003_jse_falsify_evidence_pack-2026-09-08.json`
- Population Registry: `docs/governance/POPULATION_REGISTRY.md` + `population_registry.json`
