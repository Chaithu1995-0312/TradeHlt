"""CH-htf-state-objective — HTFState classifier (not CRTState)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config_layer.crt_engine_v2 import Candle
from config_layer.htf_state import HTFState, HTFStateThresholds, classify_htf_state
from config_layer.state_identity import CRTState


_T0 = datetime(2026, 1, 1)
_TH = HTFStateThresholds(1.2, 0.7, 1.0)


def _c(i, o, h, l, cl) -> Candle:
    return Candle(
        timestamp=_T0 + timedelta(hours=4 * i),
        open=o, high=h, low=l, close=cl, volume=1.0, index=i,
    )


def test_htf_state_is_a_separate_enum():
    assert HTFState is not CRTState
    assert HTFState.DISTRIBUTION is not CRTState.DISTRIBUTION_C3
    assert HTFState.EXPANSION is not CRTState.EXPANSION
    assert "ACCUMULATION" not in CRTState.__members__
    assert "REVERSAL" not in CRTState.__members__


def test_first_pair_reversal_prev_bull_broke_low():
    prev = _c(0, 100, 110, 100, 108)   # bull
    curr = _c(1, 107, 108, 90, 92)     # close below prev.low
    assert classify_htf_state(prev, curr, _TH) is HTFState.REVERSAL


def test_expansion_breaks_high_with_large_range():
    prev = _c(0, 100, 105, 100, 104)   # range 5
    curr = _c(1, 104, 120, 103, 118)   # range 17, close > prev.high
    assert classify_htf_state(prev, curr, _TH) is HTFState.EXPANSION


def test_accumulation_small_inside():
    prev = _c(0, 100, 120, 100, 110)   # range 20
    curr = _c(1, 108, 112, 107, 111)   # range 5, inside
    assert classify_htf_state(prev, curr, _TH) is HTFState.ACCUMULATION


def test_distribution_large_inside():
    prev = _c(0, 100, 110, 100, 105)   # range 10
    curr = _c(1, 101, 114, 100.5, 104)  # range 13.5, close inside
    assert classify_htf_state(prev, curr, _TH) is HTFState.DISTRIBUTION


def test_thresholds_reject_inverted_cuts():
    with pytest.raises(ValueError, match="accumulation_max"):
        HTFStateThresholds(1.2, 1.5, 1.0)
