"""
test_goal_schema.py — Goal Layer schema (GoalSpec) loading + fail-soft contract.

Run: python -m pytest tests/test_goal_schema.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer import goal_schema
from config_layer.goal_schema import GoalSpec, load_goal_spec


_GOAL_SECTION = {
    "goal_id": "G001",
    "enforce": False,
    "trades_per_month": {"min": 20, "target": 40, "max": 80},
    "avg_rr": {"min": 2.0},
    "win_rate": {"min": 0.35},
    "max_drawdown_pct": {"max": 0.10},
    "risk_per_trade": {"target": 0.005},
    "expectancy_r": {"min": 0.20},
    "timeframe": {"execution": "M15", "structure": "H1"},
    "instruments": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "constraints": {"reaction_only": True, "human_execution": True, "no_prediction": True},
}


def test_from_prod_config_parses_all_fields():
    spec = GoalSpec.from_prod_config(_GOAL_SECTION)
    assert spec.enabled is True
    assert spec.goal_id == "G001"
    assert spec.enforce is False
    assert spec.trades_per_month_min == 20.0
    assert spec.trades_per_month_max == 80.0
    assert spec.trades_per_month_target == 40.0
    assert spec.avg_rr_min == 2.0
    assert spec.win_rate_min == 0.35
    assert spec.max_drawdown_pct_max == 0.10
    assert spec.expectancy_r_min == 0.20
    assert spec.timeframe_execution == "M15"
    assert spec.timeframe_structure == "H1"
    assert spec.instruments == ("BTCUSDT", "ETHUSDT", "BNBUSDT")
    assert spec.reaction_only is True
    assert spec.no_prediction is True


def test_partial_goal_allows_undeclared_bounds():
    # A goal that only declares win_rate leaves every other bound None.
    spec = GoalSpec.from_prod_config({"goal_id": "G_partial", "enforce": True,
                                      "win_rate": {"min": 0.5}})
    assert spec.enabled is True
    assert spec.enforce is True
    assert spec.win_rate_min == 0.5
    assert spec.avg_rr_min is None
    assert spec.trades_per_month_min is None


def test_disabled_spec_is_advisory_off():
    spec = GoalSpec.disabled()
    assert spec.enabled is False
    assert spec.enforce is False
    assert spec.trades_per_month_min is None


def test_absent_section_fail_soft(monkeypatch):
    # F-018 contract: a lagging config without a `goal` section must NOT raise.
    import config_layer.production_config as pc

    def _raise(section, version=None):
        raise RuntimeError(f"Section '{section}' not found")

    monkeypatch.setattr(pc, "get_prod_section", _raise)
    spec = load_goal_spec()
    assert spec.enabled is False           # disabled, not an exception


def test_present_but_malformed_fails_fast():
    # Missing the mandatory goal_id → fail-fast (real misconfiguration).
    with pytest.raises(KeyError, match="goal_id"):
        GoalSpec.from_prod_config({"enforce": False})


def test_present_range_missing_subbound_fails_fast():
    # A declared range key with no expected sub-bound is malformed → fail-fast.
    with pytest.raises(KeyError, match="avg_rr"):
        GoalSpec.from_prod_config({"goal_id": "x", "enforce": False, "avg_rr": {}})


def test_active_config_loads_g001():
    # The real active production config carries the G001 goal section.
    spec = load_goal_spec()
    assert spec.enabled is True
    assert spec.goal_id == "G001"
    assert spec.enforce is False           # advisory by default
