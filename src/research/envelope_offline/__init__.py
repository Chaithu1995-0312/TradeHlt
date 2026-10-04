"""Envelope offline research training (ENV_OFFLINE_TRAIN_V1).

No spine imports. No registry promote. Artifacts under results/envelope_offline only.
"""
from research.envelope_offline.shadow import (
    SHADOW_CHARTER_ID,
    ShadowConfig,
    run_shadow,
)
from research.envelope_offline.train import (
    CHARTER_ID,
    HEADS,
    TrainConfig,
    run_offline_train,
)

__all__ = [
    "CHARTER_ID",
    "HEADS",
    "SHADOW_CHARTER_ID",
    "ShadowConfig",
    "TrainConfig",
    "run_offline_train",
    "run_shadow",
]
