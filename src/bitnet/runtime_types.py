"""
runtime_types.py
================
Shared value types for the BitNet inference hierarchy
(Encoder → Backbone → Heads → Adapter). Spec v1.2.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class FeatureIdentity:
    name: str
    fm_id: str = ""
    formula_id: str = ""


@dataclass(frozen=True)
class EncodedTensor:
    """Dense float vector after encoding (no feature names)."""
    data: List[float]
    dim: int
    feature_order_hash: str = ""

    def as_list(self) -> List[float]:
        return list(self.data)


@dataclass(frozen=True)
class Latent:
    data: List[float]
    dim: int

    def as_list(self) -> List[float]:
        return list(self.data)


@dataclass(frozen=True)
class HeadOutputs:
    confidence: float
    win_probability: Optional[float] = None
    expected_rr: Optional[float] = None
    embedding: Optional[List[float]] = None
    extras: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Prediction:
    confidence: float
    schema_version: str
    feature_dim: int
    feature_order_hash: str = ""
    encoder_id: str = ""
    backbone_id: str = ""
    heads_id: str = ""
    adapter_id: str = ""
    heads: Mapping[str, float] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelMetadata:
    schema_version: str
    feature_dim: int
    feature_names: List[str]
    feature_order_hash: str
    encoder_id: str
    backbone_id: str
    heads_id: str
    adapter_id: str
    defaults_profile: str = ""
    label_contract_id: str = ""
    economic_authority: str = ""
    train_feature_identities: List[FeatureIdentity] = field(default_factory=list)
    artifact_sha256: str = ""
    instrument_scope: str = "global"
    created_at: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
