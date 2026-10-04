"""ParentCRTFeed — calendar-true parent close → ParentCRTTrack → bias.

Proves the F-075 caller adapter: no lookahead, C3-only bias, fail-fast config,
and enabled:false returns None (v2_multi byte-identical path).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config_layer.crt_engine_v2 import Candle
from config_layer.htf_state import HTFStateThresholds
from config_layer.state_identity import CRTState, Direction
from runtime.parent_crt_feed import ParentCRTFeed

_THRESH = HTFStateThresholds(1.2, 0.7, 1.0)


def _c(ts, o, h, l, cl) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1.0)


def _h4_children(start: datetime, o: float, h: float, l: float, cl: float) -> list[Candle]:
    """16 M15 bars that aggregate to one H4 with the given OHLC."""
    bars = []
    mid = (o + cl) / 2.0
    for i in range(16):
        ts = start + timedelta(minutes=15 * i)
        if i == 0:
            bo, bc = o, o
        elif i == 15:
            bo, bc = cl, cl
        else:
            bo = bc = mid
        hi = h if i == 1 else max(bo, bc)
        lo = l if i == 2 else min(bo, bc)
        if hi < max(bo, bc):
            hi = max(bo, bc)
        if lo > min(bo, bc):
            lo = min(bo, bc)
        bars.append(_c(ts, bo, hi, lo, bc))
    return bars


def _long_narrative_m15() -> list[Candle]:
    """C1 [100,110] → C2 sweep-low → C3 bullish close above sweep. 49 M15 bars:
    16+16+16 children plus the first bar of the next H4 that closes C3."""
    t0 = datetime(2024, 1, 2, 0, 0)
    c1 = _h4_children(t0, 105, 110, 100, 107)
    c2 = _h4_children(t0 + timedelta(hours=4), 99, 101, 95, 100.5)
    c3 = _h4_children(t0 + timedelta(hours=8), 101, 120, 100, 118)
    closer = _c(t0 + timedelta(hours=12), 118, 119, 117, 118.5)
    return c1 + c2 + c3 + [closer]


def test_bias_none_until_first_parent_closes():
    feed = ParentCRTFeed("H4", _THRESH)
    t0 = datetime(2024, 1, 2, 0, 0)
    for i, bar in enumerate(_h4_children(t0, 105, 110, 100, 107)[:15]):
        assert feed.push(bar) is False, i
        assert feed.bias is Direction.NONE
        assert feed.state is CRTState.RANGE_C1


def test_first_closed_parent_is_c1_bias_still_none():
    feed = ParentCRTFeed("H4", _THRESH)
    bars = _long_narrative_m15()
    for bar in bars[:16]:
        feed.push(bar)
    assert feed.bias is Direction.NONE
    closed = feed.push(bars[16])  # 04:00 — closes C1
    assert closed is True
    assert feed.state is CRTState.RANGE_C1
    assert feed.bias is Direction.NONE


def test_golden_narrative_bias_only_after_c3_close():
    feed = ParentCRTFeed("H4", _THRESH)
    bars = _long_narrative_m15()
    for i, bar in enumerate(bars):
        feed.push(bar)
        if i < 48:
            assert feed.bias is Direction.NONE, f"bias leaked at child {i}"
    # bars[48] is 12:00 — closes C3
    assert feed.state is CRTState.DISTRIBUTION_C3
    assert feed.bias is Direction.LONG


def test_no_lookahead_open_h4_does_not_move_bias():
    """After C3 is confirmed, further children of the NEXT H4 must not change
    bias until that next H4 itself closes."""
    feed = ParentCRTFeed("H4", _THRESH)
    bars = _long_narrative_m15()
    for bar in bars:
        feed.push(bar)
    assert feed.bias is Direction.LONG
    t_next = datetime(2024, 1, 2, 12, 15)
    for i in range(14):
        feed.push(_c(t_next + timedelta(minutes=15 * i), 118, 119, 117, 118))
        assert feed.bias is Direction.LONG
        assert feed.state is CRTState.DISTRIBUTION_C3


def test_from_prod_config_armed_on_active_htfcrt():
    feed = ParentCRTFeed.from_prod_config()
    # ACTIVE_VERSION is v2_htfcrt_2026_08 (parent_crt.enabled:true, timeframe H4).
    assert feed is not None
    assert feed.rule == "H4"


def test_from_prod_config_none_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "runtime.parent_crt_feed.get_prod_section",
        lambda name: {
            "enabled": False,
            "timeframe": "H4",
            "bias_gate_mode": "reject_on_mismatch",
            "htf_state": {
                "expansion_min_range_ratio": 1.2,
                "accumulation_max_range_ratio": 0.7,
                "distribution_min_range_ratio": 1.0,
            },
            "objective_gate": {"enabled": False, "mode": "allow_exists_only"},
        },
    )
    assert ParentCRTFeed.from_prod_config() is None


def test_from_prod_config_rejects_unknown_bias_mode(monkeypatch):
    monkeypatch.setattr(
        "runtime.parent_crt_feed.get_prod_section",
        lambda name: {
            "enabled": True,
            "timeframe": "H4",
            "bias_gate_mode": "warn_only",
        },
    )
    with pytest.raises(ValueError, match="warn_only"):
        ParentCRTFeed.from_prod_config()


def test_unsupported_rule_raises():
    with pytest.raises(ValueError, match="M15"):
        ParentCRTFeed("M15", _THRESH)
