"""
layers.py
=========
Pure numeric primitives for BitNet runtime (no I/O).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple


def clip_m1_p1(xs: Sequence[float]) -> List[float]:
    return [max(-1.0, min(1.0, float(v))) for v in xs]


def sigmoid(x: float) -> float:
    # Stable-ish scalar sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def dense_linear(
    x: Sequence[float],
    weight: Sequence[Sequence[float]],
    bias: Sequence[float] | None,
) -> List[float]:
    """weight shape (out, in); x length in."""
    out: List[float] = []
    for i, row in enumerate(weight):
        acc = sum(float(xi) * float(wi) for xi, wi in zip(x, row))
        if bias is not None:
            acc += float(bias[i])
        out.append(acc)
    return out


def bitlinear(
    x: Sequence[float],
    w_ternary: Sequence[Sequence[float]],
    scale: Sequence[float],
    bias: Sequence[float] | None,
) -> List[float]:
    """
    y = (W_ternary @ x) * scale + bias
    W entries should be in {-1, 0, +1} (float-encoded).
    """
    raw = dense_linear(x, w_ternary, bias=None)
    out: List[float] = []
    for i, z in enumerate(raw):
        y = z * float(scale[i])
        if bias is not None:
            y += float(bias[i])
        out.append(y)
    return out


def validate_ternary(w: Sequence[Sequence[float]], *, name: str = "W") -> None:
    allowed = {-1.0, 0.0, 1.0}
    for i, row in enumerate(w):
        for j, v in enumerate(row):
            fv = float(v)
            if fv not in allowed:
                # tolerate tiny float noise from JSON
                if abs(fv) < 1e-6:
                    continue
                if abs(fv - 1.0) < 1e-6 or abs(fv + 1.0) < 1e-6:
                    continue
                raise ValueError(
                    f"{name}[{i}][{j}]={fv} not ternary {{-1,0,+1}}"
                )


def parse_bitlinear_layer(layer: dict) -> Tuple[List[List[float]], List[float], List[float] | None]:
    """Extract W (out,in), scale (out,), optional bias from envelope stage dict."""
    if "W_ternary" in layer:
        W = layer["W_ternary"]
    elif "weights" in layer:
        # Allow binary {0,1} export style → map to ternary
        raw = layer["weights"]
        W = [[2.0 * float(v) - 1.0 for v in row] for row in raw]
    else:
        raise ValueError("bitlinear layer missing W_ternary/weights")
    scale = [float(s) for s in layer["scale"]]
    bias = None
    if layer.get("bias") is not None:
        bias = [float(b) for b in layer["bias"]]
    out_dim = len(W)
    in_dim = len(W[0]) if W else 0
    if "out" in layer and int(layer["out"]) != out_dim:
        raise ValueError(
            f"layer out={layer['out']} != weight rows {out_dim}"
        )
    if "in" in layer and int(layer["in"]) != in_dim:
        raise ValueError(
            f"layer in={layer['in']} != weight cols {in_dim}"
        )
    if len(scale) != out_dim:
        raise ValueError(f"scale len {len(scale)} != out {out_dim}")
    if bias is not None and len(bias) != out_dim:
        raise ValueError(f"bias len {len(bias)} != out {out_dim}")
    validate_ternary(W, name=str(layer.get("name", "W")))
    return W, scale, bias
