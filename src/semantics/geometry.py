"""Geometry primitives GP-01..GP-06 (concept_contracts.yaml). Pure bar-vs-price predicates.

Equality table (frozen in the contracts, enforced by tests/semantics/test_geometry.py):

    GP-01 PIERCE              high >  L      (UPPER)   low  <  L      (LOWER)
    GP-02 BEYOND              close > L                close < L                      strict
    GP-03 REACH               close >= L               close <= L                     inclusive
    GP-04 PIERCE_AND_REJECT   PIERCE and close <  L    PIERCE and close >  L          strict (SP-001)
    GP-05 OVERLAP             bar range intersects [zone_low, zone_high], edges inclusive
    GP-06 DIRECTIONAL_IMPULSE F-074 contract (SP-002)

A close exactly AT L is neither BEYOND nor PIERCE_AND_REJECT — it is "at the level".
GP-07 IN_BAND is PROPOSED (SP-003 deferred on OQ7) and deliberately not implemented.

GP-04 / GP-05 / GP-06 delegate to the existing authorities whose meaning matches:
structure.predicates (SP-001, SP-002) and features.smc._geometry.is_mitigated.
"""

from __future__ import annotations

from features.smc._geometry import Zone as _SmcZone
from features.smc._geometry import is_mitigated as _smc_overlap
from structure import predicates as _sp

from semantics.types import Bar, Bias, Side


def pierce(bar: Bar, level: float, side: Side) -> bool:
    """GP-01."""
    return bar.high > level if side is Side.UPPER else bar.low < level


def beyond(bar: Bar, level: float, side: Side) -> bool:
    """GP-02 (strict)."""
    return bar.close > level if side is Side.UPPER else bar.close < level


def reach(bar: Bar, level: float, side: Side) -> bool:
    """GP-03 (inclusive)."""
    return bar.close >= level if side is Side.UPPER else bar.close <= level


def pierce_and_reject(bar: Bar, level: float, side: Side) -> bool:
    """GP-04 = SP-001 swept_high / swept_low."""
    if side is Side.UPPER:
        return _sp.swept_high(bar.high, bar.close, level)
    return _sp.swept_low(bar.low, bar.close, level)


def overlap(bar: Bar, zone_low: float, zone_high: float) -> bool:
    """GP-05 (edges inclusive) = features.smc._geometry.is_mitigated."""
    if zone_low > zone_high:
        raise ValueError(f"zone_low {zone_low} > zone_high {zone_high}")
    return _smc_overlap(_SmcZone(high=zone_high, low=zone_low, formed_at_index=0, bullish=True), bar)


def directional_impulse(bar: Bar, sweep_price: float, bias: Bias) -> bool:
    """GP-06 = SP-002 (F-074). `bias` is inherited from the sweep, never re-derived from this bar."""
    return _sp.directional_impulse(bar.open, bar.close, sweep_price, is_long=bias is Bias.LONG)
