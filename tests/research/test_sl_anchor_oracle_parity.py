"""K23 F3 — oracle `sweep_extreme` arm vs the engine's `sl_anchor="sweep_extreme"` stop.

The table (oracle labels) and the strategy (spine) must measure the same trade object
(F-088 class). The oracle anchor is a trailing-N-bar-extreme PROXY, so exact parity is
asserted only where the engine's sweep candle IS that extreme; a negative control pins the
proxy boundary instead of hiding it.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.crt_engine_v2 import (  # noqa: E402
    Candle, CRTState, Direction, EngineState, ExecutionEngine, Range, SweepEvent,
)
from governance.measurement_basis import REF_LEVEL_SWEEP_EXTREME  # noqa: E402
from research.oracle.labeler import (  # noqa: E402
    SL_GEOM_SWEEP_EXTREME, label_corpus, sweep_extreme_stop,
)
from tests.helpers.crt_config import crt_config_for_test  # noqa: E402
from tests.research.test_oracle_labeler import _CRT_CFG, _cost_model, _synthetic  # noqa: E402

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_ATR = 2.0


class _B:  # minimal Bar stand-in
    def __init__(self, high, low):
        self.high, self.low = high, low


def _c(o, h, l, c) -> Candle:
    return Candle(timestamp=_T0, open=o, high=h, low=l, close=c)


def _engine_state(direction: Direction, sweep_low: float, sweep_high: float) -> EngineState:
    st = EngineState()
    st.active_range = Range(h_ref=120.0, l_ref=80.0, equilibrium=100.0,
                            formed_at=_T0, htf_candle_id="H", session="LONDON")
    st.direction = direction
    st.atr_abs = _ATR
    st.sweep_event = SweepEvent(
        direction=direction, price=80.0, candle=_c(85, sweep_high, sweep_low, 84))
    st.displacement_candle = _c(90, 96, 88.0, 95) if direction == Direction.LONG else _c(110, 112, 104, 105)
    st.retest_candle = _c(94, 95, 92, 93) if direction == Direction.LONG else _c(106, 108, 105, 106)
    st.current_state = CRTState.RETEST
    return st


def _engine_sl(direction, sweep_low, sweep_high):
    cfg = crt_config_for_test()
    ex = ExecutionEngine(cfg, sl_anchor="sweep_extreme")
    ex.build_trade(_engine_state(direction, sweep_low, sweep_high), None)
    return cfg, ex.last_build_attempt


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_oracle_stop_equals_engine_stop_when_window_extreme_is_the_sweep_candle(direction):
    cfg, built = _engine_sl(direction, sweep_low=70.0, sweep_high=130.0)
    is_long = direction == Direction.LONG
    # Trailing window whose extreme IS the sweep candle's wick; other bars are inside it.
    window = [_B(high=100.0, low=90.0)] * 5 + [_B(high=130.0, low=70.0)] + [_B(high=100.0, low=90.0)] * 4
    got = sweep_extreme_stop(window, _ATR, cfg.sl_atr_buffer, is_long)
    assert got == pytest.approx(built.computed_sl, abs=1e-12)


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_proxy_boundary_window_extreme_not_the_sweep_candle_differs(direction):
    """Negative control: a deeper extreme in the window than the sweep candle's own wick."""
    cfg, built = _engine_sl(direction, sweep_low=70.0, sweep_high=130.0)
    is_long = direction == Direction.LONG
    window = [_B(high=140.0, low=60.0)] + [_B(high=100.0, low=90.0)] * 9
    got = sweep_extreme_stop(window, _ATR, cfg.sl_atr_buffer, is_long)
    assert got != pytest.approx(built.computed_sl, abs=1e-6)


def test_sweep_extreme_rows_exist_and_carry_the_new_reference_level():
    matrix, raw = _synthetic(n=200)
    labels, stats = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                                 max_forward=40, crt_cfg=_CRT_CFG, sweep_lookback=16)
    sw = labels[labels["sl_geom"] == SL_GEOM_SWEEP_EXTREME]
    assert len(sw) > 0
    assert (sw["reference_level"] == REF_LEVEL_SWEEP_EXTREME).all()
    assert stats["rejects"]["insufficient_sweep_lookback"] == 15 * 2  # p<15, both directions


def test_sweep_extreme_sl_matches_trailing_window_and_is_never_tighter_than_disp_bar():
    matrix, raw = _synthetic(n=200)
    labels, _ = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                             max_forward=40, crt_cfg=_CRT_CFG, sweep_lookback=16)
    buf = 0.2
    sw = labels[(labels["sl_geom"] == SL_GEOM_SWEEP_EXTREME) & (labels["tie_break"] == "production")]
    for _, r in sw.sample(30, random_state=5).iterrows():
        p = int(r["_pos"])
        win = raw[(raw["_pos"] > p - 16) & (raw["_pos"] <= p)]
        want = (win["low"].min() - buf * _ATR) if r["direction"] == "long" else (
            win["high"].max() + buf * _ATR)
        assert r["sl"] == pytest.approx(want, abs=1e-9)
        disp = labels[(labels["_pos"] == p) & (labels["direction"] == r["direction"])
                      & (labels["sl_geom"] == "disp_bar") & (labels["tie_break"] == "production")]
        if len(disp):
            d = disp.iloc[0]
            assert (r["sl"] <= d["sl"] + 1e-9) if r["direction"] == "long" else (r["sl"] >= d["sl"] - 1e-9)


def test_legacy_arms_are_byte_identical_with_and_without_the_new_arm():
    matrix, raw = _synthetic(n=200)
    kw = dict(cost_model=_cost_model(), adverse_fill=None, max_forward=40, crt_cfg=_CRT_CFG)
    legacy, _ = label_corpus(matrix, raw, **kw)
    with_arm, _ = label_corpus(matrix, raw, sweep_lookback=16, **kw)
    keep = with_arm[with_arm["sl_geom"] != SL_GEOM_SWEEP_EXTREME].reset_index(drop=True)
    pd.testing.assert_frame_equal(legacy.reset_index(drop=True), keep)


def test_invalid_lookback_rejected():
    matrix, raw = _synthetic(n=60)
    with pytest.raises(ValueError, match="sweep_lookback"):
        label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                     crt_cfg=_CRT_CFG, sweep_lookback=0)


def test_backtest_reference_level_follows_sl_anchor():
    import runtime.backtest_v2 as b
    from governance.measurement_basis import REFERENCE_LEVELS
    assert set(b.SL_ANCHOR_REFERENCE_LEVEL.values()) <= REFERENCE_LEVELS
    assert b.SL_ANCHOR_REFERENCE_LEVEL["displacement"] == b.BACKTEST_REFERENCE_LEVEL
    assert b.SL_ANCHOR_REFERENCE_LEVEL["sweep_extreme"] == REF_LEVEL_SWEEP_EXTREME
