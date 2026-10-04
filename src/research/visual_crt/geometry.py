"""geometry.py — Visual CRT sweep + directional-displacement geometry (SEM-012).

Pure, no-lookahead primitives. Every function inspects only the bar(s) it is handed and
returns a value; no config reads, no I/O, no state.

Two geometries are re-expressed here against a chart-visible ``LiquidityPool`` instead of
the engine's own envelope, following the ``research.weekly_sweep`` isolation precedent
(reimplement the small shared arithmetic locally; never import the live spine):

  * SWEEP — ``crt_engine_v2.RangeDetector.detect_sweep``'s boundary-cross-then-close-back-
    inside test (``high > ref and close < ref``, symmetric for the low side), and its
    short-on-high-sweep / long-on-low-sweep convention.
  * DISPLACEMENT — the F-074 directional contract
    (``CH-directional-displacement-contract``, user-authorized 2026-08-13) as implemented
    in ``StateMachine.try_sweep_to_displacement``: the impulse must travel AWAY from the
    swept side. Unsigned energy-only displacement is not legal.

``body_ratio`` is imported from ``features.candle_math`` — the single source of truth for
candle geometry (F-046/F-047). It is never re-derived here; the ownership lint would flag
a local re-derivation, and correctly.

Thresholds are parameters, never literals: the caller passes values it has pre-registered
in its measurement contract. Defaults are absent on purpose — a silent default is exactly
the config-illusion class F-056 documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from features.candle_math import body_ratio, candle_range
# SK-1 (2026-08-19): SP-001/SP-002 identities. Same standing as `candle_math` above — a pure
# identity module, not the live spine. The pool FOUNDING below stays local (F-081's ontology).
from structure.predicates import (
    directional_impulse as _directional_impulse,
    swept_high as _swept_high,
    swept_low as _swept_low,
)

from research.visual_crt.pools import LiquidityPool

if TYPE_CHECKING:  # type-only; never a runtime dependency on the spine
    from config_layer.crt_engine_v2 import Candle


@dataclass(frozen=True)
class PoolSweepEvent:
    """A pierce of a chart-visible pool that closed back on the origin side."""

    pool: LiquidityPool
    direction: str           # "long" (low swept) | "short" (high swept)
    sweep_price: float       # the extreme that did the piercing — this bar's own high/low
    bar_index: int


@dataclass(frozen=True)
class DisplacementEvent:
    """A directional impulse away from the swept side (F-074)."""

    sweep: PoolSweepEvent
    direction: str           # inherited from the sweep; never re-derived
    bar_index: int
    body_ratio: float
    move: float              # |close - open| in price units
    close: float             # the displacement bar's close — Arm B's impulse input
    bars_since_sweep: int


def detect_pool_sweep(
    bar: "Candle",
    pools: Sequence[LiquidityPool],
) -> PoolSweepEvent | None:
    """Boundary-cross-then-close-back-inside, evaluated on `bar` against `pools`.

    A HIGH pool is swept when the bar trades above it but closes back below; a LOW pool
    when the bar trades below it but closes back above. Sweeping buy-side liquidity (a
    HIGH pool) implies a SHORT; sweeping sell-side (a LOW pool) implies a LONG.

    When several pools are swept on one bar the FURTHEST pierced level wins — the deepest
    stop-run is the one a trader would read as the liquidity event. Ties resolve to the
    first pool in the supplied order, so the caller's ordering is the tie-break and the
    result is deterministic.

    Pools formed at or after `bar.index` are ignored: a level is only sweepable once it is
    already on the chart.
    """
    high = float(bar.high)
    low = float(bar.low)
    close = float(bar.close)
    idx = int(bar.index)

    best: PoolSweepEvent | None = None
    best_depth = 0.0

    for pool in pools:
        if pool.formed_at_index >= idx:
            continue  # not yet visible when this bar traded
        if pool.side == "HIGH":
            if _swept_high(high, close, pool.price):
                depth = high - pool.price
                if depth > best_depth:
                    best_depth = depth
                    best = PoolSweepEvent(
                        pool=pool, direction="short", sweep_price=high, bar_index=idx
                    )
        else:
            if _swept_low(low, close, pool.price):
                depth = pool.price - low
                if depth > best_depth:
                    best_depth = depth
                    best = PoolSweepEvent(
                        pool=pool, direction="long", sweep_price=low, bar_index=idx
                    )

    return best


def detect_directional_displacement(
    bar: "Candle",
    sweep: PoolSweepEvent,
    atr_abs: float,
    *,
    body_ratio_min: float,
    atr_min_displacement: float,
    atr_multiplier_min: float,
    max_sweep_age_candles: int,
) -> DisplacementEvent | None:
    """F-074 directional displacement, re-expressed against a `PoolSweepEvent`.

    All six gates must pass, in the same order the engine applies them:

    1. sweep age — `bar.index - sweep.bar_index <= max_sweep_age_candles`
    2. direction present (guaranteed by `PoolSweepEvent`, asserted defensively)
    3. **direction** — LONG requires a bullish body (close > open); SHORT bearish.
       This is the F-074 contract: energy alone is not displacement.
    4. **displacement past the swept level** — LONG requires close > sweep price;
       SHORT requires close < sweep price.
    5. body quality — `body_ratio >= body_ratio_min`
    6. bar size — `candle_range >= atr_multiplier_min * atr_abs` and
       `|close - open| >= atr_min_displacement * atr_abs`

    `atr_abs` is ATR in PRICE units (FM-074 `atr_absolute`), not the close-relative
    canonical `atr` (FM-041). Passing the relative form silently shrinks every threshold —
    the F-072 defect class. The caller owns the conversion.

    Returns None on any failed gate (the caller decides whether to keep waiting or drop
    the sweep); never raises on ordinary rejection.
    """
    if atr_abs <= 0:
        return None

    age = int(bar.index) - sweep.bar_index
    if age < 0:
        raise ValueError(
            f"detect_directional_displacement: bar {bar.index} precedes sweep {sweep.bar_index}"
        )
    if age > max_sweep_age_candles:
        return None

    direction = sweep.direction
    if direction not in ("long", "short"):
        raise ValueError(f"detect_directional_displacement: bad direction {direction!r}")

    o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
    is_long = direction == "long"

    # Gates 3+4 — F-074 (SP-002): bodied in the intended direction AND clearing the swept
    # level. One call, one implementation; the six-gate ORDER and every magnitude gate below
    # are unchanged (magnitude is caller-applied, never part of the direction contract).
    if not _directional_impulse(o, c, sweep.sweep_price, is_long=is_long):
        return None

    # Gate 5 — body quality (canonical FM-010 identity).
    br = body_ratio(o, h, l, c)
    if br < body_ratio_min:
        return None

    # Gate 6 — the bar must actually be large.
    if candle_range(h, l) < atr_multiplier_min * atr_abs:
        return None
    move = abs(c - o)
    if move < atr_min_displacement * atr_abs:
        return None

    return DisplacementEvent(
        sweep=sweep,
        direction=direction,
        bar_index=int(bar.index),
        body_ratio=br,
        move=move,
        close=c,
        bars_since_sweep=age,
    )
