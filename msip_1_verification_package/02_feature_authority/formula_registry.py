"""
Formula registry — BACK-COMPAT FACADE over the registry package (src/features/registry/).

The feature-math registry was split into a package (primitive/composition/derived sub-registries)
to mirror the ontology's conceptual layers. This thin module re-exports the package's STABLE public
API so existing `from features import formula_registry` / `fr.*` call sites keep working unchanged,
and future internal splits never ripple outward.

AUTHORITY MODEL: the ontology (configs/formulas/market_ontology.yaml) DECLARES what each quantity
means; the registry is the single authority for HOW it is computed. Formulas are NEVER `eval`'d —
every declared name resolves to an explicit, named callable. A parity test binds declaration to
implementation; an ownership-lint (scripts/analysis/feature_math_lint.py) forbids re-derivation.

Consumers import ONLY this stable surface (or the same names from `features.registry`); the
sub-registries are internal.
"""
from __future__ import annotations

from features.registry import (  # noqa: F401  (re-export)
    FORMULA_REGISTRY,
    build_lineage_graph,
    compute_composition,
    compute_derived,
    load_ontology,
    validate_registry,
    _ONTOLOGY_PATH,
)

__all__ = [
    "FORMULA_REGISTRY",
    "compute_composition",
    "compute_derived",
    "validate_registry",
    "build_lineage_graph",
    "load_ontology",
    "_ONTOLOGY_PATH",
]
