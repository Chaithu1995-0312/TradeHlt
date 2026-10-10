# tests/test_config_validator_gates.py
"""
ConfigValidator quality gates: expectancy is a HARD gate, and a month-sized
validation window uses min_trades_per_month instead of min_trades_per_instrument.
Runs from the repo root (the validator reads configs/production/ at import).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_layer import config_validator as cv


def _res(trades=20, exp=0.2, dd=0.05, wr=0.5):
    return {
        "score": 0.5, "trades": trades, "win_rate": wr, "expectancy_rr": exp,
        "max_drawdown": dd, "total_pnl_rr": exp * trades, "error": None,
    }


def _gates(res, window="full"):
    metrics = {"final_score": 0.5, "mean_score": 0.5, "consistency_penalty": 0.0,
               "total_trades": res["trades"], "max_drawdown_across": res["max_drawdown"]}
    return cv._run_quality_gates({"XAUUSD": res}, metrics, {}, window=window)


def test_config_values():
    assert cv._GATE_MIN_EXPECTANCY == 0.0
    assert cv._GATE_MIN_TRADES_PER_MONTH == 4
    assert cv._GATE_MIN_TRADES_PER_INSTRUMENT == 10


def test_negative_expectancy_is_hard_reject():
    decision, hard, _ = _gates(_res(exp=-0.05))
    assert decision == "REJECT"
    assert any("expectancy" in h for h in hard)


def test_buggy_engine_expectancy_rejected():
    decision, hard, _ = _gates(_res(trades=12, exp=-0.867, dd=0.116))
    assert decision == "REJECT"


def test_zero_expectancy_passes():
    decision, hard, _ = _gates(_res(exp=0.0))
    assert decision == "APPROVE" and hard == []


def test_expectancy_no_longer_a_soft_warning():
    _, _, warnings = _gates(_res(exp=-0.3))
    assert not any("expectancy" in w for w in warnings)


def test_full_window_needs_ten_trades():
    assert _gates(_res(trades=9))[0] == "REJECT"
    assert _gates(_res(trades=10))[0] == "APPROVE"


def test_month_window_needs_four_trades():
    assert _gates(_res(trades=3), window="month")[0] == "REJECT"
    assert _gates(_res(trades=4), window="month")[0] == "APPROVE"


def test_four_trades_still_fail_full_window():
    decision, hard, _ = _gates(_res(trades=4), window="full")
    assert decision == "REJECT" and any("minimum is 10" in h for h in hard)


def test_invalid_window_raises():
    with pytest.raises(ValueError):
        _gates(_res(), window="week")
    with pytest.raises(ValueError):
        cv.ConfigValidator.validate(params={}, csv_paths={"X": "x.csv"}, window="week")


def _write_csv(path, days):
    rows = ["timestamp,open,high,low,close,volume"]
    for d in range(days + 1):
        rows.append(f"2025-07-{d + 1:02d} 01:00:00,100,101,99,100.5,10")
    path.write_text("\n".join(rows) + "\n")


def test_csv_span_days(tmp_path):
    p = tmp_path / "XAUUSD_M15.csv"
    _write_csv(p, 10)
    assert cv._csv_span_days(str(p)) == pytest.approx(10.0)


def test_month_window_rejects_long_span(tmp_path):
    p = tmp_path / "XAUUSD_M15.csv"
    _write_csv(p, 30)   # ~30 days: allowed
    assert cv._csv_span_days(str(p)) <= cv._MONTH_WINDOW_MAX_DAYS
    q = tmp_path / "long.csv"
    rows = ["timestamp,open,high,low,close,volume",
            "2025-01-01 01:00:00,100,101,99,100.5,10",
            "2025-07-01 01:00:00,100,101,99,100.5,10"]
    q.write_text("\n".join(rows) + "\n")
    report = cv.ConfigValidator.validate(
        params={"body_ratio_min": 0.65}, csv_paths={"XAUUSD": str(q)}, window="month",
    )
    assert report["decision"] == "REJECT"
    assert any("month window declared" in h for h in report["hard_failures"])
