"""Feature-lineage exhaustiveness floor — the "no orphan features" invariant.

Proves the ontology, registry, implementations, parity tests, feature vector and dependency graph
form ONE coherent contract. For every governed feature the full chain must resolve:
    Feature -> ontology entry (id/version/lifecycle/formula) -> registry impl callable
            -> parity test (parity_verified+) -> pipeline column / vector (consumable)
Plus: the dependency DAG is acyclic and resolves to OHLC base inputs, `used_by` is the exact
transpose of `depends_on`, ids are unique/stable, and no consumer reaches past the stable public
API into the internal sub-registries.

This is the test that validates the ARCHITECTURE, not a single feature (round-2 review item #7).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from features import formula_registry as fr
from features.feature_schema import CANONICAL_FEATURES

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"

# Lifecycle ladder (verification maturity), low -> high.
_LADDER = ["proposed", "research", "registered", "parity_verified", "consumable", "deprecated"]

# Features covered by a parity test (test_candle_math.py + test_derived_math.py). A
# parity_verified+ feature MUST appear here — this cross-check is what "parity test exists" means.
_PARITY_COVERED = {
    "body_size", "candle_range", "upper_wick", "lower_wick", "total_wick", "body_ratio",
    "disp_strength", "retest_depth", "ema_spread", "momentum_score", "volatility_ratio",
}

# Code/column aliases: ontology name -> feature-vector column name.
_ALIAS = {"candle_range": "wick_size"}

# Internal sub-registries — no consumer may import these directly (stable public API is the facade).
_INTERNAL_MODULES = (
    "features.registry.primitive_registry",
    "features.registry.composition_registry",
    "features.registry.derived_registry",
    "features.registry._loader",
)

_ID_RE = re.compile(r"^FM-\d{3}$")


@pytest.fixture(scope="module")
def ont():
    return fr.load_ontology()


def _entries(ont):
    for section in ("primitives", "feature_compositions", "derived_metrics", "rolling_indicators"):
        for name, spec in (ont.get(section) or {}).items():
            yield section, name, spec


def _at_least(lifecycle: str, floor: str) -> bool:
    return _LADDER.index(lifecycle) >= _LADDER.index(floor)


def test_registry_and_ontology_agree():
    assert fr.validate_registry() == []


def test_every_entry_has_stable_id_version_lifecycle(ont):
    seen: dict[str, str] = {}
    for section, name, spec in _entries(ont):
        fid = spec.get("id")
        assert fid and _ID_RE.match(fid), f"{section}.{name}: bad id {fid!r}"
        assert fid not in seen, f"duplicate id {fid} ({name} vs {seen.get(fid)})"
        seen[fid] = name
        assert isinstance(spec.get("version"), int), f"{name}: version must be int"
        assert spec.get("lifecycle") in _LADDER, f"{name}: bad lifecycle {spec.get('lifecycle')!r}"


def test_formula_or_composition_present(ont):
    for section, name, spec in _entries(ont):
        if section == "feature_compositions":
            assert spec.get("numerator") and spec.get("denominator"), f"{name}: missing num/den"
        else:
            assert str(spec.get("formula", "")).strip(), f"{name}: missing formula"


def test_registered_plus_resolve_impl(ont):
    for section, name, spec in _entries(ont):
        if section == "feature_compositions":
            continue  # compositions resolve via primitives (checked by validate_registry)
        if section == "rolling_indicators":
            continue  # windowed — no scalar callable; impl names the pipeline computation authority
        if _at_least(spec["lifecycle"], "registered"):
            assert spec.get("impl") in fr.FORMULA_REGISTRY, f"{name}: impl not in FORMULA_REGISTRY"


def test_parity_verified_have_parity_coverage(ont):
    for _section, name, spec in _entries(ont):
        if _at_least(spec["lifecycle"], "parity_verified") and spec["lifecycle"] != "deprecated":
            assert name in _PARITY_COVERED, (
                f"{name} is {spec['lifecycle']} but has no parity test — add one or lower lifecycle"
            )


def test_consumable_are_in_feature_vector(ont):
    canon = set(CANONICAL_FEATURES)
    for _section, name, spec in _entries(ont):
        if spec["lifecycle"] == "consumable":
            col = _ALIAS.get(name, name)
            assert col in canon, f"{name} is consumable but neither it nor alias {col!r} ∈ CANONICAL_FEATURES"


def test_dependency_graph_acyclic_and_grounded(ont):
    g = fr.build_lineage_graph(ont)
    depends_on = g["depends_on"]
    registered = set(depends_on)
    base = set(g["base_inputs"])

    # every dependency edge points to a registered feature or a base input
    for name, deps in depends_on.items():
        for d in deps:
            assert d in registered or d in base, f"{name} depends_on unknown node {d!r}"

    # acyclic + every feature resolves down to base inputs
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in registered}

    def visit(n, stack):
        if n in base:
            return
        assert n in registered, f"dangling node {n!r}"
        if color[n] == BLACK:
            return
        assert color[n] != GREY, f"cycle through {n!r} (stack {stack})"
        color[n] = GREY
        for d in depends_on[n]:
            visit(d, stack + [n])
        color[n] = BLACK

    for n in registered:
        visit(n, [])


def test_used_by_is_transpose_of_depends_on(ont):
    g = fr.build_lineage_graph(ont)
    depends_on, used_by = g["depends_on"], g["used_by"]
    expected: dict[str, set] = {}
    for name, deps in depends_on.items():
        for d in deps:
            expected.setdefault(d, set()).add(name)
    for node, users in expected.items():
        assert set(used_by.get(node, [])) == users, f"used_by[{node}] != transpose"


def test_no_consumer_imports_internal_subregistries():
    """Consumers must import only the stable public surface (facade / features.registry package)."""
    offenders = []
    for path in _SRC.rglob("*.py"):
        rel = path.relative_to(_SRC).as_posix()
        if rel.startswith("features/registry/"):
            continue  # the package itself legitimately imports its own submodules
        text = path.read_text(encoding="utf-8")
        for mod in _INTERNAL_MODULES:
            if mod in text:
                offenders.append(f"{rel}: imports internal {mod}")
    assert offenders == [], offenders
