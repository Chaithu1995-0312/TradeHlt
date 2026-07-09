"""
Feature-math registry — the AUTHORITATIVE source of feature-mathematics implementation.

Authority model (CLAUDE.md §6.5): the ontology (configs/formulas/market_ontology.yaml) DECLARES
what each quantity means; THIS registry is the single authority for HOW it is computed. Formulas
are NEVER `eval`'d — every declared name resolves to an explicit, named callable.

PUBLIC API (import from `features.formula_registry` facade or here):
    FORMULA_REGISTRY, compute_composition, compute_derived, validate_registry,
    build_lineage_graph, load_ontology

The sub-registries (primitive_/composition_/derived_registry, _loader) are INTERNAL — consumers
must not import them directly (enforced by tests/test_feature_lineage.py). Internal splits may
evolve freely behind this stable surface.
"""
from __future__ import annotations

from typing import Callable

from features.registry._loader import load_ontology, _ONTOLOGY_PATH
from features.registry.primitive_registry import PRIMITIVES, PRIMITIVE_SHORTNAME
from features.registry.composition_registry import compute_composition
from features.registry.derived_registry import DERIVED, compute_derived

# The aggregated executor: every declared impl name -> its explicit Python callable (NO eval).
FORMULA_REGISTRY: dict[str, Callable] = {**PRIMITIVES, **DERIVED}

_VALID_LIFECYCLE = (
    "proposed", "research", "registered", "parity_verified", "consumable", "deprecated",
)

__all__ = [
    "FORMULA_REGISTRY", "compute_composition", "compute_derived",
    "validate_registry", "build_lineage_graph", "load_ontology", "_ONTOLOGY_PATH",
]


def _iter_entries(ont: dict):
    """Yield (section, name, spec) for every governed feature across the three sections."""
    for section in ("primitives", "feature_compositions", "derived_metrics"):
        for name, spec in (ont.get(section) or {}).items():
            yield section, name, spec


def validate_registry(ontology: dict | None = None) -> list[str]:
    """
    Return a list of consistency problems between the ontology and the registry.
    Empty list == the WHAT authority and the executor agree. Used by the parity/lineage tests.

    Checks: every impl resolves; primitives/derived carry a formula; compositions carry
    numerator+denominator that resolve to primitives; ids unique; version is an int; lifecycle valid.
    """
    ont = ontology or load_ontology()
    problems: list[str] = []
    seen_ids: dict[str, str] = {}

    for section, name, spec in _iter_entries(ont):
        # id uniqueness + presence
        fid = spec.get("id")
        if not fid:
            problems.append(f"{section} '{name}': missing id")
        elif fid in seen_ids:
            problems.append(f"{section} '{name}': duplicate id {fid!r} (also {seen_ids[fid]!r})")
        else:
            seen_ids[fid] = name
        # version
        if not isinstance(spec.get("version"), int):
            problems.append(f"{section} '{name}': version must be an int")
        # lifecycle
        lc = spec.get("lifecycle")
        if lc not in _VALID_LIFECYCLE:
            problems.append(f"{section} '{name}': invalid lifecycle {lc!r}")

        if section == "feature_compositions":
            for side in ("numerator", "denominator"):
                ref = spec.get(side)
                if ref not in PRIMITIVE_SHORTNAME:
                    problems.append(f"composition '{name}': {side} {ref!r} not a known primitive")
        else:
            impl = spec.get("impl")
            if impl not in FORMULA_REGISTRY:
                problems.append(f"{section} '{name}': impl {impl!r} not in FORMULA_REGISTRY")
            if not str(spec.get("formula", "")).strip():
                problems.append(f"{section} '{name}': missing formula declaration")
        # registered+ must resolve its impl (compositions resolve via primitives, handled above)
        if lc in ("registered", "parity_verified", "consumable", "deprecated") and not fid:
            problems.append(f"{section} '{name}': lifecycle {lc!r} requires an id")

    return problems


def build_lineage_graph(ontology: dict | None = None) -> dict:
    """
    Build the feature dependency DAG from the ontology's `depends_on` edges.

    Returns {"depends_on": {name: [deps]}, "used_by": {name: [users]}, "nodes": [...],
             "base_inputs": [...]}. `used_by` is COMPUTED as the transpose of `depends_on`
    (never stored). Nodes include registered features and declared base_inputs.
    """
    ont = ontology or load_ontology()
    base_inputs = list(ont.get("base_inputs") or [])

    depends_on: dict[str, list[str]] = {}
    for _section, name, spec in _iter_entries(ont):
        depends_on[name] = list(spec.get("depends_on") or [])

    nodes = set(depends_on) | set(base_inputs)
    for deps in depends_on.values():
        nodes |= set(deps)

    used_by: dict[str, list[str]] = {n: [] for n in nodes}
    for name, deps in depends_on.items():
        for d in deps:
            used_by.setdefault(d, []).append(name)

    return {
        "depends_on": depends_on,
        "used_by": {k: sorted(v) for k, v in used_by.items()},
        "nodes": sorted(nodes),
        "base_inputs": base_inputs,
    }
