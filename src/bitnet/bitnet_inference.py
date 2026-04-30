"""
bitnet_inference.py
===================
BitNet inference layer supporting two JSON model schemas.

Schema 1 — legacy (model.json):
    {
      "layer1_w": [[...]], "layer1_b": [...],
      "layer2_w": [[...]], "layer2_b": [...],
      "out_w":    [[...]], "out_b":    [...]
    }
    Used by the existing global `bitnet` instance and `bitnet_score()`.

Schema 2 — export (e.g. exported_model.json / model_export_format.json):
    {
      "layers": [
        {"name": "fc1", "weights": [[0,1,...]], "scale": [...]},
        {"name": "fc2", "weights": [[0,1,...]], "scale": [...]},
        {"name": "fc3", "weights": [[0,1,...]], "scale": [...]}
      ]
    }
    Used by the new `BitNetModel.predict(vector)` for 24-length BitNet vectors.

Self-Review
-----------
Assumptions:
    - Model is a shallow feed-forward network (≤ 10 layers).
    - Export schema: `scale` shape equals output_dim of that layer.
    - Binary weights are 0/1 integers; ternary mapping: 0→-1, 1→+1.

Edge Cases:
    - NaN input: caught before inference by explicit assertion in predict().
    - Model file missing: FileNotFoundError raised in __init__.
    - Wrong weight dimensions: numpy matmul raises ValueError immediately.
    - Extreme z values: tanh on final layer clamps output to (-1, 1).

Failure Modes:
    - Misaligned feature order: predict() trusts the caller's FEATURE_ORDER.
    - scale shape mismatch: numpy broadcast raises ValueError (fail-fast).

Risks:
    - Signal threshold 0.5 is hardcoded per spec; expose via config for tuning.
    - Inference latency for 24→N→M→1 network is microseconds (no concern).

Integration Notes:
    - For C++ port: binary weights are already 0/1 int arrays, trivially
      serializable to bitpacked C++ arrays. Scale vectors are float32.
"""

import json
import math
import os

import numpy as np


class BitNetModel:
    """
    Two-schema BitNet model loader.

    Parameters
    ----------
    model_path : str
        Path to JSON model file. Schema is auto-detected.
    """

    def __init__(self, model_path: str = "model.json"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"BitNetModel: model file not found: '{model_path}'"
            )
        with open(model_path, "r") as f:
            self.model = json.load(f)

        # Auto-detect schema
        self.is_v4 = self.model.get("schema") == "bitnet_export_v1"
        # Also treat any model with 'layers' (and no legacy 'layer1_w') as export schema
        self._export_schema = self.is_v4 or (
            "layers" in self.model and "layer1_w" not in self.model
        )

        if self.is_v4:
            self.input_dim = self.model["input_dim"]
        elif self._export_schema:
            first_layer = self.model["layers"][0]
            # Prefer explicit "in" key; fall back to inferring from weights shape
            if "in" in first_layer:
                self.input_dim = first_layer["in"]
            else:
                self.input_dim = len(first_layer["weights"][0])
        else:
            # Legacy model.json schema — input dim is fixed at 6
            self.input_dim = 6

    # ------------------------------------------------------------------
    # PUBLIC API — 24-vector inference (export schema)
    # ------------------------------------------------------------------

    def predict(self, x: np.ndarray) -> float:
        """
        Forward pass for a single 24-length feature vector.

        Parameters
        ----------
        x : np.ndarray, shape (24,), dtype float32
            BitNet feature vector produced by FeaturePipeline.

        Returns
        -------
        float
            Score in (-1, 1).  Interpretation:
                score >  0.5  → bullish signal
                score < -0.5  → bearish signal
                otherwise     → neutral

        Raises
        ------
        ValueError
            If x has wrong shape or contains NaN.
        """
        x = np.asarray(x, dtype=np.float32)

        # ── Assertion 1: shape ────────────────────────────────────────
        if x.shape != (self.input_dim,):
            raise ValueError(
                f"BitNetModel.predict: expected shape ({self.input_dim},), got {x.shape}"
            )

        # ── Assertion 2: no NaN ───────────────────────────────────────
        if np.isnan(x).any():
            raise ValueError(
                "BitNetModel.predict: input vector contains NaN — "
                "ensure FeaturePipeline.finalize() has been called."
            )

        if self._export_schema:
            return self._forward_export(x)
        else:
            # Legacy schema fallback — map 24-vector through old API
            return float(self.forward(x.tolist()))

    # ------------------------------------------------------------------
    # FORWARD PASS — export schema (binary weights + scale)
    # ------------------------------------------------------------------

    def _forward_export(self, x: np.ndarray) -> float:
        """
        Forward pass for model_export_format.json schema.

        Per-layer computation:
            W_ternary = 2 * W_binary - 1          # {0,1} → {-1,+1}
            z         = (W_ternary @ h) * scale    # scaled linear
            h         = clamp(z, -1, 1)            # hidden activation

        Final layer uses tanh to map scalar output to (-1, 1).

        Shape validation is implicit via numpy matmul — wrong dimensions
        raise ValueError immediately (fail-fast, no silent corruption).
        """
        h = x
        layers = self.model["layers"]

        for i, layer in enumerate(layers):
            W = np.array(layer["weights"], dtype=np.float32)  # (out_dim, in_dim)
            s = np.array(layer["scale"],   dtype=np.float32)  # (out_dim,)

            if W.ndim != 2:
                raise ValueError(
                    f"BitNetModel: layer '{layer.get('name', i)}' weights must be 2D, "
                    f"got shape {W.shape}"
                )
            if s.shape[0] != W.shape[0]:
                raise ValueError(
                    f"BitNetModel: layer '{layer.get('name', i)}' scale length "
                    f"{s.shape[0]} != weight output dim {W.shape[0]}"
                )

            # Binary → ternary quantization
            W_ternary = 2.0 * W - 1.0  # {0,1} → {-1,+1}
            z = (W_ternary @ h) * s

            is_last = (i == len(layers) - 1)
            if is_last:
                # Output scalar: tanh for (-1, 1) range
                # Clamp to avoid floating-point saturation at exact ±1.0
                h = float(np.tanh(z[0]))
                h = max(-1.0 + 1e-7, min(1.0 - 1e-7, h))
            else:
                # Hidden activation: clamp to [-1, 1]  (BitNet style)
                h = np.clip(z, -1.0, 1.0)

        return float(h)

    # ------------------------------------------------------------------
    # LEGACY FORWARD PASS — model.json schema (kept for backward compat)
    # ------------------------------------------------------------------

    def _linear(self, x, w, b):
        return [sum(xi * wi for xi, wi in zip(x, row)) + bi
                for row, bi in zip(w, b)]

    def _activation(self, x):
        return [max(-1.0, min(1.0, v)) for v in x]

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def forward(self, x):
        """Legacy 6-input forward pass. Preserved for backward compatibility."""
        l1 = self._activation(self._linear(x, self.model["layer1_w"], self.model["layer1_b"]))
        l2 = self._activation(self._linear(l1, self.model["layer2_w"], self.model["layer2_b"]))
        out = self._linear(l2, self.model["out_w"], self.model["out_b"])[0]
        return self._sigmoid(out)


# ---------------------------------------------------------------------------
# Legacy global instance (used by CRT engine and other modules)
# Lazy-loaded so that importing this module does not require model.json to exist.
# ---------------------------------------------------------------------------

_bitnet_instance: "BitNetModel | None" = None


def _get_bitnet() -> BitNetModel:
    global _bitnet_instance
    if _bitnet_instance is None:
        _bitnet_instance = BitNetModel()  # FileNotFoundError surfaces here if model absent
    return _bitnet_instance


def bitnet_score(features: dict) -> float:
    """
    Input:  CRT features dict (canonical keys only)
    Output: confidence score [0, 1]

    Uses hard key access — CRASH on missing (production behavior).
    """
    x = [
        features["body_ratio"],
        features["retest_depth"],
        features["disp_strength"],
        features["atr"],
        features["candles_since_retest"],
        float(features["double_sweep"]),
    ]
    return _get_bitnet().forward(x)
