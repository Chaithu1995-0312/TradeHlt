"""
encoders.py
===========
IFeatureEncoder implementations (Spec hierarchy).
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from bitnet.defaults import (
    ENC_CANONICAL38_ID,
    ENC_LEGACY6_ID,
    LEGACY6_KEYS,
)
from bitnet.runtime_types import EncodedTensor, FeatureIdentity

try:
    from features.feature_schema import CANONICAL_FEATURES, FEATURE_ORDER_HASH
except Exception:  # pragma: no cover
    CANONICAL_FEATURES = []  # type: ignore
    FEATURE_ORDER_HASH = ""


def _require_finite(name: str, value: float) -> float:
    if value != value:  # NaN
        raise ValueError(f"encoder: feature {name!r} is NaN")
    if value in (float("inf"), float("-inf")):
        raise ValueError(f"encoder: feature {name!r} is non-finite")
    return float(value)


class Legacy6Encoder:
    """CONTRACT-A 6 hard keys — fail-fast on missing (production bitnet_score)."""

    id_ = ENC_LEGACY6_ID

    def __init__(self, keys: Sequence[str] = LEGACY6_KEYS):
        self._keys = tuple(keys)

    def id(self) -> str:
        return self.id_

    def identities(self) -> List[FeatureIdentity]:
        return [FeatureIdentity(name=k) for k in self._keys]

    def dim(self) -> int:
        return len(self._keys)

    def feature_order_hash(self) -> str:
        return ""

    def encode(self, features: Mapping[str, object]) -> EncodedTensor:
        data: List[float] = []
        for k in self._keys:
            if k not in features:
                raise KeyError(k)
            raw = features[k]
            if k == "double_sweep":
                data.append(_require_finite(k, float(raw)))
            else:
                data.append(_require_finite(k, float(raw)))  # type: ignore[arg-type]
        return EncodedTensor(data=data, dim=len(data), feature_order_hash="")


class Canonical38Encoder:
    """CONTRACT-B 38-dim encoder with optional mean/std normalize."""

    id_ = ENC_CANONICAL38_ID

    def __init__(
        self,
        feature_names: Optional[Sequence[str]] = None,
        *,
        mean: Optional[Sequence[float]] = None,
        std: Optional[Sequence[float]] = None,
        feature_order_hash: str = "",
    ):
        names = list(feature_names) if feature_names is not None else list(CANONICAL_FEATURES)
        if len(names) != 38 and feature_names is None and CANONICAL_FEATURES:
            # Prefer live schema; allow override for tests with explicit names.
            pass
        if not names:
            raise ValueError("Canonical38Encoder: empty feature_names")
        self._names = names
        self._hash = feature_order_hash or FEATURE_ORDER_HASH
        self._mean = [float(x) for x in mean] if mean is not None else None
        self._std = [float(x) for x in std] if std is not None else None
        if self._mean is not None and len(self._mean) != len(self._names):
            raise ValueError("Canonical38Encoder: mean length mismatch")
        if self._std is not None and len(self._std) != len(self._names):
            raise ValueError("Canonical38Encoder: std length mismatch")

    def id(self) -> str:
        return self.id_

    def identities(self) -> List[FeatureIdentity]:
        return [FeatureIdentity(name=n) for n in self._names]

    def dim(self) -> int:
        return len(self._names)

    def feature_order_hash(self) -> str:
        return self._hash

    def encode(self, features: Mapping[str, object]) -> EncodedTensor:
        data: List[float] = []
        for i, name in enumerate(self._names):
            if name not in features:
                raise KeyError(name)
            v = _require_finite(name, float(features[name]))  # type: ignore[arg-type]
            if self._mean is not None and self._std is not None:
                s = self._std[i] if self._std[i] != 0.0 else 1.0
                v = (v - self._mean[i]) / s
            data.append(v)
        return EncodedTensor(
            data=data,
            dim=len(data),
            feature_order_hash=self._hash,
        )

    def encode_vector(self, vector: Sequence[float]) -> EncodedTensor:
        if len(vector) != self.dim():
            raise ValueError(
                f"Canonical38Encoder.encode_vector: expected {self.dim()}, got {len(vector)}"
            )
        data = [_require_finite(f"idx{i}", float(v)) for i, v in enumerate(vector)]
        if self._mean is not None and self._std is not None:
            out = []
            for i, v in enumerate(data):
                s = self._std[i] if self._std[i] != 0.0 else 1.0
                out.append((v - self._mean[i]) / s)
            data = out
        return EncodedTensor(data=data, dim=len(data), feature_order_hash=self._hash)


def apply_crt_serve_aliases(features: Mapping[str, object]) -> Dict[str, object]:
    """Map CRT cache FM-027/028 (+ atr_abs) into legacy bitnet_score keys.

    Pure dict transform for Adapter / CRT call-site documentation.
    Does not invent missing keys; only renames when source present.
    """
    out: Dict[str, object] = dict(features)
    if "displacement_retrace" in features and "retest_depth" not in out:
        out["retest_depth"] = features["displacement_retrace"]
    if "displacement_atr_ratio" in features and "disp_strength" not in out:
        out["disp_strength"] = features["displacement_atr_ratio"]
    if "atr_abs" in features and "atr" not in out:
        out["atr"] = features["atr_abs"]
    return out
