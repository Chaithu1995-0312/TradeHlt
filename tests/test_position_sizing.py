"""
test_position_sizing.py
========================
Dedicated test suite for core.position_sizing — the D11 sizing bridge (2026-09-30):
the ONE place an INR risk budget becomes a broker-legal LOT size. UltronRiskGate's
final_position_size, live_engine_hook's position_size_hint, and backtest_v2's
CapitalCurve all route through size_trade_lots(); this file covers that arithmetic
directly. Its wiring INTO each of those three callers is covered in their own suites
(tests/test_ultron_risk_gate.py section 8b, etc.) — not repeated here.
"""

from __future__ import annotations

import pytest

from config_layer.strict_config import ConfigKeyMissingError
from core.position_sizing import (
    REASON_SIZE_BELOW_MIN_LOT,
    floor_to_lot_step,
    has_instrument_spec,
    instrument_spec,
    legacy_oz_size_units,
    size_trade_lots,
    usd_quote_pnl_inr,
)

# Measured XAUUSD broker facts (results/research/xauusd_mt5_cost_calibration/swap_LATEST.json
# for contract_size; lot_min/lot_max mirror live_integration.mt5 on the active config).
_XAUUSD_SPEC = {"contract_size": 100.0, "lot_step": 0.01, "lot_min": 0.01, "lot_max": 10.0}
_RATE = 84.0  # capital_management.usd_to_inr_rate on the active config


# ── floor_to_lot_step ────────────────────────────────────────────────────────────

def test_floor_to_lot_step_exact_multiple():
    assert floor_to_lot_step(0.05, 0.01) == pytest.approx(0.05)

def test_floor_to_lot_step_truncates_never_rounds():
    """0.0299 at a 0.01 step floors to 0.02, never rounds to 0.03."""
    assert floor_to_lot_step(0.0299, 0.01) == pytest.approx(0.02)

def test_floor_to_lot_step_below_one_step():
    assert floor_to_lot_step(0.005, 0.01) == pytest.approx(0.0)


# ── size_trade_lots — the worked example from the approved plan ─────────────────

def test_worked_example_1l_capital_half_pct_risk():
    """₹1L capital, 0.5% risk, XAUUSD stop-distance case (plan's own worked example).

    risk_capital_inr = 100_000 * 0.005 = 500
    risk_usd         = 500 / 84.0      = 5.952380952380...
    price_risk_distance chosen so size_units = risk_usd / distance is illustrative;
    this test pins the exact closed-form result rather than the plan's rough estimate.
    """
    risk_capital_inr = 100_000.0 * 0.005
    distance = 5.0351  # USD/oz — matches ultron_risk_gate.py's own __main__ example
    lots, reason = size_trade_lots(
        risk_capital_inr, _RATE, distance,
        _XAUUSD_SPEC["contract_size"], _XAUUSD_SPEC["lot_step"],
        _XAUUSD_SPEC["lot_min"], _XAUUSD_SPEC["lot_max"],
    )
    assert reason is None
    # risk_usd=5.95238..., size_units=1.18219 oz, /100 contract = 0.0118219 lots,
    # floored to the 0.01 step -> 0.01.
    assert lots == pytest.approx(0.01)

def test_size_trade_lots_floors_to_step_not_rounds():
    """A size that would round UP to the next step must NOT be rounded up."""
    # size_units/contract_size = 0.0199 lots at a 0.01 step -> floors to 0.01, not 0.02.
    risk_capital_inr = 0.0199 * 100.0 * _RATE  # reverse-engineered to hit 0.0199 exactly
    lots, reason = size_trade_lots(
        risk_capital_inr, _RATE, 1.0,
        100.0, 0.01, 0.01, 10.0,
    )
    assert reason is None
    assert lots == pytest.approx(0.01)

def test_size_trade_lots_rejects_below_min_never_rounds_up():
    """A budget too small for even lot_min -> reject, never a rounded-up risk."""
    lots, reason = size_trade_lots(
        1.0, _RATE, 5.0,   # tiny INR budget
        100.0, 0.01, 0.01, 10.0,
    )
    assert lots is None
    assert reason == REASON_SIZE_BELOW_MIN_LOT

def test_size_trade_lots_clamps_to_lot_max():
    """An oversized risk budget clamps to lot_max, does not exceed the broker cap."""
    lots, reason = size_trade_lots(
        1_000_000_000.0, _RATE, 1.0,   # absurdly large budget
        100.0, 0.01, 0.01, 10.0,
    )
    assert reason is None
    assert lots == pytest.approx(10.0)

def test_size_trade_lots_exactly_at_min_lot_approves():
    """A size that lands exactly on lot_min is approved, not rejected."""
    # size_units/contract_size = exactly 0.01 lots.
    risk_capital_inr = 0.01 * 100.0 * _RATE
    lots, reason = size_trade_lots(
        risk_capital_inr, _RATE, 1.0,
        100.0, 0.01, 0.01, 10.0,
    )
    assert reason is None
    assert lots == pytest.approx(0.01)


# ── instrument_spec / has_instrument_spec — strict, fail-closed ─────────────────

def test_instrument_spec_returns_declared_values():
    specs = {"XAUUSD": _XAUUSD_SPEC}
    spec = instrument_spec(specs, "XAUUSD")
    assert spec == _XAUUSD_SPEC

def test_instrument_spec_raises_for_undeclared_instrument():
    with pytest.raises(ConfigKeyMissingError):
        instrument_spec({"XAUUSD": _XAUUSD_SPEC}, "EURUSD")

def test_instrument_spec_raises_for_empty_specs():
    with pytest.raises(ConfigKeyMissingError):
        instrument_spec(None, "XAUUSD")

def test_instrument_spec_raises_for_incomplete_entry():
    with pytest.raises(ConfigKeyMissingError):
        instrument_spec({"XAUUSD": {"contract_size": 100.0}}, "XAUUSD")

def test_has_instrument_spec_true_for_complete_entry():
    assert has_instrument_spec({"XAUUSD": _XAUUSD_SPEC}, "XAUUSD") is True

def test_has_instrument_spec_false_for_undeclared():
    assert has_instrument_spec({"XAUUSD": _XAUUSD_SPEC}, "EURUSD") is False

def test_has_instrument_spec_false_for_none():
    assert has_instrument_spec(None, "XAUUSD") is False


# ── legacy_oz_size_units — the PRE-D11 backtest fallback, unchanged math ────────

def test_legacy_oz_size_units_is_plain_division():
    assert legacy_oz_size_units(500.0, 2.0) == pytest.approx(250.0)


# ── usd_quote_pnl_inr — the money identity both rails book through ──────────────

def test_usd_quote_pnl_inr_identity():
    # $2/oz move * 100 oz/lot * 0.5 lots * 84 INR/USD = 8400 INR.
    assert usd_quote_pnl_inr(2.0, 100.0, 0.5, 84.0) == pytest.approx(8400.0)

def test_usd_quote_pnl_inr_zero_move_is_zero():
    assert usd_quote_pnl_inr(0.0, 100.0, 1.0, 84.0) == pytest.approx(0.0)

def test_usd_quote_pnl_inr_negative_move_is_a_loss():
    assert usd_quote_pnl_inr(-1.5, 100.0, 0.1, 84.0) == pytest.approx(-1.5 * 100.0 * 0.1 * 84.0)
