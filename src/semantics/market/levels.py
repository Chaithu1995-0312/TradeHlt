"""MKT-L01 liquidity_level and MKT-L02 derived_level.

A LEVEL is a price the market defined. It never carries a role (objective / stop): roles are
Trading-layer bindings onto a level (I-10).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

import numpy as np

from features.causal_structure import causal_structure_series
from features.smc._geometry import collect_causal_swings
from features.smc.levels import _nearest_equal_cluster

from semantics.identity import parameterization_id
from semantics.types import Bar, LevelStatus, Side

LIQUIDITY_LEVEL = "MKT-L01"
DERIVED_LEVEL = "MKT-L02"

#: Founding enumeration (structure_profiles.yaml SPP ids where they exist).
FOUNDINGS = (
    "m15_structural_range",   # SPP-001
    "parent_candle",          # SPP-002
    "weekly_mon_tue",         # SPP-003
    "visual_pool",            # SPP-004
    "swing_pivot",            # SPP-005
    "prior_day",              # SPP-006
    "equal_cluster",          # SPP-007
    "mother_range",           # SPP-008
    "htf_range_resolver",     # SPP-009
)


@dataclass(frozen=True)
class Level:
    concept_id: str
    price: float
    side: Optional[Side]   # None only for MKT-L02 levels without a side (equilibrium)
    founding: str
    timeframe: str
    clock: str
    formed_at: int          # bar index the level describes
    available_at: int       # first bar index at which the level is knowable (I-6)
    parameterization_id: str
    status: LevelStatus = LevelStatus.ACTIVE
    anchor: Optional[str] = None   # MKT-L02 only: what the level is derived from

    def __post_init__(self) -> None:
        if self.available_at < self.formed_at:
            raise ValueError(f"{self.concept_id}: available_at {self.available_at} < formed_at {self.formed_at}")
        if self.concept_id == LIQUIDITY_LEVEL:
            if self.founding not in FOUNDINGS:
                raise ValueError(f"unknown founding {self.founding!r}")
            if self.side is None:
                raise ValueError("a liquidity level must declare its side")

    def with_status(self, status: LevelStatus) -> "Level":
        return replace(self, status=status)


# ── MKT-L01 constructors ──────────────────────────────────────────────────────

def swing_levels(highs: Sequence[float], lows: Sequence[float], *, k: int,
                 timeframe: str = "M15") -> list[Level]:
    """Confirmed swing pivots as liquidity levels, founding `swing_pivot(k)`.

    Reuses `causal_structure_series` (the FC1-A causal binding): a pivot at bar j is published
    at bar j+k, so `available_at = formed_at + k`. Only the swing flags are read; ATR is not an
    input of this concept (unit array passed to satisfy the signature).
    """
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    n = len(h)
    with np.errstate(all="ignore"):
        s = causal_structure_series(h, l, (h + l) / 2, np.ones(n), k=k, double_sweep_window=1)
    pid = parameterization_id(LIQUIDITY_LEVEL, {"founding": "swing_pivot", "k": int(k)}, ("founding", "k"))
    out: list[Level] = []
    for i in range(n):
        j = i - k
        if s["swing_high"][i]:
            out.append(Level(LIQUIDITY_LEVEL, float(h[j]), Side.UPPER, "swing_pivot", timeframe,
                             "bar_close", j, i, pid))
        if s["swing_low"][i]:
            out.append(Level(LIQUIDITY_LEVEL, float(l[j]), Side.LOWER, "swing_pivot", timeframe,
                             "bar_close", j, i, pid))
    return out


def range_levels(h_ref: float, l_ref: float, *, founding: str, formed_at: int, available_at: int,
                 timeframe: str, clock: str) -> tuple[Level, Level]:
    """Upper and lower boundary of a founded range (SEM-011 envelope, parent C1, weekly box …).

    The range object itself is built by its existing authority (e.g.
    `config_layer.m15_structural_range.from_child_window`); this only types its two edges.
    """
    pid = parameterization_id(LIQUIDITY_LEVEL, {"founding": founding}, ("founding",))
    return (
        Level(LIQUIDITY_LEVEL, float(h_ref), Side.UPPER, founding, timeframe, clock, formed_at, available_at, pid),
        Level(LIQUIDITY_LEVEL, float(l_ref), Side.LOWER, founding, timeframe, clock, formed_at, available_at, pid),
    )


def prior_day_levels(day_high: float, day_low: float, *, formed_at: int, available_at: int,
                     clock: str) -> tuple[Level, Level]:
    """PDH / PDL. The clock is declared by the caller (F-066: broker day is not the UTC day)."""
    if not clock:
        raise ValueError("prior_day requires a declared clock")
    return range_levels(day_high, day_low, founding="prior_day", formed_at=formed_at,
                        available_at=available_at, timeframe="D1", clock=clock)


def structural_range_levels(candles: Sequence[Bar], *, clock_id: str, formed_at: int,
                            available_at: int, clock: str, session: str = "UNKNOWN",
                            timeframe: str = "M15") -> tuple[Level, Level]:
    """M15 structural-range edges. The envelope is built by `m15_structural_range.from_child_window`."""
    from config_layer.m15_structural_range import from_child_window

    if not clock:
        raise ValueError("m15_structural_range requires a declared clock")
    env = from_child_window(list(candles), clock_id, session=session)
    return range_levels(env.h_ref, env.l_ref, founding="m15_structural_range", formed_at=formed_at,
                        available_at=available_at, timeframe=timeframe, clock=clock)


def equal_cluster_level(window: Sequence[Bar], *, k: int, atr_abs: float, tolerance_atr: float,
                        side: Side, max_swings: int = 8, timeframe: str = "M15") -> Optional[Level]:
    """EQH / EQL: the most recent swing with another swing within `tolerance_atr * atr_abs`.

    Reuses `features.smc.levels._nearest_equal_cluster` over `collect_causal_swings`. Returns
    None when no cluster exists (absence is None, never a sentinel price — I-7).
    """
    kind = "high" if side is Side.UPPER else "low"
    swings = collect_causal_swings(window, k, kind, max_count=max_swings)
    hit = _nearest_equal_cluster(swings, atr_abs, tolerance_atr)
    if hit is None:
        return None
    pid = parameterization_id(LIQUIDITY_LEVEL,
                              {"founding": "equal_cluster", "k": int(k), "tolerance_atr": float(tolerance_atr)},
                              ("founding", "k", "tolerance_atr"))
    return Level(LIQUIDITY_LEVEL, float(hit.price), side, "equal_cluster", timeframe, "bar_close",
                 int(hit.index), int(hit.index) + k, pid)


# ── MKT-L02 derived levels ────────────────────────────────────────────────────

def _derived(price: float, side: Optional[Side], anchor: str, kind: str, params: dict,
             formed_at: int, available_at: int, timeframe: str) -> Level:
    pid = parameterization_id(DERIVED_LEVEL, {"kind": kind, **params}, ("kind", *params))
    return Level(DERIVED_LEVEL, float(price), side, kind, timeframe, "bar_close",
                 formed_at, available_at, pid, anchor=anchor)


def retracement(move_start: float, move_end: float, fraction: float, *, anchor: str,
                formed_at: int, available_at: int, timeframe: str = "M15") -> Level:
    """Price that retraces `fraction` of the move start→end, measured back from `move_end`."""
    price = move_end - fraction * (move_end - move_start)
    side = Side.LOWER if move_end >= move_start else Side.UPPER
    return _derived(price, side, anchor, "retracement", {"fraction": float(fraction)},
                    formed_at, available_at, timeframe)


def extension(origin: float, move_end: float, fib: float, *, anchor: str,
              formed_at: int, available_at: int, timeframe: str = "M15") -> Level:
    """Price at `fib` × (move_end − origin) beyond `origin`, in the move's direction."""
    price = origin + fib * (move_end - origin)
    side = Side.UPPER if move_end >= origin else Side.LOWER
    return _derived(price, side, anchor, "extension", {"fib": float(fib)}, formed_at, available_at, timeframe)


def equilibrium(upper: Level, lower: Level, *, anchor: str) -> Level:
    """Midpoint of a founded range. Distinct identity from a 50% move retracement."""
    return _derived((upper.price + lower.price) / 2, None, anchor, "equilibrium", {},
                    max(upper.formed_at, lower.formed_at), max(upper.available_at, lower.available_at),
                    upper.timeframe)


def candle_extreme(bar: Bar, side: Side, *, anchor: str, timeframe: str = "M15") -> Level:
    """High (UPPER) or low (LOWER) of one bar, e.g. the displacement candle."""
    price = bar.high if side is Side.UPPER else bar.low
    return _derived(price, side, anchor, "candle_extreme", {}, bar.index, bar.index, timeframe)
