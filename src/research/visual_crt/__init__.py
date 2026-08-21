"""visual_crt — the Visual CRT trade object (SEM-012), Lane 1 geometry.

A research interpreter for "the trade a trader reading the chart would have taken":
sweep of a CHART-VISIBLE liquidity pool → directional displacement away from the swept
side (F-074) → entry.

Not a CRT engine object. This package founds on prior-closed-H4 / PDH-PDL pools, never on
``M15StructuralLiquidityRange``, never imports ``config_layer.crt_engine_v2`` at runtime,
and is wired into no engine. `P-CRT-LIQ-01` ("no second named CRT liquidity object") is
therefore untouched — this is a research lane, not a second CRT liquidity type.

Grants no authority (CLAUDE.md §6.5). Nothing here promotes, gates, or changes
``ACTIVE_VERSION``.

Spec: ``docs/research/visual_crt_trade_object.md``
Floor: ``tests/research/test_visual_crt_trade_object.py``
"""

from research.visual_crt.geometry import (
    DisplacementEvent,
    PoolSweepEvent,
    detect_directional_displacement,
    detect_pool_sweep,
)
from research.visual_crt.pools import POOL_KINDS, LiquidityPool, visible_pools

__all__ = [
    "POOL_KINDS",
    "DisplacementEvent",
    "LiquidityPool",
    "PoolSweepEvent",
    "detect_directional_displacement",
    "detect_pool_sweep",
    "visible_pools",
]
