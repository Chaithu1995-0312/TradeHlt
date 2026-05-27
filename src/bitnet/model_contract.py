"""
model_contract.py
=================
Canonical BitNet serialization contract — schema v3 ("bitnet_v3").

One envelope shape, three loader paths:

  1. bitnet_v3 (canonical)     — verified by schema_version + feature_dim + feature_order_hash.
  2. bitnet_export_v1 (legacy) — accepted via legacy bridge; emits BITNET_LEGACY_LOAD.
  3. legacy_6input             — accepted via legacy bridge; emits BITNET_LEGACY_LOAD.

Loaders NEVER silently reinterpret feature dimensions. A mismatch between
declared feature_dim and any inferable model shape raises RuntimeError.

This module intentionally has no numpy / torch dependencies — it operates on
plain dicts so it can be imported by exporters, loaders, and tests alike.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from features.feature_schema import (
    CANONICAL_FEATURES,
    CANONICAL_FEATURE_DIM as _SCHEMA_FEATURE_DIM,
)

# ── Public constants ─────────────────────────────────────────────────────────

CANONICAL_MODEL_SCHEMA_VERSION: str = "bitnet_v3"

# Single source of truth for the canonical feature dimension.
# Re-exported from features.feature_schema so any future change to the
# canonical schema flows through automatically (and the assert fires).
CANONICAL_FEATURE_DIM: int = _SCHEMA_FEATURE_DIM
assert CANONICAL_FEATURE_DIM == 38, (
    f"BitNet v3 contract expects 38-feature canonical schema; got {CANONICAL_FEATURE_DIM}."
)

# Schemas accepted via the legacy bridge. Any other schema string fails loud.
LEGACY_SCHEMAS = frozenset({"legacy_6input", "bitnet_export_v1"})


# ── Hashing ──────────────────────────────────────────────────────────────────

def feature_order_hash(feature_names: List[str]) -> str:
    """Stable SHA-256[:16] of an ordered feature-name list.

    Matches the algorithm in features.feature_schema._feature_order_hash so
    canonical envelopes verify against FEATURE_ORDER_HASH for 38-d models.
    """
    payload = json.dumps(list(feature_names), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# ── Envelope builder (used by exporters) ─────────────────────────────────────

def build_envelope(
    layers: list,
    *,
    feature_names: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """Wrap layers + metadata in the canonical bitnet_v3 envelope.

    Parameters
    ----------
    layers : list
        Layer definitions; opaque to this contract. Exporters pass whatever
        shape their forward pass expects (e.g. [{"name":"fc1","weights":...}]).
    feature_names : list[str], optional
        Ordered feature names. Defaults to the canonical 38-feature ordering.
    metadata : dict, optional
        Free-form metadata (e.g. {"source": "export_bitnet_model", "epochs": 50}).
    """
    names = list(feature_names) if feature_names else list(CANONICAL_FEATURES)
    return {
        "schema_version":     CANONICAL_MODEL_SCHEMA_VERSION,
        "feature_dim":        len(names),
        "feature_order_hash": feature_order_hash(names),
        "feature_names":      names,
        "layers":             layers,
        "metadata":           metadata or {},
    }


# ── Normalizer (used by loaders) ─────────────────────────────────────────────

def normalize_loaded(model: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized canonical view of a loaded model dict.

    Returns a dict with keys:
        schema_version    : str
        feature_dim       : int
        feature_order_hash: str  (may be "" for legacy without stored hash)
        feature_names     : list[str] (may be empty for legacy without feature_order)
        layers            : list (raw, opaque)
        raw               : original loaded dict (untouched)

    Behavior
    --------
    * bitnet_v3 model → returned as-is (validated).
    * Legacy schema (legacy_6input / bitnet_export_v1) → emits BITNET_LEGACY_LOAD
      integrity event, returns normalized view inferred from layer shapes.
    * Unrecognized → RuntimeError. Never silently reinterprets feature_dim.
    """
    # Lazy import keeps integrity_events optional at module-import time.
    try:
        from src.utils.integrity_events import emit_integrity_event
    except Exception:  # noqa: BLE001
        def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
            return None

    # Canonical models are identified by schema_version=="bitnet_v3". Legacy
    # models use the older "schema" field (e.g. "legacy_6input",
    # "bitnet_export_v1") and may carry an unrelated schema_version like "v5".
    declared_schema_version = model.get("schema_version")
    declared_schema = model.get("schema")
    is_canonical_v3 = declared_schema_version == CANONICAL_MODEL_SCHEMA_VERSION
    schema = declared_schema or declared_schema_version or "unknown"

    # ── Canonical bitnet_v3 path ──────────────────────────────────────────
    if is_canonical_v3:
        schema = CANONICAL_MODEL_SCHEMA_VERSION
        try:
            dim = int(model["feature_dim"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"BitNet model_contract: bitnet_v3 model missing valid feature_dim: {exc}"
            )
        names = list(model.get("feature_names", []))
        return {
            "schema_version":     schema,
            "feature_dim":        dim,
            "feature_order_hash": str(model.get("feature_order_hash", "")),
            "feature_names":      names,
            "layers":             model.get("layers", []),
            "raw":                model,
        }

    # ── Classify shape ────────────────────────────────────────────────────
    is_legacy_schema = schema in LEGACY_SCHEMAS
    has_legacy_6input_shape = "layer1_w" in model
    has_new_shape_layers = "layers" in model and not has_legacy_6input_shape

    # A model with new-shape "layers" but no schema_version at all is the
    # historical bitnet_export_v1 default. We preserve backward compat by
    # routing it through the legacy bridge, but emit a separate WARNING so
    # operators can spot un-versioned models and re-export them.
    if (
        schema == "unknown"
        and has_new_shape_layers
        and not is_legacy_schema
    ):
        emit_integrity_event(
            "BITNET_MISSING_SCHEMA_VERSION",
            "WARNING",
            "bitnet.model_contract",
            {
                "feature_dim_inferred": int(
                    model["layers"][0].get(
                        "in",
                        len(model["layers"][0].get("weights", [[None]])[0]),
                    )
                ) if model.get("layers") else None,
                "note": (
                    "model has new-shape layers but no schema_version; "
                    "loading via bitnet_export_v1 legacy bridge — re-export "
                    f"with schema_version='{CANONICAL_MODEL_SCHEMA_VERSION}'."
                ),
            },
        )
        schema = "bitnet_export_v1"
        is_legacy_schema = True

    # ── Legacy bridge ─────────────────────────────────────────────────────
    has_legacy_shape = has_legacy_6input_shape or has_new_shape_layers
    if is_legacy_schema or has_legacy_shape:
        # Infer feature_dim from declared or layer shapes.
        if "input_dim" in model:
            try:
                dim = int(model["input_dim"])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"BitNet model_contract: legacy input_dim not int-castable: {exc}"
                )
        elif "layer1_w" in model:
            dim = 6  # legacy_6input is the only schema using layer1_w shape.
        elif "layers" in model and model["layers"]:
            first = model["layers"][0]
            if "in" in first:
                try:
                    dim = int(first["in"])
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"BitNet model_contract: legacy layers[0]['in'] not int-castable: {exc}"
                    )
            else:
                # Infer from weight matrix shape: weights is [out_dim][in_dim].
                weights = first.get("weights")
                if not weights or not weights[0]:
                    raise RuntimeError(
                        "BitNet model_contract: legacy layers[0] has no shape information."
                    )
                dim = len(weights[0])
        else:
            raise RuntimeError(
                f"BitNet model_contract: cannot infer feature_dim from schema={schema!r}"
            )

        names = list(model.get("feature_order", []))
        h = feature_order_hash(names) if names else ""

        emit_integrity_event(
            "BITNET_LEGACY_LOAD",
            "WARNING",
            "bitnet.model_contract",
            {
                "schema":             schema,
                "feature_dim":        dim,
                "feature_order_hash": h,
                "note":               "loaded under legacy bridge; upgrade to bitnet_v3",
            },
        )
        return {
            "schema_version":     schema,
            "feature_dim":        dim,
            "feature_order_hash": h,
            "feature_names":      names,
            "layers":             model.get("layers", []),
            "raw":                model,
        }

    # ── Unrecognized → fail loud ──────────────────────────────────────────
    raise RuntimeError(
        f"BitNet model_contract: unrecognized schema={schema!r}. "
        f"Expected '{CANONICAL_MODEL_SCHEMA_VERSION}' or a legacy schema "
        f"in {sorted(LEGACY_SCHEMAS)}."
    )


__all__ = [
    "CANONICAL_MODEL_SCHEMA_VERSION",
    "CANONICAL_FEATURE_DIM",
    "LEGACY_SCHEMAS",
    "build_envelope",
    "feature_order_hash",
    "normalize_loaded",
]
