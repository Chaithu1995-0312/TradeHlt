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

import importlib
import inspect
import re
from pathlib import Path

import pytest

from features import formula_registry as fr
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"

# Lifecycle ladder (verification maturity), low -> high.
_LADDER = ["proposed", "research", "registered", "parity_verified", "consumable", "deprecated"]

# Features covered by a parity test (test_candle_math.py + test_derived_math.py). A
# parity_verified+ feature MUST appear here — this cross-check is what "parity test exists" means.
_PARITY_COVERED = {
    "body_size", "candle_range", "upper_wick", "lower_wick", "total_wick", "body_ratio",
    "disp_strength", "retest_depth", "ema_spread", "momentum_score", "volatility_ratio",
    # FM-030/031 (2026-07-22): parity lives in tests/test_fm030_031_normalization_basis.py
    # rather than the test_derived_math.py battery, because these identities are selected by
    # `feature_pipeline.normalization_basis` and the parity assertion has to run the pipeline
    # under the non-default arm. They are `active: false` — covered, not consumed.
    "ema_spread_atr", "momentum_score_atr",
}

# Code/column aliases: ontology name -> feature-vector column name.
# EMPTIED in schema v4.0 (2026-07-22): the sole entry was {"candle_range": "wick_size"}, which
# existed only because the vector slot carried the misnomer while the ontology carried the honest
# name. v4.0 renamed the slot, so ontology name == column name and no alias is needed. Kept as a
# dict (not deleted) because a future rename may legitimately need one again.
_ALIAS: dict[str, str] = {}

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
    # DERIVED from the registry's own section tuple, never re-declared here (2026-07-24). This was
    # a hand-written literal and it silently went stale the moment `structural_states` was added:
    # every check in this file quietly stopped covering the new section instead of failing. The
    # repo had FIVE independent copies of this list; a local literal is one drift waiting to happen.
    from features.registry import _ITERATED_SECTIONS

    for section in _ITERATED_SECTIONS:
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
        if section in ("rolling_indicators", "temporal_context", "structural_states"):
            continue  # windowed/calendar/event — no scalar callable; impl names the pipeline computation authority
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


# Canonical slots with NO ontology identity. This set may only ever SHRINK — it is a ratchet, not
# a parking lot. RESOLVED 2026-07-31 (both entries): `trend_strength` is registered as FM-064
# (engine_runner.py:151's colliding local renamed to `ema_spread_abs`); `candles_since_retest` is
# registered as FM-065, with the CRT engine's distinct bars-since-RETEST-CANDLE quantity
# registered separately as FM-070 `candles_since_retest_state` and the crt_engine_v2.py emission
# sites renamed, aliased to the legacy key only at the BitNet call boundary (CH-002 pattern).
_UNREGISTERED_VECTOR_SLOTS: dict[str, str] = {}


def test_every_canonical_feature_has_an_identity(ont):
    """REVERSE coverage — the direction `test_consumable_are_in_feature_vector` does not check.

    That test proves ontology -> vector. Nothing proved vector -> ontology, so a feature could be
    emitted into the 39-dim vector with no declared identity, no formula, and no owner, and no
    floor would notice. Eleven features were in exactly that state before ontology v1.4.

    `_UNREGISTERED_VECTOR_SLOTS` is a SHRINK-ONLY ratchet: a new uncovered slot fails here, and
    removing one is the only legal edit.
    """
    known = {name for _s, name, _sp in _entries(ont)}
    known |= set(ont.get("base_inputs") or ())
    uncovered = [f for f in CANONICAL_FEATURES if _ALIAS.get(f, f) not in known]

    unexpected = sorted(set(uncovered) - set(_UNREGISTERED_VECTOR_SLOTS))
    assert not unexpected, (
        "CANONICAL_FEATURES emitted with no ontology identity and no declared reason:\n  "
        + "\n  ".join(unexpected)
        + "\nRegister them in market_ontology.yaml, or add them to _UNREGISTERED_VECTOR_SLOTS "
          "with the blocking reason."
    )

    stale = sorted(set(_UNREGISTERED_VECTOR_SLOTS) - set(uncovered))
    assert not stale, (
        "_UNREGISTERED_VECTOR_SLOTS lists slots that ARE now registered — the ratchet only "
        f"shrinks, so delete these entries: {stale}"
    )


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


# ─────────────────────────────────────────────────────────────────────────────
# L2 (2026-07-25): make ontology LINEAGE-BLOCK claims machine-verifiable.
# The tests above prove ontology<->vector MEMBERSHIP; these prove the `lineage:` block's own
# claims resolve — vector_key IDENTITY, vector_index ACCURACY, and that PRODUCER / declared
# CONSUMER references name real modules / symbols / features. Additive; no runtime change.
# ─────────────────────────────────────────────────────────────────────────────

# Ontology lineage refs use module SHORTHANDS ("feature_pipeline", "candle_math", ...); map each to
# its importable module once. A `produced_by`/`consumed_by` token is either a bare module (e.g.
# "bitnet.encoders") or "<module>.<symbol>". Symbols may be module-level OR methods on a class the
# module defines (the compute_* pipeline stages).
_LINEAGE_MODULE_ALIAS = {
    "feature_pipeline":            "features.feature_pipeline",
    "candle_math":                 "features.candle_math",
    "derived_math":                "features.derived_math",
    "session_classifier":          "features.session_classifier",
    "features.session_classifier": "features.session_classifier",
    "scoring_engine":              "engines.scoring_engine",
    "crt_engine_v2":               "config_layer.crt_engine_v2",
    "crt_gaussian_scorer":         "config_layer.crt_gaussian_scorer",
    "bitnet.encoders":             "bitnet.encoders",
}


def _module_defines(mod, symbol: str) -> bool:
    """True if `symbol` is a module-level attr OR a method on a class DEFINED in `mod`."""
    if hasattr(mod, symbol):
        return True
    for _n, obj in inspect.getmembers(mod, inspect.isclass):
        if getattr(obj, "__module__", None) == mod.__name__ and hasattr(obj, symbol):
            return True
    return False


def _lineage_symbol_resolves(dotted: str) -> bool:
    """Resolve an ontology lineage reference to a real module (bare) or module.symbol."""
    if dotted in _LINEAGE_MODULE_ALIAS:                     # bare module reference
        try:
            importlib.import_module(_LINEAGE_MODULE_ALIAS[dotted])
            return True
        except Exception:
            return False
    if "." not in dotted:
        return False
    prefix, symbol = dotted.rsplit(".", 1)
    modname = _LINEAGE_MODULE_ALIAS.get(prefix, prefix)
    try:
        mod = importlib.import_module(modname)
    except Exception:
        return False
    return _module_defines(mod, symbol)


def test_lineage_vector_key_and_index_match_schema(ont):
    """identity + vector index — vector_key names a real canonical feature at exactly vector_index;
    an unbound feature declares BOTH as [] (never one-sided)."""
    for _section, name, spec in _entries(ont):
        lin = spec.get("lineage") or {}
        vk, vi = lin.get("vector_key"), lin.get("vector_index")
        if vk == [] or vi == []:
            assert vk == [] and vi == [], (
                f"{name}: vector_key/vector_index must BOTH be [] when unbound (got vk={vk!r} vi={vi!r})"
            )
            continue
        assert isinstance(vk, str) and vk in FEATURE_INDEX_MAP, (
            f"{name}: vector_key {vk!r} is not a CANONICAL_FEATURES name"
        )
        assert vi == FEATURE_INDEX_MAP[vk], (
            f"{name}: vector_index {vi} != index of {vk!r} in CANONICAL_FEATURES "
            f"({FEATURE_INDEX_MAP[vk]})"
        )


def test_lineage_produced_by_resolves(ont):
    """producer — every entry's produced_by names a real emitter (module.symbol or a pipeline method)."""
    for _section, name, spec in _entries(ont):
        pb = (spec.get("lineage") or {}).get("produced_by")
        assert isinstance(pb, str) and pb.strip(), f"{name}: produced_by must be a non-empty symbol"
        assert _lineage_symbol_resolves(pb), (
            f"{name}: produced_by {pb!r} does not resolve to a known module/symbol"
        )


def test_lineage_declared_consumers_resolve(ont):
    """consumer WHERE DECLARED — each consumed_by token (other than the [UNKNOWN] marker) is either a
    registered feature/base_input or a resolvable module/symbol; a dangling consumer edge fails."""
    known = {n for _s, n, _sp in _entries(ont)} | set(ont.get("base_inputs") or ())
    for _section, name, spec in _entries(ont):
        cb = (spec.get("lineage") or {}).get("consumed_by")
        assert isinstance(cb, list), f"{name}: consumed_by must be a list (use [] or [UNKNOWN])"
        for tok in cb:
            if tok == "UNKNOWN":
                continue  # explicit undiscovered marker — allowed
            assert isinstance(tok, str) and tok.strip(), f"{name}: empty consumer token"
            assert tok in known or _lineage_symbol_resolves(tok), (
                f"{name}: declared consumer {tok!r} is neither a registered feature nor a "
                "resolvable module/symbol"
            )
