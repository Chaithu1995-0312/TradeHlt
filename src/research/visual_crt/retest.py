"""retest.py — Arm B retest predicate for the Visual CRT trade object (SEM-012 v2).

Pure, no-lookahead. Mirrors ``crt_engine_v2.StateMachine.try_expansion_to_retest``'s
adaptive-ceiling shape against a chart-visible pool.

DECLARED MODELLING SUBSTITUTION (MC-VCRT-XAUUSD-M15-V1, Arm B)
--------------------------------------------------------------
The engine's static ceiling is ``retest_depth_max * rng.size``. A pool is a **level**, not a
range, so ``rng.size`` is undefined here. This module substitutes::

    impulse = abs(displacement.close - sweep.sweep_price)

That is a substitution, not a discovery. It must never be restated as "the canonical CRT
retest formula". A positive Arm B result validates *this research object under this
substitution*; it does not certify ``try_expansion_to_retest`` and grants that engine path no
authority. Enforced as ``FC-PIPELINE-SUBSTITUTION-LAUNDERED-AS-CANON`` in the sealed contract.

SEARCH WINDOW: the sealed contract froze the retest *predicate* but declared no separate
retest age bound. Rather than introduce an undeclared parameter, the caller bounds the search
with the contract's already-declared 40-bar horizon (``labels.horizon_bars`` /
``exits.parameters.max_forward``). No new number enters the object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from research.visual_crt.geometry import DisplacementEvent

if TYPE_CHECKING:  # type-only; never a runtime dependency on the spine
    from config_layer.crt_engine_v2 import Candle


@dataclass(frozen=True)
class RetestEvent:
    """Price returned toward the swept pool, inside the adaptive ceiling."""

    displacement: DisplacementEvent
    direction: str
    bar_index: int
    depth_abs: float
    min_depth: float
    adaptive_ceiling: float
    impulse: float
    bars_since_displacement: int


def detect_pool_retest(
    bar: "Candle",
    displacement: DisplacementEvent,
    atr_abs: float,
    *,
    retest_depth_max: float,
    retest_atr_depth_fraction: float,
    retest_min_depth_atr_fraction: float,
) -> RetestEvent | None:
    """Evaluate the retest predicate on `bar`.

    ``depth_abs`` measures how far the close still sits beyond the swept pool:
    ``close - pool.price`` for LONG, ``pool.price - close`` for SHORT. A retest fires when
    that distance has fallen back inside the adaptive ceiling but is not yet degenerate::

        min_depth <= depth_abs <= adaptive_ceiling

    Returns None on any miss — including a close that has crossed back through the pool
    (``depth_abs < 0``), which is a failed setup rather than a deep retest.
    """
    if atr_abs <= 0:
        return None

    age = int(bar.index) - displacement.bar_index
    if age < 0:
        raise ValueError(
            f"detect_pool_retest: bar {bar.index} precedes displacement {displacement.bar_index}"
        )
    if age == 0:
        return None  # the displacement bar is not its own retest

    sweep = displacement.sweep
    pool_price = sweep.pool.price
    close = float(bar.close)

    if displacement.direction == "long":
        depth_abs = close - pool_price
    else:
        depth_abs = pool_price - close

    if depth_abs < 0:
        return None  # closed back through the pool — setup failed, not a retest

    impulse = abs(displacement.close - sweep.sweep_price)
    static_ceiling = retest_depth_max * impulse
    atr_ceiling = retest_atr_depth_fraction * atr_abs
    adaptive_ceiling = max(static_ceiling, atr_ceiling)
    min_depth = retest_min_depth_atr_fraction * atr_abs

    if not (min_depth <= depth_abs <= adaptive_ceiling):
        return None

    return RetestEvent(
        displacement=displacement,
        direction=displacement.direction,
        bar_index=int(bar.index),
        depth_abs=depth_abs,
        min_depth=min_depth,
        adaptive_ceiling=adaptive_ceiling,
        impulse=impulse,
        bars_since_displacement=age,
    )
