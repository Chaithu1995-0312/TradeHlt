"""Floor for the SEM-020 exit-capture decomposition.

Two things are protected here:

  AGREEMENT  the vectorised excursion walk must reproduce the audited scalar
             `forward_walk.horizon_excursion` bar-for-bar. The fast version exists only
             for speed; if it ever disagrees, the ceiling it feeds is measuring something
             other than what the audited kernel measures, and every ceiling downstream is
             quietly wrong.

  ALGEBRA    the identity `reality_gap == mfe_capture - e_gross` must hold exactly (the
             cost term cancels), and a capture ratio above 1 must be COUNTED as a defect
             rather than averaged into a percentile.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.contracts import Signal  # noqa: E402
from research.costs import ComponentCostModel  # noqa: E402
from research.measurement.forward_walk import horizon_excursion  # noqa: E402
from research.oracle.exit_analysis import (  # noqa: E402
    capture_ratios,
    ceiling_block,
    gate_verdict,
    horizon_excursions,
    min_achievable_cost,
    passive_exposure_r,
)


@dataclass
class _Bar:
    high: float
    low: float
    close: float
    index: int
    timestamp: datetime = datetime(2024, 5, 22, 1, 0, 0)


def _corpus(n=400, seed=13):
    rng = np.random.default_rng(seed)
    px = 2000.0 + np.cumsum(rng.normal(0, 1.5, n))
    hi = px + np.abs(rng.normal(0, 0.9, n))
    lo = px - np.abs(rng.normal(0, 0.9, n))
    return np.maximum(hi, px), np.minimum(lo, px), px


def _cost_model():
    return ComponentCostModel(
        half_spread=0.045, commission=0.04, entry_slippage=0.09, stop_slippage=0.09,
        swap_long_per_night=-0.56, swap_short_per_night=0.38,
        instrument="TEST", source="SYNTHETIC", status="MEASURED",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agreement with the audited scalar kernel
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("direction", ["long", "short"])
@pytest.mark.parametrize("horizon", [5, 20, 40])
def test_vectorised_excursions_match_audited_scalar(direction, horizon):
    """THE test that licenses using the fast path at all."""
    high, low, close = _corpus()
    n = close.size
    entry = close.copy()
    exc = horizon_excursions(high, low, entry, horizon=horizon)
    atr = 2.0
    risk = 1.0 * atr

    bars = [_Bar(high=float(high[i]), low=float(low[i]), close=float(close[i]), index=i)
            for i in range(n)]

    checked = 0
    for i in range(0, n - horizon, 7):          # stride to keep the test quick but broad
        sig = Signal(instrument="_", timestamp=bars[i].timestamp, entry_index=i,
                     direction=direction, entry=float(entry[i]),
                     sl_atr_mult=1.0, tp_atr_mult=2.0, atr=atr)
        ref = horizon_excursion(sig, bars[i + 1:], max_forward=horizon)
        # The scalar kernel ROUNDS mfe_r/mae_r to 4dp on return, so agreement is asserted
        # at the precision it actually reports. Comparing raw floats would fail on the
        # rounding alone and say nothing about whether the two walks agree.
        assert round(exc[direction]["mfe"][i] / risk, 4) == pytest.approx(ref["mfe_r"], abs=1e-9)
        assert round(exc[direction]["mae"][i] / risk, 4) == pytest.approx(ref["mae_r"], abs=1e-9)
        checked += 1
    assert checked > 20, f"only {checked} bars compared — test is near-vacuous"


def test_bars_without_a_full_window_are_nan_not_truncated():
    """A short window is a DIFFERENT measurement, not a missing one."""
    high, low, close = _corpus(n=100)
    exc = horizon_excursions(high, low, close.copy(), horizon=40)
    mfe = exc["long"]["mfe"]
    assert np.isfinite(mfe[:60]).all()
    assert np.isnan(mfe[60:]).all()
    assert exc["n_valid"] == 60


def test_excursions_are_sign_clamped_like_the_scalar_version():
    high, low, close = _corpus()
    exc = horizon_excursions(high, low, close.copy(), horizon=20)
    for d in ("long", "short"):
        mfe = exc[d]["mfe"][np.isfinite(exc[d]["mfe"])]
        mae = exc[d]["mae"][np.isfinite(exc[d]["mae"])]
        assert (mfe >= 0).all()
        assert (mae <= 0).all()


def test_long_and_short_excursions_are_mirror_images():
    """Same window, opposite sign: long MFE is short MAE's magnitude, by construction."""
    high, low, close = _corpus()
    exc = horizon_excursions(high, low, close.copy(), horizon=20)
    ok = np.isfinite(exc["long"]["mfe"])
    np.testing.assert_allclose(exc["long"]["mfe"][ok], -exc["short"]["mae"][ok], atol=1e-9)
    np.testing.assert_allclose(exc["long"]["mae"][ok], -exc["short"]["mfe"][ok], atol=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# Ceiling algebra
# ─────────────────────────────────────────────────────────────────────────────
def test_reality_gap_identity_holds_exactly():
    """min_cost cancels, so reality_gap == mfe_capture - e_gross. Asserted, not trusted."""
    rng = np.random.default_rng(3)
    mfe_r = np.abs(rng.normal(1.2, 0.4, 5000))
    gross = rng.normal(-0.1, 0.9, 5000)
    for min_cost in (0.0, 0.04, 0.51):
        b = ceiling_block(mfe_r=mfe_r, realised_gross_r=gross, min_cost=min_cost,
                          exit_object="test", cost_basis="test", tie_break="production")
        assert b["reality_gap"] == pytest.approx(
            b["mfe_capture"] - b["expectancy_gross"], abs=1e-6)


def test_capture_ratio_above_one_is_counted_as_a_defect():
    """A trade cannot realise more than its own favourable excursion."""
    mfe_r = np.array([1.0, 1.0, 1.0, 1.0])
    gross = np.array([0.5, 0.9, 1.5, -1.0])          # 1.5 is impossible
    b = ceiling_block(mfe_r=mfe_r, realised_gross_r=gross, min_cost=0.0,
                      exit_object="t", cost_basis="t", tie_break="production")
    assert b["capture_ratio_violations"] == 1


def test_capture_ratio_undefined_when_no_favourable_excursion():
    """A trade never in profit has no capture to measure; a 0 there would flatter the exit."""
    cr = capture_ratios(np.array([-1.0, 0.5]), np.array([0.0, 1.0]))
    assert np.isnan(cr[0])
    assert cr[1] == pytest.approx(0.5)


def test_regime_is_engineering_when_structural_bound_is_negative():
    mfe_r = np.full(100, 1.0)
    gross = np.full(100, -0.5)
    b = ceiling_block(mfe_r=mfe_r, realised_gross_r=gross, min_cost=0.1,
                      exit_object="t", cost_basis="t", tie_break="production")
    assert b["regime"] == "ENGINEERING"
    assert b["structural_upper_bound"] == pytest.approx(-0.6)
    assert b["exit_axis_open"] is True          # perfect bound 0.9 > 0 even so


def test_gate_closes_when_perfect_foresight_cannot_profit():
    """The Stage-A gate: no room even with foresight means no policy can help."""
    mfe_r = np.full(100, 0.05)
    gross = np.full(100, -0.5)
    b = ceiling_block(mfe_r=mfe_r, realised_gross_r=gross, min_cost=0.4,
                      exit_object="t", cost_basis="t", tie_break="production")
    assert b["exit_axis_open"] is False
    v = gate_verdict({"cell": b})
    assert v["verdict"] == "EXIT_AXIS_CLOSED"


def test_gate_opens_when_any_cell_has_room():
    open_b = ceiling_block(mfe_r=np.full(50, 2.0), realised_gross_r=np.full(50, -0.3),
                           min_cost=0.05, exit_object="t", cost_basis="t",
                           tie_break="production")
    shut_b = ceiling_block(mfe_r=np.full(50, 0.01), realised_gross_r=np.full(50, -0.3),
                           min_cost=0.5, exit_object="t", cost_basis="t",
                           tie_break="production")
    v = gate_verdict({"a": open_b, "b": shut_b})
    assert v["verdict"] == "EXIT_AXIS_OPEN"
    assert v["cells_with_room"] == 1


def test_ceiling_block_requires_its_basis_declarations():
    """A ceiling without its exit object / cost basis is not comparable to anything."""
    with pytest.raises(TypeError):
        ceiling_block(mfe_r=np.ones(3), realised_gross_r=np.zeros(3), min_cost=0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Cost floor and the drift control
# ─────────────────────────────────────────────────────────────────────────────
def test_min_cost_falls_as_the_stop_widens():
    """cost_r is cost_price/risk_distance, so a wider stop dilutes cost in R."""
    cm = _cost_model()
    entry = np.full(500, 2000.0)
    atr = np.full(500, 2.0)
    wide = min_achievable_cost(cm, entry=entry, atr_abs=atr, widest_sl_atr_mult=3.0)
    tight = min_achievable_cost(cm, entry=entry, atr_abs=atr, widest_sl_atr_mult=0.5)
    assert wide < tight
    assert wide == pytest.approx(tight / 6.0, rel=1e-9)


def test_min_cost_uses_the_limit_exit_not_the_stop_exit():
    """The floor must not include stop slippage: a TP exit does not pay it."""
    cm = _cost_model()
    entry, atr = np.full(10, 2000.0), np.full(10, 2.0)
    floor = min_achievable_cost(cm, entry=entry, atr_abs=atr, widest_sl_atr_mult=1.0)
    stop_cost = cm.cost_r(2000.0, 2.0, exit_kind="SL_HIT")
    assert floor < stop_cost


def test_passive_exposure_tracks_drift_with_the_right_sign():
    n = 200
    close = np.arange(n, dtype=float) + 2000.0        # steady uptrend
    entry = close.copy()
    risk = np.full(n, 2.0)
    lng = passive_exposure_r(close, entry, risk, horizon=10, direction="long")
    sht = passive_exposure_r(close, entry, risk, horizon=10, direction="short")
    ok = np.isfinite(lng)
    assert (lng[ok] > 0).all()
    np.testing.assert_allclose(lng[ok], -sht[ok], atol=1e-9)
    assert lng[0] == pytest.approx(10.0 / 2.0)
