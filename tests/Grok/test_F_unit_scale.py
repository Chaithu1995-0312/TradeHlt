"""F. Unit / scale mismatches — relative ATR, absolute ATR, price, RR, range.

Semantic invariant: a quantity used as a *price offset* must be in price units.
Feeding FM-041 (close-relative ATR ≈ 0.002) into an SL formula that expects
atr_abs (≈ 9.5 on XAUUSD) collapses the buffer. Ordinary tests use one scale.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from config_layer.crt_engine_v2 import Range, RangeDetector
from config_layer.state_identity import CRTConfig, Direction

from tests.Grok._fixtures import candle, engine_ready_short, executor


def test_relative_atr_as_sl_operand_is_not_a_protective_buffer():
    """Extreme scale: feat_atr=0.002521 (proof SHORT) vs atr_abs=9.562143.

    Source: operands.csv + proof_*_SHORT_A3.md feature row
    Failure mode: `sl = disp_high + 0.2 * feat_atr` ≈ disp_high.
    """
    disp_high = 4146.75
    feat_atr = 0.002521
    atr_abs = 9.562143
    sl_wrong = disp_high + 0.2 * feat_atr
    sl_right = disp_high + 0.2 * atr_abs
    assert sl_wrong == pytest.approx(disp_high, abs=1e-2)
    assert sl_right - disp_high == pytest.approx(1.9124286, abs=1e-6)
    assert sl_right - sl_wrong > 1.0


def test_price_scaled_momentum_is_not_a_z_score():
    """momentum_score / ema_spread in the thousands are price/ATR-relative, not σ.

    Source: feature formula in episode ledgers: close_delta / atr
    On XAUUSD, |momentum_score| ~ 10^3 is expected (F-060/F-061 class).
    """
    # synthetic: Δclose=5, relative atr=0.002 → score = 2500
    close_delta = 5.0
    rel_atr = 0.002
    score = close_delta / rel_atr
    assert score == pytest.approx(2500.0)
    assert abs(score) > 10.0  # cannot be a typical z-score


def test_range_size_is_price_not_percent():
    rng = Range(
        h_ref=4156.03,
        l_ref=4107.15,
        equilibrium=4131.59,
        formed_at=datetime(2026, 7, 22, 16, 45, 0),
        htf_candle_id="XAUUSD-HTF-000016",
    )
    assert rng.size == pytest.approx(48.88)
    pct = rng.size / rng.equilibrium
    assert pct < 0.05  # ~1.2%, not 48.88
    assert rng.size != pytest.approx(pct)


def test_rr_on_inverted_geometry_is_never_computed():
    """When build_trade returns None, TP/RR do not exist — do not infer them.

    Source: build_trade returns before risk_dist / tp1 / tp2 (crt_engine_v2.py:2254)
    """
    trade = executor().build_trade(engine_ready_short())
    assert trade is None


def test_body_size_vs_candle_range_are_not_interchangeable():
    """body_size (FM-009) ≠ wick_size/candle_range (FM-002) on the CRT Candle.

    Source: Candle.body_size / Candle.wick_size
    """
    c = candle(datetime(2026, 1, 1, 0, 0, 0), 100, 120, 80, 110)
    assert c.body_size == pytest.approx(10.0)
    assert c.wick_size == pytest.approx(40.0)
    assert c.body_ratio == pytest.approx(0.25)
    assert c.body_size != c.wick_size


def test_hundred_x_price_scale_blows_relative_formula_if_abs_expected():
    """Deliberate 100× price shift: absolute ATR scales; relative should not.

    If a consumer multiplies sl_atr_buffer * (atr_rel) * close they get the
    absolute buffer; if they forget `* close` the buffer vanishes at high prices.
    """
    det = RangeDetector(CRTConfig())

    def series(px: float):
        return [
            candle(datetime(2026, 1, 1, 0, i, 0), px, px + 1, px - 1, px, idx=i)
            for i in range(16)
        ]

    a1 = det.compute_atr(series(100.0), 14)
    a2 = det.compute_atr(series(10000.0), 14)
    # true range is 2.0 on both (high-low=2, prev close equal) → ATR identical
    assert a1 == pytest.approx(a2)
    rel1 = a1 / 100.0
    rel2 = a2 / 10000.0
    assert rel1 / rel2 == pytest.approx(100.0)
    # feeding rel2 into an SL that expects a1 understates the buffer 100×
    assert (0.2 * rel2) * 100 == pytest.approx(0.2 * rel1)
    assert 0.2 * rel2 != pytest.approx(0.2 * a1)


def test_long_retrace_depth_uses_range_size_not_atr():
    """Range.retrace_depth is a fraction of range.size, not of ATR.

    Source: Range.retrace_depth
    """
    rng = Range(
        h_ref=110.0,
        l_ref=100.0,
        equilibrium=105.0,
        formed_at=datetime(2026, 1, 1, 0, 0, 0),
        htf_candle_id="T",
    )
    # LONG: (price - l_ref) / size
    assert rng.retrace_depth(102.0, Direction.LONG) == pytest.approx(0.2)
    assert rng.retrace_depth(102.0, Direction.SHORT) == pytest.approx(0.8)
