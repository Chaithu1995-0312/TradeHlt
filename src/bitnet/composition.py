"""
composition.py
==============
IBitNetModel composition root: Encoder → Backbone → Heads → Adapter.

Spec v1.2.1. Pure inference after load. Does not enable CRT use_bitnet.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

from bitnet.adapters import CrtGateAdapter, ResearchAdapter
from bitnet.backbones import (
    BitLinearResBackbone,
    LegacyMLPBackbone,
    build_default_backbone_envelope,
)
from bitnet.defaults import (
    AD_CRT_GATE_ID,
    BB_BITLINEAR_RES_ID,
    BB_LEGACY_MLP_ID,
    DEFAULTS_PROFILE,
    ENC_CANONICAL38_ID,
    ENC_LEGACY6_ID,
    HD_CONFIDENCE_ID,
    HD_MULTI_ID,
    LEGACY6_KEYS,
)
from bitnet.encoders import (
    Canonical38Encoder,
    Legacy6Encoder,
    apply_crt_serve_aliases,
)
from bitnet.heads import ConfidenceSigmoidHead, MultiHead, random_linear_head
from bitnet.runtime_types import ModelMetadata, Prediction


@runtime_checkable
class SupportsEncode(Protocol):
    def id(self) -> str: ...
    def dim(self) -> int: ...
    def feature_order_hash(self) -> str: ...
    def encode(self, features: Mapping[str, object]): ...


@runtime_checkable
class SupportsBackbone(Protocol):
    def id(self) -> str: ...
    def latent_dim(self) -> int: ...
    def forward(self, encoded): ...


@runtime_checkable
class SupportsHeads(Protocol):
    def id(self) -> str: ...
    def forward(self, latent): ...


@runtime_checkable
class SupportsAdapter(Protocol):
    def id(self) -> str: ...
    def adapt(self, heads, context=None) -> Prediction: ...


class BitNetComposition:
    """Composition root implementing load/predict/metadata contract."""

    def __init__(
        self,
        encoder: SupportsEncode,
        backbone: SupportsBackbone,
        heads: SupportsHeads,
        adapter: SupportsAdapter,
        *,
        metadata: ModelMetadata,
        apply_crt_aliases: bool = False,
    ):
        self._encoder = encoder
        self._backbone = backbone
        self._heads = heads
        self._adapter = adapter
        self._metadata = metadata
        self._apply_crt_aliases = apply_crt_aliases

    def encoder(self) -> SupportsEncode:
        return self._encoder

    def backbone(self) -> SupportsBackbone:
        return self._backbone

    def heads(self) -> SupportsHeads:
        return self._heads

    def adapter(self) -> SupportsAdapter:
        return self._adapter

    def metadata(self) -> ModelMetadata:
        return self._metadata

    def predict(self, features: Mapping[str, object]) -> Prediction:
        feats: Mapping[str, object] = features
        if self._apply_crt_aliases:
            feats = apply_crt_serve_aliases(features)
        encoded = self._encoder.encode(feats)
        latent = self._backbone.forward(encoded)
        head_out = self._heads.forward(latent)
        return self._adapter.adapt(head_out, context=dict(feats))


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_legacy_composition(model_path: str = "model.json") -> BitNetComposition:
    """
    CONTRACT-A recipe:
      enc_legacy6_v1 + bb_legacy_mlp_6_16_8_v1
      + hd_confidence_sigmoid_v1 + ad_crt_gate_v1

    Forward math matches BitNetModel.forward (dense float legacy).
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"load_legacy_composition: model file not found: {model_path!r}"
        )
    with open(model_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    encoder = Legacy6Encoder()
    backbone = LegacyMLPBackbone(model)
    heads = ConfidenceSigmoidHead.from_legacy_out(model)
    adapter = CrtGateAdapter(
        schema_version=str(model.get("schema") or model.get("schema_version") or "legacy_6input"),
        feature_dim=encoder.dim(),
        feature_order_hash="",
        encoder_id=encoder.id(),
        backbone_id=backbone.id(),
        heads_id=heads.id(),
    )
    names = list(model.get("feature_order") or LEGACY6_KEYS)
    meta = ModelMetadata(
        schema_version=str(model.get("schema") or "legacy_6input"),
        feature_dim=len(names),
        feature_names=names,
        feature_order_hash="",
        encoder_id=ENC_LEGACY6_ID,
        backbone_id=BB_LEGACY_MLP_ID,
        heads_id=HD_CONFIDENCE_ID,
        adapter_id=AD_CRT_GATE_ID,
        defaults_profile="",
        artifact_sha256=_sha256_file(model_path),
        raw={"model_path": model_path},
    )
    return BitNetComposition(
        encoder,
        backbone,
        heads,
        adapter,
        metadata=meta,
        apply_crt_aliases=True,
    )


def load_bitlinear_composition(envelope: Dict[str, Any]) -> BitNetComposition:
    """
    CONTRACT-B family recipe from a self-describing envelope.

    Expected keys:
      backbone: { id, input_dim, hidden_dim, latent_dim, n_residual_blocks, stages, ... }
      heads: { confidence: {weight, bias}, optional win/rr/embedding }
      optional encoder: { feature_names, mean, std, feature_order_hash }
      schema_version, metadata...
    """
    bb_sec = envelope["backbone"]
    backbone = BitLinearResBackbone.from_envelope(bb_sec)
    latent_dim = backbone.latent_dim()

    heads_sec = envelope.get("heads") or {
        "confidence": random_linear_head(latent_dim, seed=0),
    }
    if "win_probability" in heads_sec or "expected_rr" in heads_sec or "embedding" in heads_sec:
        heads: Any = MultiHead.from_envelope(heads_sec, latent_dim=latent_dim)
        heads_id = HD_MULTI_ID
        adapter_cls = ResearchAdapter
    else:
        heads = ConfidenceSigmoidHead.from_envelope(
            heads_sec["confidence"], latent_dim=latent_dim
        )
        heads_id = HD_CONFIDENCE_ID
        adapter_cls = CrtGateAdapter

    enc_sec = envelope.get("encoder") or {}
    feature_names = enc_sec.get("feature_names")
    encoder = Canonical38Encoder(
        feature_names=feature_names,
        mean=enc_sec.get("mean"),
        std=enc_sec.get("std"),
        feature_order_hash=str(enc_sec.get("feature_order_hash") or ""),
    )
    if encoder.dim() != backbone.input_dim:
        raise ValueError(
            f"encoder dim {encoder.dim()} != backbone input_dim {backbone.input_dim}"
        )

    schema = str(envelope.get("schema_version") or "bitnet_cpp_v1")
    adapter = adapter_cls(
        schema_version=schema,
        feature_dim=encoder.dim(),
        feature_order_hash=encoder.feature_order_hash(),
        encoder_id=encoder.id(),
        backbone_id=backbone.id(),
        heads_id=heads.id(),
    )
    meta = ModelMetadata(
        schema_version=schema,
        feature_dim=encoder.dim(),
        feature_names=[fi.name for fi in encoder.identities()],
        feature_order_hash=encoder.feature_order_hash(),
        encoder_id=ENC_CANONICAL38_ID,
        backbone_id=BB_BITLINEAR_RES_ID,
        heads_id=heads_id,
        adapter_id=adapter.id(),
        defaults_profile=str(bb_sec.get("defaults_profile") or DEFAULTS_PROFILE),
        label_contract_id=str(
            (envelope.get("metadata") or {}).get("label_contract_id") or ""
        ),
        economic_authority=str(
            (envelope.get("metadata") or {}).get("economic_authority") or ""
        ),
        raw=envelope,
    )
    return BitNetComposition(
        encoder,
        backbone,
        heads,
        adapter,
        metadata=meta,
        apply_crt_aliases=False,
    )


def build_synthetic_bitlinear_envelope(
    *,
    input_dim: int = 38,
    hidden_dim: int = 64,
    latent_dim: int = 32,
    n_residual_blocks: int = 2,
    seed: int = 0,
    multi_head: bool = False,
    feature_names: Optional[list] = None,
) -> Dict[str, Any]:
    """Test/bootstrap envelope with defaults profile numerics (or custom L2 dims)."""
    bb = build_default_backbone_envelope(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        latent_dim=latent_dim,
        n_residual_blocks=n_residual_blocks,
        seed=seed,
    )
    heads: Dict[str, Any] = {
        "confidence": random_linear_head(latent_dim, seed=seed + 1),
    }
    if multi_head:
        heads["win_probability"] = random_linear_head(latent_dim, seed=seed + 2)
        heads["expected_rr"] = random_linear_head(latent_dim, seed=seed + 3)
    names = feature_names
    if names is None:
        try:
            from features.feature_schema import CANONICAL_FEATURES

            names = list(CANONICAL_FEATURES)
        except Exception:
            names = [f"f{i}" for i in range(input_dim)]
    if len(names) != input_dim:
        names = [f"f{i}" for i in range(input_dim)]
    return {
        "schema_version": "bitnet_cpp_v1",
        "backbone": bb,
        "heads": heads,
        "encoder": {"feature_names": names, "feature_order_hash": ""},
        "metadata": {
            "label_contract_id": "BITNET_LABEL_SYNTHETIC_V0",
            "economic_authority": "DIAGNOSTIC_ONLY",
        },
    }


# ---------------------------------------------------------------------------
# Default CRT façade composition (lazy)
# ---------------------------------------------------------------------------

_default_composition: Optional[BitNetComposition] = None
_default_composition_path: Optional[str] = None


def _resolve_default_model_path(explicit: Optional[str] = None) -> str:
    """Prefer explicit path; else BitNet registry composition_default / selection."""
    if explicit is not None and explicit != "model.json":
        return explicit
    try:
        from bitnet.bitnet_registry import resolve_composition_model_path
        return resolve_composition_model_path()
    except Exception as exc:
        # Registry absent or unreadable: keep historical default (model.json)
        logger = __import__("logging").getLogger(__name__)
        logger.debug(
            "get_default_composition: registry resolve failed (%s); using %r",
            exc, explicit or "model.json",
        )
        return explicit or "model.json"


def get_default_composition(model_path: str = "model.json") -> BitNetComposition:
    """Lazy CRT façade composition.

    Path resolution (P1 BitNet registry governance 2026-07-22):
      1. Explicit non-default ``model_path`` argument wins.
      2. Else ``models/bitnet/bitnet_registry.json`` composition_default / selection.
      3. Else historical ``model.json``.
    """
    global _default_composition, _default_composition_path
    resolved = _resolve_default_model_path(model_path)
    if _default_composition is None or _default_composition_path != resolved:
        _default_composition = load_legacy_composition(resolved)
        _default_composition_path = resolved
    return _default_composition


def reset_default_composition() -> None:
    """Test helper — drop cached composition."""
    global _default_composition, _default_composition_path
    _default_composition = None
    _default_composition_path = None
