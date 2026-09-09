"""Identity split: M15 structural liquidity range vs HTFBuilder clock vs ParentRange."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config_layer.crt_engine_v2 import Candle, Range, RangeDetector
from config_layer.m15_structural_range import (
    CANONICAL_NAME,
    DISPLAY_NAME,
    OBJECT_ID,
    SEMANTIC_NODE_ID,
    M15StructuralLiquidityRange,
    from_child_window,
)
from config_layer.parent_crt import ParentRange
from runtime.backtest_v2 import HTFBuilder

_T0 = datetime(2026, 7, 7, 1, 0, tzinfo=timezone.utc)


def _c(i: int, h: float, l: float) -> Candle:
    mid = (h + l) / 2
    return Candle(
        timestamp=_T0 + timedelta(minutes=15 * i),
        open=mid,
        high=h,
        low=l,
        close=mid,
        index=i,
    )


def test_range_alias_is_the_named_object():
    assert Range is M15StructuralLiquidityRange
    rng = Range(
        h_ref=110.0,
        l_ref=100.0,
        equilibrium=105.0,
        formed_at=_T0,
        htf_candle_id="XAUUSD-HTF-000001",
    )
    assert isinstance(rng, M15StructuralLiquidityRange)
    assert rng.clock_id == "XAUUSD-HTF-000001"
    assert rng.clock_id == rng.htf_candle_id
    assert rng.object_id == OBJECT_ID
    assert OBJECT_ID == "M15-SLR"
    assert CANONICAL_NAME == "M15_STRUCTURAL_LIQUIDITY_RANGE"
    assert DISPLAY_NAME == "M15 structural liquidity range"
    assert SEMANTIC_NODE_ID == "SEM-011"


def test_from_child_window_matches_max_high_min_low():
    kids = [_c(0, 10.0, 8.0), _c(1, 12.0, 7.5), _c(2, 11.0, 9.0)]
    rng = from_child_window(kids, clock_id="CLK-1", session="LONDON")
    assert rng.h_ref == 12.0
    assert rng.l_ref == 7.5
    assert rng.equilibrium == (12.0 + 7.5) / 2
    assert rng.child_count == 3
    assert rng.clock_id == "CLK-1"
    assert rng.session == "LONDON"


def test_detect_legacy_name_is_same_object():
    det = RangeDetector(config=None)  # type: ignore[arg-type]
    det.config = type("C", (), {})()
    kids = [_c(0, 5.0, 1.0), _c(1, 6.0, 2.0)]
    a = det.detect_m15_structural_range(kids, "CLK-2")
    b = det.detect_htf_range(kids, "CLK-2")
    assert type(a) is M15StructuralLiquidityRange
    assert type(b) is M15StructuralLiquidityRange
    assert (a.h_ref, a.l_ref, a.clock_id) == (b.h_ref, b.l_ref, b.clock_id) == (6.0, 1.0, "CLK-2")


def test_htf_builder_is_not_the_range_type():
    htf = HTFBuilder(16, "XAUUSD")
    assert not isinstance(htf, M15StructuralLiquidityRange)
    assert not hasattr(htf, "h_ref")


def test_parent_range_is_a_different_type():
    parent = ParentRange(h_ref=200.0, l_ref=100.0, formed_at_index=0)
    assert type(parent) is not M15StructuralLiquidityRange
    assert not isinstance(parent, M15StructuralLiquidityRange)
