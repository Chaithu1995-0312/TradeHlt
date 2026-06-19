"""
Phase 5.6 (reality fix) — server↔UTC offset detection (pure, CI, no terminal).

MT5 deal/candle `time` is the trade SERVER's wall clock as an epoch (UTC+offset), not true
UTC. `detect_offset_seconds` recovers the offset from a live server timestamp vs real UTC
now so the adapter can normalize every timestamp to true UTC below the feature layer.
"""
from __future__ import annotations

from mt5_analytics.core.mt5_adapter import detect_offset_seconds

NOW = 1_700_000_000


def test_positive_offset_three_hours():
    assert detect_offset_seconds(NOW + 3 * 3600, NOW) == 3 * 3600


def test_rounds_to_half_hour():
    # +2h58m -> nearest 30 min = +3h
    assert detect_offset_seconds(NOW + 3 * 3600 - 120, NOW) == 3 * 3600
    # +2h12m -> nearest 30 min = +2h
    assert detect_offset_seconds(NOW + 2 * 3600 + 12 * 60, NOW) == 2 * 3600


def test_negative_offset():
    assert detect_offset_seconds(NOW - 5 * 3600, NOW) == -5 * 3600


def test_zero_when_aligned():
    assert detect_offset_seconds(NOW, NOW) == 0


def test_stale_tick_returns_none():
    # a tick 30h away (closed market) is not a real tz offset -> None (caller falls back)
    assert detect_offset_seconds(NOW + 30 * 3600, NOW) is None
