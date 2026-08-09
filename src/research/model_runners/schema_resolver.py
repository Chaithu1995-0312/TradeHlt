"""Single live->trained feature-schema authority for model_runners (R1).

Problem this closes
-------------------
Before this module three adapters each answered "which features was this model
trained on, and in what order?" independently:

  * ``rr_trained``   — a local ``_v3_order_from_v4()`` with hardcoded rename literals
  * ``envelope``     — ``research.clean_labels.builder.LEGACY_FEATURE_NAMES``
  * ``gaussian_ml``  — ``meta['feature_schema_resolved']`` via ``gaussian_schema_contract``

Two of those produce a **38-name** order that disagree on NAMING
(``rr_trained`` renames ``macd_hist_z``->``macd_hist`` and
``candle_range``->``wick_size``; ``envelope`` keeps the live v4 names). Same
dimension, different convention, no shared authority — so "which schema is this
artifact?" was only answerable by opening and diffing JSON.

Contract
--------
1. A schema is identified by a stable ``schema_id`` (see ``SCHEMA_REGISTRY``) or
   is **declared by the artifact itself** (``resolve_declared``).
2. Every trained name resolves to a live canonical name. The alias table is
   ``features.feature_schema.SCHEMA_V3_ALIASES`` — the single alias authority.
   This module never defines its own rename literals.
3. Vectors are built **by name, in trained order** (never positional slicing of
   the ambient live vector, never zero-fill, never pad/truncate).
4. No defaults anywhere: an unknown ``schema_id``, an unresolvable trained name,
   a duplicate resolution, or a missing live feature raises.

Authority: research only. Grants no promote/activation authority (CLAUDE.md §6.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    SCHEMA_V3_ALIASES,
)


class SchemaResolutionError(ValueError):
    """A trained schema cannot be aligned to the live canonical schema."""


# Live name -> the v3 name that maps onto it (inverse of SCHEMA_V3_ALIASES).
# Derived, never hand-written: SCHEMA_V3_ALIASES is the only alias authority.
_LIVE_TO_V3: dict[str, str] = {live: v3 for v3, live in SCHEMA_V3_ALIASES.items()}

# The one dimension v4 added over v3/legacy-38 (the MACD histogram split).
_V4_ONLY_FEATURE = "macd_hist_raw"


def _canonical_minus_v4_only() -> list[str]:
    """Live canonical order with the v4-only feature removed (39 -> 38)."""
    if _V4_ONLY_FEATURE not in CANONICAL_FEATURES:
        raise SchemaResolutionError(
            f"expected {_V4_ONLY_FEATURE!r} in CANONICAL_FEATURES; live schema "
            f"changed (dim={CANONICAL_FEATURE_DIM}). Update schema_resolver."
        )
    return [n for n in CANONICAL_FEATURES if n != _V4_ONLY_FEATURE]


@dataclass(frozen=True)
class ResolvedSchema:
    """A trained feature order, aligned to live canonical names.

    ``trained_names[i]`` is what the artifact calls slot *i*;
    ``live_names[i]`` is the key to read from the live feature dict for slot *i*.
    The two lists are positionally aligned and equal length.
    """

    schema_id: str
    trained_names: tuple[str, ...]
    live_names: tuple[str, ...]
    source: str  # "registry" (fixed id) | "artifact" (self-declared)

    def __post_init__(self) -> None:
        if len(self.trained_names) != len(self.live_names):
            raise SchemaResolutionError(
                f"{self.schema_id}: trained/live length mismatch "
                f"{len(self.trained_names)} != {len(self.live_names)}"
            )
        if not self.trained_names:
            raise SchemaResolutionError(f"{self.schema_id}: empty schema")
        if len(set(self.live_names)) != len(self.live_names):
            raise SchemaResolutionError(
                f"{self.schema_id}: trained names collapse onto duplicate live "
                f"names (a trained dimension would be silently dropped)"
            )
        unknown = [n for n in self.live_names if n not in CANONICAL_FEATURES]
        if unknown:
            raise SchemaResolutionError(
                f"{self.schema_id}: live name(s) absent from CANONICAL_FEATURES: "
                f"{unknown}"
            )

    @property
    def dim(self) -> int:
        return len(self.live_names)

    @property
    def renames(self) -> dict[str, str]:
        """trained -> live for slots whose name changed (empty when none)."""
        return {
            t: l
            for t, l in zip(self.trained_names, self.live_names)
            if t != l
        }

    def build_vector(self, features: Mapping[str, float]) -> list[float]:
        """Name-anchored extraction in trained order. Missing key raises."""
        vec: list[float] = []
        for live in self.live_names:
            if live not in features:
                raise SchemaResolutionError(
                    f"{self.schema_id}: live feature dict missing {live!r} "
                    f"required by the trained order. No zero-fill."
                )
            try:
                vec.append(float(features[live]))
            except (TypeError, ValueError) as exc:
                raise SchemaResolutionError(
                    f"{self.schema_id}: feature {live!r} not coercible to float: {exc}"
                ) from exc
        if len(vec) != self.dim:
            raise SchemaResolutionError(
                f"{self.schema_id}: built {len(vec)} values, expected {self.dim}"
            )
        return vec

    def assert_model_width(self, model_n_features: int) -> None:
        """Fail closed when the artifact's width disagrees with this schema."""
        if int(model_n_features) != self.dim:
            raise SchemaResolutionError(
                f"{self.schema_id}: model n_features={model_n_features} != "
                f"schema dim={self.dim}. Refusing silent pad/truncate — the "
                f"artifact was trained on a different schema generation."
            )

    def to_manifest(self) -> dict:
        """Machine-readable stamp for RunManifest.artifact (A8)."""
        return {
            "trained_schema_id": self.schema_id,
            "trained_schema_source": self.source,
            "trained_schema_dim": self.dim,
            "trained_schema_renames": self.renames,
        }


def _build_canonical_39() -> ResolvedSchema:
    names = tuple(CANONICAL_FEATURES)
    return ResolvedSchema(
        schema_id="canonical_39",
        trained_names=names,
        live_names=names,
        source="registry",
    )


def _build_legacy_38_env() -> ResolvedSchema:
    """Envelope / clean-labels convention: drop the v4-only feature, no renames."""
    live = tuple(_canonical_minus_v4_only())
    return ResolvedSchema(
        schema_id="legacy_38_env",
        trained_names=live,
        live_names=live,
        source="registry",
    )


def _build_canonical_38_v3() -> ResolvedSchema:
    """NanoInference / rr_trained convention: drop v4-only feature AND use v3 names."""
    live = tuple(_canonical_minus_v4_only())
    # Explicit branch, not `.get(n, n)`: this package bans soft-default lookups
    # (tests/research/test_model_runners_contracts.py).
    trained_list: list[str] = []
    for n in live:
        if n in _LIVE_TO_V3:
            trained_list.append(_LIVE_TO_V3[n])
        else:
            trained_list.append(n)
    trained = tuple(trained_list)
    return ResolvedSchema(
        schema_id="canonical_38_v3",
        trained_names=trained,
        live_names=live,
        source="registry",
    )


SCHEMA_REGISTRY: dict[str, ResolvedSchema] = {
    s.schema_id: s
    for s in (
        _build_canonical_39(),
        _build_legacy_38_env(),
        _build_canonical_38_v3(),
    )
}


def resolve_named(schema_id: str) -> ResolvedSchema:
    """Return a fixed registered schema by id. Unknown id raises (no default)."""
    if schema_id not in SCHEMA_REGISTRY:
        known = ", ".join(sorted(SCHEMA_REGISTRY))
        raise SchemaResolutionError(
            f"unknown trained_schema_id={schema_id!r}. Known: {known}"
        )
    return SCHEMA_REGISTRY[schema_id]


def resolve_trained_name(name: str) -> str:
    """Map one trained name to its live canonical name. Unresolvable raises."""
    if name in CANONICAL_FEATURES:
        return name
    alias = SCHEMA_V3_ALIASES.get(name)
    if alias is not None and alias in CANONICAL_FEATURES:
        return alias
    raise SchemaResolutionError(
        f"trained feature {name!r} is absent from the live canonical schema "
        f"(dim={CANONICAL_FEATURE_DIM}) and has no SCHEMA_V3_ALIASES target. "
        f"Remap or retrain."
    )


def resolve_declared(
    saved_schema: Sequence[str], *, schema_id: str | None = None
) -> ResolvedSchema:
    """Resolve an artifact-declared feature_schema list to live names.

    Used by artifacts that self-describe (e.g. trained GaussianNB bundles).
    Order is preserved. Unresolvable or duplicate-collapsing names raise.
    """
    if not saved_schema:
        raise SchemaResolutionError(
            "artifact declared an empty feature_schema — cannot name-align"
        )
    trained = tuple(str(n) for n in saved_schema)
    live: list[str] = []
    missing: list[str] = []
    for n in trained:
        try:
            live.append(resolve_trained_name(n))
        except SchemaResolutionError:
            missing.append(n)
    if missing:
        raise SchemaResolutionError(
            f"artifact feature_schema has name(s) absent from the live schema: "
            f"{missing}. Known aliases: {dict(SCHEMA_V3_ALIASES)}. Remap or retrain."
        )
    resolved_id = schema_id if schema_id else f"artifact_declared_{len(trained)}"
    return ResolvedSchema(
        schema_id=resolved_id,
        trained_names=trained,
        live_names=tuple(live),
        source="artifact",
    )


def identify_registered(live_names: Sequence[str]) -> str | None:
    """Return the registry schema_id whose live order matches, else None.

    Lets an artifact-declared schema be reported under a stable id when it
    happens to equal a known generation.
    """
    target = tuple(live_names)
    for sid, schema in SCHEMA_REGISTRY.items():
        if schema.live_names == target:
            return sid
    return None
