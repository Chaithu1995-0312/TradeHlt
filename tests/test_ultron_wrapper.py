"""
tests/test_ultron_wrapper.py

Tests for core/ultron_risk_gate_wrapper.py — UltronRiskGateWrapper.

SR-1 compliance: the real gate is ALWAYS called.
"""

import sys
import os
import copy
import pytest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config_layer.strict_config import ConfigKeyMissingError
from core.ultron_risk_gate_wrapper import UltronRiskGateWrapper

# EPIC-84 STORY-84.2: regime_factors is the declared ultron_risk_gate.regime_factors mapping
# (active-config values) — no in-code default table.
_FACTORS = {"trend": 1.0, "range": 0.8, "neutral": 0.6, "uncertain": 0.5}


def _make_gate(decision="approve"):
    """Create a mock gate that returns a standardised response."""
    gate = MagicMock()
    gate.evaluate.return_value = {
        "decision":            decision,
        "execution_id":        "X001",
        "final_position_size": 1.0 if decision == "approve" else 0.0,
        "risk_reason":         "ok" if decision == "approve" else "rr_too_low",
        "allowed_risk_pct":    1.0,
        "portfolio_state":     {"total_risk": 0.0, "open_positions": 0},
    }
    return gate


def _trade(risk_percent=1.0):
    return {
        "risk_percent":  risk_percent,
        "rr_ratio":      2.0,
        "entry_price":   100.0,
        "stop_loss":      98.0,
        "execution_id":  "X001",
    }


def _portfolio():
    return {
        "account_balance":      10_000.0,
        "total_open_risk_pct":  0.0,
        "trades_today":         0,
        "daily_loss_pct":       0.0,
        "open_positions":       0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Test 12: Gate is ALWAYS called (SR-1 compliance)
# ──────────────────────────────────────────────────────────────────────────────

def test_wrapper_always_calls_through_to_gate():
    gate    = _make_gate()
    wrapper = UltronRiskGateWrapper(gate, regime_factors=_FACTORS)

    result = wrapper.evaluate(_trade(), _portfolio(), regime="trend")

    gate.evaluate.assert_called_once()
    assert result["decision"] == "approve"


def test_wrapper_calls_gate_on_rejection_too():
    gate    = _make_gate(decision="reject")
    wrapper = UltronRiskGateWrapper(gate, regime_factors=_FACTORS)

    result = wrapper.evaluate(_trade(), _portfolio(), regime="range")

    gate.evaluate.assert_called_once()
    assert result["decision"] == "reject"


# ──────────────────────────────────────────────────────────────────────────────
# Test 13: risk_percent is scaled correctly by regime
# ──────────────────────────────────────────────────────────────────────────────

def test_wrapper_scales_risk_for_range_regime():
    captured = {}

    class CapturingGate:
        def evaluate(self, trade, portfolio):
            captured["risk_percent"] = trade["risk_percent"]
            return {"decision": "approve", "execution_id": "X",
                    "final_position_size": 1.0, "risk_reason": "ok",
                    "allowed_risk_pct": 1.0, "portfolio_state": {}}

    wrapper = UltronRiskGateWrapper(CapturingGate(), regime_factors={"range": 0.8})
    wrapper.evaluate(_trade(risk_percent=1.0), _portfolio(), regime="range")
    assert abs(captured["risk_percent"] - 0.8) < 1e-9


def test_wrapper_no_scaling_for_trend_regime():
    captured = {}

    class CapturingGate:
        def evaluate(self, trade, portfolio):
            captured["risk_percent"] = trade["risk_percent"]
            return {"decision": "approve", "execution_id": "X",
                    "final_position_size": 1.0, "risk_reason": "ok",
                    "allowed_risk_pct": 1.0, "portfolio_state": {}}

    wrapper = UltronRiskGateWrapper(CapturingGate(), regime_factors={"trend": 1.0})
    wrapper.evaluate(_trade(risk_percent=2.0), _portfolio(), regime="trend")
    assert abs(captured["risk_percent"] - 2.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
# Test 14: caller's trade dict is NOT mutated
# ──────────────────────────────────────────────────────────────────────────────

def test_wrapper_does_not_mutate_caller_trade_dict():
    gate    = _make_gate()
    wrapper = UltronRiskGateWrapper(gate, regime_factors=_FACTORS)
    trade   = _trade(risk_percent=1.5)
    original_risk = trade["risk_percent"]

    wrapper.evaluate(trade, _portfolio(), regime="range")

    assert trade["risk_percent"] == original_risk, \
        "Wrapper must not mutate the caller's trade dict"


# ──────────────────────────────────────────────────────────────────────────────
# Test: Result schema is gate's output verbatim (no extra fields)
# ──────────────────────────────────────────────────────────────────────────────

def test_wrapper_returns_gate_result_verbatim():
    gate_response = {
        "decision":            "approve",
        "execution_id":        "X001",
        "final_position_size": 1.5,
        "risk_reason":         "ok",
        "allowed_risk_pct":    1.0,
        "portfolio_state":     {"total_risk": 0.5, "open_positions": 1},
        "custom_field":        "should_be_preserved",
    }
    gate = MagicMock()
    gate.evaluate.return_value = gate_response

    wrapper = UltronRiskGateWrapper(gate, regime_factors=_FACTORS)
    result  = wrapper.evaluate(_trade(), _portfolio(), regime="trend")

    assert result == gate_response


# ──────────────────────────────────────────────────────────────────────────────
# Test: Unknown regime defaults to factor=1.0 (no scaling)
# ──────────────────────────────────────────────────────────────────────────────

def test_unknown_regime_uses_factor_one():
    captured = {}

    class CapturingGate:
        def evaluate(self, trade, portfolio):
            captured["risk_percent"] = trade["risk_percent"]
            return {"decision": "approve", "execution_id": "X",
                    "final_position_size": 1.0, "risk_reason": "ok",
                    "allowed_risk_pct": 1.0, "portfolio_state": {}}

    wrapper = UltronRiskGateWrapper(CapturingGate(), regime_factors=_FACTORS)
    # "alien_regime" not in the declared factors → factor 1.0 (identity; KEPT, see L-B report)
    wrapper.evaluate(_trade(risk_percent=1.0), _portfolio(), regime="alien_regime")
    assert abs(captured["risk_percent"] - 1.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
# EPIC-84 STORY-84.2: strict config + per-trade missing values
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_regime_factors_raises():
    """Rewritten default: omitting regime_factors no longer falls back to a code table."""
    with pytest.raises(ConfigKeyMissingError) as ei:
        UltronRiskGateWrapper(_make_gate(), regime_factors=None)
    assert ei.value.missing == ("regime_factors",)
    assert ei.value.section == "ultron_risk_gate"


def test_missing_risk_percent_forwarded_unscaled_and_real_gate_rejects():
    """risk_percent absent is NOT invented as 0.0: the copy reaches the real gate without it
    and the gate REJECTs with config_key_missing:trade.risk_percent (SR-1: wrapper never rejects)."""
    from core.ultron_risk_gate import UltronRiskGate
    captured = {}

    class Spy(UltronRiskGate):
        def evaluate(self, trade, portfolio_state):
            captured["has_risk"] = "risk_percent" in trade
            return super().evaluate(trade, portfolio_state)

    gate = Spy({
        "disabled": False, "max_risk_per_trade_pct": 1.0, "max_portfolio_risk_pct": 5.0,
        "max_trades_per_day": 10, "max_daily_loss_pct": 3.0, "min_rr_ratio": 1.5,
        "spread_pips": 0.0, "slippage_pips": 0.0, "pip_size": 0.0001, "min_sl_pips": 0.0,
    })
    gate.reset_kill_switch()
    try:
        trade = _trade()
        del trade["risk_percent"]
        result = UltronRiskGateWrapper(gate, regime_factors=_FACTORS).evaluate(
            trade, _portfolio(), regime="range",
        )
        assert captured["has_risk"] is False
        assert result["decision"] == "reject"
        assert result["risk_reason"] == "config_key_missing:trade.risk_percent"
    finally:
        gate.reset_kill_switch()
