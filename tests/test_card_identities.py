"""CH-card-identity-census-v9: the card sentences that had no formula.

morning_star is candle geometry (slot 71). higher_low / lower_high / sideways are
swing-sequence states (slots 72-74), not the FM-055/FM-056 pierce events.
The rejection block is the live wick of a confirmed causal swing (slots 75-78).
wait_for_next_candle and the 1:3 bracket are identities and are not vector slots.
Pattern flags stay observations. The live gate min_rr_ratio stays 1.5.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from config_layer.crt_engine_v2 import Candle
from features import candle_patterns as cp
from features.confirmation_state import (
    LONG_ARM, SHORT_ARM, armed_setups, wait_for_next_candle, wait_for_next_series,
)
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
from features.registry import FORMULA_REGISTRY
from features.reward_bracket import reward_risk_clears
from features.smc.rejection import (
    find_live_rejection_blocks, rejection_bear_distance, rejection_bull_distance,
)
from features.structure_sequence import swing_sequence_states

ROOT = Path(__file__).resolve().parents[1]
P = cp.CandlePatternParams(
    size_gate_atr_k=0.5, swing_lookback=5, pin_wick_min=0.60, pin_body_max=0.25,
    pin_opposite_wick_max=0.15, probe_wick_body_multiple=2.0, probe_opposite_wick_max=0.10,
    doji_body_max=0.10, doji_wick_asymmetry_max=0.20, doji_extreme_body_max=0.05,
    doji_extreme_wick_min=0.75, engulfing_strength_cap=3.0, compression_ratio_cap=10.0,
    morning_star_body_min=0.6, morning_star_mid_max=0.25,
)


def _c(i, o, h, l, cl) -> Candle:
    return Candle(
        timestamp=datetime(2026, 8, 3) + timedelta(minutes=15 * i),
        open=o, high=h, low=l, close=cl, volume=1.0, index=i,
    )


def test_morning_star_is_shape_only():
    # big bearish, small middle, big bullish
    assert cp.morning_star(
        10, 10.2, 8.8, 9,  9, 9.2, 8.9, 9.05,  9, 10.2, 8.8, 10,
        True, True, P,
    )
    assert not cp.morning_star(
        10, 10.2, 8.8, 9,  9, 9.2, 8.9, 9.05,  9, 10.2, 8.8, 10,
        True, False, P,
    )
    # zero-range middle has body_ratio 0 and counts as small
    assert cp.morning_star(
        10, 10.2, 8.8, 9,  9, 9, 9, 9,  9, 10.2, 8.8, 10,
        True, True, P,
    )
    # zero-range third fails "big"
    assert not cp.morning_star(
        10, 10.2, 8.8, 9,  9, 9.2, 8.9, 9.05,  9, 9, 9, 9,
        True, True, P,
    )
    assert "trend" not in cp.morning_star.__code__.co_varnames
    assert not hasattr(cp, "evening_star")
    assert "evening_star" not in CANONICAL_FEATURES


def test_sequence_states_persist_and_do_not_invent_sideways():
    # confirmation bars: high at 2 then 6, low at 3 then 7
    sh = np.array([0, 0, 1, 0, 0, 0, 1, 0], dtype=np.int8)
    sl = np.array([0, 0, 0, 1, 0, 0, 0, 1], dtype=np.int8)
    last_h = np.array([np.nan, np.nan, 20, 20, 20, 20, 25, 25], dtype=float)
    last_l = np.array([np.nan, np.nan, np.nan, 10, 10, 10, 10, 8], dtype=float)
    hl, lh, side = swing_sequence_states(sh, sl, last_h, last_l)
    assert hl.tolist() == [0, 0, 0, 0, 0, 0, 0, 0]
    assert lh.tolist() == [0, 0, 0, 0, 0, 0, 0, 0]
    # unknown until both pairs exist; the expanding pair (HH + LL) is sideways
    assert side.tolist() == [0, 0, 0, 0, 0, 0, 0, 1]
    # equals are not higher
    last_l_eq = last_l.copy()
    last_l_eq[7] = 10
    hl_eq, _, side_eq = swing_sequence_states(sh, sl, last_h, last_l_eq)
    assert hl_eq[7] == 0 and side_eq[7] == 1
    # a real higher low persists after the confirmation bar
    last_l_up = last_l.copy()
    last_l_up[7] = 12
    sl_hold = np.array([0, 0, 0, 1, 0, 0, 0, 1, 0], dtype=np.int8)
    sh_hold = np.array([0, 0, 1, 0, 0, 0, 1, 0, 0], dtype=np.int8)
    last_h_hold = np.array([np.nan, np.nan, 20, 20, 20, 20, 25, 25, 25], dtype=float)
    last_l_hold = np.array([np.nan, np.nan, np.nan, 10, 10, 10, 10, 12, 12], dtype=float)
    hl_up, lh_up, side_up = swing_sequence_states(sh_hold, sl_hold, last_h_hold, last_l_hold)
    assert hl_up.tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 1]
    assert lh_up[-1] == 0 and side_up[-1] == 0
    with pytest.raises(ValueError):
        swing_sequence_states(sh, sl[:-1], last_h, last_l)


def test_rejection_block_lives_at_confirmation_and_dies_on_a_retest():
    # k=2, pivot index 2, confirmation when the window includes bar 4.
    # highs stay under 110. Bar 0's low keeps this from also being the swing low.
    base = [
        _c(0, 100, 101, 90, 100),
        _c(1, 100, 102, 99, 101),
        _c(2, 104, 110, 103, 106),
        _c(3, 105, 107, 104, 106),
        _c(4, 105, 108, 104, 107),
    ]
    bull, bear = find_live_rejection_blocks(base, 2)
    assert bull is None
    assert bear is not None and bear.bullish is False
    assert bear.low == pytest.approx(106) and bear.high == pytest.approx(110)
    assert bear.formed_at_index == 2
    # a later high into the wick kills it; a high that stops short of the body top does not
    kept = base + [_c(5, 105, 105.5, 104, 105)]
    assert find_live_rejection_blocks(kept, 2)[1] is not None
    dropped = base + [_c(5, 105, 106.5, 104, 105)]
    assert find_live_rejection_blocks(dropped, 2)[1] is None
    closed = base + [_c(5, 108, 112, 107, 111)]
    assert find_live_rejection_blocks(closed, 2)[1] is None
    assert rejection_bear_distance(closed, 2, 1.0) == 0.0
    # bullish mirror: lower wick of a swing low, live at confirmation
    bull_win = [
        _c(0, 100, 108, 99, 101),
        _c(1, 101, 107, 100, 102),
        _c(2, 100, 101, 90, 98),
        _c(3, 99, 102, 98, 100),
        _c(4, 99, 103, 98, 101),
    ]
    bull2, bear2 = find_live_rejection_blocks(bull_win, 2)
    assert bear2 is None and bull2 is not None and bull2.bullish is True
    assert bull2.low == pytest.approx(90) and bull2.high == pytest.approx(98)
    assert rejection_bull_distance(base, 2, 1.0) == 0.0


def test_wait_for_next_candle_is_the_following_bar():
    assert "doji_material" not in LONG_ARM and "doji_material" not in SHORT_ARM
    flags = {name: False for name in LONG_ARM + SHORT_ARM}
    flags["doji_material"] = True
    assert armed_setups(flags) == (False, False)
    flags["hammer"] = True
    assert armed_setups(flags) == (True, False)
    # the bar that prints the pattern is not the entry
    assert wait_for_next_candle(False, False, True, 10, 11) == 0
    assert wait_for_next_candle(True, False, True, 10, 11) == 1
    assert wait_for_next_candle(True, False, False, 10, 11) == 0   # gap expires
    assert wait_for_next_candle(True, True, True, 10, 10) == 0     # close == open
    assert wait_for_next_candle(True, True, True, 10, 11) == 1     # close side wins
    assert wait_for_next_candle(True, True, True, 11, 10) == -1
    series = wait_for_next_series(
        [1, 0, 0], [0, 0, 1], [False, True, False], [10, 10, 10], [10, 11, 9],
    )
    assert series.tolist() == [0, 1, 0]


def test_reward_bracket_requires_a_multiple_and_is_not_the_live_gate():
    with pytest.raises(TypeError):
        reward_risk_clears(100, 99, 103)
    assert reward_risk_clears(100, 99, 103, 3) is True
    assert reward_risk_clears(100, 99, 101.5, 3) is False
    assert reward_risk_clears(100, 100, 103, 3) is False
    cfg = json.loads(
        (ROOT / "configs" / "production" / "v2_htfcrt_2026_08.json").read_text(encoding="utf-8")
    )
    assert cfg["ultron_risk_gate"]["min_rr_ratio"] == 1.5


def test_registry_and_vector_split():
    for name in (
        "features.candle_patterns.morning_star",
        "features.smc.rejection.rejection_bull_present",
        "features.smc.rejection.rejection_bear_present",
        "features.smc.rejection.rejection_bull_distance",
        "features.smc.rejection.rejection_bear_distance",
        "features.reward_bracket.reward_risk_clears",
    ):
        assert name in FORMULA_REGISTRY
    assert "features.structure_sequence.swing_sequence_states" not in FORMULA_REGISTRY
    assert "features.confirmation_state.wait_for_next_candle" not in FORMULA_REGISTRY
    assert CANONICAL_FEATURE_DIM == 79
    assert CANONICAL_FEATURES[71:] == (
        "morning_star", "higher_low", "lower_high", "sideways",
        "rejection_bull_present", "rejection_bear_present",
        "rejection_bull_distance", "rejection_bear_distance",
    )
    assert "wait_for_next_candle" not in CANONICAL_FEATURES
    assert "reward_risk_bracket" not in CANONICAL_FEATURES


def test_pipeline_tail_is_finite():
    from features.feature_pipeline import FeaturePipeline
    n = 220
    rng = np.random.default_rng(3)
    close = 2000 + np.cumsum(rng.normal(0, 0.4, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.3
    low = np.minimum(open_, close) - 0.3
    ts = [datetime(2026, 3, 23) + timedelta(minutes=15 * i) for i in range(n)]
    import pandas as pd
    df = pd.DataFrame({
        "timestamp": ts, "open": open_, "high": high, "low": low, "close": close,
        "volume": np.full(n, 10.0),
    })
    out, vectors = FeaturePipeline(df).run()
    assert vectors.shape[1] == 79
    tail = (
        "morning_star", "higher_low", "lower_high", "sideways",
        "rejection_bull_present", "rejection_bear_present",
        "rejection_bull_distance", "rejection_bear_distance",
    )
    for name in tail:
        assert name in out.columns
        assert np.isfinite(out[name].to_numpy()).all()
