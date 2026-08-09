"""
gaussian_schema_contract.py
===========================
Gaussian NB feature-schema contract under SCHEMA-V4-VECTOR-MIGRATION (P0).

Problem
-------
Trained Gaussian checkpoints store a v2/v3 ``feature_schema`` name list
(``macd_hist``, ``wick_size``, dim 35/38). Live runtime is schema v4.0 (39-dim:
``macd_hist_raw``/``macd_hist_z``, ``candle_range``).

Two failure modes must not coexist:
  * FAIL_OPEN  — silent index truncation of a longer live vector (mis-score)
  * FAIL_CLOSED without a remap path — refuse forever even when names only renamed

Contract
--------
1. Every trained name must resolve to a live canonical name (exact or via
   ``SCHEMA_V3_ALIASES``). Unresolvable names → ``GaussianSchemaError`` at load.
2. Inference vectors are built **by name in trained order**, never by truncating
   the ambient 39-dim vector.
3. ``len(vector)`` must equal ``model.n_features`` exactly.

Authority
---------
Alignment only (CLAUDE.md §6.5). Grants no re-enable of ``gaussian_impl=ml``
and no economic authority. Live spine default remains heuristic (F-060).
"""
from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence

from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURE_ORDER,
    SCHEMA_V3_ALIASES,
)


class GaussianSchemaError(ValueError):
    """Trained Gaussian feature contract cannot be aligned to the live schema."""


def resolve_trained_feature_name(name: str) -> str:
    """Map one trained feature name to the live canonical name.

    Raises
    ------
    GaussianSchemaError
        If the name is neither live nor a known v3 alias.
    """
    live = set(CANONICAL_FEATURE_ORDER)
    if name in live:
        return name
    alias = SCHEMA_V3_ALIASES.get(name)
    if alias is not None and alias in live:
        return alias
    raise GaussianSchemaError(
        f"Gaussian feature '{name}' is absent from live schema v4 "
        f"(CANONICAL_FEATURE_DIM={CANONICAL_FEATURE_DIM}) and has no "
        f"SCHEMA_V3_ALIASES target. Remap or retrain."
    )


def resolve_trained_feature_schema(saved_schema: Sequence[str]) -> List[str]:
    """Resolve a full trained feature_schema list to live names (order preserved).

    Raises
    ------
    GaussianSchemaError
        On empty schema, unresolvable names, or duplicate resolved names
        (would collapse distinct trained dims).
    """
    if not saved_schema:
        raise GaussianSchemaError(
            "Gaussian model bundle has empty feature_schema — cannot name-align."
        )
    resolved: List[str] = []
    missing: List[str] = []
    for raw in saved_schema:
        try:
            resolved.append(resolve_trained_feature_name(str(raw)))
        except GaussianSchemaError:
            missing.append(str(raw))
    if missing:
        raise GaussianSchemaError(
            f"Gaussian feature_schema has name(s) absent from live schema: {missing}. "
            f"Known aliases: {dict(SCHEMA_V3_ALIASES)}. Remap or retrain."
        )
    # Collapse detection: two trained names must not map to the same live slot
    # (would silently drop a dimension of the model).
    if len(set(resolved)) != len(resolved):
        raise GaussianSchemaError(
            f"Gaussian feature_schema resolves to duplicate live names "
            f"(trained dims would collapse): {resolved}"
        )
    return resolved


def assert_model_schema_compatible(
    saved_schema: Sequence[str],
    *,
    model_n_features: int,
) -> List[str]:
    """Load-time gate: resolved schema must match model width.

    Returns the resolved live-name order for name-anchored extraction.
    """
    resolved = resolve_trained_feature_schema(saved_schema)
    if len(resolved) != int(model_n_features):
        raise GaussianSchemaError(
            f"Gaussian resolved feature_schema length {len(resolved)} != "
            f"model.n_features {model_n_features}."
        )
    return resolved


def extract_model_feature_vector(
    features: Mapping[str, object],
    trained_order: Sequence[str],
) -> List[float]:
    """Build the model input vector in **trained name order** from a feature dict.

    ``trained_order`` must already be **resolved** live names (see
    ``resolve_trained_feature_schema``). Missing keys raise — never zero-fill.
    """
    if not trained_order:
        raise GaussianSchemaError("trained_order is empty — refusing extract")
    try:
        return [float(features[name]) for name in trained_order]
    except KeyError as exc:
        raise GaussianSchemaError(
            f"Live feature dict missing '{exc.args[0]}' required by the Gaussian "
            f"model's trained order. Pipeline must emit all resolved names."
        ) from exc
    except (TypeError, ValueError) as exc:
        raise GaussianSchemaError(
            f"Gaussian feature coercion failed: {exc}"
        ) from exc


def schema_alignment_report(
    saved_schema: Iterable[str],
) -> dict:
    """Diagnostic report for validation harnesses (never throws on soft fields)."""
    saved = list(saved_schema)
    live = list(CANONICAL_FEATURE_ORDER)
    resolved: List[str] = []
    missing: List[str] = []
    renames: dict = {}
    for n in saved:
        try:
            r = resolve_trained_feature_name(n)
            resolved.append(r)
            if r != n:
                renames[n] = r
        except GaussianSchemaError:
            missing.append(n)
    return {
        "saved_dim": len(saved),
        "live_dim": len(live),
        "resolved_dim": len(resolved),
        "missing": missing,
        "renames": renames,
        "resolved_order": resolved,
        "alignable": missing == [] and len(set(resolved)) == len(resolved),
        "is_full_live": resolved == live,
        "is_strict_subset": (
            missing == []
            and len(resolved) < len(live)
            and set(resolved) <= set(live)
        ),
    }
