"""semantics — runtime of the Semantic OS v2 meaning plane (slice 1: foundation + market core; slice 2: trading).

Spec: docs/governance/SEMANTIC_OS_V2_MEANING_PLANE.md
Registries: configs/formulas/concept_contracts.yaml, configs/formulas/representation_registry/,
configs/formulas/terminal_reason_map.yaml

Layering (a module may import only from its own layer or below):
    geometry  ->  market  ->  trading  ->  (decision/execution: later slice)

Existing modules are CALLED where their meaning matches a concept contract (structure.predicates,
features.causal_structure, features.smc.*, config_layer.m15_structural_range); they are never
edited from here. Nothing in this package is wired into the engine, the pipeline or the live rail.
"""
