"""Fail-closed CRTConfig factory for tests — authority defaults, no silent engine fallbacks."""
from __future__ import annotations

from src.config_layer.state_identity import CRTConfig

# Authority (prod params). FOREX/CRYPTO Overrides are separate and must be passed explicitly.
_AUTHORITY = dict(
    body_ratio_min=0.65,
    atr_multiplier_min=1.0,
    retest_depth_max=0.15,
    expansion_atr_min_distance=0.30,
)


def crt_config_for_test(**overrides) -> CRTConfig:
    """Build CRTConfig with authority four keys; tests may override any field."""
    kw = dict(_AUTHORITY)
    kw.update(overrides)
    return CRTConfig(**kw)
