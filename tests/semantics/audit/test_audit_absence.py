
# Phase 1 audit test. Authority: invariant I-7, decision D-7, concept_contracts.yaml MKT-Z02 / MKT-L01.

from __future__ import annotations

from semantics.market.conditions import StructuralPosition, structural_position
from semantics.market.events import sweep
from semantics.market.levels import equal_cluster_level, swing_levels
from semantics.market.zones import close_relation, fvg_views
from semantics.types import OhlcBar, Side

_SENTINELS = (0.0, 10.0, 99.0, -1.0, 9999.0)


def test_no_zone_is_distinguishable_from_price_exactly_on_the_zone_edge():
    quiet = [OhlcBar(10.0, 10.2, 9.8, 10.0, i) for i in range(5)]
    absent = fvg_views(quiet)
    assert all(z.present is False for z in absent)
    assert absent[-1].low is None and absent[-1].high is None
    assert close_relation(absent[-1], quiet[-1]) is None
    gapped = [
        OhlcBar(9.5, 10.0, 9.0, 9.6, 0),
        OhlcBar(10.2, 11.0, 10.0, 10.8, 1),
        OhlcBar(12.2, 12.6, 12.0, 12.4, 2),
        OhlcBar(10.0, 10.2, 9.9, 10.0, 3),
    ]
    views = fvg_views(gapped)
    assert views[3].present is True and views[3].low == 10.0
    assert close_relation(views[3], gapped[3]) == 0.0
    assert close_relation(absent[-1], quiet[-1]) != 0.0


def test_no_swing_yet_is_undefined_not_inside():
    n = 12
    series = structural_position([10.0] * n, [9.0] * n, [9.5] * n, k=3)
    assert series.values[0] is None
    assert series.values[0] is not StructuralPosition.INSIDE


def test_no_sentinel_price_stands_for_absence_in_a_level():
    highs = [10.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(20)]
    lows = [9.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(20)]
    for level in swing_levels(highs, lows, k=2):
        assert level.price not in _SENTINELS


def test_equal_cluster_returns_none_and_not_a_sentinel_when_no_cluster():
    bars = [OhlcBar(c, c + 0.1, c - 0.1, c, i) for i, c in enumerate([100.0 + 0.05 * i for i in range(10)])]
    hit = equal_cluster_level(bars, k=2, atr_abs=1.0, tolerance_atr=0.001, side=__import__("semantics.types", fromlist=["Side"]).Side.UPPER)
    assert hit is None or hit.price not in _SENTINELS


def test_no_sentinel_is_ever_used_as_a_price_for_absence():
    # Real levels carry real prices; absence is None, never one of the sentinel prices.
    highs = [2400.0 + (5.0 if i % 3 == 0 else 0.0) for i in range(16)]
    lows = [2390.0 - (5.0 if i % 3 == 1 else 0.0) for i in range(16)]
    levels = swing_levels(highs, lows, k=2)
    assert levels
    for level in levels:
        assert level.price not in _SENTINELS
    hit = equal_cluster_level([OhlcBar(2400.0 + i, 2401.0 + i, 2399.0 + i, 2400.0 + i, i) for i in range(10)],
                              k=2, atr_abs=1.0, tolerance_atr=0.001, side=Side.UPPER)
    assert hit is None or hit.price not in _SENTINELS
