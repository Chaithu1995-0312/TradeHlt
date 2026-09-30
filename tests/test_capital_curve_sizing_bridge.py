"""
test_capital_curve_sizing_bridge.py
====================================
D11 (2026-09-30): backtest_v2.CapitalCurve is a THIRD, independent sizing rail
(F-103 — it never calls UltronRiskGate). This covers its own sizing-bridge wiring
directly: a real end-to-end backtest run cannot exercise it on XAUUSD right now
because of a pre-existing, unrelated bug (direction never reaches EngineRunner on
the backtest path — see assistant_project.md 2026-09-30, task_d0134aa6, deferred
separately by user decision), so CapitalCurve is tested in isolation here instead.
"""

from __future__ import annotations

import pytest

from runtime.backtest_v2 import CapitalCurve

_XAUUSD_SPEC = {"contract_size": 100.0, "lot_step": 0.01, "lot_min": 0.01, "lot_max": 10.0}
_RATE = 84.0


# ── Declared instrument: honest INR/lots conversion ──────────────────────────────

def test_declared_instrument_uses_lots_inr_basis():
    cap = CapitalCurve(
        initial_capital=100_000.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC}, usd_inr_rate=_RATE,
    )
    assert cap.sizing_basis == "lots_inr"

def test_declared_instrument_position_size_is_lots_not_ounces():
    """Same worked example as test_position_sizing.py's plan example: expect 0.01 lots,
    NOT the pre-D11 ~1.18 oz."""
    cap = CapitalCurve(
        initial_capital=100_000.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC}, usd_inr_rate=_RATE,
    )
    size = cap.position_size(entry=2600.0, sl=2594.9649, pip_size=0.01)
    assert size == pytest.approx(0.01)

def test_declared_instrument_apply_trade_books_honest_inr():
    """A $2/oz favourable move on 0.01 lots books 2*100*0.01*84 = 168 INR, not $2."""
    cap = CapitalCurve(
        initial_capital=100_000.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC}, usd_inr_rate=_RATE,
    )
    new_capital = cap.apply_trade(pnl_per_unit=2.0, position_size=0.01)
    assert new_capital == pytest.approx(100_000.0 + 168.0)
    assert cap.current_capital == pytest.approx(100_168.0)

def test_declared_instrument_losing_trade_reduces_capital_honestly():
    cap = CapitalCurve(
        initial_capital=100_000.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC}, usd_inr_rate=_RATE,
    )
    new_capital = cap.apply_trade(pnl_per_unit=-5.0351, position_size=0.01)
    assert new_capital == pytest.approx(100_000.0 - 5.0351 * 100.0 * 0.01 * _RATE)


# ── Undeclared instrument: pre-D11 legacy math, byte-identical ──────────────────

def test_undeclared_instrument_keeps_legacy_ounce_basis():
    cap = CapitalCurve(initial_capital=10_000.0, risk_pct=0.005, compounding=False,
                        instrument="EURUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC},
                        usd_inr_rate=_RATE)
    assert cap.sizing_basis == "legacy_oz"

def test_undeclared_instrument_position_size_is_plain_division():
    """Pre-D11 math: current_risk_amount / risk_distance, unchanged."""
    cap = CapitalCurve(initial_capital=10_000.0, risk_pct=0.005, compounding=False,
                        instrument="EURUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC},
                        usd_inr_rate=_RATE)
    size = cap.position_size(entry=1.10, sl=1.098, pip_size=0.0001)
    # current_risk_amount = 10000 * 0.005 = 50; risk_distance = 0.002 -> 25000
    assert size == pytest.approx(50.0 / 0.002)

def test_undeclared_instrument_apply_trade_is_plain_multiplication():
    cap = CapitalCurve(initial_capital=10_000.0, risk_pct=0.005, compounding=False,
                        instrument="EURUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC},
                        usd_inr_rate=_RATE)
    new_capital = cap.apply_trade(pnl_per_unit=0.002, position_size=25_000.0)
    assert new_capital == pytest.approx(10_000.0 + 0.002 * 25_000.0)

def test_no_instrument_specs_at_all_keeps_legacy_basis():
    """No instrument_specs / usd_inr_rate passed at all (e.g. an older config) ->
    legacy math, same as before D11 -- not a crash."""
    cap = CapitalCurve(initial_capital=10_000.0, risk_pct=0.005, compounding=False)
    assert cap.sizing_basis == "legacy_oz"
    assert cap.position_size(entry=100.0, sl=98.0, pip_size=0.0001) == pytest.approx(25.0)


# ── Zero-distance guard unaffected by the sizing basis ───────────────────────────

def test_zero_risk_distance_returns_zero_regardless_of_basis():
    cap = CapitalCurve(
        initial_capital=100_000.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": _XAUUSD_SPEC}, usd_inr_rate=_RATE,
    )
    assert cap.position_size(entry=2600.0, sl=2600.0, pip_size=0.01) == 0.0


# ── Below-min-lot on the declared rail: 0.0, never rounded up ───────────────────

def test_declared_instrument_below_min_lot_returns_zero():
    tiny_spec = {"contract_size": 100.0, "lot_step": 0.01, "lot_min": 1.0, "lot_max": 10.0}
    cap = CapitalCurve(
        initial_capital=4.0, risk_pct=0.005, compounding=False,
        instrument="XAUUSD", instrument_specs={"XAUUSD": tiny_spec}, usd_inr_rate=_RATE,
    )
    assert cap.position_size(entry=100.0, sl=98.0, pip_size=0.01) == 0.0
