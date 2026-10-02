"""I-7: no zone is None. A close exactly on an edge is 0.0 with present=True.

No confirmed swing is UNDEFINED (None), not INSIDE.
"""

from __future__ import annotations

from semantics.market.conditions import StructuralPosition, structural_position
from semantics.market.zones import close_relation, fvg_views
from semantics.types import OhlcBar, ZoneStatus


def test_no_zone_is_distinct_from_a_close_on_the_edge():
    quiet = [OhlcBar(10.0, 10.2, 9.8, 10.0, i) for i in range(5)]
    absent_views = fvg_views(quiet)
    assert all(zone.present is False for zone in absent_views)
    assert close_relation(absent_views[-1], quiet[-1]) is None

    # prev.high 10 < next.low 12 → bullish zone [10, 12], available at the confirming bar.
    gapped = [
        OhlcBar(9.5, 10.0, 9.0, 9.6, 0),
        OhlcBar(10.2, 11.0, 10.0, 10.8, 1),
        OhlcBar(12.2, 12.6, 12.0, 12.4, 2),
        OhlcBar(10.0, 10.2, 9.9, 10.0, 3),
    ]
    views = fvg_views(gapped)
    assert views[0].present is False and views[1].present is False
    assert views[2].present is True
    assert views[2].status is ZoneStatus.ACTIVE
    assert views[2].low == 10.0 and views[2].high == 12.0
    assert views[2].available_at == 2
    assert views[3].present is True
    assert views[3].status is ZoneStatus.TOUCHED
    assert close_relation(views[3], gapped[3]) == 0.0


def test_no_swing_is_undefined_not_inside():
    """Before a swing is confirmed the value is None. INSIDE is a later, different value.

    A flat book does confirm swings once k bars exist on both sides of a pivot
    (`causal_structure_series`). Those later bars are INSIDE, which must stay
    distinguishable from the earlier None.
    """
    n = 12
    highs = [10.0] * n
    lows = [9.0] * n
    closes = [9.5] * n
    series = structural_position(highs, lows, closes, k=3)
    assert all(value is None for value in series.values[:6])
    assert series.values[7] is StructuralPosition.INSIDE
    assert series.values[7] is not None
