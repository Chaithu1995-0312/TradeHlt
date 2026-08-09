"""
backbones.py
============
IBackbone implementations: legacy MLP + BitLinear residual family.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from bitnet.defaults import (
    BB_BITLINEAR_RES_ID,
    BB_LEGACY_MLP_ID,
    DEFAULT_HIDDEN_DIM,
    DEFAULT_INPUT_DIM,
    DEFAULT_LATENT_DIM,
    DEFAULT_N_RESIDUAL_BLOCKS,
    DEFAULTS_PROFILE,
)
from bitnet.layers import bitlinear, clip_m1_p1, dense_linear, parse_bitlinear_layer
from bitnet.runtime_types import EncodedTensor, Latent


class LegacyMLPBackbone:
    """6→16→8 latent; matches BitNetModel.forward hidden stack (pre-output)."""

    id_ = BB_LEGACY_MLP_ID

    def __init__(self, model: Dict[str, Any]):
        self._w1 = model["layer1_w"]
        self._b1 = model["layer1_b"]
        self._w2 = model["layer2_w"]
        self._b2 = model["layer2_b"]
        # latent dim = len of layer2 output
        self._latent_dim = len(self._w2)

    def id(self) -> str:
        return self.id_

    def latent_dim(self) -> int:
        return self._latent_dim

    def forward(self, encoded: EncodedTensor) -> Latent:
        x = encoded.as_list()
        h1 = clip_m1_p1(dense_linear(x, self._w1, self._b1))
        h2 = clip_m1_p1(dense_linear(h1, self._w2, self._b2))
        return Latent(data=h2, dim=len(h2))


class BitLinearResBackbone:
    """
    Family bb_bitlinear_res_v1 (Spec L1):
      Din → H → Res×N_res @ H → L
    Numerics from envelope (L2 self-describing).
    """

    id_ = BB_BITLINEAR_RES_ID

    def __init__(
        self,
        *,
        input_dim: int,
        hidden_dim: int,
        latent_dim: int,
        n_residual_blocks: int,
        stages: Sequence[Dict[str, Any]],
        defaults_profile: str = DEFAULTS_PROFILE,
        layernorm: bool = False,
        residual: str = "post_act_add",
        activation: str = "hardtanh_m1_p1",
        quantization: str = "ternary_per_out_scale",
    ):
        if layernorm:
            raise ValueError(
                "BitLinearResBackbone: layernorm=true is out of family (L1)"
            )
        if residual != "post_act_add":
            raise ValueError(f"unsupported residual={residual!r}")
        if activation != "hardtanh_m1_p1":
            raise ValueError(f"unsupported activation={activation!r}")
        if quantization != "ternary_per_out_scale":
            raise ValueError(f"unsupported quantization={quantization!r}")
        if n_residual_blocks < 0:
            raise ValueError("n_residual_blocks must be >= 0")

        expected_stages = 1 + 2 * n_residual_blocks + 1
        if len(stages) != expected_stages:
            raise ValueError(
                f"stages length {len(stages)} != expected {expected_stages} "
                f"for N_res={n_residual_blocks}"
            )

        self.input_dim = int(input_dim)
        self.hidden_dim = int(hidden_dim)
        self._latent_dim = int(latent_dim)
        self.n_residual_blocks = int(n_residual_blocks)
        self.defaults_profile = defaults_profile
        self._stages = [parse_bitlinear_layer(dict(s)) for s in stages]

        # Shape checks against declared dims
        W0, _, _ = self._stages[0]
        if len(W0) != self.hidden_dim or (W0 and len(W0[0]) != self.input_dim):
            raise ValueError(
                f"stage0 shape {(len(W0), len(W0[0]) if W0 else 0)} "
                f"!= (H={self.hidden_dim}, Din={self.input_dim})"
            )
        Wl, _, _ = self._stages[-1]
        if len(Wl) != self._latent_dim or (Wl and len(Wl[0]) != self.hidden_dim):
            raise ValueError(
                f"latent stage shape {(len(Wl), len(Wl[0]) if Wl else 0)} "
                f"!= (L={self._latent_dim}, H={self.hidden_dim})"
            )

    @classmethod
    def from_envelope(cls, backbone: Dict[str, Any]) -> "BitLinearResBackbone":
        bid = backbone.get("id", BB_BITLINEAR_RES_ID)
        if bid != BB_BITLINEAR_RES_ID:
            raise ValueError(f"unexpected backbone id {bid!r}")
        return cls(
            input_dim=int(backbone["input_dim"]),
            hidden_dim=int(backbone["hidden_dim"]),
            latent_dim=int(backbone["latent_dim"]),
            n_residual_blocks=int(backbone["n_residual_blocks"]),
            stages=backbone["stages"],
            defaults_profile=str(
                backbone.get("defaults_profile", DEFAULTS_PROFILE)
            ),
            layernorm=bool(backbone.get("layernorm", False)),
            residual=str(backbone.get("residual", "post_act_add")),
            activation=str(backbone.get("activation", "hardtanh_m1_p1")),
            quantization=str(
                backbone.get("quantization", "ternary_per_out_scale")
            ),
        )

    def id(self) -> str:
        return self.id_

    def latent_dim(self) -> int:
        return self._latent_dim

    def forward(self, encoded: EncodedTensor) -> Latent:
        if encoded.dim != self.input_dim:
            raise ValueError(
                f"BitLinearResBackbone: expected dim {self.input_dim}, "
                f"got {encoded.dim}"
            )
        h = encoded.as_list()
        # S0 projection
        W, s, b = self._stages[0]
        h = clip_m1_p1(bitlinear(h, W, s, b))

        # Residual blocks
        idx = 1
        for _ in range(self.n_residual_blocks):
            residual_in = h
            W1, s1, b1 = self._stages[idx]
            W2, s2, b2 = self._stages[idx + 1]
            idx += 2
            u = clip_m1_p1(bitlinear(h, W1, s1, b1))
            u = clip_m1_p1(bitlinear(u, W2, s2, b2))
            h = clip_m1_p1([a + b for a, b in zip(residual_in, u)])

        # Latent projection
        Wl, sl, bl = self._stages[idx]
        z = clip_m1_p1(bitlinear(h, Wl, sl, bl))
        return Latent(data=z, dim=len(z))


def build_default_bitlinear_stages(
    *,
    input_dim: int = DEFAULT_INPUT_DIM,
    hidden_dim: int = DEFAULT_HIDDEN_DIM,
    latent_dim: int = DEFAULT_LATENT_DIM,
    n_residual_blocks: int = DEFAULT_N_RESIDUAL_BLOCKS,
    seed: int = 0,
    with_bias: bool = True,
) -> List[Dict[str, Any]]:
    """Deterministic synthetic ternary stages for tests / bootstrap."""
    import random

    rng = random.Random(seed)

    def _layer(name: str, din: int, dout: int) -> Dict[str, Any]:
        W = [[float(rng.choice((-1, 0, 1))) for _ in range(din)] for _ in range(dout)]
        scale = [0.5 + rng.random() for _ in range(dout)]
        bias = [rng.uniform(-0.1, 0.1) for _ in range(dout)] if with_bias else None
        stage: Dict[str, Any] = {
            "name": name,
            "type": "bitlinear",
            "in": din,
            "out": dout,
            "W_ternary": W,
            "scale": scale,
        }
        if bias is not None:
            stage["bias"] = bias
        return stage

    stages: List[Dict[str, Any]] = [_layer("in", input_dim, hidden_dim)]
    for i in range(n_residual_blocks):
        stages.append(_layer(f"res{i}_f0", hidden_dim, hidden_dim))
        stages.append(_layer(f"res{i}_f1", hidden_dim, hidden_dim))
    stages.append(_layer("lat", hidden_dim, latent_dim))
    return stages


def build_default_backbone_envelope(
    *,
    input_dim: int = DEFAULT_INPUT_DIM,
    hidden_dim: int = DEFAULT_HIDDEN_DIM,
    latent_dim: int = DEFAULT_LATENT_DIM,
    n_residual_blocks: int = DEFAULT_N_RESIDUAL_BLOCKS,
    seed: int = 0,
) -> Dict[str, Any]:
    return {
        "id": BB_BITLINEAR_RES_ID,
        "defaults_profile": DEFAULTS_PROFILE,
        "input_dim": input_dim,
        "hidden_dim": hidden_dim,
        "latent_dim": latent_dim,
        "n_residual_blocks": n_residual_blocks,
        "activation": "hardtanh_m1_p1",
        "residual": "post_act_add",
        "layernorm": False,
        "quantization": "ternary_per_out_scale",
        "bias": True,
        "stages": build_default_bitlinear_stages(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            latent_dim=latent_dim,
            n_residual_blocks=n_residual_blocks,
            seed=seed,
        ),
    }
