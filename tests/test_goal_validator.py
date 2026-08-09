"""
test_goal_validator.py — Goal Layer comparator (GoalValidator/GoalReport).

Run: python -m pytest tests/test_goal_validator.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.goal_schema import GoalSpec
from config_layer.goal_validator import GoalReport, GoalValidator


def _spec(enforce: bool = False) -> GoalSpec:
    return GoalSpec.from_prod_config({
        "goal_id": "G001",
        "enforce": enforce,
        "trades_per_month": {"min": 20, "max": 80},
        "avg_rr": {"min": 2.0},
        "win_rate": {"min": 0.35},
        "max_drawdown_pct": {"max": 0.10},
        "expectancy_r": {"min": 0.20},
    })


def _status(report: GoalReport, name: str) -> str:
    return next(c["status"] for c in report.criteria if c["name"] == name)


def test_disabled_spec_is_pass_noop():
    r = GoalValidator.evaluate({"win_rate": 0.0}, spec=GoalSpec.disabled())
    assert r.enabled is False
    assert r.decision == "PASS"
    assert r.criteria == []


def test_all_targets_met_passes():
    r = GoalValidator.evaluate({
        "trades_per_month": 40.0, "avg_rr": 2.5, "win_rate": 0.5,
        "max_drawdown_pct": 0.05, "expectancy_r": 0.3,
    }, spec=_spec())
    assert r.decision == "PASS"
    assert r.failed_criteria == []


def test_program1_reality_fails_frequency_and_expectancy():
    # The measured Program-1 reality: ~0.8 trades/month, negative E[R].
    r = GoalValidator.evaluate({
        "trades_per_month": 0.8, "win_rate": 0.40,
        "max_drawdown_pct": 0.03, "expectancy_r": -0.14,
    }, spec=_spec())
    assert r.decision == "FAIL"
    assert "trades_per_month_min" in r.failed_criteria
    assert "expectancy_r_min" in r.failed_criteria
    # win_rate / drawdown still pass; max-frequency still passes.
    assert _status(r, "win_rate_min") == "PASS"
    assert _status(r, "max_drawdown_pct_max") == "PASS"


def test_missing_metric_is_skip_not_fail():
    # avg_rr not supplied → SKIP, never FAIL (config_validator subset case).
    r = GoalValidator.evaluate({
        "trades_per_month": 40.0, "win_rate": 0.5,
        "max_drawdown_pct": 0.05, "expectancy_r": 0.3,
    }, spec=_spec())
    assert _status(r, "avg_rr_min") == "SKIP"
    assert r.decision == "PASS"            # skip does not fail the report


def test_gap_sign_convention():
    # gap is positive when satisfied with margin, for both >= and <= comparators.
    r = GoalValidator.evaluate({
        "win_rate": 0.45,        # >= 0.35  → gap +0.10
        "max_drawdown_pct": 0.04,  # <= 0.10 → gap +0.06
        "expectancy_r": 0.10,    # >= 0.20  → gap -0.10 (FAIL)
    }, spec=_spec())
    wr = next(c for c in r.criteria if c["name"] == "win_rate_min")
    dd = next(c for c in r.criteria if c["name"] == "max_drawdown_pct_max")
    exp = next(c for c in r.criteria if c["name"] == "expectancy_r_min")
    assert wr["gap"] == 0.10 and wr["status"] == "PASS"
    assert dd["gap"] == 0.06 and dd["status"] == "PASS"
    assert exp["gap"] == -0.10 and exp["status"] == "FAIL"


def test_enforced_flag_reflects_spec():
    assert GoalValidator.evaluate({}, spec=_spec(enforce=False)).enforced is False
    assert GoalValidator.evaluate({}, spec=_spec(enforce=True)).enforced is True


def test_to_dict_is_stable_shape():
    d = GoalValidator.evaluate({"win_rate": 0.5}, spec=_spec()).to_dict()
    assert set(d) == {"enabled", "enforced", "goal_id", "decision", "criteria"}
    assert d["goal_id"] == "G001"
