"""
fm_resolve.py
═══════════════════════════════════════════════════════════════════════════════
Phase-2 FM resolution (Option A) — FM id → callable via ontology + FORMULA_REGISTRY.

Authority:
  WHAT  = market_ontology.yaml + FORMULA_REGISTRY / compute_composition
  WHO   = state_contracts declare required_fm (dependency identity only)
  Control flow = Python call sites (caller must pass explicit fm_id + inputs)

Never:
  - auto-execute state_contracts.required_fm as a schedule
  - eval YAML formulas / expressions
  - invent alternate math

Parity goal: resolved callables for FM-002/027/028 are identity-equal to the
existing candle_math / derived_math bindings; FM-010 uses the composition path
with float-parity to candle_math.body_ratio.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Mapping, Optional

_ACCEPTABLE_FM_LIFECYCLES = frozenset(
    {"registered", "parity_verified", "consumable"}
)

# CRT Phase-2 slice — FM ids wired into crt_engine_v2 call sites.
# FM-070 added 2026-07-31 (candles_since_retest_state — FM-065 collision resolution, CH-002 pattern).
PHASE2_CRT_FM_IDS: frozenset[str] = frozenset(
    {"FM-002", "FM-010", "FM-027", "FM-028", "FM-070"}
)

# Phase-3a: crt_feature_builder geometry (transcriber; 0 live callers historically).
PHASE3A_FEATURE_BUILDER_FM_IDS: frozenset[str] = frozenset(
    {"FM-001", "FM-002", "FM-010"}
)

# Phase-3b: scoring_engine breakout displacement rescale (GD-004 / FM-029).
PHASE3B_SCORING_FM_IDS: frozenset[str] = frozenset({"FM-029"})

# Phase-3c: causal_structure live liquidity metrics (FeatureStore online path).
PHASE3C_CAUSAL_STRUCTURE_FM_IDS: frozenset[str] = frozenset(
    {"FM-025", "FM-026"}
)


class FMResolveError(ValueError):
    """Fail-closed FM resolution / contract membership error."""


@dataclass(frozen=True, slots=True)
class ResolvedFM:
    """Immutable resolution of one FM id to an executable binding."""

    fm_id: str
    name: str
    section: str
    kind: str  # "registry" | "composition"
    callable: Callable[..., float]
    impl_key: Optional[str]  # FORMULA_REGISTRY key when kind=registry


def _ontology_index() -> dict[str, dict[str, Any]]:
    """Map FM-0NN → ontology entry metadata (no leading-underscore internal keys)."""
    # facade rule: consumers import only the stable public surface (features.registry
    # re-exports PRIMITIVE_SHORTNAME) — never internal subregistries directly
    from features.registry import FORMULA_REGISTRY, PRIMITIVE_SHORTNAME, load_ontology

    ont = load_ontology()
    index: dict[str, dict[str, Any]] = {}
    for section in ("primitives", "feature_compositions", "derived_metrics"):
        block = ont.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if not isinstance(spec, dict):
                continue
            fid = spec.get("id")
            if not fid:
                continue
            if fid in index:
                raise FMResolveError(
                    f"Ontology duplicate FM id {fid!r} "
                    f"({index[fid]['name']} and {name})"
                )
            index[fid] = {
                "id": fid,
                "name": name,
                "section": section,
                "impl": spec.get("impl"),
                "lifecycle": spec.get("lifecycle"),
                "numerator": spec.get("numerator"),
                "denominator": spec.get("denominator"),
                "spec": spec,
            }
    # Private attachments for resolvers (not FM ids)
    index["__FORMULA_REGISTRY__"] = FORMULA_REGISTRY  # type: ignore[assignment]
    index["__PRIMITIVE_SHORTNAME__"] = PRIMITIVE_SHORTNAME  # type: ignore[assignment]
    return index


def clear_fm_resolve_cache() -> None:
    """Test helper — drop lru caches."""
    resolve_fm.cache_clear()
    resolve_fm_callable.cache_clear()


@lru_cache(maxsize=128)
def resolve_fm(fm_id: str) -> ResolvedFM:
    """
    Resolve an FM id to a callable binding. Fail-closed.

    Does not execute the formula — only binds the implementation.
    """
    if not isinstance(fm_id, str) or not fm_id.startswith("FM-"):
        raise FMResolveError(
            f"Invalid FM id {fm_id!r}: expected FM-0NN form"
        )
    if any(ch in fm_id for ch in ("=", "*", "/", "(", ")", " ", "\t", "\n")):
        raise FMResolveError(
            f"Invalid FM id {fm_id!r}: looks like an expression"
        )

    index = _ontology_index()
    entry = index.get(fm_id)
    if entry is None or fm_id.startswith("__"):
        raise FMResolveError(
            f"required_fm {fm_id!r}: FM ID not found in market ontology / FORMULA_REGISTRY"
        )

    lifecycle = entry.get("lifecycle")
    if lifecycle is not None and lifecycle not in _ACCEPTABLE_FM_LIFECYCLES:
        raise FMResolveError(
            f"required_fm {fm_id!r}: lifecycle={lifecycle!r} not in "
            f"{sorted(_ACCEPTABLE_FM_LIFECYCLES)}"
        )

    reg: Mapping[str, Any] = index["__FORMULA_REGISTRY__"]  # type: ignore[assignment]
    prims: Mapping[str, Any] = index["__PRIMITIVE_SHORTNAME__"]  # type: ignore[assignment]
    section = entry["section"]
    name = entry["name"]

    if section in ("primitives", "derived_metrics"):
        impl = entry.get("impl")
        if not impl:
            raise FMResolveError(
                f"required_fm {fm_id!r}: missing implementation binding (impl)"
            )
        if impl not in reg:
            raise FMResolveError(
                f"required_fm {fm_id!r}: impl {impl!r} not in FORMULA_REGISTRY"
            )
        fn = reg[impl]
        if not callable(fn):
            raise FMResolveError(
                f"required_fm {fm_id!r}: impl {impl!r} is not callable"
            )
        return ResolvedFM(
            fm_id=fm_id,
            name=name,
            section=section,
            kind="registry",
            callable=fn,
            impl_key=impl,
        )

    if section == "feature_compositions":
        num = entry.get("numerator")
        den = entry.get("denominator")
        if not num or not den:
            raise FMResolveError(
                f"required_fm {fm_id!r}: composition missing numerator/denominator"
            )
        if num not in prims or den not in prims:
            raise FMResolveError(
                f"required_fm {fm_id!r}: composition primitives "
                f"numerator={num!r} denominator={den!r} unresolved"
            )
        if not callable(prims[num]) or not callable(prims[den]):
            raise FMResolveError(
                f"required_fm {fm_id!r}: composition primitives not callable"
            )

        from features.registry import compute_composition

        def _composition_fn(
            open_: float, high: float, low: float, close: float
        ) -> float:
            return float(compute_composition(name, open_, high, low, close))

        _composition_fn.__name__ = f"composition_{name}"
        _composition_fn.__qualname__ = f"fm_resolve.composition_{name}"
        return ResolvedFM(
            fm_id=fm_id,
            name=name,
            section=section,
            kind="composition",
            callable=_composition_fn,
            impl_key=None,
        )

    raise FMResolveError(
        f"required_fm {fm_id!r}: unknown ontology section {section!r}"
    )


@lru_cache(maxsize=128)
def resolve_fm_callable(fm_id: str) -> Callable[..., float]:
    """Convenience: resolve and return only the callable."""
    return resolve_fm(fm_id).callable


def assert_registry_identity(fm_id: str, expected: Callable[..., float]) -> None:
    """
    Fail-closed if a registry-kind FM does not resolve to the expected callable
    by identity (``is``). Compositions are excluded (use float parity instead).
    """
    resolved = resolve_fm(fm_id)
    if resolved.kind != "registry":
        raise FMResolveError(
            f"{fm_id}: assert_registry_identity only applies to registry-kind "
            f"bindings (got kind={resolved.kind!r})"
        )
    if resolved.callable is not expected:
        raise FMResolveError(
            f"{fm_id}: resolved callable {resolved.callable!r} is not "
            f"identity-equal to expected {expected!r} "
            f"(impl_key={resolved.impl_key!r})"
        )


def assert_fm_in_contract(
    bundle: Any,
    state_id: str,
    fm_id: str,
) -> None:
    """
    Assert that ``fm_id`` is declared in ``state_contracts[state_id].required_fm``.

    Used by tests / optional debug checks — not a hot-path auto-schedule.
    ``bundle`` is a StateContractBundle (duck-typed via .get).
    """
    sc = bundle.get(state_id)
    required = getattr(sc, "required_fm", ())
    if fm_id not in required:
        raise FMResolveError(
            f"contract membership: {fm_id!r} not in "
            f"state_contracts[{state_id!r}].required_fm={list(required)}"
        )


def bind_phase2_crt_callables() -> dict[str, Callable[..., float]]:
    """
    Resolve the Phase-2 CRT FM slice once; assert registry identity where applicable.

    Returns ``{fm_id: callable}``. Safe to call at module import of crt_engine_v2.
    """
    from features import candle_math as _cm
    from features import derived_math as _dm

    # Registry identity proofs (STOP if FORMULA_REGISTRY drifts off canonical modules)
    assert_registry_identity("FM-002", _cm.candle_range)
    assert_registry_identity("FM-027", _dm.displacement_retrace)
    assert_registry_identity("FM-028", _dm.displacement_atr_ratio)
    assert_registry_identity("FM-070", _dm.candles_since_retest_state)

    # FM-010 composition: bind composition path; float parity checked in tests
    out: dict[str, Callable[..., float]] = {
        "FM-002": resolve_fm_callable("FM-002"),
        "FM-010": resolve_fm_callable("FM-010"),
        "FM-027": resolve_fm_callable("FM-027"),
        "FM-028": resolve_fm_callable("FM-028"),
        "FM-070": resolve_fm_callable("FM-070"),
    }
    return out


def bind_phase3a_feature_builder_callables() -> dict[str, Callable[..., float]]:
    """
    Phase-3a: geometry slice for ``crt_feature_builder`` (FM-001 / FM-002 / FM-010).

    Registry identities for primitives; FM-010 composition float-parity in tests.
    Safe to call at module import of crt_feature_builder.
    """
    from features import candle_math as _cm

    assert_registry_identity("FM-001", _cm.body_size)
    assert_registry_identity("FM-002", _cm.candle_range)
    out: dict[str, Callable[..., float]] = {
        "FM-001": resolve_fm_callable("FM-001"),
        "FM-002": resolve_fm_callable("FM-002"),
        "FM-010": resolve_fm_callable("FM-010"),
    }
    if set(out) != PHASE3A_FEATURE_BUILDER_FM_IDS:
        raise FMResolveError(
            f"phase3a bind key set {set(out)} != {PHASE3A_FEATURE_BUILDER_FM_IDS}"
        )
    return out


def bind_phase3b_scoring_callables() -> dict[str, Callable[..., float]]:
    """
    Phase-3b: scoring_engine FM-029 (``disp_strength_atr_rescale``).

    Identity-equal to ``derived_math.disp_strength_atr_rescale`` (GD-004 as-wired math).
    Safe to call at module import of scoring_engine.
    """
    from features import derived_math as _dm

    assert_registry_identity("FM-029", _dm.disp_strength_atr_rescale)
    out: dict[str, Callable[..., float]] = {
        "FM-029": resolve_fm_callable("FM-029"),
    }
    if set(out) != PHASE3B_SCORING_FM_IDS:
        raise FMResolveError(
            f"phase3b bind key set {set(out)} != {PHASE3B_SCORING_FM_IDS}"
        )
    return out


def bind_phase3c_causal_structure_callables() -> dict[str, Callable[..., float]]:
    """
    Phase-3c: causal_structure FM-025 / FM-026 (liquidity distance + pressure).

    Identity-equal to ``derived_math.liquidity_distance`` /
    ``derived_math.liquidity_pressure_score``. Safe to call at module import of
    causal_structure (live FeatureStore online path).
    """
    from features import derived_math as _dm

    assert_registry_identity("FM-025", _dm.liquidity_distance)
    assert_registry_identity("FM-026", _dm.liquidity_pressure_score)
    out: dict[str, Callable[..., float]] = {
        "FM-025": resolve_fm_callable("FM-025"),
        "FM-026": resolve_fm_callable("FM-026"),
    }
    if set(out) != PHASE3C_CAUSAL_STRUCTURE_FM_IDS:
        raise FMResolveError(
            f"phase3c bind key set {set(out)} != {PHASE3C_CAUSAL_STRUCTURE_FM_IDS}"
        )
    return out
