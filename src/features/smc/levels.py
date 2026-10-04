"""features.smc.levels — Previous-Day High/Low (PDH/PDL) and Equal Highs/Lows (EQH/EQL).

PDH/PDL: the most recently CLOSED D1 parent candle's high/low. This module does not build its
own D1 aggregation — it takes the caller's `features.parent_candle.ParentCandleBuilder("D1",
keep>=1).parent_history` directly, so the M15 pipeline drives ONE D1 builder shared across
whatever consumes daily levels, rather than every consumer re-deriving its own day boundaries.

EQH/EQL: 2+ confirmed swing highs (or lows) within a small ATR-scaled tolerance of each other —
the standard SMC "resting liquidity pool" reading (the market treats near-equal highs/lows as a
single larger liquidity target, not independent levels). `market_reality_v1.yaml` never named
this dimension explicitly, but it is exactly the kind of resting-liquidity structure
`liquidity_pressure_score`/`liquidity_distance` (FM-025/026) already approximate at the single-
swing level — EQH/EQL extends that to CLUSTERS of swings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from features.smc._geometry import SwingPoint, collect_causal_swings, signed_atr_distance

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


def pdh_pdl_distance(close: float, d1_parent_history: "Sequence[Candle]", atr: float) -> tuple[float, float]:
    """(pdh_distance, pdl_distance) — signed, ATR-normalized, tanh-bounded distances from
    `close` to the most recently closed D1 parent's high/low. `(0.0, 0.0)` if no D1 parent has
    closed yet (empty history)."""
    hist = list(d1_parent_history)
    if not hist:
        return 0.0, 0.0
    prev_day = hist[-1]
    pdh_dist = signed_atr_distance(close, prev_day.high, atr, favorable_sign=-1)   # below PDH = inside
    pdl_dist = signed_atr_distance(close, prev_day.low, atr, favorable_sign=1)     # above PDL = inside
    return pdh_dist, pdl_dist


def _nearest_equal_cluster(
    swings: list[SwingPoint], atr: float, tolerance_atr: float,
) -> Optional[SwingPoint]:
    """The most recent swing that has at least one OTHER swing (any recency) within
    `tolerance_atr * atr` of its price — i.e. the most recent member of an equal-highs/lows
    cluster. `swings` is most-recent-first (from `collect_causal_swings`)."""
    if atr is None or atr <= 0 or len(swings) < 2:
        return None
    band = tolerance_atr * atr
    for i, s in enumerate(swings):
        for other in swings[i + 1:]:
            if abs(s.price - other.price) <= band:
                return s   # s is the more recent of the pair (swings is most-recent-first)
    return None


def eqh_eql_distance(
    window: "Sequence[Candle]", k: int, atr: float, *, tolerance_atr: float = 0.1, max_swings: int = 8,
) -> tuple[float, float]:
    """(eqh_distance, eql_distance) — signed, ATR-normalized, tanh-bounded distances from
    `window[-1].close` to the nearest equal-highs cluster above / equal-lows cluster below.
    `0.0` component when no cluster of that kind exists yet."""
    close = window[-1].close
    highs = collect_causal_swings(window, k, "high", max_count=max_swings)
    lows = collect_causal_swings(window, k, "low", max_count=max_swings)
    eqh = _nearest_equal_cluster(highs, atr, tolerance_atr)
    eql = _nearest_equal_cluster(lows, atr, tolerance_atr)
    eqh_dist = signed_atr_distance(close, eqh.price, atr, favorable_sign=-1) if eqh is not None else 0.0
    eql_dist = signed_atr_distance(close, eql.price, atr, favorable_sign=1) if eql is not None else 0.0
    return eqh_dist, eql_dist
