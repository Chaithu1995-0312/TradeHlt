"""
MSIP shadow continuous market-state package (OBSERVATION_ONLY).

Authority: G-IMPL-01 OPEN narrow shadow implementation only.
Does NOT influence CRT state, events, trades, or execution.
"""

from __future__ import annotations

from msip.interpretation_config import (
    Disabled,
    MsipShadowConfig,
    load_msip_shadow_config,
)
from msip.market_state_vector import MarketStateVector, CrtPhaseObservation
from msip.shadow_emitter import (
    ProvenanceContext,
    build_market_state,
    emit_jsonl,
    observe_crt_state,
)

__all__ = [
    "Disabled",
    "MsipShadowConfig",
    "load_msip_shadow_config",
    "MarketStateVector",
    "CrtPhaseObservation",
    "ProvenanceContext",
    "build_market_state",
    "emit_jsonl",
    "observe_crt_state",
]

SHADOW_AFFECTS_CRT = False
SHADOW_AFFECTS_EXECUTION = False
SHADOW_AFFECTS_EVENTS = False
