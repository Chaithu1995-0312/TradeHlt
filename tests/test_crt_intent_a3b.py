"""EPIC-84 A3b: the CRT engine supplies its trade-intent inputs; pullback is direction-aware."""
from datetime import datetime

import numpy as np
import pytest

from config_layer.crt_engine_v2 import (
    Candle, CRTState, Direction, EngineState, ExecutionEngine, Range, StateMachine, SweepEvent,
)
from features.bar_feature_frame import BAR_FEATURE_KEYS, BarFeatureFrame
from features.feature_schema import FEATURE_INDEX_MAP
from tests.helpers.crt_config import bar_features_for_test, crt_config_for_test

_BASE = {
    "displacement_retrace": 0.5, "displacement_atr_ratio": 1.0, "body_ratio": 0.5,
    "double_sweep": False, "sweep_detected": False, "candles_since_sweep": 3,
    "momentum_score": 0.0,
}


def _intent(direction, **kw):
    return ExecutionEngine._derive_trade_intent({**_BASE, **kw}, 1.5, direction)


@pytest.mark.parametrize("key", ExecutionEngine.INTENT_INPUT_KEYS)
def test_every_intent_input_is_required(key):
    inputs = dict(_BASE)
    inputs.pop(key)
    with pytest.raises(KeyError):
        ExecutionEngine._derive_trade_intent(inputs, 1.5, Direction.LONG)


def test_direction_must_be_long_or_short():
    with pytest.raises(ValueError):
        ExecutionEngine._derive_trade_intent(dict(_BASE), 1.5, Direction.NONE)


def test_pullback_is_direction_aware():
    assert _intent(Direction.LONG, momentum_score=0.4) == "pullback"
    assert _intent(Direction.SHORT, momentum_score=-0.4) == "pullback"
    # momentum against the trade is not a pullback confirmation
    assert _intent(Direction.SHORT, momentum_score=0.4) == "reversal"
    assert _intent(Direction.LONG, momentum_score=-0.4) == "reversal"
    # outside the 0.3..0.7 retrace or too long since the sweep
    assert _intent(Direction.LONG, momentum_score=0.4, displacement_retrace=0.9) == "reversal"
    assert _intent(Direction.LONG, momentum_score=0.4, candles_since_sweep=6) == "reversal"


def test_liq_sweep_from_the_bar_feature():
    assert _intent(Direction.LONG, sweep_detected=True) == "liq_sweep"
    assert _intent(Direction.SHORT, double_sweep=True) == "liq_sweep"


def test_old_fallback_values_still_give_reversal():
    """bar_features_for_test() declares the values the removed fallbacks supplied."""
    bf = bar_features_for_test()
    inputs = {**_BASE, **bf, "sweep_detected": bool(bf["sweep_detected"])}
    assert ExecutionEngine._derive_trade_intent(inputs, 1.5, Direction.LONG) == "reversal"


def _retest_state(bar_features):
    st = EngineState()
    st.bar_features = bar_features
    st.current_state = CRTState.EXPANSION
    st.direction = Direction.LONG
    st.atr_abs = 10.0
    st.active_range = Range(h_ref=120.0, l_ref=100.0, equilibrium=110.0,
                            formed_at=datetime(2024, 1, 1), htf_candle_id="T", session="LONDON")
    st.displacement_candle = Candle(timestamp=datetime(2024, 1, 1, 12), open=100, high=112,
                                    low=99, close=110, volume=1, index=5)
    st.sweep_event = SweepEvent(
        candle=Candle(timestamp=datetime(2024, 1, 1, 11), open=101, high=101, low=99.5,
                      close=100.5, volume=1, index=4),
        price=99.5, direction=Direction.LONG, candle_index=4, double_confirmed=False)
    st.current_candle_index = 10
    retest = Candle(timestamp=datetime(2024, 1, 1, 13), open=102, high=103, low=100.5,
                    close=101.5, volume=1, index=10)
    return st, retest


def _sm():
    return StateMachine(crt_config_for_test(
        retest_min_depth_atr_fraction=0.10, retest_depth_max=1.0,
        retest_atr_depth_fraction=1.0, max_displacement_strength=10.0))


def test_retest_without_bar_features_is_rejected():
    st, retest = _retest_state(None)
    assert _sm().try_expansion_to_retest(st, retest, 10.0) is False
    assert st.retest_candle is None


def test_retest_caches_the_three_bar_features():
    st, retest = _retest_state(bar_features_for_test(sweep_detected=1, candles_since_sweep=2,
                                                     momentum_score=0.25))
    assert _sm().try_expansion_to_retest(st, retest, 10.0) is True
    assert st.cached_features["sweep_detected"] is True
    assert st.cached_features["candles_since_sweep"] == 2
    assert st.cached_features["momentum_score"] == pytest.approx(0.25)


def test_bar_feature_frame_reads_the_canonical_slots():
    n = max(FEATURE_INDEX_MAP.values()) + 1
    vectors = np.zeros((2, n), dtype=float)
    vectors[1, FEATURE_INDEX_MAP["sweep_detected"]] = 1
    vectors[1, FEATURE_INDEX_MAP["candles_since_sweep"]] = 4
    vectors[1, FEATURE_INDEX_MAP["momentum_score"]] = -0.3
    frame = BarFeatureFrame(vectors, {"2024-01-01 00:00:00": 0, "2024-01-01 00:15:00": 1})
    c = Candle(timestamp=datetime(2024, 1, 1, 0, 15), open=1, high=1, low=1, close=1, volume=1)
    got = frame.for_candle(c)
    assert set(got) == set(BAR_FEATURE_KEYS)
    assert (got["sweep_detected"], got["candles_since_sweep"], got["momentum_score"]) == (1, 4, -0.3)
    missing = Candle(timestamp=datetime(2024, 1, 2), open=1, high=1, low=1, close=1, volume=1)
    assert frame.for_candle(missing) is None
