"""
heads.py
========
IHeads implementations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from bitnet.defaults import HD_CONFIDENCE_ID, HD_MULTI_ID
from bitnet.layers import dense_linear, sigmoid
from bitnet.runtime_types import HeadOutputs, Latent


class ConfidenceSigmoidHead:
    """Linear(L→1) + sigmoid. Used by CONTRACT-A legacy out layer."""

    id_ = HD_CONFIDENCE_ID

    def __init__(
        self,
        weight: Sequence[Sequence[float]],
        bias: Sequence[float],
    ):
        # weight (1, L)
        if len(weight) != 1:
            raise ValueError("ConfidenceSigmoidHead expects weight shape (1, L)")
        self._w = weight
        self._b = bias
        self._in = len(weight[0]) if weight else 0

    @classmethod
    def from_legacy_out(cls, model: Dict[str, Any]) -> "ConfidenceSigmoidHead":
        return cls(model["out_w"], model["out_b"])

    @classmethod
    def from_envelope(cls, head: Dict[str, Any], *, latent_dim: int) -> "ConfidenceSigmoidHead":
        w = head["weight"]
        b = head["bias"]
        if len(w[0]) != latent_dim:
            raise ValueError(
                f"confidence head in_features {len(w[0])} != latent_dim {latent_dim}"
            )
        return cls(w, b)

    def id(self) -> str:
        return self.id_

    def head_names(self) -> List[str]:
        return ["confidence"]

    def forward(self, latent: Latent) -> HeadOutputs:
        if latent.dim != self._in:
            raise ValueError(
                f"ConfidenceSigmoidHead: expected latent {self._in}, got {latent.dim}"
            )
        logit = dense_linear(latent.as_list(), self._w, self._b)[0]
        return HeadOutputs(confidence=sigmoid(logit))


class MultiHead:
    """CONTRACT-B multi-head: confidence (+ optional win / rr / embedding)."""

    id_ = HD_MULTI_ID

    def __init__(
        self,
        *,
        confidence: ConfidenceSigmoidHead,
        win_weight: Optional[Sequence[Sequence[float]]] = None,
        win_bias: Optional[Sequence[float]] = None,
        rr_weight: Optional[Sequence[Sequence[float]]] = None,
        rr_bias: Optional[Sequence[float]] = None,
        emb_weight: Optional[Sequence[Sequence[float]]] = None,
        emb_bias: Optional[Sequence[float]] = None,
    ):
        self._conf = confidence
        self._win_w = win_weight
        self._win_b = win_bias
        self._rr_w = rr_weight
        self._rr_b = rr_bias
        self._emb_w = emb_weight
        self._emb_b = emb_bias

    @classmethod
    def from_envelope(cls, heads: Dict[str, Any], *, latent_dim: int) -> "MultiHead":
        conf = ConfidenceSigmoidHead.from_envelope(heads["confidence"], latent_dim=latent_dim)
        win_w = win_b = rr_w = rr_b = emb_w = emb_b = None
        if "win_probability" in heads:
            win_w = heads["win_probability"]["weight"]
            win_b = heads["win_probability"]["bias"]
        if "expected_rr" in heads:
            rr_w = heads["expected_rr"]["weight"]
            rr_b = heads["expected_rr"]["bias"]
        if "embedding" in heads:
            emb_w = heads["embedding"]["weight"]
            emb_b = heads["embedding"].get("bias")
        return cls(
            confidence=conf,
            win_weight=win_w,
            win_bias=win_b,
            rr_weight=rr_w,
            rr_bias=rr_b,
            emb_weight=emb_w,
            emb_bias=emb_b,
        )

    def id(self) -> str:
        return self.id_

    def head_names(self) -> List[str]:
        names = ["confidence"]
        if self._win_w is not None:
            names.append("win_probability")
        if self._rr_w is not None:
            names.append("expected_rr")
        if self._emb_w is not None:
            names.append("embedding")
        return names

    def forward(self, latent: Latent) -> HeadOutputs:
        base = self._conf.forward(latent)
        win = rr = None
        emb = None
        x = latent.as_list()
        if self._win_w is not None:
            win = sigmoid(dense_linear(x, self._win_w, self._win_b)[0])
        if self._rr_w is not None:
            rr = dense_linear(x, self._rr_w, self._rr_b)[0]
        if self._emb_w is not None:
            emb = dense_linear(x, self._emb_w, self._emb_b)
        return HeadOutputs(
            confidence=base.confidence,
            win_probability=win,
            expected_rr=rr,
            embedding=emb,
        )


def random_linear_head(latent_dim: int, out_dim: int = 1, seed: int = 1) -> Dict[str, Any]:
    import random

    rng = random.Random(seed)
    w = [[rng.uniform(-0.1, 0.1) for _ in range(latent_dim)] for _ in range(out_dim)]
    b = [0.0 for _ in range(out_dim)]
    return {"weight": w, "bias": b}
