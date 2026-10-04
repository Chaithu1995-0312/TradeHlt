"""I-6: a value at bar t does not change when later bars are appended."""

from __future__ import annotations

import numpy as np

from semantics.market.conditions import structural_position
from semantics.market.events import structure_breaks
from semantics.market.levels import equal_cluster_level, swing_levels
from semantics.market.zones import fvg_views, order_block_views
from semantics.types import OhlcBar, Side


def _walk(n: int, seed: int = 7):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, n))
    high = close + np.abs(rng.normal(0.4, 0.1, n))
    low = close - np.abs(rng.normal(0.4, 0.1, n))
    bars = [
        OhlcBar(float(close[i]), float(high[i]), float(low[i]), float(close[i]), i)
        for i in range(n)
    ]
    return high, low, close, bars


def test_swing_levels_prefix():
    high, low, _close, _bars = _walk(36)
    k = 3
    full = swing_levels(high, low, k=k)
    for t in range(k, len(high)):
        prefix = swing_levels(high[: t + 1], low[: t + 1], k=k)
        assert prefix == [level for level in full if level.available_at <= t]


def test_structural_position_and_structure_break_prefix():
    high, low, close, _bars = _walk(36)
    k = 3
    full_pos = structural_position(high, low, close, k=k)
    full_events = structure_breaks(full_pos)
    for t in (5, 12, 20, 35):
        prefix_pos = structural_position(high[: t + 1], low[: t + 1], close[: t + 1], k=k)
        assert prefix_pos.values == full_pos.values[: t + 1]
        assert prefix_pos.parameterization_id == full_pos.parameterization_id
        prefix_events = structure_breaks(prefix_pos)
        assert prefix_events == full_events[: t + 1]


def test_zone_views_prefix():
    _high, _low, _close, bars = _walk(30, seed=11)
    # Plant one bullish gap so the FVG view is non-vacuous on the prefix.
    bars[2] = OhlcBar(100.0, 100.4, 99.6, 100.0, 2)
    bars[3] = OhlcBar(100.2, 100.6, 99.8, 100.3, 3)
    bars[4] = OhlcBar(102.0, 102.4, 101.2, 102.1, 4)
    full_fvg = fvg_views(bars)
    full_ob = order_block_views(bars, k=2)
    for t in range(len(bars)):
        assert fvg_views(bars[: t + 1])[t] == full_fvg[t]
        assert order_block_views(bars[: t + 1], k=2)[t] == full_ob[t]


def test_equal_cluster_on_a_prefix_is_stable():
    _high, _low, _close, bars = _walk(24, seed=3)
    k = 2
    for t in range(k + 2, len(bars)):
        window = bars[: t + 1]
        first = equal_cluster_level(window, k=k, atr_abs=1.0, tolerance_atr=0.5, side=Side.UPPER)
        second = equal_cluster_level(window, k=k, atr_abs=1.0, tolerance_atr=0.5, side=Side.UPPER)
        assert first == second
        if first is not None:
            assert first.available_at <= t
