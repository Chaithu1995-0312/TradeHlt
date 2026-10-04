"""
adapters.py
===========
IAdapter implementations — consumer-facing Prediction only.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from bitnet.defaults import AD_CRT_GATE_ID, AD_IDENTITY_ID, AD_RESEARCH_ID
from bitnet.runtime_types import HeadOutputs, Prediction


class CrtGateAdapter:
    """CONTRACT-A consumer: expose confidence only (+ hierarchy ids)."""

    id_ = AD_CRT_GATE_ID

    def __init__(
        self,
        *,
        schema_version: str,
        feature_dim: int,
        feature_order_hash: str = "",
        encoder_id: str = "",
        backbone_id: str = "",
        heads_id: str = "",
    ):
        self._schema = schema_version
        self._dim = feature_dim
        self._hash = feature_order_hash
        self._enc = encoder_id
        self._bb = backbone_id
        self._hd = heads_id

    def id(self) -> str:
        return self.id_

    def adapt(
        self,
        heads: HeadOutputs,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Prediction:
        c = float(heads.confidence)
        if c != c or c < 0.0 or c > 1.0:
            # Soft clamp only for non-finite safety; legacy sigmoid is already [0,1]
            if c != c:
                raise ValueError("CrtGateAdapter: confidence is NaN")
            c = max(0.0, min(1.0, c))
        return Prediction(
            confidence=c,
            schema_version=self._schema,
            feature_dim=self._dim,
            feature_order_hash=self._hash,
            encoder_id=self._enc,
            backbone_id=self._bb,
            heads_id=self._hd,
            adapter_id=self.id_,
            heads={"confidence": c},
        )


class ResearchAdapter:
    """Expose full multi-head map."""

    id_ = AD_RESEARCH_ID

    def __init__(
        self,
        *,
        schema_version: str,
        feature_dim: int,
        feature_order_hash: str = "",
        encoder_id: str = "",
        backbone_id: str = "",
        heads_id: str = "",
    ):
        self._schema = schema_version
        self._dim = feature_dim
        self._hash = feature_order_hash
        self._enc = encoder_id
        self._bb = backbone_id
        self._hd = heads_id

    def id(self) -> str:
        return self.id_

    def adapt(
        self,
        heads: HeadOutputs,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Prediction:
        hmap: Dict[str, float] = {"confidence": float(heads.confidence)}
        if heads.win_probability is not None:
            hmap["win_probability"] = float(heads.win_probability)
        if heads.expected_rr is not None:
            hmap["expected_rr"] = float(heads.expected_rr)
        return Prediction(
            confidence=float(heads.confidence),
            schema_version=self._schema,
            feature_dim=self._dim,
            feature_order_hash=self._hash,
            encoder_id=self._enc,
            backbone_id=self._bb,
            heads_id=self._hd,
            adapter_id=self.id_,
            heads=hmap,
            embedding=list(heads.embedding) if heads.embedding is not None else None,
        )


class IdentityAdapter:
    """Harness pass-through (same as CRT gate for scalar confidence)."""

    id_ = AD_IDENTITY_ID

    def __init__(self, **kwargs: Any):
        self._inner = CrtGateAdapter(**kwargs)

    def id(self) -> str:
        return self.id_

    def adapt(
        self,
        heads: HeadOutputs,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Prediction:
        pred = self._inner.adapt(heads, context)
        # Rebuild with identity adapter id
        return Prediction(
            confidence=pred.confidence,
            schema_version=pred.schema_version,
            feature_dim=pred.feature_dim,
            feature_order_hash=pred.feature_order_hash,
            encoder_id=pred.encoder_id,
            backbone_id=pred.backbone_id,
            heads_id=pred.heads_id,
            adapter_id=self.id_,
            heads=dict(pred.heads),
            embedding=pred.embedding,
            diagnostics=dict(pred.diagnostics),
        )
